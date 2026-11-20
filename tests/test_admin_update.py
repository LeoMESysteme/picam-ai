"""picam update: vorbereiten, umschalten, Rückweg (ohne echten Dienst)."""
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packaging'))
from picam_installer import update as inst_update  # noqa: E402

from dispread.admin import cli, probes  # noqa: E402
from dispread.admin import update as admin_update  # noqa: E402
from dispread.admin.instance import Instance  # noqa: E402


def make_release(prefix: Path, name: str) -> Path:
    release = prefix / 'releases' / name
    (release / '.venv/bin').mkdir(parents=True)
    (release / '.venv/bin/python').write_text('')
    (release / 'release.json').write_text(f'{{"release_id": "{name}"}}')
    return release


@pytest.fixture
def prefix(tmp_path):
    root = tmp_path / 'opt-picam'
    make_release(root, '1.0.0')
    (root / 'current').symlink_to(root / 'releases/1.0.0')
    return root


def test_activate_swaps_current_and_remembers_previous(prefix):
    make_release(prefix, '1.1.0')
    assert inst_update.activate(prefix, '1.1.0') == {'current': '1.1.0', 'previous': '1.0.0'}
    state = inst_update.releases(prefix)
    assert (state['current'], state['previous']) == ('1.1.0', '1.0.0')
    assert not (prefix / 'current.neu').exists()
    inst_update.activate(prefix, '1.0.0')
    assert inst_update.releases(prefix)['current'] == '1.0.0'


def test_activate_refuses_incomplete_or_active(prefix):
    (prefix / 'releases/halb').mkdir()
    with pytest.raises(ValueError, match='nicht vollständig'):
        inst_update.activate(prefix, 'halb')
    with pytest.raises(ValueError, match='bereits aktiv'):
        inst_update.activate(prefix, '1.0.0')


def test_remove_keeps_active_and_previous(prefix):
    make_release(prefix, '1.1.0')
    make_release(prefix, '0.9.0')
    inst_update.activate(prefix, '1.1.0')
    for name in ('1.1.0', '1.0.0'):
        with pytest.raises(ValueError):
            inst_update.remove(prefix, name)
    inst_update.remove(prefix, '0.9.0')
    assert inst_update.releases(prefix)['installed'] == ['1.0.0', '1.1.0']


def test_plan_refuses_same_or_existing_version(prefix, monkeypatch):
    bundle = SimpleNamespace(release_id='1.0.0')
    monkeypatch.setattr(inst_update, 'load_source', lambda source, sha=None: bundle)
    with pytest.raises(ValueError, match='bereits aktiv'):
        inst_update.plan_update(prefix, 'x.tar.gz')
    make_release(prefix, '1.1.0')
    bundle.release_id = '1.1.0'
    with pytest.raises(ValueError, match='--activate 1.1.0'):
        inst_update.plan_update(prefix, 'x.tar.gz')


def test_prepare_failure_leaves_nothing(prefix, monkeypatch):
    monkeypatch.setattr(inst_update, 'load_source', lambda source, sha=None: SimpleNamespace(release_id='2.0.0'))
    monkeypatch.setattr(inst_update, 'probe_system', lambda python, runner=None: SimpleNamespace(missing_modules=()))

    def broken(bundle, target, info, runner, progress):
        target.mkdir()
        raise ValueError('Selbsttest fehlgeschlagen')
    monkeypatch.setattr(inst_update, 'prepare_release', broken)
    with pytest.raises(ValueError, match='Selbsttest'):
        inst_update.prepare(prefix, 'x.tar.gz')
    assert not (prefix / 'releases/2.0.0').exists()
    assert inst_update.releases(prefix)['current'] == '1.0.0'


def installed(prefix: Path) -> Instance:
    return Instance(kind='system', unit='picam-werkbank.service', scope='system',
                    root=str(prefix / 'releases/1.0.0'), host='127.0.0.1', port=1)


def snapshot_collect(live):
    def collect(instance, include_setup=True, **_):
        facts = {'dienst': probes.Fact('dienst', 'Dienst', probes.OK, 'läuft')}
        return probes.Snapshot(instance, facts, live, time.time())
    return collect


@pytest.fixture
def admin(prefix, monkeypatch):
    monkeypatch.setattr(admin_update, 'installer_module', lambda instance, name: inst_update)
    make_release(prefix, '1.1.0')
    return installed(prefix)


def test_switch_rolls_back_when_new_version_does_not_answer(prefix, admin, monkeypatch):
    answers = iter([False, True])  # neue Version antwortet nicht, alte wieder
    monkeypatch.setattr(admin_update, '_restart_and_wait', lambda instance, echo: next(answers))
    ok, message = admin_update.switch(admin, '1.1.0', echo=lambda _: None,
                                      collect=snapshot_collect({'state': 'idle', 'diagnose_kopie': False}))
    assert not ok and '1.0.0 läuft wieder' in message
    assert inst_update.releases(prefix)['current'] == '1.0.0'


def test_switch_refused_during_run(prefix, admin, monkeypatch):
    monkeypatch.setattr(admin_update, '_restart_and_wait', lambda *a: pytest.fail('kein Neustart im Lauf'))
    ok, message = admin_update.switch(admin, '1.1.0', echo=lambda _: None,
                                      collect=snapshot_collect({'state': 'running', 'diagnose_kopie': False}))
    assert not ok and 'gesperrt' in message
    assert inst_update.releases(prefix)['current'] == '1.0.0'


def test_successful_switch(prefix, admin, monkeypatch):
    monkeypatch.setattr(admin_update, '_restart_and_wait', lambda instance, echo: True)
    ok, _ = admin_update.switch(admin, '1.1.0', echo=lambda _: None,
                                collect=snapshot_collect({'state': 'idle', 'diagnose_kopie': False}))
    assert ok and inst_update.releases(prefix)['current'] == '1.1.0'


def test_update_only_for_installed_instances(monkeypatch, capsys):
    dev = Instance(kind='dev', unit='u', scope='user', root='/r')
    monkeypatch.setattr(cli, 'discover', lambda *_: dev)
    assert cli.main(['update', '--check']) == cli.EXIT_FAIL
    assert 'git pull' in capsys.readouterr().err


def test_cli_check_lists_versions(prefix, admin, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'discover', lambda *_: admin)
    assert cli.main(['update', '--check']) == 0
    out = capsys.readouterr().out
    assert 'aktiv:      1.0.0' in out and '1.1.0' in out


def test_cli_system_update_hands_over_to_sudo(prefix, admin, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, 'discover', lambda *_: admin)
    monkeypatch.setattr(admin_update.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(cli.subprocess, 'call', lambda command: calls.append(command) or 0)
    archive = tmp_path / 'picam-1.2.0.tar.gz'
    assert cli.main(['update', '--source', str(archive), '--yes']) == 0
    assert calls[0][0] == 'sudo' and calls[0][-4:] == ['update', '--source', str(archive), '--yes']


@pytest.mark.parametrize('name', ['../x', '..', '', 'a/b', '.'])
def test_activate_rejects_paths_outside_releases(prefix, name):
    with pytest.raises(ValueError):
        inst_update.activate(prefix, name)


def test_activate_rejects_symlinked_release(prefix, tmp_path):
    outside = make_release(tmp_path / 'fremd', 'x')
    (prefix / 'releases/link').symlink_to(outside)
    with pytest.raises(ValueError, match='nicht direkt'):
        inst_update.activate(prefix, 'link')
