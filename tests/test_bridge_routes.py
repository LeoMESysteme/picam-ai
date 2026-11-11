"""Actual TLS HTTP/WSS boundaries with a contract-compatible test-only hub."""

import asyncio
import ssl
from contextlib import asynccontextmanager
from dataclasses import dataclass

import aiohttp
import pytest
from aiohttp import web

from dispread.bridge.identity import DeviceIdentity
from dispread.bridge.pairing import PairingStore
from dispread.bridge.protocol import decode_v2, encode_v2, parse_profile
from dispread.bridge.types import PeerHello
from dispread.workbench.server import make_app


@dataclass
class Lease:
    lease_id: str


class FakeHub:
    def __init__(self, pi_id):
        self.pi_id = pi_id
        self.leases = {}
        self.exchanged = []
        self.detached = []

    def prepare(self, transport, client_id, lease=None):
        return PeerHello(self.pi_id, client_id, 2, transport, None, "idle", "output_off")

    def attach(self, client_id, transport, capabilities=None):
        self.capabilities = capabilities
        lease = Lease("lease-" + str(len(self.leases) + 1))
        self.leases[lease.lease_id] = client_id
        return lease

    def detach(self, lease_id):
        self.detached.append(lease_id)
        self.leases.pop(lease_id, None)

    def exchange(self, lease_id, message):
        self.exchanged.append(message)
        return dict(
            version=2,
            type="idle",
            pi_id=self.pi_id,
            client_id=self.leases[lease_id],
            request_id=message["request_id"],
            run_id=None,
            lease_id=lease_id,
            release_block="output_off",
        )


@pytest.fixture(scope="module")
def identity(tmp_path_factory):
    return DeviceIdentity.load_or_create(tmp_path_factory.mktemp("routes-pi") / "identity", "test-pi")


@asynccontextmanager
async def service(tmp_path, identity, *, tls=True, configured_hub=True, real_hub=False):
    store = PairingStore(tmp_path / "pairing")
    if real_hub:
        from dispread.bridge.hub import BridgeHub
        hub = BridgeHub(identity.pi_id, tmp_path / 'audit', identity=identity, pairing_store=store)
    else:
        hub = FakeHub(identity.pi_id)
    from dispread.workbench.controller import Controller

    controller = Controller(tmp_path / "data", simulate=True)
    app = make_app(
        controller,
        verifier=lambda password: password == "local-test",
        bridge_identity=identity,
        bridge_pairing_store=store,
        bridge_hub=hub if configured_hub else None,
        bridge_name="Labor",
        bridge_endpoints=("https://configured.example:8080",),
    )
    runner = web.AppRunner(app, access_log=None, shutdown_timeout=0.5)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=identity.tls_context() if tls else None)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    base = f"{'https' if tls else 'http'}://127.0.0.1:{port}"
    context = ssl.create_default_context(cadata=identity.certificate_pem)
    # The profile pins the Pi URI identity, not DHCP hostnames. Chain/time remain checked.
    context.check_hostname = False
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=context), cookie_jar=aiohttp.CookieJar(unsafe=True)
    ) as client:
        try:
            yield client, base, store, hub
        finally:
            await runner.cleanup()
            if real_hub:
                hub.close()


async def login(client, base):
    headers = {"Origin": base}
    assert (await client.post(base + "/login", json={"password": "local-test"}, headers=headers)).status == 200
    status = await (await client.get(base + "/status")).json()
    return {**headers, "X-CSRF-Token": status["csrf"]}


def hello(identity, **changes):
    return dict(
        version=2,
        type="hello",
        request_id="req-1",
        pi_id=identity.pi_id,
        client_id="client-a",
        protocol_version=2,
        transport="network",
        run_id=None,
        state="connecting",
        release_block=None,
        capabilities={},
        permissions=[],
        **changes,
    )


async def connect(client, base, store, identity):
    token = store.redeem_offer(store.create_offer("network"), "client-a", "network")
    ws = await client.ws_connect(base + "/bridge/v2", headers={"Authorization": "Bearer " + token})
    await ws.send_str(encode_v2(hello(identity)).decode())
    response = decode_v2((await ws.receive_str(timeout=1)).encode())
    return ws, response


def test_profile_offers_and_revoke_require_operator_and_csrf(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            assert (await client.get(base + "/live/bridge/profile")).status == 401
            assert (await client.post(base + "/live/bridge/offers", json={"transport": "network"})).status == 401
            headers = await login(client, base)
            assert (
                await client.post(base + "/live/bridge/offers", json={"transport": "network"}, headers={"Origin": base})
            ).status == 403
            assert (await client.delete(base + "/live/bridge/clients/client-a", headers={"Origin": base})).status == 403
            response = await client.get(base + "/live/bridge/profile", headers={"Host": "attacker.example"})
            profile = parse_profile(await response.read())
            assert profile.pi_id == identity.pi_id
            assert profile.endpoints == ("https://configured.example:8080",)
            assert profile.pairing_offer is None
            offer = await (
                await client.post(base + "/live/bridge/offers", json={"transport": "network"}, headers=headers)
            ).json()
            assert len(offer["offer"]) == 43
            assert offer["expires_in_s"] == 300

    asyncio.run(check())


def test_pair_exchange_is_tls_bounded_once_and_network_scoped(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            payload = dict(
                pi_id=identity.pi_id, client_id="client-a", transport="network", offer=store.create_offer("network")
            )
            response = await client.post(base + "/bridge/v2/pair", json=payload)
            assert response.status == 200
            token = (await response.json())["token"]
            assert store.authorize(token, "network") == "client-a"
            assert (await client.post(base + "/bridge/v2/pair", json=payload)).status == 401
            payload["offer"] = store.create_offer("uart")
            payload["transport"] = "uart"
            assert (await client.post(base + "/bridge/v2/pair", json=payload)).status == 400
            assert (await client.post(base + "/bridge/v2/pair", data=b"x" * 4097)).status == 413
        async with service(tmp_path / "plain", identity, tls=False) as (client, base, store, hub):
            payload = dict(
                pi_id=identity.pi_id, client_id="client-a", transport="network", offer=store.create_offer("network")
            )
            assert (await client.post(base + "/bridge/v2/pair", json=payload)).status == 403

    asyncio.run(check())


def test_v2_requires_scoped_token_and_rejects_cookie_and_url_auth(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            await login(client, base)
            token = store.redeem_offer(store.create_offer("uart"), "client-a", "uart")
            for suffix, headers in [("", {}), ("?token=" + token, {}), ("", {"Authorization": "Bearer " + token})]:
                with pytest.raises(aiohttp.WSServerHandshakeError) as error:
                    await client.ws_connect(base + "/bridge/v2" + suffix, headers=headers)
                assert error.value.status in (400, 401)

    asyncio.run(check())


def test_v2_readiness_without_measurement_and_bound_requests(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            ws, response = await connect(client, base, store, identity)
            assert response["state"] == "idle" and response["run_id"] is None
            assert response["release_block"] == "output_off"
            poll = dict(
                version=2,
                type="poll",
                request_id="poll-1",
                pi_id=identity.pi_id,
                client_id="client-a",
                lease_id=response["lease_id"],
                run_id=None,
            )
            await ws.send_str(encode_v2(poll).decode())
            assert (await ws.receive_json(timeout=1))["type"] == "idle"
            assert len(hub.exchanged) == 1
            poll["client_id"] = "client-b"
            await ws.send_str(encode_v2(poll).decode())
            assert (await ws.receive(timeout=1)).type == aiohttp.WSMsgType.CLOSE
            assert len(hub.exchanged) == 1
            assert response["lease_id"] in hub.detached

    asyncio.run(check())


@pytest.mark.parametrize(
    "mutation", [{"version": 1}, {"pi_id": "other-pi"}, {"transport": "uart"}, {"client_id": "other-client"}]
)
def test_v2_rejects_wrong_version_identity_client_transport(tmp_path, identity, mutation):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            token = store.redeem_offer(store.create_offer("network"), "client-a", "network")
            ws = await client.ws_connect(base + "/bridge/v2", headers={"Authorization": "Bearer " + token})
            await ws.send_json({**hello(identity), **mutation})
            assert (await ws.receive(timeout=1)).type == aiohttp.WSMsgType.CLOSE
            assert not hub.leases

    asyncio.run(check())


def test_revoked_client_loses_active_connection(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            ws, response = await connect(client, base, store, identity)
            store.revoke("client-a")  # Also catches local CLI/other-process revocation, with no client traffic.
            assert (await ws.receive(timeout=1)).type == aiohttp.WSMsgType.CLOSE
            assert response["lease_id"] in hub.detached
            assert not hub.leases

    asyncio.run(check())


def test_identity_private_key_not_downloadable(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            await login(client, base)
            profile = await (await client.get(base + "/live/bridge/profile")).read()
            assert b"PRIVATE KEY" not in profile and b"private_key" not in profile
            for path in (
                "/live/bridge/identity.json",
                "/bridge/identity.json",
                "/live/bridge/key.pem",
                "/static/../bridge/identity.json",
            ):
                assert (await client.get(base + path)).status == 404

    asyncio.run(check())


def test_unconfigured_hub_never_claims_readiness(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity, configured_hub=False) as (client, base, store, hub):
            token = store.redeem_offer(store.create_offer("network"), "client-a", "network")
            with pytest.raises(aiohttp.WSServerHandshakeError) as error:
                await client.ws_connect(base + "/bridge/v2", headers={"Authorization": "Bearer " + token})
            assert error.value.status == 503

    asyncio.run(check())


def test_portable_bind_and_explicit_bridge_options():
    from dispread.workbench.cli import parser

    args = parser().parse_args(["serve"])
    assert args.host == "127.0.0.1"
    assert args.bridge_directory is None
    args = parser().parse_args(
        [
            "serve",
            "--bridge-directory",
            "/existing",
            "--bridge-endpoint",
            "https://pi.example:8080",
            "--bridge-name",
            "Labor",
            "--bridge-discovery",
        ]
    )
    assert args.bridge_endpoint == ["https://pi.example:8080"] and args.bridge_discovery


def test_pair_response_uncacheable_and_bounded_source_limit(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            payload = dict(
                pi_id=identity.pi_id, client_id="client-a", transport="network", offer=store.create_offer("network")
            )
            response = await client.post(base + "/bridge/v2/pair", json=payload)
            assert response.status == 200
            assert response.headers.get("Cache-Control") == "no-store"
            for _ in range(4):
                assert (await client.post(base + "/bridge/v2/pair", json=payload)).status == 401
            assert (await client.post(base + "/bridge/v2/pair", json=payload)).status == 429

    asyncio.run(check())


def test_pair_rejects_duplicate_fields_unknown_identity_and_chunked_oversize(tmp_path, identity):
    async def chunks():
        yield b"{" + b" " * 3000
        await asyncio.sleep(0.01)
        yield b" " * 3000 + b"}"

    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            assert (await client.post(base + "/bridge/v2/pair", data=b'{"offer":"a","offer":"b"}')).status == 400
            assert (
                await client.post(
                    base + "/bridge/v2/pair",
                    json={
                        "pi_id": "other-pi",
                        "client_id": "client-a",
                        "transport": "network",
                        "offer": store.create_offer("network"),
                    },
                )
            ).status == 401
            assert (await client.post(base + "/bridge/v2/pair", data=chunks())).status == 413

    asyncio.run(check())


def test_wss_refuses_plain_http_even_with_valid_token(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity, tls=False) as (client, base, store, hub):
            token = store.redeem_offer(store.create_offer("network"), "client-a", "network")
            with pytest.raises(aiohttp.WSServerHandshakeError) as error:
                await client.ws_connect(base + "/bridge/v2", headers={"Authorization": "Bearer " + token})
            assert error.value.status == 403

    asyncio.run(check())


def test_bridge_serve_loads_only_existing_identity_and_preserves_legacy_tls(tmp_path, monkeypatch, identity):
    from argparse import Namespace

    from dispread.bridge import identity as identity_module
    from dispread.workbench.server import bridge_service_config

    monkeypatch.setattr(identity_module, "local_hardware_id", lambda: "test-pi")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert.write_text("existing certificate")
    key.write_text("existing private key")
    args = Namespace(
        bridge_directory=str(identity.directory),
        bridge_endpoint=["https://pi.example:8080"],
        bridge_name="Labor",
        bridge_discovery=False,
        cert=str(cert),
        key=str(key),
    )
    config, tls = bridge_service_config(args)
    assert config["bridge_identity"].pi_id == identity.pi_id
    assert config["bridge_endpoints"] == ("https://pi.example:8080",)
    assert isinstance(tls, ssl.SSLContext)
    assert cert.read_text() == "existing certificate" and key.read_text() == "existing private key"
    args.bridge_directory = str(tmp_path / "never-provision")
    with pytest.raises(ValueError):
        bridge_service_config(args)
    assert not (tmp_path / "never-provision" / "identity.json").exists()
    args.bridge_directory = None
    with pytest.raises(ValueError):
        bridge_service_config(args)
    args.bridge_endpoint = []
    assert bridge_service_config(args) == ({}, None)


def test_configured_pam_account_requires_matching_effective_non_root_user(monkeypatch):
    from types import SimpleNamespace

    from dispread.workbench import server

    monkeypatch.setattr(server.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(server.pwd, "getpwuid", lambda uid: SimpleNamespace(pw_name="operator"))
    assert server.service_pam_user("operator") == "operator"
    with pytest.raises(ValueError):
        server.service_pam_user("someone-else")
    monkeypatch.setattr(server.os, "geteuid", lambda: 0)
    with pytest.raises(ValueError):
        server.service_pam_user("operator")


def test_pair_accepts_valid_fragmented_body(tmp_path, identity):
    import json

    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            payload = json.dumps(
                dict(
                    pi_id=identity.pi_id, client_id="client-a", transport="network", offer=store.create_offer("network")
                )
            ).encode()

            async def chunks():
                yield payload[:10]
                await asyncio.sleep(0.01)
                yield payload[10:]

            assert (await client.post(base + "/bridge/v2/pair", data=chunks())).status == 200

    asyncio.run(check())


def test_pair_rejects_excessive_json_nesting_without_server_error(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            assert (await client.post(base + "/bridge/v2/pair", data=b"[" * 1500 + b"0" + b"]" * 1500)).status == 400

    asyncio.run(check())


def test_store_read_error_closes_silent_connection_and_detaches(tmp_path, identity, monkeypatch, caplog):
    import sqlite3

    task_errors = []

    async def check():
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(lambda loop, context: task_errors.append(context))
        async with service(tmp_path, identity) as (client, base, store, hub):
            ws, response = await connect(client, base, store, identity)

            def unavailable(token, transport):
                raise sqlite3.OperationalError("fixture database unavailable")

            monkeypatch.setattr(store, "authorize", unavailable)
            assert (await ws.receive(timeout=0.9)).type == aiohttp.WSMsgType.CLOSE
            assert response["lease_id"] in hub.detached
            assert not hub.leases

    asyncio.run(check())
    assert not task_errors
    assert not any("Error handling request" in record.getMessage() for record in caplog.records)


@asynccontextmanager
async def locked_pairing_database(store, *, mode):
    """Real SQLite contention, with a bounded failsafe for pre-fix loop stalls."""
    import sqlite3
    import threading

    database = sqlite3.connect(store.path, isolation_level=None, check_same_thread=False)
    database.execute("BEGIN " + mode)
    guard = threading.Lock()

    def release():
        with guard:
            database.rollback()

    timer = threading.Timer(1.5, release)
    timer.start()
    try:
        yield release
    finally:
        release()
        timer.cancel()
        timer.join()
        database.close()


def test_database_read_contention_closes_lease_before_pending_read_completes(tmp_path, identity, monkeypatch):
    import threading

    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            ws, response = await connect(client, base, store, identity)
            original = store.authorize
            completed = threading.Event()

            def observed(token, transport):
                try:
                    return original(token, transport)
                finally:
                    completed.set()

            async with locked_pairing_database(store, mode="EXCLUSIVE") as release:
                monkeypatch.setattr(store, "authorize", observed)
                started = asyncio.get_running_loop().time()
                assert (await ws.receive(timeout=0.9)).type == aiohttp.WSMsgType.CLOSE
                assert asyncio.get_running_loop().time() - started < 0.9
                assert response["lease_id"] in hub.detached and not hub.leases
                # Cancelling a thread await cannot cancel SQLite. The lease must
                # already be gone while the original bounded DB read still waits.
                assert not completed.is_set()
                release()
                assert await asyncio.to_thread(completed.wait, 1)
                assert not hub.leases

    asyncio.run(check())


@pytest.mark.parametrize("operation", ["create_offer", "revoke", "redeem_offer"])
def test_store_writes_wait_off_loop_while_silent_connection_is_monitored(tmp_path, identity, monkeypatch, operation):
    import threading

    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            ws, hello_response = await connect(client, base, store, identity)
            headers = await login(client, base)
            offer = store.create_offer("network")
            entered, completed, checked = threading.Event(), threading.Event(), threading.Event()
            original = getattr(store, operation)
            original_authorize = store.authorize

            def observed_authorize(*args):
                result = original_authorize(*args)
                checked.set()
                return result

            monkeypatch.setattr(store, "authorize", observed_authorize)

            def observed(*args):
                entered.set()
                try:
                    return original(*args)
                finally:
                    completed.set()

            monkeypatch.setattr(store, operation, observed)
            async with locked_pairing_database(store, mode="IMMEDIATE") as release:
                started = asyncio.get_running_loop().time()
                if operation == "create_offer":
                    pending = asyncio.create_task(
                        client.post(base + "/live/bridge/offers", json={"transport": "network"}, headers=headers)
                    )
                elif operation == "revoke":
                    pending = asyncio.create_task(
                        client.delete(base + "/live/bridge/clients/client-a", headers=headers)
                    )
                else:
                    pending = asyncio.create_task(
                        client.post(
                            base + "/bridge/v2/pair",
                            json={
                                "pi_id": identity.pi_id,
                                "client_id": "client-b",
                                "transport": "network",
                                "offer": offer,
                            },
                        )
                    )
                assert await asyncio.to_thread(entered.wait, 1)
                assert await asyncio.to_thread(checked.wait, 0.8)
                assert asyncio.get_running_loop().time() - started < 0.9
                assert not completed.is_set() and not pending.done()
                assert (await client.get(base + "/live/bridge/profile")).status == 200
                assert not completed.is_set()
                assert hello_response["lease_id"] in hub.leases
                release()
                assert (await pending).status == 200
                assert completed.is_set()
            await ws.close()

    asyncio.run(check())


def test_revoked_upgraded_client_without_hello_closes_without_attach(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            token = store.redeem_offer(store.create_offer("network"), "client-a", "network")
            ws = await client.ws_connect(base + "/bridge/v2", headers={"Authorization": "Bearer " + token})
            store.revoke("client-a")
            assert (await ws.receive(timeout=0.9)).type == aiohttp.WSMsgType.CLOSE
            assert not hub.leases and not hub.detached and not hub.exchanged

    asyncio.run(check())


def test_revocation_aborts_transport_when_close_handshake_stalls(tmp_path, identity, monkeypatch):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            ws, response = await connect(client, base, store, identity)
            original = web.WebSocketResponse.close

            async def stalled_close(self, *args, **kwargs):
                await asyncio.Event().wait()

            monkeypatch.setattr(web.WebSocketResponse, "close", stalled_close)
            try:
                store.revoke("client-a")
                message = await ws.receive(timeout=0.9)
                assert message.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}
                assert response["lease_id"] in hub.detached and not hub.leases
            finally:
                monkeypatch.setattr(web.WebSocketResponse, "close", original)

    asyncio.run(check())


def test_heartbeat_is_explicitly_allowed_without_poll(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            token = store.redeem_offer(store.create_offer('network'), 'client-a', 'network')
            async with client.ws_connect(base + '/bridge/v2', headers={'Authorization': 'Bearer ' + token}) as ws:
                await ws.send_str(encode_v2(hello(identity)).decode())
                first = decode_v2((await ws.receive()).data.encode())
                message = dict(version=2, type='heartbeat', request_id='beat', pi_id=identity.pi_id,
                               client_id='client-a', lease_id=first['lease_id'], run_id=None)
                await ws.send_str(encode_v2(message).decode())
                response = await ws.receive(timeout=1)
                assert response.type == aiohttp.WSMsgType.TEXT
                assert hub.exchanged == [message]
    asyncio.run(check())


def test_operator_uart_prepare_requires_csrf_and_is_explicit(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            prepared = []
            hub.prepare_uart = lambda: prepared.append(True) or {'uart_prepared': True}
            hub.status = lambda: {'uart_prepared': bool(prepared)}
            assert (await client.post(base + '/live/bridge/prepare', json={'transport': 'uart'})).status == 401
            headers = await login(client, base)
            await client.get(base + '/live/bridge/profile')
            assert prepared == []
            assert (await client.post(base + '/live/bridge/prepare', json={'transport': 'uart'})).status == 403
            response = await client.post(base + '/live/bridge/prepare', json={'transport': 'uart'}, headers=headers)
            assert response.status == 200
            assert prepared == [True]
            response = await client.get(base + '/live/bridge/status')
            assert (await response.json())['uart_prepared'] is True
    asyncio.run(check())


def test_real_hub_wss_idle_run_resync_demo_and_lease_exclusion(tmp_path, identity):
    async def check():
        async with service(tmp_path, identity, real_hub=True) as (client, base, store, hub):
            token = store.redeem_offer(store.create_offer('network'), 'client-a', 'network')
            headers = {'Authorization': 'Bearer ' + token}
            async with client.ws_connect(base + '/bridge/v2', headers=headers) as ws:
                await ws.send_str(encode_v2(hello(identity)).decode())
                first = decode_v2((await ws.receive(timeout=1)).data.encode())
                assert first['run_id'] is None and first['state'] == 'output_off'
                async with client.ws_connect(base + '/bridge/v2', headers=headers) as duplicate:
                    await duplicate.send_str(encode_v2(hello(identity)).decode())
                    conflict = decode_v2((await duplicate.receive(timeout=1)).data.encode())
                    assert conflict['type'] == 'error' and conflict['code'] == 'lease_unavailable'
                    assert 'existing connection' in conflict['detail']
                message = dict(version=2, type='heartbeat', request_id='beat', pi_id=identity.pi_id,
                               client_id='client-a', lease_id=first['lease_id'], run_id=None)
                hub.reserve_real_run('real')
                await ws.send_str(encode_v2(message).decode())
                resync = decode_v2((await ws.receive(timeout=1)).data.encode())
                assert resync['type'] == 'hello' and resync['run_id'] == 'real'
                hub.release_real_run('real')
                demo = dict(version=2, type='demo_request', request_id='demo', pi_id=identity.pi_id,
                            client_id='client-a', run_id=None, transport='network', count=10, rate_hz=10)
                await ws.send_str(encode_v2(demo).decode())
                started = decode_v2((await ws.receive(timeout=1)).data.encode())
                assert started['type'] == 'hello' and started['run_id'] != 'real'
                await ws.send_str(encode_v2({**message, 'type': 'poll', 'run_id': started['run_id']}).decode())
                output = decode_v2((await ws.receive(timeout=1)).data.encode())
                assert output['type'] == 'record' and output['demo'] is True
                assert output['record']['capture_timestamp']['base'] == 'synthetic'
    asyncio.run(check())


def test_revocation_during_pending_attach_does_not_leave_late_lease(tmp_path, identity):
    import threading
    async def check():
        async with service(tmp_path, identity) as (client, base, store, hub):
            entered, release = threading.Event(), threading.Event()
            original = hub.attach
            def blocked(client_id, transport, **kwargs):
                entered.set()
                assert release.wait(2)
                return original(client_id, transport, **kwargs)
            hub.attach = blocked
            token = store.redeem_offer(store.create_offer('network'), 'client-a', 'network')
            async with client.ws_connect(base + '/bridge/v2', headers={'Authorization': 'Bearer ' + token}) as ws:
                await ws.send_str(encode_v2(hello(identity)).decode())
                assert await asyncio.to_thread(entered.wait, 1)
                store.revoke('client-a')
                try:
                    assert (await ws.receive(timeout=1)).type == aiohttp.WSMsgType.CLOSE
                finally:
                    release.set()
                for _ in range(100):
                    if hub.detached:
                        break
                    await asyncio.sleep(.01)
                assert hub.detached and not hub.leases
    asyncio.run(check())
