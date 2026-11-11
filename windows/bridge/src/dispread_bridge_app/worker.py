"""One bounded worker consumes only ConnectionManager's validated W1 seam."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from dispread.bridge.protocol import TEST_RELEASE
from dispread.bridge.types import BridgeEvent
from dispread.gsv_bridge import BridgeAuditError, BridgeSession, DeliveryBlockedError, DeliveryUncertainError

IDLE_FIRST_S, IDLE_MAX_S = 0.05, 0.2
# The Pi slot keeps only the latest value. Right after a value, a 50-200 ms
# pause would skip values of a 10-100 Hz producer, so polling stays at the old
# 10 ms pace for ACTIVE_HOLD_S after the last non-idle outcome (measured: 600
# demo values at 20 Hz gave 573 writes with plain backoff, 600 with this hold).
ACTIVE_POLL_S, ACTIVE_HOLD_S = 0.01, 2.0
_QUIET = frozenset({'idle', 'ended'})


@dataclass(frozen=True)
class WorkerStatus:
    """Local COM readiness, to combine with W1's connection readiness.

    This never authorizes DUT values or proves GSVmulti reception. failure code
    persists through stopped so a connected peer cannot mask a blocked journal.
    demo_only is False only while the current link carries the Pi-operator's
    confirmed test release (R1); the worker itself can never set it.
    """

    state: str
    active: bool
    output_ready: bool
    code: str | None
    demo_only: bool = True
    gsv_receipt_confirmed: bool = False
    exchanges_total: int = 0      # additiv: alle Poll-Runden, auch die nicht gemeldeten Leerlaufrunden
    # B2 (2026-11-11), additiv, je laufendem bzw. letztem Lauf; nur lokale COM-Annahme:
    ticks_written: int = 0        # vom Pi empfangene Takte, als Zeile an COM geschrieben
    ticks_invalid: int = 0        # davon vom Pi als ungueltig markiert (gueltig = 0)
    ticks_filled: int = 0         # von Windows aufgefuellte Fehlwertzeilen fuer verlorene Takte
    tick_disturbed: bool = False  # Luecke > 50 Takte nicht aufgefuellt: Zeilenzahl weicht ab


class BridgeWorker:
    """No record queue: one poll/exchange, one COM write and at most one intent.

    com_factory() opens the explicitly selected COM endpoint and must return a
    pySerial-compatible, bounded-timeout handle. start() never reconnects W1.
    Ordinary link loss waits for W1's validated replacement; completed runs
    leave the worker available for the next explicitly requested demo.
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
        self._exchanges = 0
        self._released = False
        self._link = None
        self._session = None
        self._wait = self._stop.wait   # Naht fuer Tests mit simulierter Uhr
        self._clock = time.monotonic

    @staticmethod
    def _copy_event(event):
        return None if event is None else BridgeEvent(event.kind, event.code, event.run_id,
                                                      event.frame_sequence, dict(event.detail))

    @property
    def status(self) -> WorkerStatus:
        with self._lock:
            link, released = self._link, self._released
        # The cached value only lags one exchange; the link's current Pi marker
        # is rechecked outside the worker lock (manager lock order unchanged).
        if released:
            released = link is not None and self._release_gate(link, getattr(link, 'run_id', None))
        with self._lock:
            session = self._session
        ticks = session.tick_stats() if session is not None else {}
        with self._lock:
            return WorkerStatus(self._state, self.is_active(),
                                self._state == 'running' and self._failure is None
                                and not self._stop.is_set(),
                                None if self._failure is None else self._failure.code,
                                demo_only=not (released and self._released),
                                exchanges_total=self._exchanges,
                                ticks_written=ticks.get('ticks_written', 0),
                                ticks_invalid=ticks.get('ticks_invalid', 0),
                                ticks_filled=ticks.get('ticks_filled', 0),
                                tick_disturbed=ticks.get('tick_disturbed', False))

    @property
    def last_event(self):
        with self._lock:
            return self._copy_event(self._last_event)

    @property
    def failure(self):
        with self._lock:
            return self._copy_event(self._failure)

    @staticmethod
    def _release_gate(link, run_id):
        """Pi-marked test release of this exact generation/run; no local switch."""
        check = getattr(link, 'test_release_for', None)
        return bool(check is not None and check(run_id))

    def _event(self, kind, *, strict=True, code=None, **fields):
        with self._lock:
            released = self._released and kind not in ('recovering', 'stopped')
        event = BridgeEvent(kind, code or fields.get('outcome') or kind, None, None,
                            dict(version=1, provisional=True, demo_only=not released,
                                 gsv_receipt_confirmed=False,
                                 completion_stage='com_driver_write',
                                 **({'release': TEST_RELEASE} if released else {}), **fields))
        with self._lock:
            self._last_event = event
            if kind == 'started':
                self._state = 'running'
            elif kind == 'recovering':
                self._state, self._released = 'recovering', False
            elif kind == 'stopped':
                self._state, self._released = 'stopped', False
            if kind in ('audit_failed', 'connection_failed', 'blocked'):
                self._failure = event
                self._state, self._released = kind, False
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

    def _check_journal(self, *, recovering=False):
        try:
            pi_id = self.connection.profile.pi_id
            if self.journal.has_unresolved_invalidation(pi_id):
                raise DeliveryBlockedError('unknown invalidation')
            # B2: eine unbekannte Taktzeile macht die Zeilenzahl ungewiss.
            if self.journal.has_unresolved_tick(pi_id):
                raise DeliveryUncertainError('unknown tick delivery')
            # A COM failure can itself lose its failed ACK. That outer link
            # exception must never hide uncertain bytes and enable auto-resume.
            if recovering and any(row.pi_id == pi_id for row in self.journal.unresolved()):
                raise DeliveryUncertainError('unknown delivery')
        except (DeliveryBlockedError, DeliveryUncertainError):
            raise
        except Exception as exc:
            raise BridgeAuditError('audit_failed reading journal') from exc

    def _may_recover(self, error):
        # Local import avoids connection -> readiness -> worker import cycle.
        from .connection import ConnectionError

        if not isinstance(error, ConnectionError) or error.code not in {
                'connection_unavailable', 'connection_lost', 'lease_unavailable'}:
            return False
        state = self.connection.snapshot()
        # W1 owns retry/backoff. A terminal refusal or explicit disconnect must
        # not leave this worker waiting forever on an already stopped manager.
        return (state.peer in {'connecting', 'backoff', 'authenticated'}
                or (state.peer == 'disconnected' and state.next_action == 'reconnect'))

    def _run(self):
        com = link = None
        recovering = False
        idle_delay = 0.0          # adaptiver Leerlauftakt; 0 = naechster Poll sofort
        last_outcome = None
        last_active = None
        try:
            pi_id = self.connection.profile.pi_id
            session = BridgeSession(journal=self.journal, pi_id=pi_id,
                                    admit_write=self._admit_write, release_gate=self._release_gate)
            with self._lock:
                self._session = session
            disturbed = None
            while not self._stop.is_set():
                try:
                    current = self.connection.data_link()
                    if recovering and current is link:
                        self._wait(0.05)
                        continue
                    if com is None or recovering:
                        self._check_journal(recovering=recovering)
                        if self._stop.is_set():
                            break
                        if com is None:
                            com = self.com_factory()
                            with self._lock:
                                self._com = com
                        self._event('started')
                        recovering = False
                    link = current
                    with self._lock:
                        self._link = link
                    outcome = session.exchange(link, com)
                    released = self._release_gate(link, getattr(link, 'run_id', None))
                    with self._lock:
                        self._exchanges += 1
                        changed, self._released = self._released != released, released
                    # Wiederholtes idle/ended nur als Uebergang melden; alles
                    # andere (written, invalid, ...) bleibt ein Ereignis je Runde.
                    if outcome not in _QUIET or outcome != last_outcome or changed:
                        self._event('exchange', outcome=outcome)
                    ticks = session.tick_stats()
                    if ticks['tick_disturbed'] and disturbed != ticks['run_id']:
                        # Einmal je Lauf: Luecke ueber 50 Takte, nicht aufgefuellt.
                        disturbed = ticks['run_id']
                        self._event('tick_disturbed', code='tick_gap_unfilled')
                    last_outcome = outcome
                    if outcome not in _QUIET:
                        idle_delay, last_active = 0.0, self._clock()
                    elif last_active is not None and self._clock() - last_active < ACTIVE_HOLD_S:
                        idle_delay = ACTIVE_POLL_S
                    else:
                        idle_delay = IDLE_FIRST_S if idle_delay in (0, ACTIVE_POLL_S) else min(idle_delay * 2, IDLE_MAX_S)
                    # ended completes a run, not the authenticated connection.
                    # Only a later explicit producer run supplies more values.
                except (DeliveryBlockedError, DeliveryUncertainError, BridgeAuditError):
                    raise
                except Exception as error:
                    if self._stop.is_set():
                        self._check_journal(recovering=True)
                        break
                    if not self._may_recover(error):
                        raise
                    if not recovering:
                        self._check_journal(recovering=True)
                        self._event('recovering', code='connection_unavailable')
                        recovering = True
                    last_outcome, idle_delay = None, 0.0
                    self._wait(0.05)
                # Idle polling backs off (50 -> 200 ms, far below the 1 s heartbeat
                # and 5 s lease); after any real outcome the next poll is immediate,
                # so no value waits behind a queue and none is buffered.
                self._wait(idle_delay)
        except DeliveryBlockedError:
            self._event('blocked', strict=False, code='unknown_invalidation', outcome='unknown')
        except DeliveryUncertainError:
            self._event('blocked', strict=False, code='unknown_delivery', outcome='unknown')
        except BridgeAuditError:
            self._event('audit_failed', strict=False, code='audit_failed', outcome='unknown')
        except Exception:
            # No arbitrary exception strings: they may contain credentials/URLs.
            self._event('connection_failed', strict=False, code='connection_failed', outcome='stopped')
        finally:
            with self._admission_lock:
                self._stop.set()
            try:
                self.connection.disconnect()
            except Exception:
                self._event('connection_failed', strict=False, code='connection_failed', outcome='stopped')
            try:
                if com is not None:
                    com.close()
            except Exception:
                self._event('connection_failed', strict=False, code='connection_failed', outcome='stopped')
            with self._lock:
                self._com = self._link = None
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
