"""Optionale Komponente me-fastfetch: nur temporäre Homes und aufzeichnende Runner."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packaging'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from picam_installer import engine, fastfetch, uninstall  # noqa: E402
from test_installer import bundle, fake_runner, fixture_template_hash, healthy  # noqa: E402,F401
from test_installer_uninstall import layout  # noqa: E402


@pytest.fixture
def home(tmp_path):
    path = tmp_path / 'home' / 'labor'
    path.mkdir(parents=True)
    (path / '.bashrc').write_text('# eigene Einstellungen\nexport PATH="$HOME/.local/bin:$PATH"\n')
    return path


def files():
    return fastfetch.sources()


def recorder(calls):
    def run(command, **_):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout='', stderr='')
    return run


def install(home, calls=None, **options):
    return fastfetch.apply(home, files(), uid=os.getuid(), gid=os.getgid(),
                           runner=recorder(calls if calls is not None else []), **options)


def test_sources_come_from_repo_and_cover_all_targets():
    found = files()
    assert set(found) == {name for name, _, _ in fastfetch.TARGETS}
    assert b'@ME_LOGO@' in found['me-fastfetch.in'] and b'/usr/bin/python3' in found['me-fastfetch.in']
    assert b'me-logo.txt' in found['config.jsonc']


def test_bundle_files_win_over_local_copy():
    bundled = {f'{fastfetch.SOURCE_DIR}/me-logo.txt': b'aus dem Release'}
    assert fastfetch.sources(bundled)['me-logo.txt'] == b'aus dem Release'


def test_plan_is_read_only(home):
    before = sorted(str(p) for p in home.rglob('*'))
    plan = fastfetch.plan(home, files(), package_present=False, can_install_package=True)
    assert {entry['state'] for entry in plan['files']} == {'neu'}
    assert plan['bashrc']['state'] == 'fehlt' and plan['package'] == 'installieren'
    assert sorted(str(p) for p in home.rglob('*')) == before


def test_apply_installs_files_block_and_manifest(home):
    result = install(home)
    assert result['applied'] and result['package_installed'] is False
    wrapper = home / '.local/bin/me-fastfetch'
    assert wrapper.stat().st_mode & 0o777 == 0o755
    script = shlex.quote(str(home / '.local/share/me-fastfetch/me-logo.py'))
    assert f'exec /usr/bin/python3 {script} --fastfetch "$@"' in wrapper.read_text()
    assert (home / '.config/fastfetch/config.jsonc').read_bytes() == files()['config.jsonc']
    assert (home / '.local/share/me-fastfetch/me-logo.py').read_bytes() == files()['me-logo.py']
    text = (home / '.bashrc').read_text()
    assert text.startswith('# eigene Einstellungen\n') and text.count(fastfetch.BEGIN) == 1
    assert '$SSH_CONNECTION' in text and '[ -t 1 ]' in text and 'fastfetch\n' in text
    backups = list(home.glob('.bashrc.vor-me-fastfetch-*'))
    assert len(backups) == 1 and fastfetch.BEGIN not in backups[0].read_text()
    manifest = json.loads((home / fastfetch.MANIFEST).read_text())
    assert set(manifest['files']) == {str(home / rel) for _, rel, _ in fastfetch.TARGETS}


def test_block_is_valid_bash(home):
    install(home)
    subprocess.run(['bash', '-n', str(home / '.bashrc')], check=True)


def test_repeat_is_idempotent(home):
    install(home)
    bashrc = (home / '.bashrc').read_text()
    result = install(home)
    assert result['written'] == [] and result['backups'] == []
    assert (home / '.bashrc').read_text() == bashrc
    assert len(list(home.glob('.bashrc.vor-*'))) == 1


def test_different_config_is_backed_up_not_overwritten_silently(home):
    config = home / '.config/fastfetch/config.jsonc'
    config.parent.mkdir(parents=True)
    config.write_text('{"eigene": true}\n')
    plan = fastfetch.plan(home, files(), package_present=True, can_install_package=False)
    assert {e['path']: e['state'] for e in plan['files']}[str(config)] == 'sichern'
    result = install(home)
    backup = [Path(p) for p in result['backups'] if 'config.jsonc' in p]
    assert len(backup) == 1 and backup[0].read_text() == '{"eigene": true}\n'
    assert config.read_bytes() == files()['config.jsonc']


def test_identical_existing_file_is_not_claimed(home):
    logo = home / '.config/fastfetch/me-logo.txt'
    logo.parent.mkdir(parents=True)
    logo.write_bytes(files()['me-logo.txt'])
    install(home)
    manifest = json.loads((home / fastfetch.MANIFEST).read_text())
    assert str(logo) not in manifest['files']


def test_foreign_fastfetch_call_in_bashrc_is_left_alone(home):
    original = (home / '.bashrc').read_text() + 'fastfetch\n'
    (home / '.bashrc').write_text(original)
    plan = fastfetch.plan(home, files(), package_present=True, can_install_package=False)
    assert plan['bashrc']['state'] == 'fremd' and plan['notes']
    install(home)
    assert (home / '.bashrc').read_text() == original
    assert not list(home.glob('.bashrc.vor-*'))


def test_stale_block_is_replaced_in_place(home):
    old = fastfetch.BLOCK.replace('fastfetch\n    fi', 'fastfetch --alt\n    fi')
    (home / '.bashrc').write_text('vorher\n\n' + old + 'nachher\n')
    install(home)
    text = (home / '.bashrc').read_text()
    assert text == 'vorher\n\n' + fastfetch.BLOCK + 'nachher\n'


def test_symlink_in_target_is_refused(home, tmp_path):
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    (home / '.config').symlink_to(elsewhere)
    with pytest.raises(ValueError, match='Symlink'):
        fastfetch.plan(home, files(), package_present=True, can_install_package=False)
    with pytest.raises(ValueError, match='Symlink'):
        install(home)
    assert list(elsewhere.iterdir()) == []


def test_apt_only_when_requested(home):
    calls = []
    install(home, calls)
    assert calls == []
    install(home, calls, install_package=True)
    assert calls == [['apt-get', 'install', '-y', '--', 'fastfetch']]
    assert json.loads((home / fastfetch.MANIFEST).read_text())['package_installed_by_picam'] is True


def test_block_roundtrip_restores_text():
    text = 'a\nb\n'
    assert fastfetch.without_block(fastfetch.with_block(text)) == text
    assert fastfetch.with_block(fastfetch.with_block(text)) == fastfetch.with_block(text)


# ---------------------------------------------------------------- Deinstallation
def test_uninstall_removes_unchanged_files_and_block_keeps_changed(home, tmp_path):
    original = (home / '.bashrc').read_text()
    install(home)
    changed = home / '.config/fastfetch/config.jsonc'
    changed.write_text('{"angepasst": true}\n')
    paths = layout(tmp_path / 'inst', mode='portable')
    plan = uninstall.plan_uninstall(**paths, home=home)
    kinds = [(a['kind'], a.get('path')) for a in plan['actions']]
    assert ('bashrc_block', str(home / '.bashrc')) in kinds
    assert ('unlink', str(changed)) not in kinds
    assert any(item['path'] == str(changed) for item in plan['keep'])
    calls = []
    uninstall.apply_uninstall(plan, runner=recorder(calls))
    assert calls == []
    assert (home / '.bashrc').read_text() == original
    assert not (home / '.local/bin/me-fastfetch').exists()
    assert not (home / '.local/share/me-fastfetch').exists()
    assert changed.read_text() == '{"angepasst": true}\n'
    assert list(home.glob('.bashrc.vor-me-fastfetch-entfernen-*'))


def test_uninstall_without_manifest_does_not_touch_home(home, tmp_path):
    (home / '.bashrc').write_text('fastfetch\n')
    paths = layout(tmp_path / 'inst', mode='portable')
    plan = uninstall.plan_uninstall(**paths, home=home)
    assert not any(str(home) in str(a.get('path')) for a in plan['actions'])


def test_uninstall_package_only_on_request_and_only_if_installed_by_picam(home, tmp_path, monkeypatch):
    install(home, install_package=True)
    paths = layout(tmp_path / 'inst', mode='system')
    plan = uninstall.plan_uninstall(**paths, home=home)
    assert not any(a.get('argv', [None])[0] == 'apt-get' for a in plan['actions'])
    assert any('fastfetch bleibt' in note for note in plan['notes'])
    plan = uninstall.plan_uninstall(**paths, home=home, remove_fastfetch_package=True)
    assert ['apt-get', 'remove', '-y', '--', 'fastfetch'] in [a.get('argv') for a in plan['actions']]


# ---------------------------------------------------------------- Engine
@pytest.fixture
def operator(monkeypatch, home):
    account = SimpleNamespace(pw_name='labor', pw_dir=str(home), pw_uid=os.geteuid(), pw_gid=os.getegid())
    monkeypatch.setattr(engine, 'account', lambda name: account)
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    return account


def engine_args(tmp_path, *extra):
    return engine.parser().parse_args(['--source', str(bundle(tmp_path)), '--mode', 'portable', '--prefix',
                                       str(tmp_path / 'target'), '--host', 'pi.local', '--user', 'labor', *extra])


def test_engine_default_has_no_fastfetch(tmp_path, operator, home):
    result = engine.install(engine_args(tmp_path, '--apply'), runner=fake_runner([]))
    assert 'fastfetch' not in result and not (home / '.local').exists()


def test_engine_plan_lists_component_without_writing(tmp_path, operator, home):
    result = engine.install(engine_args(tmp_path, '--with-fastfetch'), runner=fake_runner([]))
    assert result['fastfetch']['bashrc']['state'] == 'fehlt'
    assert result['fastfetch']['package'] == 'fehlt'  # portabel: nie apt
    assert not (home / '.local').exists()


def test_engine_apply_installs_component_after_product(tmp_path, operator, home):
    calls, steps = [], []
    result = engine.install(engine_args(tmp_path, '--apply', '--with-fastfetch'), runner=fake_runner(calls),
                            progress=steps.append)
    assert result['applied'] and result['fastfetch']['applied']
    assert steps[-1].startswith('me-fastfetch') and (home / '.local/bin/me-fastfetch').is_file()
    assert not any(c[0] == 'apt-get' for c in calls)


def test_engine_component_failure_keeps_product(tmp_path, operator, home, monkeypatch):
    def broken(*a, **kw):
        raise OSError('Platte voll')
    monkeypatch.setattr(fastfetch, 'apply', broken)
    result = engine.install(engine_args(tmp_path, '--apply', '--with-fastfetch'), runner=fake_runner([]))
    assert result['applied'] and result['fastfetch']['error'] == 'Platte voll'
    assert (tmp_path / 'target/current').is_symlink()


def test_system_uninstall_finds_operator_from_config(tmp_path):
    import pwd
    config = tmp_path / 'config.toml'
    me = pwd.getpwuid(os.getuid())
    config.write_text('[workbench]\npam_user = ' + json.dumps(me.pw_name) + '\n')
    assert uninstall._config_user(config).pw_dir == me.pw_dir
    config.write_text('[workbench]\n')
    assert uninstall._config_user(config) is None
