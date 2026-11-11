"""One Pi bridge owner, real-run reservation and bounded v2 state projection.

The registry lock protects metadata only. Audit operations use the existing
OutputState lock, with lease/run revalidation after acquiring it. Transport I/O
occurs outside both locks. UART is created only by explicit prepare_uart().
"""
from __future__ import annotations

import json
import math
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .output_state import RELEASE_BLOCK, OutputState
from .protocol import TICK_CAPABILITY, TICK_CAPABILITY_VERSION, _identifier, _transport, decode_v2, encode_v2
from .types import PeerHello

HEARTBEAT_INTERVAL_S = 1
LEASE_TIMEOUT_S = 5
DEMO_FINAL_GRACE_S = 2.0
#: B2: Ein Vierkanal-Takt-Lauf bietet nur Clients mit Taktfaehigkeit etwas an.
TICK_CLIENT_BLOCK = 'DUT-Ausgabe gesperrt: Brücken-App kennt den Vierkanal-Takt nicht (bitte aktualisieren)'


class BridgeOccupied(ValueError):
    """Bruecke ist durch einen Lauf oder Empfangstest belegt."""


@dataclass
class Lease:
    lease_id: str
    client_id: str
    transport: str
    run_id: str | None
    renewed_at: float
    #: Zuletzt per Hello/Idle angekuendigter Freigabestand (R1). Ein Record
    #: geht nur an einen Client, der den aktuellen Stand schon kennt.
    release: str | None = None
    #: B2: Client hat im Hello ``capabilities.tick == 1`` gemeldet.
    tick: bool = False


class BridgeHub:
    def __init__(self, pi_id: str, audit_root: Path, *, clock=time.monotonic,
                 identity=None, pairing_store=None, serial_opener=None, port_leases=None):
        _identifier(pi_id)
        self.pi_id, self.audit_root, self.clock = pi_id, Path(audit_root), clock
        self.identity, self.pairing_store = identity, pairing_store
        self.serial_opener, self.port_leases = serial_opener, port_leases
        self._lock = threading.RLock()
        self._lease = None
        self._run_id = None
        self._real_run = None
        self._state = None
        self._transport = None
        self._uart = None
        self._demo_stop = threading.Event()
        self._demo_thread = None
        self._closed = False

    @contextmanager
    def _output_guard(self):
        # Lock order is always OutputState -> registry. A changed snapshot is
        # retried by the caller; never wait for output I/O holding registry.
        with self._lock:
            state = self._state
        if state is None:
            yield None
        else:
            with state._lock:
                yield state

    def _release_locked(self, transport=None, lease=None):
        """Testfreigabe nur fuer den gebundenen echten Lauf und seinen Ausgabeweg.

        Die Freigabe kommt ausschliesslich aus dem vom Pi-Bediener bestaetigten
        Laufstart (OutputState.release), nie aus einer Client-Nachricht.
        """
        state = self._state
        if (state is None or state.demo or state.release is None or self._real_run != state.run_id
                or (transport is not None and self._transport not in (None, transport))):
            return None
        if state.tick_mode and lease is not None and not lease.tick:
            # Alte Clients sehen nie einen Takt (fail-closed, B2).
            return None
        return state.release

    def _block_locked(self, transport=None, lease=None):
        if self._release_locked(transport, lease) is not None:
            return None
        if self._release_locked(transport) is not None:
            return TICK_CLIENT_BLOCK
        return RELEASE_BLOCK if self._real_run or (self._state and not self._state.demo) else None

    def status(self):
        with self._lock:
            lease = self._lease
            release = self._release_locked()
            return dict(pi_id=self.pi_id, run_id=self._run_id, real_run=self._real_run is not None,
                        transport=lease.transport if lease else None,
                        connected=lease is not None and self.clock() - lease.renewed_at < LEASE_TIMEOUT_S,
                        uart_prepared=self._uart is not None and self._uart.state in ('opening', 'listening'),
                        uart_state=self._uart.state if self._uart else 'unprepared',
                        uart_error=self._uart.error if self._uart else None,
                        release_block=None if release else RELEASE_BLOCK, release=release)

    def prepare(self, transport, client_id, lease=None):
        _transport(transport)
        _identifier(client_id)
        with self._lock:
            if self._closed:
                raise ValueError('bridge closed')
            if transport == 'uart' and (self._uart is None or self._uart.state not in ('opening', 'listening')):
                raise ValueError('UART requires explicit operator prepare')
            return PeerHello(self.pi_id, client_id, 2, transport, self._run_id,
                             'output_off' if self._state is None else 'ready',
                             self._block_locked(transport, lease), self._release_locked(transport, lease))

    def _expire(self):
        with self._lock:
            expired = self._lease and self.clock() - self._lease.renewed_at >= LEASE_TIMEOUT_S
            lease_id = self._lease.lease_id if expired else None
        if lease_id:
            self.detach(lease_id)

    def attach(self, client_id, transport, capabilities=None):
        self.prepare(transport, client_id)
        tick = (isinstance(capabilities, dict)
                and type(capabilities.get(TICK_CAPABILITY)) is int
                and capabilities[TICK_CAPABILITY] == TICK_CAPABILITY_VERSION)
        self._expire()
        with self._lock:
            if self._closed:
                raise ValueError('bridge closed')
            if self._lease is not None:
                raise ValueError('bridge occupied by another connection')
            lease = Lease(uuid.uuid4().hex, client_id, transport, self._run_id, self.clock(), tick=tick)
            self._lease = lease
            return lease

    def detach(self, lease_id):
        while True:
            with self._output_guard() as guarded_state:
                with self._lock:
                    if guarded_state is not self._state:
                        continue
                    if self._lease is None or self._lease.lease_id != lease_id:
                        return
                    self._lease = None
                    state = self._state
                    if self._real_run is None and self._run_id is not None:
                        self._demo_stop.set()
                if state is not None:
                    state.abandon_pending()
                return

    def reserve_real_run(self, run_id):
        _identifier(run_id)
        with self._lock:
            if self._closed or self._run_id is not None:
                raise BridgeOccupied('bridge occupied by an active run')
            self._real_run = self._run_id = run_id

    def release_real_run(self, run_id):
        self.unbind_run(run_id)
        with self._lock:
            if self._real_run == run_id:
                self._real_run = None
                self._run_id = None

    def bind_run(self, run_id, state: OutputState, *, transport=None):
        _identifier(run_id)
        with self._lock:
            if self._closed or self._state is not None or self._run_id not in (None, run_id):
                raise ValueError('bridge occupied by an active run')
            if state.run_id != run_id:
                raise ValueError('output run identity mismatch')
            self._run_id, self._state, self._transport = run_id, state, transport

    def unbind_run(self, run_id):
        while True:
            with self._output_guard() as guarded_state:
                with self._lock:
                    if guarded_state is not self._state:
                        continue
                    if self._run_id != run_id:
                        return
                    state, self._state = self._state, None
                    self._transport = None
                    if self._real_run != run_id:
                        self._run_id = None
                if state is not None:
                    state.abandon_pending()
                return

    def _hello(self, lease, request_id):
        hello = self.prepare(lease.transport, lease.client_id, lease=lease)
        lease.release = hello.release
        return dict(version=2, type='hello', request_id=request_id, pi_id=self.pi_id,
                    client_id=lease.client_id, lease_id=lease.lease_id, run_id=hello.run_id,
                    protocol_version=2, transport=lease.transport, state=hello.state,
                    release_block=hello.release_block,
                    # dut_output bleibt False: Testfreigabe ist keine Abnahme.
                    capabilities=dict(heartbeat_interval_s=1, lease_timeout_s=5, dut_output=False),
                    permissions=['readiness', 'demo'],
                    # Additiv (R1): nur gesendet, wenn freigegeben; alte Clients
                    # lehnen das unbekannte Feld ab und bleiben so ohne Ausgabe.
                    **({'release': hello.release} if hello.release else {}))

    def exchange(self, lease_id, message):
        # Validation precedes state mutation even for in-process callers.
        message = decode_v2(encode_v2(message))
        while True:
            with self._output_guard() as guarded_state:
                self._expire()
                with self._lock:
                    if guarded_state is not self._state:
                        continue
                    lease = self._lease
                    if lease is None or lease.lease_id != lease_id:
                        raise ValueError('lease expired or detached')
                    if message['pi_id'] != self.pi_id or message['client_id'] != lease.client_id:
                        raise ValueError('identity mismatch')
                    kind = message['type']
                    if kind not in ('poll', 'ack', 'tick_ack', 'heartbeat', 'demo_request'):
                        raise ValueError('unexpected message')
                    if kind != 'demo_request' and message['lease_id'] != lease_id:
                        raise ValueError('lease mismatch')
                    run_id, state, transport = self._run_id, self._state, self._transport
                    if message['run_id'] != run_id:
                        if kind in ('poll', 'heartbeat') or (kind in ('ack', 'tick_ack')
                                                             and message['run_id'] == lease.run_id):
                            # Eine Quittung fuer den Lauf, in dem diese Lease zuletzt war, ueberlebt
                            # dessen Ende: nicht angenommen (das Angebot ist als "unconfirmed"
                            # auditiert, abandon_pending), Verbindung bleibt, Client bekommt den neuen
                            # Laufstand. Fremde Lauf-IDs bleiben ein Fehler.
                            lease.run_id = run_id
                            return self._hello(lease, message['request_id'])
                        raise ValueError('run mismatch')
                    if kind in ('poll', 'heartbeat') and lease.release != self._release_locked(lease.transport, lease):
                        # Freigabestand hat sich im selben Lauf geaendert (Bindung
                        # nach Reservierung): erst ankuendigen, dann Werte.
                        lease.renewed_at = self.clock()
                        return self._hello(lease, message['request_id'])
                    lease.renewed_at = self.clock()
                    lease.run_id = run_id
                if kind == 'demo_request':
                    if message['transport'] != lease.transport:
                        raise ValueError('transport mismatch')
                    self.start_demo(lease.client_id, lease.transport, message['count'], message['rate_hz'],
                                    _expected_lease_id=lease_id)
                    return self._hello(lease, message['request_id'])
                base = dict(version=2, request_id=message['request_id'], pi_id=self.pi_id,
                            client_id=lease.client_id, lease_id=lease_id, run_id=run_id)
                if kind == 'heartbeat':
                    return {**base, 'type': 'heartbeat'}
                if state is None or transport not in (None, lease.transport):
                    if kind in ('ack', 'tick_ack'):
                        if state is None:
                            # Lauf beendet (Ausgabe abgebaut), Reservierung noch nicht freigegeben.
                            return self._hello(lease, message['request_id'])
                        raise ValueError('no pending output')
                    return {**base, 'type': 'idle', 'release_block': RELEASE_BLOCK if self._real_run else None}
                if state.tick_mode and not lease.tick:
                    # Nie ein Takt an einen Client ohne Taktfaehigkeit, auch keine Quittung.
                    if kind != 'poll':
                        raise ValueError('tick output requires tick-capable client')
                    return {**base, 'type': 'idle', 'release_block': TICK_CLIENT_BLOCK}
                legacy = {k: v for k, v in message.items() if k not in ('pi_id', 'client_id', 'lease_id')}
                legacy['version'] = 1
                reply = state.handle_v1(legacy)
                if reply is None:
                    lease.release = state.release
                    return {**base, 'type': 'idle', 'release_block': state.release_block,
                            **({'release': state.release} if state.release else {})}
                reply.pop('version')
                if reply['type'] != 'record':
                    reply.pop('demo', None)
                if reply['type'] == 'idle':
                    reply.setdefault('release_block', None)
                return decode_v2(encode_v2({**base, **reply}))

    def start_demo(self, client_id, transport, count=600, rate_hz=10.0, *, _expected_lease_id=None):
        from dispread.gsv_bridge import demo_records

        if type(count) is not int or not 1 <= count <= 100000:
            raise ValueError('invalid demo count')
        if type(rate_hz) not in (int, float) or not math.isfinite(rate_hz) or not 0 < rate_hz <= 100:
            raise ValueError('invalid demo rate')
        run_id = uuid.uuid4().hex
        state = OutputState(self.audit_root / 'demo' / run_id, demo=True)
        state.run_id = run_id
        stop = threading.Event()
        with self._lock:
            if self._real_run:
                raise ValueError('demo refused during real run')
            if self._closed or self._run_id:
                raise ValueError('bridge occupied by active run')
            lease = self._lease
            if lease is None or (lease.client_id, lease.transport) != (client_id, transport):
                raise ValueError('authenticated lease required')
            # The authenticated connection that requested the demo must still
            # own the lease at this reservation point, even for the same client
            # reconnecting. No run/artifact side effect precedes this check.
            if ((_expected_lease_id is not None and lease.lease_id != _expected_lease_id)
                    or self.clock() - lease.renewed_at >= LEASE_TIMEOUT_S):
                raise ValueError('demo lease expired or replaced')
            self._run_id = run_id
            self._demo_stop = stop
        try:
            state.start()
            (state.out_dir / 'demo.json').write_text(json.dumps(dict(
                run_id=run_id, demo=True, provisional=True, time_claim=False,
                capture_time_base='synthetic', count=count, rate_hz=rate_hz)))
            self.bind_run(run_id, state, transport=transport)
            def produce():
                try:
                    last = None
                    with (state.out_dir / 'records.jsonl').open('w', encoding='utf-8') as records:
                        for record in demo_records(count):
                            if stop.is_set():
                                break
                            records.write(json.dumps(record.to_dict(), allow_nan=False) + '\n')
                            records.flush()
                            state.publish(record)
                            last = record.frame_sequence
                            # Bounded waits also handle extremely small positive
                            # rates without overflowing the OS timeout. A silent
                            # expired client cannot reserve the bridge forever.
                            due = time.monotonic() + 1 / rate_hz
                            while not stop.is_set():
                                self._expire()
                                remaining = due - time.monotonic()
                                if remaining <= 0:
                                    break
                                stop.wait(min(.2, remaining))
                    # ``ended`` must not overtake the final value: a client that
                    # polls late would otherwise get 599 of 600. Bounded; a silent
                    # client loses its lease (_expire) and ends the wait too.
                    grace = time.monotonic() + DEMO_FINAL_GRACE_S
                    while last is not None and not stop.is_set() and not state.settled(last):
                        self._expire()
                        if time.monotonic() >= grace:
                            break
                        stop.wait(.02)
                finally:
                    try:
                        state.stop()
                    finally:
                        self.unbind_run(run_id)
            self._demo_thread = threading.Thread(target=produce, name='bridge-demo', daemon=True)
            self._demo_thread.start()
        except BaseException:
            self.unbind_run(run_id)
            state.stop()
            raise
        return run_id

    def prepare_uart(self):
        from .uart import UartListener

        if self.identity is None or self.pairing_store is None:
            raise ValueError('UART identity and pairing store not configured')
        with self._lock:
            if self._closed:
                raise ValueError('bridge closed')
            if self._uart is not None and self._uart.state not in ('failed', 'stopped'):
                return self.status()
            listener = UartListener(self, self.identity, self.pairing_store,
                                    opener=self.serial_opener, port_leases=self.port_leases)
            self._uart = listener
        try:
            listener.start()
        except BaseException:
            with self._lock:
                if self._uart is listener:
                    self._uart = None
            raise
        return self.status()

    def stop_uart(self):
        with self._lock:
            listener = self._uart
        if listener:
            listener.stop()
            with self._lock:
                if self._uart is listener and (listener._thread is None or not listener._thread.is_alive()):
                    self._uart = None
        return self.status()

    def close(self):
        with self._lock:
            self._closed = True
            listener, self._uart = self._uart, None
            lease = self._lease
        if listener:
            listener.stop()
        self._demo_stop.set()
        if self._demo_thread and self._demo_thread.is_alive():
            self._demo_thread.join(timeout=2)
        if lease:
            self.detach(lease.lease_id)
