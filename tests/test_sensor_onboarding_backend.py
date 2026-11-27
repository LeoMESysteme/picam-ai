"""Vertrag der Werkzeug-CLI ohne Kamera, UART oder echten Assistenten."""

import json
import threading

import pytest


@pytest.mark.parametrize(('example', 'unit', 'sign', 'number', 'digits', 'decimal'), [
    ('+ 1.2345 mV/V', 'mV/V', (0,), tuple(range(1, 8)), 6, 'point'),
    ('-12.345 kg', 'kg', (0,), tuple(range(1, 7)), 5, 'point'),
    ('  0.4678 mV/V', 'mV/V', (), tuple(range(8)), 7, 'point'),
    ('123 kg', 'kg', (), (0, 1, 2), 3, 'none'),
])
def test_derive_display(example, unit, sign, number, digits, decimal):
    from dispread.sensors.formats import derive_display

    display = derive_display(example, unit)
    assert display.roles.sign == sign
    assert display.roles.number == number
    assert display.format.digits == digits
    assert display.format.decimal == decimal
    assert sorted(cell for role in display.roles.__slots__ for cell in getattr(display.roles, role)) == list(range(16))


@pytest.mark.parametrize('example', ['1.2.3 kg', '1.2kg', '1,2 kg', '12. kg', '+ x kg', '12 kg 3'])
def test_bad_example(example):
    from dispread.sensors.formats import derive_display

    with pytest.raises(ValueError):
        derive_display(example, 'kg')


def test_generic_parser():
    from dispread.ocr.dotmatrix import FORMAT_RULES
    from dispread.sensors.formats import derive_display

    parse = FORMAT_RULES['char_number_v1']
    display = derive_display('+ 1.2345 mV/V', 'mV/V', sign_chars='+-')
    assert parse('- 1.2345 ', display) == ('-1.2345', -1.2345)
    assert parse('+0.46783 ', display) == ('+0.46783', 0.46783)
    exact = derive_display('+ 1.2345 mV/V', 'mV/V', digits=5)
    assert parse('+0.46783 ', exact) is None
    for invalid in ('+ 0.123  ', '+ 0.1234X', '+ 0.12.4 ', '+  0.123 ', '  1.2345 '):
        assert parse(invalid, display) is None
    integer = derive_display(' 123 kg', 'kg')
    assert parse(' 123 ', integer) == ('123', 123.0)
    assert parse('12.3 ', integer) is None


@pytest.fixture(autouse=True)
def _feature_on(monkeypatch):
    """Onboarding und propose sind hinter dem Schalter [features]; hier zaehlt der Ablauf, nicht der Schalter."""
    monkeypatch.setattr('dispread.sensors.features.enabled', lambda instance: True)


@pytest.fixture
def state(tmp_path):
    from dispread.sensors.onboarding import RunDir

    config = tmp_path / 'config.toml'
    config.write_text('[workbench]\ndata = "state/workbench"\n')
    run = RunDir.create(tmp_path / 'state/sensor-onboarding', {
        'v': 1, 'name': 'Labor 01', 'manufacturer': 'Labor', 'display_family': 'hd44780_5x8',
        'example': '+ 0.4678 mV/V', 'unit': 'mV/V', 'connection': {'kind': 'none'}, 'assistant': 'none',
    })
    return config, run


def test_onboard_none(state, capsys):
    from dispread.admin.cli import main
    from dispread.live.session import LiveConfig
    from dispread.sensors import get_sensor, local_root
    from dispread.workbench.config import load_config

    config, run = state
    stopped = threading.Event()

    def answer():
        while not stopped.wait(0.01):
            for event in run.read_events():
                if event['type'] == 'question' and not run.answer_path(event['id']).exists():
                    run.write_answer(event['id'], event['options'][0]['value'] if event['kind'] == 'choice' else True)

    worker = threading.Thread(target=answer, daemon=True)
    worker.start()
    try:
        assert main(['--config', str(config), 'sensor', 'onboard', '--run', str(run.path),
                     '--source', 'synthetic://']) == 0
    finally:
        stopped.set()
        worker.join()
    result = json.loads(capsys.readouterr().out)
    assert result['sensor_id'] == 'labor-01'
    assert run.read_events()[-1]['type'] == 'done'
    assert (run.work_dir / 'capture.png').stat().st_size > 0
    workbench, live, _ = load_config(config)
    cfg = LiveConfig(**live, sensor_root=local_root(workbench))
    assert cfg.definition.status == 'provisional'
    assert cfg.definition.templates.sha256 == get_sensor().templates.sha256


def test_propose_check_activate(state, capsys):
    from dispread.admin.cli import main

    config, run = state
    prefix = ['--config', str(config), 'sensor']
    assert main([*prefix, 'propose', '--run', str(run.path), '--id', 'test-01']) == 0
    assert json.loads(capsys.readouterr().out)['sensor_id'] == 'test-01'
    assert main([*prefix, 'check', '--id', 'test-01', '--run', str(run.path)]) == 0
    assert json.loads(capsys.readouterr().out)['mode'] == 'static'
    assert main([*prefix, 'activate', '--id', 'test-01']) != 0
    assert main([*prefix, 'activate', '--id', 'test-01', '--accept-provisional']) == 0
    assert 'Neustart' in json.loads(capsys.readouterr().out)['message']
    assert main([*prefix, 'propose', '--run', str(run.path), '--id', 'test-02', '--sign-chars=+-']) != 0
    assert 'Ernte/Training' in capsys.readouterr().err
    assert main([*prefix, 'propose', '--run', str(run.path), '--id', 'test-02', '--example', '1.2345 mV/V']) != 0
    assert 'Zelle 0' in capsys.readouterr().err


def test_sniff_only_reads(monkeypatch):
    import serial

    from dispread.sensors import tools

    calls = []

    class FakeSerial:
        def __init__(self, **kwargs):
            assert kwargs['timeout'] <= 0.2
            assert kwargs['port'] is None
            calls.append(kwargs['baudrate'])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def open(self):
            assert self.port == '/dev/fake'
            assert self.dtr is False and self.rts is False

        def read(self, count):
            return b'+0.46780 mV/V\r\n'[:count]

        def write(self, data):
            pytest.fail('Sensor-Werkzeug hat auf die Schnittstelle geschrieben')

    times = iter(range(20))
    monkeypatch.setattr(serial, 'Serial', FakeSerial)
    monkeypatch.setattr(tools.time, 'monotonic', lambda: next(times))
    result = tools.sniff('/dev/fake', '9600,19200', 2)
    assert calls == [9600, 19200]
    assert [r['matches'] for r in result] == [{'gsv2as-161a': 1}] * 2
    assert result[0]['printable_fraction'] == 1


def test_capture_uses_workbench_preview(state, monkeypatch):
    import base64

    import cv2
    import numpy as np

    from dispread.admin.instance import discover
    from dispread.sensors import tools

    config, run = state
    inst = discover(str(config))
    socket = config.with_name('control.sock')
    socket.touch()
    inst.socket = str(socket)
    jpeg = cv2.imencode('.jpg', np.full((20, 30, 3), 180, np.uint8))[1].tobytes()

    def snapshot(path, op):
        assert (path, op) == (str(socket), 'live.snapshot')
        return {'camera_running': True, 'jpeg': base64.b64encode(jpeg).decode('ascii')}

    monkeypatch.setattr('dispread.admin.probes.socket_request', snapshot)
    monkeypatch.setattr('dispread.frames.open_source', lambda *a: pytest.fail('Kamera ist bereits belegt'))
    result = tools.capture(run, inst)
    assert result['source'] == 'werkbank'
    assert cv2.imread(result['path']).shape == (20, 30, 3)


@pytest.mark.parametrize('name', ['claude', 'codex'])
def test_agent_command_and_sandbox(state, monkeypatch, tmp_path, name):
    import os
    import shlex

    from dispread.sensors import agent

    _, run = state
    outside = tmp_path / 'verboten'
    fake = tmp_path / name
    fake.write_text(
        '#!/bin/sh\n'
        f'if (echo verbot > {shlex.quote(str(outside))}) 2>/dev/null; then exit 9; fi\n'
        'case "$*" in *--json*|*stream-json*) ;; *) exit 8;; esac\n'
        'read -r header\n'
        'case "$header" in *Sensor-Onboarding*) ;; *) exit 7;; esac\n'
        'python3 -c "import errno, socket\ntry: socket.socket(socket.AF_UNIX)\nexcept OSError as e: '
        'raise SystemExit(e.errno != errno.EACCES)\nelse: raise SystemExit(5)" || exit 5\n'
        'picam sensor log --run "$PWD" --text "über den Wrapper" || exit 6\n'
        'echo \'{"type":"item.completed","item":{"type":"agent_message","text":"Fake-Text"}}\'\n',
        encoding='utf-8',
    )
    fake.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path) + os.pathsep + os.environ['PATH'])

    from dispread.admin.instance import discover
    from dispread.admin.sensor_cli import _AgentTools

    config, _ = state
    broker = _AgentTools(run, discover(str(config)), run.request(), None)
    assert agent.run_agent(run, name, broker.serve, timeout=10) == 0, (run.path / 'agent.log').read_text()
    assert not outside.exists()
    assert [e['text'] for e in run.read_events() if e['type'] == 'log' and e['source'] == 'agent'] == [
        'über den Wrapper', 'Fake-Text']


def test_ai_onboarding_uses_confirmed_host_commands(state, monkeypatch, capsys, tmp_path):
    import os
    import time

    from dispread.admin.cli import main

    config, run = state
    fake = tmp_path / 'claude'
    fake.write_text(
        '#!/bin/sh\n'
        'if [ "$1" = --version ]; then echo "claude Test"; exit 0; fi\n'
        'if [ "$1" = auth ]; then echo \'{"loggedIn":true}\'; exit 0; fi\n'
        'picam sensor propose --run "$PWD" --id ki-test || exit 1\n'
        'picam sensor check --id ki-test --run "$PWD" || exit 1\n'
        'picam sensor activate --id ki-test --accept-provisional\n',
        encoding='utf-8',
    )
    fake.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path) + os.pathsep + os.environ['PATH'])
    stopped = threading.Event()

    def answer():
        deadline = time.monotonic() + 10
        while not stopped.wait(0.01) and time.monotonic() < deadline:
            for event in run.read_events():
                if event['type'] == 'question' and not run.answer_path(event['id']).exists():
                    run.write_answer(event['id'], event['options'][0]['value'] if event['kind'] == 'choice' else True)
        if not stopped.is_set():
            run.request_cancel()

    worker = threading.Thread(target=answer, daemon=True)
    worker.start()
    try:
        assert main(['--config', str(config), 'sensor', 'onboard', '--run', str(run.path),
                     '--assistant', 'claude']) == 0
    finally:
        stopped.set()
        worker.join()
    assert json.loads(capsys.readouterr().out)['activated'] is True
    assert [e['ok'] for e in run.read_events() if e['type'] == 'done'] == [True]


def test_generic_reader_rejects_bad_cells():
    from dataclasses import replace

    from dotmatrix_helpers import GRID, render, synthetic_reader

    from dispread.layout import CharLayout
    from dispread.sensors import get_sensor
    from dispread.sensors.formats import derive_display

    reader = synthetic_reader()
    sensor = replace(get_sensor(), display=derive_display('+ 0.4678 mV/V', 'mV/V'))
    layout = CharLayout.from_definition(sensor, GRID)
    assert reader.read(render('+ 0.4678 '), layout).value == 0.4678
    for invalid in ('+ 0.46781', '+ 0.467  ', '+ 0.4678     1', '+ 0..678 '):
        assert reader.read(render(invalid), layout).value is None
    integer = replace(sensor, display=derive_display('+123 N', 'N'), unit='N')
    read = reader.read(render('+123 '), CharLayout.from_definition(integer, GRID))
    assert read.value == 123 and read.decimal_point_detected is False


def test_dev_activation_uses_normal_start(tmp_path, state, monkeypatch, capsys):
    from dispread.admin.cli import main
    from dispread.admin.instance import _dev_from_argv
    from dispread.workbench.cli import parser
    from dispread.workbench.config import apply_config

    _, run = state
    argv = ['serve', '--data', str(tmp_path / 'anderer-standort/workbench')]
    instance = _dev_from_argv(argv, str(tmp_path))
    monkeypatch.setattr('dispread.admin.cli.discover', lambda _: instance)
    assert main(['sensor', 'propose', '--run', str(run.path), '--id', 'dev-sensor']) == 0
    assert main(['sensor', 'activate', '--id', 'dev-sensor', '--accept-provisional']) == 0
    assert apply_config(parser().parse_args(argv), argv).live_config.definition.id == 'dev-sensor'
    assert _dev_from_argv(argv, str(tmp_path)).sensor == 'dev-sensor'
    assert 'Neustart' in capsys.readouterr().out


def test_run_with_provisional_sensor_and_gsv_recording(state, tmp_path, capsys, monkeypatch):
    import asyncio
    import hashlib
    from dataclasses import replace

    import cv2
    from devdata_helpers import local_recording
    from test_live_session import FakeOwner, _files

    from dispread.admin.cli import main
    from dispread.detect.manual_roi import ManualRoiLocator
    from dispread.live.clock import ClockLog
    from dispread.live.service import LiveService
    from dispread.live.session import LiveConfig, LiveSession
    from dispread.records import ValueStatus
    from dispread.session_profile import SessionProfile
    from dispread.workbench.cli import parser
    from dispread.workbench.config import apply_config
    from dispread.workbench.server import handle_local_op

    image_path = local_recording('diagnostics/ab4-still/frames/frame_000016.png')
    old_profile = SessionProfile.load(local_recording('diagnostics/ab4-profile-regrid1.json'))
    image = cv2.imread(str(image_path))
    assert image is not None
    config, run = state
    _, files = _files(tmp_path)
    config.write_text(config.read_text() + f'\n[live]\ncalibration = "{files.calibration}"\n')
    prefix = ['--config', str(config), 'sensor']
    assert main([*prefix, 'propose', '--id', 'smoke-161a', '--run', str(run.path)]) == 0
    assert main([*prefix, 'activate', '--id', 'smoke-161a', '--accept-provisional']) == 0
    capsys.readouterr()
    argv = ['serve', '--config', str(config)]
    active = apply_config(parser().parse_args(argv), argv).live_config

    reference = {'path': str(image_path), 'sha256': hashlib.sha256(image_path.read_bytes()).hexdigest()}
    values = []
    profile_path = run.work_dir / 'profile.json'
    for cfg in (LiveConfig(calibration=active.calibration), active):
        replace(old_profile, device_id=cfg.definition.device_id, reference_frame=reference,
                confirmed_by='Rauchtest', offline=False).save(profile_path)
        owner = FakeOwner([image] * 2)
        session = LiveSession(owner, profile_path, cfg, tmp_path / cfg.definition.id,
                              locator_factory=lambda _, quad: ManualRoiLocator(tuple(map(tuple, quad))),
                              clock=ClockLog(measure=lambda: 0), output={'transport': 'off'})
        session.start()
        try:
            session.step()
            record = session.step()
            assert record.status is ValueStatus.VALID
            values.append((record.value, record.raw_text))
        finally:
            session.stop()
    assert values == [(0.4678, '+0.46780')] * 2
    metadata = json.loads((tmp_path / 'smoke-161a/session.json').read_text())
    assert metadata['sensor_status'] == metadata['audit']['sensor_status'] == 'provisional'
    service = LiveService(owner, tmp_path, config=active, diagnostic_staging_root=tmp_path)
    status = service.status()
    assert 'Vorläufiger Sensor' in status['release_notice']
    assert status['sensor_status'] == 'provisional'
    monkeypatch.setattr(service, '_profile_path', profile_path)

    async def inline(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr('dispread.workbench.server.asyncio.to_thread', inline)

    def confirmed(_path, op, args):
        assert (op, args) == ('live.snapshot', {'confirmed': True})
        response = asyncio.run(handle_local_op(op, args, None, service))
        assert response.status == 200
        return json.loads(response.text)

    monkeypatch.setattr('dispread.admin.probes.socket_request', confirmed)
    assert main([*prefix, 'capture', '--run', str(run.path), '--confirmed']) == 0
    assert json.loads(capsys.readouterr().out)['source'] == 'werkbank_bestaetigt'
    assert main([*prefix, 'check', '--id', 'smoke-161a', '--run', str(run.path)]) == 0
    assert json.loads(capsys.readouterr().out)['mode'] == 'reading'


def test_dev_data_alias_and_sibling_are_distinct(tmp_path, state):
    from dispread.admin.instance import _dev_from_argv
    from dispread.sensors import local_root, tools
    from dispread.workbench.cli import parser
    from dispread.workbench.config import apply_config

    _, run = state
    target = tmp_path / 'inst-a'
    target.mkdir()
    link = tmp_path / 'workbench'
    link.symlink_to(target, target_is_directory=True)
    argv = ['serve', '--data', str(link)]
    inst = _dev_from_argv(argv, str(tmp_path))
    tools.propose(run, inst, 'eins')
    tools.activate(inst, 'eins', True)

    args = apply_config(parser().parse_args(argv), argv)
    assert args.live_config.definition.id == 'eins'
    other = ['serve', '--data', str(tmp_path / 'inst-b')]
    assert not hasattr(apply_config(parser().parse_args(other), other), 'live_config')
    assert local_root(inst) == target / 'sensors'
    assert local_root(_dev_from_argv(other, str(tmp_path))) == tmp_path / 'inst-b/sensors'


def test_sniff_respects_workbench_reference_owner(state, tmp_path, monkeypatch):
    import serial

    from dispread.admin.instance import discover
    from dispread.sensors import tools

    config, _ = state
    instance = discover(str(config))
    ref = tmp_path / 'reference'
    ref.touch()
    alias = tmp_path / 'reference-alias'
    alias.symlink_to(ref)
    path = tmp_path / 'control.sock'
    path.touch()
    instance.socket = str(path)
    instance.reference_port = str(ref)
    monkeypatch.setattr('dispread.admin.probes.socket_request', lambda *a: {'state': 'running'})
    monkeypatch.setattr(serial, 'Serial', lambda *a, **kw: pytest.fail('Belegter Port wurde geöffnet'))
    with pytest.raises(ValueError, match='Referenzport'):
        tools.sniff(str(alias), instance=instance)


def test_agent_does_not_repeat_declined_activation(state, monkeypatch):
    import time

    from dispread.admin import sensor_cli
    from dispread.admin.instance import discover
    from dispread.sensors.onboarding import OnboardingCancelled

    config, run = state
    broker = sensor_cli._AgentTools(run, discover(str(config)), run.request(), None)
    broker.proposal = {'sensor_id': 'neu'}
    broker.checked = True
    questions = []

    def refuse(*args, **kwargs):
        questions.append(args)
        return None

    monkeypatch.setattr(sensor_cli, '_confirm_activation', refuse)
    args = ['sensor', 'activate', '--id', 'neu', '--accept-provisional']
    for _ in range(2):
        with pytest.raises(OnboardingCancelled, match='abgelehnt'):
            broker.execute(args, time.monotonic() + 1)
    assert len(questions) == 1


def test_ask_cancelled_exits_three(state, capsys):
    from dispread.admin.cli import main

    config, run = state
    run.request_cancel()
    assert main(['--config', str(config), 'sensor', 'ask', '--run', str(run.path),
                 '--kind', 'confirm', '--prompt', 'Übernehmen?']) == 3
    result = capsys.readouterr()
    assert not result.out
    assert 'abgebrochen' in result.err


def test_setup_reference_accepts_typed_value_for_char_number_package():
    from dispread.sensors import get_sensor
    from dispread.sensors.formats import derive_display, setup_reference

    base = get_sensor()
    display = derive_display('+ 0.1489 mV/V   ', 'mV/V')

    class Definition:
        unit = 'mV/V'

    Definition.display = display
    expected = '+ 0.1489 '
    for typed in ('0.1489', '+0.1489', '0,1489', '0.1489 mV/V', '+ 0.1489 mV/V', ' 0.1489'):
        assert setup_reference(typed, Definition) == expected, typed
    for bad in ('-0.1489', '12345.678', 'abc', '0.1489 kg'):
        with pytest.raises(ValueError):
            setup_reference(bad, Definition)
    assert base.id == 'gsv2as-161a'
