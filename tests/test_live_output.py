"""Live-Ausgabe ausschließlich mit pty/Fakes; niemals Hardware öffnen."""
import json
import threading
import time
from dataclasses import replace

import pytest
from dotmatrix_helpers import embed
from test_live_service import FakeOwner
from test_live_session import _session

from dispread.live.service import LiveError, LiveService


def wait_receipts(session, count):
    path = session.records_path.parent / 'tx.jsonl'
    deadline = time.monotonic() + 3
    while True:
        lines = path.read_text().splitlines()
        if len(lines) >= count:
            return [json.loads(line) for line in lines]
        assert time.monotonic() < deadline
        time.sleep(.005)


class FakeSerial:
    out_waiting = 0

    def __init__(self, *args, **kwargs):
        assert kwargs['write_timeout'] == 1.0
        self.writes = []
        self.closed = False
        self.resets = 0

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def reset_output_buffer(self):
        self.resets += 1

    def flush(self):
        pytest.fail('Live-Ausgang darf nicht flushen')

    def close(self):
        self.closed = True


def make_session(tmp_path, monkeypatch, factory, **kwargs):
    monkeypatch.setattr('serial.Serial', factory)
    session = _session(tmp_path, [embed('+ 1.2345 ')] * 5,
                       output={'port': '/fake/output', 'acknowledge_unaccepted': True}, **kwargs)
    session._config = replace(session._config, confirm_frames=1)
    return session


def test_serial_session_records_missing_acceptance_and_acknowledgement(tmp_path, monkeypatch):
    session = make_session(tmp_path, monkeypatch, FakeSerial)
    session.start()
    try:
        output = json.loads(session.session_path.read_text())['output']
        assert output['acceptance'] == 'fehlt'
        assert output['acknowledged_unaccepted'] is True
        assert output['capabilities']['provisional'] is True
    finally:
        session.stop()
    output = json.loads(session.session_path.read_text())['output']
    assert output['acceptance'] == 'fehlt'
    assert output['acknowledged_unaccepted'] is True


def test_busy_output_drops_without_blocking_read_or_catchup(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    ports = []

    class SlowSerial(FakeSerial):
        def write(self, data):
            # Audit must exist before any transport access.
            assert (tmp_path / 'run/records.jsonl').read_text().splitlines()
            entered.set()
            assert release.wait(15)
            return super().write(data)

    def open_port(*args, **kwargs):
        port = SlowSerial(*args, **kwargs)
        ports.append(port)
        return port

    session = make_session(tmp_path, monkeypatch, open_port)
    session.start()
    try:
        session.step()
        assert entered.wait(3)
        session.step()
        session.step()
        assert not release.is_set()  # Reader progressed while transport is still stuck.
        assert session.latest.frame_sequence == 3
        assert ports[0].writes == []
        release.set()
        tx = wait_receipts(session, 3)
        assert sorted(r['frame_sequence'] for r in tx if r['dropped']) == [2, 3]
        assert all(r['omitted'] and r['drop_reason'] == 'output_busy' for r in tx if r['dropped'])
        session.step()
        wait_receipts(session, 4)
    finally:
        release.set()
        session.stop()
    assert ports[0].writes == [b'%+1.2345\r\n'] * 2
    assert ports[0].closed
    output = json.loads(session.session_path.read_text())['output']
    assert (output['sent'], output['omitted'], output['dropped'], output['errors']) == (2, 2, 2, 0)


def test_short_writes_finish_one_frame_before_accepting_another(tmp_path, monkeypatch):
    ports = []

    class PartialSerial(FakeSerial):
        def write(self, data):
            chunk = data[:2]
            self.writes.append(chunk)
            return len(chunk)

    def open_port(*args, **kwargs):
        port = PartialSerial(*args, **kwargs)
        ports.append(port)
        return port

    session = make_session(tmp_path, monkeypatch, open_port)
    session.start()
    try:
        for count in (1, 2):
            session.step()
            tx = wait_receipts(session, count)[-1]
            assert tx['bytes_written'] == len(b'%+1.2345\r\n')
            assert tx['t_complete_ns'] is not None and not tx['error']
        assert b''.join(ports[0].writes) == b'%+1.2345\r\n' * 2
        assert ports[0].resets == 0
    finally:
        session.stop()


@pytest.mark.parametrize('failure', ['timeout', 'error', 'no_progress', 'deadline', 'eagain'])
def test_transport_failure_latches_and_never_appends_a_frame(tmp_path, monkeypatch, failure):
    import serial

    ports = []

    class BrokenSerial(FakeSerial):
        def write(self, data):
            if not self.writes:
                self.writes.append(data[:2])
                return 2
            if failure == 'no_progress':
                return 0
            if failure == 'timeout':
                raise serial.SerialTimeoutException('blocked')
            if failure == 'eagain':
                raise BlockingIOError('would block')
            raise OSError('disconnected')

    def open_port(*args, **kwargs):
        port = BrokenSerial(*args, **kwargs)
        ports.append(port)
        return port

    session = make_session(tmp_path, monkeypatch, open_port)
    if failure == 'deadline':
        ticks = iter([0, 0, 2])
        monkeypatch.setattr('dispread.sink.serial_out.monotonic', lambda: next(ticks))
    session.start()
    try:
        session.step()
        tx = wait_receipts(session, 1)[0]
        session.step()
        following = wait_receipts(session, 2)[1]
        assert session.end_reason is None and session.latest.status.value == 'valid'
        status = session.output_status()
        assert status['sent'] == 0 and status['errors'] == 1 and not status['enabled']
        assert session.unified_output_status()['state'] == 'failed'
        assert session.unified_output_status()['last_ack'] is None
        assert not session._output._busy
        assert tx['error'] and tx['t_complete_ns'] is None
        assert tx['bytes_written'] == (2 if failure in ('no_progress', 'deadline', 'eagain') else None)
        assert 'confirmed_bytes_written=2' in tx['error']
        assert following['drop_reason'] == 'output_failed' and following['bytes_written'] == 0
        assert json.loads(session.session_path.read_text())['output']['first_error'] == tx['error']
        assert b''.join(ports[0].writes) == b'%+'  # A failed link cannot finish CRLF; never append a new prefix.
        assert ports[0].resets == 0
    finally:
        session.stop()
    assert json.loads(session.session_path.read_text())['output']['first_error'] == tx['error']
    assert session.unified_output_status()['state'] == 'failed'


def test_backlog_drops_new_frame_without_purging_previous(tmp_path, monkeypatch):
    port = FakeSerial(write_timeout=1.0)
    session = make_session(tmp_path, monkeypatch, lambda *a, **kw: port)
    session.start()
    try:
        session.step()
        wait_receipts(session, 1)
        port.out_waiting = 3
        session.step()
        tx = wait_receipts(session, 2)[1]
        assert tx['drop_reason'] == 'output_backlog' and tx['bytes_written'] == 0
        assert b''.join(port.writes) == b'%+1.2345\r\n'
        assert port.resets == 0 and session.output_status()['errors'] == 0
    finally:
        session.stop()


@pytest.mark.parametrize('where', ['emit', 'record'])
def test_unexpected_thread_exception_is_visible_and_clears_busy(tmp_path, monkeypatch, where):
    session = make_session(tmp_path, monkeypatch, FakeSerial)
    session.start()
    target = session._output._sink if where == 'emit' else session._output
    method = 'emit' if where == 'emit' else '_record'
    original = getattr(target, method)
    calls = []

    def broken(*args, **kwargs):
        if not calls:
            calls.append(1)
            raise RuntimeError('unexpected sender failure')
        return original(*args, **kwargs)

    monkeypatch.setattr(target, method, broken)
    try:
        session.step()
        tx = wait_receipts(session, 1)[0]
        assert 'unexpected sender failure' in tx['error']
        assert not session._output._busy and not session.output_status()['enabled']
        session.step()
        assert wait_receipts(session, 2)[1]['drop_reason'] == 'output_failed'
    finally:
        session.stop()


def test_audit_failure_prevents_output(tmp_path, monkeypatch):
    from dispread.live.session import AuditFailed

    session = make_session(tmp_path, monkeypatch, FakeSerial)
    session.start()
    original = session._sink.emit

    def failed(record):
        return replace(original(record), t_complete_ns=None)

    monkeypatch.setattr(session._sink, 'emit', failed)
    try:
        with pytest.raises(AuditFailed):
            session.step()
    finally:
        session.stop()
    assert (tmp_path / 'run/tx.jsonl').read_bytes() == b''


def test_unreadable_and_transition_use_omit_policy(tmp_path, monkeypatch):
    session = make_session(tmp_path, monkeypatch, FakeSerial)
    session._config = replace(session._config, confirm_frames=2)
    session._owner.items[1] = (2, embed('+ 1.2345 ') * 0 + 200)
    session.start()
    try:
        session.step()
        session.step()
        tx = wait_receipts(session, 2)
        assert all(r['omitted'] and not r['dropped'] and r['wire_bytes'] is None for r in tx)
        assert all(r.get('provisional') is True for r in tx)
    finally:
        session.stop()


def test_actual_reference_port_collision_rejected_before_output_open(tmp_path, monkeypatch):
    from dispread.live.session import StartRefused

    class Recorder:
        port = '/fake/output'

        def start(self):
            pass

        def stop(self):
            pass

        def status(self):
            return {'enabled': True}

    def forbidden(*args, **kwargs):
        pytest.fail('Ausgang darf den aktiven Referenzport nicht oeffnen')

    session = make_session(tmp_path, monkeypatch, forbidden, reference_recorder=Recorder())
    with pytest.raises(StartRefused, match='Referenz/Werteplan'):
        session.start()


@pytest.mark.parametrize('baudrate', [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600])
def test_documented_baudrates_are_accepted(baudrate):
    from dispread.live.output import validate_output

    assert validate_output({'port': '/fake/output', 'baudrate': baudrate}) == {
        'port': '/fake/output', 'baudrate': baudrate, 'prefix': '%', 'allow_reference_adapter': False,
    }


@pytest.mark.parametrize('baudrate', [2400, 4800])
def test_slow_baudrates_rejected(baudrate):
    from dispread.live.output import validate_output

    with pytest.raises(ValueError, match='33 ms'):
        validate_output({'port': '/fake/output', 'baudrate': baudrate})


@pytest.mark.parametrize('alias', [False, True])
def test_reference_adapter_usb_identity_and_override(tmp_path, alias):
    from dispread.live.output import validate_output

    root = tmp_path / 'sys'
    usb = root / 'devices/usb1/1-2'
    usb.mkdir(parents=True)
    (usb / 'idVendor').write_text('067b\n')
    (usb / 'idProduct').write_text('2303\n')
    device = usb / '1-2:1.0/ttyUSB1'
    device.mkdir(parents=True)
    tty = root / 'class/tty/ttyUSB1'
    tty.mkdir(parents=True)
    (tty / 'device').symlink_to(device)
    port = '/dev/ttyUSB1'
    if alias:
        link = tmp_path / 'by-id-reference'
        link.symlink_to(port)
        port = str(link)
    with pytest.raises(ValueError, match='067b:2303'):
        validate_output({'port': port}, sysfs_root=root)
    options = {'port': port, 'allow_reference_adapter': True}
    assert validate_output(options, sysfs_root=root)['allow_reference_adapter'] is True
    with pytest.raises(ValueError, match='Referenz/Werteplan'):
        validate_output(options, reference_port='/dev/ttyUSB1', sysfs_root=root)
    (usb / 'idProduct').write_text('9999')
    assert validate_output({'port': port}, sysfs_root=root)


@pytest.mark.parametrize('value', [1, 'true', None])
def test_reference_adapter_override_requires_bool(value):
    from dispread.live.output import validate_output

    with pytest.raises(ValueError, match='allow_reference_adapter'):
        validate_output({'port': '/fake/output', 'allow_reference_adapter': value})


@pytest.mark.parametrize('open_fails', [False, True])
def test_output_open_precedes_reference_and_failed_open_never_starts_or_restores(tmp_path, monkeypatch, open_fails):
    from dispread.live.session import StartRefused

    events = []

    class Recorder:
        port = '/fake/reference'

        def start(self):
            events.append('reference-start')

        def stop(self):
            events.append('reference-stop')

        def status(self):
            return {'enabled': True}

    def open_port(*args, **kwargs):
        events.append('output-open')
        if open_fails:
            raise OSError('open failed')
        return FakeSerial(*args, **kwargs)

    session = make_session(tmp_path, monkeypatch, open_port, reference_recorder=Recorder())
    if open_fails:
        with pytest.raises(StartRefused, match='open failed'):
            session.start()
        assert events == ['output-open']
    else:
        session.start()
        assert events == ['output-open', 'reference-start']
        session.stop()
        assert events[-1] == 'reference-stop'


def test_live_length_budget_is_enforced_before_writing(tmp_path, monkeypatch):
    from test_userdefined_formatter import record

    from dispread.live.output import MAX_TELEGRAM_BYTES

    port = FakeSerial(write_timeout=1.0)
    session = make_session(tmp_path, monkeypatch, lambda *a, **kw: port)
    session.start()
    try:
        session._output.submit(record('0000000000000001', 1.0))
        tx = wait_receipts(session, 1)[0]
        assert tx['bytes_written'] == MAX_TELEGRAM_BYTES == 19
        assert b''.join(port.writes) == b'%0000000000000001\r\n'
        session._output.submit(record('00000000000000001', 1.0))
        tx = wait_receipts(session, 2)[1]
        assert tx['error'] and tx['bytes_written'] == 0 and tx['t_complete_ns'] is None
        assert len(port.writes) == 1 and not session.output_status()['enabled']
    finally:
        session.stop()


def test_reference_identity_is_rechecked_at_start(tmp_path, monkeypatch):
    from dispread.live.session import StartRefused

    session = make_session(tmp_path, monkeypatch, FakeSerial)
    root = tmp_path / 'sys'
    device = root / 'class/tty/output/device'
    device.mkdir(parents=True)
    (device / 'idVendor').write_text('067b')
    (device / 'idProduct').write_text('2303')
    monkeypatch.setattr('dispread.live.output.SYSFS_ROOT', root)
    monkeypatch.setattr('serial.Serial', lambda *a, **kw: pytest.fail('Protected adapter opened'))
    with pytest.raises(StartRefused, match='067b:2303'):
        session.start()


def test_unexpected_audit_exception_latches_without_stopping_reader(tmp_path, monkeypatch):
    session = make_session(tmp_path, monkeypatch, FakeSerial)
    session.start()
    session._output._stream.close()  # write() now raises ValueError, not OSError.
    try:
        session.step()
        deadline = time.monotonic() + 3
        while not session.output_status()['errors']:
            assert time.monotonic() < deadline
            time.sleep(.005)
        session.step()
        assert session.latest.frame_sequence == 2 and session.end_reason is None
        assert not session.output_status()['enabled'] and not session._output._busy
        assert session.unified_output_status()['state'] == 'audit_failed'
    finally:
        session.stop()


class Publisher:
    def __init__(self, config, out_dir):
        self.config, self.out_dir = config, out_dir
        self.started = self.stopped = False
        self.records = []

    def start(self):
        self.started = True

    def publish(self, record):
        # This fails if publication precedes the mandatory audit.
        lines = (self.out_dir / "records.jsonl").read_text().splitlines()
        assert json.loads(lines[-1]) == record.to_dict()
        self.records.append(record)

    def stop(self):
        self.stopped = True

    def status(self):
        return {"transport": self.config.transport, "state": "disconnected", "release_block": "Windows-Abnahme fehlt",
                "error": None, "last_ack": None, "ack_scope": "COM driver write, not GSVmulti reception"}

    def metadata(self):
        return {"config": self.config.to_dict(), "provisional": True}


def test_publish_follows_audit_and_stop_closes_output(tmp_path):
    from dispread.gsv_transport import OutputConfig

    session = _session(tmp_path, [embed("+ 1.2345 "), embed("+ 1.2345 ")],
                       output=OutputConfig.from_dict({"transport": "tcp"}), output_factory=Publisher)
    session.start()
    assert session._output.started
    session.step()
    session.step()
    assert len(session._output.records) == 2
    assert session.output_status()["state"] == "disconnected"
    assert session.end_reason is None
    assert session._sink.max_bytes == 0
    session.stop()
    assert session._output.stopped
    data = json.loads(session.session_path.read_text())
    assert data["output"]["provisional"] is True
    assert data["output"]["status"]["state"] == "disconnected"


def test_failed_audit_does_not_publish_record(tmp_path, monkeypatch):
    from dispread.gsv_transport import OutputConfig
    from dispread.live.session import AuditFailed
    from dispread.records import TxReceipt

    session = _session(tmp_path, [embed("+ 1.2345 ")],
                       output=OutputConfig.from_dict({"transport": "tcp"}), output_factory=Publisher)
    session.start()
    monkeypatch.setattr(session._sink, "emit", lambda record: TxReceipt(record.frame_sequence, 1, "jsonl", None, 0, None))
    with pytest.raises(AuditFailed):
        session.step()
    assert session._output.records == []
    session.stop()
    assert session._output.stopped


def test_test_override_refuses_external_output_before_creating_run(tmp_path):
    service = LiveService(FakeOwner(), tmp_path)
    service._state = "confirmed"
    service._profile_path = tmp_path / "profile.json"
    service._run_block = "Gegenlesen fehlt"
    with pytest.raises(LiveError, match="Testlauf"):
        service.start_run(test_override=True, reference=False, output={"transport": "tcp"})
    assert not list(tmp_path.glob("run-*"))


def test_invalid_output_is_live_error_before_creating_run(tmp_path):
    service = LiveService(FakeOwner(), tmp_path)
    with pytest.raises(LiveError):
        service.start_run(output={"transport": "unknown"})
    assert not list(tmp_path.glob("run-*"))


def test_late_start_metadata_failure_closes_audit_and_output(tmp_path, monkeypatch):
    from dispread.gsv_transport import OutputConfig

    session = _session(tmp_path, [], output=OutputConfig.from_dict({"transport": "tcp"}),
                       output_factory=Publisher)
    write = session._write_session
    calls = []

    def fail_second_write(*, ended):
        calls.append(ended)
        if len(calls) == 2:
            raise OSError("Metadaten voll")
        return write(ended=ended)

    monkeypatch.setattr(session, "_write_session", fail_second_write)
    with pytest.raises(OSError, match="Metadaten voll"):
        session.start()
    assert session._output.stopped
    assert session._sink._fh is None


OUTPUT_CASES = [
    ({'port': '/fake/output', 'acknowledge_unaccepted': True}, 'serial'),
    ({'transport': 'serial', 'port': '/fake/output', 'prefix': '#', 'baudrate': 9600,
      'acknowledge_unaccepted': True}, 'serial'),
    ({'transport': 'uart'}, 'uart'),
    ({'transport': 'tcp', 'tcp_port': 5001}, 'tcp'),
    (None, 'off'),
    ({'transport': 'off'}, 'off'),
]


@pytest.mark.parametrize('config,transport', OUTPUT_CASES)
def test_unified_service_output_contract(tmp_path, monkeypatch, config, transport):
    monkeypatch.setattr('serial.Serial', FakeSerial)
    from dispread.bridge.hub import BridgeHub
    service = LiveService(FakeOwner(), tmp_path, bridge_hub=BridgeHub('pi', tmp_path / 'audit'))
    service._state, service._profile_path = 'confirmed', tmp_path / 'profile.json'

    def factory(owner, profile, settings, out_dir, **kwargs):
        kwargs.pop('output_factory', None)  # contract fixture uses its controlled publisher
        return _session(tmp_path, [], out_dir=out_dir, output_factory=Publisher, **kwargs)

    monkeypatch.setattr('dispread.live.service.LiveSession', factory)
    try:
        service.start_run(reference=False, output=config)
        status = service.status()
        output = status['output']
        assert output['transport'] == transport
        if transport == 'off':
            assert output == {'transport': 'off', 'state': 'off'}
            assert 'output' not in status['run']
        else:
            assert {'transport', 'state', 'config', 'error', 'release_block'} <= output.keys()
            assert {'last_ack', 'ack_scope', 'acceptance'} <= output.keys()
            assert output['acceptance'] == 'fehlt'
            assert output['config']['transport'] == transport
            if transport == 'serial':
                assert status['run']['output'] == service._session.output_status()
                assert 'state' not in status['run']['output']
                assert output['state'] == 'serial_ready'
                assert output['last_ack'] is None
                assert output['ack_scope'] == 'lokale Annahme'
                assert output['release_note'] == (
                    'Prototyp – nicht am Windows-PC abgenommen, keine Messfreigabe. '
                    'Ungültige Werte werden ausgelassen; GSVmulti zeigt dann den letzten Wert unmarkiert weiter.')
                assert status['run']['output']['prefix'] == (config or {}).get('prefix', '%')
            else:
                assert output['state'] == 'disconnected'
                assert output['release_block']
    finally:
        service.stop_run()
    if transport == 'serial':
        assert service.status()['output']['state'] == 'stopped'


@pytest.mark.parametrize('config,transport', OUTPUT_CASES[:4])
def test_all_external_transports_reject_test_override_before_side_effects(tmp_path, monkeypatch, config, transport):
    service = LiveService(FakeOwner(), tmp_path)
    service._state, service._profile_path = 'confirmed', tmp_path / 'profile.json'
    monkeypatch.setattr('serial.Serial', lambda *a, **kw: pytest.fail('Kein Portzugriff im Testlauf'))
    with pytest.raises(LiveError, match='^Testlauf erlaubt keine externe Ausgabe$'):
        service.start_run(test_override=True, reference=False, output=config)
    assert not list(tmp_path.iterdir())
    assert service._owner.restarts == 0


@pytest.mark.parametrize('config,transport', OUTPUT_CASES[:4])
def test_session_also_rejects_external_output_for_test_run(tmp_path, config, transport):
    from dispread.live.session import StartRefused

    with pytest.raises(StartRefused, match='^Testlauf erlaubt keine externe Ausgabe$'):
        _session(tmp_path, [], test_run={'testlauf': True}, output=config, output_factory=Publisher)


def test_no_run_reports_output_off(tmp_path):
    assert LiveService(FakeOwner(), tmp_path).status()['output'] == {'transport': 'off', 'state': 'off'}


@pytest.mark.parametrize('config', [
    {'transport': 'unknown'}, {'transport': None}, {'transport': ['serial']},
])
def test_unknown_transport_has_german_live_error(tmp_path, config):
    with pytest.raises(LiveError, match='Unbekannter Ausgabeweg'):
        LiveService(FakeOwner(), tmp_path).start_run(output=config)


@pytest.mark.parametrize('config', [
    {'transport': 'serial', 'port': '/dev/serial0'},
    {'transport': 'serial', 'port': '/dev/ttyUSB0'},
    {'transport': 'serial', 'port': '/fake/output', 'unknown': True},
    {'transport': 'uart', 'serial_port': '/dev/ttyUSB0'},
    {'transport': 'tcp', 'tcp_port': 0},
])
def test_explicit_transports_keep_existing_validation_locks(tmp_path, config):
    with pytest.raises(LiveError):
        LiveService(FakeOwner(), tmp_path).start_run(output=config)


@pytest.mark.parametrize('config,transport', OUTPUT_CASES)
def test_ui_fake_accepts_unified_output_without_losing_scenes(tmp_path, config, transport):
    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'preview.png')
    service.start_run(reference=False, output=config, diagnostics=True)
    status = service.status(full=True)
    assert status['state'] == 'running' and status['run']['latest']['status'] == 'valid'
    assert status['output']['transport'] == transport
    assert status['diagnostics']['enabled']
    assert status['cause_texts']
    assert status['setup']['grid']['quad']
    assert 'latest' in status['reference']
    service.stop_run()
    assert service.status()['output']['state'] == ('off' if transport == 'off' else 'stopped')


@pytest.mark.parametrize('config,transport', OUTPUT_CASES[:4])
def test_ui_fake_rejects_output_for_test_run_before_scene_change(tmp_path, config, transport):
    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'preview.png')
    before = service.status()
    with pytest.raises(LiveError, match='^Testlauf erlaubt keine externe Ausgabe$'):
        service.start_run(test_override=True, output=config)
    assert service.status() == before


@pytest.mark.parametrize('text,value', [
    ('+ 1.7643', 1.7643), ('-012.50', -12.5), ('0', 0.0),
    ('-0.000', -0.0), ('+000.00', 0.0), (' 12 3.45 ', 123.45),
    ('+0.12345', 0.12345), ('0.10000000000000001', 0.1),
])
def test_formatter_contracts_are_distinct_over_existing_fixtures(text, value):
    from test_userdefined_formatter import record

    from dispread.sink.protocol.user_defined import UserDefinedFormatter as BridgeFormatter
    from dispread.sink.protocol.userdefined import UserDefinedFormatter as DirectFormatter

    item = replace(record(text, value), unit='mV/V')
    direct, bridge = DirectFormatter(), BridgeFormatter()
    if ' ' in text or text == '0':
        assert direct.format(item) == ('%' + text.replace(' ', '') + '\r\n').encode('ascii')
        with pytest.raises(ValueError):
            bridge.format(item)
    elif text == '0.10000000000000001':
        assert direct.format(item) is None
        assert bridge.format(item) == b'%0.10000000000000001\r\n'
    else:
        assert direct.format(item) == bridge.format(item) == ('%' + text + '\r\n').encode('ascii')


@pytest.mark.parametrize('stop_fails', [False, True])
def test_bridge_stop_runs_once_and_always_closes_audit(tmp_path, stop_fails):
    class ClosingPublisher(Publisher):
        stops = 0

        def stop(self):
            self.stops += 1
            if stop_fails:
                raise OSError('Ausgabeabschluss fehlgeschlagen')
            super().stop()

    session = _session(tmp_path, [], output={'transport': 'tcp'}, output_factory=ClosingPublisher)
    session.start()
    if stop_fails:
        with pytest.raises(OSError, match='Ausgabeabschluss'):
            session.stop()
    else:
        session.stop()
    assert session._output.stops == 1
    assert session._sink._fh is None
    assert session._stopped


@pytest.mark.parametrize('transport', ['uart', 'tcp'])
def test_explicit_legacy_v1_demo_publisher_keeps_dut_lock(tmp_path, monkeypatch, transport):
    from dispread.gsv_transport import RELEASE_BLOCK, OutputPublisher

    # Echte Publisher-Logik und Audit, aber kein Port oder Socket im Test.
    monkeypatch.setattr(OutputPublisher, '_worker', lambda self: None)
    session = _session(tmp_path, [embed('+ 1.2345 ')], output={'transport': transport},
                       output_factory=OutputPublisher)
    session._config = replace(session._config, confirm_frames=1)
    session.start()
    try:
        item = session.step()
        assert item.status.value == 'valid'
        assert json.loads(session.records_path.read_text()) == item.to_dict()
        output = session.unified_output_status()
        assert output['config']['transport'] == transport
        assert output['error'] is None and output['last_ack'] is None
        assert output['release_block'] == RELEASE_BLOCK
        reply = session._output.handle({'version': 1, 'type': 'poll', 'request_id': 'dut'})
        assert reply['type'] == 'idle' and 'record' not in reply
        assert reply['release_block'] == RELEASE_BLOCK
    finally:
        session.stop()
    data = json.loads(session.session_path.read_text())['output']
    assert data['formatter']['provisional'] is True
    assert data['release_block'] == RELEASE_BLOCK


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('ack', ['missing', False, None, 1, 'true'])
@pytest.mark.parametrize('fake', [False, True])
def test_serial_requires_explicit_ack_before_start(tmp_path, monkeypatch, legacy, ack, fake):
    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'preview.png') if fake else LiveService(FakeOwner(), tmp_path)
    before = service.status()
    files_before = list(tmp_path.iterdir())
    config = {'port': '/fake/output'}
    if not legacy:
        config['transport'] = 'serial'
    if ack != 'missing':
        config['acknowledge_unaccepted'] = ack
    monkeypatch.setattr('serial.Serial', lambda *a, **kw: pytest.fail('Kein Portzugriff ohne Bestaetigung'))
    with pytest.raises(LiveError, match='^Ausgabe: UART direkt ist nicht abgenommen – Hinweis bestätigen$'):
        service.start_run(reference=False, output=config)
    after = service.status()
    assert after['run'] is before['run'] is None
    if fake:
        # Nur Startfolgen vergleichen, keine zeitabhaengigen Vorschauwerte.
        keys = ('state', 'error', 'output', 'session_id', 'test_run')
        assert {key: after[key] for key in keys} == {key: before[key] for key in keys}
    else:
        # Freier Plattenplatz kann sich durch parallele Tests aendern.
        assert {key: value for key, value in after.items() if key != 'storage'} == {
            key: value for key, value in before.items() if key != 'storage'}
        assert service._owner.restarts == 0
    assert list(tmp_path.iterdir()) == files_before


@pytest.mark.parametrize('config,transport', OUTPUT_CASES)
def test_fake_output_status_matches_real_transport_keys(tmp_path, monkeypatch, config, transport):
    from live_ui_server import FakeLiveService

    from dispread.gsv_transport import OutputPublisher

    monkeypatch.setattr('serial.Serial', FakeSerial)
    session = _session(tmp_path, [], output=config)
    fake = FakeLiveService(tmp_path / 'preview.png')
    fake.start_run(reference=False, output=config)
    real_status, fake_status = session.unified_output_status(), fake.status()['output']
    assert fake_status.keys() == real_status.keys()
    assert fake_status == real_status
    if transport in ('uart', 'tcp'):
        assert real_status['state'] == 'waiting'
        assert real_status['ack_scope'] == 'COM driver write, not GSVmulti reception'
        assert real_status['acceptance'] == 'fehlt'
        # G1 ergaenzt Konfiguration/Abnahmestand, die Bruecke selbst bleibt unveraendert.
        assert OutputPublisher(session._output.config, tmp_path).status().keys() == (
            real_status.keys() - {'config', 'acceptance'})


def test_serial_last_ack_records_only_completed_driver_writes(tmp_path, monkeypatch):
    from test_userdefined_formatter import record

    from dispread.records import ValueStatus

    session = make_session(tmp_path, monkeypatch, FakeSerial)
    session.start()
    try:
        assert session.unified_output_status()['last_ack'] is None
        session.step()
        receipt = wait_receipts(session, 1)[0]
        ack = session.unified_output_status()['last_ack']
        assert ack == {'frame_sequence': 1, 'tx_sequence': 1, 'bytes_written': 10,
                       't_complete_ns': receipt['t_complete_ns'], 'time_base': 'host_monotonic',
                       'uncertainty_ns': None}
        assert session.unified_output_status()['ack_scope'] == 'lokale Annahme'
        session._output.submit(record('0', None, status=ValueStatus.UNREADABLE))
        wait_receipts(session, 2)
        assert session.unified_output_status()['last_ack'] == ack
    finally:
        session.stop()


def test_formatter_comparison_includes_bridge_fixtures():
    from test_gsv_transport import record

    from dispread.records import InvalidValuePolicy, ValueStatus
    from dispread.sink.protocol.user_defined import UserDefinedFormatter as BridgeFormatter
    from dispread.sink.protocol.userdefined import UserDefinedFormatter as DirectFormatter

    direct, bridge = DirectFormatter(), BridgeFormatter()
    assert direct.format(record()) == bridge.format(record()) == b'%+0.12345\r\n'
    assert direct.format(record(status=ValueStatus.UNREADABLE)) is None
    assert bridge.format(record(status=ValueStatus.UNREADABLE)) is None
    mismatch = replace(record(), value=0.2)
    assert direct.format(mismatch) is None
    with pytest.raises(ValueError):
        bridge.format(mismatch)
    for raw in ['1e2', '1_0', ' NaN', '1\n2', '+inf', '+0.12345 ']:
        item = replace(record(), raw_text=raw)
        with pytest.raises(ValueError):
            bridge.format(item)
        assert direct.format(item) == (b'%+0.12345\r\n' if raw == '+0.12345 ' else None)
    invalid = record(status=ValueStatus.UNREADABLE)
    assert direct.format(invalid) is None
    assert BridgeFormatter(invalid_policy=InvalidValuePolicy.SEND_NAN, demo=True).format(invalid) == b'%NaN\r\n'


def test_standalone_session_refuses_unconfigured_paired_output(tmp_path, monkeypatch):
    from dispread.gsv_transport import OutputPublisher
    from dispread.live.session import StartRefused
    # RED guard: do not permit the old default to open a raw test listener.
    monkeypatch.setattr(OutputPublisher, '_worker', lambda self: None)
    session = _session(tmp_path, [], output={'transport': 'tcp'})
    with pytest.raises(StartRefused, match='hub is not configured'):
        session.start()


def test_paired_client_loss_keeps_camera_and_record_audit_running(tmp_path):
    from dispread.bridge.hub import BridgeHub
    from dispread.bridge.publisher import PairedOutputPublisher
    now = [0.0]
    hub = BridgeHub('pi', tmp_path / 'bridge', clock=lambda: now[0])
    hub.reserve_real_run('real-run')
    session = _session(tmp_path, [embed('+ 1.2345 ')] * 3, output={'transport': 'tcp'},
                       output_factory=lambda config, out_dir: PairedOutputPublisher(
                           config, out_dir, hub=hub, run_id='real-run'))
    session.bridge_run_id = 'real-run'
    session._config = replace(session._config, confirm_frames=1)
    session.start()
    lease = hub.attach('pc', 'network')
    try:
        assert session.step().status.value == 'valid'
        now[0] = 5.0
        assert session.step().status.value == 'valid'
        with pytest.raises(ValueError, match='expired'):
            hub.exchange(lease.lease_id, dict(version=2, type='heartbeat', request_id='beat', pi_id='pi',
                         client_id='pc', lease_id=lease.lease_id, run_id='real-run'))
        assert session.step().status.value == 'valid'
        records = [json.loads(line) for line in session.records_path.read_text().splitlines()]
        assert len(records) == 3
        assert session._output._latest.frame_sequence == records[-1]['frame_sequence']
        assert session._output._pending is None
        assert session.unified_output_status()['release_block']
    finally:
        session.stop()
        hub.release_real_run('real-run')
        hub.close()
    assert json.loads(session.session_path.read_text())['run_id'] == 'real-run'
