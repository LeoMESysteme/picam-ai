"""Durable claims, payload binding and conservative restart behavior."""
from concurrent.futures import ThreadPoolExecutor

import pytest


def journal(path):
    from dispread_bridge_app.delivery_journal import DeliveryJournal
    return DeliveryJournal(path)


def test_intent_survives_restart_and_never_reclaims_numeric(tmp_path):
    path = tmp_path / 'audit.sqlite'
    with journal(path) as first:
        attempt = first.begin_attempt('pi', 'run', 1, None, b'%+1\r\n')
    with journal(path) as second:
        assert second.unresolved()[0].attempt_id == attempt
        assert not second.should_emit('pi', 'run', 1, None, b'%+1\r\n')
        with pytest.raises(Exception, match='duplicate'):
            second.begin_attempt('pi', 'run', 1, None, b'%+1\r\n')


def test_written_receipt_survives_restart_and_binds_bytes(tmp_path):
    path = tmp_path / 'audit.sqlite'
    with journal(path) as first:
        attempt = first.begin_attempt('pi', 'run', 1, None, b'%+1\r\n')
        first.finish_attempt(attempt, 'written')
    with journal(path) as second:
        assert second.receipt('pi', 'run', 1, None, b'%+1\r\n') == 'written'
        assert second.unresolved() == ()
        with pytest.raises(Exception, match='payload'):
            second.begin_attempt('pi', 'run', 1, None, b'%+2\r\n')


def test_unknown_invalidation_blocks_new_valid_after_restart(tmp_path):
    path = tmp_path / 'audit.sqlite'
    with journal(path) as first:
        attempt = first.begin_attempt('pi', 'run', 1, 8, b'%NaN\r\n')
        first.finish_attempt(attempt, 'unknown')
    with journal(path) as second:
        assert not second.should_emit('pi', 'other-run', 200, None, b'%+1\r\n')
        with pytest.raises(Exception, match='invalidation'):
            second.begin_attempt('pi', 'other-run', 200, None, b'%+1\r\n')
        assert second.should_emit('different-pi', 'run', 1, None, b'%+1\r\n')


def test_absent_barrier_claim_is_atomic_across_connections(tmp_path):
    path = tmp_path / 'audit.sqlite'
    with journal(path):
        pass
    def claim(_):
        with journal(path) as db:
            try:
                return db.begin_attempt('pi', 'run', 1, None, b'%+1\r\n')
            except Exception as exc:
                assert 'duplicate' in str(exc)
                return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(claim, range(12)))
    assert sum(result is not None for result in results) == 1


def test_outcome_cannot_upgrade_unknown_to_written(tmp_path):
    with journal(tmp_path / 'audit.sqlite') as db:
        attempt = db.begin_attempt('pi', 'run', 1, None, b'%+1\r\n')
        db.finish_attempt(attempt, 'unknown')
        with pytest.raises(Exception, match='terminal'):
            db.finish_attempt(attempt, 'written')


def test_diagnostic_retention_preserves_audit_and_redacts_secrets(tmp_path):
    from dispread_bridge_app.delivery_journal import DiagnosticStore
    audit = tmp_path / 'audit.sqlite'
    audit.write_bytes(b'preserve')
    store = DiagnosticStore(tmp_path / 'diagnostics', max_bytes=160, max_age_s=10,
                            clock=lambda: 20)
    store.append({'type': 'connected', 'token': 'SECRET', 'nested': {'password': 'SECRET'}})
    for _ in range(10):
        store.append({'type': 'idle'})
    assert store.usage()['bytes'] <= 160
    assert 'SECRET' not in store.export()
    assert audit.read_bytes() == b'preserve'
    expired = DiagnosticStore(tmp_path / 'diagnostics', clock=lambda: 100, max_age_s=10)
    expired.prune()
    assert expired.usage()['bytes'] == 0


def test_unknown_invalidation_prevents_reack_of_old_valid_receipt(tmp_path):
    with journal(tmp_path / 'audit.sqlite') as db:
        old = db.begin_attempt('pi', 'run', 1, None, b'%+1\r\n')
        db.finish_attempt(old, 'written')
        db.begin_attempt('pi', 'run', 2, 10, b'%NaN\r\n')
        with pytest.raises(Exception, match='invalidation'):
            db.begin_attempt('pi', 'run', 1, None, b'%+1\r\n')


def test_diagnostics_do_not_export_credential_shaped_values_in_public_fields(tmp_path):
    from dispread_bridge_app.delivery_journal import DiagnosticStore
    store = DiagnosticStore(tmp_path)
    store.append({'type': 'LONGsecrettoken123', 'outcome': 'unknown'})
    assert 'LONGsecrettoken123' not in store.export()
    assert 'unknown' in store.export()


@pytest.mark.parametrize('kwargs', [{'max_bytes': 64*1024*1024 + 1}, {'max_age_s': 7*86400 + 1}])
def test_detail_retention_cannot_exceed_backend_maximum(tmp_path, kwargs):
    from dispread_bridge_app.delivery_journal import DiagnosticStore
    with pytest.raises(ValueError):
        DiagnosticStore(tmp_path, **kwargs)


def test_detail_store_bounds_file_count_for_small_events(tmp_path):
    from dispread_bridge_app.delivery_journal import DiagnosticStore
    store = DiagnosticStore(tmp_path)
    for _ in range(100):
        store.append({'type': 'idle'})
    assert len(list(tmp_path.iterdir())) <= 2
    assert len(store.export().splitlines()) == 100


def test_orphaned_intent_cannot_be_upgraded_by_new_journal_owner(tmp_path):
    path = tmp_path / 'audit.sqlite'
    with journal(path) as first:
        attempt = first.begin_attempt('pi', 'run', 1, 5, b'%NaN\r\n')
    with journal(path) as second:
        with pytest.raises(Exception, match='live claim'):
            second.finish_attempt(attempt, 'written')
        assert second.has_unresolved_invalidation('pi')


def test_expired_diagnostics_pruned_on_reopen_without_explicit_maintenance(tmp_path):
    from dispread_bridge_app.delivery_journal import DiagnosticStore
    audit = tmp_path / 'audit.sqlite'
    audit.write_bytes(b'audit-preserved')
    path = tmp_path / 'detail'
    now = [0]
    first = DiagnosticStore(path, max_age_s=10, clock=lambda: now[0])
    first.append({'type': 'connected'})
    now[0] = 11
    second = DiagnosticStore(path, max_age_s=10, clock=lambda: now[0])
    assert list(path.glob('detail-*.jsonl')) == []
    assert second.export() == ''
    assert second.usage()['bytes'] == 0
    assert audit.read_bytes() == b'audit-preserved'


@pytest.mark.parametrize('access', ['export', 'usage'])
def test_clock_advance_prunes_details_on_access_without_append(tmp_path, access):
    from dispread_bridge_app.delivery_journal import DiagnosticStore
    audit = tmp_path / 'audit.sqlite'
    audit.write_bytes(b'audit-preserved')
    now = [0]
    store = DiagnosticStore(tmp_path / 'detail', max_age_s=10, clock=lambda: now[0])
    store.append({'type': 'connected'})
    now[0] = 11
    result = getattr(store, access)()
    assert result == '' if access == 'export' else result['bytes'] == 0
    assert list((tmp_path / 'detail').glob('detail-*.jsonl')) == []
    assert audit.read_bytes() == b'audit-preserved'


def test_secret_dictionary_keys_are_dropped_recursively_before_storage(tmp_path):
    from dispread_bridge_app.delivery_journal import DiagnosticStore
    store = DiagnosticStore(tmp_path)
    store.append({'Bearer TOPSECRET': 1, 'detail': {'nested': [{'Bearer SECRET2': 1}],
                                                 'type': 'connected'}})
    stored = ''.join(path.read_text() for path in tmp_path.glob('detail-*.jsonl'))
    assert 'TOPSECRET' not in stored
    assert 'SECRET2' not in stored
    assert 'connected' in stored
    assert 'TOPSECRET' not in store.export() and 'SECRET2' not in store.export()


def test_legacy_diagnostic_export_redacts_unknown_secret_keys_recursively(tmp_path):
    import json
    import os

    from dispread_bridge_app.delivery_journal import DiagnosticStore
    legacy = tmp_path / 'detail-legacy.jsonl'
    legacy.write_text(json.dumps({'Bearer TOPSECRET': 1,
                                'detail': {'nested': [{'Bearer SECRET2': 1}],
                                           'type': 'connected'}}) + '\n')
    os.utime(legacy, (0, 0))
    store = DiagnosticStore(tmp_path, clock=lambda: 0)
    exported = store.export()
    assert 'TOPSECRET' not in exported and 'SECRET2' not in exported
    assert 'connected' in exported



def test_diagnostic_export_preserves_reviewed_recovery_codes_and_redacts_nested_text(tmp_path):
    import json

    from dispread_bridge_app.delivery_journal import DiagnosticStore

    from dispread.bridge.types import BridgeEvent
    store = DiagnosticStore(tmp_path)
    store.append(BridgeEvent('recovering', 'connection_unavailable', None, None,
                             dict(nested=[dict(code='token=SECRET', kind='arbitrary-state')],
                                  token='SECRET')))
    exported = store.export()
    value = json.loads(exported)
    assert (value['kind'], value['code']) == ('recovering', 'connection_unavailable')
    assert value['detail']['nested'] == [dict(code='[redacted]', kind='[redacted]')]
    assert 'SECRET' not in exported and 'arbitrary-state' not in exported


# --- B2 (2026-11-11): Takte und Fehlwertzeilen, je Zeile vor dem COM-Schreiben ------

def test_tick_rows_track_last_written_and_survive_restart(tmp_path):
    path = tmp_path / 'audit.sqlite'
    with journal(path) as first:
        assert first.last_tick_written('pi', 'run') == 0
        fill = first.begin_tick('pi', 'run', 1, 'fill', False, b'%99999999.0;0;1;1.000000\r\n')
        first.finish_tick(fill, 'written')
        tick = first.begin_tick('pi', 'run', 2, 'tick', True, b'%1.0;1;2;1.100000\r\n')
        first.finish_tick(tick, 'written')
        lost = first.begin_tick('pi', 'run', 3, 'tick', False, b'%99999999.0;0;3;1.200000\r\n')
        first.finish_tick(lost, 'not_written')
    with journal(path) as second:
        assert second.last_tick_written('pi', 'run') == 2      # not_written zaehlt nicht
        assert second.last_tick_written('pi', 'other') == 0
        assert second.tick_outcome('pi', 'run', 2) == 'written'
        assert second.tick_outcome('pi', 'run', 1) is None     # Auffuellung ist kein Pi-Takt
        assert second.unresolved_ticks() == ()


def test_pending_tick_blocks_every_further_tick_for_this_pi(tmp_path):
    from dispread.gsv_bridge import DeliveryAlreadyAttempted, DeliveryBlockedError

    path = tmp_path / 'audit.sqlite'
    with journal(path) as first:
        first.begin_tick('pi', 'run', 1, 'tick', True, b'%1.0;1;1;1.000000\r\n')
    with journal(path) as second:
        assert [row.seq for row in second.unresolved_ticks()] == [1]
        assert second.has_unresolved_tick('pi') and not second.has_unresolved_tick('other')
        with pytest.raises(DeliveryBlockedError):
            second.begin_tick('pi', 'run', 2, 'tick', True, b'%1.0;1;2;1.100000\r\n')
        with pytest.raises(DeliveryAlreadyAttempted):
            second.begin_tick('pi', 'run', 1, 'tick', True, b'%1.0;1;1;1.000000\r\n')
        orphan = second.unresolved_ticks()[0].attempt_id
        with pytest.raises(Exception, match='live claim'):
            second.finish_tick(orphan, 'written')


def test_unfilled_gap_is_recorded(tmp_path):
    with journal(tmp_path / 'audit.sqlite') as store:
        store.record_tick_gap('pi', 'run', 60, 59)
        assert store.tick_gaps('pi', 'run') == ((60, 59),)
        assert store.last_tick_written('pi', 'run') == 0


@pytest.mark.parametrize('args', [
    ('pi', 'run', 0, 'tick', True, b'x'), ('pi', 'run', 1, 'other', True, b'x'),
    ('pi', 'run', 1, 'fill', True, b'x'), ('pi', 'run', 1, 'tick', True, b''),
    ('pi', '', 1, 'tick', True, b'x'),
])
def test_tick_identity_is_validated(tmp_path, args):
    with journal(tmp_path / 'audit.sqlite') as store:
        with pytest.raises(Exception, match='invalid'):
            store.begin_tick(*args)


def test_expired_tick_can_later_be_filled_once(tmp_path):
    from dispread.gsv_bridge import DeliveryAlreadyAttempted

    with journal(tmp_path / 'audit.sqlite') as store:
        tick = store.begin_tick('pi', 'run', 1, 'tick', True, b'%1.0;1;1;1.000000\r\n')
        store.finish_tick(tick, 'not_written')
        fill = store.begin_tick('pi', 'run', 1, 'fill', False, b'%99999999.0;0;1;1.000000\r\n')
        store.finish_tick(fill, 'written')
        assert store.last_tick_written('pi', 'run') == 1
        with pytest.raises(DeliveryAlreadyAttempted):
            store.begin_tick('pi', 'run', 1, 'fill', False, b'%99999999.0;0;1;1.000000\r\n')


def test_diagnostics_keep_time_and_known_error_codes_but_not_secrets(tmp_path):
    """13.11.2026: UART-Abbruch im Export nur als „[redacted]/[redacted]“ ohne Zeit."""
    import json

    from dispread_bridge_app.delivery_journal import DiagnosticStore

    from dispread.bridge.types import BridgeEvent
    store = DiagnosticStore(tmp_path, clock=lambda: 1794398707.4388)
    store.append(BridgeEvent('connection', 'uart_peer_unavailable', 'run-secret-id', None,
                             dict(token='SECRET', outcome='unknown')))
    line = json.loads(store.export())
    assert (line['kind'], line['code'], line['ts']) == ('connection', 'uart_peer_unavailable', 1794398707.439)
    assert 'SECRET' not in store.export() and 'run-secret-id' not in store.export()
