"""Identity/lease and generation tests use the actual reviewed Pi hub."""
import threading
import time
from dataclasses import replace

import pytest
from dispread_bridge_app.connection import ConnectionError, ConnectionManager
from dispread_bridge_app.devices import WindowsDevices
from dispread_bridge_app.types import DeviceInfo

from dispread.bridge.hub import BridgeHub
from dispread.bridge.identity import DeviceIdentity
from dispread.bridge.types import BridgeProfile


@pytest.fixture(scope='module')
def identity(tmp_path_factory):
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'portable-test-pi')])
    now = datetime.now(UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1)).add_extension(x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier('urn:dispread:pi:portable-test-pi')]), critical=False)
            .sign(key, hashes.SHA256()))
    return DeviceIdentity(tmp_path_factory.mktemp('w1'), 'portable-test-pi',
                          cert.public_bytes(serialization.Encoding.PEM).decode(),
                          cert.fingerprint(hashes.SHA256()).hex(), key)


@pytest.fixture
def profile(identity):
    return BridgeProfile(1, identity.pi_id, 'Pi', identity.certificate_pem, identity.fingerprint,
                         ('https://pi.local:8080',), 2)


class Credentials:
    def load(self, pi_id, mode, *, expected_pin=None):
        return 'a' * 43

    def save(self, *args, **kwargs):
        pass


class HubTransport:
    def __init__(self, hub, mode='network', mutate=None):
        self.hub, self.mode, self.mutate = hub, mode, mutate
        self.lease = None
        self.pending = None
        self.closed = False
        self.kinds = []

    def send(self, message):
        if self.closed:
            raise OSError('closed')
        self.kinds.append(message['type'])
        if message['type'] == 'hello':
            try:
                self.hello = message
                self.lease = self.hub.attach(message['client_id'], self.mode,
                                             capabilities=message['capabilities'])
            except ValueError:
                # Match the real WSS route's typed, bound lease-conflict reply.
                self.pending = {key: message[key] for key in ('version', 'pi_id', 'client_id', 'request_id')}
                self.pending.update(type='error', run_id=None, code='lease_unavailable', detail='owner still attached')
            else:
                self.pending = self.hub._hello(self.lease, message['request_id'])
        else:
            self.pending = self.hub.exchange(self.lease.lease_id, message)
        if self.mutate:
            self.pending = self.mutate(self.pending)

    def receive(self):
        result, self.pending = self.pending, None
        if result is None:
            raise OSError('missing response')
        return result

    def close(self):
        self.closed = True
        if self.lease:
            self.hub.detach(self.lease.lease_id)


class Factory:
    def __init__(self, hub, mutate=None):
        self.hub, self.mutate = hub, mutate
        self.transports = []

    def __call__(self, profile, client_id, mode, credential, device, cancel):
        transport = HubTransport(self.hub, mode, self.mutate)
        self.transports.append(transport)
        return transport


def wait_for(predicate):
    deadline = time.monotonic() + 10
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(.005)


@pytest.fixture
def setup(tmp_path, profile):
    hub = BridgeHub(profile.pi_id, tmp_path / 'audit')
    factory = Factory(hub)
    events = []
    manager = ConnectionManager(profile, 'windows-a', Credentials(), None, factory, events.append)
    yield manager, factory, hub, events
    manager.disconnect()
    hub.close()


def connected(manager):
    manager.connect('network')
    wait_for(lambda: manager.snapshot().peer == 'authenticated')
    return manager.data_link()


def test_stable_link_and_atomic_admission_reject_revoked_generation(setup):
    manager, factory, hub, events = setup
    link = connected(manager)
    assert manager.data_link() is link
    assert manager.admit_write(link, lambda: 'claimed') == 'claimed'
    manager.disconnect()
    called = []
    with pytest.raises(ConnectionError):
        manager.admit_write(link, lambda: called.append(True))
    assert called == []
    newer = connected(manager)
    assert newer is not link
    with pytest.raises(ConnectionError):
        manager.admit_write(link, lambda: called.append(True))
    assert manager.profile is manager.profile
    with pytest.raises(AttributeError):
        manager.profile = None


@pytest.mark.parametrize('field,value', [('pi_id', 'wrong-pi'), ('protocol_version', 1), ('transport', 'uart')])
def test_same_hostname_different_pi_never_reconnects(setup, field, value):
    manager, factory, hub, events = setup
    factory.mutate = lambda msg: dict(msg, **{field: value})
    manager.connect('network')
    wait_for(lambda: manager.snapshot().next_action == 'peer_invalid')
    with pytest.raises(ConnectionError):
        manager.data_link()
    assert hub.status()['connected'] is False


def test_cancel_late_opener_cannot_attach(setup):
    manager, factory, hub, events = setup
    entered, release = threading.Event(), threading.Event()
    original = factory.__call__
    def delayed(*args):
        entered.set()
        release.wait(2)
        return original(*args)
    manager._transport_factory = delayed
    manager.connect('network')
    assert entered.wait(1)
    started = time.monotonic()
    manager.cancel()
    assert time.monotonic() - started < .5
    release.set()
    wait_for(lambda: factory.transports and factory.transports[0].closed)
    assert manager.snapshot().peer == 'disconnected'
    assert hub.status()['connected'] is False


def test_matching_adapter_without_unique_serial_needs_selection(setup):
    manager, factory, hub, events = setup
    class Devices(WindowsDevices):
        def inventory(self):
            return (DeviceInfo('a', 'COM6', 0x403, 0x6001, None, None, 0),
                    DeviceInfo('b', 'COM7', 0x403, 0x6001, None, None, 0))
    manager._devices = Devices()
    manager.connect('uart')
    wait_for(lambda: manager.snapshot().next_action == 'selection_required')
    assert factory.transports == []


def test_heartbeat_has_no_numeric_poll_and_demo_is_explicit(setup):
    manager, factory, hub, events = setup
    link = connected(manager)
    assert hub.status()['run_id'] is None
    wait_for(lambda: 'heartbeat' in factory.transports[0].kinds)
    assert 'poll' not in factory.transports[0].kinds
    run_id = manager.start_demo(count=1, rate_hz=100)
    assert run_id
    link.send(dict(version=1, type='poll', request_id='poll-a'))
    reply = link.receive()
    if reply['type'] == 'record':
        link.send(dict(version=1, type='ack', request_id='poll-a', run_id=run_id,
                       frame_sequence=reply['record']['frame_sequence'], barrier_id=reply['barrier_id'], outcome='written'))
        assert factory.transports[0].pending is None
    link.send(dict(version=1, type='poll', request_id='poll-b'))
    assert link.receive()['request_id'] == 'poll-b'


def test_invalid_imported_pin_stops_before_credentials_or_transport(setup):
    manager, factory, hub, events = setup
    manager._profile = replace(manager.profile, certificate_sha256='0' * 64)
    manager.connect('network')
    wait_for(lambda: manager.snapshot().next_action == 'profile_invalid')
    assert factory.transports == []


def test_uart_reconnect_tracks_unique_serial_across_com_renumbering(setup):
    manager, factory, hub, events = setup
    class Devices(WindowsDevices):
        port = 'COM6'
        def inventory(self):
            return (DeviceInfo('a-' + self.port, self.port, 0x403, 0x6001, 'unique', None, 0),)
    devices = Devices()
    manager._devices = devices
    seen_ports = []
    def opener(profile, client, mode, credential, device, cancel):
        seen_ports.append(device.port)
        return factory(profile, client, mode, credential, device, cancel)
    manager._transport_factory = opener
    class PreparedListener:
        state = 'listening'
        error = None
        def stop(self):
            pass
    hub._uart = PreparedListener()
    manager.connect('uart')
    wait_for(lambda: manager.snapshot().peer == 'authenticated')
    first = manager.data_link()
    devices.port = 'COM9'
    factory.transports[0].close()
    wait_for(lambda: len(factory.transports) > 1 and manager.snapshot().peer == 'authenticated')
    assert seen_ports == ['COM6', 'COM9']
    assert manager.data_link() is not first
    with pytest.raises(ConnectionError):
        manager.admit_write(first, lambda: pytest.fail('stale write admitted'))


def test_cancel_during_backoff_stops_retry_without_error_leak(setup):
    from dispread_bridge_app.transports import TransportError
    manager, factory, hub, events = setup
    calls = []
    def unavailable(*args):
        calls.append(True)
        raise TransportError('network_unavailable') from OSError('offer=' + 's' * 43)
    manager._transport_factory = unavailable
    manager.connect('network')
    wait_for(lambda: manager.snapshot().peer == 'backoff')
    manager.cancel()
    manager._thread.join(.5)
    assert not manager._thread.is_alive()
    assert len(calls) == 1
    assert 's' * 43 not in repr(events)


def test_old_run_offer_cannot_be_admitted_after_heartbeat_resync(setup):
    from dispread.bridge.output_state import OutputState
    from dispread.gsv_bridge import demo_records
    manager, factory, hub, events = setup
    link = connected(manager)
    state = OutputState(hub.audit_root / 'manual', demo=True)
    state.start()
    hub.bind_run(state.run_id, state)
    state.publish(next(iter(demo_records(1))))
    link.send(dict(version=1, type='poll', request_id='offer-a'))
    assert link.receive()['type'] == 'record'
    hub.unbind_run(state.run_id)
    link.heartbeat()
    with pytest.raises(ConnectionError, match='run_changed'):
        manager.admit_write(link, lambda: pytest.fail('old run admitted'))
    state.stop()


def test_expired_certificate_stops_before_credential_loading(setup, identity):
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.x509.oid import NameOID
    manager, factory, hub, events = setup
    now = datetime.now(UTC)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'expired')])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(identity._key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=2)).not_valid_after(now - timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(
                'urn:dispread:pi:' + identity.pi_id)]), critical=False).sign(identity._key, hashes.SHA256()))
    manager._profile = replace(manager.profile, certificate_pem=cert.public_bytes(serialization.Encoding.PEM).decode(),
                               certificate_sha256=cert.fingerprint(hashes.SHA256()).hex())
    class ForbiddenCredentials:
        def load(self, *args, **kwargs):
            pytest.fail('credential consulted before certificate validity')
    manager._credentials = ForbiddenCredentials()
    manager.connect('network')
    wait_for(lambda: manager.snapshot().next_action == 'clock_or_certificate_invalid')
    assert factory.transports == []


def test_write_admission_and_disconnect_share_one_linearization_lock(setup):
    manager, factory, hub, events = setup
    link = connected(manager)
    entered, release, disconnected = threading.Event(), threading.Event(), threading.Event()
    results = []
    def claim():
        entered.set()
        release.wait(1)  # Test barrier only; real claims are required to be nonblocking.
        return 'admitted_before_revoke'
    admitting = threading.Thread(target=lambda: results.append(manager.admit_write(link, claim)))
    admitting.start()
    assert entered.wait(1)
    def revoke():
        manager.disconnect()
        disconnected.set()
    revoking = threading.Thread(target=revoke)
    revoking.start()
    assert not disconnected.wait(.05)
    release.set()
    admitting.join(1)
    revoking.join(1)
    assert results == ['admitted_before_revoke']
    assert disconnected.is_set()
    with pytest.raises(ConnectionError):
        manager.admit_write(link, lambda: pytest.fail('post revoke claim'))


def test_ack_response_loss_revokes_link_and_does_not_replay_record(setup):
    from dispread.bridge.output_state import OutputState
    from dispread.gsv_bridge import demo_records
    manager, factory, hub, events = setup
    link = connected(manager)
    state = OutputState(hub.audit_root / 'manual-ack', demo=True)
    state.start()
    hub.bind_run(state.run_id, state)
    state.publish(next(iter(demo_records(1))))
    link.send(dict(version=1, type='poll', request_id='poll-lost-ack'))
    reply = link.receive()
    assert reply['type'] == 'record'
    transport = factory.transports[0]
    def lose_response():
        transport.pending = None
        raise OSError('lost ACK response')
    transport.receive = lose_response
    with pytest.raises(ConnectionError, match='connection_lost'):
        link.send(dict(version=1, type='ack', request_id='poll-lost-ack', run_id=reply['run_id'],
                       frame_sequence=reply['record']['frame_sequence'], barrier_id=reply['barrier_id'], outcome='written'))
    with pytest.raises(ConnectionError):
        manager.data_link()
    wait_for(lambda: hub.status()['connected'] is False)
    manager.connect('network')
    wait_for(lambda: manager.snapshot().peer == 'authenticated')
    new_link = manager.data_link()
    new_link.send(dict(version=1, type='poll', request_id='after-loss'))
    assert new_link.receive()['type'] != 'record'
    state.stop()


def test_worker_failure_is_aggregated_by_manager(setup):
    from dispread_bridge_app.worker import WorkerStatus
    manager, factory, hub, events = setup
    connected(manager)
    class Worker:
        status = WorkerStatus('stopped', False, False, 'unknown_invalidation')
    manager.set_worker(Worker())
    snapshot = manager.snapshot()
    assert snapshot.output == 'blocked'
    assert snapshot.next_action == 'unknown_invalidation'
    assert snapshot.peer == 'authenticated'
    assert snapshot.gsv == 'unconfirmed'


def test_delayed_event_sink_cannot_overwrite_a_newer_connect_generation(setup):
    manager, factory, hub, events = setup
    entered, release = threading.Event(), threading.Event()
    def delayed_event(event):
        if threading.current_thread().name == 'older-connect':
            entered.set()
            release.wait(2)
    manager._emit = delayed_event
    first = threading.Thread(target=lambda: manager.connect('network'), name='older-connect')
    first.start()
    assert entered.wait(1)
    manager.connect('network')
    wait_for(lambda: manager.snapshot().peer == 'authenticated')
    current = manager.data_link()
    release.set()
    first.join(1)
    time.sleep(.05)
    assert manager.data_link() is current
    assert len(factory.transports) == 1


def test_usb_parent_and_serial_child_use_n2_single_device_selection(setup):
    manager, factory, hub, events = setup
    class Devices(WindowsDevices):
        def inventory(self):
            return (DeviceInfo('usb-parent', None, 0x403, 0x6001, 'unique', None, 0),
                    DeviceInfo('serial-child', 'COM6', 0x403, 0x6001, 'unique', None, 0))
    class PreparedListener:
        state = 'listening'
        error = None
        def stop(self):
            pass
    manager._devices = Devices()
    hub._uart = PreparedListener()
    manager.connect('uart')
    wait_for(lambda: manager.snapshot().peer == 'authenticated')
    assert manager.data_link()


def test_tailscale_logged_out_is_local_evidence_without_claiming_route_cause(setup):
    from dispread_bridge_app.transports import TransportError

    from dispread.bridge.discovery import TailscaleStatus
    manager, factory, hub, events = setup
    manager._network_diagnostics = lambda: TailscaleStatus('logged_out')
    def no_route(*args):
        raise TransportError('network_unavailable')
    manager._transport_factory = no_route
    manager.connect('network')
    wait_for(lambda: manager.snapshot().peer == 'backoff')
    assert manager.network_status.state == 'logged_out'
    assert manager.snapshot().next_action == 'network_unavailable'
    assert any(event.code == 'tailscale_logged_out' for event in events)
    assert not hub.status()['connected']


@pytest.mark.parametrize('cancel_replacement', [False, True])
def test_delayed_old_close_retries_typed_lease_conflict_without_overlapping_owner(setup, cancel_replacement):
    manager, factory, hub, events = setup
    from dispread.bridge.discovery import TailscaleStatus
    manager._network_diagnostics = lambda: TailscaleStatus('running')
    old_link = connected(manager)
    old_transport = factory.transports[0]
    old_lease = old_transport.lease
    entered, release = threading.Event(), threading.Event()
    original_close = old_transport.close
    def delayed_close():
        entered.set()
        release.wait(3)
        original_close()
    old_transport.close = delayed_close
    try:
        manager.connect('network')
        assert entered.wait(1)
        wait_for(lambda: manager.snapshot().next_action == 'lease_unavailable')
        assert manager.snapshot().peer == 'backoff'
        assert hub._lease is old_lease
        assert factory.transports[1].lease is None
        with pytest.raises(ConnectionError):
            manager.admit_write(old_link, lambda: pytest.fail('revoked owner admitted'))
        if cancel_replacement:
            manager.cancel()
            manager._thread.join(.5)
            assert not manager._thread.is_alive()
        release.set()
        if cancel_replacement:
            wait_for(lambda: not hub.status()['connected'])
            assert manager.snapshot().peer == 'disconnected'
            assert len(factory.transports) == 2
        else:
            wait_for(lambda: manager.snapshot().peer == 'authenticated')
            assert manager.data_link() is not old_link
            assert len(factory.transports) == 3
            assert hub._lease is factory.transports[2].lease
            assert old_transport.closed
    finally:
        release.set()


@pytest.mark.parametrize('worker_code', ['unbound', None, 'audit_failed'])
def test_blocked_replacement_opener_clears_revoked_output_readiness(setup, worker_code):
    from dispread_bridge_app.worker import WorkerStatus
    manager, factory, hub, events = setup
    old_link = connected(manager)
    assert manager.snapshot().output == 'output_off'
    class Worker:
        status = WorkerStatus('running' if worker_code is None else 'stopped', False,
                              worker_code is None, worker_code)
    if worker_code != 'unbound':
        manager.set_worker(Worker())
    entered, release = threading.Event(), threading.Event()
    def blocked(*args):
        entered.set()
        release.wait(3)
        return factory(*args)
    manager._transport_factory = blocked
    try:
        manager.connect('network')
        assert entered.wait(1)
        snapshot = manager.snapshot()
        assert snapshot.peer == 'connecting'
        assert snapshot.output == ('blocked' if worker_code == 'audit_failed' else 'unavailable')
        assert snapshot.gsv == 'unconfirmed'
        with pytest.raises(ConnectionError):
            manager.data_link()
        with pytest.raises(ConnectionError):
            manager.admit_write(old_link, lambda: pytest.fail('old output admitted'))
    finally:
        manager.cancel()
        release.set()


@pytest.mark.parametrize('error_code,wrong_pi,expected', [
    ('authentication_refused', False, 'peer_refused'),
    ('lease_unavailable', True, 'peer_invalid'),
])
def test_bound_auth_or_identity_error_remains_fatal(setup, error_code, wrong_pi, expected):
    manager, factory, hub, events = setup
    def refuse(message):
        error = {key: message[key] for key in ('version', 'pi_id', 'client_id', 'request_id')}
        error.update(type='error', run_id=None, code=error_code, detail='offer=' + 's' * 43)
        if wrong_pi:
            error['pi_id'] = 'impostor'
        return error
    factory.mutate = refuse
    manager.connect('network')
    wait_for(lambda: manager.snapshot().next_action == expected)
    manager._thread.join(.5)
    assert not manager._thread.is_alive()
    assert len(factory.transports) == 1
    assert 's' * 43 not in repr(events)


def test_same_run_idle_release_updates_are_safe_and_bound_to_current_generation(setup):
    from dispread.bridge.output_state import RELEASE_BLOCK, OutputState
    manager, factory, hub, events = setup
    link = connected(manager)
    assert (manager.snapshot().output, manager.snapshot().next_action) == ('output_off', 'output_off')
    state = OutputState(hub.audit_root / 'peer-readiness', demo=True)
    state.start()
    hub.bind_run(state.run_id, state)
    try:
        link.heartbeat()  # Run-change Hello must refresh the output state.
        assert manager.snapshot().output == 'demo_only'
        transport = factory.transports[0]
        for index, block, reason in [(1, RELEASE_BLOCK, 'dut_release_blocked'),
                                     (2, 'token=SECRET', 'peer_release_blocked'),
                                     (3, None, None)]:
            transport.mutate = lambda reply, block=block: dict(reply, release_block=block)
            link.send(dict(version=1, type='poll', request_id=f'readiness-{index}'))
            assert link.receive()['type'] == 'idle'
            snapshot = manager.snapshot()
            assert snapshot.output == ('demo_only' if block is None else 'blocked')
            assert snapshot.next_action == reason
            latest = [event for event in events if event.code == 'peer_output_changed'][-1]
            assert latest.run_id == state.run_id
            assert latest.detail['reason'] == reason
            assert latest.detail['generation'] == link.generation
        assert 'SECRET' not in repr(events)
        manager.disconnect()
        cleared = manager.snapshot()
        assert (cleared.output, cleared.next_action) == ('unavailable', 'connect')
        with pytest.raises(ConnectionError):
            link.heartbeat()
        assert manager.snapshot() == cleared
    finally:
        hub.unbind_run(state.run_id)
        state.stop()


# R1 (2026-11-09): echte Werte nur nach Pi-Freigabestand dieser Generation/Run-ID.
def _real(seq):
    from dispread.records import TimeBaseKind, Timestamp, ValueRecord, ValueStatus
    return ValueRecord(seq, Timestamp(seq, TimeBaseKind.V4L2_MONOTONIC), 1.5, 'mV/V', ValueStatus.VALID,
                       1.0, 'p', None, None, raw_text='+1.5')


def _bind(hub, run_id, *, release):
    from dispread.bridge.output_state import OutputState
    hub.reserve_real_run(run_id)
    state = OutputState(hub.audit_root / run_id, release=release)
    state.run_id = run_id
    state.start()
    hub.bind_run(run_id, state, transport='network')
    return state


def test_test_release_follows_pi_marker_for_current_run_only(setup):
    manager, factory, hub, events = setup
    state = _bind(hub, 'released-run', release='test_unaccepted')
    try:
        link = connected(manager)
        assert (manager.snapshot().output, manager.snapshot().next_action) == ('test_release', None)
        assert link.test_release_for('released-run') and not link.test_release_for('other')
        state.publish(_real(1))
        link.send(dict(version=1, type='poll', request_id='p1'))
        reply = link.receive()
        assert (reply['type'], reply['demo'], reply['release']) == ('record', False, 'test_unaccepted')
        link.send(dict(version=1, type='ack', request_id='p1', run_id='released-run', frame_sequence=1,
                       barrier_id=None, outcome='written'))
    finally:
        hub.release_real_run('released-run')
        state.stop()
    blocked = _bind(hub, 'locked-run', release=None)
    try:
        link.send(dict(version=1, type='poll', request_id='p2'))  # Laufwechsel -> Hello ohne Freigabe
        assert link.receive()['type'] == 'idle'
        assert not link.test_release_for('locked-run')
        assert (manager.snapshot().output, manager.snapshot().next_action) == ('blocked', 'dut_release_blocked')
    finally:
        hub.release_real_run('locked-run')
        blocked.stop()


def test_record_claiming_release_without_prior_pi_marker_revokes_link(setup):
    manager, factory, hub, events = setup
    factory.mutate = lambda reply: ({k: v for k, v in reply.items() if k != 'release'}
                                    if reply['type'] in ('hello', 'idle') else reply)
    state = _bind(hub, 'sneaky-run', release='test_unaccepted')
    try:
        link = connected(manager)
        assert manager.snapshot().output == 'demo_only' or manager.snapshot().output != 'test_release'
        state.publish(_real(1))
        with pytest.raises(ConnectionError, match='peer_invalid'):
            link.send(dict(version=1, type='poll', request_id='p1'))
        assert not link.test_release_for('sneaky-run')
    finally:
        hub.release_real_run('sneaky-run')
        state.stop()


# B2 (2026-11-11): Taktnachricht ueber die validierte v1-Naht.
def _bind_ticks(hub, run_id, *, release='test_unaccepted'):
    from dispread.bridge.output_state import OutputState
    hub.reserve_real_run(run_id)
    clock = [0]
    state = OutputState(hub.audit_root / run_id, release=release, clock=lambda: clock[0], tick_rate_hz=10,
                        tick_thread=False)
    state.run_id = run_id
    state.start()
    hub.bind_run(run_id, state, transport='network')

    def advance(ticks=1):
        for _ in range(ticks):
            clock[0] += 100_000_000
            state.step_ticks()
    return state, advance


def test_client_hello_announces_tick_capability(setup):
    manager, factory, hub, events = setup
    connected(manager)
    assert factory.transports[-1].hello['capabilities'] == {'tick': 1}


def test_tick_and_tick_ack_cross_the_validated_seam(setup):
    manager, factory, hub, events = setup
    state, advance = _bind_ticks(hub, 'tick-run')
    try:
        link = connected(manager)
        assert link.test_release_for('tick-run')
        advance(2)
        link.send(dict(version=1, type='poll', request_id='p1'))
        reply = link.receive()
        assert (reply['type'], reply['seq'], reply['valid'], reply['version']) == ('tick', 1, False, 1)
        assert set(reply) == {'version', 'type', 'request_id', 'run_id', 'seq', 'valid', 'value_text',
                              'frame_sequence', 'time_unix_ns', 'origin_unix_ns', 'rate_hz', 'release'}
        with pytest.raises(ConnectionError, match='stale_ack'):
            link.send(dict(version=1, type='tick_ack', request_id='p1', run_id='tick-run', seq=2,
                           outcome='written', filled=0))
        link = connected(manager)
        advance()
        link.send(dict(version=1, type='poll', request_id='p2'))
        second = link.receive()
        assert second['seq'] == 2                       # Takt 1 bleibt unbestaetigt, nie erneut
        link.send(dict(version=1, type='tick_ack', request_id='p2', run_id='tick-run', seq=2,
                       outcome='written', filled=1))
        tick = state.status()['tick']
        assert (tick['acknowledged'], tick['unconfirmed']) == (1, 1)
    finally:
        hub.release_real_run('tick-run')
        state.drain_timeout_s = 0
        state.stop()


def test_tick_claiming_release_without_prior_pi_marker_revokes_link(setup):
    manager, factory, hub, events = setup
    factory.mutate = lambda reply: ({k: v for k, v in reply.items() if k != 'release'}
                                    if reply['type'] in ('hello', 'idle') else reply)
    state, advance = _bind_ticks(hub, 'sneaky-tick')
    try:
        link = connected(manager)
        advance()
        with pytest.raises(ConnectionError, match='peer_invalid'):
            link.send(dict(version=1, type='poll', request_id='p1'))
        assert not link.test_release_for('sneaky-tick')
    finally:
        hub.release_real_run('sneaky-tick')
        state.drain_timeout_s = 0
        state.stop()
