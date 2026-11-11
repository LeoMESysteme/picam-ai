"""Worker uses the validated W1 seam and the real BridgeSession/journal."""
import threading
from types import SimpleNamespace

import pytest

from dispread.gsv_bridge import BridgeError, BridgeSession
from dispread.records import TimeBaseKind, Timestamp, ValueRecord, ValueStatus


def message(status=ValueStatus.VALID, sequence=7, barrier=None, run='run'):
    record = ValueRecord(sequence, Timestamp(1, TimeBaseKind.SYNTHETIC),
                         1.0 if status is ValueStatus.VALID else None, 'mV/V', status,
                         1.0, 'demo', None, None, raw_text='+1.0',
                         reject_reasons=() if status is ValueStatus.VALID else ('demo',))
    return dict(version=1, type='record', run_id=run, record=record.to_dict(),
                frame_age_ns=None, barrier_id=barrier, demo=True)


class Link:
    def __init__(self, reply=None, fail_ack=False):
        self.reply, self.fail_ack, self.messages = reply or message(), fail_ack, []
    def send(self, message):
        if message['type'] == 'ack' and self.fail_ack:
            raise ConnectionError('lost before ACK')
        self.messages.append(message)
    def receive(self):
        return dict(self.reply, request_id=self.messages[-1]['request_id'])


class Com:
    def __init__(self, short=False, crash=False):
        self.payloads, self.short, self.crash, self.closed = [], short, crash, False
    def write(self, payload):
        self.payloads.append(payload)
        if self.crash:
            raise SystemExit('simulated kill')
        return len(payload) - int(self.short)
    def close(self):
        self.closed = True


def session(db, **kwargs):
    return BridgeSession(journal=db, pi_id='pi', **kwargs)


def test_kill_after_write_before_ack_does_not_resend_numeric(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    path, com = tmp_path / 'audit.sqlite', Com(crash=True)
    with DeliveryJournal(path) as db:
        with pytest.raises(SystemExit):
            session(db).exchange(Link(), com)
    with DeliveryJournal(path) as db:
        with pytest.raises(BridgeError, match='unknown'):
            session(db).exchange(Link(), com)
    assert len(com.payloads) == 1


def test_durable_written_result_reacks_after_lost_ack(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    com = Com()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        with pytest.raises(ConnectionError):
            session(db).exchange(Link(fail_ack=True), com)
        link = Link()
        assert session(db).exchange(link, com) == 'written'
        assert link.messages[-1]['outcome'] == 'written'
    assert len(com.payloads) == 1


def test_partial_write_is_unknown_not_success(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        link, com = Link(), Com(short=True)
        with pytest.raises(BridgeError):
            session(db).exchange(link, com)
        assert db.unresolved()[0].outcome == 'unknown'
        assert link.messages[-1]['outcome'] == 'failed'
        assert len(com.payloads) == 1


def test_full_disk_before_intent_prevents_write():
    class FullDisk:
        def begin_attempt(self, *args):
            raise OSError('disk full')
    com = Com()
    with pytest.raises(BridgeError, match='audit_failed'):
        session(FullDisk()).exchange(Link(), com)
    assert com.payloads == []


def test_audit_failure_after_write_stops_and_marks_unknown(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    class FullAfterWrite(DeliveryJournal):
        def finish_attempt(self, *args):
            raise OSError('disk full')
    path, com, link = tmp_path / 'audit.sqlite', Com(), Link()
    with FullAfterWrite(path) as db:
        with pytest.raises(BridgeError, match='audit_failed.*unknown'):
            session(db).exchange(link, com)
    with DeliveryJournal(path) as db:
        assert db.unresolved()[0].outcome == 'pending'
    assert len(com.payloads) == 1
    assert all(m.get('outcome') != 'written' for m in link.messages)


def test_journal_latency_recomputes_remaining_budget(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    now = [0]
    class SlowJournal(DeliveryJournal):
        def begin_attempt(self, *args):
            attempt = super().begin_attempt(*args)
            now[0] = 2_000_000_000
            return attempt
    with SlowJournal(tmp_path / 'audit.sqlite') as db:
        com = Com()
        assert session(db, clock=lambda: now[0]).exchange(Link(), com) == 'expired'
        assert com.payloads == []
        assert db.unresolved() == ()


@pytest.mark.parametrize('status,barrier', [(ValueStatus.UNREADABLE, None),
                                          (ValueStatus.STALE, 0), (ValueStatus.VALID, 8)])
def test_malformed_barrier_metadata_prevents_all_writes(tmp_path, status, barrier):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        com = Com()
        with pytest.raises(BridgeError, match='barrier'):
            session(db).exchange(Link(message(status, barrier=barrier)), com)
        assert com.payloads == []
        assert db.unresolved() == ()


class Connection:
    profile = SimpleNamespace(pi_id='pi')
    def __init__(self, link):
        self.link, self.disconnected = link, False
        self._generation_lock = threading.RLock()
    def data_link(self):
        with self._generation_lock:
            if self.disconnected:
                raise ConnectionError('lease lost')
            return self.link
    def admit_write(self, link, claim):
        with self._generation_lock:
            if self.disconnected or link is not self.link:
                raise ConnectionError('generation revoked')
            return claim()
    def disconnect(self):
        with self._generation_lock:
            self.disconnected = True


def worker(connection, com, db, emit):
    from dispread_bridge_app.worker import BridgeWorker
    return BridgeWorker(connection, lambda: com, db, emit)


def test_worker_stop_disconnects_and_closes_com(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    connection, com, events, ready = Connection(Link()), Com(), [], threading.Event()
    def emit(event):
        events.append(event)
        if event.kind == 'exchange':
            ready.set()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, emit)
        w.start()
        assert ready.wait(2)
        assert w.is_active()  # Minimizing a GUI has no core lifecycle side effect.
        w.stop()
        assert not w.is_active()
    assert connection.disconnected and com.closed
    assert events[-1].kind == 'stopped'


def test_worker_lease_loss_stops_without_opening_com(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    connection, com, events, done = Connection(Link()), Com(), [], threading.Event()
    connection.disconnect()
    def emit(event):
        events.append(event)
        if event.kind == 'stopped':
            done.set()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, emit)
        w.start()
        assert done.wait(2)
        w.stop()
    assert com.payloads == [] and not com.closed
    assert any(e.kind == 'connection_failed' for e in events)


def test_slow_uart_keeps_latest_bounded(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    class Latest(Link):
        current = 1
        def receive(self):
            return dict(message(sequence=self.current), request_id=self.messages[-1]['request_id'])
    class SlowCom(Com):
        def write(self, payload):
            super().write(payload)
            if len(self.payloads) == 1:
                entered.set()
                assert release.wait(2)
            return len(payload)
    link, com, sequences = Latest(), SlowCom(), []
    def emit(event):
        if event.kind == 'exchange':
            sequences.append(link.current)
            if len(sequences) == 2:
                done.set()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(Connection(link), com, db, emit)
        w.start()
        assert entered.wait(2)
        link.current = 10000  # Pi latest slot advances while the one COM call blocks.
        release.set()
        assert done.wait(2)
        w.stop()
        assert len(com.payloads) == 2
        assert sequences[:2] == [10000, 10000]  # Poll ohne Wartezeit: weitere Runden moeglich
        assert [r.frame_sequence for r in db.attempts()] == [1, 10000]


def test_worker_audit_failure_stops_and_exposes_unknown(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    class FullAfterWrite(DeliveryJournal):
        def finish_attempt(self, *args):
            raise OSError('disk full')
    com, connection, events, done = Com(), Connection(Link()), [], threading.Event()
    def emit(event):
        events.append(event)
        if event.kind == 'stopped':
            done.set()
    with FullAfterWrite(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, emit)
        w.start()
        assert done.wait(2)
        w.stop()
        assert db.unresolved()[0].outcome == 'pending'
    assert com.payloads == [b'%+1.0\r\n']
    event = next(event for event in events if event.kind == 'audit_failed')
    assert event.detail['outcome'] == 'unknown'
    assert connection.disconnected and com.closed


def test_stop_during_blocked_intent_prevents_com_write(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    class SlowIntent(DeliveryJournal):
        def begin_attempt(self, *args):
            attempt = super().begin_attempt(*args)
            entered.set()
            assert release.wait(3)
            return attempt
    com, connection = Com(), Connection(Link())
    def emit(event):
        if event.kind == 'stopped':
            done.set()
    with SlowIntent(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, emit)
        w.start()
        assert entered.wait(2)
        stopper = threading.Thread(target=w.stop)
        stopper.start()
        assert connection.disconnected or w.is_active()
        release.set()
        stopper.join(2)
        assert done.wait(2)
        assert not w.is_active()
        assert db.unresolved() == ()
        assert db.attempts()[0].outcome == 'not_written'
    assert com.payloads == []


def test_lease_loss_during_intent_prevents_write(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    connection, com = Connection(Link()), Com()
    class LosingIntent(DeliveryJournal):
        def begin_attempt(self, *args):
            attempt = super().begin_attempt(*args)
            connection.disconnect()
            return attempt
    done = threading.Event()
    def emit(event):
        if event.kind == 'stopped':
            done.set()
    with LosingIntent(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, emit)
        w.start()
        assert done.wait(2)
        w.stop()
        assert db.attempts()[0].outcome == 'not_written'
    assert com.payloads == []


def test_unknown_invalidation_prevents_worker_valid_write_after_restart(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    path = tmp_path / 'audit.sqlite'
    with DeliveryJournal(path) as db:
        attempt = db.begin_attempt('pi', 'old-run', 1, 10, b'%NaN\r\n')
        db.finish_attempt(attempt, 'unknown')
    with DeliveryJournal(path) as db:
        com = Com()
        with pytest.raises(BridgeError):
            session(db).exchange(Link(message(run='new-run')), com)
        assert com.payloads == []


def test_prewrite_check_time_also_counts_against_budget(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    now, com = [0], Com()
    def before_write():
        now[0] = 2_000_000_000
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        assert session(db, clock=lambda: now[0], before_write=before_write).exchange(Link(), com) == 'expired'
    assert com.payloads == []


def test_diagnostic_sink_full_stops_com_and_exposes_audit_failure(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    com, connection, entered = Com(), Connection(Link()), threading.Event()
    def full_sink(event):
        entered.set()
        raise OSError('disk full with secret-token')
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, full_sink)
        w.start()
        assert entered.wait(2)
        w.stop()
        assert w.last_event.kind == 'stopped'
        assert w.failure.kind == 'audit_failed'
    assert com.payloads == [] and com.closed


def test_shared_bridge_event_and_status_are_backend_authoritative(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal

    from dispread.bridge.types import BridgeEvent
    events, ready = [], threading.Event()
    def emit(event):
        events.append(event)
        if isinstance(event, BridgeEvent) and event.kind == 'exchange':
            ready.set()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(Connection(Link()), Com(), db, emit)
        assert not w.status.output_ready
        w.start()
        assert ready.wait(2)
        assert w.status.output_ready
        assert w.status.demo_only and not w.status.gsv_receipt_confirmed
        w.stop()
        assert not w.status.output_ready and not w.status.active
    assert all(isinstance(event, BridgeEvent) for event in events)
    assert events[-1].kind == 'stopped'
    assert events[-1].detail['provisional'] is True


def test_unknown_barrier_blocks_worker_before_com_open(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    com, events, done = Com(), [], threading.Event()
    def emit(event):
        events.append(event)
        if event.kind == 'stopped':
            done.set()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        db.begin_attempt('pi', 'old-run', 1, 4, b'%NaN\r\n')
        w = worker(Connection(Link()), com, db, emit)
        w.start()
        assert done.wait(2)
        w.stop()
        assert not w.status.output_ready
        assert w.failure.kind == 'blocked'
        assert w.failure.code == 'unknown_invalidation'
    assert not com.closed and com.payloads == []
    assert any(event.kind == 'blocked' for event in events)


def test_real_process_exit_after_fake_com_preserves_unknown_intent(tmp_path):
    import subprocess
    import sys

    from dispread_bridge_app.delivery_journal import DeliveryJournal
    path, submitted = tmp_path / 'audit.sqlite', tmp_path / 'submitted.bin'
    script = '''
import os, sys
from pathlib import Path
from dispread_bridge_app.delivery_journal import DeliveryJournal
from dispread.gsv_bridge import BridgeSession
from dispread.records import ValueRecord, ValueStatus, Timestamp, TimeBaseKind
class Link:
    def send(self, message):
        self.request = message['request_id']
    def receive(self):
        record = ValueRecord(7, Timestamp(1, TimeBaseKind.SYNTHETIC), 1.0,
            'mV/V', ValueStatus.VALID, 1.0, 'demo', None, None, raw_text='+1.0')
        return dict(version=1,type='record',request_id=self.request,run_id='run',
            record=record.to_dict(),frame_age_ns=None,barrier_id=None,demo=True)
class Com:
    def write(self, payload):
        with open(sys.argv[2], 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os._exit(23)
with DeliveryJournal(sys.argv[1]) as journal:
    BridgeSession(journal=journal, pi_id='pi').exchange(Link(), Com())
'''
    result = subprocess.run([sys.executable, '-c', script, str(path), str(submitted)],
                            capture_output=True, timeout=10)
    assert result.returncode == 23, result.stderr
    assert submitted.read_bytes() == b'%+1.0\r\n'
    com = Com()
    with DeliveryJournal(path) as db:
        assert db.unresolved()[0].outcome == 'pending'
        with pytest.raises(BridgeError, match='unknown'):
            session(db).exchange(Link(), com)
    assert com.payloads == []


def test_written_duplicate_reacks_even_after_request_budget_elapsed(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    now, com = [0], Com()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        session(db).exchange(Link(), com)
        class SlowReply(Link):
            def receive(self):
                result = super().receive()
                now[0] = 2_000_000_000
                return result
        link = SlowReply()
        assert session(db, clock=lambda: now[0]).exchange(link, com) == 'written'
        assert link.messages[-1]['outcome'] == 'written'
        assert len(com.payloads) == 1


class AdmittingConnection(Connection):
    """Models the proposed W1 generation-locked, nonblocking claim contract."""
    def __init__(self, link):
        super().__init__(link)
        self.generation_lock = threading.RLock()
        self.claims = 0
    def data_link(self):
        with self.generation_lock:
            return super().data_link()
    def admit_write(self, link, claim):
        with self.generation_lock:
            if self.disconnected or link is not self.link:
                raise ConnectionError('generation revoked')
            result = claim()
            self.claims += 1
            return result
    def replace_link(self, link):
        with self.generation_lock:
            self.link = link
    def disconnect(self):
        with self.generation_lock:
            super().disconnect()


class SetupBlockingCom(Com):
    def __init__(self):
        super().__init__()
        self.setup_entered = threading.Event()
        self.resume_setup = threading.Event()
    @property
    def write_timeout(self):
        return self._timeout
    @write_timeout.setter
    def write_timeout(self, timeout):
        self._timeout = timeout
        self.setup_entered.set()
        assert self.resume_setup.wait(5)


def test_generation_a_record_cannot_borrow_generation_b_lease_during_intent(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    connection, com, done = AdmittingConnection(Link()), Com(), threading.Event()
    class ReconnectedIntent(DeliveryJournal):
        def begin_attempt(self, *args):
            result = super().begin_attempt(*args)
            connection.replace_link(Link(message(sequence=800)))
            return result
    def emit(event):
        if event.kind == 'stopped':
            done.set()
    with ReconnectedIntent(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, emit)
        w.start()
        assert done.wait(2)
        w.stop()
        assert db.attempts()[0].outcome == 'not_written'
    assert connection.claims == 0 and com.payloads == []


def test_stop_while_timeout_setter_blocks_prevents_new_com_admission(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    com, connection, done = SetupBlockingCom(), AdmittingConnection(Link()), threading.Event()
    def emit(event):
        if event.kind == 'stopped':
            done.set()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, emit)
        w.start()
        assert com.setup_entered.wait(2)
        w.stop()  # two-second join may expire: setup has not returned yet
        assert w.is_active() and not w.status.output_ready
        com.resume_setup.set()
        assert done.wait(2)
        w.stop()
        assert db.attempts()[0].outcome == 'not_written'
    assert connection.claims == 0 and com.payloads == []


def test_lease_revoked_while_timeout_setter_blocks_prevents_admission(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    com, connection, done = SetupBlockingCom(), AdmittingConnection(Link()), threading.Event()
    def emit(event):
        if event.kind == 'stopped':
            done.set()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, emit)
        w.start()
        assert com.setup_entered.wait(2)
        connection.disconnect()
        com.resume_setup.set()
        assert done.wait(2)
        w.stop()
        assert db.attempts()[0].outcome == 'not_written'
    assert connection.claims == 0 and com.payloads == []


def test_timeout_setter_expiry_prevents_driver_submission(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    now = [0]
    class SlowSetupCom(Com):
        @property
        def write_timeout(self):
            return 1.0
        @write_timeout.setter
        def write_timeout(self, value):
            now[0] = 2_000_000_000
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        com, link = SlowSetupCom(), Link()
        assert session(db, clock=lambda: now[0]).exchange(link, com) == 'expired'
        assert db.attempts()[0].outcome == 'not_written'
        assert link.messages[-1]['outcome'] == 'expired'
    assert com.payloads == []


def test_admission_lock_wait_consumes_final_budget(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    now, com, claims = [0], Com(), []
    def waited_admission(link, claim):
        now[0] = 2_000_000_000  # generation/admission lock only became available now
        claim()
        claims.append('admitted')
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        link = Link()
        assert session(db, clock=lambda: now[0], admit_write=waited_admission).exchange(link, com) == 'expired'
        assert db.attempts()[0].outcome == 'not_written'
    assert com.payloads == [] and claims == []


class RecoveringConnection(Connection):
    def __init__(self, link):
        super().__init__(link)
        self.peer, self.action = 'authenticated', None
    def snapshot(self):
        return SimpleNamespace(peer=self.peer, next_action=self.action)
    def data_link(self):
        from dispread_bridge_app.connection import ConnectionError as LinkError
        if self.peer != 'authenticated':
            raise LinkError('connection_unavailable')
        return super().data_link()


def test_transient_loss_waits_for_new_validated_link_without_disconnect(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    connection = RecoveringConnection(Link())
    connection.peer, connection.action = 'backoff', 'network_unavailable'
    com, recovering, resumed = Com(), threading.Event(), threading.Event()
    def emit(event):
        if event.kind == 'recovering':
            recovering.set()
        if event.kind == 'exchange':
            resumed.set()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, emit)
        w.start()
        try:
            assert recovering.wait(2)
            assert w.status.state == 'recovering' and not w.status.output_ready
            assert not connection.disconnected and not com.closed
            connection.link = Link(message(sequence=50))
            connection.peer, connection.action = 'authenticated', None
            assert resumed.wait(2)
            assert w.status.output_ready and w.failure is None
        finally:
            w.stop()
    assert com.payloads == [b'%+1.0\r\n']


def test_clean_ended_keeps_worker_available_for_next_explicit_run(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    link = Link(dict(version=1, type='ended', run_id='old'))
    connection, com, ended, written = Connection(link), Com(), threading.Event(), threading.Event()
    def emit(event):
        if event.kind == 'exchange' and event.detail['outcome'] == 'ended':
            ended.set()
        if event.kind == 'exchange' and event.detail['outcome'] == 'written':
            written.set()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, emit)
        w.start()
        try:
            assert ended.wait(2)
            assert w.is_active() and not connection.disconnected and not com.closed
            link.reply = message(run='new', sequence=100)
            assert written.wait(2)
        finally:
            w.stop()
    assert com.payloads == [b'%+1.0\r\n']


@pytest.mark.parametrize('action', ['peer_invalid', 'pairing_required', 'authentication_refused', 'connect'])
def test_permanent_manager_failure_is_not_a_recovery_spin(tmp_path, action):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    connection = RecoveringConnection(Link())
    connection.peer, connection.action = 'disconnected', action
    done = threading.Event()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, Com(), db, lambda e: done.set() if e.kind == 'stopped' else None)
        w.start()
        assert done.wait(2)
        assert w.failure.kind == 'connection_failed'
        w.stop()


def test_stop_interrupts_transient_recovery(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    connection, recovering, com = RecoveringConnection(Link()), threading.Event(), Com()
    connection.peer, connection.action = 'backoff', 'network_unavailable'
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(connection, com, db, lambda e: recovering.set() if e.kind == 'recovering' else None)
        w.start()
        try:
            assert recovering.wait(2)
        finally:
            w.stop()
        assert not w.is_active() and connection.disconnected
    assert not com.closed and com.payloads == []


# ---- BQ4: Leerlauftakt und Ereignisverdichtung (injizierte Uhr, keine echte Zeit)
class ScriptLink:
    """Antwortet je Poll aus einem Skript; danach dauerhaft idle."""
    def __init__(self, script=()):
        self.script, self.messages, self.polls = list(script), [], 0
    def send(self, msg):
        self.messages.append(msg)
        self.polls += msg['type'] == 'poll'
    def receive(self):
        rid = self.messages[-1]['request_id']
        if self.messages[-1]['type'] != 'poll':
            return dict(version=1, type='idle', request_id=rid, run_id=None, release_block=None)
        reply = self.script.pop(0) if self.script else dict(type='idle', run_id=None, release_block=None)
        return dict(reply, version=1, request_id=rid)


class SimClock:
    """Ersetzt Event.wait: sammelt Wartezeiten, stoppt nach simulierter Zeit."""
    def __init__(self, w, limit):
        self.w, self.limit, self.now, self.waits = w, limit, 0.0, []
        w._clock = lambda: self.now
    def __call__(self, seconds):
        self.waits.append(seconds)
        self.now += seconds + 0.001           # 1 ms Netzzeit je Runde
        if self.now >= self.limit:
            self.w._stop.set()
        return self.w._stop.is_set()


def run_sim(tmp_path, script=(), limit=10.0):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    link, events = ScriptLink(script), []
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        from dispread_bridge_app.worker import BridgeWorker
        w = BridgeWorker(Connection(link), lambda: Com(), db, events.append)
        clock = SimClock(w, limit)
        w._wait = clock
        w._run()
    return link, events, clock


def test_idle_poll_rate_is_bounded(tmp_path):
    link, events, clock = run_sim(tmp_path, limit=10.0)
    assert link.polls / 10.0 <= 25
    assert clock.waits[:5] == [0.05, 0.1, 0.2, 0.2, 0.2]
    assert max(clock.waits) <= 0.2          # unter dem 1-s-Heartbeat und dem 5-s-Lease


def test_poll_after_written_has_no_wait(tmp_path):
    rec = dict(message(sequence=1), request_id='x')
    rec.pop('request_id')
    link, events, clock = run_sim(tmp_path, script=[rec, dict(rec, record=message(sequence=2)['record'])],
                                  limit=1.0)
    outcomes = [e.detail['outcome'] for e in events if e.kind == 'exchange']
    assert outcomes[:2] == ['written', 'written']
    assert clock.waits[0] == 0 and clock.waits[1] == 0
    assert clock.waits[2] == 0.01           # kurze Haltezeit: Pi-Slot haelt nur den letzten Wert


def test_idle_backoff_resets_after_record(tmp_path):
    rec = message(sequence=3)
    rec.pop('request_id', None)
    idle = dict(type='idle', run_id=None, release_block=None)
    link, events, clock = run_sim(tmp_path, script=[idle, idle, idle, rec], limit=1.0)
    assert clock.waits[:5] == [0.05, 0.1, 0.2, 0, 0.01]


def test_thousand_idle_rounds_emit_one_idle_event(tmp_path):
    link, events, clock = run_sim(tmp_path, limit=1000 * 0.2)
    idle = [e for e in events if e.kind == 'exchange' and e.detail['outcome'] == 'idle']
    assert link.polls >= 900 and len(idle) == 1


def test_idle_after_written_emits_transition_again(tmp_path):
    rec = message(sequence=3)
    idle = dict(type='idle', run_id=None, release_block=None)
    link, events, clock = run_sim(tmp_path, script=[idle, idle, rec, idle, idle], limit=1.0)
    outcomes = [e.detail['outcome'] for e in events if e.kind == 'exchange']
    assert outcomes == ['idle', 'written', 'idle']


def test_status_counts_exchanges(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    from dispread_bridge_app.worker import BridgeWorker
    link = ScriptLink()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = BridgeWorker(Connection(link), lambda: Com(), db, lambda e: None)
        w._wait = SimClock(w, 1.0)
        w._run()
        assert w.status.exchanges_total == link.polls > 3


def test_stop_during_idle_wait_is_prompt(tmp_path):
    import time

    from dispread_bridge_app.delivery_journal import DeliveryJournal
    link = ScriptLink()
    done = threading.Event()
    def emit(e):
        if e.kind == 'stopped':
            done.set()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(Connection(link), Com(), db, emit)
        w.start()
        time.sleep(0.5)                      # Backoff hat 0,2 s erreicht
        t = time.monotonic()
        w.stop()
        assert done.wait(1) and time.monotonic() - t < 0.05
        assert not w.is_active()


def test_active_hold_then_backoff_after_record(tmp_path):
    rec = message(sequence=3)
    link, events, clock = run_sim(tmp_path, script=[rec], limit=10.0)
    assert clock.waits[:3] == [0, 0.01, 0.01]
    assert 0.05 in clock.waits and clock.waits[-1] == 0.2    # nach 2 s Backoff
    assert link.polls / 10.0 <= 25 + 100 * 2 / 10             # Haltezeit zaehlt einmalig


def test_producer_at_20hz_loses_no_values(tmp_path):
    """Pi-Slot haelt nur den letzten Wert: Takt nach einem Wert darf keinen ueberspringen."""
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    from dispread_bridge_app.worker import BridgeWorker

    class Slot:
        def __init__(self, clock):
            self.clock, self.messages, self.last = clock, [], -1
        def send(self, m):
            self.messages.append(m)
        def receive(self):
            rid = self.messages[-1]['request_id']
            seq = int(self.clock.now / 0.05)            # neuer Wert alle 50 ms, nur letzter bleibt
            if seq < 600 and seq != self.last:
                self.last = seq
                return dict(message(sequence=seq), request_id=rid)
            return dict(version=1, type='idle', request_id=rid, run_id=None, release_block=None)
    events, com = [], Com()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = BridgeWorker(Connection(None), lambda: com, db, events.append)
        clock = SimClock(w, 33.0)
        w._wait = clock
        w.connection.link = Slot(clock)
        w._run()
    assert len(com.payloads) == 600


# R1 (2026-11-09): echte Werte nur mit Pi-Testfreigabe der aktuellen Bindung.
def released(status=ValueStatus.VALID, sequence=9, barrier=None, raw='+ 1.2345 ', value=1.2345, release=True):
    valid = status is ValueStatus.VALID
    record = ValueRecord(sequence, Timestamp(5, TimeBaseKind.V4L2_MONOTONIC), value if valid else None, 'mV/V',
                         status, 1.0, 'p', None, None, raw_text=raw if valid else '',
                         reject_reasons=() if valid else ('unreadable',))
    return dict(version=1, type='record', run_id='run', record=record.to_dict(), frame_age_ns=None,
                barrier_id=barrier, demo=False, **({'release': 'test_unaccepted'} if release else {}))


@pytest.mark.parametrize('gate', [None, False])
def test_real_record_without_current_pi_release_never_reaches_com(tmp_path, gate):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    com = Com()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        kwargs = {} if gate is None else dict(release_gate=lambda link, run_id: gate)
        with pytest.raises(BridgeError, match='gesperrt'):
            session(db, **kwargs).exchange(Link(released()), com)
        assert db.attempts() == ()
    assert com.payloads == []


def test_real_record_without_release_marker_is_refused_even_with_open_gate(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    com = Com()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        with pytest.raises(BridgeError, match='gesperrt'):
            session(db, release_gate=lambda link, run_id: True).exchange(Link(released(release=False)), com)
    assert com.payloads == []


def test_released_valid_value_uses_direct_uart_formatter_bytes(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal

    from dispread.records import ValueRecord as VR
    from dispread.sink.protocol.userdefined import UserDefinedFormatter
    com, seen = Com(), []
    reply = released()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        link = Link(reply)
        gate = lambda link, run_id: seen.append(run_id) or True  # noqa: E731
        assert session(db, release_gate=gate).exchange(link, com) == 'written'
        assert [a.outcome for a in db.attempts()] == ['written']
    expected = UserDefinedFormatter(prefix='%').format(VR.from_dict(reply['record']))
    assert com.payloads == [expected] == [b'%+1.2345\r\n']
    assert seen == ['run']
    assert link.messages[-1]['outcome'] == 'written'


@pytest.mark.parametrize('reply', [
    released(ValueStatus.UNREADABLE, barrier=3),
    released(raw='+ 1.2346 '),  # Text/Wert inkonsistent: Formatter laesst aus
])
def test_released_invalidation_or_unformattable_value_is_omitted_not_written(tmp_path, reply):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    com = Com()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        link = Link(reply)
        assert session(db, release_gate=lambda link, run_id: True).exchange(link, com) == 'omitted'
        assert db.attempts() == ()
        assert not db.has_unresolved_invalidation('pi')
    assert com.payloads == []
    ack = link.messages[-1]
    assert (ack['type'], ack['outcome'], ack['barrier_id']) == ('ack', 'omitted', reply['barrier_id'])


def test_worker_reports_release_only_while_link_holds_it(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    from dispread_bridge_app.worker import BridgeWorker

    class ReleasedLink(Link):
        released = True
        run_id = 'run'

        def test_release_for(self, run_id):
            return self.released and run_id == self.run_id

    link = ReleasedLink(released())

    class Manager:
        profile = SimpleNamespace(pi_id='pi')

        def data_link(self):
            return link

        def admit_write(self, link, claim):
            return claim()

        def disconnect(self):
            pass

    com, events = Com(), []
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        worker = BridgeWorker(Manager(), lambda: com, db, events.append)
        assert worker.status.demo_only is True
        worker.start()
        deadline = __import__('time').monotonic() + 3
        while not any(e.detail.get('release') == 'test_unaccepted' for e in list(events) if e.kind == 'exchange'):
            assert __import__('time').monotonic() < deadline
        assert com.payloads and worker.status.demo_only is False
        link.released = False
        link.reply = dict(version=1, type='idle', run_id='run', release_block='gesperrt')
        while worker.status.demo_only is False:
            assert __import__('time').monotonic() < deadline
        worker.stop()
    assert com.payloads == [b'%+1.2345\r\n']


def test_worker_drops_release_immediately_when_link_loses_it_between_exchanges(tmp_path):
    import threading as _threading
    import time as _time

    from dispread_bridge_app.delivery_journal import DeliveryJournal
    from dispread_bridge_app.worker import BridgeWorker

    hold = _threading.Event()

    class ReleasedLink(Link):
        released, run_id = True, 'run'

        def test_release_for(self, run_id):
            return self.released and run_id == self.run_id

        def receive(self):
            if len(self.messages) > 2:
                hold.wait(3)  # naechster Austausch bleibt haengen
            return super().receive()

    link = ReleasedLink(released())

    class Manager:
        profile = SimpleNamespace(pi_id='pi')

        def data_link(self):
            return link

        def admit_write(self, link, claim):
            return claim()

        def disconnect(self):
            hold.set()

    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        worker = BridgeWorker(Manager(), lambda: Com(), db, lambda event: None)
        worker.start()
        deadline = _time.monotonic() + 3
        while worker.status.demo_only:
            assert _time.monotonic() < deadline
        link.released = False  # Pi meldet neuen, gesperrten Lauf
        assert worker.status.demo_only is True
        worker.stop()


# --- B2 (2026-11-11): Taktzeilen und Auffuellung im WorkerStatus --------------------

def tick_message(seq, valid=True, run='run'):
    return dict(version=1, type='tick', run_id=run, seq=seq, valid=valid,
                value_text='1.2345' if valid else None, frame_sequence=seq if valid else None,
                time_unix_ns=1_794_397_184_000_000_000 + seq * 100_000_000,
                origin_unix_ns=1_794_397_184_000_000_000, rate_hz=10, release='test_unaccepted')


def _tick_worker(tmp_path, replies, db):
    from dispread_bridge_app.worker import BridgeWorker

    class TickLink(Link):
        run_id = 'run'

        def test_release_for(self, run_id):
            return run_id == self.run_id

        def receive(self):
            reply = replies.pop(0) if replies else dict(version=1, type='idle', run_id='run',
                                                        release_block=None, release='test_unaccepted')
            return dict(reply, request_id=self.messages[-1]['request_id'])

    link = TickLink()

    class Manager:
        profile = SimpleNamespace(pi_id='pi')

        def data_link(self):
            return link

        def admit_write(self, link, claim):
            return claim()

        def disconnect(self):
            pass

    com, events = Com(), []
    return BridgeWorker(Manager(), lambda: com, db, events.append), com, events, link


def test_worker_status_counts_tick_lines_fills_and_disturbance(tmp_path):
    import time as _time

    from dispread_bridge_app.delivery_journal import DeliveryJournal
    from dispread_bridge_app.worker import WorkerStatus

    idle = WorkerStatus('idle', False, False, None)
    assert (idle.ticks_written, idle.ticks_invalid, idle.ticks_filled, idle.tick_disturbed) == (0, 0, 0, False)
    replies = [tick_message(1), tick_message(2, valid=False), tick_message(5), tick_message(70)]
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        worker, com, events, link = _tick_worker(tmp_path, replies, db)
        worker.start()
        deadline = _time.monotonic() + 3
        while not any(e.kind == 'tick_disturbed' for e in list(events)):  # nach Takt 70
            assert _time.monotonic() < deadline, worker.status
            _time.sleep(.01)
        status = worker.status
        worker.stop()
    assert (status.ticks_written, status.ticks_invalid, status.ticks_filled) == (4, 1, 2)
    assert [p.split(b';')[2] for p in com.payloads] == [b'1', b'2', b'3', b'4', b'5', b'70']
    assert any(e.kind == 'tick_disturbed' for e in events)
    assert [m['filled'] for m in link.messages if m['type'] == 'tick_ack'] == [0, 0, 2, 0]


def test_unknown_tick_line_blocks_worker_before_com_open(tmp_path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal

    com, events, done = Com(), [], threading.Event()

    def emit(event):
        events.append(event)
        if event.kind == 'stopped':
            done.set()
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        db.begin_tick('pi', 'old-run', 3, 'tick', True, b'%1.0;1;3;1.000000\r\n')
    with DeliveryJournal(tmp_path / 'audit.sqlite') as db:
        w = worker(Connection(Link()), com, db, emit)
        w.start()
        assert done.wait(2)
        w.stop()
        assert w.failure.kind == 'blocked' and w.failure.code == 'unknown_delivery'
    assert not com.closed and com.payloads == []
