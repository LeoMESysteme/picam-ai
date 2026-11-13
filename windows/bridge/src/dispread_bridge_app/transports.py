"""Bounded real WSS/pySerial adapters; no transport contains COM-output logic."""
from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import hashlib
import hmac
import json
import secrets
import ssl
import threading
import time
from urllib.parse import urlsplit, urlunsplit

from dispread.bridge.identity import verify_certificate, verify_hello
from dispread.bridge.protocol import (
    MAX_MESSAGE_BYTES,
    V2LineReader,
    _endpoint,
    _token,
    canonical_uart_hello,
    decode_v2,
    encode_v2,
)


class TransportError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def resolve_endpoints(endpoint: str) -> tuple[str, str]:
    try:
        _endpoint(endpoint)
        url = urlsplit(endpoint)
        if url.path not in ('', '/', '/bridge/v2'):
            raise ValueError('unsupported path')
        return (urlunsplit(('wss', url.netloc, '/bridge/v2', '', '')),
                urlunsplit(('https', url.netloc, '/bridge/v2/pair', '', '')))
    except (TypeError, ValueError):
        raise TransportError('endpoint_unsupported') from None


def _verified(profile):
    try:
        return verify_certificate(profile.certificate_pem, profile.certificate_sha256, profile.pi_id)
    except Exception:
        raise TransportError('profile_invalid') from None


def tls_context(profile):
    _verified(profile)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False  # Pi URI identity, not routing hostname
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cadata=profile.certificate_pem)
    return context


def verify_tls_peer(profile, der):
    """The same DER pin and Pi certificate policy for probes and actual WSS."""
    try:
        if not der or not hmac.compare_digest(hashlib.sha256(der).hexdigest(), profile.certificate_sha256):
            raise ValueError('pin mismatch')
        verify_certificate(ssl.DER_cert_to_PEM_cert(der), profile.certificate_sha256, profile.pi_id)
    except Exception:
        raise TransportError('peer_invalid') from None


def _bound(reply, request):
    reply = decode_v2(encode_v2(reply))
    if any(reply[k] != request[k] for k in ('pi_id', 'client_id', 'request_id')):
        raise TransportError('peer_invalid')
    if reply['type'] == 'error':
        raise TransportError('authentication_refused')
    return reply


class SerialTransport:
    """Signed UART preauth; imported pin is verified before sending credentials."""
    def __init__(self, profile, client_id, credential, device, cancel, *, opener=None):
        _verified(profile)
        if device is None or device.port is None:
            raise TransportError('adapter_unavailable')
        if cancel.is_set():
            raise TransportError('cancelled')
        if opener is None:
            from serial import Serial
            opener = Serial
        self._closed = threading.Event()
        self._stream = None
        self._reader = V2LineReader()
        self._messages = []
        self.authenticated_token = None
        try:
            self._stream = opener(port=device.port, baudrate=profile.uart_baud, timeout=.1, write_timeout=.2)
            if cancel.is_set():
                raise TransportError('cancelled')
            nonce = secrets.token_urlsafe(32)
            base = dict(version=2, pi_id=profile.pi_id, client_id=client_id, request_id=secrets.token_hex(16))
            request = dict(base, type='uart_challenge', nonce=nonce)
            self.send(request)
            reply = _bound(self.receive(), request)
            if reply['type'] != 'uart_proof' or reply['nonce'] != nonce:
                raise TransportError('peer_invalid')
            try:
                verify_hello(profile.certificate_pem, canonical_uart_hello(profile.pi_id, client_id, nonce),
                             base64.b64decode(reply['signature'], validate=True))
            except Exception:
                raise TransportError('peer_invalid') from None
            if cancel.is_set():
                raise TransportError('cancelled')
            token = credential or profile.pairing_offer
            if token is None:
                raise TransportError('pairing_required')
            request = dict(base, type='uart_auth', nonce=nonce,
                           mode='token' if credential else 'offer', credential=token)
            self.send(request)
            reply = _bound(self.receive(), request)
            if reply['type'] != 'uart_authenticated':
                raise TransportError('authentication_refused')
            self.authenticated_token = reply['token']
        except Exception as error:
            self.close()
            if isinstance(error, TransportError):
                raise
            raise TransportError('uart_peer_unavailable') from None

    def send(self, message):
        if self._closed.is_set():
            raise TransportError('disconnected')
        data = encode_v2(message)
        try:
            if self._stream.write(data) != len(data):
                raise TransportError('transport_write_uncertain')
        except TransportError:
            raise
        except Exception:
            raise TransportError('uart_peer_unavailable') from None

    def receive(self):
        # Ursache unterscheidbar (13.11.2026: UART-Empfangstest brach ab, der Export
        # sagte nur connection_unavailable): Zeitlimit, unlesbarer Rahmen, Port weg.
        deadline = time.monotonic() + 2
        while not self._closed.is_set() and time.monotonic() < deadline:
            if self._messages:
                return self._messages.pop(0)
            # pySerial read(n) blocks for n bytes or the timeout: read only
            # what is waiting (at least one byte), never a fixed 4096 (R1).
            try:
                waiting = getattr(self._stream, 'in_waiting', 0) or 0
                data = self._stream.read(max(1, min(waiting, 4096)))
            except Exception:
                raise TransportError('uart_port_failed') from None
            try:
                self._messages.extend(self._reader.feed(data))
            except Exception:
                raise TransportError('uart_frame_invalid') from None
        raise TransportError('uart_closed' if self._closed.is_set() else 'uart_timeout')

    def close(self):
        self._closed.set()
        stream, self._stream = self._stream, None
        if stream is not None:
            for name in ('cancel_read', 'cancel_write', 'close'):
                try:
                    operation = getattr(stream, name, None)
                    if operation:
                        operation()
                except Exception:
                    pass


class WssTransport:
    """aiohttp owns WebSocket framing; TLS is profile-local and checked pre-HTTP.

    The connector adapter checks the *actual* TLS peer before returning a socket
    to aiohttp's HTTP writer. A separate preliminary probe is insufficient.
    Redirect tracing refuses the first redirect before any second request.
    """
    def __init__(self, profile, client_id, credential, endpoint, cancel):
        _verified(profile)
        self._ws_url, self._pair_url = resolve_endpoints(endpoint)
        self._profile, self._client_id = profile, client_id
        self._cancel = cancel
        self._loop = asyncio.new_event_loop()
        self._closed = threading.Event()
        self._session = self._ws = None
        self.authenticated_token = None
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name='bridge-wss')
        self._thread.start()
        try:
            self._submit(self._open(credential), timeout=4)
        except Exception:
            self.close()
            raise

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            tasks = asyncio.all_tasks(self._loop)
            for task in tasks:
                task.cancel()
            if tasks:
                self._loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            self._loop.close()

    def _submit(self, coroutine, *, timeout=2.5):
        if self._closed.is_set():
            coroutine.close()
            raise TransportError('disconnected')
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout)
        except Exception as error:
            import aiohttp
            future.cancel()
            if isinstance(error, TransportError):
                raise
            if isinstance(error, (aiohttp.ClientConnectorCertificateError, aiohttp.ClientConnectorSSLError)):
                raise TransportError('peer_invalid') from None
            raise TransportError('network_unavailable') from None

    async def _open(self, credential):
        import aiohttp
        # Private connector interception is reviewed against this exact SDK.
        if aiohttp.__version__ != '3.14.3':
            raise TransportError('components_unsupported')
        profile = self._profile
        context = tls_context(profile)

        class PinnedConnector(aiohttp.TCPConnector):
            async def _wrap_create_connection(self, *args, **kwargs):
                transport, protocol = await super()._wrap_create_connection(*args, **kwargs)
                try:
                    peer = transport.get_extra_info('ssl_object')
                    der = peer.getpeercert(binary_form=True) if peer else None
                    verify_tls_peer(profile, der)
                except Exception:
                    transport.abort()
                    raise TransportError('peer_invalid') from None
                return transport, protocol

        trace = aiohttp.TraceConfig()
        async def reject_redirect(*args):
            raise TransportError('redirect_refused')
        trace.on_request_redirect.append(reject_redirect)
        self._session = aiohttp.ClientSession(
            connector=PinnedConnector(ssl=context, force_close=True),
            timeout=aiohttp.ClientTimeout(total=3, connect=2, sock_read=2),
            trust_env=False, trace_configs=[trace], cookie_jar=aiohttp.DummyCookieJar())
        if self._cancel.is_set():
            raise TransportError('cancelled')
        token = credential
        if token is None:
            if not profile.pairing_offer:
                raise TransportError('pairing_required')
            async with self._session.post(self._pair_url, allow_redirects=False, json=dict(
                    pi_id=profile.pi_id, client_id=self._client_id, transport='network', offer=profile.pairing_offer)) as response:
                if response.status != 200:
                    raise TransportError('pairing_refused')
                raw = await response.content.read(4097)
                if len(raw) > 4096:
                    raise TransportError('peer_invalid')
                value = json.loads(raw)
                if set(value) != {'pi_id', 'client_id', 'transport', 'token'} or (
                        value['pi_id'], value['client_id'], value['transport']) != (
                        profile.pi_id, self._client_id, 'network'):
                    raise TransportError('peer_invalid')
                _token(value['token'])
                token = value['token']
        _token(token)
        if self._cancel.is_set():
            raise TransportError('cancelled')
        try:
            self._ws = await self._session.ws_connect(
                self._ws_url, headers={'Authorization': 'Bearer ' + token}, max_msg_size=MAX_MESSAGE_BYTES,
                timeout=aiohttp.ClientWSTimeout(ws_receive=2, ws_close=.2))
        except aiohttp.WSServerHandshakeError as error:
            raise TransportError('authentication_refused' if error.status in (401, 403) else 'network_unavailable') from None
        self.authenticated_token = token

    async def _send(self, message):
        await self._ws.send_str(encode_v2(message).decode('utf-8'))

    async def _receive(self):
        import aiohttp
        message = await self._ws.receive(timeout=2)
        if message.type != aiohttp.WSMsgType.TEXT:
            raise TransportError('connection_lost')
        return decode_v2(message.data.encode('utf-8'))

    def send(self, message):
        return self._submit(self._send(message))

    def receive(self):
        return self._submit(self._receive())

    async def _shutdown(self):
        try:
            if self._ws:
                await self._ws.close()
        finally:
            if self._session:
                await self._session.close()

    def close(self):
        if self._closed.is_set():
            return
        self._closed.set()
        if self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
            try:
                future.result(.4)
            except (Exception, concurrent.futures.TimeoutError):
                future.cancel()
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not threading.current_thread():
            self._thread.join(.5)


class TransportFactory:
    """Only explicitly selected transport and first configured endpoint; no discovery switch."""
    def __call__(self, profile, client_id, mode, credential, device, cancel):
        if mode == 'uart':
            return SerialTransport(profile, client_id, credential, device, cancel)
        if mode == 'network' and profile.endpoints:
            return WssTransport(profile, client_id, credential, profile.endpoints[0], cancel)
        raise TransportError('endpoint_required')
