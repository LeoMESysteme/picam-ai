"""Opt-in installer configuration must not change existing serve invocations."""

import asyncio
from types import SimpleNamespace

import pytest

from dispread.workbench import cli


def configured(path, text, *options):
    path.write_text(text, encoding='utf-8')
    argv = ['serve', '--config', str(path), *options]
    args = cli.parser().parse_args(argv)
    from dispread.workbench.config import apply_config
    return apply_config(args, argv)


def test_config_paths_resolve_against_file_from_another_cwd(tmp_path, monkeypatch):
    directory = tmp_path / 'configuration'
    directory.mkdir()
    other = tmp_path / 'cwd'
    other.mkdir()
    monkeypatch.chdir(other)
    args = configured(directory / 'config.toml', '''
[workbench]
host = "pi.example"
port = 9443
pam_user = "operator"
data = "../state/workbench"
live_data = "../state/live"
socket = "../runtime/control.sock"
cert = "tls/cert.pem"
key = "tls/key.pem"
bridge_directory = "../state/bridge"
bridge_endpoint = ["https://pi.example:9443", "wss://pi.example:9443/bridge"]
bridge_name = "Pi im Labor"
bridge_discovery = true
camera = 2
simulate = true
[live]
templates = "../release/templates.json"
calibration = "../state/calibration/missing.json"
''')
    assert (args.host, args.port, args.pam_user, args.camera) == ('pi.example', 9443, 'operator', 2)
    assert args.bridge_discovery is True and args.simulate is True
    assert args.bridge_name == 'Pi im Labor'
    assert args.bridge_endpoint == ['https://pi.example:9443', 'wss://pi.example:9443/bridge']
    assert args.data == str(tmp_path / 'state/workbench')
    assert args.live_data == str(tmp_path / 'state/live')
    assert args.socket == str(tmp_path / 'runtime/control.sock')
    assert args.cert == str(directory / 'tls/cert.pem')
    assert args.key == str(directory / 'tls/key.pem')
    assert args.bridge_directory == str(tmp_path / 'state/bridge')
    assert args.live_config.templates == tmp_path / 'release/templates.json'
    assert args.live_config.calibration == tmp_path / 'state/calibration/missing.json'
    assert not args.live_config.calibration.exists()
    assert sorted(tmp_path.iterdir()) == [directory, other]


def test_explicit_cli_values_override_file_including_defaults_and_equals_form(tmp_path):
    args = configured(tmp_path / 'config.toml', '''
[workbench]
host = "pi.example"
port = 9443
data = "configured"
bridge_endpoint = ["https://file.example"]
simulate = false
''', '--host=127.0.0.1', '--port', '8080', '--data', 'cli-data',
                      '--bridge-endpoint', 'https://cli.example', '--simulate')
    assert (args.host, args.port, args.data) == ('127.0.0.1', 8080, 'cli-data')
    assert args.bridge_endpoint == ['https://cli.example']
    assert args.simulate is True


def test_no_config_keeps_original_defaults_and_namespace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    argv = ['serve']
    args = cli.parser().parse_args(argv)
    before = vars(args).copy()
    from dispread.workbench.config import apply_config
    assert apply_config(args, argv) is args
    assert vars(args) == before
    assert (args.host, args.port, args.data, args.live_data) == ('127.0.0.1', 8080, 'var/workbench', 'var/live')
    assert args.cert == 'var/workbench/tls/cert.pem'
    assert args.key == 'var/workbench/tls/key.pem'
    assert not hasattr(args, 'live_config')


@pytest.mark.parametrize('text', [
    '[unknown]\nport = 9443',
    '[workbench]\nunknown = true',
    '[live]\ntemplates_sha256 = "other"',
    'workbench = "invalid"',
    'live = []',
    '[workbench]\nport = "9443"',
    '[workbench]\nport = true',
    '[workbench]\nport = 0',
    '[workbench]\nport = 65536',
    '[workbench]\nport = 2.5',
    '[workbench]\ncamera = true',
    '[workbench]\ncamera = -1',
    '[workbench]\nsimulate = "false"',
    '[workbench]\nbridge_discovery = 1',
    '[workbench]\npam_user = ""',
    '[workbench]\nbridge_name = []',
    '[workbench]\nhost = ""',
    '[workbench]\nhost = "https://pi.example"',
    '[workbench]\nhost = "bad host"',
    '[workbench]\nhost = "fe80::1%bad scope"',
    '[workbench]\nhost = "-invalid.example"',
    '[workbench]\nhost = 123',
    '[workbench]\ndata = ""',
    '[workbench]\ndata = 3',
    '[workbench]\nsocket = "bad\\u0000path"',
    '[live]\ntemplates = false',
    '[live]\ncalibration = ""',
    '[workbench]\nbridge_endpoint = "https://pi.example"',
    '[workbench]\nbridge_endpoint = [1]',
    '[workbench]\nbridge_endpoint = ["http://pi.example"]',
    '[workbench]\nbridge_endpoint = ["https://user:password@pi.example"]',
    '[workbench]\nport = [',
])
def test_invalid_config_is_rejected_without_startup(tmp_path, text):
    path = tmp_path / 'config.toml'
    path.write_text(text)
    argv = ['serve', '--config', str(path)]
    args = cli.parser().parse_args(argv)
    before = vars(args).copy()
    from dispread.workbench.config import apply_config
    with pytest.raises(ValueError, match='config|Konfiguration'):
        apply_config(args, argv)
    assert vars(args) == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('host', ['127.0.0.1', '0.0.0.0', '::', '2001:db8::1', 'localhost', 'pi-lab.example'])
def test_valid_listen_hosts(tmp_path, host):
    assert configured(tmp_path / 'config.toml', f'[workbench]\nhost = "{host}"').host == host


@pytest.mark.parametrize(('section', 'field', 'existing_kind'), [
    ('workbench', 'data', 'file'), ('workbench', 'live_data', 'file'),
    ('workbench', 'bridge_directory', 'file'), ('workbench', 'cert', 'directory'),
    ('workbench', 'key', 'directory'), ('workbench', 'socket', 'directory'),
    ('live', 'templates', 'directory'), ('live', 'calibration', 'directory'),
])
def test_path_kind_conflicts_are_rejected(tmp_path, section, field, existing_kind):
    target = tmp_path / 'target'
    if existing_kind == 'file':
        target.touch()
    else:
        target.mkdir()
    with pytest.raises(ValueError, match=field):
        configured(tmp_path / 'config.toml', f'[{section}]\n{field} = "target"')


def test_path_with_file_as_parent_is_rejected(tmp_path):
    (tmp_path / 'file').touch()
    with pytest.raises(ValueError, match='data'):
        configured(tmp_path / 'config.toml', '[workbench]\ndata = "file/subdirectory"')


def test_main_reports_missing_config_without_starting_server(tmp_path, capsys):
    assert cli.main(['serve', '--config', str(tmp_path / 'missing.toml')]) == 1
    assert 'missing.toml' in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


def test_main_applies_config_with_real_process_argv(tmp_path, monkeypatch):
    import sys

    from dispread.workbench import server

    path = tmp_path / 'config.toml'
    path.write_text('[workbench]\nport = 9443\nhost = "pi.example"')
    received = []

    async def serve(args):
        received.append((args.host, args.port))

    monkeypatch.setattr(server, 'serve', serve)
    monkeypatch.setattr(sys, 'argv', ['dispread', 'serve', '--config', str(path), '--port=8080'])
    assert cli.main() == 0
    assert received == [('pi.example', 8080)]


def test_config_only_available_for_serve(tmp_path):
    with pytest.raises(SystemExit) as error:
        cli.parser().parse_args(['status', '--config', str(tmp_path / 'config.toml')])
    assert error.value.code == 2


def test_server_hands_config_to_live_service_before_camera_start(tmp_path, monkeypatch):
    from dispread.workbench import server

    runtime = tmp_path / 'runtime'
    runtime.mkdir(mode=0o700)
    args = configured(tmp_path / 'config.toml', f'''
[workbench]
socket = "{runtime}/control.sock"
simulate = true
[live]
templates = "templates.json"
calibration = "calibration.json"
''')
    monkeypatch.setattr(server, 'service_pam_user', lambda value: 'operator')
    monkeypatch.setattr(server, 'bridge_service_config', lambda value: ({}, None))
    monkeypatch.setattr(server, 'CameraOwner', lambda *args, **kwargs: SimpleNamespace())

    class ReachedLiveService(Exception):
        pass

    def start_live(owner, data_dir, *, config, simulate, bridge_hub):
        assert config.templates == tmp_path / 'templates.json'
        assert config.calibration == tmp_path / 'calibration.json'
        assert simulate is True
        raise ReachedLiveService

    monkeypatch.setattr(server, 'LiveService', start_live)
    with pytest.raises(ReachedLiveService):
        asyncio.run(server.serve(args))
