"""One bounded worker consumes only ConnectionManager's validated W1 seam."""
from __future__ import annotations

import threading
from dataclasses import dataclass

from dispread.bridge.types import BridgeEvent
from dispread.gsv_bridge import BridgeAuditError, BridgeSession, DeliveryBlockedError, DeliveryUncertainError


@dataclass(frozen=True)
class WorkerStatus:
    """Local demo COM readiness, to combine with W1's connection readiness.

    This never authorizes DUT values or proves GSVmulti reception. failure code
    persists through stopped so a connected peer cannot mask a blocked journal.
    """

    state: str
    active: bool
    output_ready: bool
    code: str | None
    demo_only: bool = True
    gsv_receipt_confirmed: bool = False


class BridgeWorker:
    """No record queue: one poll/exchange, one COM write and at most one intent.

    com_factory() opens the explicitly selected COM endpoint and must return a
    pySerial-compatible, bounded-timeout handle. start() never reconnects W1.
    stop() is permanent for this worker/connection: release the Pi lease, cancel
    a blocked driver write when supported, then wait up to two seconds. A driver
    that ignores cancellation remains visibly active until its call returns.
    GUI minimize has no core operation; quit/logoff/suspend callers invoke stop.
    """

    def __init__(self, connection, com_factory, journal, emit):
        self.connection, self.com_factory = connection, com_factory
        self.journal, self.emit = journal, emit
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._admission_lock = threading.Lock()
        self._thread = None
        self._com = None
        self._last_event = self._failure = None
        self._state = 'idle'

    @staticmethod
    def _copy_event(event):
        return None if event is None else BridgeEvent(event.kind, event.code, event.run_id,
                                                      event.frame_sequence, dict(event.detail))

    @property
    def status(self) -> WorkerStatus:
        with self._lock:
            return WorkerStatus(self._state, self.is_active(),
                                self._state == 'running' and self._failure is None
                                and not self._stop.is_set(),
                                None if self._failure is None else self._failure.code)

    @property
    def last_event(self):
        with self._lock:
            return self._copy_event(self._last_event)

    @property
    def failure(self):
        with self._lock:
            return self._copy_event(self._failure)

    def _event(self, kind, *, strict=True, code=None, **fields):
        event = BridgeEvent(kind, code or fields.get('outcome') or kind, None, None,
                            dict(version=1, provisional=True, demo_only=True,
                                 gsv_receipt_confirmed=False,
                                 completion_stage='com_driver_write', **fields))
        with self._lock:
            self._last_event = event
            if kind == 'started':
                self._state = 'running'
            elif kind == 'stopped':
                self._state = 'stopped'
            if kind in ('audit_failed', 'connection_failed', 'blocked'):
                self._failure = event
                self._state = kind
        try:
            self.emit(self._copy_event(event))
        except Exception as exc:
            with self._lock:
                self._failure = BridgeEvent('audit_failed', 'audit_failed', None, None,
                                           dict(outcome='unknown', provisional=True,
                                                demo_only=True, gsv_receipt_confirmed=False))
                self._state = 'audit_failed' if kind != 'stopped' else 'stopped'
            if strict:
                raise BridgeAuditError('audit_failed in event sink; output stopped') from exc

    def start(self):
        with self._lock:
            if self._stop.is_set():
                raise RuntimeError('worker was permanently stopped')
            if self._thread is not None:
                raise RuntimeError('worker already started')
            self._state = 'starting'
            self._thread = threading.Thread(target=self._run, name='bridge-worker', daemon=True)
            self._thread.start()

    def is_active(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def _admit_write(self, link, claim):
        def claim_unless_stopped():
            with self._admission_lock:
                if self._stop.is_set():
                    raise InterruptedError('worker stopping')
                return claim()
        # W1 serializes this exact adapter identity/live lease check with all
        # reconnect/revocation. Lock order is manager -> worker admission.
        return self.connection.admit_write(link, claim_unless_stopped)

    def _run(self):
        com = None
        try:
            link = self.connection.data_link()  # validation precedes opening COM
            if self._stop.is_set():
                return
            pi_id = self.connection.profile.pi_id
            try:
                if self.journal.has_unresolved_invalidation(pi_id):
                    raise DeliveryBlockedError('unknown invalidation')
            except DeliveryBlockedError:
                raise
            except Exception as exc:
                raise BridgeAuditError('audit_failed reading journal') from exc
            session = BridgeSession(journal=self.journal, pi_id=pi_id,
                                    admit_write=self._admit_write)
            com = self.com_factory()
            with self._lock:
                self._com = com
            self._event('started')
            while not self._stop.is_set():
                link = self.connection.data_link()
                outcome = session.exchange(link, com)
                self._event('exchange', outcome=outcome)
                if outcome == 'ended':
                    break
                # Prevent an idle/busy loop without buffering historical values.
                self._stop.wait(0.01)
        except DeliveryBlockedError:
            self._event('blocked', strict=False, code='unknown_invalidation', outcome='unknown')
        except DeliveryUncertainError:
            self._event('blocked', strict=False, code='unknown_delivery', outcome='unknown')
        except BridgeAuditError:
            self._event('audit_failed', strict=False, outcome='unknown')
        except Exception:
            # No arbitrary exception strings: they may contain credentials/URLs.
            self._event('connection_failed', strict=False, outcome='stopped')
        finally:
            with self._admission_lock:
                self._stop.set()
            try:
                self.connection.disconnect()
            except Exception:
                self._event('connection_failed', strict=False, outcome='stopped')
            try:
                if com is not None:
                    com.close()
            except Exception:
                self._event('connection_failed', strict=False, outcome='stopped')
            with self._lock:
                self._com = None
            self._event('stopped', strict=False)

    def stop(self):
        # Release worker admission lock BEFORE calling manager.disconnect():
        # never invert the manager -> worker order used by admit_write.
        with self._admission_lock:
            self._stop.set()
        with self._lock:
            if self._state not in ('idle', 'stopped'):
                self._state = 'stopping'
        # Disconnect wakes receive and revokes the connection generation/lease.
        try:
            self.connection.disconnect()
        finally:
            with self._lock:
                com, thread = self._com, self._thread
            cancel = getattr(com, 'cancel_write', None)
            if cancel is not None:
                try:
                    cancel()
                except Exception:
                    pass
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=2)
