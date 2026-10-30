"""Live-Ausgabe ausschließlich mit pty/Fakes; niemals Hardware öffnen."""
import json
import threading
import time
from dataclasses import replace

import pytest
from dotmatrix_helpers import embed
from test_live_session import _session


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
                       output={'port': '/fake/output'}, **kwargs)
    session._config = replace(session._config, confirm_frames=1)
    return session


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
    finally:
        session.stop()
