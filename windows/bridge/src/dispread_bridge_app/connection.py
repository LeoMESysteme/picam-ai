"""Authenticated connection generations and validated v1 data seam.

The metadata lock linearizes revocation/replacement with W2 admission. No
transport, COM, filesystem, emit or worker status I/O runs under that lock.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, replace

from dispread.bridge.discovery import TailscaleStatus, tailscale_status
from dispread.bridge.identity import verify_certificate
from dispread.bridge.protocol import (
    TEST_RELEASE,
    TICK_CAPABILITY,
    TICK_CAPABILITY_VERSION,
    _identifier,
    decode_v2,
    encode_v2,
    parse_profile,
)
from dispread.bridge.types import BridgeEvent, BridgeProfile

from .credentials import CredentialError
from .devices import DeviceSelectionError
from .readiness import Readiness, aggregate_readiness, peer_output_readiness
from .transports import TransportError, TransportFactory


class ConnectionError(OSError):
    def __init__(self, code='connection_unavailable'):
        self.code = code
        super().__init__(code)


def _close(transport):
    try:
        transport.close()
    except Exception:
        pass


class _DataLink:
    def __init__(self, manager, transport, mode, generation):
        self.manager, self.transport, self.mode, self.generation = manager, transport, mode, generation
        self.lease_id = self.run_id = None
        self.run_format = self._declared_run_format = None
        self.renewed_at = 0
        self.valid = False
        self._peer_state, self._peer_release_block = 'unknown', None
        self._peer_release = None  # R1: nur der Pi-Marker dieser Generation/Run-ID
        #: Nachtrag B2: '1ch'/'4ch' des gebundenen Pi-Laufs aus hello/idle, sonst None.
        self.peer_output_format = None
        self.output, self.output_reason = 'unavailable', None
        self._operation = threading.Lock()
        self._local = threading.local()
        self._offered = None
        self.failed = threading.Event()

    def _base(self, kind, request_id=None):
        return dict(version=2, type=kind, pi_id=self.manager.profile.pi_id,
                    client_id=self.manager.client_id, request_id=request_id or uuid.uuid4().hex)

    def _exchange(self, request, *, initial=False):
        request = decode_v2(encode_v2(request))
        try:
            if not initial:
                self.manager._check(self)
            self.transport.send(request)
            reply = decode_v2(encode_v2(self.transport.receive()))
            if any(reply[k] != request[k] for k in ('pi_id', 'client_id', 'request_id')):
                raise ConnectionError('peer_invalid')
            if reply['type'] == 'error':
                # The previous exclusive owner may still be detaching. Preserve
                # only this reviewed retryable code, never external error text.
                raise ConnectionError('lease_unavailable' if reply['code'] == 'lease_unavailable'
                                      else 'peer_refused')
            if reply.get('lease_id') is None or (not initial and reply['lease_id'] != self.lease_id):
                raise ConnectionError('peer_invalid')
            if reply['type'] == 'hello':
                if reply['protocol_version'] != 2 or reply['transport'] != self.mode:
                    raise ConnectionError('peer_invalid')
                if not {'readiness', 'demo'} <= set(reply['permissions']):
                    raise ConnectionError('peer_invalid')
                if reply['capabilities'].get('dut_output') is not False:
                    raise ConnectionError('peer_invalid')
                if (reply['capabilities'].get('heartbeat_interval_s') != 1
                        or reply['capabilities'].get('lease_timeout_s') != 5):
                    raise ConnectionError('peer_invalid')
            elif reply.get('run_id') != self.run_id:
                raise ConnectionError('peer_invalid')
            allowed = {'hello': {'hello'}, 'heartbeat': {'heartbeat', 'hello'},
                       'poll': {'record', 'tick', 'idle', 'ended', 'hello'}, 'ack': {'idle', 'hello'},
                       'tick_ack': {'idle', 'hello'}, 'demo_request': {'hello'}}
            if reply['type'] not in allowed.get(request['type'], set()):
                raise ConnectionError('peer_invalid')
            output_changed = False
            with self.manager._lock:
                previous_run = self.run_id
                if initial:
                    self.lease_id, self.run_id = reply['lease_id'], reply['run_id']
                else:
                    self.manager._check_locked(self)
                    if reply['type'] == 'hello':
                        self.run_id = reply['run_id']
                        self._offered = None
                if reply['type'] == 'hello':
                    self._peer_state = reply['state']
                    self._peer_release_block = reply['release_block']
                    self._peer_release = reply.get('release')
                    self.peer_output_format = reply.get('output_format')
                elif reply['type'] == 'idle':
                    self._peer_release_block = reply['release_block']
                    self._peer_release = reply.get('release')
                    self.peer_output_format = reply.get('output_format')
                elif reply['type'] == 'record':
                    # Ein echter Wert ist nur zulaessig, wenn der Pi die
                    # Testfreigabe fuer genau diesen Lauf vorher gemeldet hat.
                    if reply['demo'] is not True and (self._peer_release != TEST_RELEASE
                                                      or reply.get('release') != TEST_RELEASE):
                        raise ConnectionError('peer_invalid')
                    if reply['demo'] is True:
                        self._peer_release = None
                    self._peer_state, self._peer_release_block = 'ready', None
                elif reply['type'] == 'tick':
                    # B2: ein Takt traegt immer echte Werte bzw. Fehlwerte und
                    # setzt dieselbe vorher angekuendigte Testfreigabe voraus.
                    if self._peer_release != TEST_RELEASE or reply['release'] != TEST_RELEASE:
                        raise ConnectionError('peer_invalid')
                    self._peer_state, self._peer_release_block = 'ready', None
                elif reply['type'] == 'ended':
                    self._peer_state, self._peer_release = 'ended', None
                if previous_run != self.run_id or self.run_id is None or reply['type'] == 'ended':
                    self.run_format = self._declared_run_format = None
                if self.run_id is not None and reply['type'] != 'ended':
                    # Hello/Idle melden output_format des gebundenen Laufs (Vorrang vor dem
                    # Schluss aus tick/record); so warnt die App vor dem ersten Wert.
                    self._declared_run_format = reply.get('output_format', self._declared_run_format)
                    self.run_format = self._declared_run_format or {
                        'tick': '4ch', 'record': '1ch'}.get(reply['type'], self.run_format)
                event_run_id, event_format = self.run_id, self.run_format
                self.output, self.output_reason = peer_output_readiness(
                    self._peer_state, self.run_id, self._peer_release_block, self._peer_release)
                self.renewed_at = time.monotonic()
                if not initial:
                    output_changed = self.manager._peer_output_locked(self) or previous_run != self.run_id
            if output_changed:
                self.manager._event('peer_output_changed', run_id=self.run_id, output=self.output,
                                    reason=self.output_reason, generation=self.generation)
            try:
                self.manager._emit(BridgeEvent('activity', request['type'], event_run_id, None,
                                              dict(run_format=event_format, generation=self.generation)))
            except Exception:
                pass
            return reply
        except Exception as error:
            self.failed.set()
            self.manager._revoke(self)
            code = getattr(error, 'code', None)
            if not isinstance(error, ConnectionError) and isinstance(code, str):
                # Transportcode (z. B. uart_frame_invalid) ins Diagnoseprotokoll; nur
                # freigegebene Bezeichner erscheinen dort ungeschwaerzt.
                self.manager._event(code)
            if isinstance(error, ConnectionError):
                raise
            raise ConnectionError('peer_invalid' if isinstance(error, (ValueError, KeyError, TypeError))
                                  else 'connection_lost') from None

    def test_release_for(self, run_id) -> bool:
        """True only for the current authenticated generation and Pi-marked run."""
        with self.manager._lock:
            return (self.valid and self.manager._link is self and run_id is not None
                    and run_id == self.run_id and self._peer_release == TEST_RELEASE
                    and self._peer_release_block is None)

    def handshake(self):
        with self._operation:
            request = dict(self._base('hello'), protocol_version=2, transport=self.mode,
                           run_id=None, state='ready', release_block=None,
                           # B2: ohne diese Faehigkeit bietet der Pi nie einen Takt an.
                           capabilities={TICK_CAPABILITY: TICK_CAPABILITY_VERSION}, permissions=[])
            reply = self._exchange(request, initial=True)
            if reply['type'] != 'hello':
                raise ConnectionError('peer_invalid')

    def heartbeat(self):
        with self._operation:
            reply = self._exchange(dict(self._base('heartbeat'), lease_id=self.lease_id, run_id=self.run_id))
            if reply['type'] not in ('heartbeat', 'hello'):
                raise ConnectionError('peer_invalid')

    def start_demo(self, count, rate_hz):
        with self._operation:
            if self.run_id is not None:
                raise ConnectionError('run_conflict')
            request = dict(self._base('demo_request'), transport=self.mode, run_id=None, count=count, rate_hz=rate_hz)
            # No retry of an uncertain start, even after reconnection/new lease.
            reply = self._exchange(request)
            if reply['type'] != 'hello' or reply['run_id'] is None:
                raise ConnectionError('demo_unconfirmed')
            return reply['run_id']

    def send(self, message):
        with self._operation:
            try:
                if not isinstance(message, dict) or type(message.get('version')) is not int or message['version'] != 1:
                    raise ConnectionError('invalid_legacy_request')
                kind = message.get('type')
                if kind == 'poll':
                    if set(message) != {'version', 'type', 'request_id'} or getattr(self._local, 'reply', None) is not None:
                        raise ConnectionError('invalid_legacy_request')
                    request = dict(self._base('poll', message['request_id']), lease_id=self.lease_id, run_id=self.run_id)
                    reply = self._exchange(request)
                    # Der Pi kann zwischen Anfrage und Wiederholung erneut wechseln (Ausgabe abgebaut,
                    # dann Lauf freigegeben): jedes hello nur begrenzt oft nachfuehren, jede Antwort
                    # bleibt voll validiert (unten); mehr als drei in Folge sind ein Peer-Fehler.
                    for _ in range(3):
                        if reply['type'] != 'hello':
                            break
                        request['run_id'] = self.run_id
                        reply = self._exchange(request)
                    if reply['type'] not in ('record', 'tick', 'idle', 'ended'):
                        raise ConnectionError('peer_invalid')
                    if reply['type'] == 'record':
                        self._offered = (reply['request_id'], reply['run_id'],
                                         reply['record']['frame_sequence'], reply['barrier_id'])
                    elif reply['type'] == 'tick':
                        self._offered = ('tick', reply['request_id'], reply['run_id'], reply['seq'])
                    self._local.run_id = reply['run_id']
                    self._local.reply = {k: v for k, v in reply.items() if k not in ('pi_id', 'client_id', 'lease_id')}
                    self._local.reply['version'] = 1
                    return
                if kind == 'ack':
                    if set(message) != {'version', 'type', 'request_id', 'run_id', 'frame_sequence', 'barrier_id', 'outcome'}:
                        raise ConnectionError('invalid_legacy_request')
                    binding = tuple(message[k] for k in ('request_id', 'run_id', 'frame_sequence', 'barrier_id'))
                    if binding != self._offered or message['run_id'] != self.run_id:
                        raise ConnectionError('stale_ack')
                    request = dict(message, version=2, pi_id=self.manager.profile.pi_id,
                                   client_id=self.manager.client_id, lease_id=self.lease_id)
                    reply = self._exchange(request)
                    if reply['type'] not in ('idle', 'hello'):
                        raise ConnectionError('peer_invalid')
                    # hello: der Lauf endete vor der Quittung; der Pi nimmt sie nicht an (sein Audit
                    # fuehrt das Angebot als unbestaetigt), die Verbindung bleibt.
                    self._offered = None  # drain ACK response; never queue it as the next poll.
                    return
                if kind == 'tick_ack':
                    if set(message) != {'version', 'type', 'request_id', 'run_id', 'seq', 'outcome', 'filled'}:
                        raise ConnectionError('invalid_legacy_request')
                    binding = ('tick', *(message[k] for k in ('request_id', 'run_id', 'seq')))
                    if binding != self._offered or message['run_id'] != self.run_id:
                        raise ConnectionError('stale_ack')
                    request = dict(message, version=2, pi_id=self.manager.profile.pi_id,
                                   client_id=self.manager.client_id, lease_id=self.lease_id)
                    reply = self._exchange(request)
                    if reply['type'] not in ('idle', 'hello'):
                        raise ConnectionError('peer_invalid')
                    self._offered = None
                    return
                raise ConnectionError('invalid_legacy_request')
            except Exception:
                self.failed.set()
                self.manager._revoke(self)
                raise

    def receive(self):
        self.manager._check(self)
        reply = getattr(self._local, 'reply', None)
        self._local.reply = None
        if reply is None:
            raise ConnectionError('no_pending_poll')
        if reply['run_id'] != self.run_id:
            raise ConnectionError('run_changed')
        return reply


class ConnectionManager:
    def __init__(self, profile: BridgeProfile, client_id: str, credentials, devices,
                 transport_factory=None, emit=None, *, network_diagnostics=None):
        _identifier(client_id)
        self._profile, self.client_id = profile, client_id
        self._credentials, self._devices = credentials, devices
        self._transport_factory = transport_factory or TransportFactory()
        self._emit = emit or (lambda event: None)
        self._network_diagnostics = network_diagnostics or tailscale_status
        self._network_status = TailscaleStatus('unknown')
        self._lock = threading.RLock()
        self._generation = 0
        self._cancel = threading.Event()
        self._thread = self._link = self._worker = None
        self._readiness = Readiness('ready', 'unknown', 'disconnected', 'unavailable', 'unknown', 'unconfirmed', 'connect')

    @property
    def profile(self) -> BridgeProfile:
        return self._profile

    @property
    def network_status(self) -> TailscaleStatus:
        with self._lock:
            return self._network_status

    def set_worker(self, worker):
        """Consume the actual W2 frozen status; GUI need not reproduce the policy."""
        with self._lock:
            self._worker = worker

    def snapshot(self) -> Readiness:
        with self._lock:
            base, worker, link = self._readiness, self._worker, self._link
            if link is not None and time.monotonic() - link.renewed_at >= 5:
                base = replace(base, peer='disconnected', output='unavailable', next_action='reconnect')
        return aggregate_readiness(base, None if worker is None else worker.status)

    def _event(self, code, *, run_id=None, output=None, reason=None, generation=None):
        detail = dict(version=2, demo_only=output != 'test_release', provisional=True,
                      gsv_receipt_confirmed=False)
        if output is not None:
            detail.update(output=output, reason=reason, generation=generation)
        try:
            self._emit(BridgeEvent('connection', code, run_id, None, detail))
        except Exception:
            pass

    def _peer_output_locked(self, link):
        """Called only after current generation/lease/run validation under _lock."""
        changed = (self._readiness.output, self._readiness.next_action) != (link.output, link.output_reason)
        self._readiness = replace(self._readiness, output=link.output, next_action=link.output_reason)
        return changed

    def _state(self, generation, peer, action=None, adapter=None):
        with self._lock:
            if generation != self._generation or self._cancel.is_set():
                return
            link = self._link if peer == 'authenticated' else None
            if peer == 'authenticated' and link is None:
                return
            output = link.output if link else 'unavailable'
            reason = link.output_reason if link else action
            self._readiness = replace(self._readiness, peer=peer, next_action=reason,
                                      adapter=adapter or self._readiness.adapter, output=output)
            run_id = link.run_id if link else None
        self._event(action or peer, run_id=run_id, output=output, reason=reason, generation=generation)

    def _check_locked(self, link):
        if (self._link is not link or not link.valid or self._cancel.is_set()
                or time.monotonic() - link.renewed_at >= 5):
            raise ConnectionError('connection_unavailable')

    def _check(self, link):
        with self._lock:
            self._check_locked(link)

    def data_link(self):
        with self._lock:
            link = self._link
            if link is None:
                raise ConnectionError()
            self._check_locked(link)
            return link

    def admit_write(self, link, claim):
        """Run only the nonblocking W2 final claim under generation metadata lock.

        Lock order is manager -> worker. COM/journal/network I/O is forbidden in
        claim. Already admitted attempts may finish or become unknown after revoke.
        """
        with self._lock:
            self._check_locked(link)
            if getattr(link._local, 'run_id', link.run_id) != link.run_id:
                raise ConnectionError('run_changed')
            return claim()

    def _revoke(self, link):
        with self._lock:
            link.valid = False
            if self._link is link:
                self._link = None
                self._readiness = replace(self._readiness, peer='disconnected', output='unavailable', next_action='reconnect')
        # Cleanup can involve transport/audit I/O, so it runs after metadata revoke.
        threading.Thread(target=_close, args=(link.transport,), daemon=True).start()

    def disconnect(self):
        with self._lock:
            self._cancel.set()
            self._generation += 1
            link, self._link = self._link, None
            if link:
                link.valid = False
            self._readiness = replace(self._readiness, peer='disconnected', output='unavailable', next_action='connect')
        if link:
            threading.Thread(target=_close, args=(link.transport,), daemon=True).start()
        self._event('disconnected')

    def cancel(self):
        self.disconnect()

    def connect(self, mode: str, selected_device_id: str | None = None):
        if mode not in ('network', 'uart'):
            raise ConnectionError('transport_unsupported')
        with self._lock:
            self._cancel.set()
            self._generation += 1
            old_link, self._link = self._link, None
            if old_link is not None:
                old_link.valid = False
            self._cancel = cancel = threading.Event()
            self._network_status = TailscaleStatus('unknown')
            generation = self._generation
            self._readiness = replace(self._readiness, peer='connecting', output='unavailable', next_action=None,
                                      adapter='not_required' if mode == 'network' else 'unknown')
            thread = threading.Thread(target=self._connect_loop, args=(generation, cancel, mode, selected_device_id),
                                      daemon=True, name='bridge-connection')
            self._thread = thread
        if old_link is not None:
            threading.Thread(target=_close, args=(old_link.transport,), daemon=True).start()
        self._event('connecting')
        thread.start()

    def _device(self, selected, *, reconnect, identity):
        if self._devices is None:
            raise ConnectionError('adapter_unavailable')
        if reconnect and identity is None:
            raise ConnectionError('selection_required')
        if identity is None and selected is not None:
            matches = [item for item in self._devices.inventory()
                       if item.is_supported and item.instance_id == selected]
            if len(matches) != 1:
                raise ConnectionError('selection_required')
            identity = matches[0].identity
        try:
            item = self._devices.select_supported(identity)
        except DeviceSelectionError as error:
            raise ConnectionError('adapter_unavailable' if str(error) == 'not_found'
                                  else 'selection_required') from None
        if not item.port or item.pnp_error != 0:
            raise ConnectionError('adapter_driver_unavailable')
        return item, item.identity if item.serial else None

    def _connect_loop(self, generation, cancel, mode, selected):
        try:
            parse_profile(json.dumps(asdict(self.profile)).encode())
            verify_certificate(self.profile.certificate_pem, self.profile.certificate_sha256, self.profile.pi_id)
        except Exception as error:
            code = 'clock_or_certificate_invalid' if 'validity interval' in str(error) else 'profile_invalid'
            self._state(generation, 'disconnected', code)
            return
        attempt, reconnect, identity = 0, False, None
        permanent = {'peer_invalid', 'profile_invalid', 'selection_required', 'pairing_required', 'pairing_refused',
                     'authentication_refused', 'peer_refused', 'endpoint_unsupported', 'endpoint_required',
                     'adapter_driver_unavailable', 'credential_unavailable', 'components_unsupported'}
        while not cancel.is_set():
            transport = link = None
            try:
                device = None
                if mode == 'uart':
                    device, identity = self._device(selected, reconnect=reconnect, identity=identity)
                credential = self._credentials.load(self.profile.pi_id, mode,
                                                    expected_pin=self.profile.certificate_sha256)
                if cancel.is_set():
                    return
                transport = self._transport_factory(self.profile, self.client_id, mode, credential, device, cancel)
                if cancel.is_set():
                    _close(transport)
                    return
                link = _DataLink(self, transport, mode, generation)
                link.handshake()
                token = getattr(transport, 'authenticated_token', None)
                if token is not None and token != credential:
                    self._credentials.save(self.profile.pi_id, mode, token,
                                           expected_pin=self.profile.certificate_sha256)
                with self._lock:
                    if generation != self._generation or cancel.is_set():
                        raise ConnectionError('cancelled')
                    link.valid = True
                    self._link = link
                attempt = 0
                self._state(generation, 'authenticated', adapter='ready' if mode == 'uart' else 'not_required')
                while not cancel.wait(1):
                    link.heartbeat()
                return
            except Exception as error:
                if link:
                    self._revoke(link)
                elif transport:
                    _close(transport)
                if cancel.is_set():
                    return
                code = error.code if isinstance(error, (ConnectionError, TransportError)) else (
                    'credential_unavailable' if isinstance(error, CredentialError) else 'connection_unavailable')
                if code in permanent:
                    self._state(generation, 'disconnected', code)
                    return
                if mode == 'network' and code != 'lease_unavailable':
                    try:
                        status = self._network_diagnostics()
                    except Exception:
                        status = TailscaleStatus('unreachable')
                    allowed = {'not_installed', 'logged_out', 'needs_approval', 'running', 'dns_error', 'unreachable'}
                    status = TailscaleStatus(status.state if isinstance(status, TailscaleStatus)
                                             and status.state in allowed else 'unreachable')
                    with self._lock:
                        current = generation == self._generation and not cancel.is_set()
                        if current:
                            self._network_status = status
                    if current:
                        self._event('tailscale_' + status.state)
                self._state(generation, 'backoff', code)
                if cancel.wait(min(2 ** min(attempt, 3), 8)):
                    return
                attempt += 1
                reconnect = True

    def start_demo(self, count=600, rate_hz=10.0) -> str:
        return self.data_link().start_demo(count, rate_hz)
