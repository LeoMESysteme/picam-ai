"""B2-Harness: Vierkanal-Takt Ende zu Ende über die Brücke (UART-pty oder lokales TLS).

Pi: ``PairedOutputPublisher`` im Taktbetrieb (derselbe ``Ticker`` wie UART direkt)
-> ``BridgeHub`` -> UartListener auf pty bzw. TLS-WSS-Route -> Windows-Kern
(``ConnectionManager``/``BridgeWorker``/``BridgeSession``/``DeliveryJournal``)
-> Fake-COM. Keine Kamera, kein ``/dev/ttyAMA0``, kein Dienst, kein GSVmulti.

**Zeitraffer mit Gegendruck:** Die Pi-Taktuhr ist virtuell und rückt je Takt
genau eine Periode vor, sobald Windows abgeholt hat; Kamerazeitstempel und
Taktentscheid nutzen dieselbe Uhr. So sind Aussetzer und Staus exakt und vom
Lastzustand des geteilten Pi unabhängig. Transport und Journal laufen in
Echtzeit; die Latenz dieses Modus ist nur bedingt aussagekräftig, die
Echtzeitmessung (``realtime=True``) liefert sie sauber. Pi-Taktbeleg und
COM-Zeit stammen aus derselben Prozessuhr; nur deshalb ist die Differenz hier
eine zulässige Latenzangabe. Kein Windows-, Treiber- oder GSVmulti-Nachweis.

Aufruf mit ``PYTHONPATH=src:windows/bridge/src``.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import threading
import time
from pathlib import Path

from bridge_release_harness import (
    CLIENT_ID,
    PtyCable,
    PtyDevices,
    TestProtector,
    TlsServer,
    _percentile,
    wait_for,
)
from dispread_bridge_app.connection import ConnectionManager
from dispread_bridge_app.credentials import CredentialStore
from dispread_bridge_app.delivery_journal import DeliveryJournal
from dispread_bridge_app.worker import BridgeWorker

from dispread.bridge.discovery import TailscaleStatus
from dispread.bridge.hub import BridgeHub
from dispread.bridge.pairing import PairingStore
from dispread.bridge.protocol import TEST_RELEASE
from dispread.bridge.publisher import PairedOutputPublisher
from dispread.bridge.resources import SerialPortLease
from dispread.bridge.types import BridgeProfile
from dispread.gsv_transport import OutputConfig
from dispread.live.tick import Tick, nominal_unix_ns, tick_period_ns
from dispread.records import TimeBaseKind, Timestamp, ValueRecord, ValueStatus
from dispread.sink.protocol.userdefined_4ch import TickFormatter


class TickCom:
    """Fake-COM: jede Zeile mit Echtzeit. An einem Stau-Takt meldet der Schreibaufruf
    ``entered`` und hängt, bis ``release`` gesetzt ist (künstlicher Windows-Stau)."""

    def __init__(self, stalls=None):
        self.writes, self.closed = [], False
        self._stalls = dict(stalls or {})

    def write(self, payload):
        seq = int(payload.split(b';')[2])
        stall = self._stalls.pop(seq, None)
        if stall is not None:
            stall['entered'].set()
            stall['release'].wait(60)
        self.writes.append((time.monotonic_ns(), bytes(payload)))
        return len(payload)

    def reset_output_buffer(self):
        pass

    def close(self):
        self.closed = True


def _rig(tmp, identity, transport, bytes_per_s):
    store = PairingStore(tmp / 'pairing')
    cable = server = None
    mode = 'uart' if transport == 'uart' else 'network'
    if mode == 'uart':
        cable = PtyCable(bytes_per_s)

        def opener(port, **kwargs):
            import serial
            return serial.Serial(cable.pi_path, **kwargs)  # nie /dev/ttyAMA0
        hub = BridgeHub(identity.pi_id, tmp / 'pi-audit', identity=identity, pairing_store=store,
                        serial_opener=opener, port_leases=SerialPortLease(tmp / 'locks'))
        hub.prepare_uart()
        wait_for(lambda: hub.status()['uart_state'] == 'listening', what='UART listening')
        endpoints, devices = (), PtyDevices(cable.win_path)
    else:
        hub = BridgeHub(identity.pi_id, tmp / 'pi-audit', identity=identity, pairing_store=store)
        server = TlsServer(identity, hub, store)
        endpoints, devices = (f'https://127.0.0.1:{server.port}',), None
    profile = BridgeProfile(1, identity.pi_id, 'B2', identity.certificate_pem, identity.fingerprint,
                            endpoints, 2, store.create_offer(mode, CLIENT_ID))
    credentials = CredentialStore(tmp / 'windows-credentials', protector=TestProtector())
    manager = ConnectionManager(profile, CLIENT_ID, credentials, devices,
                                network_diagnostics=lambda: TailscaleStatus('running'))
    return hub, manager, mode, cable, server


def _record(frame, capture_ns, phase):
    """Synthetisches Kamerabild: unlesbare Phase 100..129, sonst gültig, Wert wechselt."""
    unreadable = 100 <= phase < 130
    text = f'{1.2 + (frame % 997) / 10000:.4f}'
    return ValueRecord(frame, Timestamp(capture_ns, TimeBaseKind.V4L2_MONOTONIC),
                       None if unreadable else float(text), 'mV/V',
                       ValueStatus.UNREADABLE if unreadable else ValueStatus.VALID, 1.0, 'b2', None, None,
                       raw_text=text, reject_reasons=('b2_phase',) if unreadable else ())


def run_ticks(tmp: Path, identity, *, transport: str, ticks: int = 6000, rate_hz: float = 10,
              realtime: bool = False, max_age_ms: int = 1000, frame_ms: float = 66.0,
              bytes_per_s: float | None = None, invalid_every: int = 600, jumps: dict | None = None,
              stalls: tuple = (2000, 4500), stall_ticks: int = 60) -> dict:
    """Ein Takt-Lauf mit ungültigen Phasen (``invalid_every``: unlesbar 100..129, dunkel
    300..319), Pi-Aussetzern (``jumps``: Takt -> zusätzlich übersprungene Perioden) und
    Windows-Staus (``stalls``: Takt, an dem COM hängt, bis ``stall_ticks`` weitere Takte
    erzeugt sind).

    ``realtime=False`` (Zeitraffer mit Gegendruck): Eine virtuelle Pi-Monotonuhr rückt
    je Takt genau eine Periode vor, sobald höchstens ein Takt wartet; Staus und
    Aussetzer sind damit exakt und lastunabhängig. ``realtime=True``: echter
    Taktthread mit Wanduhr (für Latenz), ohne Gegendruck.
    """
    tmp = Path(tmp)
    jumps = {1000: 3, 3000: 7, 5000: 1} if jumps is None else jumps
    period_ns = 1_000_000_000 / rate_hz
    stall_events = {seq: dict(entered=threading.Event(), release=threading.Event()) for seq in stalls}
    com = TickCom(stall_events)
    hub, manager, mode, cable, server = _rig(tmp, identity, transport, bytes_per_s)
    virtual = [time.monotonic_ns()]
    run_id = 'b2-' + os.urandom(6).hex()
    publisher = worker = None
    enqueued = {}
    stop = threading.Event()
    try:
        with DeliveryJournal(tmp / 'delivery.sqlite') as journal:
            events = []
            worker = BridgeWorker(manager, lambda: com, journal, events.append)
            manager.set_worker(worker)
            manager.connect(mode)
            wait_for(lambda: manager.snapshot().peer == 'authenticated', what='authenticated')
            worker.start()
            wait_for(lambda: worker.status.output_ready, what='worker ready')
            hub.reserve_real_run(run_id)
            publisher = PairedOutputPublisher(OutputConfig(transport=transport, max_frame_age_ms=max_age_ms),
                                              tmp / 'run', hub=hub, run_id=run_id, release=TEST_RELEASE,
                                              tick_rate_hz=rate_hz,
                                              tick_max_frame_age_ns=max_age_ms * 1_000_000)
            if not realtime:
                publisher._clock = lambda: virtual[0]     # Testnaht: virtuelle Pi-Taktuhr
                publisher._tick_thread_enabled = False    # der Treiber unten erzeugt die Takte
            publisher.drain_timeout_s = 5
            step = publisher.step_ticks

            def stepped():
                tick = step()
                if tick is not None:
                    enqueued[tick.seq] = time.monotonic_ns()
                return tick
            publisher.step_ticks = stepped
            publisher.start()
            ticker = publisher._ticker
            wait_for(lambda: manager.snapshot().output == 'test_release' and not worker.status.demo_only,
                     what='tick readiness', describe=lambda: (manager.snapshot(), worker.status))
            t_start = time.monotonic()
            if realtime:
                def feed():
                    frame = 0
                    while not stop.is_set():
                        now = time.monotonic_ns()
                        phase = int((now - ticker.start_ns) / period_ns) % invalid_every
                        if not 300 <= phase < 320:
                            frame += 1
                            publisher.publish(_record(frame, now - 20_000_000, phase))
                        stop.wait(frame_ms / 1000)
                feeder = threading.Thread(target=feed, daemon=True, name='b2-feeder')
                feeder.start()
                wait_for(lambda: ticker.stats()['seq'] >= ticks, timeout=ticks / rate_hz * 2 + 30,
                         what='tick count', describe=lambda: (publisher.tick_status(), worker.status))
                stop.set()
                feeder.join(2)
            else:
                _drive(publisher, ticker, virtual, period_ns, ticks, frame_ms, invalid_every, jumps,
                       stall_events, stall_ticks)
            publisher.stop()                     # Takt aus, Rest begrenzt abholen lassen, entbinden
            t_run = time.monotonic() - t_start
            pi_status = publisher.status()['tick']
            hub.release_real_run(run_id)
            # Gedrosselte Leitung (115 200 Baud) hat Rückstau: Laufende großzügig abwarten.
            wait_for(lambda: manager.snapshot().output in ('output_off', 'ended'), timeout=60, what='run end')
            worker_status = worker.status
            worker.stop()
            attempts = journal.tick_attempts()
            gaps = journal.tick_gaps(identity.pi_id, run_id)
    finally:
        stop.set()
        for stall in stall_events.values():
            stall['release'].set()
        if publisher is not None:
            publisher.stop()
        if worker is not None:
            worker.stop()
        manager.disconnect()
        if server is not None:
            server.close()
        hub.close()
        if cable is not None:
            cable.close()
    pi_events = [json.loads(line) for line in (tmp / 'run' / 'output.jsonl').read_text().splitlines()]
    return analyse(pi_events, com.writes, attempts, gaps, pi_status, worker_status, enqueued,
                   dict(transport=transport, mode='realtime' if realtime else 'virtual_backpressure',
                        rate_hz=rate_hz, max_age_ms=max_age_ms, bytes_per_s=bytes_per_s, wall_s=round(t_run, 1),
                        jumps=jumps, stalls=list(stalls), stall_ticks=stall_ticks,
                        cable_bytes=None if cable is None else dict(cable.bytes)))


def _drive(publisher, ticker, virtual, period_ns, ticks, frame_ms, invalid_every, jumps, stalls, stall_ticks):
    """Virtuelle Pi-Uhr: Bilder alle ``frame_ms``, je Takt eine Periode.

    Gegendruck (höchstens ein wartender Takt) außer während eines Staus: Dann
    entstehen ``stall_ticks`` weitere Takte, während COM hängt; alles, was dabei
    älter als das Fenster wird, verfällt auf dem Pi und wird auf Windows aufgefüllt.
    """
    frame, next_frame = 0, virtual[0]
    release_at = {}
    skip = 0
    period = tick_period_ns(ticker.rate_hz)
    while ticker.stats()['seq'] < ticks:
        if not release_at:
            wait_for(lambda: publisher.tick_status()['queued'] <= 1, timeout=30, what='queue drain',
                     describe=publisher.tick_status)
        target = ticker.stats()['seq'] + 1 + skip
        skip = 0
        deadline = ticker.start_ns + math.ceil(target * period)
        while next_frame <= deadline:                    # Bilder bis zum Taktzeitpunkt
            phase = int((next_frame - ticker.start_ns) / period_ns) % invalid_every
            if not 300 <= phase < 320:                   # dunkle Phase: kein Bild
                frame += 1
                publisher.publish(_record(frame, next_frame, phase))
            next_frame += int(frame_ms * 1_000_000)
        virtual[0] = deadline
        tick = publisher.step_ticks()
        assert tick is not None, publisher.tick_status()
        if jumps.get(tick.seq):
            # Pi unter Last: der nächste Taktentscheid kommt erst nach weiteren
            # Perioden; dazwischen liegende Takte werden verpasst (kein Aufholen).
            skip = jumps[tick.seq]
        for seq, stall in stalls.items():
            if seq in release_at:
                if tick.seq >= release_at[seq]:
                    stall['release'].set()               # Stau löst sich nach stall_ticks Takten
                    del release_at[seq]
            elif tick.seq >= seq and not stall['release'].is_set():
                wait_for(stall['entered'].is_set, timeout=30, what=f'stall {seq} entered')
                release_at[seq] = tick.seq + stall_ticks


def analyse(pi_events, writes, attempts, gaps, pi_status, worker_status, enqueued, setup):
    formatter = TickFormatter()
    start = next(e for e in pi_events if e['event'] == 'tick_start')
    origin, rate = start['origin_unix_ns'], setup['rate_hz']
    audited = {e['seq']: e for e in pi_events if e['event'] == 'tick'}
    acked = {e['seq']: e for e in pi_events if e['event'] == 'tick_ack'}
    lines = [(t, payload) for t, payload in writes]
    fields = [payload.decode('ascii').rstrip('\r\n').split(';') for _, payload in lines]
    seqs = [int(f[2]) for f in fields]
    kinds = {row.seq: row.kind for row in attempts if row.outcome == 'written'}
    fill_ok, tick_ok, fresh_ok = True, True, True
    max_age_ns = setup['max_age_ms'] * 1_000_000
    valid_frames = []
    for (_t, payload), seq in zip(lines, seqs, strict=True):
        nominal = nominal_unix_ns(origin, rate, seq)
        if kinds.get(seq) == 'tick':
            event = audited[seq]
            tick = Tick(seq, event['valid'], event['value_text'], event['time_unix_ns'], event['frame_sequence'])
            tick_ok &= payload == formatter.format_tick(tick)
            if tick.valid:
                valid_frames.append(tick.frame_sequence)
                period = nominal_unix_ns(origin, rate, seq + 1) - nominal
                # Bild erfasst vor dem Taktentscheid und jünger als die Altersgrenze.
                fresh_ok &= tick.time_unix_ns < nominal + period and nominal - tick.time_unix_ns < max_age_ns
        else:
            fill_ok &= (kinds.get(seq) == 'fill'
                        and payload == formatter.format_tick(Tick(seq, False, None, nominal, None)))
    n = pi_status['seq']
    filled = {seq for seq, kind in kinds.items() if kind == 'fill'}
    pi_written = {seq for seq, ack in acked.items() if ack['outcome'] == 'written'}
    missed_or_lost = set(range(1, n + 1)) - set(audited) | {
        seq for seq in audited if seq not in acked}
    latencies = [(t - enqueued[seq]) / 1e6 for (t, _), seq in zip(lines, seqs, strict=True)
                 if kinds.get(seq) == 'tick' and seq in enqueued]
    # Ohne die künstlichen Windows-Staus und den anschließenden Rückstau.
    stalled = {seq for start_seq in setup['stalls']
               for seq in range(start_seq, start_seq + 2 * setup['stall_ticks'])}
    steady = [(t - enqueued[seq]) / 1e6 for (t, _), seq in zip(lines, seqs, strict=True)
              if kinds.get(seq) == 'tick' and seq in enqueued and seq not in stalled]
    lost_reasons = {}
    for event in pi_events:
        if event['event'] == 'tick_lost':
            lost_reasons[event['reason']] = lost_reasons.get(event['reason'], 0) + event['count']
    return dict(
        **setup,
        ticks=n, lines=len(lines), lines_equal_ticks=len(lines) == n,
        sequence_complete=seqs == list(range(1, n + 1)),
        pi_total=pi_status['total'], pi_missed=pi_status['missed'], pi_valid=pi_status['valid'],
        pi_invalid=pi_status['invalid'], pi_offered=pi_status['offered'],
        pi_acknowledged=pi_status['acknowledged'], pi_unconfirmed=pi_status['unconfirmed'],
        pi_lost=pi_status['lost'], pi_lost_reasons=lost_reasons, pi_queued=pi_status['queued'],
        pi_accounted=pi_status['acknowledged'] + pi_status['unconfirmed'] + pi_status['lost']
        + pi_status['queued'] == pi_status['total'],
        filled=len(filled), filled_matches_pi=filled == missed_or_lost and pi_written == set(kinds) - filled,
        fill_bytes_exact=fill_ok, tick_bytes_exact=tick_ok,
        valid_lines=len(valid_frames), valid_unique=len(valid_frames) == len(set(valid_frames)),
        valid_frames_increasing=valid_frames == sorted(set(valid_frames)), valid_fresh=fresh_ok,
        unfilled_gaps=list(gaps),
        worker=dict(ticks_written=worker_status.ticks_written, ticks_invalid=worker_status.ticks_invalid,
                    ticks_filled=worker_status.ticks_filled, tick_disturbed=worker_status.tick_disturbed),
        latency_ms=_latency(latencies), latency_without_stalls_ms=_latency(steady),
    )


def _latency(values):
    """Pi-Takt auditiert und angeboten -> COM-Zeile geschrieben, Echtzeit in ms."""
    if not values:
        return None
    return dict(p50=round(statistics.median(values), 2), p99=round(_percentile(values, .99), 2),
                max=round(max(values), 2), n=len(values))


def run_session_ticks(tmp: Path, identity, *, transport: str, ack: bool = True, duration_s: float = 3.0) -> dict:
    """Echter LiveSession-Lauf (synthetische Bilder, echte Kette) mit ``format: '4ch'`` über die Brücke."""
    from bridge_release_harness import PacedOwner
    from dotmatrix_helpers import QUAD, synthetic_reader
    from test_live_session import _files

    from dispread.detect.manual_roi import ManualRoiLocator
    from dispread.live.session import LiveSession

    tmp = Path(tmp)
    com = TickCom()
    hub, manager, mode, cable, server = _rig(tmp, identity, transport, None)
    run_id = 'b2s-' + os.urandom(6).hex()
    session = worker = None
    try:
        with DeliveryJournal(tmp / 'delivery.sqlite') as journal:
            worker = BridgeWorker(manager, lambda: com, journal, lambda event: None)
            manager.set_worker(worker)
            manager.connect(mode)
            wait_for(lambda: manager.snapshot().peer == 'authenticated', what='authenticated')
            worker.start()
            wait_for(lambda: worker.status.output_ready, what='worker ready')
            hub.reserve_real_run(run_id)
            owner = PacedOwner(15, hold_frames=10)
            profile_path, config = _files(tmp)
            session = LiveSession(
                owner, profile_path, config, tmp / 'run',
                reader_factory=lambda _p, _s, **kw: synthetic_reader(),
                locator_factory=lambda _ref, quad: ManualRoiLocator(tuple(tuple(p) for p in QUAD)),
                output={'transport': transport, 'format': '4ch', 'rate_hz': 10,
                        **({'acknowledge_unaccepted': True} if ack else {})},
                output_factory=lambda cfg, out_dir, **kw: PairedOutputPublisher(cfg, out_dir, hub=hub,
                                                                                run_id=run_id, **kw))
            session.bridge_run_id = run_id
            session.start()
            stop = threading.Event()
            reader = threading.Thread(target=session.run, args=(stop,), daemon=True, name='b2-live')
            owner.start_clock()
            reader.start()
            expected = 'test_release' if ack else 'blocked'
            # Der Worker übernimmt den Freigabestand erst nach seinem nächsten Austausch.
            wait_for(lambda: manager.snapshot().output == expected and worker.status.demo_only is not ack,
                     what='run readiness', describe=lambda: (manager.snapshot(), worker.status))
            readiness = (manager.snapshot(), worker.status)
            time.sleep(duration_s)
            stop.set()
            reader.join(5)
            session.stop()
            session = None
            hub.release_real_run(run_id)
            wait_for(lambda: manager.snapshot().output in ('output_off', 'ended'), what='run end')
            worker_status = worker.status
            worker.stop()
            attempts = journal.tick_attempts()
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
    return dict(writes=com.writes, attempts=attempts, readiness=readiness, worker=worker_status,
                session=json.loads((run_dir / 'session.json').read_text()),
                records=[json.loads(line) for line in (run_dir / 'records.jsonl').read_text().splitlines()],
                pi_events=[json.loads(line) for line in (run_dir / 'output.jsonl').read_text().splitlines()])
