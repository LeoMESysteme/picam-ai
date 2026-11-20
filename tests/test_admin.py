"""picam: Instanzerkennung, Prüfungen, Dienstplan, Konfiguration und CLI (ohne Hardware)."""

import json
import os
import time
from pathlib import Path

import pytest

from dispread.admin import cli, configedit, probes, service
from dispread.admin import instance as inst_mod
from dispread.admin.instance import Instance, discover, parse_exec_start

EXEC = ('{ path=/r/.venv/bin/python ; argv[]=/r/.venv/bin/python -m dispread.workbench.cli serve '
        '--host 10.0.0.5 --port 8082 --data /r/var/wb --live-data /r/var/live '
        '--socket /tmp/x/control.sock --bridge-directory /r/var/wb/bridge '
        '--bridge-endpoint https://10.0.0.5:8082 ; ignore_errors=no ; start_time=[Thu] ; pid=1 }')


def fake_run(table):
    def run(command, timeout=5.0):
        for key, result in table.items():
            if key in ' '.join(map(str, command)):
                return result
        return 1, '', 'unbekannt'
    return run


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'xdg'))
    monkeypatch.delenv('PICAM_CONFIG', raising=False)
    monkeypatch.setattr(inst_mod, 'SYSTEM_CONFIG', tmp_path / 'etc' / 'config.toml')


# ------------------------------------------------------------------ Instanz

def test_parse_exec_start_reads_argv():
    argv = parse_exec_start(EXEC)
    assert argv[:3] == ['/r/.venv/bin/python', '-m', 'dispread.workbench.cli']
    assert argv[-1] == 'https://10.0.0.5:8082'


def test_dev_instance_from_running_unit_is_remembered(tmp_path):
    run = fake_run({'show dispread-werkbank-bruecke': (0, f'ExecStart={EXEC}\nWorkingDirectory=/r\n', '')})
    found = discover(run=run)
    assert (found.kind, found.unit, found.scope) == ('dev', 'dispread-werkbank-bruecke', 'user')
    assert (found.host, found.port, found.socket) == ('10.0.0.5', 8082, '/tmp/x/control.sock')
    assert found.url == 'https://10.0.0.5:8082/live'
    assert found.templates == '/r/var/dotmatrix/templates-stufe2c-2026-09-30.json'
    # Unit gestoppt (transient, verschwunden): Angaben bleiben bekannt.
    gone = discover(run=fake_run({'show': (0, 'LoadState=not-found\n', '')}))
    assert gone.kind == 'dev' and gone.argv == found.argv and gone.port == 8082


def test_installed_config_wins_and_is_read(tmp_path):
    config = tmp_path / 'etc' / 'config.toml'
    config.parent.mkdir()
    config.write_text('[workbench]\npam_user = "labor"\nhost = "192.168.1.9"\nport = 8443\n'
                      f'socket = "{tmp_path}/run/control.sock"\ndata = "{tmp_path}/data/wb"\n'
                      'bridge_endpoint = ["https://192.168.1.9:8443/bridge/v2"]\n'
                      f'bridge_directory = "{tmp_path}/data/wb/bridge"\n'
                      f'[live]\ncalibration = "{tmp_path}/cal.json"\n')
    found = discover(run=fake_run({}))
    assert (found.kind, found.unit, found.scope) == ('system', 'picam-werkbank.service', 'system')
    assert (found.host, found.port, found.pam_user) == ('192.168.1.9', 8443, 'labor')
    assert found.calibration == str(tmp_path / 'cal.json')


def test_broken_config_is_reported_not_guessed(tmp_path):
    config = tmp_path / 'c.toml'
    config.write_text('[workbench]\nport = "kein int"\n')
    found = discover(str(config), run=fake_run({}))
    assert found.kind == 'portable' and found.unit is None
    assert 'nicht lesbar' in found.problem


# ------------------------------------------------------------------ Prüfungen

DEV = Instance(kind='dev', unit='dispread-werkbank-bruecke', scope='user', host='127.0.0.1', port=1,
               socket=None)


@pytest.mark.parametrize('out,level,value', [
    ('ActiveState=active\nActiveEnterTimestamp=Do 2026-11-19 21:31:39 CET\nMainPID=7\n', probes.OK, 'läuft'),
    ('ActiveState=inactive\n', probes.OFF, 'gestoppt'),
    ('ActiveState=failed\nResult=exit-code\n', probes.FAIL, 'ausgefallen'),
    ('ActiveState=activating\n', probes.WARN, 'startet'),
])
def test_service_states(out, level, value):
    fact = probes.fact_service(DEV, fake_run({'show': (0, out, '')}))
    assert (fact.level, fact.value) == (level, value)


def test_service_unknown_when_systemctl_fails():
    assert probes.fact_service(DEV, fake_run({'show': (1, '', 'kein Bus')})).level == probes.UNKNOWN


def _snapshot(live, service_level=probes.OK):
    facts = {'dienst': probes.Fact('dienst', 'Dienst', service_level, 'x')}
    return probes.Snapshot(DEV, facts, live, time.time())


@pytest.mark.parametrize('live,blocked', [
    ({'state': 'idle', 'diagnose_kopie': False}, False),
    ({'state': 'confirmed', 'diagnose_kopie': False}, False),
    ({'state': 'running', 'diagnose_kopie': False}, True),
    ({'state': 'setup_running', 'diagnose_kopie': False}, True),
    ({'state': 'stopped', 'diagnose_kopie': True}, True),
    (None, True),  # Laufstatus unbekannt: nicht stoppen
])
def test_stop_blocker_matches_service_script(live, blocked):
    assert (_snapshot(live).stop_blocker is not None) is blocked


def test_stopped_service_has_no_blocker():
    assert _snapshot(None, probes.OFF).stop_blocker is None


def test_run_fact_without_measurement_values():
    live = {'state': 'running', 'session_id': 'S1', 'output': {'transport': 'bridge_network'},
            'camera': {'frames': 123456}, 'run': {'valid': 99}}
    fact = probes.fact_run(live, probes.Fact('dienst', 'Dienst', probes.OK, 'läuft'))
    assert fact.value == 'Lauf aktiv'
    text = json.dumps(fact.to_json())
    assert '123456' not in text and '99' not in text


def test_camera_from_live_status_and_usb2_warning():
    service = probes.Fact('dienst', 'Dienst', probes.OK, 'läuft')
    live = {'camera': {'running': True, 'stalled': False, 'error': None,
                       'source': {'device': '/dev/video0', 'usb_id': '046d:0893', 'usb_speed_mbps': 480,
                                  'size': [1280, 720], 'fourcc': 'YUYV'}}}
    assert probes.fact_camera(live, service).level == probes.WARN
    live['camera']['source']['usb_speed_mbps'] = 5000
    assert probes.fact_camera(live, service).value == 'bereit'
    live['camera']['stalled'] = True
    assert probes.fact_camera(live, service).level == probes.FAIL


def test_camera_without_service_uses_usb(tmp_path):
    off = probes.Fact('dienst', 'Dienst', probes.OFF, 'gestoppt')
    assert probes.fact_camera(None, off, usb=lambda: None).level == probes.FAIL
    assert probes.fact_camera(None, off, usb=lambda: {'speed_mbps': 5000, 'port': '4-1'}).level == probes.OK


def test_usb_scan_reads_sysfs(tmp_path):
    device = tmp_path / '4-1'
    device.mkdir()
    (device / 'idVendor').write_text('046d\n')
    (device / 'idProduct').write_text('0893\n')
    (device / 'speed').write_text('5000\n')
    assert probes._usb_camera(tmp_path) == {'speed_mbps': 5000, 'port': '4-1'}


def test_uart_checks_boot_config_and_console(tmp_path):
    device = tmp_path / 'ttyAMA0'
    config, cmdline = tmp_path / 'config.txt', tmp_path / 'cmdline.txt'
    config.write_text('# dtparam=uart0=on\n')
    cmdline.write_text('console=tty1 root=/dev/x\n')
    assert probes.fact_uart(device, (config,), (cmdline,)).level == probes.WARN
    device.write_text('')
    config.write_text('dtparam=uart0=on\n')
    assert probes.fact_uart(device, (config,), (cmdline,)).level == probes.OK
    cmdline.write_text('console=ttyAMA0,115200 console=tty1\n')
    assert probes.fact_uart(device, (config,), (cmdline,)).value == 'Konsole belegt'


def test_templates_and_calibration(tmp_path):
    from dispread.live import DEFAULT_TEMPLATES_SHA256

    template = tmp_path / 't.json'
    template.write_text('{}')
    instance = Instance(kind='dev', unit=None, scope='user', templates=str(template),
                        calibration=str(tmp_path / 'fehlt.json'))
    assert probes.fact_templates(instance).value == 'verändert'
    assert DEFAULT_TEMPLATES_SHA256 != probes._sha256(template)
    calibration = probes.fact_calibration(instance)
    assert calibration.level == probes.FAIL and 'kein Messlauf' in calibration.hint


def test_storage_levels(tmp_path):
    instance = Instance(kind='dev', unit=None, scope='user', live_data=str(tmp_path))
    for free, level in ((5e9, probes.OK), (3e9, probes.WARN), (1e9, probes.FAIL)):
        live = {'storage': {'free_bytes': free, 'reserve_bytes': 2e9}}
        assert probes.fact_storage(instance, live).level == level


def test_collect_with_fake_sources_never_touches_socket():
    run = fake_run({'show dispread': (0, 'ActiveState=active\n', ''), 'loginctl': (0, 'yes\n', ''),
                    'timedatectl': (0, 'yes\n', ''), 'git': (0, 'v1.0.0\n', '')})
    snapshot = probes.collect(DEV, run=run, live_source=lambda: {'state': 'idle', 'diagnose_kopie': False},
                              bridge_source=lambda: None)
    assert snapshot.facts['lauf'].value == 'kein Lauf'
    assert snapshot.facts['zertifikat'].level == probes.FAIL  # Port 1 antwortet nicht
    data = snapshot.to_json()
    assert data['schema'] == 'picam.status/1' and data['overall'] == probes.FAIL


# ------------------------------------------------------------------ Dienst

def test_dev_plan_restarts_with_remembered_argv():
    dev = Instance(kind='dev', unit='dispread-werkbank-bruecke', scope='user', argv=['/py', '-m', 'x'],
                   workdir='/r', host='h', port=1)
    plan = service.plan('restart', dev, _snapshot({'state': 'idle', 'diagnose_kopie': False}))
    assert plan.commands[0] == ['systemctl', '--user', 'stop', 'dispread-werkbank-bruecke']
    assert plan.commands[1][:3] == ['systemd-run', '--user', '--unit=dispread-werkbank-bruecke']
    assert plan.commands[1][-3:] == ['/py', '-m', 'x'] and plan.blocker is None


def test_system_plan_uses_sudo_when_not_root(monkeypatch):
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    system = Instance(kind='system', unit='picam-werkbank.service', scope='system')
    assert service.plan('start', system).commands == [['sudo', 'systemctl', 'start', 'picam-werkbank.service']]


def test_running_measurement_blocks_stop_and_execute_refuses():
    plan = service.plan('stop', DEV, _snapshot({'state': 'running', 'diagnose_kopie': False}))
    assert plan.blocker
    calls = []
    ok, message = service.execute(plan, DEV, run=lambda c: calls.append(c) or 0, echo=lambda _: None)
    assert not ok and message.startswith('Gesperrt') and calls == []
    assert service.plan('stop', DEV, _snapshot({'state': 'running'}), force=True).blocker is None


def test_execute_stops_on_first_failure(monkeypatch):
    monkeypatch.setattr(service.subprocess, 'call', lambda *a, **k: 0)
    calls = []
    plan = service.Plan('restart', [['a'], ['b']])
    ok, message = service.execute(plan, Instance(kind='user', unit='u', scope='user'),
                                  run=lambda c: calls.append(c) or 3, echo=lambda _: None, recheck=lambda: None)
    assert not ok and calls == [['a']] and 'Exit 3' in message


def test_journal_parsing_levels_and_systemd_compaction():
    lines = [
        {'MESSAGE': 'Kamerastart', 'PRIORITY': '6', '__REALTIME_TIMESTAMP': '1763584299000000'},
        {'MESSAGE': 'Traceback (most recent call last):\n  File x', 'PRIORITY': '6',
         '__REALTIME_TIMESTAMP': '1763584300000000'},
        {'MESSAGE': 'warn: Speicher knapp', 'PRIORITY': '4', '__REALTIME_TIMESTAMP': '1763584301000000'},
        {'MESSAGE': 'Started picam-werkbank.service - [systemd-run] /py -m serve --a b.',
         'SYSLOG_IDENTIFIER': 'systemd', 'PRIORITY': '6', '__REALTIME_TIMESTAMP': '1763584302000000'},
        'kein json',
    ]
    text = '\n'.join(json.dumps(x) if isinstance(x, dict) else x for x in lines)
    parsed = service.parse_journal(text)
    assert [p.level for p in parsed] == ['info', 'fehler', 'info', 'warnung', 'info']
    assert parsed[-1].text == 'Dienst gestartet (picam-werkbank)'


# ------------------------------------------------------------------ Konfiguration

CONFIG = """# picam installer
[workbench]
pam_user = "labor"
host = "192.168.1.9"
port = 8080
bridge_endpoint = ["https://192.168.1.9:8080/bridge/v2"]

[live]
"""


def test_port_change_updates_endpoint_and_validates(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text(CONFIG)
    text, changes = configedit.propose(config, 'port', '8443')
    assert [c.key for c in changes] == ['port', 'bridge_endpoint']
    assert 'port = 8443' in text and 'https://192.168.1.9:8443/bridge/v2' in text
    assert config.read_text() == CONFIG  # erst apply schreibt
    configedit.apply(config, text)
    assert 'port = 8443' in config.read_text()
    assert not [p for p in tmp_path.iterdir() if p.name != 'config.toml']


@pytest.mark.parametrize('key,raw', [('port', '0'), ('port', 'abc'), ('host', '1.2.3.4'),
                                     ('bridge_discovery', 'vielleicht'), ('bridge_name', '')])
def test_invalid_or_locked_values_are_refused(tmp_path, key, raw):
    config = tmp_path / 'config.toml'
    config.write_text(CONFIG)
    with pytest.raises(ValueError):
        configedit.propose(config, key, raw)


def test_new_key_is_inserted_into_workbench_section(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text(CONFIG)
    text, changes = configedit.propose(config, 'bridge_discovery', 'ja')
    assert changes[0].old is None and changes[0].new is True
    workbench = text.split('[live]')[0]
    assert 'bridge_discovery = true' in workbench


# ------------------------------------------------------------------ CLI

def _collect_with(level):
    def collect(instance, include_setup=True, **_):
        facts = {k: probes.Fact(k, k.title(), probes.OK, 'gut') for k in probes.OVERVIEW + probes.SETUP}
        facts['speicher'] = probes.Fact('speicher', 'Speicher', level, 'x', hint='h', command='c')
        return probes.Snapshot(DEV, facts, {'state': 'idle', 'diagnose_kopie': False}, time.time())
    return collect


@pytest.mark.parametrize('level,code', [(probes.OK, 0), (probes.WARN, 2), (probes.FAIL, 1)])
def test_doctor_exit_codes(monkeypatch, capsys, level, code):
    monkeypatch.setattr(cli, 'discover', lambda *_: DEV)
    monkeypatch.setattr(probes, 'collect', _collect_with(level))
    assert cli.main(['--no-color', 'doctor']) == code
    out = capsys.readouterr().out
    assert ('→ c' in out) is (level != probes.OK)


def test_status_json_is_clean(monkeypatch, capsys):
    monkeypatch.setattr(cli, 'discover', lambda *_: DEV)
    monkeypatch.setattr(probes, 'collect', _collect_with(probes.OK))
    assert cli.main(['status', '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['schema'] == 'picam.status/1' and data['instance']['kind'] == 'dev'


def test_stop_during_run_exits_blocked(monkeypatch, capsys):
    monkeypatch.setattr(cli, 'discover', lambda *_: DEV)

    def running(instance, include_setup=True, **_):
        return _snapshot({'state': 'running', 'diagnose_kopie': False})
    monkeypatch.setattr(probes, 'collect', running)
    assert cli.main(['stop', '--yes']) == cli.EXIT_BLOCKED
    assert 'gesperrt' in capsys.readouterr().err


def test_ascii_output_has_no_unicode(monkeypatch, capsys):
    monkeypatch.setattr(cli, 'discover', lambda *_: DEV)
    monkeypatch.setattr(probes, 'collect', _collect_with(probes.WARN))
    cli.main(['status', '--ascii', '--no-color'])
    out = capsys.readouterr().out
    assert out.isascii() and '! Speicher' in out


def test_usage_error_exit_code():
    assert cli.main(['gibtsnicht']) == cli.EXIT_USAGE


def test_config_set_without_terminal_needs_yes(monkeypatch, tmp_path, capsys):
    config = tmp_path / 'config.toml'
    config.write_text(CONFIG)
    found = Instance(kind='portable', unit=None, scope='user', config=str(config))
    monkeypatch.setattr(cli, 'discover', lambda *_: found)
    monkeypatch.setattr('sys.stdin', open(os.devnull))
    assert cli.main(['config', 'set', 'port', '9000']) == cli.EXIT_ABORT
    assert 'port = 8080' in config.read_text()
    assert cli.main(['config', 'set', 'port', '9000', '--yes']) == 0
    assert 'port = 9000' in Path(config).read_text()


# ------------------------------------------------------------------ Review 20.11.

def test_stop_without_checked_run_state_is_blocked():
    assert service.plan('stop', DEV, None).blocker == 'Laufstatus noch nicht geprüft'
    assert service.plan('restart', dev_with_argv(), None, force=True).blocker is None
    assert service.plan('start', dev_with_argv(), None).blocker is None


def test_execute_rechecks_run_state_right_before_stopping():
    calls = []
    plan = service.plan('restart', dev_with_argv(), _snapshot({'state': 'idle', 'diagnose_kopie': False}))
    ok, message = service.execute(plan, dev_with_argv(), run=lambda c: calls.append(c) or 0, echo=lambda _: None,
                                  recheck=lambda: 'Lauf aktiv – erst in der Werkbank beenden')
    assert not ok and 'Lauf aktiv' in message and calls == []


def test_execute_reports_timeout_instead_of_crashing():
    def hang(command):
        raise service.subprocess.TimeoutExpired(command, 120)
    plan = service.Plan('start', [['systemctl', 'start', 'x']])
    ok, message = service.execute(plan, dev_with_argv(), run=hang, echo=lambda _: None)
    assert not ok and 'nicht abgeschlossen' in message


def dev_with_argv():
    return Instance(kind='dev', unit='dispread-werkbank-bruecke', scope='user', argv=['/py', '-m', 'x'],
                    workdir='/r', host='127.0.0.1', port=1)


def test_config_header_with_comment_and_multiline_array(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('[workbench] # vom Installer\nport = 8080\n')
    text, _ = configedit.propose(config, 'port', '8081')
    assert 'port = 8081' in text
    config.write_text('[workbench]\nhost = "h"\nport = 8080\nbridge_endpoint = [\n  "https://h:8080/bridge/v2",\n]\n')
    with pytest.raises(ValueError, match='mehrzeilig'):
        configedit.propose(config, 'port', '8081')


def test_shell_hints_are_quoted(monkeypatch):
    monkeypatch.setenv('USER', 'a b')
    fact = probes.fact_linger(Instance(kind='dev', unit='u', scope='user'),
                              run=lambda c, timeout=5.0: (0, 'no\n', ''))
    assert fact.command == "sudo loginctl enable-linger 'a b'"


def test_cleanup_lists_then_deletes_only_after_yes(monkeypatch, capsys):
    calls = []

    def socket_request(path, op, timeout=3.0, args=None):
        calls.append(args)
        return {'entries': [{'path': '/v/live/a/run-01', 'mb': 20.5}], 'total_mb': 20.5, 'failed': False}
    monkeypatch.setattr(cli, 'discover', lambda *_: DEV)
    monkeypatch.setattr(probes, 'socket_request', socket_request)
    monkeypatch.setattr('sys.stdin', open(os.devnull))
    assert cli.main(['aufraeumen']) == cli.EXIT_ABORT
    assert [c['execute'] for c in calls] == [False]
    assert cli.main(['aufraeumen', '--tage', '30', '--yes']) == 0
    assert calls[-1] == {'days': 30, 'diagnostics_only': False, 'execute': True}
    out = capsys.readouterr().out
    assert '1 Lauf, zusammen 20 MB' in out and '20 MB freigegeben' in out


def test_setup_walks_problems_and_runs_only_confirmed(monkeypatch, capsys):
    monkeypatch.setattr(cli, 'discover', lambda *_: DEV)
    monkeypatch.setattr(probes, 'collect', _collect_with(probes.WARN))
    ran = []
    monkeypatch.setattr(cli, 'run_hint_command', lambda command, instance: ran.append(command) or 0)
    monkeypatch.setattr('sys.stdin', open(os.devnull))
    assert cli.main(['--no-color', 'setup']) == cli.EXIT_WARN
    out = capsys.readouterr().out
    assert '1/1' in out and 'Befehl: c' in out and ran == []


def test_bridge_pairings_are_read_from_sqlite_store(tmp_path):
    from dispread.bridge.pairing import PairingStore

    bridge_dir = tmp_path / 'bridge'
    bridge_dir.mkdir()
    (bridge_dir / 'identity.json').write_text('{}')
    store = PairingStore(bridge_dir / 'pairing')
    instance = Instance(kind='dev', unit='u', scope='user', bridge_directory=str(bridge_dir))
    service_ok = probes.Fact('dienst', 'Dienst', probes.OK, 'läuft')
    assert probes.fact_bridge(instance, {'connected': False}, service_ok).value == 'nicht gekoppelt'
    offer = store.create_offer('network')
    store.redeem_offer(offer, 'labor-pc', 'network')
    fact = probes.fact_bridge(instance, {'connected': False}, service_ok)
    assert fact.value == 'gekoppelt' and ('Kopplungen', 'Netzwerk 1') in fact.detail


def test_network_detects_lost_address():
    out = json.dumps([{'ifname': 'lo', 'addr_info': [{'local': '127.0.0.1'}]},
                      {'ifname': 'eth0', 'addr_info': [{'local': '192.168.1.20'}]}])
    run = fake_run({'ip -j': (0, out, '')})
    here = Instance(kind='system', unit='u', scope='system', host='192.168.1.20')
    assert probes.fact_network(here, run).value == 'eth0'
    gone = Instance(kind='system', unit='u', scope='system', host='192.168.1.9')
    fact = probes.fact_network(gone, run)
    assert fact.level == probes.FAIL and 'DHCP' in fact.hint


def test_color_system_truecolor_when_terminal_does_not_say():
    from dispread.admin.cli import choose_color_system
    env = {'TERM': 'xterm-256color'}
    assert choose_color_system(env) == 'truecolor' and env['TEXTUAL_COLOR_SYSTEM'] == 'truecolor'
    assert choose_color_system({'TERM': 'xterm-256color', 'COLORTERM': 'truecolor'}) is None
    assert choose_color_system({'TERM': 'linux'}) is None
    assert choose_color_system({'TERM': 'xterm', 'NO_COLOR': '1'}) is None
    env = {'TERM': 'xterm-256color', 'PICAM_COLORS': '256'}
    assert choose_color_system(env) == '256'
    assert choose_color_system({'TERM': 'x', 'TEXTUAL_COLOR_SYSTEM': 'standard'}) is None


def test_socket_request_works_inside_running_event_loop(tmp_path, monkeypatch):
    """Regression raspi01: Laufprüfung vor sudo-Stopp lief im Textual-Loop, asyncio.run scheiterte."""
    import asyncio

    from dispread.workbench import cli as workbench_cli

    sock = tmp_path / 'control.sock'
    sock.write_text('')

    async def fake_request(op, args, socket_path=None):
        return {'state': 'idle', 'op': op}
    monkeypatch.setattr(workbench_cli, 'request', fake_request)

    async def inside_loop():
        return probes.socket_request(str(sock), 'live.status')
    assert asyncio.run(inside_loop()) == {'state': 'idle', 'op': 'live.status'}
    assert probes.socket_request(str(sock), 'live.status') == {'state': 'idle', 'op': 'live.status'}
