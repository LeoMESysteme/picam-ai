
import pytest
from dispread_bridge_app.transports import TransportError, resolve_endpoints


class _ScopedTestAuth:
    """Test-only scoped auth boundary; real Pi persistence is tested by P2/P3."""
    def __init__(self, *, clock=None):
        import threading
        import time
        self.clock = clock or time.monotonic
        self.offers, self.tokens = {}, {}
        self.lock = threading.Lock()

    def create_offer(self, transport, client_id=None):
        import secrets
        offer = secrets.token_urlsafe(32)
        with self.lock:
            self.offers[offer] = (transport, client_id, self.clock() + 300)
        return offer

    def redeem_offer(self, offer, client_id, transport):
        import secrets

        from dispread.bridge.pairing import PairingError
        with self.lock:
            saved = self.offers.get(offer)
            if saved is None or saved[0] != transport or saved[1] not in (None, client_id) or self.clock() >= saved[2]:
                raise PairingError('offer_refused')
            del self.offers[offer]
            token = secrets.token_urlsafe(32)
            self.tokens[token] = (client_id, transport)
            return token

    def authorize(self, token, transport):
        from dispread.bridge.pairing import PairingError
        with self.lock:
            saved = self.tokens.get(token)
            if saved is None or saved[1] != transport:
                raise PairingError('token_refused')
            return saved[0]


def _test_identity(directory, pi_id):
    """Portable ephemeral producer identity; never calls Pi provisioning APIs."""
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    from dispread.bridge.identity import DeviceIdentity
    directory.mkdir(parents=True, mode=0o700)
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    now = datetime.now(UTC)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, pi_id)])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1)).add_extension(x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier('urn:dispread:pi:' + pi_id)]), critical=False)
            .sign(key, hashes.SHA256()))
    return DeviceIdentity(directory, pi_id, cert.public_bytes(serialization.Encoding.PEM).decode(),
                          cert.fingerprint(hashes.SHA256()).hex(), key)


def _test_tls_context(identity):
    """Local test-server TLS without the producer's POSIX-only persistence helper."""
    import ssl
    import tempfile
    from pathlib import Path

    from cryptography.hazmat.primitives import serialization
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    with tempfile.TemporaryDirectory(dir=identity.directory) as directory:
        cert, key = Path(directory) / 'cert.pem', Path(directory) / 'key.pem'
        cert.write_text(identity.certificate_pem)
        key.write_bytes(identity._key.private_bytes(serialization.Encoding.PEM,
                        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        key.chmod(0o600)
        context.load_cert_chain(cert, key)
    return context


@pytest.mark.parametrize('source', ['https://pi.local:8080', 'https://pi.local:8080/',
                                  'wss://pi.local:8080/bridge/v2', 'https://pi.local:8080/bridge/v2'])
def test_endpoint_origin_and_exact_bridge_path(source):
    assert resolve_endpoints(source) == ('wss://pi.local:8080/bridge/v2', 'https://pi.local:8080/bridge/v2/pair')


@pytest.mark.parametrize('source', ['https://pi/x', 'https://pi/bridge/v2/pair', 'http://pi',
                                  'https://pi/bridge/v2?token=x', 'https://u:p@pi', 'https://pi/#x'])
def test_unsupported_paths_and_credentials_are_refused(source):
    with pytest.raises(TransportError):
        resolve_endpoints(source)


def test_real_wss_pairs_and_exchanges_against_reviewed_hub(tmp_path):
    import asyncio
    import time
    from dataclasses import replace

    from aiohttp import web
    from dispread_bridge_app.connection import ConnectionManager

    from dispread.bridge.hub import BridgeHub
    from dispread.bridge.routes import add_bridge_routes
    from dispread.bridge.types import BridgeProfile
    from dispread.gsv_bridge import BridgeSession

    async def check():
        identity = _test_identity(tmp_path / 'identity', 'w1-wss')
        store = _ScopedTestAuth()
        hub = BridgeHub(identity.pi_id, tmp_path / 'audit', identity=identity, pairing_store=store)
        app = web.Application()
        add_bridge_routes(app, identity, store, hub, lambda request: True)
        runner = web.AppRunner(app, access_log=None, shutdown_timeout=.2)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0, ssl_context=_test_tls_context(identity))
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        profile = BridgeProfile(1, identity.pi_id, 'Pi', identity.certificate_pem, identity.fingerprint,
                                (f'https://127.0.0.1:{port}',), 2, store.create_offer('network', 'w1-client'))
        class Credentials:
            token = pin = None
            def load(self, *args, expected_pin=None):
                return self.token if self.pin == expected_pin else None
            def save(self, pi_id, mode, token, *, expected_pin=None):
                self.token, self.pin = token, expected_pin
        credentials = Credentials()
        manager = ConnectionManager(profile, 'w1-client', credentials, None)
        class Com:
            write_timeout = 1
            payloads = []
            def write(self, payload):
                self.payloads.append(payload)
                return len(payload)
        def exercise():
            manager.connect('network')
            deadline = time.monotonic() + 3
            while manager.snapshot().peer != 'authenticated':
                assert time.monotonic() < deadline, manager.snapshot()
                time.sleep(.01)
            assert credentials.token and credentials.token != profile.pairing_offer
            assert credentials.pin == profile.certificate_sha256
            assert hub.status()['run_id'] is None
            run_id = manager.start_demo(count=20, rate_hz=20)
            assert run_id
            com = Com()
            session = BridgeSession()
            link = manager.data_link()
            for _ in range(5):
                session.exchange(link, com)
                time.sleep(.06)
            assert com.payloads
            # Same adapter across heartbeat and no queued ACK reply on the next poll.
            assert manager.data_link() is link
            manager.disconnect()
            deadline = time.monotonic() + 2
            while hub.status()['connected']:
                assert time.monotonic() < deadline
                time.sleep(.01)
            # Expired/reused offer is irrelevant when a protected scoped token is available.
            manager._profile = replace(profile, pairing_offer=None)
            manager.connect('network')
            deadline = time.monotonic() + 3
            while manager.snapshot().peer != 'authenticated':
                assert time.monotonic() < deadline, manager.snapshot()
                time.sleep(.01)
            assert manager.data_link() is not link
        try:
            await asyncio.to_thread(exercise)
        finally:
            manager.disconnect()
            await asyncio.sleep(.25)
            await runner.cleanup()
            hub.close()
    asyncio.run(check())


def test_actual_tls_peer_pin_is_checked_before_authorization_headers(tmp_path, monkeypatch):
    import asyncio
    import ssl
    import threading

    from aiohttp import web
    from dispread_bridge_app.transports import WssTransport

    from dispread.bridge.types import BridgeProfile

    trusted = _test_identity(tmp_path / 'trusted', 'trusted')
    impostor = _test_identity(tmp_path / 'impostor', 'impostor')
    requests = []
    original = ssl.SSLContext.load_verify_locations
    def allow_impostor_chain(self, cafile=None, capath=None, cadata=None):
        return original(self, cafile=cafile, capath=capath,
                        cadata=cadata + impostor.certificate_pem if cadata else cadata)
    monkeypatch.setattr(ssl.SSLContext, 'load_verify_locations', allow_impostor_chain)
    async def check():
        async def route(request):
            requests.append(dict(request.headers))
            return web.Response(status=401)
        app = web.Application()
        app.router.add_get('/bridge/v2', route)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0, ssl_context=_test_tls_context(impostor))
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        profile = BridgeProfile(1, trusted.pi_id, 'Pi', trusted.certificate_pem, trusted.fingerprint,
                                (f'https://127.0.0.1:{port}',), 2)
        try:
            with pytest.raises(TransportError, match='peer_invalid'):
                await asyncio.to_thread(WssTransport, profile, 'client', 'a' * 43,
                                        profile.endpoints[0], threading.Event())
            assert requests == []
        finally:
            await runner.cleanup()
    asyncio.run(check())


def test_real_wss_redirect_never_follows_configured_path(tmp_path):
    import asyncio
    import threading

    from aiohttp import web
    from dispread_bridge_app.transports import WssTransport

    from dispread.bridge.types import BridgeProfile

    identity = _test_identity(tmp_path / 'identity', 'redirect')
    unexpected = []
    async def check():
        async def redirect(request):
            raise web.HTTPFound('/unexpected')
        async def sink(request):
            unexpected.append(dict(request.headers))
            return web.Response(status=401)
        app = web.Application()
        app.router.add_get('/bridge/v2', redirect)
        app.router.add_get('/unexpected', sink)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0, ssl_context=_test_tls_context(identity))
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        profile = BridgeProfile(1, identity.pi_id, 'Pi', identity.certificate_pem, identity.fingerprint,
                                (f'https://127.0.0.1:{port}',), 2)
        try:
            with pytest.raises(TransportError, match='redirect_refused'):
                await asyncio.to_thread(WssTransport, profile, 'client', 'a' * 43,
                                        profile.endpoints[0], threading.Event())
            assert unexpected == []
        finally:
            await runner.cleanup()
    asyncio.run(check())


def test_signed_uart_proof_precedes_credential_submission(tmp_path):
    import base64
    import threading

    from dispread_bridge_app.transports import SerialTransport
    from dispread_bridge_app.types import DeviceInfo

    from dispread.bridge.protocol import canonical_uart_hello, decode_v2, encode_v2
    from dispread.bridge.types import BridgeProfile

    identity = _test_identity(tmp_path / 'identity', 'uart-proof')
    profile = BridgeProfile(1, identity.pi_id, 'Pi', identity.certificate_pem, identity.fingerprint, (), 2)
    class Stream:
        def __init__(self, bad=False):
            self.buffer = b''
            self.types = []
            self.bad = bad
        def write(self, raw):
            message = decode_v2(raw)
            self.types.append(message['type'])
            base = {k: message[k] for k in ('version', 'pi_id', 'client_id', 'request_id')}
            if message['type'] == 'uart_challenge':
                signature = identity.sign_hello(canonical_uart_hello(identity.pi_id, message['client_id'], message['nonce']))
                if self.bad:
                    signature = bytes([signature[0] ^ 1]) + signature[1:]
                self.buffer = encode_v2(dict(base, type='uart_proof', nonce=message['nonce'],
                                            signature=base64.b64encode(signature).decode()))
            else:
                self.buffer = encode_v2(dict(base, type='uart_authenticated', token=message['credential']))
            return len(raw)
        def read(self, count):
            result, self.buffer = self.buffer[:7], self.buffer[7:]
            return result
        def close(self):
            pass
    device = DeviceInfo('a', 'COM6', 0x403, 0x6001, 'serial-a', None, 0)
    good = Stream()
    adapter = SerialTransport(profile, 'client', 'a' * 43, device, threading.Event(), opener=lambda **kw: good)
    assert good.types == ['uart_challenge', 'uart_auth']
    assert adapter.authenticated_token == 'a' * 43
    adapter.close()
    bad = Stream(bad=True)
    with pytest.raises(TransportError, match='peer_invalid'):
        SerialTransport(profile, 'client', 'a' * 43, device, threading.Event(), opener=lambda **kw: bad)
    assert bad.types == ['uart_challenge']


@pytest.mark.parametrize('offer_mode', ['expired', 'wrong_transport'])
def test_real_wss_refuses_expired_or_uart_scoped_offer(tmp_path, offer_mode):
    import asyncio
    import threading

    from aiohttp import web
    from dispread_bridge_app.transports import WssTransport

    from dispread.bridge.hub import BridgeHub
    from dispread.bridge.routes import add_bridge_routes
    from dispread.bridge.types import BridgeProfile

    async def check():
        identity = _test_identity(tmp_path / 'identity', 'refused-offer')
        clock = [10.0]
        store = _ScopedTestAuth(clock=lambda: clock[0])
        offer = store.create_offer('uart' if offer_mode == 'wrong_transport' else 'network', 'client')
        if offer_mode == 'expired':
            clock[0] += 300
        hub = BridgeHub(identity.pi_id, tmp_path / 'audit', identity=identity, pairing_store=store)
        app = web.Application()
        add_bridge_routes(app, identity, store, hub, lambda request: True)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0, ssl_context=_test_tls_context(identity))
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        profile = BridgeProfile(1, identity.pi_id, 'Pi', identity.certificate_pem, identity.fingerprint,
                                (f'https://127.0.0.1:{port}',), 2, offer)
        try:
            with pytest.raises(TransportError, match='pairing_refused'):
                await asyncio.to_thread(WssTransport, profile, 'client', None, profile.endpoints[0], threading.Event())
            assert not hub.status()['connected']
        finally:
            await runner.cleanup()
            hub.close()
    asyncio.run(check())


def test_unreviewed_aiohttp_version_fails_closed_before_connection(tmp_path, monkeypatch):
    import threading

    import aiohttp
    from dispread_bridge_app.transports import WssTransport

    from dispread.bridge.types import BridgeProfile
    identity = _test_identity(tmp_path / 'identity', 'version-guard')
    profile = BridgeProfile(1, identity.pi_id, 'Pi', identity.certificate_pem, identity.fingerprint,
                            ('https://127.0.0.1:9',), 2)
    monkeypatch.setattr(aiohttp, '__version__', '4.0.0')
    with pytest.raises(TransportError, match='components_unsupported'):
        WssTransport(profile, 'client', 'a' * 43, profile.endpoints[0], threading.Event())


@pytest.mark.parametrize('saved_binding', ['legacy', 'original_pin'])
@pytest.mark.parametrize('fresh_offer', [False, True])
def test_changed_certificate_same_pi_never_receives_saved_token_before_fresh_pairing(tmp_path, fresh_offer, saved_binding):
    import asyncio
    import json
    import time

    from aiohttp import web
    from dispread_bridge_app.connection import ConnectionManager
    from dispread_bridge_app.credentials import CredentialStore

    from dispread.bridge.hub import BridgeHub
    from dispread.bridge.routes import add_bridge_routes
    from dispread.bridge.types import BridgeProfile

    class TestProtector:
        def protect(self, raw):
            return bytes(x ^ 127 for x in raw)
        def unprotect(self, raw):
            return bytes(x ^ 127 for x in raw)
        def secure_path(self, path):
            pass  # Portable fake encryption; this test proves peer credential selection.

    async def check():
        identity_a = _test_identity(tmp_path / 'a', 'shared-pi')
        identity_b = _test_identity(tmp_path / 'b', 'shared-pi')
        assert identity_a.fingerprint != identity_b.fingerprint
        old_token = 'a' * 43
        credentials = CredentialStore(tmp_path / 'credentials', protector=TestProtector())
        # Both legacy unbound blobs and properly A-bound blobs must refuse B.
        binding = {} if saved_binding == 'legacy' else dict(expected_pin=identity_a.fingerprint)
        credentials.save(identity_a.pi_id, 'network', old_token, **binding)
        auth = _ScopedTestAuth()
        offer = auth.create_offer('network', 'client') if fresh_offer else None
        hub = BridgeHub(identity_b.pi_id, tmp_path / 'audit')
        requests, redemptions = [], []
        original_redeem = auth.redeem_offer
        def capture_redemption(*args):
            redemptions.append(args)
            return original_redeem(*args)
        auth.redeem_offer = capture_redemption
        @web.middleware
        async def observe(request, handler):
            requests.append((request.path, request.headers.get('Authorization')))
            return await handler(request)
        app = web.Application(middlewares=[observe])
        add_bridge_routes(app, identity_b, auth, hub, lambda request: True)
        runner = web.AppRunner(app, access_log=None, shutdown_timeout=.2)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0, ssl_context=_test_tls_context(identity_b))
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        profile_b = BridgeProfile(1, identity_b.pi_id, 'replacement', identity_b.certificate_pem,
                                  identity_b.fingerprint, (f'https://127.0.0.1:{port}',), 2, offer)
        manager = ConnectionManager(profile_b, 'client', credentials, None)
        def exercise():
            manager.connect('network')
            deadline = time.monotonic() + 3
            while manager.snapshot().peer != 'authenticated' and manager.snapshot().next_action is None:
                assert time.monotonic() < deadline, manager.snapshot()
                time.sleep(.01)
        try:
            await asyncio.to_thread(exercise)
            assert old_token not in json.dumps([requests, redemptions]), 'saved token reached replacement certificate peer'
            if fresh_offer:
                assert manager.snapshot().peer == 'authenticated'
                assert requests[0] == ('/bridge/v2/pair', None)
                assert redemptions == [(offer, 'client', 'network')]
                new_token = credentials.load('shared-pi', 'network', expected_pin=identity_b.fingerprint)
                assert new_token is not None and new_token != old_token
                assert requests[1][1] == 'Bearer ' + new_token
            else:
                assert manager.snapshot().next_action == 'pairing_required'
                assert requests == []
        finally:
            manager.disconnect()
            await asyncio.sleep(.25)
            await runner.cleanup()
            hub.close()
    asyncio.run(check())
