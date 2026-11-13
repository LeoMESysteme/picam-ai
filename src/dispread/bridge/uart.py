"""Explicit Pi UART listener. No device is opened by import or construction."""
from __future__ import annotations

import base64
import threading
import time
import uuid

from dispread.hardware_ports import GSV_UART_PORT

from .baud import UART_BAUD
from .protocol import V2LineReader, canonical_uart_hello, encode_v2
from .resources import SerialPortLease


class UartListener:
    def __init__(self, hub, identity, store, *, opener=None, port_leases=None):
        self.hub, self.identity, self.store = hub, identity, store
        self.opener = opener
        self.ports = port_leases or SerialPortLease()
        self.owner = uuid.uuid4().hex
        self._stop = threading.Event()
        self._lifecycle = threading.Lock()
        self._thread = None
        self._stream = None
        self._store_thread = None
        self._store_done = None
        self._lease = None
        self.state = 'unprepared'
        self.error = None
        self._reset()

    def _reset(self):
        lease, self._lease = self._lease, None
        if lease:
            self.hub.detach(lease.lease_id)
        self._challenge = None
        self._client = self._token = None
        self._deadline = None
        self._checked = 0
        self._decoder = V2LineReader()

    def start(self):
        # Serialize this listener's transition only; no Hub registry lock is
        # held during port acquisition or thread startup. Stop-before-start is
        # terminal, so a superseded prepare can never acquire a replacement's
        # resource. Publish only a successfully started thread to stop().
        with self._lifecycle:
            if self._stop.is_set():
                raise ValueError('UART listener already stopped')
            if self._thread is not None:
                raise ValueError('UART listener already started')
            port = self.ports.acquire(GSV_UART_PORT, self.owner, 'uart-listener')
            self.state = 'opening'
            thread = threading.Thread(target=self._worker, args=(port,), name='bridge-uart', daemon=True)
            try:
                thread.start()
            except BaseException:
                self.ports.release(self.owner)
                self.state = 'failed'
                raise
            self._thread = thread

    def _store_call(self, operation, *args):
        # A busy SQLite database may wait for seconds. Never queue more than
        # one outstanding call and never let late authorization attach a lease.
        # Completion belongs to the operation, not Thread.is_alive(): the
        # completed worker may still be tearing down when the next call starts.
        # A timed-out operation keeps its unset event and excludes new work.
        if self._store_done is not None and not self._store_done.is_set():
            raise ValueError('credential store unavailable')
        done = self._store_done = threading.Event()
        result = []
        def call():
            try:
                result.append((True, operation(*args)))
            except Exception:
                result.append((False, None))
            finally:
                done.set()
        self._store_thread = threading.Thread(target=call, name='uart-credentials', daemon=True)
        self._store_thread.start()
        deadline = time.monotonic() + .35
        while not done.wait(.02):
            if self._stop.is_set() or time.monotonic() >= deadline:
                raise ValueError('credential store unavailable')
        if self._stop.is_set() or not result[0][0]:
            raise ValueError('UART authorization refused')
        return result[0][1]

    def _send(self, message):
        payload = encode_v2(message)
        # Never retry a partial/uncertain transport write. The hub will abandon
        # its outstanding transfer when this session is reset.
        if self._stream.write(payload) != len(payload):
            raise OSError('incomplete UART write')

    def _message(self, message):
        now = time.monotonic()
        if message['pi_id'] != self.identity.pi_id:
            raise ValueError('UART identity mismatch')
        base = {key: message[key] for key in ('version', 'request_id', 'pi_id', 'client_id')}
        kind = message['type']
        if kind == 'uart_challenge':
            self._reset()
            self._challenge = (message['client_id'], message['request_id'], message['nonce'])
            self._deadline = now + 5
            signature = self.identity.sign_hello(canonical_uart_hello(
                self.identity.pi_id, message['client_id'], message['nonce']))
            return dict(base, type='uart_proof', nonce=message['nonce'],
                        signature=base64.b64encode(signature).decode('ascii'))
        if kind == 'uart_auth':
            if (self._challenge != (message['client_id'], message['request_id'], message['nonce'])
                    or self._deadline is None or now >= self._deadline):
                raise ValueError('fresh UART proof required')
            self._challenge = None  # one attempt per signed challenge
            token = message['credential']
            if message['mode'] == 'offer':
                token = self._store_call(self.store.redeem_offer, token, message['client_id'], 'uart')
            client = self._store_call(self.store.authorize, token, 'uart')
            if client != message['client_id'] or time.monotonic() >= self._deadline:
                raise ValueError('UART authorization refused')
            self._token, self._client = token, client
            self._checked = time.monotonic()
            self._deadline = self._checked + 5
            return dict(base, type='uart_authenticated', token=token)
        if self._deadline is not None and now >= self._deadline:
            raise ValueError('UART handshake expired')
        if self._token is None or message['client_id'] != self._client:
            raise ValueError('UART authorization required')
        self._authorize()
        if kind == 'hello':
            if self._lease or message['transport'] != 'uart' or message['run_id'] is not None or message.get('lease_id'):
                raise ValueError('fresh UART hello required')
            self._lease = self.hub.attach(self._client, 'uart', capabilities=message['capabilities'])
            self._deadline = None
            return self.hub._hello(self._lease, message['request_id'])
        if self._lease is None:
            raise ValueError('UART hello required')
        return self.hub.exchange(self._lease.lease_id, message)

    def _authorize(self):
        if self._store_call(self.store.authorize, self._token, 'uart') != self._client:
            raise ValueError('UART authorization ended')
        self._checked = time.monotonic()

    def _worker(self, port):
        try:
            if self._stop.is_set():
                return
            opener = self.opener
            if opener is None:
                import serial
                opener = serial.Serial
            self._stream = opener(port, baudrate=UART_BAUD, timeout=.1, write_timeout=.2, exclusive=True)
            if self._stop.is_set():
                return
            self.state = 'listening'
            while not self._stop.is_set():
                try:
                    now = time.monotonic()
                    if self._deadline is not None and now >= self._deadline:
                        self._reset()
                    if self._token and now - self._checked >= .2:
                        self._authorize()
                    if self._lease and self.hub.clock() - self._lease.renewed_at >= 5:
                        self._reset()
                    # pySerial read(n) wartet auf n Bytes oder das Timeout; nur
                    # Vorhandenes lesen, sonst kostet jede Nachricht 100 ms (R1).
                    waiting = getattr(self._stream, 'in_waiting', 0) or 0
                    data = self._stream.read(max(1, min(waiting, 4096)))
                    if not data:
                        continue
                    for message in self._decoder.feed(data):
                        if self._stop.is_set():
                            break
                        try:
                            self._send(self._message(message))
                        except ValueError:
                            self._reset()
                            self._send(dict(version=2, type='error', request_id=message['request_id'],
                                            pi_id=self.identity.pi_id, client_id=message['client_id'],
                                            run_id=None, code='uart_refused', detail='UART session refused'))
                except ValueError:
                    self._reset()
        except Exception:
            # Serial/credential exceptions can embed arbitrary data. Keep a
            # fixed diagnostic, never exception text or frames/credentials.
            self.state, self.error = 'failed', 'UART listener failed; prepare again after releasing port'
        finally:
            try:
                self._reset()
            finally:
                try:
                    if self._stream is not None:
                        self._stream.close()
                except Exception:
                    self.state, self.error = 'failed', 'UART close failed'
                finally:
                    self.ports.release(self.owner)
                    if self.state != 'failed':
                        self.state = 'stopped'

    def stop(self):
        with self._lifecycle:
            self._stop.set()
            stream, thread = self._stream, self._thread
            if thread is None:
                self.state = 'stopped'
        # Cancellation and join are outside the transition lock. A worker
        # always owns cleanup of an acquired port after successful startup.
        if stream is not None:
            for method in ('cancel_read', 'cancel_write'):
                cancel = getattr(stream, method, None)
                if cancel:
                    try:
                        cancel()
                    except OSError:
                        pass
        if thread is not None:
            thread.join(timeout=.8)
