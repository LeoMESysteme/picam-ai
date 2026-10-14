"""MEM-6: Bereinigung ausschließlich in künstlichen Homes und tmp-Bäumen."""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[1] / 'scripts/pi-housekeeping.py'
spec = importlib.util.spec_from_file_location('pi_housekeeping', SCRIPT)
hk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hk)


@pytest.fixture
def env(tmp_path):
    home, repo, tmp, proc = [tmp_path / name for name in ('home', 'repo', 'tmp', 'proc')]
    for path in (home, repo, tmp, proc):
        path.mkdir()
    return SimpleNamespace(home=home, repo=repo, tmp=tmp, proc=proc, user='tester')


def directory(path, *, old=False):
    path.mkdir(parents=True)
    (path / 'payload').write_text('keep or delete')
    if old:
        for entry in (path / 'payload', path):
            os.utime(entry, (time.time() - 7200, time.time() - 7200))
    return path


def run(env, **kwargs):
    return hk.cleanup(env.home, env.repo, env.tmp, env.user, env.proc,
                      clean=kwargs.pop('clean', True), dry_run=kwargs.pop('dry_run', False), **kwargs)


def process(env, *args, exe=None, cwd=None):
    entry = env.proc / str(len(list(env.proc.iterdir())) + 100)
    entry.mkdir()
    (entry / 'cmdline').write_bytes(('\0'.join(map(str, args)) + '\0').encode())
    (entry / 'exe').symlink_to(exe or '/usr/bin/node')
    (entry / 'cwd').symlink_to(cwd or env.home)
    return entry


def test_only_allowlist_is_deleted(env):
    allowed = [env.home / '.npm/_cacache', env.home / '.npm/_npx/old',
               env.home / '.vscode-server/cli/servers/Stable-old',
               env.home / '.codex/packages/standalone/releases/old',
               env.home / '.codex/packages/app-server-daemon/releases/old',
               env.home / '.codex/.tmp/git-old', env.repo / 'playwright-report',
               env.tmp / 'pytest-of-tester/pytest-1']
    protected = [env.repo / 'var/data', env.home / 'var-backups/data',
                 env.home / '.codex/.tmp/marketplaces', env.home / '.codex/.tmp/plugins',
                 env.home / '.codex/.tmp/bundled-marketplaces', env.home / '.codex/sessions',
                 env.home / '.cache/ms-playwright', env.tmp / 'claude-old', env.tmp / 'picam-ai-n5-old',
                 env.home / 'unlisted', env.tmp / 'pytest-of-someone-else/pytest-1']
    for path in allowed + protected:
        directory(path, old=True)
    result = run(env)
    assert {item['path'] for item in result if item['action'] == 'deleted'} == set(map(str, allowed))
    assert all(not path.exists() for path in allowed)
    assert all((path / 'payload').exists() for path in protected)


@pytest.mark.parametrize('dry_run,clean,action', [(True, True, 'would_delete'),
                                                (True, False, 'would_delete'), (False, False, 'eligible')])
def test_preview_does_not_mutate(env, dry_run, clean, action):
    path = directory(env.home / '.npm/_cacache')
    result = run(env, dry_run=dry_run, clean=clean)
    assert result[0]['action'] == action
    assert result[0]['bytes'] > 0
    assert path.exists()


def test_youngest_mtime_and_current(env):
    base = env.tmp / 'pytest-of-tester'
    current = directory(base / 'pytest-1', old=True)
    young = directory(base / 'pytest-2')
    nested = directory(base / 'pytest-3', old=True)
    directory(nested / 'nested')
    (base / 'pytest-current').symlink_to(current.name)
    git_young = directory(env.home / '.codex/.tmp/git-young')
    result = run(env)
    assert len(result) == 4
    assert all(item['action'] == 'skipped' for item in result)
    assert all(path.exists() for path in (current, young, nested, git_young))
    assert (base / 'pytest-current').is_symlink()


@pytest.mark.parametrize('package', ['standalone', 'app-server-daemon'])
@pytest.mark.parametrize('inside_releases', [False, True])
def test_codex_current_and_running_release(env, package, inside_releases):
    root = env.home / '.codex/packages' / package
    current = directory(root / 'releases/current-version')
    running = directory(root / 'releases/running-version')
    unused = directory(root / 'releases/unused-version')
    ((root / 'releases' if inside_releases else root) / 'current').symlink_to(current)
    process(env, 'daemon', exe=running / 'binary')
    run(env)
    assert current.exists() and running.exists()
    assert not unused.exists()


@pytest.mark.parametrize('reference', ['exe', 'cmdline', 'cwd'])
def test_running_versions_and_npx_are_preserved(env, reference):
    for path in (env.home / '.vscode-server/cli/servers/Stable-live', env.home / '.npm/_npx/live'):
        directory(path)
        process(env, str(path / 'script') if reference == 'cmdline' else 'node',
                exe=path / 'bin/node' if reference == 'exe' else None,
                cwd=path if reference == 'cwd' else None)
    result = run(env)
    assert all(item['action'] == 'skipped' for item in result)


def test_path_prefix_does_not_protect_other_version(env):
    unused = directory(env.home / '.npm/_npx/abc')
    process(env, str(env.home / '.npm/_npx/abcdef/bin/node'))
    run(env)
    assert not unused.exists()


def test_relative_process_argument_is_resolved_against_cwd(env):
    live = directory(env.home / '.npm/_npx/live')
    process(env, 'node', './live/script.js', cwd=live.parent)
    run(env)
    assert live.exists()


def test_pytest_process_blocks_only_pytest_category(env):
    old = directory(env.tmp / 'pytest-of-tester/pytest-1', old=True)
    cache = directory(env.home / '.npm/_cacache')
    process(env, '/usr/bin/python', '-m', 'pytest')
    run(env)
    assert old.exists()
    assert not cache.exists()


def test_incomplete_process_scan_preserves_process_dependent_entries(env):
    live = directory(env.home / '.npm/_npx/unknown')
    process(env, 'node').joinpath('exe').unlink()
    result = run(env)
    assert live.exists()
    assert result[0]['reason'] == 'Prozessprüfung unvollständig'


@pytest.mark.parametrize('own_process', [False, True])
@pytest.mark.parametrize('unreadable', ['exe', 'cwd'])
def test_process_link_permission_does_not_block_cleanup(env, monkeypatch, own_process, unreadable):
    unused = directory(env.home / '.vscode-server/cli/servers/Stable-unused')
    entry = process(env, 'node')
    monkeypatch.setattr(hk, 'process_uid', lambda path: os.getuid() + (not own_process))
    original = hk.os.readlink
    denied = []

    def readlink(path, *args, **kwargs):
        if Path(path) == entry / unreadable:
            denied.append(path)
            raise PermissionError('foreign or unreadable process')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(hk.os, 'readlink', readlink)
    result = run(env)
    assert not unused.exists()
    assert denied
    assert result[0]['action'] == 'deleted'


@pytest.mark.parametrize('own_process', [False, True])
@pytest.mark.parametrize('unreadable', ['exe', 'cwd'])
def test_process_cmdline_protects_candidate_when_links_denied(env, monkeypatch, own_process, unreadable):
    live = directory(env.home / '.npm/_npx/live')
    unused = directory(env.home / '.npm/_npx/unused')
    entry = process(env, 'node', str(live / 'script.js'))
    monkeypatch.setattr(hk, 'process_uid', lambda path: os.getuid() + (not own_process))
    original = hk.os.readlink

    def readlink(path, *args, **kwargs):
        if Path(path) == entry / unreadable:
            raise PermissionError('non-dumpable process')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(hk.os, 'readlink', readlink)
    result = run(env)
    assert live.exists()
    assert not unused.exists()
    assert result[0]['reason'] == 'Von laufendem Prozess benutzt'


@pytest.mark.parametrize('own_process', [False, True])
@pytest.mark.parametrize('unreadable', ['exe', 'cwd'])
@pytest.mark.parametrize('error', [OSError, FileNotFoundError])
def test_other_link_errors_still_block_cleanup(env, monkeypatch, own_process, unreadable, error):
    unused = directory(env.home / '.npm/_npx/unused')
    entry = process(env, 'node')
    monkeypatch.setattr(hk, 'process_uid', lambda path: os.getuid() + (not own_process))
    original = hk.os.readlink

    def readlink(path, *args, **kwargs):
        if Path(path) == entry / unreadable:
            raise error('unreadable link on existing process')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(hk.os, 'readlink', readlink)
    result = run(env)
    assert unused.exists()
    assert result[0]['reason'] == 'Prozessprüfung unvollständig'


def test_unreadable_process_stat_still_blocks_cleanup(env, monkeypatch):
    unused = directory(env.home / '.npm/_npx/unused')
    process(env, 'node')

    def denied_stat(path):
        raise PermissionError('unreadable stat')

    monkeypatch.setattr(hk, 'process_uid', denied_stat)
    result = run(env)
    assert unused.exists()
    assert result[0]['reason'] == 'Prozessprüfung unvollständig'


@pytest.mark.parametrize('own_process', [False, True])
def test_unreadable_cmdline_still_blocks_cleanup(env, monkeypatch, own_process):
    unused = directory(env.home / '.npm/_npx/unused')
    entry = process(env, 'node')
    monkeypatch.setattr(hk, 'process_uid', lambda path: os.getuid() + (not own_process))
    original = Path.read_bytes

    def read_bytes(path):
        if path == entry / 'cmdline':
            raise PermissionError('unreadable cmdline')
        return original(path)

    monkeypatch.setattr(Path, 'read_bytes', read_bytes)
    result = run(env)
    assert unused.exists()
    assert result[0]['reason'] == 'Prozessprüfung unvollständig'


def test_paperclipai_nested_and_symlink_are_preserved(env):
    named = directory(env.home / '.npm/_npx/paperclipai-something')
    nested = directory(env.home / '.npm/_npx/hash/node_modules/paperclipai')
    linked = directory(env.home / '.npm/_npx/linked/node_modules')
    (linked / 'paperclipai').symlink_to(env.home / 'outside')
    run(env)
    assert named.exists() and nested.exists() and linked.exists()


def test_paperclipai_package_alias_and_symlink_target_are_preserved(env):
    alias = directory(env.home / '.npm/_npx/alias/node_modules/alias')
    (alias / 'package.json').write_text('{"name": "paperclipai"}')
    linked = directory(env.home / '.npm/_npx/linked')
    (linked / 'alias').symlink_to(env.home / 'paperclipai')
    run(env)
    assert alias.exists() and linked.exists()


def test_age_boundary_is_strict(env):
    path = directory(env.home / '.codex/.tmp/git-old', old=True)
    newest = hk.tree_info(path)[1]
    result = run(env, dry_run=True, now=newest + 3600)
    assert result[0]['action'] == 'skipped'
    result = run(env, dry_run=True, now=newest + 3601)
    assert result[0]['action'] == 'would_delete'


def test_symlink_ancestor_and_candidate_never_followed(env):
    outside = directory(env.home / 'outside', old=True)
    (env.home / '.npm').symlink_to(outside)
    directory(outside / '_cacache')
    directory(env.home / '.codex/.tmp')
    (env.home / '.codex/.tmp/git-link').symlink_to(outside)
    run(env)
    assert outside.joinpath('_cacache/payload').exists()
    assert env.home.joinpath('.codex/.tmp/git-link').is_symlink()


def test_nested_symlink_does_not_delete_target(env):
    target = directory(env.repo / 'var/precious')
    cache = directory(env.home / '.npm/_cacache')
    (cache / 'link').symlink_to(target)
    run(env)
    assert not cache.exists()
    assert target.joinpath('payload').exists()


@pytest.mark.parametrize('dry_run', [True, False])
def test_recording_blocks_every_candidate(env, dry_run):
    cache = directory(env.home / '.npm/_cacache')
    (env.repo / 'var').mkdir()
    (env.repo / 'var/RECORDING_IN_PROGRESS').touch()
    result = run(env, dry_run=dry_run)
    assert cache.exists()
    assert result[0]['action'] == 'skipped'
    assert 'RECORDING_IN_PROGRESS' in result[0]['reason']


def test_recording_rechecked_before_deletion(env, monkeypatch):
    cache = directory(env.home / '.npm/_cacache')
    original = hk.process_snapshot
    calls = 0

    def snapshot(proc):
        nonlocal calls
        calls += 1
        if calls == 2:
            (env.repo / 'var').mkdir()
            (env.repo / 'var/RECORDING_IN_PROGRESS').touch()
        return original(proc)

    monkeypatch.setattr(hk, 'process_snapshot', snapshot)
    run(env)
    assert cache.exists()


def test_protected_overlap_blocks_misconfigured_repo(env):
    directory(env.home / '.npm/_cacache/var')
    env.repo = env.home / '.npm/_cacache'
    result = run(env)
    assert result[0]['reason'] == 'Geschützter Datenpfad'
    assert env.repo.exists()


def test_mountpoint_skipped(env, monkeypatch):
    cache = directory(env.home / '.npm/_cacache')
    original = Path.is_mount
    monkeypatch.setattr(Path, 'is_mount', lambda path: path == cache or original(path))
    result = run(env)
    assert result[0]['action'] == 'skipped'
    assert cache.exists()


def test_delete_error_is_reported(env, monkeypatch):
    directory(env.home / '.npm/_cacache')

    def fail(*args):
        raise PermissionError('denied')

    monkeypatch.setattr(hk.shutil, 'rmtree', fail)
    fail.avoids_symlink_attacks = True
    assert run(env)[0]['action'] == 'error'


@pytest.mark.parametrize('free,percent,count', [(5 * hk.GB, 50, 0), (5 * hk.GB - 1, 50.1, 2)])
def test_report_thresholds_and_protected_sizes(env, monkeypatch, free, percent, count):
    env.proc.joinpath('meminfo').write_text('MemTotal: 100 kB\nMemAvailable: 40 kB\nSwapTotal: 20 kB\nSwapFree: 5 kB\n')
    env.proc.joinpath('mounts').write_text(f'tmpfs {env.tmp} tmpfs rw 0 0\n')
    directory(env.repo / 'var/keep')
    monkeypatch.setattr(hk, 'disk', lambda path: {'free_bytes': free, 'used_percent': percent})
    data = hk.report(env.home, env.repo, env.tmp, env.proc)
    assert len(data['warnings']) == count
    assert data['ram']['used_bytes'] == 60 * 1024
    assert data['swap']['used_bytes'] == 15 * 1024
    assert data['tmp']['filesystem'] == 'tmpfs'
    assert data['largest_var'][0]['bytes'] > 0
    data['cleanup'] = []
    assert 'Karte (/)' in hk.render_text(data)
    json.dumps(data)


def test_cli_warnings_success_and_cleanup_errors_failure(env, monkeypatch, capsys):
    monkeypatch.setattr(hk, 'report', lambda *args: {'warnings': ['low disk']})
    monkeypatch.setattr(hk, 'cleanup', lambda *args, **kwargs: [])
    assert hk.main(['--json', '--home', str(env.home), '--repo', str(env.repo)]) == 0
    assert json.loads(capsys.readouterr().out)['warnings'] == ['low disk']
    monkeypatch.setattr(hk, 'cleanup', lambda *args, **kwargs: [{'action': 'error', 'reason': 'denied'}])
    assert hk.main(['--json', '--home', str(env.home)]) == 1
