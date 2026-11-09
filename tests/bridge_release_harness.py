"""R1-Harness: echter Live-Lauf -> Brücke (UART-pty oder lokales TLS) -> Windows-Kern -> Fake-COM.

Linux-Nachweis ohne Hardware: ``/dev/ttyAMA0`` wird nie geöffnet (der
injizierte Opener öffnet ein Pseudo-Terminal), keine Kamera, kein Dienst.
Das ist **kein** Windows-, Treiber- oder GSVmulti-Nachweis. Publish- und
COM-Zeit stammen hier aus derselben Prozessuhr; nur deshalb ist die
Differenz in diesem Harness eine zulässige Latenzangabe. Mit
``bytes_per_s`` wird die Kabelstrecke auf eine Baudrate gedrosselt (pty
selbst kennt keine Baudrate).

Aufruf mit ``PYTHONPATH=src:windows/bridge/src``.
"""
from __future__ import annotations

import asyncio
import json
import os
import select
import statistics
import threading
import time
import tty
from pathlib import Path
from types import SimpleNamespace

from dispread_bridge_app.connection import ConnectionManager
from dispread_bridge_app.credentials import CredentialStore
from dispread_bridge_app.delivery_journal import DeliveryJournal
from dispread_bridge_app.worker import BridgeWorker
from dotmatrix_helpers import QUAD, embed, synthetic_reader

from dispread.bridge.discovery import TailscaleStatus
from dispread.bridge.hub import BridgeHub
from dispread.bridge.pairing import PairingStore
from dispread.bridge.publisher import PairedOutputPublisher
from dispread.bridge.resources import SerialPortLease
from dispread.bridge.types import BridgeProfile
from dispread.detect.manual_roi import ManualRoiLocator
from dispread.frames import Frame
from dispread.live.session import LiveSession
from dispread.records import TimeBaseKind, Timestamp, ValueRecord
from dispread.sink.protocol.userdefined import UserDefinedFormatter as DirectFormatter

CLIENT_ID = 'r1-client'
UART_115200_BYTES_PER_S = 115200 / 10  # 8N1: zehn Bitzeiten je Byte


class TestProtector:
    """Prozesslokaler Testtresor; ausdrücklich kein DPAPI-Nachweis."""
    __test__ = False

    def __init__(self):
        self.values = {}

    def protect(self, value):
        import secrets
        key = secrets.token_bytes(32)
        self.values[key] = value
        return key

    def unprotect(self, value):
        return self.values[value]


class PtyCable:
    """Zwei pty-Paare mit Relais als „Nullmodemkabel“; beide Enden sind pySerial-Ports."""

    def __init__(self, bytes_per_s=None):
        self.bytes_per_s = bytes_per_s
        self._pairs = [os.openpty(), os.openpty()]
        for _master, slave in self._pairs:
            tty.setraw(slave)
        self.pi_path = os.ttyname(self._pairs[0][1])
        self.win_path = os.ttyname(self._pairs[1][1])
        self.bytes = {'pi_to_win': 0, 'win_to_pi': 0}
        self._stop = threading.Event()
        self._threads = [
            threading.Thread(target=self._relay, args=(self._pairs[0][0], self._pairs[1][0], 'pi_to_win'),
                             daemon=True, name='pty-pi-win'),
            threading.Thread(target=self._relay, args=(self._pairs[1][0], self._pairs[0][0], 'win_to_pi'),
                             daemon=True, name='pty-win-pi'),
        ]
        for thread in self._threads:
            thread.start()

    def _relay(self, source, target, direction):
        due = time.monotonic()
        while not self._stop.is_set():
            ready, _, _ = select.select([source], [], [], .05)
            if not ready:
                continue
            try:
                chunk = os.read(source, 4096)
            except OSError:
                time.sleep(.005)  # Gegenseite noch nicht geöffnet / gerade geschlossen
                continue
            if self.bytes_per_s:
                # Auslieferung erst nach der Übertragungszeit dieser Bytes.
                due = max(due, time.monotonic()) + len(chunk) / self.bytes_per_s
                delay = due - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
            view = memoryview(chunk)
            while view and not self._stop.is_set():
                try:
                    view = view[os.write(target, view):]
                except BlockingIOError:
                    time.sleep(.001)
                except OSError:
                    break
            self.bytes[direction] += len(chunk)

    def close(self):
        self._stop.set()
        for thread in self._threads:
            thread.join(1)
        for master, slave in self._pairs:
            for fd in (master, slave):
                try:
                    os.close(fd)
                except OSError:
                    pass


class PacedOwner:
    """Kamera-Ersatz mit fester Bildrate: liefert wie eine Kamera immer das jüngste Bild."""

    source_id = 'paced'

    def __init__(self, rate_hz, *, hold_frames, values=10):
        self.rate_hz, self.hold = rate_hz, hold_frames
        self.images = [embed(f'+ 1.{2340 + index:04d} ') for index in range(values)]
        self.t0 = None
        self.delivered = 0

    def start_clock(self):
        self.t0 = time.monotonic()

    def wait_newer(self, after, timeout):
        if self.t0 is None:
            time.sleep(min(timeout, .01))
            return None
        due = self.t0 + after / self.rate_hz
        now = time.monotonic()
        if due - now > timeout:
            time.sleep(timeout)
            return None
        if due > now:
            time.sleep(due - now)
        sequence = max(after + 1, int((time.monotonic() - self.t0) * self.rate_hz) + 1)
        self.delivered += 1
        image = self.images[((sequence - 1) // self.hold) % len(self.images)]
        stamp = Timestamp(int((self.t0 + (sequence - 1) / self.rate_hz) * 1e9), TimeBaseKind.V4L2_MONOTONIC)
        return sequence, Frame(frame_sequence=sequence, image=image, capture_timestamp=stamp, source_id='paced')

    def status(self):
        return {'running': True, 'error': None, 'frames': self.delivered, 'gaps': 0,
                'source': {'device': '/dev/paced-test'}}


class RecordingJournal(DeliveryJournal):
    current = None

    def begin_attempt(self, pi_id, run_id, frame_sequence, barrier_id, payload):
        attempt = super().begin_attempt(pi_id, run_id, frame_sequence, barrier_id, payload)
        self.current = frame_sequence
        return attempt


class RecordingCom:
    def __init__(self, journal):
        self.journal, self.writes, self.closed = journal, [], False

    def write(self, payload):
        self.writes.append((self.journal.current, time.monotonic_ns(), bytes(payload)))
        return len(payload)

    def reset_output_buffer(self):
        pass

    def close(self):
        self.closed = True


class TlsServer:
    """Echte Pi-Routen mit TLS in einem eigenen Ereignisschleifen-Thread."""

    def __init__(self, identity, hub, store):
        self.identity, self.hub, self.store = identity, hub, store
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True, name='r1-tls')
        self.thread.start()
        self.port = asyncio.run_coroutine_threadsafe(self._start(), self.loop).result(10)

    async def _start(self):
        from aiohttp import web

        from dispread.bridge.routes import add_bridge_routes
        app = web.Application()
        add_bridge_routes(app, self.identity, self.store, self.hub, lambda request: True)
        self.runner = web.AppRunner(app, access_log=None, shutdown_timeout=.2)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', 0, ssl_context=self.identity.tls_context())
        await site.start()
        return site._server.sockets[0].getsockname()[1]

    def close(self):
        asyncio.run_coroutine_threadsafe(self.runner.cleanup(), self.loop).result(10)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)


class PtyDevices:
    def __init__(self, port):
        self.item = SimpleNamespace(port=port, pnp_error=0, identity=('pty', 'R1'), serial='R1',
                                    is_supported=True, instance_id='pty-r1')

    def inventory(self):
        return (self.item,)

    def select_supported(self, identity=None):
        return self.item


def wait_for(predicate, timeout=10, what='condition', describe=None):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError(f'{what} not reached: {describe() if describe else ""}')
        time.sleep(.01)


def _percentile(values, fraction):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))]


def _session(tmp, owner, hub, run_id, *, transport, ack):
    from test_live_session import _files

    profile_path, config = _files(tmp)
    session = LiveSession(
        owner, profile_path, config, tmp / 'run',
        reader_factory=lambda _p, _s, **kw: synthetic_reader(),
        locator_factory=lambda _ref, quad: ManualRoiLocator(tuple(tuple(p) for p in QUAD)),
        output={'transport': transport, **({'acknowledge_unaccepted': True} if ack else {})},
        output_factory=lambda cfg, out_dir, **kw: PairedOutputPublisher(cfg, out_dir, hub=hub, run_id=run_id, **kw),
    )
    session.bridge_run_id = run_id
    return session


def run_release(tmp: Path, identity, *, transport: str, rate_hz: float, duration_s: float, ack: bool = True,
                bytes_per_s: float | None = None, hold_frames: int = 10) -> dict:
    """Ein vollständiger Lauf; liefert Messgrößen und Rohbelege für die Prüfungen."""
    tmp = Path(tmp)
    store = PairingStore(tmp / 'pairing')
    cable = server = None
    mode = 'uart' if transport == 'uart' else 'network'
    if mode == 'uart':
        cable = PtyCable(bytes_per_s)
        opened = []

        def opener(port, **kwargs):
            # Der Hub verlangt den Datenport; geöffnet wird ausschließlich das pty.
            opened.append(port)
            import serial
            return serial.Serial(cable.pi_path, **kwargs)
        hub = BridgeHub(identity.pi_id, tmp / 'pi-audit', identity=identity, pairing_store=store,
                        serial_opener=opener, port_leases=SerialPortLease(tmp / 'locks'))
        hub.prepare_uart()
        wait_for(lambda: hub.status()['uart_state'] == 'listening', what='UART listening')
        endpoints, devices = (), PtyDevices(cable.win_path)
    else:
        hub = BridgeHub(identity.pi_id, tmp / 'pi-audit', identity=identity, pairing_store=store)
        server = TlsServer(identity, hub, store)
        endpoints, devices = (f'https://127.0.0.1:{server.port}',), None
    profile = BridgeProfile(1, identity.pi_id, 'R1', identity.certificate_pem, identity.fingerprint,
                            endpoints, 2, store.create_offer(mode, CLIENT_ID))
    credentials = CredentialStore(tmp / 'windows-credentials', protector=TestProtector())
    manager = ConnectionManager(profile, CLIENT_ID, credentials, devices,
                                network_diagnostics=lambda: TailscaleStatus('running'))
    events, readiness = [], []
    run_id = 'r1-' + os.urandom(6).hex()
    session = worker = None
    published = {}
    try:
        with RecordingJournal(tmp / 'delivery.sqlite') as journal:
            com = RecordingCom(journal)
            worker = BridgeWorker(manager, lambda: com, journal, events.append)
            manager.set_worker(worker)
            manager.connect(mode)
            wait_for(lambda: manager.snapshot().peer == 'authenticated', what='authenticated')
            worker.start()
            wait_for(lambda: worker.status.output_ready, what='worker ready')
            readiness.append(('before_run', manager.snapshot()))
            owner = PacedOwner(rate_hz, hold_frames=hold_frames)
            hub.reserve_real_run(run_id)
            session = _session(tmp, owner, hub, run_id, transport=transport, ack=ack)
            session.start()
            publisher = session._output
            original = publisher.publish

            def publish(record):
                published[record.frame_sequence] = time.monotonic_ns()
                original(record)
            publisher.publish = publish
            stop = threading.Event()
            reader = threading.Thread(target=session.run, args=(stop,), daemon=True, name='r1-live')
            owner.start_clock()
            reader.start()
            # Reservierung kommt vor der Bindung: kurz "blocked", dann der Freigabestand.
            expected = 'test_release' if ack else 'blocked'
            wait_for(lambda: manager.snapshot().output == expected and (worker.status.demo_only is not ack),
                     what='run readiness', describe=lambda: (manager.snapshot(), worker.status))
            readiness.append(('running', manager.snapshot(), worker.status))
            time.sleep(duration_s)
            stop.set()
            reader.join(5)
            time.sleep(.5)  # Restwert noch abholen lassen (Frischegrenze 1 s)
            readiness.append(('before_stop', manager.snapshot(), worker.status))
            session.stop()
            session = None
            hub.release_real_run(run_id)
            wait_for(lambda: manager.snapshot().output in ('output_off', 'ended'), what='run end readiness',
                     describe=lambda: (manager.snapshot(), worker.status, hub.status(), events[-3:]))
            readiness.append(('after_run', manager.snapshot(), worker.status))
            worker.stop()
            attempts = journal.attempts()
            writes = list(com.writes)
    finally:
        if session is not None:
            session.stop()
        if worker is not None:
            worker.stop()
        manager.disconnect()
        if server is not None:
            server.close()
        hub.close()
        if cable is not None:
            cable.close()
    run_dir = tmp / 'run'
    records = [json.loads(line) for line in (run_dir / 'records.jsonl').read_text().splitlines()]
    by_seq = {item['frame_sequence']: item for item in records}
    pi_events = [json.loads(line) for line in (run_dir / 'output.jsonl').read_text().splitlines()]
    session_json = json.loads((run_dir / 'session.json').read_text())
    valid = [item['frame_sequence'] for item in records if item['status'] == 'valid']
    written = {seq: t for seq, t, _payload in writes}
    latencies = [(t - published[seq]) / 1e6 for seq, t, _ in writes if seq in published]
    expected = {seq: DirectFormatter(prefix='%').format(ValueRecord.from_dict(by_seq[seq])) for seq, _, _ in writes}
    acks = [event for event in pi_events if event['event'] == 'ack']
    metrics = dict(
        transport=transport, rate_hz=rate_hz, duration_s=duration_s, ack=ack, bytes_per_s=bytes_per_s,
        frames=len(records), valid_published=len(valid), written=len(writes),
        lost_valid=len([seq for seq in valid if seq not in written]),
        invalid_written=len([seq for seq in written if by_seq[seq]['status'] != 'valid']),
        barriers_omitted=len([a for a in acks if a['outcome'] == 'omitted' and a['barrier_id'] is not None]),
        stale_skipped=len([e for e in pi_events if e['event'] == 'stale_skipped']),
        unconfirmed=len([e for e in pi_events if e['event'] == 'unconfirmed']),
        bytes_exact=all(payload == expected[seq] for seq, _, payload in writes),
        in_order=[seq for seq, _, _ in writes] == sorted(written),
        latency_ms=None if not latencies else dict(
            p50=round(statistics.median(latencies), 2), p95=round(_percentile(latencies, .95), 2),
            max=round(max(latencies), 2), n=len(latencies)),
        cable_bytes=None if cable is None else dict(cable.bytes),
    )
    return dict(metrics=metrics, writes=writes, attempts=attempts, records=records, pi_events=pi_events,
                session=session_json, readiness=readiness, events=events, opened=locals().get('opened'))


def barrier_order_holds(pi_events) -> bool:
    """Kein gültiger Wert wird angeboten, solange eine angebotene Barriere unquittiert ist."""
    pending = None
    for event in pi_events:
        if event['event'] == 'offered':
            if event['barrier_id'] is not None:
                pending = event['barrier_id']
            elif pending is not None:
                return False
        elif event['event'] == 'ack' and event['barrier_id'] == pending and event['outcome'] == 'omitted':
            pending = None
    return True
