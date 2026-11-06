import base64
import queue
import secrets
import time

import pytest

from dispread.bridge.hub import BridgeHub
from dispread.bridge.identity import DeviceIdentity, verify_certificate, verify_hello
from dispread.bridge.pairing import PairingStore
from dispread.bridge.protocol import canonical_uart_hello, decode_v2, encode_v2
from dispread.bridge.resources import SerialPortLease


class Wire:
    def __init__(self):
        self.incoming, self.outgoing = queue.Queue(), queue.Queue()
        self.closed = False
    def read(self, count):
        try:
            return self.incoming.get(timeout=.02)
        except queue.Empty:
            return b''
    def write(self, data):
        self.outgoing.put(data)
        return len(data)
    def close(self):
        self.closed = True
    def send(self, message, fragmented=False):
        payload = encode_v2(message)
        if fragmented:
            self.incoming.put(payload[:7])
            payload = payload[7:]
        self.incoming.put(payload)
    def receive(self):
        return decode_v2(self.outgoing.get(timeout=2))


@pytest.fixture(scope='module')
def identity(tmp_path_factory):
    return DeviceIdentity.load_or_create(tmp_path_factory.mktemp('uart') / 'identity', 'fake-hardware')


@pytest.fixture
def ready(tmp_path, identity):
    wire = Wire()
    store = PairingStore(tmp_path / 'pairing')
    opened = []
    def opener(*args, **kwargs):
        opened.append((args, kwargs))
        return wire
    hub = BridgeHub(identity.pi_id, tmp_path / 'audit', identity=identity, pairing_store=store,
                    serial_opener=opener, port_leases=SerialPortLease(tmp_path / 'locks'))
    assert opened == []
    hub.prepare_uart()
    yield hub, wire, store
    hub.close()
    assert wire.closed


def base(identity, kind, **extra):
    return dict(version=2, type=kind, request_id='request', pi_id=identity.pi_id, client_id='pc', **extra)


def authenticate(ready, identity, *, transport='uart'):
    hub, wire, store = ready
    nonce = secrets.token_urlsafe(32)
    wire.send(base(identity, 'uart_challenge', nonce=nonce), fragmented=True)
    proof = wire.receive()
    assert proof['type'] == 'uart_proof' and proof['nonce'] == nonce
    verify_certificate(identity.certificate_pem, identity.fingerprint, identity.pi_id)
    verify_hello(identity.certificate_pem, canonical_uart_hello(identity.pi_id, 'pc', nonce),
                 base64.b64decode(proof['signature'], validate=True))
    assert not hub.status()['connected']
    offer = store.create_offer(transport)
    wire.send(base(identity, 'uart_auth', nonce=nonce, mode='offer', credential=offer))
    return wire.receive()


def test_uart_pinned_nonce_auth_before_lease_and_fragmented_demo(ready, identity):
    hub, wire, store = ready
    authenticated = authenticate(ready, identity)
    assert authenticated['type'] == 'uart_authenticated'
    assert store.authorize(authenticated['token'], 'uart') == 'pc'
    assert not hub.status()['connected']
    wire.send(base(identity, 'hello', protocol_version=2, transport='uart', run_id=None,
                   state='idle', release_block=None, capabilities={}, permissions=[]))
    hello = wire.receive()
    assert hello['type'] == 'hello' and hello['lease_id']
    wire.send(base(identity, 'demo_request', transport='uart', run_id=None, count=2, rate_hz=1))
    demo = wire.receive()
    assert demo['type'] == 'hello' and demo['run_id']
    wire.send(base(identity, 'heartbeat', run_id=demo['run_id'], lease_id=hello['lease_id']))
    assert wire.receive()['type'] == 'heartbeat'
    wire.send(base(identity, 'poll', run_id=demo['run_id'], lease_id=hello['lease_id']))
    assert wire.receive()['type'] == 'record'


def test_uart_rejects_network_offer_without_lease(ready, identity):
    hub, wire, store = ready
    response = authenticate(ready, identity, transport='network')
    assert response['type'] == 'error'
    assert not hub.status()['connected']


def test_uart_rejects_credential_without_nonce_proof(ready, identity):
    hub, wire, store = ready
    offer = store.create_offer('uart')
    wire.send(base(identity, 'uart_auth', nonce='a'*43, mode='offer', credential=offer))
    assert wire.receive()['type'] == 'error'
    assert store.redeem_offer(offer, 'pc', 'uart')  # never consumed
    assert not hub.status()['connected']


def test_uart_silent_revocation_detaches(ready, identity):
    hub, wire, store = ready
    assert authenticate(ready, identity)['type'] == 'uart_authenticated'
    wire.send(base(identity, 'hello', protocol_version=2, transport='uart', run_id=None,
                   state='idle', release_block=None, capabilities={}, permissions=[]))
    assert wire.receive()['type'] == 'hello'
    assert hub.status()['connected']
    store.revoke('pc')
    deadline = time.monotonic() + 1
    while hub.status()['connected'] and time.monotonic() < deadline:
        time.sleep(.01)
    assert not hub.status()['connected']


def test_uart_wrong_nonce_does_not_redeem_offer(ready, identity):
    hub, wire, store = ready
    nonce = secrets.token_urlsafe(32)
    wire.send(base(identity, 'uart_challenge', nonce=nonce))
    wire.receive()
    offer = store.create_offer('uart')
    wire.send(base(identity, 'uart_auth', nonce=secrets.token_urlsafe(32), mode='offer', credential=offer))
    assert wire.receive()['type'] == 'error'
    assert store.redeem_offer(offer, 'pc', 'uart')
    assert not hub.status()['connected']


def test_uart_partial_write_closes_and_releases_port(tmp_path, identity):
    import threading
    wire = Wire()
    wire.write = lambda payload: len(payload) - 1
    store = PairingStore(tmp_path / 'pairing')
    leases = SerialPortLease(tmp_path / 'locks')
    opened = threading.Event()
    def opener(*args, **kwargs):
        opened.set()
        assert kwargs['timeout'] == .1 and kwargs['write_timeout'] == .2 and kwargs['exclusive'] is True
        return wire
    hub = BridgeHub(identity.pi_id, tmp_path / 'audit', identity=identity, pairing_store=store,
                    serial_opener=opener, port_leases=leases)
    hub.prepare_uart()
    assert opened.wait(1)
    wire.send(base(identity, 'uart_challenge', nonce='a' * 43))
    hub._uart._thread.join(1)
    assert wire.closed and hub.status()['uart_state'] == 'failed'
    assert not hub.status()['uart_prepared']
    leases.acquire('/dev/ttyAMA0', 'direct', 'serial')
    leases.release('direct')
    hub.close()


def test_blocked_uart_write_does_not_block_output_publication(ready, identity):
    import threading
    from dataclasses import replace

    from dispread.gsv_bridge import demo_records
    hub, wire, store = ready
    authenticated = authenticate(ready, identity)
    assert authenticated['type'] == 'uart_authenticated', {
        'type': authenticated.get('type'), 'code': authenticated.get('code'), 'state': hub.status()}
    wire.send(base(identity, 'hello', protocol_version=2, transport='uart', run_id=None,
                   state='idle', release_block=None, capabilities={}, permissions=[]))
    hello = wire.receive()
    assert hello['type'] == 'hello' and hello.get('lease_id'), {
        'type': hello.get('type'), 'code': hello.get('code'), 'state': hub.status()}
    run_id = hub.start_demo('pc', 'uart', count=100, rate_hz=10)
    entered, release = threading.Event(), threading.Event()
    original = wire.write
    def blocked(payload):
        entered.set()
        assert release.wait(2)
        return original(payload)
    wire.write = blocked
    wire.send(base(identity, 'poll', run_id=run_id, lease_id=hello['lease_id']))
    assert entered.wait(1)
    try:
        done = threading.Event()
        state = hub._state
        def publish():
            state.publish(replace(next(demo_records(1)), frame_sequence=100))
            done.set()
        worker = threading.Thread(target=publish)
        worker.start()
        assert done.wait(.5)
        worker.join(1)
    finally:
        release.set()
        wire.receive()


def test_old_prepare_failure_keeps_replacement_listener_tracked(tmp_path, identity, monkeypatch):
    import threading

    from dispread.bridge.uart import UartListener

    wire = Wire()
    opened = threading.Event()
    def opener(*args, **kwargs):
        opened.set()
        return wire
    ports = SerialPortLease(tmp_path / 'locks')
    hub = BridgeHub(identity.pi_id, tmp_path / 'audit', identity=identity,
                    pairing_store=object(), serial_opener=opener, port_leases=ports)
    entered, resume = threading.Event(), threading.Event()
    original = UartListener.start
    errors = []
    def paused_start(listener):
        if not entered.is_set():
            entered.set()
            assert resume.wait(2)
        return original(listener)
    monkeypatch.setattr(UartListener, 'start', paused_start)
    def prepare_old():
        try:
            hub.prepare_uart()
        except Exception as exc:
            errors.append(exc)
    old = threading.Thread(target=prepare_old)
    replacement = None
    old.start()
    try:
        assert entered.wait(1)
        hub.stop_uart()
        hub.prepare_uart()
        replacement = hub._uart
        assert opened.wait(1)
        resume.set()
        old.join(1)
        assert not old.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], ValueError)
        assert hub._uart is replacement
        assert hub.status()['uart_prepared']
        hub.close()
        assert wire.closed
        ports.acquire('/dev/ttyAMA0', 'after-close', 'serial')
        ports.release('after-close')
    finally:
        resume.set()
        old.join(1)
        hub.close()
        # A failing implementation must not leave its orphan worker behind.
        if replacement is not None:
            replacement.stop()


def test_uart_stop_during_thread_start_never_joins_unstarted_thread(tmp_path, identity, monkeypatch):
    import threading

    from dispread.bridge.uart import UartListener

    wire = Wire()
    opened = threading.Event()
    def opener(*args, **kwargs):
        opened.set()
        return wire
    ports = SerialPortLease(tmp_path / 'locks')
    hub = BridgeHub(identity.pi_id, tmp_path / 'audit')
    listener = UartListener(hub, identity, object(), opener=opener, port_leases=ports)
    entering_start, resume_start, entering_stop = threading.Event(), threading.Event(), threading.Event()
    original = threading.Thread.start
    errors = []
    def paused_start(thread):
        if thread.name == 'bridge-uart':
            entering_start.set()
            assert resume_start.wait(2)
        return original(thread)
    monkeypatch.setattr(threading.Thread, 'start', paused_start)
    def start():
        try:
            listener.start()
        except Exception as exc:
            errors.append(exc)
    def stop():
        entering_stop.set()
        try:
            listener.stop()
        except Exception as exc:
            errors.append(exc)
    starter = threading.Thread(target=start)
    stopper = threading.Thread(target=stop)
    starter.start()
    try:
        assert entering_start.wait(1)
        stopper.start()
        assert entering_stop.wait(1)
        # Give stop the paused-start interval, rather than a timing-dependent
        # simultaneous release. The old implementation raises join-before-start.
        stopper.join(.1)
        resume_start.set()
        starter.join(1)
        stopper.join(1)
        assert not starter.is_alive() and not stopper.is_alive()
        assert errors == []
        assert not opened.is_set() or wire.closed
        ports.acquire('/dev/ttyAMA0', 'after-stop', 'serial')
        ports.release('after-stop')
    finally:
        resume_start.set()
        starter.join(1)
        if stopper.ident is not None:
            stopper.join(1)
        listener.stop()


def test_uart_completed_store_call_does_not_depend_on_thread_teardown(ready, identity, monkeypatch):
    import threading

    from dispread.bridge.uart import UartListener

    hub, wire, store = ready
    completed, release_teardown = threading.Event(), threading.Event()
    held_threads, refusals = [], []
    original_run = threading.Thread.run
    original_message = UartListener._message
    def run(thread):
        original_run(thread)
        if thread.name == 'uart-credentials' and not completed.is_set():
            # The database operation has returned and signalled its result.
            # Hold only thread teardown, not SQLite or the authorization call.
            held_threads.append(thread)
            completed.set()
            assert release_teardown.wait(2)
    def message(listener, value):
        try:
            return original_message(listener, value)
        except ValueError as exc:
            # Fixed production refusal strings only; never frame/credential data.
            refusals.append((value['type'], str(exc)))
            raise
    monkeypatch.setattr(threading.Thread, 'run', run)
    monkeypatch.setattr(UartListener, '_message', message)
    try:
        authenticated = authenticate(ready, identity)
        assert completed.wait(1) and held_threads[0].is_alive()
        wire.send(base(identity, 'hello', protocol_version=2, transport='uart', run_id=None,
                       state='idle', release_block=None, capabilities={}, permissions=[]))
        hello = wire.receive()
        diagnostic = (f'refusals={refusals}; auth={authenticated.get("type")}; '
                      f'hello={hello.get("type")}/{hello.get("code")}; '
                      f'UART={hub.status()["uart_state"]}; connected={hub.status()["connected"]}')
        assert authenticated['type'] == 'uart_authenticated', diagnostic
        assert hello['type'] == 'hello' and hello.get('lease_id'), diagnostic
        assert hub.status()['connected']
    finally:
        release_teardown.set()
        for thread in held_threads:
            thread.join(1)


def test_uart_pending_store_call_remains_exclusive_after_timeout(ready, identity, monkeypatch):
    import threading

    hub, wire, store = ready
    entered, release = threading.Event(), threading.Event()
    calls = []
    original = store.redeem_offer
    def pending(*args):
        calls.append(True)
        entered.set()
        assert release.wait(2)
        return original(*args)
    monkeypatch.setattr(store, 'redeem_offer', pending)
    try:
        first = authenticate(ready, identity)
        assert entered.is_set() and first['type'] == 'error'
        second = authenticate(ready, identity)
        assert second['type'] == 'error'
        assert calls == [True]  # No queued/replacement SQLite operation.
        assert not hub.status()['connected']
        release.set()
        hub._uart._store_thread.join(1)
        assert not hub._uart._store_thread.is_alive()
        assert hub._uart._token is None and hub._lease is None
    finally:
        release.set()
