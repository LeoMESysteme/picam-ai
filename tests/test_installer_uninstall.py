"""Deinstallation: nur temporäre Layouts und ein Runner, der Befehle aufzeichnet."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packaging'))

from picam_installer import engine, uninstall  # noqa: E402


def recorder(calls, fail=False):
    def run(command, **kwargs):
        calls.append(command)
        if fail:
            raise subprocess.CalledProcessError(1, command, stderr='kaputt')
        return subprocess.CompletedProcess(command, 0, stdout='', stderr='')
    return run


def layout(base: Path, mode='system'):
    """Ein Installationsbild wie nach install + einem Update."""
    if mode == 'portable':
        prefix = base / 'picam'
        data, config, runtime = prefix / 'data', prefix / 'config/config.toml', prefix / 'run'
    else:
        prefix, data, config, runtime = base / 'opt/picam', base / 'var/lib/picam', base / 'etc/picam/config.toml', None
    for release in ('v1', 'v2'):
        venv = prefix / 'releases' / release / '.venv/bin'
        venv.mkdir(parents=True)
        (venv / 'python').write_text('#!fake')
        (venv / 'picam').write_text('#!fake')
    (prefix / 'current').symlink_to(prefix / 'releases/v2')
    (prefix / 'previous').symlink_to(prefix / 'releases/v1')
    for name in ('workbench/tls', 'workbench/bridge', 'live', 'calibration'):
        (data / name).mkdir(parents=True)
    (data / 'workbench/tls/cert.pem').write_text('cert')
    config.parent.mkdir(parents=True)
    config.write_text('[workbench]\ndata = ' + json.dumps(str(data / 'workbench')) + '\n')
    if runtime:
        runtime.mkdir()
    unit = link = None
    if mode != 'portable':
        unit = base / 'etc/systemd/system/picam-werkbank.service'
        unit.parent.mkdir(parents=True)
        unit.write_text(engine.unit_text(python=prefix / 'current/.venv/bin/python', config=config,
                                         user='operator', mode=mode, runtime=Path('/run/picam')))
        link = base / 'usr/local/bin/picam'
        link.parent.mkdir(parents=True)
        link.symlink_to(prefix / 'current/.venv/bin/picam')
    return dict(mode=mode, prefix=prefix, data=data, config=config, unit=unit, link=link,
                runtime=runtime)


@pytest.fixture
def as_root(monkeypatch):
    monkeypatch.setattr(os, 'geteuid', lambda: 0)


def test_plan_is_read_only_and_keeps_data_by_default(tmp_path):
    paths = layout(tmp_path)
    before = sorted(str(p) for p in tmp_path.rglob('*'))
    plan = uninstall.plan_uninstall(**paths)
    assert sorted(str(p) for p in tmp_path.rglob('*')) == before
    assert plan['applied'] is False and plan['needs_root'] is True
    commands = [a['argv'] for a in plan['actions'] if a['kind'] == 'command']
    assert commands == [['systemctl', 'disable', '--now', 'picam-werkbank.service'],
                        ['systemctl', 'daemon-reload']]
    assert set(plan['remove']) == {str(paths['unit']), str(paths['link']), str(paths['prefix'] / 'current'),
                                   str(paths['prefix'] / 'previous'), str(paths['prefix'] / 'releases')}
    kept = {item['path'] for item in plan['keep']}
    assert str(paths['data']) in kept and str(paths['config'].parent) in kept
    json.dumps(plan)  # JSON-fähig für die Verwaltungskonsole


def test_apply_runs_service_commands_and_removes_only_code(tmp_path, as_root):
    paths = layout(tmp_path)
    calls = []
    result = uninstall.apply_uninstall(uninstall.plan_uninstall(**paths), runner=recorder(calls))
    assert result['applied'] is True
    assert calls == [['systemctl', 'disable', '--now', 'picam-werkbank.service'], ['systemctl', 'daemon-reload']]
    assert not paths['prefix'].exists()
    assert not paths['unit'].exists() and not paths['link'].is_symlink()
    assert (paths['data'] / 'workbench/tls/cert.pem').read_text() == 'cert'
    assert paths['config'].is_file()


def test_purge_lists_and_removes_exactly_data_and_config(tmp_path, as_root):
    paths = layout(tmp_path)
    neighbour = tmp_path / 'etc/other.conf'
    neighbour.write_text('x')
    plan = uninstall.plan_uninstall(**paths, purge_data=True)
    assert str(paths['data']) in plan['remove'] and str(paths['config'].parent) in plan['remove']
    assert any('neu gekoppelt' in note for note in plan['notes'])
    uninstall.apply_uninstall(plan, runner=recorder([]))
    assert not paths['data'].exists() and not paths['config'].parent.exists()
    assert neighbour.read_text() == 'x'
    assert (tmp_path / 'var/lib').is_dir() and (tmp_path / 'etc/systemd/system').is_dir()


def test_user_mode_uses_user_bus_without_root(tmp_path):
    paths = layout(tmp_path, mode='user')
    calls = []
    uninstall.apply_uninstall(uninstall.plan_uninstall(**paths), runner=recorder(calls))
    assert calls == [['systemctl', '--user', 'disable', '--now', 'picam-werkbank.service'],
                     ['systemctl', '--user', 'daemon-reload']]


def test_system_apply_requires_root(tmp_path, monkeypatch):
    paths = layout(tmp_path)
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    calls = []
    with pytest.raises(ValueError, match='root'):
        uninstall.apply_uninstall(uninstall.plan_uninstall(**paths), runner=recorder(calls))
    assert calls == [] and paths['prefix'].exists()


def test_portable_has_no_unit_and_keeps_data_inside_prefix(tmp_path):
    paths = layout(tmp_path, mode='portable')
    calls = []
    plan = uninstall.plan_uninstall(**paths)
    assert plan['unit'] is None and not any(a['kind'] == 'command' for a in plan['actions'])
    uninstall.apply_uninstall(plan, runner=recorder(calls))
    assert calls == []
    prefix = paths['prefix']
    assert sorted(p.name for p in prefix.iterdir()) == ['config', 'data', 'run']
    assert any(item['path'] == str(prefix) for item in plan['keep'])


def test_portable_purge_removes_prefix_completely(tmp_path):
    paths = layout(tmp_path, mode='portable')
    uninstall.apply_uninstall(uninstall.plan_uninstall(**paths, purge_data=True), runner=recorder([]))
    assert not paths['prefix'].exists() and tmp_path.is_dir()


def test_portable_rejects_unit(tmp_path):
    paths = layout(tmp_path, mode='portable')
    with pytest.raises(ValueError, match='keinen Dienst'):
        uninstall.plan_uninstall(**dict(paths, unit=tmp_path / 'picam-werkbank.service'))


def test_unrecognised_prefix_is_refused(tmp_path):
    paths = layout(tmp_path)
    other = tmp_path / 'somewhere'
    other.mkdir()
    with pytest.raises(ValueError, match='keine picam-Installation'):
        uninstall.plan_uninstall(**dict(paths, prefix=other))


def test_symlinked_prefix_is_refused(tmp_path):
    paths = layout(tmp_path)
    alias = tmp_path / 'alias'
    alias.symlink_to(paths['prefix'])
    with pytest.raises(ValueError, match='Symlink'):
        uninstall.plan_uninstall(**dict(paths, prefix=alias))


def test_symlinked_releases_is_refused(tmp_path):
    paths = layout(tmp_path)
    prefix = paths['prefix']
    real = tmp_path / 'elsewhere'
    (prefix / 'releases').rename(real)
    (prefix / 'releases').symlink_to(real)
    (prefix / 'current').unlink()
    (prefix / 'current').symlink_to(prefix / 'releases/v2')
    with pytest.raises(ValueError):
        uninstall.plan_uninstall(**paths)


def test_foreign_unit_and_foreign_link_are_not_touched(tmp_path, as_root):
    paths = layout(tmp_path)
    paths['unit'].write_text('[Service]\nExecStart=/usr/bin/other serve\n')
    with pytest.raises(ValueError, match='startet nicht'):
        uninstall.plan_uninstall(**paths)
    paths = layout(tmp_path / 'b')
    paths['link'].unlink()
    paths['link'].symlink_to('/usr/bin/true')
    plan = uninstall.plan_uninstall(**paths)
    assert str(paths['link']) not in plan['remove']
    uninstall.apply_uninstall(plan, runner=recorder([]))
    assert paths['link'].is_symlink()


def test_data_without_workbench_or_containing_home_is_refused(tmp_path):
    paths = layout(tmp_path)
    plain = tmp_path / 'plain'
    plain.mkdir()
    with pytest.raises(ValueError, match='kein picam-Datenordner'):
        uninstall.plan_uninstall(**dict(paths, data=plain))
    home = Path.home()
    if len(home.parts) >= 3:
        with pytest.raises(ValueError, match='Benutzerverzeichnis'):
            uninstall.plan_uninstall(**dict(paths, data=home))


def test_purge_refuses_when_config_names_other_data(tmp_path):
    paths = layout(tmp_path)
    paths['config'].write_text('[workbench]\ndata = "/srv/anders/workbench"\n')
    plan = uninstall.plan_uninstall(**paths)
    assert any('/srv/anders' in note for note in plan['notes'])
    with pytest.raises(ValueError, match='nichts geplant'):
        uninstall.plan_uninstall(**paths, purge_data=True)


def test_apply_refuses_changed_installation(tmp_path, as_root):
    paths = layout(tmp_path)
    plan = uninstall.plan_uninstall(**paths)
    (paths['prefix'] / 'previous').unlink()
    calls = []
    with pytest.raises(ValueError, match='geändert'):
        uninstall.apply_uninstall(plan, runner=recorder(calls))
    assert calls == []


def test_tampered_plan_cannot_widen_deletion(tmp_path, as_root):
    paths = layout(tmp_path)
    plan = uninstall.plan_uninstall(**paths)
    plan['actions'].append({'kind': 'rmtree', 'path': str(tmp_path), 'text': 'alles'})
    with pytest.raises(ValueError, match='geändert'):
        uninstall.apply_uninstall(plan, runner=recorder([]))
    assert paths['prefix'].exists()


def test_failed_service_stop_deletes_nothing(tmp_path, as_root):
    paths = layout(tmp_path)
    with pytest.raises(ValueError, match='fehlgeschlagen'):
        uninstall.apply_uninstall(uninstall.plan_uninstall(**paths), runner=recorder([], fail=True))
    assert paths['unit'].is_file() and (paths['prefix'] / 'releases/v2').is_dir()


def test_cli_route_prints_json_plan_without_changes(tmp_path, capsys):
    paths = layout(tmp_path, mode='portable')
    code = engine.main(['--uninstall', '--mode', 'portable', '--prefix', str(paths['prefix']), '--json'])
    assert code == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan['applied'] is False and plan['prefix'] == str(paths['prefix'])
    assert (paths['prefix'] / 'releases/v2').is_dir()


def test_cli_apply_portable(tmp_path, capsys):
    paths = layout(tmp_path, mode='portable')
    code = engine.main(['--uninstall', '--mode', 'portable', '--prefix', str(paths['prefix']),
                        '--purge-data', '--apply'])
    assert code == 0
    assert not paths['prefix'].exists()


def test_cli_error_is_reported_without_traceback(tmp_path, capsys):
    code = engine.main(['--uninstall', '--mode', 'portable', '--prefix', str(tmp_path / 'fehlt')])
    assert code == 1
    assert 'picam installer:' in capsys.readouterr().err


def test_console_and_json_share_the_read_only_uninstall_plan(tmp_path, capsys):
    from dispread.admin import uninstall as admin_uninstall
    from dispread.admin.instance import Instance

    paths = layout(tmp_path)
    (paths['prefix'] / 'fremd').write_text('bleibt')
    instance = Instance('system', paths['unit'].name, 'system',
                        root=str(paths['prefix'] / 'releases/v2'), config=str(paths['config']),
                        data=str(paths['data'] / 'workbench'))
    before = sorted(tmp_path.rglob('*'))
    plan = admin_uninstall.plan_uninstall(instance, unit_dir=paths['unit'].parent, link=paths['link'])
    assert engine.main(['--uninstall', '--json', '--prefix', str(paths['prefix']), '--data', str(paths['data']),
                        '--config', str(paths['config']), '--unit-dir', str(paths['unit'].parent),
                        '--link', str(paths['link'])]) == 0
    assert json.loads(capsys.readouterr().out) == plan
    assert plan['stop_service'] and plan['needs_root']
    assert str(paths['unit']) in plan['remove']
    assert str(paths['data']) in {item['path'] for item in plan['keep']}
    assert str(paths['prefix']) in {item['path'] for item in plan['keep']}
    assert sorted(tmp_path.rglob('*')) == before
