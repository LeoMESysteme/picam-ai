"""Pi-side composition proof: actual TLS/routes/PairingStore, fake output COM.

This deliberately does not qualify native Windows DPAPI, drivers or GSVmulti.
Run with PYTHONPATH=src:windows/bridge/src and the project .venv.
"""

import asyncio
import threading
import time
from types import SimpleNamespace

import pytest
from aiohttp import web
from dispread_bridge_app.connection import ConnectionError, ConnectionManager
from dispread_bridge_app.credentials import CredentialStore
from dispread_bridge_app.delivery_journal import DeliveryJournal
from dispread_bridge_app.worker import BridgeWorker

from dispread.bridge.discovery import TailscaleStatus
from dispread.bridge.hub import BridgeHub
from dispread.bridge.identity import DeviceIdentity
from dispread.bridge.output_state import RELEASE_BLOCK, OutputState
from dispread.bridge.pairing import PairingStore
from dispread.bridge.routes import add_bridge_routes
from dispread.bridge.types import BridgeProfile
from dispread.records import TimeBaseKind, Timestamp, ValueRecord, ValueStatus


class TestProtector:
    """Opaque process-local test vault; explicitly not Windows protection proof."""
    __test__ = False

    def __init__(self):
        self.values = {}

    def protect(self, value):
        import secrets
        key = secrets.token_bytes(32)
        self.values[key] = value
        return key

    def unprotect(self, value):
        return self.values[value]


class FakeCom:
    def __init__(self):
        self.payloads = []
        self.closed = False

    def write(self, payload):
        self.payloads.append(payload)
        return len(payload)

    def close(self):
        self.closed = True


def wait_for(predicate, timeout=6):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, 'condition not reached'
        time.sleep(.01)


def record(sequence, *, valid=True):
    return ValueRecord(sequence, Timestamp(sequence, TimeBaseKind.SYNTHETIC),
                       float(sequence) if valid else None, 'mV/V',
                       ValueStatus.VALID if valid else ValueStatus.UNREADABLE,
                       1.0, 'demo', None, None, raw_text=f'+{sequence}.0',
                       reject_reasons=() if valid else ('demo',))


@pytest.fixture(scope='module')
def identity(tmp_path_factory):
    return DeviceIdentity.load_or_create(tmp_path_factory.mktemp('g1-identity'), 'g1-pi')


def exercise_tls(tmp_path, identity, exercise, *, com=None, journal_type=DeliveryJournal):
    async def run():
        store = PairingStore(tmp_path / 'pairing')
        hub = BridgeHub(identity.pi_id, tmp_path / 'pi-audit', identity=identity, pairing_store=store)
        app = web.Application()
        add_bridge_routes(app, identity, store, hub, lambda request: True)
        runner = web.AppRunner(app, access_log=None, shutdown_timeout=.2)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0, ssl_context=identity.tls_context())
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        profile = BridgeProfile(1, identity.pi_id, 'G1', identity.certificate_pem, identity.fingerprint,
                                (f'https://127.0.0.1:{port}',), 2, store.create_offer('network', 'g1-client'))
        credentials = CredentialStore(tmp_path / 'windows-credentials', protector=TestProtector())
        manager = ConnectionManager(profile, 'g1-client', credentials, None,
                                    network_diagnostics=lambda: TailscaleStatus('running'))
        events, states = [], []
        output = com or FakeCom()
        with journal_type(tmp_path / 'delivery.sqlite') as journal:
            worker = BridgeWorker(manager, lambda: output, journal, events.append)
            manager.set_worker(worker)
            rig = SimpleNamespace(manager=manager, worker=worker, com=output, journal=journal,
                                  events=events, hub=hub, store=store, credentials=credentials,
                                  profile=profile, states=states)

            def bind(*, demo=True):
                state = OutputState(tmp_path / ('run-' + str(len(states))), demo=demo)
                state.start()
                hub.bind_run(state.run_id, state)
                states.append(state)
                return state
            rig.bind = bind

            def connected_exercise():
                manager.connect('network')
                wait_for(lambda: manager.snapshot().peer == 'authenticated')
                token = credentials.load(identity.pi_id, 'network', expected_pin=identity.fingerprint)
                assert token and token != profile.pairing_offer
                assert store.authorize(token, 'network') == 'g1-client'
                exercise(rig)
            try:
                await asyncio.to_thread(connected_exercise)
            finally:
                await asyncio.to_thread(worker.stop)
                await asyncio.sleep(.05)
                await runner.cleanup()
                hub.close()
                for state in states:
                    state.stop()
    asyncio.run(run())


def test_dut_stays_locked_after_successful_pairing(tmp_path, identity):
    def check(rig):
        initial = rig.manager.snapshot()
        assert (initial.output, initial.next_action) == ('output_off', 'output_off')
        state = rig.bind(demo=False)
        state.publish(record(1))
        rig.worker.start()
        wait_for(lambda: any(e.kind == 'exchange' for e in rig.events))
        assert rig.com.payloads == []
        assert state.status()['release_block'] == RELEASE_BLOCK
        assert rig.hub.prepare('network', 'g1-client').release_block == RELEASE_BLOCK
        blocked = rig.manager.snapshot()
        assert (blocked.output, blocked.next_action) == ('blocked', 'dut_release_blocked')
        assert blocked.gsv == 'unconfirmed'
        rig.hub.unbind_run(state.run_id)
        state.stop()
        wait_for(lambda: rig.manager.snapshot().output == 'output_off')
        assert rig.manager.snapshot().next_action == 'output_off'
        assert rig.com.payloads == []
        demo = rig.bind(demo=True)  # Explicit empty demo: readiness, not COM throughput.
        wait_for(lambda: rig.manager.snapshot().output == 'demo_only')
        assert (rig.manager.snapshot().output, rig.manager.snapshot().next_action) == ('demo_only', None)
        assert rig.com.payloads == []
        first = rig.manager.data_link()
        first.transport.close()
        wait_for(lambda: rig.worker.status.state == 'recovering')
        assert rig.manager.snapshot().output == 'unavailable'
        rig.hub.unbind_run(demo.run_id)
        demo.stop()
        wait_for(lambda: rig.manager.snapshot().peer == 'authenticated' and rig.worker.status.output_ready)
        assert rig.manager.data_link() is not first
        recovered = rig.manager.snapshot()
        assert (recovered.output, recovered.next_action) == ('output_off', 'output_off')
        assert recovered.gsv == 'unconfirmed'
        assert rig.com.payloads == []
    exercise_tls(tmp_path, identity, check)


def test_barrier_precedes_only_latest_valid_over_real_tls(tmp_path, identity):
    def check(rig):
        state = rig.bind()
        state.publish(record(1, valid=False))
        state.publish(record(2))
        state.publish(record(100))
        rig.worker.start()
        wait_for(lambda: len([a for a in rig.journal.attempts() if a.outcome == 'written']) == 2)
        assert rig.com.payloads == [b'%NaN\r\n', b'%+100.0\r\n']
        assert [a.frame_sequence for a in rig.journal.attempts()] == [1, 100]
        assert all(a.outcome == 'written' for a in rig.journal.attempts())
        assert rig.manager.snapshot().output == 'demo_only'
    exercise_tls(tmp_path, identity, check)


def test_actual_manager_worker_recovers_same_route_without_replaying_or_starting_demo(tmp_path, identity):
    def check(rig):
        state = rig.bind()
        state.publish(record(1))
        rig.worker.start()
        wait_for(lambda: len(rig.com.payloads) == 1)
        first = rig.manager.data_link()
        first.transport.close()  # Actual WSS socket closure; W1 owns all retry.
        wait_for(lambda: rig.worker.status.state == 'recovering')
        assert not rig.worker.status.output_ready
        assert rig.manager.snapshot().output == 'unavailable'
        rig.hub.unbind_run(state.run_id)
        state.stop()
        wait_for(lambda: rig.manager.snapshot().peer == 'authenticated')
        replacement = rig.manager.data_link()
        assert replacement is not first and replacement.mode == first.mode == 'network'
        assert replacement.lease_id != first.lease_id
        wait_for(lambda: rig.worker.status.output_ready)
        assert rig.com.payloads == [b'%+1.0\r\n']
        assert rig.hub.status()['run_id'] is None  # Recovery did not start a demo.
        with pytest.raises(ConnectionError):
            rig.manager.admit_write(first, lambda: pytest.fail('revoked generation admitted'))
        new = rig.bind()
        new.publish(record(9))
        wait_for(lambda: len(rig.com.payloads) == 2)
        assert rig.com.payloads == [b'%+1.0\r\n', b'%+9.0\r\n']
        assert [a.run_id for a in rig.journal.attempts()] == [state.run_id, new.run_id]
        assert rig.worker.is_active() and rig.worker.failure is None
    exercise_tls(tmp_path, identity, check)


def test_clean_ended_keeps_connection_for_next_explicit_demo(tmp_path, identity):
    def check(rig):
        state = rig.bind()
        state.stop()  # Keep bound briefly so the actual route returns ended.
        rig.worker.start()
        wait_for(lambda: any(e.kind == 'exchange' and e.detail['outcome'] == 'ended' for e in rig.events))
        first = rig.manager.data_link()
        assert rig.worker.is_active() and rig.worker.status.output_ready
        assert rig.manager.snapshot().peer == 'authenticated'
        rig.hub.unbind_run(state.run_id)
        first.heartbeat()  # Validated run resync before the explicit request.
        run_id = rig.manager.start_demo(count=2, rate_hz=10)
        wait_for(lambda: bool(rig.com.payloads))
        assert run_id != state.run_id
        assert rig.manager.data_link() is first
    exercise_tls(tmp_path, identity, check)


def test_stop_during_real_connection_recovery_is_permanent(tmp_path, identity):
    def check(rig):
        rig.worker.start()
        wait_for(lambda: rig.worker.status.output_ready)
        rig.manager.data_link().transport.close()
        wait_for(lambda: rig.worker.status.state == 'recovering')
        rig.worker.stop()
        assert not rig.worker.is_active() and rig.com.closed
        assert rig.manager.snapshot().peer == 'disconnected'
        with pytest.raises(RuntimeError, match='permanently stopped'):
            rig.worker.start()
        assert rig.com.payloads == []
    exercise_tls(tmp_path, identity, check)


def test_revoked_pairing_terminates_recovery_instead_of_spinning(tmp_path, identity):
    def check(rig):
        rig.worker.start()
        wait_for(lambda: rig.worker.status.output_ready)
        rig.store.revoke('g1-client')
        wait_for(lambda: not rig.worker.is_active())
        assert rig.worker.failure.kind == 'connection_failed'
        assert rig.manager.snapshot().output == 'blocked'
        assert rig.manager.snapshot().gsv == 'unconfirmed'
        assert rig.com.payloads == [] and rig.com.closed
    exercise_tls(tmp_path, identity, check)


def test_unknown_barrier_from_previous_run_blocks_new_run_before_com(tmp_path, identity):
    def check(rig):
        intent = rig.journal.begin_attempt(identity.pi_id, 'previous-run', 1, 1, b'%NaN\r\n')
        rig.journal.finish_attempt(intent, 'unknown')
        state = rig.bind()
        state.publish(record(5))
        rig.worker.start()
        wait_for(lambda: not rig.worker.is_active())
        assert rig.worker.failure.code == 'unknown_invalidation'
        assert rig.manager.snapshot().output == 'blocked'
        assert rig.com.payloads == [] and not rig.com.closed
    exercise_tls(tmp_path, identity, check)


def test_old_generation_intent_cannot_borrow_reconnected_lease(tmp_path, identity):
    entered, release = threading.Event(), threading.Event()
    class BlockingJournal(DeliveryJournal):
        def begin_attempt(self, *args):
            result = super().begin_attempt(*args)
            if not entered.is_set():
                entered.set()
                assert release.wait(8)
            return result
    def check(rig):
        state = rig.bind()
        state.publish(record(1))
        rig.worker.start()
        try:
            assert entered.wait(2)
            first = rig.manager.data_link()
            first.transport.close()
            wait_for(lambda: rig.manager.snapshot().peer == 'backoff')
            rig.hub.unbind_run(state.run_id)
            state.stop()
            wait_for(lambda: rig.manager.snapshot().peer == 'authenticated')
            assert rig.manager.data_link() is not first
            new = rig.bind()
            new.publish(record(9))
        finally:
            release.set()
        wait_for(lambda: any(a.outcome == 'written' for a in rig.journal.attempts()))
        assert rig.com.payloads == [b'%+9.0\r\n']
        attempts = rig.journal.attempts()
        assert [(a.frame_sequence, a.outcome) for a in attempts] == [(1, 'not_written'), (9, 'written')]
    exercise_tls(tmp_path, identity, check, journal_type=BlockingJournal)


@pytest.mark.parametrize('failure', ['audit', 'com_and_ack', 'event_sink'])
def test_uncertain_output_and_audit_failures_never_enter_recovery(tmp_path, identity, failure):
    class FailingJournal(DeliveryJournal):
        def finish_attempt(self, *args):
            if failure == 'audit':
                raise OSError('simulated audit disk failure')
            return super().finish_attempt(*args)
    def check(rig):
        state = rig.bind()
        state.publish(record(1))
        if failure == 'com_and_ack':
            def short_and_lost(payload):
                rig.com.payloads.append(payload)
                rig.manager.data_link().transport.close()
                return len(payload) - 1
            rig.com.write = short_and_lost
        if failure == 'event_sink':
            def failed_sink(event):
                rig.events.append(event)
                if event.kind == 'exchange':
                    raise OSError('simulated event sink failure')
            rig.worker.emit = failed_sink
        rig.worker.start()
        wait_for(lambda: not rig.worker.is_active())
        expected = 'unknown_delivery' if failure == 'com_and_ack' else 'audit_failed'
        assert rig.worker.failure.code == expected
        assert not any(e.kind == 'recovering' for e in rig.events)
        assert rig.manager.snapshot().output == 'blocked'
        assert rig.com.payloads == [b'%+1.0\r\n']
        assert rig.com.closed
        if failure != 'event_sink':
            assert rig.journal.unresolved()
    exercise_tls(tmp_path, identity, check, journal_type=FailingJournal)


def test_numeric_unknown_survives_sqlite_restart_without_retransmit(tmp_path, identity):
    def check(rig):
        state = rig.bind()
        state.publish(record(1))
        rig.journal.begin_attempt(identity.pi_id, state.run_id, 1, None, b'%+1.0\r\n')
        # Model a previously interrupted COM intent through a real DB reopen.
        rig.journal.close()
        reopened = DeliveryJournal(tmp_path / 'delivery.sqlite')
        rig.worker.journal = reopened
        try:
            rig.worker.start()
            wait_for(lambda: not rig.worker.is_active())
            assert rig.worker.failure.code == 'unknown_delivery'
            assert rig.com.payloads == []
            assert reopened.unresolved()[0].outcome == 'pending'
        finally:
            rig.worker.stop()
            reopened.close()
    exercise_tls(tmp_path, identity, check)


@pytest.mark.parametrize('before_release', [True, False], ids=['run-still-reserved', 'run-released'])
def test_ack_in_flight_at_run_end_does_not_kill_the_connection(tmp_path, identity, before_release):
    """Wert angeboten, Lauf endet, dann kommt die Quittung: kein terminaler Verbindungsfehler.

    Die Pi-Seite hat das Angebot beim Laufende als unbestaetigt auditiert (abandon_pending);
    die verspaetete Quittung wird nicht angenommen, die Verbindung bleibt fuer den naechsten Lauf.
    """
    def check(rig):
        state = rig.bind(demo=True)
        state.publish(record(1))
        link = rig.manager.data_link()
        link.send({'version': 1, 'type': 'poll', 'request_id': 'p1'})
        offered = link.receive()
        assert offered['type'] == 'record'
        rig.hub.unbind_run(state.run_id)
        if not before_release:
            rig.hub.release_real_run(state.run_id)
        link.send({'version': 1, 'type': 'ack', 'request_id': offered['request_id'], 'run_id': offered['run_id'],
                   'frame_sequence': 1, 'barrier_id': None, 'outcome': 'written'})
        assert rig.manager.snapshot().peer == 'authenticated'
        assert rig.manager.data_link() is link
        link.send({'version': 1, 'type': 'poll', 'request_id': 'p2'})
        assert link.receive()['type'] in ('idle', 'ended')
    exercise_tls(tmp_path, identity, check)


def test_poll_survives_two_state_changes_between_hello_and_retry(tmp_path, identity):
    """Ursache des R4-Befunds (connection_failed am Laufende): zwischen unbind_run und release_real_run
    antwortet der Pi zweimal mit hello (Freigabestand weg, dann Lauf weg). Ein einziger Wiederholversuch
    endete in peer_invalid; der Client muss mehrere Zustandswechsel hintereinander aufnehmen."""
    from dispread.bridge.output_state import TEST_RELEASE

    def check(rig):
        rig.hub.reserve_real_run('run-r')
        state = OutputState(tmp_path / 'run-r', release=TEST_RELEASE)
        state.run_id = 'run-r'
        state.start()
        rig.hub.bind_run('run-r', state, transport='network')
        link = rig.manager.data_link()
        link.send({'version': 1, 'type': 'poll', 'request_id': 'p0'})
        assert link.receive()['type'] == 'idle'
        rig.hub.unbind_run('run-r')          # Freigabestand verschwindet, Lauf noch reserviert
        original, calls = link._exchange, []

        def exchange(request, **kwargs):
            reply = original(request, **kwargs)
            calls.append(reply['type'])
            if len(calls) == 1:
                assert reply['type'] == 'hello'
                rig.hub.release_real_run('run-r')   # zweiter Wechsel vor der Wiederholung
            return reply
        link._exchange = exchange
        link.send({'version': 1, 'type': 'poll', 'request_id': 'p1'})
        assert link.receive()['type'] == 'idle'
        assert calls[0] == 'hello' and calls[-1] == 'idle'
        assert rig.manager.snapshot().peer == 'authenticated'
        state.stop()
    exercise_tls(tmp_path, identity, check)
