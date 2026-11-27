"""Geführte Installation: Fragen, Plan, Bestätigung, sudo-Übergabe (ohne echte Systemänderung)."""
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packaging'))
from picam_installer import engine, guided  # noqa: E402


def fake_runner(python=(3, 13, 5), missing=(), ip=None, packages_missing=()):
    def run(command, **_):
        text = ' '.join(map(str, command))
        if '-I' in command and '-c' in command:
            return SimpleNamespace(returncode=0, stdout=json.dumps(
                {'version': list(python), 'missing': list(missing), 'python': '/usr/bin/python3'}), stderr='')
        if text.startswith('ip -j'):
            return SimpleNamespace(returncode=0, stdout=json.dumps(ip or [
                {'ifname': 'lo', 'addr_info': [{'family': 'inet', 'local': '127.0.0.1'}]},
                {'ifname': 'eth0', 'addr_info': [{'family': 'inet', 'local': '192.168.10.42'}]}]), stderr='')
        if text.startswith('dpkg-query'):
            name = command[-1]
            installed = name not in packages_missing
            return SimpleNamespace(returncode=0 if installed else 1,
                                   stdout='install ok installed' if installed else '', stderr='')
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    return run


@pytest.fixture
def env(monkeypatch, tmp_path):
    archive = tmp_path / 'picam-9.9.9.tar.gz'
    archive.write_bytes(b'x')
    bundle = SimpleNamespace(release_id='9.9.9', sha256='0' * 64,
                             files={'packaging/apt-packages.txt': b'python3-numpy\npython3-zeroconf\n'})
    monkeypatch.setattr('picam_installer.archive.load_source', lambda source, sha=None: bundle)
    monkeypatch.setattr(engine, 'hardware_id_available', lambda: True)
    monkeypatch.setattr(guided, 'port_free', lambda host, port: True)
    monkeypatch.setattr(engine, 'account', lambda name: SimpleNamespace(pw_name=name, pw_dir=str(tmp_path / 'home'),
                                                                        pw_uid=1000, pw_gid=1000))
    monkeypatch.setattr(guided, 'getpass', SimpleNamespace(getuser=lambda: 'labor'))
    monkeypatch.delenv('SUDO_USER', raising=False)
    return SimpleNamespace(tmp=tmp_path, archive=archive)


def answers(*values):
    queue = list(values)

    def input_(prompt):
        if not queue:
            raise AssertionError(f'unerwartete Frage: {prompt}')
        return queue.pop(0)
    return input_


def fake_installer(calls):
    def install(args, runner=None, progress=None):
        calls.append((args, progress))
        if progress:
            progress('Zielverzeichnisse anlegen')
        prefix = args.prefix or '/opt/picam'
        return {'applied': bool(args.apply), 'release_id': '9.9.9', 'url': f'https://{args.host}:{args.port}/live',
                'paths': {'prefix': prefix, 'data': prefix + '/data', 'config': prefix + '/config/config.toml',
                          'runtime': prefix + '/run', 'unit': None},
                'start_command': ['python', '-m', 'dispread.workbench.cli', 'serve']}
    return install


def test_portable_flow_asks_plans_and_installs(env, monkeypatch):
    calls, out = [], io.StringIO()
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    code = guided.run([], input_=answers('3', '', '1', '8095', str(env.tmp / 'p'), 'j'),
                      out=guided.Out(out, color=False), runner=fake_runner(), installer=fake_installer(calls),
                      installer_root=env.tmp)
    text = out.getvalue()
    assert code == 0, text
    assert 'picam-9.9.9.tar.gz' in text and '192.168.10.42' in text and '127.0.0.1' not in text
    assert 'Plan' in text and 'Nächste Schritte' in text and 'Zielverzeichnisse anlegen' in text
    plan_args, apply_args = calls[0][0], calls[1][0]
    assert (plan_args.mode, plan_args.user, plan_args.host, plan_args.port) == ('portable', 'labor',
                                                                                 '192.168.10.42', 8095)
    assert apply_args.apply is True and plan_args.prefix == str(env.tmp / 'p')


def test_declining_changes_nothing(env):
    calls, out = [], io.StringIO()
    code = guided.run(['--mode', 'portable', '--prefix', str(env.tmp / 'p')],
                      input_=answers('', '1', '8080', 'n'), out=guided.Out(out, color=False),
                      runner=fake_runner(), installer=fake_installer(calls), installer_root=env.tmp)
    assert code == 130 and len(calls) == 1 and 'nichts geändert' in out.getvalue()


def test_system_install_hands_over_to_sudo_with_fixed_answers(env, monkeypatch):
    calls, execs = [], []
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    code = guided.run([], input_=answers('1', '', '1', '8080', 'j'), out=guided.Out(io.StringIO(), color=False),
                      runner=fake_runner(packages_missing=('python3-zeroconf',)),
                      installer=fake_installer(calls), installer_root=env.tmp,
                      execvp=lambda name, argv: execs.append(argv))
    assert code == 1 and len(calls) == 1  # nur Plan, Ausführung erst nach sudo
    argv = execs[0]
    assert argv[0] == 'sudo' and '--guided-apply' in argv and '--install-packages' in argv
    assert argv[argv.index('--source') + 1] == str(env.archive.resolve())
    assert argv[argv.index('--user') + 1] == 'labor'


def test_old_python_is_refused_before_questions(env):
    out = io.StringIO()
    code = guided.run([], input_=answers(), out=guided.Out(out, color=False), runner=fake_runner(python=(3, 11, 2)),
                      installer=fake_installer([]), installer_root=env.tmp)
    assert code == 1 and 'Python 3.13' in out.getvalue()


def test_deep_portable_folder_is_refused(env, monkeypatch):
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    deep = env.tmp / ('x' * 120)
    out = io.StringIO()
    code = guided.run(['--mode', 'portable'], input_=answers('', '1', '8080', str(deep)),
                      out=guided.Out(out, color=False), runner=fake_runner(), installer=fake_installer([]),
                      installer_root=env.tmp)
    assert code == 1 and 'zu tief' in out.getvalue()


def test_ctrl_d_aborts_cleanly(env):
    def eof(_prompt):
        raise EOFError
    out = io.StringIO()
    assert guided.run([], input_=eof, out=guided.Out(out, color=False), runner=fake_runner(),
                      installer=fake_installer([]), installer_root=env.tmp) == 130


def test_engine_routes_guided_apply(monkeypatch):
    seen = []
    monkeypatch.setattr(guided, 'guided_apply_main', lambda argv: seen.append(argv) or 0)
    assert engine.main(['--guided-apply', '--source', 'x']) == 0 and seen


def test_engine_without_tty_keeps_strict_flags(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'stdin', io.StringIO(''))
    with pytest.raises(SystemExit):
        engine.main(['--source', 'x'])
    assert 'required' in capsys.readouterr().err


def test_addresses_skip_loopback():
    found = guided.addresses(fake_runner())
    assert ('192.168.10.42', 'eth0') in found and all(a != '127.0.0.1' for a, _ in found)


def test_out_respects_no_color(monkeypatch):
    monkeypatch.setenv('NO_COLOR', '1')
    stream = io.StringIO()
    stream.isatty = lambda: True
    out = guided.Out(stream)
    out.status('ok', 'X', 'y')
    assert '\033[' not in stream.getvalue()


def test_apply_starts_service_only_after_yes(env, monkeypatch):
    calls, commands = [], []
    monkeypatch.setattr(guided, 'wait_ready', lambda host, port: True)
    args = engine.parser().parse_args(['--source', str(env.archive), '--mode', 'user', '--user', 'labor',
                                       '--host', '192.168.10.42'])

    def runner(command, **_):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, '', '')
    out = io.StringIO()
    assert guided.apply(args, out=guided.Out(out, color=False), input_=answers('n'), runner=runner,
                        installer=fake_installer(calls)) == 0
    assert commands == [] and 'picam start' in out.getvalue()
    assert guided.apply(args, out=guided.Out(io.StringIO(), color=False), input_=answers(''), runner=runner,
                        installer=fake_installer(calls)) == 0
    assert ['systemctl', '--user', 'enable', '--now', 'picam-werkbank.service'] in commands


# --- Optional: KI-Sensoreinrichtung und Marktplatz (Konfiguration [features], Vorgabe aus) ---------

def _config_for(sensor_assistant):
    args = engine.parser().parse_args(['--source', 'x', '--mode', 'portable', '--user', 'labor', '--host', 'h',
                                       '--port', '8080'] + (['--with-sensor-assistant'] if sensor_assistant else []))
    paths = {'data': Path('/d'), 'runtime': Path('/r')}
    return engine.config_text(args, paths, Path('/opt/picam/releases/9.9.9'))


def test_config_text_writes_features_off_by_default_and_on_with_flag():
    import tomllib

    from dispread.workbench.config import parse_config

    for flag in (False, True):
        text = _config_for(flag)
        data = tomllib.loads(text)
        assert data['features'] == {'sensor_assistant': flag}
        assert parse_config(data, Path('/tmp'))  # der Server liest die Datei
    assert engine.parser().parse_args(['--source', 'x', '--mode', 'portable', '--user', 'u', '--host', 'h',
                                       '--port', '1', '--without-sensor-assistant']).sensor_assistant is False


def test_guided_offers_sensor_assistant_default_no_and_passes_choice(env, monkeypatch):
    seen = []

    class Recording(guided.Typed):
        def multi(self, label, items):
            seen.append({key: on for key, _, _, on in items})
            return {'sensor_assistant'} if self.choose_assistant else {key for key, _, _, on in items if on}

        choose_assistant = False

    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    for choose in (False, True):
        Recording.choose_assistant = choose
        calls = []
        input_ = answers('3', '', '1', '8095', str(env.tmp / 'p'), 'j')
        out = guided.Out(io.StringIO(), color=False)
        code = guided.run([], input_=input_, out=out, runner=fake_runner(), installer=fake_installer(calls),
                          installer_root=env.tmp, ui=Recording(out, input_))
        assert code == 0
        assert seen[-1] == {'fastfetch': True, 'sensor_assistant': False}  # Vorgabe: nein
        assert calls[0][0].sensor_assistant is choose and calls[1][0].sensor_assistant is choose


def test_guided_flag_skips_question_and_reaches_sudo_handover(env, monkeypatch):
    calls, execs = [], []
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    guided.run(['--with-sensor-assistant', '--without-fastfetch'], input_=answers('1', '', '1', '8080', 'j'),
               out=guided.Out(io.StringIO(), color=False), runner=fake_runner(), installer=fake_installer(calls),
               installer_root=env.tmp, execvp=lambda name, argv: execs.append(argv))
    assert calls[0][0].sensor_assistant is True and '--with-sensor-assistant' in execs[0]
