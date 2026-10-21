import json
import threading
import time
from collections import deque

import pytest

from dispread.gsv2as_serial import _apply_norm_dpoint, _encode_norm
from dispread.live.reference import ReferenceRecorder


class FakePort:
    def __init__(self, lines=()):
        self.lines = deque(lines)
        self.closed = False
        self.writes = []
        self.timeout = 0.01

    def readline(self):
        if self.lines:
            return self.lines.popleft()
        time.sleep(0.005)
        return b''

    def close(self):
        self.closed = True

    def write(self, data):
        self.writes.append(data)

    def flush(self):
        pass

    def reset_input_buffer(self):
        pass

    def read(self, count):
        return b';\xa0'[:count]


def test_read_only_discards_initial_fragment_and_counts_bad_lines(tmp_path):
    port = FakePort([b'partial\r\n', b'+01.2345 mV/V\r\n', b'bad\r\n', b'+02.3456 mV/V\r\n'])
    ticks = iter([100, 200, 1_100_000_201])
    recorder = ReferenceRecorder(lambda: port, tmp_path / 'reference.jsonl', clock=lambda: next(ticks))
    recorder.start()
    deadline = time.monotonic() + 1
    while recorder.status()['lines'] < 3 and time.monotonic() < deadline:
        time.sleep(0.005)
    start = time.monotonic()
    result = recorder.stop()
    assert time.monotonic() - start < 2
    assert port.closed and port.writes == []
    assert result['lines'] == 3 and result['parse_errors'] == 1 and result['gaps'] == 1
    rows = [json.loads(line) for line in (tmp_path / 'reference.jsonl').read_text().splitlines()]
    assert rows[0] == {'t_boottime_ns': 100, 'raw': '+01.2345 mV/V', 'cell_text': '+ 1.2345 ', 'value': 1.2345}
    assert rows[1]['raw'] == 'bad' and rows[1]['cell_text'] is None and rows[1]['value'] is None
    assert rows[1]['error'] and rows[1]['t_boottime_ns'] == 200
    assert recorder.latest() == rows[-1]


def test_shared_encoding_preserves_original_bytes_and_waits(monkeypatch):
    waits = []
    monkeypatch.setattr('dispread.gsv2as_serial._sleep', waits.append)
    port = FakePort()
    norm, dp = _encode_norm(1.0)
    assert norm == (0x50, 0x1B, 0xE4) and dp == 1
    import io
    assert _apply_norm_dpoint(port, norm, dp, io.StringIO(), {}, label='test')
    assert port.writes == [b'#', b'%', b'\x10\x50\x1b\xe4', b'B', b'\x11\x01', b'B', b'$']
    assert waits == [0.25, 0.15, 0.35, 0.35, 0.7]


def test_open_failure_and_no_telegrams_disable_reference(tmp_path):
    def missing():
        raise OSError('Port fehlt')
    recorder = ReferenceRecorder(missing, tmp_path / 'a.jsonl')
    recorder.start()
    assert recorder.stop()['enabled'] is False
    assert 'Port fehlt' in recorder.status()['reason']
    port = FakePort()
    recorder = ReferenceRecorder(lambda: port, tmp_path / 'b.jsonl', startup_timeout_s=0.03)
    recorder.start()
    assert recorder.status()['enabled'] is False
    assert port.closed and not port.writes


@pytest.mark.parametrize('schedule', [[(0.1, 1)], [(1, 0)], [(1, float('nan'))], []])
def test_invalid_schedule_rejected_before_open(tmp_path, schedule):
    with pytest.raises(ValueError):
        ReferenceRecorder(lambda: pytest.fail('Port geoeffnet'), tmp_path / 'a', norm_schedule=schedule)


class RegisterPort(FakePort):
    def __init__(self):
        super().__init__([b'partial\n', b'+01.2345 mV/V\n'])
        self.norm, self.dp = [80, 27, 228], 1
        self.response = b''

    def write(self, data):
        super().write(data)
        if data[0] == 0x10:
            self.norm = list(data[1:])
        elif data[0] == 0x11:
            self.dp = data[1]
        self.response = {0x1a: bytes([59, *self.norm]), 0x1c: bytes([59, self.dp]),
                         0x42: b';\xa0'}.get(data[0], b'')

    def read(self, count):
        result, self.response = self.response[:count], self.response[count:]
        return result


def _wait_for(predicate):
    deadline = time.monotonic() + 1
    while not predicate() and time.monotonic() < deadline:
        threading.Event().wait(0.005)
    assert predicate()


@pytest.mark.parametrize('mismatch', [False, True])
def test_schedule_restores_on_abort_with_established_waits(tmp_path, monkeypatch, mismatch):
    port = RegisterPort()
    ticks, waits = [0.0], []
    def sleep(seconds):
        waits.append(seconds)
        ticks[0] += seconds
    monkeypatch.setattr('dispread.gsv2as_serial._sleep', sleep)
    point = {'register': {'norm': {'daten': [80, 27, 228]}, 'dpoint': {'daten': [1]}}}
    if mismatch:
        port.dp = 2
    recorder = ReferenceRecorder(lambda: port, tmp_path / 'reference.jsonl',
                                 norm_schedule=[(2, 20), (3, 20)], restore_point=point,
                                 monotonic=lambda: ticks[0], clock=lambda: int(ticks[0] * 1e9))
    recorder.start()
    _wait_for(lambda: 'precheck' in recorder.status() if mismatch else any(b[0] == 16 for b in port.writes))
    result = recorder.stop()
    assert port.closed
    if mismatch:
        assert not any(b[0] in (16, 17) for b in port.writes)
        assert 'Rueckstellpunkt' in result['schedule_aborted']
    else:
        assert port.norm == [80, 27, 228] and port.dp == 1
        assert result['restore_verification']['matches_restore_point']
        assert waits[-8:] == [0.25, 0.15, 0.35, 0.35, 0.7, 0.3, 0.2, 0.8]
        assert [b for b in port.writes if b[0] == 16] == [b'\x10\x10\x05\x94', b'\x10P\x1b\xe4']
        commands = [json.loads(s) for s in (tmp_path / 'commands.jsonl').read_text().splitlines()]
        assert all('t_boottime_ns' in e for e in commands)
        assert commands[-1]['label'] == 'restore_verify'


def test_restoring_visible_and_timeout_closes_port(tmp_path, monkeypatch):
    port = RegisterPort()
    restoring, release = threading.Event(), threading.Event()
    ticks = [0.0]
    recorder = None
    def sleep(seconds):
        ticks[0] += seconds
        if recorder.status()['restoring']:
            restoring.set()
            release.wait(1)
    monkeypatch.setattr('dispread.gsv2as_serial._sleep', sleep)
    point = {'register': {'norm': {'daten': [80, 27, 228]}, 'dpoint': {'daten': [1]}}}
    recorder = ReferenceRecorder(lambda: port, tmp_path / 'r', norm_schedule=[(2, 20)],
                                 restore_point=point, monotonic=lambda: ticks[0])
    recorder.start()
    _wait_for(lambda: any(b[0] == 16 for b in port.writes))
    monkeypatch.setattr('dispread.live.reference.JOIN_TIMEOUT_S', 0.05)
    result = []
    stopper = threading.Thread(target=lambda: result.append(recorder.stop()))
    stopper.start()
    assert restoring.wait(0.5)
    assert recorder.status()['restoring'] and not port.closed
    stopper.join(0.5)
    assert result[0]['error'] == 'Rückstellung nicht bestätigt – Gerät prüfen (gsv-registers.py)'
    assert port.closed
    release.set()
    recorder._reader.join(1)


def test_slow_disk_uses_bounded_drop_oldest_queue(tmp_path, monkeypatch):
    from pathlib import Path
    blocked, release = threading.Event(), threading.Event()
    original_open = Path.open
    target = tmp_path / 'reference.jsonl'
    class SlowFile:
        def __enter__(self):
            self.stream = original_open(target, 'w', encoding='utf-8')
            return self
        def write(self, text):
            blocked.set()
            release.wait(1)
            self.stream.write(text)
        def flush(self):
            self.stream.flush()
        def __exit__(self, *args):
            self.stream.close()
    monkeypatch.setattr(Path, 'open', lambda self, *a, **kw: SlowFile() if self == target else original_open(self, *a, **kw))
    port = FakePort([b'partial\n'] + [b'+01.2345 mV/V\n'] * 100)
    recorder = ReferenceRecorder(lambda: port, target, queue_size=2)
    recorder.start()
    assert blocked.wait(1)
    deadline = time.monotonic() + 1
    while recorder.status()['lines'] < 100 and time.monotonic() < deadline:
        threading.Event().wait(0.005)
    assert recorder.status()['lines'] == 100
    assert recorder.status()['dropped_oldest'] > 0
    assert recorder._queue.qsize() <= 2
    release.set()
    recorder.stop()
    assert port.closed


def test_schedule_logs_every_port_write_and_never_writes_after_timeout_close(tmp_path, monkeypatch):
    port = RegisterPort()
    monkeypatch.setattr('dispread.gsv2as_serial._sleep', lambda _s: None)
    point = {'register': {'norm': {'daten': [80, 27, 228]}, 'dpoint': {'daten': [1]}}}
    recorder = ReferenceRecorder(lambda: port, tmp_path / 'reference.jsonl',
                                 norm_schedule=[(2, 20)], restore_point=point)
    recorder.start()
    _wait_for(lambda: any(b[0] == 16 for b in port.writes))
    recorder.stop()
    rows = [json.loads(s) for s in (tmp_path / 'commands.jsonl').read_text().splitlines()]
    assert [bytes(e['command_bytes']) for e in rows if e['event'] == 'serial_write'] == port.writes
    before = len(port.writes)
    with pytest.raises(OSError, match='geschlossen'):
        recorder._port.write(b'\x10P\x1b\xe4')
    assert len(port.writes) == before


def test_schedule_without_telegrams_stays_read_only_and_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr('dispread.live.reference.JOIN_TIMEOUT_S', 0.05)
    port = RegisterPort()
    port.lines.clear()
    point = {'register': {'norm': {'daten': [80, 27, 228]}, 'dpoint': {'daten': [1]}}}
    recorder = ReferenceRecorder(lambda: port, tmp_path / 'r', norm_schedule=[(2, 20)],
                                 restore_point=point, startup_timeout_s=0.03)
    recorder.start()
    assert port.closed and not port.writes
    assert not recorder.status()['enabled']


def test_stop_deadline_starts_when_service_requests_no_more_steps(tmp_path, monkeypatch):
    ticks = [100.0]
    monkeypatch.setattr('dispread.live.reference.time.monotonic', lambda: ticks[0])
    recorder = ReferenceRecorder(lambda: None, tmp_path / 'r', norm_schedule=[(1, 2)])
    recorder.request_stop()
    ticks[0] += 3
    recorder.request_stop()
    class Joined:
        def join(self, remaining):
            assert remaining == 17.0
        def is_alive(self):
            return False
    recorder._reader = recorder._writer = Joined()
    recorder.stop()


def test_reference_file_is_visible_during_run(tmp_path):
    port = FakePort([b'partial\n', b'+01.2345 mV/V\n'])
    target = tmp_path / 'reference.jsonl'
    recorder = ReferenceRecorder(lambda: port, target)
    recorder.start()
    try:
        _wait_for(lambda: target.exists() and bool(target.read_text()))
    finally:
        recorder.stop()


@pytest.mark.parametrize('point', [None, {}, {'register': {'norm': {'daten': [True, 27, 228]}, 'dpoint': {'daten': [1]}}}])
def test_restore_point_validated_synchronously_before_open(tmp_path, monkeypatch, point):
    monkeypatch.setattr('dispread.live.reference.DEFAULT_RESTORE_POINT', tmp_path / 'missing.json')
    recorder = ReferenceRecorder(lambda: pytest.fail('Port opened'), tmp_path / 'run' / 'r',
                                 norm_schedule=[(2, 20)], restore_point=point)
    with pytest.raises((OSError, ValueError), match='missing|Rueckstellpunkt'):
        recorder.start()
    assert not (tmp_path / 'run').exists()


def test_precheck_mismatch_continues_recording_read_only(tmp_path, monkeypatch):
    monkeypatch.setattr('dispread.gsv2as_serial._sleep', lambda _s: None)
    port = RegisterPort()
    port.dp = 2
    point = {'register': {'norm': {'daten': [80, 27, 228]}, 'dpoint': {'daten': [1]}}}
    recorder = ReferenceRecorder(lambda: port, tmp_path / 'r', norm_schedule=[(2, 20)], restore_point=point)
    recorder.start()
    try:
        _wait_for(lambda: 'precheck' in recorder.status())
        assert recorder.status()['enabled'] and not port.closed
        assert 'Rueckstellpunkt' in recorder.status()['schedule_aborted']
        port.lines.extend([b'discard\n', b'+02.3456 mV/V\n'])
        _wait_for(lambda: recorder.latest()['value'] == 2.3456)
        assert not any(b[0] in (16, 17) for b in port.writes)
    finally:
        recorder.stop()


def test_oversized_rejected_line_is_audited(tmp_path):
    raw = b'x' * 4097
    port = FakePort([b'discard\n', b'+01.2345 mV/V\n', raw, b'end\n', b'+02.3456 mV/V\n'])
    recorder = ReferenceRecorder(lambda: port, tmp_path / 'r')
    recorder.start()
    try:
        _wait_for(lambda: recorder.latest()['value'] == 2.3456)
    finally:
        recorder.stop()
    rows = [json.loads(line) for line in (tmp_path / 'r').read_text().splitlines()]
    assert len(rows) == 3
    assert rows[1]['raw'] == raw.decode('ascii')
    assert rows[1]['cell_text'] is None and rows[1]['value'] is None and rows[1]['error']
