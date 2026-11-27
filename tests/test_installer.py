"""Installer tests use only fresh temporary roots and process doubles."""
from __future__ import annotations

import hashlib
import io
import json
import os
import pwd
import shutil
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packaging'))
SENSOR_DIR = 'src/dispread/data/sensors/gsv2as-161a'
ACCOUNT = pwd.getpwuid(os.getuid()).pw_name


@pytest.fixture(autouse=True)
def fixture_template_hash(monkeypatch):
    # Tiny fixture has a known independent payload; production pins the real template.
    from picam_installer import archive
    monkeypatch.setattr(archive, 'TEMPLATE_SHA256', hashlib.sha256(b'{}').hexdigest())
    # Apply tests never contact a real host or service.
    from picam_installer import engine
    monkeypatch.setattr(engine, 'hardware_id_available', lambda: True)
    def no_listener(*args, **kwargs):
        raise ConnectionRefusedError
    monkeypatch.setattr(engine.socket, 'create_connection', no_listener)


def bundle(tmp_path, extra=None, mutate=None, change_files=None):
    files = {
        'pyproject.toml': b'[project]\nname="picam-number-ingestion"\n',
        'VERSION': b'1.0\n',
        'packaging/apt-packages.txt': b'python3-venv # venv\n',
        'scripts/install.py': b'print("installer")\n',
        'install.sh': b'#!/bin/sh\n',
        'packaging/picam_installer/__main__.py': b'',
        'src/dispread/__init__.py': b'',
        f'{SENSOR_DIR}/sensor.json': json.dumps({'templates': {
            'file': 'templates.json', 'sha256': hashlib.sha256(b'{}').hexdigest()}}).encode(),
        f'{SENSOR_DIR}/display.json': b'{}',
        f'{SENSOR_DIR}/templates.json': b'{}',
    }
    if change_files:
        change_files(files)
    manifest = {'schema': 1, 'release_id': 'v1', 'commit': 'abc123',
                'files': {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}
    if mutate:
        mutate(manifest)
    files['release.json'] = json.dumps(manifest).encode()
    path = tmp_path / 'release.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        for name, data in files.items():
            item = tarfile.TarInfo('picam/' + name)
            item.size = len(data)
            archive.addfile(item, io.BytesIO(data))
        if extra:
            archive.addfile(*extra)
    return path


def installer():
    from picam_installer import engine
    return engine


def test_dry_run_never_creates_destination_or_runs_commands(tmp_path, monkeypatch):
    engine = installer()
    source = bundle(tmp_path)
    target = tmp_path / 'new'
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    def forbidden(*a, **kw):
        pytest.fail('dry-run attempted a mutation command')
    args = engine.parser().parse_args(['--source', str(source), '--mode', 'portable',
                                     '--prefix', str(target), '--host', 'pi.local', '--user', ACCOUNT])
    result = engine.install(args, runner=forbidden)
    assert result['applied'] is False
    assert not target.exists()


def healthy(engine, **changes):
    values = dict(system='Linux', machine='aarch64', os_id='debian', os_version='13',
                  python='/usr/bin/python3', version=(3, 13, 5), missing_modules=(),
                  apt=True, systemd=True, user_bus=True)
    values.update(changes)
    return engine.SystemInfo(**values)


@pytest.mark.parametrize('system,version,missing,match', [
    ('Windows', (3, 13, 0), (), 'Linux'),
    ('Darwin', (3, 13, 0), (), 'Linux'),
    ('Linux', (3, 11, 9), (), '3.13'),
    ('Linux', (3, 12, 3), (), '3.13'),
    ('Linux', (3, 13, 5), ('cv2',), 'cv2'),
])
def test_incompatible_runtime_is_rejected_without_writes(tmp_path, monkeypatch, system, version, missing, match):
    engine = installer()
    source = bundle(tmp_path)
    target = tmp_path / 'new'
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine, system=system, version=version,
                                                                      missing_modules=missing))
    args = engine.parser().parse_args(['--source', str(source), '--mode', 'portable', '--prefix', str(target),
                                     '--host', 'pi.local', '--user', 'operator', '--apply'])
    with pytest.raises(ValueError, match=match):
        engine.install(args)
    assert not target.exists()


@pytest.mark.parametrize('name,kind', [('picam/../escape', 'file'), ('/escape', 'file'),
                                     ('picam/linked', 'symlink'), ('picam/hard', 'hardlink'),
                                     ('picam/VERSION', 'file')])
def test_unsafe_archives_are_rejected_before_extract(tmp_path, name, kind):
    from picam_installer.archive import read_bundle
    item = tarfile.TarInfo(name)
    item.size = 0
    if kind == 'symlink':
        item.type, item.linkname = tarfile.SYMTYPE, '/etc'
    if kind == 'hardlink':
        item.type, item.linkname = tarfile.LNKTYPE, 'picam/VERSION'
    source = bundle(tmp_path, extra=(item, None))
    with pytest.raises(ValueError):
        read_bundle(source.read_bytes())
    assert not (tmp_path / 'escape').exists()


def test_manipulated_manifest_cannot_activate_release(tmp_path):
    from picam_installer.archive import read_bundle
    source = bundle(tmp_path, mutate=lambda m: m['files'].__setitem__('VERSION', '0' * 64))
    with pytest.raises(ValueError, match='Hash'):
        read_bundle(source.read_bytes())


@pytest.mark.parametrize('name', ['sensor.json', 'display.json', 'templates.json'])
def test_missing_sensor_file_with_matching_manifest_is_rejected(tmp_path, name):
    from picam_installer.archive import read_bundle
    source = bundle(tmp_path, change_files=lambda files: files.pop(f'{SENSOR_DIR}/{name}'))
    with pytest.raises(ValueError, match='unvollstaendig'):
        read_bundle(source.read_bytes())


@pytest.mark.parametrize('path', [f'{SENSOR_DIR}/templates.json', 'src/dispread/data/templates-stufe2c-2026-09-30.json'])
def test_changed_template_with_matching_manifest_is_rejected(tmp_path, path):
    from picam_installer.archive import read_bundle
    source = bundle(tmp_path, change_files=lambda files: files.update({path: b'anders'}))
    with pytest.raises(ValueError, match='Vorlage'):
        read_bundle(source.read_bytes())


def test_package_without_installer_is_incomplete(tmp_path):
    from picam_installer.archive import read_bundle
    source = bundle(tmp_path, mutate=lambda m: m['files'].pop('scripts/install.py'))
    with pytest.raises(ValueError):
        read_bundle(source.read_bytes())


def test_systemd_missing_offers_portable_without_silent_mode_change(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine, systemd=False))
    args = engine.parser().parse_args(['--source', str(bundle(tmp_path)), '--mode', 'system',
                                     '--root', str(tmp_path / 'stage'), '--host', 'pi.local', '--user', 'operator'])
    with pytest.raises(ValueError, match='portable'):
        engine.install(args)
    assert not (tmp_path / 'stage').exists()


def test_home_with_spaces_is_quoted_in_unit_without_shell_execution():
    engine = installer()
    text = engine.unit_text(python=Path('/home/A B/picam/.venv/bin/python'),
                            config=Path('/home/A B/picam/config.toml'), user='operator', mode='user',
                            runtime=Path('/home/A B/picam/run'))
    assert '"/home/A B/picam/.venv/bin/python"' in text
    assert 'User=' not in text
    assert 'WantedBy=default.target' in text
    assert '/bin/sh' not in text


def test_working_directory_is_unquoted_absolute_path():
    """Regression raspi01: ``WorkingDirectory="/opt/picam/current"`` → „path is not absolute“."""
    engine = installer()
    text = engine.unit_text(python=Path('/opt/picam/current/.venv/bin/python'), config=Path('/etc/picam/config.toml'),
                            user='operator', mode='system', runtime=Path('/run/picam'))
    assert 'WorkingDirectory=/opt/picam/current\n' in text
    spaced = engine.unit_text(python=Path('/home/A B/50%/.venv/bin/python'), config=Path('/home/A B/c.toml'),
                              user='operator', mode='user', runtime=Path('/home/A B/run'))
    assert 'WorkingDirectory=/home/A B/50%%\n' in spaced
    with pytest.raises(ValueError):
        engine.path_unit('relative/path')


@pytest.mark.skipif(shutil.which('systemd-analyze') is None, reason='systemd-analyze fehlt')
@pytest.mark.parametrize('mode', ['system', 'user'])
def test_generated_unit_passes_systemd_analyze_verify(tmp_path, mode):
    import getpass

    engine = installer()
    root = tmp_path / 'opt dir' / 'current'
    python = root / '.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\n')
    python.chmod(0o755)
    config = tmp_path / 'config.toml'
    config.write_text('[workbench]\n')
    unit = tmp_path / 'picam-werkbank.service'
    unit.write_text(engine.unit_text(python=python, config=config, user=getpass.getuser(), mode=mode,
                                     runtime=tmp_path / 'run'))
    command = ['systemd-analyze', *(['--user'] if mode == 'user' else []), 'verify', str(unit)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    problems = [line for line in result.stderr.splitlines() if 'picam-werkbank.service' in line]
    assert not problems, result.stderr
    assert result.returncode == 0, result.stderr


def test_bootstrap_help_works_without_any_installation():
    path = ROOT / 'install.sh'
    result = subprocess.run(['bash', str(path), '--help'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '--apply' in result.stdout
    assert '--mode' in result.stdout


def fake_runner(calls, fail=False):
    def run(command, **kwargs):
        calls.append(command)
        if '-m' in command and 'venv' in command:
            directory = Path(command[-1])
            (directory / 'bin').mkdir(parents=True)
            (directory / 'bin/python').write_text('#!fake')
            (directory / 'pyvenv.cfg').write_text('include-system-site-packages = true\n')
        if fail and 'pip' in command:
            raise subprocess.CalledProcessError(1, command, stderr='test failure')
        return subprocess.CompletedProcess(command, 0, stdout='{}', stderr='')
    return run


def portable_args(engine, tmp_path, source):
    return engine.parser().parse_args(['--source', str(source), '--mode', 'portable', '--prefix', str(tmp_path / 'target'),
                                     '--host', 'pi.local', '--user', ACCOUNT, '--apply'])


def test_apply_uses_only_new_target_and_preserves_it_on_repetition(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    args = portable_args(engine, tmp_path, bundle(tmp_path))
    calls = []
    result = engine.install(args, runner=fake_runner(calls))
    prefix = tmp_path / 'target'
    assert result['applied'] is True
    assert (prefix / 'current').resolve() == prefix / 'releases/v1'
    assert (prefix / 'config/config.toml').is_file()
    assert not any(c[0] in ('apt-get', 'sudo', 'systemctl') for c in calls)
    assert not any('start' in c or 'enable' in c for c in calls)
    config = (prefix / 'config/config.toml').read_bytes()
    templates = Path(tomllib.loads(config.decode())['live']['templates'])
    assert templates == prefix / 'current' / SENSOR_DIR / 'templates.json'
    assert templates.is_file()
    before = len(calls)
    with pytest.raises(ValueError, match='besteht|vorhanden|bereits'):
        engine.install(args, runner=fake_runner(calls))
    assert len(calls) == before
    assert (prefix / 'config/config.toml').read_bytes() == config


def test_apply_under_strict_umask_keeps_code_usable_for_the_service_account(tmp_path, monkeypatch):
    """raspi01 25.11.: get-picam.sh vererbte umask 077, das Dienstkonto durfte die venv nicht ausführen."""
    import os
    import stat

    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    args = portable_args(engine, tmp_path, bundle(tmp_path))
    previous = os.umask(0o077)
    try:
        engine.install(args, runner=fake_runner([]))
        effective = os.umask(0o022)
    finally:
        os.umask(previous)
    assert effective == 0o022
    release = tmp_path / 'target/releases/v1'
    for path in (release, *release.rglob('*')):
        if path.is_dir() and not path.is_symlink():
            assert path.stat().st_mode & stat.S_IROTH and path.stat().st_mode & stat.S_IXOTH, path


def test_failed_install_does_not_activate_or_leave_partial_target(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    args = portable_args(engine, tmp_path, bundle(tmp_path))
    with pytest.raises(subprocess.CalledProcessError):
        engine.install(args, runner=fake_runner([], fail=True))
    assert not (tmp_path / 'target').exists()


def test_existing_directory_or_symlink_is_never_adopted(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    source = bundle(tmp_path)
    original = tmp_path / 'original'
    original.mkdir()
    (original / 'keep').write_text('old installation')
    (tmp_path / 'target').symlink_to(original, target_is_directory=True)
    args = portable_args(engine, tmp_path, source)
    with pytest.raises(ValueError):
        engine.install(args, runner=fake_runner([]))
    assert (original / 'keep').read_text() == 'old installation'


def test_target_parent_symlink_cannot_redirect_installation(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    source = bundle(tmp_path)
    original = tmp_path / 'original'
    original.mkdir()
    (tmp_path / 'linked').symlink_to(original, target_is_directory=True)
    args = portable_args(engine, tmp_path, source)
    args.prefix = str(tmp_path / 'linked/target')
    with pytest.raises(ValueError, match='Symlink'):
        engine.install(args, runner=fake_runner([]))
    assert list(original.iterdir()) == []


@pytest.mark.parametrize('mode', ['system', 'user', 'portable'])
def test_modes_generate_isolated_absolute_paths(tmp_path, monkeypatch, mode):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    args = engine.parser().parse_args(['--source', str(bundle(tmp_path)), '--mode', mode,
                                     '--root', str(tmp_path / 'stage'), '--host', 'pi.local', '--user', ACCOUNT])
    result = engine.install(args, runner=fake_runner([]))
    for key in ('prefix', 'data', 'config', 'runtime'):
        assert Path(result['paths'][key]).is_relative_to(tmp_path / 'stage')
    assert not (tmp_path / 'stage').exists()


def test_custom_python_does_not_allow_apt_to_hide_missing_native_modules(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine, python='/opt/custom/python',
                                                                      missing_modules=('cv2',)))
    args = portable_args(engine, tmp_path, bundle(tmp_path))
    args.install_packages = True
    calls = []
    with pytest.raises(ValueError):
        engine.install(args, runner=fake_runner(calls))
    assert not calls


@pytest.mark.parametrize('os_id,version,arch', [('debian', '13', 'aarch64'), ('raspbian', '13', 'armv7l'),
    ('ubuntu', '24.04', 'x86_64'), ('fedora', '43', 'x86_64'), ('arch', 'rolling', 'aarch64')])
def test_portable_uses_capabilities_instead_of_distro_version_allowlist(tmp_path, monkeypatch, os_id, version, arch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine, os_id=os_id, os_version=version,
                                                                      machine=arch, apt=False, systemd=False))
    args = portable_args(engine, tmp_path, bundle(tmp_path))
    result = engine.install(args, runner=fake_runner([]))
    assert result['applied'] is True
    assert result['paths']['unit'] is None


def test_busy_port_never_stops_service_or_creates_target(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    class Listener:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(engine.socket, 'create_connection', lambda *a, **kw: Listener())
    with pytest.raises(ValueError, match='belegt'):
        engine.install(portable_args(engine, tmp_path, bundle(tmp_path)), runner=fake_runner([]))
    assert not (tmp_path / 'target').exists()


def test_service_runtime_override_must_match_systemd_runtime_directory(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    args = engine.parser().parse_args(['--source', str(bundle(tmp_path)), '--mode', 'system', '--root',
                                     str(tmp_path / 'stage'), '--runtime', '/tmp/different', '--host', 'pi.local',
                                     '--user', ACCOUNT])
    with pytest.raises(ValueError, match='runtime|Runtime'):
        engine.install(args)


@pytest.mark.parametrize('host', ['fe80::1%bad scope', 'fe80::1%eth0', 'pi.local\n', '999.1.1.1',
                                  '0.0.0.0', '::', '224.0.0.1', 'ff02::1'])
def test_bad_hosts_are_rejected_before_any_destination(tmp_path, host):
    engine = installer()
    with pytest.raises(ValueError):
        engine.valid_host(host)


def test_all_builder_release_ids_are_accepted_by_reader(tmp_path):
    from picam_installer.archive import read_bundle
    source = bundle(tmp_path, mutate=lambda m: m.__setitem__('release_id', 'v' * 128))
    assert read_bundle(source.read_bytes()).release_id == 'v' * 128


def test_failed_install_cannot_leave_existing_unit_or_directories_changed(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    unit_dir = tmp_path / 'units'
    unit_dir.mkdir()
    (unit_dir / 'other.service').write_text('keep')
    args = portable_args(engine, tmp_path, bundle(tmp_path))
    args.mode = 'user'
    args.data = str(tmp_path / 'new-data')
    args.config = str(tmp_path / 'new-config/config.toml')
    args.runtime = None
    args.unit_dir = str(unit_dir)
    with pytest.raises(subprocess.CalledProcessError):
        engine.install(args, runner=fake_runner([], fail=True))
    assert (unit_dir / 'other.service').read_text() == 'keep'
    assert not (tmp_path / 'new-data').exists()
    assert not (tmp_path / 'new-config').exists()


@pytest.mark.parametrize('option', ['data', 'config'])
def test_mutable_directories_cannot_contain_code(tmp_path, monkeypatch, option):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    args = portable_args(engine, tmp_path, bundle(tmp_path))
    setattr(args, option, str(tmp_path / 'target') + ('/config.toml' if option == 'config' else ''))
    with pytest.raises(ValueError, match='Code|Daten|Konfiguration'):
        engine.install(args, runner=fake_runner([]))
    assert not (tmp_path / 'target').exists()


def test_archive_metadata_is_bounded_before_tar_parser(tmp_path, monkeypatch):
    import gzip

    from picam_installer import archive
    monkeypatch.setattr(archive, 'MAX_BYTES', 4096)
    # A highly compressed extended-header payload exceeds the expanded budget
    # before tarfile gets to consume metadata. Not a malformed-metadata test.
    raw = gzip.compress(b'0' * 8192)
    assert len(raw) < 4096
    with pytest.raises(ValueError, match='gross'):
        archive.read_bundle(raw)


def test_system_ownership_calls_never_follow_symlinks(tmp_path, monkeypatch):
    engine = installer()
    root = tmp_path / 'data'
    root.mkdir()
    (root / 'external').symlink_to('/usr/bin/python3')
    calls = []
    monkeypatch.setattr(engine.os, 'chown', lambda *a, **kw: calls.append((a, kw)))
    engine.assign_owner(root, 1000, 1000)
    assert calls
    assert all(kw.get('follow_symlinks') is False for args, kw in calls)


def test_bridge_requires_real_hardware_id_or_explicit_browser_only_fallback(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    monkeypatch.setattr(engine, 'hardware_id_available', lambda: False)
    args = portable_args(engine, tmp_path, bundle(tmp_path))
    with pytest.raises(ValueError, match='without-bridge'):
        engine.install(args, runner=fake_runner([]))
    assert not (tmp_path / 'target').exists()
    args.without_bridge = True
    calls = []
    result = engine.install(args, runner=fake_runner(calls))
    assert result['applied'] is True
    assert not any('identity' in c for c in calls)
    config = (tmp_path / 'target/config/config.toml').read_text()
    assert 'bridge_directory' not in config
    assert any('init-tls' in c for c in calls)


def test_installer_exports_the_same_certificate_the_bridge_serves(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    args = portable_args(engine, tmp_path, bundle(tmp_path))
    calls = []
    engine.install(args, runner=fake_runner(calls))
    identity_command = next(c for c in calls if 'identity' in c)
    assert '--host' in identity_command
    assert identity_command[identity_command.index('--host') + 1] == 'pi.local'
    assert '--export-certificate' in identity_command
    assert not any('init-tls' in c for c in calls)


def test_non_linux_probe_gives_platform_error_without_posix_calls(monkeypatch):
    from picam_installer import platform as detection
    monkeypatch.setattr(detection.platform, 'system', lambda: 'Darwin')
    def forbidden(*args, **kwargs):
        pytest.fail('unsupported platform should be reported before subprocess probe')
    info = detection.probe_system('/not/a/python', runner=forbidden)
    assert info.system == 'Darwin'


@pytest.mark.parametrize('response', ['[]', '{}', '{"version":true}', 'not json'])
def test_bad_interpreter_probe_has_actionable_error(response):
    from picam_installer.platform import probe_system
    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=response, stderr='')
    with pytest.raises(ValueError, match='Python'):
        probe_system(sys.executable, runner=run)


def test_staged_system_install_writes_unit_but_never_calls_service_manager(tmp_path, monkeypatch):
    engine = installer()
    monkeypatch.setattr(engine, 'probe_system', lambda *a, **kw: healthy(engine))
    stage = tmp_path / 'stage'
    args = engine.parser().parse_args(['--source', str(bundle(tmp_path)), '--root', str(stage), '--apply',
                                     '--mode', 'system', '--user', ACCOUNT, '--host', 'pi.local'])
    calls = []
    result = engine.install(args, runner=fake_runner(calls))
    unit = Path(result['paths']['unit'])
    assert unit.is_relative_to(stage)
    assert unit.is_file()
    assert 'User=' + ACCOUNT in unit.read_text()
    assert 'WantedBy=multi-user.target' in unit.read_text()
    assert not any(c[0] in {'sudo', 'systemctl', 'apt-get', 'runuser'} for c in calls)
    assert result['service_started'] is False


def test_process_failure_diagnostic_includes_captured_cause(monkeypatch, capsys):
    engine = installer()
    def fail(*a, **kw):
        raise subprocess.CalledProcessError(1, ['python', '-m', 'venv'], stderr='ensurepip is not available')
    monkeypatch.setattr(engine, 'install', fail)
    code = engine.main(['--source', 'unused', '--mode', 'portable', '--host', 'pi.local', '--user', ACCOUNT])
    assert code == 1
    assert 'ensurepip is not available' in capsys.readouterr().err
