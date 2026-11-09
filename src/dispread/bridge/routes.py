"""Pi operator routes and independently authenticated, TLS-only v2 WSS."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import sqlite3
import time
from collections import defaultdict, deque
from dataclasses import asdict

from aiohttp import WSMsgType, web

from .pairing import PairingError
from .protocol import MAX_MESSAGE_BYTES, decode_v2, encode_v2, parse_profile
from .types import BridgeProfile

PUBLIC_PATHS = frozenset({"/bridge/v2", "/bridge/v2/pair"})
_AUTH_CHECK_TIMEOUT_S = 0.35
_AUTH_CHECK_INTERVAL_S = 0.2
_AUTH_CLOSE_TIMEOUT_S = 0.2


class _StoreUnavailable(OSError):
    """Storage could not establish authorization, without exposing its contents."""


async def _store_io(operation, *args):
    # SQLite's own busy timeout may be ten seconds. Only its I/O runs here;
    # late completion can never attach a Hub lease or send a bridge record.
    try:
        return await asyncio.to_thread(operation, *args)
    except (sqlite3.Error, OSError):
        raise _StoreUnavailable("Credential store unavailable") from None


class UnconfiguredHub:
    """No pretend readiness before the real exclusive output hub is attached."""

    def prepare(self, transport, client_id):
        raise ValueError("bridge output hub is not configured")


class _SourceLimit:
    def __init__(self):
        self.sources = defaultdict(deque)
        self.all = deque()

    def allow(self, source):
        now = time.monotonic()
        for queue in [self.all, *self.sources.values()]:
            while queue and queue[0] <= now - 60:
                queue.popleft()
        self.sources = defaultdict(deque, {key: value for key, value in self.sources.items() if value})
        if len(self.sources) >= 1024 and source not in self.sources:
            return False
        queue = self.sources[source]
        if len(queue) >= 5 or len(self.all) >= 40:
            return False
        queue.append(now)
        self.all.append(now)
        return True


def _tls(request):
    if not request.secure:
        raise web.HTTPForbidden(text="Bridge requires TLS")
    if request.query_string:
        raise web.HTTPBadRequest(text="Bridge credentials and options must not be in URLs")


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


async def _body(request):
    if request.content_length is not None and request.content_length > 4096:
        raise web.HTTPRequestEntityTooLarge(max_size=4096, actual_size=request.content_length)
    try:
        async with asyncio.timeout(2):
            raw = bytearray()
            while not request.content.at_eof() and len(raw) <= 4096:
                raw.extend(await request.content.read(4097 - len(raw)))
    except TimeoutError:
        raise web.HTTPRequestTimeout() from None
    if len(raw) > 4096 or not request.content.at_eof():
        raise web.HTTPRequestEntityTooLarge(max_size=4096, actual_size=4097)
    try:
        value = json.loads(raw, object_pairs_hook=_json_pairs)
    except (ValueError, UnicodeError):
        raise web.HTTPBadRequest(text="Invalid bridge request") from None
    if not isinstance(value, dict):
        raise web.HTTPBadRequest(text="Expected object")
    return value


def add_bridge_routes(app, identity, pairing_store, hub, authorize_operator, *, endpoints=(), name="Dispread Pi"):
    """Register routes without exposing the identity directory as static files.

    Hub methods are synchronous and bounded: prepare(transport, client_id) ->
    PeerHello; attach(client_id, transport) -> lease with lease_id;
    detach(lease_id); exchange(lease_id, strict_message) -> strict v2 dict.
    No Hub receives a credential. Operator callback must enforce login/CSRF.
    """
    public_profile = asdict(
        BridgeProfile(1, identity.pi_id, name, identity.certificate_pem, identity.fingerprint, tuple(endpoints), 2)
    )
    parse_profile(json.dumps(public_profile).encode())
    hub = hub if hub is not None else UnconfiguredHub()
    limiter = _SourceLimit()
    connections = set()

    async def authorized_client(token):
        try:
            async with asyncio.timeout(_AUTH_CHECK_TIMEOUT_S):
                return await _store_io(pairing_store.authorize, token, "network")
        except TimeoutError:
            # Cancellation bounds the lease decision; SQLite may finish later
            # in its thread. Its eventual result cannot restore this connection.
            raise _StoreUnavailable("Credential check deadline exceeded") from None

    async def operator(request):
        result = authorize_operator(request)
        if inspect.isawaitable(result):
            result = await result
        if result is False:
            raise web.HTTPUnauthorized()

    async def profile(request):
        await operator(request)
        return web.json_response(public_profile, headers={"Content-Disposition": 'attachment; filename="pi.dispread"'})

    async def bridge_status(request):
        await operator(request)
        if not hasattr(hub, 'status'):
            raise web.HTTPServiceUnavailable(text='Bridge hub unavailable')
        return web.json_response(hub.status())

    async def prepare_uart(request):
        await operator(request)
        data = await _body(request)
        if data != {'transport': 'uart'}:
            raise web.HTTPBadRequest(text='Explicit UART transport required')
        if not hasattr(hub, 'prepare_uart'):
            raise web.HTTPServiceUnavailable(text='Bridge hub unavailable')
        try:
            result = await asyncio.to_thread(hub.prepare_uart)
        except (ValueError, OSError):
            raise web.HTTPConflict(text='UART unavailable or occupied; release its owner first') from None
        return web.json_response(result)

    async def stop_uart(request):
        await operator(request)
        if not hasattr(hub, 'stop_uart'):
            raise web.HTTPServiceUnavailable(text='Bridge hub unavailable')
        await asyncio.to_thread(hub.stop_uart)
        return web.json_response(hub.status())

    async def offers(request):
        await operator(request)
        data = await _body(request)
        if set(data) - {"transport", "client_id"} or "transport" not in data:
            raise web.HTTPBadRequest(text="Invalid offer request")
        try:
            offer = await _store_io(pairing_store.create_offer, data["transport"], data.get("client_id"))
        except PairingError:
            raise web.HTTPBadRequest(text="Offer request refused") from None
        except _StoreUnavailable:
            raise web.HTTPServiceUnavailable(text="Credential store unavailable; offer not confirmed") from None
        return web.json_response({"offer": offer, "expires_in_s": 300})

    async def revoke(request):
        await operator(request)
        try:
            await _store_io(pairing_store.revoke, request.match_info["client_id"])
        except PairingError:
            raise web.HTTPBadRequest(text="Invalid client") from None
        except _StoreUnavailable:
            raise web.HTTPServiceUnavailable(text="Credential store unavailable; revocation not confirmed") from None
        return web.json_response({"ok": True})

    async def pair(request):
        _tls(request)
        if not limiter.allow(request.remote):
            raise web.HTTPTooManyRequests(text="Pairing rate limit")
        data = await _body(request)
        if set(data) != {"pi_id", "client_id", "transport", "offer"} or data["transport"] != "network":
            raise web.HTTPBadRequest(text="Invalid network pairing request")
        if data["pi_id"] != identity.pi_id:
            raise web.HTTPUnauthorized(text="Pairing refused")
        try:
            token = await _store_io(pairing_store.redeem_offer, data["offer"], data["client_id"], "network")
        except (ValueError, TypeError):
            raise web.HTTPUnauthorized(text="Pairing refused or expired; check identity and offer validity") from None
        except _StoreUnavailable:
            raise web.HTTPServiceUnavailable(text="Credential store unavailable; pairing not confirmed") from None
        return web.json_response(
            {"pi_id": identity.pi_id, "client_id": data["client_id"], "transport": "network", "token": token},
            headers={"Cache-Control": "no-store", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff"},
        )

    async def authorize(request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or len(header) > 128:
            raise web.HTTPUnauthorized(text="Network client credential required")
        token = header[7:]
        try:
            client_id = await authorized_client(token)
        except (ValueError, TypeError):
            raise web.HTTPUnauthorized(text="Network client credential refused") from None
        except _StoreUnavailable:
            raise web.HTTPServiceUnavailable(text="Credential store unavailable") from None
        return token, client_id

    async def websocket(request):
        _tls(request)
        token, client_id = await authorize(request)
        try:
            readiness = hub.prepare("network", client_id)
        except ValueError:
            raise web.HTTPServiceUnavailable(text="Bridge hub unavailable") from None
        if (readiness.pi_id, readiness.client_id, readiness.transport, readiness.protocol_version) != (
            identity.pi_id,
            client_id,
            "network",
            2,
        ):
            raise web.HTTPServiceUnavailable(text="Bridge hub identity mismatch")
        ws = web.WebSocketResponse(heartbeat=15, max_msg_size=MAX_MESSAGE_BYTES)
        await ws.prepare(request)
        connections.add(ws)
        lease_id = None
        created_lease = [None]
        watchdog = None
        authorization_ended = False

        async def check_authorization():
            current = await authorized_client(token)
            if authorization_ended or ws.closed or current != client_id:
                raise PairingError("Connection authorization ended")

        async def detach():
            nonlocal lease_id
            value = lease_id or created_lease[0]
            lease_id = created_lease[0] = None
            if value is not None:
                try:
                    async with asyncio.timeout(.35):
                        await asyncio.to_thread(hub.detach, value)
                except TimeoutError:
                    # Late audit cleanup cannot restore the connection/lease.
                    pass

        async def close_connection(*, message=b"Client authorization ended"):
            try:
                async with asyncio.timeout(_AUTH_CLOSE_TIMEOUT_S):
                    await ws.close(code=1008, message=message)
            except asyncio.CancelledError:
                if request.transport is not None:
                    request.transport.abort()
                raise
            except Exception:
                # A peer that stalls close/drain cannot retain the transport.
                if request.transport is not None:
                    request.transport.abort()

        async def monitor():
            nonlocal authorization_ended
            while not ws.closed:
                await asyncio.sleep(_AUTH_CHECK_INTERVAL_S)
                try:
                    await check_authorization()
                except Exception:
                    authorization_ended = True
                    # An unavailable authorization source never leaves a lease live.
                    try:
                        await detach()
                    finally:
                        await close_connection()
                    return

        def bound(message):
            if message["pi_id"] != identity.pi_id or message["client_id"] != client_id:
                raise ValueError("connection identity mismatch")

        # Revocation applies from upgrade onward, including a silent client
        # that never sends hello. No lease exists until reauthorization below.
        watchdog = asyncio.create_task(monitor())
        try:
            first = await ws.receive(timeout=5)
            if first.type != WSMsgType.TEXT:
                raise ValueError("expected text hello")
            message = decode_v2(first.data.encode("utf-8"))
            bound(message)
            if (
                message["type"] != "hello"
                or message["transport"] != "network"
                or message["run_id"] is not None
                or message.get("lease_id") is not None
            ):
                raise ValueError("expected network readiness hello")
            await check_authorization()
            def attach_authorized():
                lease = hub.attach(client_id, "network")
                created_lease[0] = lease.lease_id
                if authorization_ended or ws.closed:
                    hub.detach(lease.lease_id)
                    raise ValueError('Connection authorization ended')
                return lease

            try:
                lease = await asyncio.to_thread(attach_authorized)
            except ValueError:
                if not authorization_ended and not ws.closed:
                    response = dict(version=2, type='error', request_id=message['request_id'],
                                    pi_id=identity.pi_id, client_id=client_id, run_id=None,
                                    code='lease_unavailable',
                                    detail='Bridge lease unavailable; close the existing connection first')
                    async with asyncio.timeout(.35):
                        await ws.send_str(encode_v2(response).decode('utf-8'))
                raise
            await check_authorization()
            lease_id = lease.lease_id
            readiness = hub.prepare("network", client_id)
            lease.release = readiness.release  # angekuendigter Freigabestand (R1)
            response = dict(
                version=2,
                type="hello",
                request_id=message["request_id"],
                pi_id=identity.pi_id,
                client_id=client_id,
                protocol_version=2,
                transport="network",
                run_id=readiness.run_id,
                state=readiness.state,
                release_block=readiness.release_block,
                lease_id=lease_id,
                capabilities={"protocol_version": 2, "dut_output": False,
                              "heartbeat_interval_s": 1, "lease_timeout_s": 5},
                permissions=["readiness", "demo"],
                **({"release": readiness.release} if readiness.release else {}),
            )
            await ws.send_str(encode_v2(response).decode("utf-8"))
            async for frame in ws:
                if frame.type != WSMsgType.TEXT:
                    break
                await check_authorization()
                if lease_id is None:
                    raise ValueError("authorization ended")
                message = decode_v2(frame.data.encode("utf-8"))
                bound(message)
                if message["type"] not in {"poll", "ack", "heartbeat", "demo_request"}:
                    raise ValueError("unexpected client message")
                if message["type"] == "demo_request":
                    if message["transport"] != "network":
                        raise ValueError("transport mismatch")
                elif message["lease_id"] != lease_id:
                    raise ValueError("lease mismatch")
                # The hub owns run transitions and checks run binding before output.
                response = await asyncio.to_thread(hub.exchange, lease_id, message)
                bound(response)
                if response.get("lease_id", lease_id) != lease_id or response["request_id"] != message["request_id"]:
                    raise ValueError("hub response binding mismatch")
                await ws.send_str(encode_v2(response).decode("utf-8"))
        except (ValueError, TypeError, KeyError, OSError, TimeoutError, ConnectionError, sqlite3.Error):
            pass
        finally:
            authorization_ended = True
            try:
                if watchdog is not None:
                    watchdog.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await watchdog
            finally:
                try:
                    await detach()
                finally:
                    connections.discard(ws)
                    await close_connection()
        return ws

    async def shutdown(_):
        await asyncio.gather(*(ws.close(code=1001, message=b"Service stopping") for ws in tuple(connections)))

    app.on_shutdown.append(shutdown)
    app.router.add_get("/live/bridge/status", bridge_status)
    app.router.add_post("/live/bridge/prepare", prepare_uart)
    app.router.add_delete("/live/bridge/prepare", stop_uart)
    app.router.add_get("/live/bridge/profile", profile)
    app.router.add_post("/live/bridge/offers", offers)
    app.router.add_delete("/live/bridge/clients/{client_id}", revoke)
    app.router.add_post("/bridge/v2/pair", pair)
    app.router.add_get("/bridge/v2", websocket)
