"""Dienstverwaltung nur in einer temporaeren Repo-Kopie mit Prozessattrappen."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/werkbank-dienst.sh'


@pytest.fixture
def service_script(tmp_path):
    assert SCRIPT.exists(), 'Dienstskript fehlt'
    repo = tmp_path / 'repo with spaces'
    (repo / 'scripts').mkdir(parents=True)
    shutil.copy(SCRIPT, repo / 'scripts/werkbank-dienst.sh')
    (repo / '.venv/bin').mkdir(parents=True)
    (repo / '.venv/bin/python').symlink_to(sys.executable)
    source = repo / 'src/dispread'
    (source / 'workbench').mkdir(parents=True)
    (source / '__init__.py').touch()
    (source / 'workbench/__init__.py').touch()
    shutil.copy(ROOT / 'src/dispread/defaults.py', source / 'defaults.py')
    (source / 'workbench/cli.py').write_text(
        'import json, os, sys\n'
        'with open(os.environ["CALL_LOG"], "a") as out:\n'
        ' out.write(json.dumps(["dispread", *sys.argv[1:]]) + "\\n")\n'
        'print(os.environ.get("LIVE_STATUS", "{}"))\n'
        'sys.exit(int(os.environ.get("LIVE_EXIT", "0")))\n'
    )
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    stub = f'#!{sys.executable}\n' + '''import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as out:
    out.write(json.dumps([name, *args]) + '\\n')
if name == 'loginctl':
    print('no')
elif name == 'systemctl':
    if 'show' in args:
        print(os.environ.get('STOP_RESULT', 'success') if 'Result' in args
              else os.environ.get('UNIT_STATE', 'active'))
    if 'stop' in args:
        sys.exit(int(os.environ.get('STOP_EXIT', '0')))
elif name == 'curl':
    sys.exit(int(os.environ.get('CURL_EXIT', '0')))
'''
    for name in ('systemd-run', 'systemctl', 'journalctl', 'loginctl', 'curl'):
        path = binaries / name
        path.write_text(stub)
        path.chmod(0o755)
    log = tmp_path / 'calls.jsonl'
    env = dict(os.environ, PATH=f'{binaries}:{os.defpath}', CALL_LOG=str(log),
               LIVE_STATUS=json.dumps({'state': 'idle', 'run': None, 'diagnose_kopie': False}))

    def run(*args, **changes):
        log.write_text('')
        result = subprocess.run(['bash', repo / 'scripts/werkbank-dienst.sh', *args], cwd=tmp_path,
                                env=env | changes, capture_output=True, text=True, timeout=20)
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        return result, calls, repo

    return run


def test_service_script_shell_syntax():
    assert SCRIPT.exists()
    subprocess.run(['bash', '-n', SCRIPT], check=True)


@pytest.mark.parametrize('args', [('start',), ('start', '--host', 'pi.example'), ('stop', '--port', '8081')])
def test_host_and_port_required_without_side_effects(service_script, args):
    result, calls, _ = service_script(*args)
    assert result.returncode != 0
    assert not calls


def test_start_constructs_repo_relative_command_and_private_socket_directory(service_script):
    result, calls, repo = service_script('start', '--host', 'pi.example', '--port', '8081')
    assert result.returncode == 0, result.stderr
    command = next(call for call in calls if call[0] == 'systemd-run')
    assert '--user' in command
    assert '--unit=dispread-werkbank-bruecke' in command
    assert f'--working-directory={repo}' in command
    serve = command[command.index('serve'):]
    for option, expected in {'--host': 'pi.example', '--port': '8081',
                             '--data': str(repo / 'var/workbench'), '--live-data': str(repo / 'var/live'),
                             '--bridge-directory': str(repo / 'var/workbench/bridge'),
                             '--bridge-endpoint': 'https://pi.example:8081/bridge/v2'}.items():
        assert serve[serve.index(option) + 1] == expected
    socket = Path(serve[serve.index('--socket') + 1])
    assert socket.is_relative_to(repo)
    assert socket.parent.stat().st_mode & 0o777 == 0o700
    assert 'enable-linger' in result.stdout + result.stderr
    assert all(call[:2] != ['loginctl', 'enable-linger'] for call in calls)


def test_start_preserves_explicit_options(service_script, tmp_path):
    socket = tmp_path / 'private/control.sock'
    result, calls, _ = service_script('start', '--host', 'pi.example', '--port', '9443',
                                     '--data', 'my data', '--live-data', 'my live', '--socket', str(socket),
                                     '--bridge-directory', 'my bridge', '--endpoint', 'https://other:9443/bridge/v2',
                                     '--unit', 'test-werkbank')
    assert result.returncode == 0, result.stderr
    command = next(call for call in calls if call[0] == 'systemd-run')
    assert '--unit=test-werkbank' in command
    for option, value in (('--data', 'my data'), ('--live-data', 'my live'), ('--bridge-directory', 'my bridge')):
        assert command[command.index(option) + 1].endswith('/' + value)
    assert command[command.index('--bridge-endpoint') + 1] == 'https://other:9443/bridge/v2'


@pytest.mark.parametrize('action', ['stop', 'restart'])
@pytest.mark.parametrize('status', [
    {'state': 'running', 'run': {}, 'diagnose_kopie': False},
    {'state': 'setup_running', 'run': None, 'diagnose_kopie': False},
    {'state': 'stopped', 'diagnose_kopie': True},
    {},
])
def test_stop_refuses_active_or_unknown_state(service_script, action, status):
    result, calls, _ = service_script(action, '--host', 'pi.example', '--port', '8081', LIVE_STATUS=json.dumps(status))
    assert result.returncode != 0
    assert not any('stop' in call or call[0] == 'systemd-run' for call in calls if call[0] != 'dispread')
    cli = next(call for call in calls if call[0] == 'dispread')
    assert cli[1:3] == ['live', 'status']
    assert '--socket' in cli


def test_stop_refuses_unavailable_status(service_script):
    result, calls, _ = service_script('stop', '--host', 'pi.example', '--port', '8081', LIVE_EXIT='1')
    assert result.returncode != 0
    assert not any(call[0] == 'systemctl' and 'stop' in call for call in calls)


def test_stop_allows_finished_run_with_retained_audit(service_script):
    result, calls, _ = service_script('stop', '--host', 'pi.example', '--port', '8081',
                                     LIVE_STATUS=json.dumps({'state': 'stopped', 'run': {'summary': {}},
                                                             'diagnose_kopie': False}))
    assert result.returncode == 0, result.stderr
    assert ['systemctl', '--user', 'stop', 'dispread-werkbank-bruecke'] in calls


def test_force_stop_warns_and_stops(service_script):
    result, calls, _ = service_script('stop', '--host', 'pi.example', '--port', '8081', '--force',
                                     LIVE_STATUS='{"state":"running"}')
    assert result.returncode == 0, result.stderr
    assert 'WARNUNG' in result.stderr
    assert any(call[0] == 'systemctl' and 'stop' in call for call in calls)


def test_stop_timeout_resets_failed_and_reports_failure(service_script):
    result, calls, _ = service_script('stop', '--host', 'pi.example', '--port', '8081',
                                     STOP_EXIT='1', STOP_RESULT='timeout')
    assert result.returncode != 0
    assert ['systemctl', '--user', 'reset-failed', 'dispread-werkbank-bruecke'] in calls


def test_restart_waits_for_live_http_response(service_script):
    result, calls, _ = service_script('restart', '--host', 'pi.example', '--port', '8081')
    assert result.returncode == 0, result.stderr
    stop = next(i for i, call in enumerate(calls) if call[0] == 'systemctl' and 'stop' in call)
    start = next(i for i, call in enumerate(calls) if call[0] == 'systemd-run')
    ready = next(i for i, call in enumerate(calls) if call[0] == 'curl')
    assert stop < start < ready
    assert calls[ready][-1] == 'https://pi.example:8081/live'


def test_restart_readiness_failure_is_nonzero(service_script):
    result, calls, _ = service_script('restart', '--host', 'pi.example', '--port', '8081',
                                     '--wait-seconds', '1', CURL_EXIT='7')
    assert result.returncode != 0
    assert any(call[0] == 'curl' for call in calls)


@pytest.mark.parametrize(('action', 'binary'), [('status', 'systemctl'), ('logs', 'journalctl')])
def test_status_and_logs_address_selected_user_unit(service_script, action, binary):
    result, calls, _ = service_script(action, '--host', 'pi.example', '--port', '8081', '--unit', 'another-unit')
    assert result.returncode == 0
    assert any(call[0] == binary and '--user' in call and 'another-unit' in call for call in calls)
    assert not any(call[0] == 'systemd-run' for call in calls)
