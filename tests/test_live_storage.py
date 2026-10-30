"""Aufbewahrung ausschliesslich in temporaeren Live-Baeumen."""

import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from dispread.live.storage import cleanup_runs

NOW = datetime(2026, 10, 23, tzinfo=UTC)
OLD = NOW - timedelta(days=20)


def age_tree(path, when=OLD):
    for item in [*path.rglob('*'), path]:
        os.utime(item, (when.timestamp(), when.timestamp()), follow_symlinks=False)


def run_tree(root, session='live-20261001T120000Z', run='run-01', ended=OLD):
    path = root / session / run
    (path / 'diagnose').mkdir(parents=True)
    (path / 'diagnose' / '001.png').write_bytes(b'picture')
    (path / 'records.jsonl').write_bytes(b'audit')
    (path / 'session.json').write_text(json.dumps({'ended_at_utc': ended.isoformat() if ended else None}))
    age_tree(path)
    return path


@pytest.mark.parametrize('diagnostics_only', [False, True])
def test_cleanup_dry_run_lists_sizes_then_explicit_execute(tmp_path, diagnostics_only):
    root = tmp_path / 'live'
    run = run_tree(root)
    target = run / 'diagnose' if diagnostics_only else run
    expected = sum(p.stat().st_size for p in target.rglob('*') if p.is_file())
    result = cleanup_runs(root, days=10, diagnostics_only=diagnostics_only, now=NOW)
    assert result['dry_run'] is True and result['total_bytes'] == expected
    assert result['entries'] == [{'path': str(target), 'bytes': expected, 'mb': expected / 1e6,
                                  'status': 'planned'}]
    assert target.exists()
    deleted = cleanup_runs(root, days=10, diagnostics_only=diagnostics_only, execute=True, now=NOW)
    assert deleted['entries'] == [{**result['entries'][0], 'status': 'deleted'}]
    assert not target.exists() and deleted['failed'] is False
    assert deleted['dry_run'] is False
    if diagnostics_only:
        assert (run / 'records.jsonl').read_bytes() == b'audit'


def test_cleanup_keeps_setup_profile_running_unknown_recent_and_protected(tmp_path):
    root = tmp_path / 'live'
    old = run_tree(root)
    session = old.parent
    (session / 'setup').mkdir()
    (session / 'setup' / 'still.png').write_bytes(b'setup')
    (session / 'profile.json').write_bytes(b'confirmed')
    (session / 'confirmation.json').write_bytes(b'name')
    running = run_tree(root, run='run-02', ended=None)
    protected = run_tree(root, run='run-03')
    recent = run_tree(root, run='run-04', ended=NOW)
    copying = run_tree(root, run='run-05')
    age_tree(copying / 'diagnose', NOW)
    malformed = run_tree(root, run='run-06')
    (malformed / 'session.json').write_text('{bad')
    age_tree(malformed)
    outside = run_tree(tmp_path / 'outside')
    result = cleanup_runs(root, days=10, execute=True, protected={protected}, now=NOW)
    assert [entry['path'] for entry in result['entries']] == [str(old)]
    for kept in (running, protected, recent, copying, malformed, outside, session / 'setup'):
        assert kept.exists()
    assert (session / 'profile.json').read_bytes() == b'confirmed'
    assert (session / 'confirmation.json').read_bytes() == b'name'


@pytest.mark.parametrize('kind', ['session', 'run', 'diagnose', 'file'])
@pytest.mark.parametrize('linked_parent', [False, True])
def test_cleanup_never_follows_symlinks(tmp_path, kind, linked_parent):
    parent = tmp_path / 'real'
    parent.mkdir()
    root = parent / 'live'
    outside = run_tree(tmp_path / 'outside')
    run = run_tree(root)
    if kind == 'session':
        (root / 'live-20260901T120000Z').symlink_to(outside.parent, target_is_directory=True)
    elif kind == 'run':
        (run.parent / 'run-02').symlink_to(outside, target_is_directory=True)
    else:
        target = run / 'diagnose' if kind == 'diagnose' else run
        (target / 'escape').symlink_to(outside, target_is_directory=True)
    age_tree(run)
    configured = root
    if linked_parent:
        link = tmp_path / 'link'
        link.symlink_to(parent, target_is_directory=True)
        configured = link / 'live'
    cleanup_runs(configured, days=10, execute=True, now=NOW)
    assert (outside / 'records.jsonl').read_bytes() == b'audit'
    if kind in ('diagnose', 'file'):
        assert run.exists()


@pytest.mark.parametrize('days', [0, -1, 1.5, True, '10'])
def test_cleanup_rejects_invalid_age(tmp_path, days):
    with pytest.raises(ValueError, match='Tage'):
        cleanup_runs(tmp_path, days=days, now=NOW)


def test_cleanup_absent_root_does_not_create_it(tmp_path):
    root = tmp_path / 'missing'
    assert cleanup_runs(root, days=1, now=NOW)['entries'] == []
    assert not root.exists()


@pytest.mark.parametrize('kind', ['root', 'parent', 'dotdot'])
def test_cleanup_resolves_configured_root_once(tmp_path, kind):
    # Reviewer probe: lnkroot, lnkparent/live und live/session/.. sind zulaessig.
    root = tmp_path / 'real' / 'live'
    run = run_tree(root)
    if kind == 'dotdot':
        configured = run.parent / '..'
    else:
        link = tmp_path / 'link'
        link.symlink_to(root if kind == 'root' else root.parent, target_is_directory=True)
        configured = link if kind == 'root' else link / 'live'
    result = cleanup_runs(configured, days=10, execute=True, now=NOW)
    assert [entry['path'] for entry in result['entries']] == [str(run)]
    assert not run.exists()


def test_cleanup_diagnostics_then_full_run_ignores_directory_mtimes(tmp_path):
    # Reviewer probe: Diagnose-Loeschung darf das alte Audit nicht wieder verjuengen.
    run = run_tree(tmp_path)
    diagnostics = cleanup_runs(tmp_path, days=10, diagnostics_only=True, execute=True, now=NOW)
    assert diagnostics['entries'][0]['path'] == str(run / 'diagnose')
    assert not (run / 'diagnose').exists()
    assert (run / 'records.jsonl').read_bytes() == b'audit'
    os.utime(run, (NOW.timestamp(), NOW.timestamp()))
    result = cleanup_runs(tmp_path, days=10, execute=True, now=NOW)
    assert [entry['path'] for entry in result['entries']] == [str(run)]
    assert not run.exists()


@pytest.mark.parametrize('diagnostics_only', [False, True])
def test_cleanup_reports_partial_failure_and_continues(tmp_path, monkeypatch, diagnostics_only):
    import shutil

    runs = [run_tree(tmp_path, run=f'run-{i:02}') for i in range(1, 4)]
    targets = [run / 'diagnose' if diagnostics_only else run for run in runs]
    rmtree = shutil.rmtree
    calls = []

    def fail_middle(target):
        calls.append(target)
        if target == targets[1]:
            # Ein Fehler kann auch nach dem Loeschen einzelner Dateien auftreten.
            (target / '001.png' if diagnostics_only else target / 'records.jsonl').unlink()
            raise OSError('Loeschen verweigert')
        rmtree(target)

    monkeypatch.setattr(shutil, 'rmtree', fail_middle)
    result = cleanup_runs(tmp_path, days=10, diagnostics_only=diagnostics_only, execute=True, now=NOW)
    assert calls == targets
    assert [entry['path'] for entry in result['entries']] == [str(p) for p in targets]
    assert [entry['status'] for entry in result['entries']] == ['deleted', 'failed', 'deleted']
    assert result['entries'][1]['error'] == 'Loeschen verweigert'
    assert result['failed'] is True
    assert result['total_bytes'] == sum(entry['bytes'] for entry in result['entries'])
    assert not targets[0].exists() and targets[1].exists() and not targets[2].exists()


@pytest.mark.parametrize('case', ['no_end', 'naive_end', 'recent_end', 'recent_file', 'session_name', 'run_name'])
def test_cleanup_preserves_reviewer_probe_ineligible_runs(tmp_path, case):
    run = run_tree(tmp_path,
                   session='weird-20260901' if case == 'session_name' else 'live-20260901T000000Z',
                   run='run-x1' if case == 'run_name' else 'run-01')
    if case in ('no_end', 'naive_end', 'recent_end'):
        metadata = {} if case == 'no_end' else {
            'ended_at_utc': OLD.replace(tzinfo=None).isoformat() if case == 'naive_end' else NOW.isoformat()}
        (run / 'session.json').write_text(json.dumps(metadata))
        age_tree(run)
    elif case == 'recent_file':
        os.utime(run / 'records.jsonl', (NOW.timestamp(), NOW.timestamp()))
    assert cleanup_runs(tmp_path, days=10, execute=True, now=NOW)['entries'] == []
    assert (run / 'records.jsonl').read_bytes() == b'audit'


@pytest.mark.parametrize('option', ['diagnostics_only', 'execute'])
def test_cleanup_requires_explicit_boolean_options(tmp_path, option):
    run = run_tree(tmp_path)
    with pytest.raises(ValueError, match='boolesch'):
        cleanup_runs(tmp_path, days=10, now=NOW, **{option: 'false'})
    assert run.exists()


def test_cleanup_keeps_runs_at_exact_age_boundary(tmp_path):
    cutoff = NOW - timedelta(days=10)
    run = run_tree(tmp_path, ended=cutoff)
    assert cleanup_runs(tmp_path, days=10, execute=True, now=NOW)['entries'] == []
    assert run.exists()
