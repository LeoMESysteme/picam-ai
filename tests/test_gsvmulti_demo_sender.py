"""Nur pty/Fakes: keine Hardwareports und keine Windows-Abnahme."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import serial

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/gsvmulti-demo-sender.py"


@pytest.fixture
def demo():
    spec = importlib.util.spec_from_file_location("gsvmulti_demo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_clock(demo, monkeypatch):
    class Clock:
        now = 0

        def sleep(self, seconds):
            self.now += round(seconds * 1_000_000_000)

    clock = Clock()
    monkeypatch.setattr(demo, "boottime_ns", lambda: clock.now)
    monkeypatch.setattr(demo, "sleep", clock.sleep)
    return clock


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.mark.parametrize("profile", ["constant", "staircase", "boundaries"])
def test_cli_pty_bytes_count_and_coarse_rate(tmp_path, profile):
    output = tmp_path / "frames.jsonl"
    master, slave = os.openpty()
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--port", os.ttyname(slave), "--output", str(output),
             "--profile", profile, "--count", "8", "--rate", "40", "--prefix", "#"],
            capture_output=True, text=True, timeout=20,
            env={**os.environ, 'PYTHONPATH': str(SCRIPT.parents[1] / 'src')},
        )
        assert result.returncode == 0, result.stderr
        entries = rows(output)
        assert len(entries) == 8
        assert [entry["sequence"] for entry in entries] == list(range(1, 9))
        assert all(entry["status"] == "sent" for entry in entries)
        expected = b"".join(bytes.fromhex(entry["bytes_hex"]) for entry in entries)
        os.set_blocking(master, False)
        wire = bytearray()
        while True:
            try:
                wire.extend(os.read(master, 4096))
            except BlockingIOError:
                break
        assert bytes(wire) == expected
        assert wire.count(b"\r\n") == 8 and wire.startswith(b"#")
        assert all(bytes.fromhex(e["bytes_hex"]) == f'#{e["value_text"]}\r\n'.encode() for e in entries)
        # Nur grobe Untergrenze; langsame/ausgelastete Hosts dürfen länger brauchen.
        assert entries[-1]["t_send_boottime_ns"] - entries[0]["t_send_boottime_ns"] >= 100_000_000
        assert all(e["send_time_base"] == "CLOCK_BOOTTIME" for e in entries)
        assert all(e["demo"] and e["provisional"] and e["capture_time_base"] == "synthetic" for e in entries)
    finally:
        os.close(master)
        os.close(slave)


@pytest.mark.parametrize("port", ["/dev/ttyUSB0", "/dev/serial0"])
def test_protected_ports_rejected_before_open(demo, monkeypatch, port, tmp_path):
    monkeypatch.setattr(serial, "Serial", lambda *a, **kw: pytest.fail("Port wurde geöffnet"))
    with pytest.raises(SystemExit) as exc:
        demo.main(["--port", port, "--output", str(tmp_path / "out.jsonl")])
    assert exc.value.code == 2
    assert not (tmp_path / "out.jsonl").exists()


def test_protected_alias_rejected(demo, monkeypatch, tmp_path):
    alias = tmp_path / "reference"
    alias.symlink_to("/dev/ttyUSB0")
    monkeypatch.setattr(serial, "Serial", lambda *a, **kw: pytest.fail("Port wurde geöffnet"))
    with pytest.raises(SystemExit):
        demo.main(["--port", str(alias)])


@pytest.mark.parametrize("args", [
    ["--rate", "0"], ["--rate", "nan"], ["--rate", "inf"], ["--rate", "-1"],
    ["--count", "0"], ["--count", "-1"], ["--baud", "12345"], ["--prefix", "1"],
])
def test_bad_arguments_never_open_port(demo, monkeypatch, args):
    monkeypatch.setattr(serial, "Serial", lambda *a, **kw: pytest.fail("Port wurde geöffnet"))
    with pytest.raises(SystemExit) as exc:
        demo.main(["--port", "/fake", *args])
    assert exc.value.code == 2


def test_dry_run_only_jsonl_and_defaults(demo, monkeypatch, fake_clock, capsys):
    monkeypatch.setattr(serial, "Serial", lambda *a, **kw: pytest.fail("dry-run öffnet Port"))
    assert demo.main(["--dry-run"]) == 0
    entries = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(entries) == 600
    assert all(e["status"] == "dry_run" and e["baudrate"] == 115200 for e in entries)
    assert entries[1]["t_send_boottime_ns"] - entries[0]["t_send_boottime_ns"] == 100_000_000
    assert all(e["format_id"] == "gsvmulti_userdefined_v0" for e in entries)


def test_requires_port_without_dry_run(demo):
    with pytest.raises(SystemExit):
        demo.main([])


class FakeSerial:
    out_waiting = 0

    def __init__(self):
        self.written = []
        self.resets = 0
        self.closed = False

    def write(self, data):
        self.written.append(data)
        return len(data)

    def reset_output_buffer(self):
        self.resets += 1
        self.out_waiting = 0

    def close(self):
        self.closed = True


def test_explicit_allow_port_and_serial_configuration(demo, monkeypatch, fake_clock, tmp_path):
    transport = FakeSerial()
    calls = []

    def open_serial(*args, **kwargs):
        calls.append((args, kwargs))
        return transport

    monkeypatch.setattr(serial, "Serial", open_serial)
    assert demo.main(["--port", "/dev/ttyUSB0", "--allow-port", "--count", "1",
                      "--output", str(tmp_path / "out.jsonl")]) == 0
    assert calls[0][0] == ("/dev/ttyUSB0",)
    config = calls[0][1]
    assert config == dict(baudrate=115200, bytesize=8, parity="N", stopbits=1, timeout=0,
                          write_timeout=1.0, xonxoff=False, rtscts=False, dsrdtr=False)
    assert transport.closed


def test_partial_write_finishes_without_truncating_frame(demo, monkeypatch, fake_clock, tmp_path):
    transport = FakeSerial()

    def write(data):
        transport.written.append(data[:2])
        return len(data[:2])

    transport.write = write
    monkeypatch.setattr(serial, "Serial", lambda *a, **kw: transport)
    output = tmp_path / 'frames.jsonl'
    assert demo.main(['--port', '/fake', '--count', '2', '--output', str(output)]) == 0
    assert b''.join(transport.written) == b'%+12.345\r\n' * 2
    assert all(e['status'] == 'sent' and e['bytes_written'] == 10 for e in rows(output))
    assert transport.resets == 0


def test_partial_timeout_stops_without_appending_next_frame(demo, monkeypatch, fake_clock, tmp_path):
    transport = FakeSerial()

    def write(data):
        if not transport.written:
            transport.written.append(data[:2])
            return 2
        raise serial.SerialTimeoutException('blocked')

    transport.write = write
    monkeypatch.setattr(serial, 'Serial', lambda *a, **kw: transport)
    output = tmp_path / 'frames.jsonl'
    assert demo.main(['--port', '/fake', '--count', '3', '--output', str(output)]) == 1
    entries = rows(output)
    assert len(entries) == 1 and entries[0]['error']
    assert entries[0]['bytes_written'] is None
    assert 'confirmed_bytes_written=2' in entries[0]['error']
    assert b''.join(transport.written) == b'%+' and transport.resets == 0


def test_backlog_preserves_previous_frame_and_drops_next(demo, monkeypatch, fake_clock, tmp_path):
    transport = FakeSerial()

    def write(data):
        transport.written.append(data)
        transport.out_waiting = len(data)
        return len(data)

    def drain(seconds):
        fake_clock.sleep(seconds)
        if fake_clock.now >= 200_000_000:
            transport.out_waiting = 0

    transport.write = write
    monkeypatch.setattr(demo, 'sleep', drain)
    monkeypatch.setattr(serial, 'Serial', lambda *a, **kw: transport)
    output = tmp_path / 'frames.jsonl'
    assert demo.main(['--port', '/fake', '--count', '3', '--output', str(output)]) == 0
    entries = rows(output)
    assert [e['status'] for e in entries] == ['sent', 'dropped', 'sent']
    assert entries[1]['drop_reason'] == 'output_backlog' and entries[1]['bytes_written'] == 0
    assert b''.join(transport.written) == b'%+12.345\r\n' * 2 and transport.resets == 0
    assert entries[2]['t_send_boottime_ns'] == 200_000_000


def test_port_failure_logged_once_and_stops(demo, monkeypatch, fake_clock, tmp_path):
    transport = FakeSerial()

    def fail(data):
        raise serial.SerialException("disconnected")

    transport.write = fail
    monkeypatch.setattr(serial, "Serial", lambda *a, **kw: transport)
    output = tmp_path / "frames.jsonl"
    assert demo.main(["--port", "/fake", "--count", "3", "--output", str(output)]) == 1
    entries = rows(output)
    assert len(entries) == 1 and entries[0]["status"] == "dropped"
    assert entries[0]["drop_reason"] == "serial_error" and "disconnected" in entries[0]["error"]
    assert transport.closed


def test_sleep_interrupted_early_does_not_send_before_due(demo, monkeypatch, fake_clock, tmp_path):
    """Frühes Aufwachen darf Rate nicht erhöhen; deterministisch ohne Lastgrenzen."""
    transport = FakeSerial()
    attempts = []

    def write(data):
        attempts.append(fake_clock.now)
        return len(data)

    transport.write = write
    sleeps = []

    def early_sleep(seconds):
        sleeps.append(seconds)
        # Erstes Warten endet früh, danach regulär bis zur Frist.
        fake_clock.sleep(seconds / 2 if len(sleeps) == 1 else seconds)

    monkeypatch.setattr(demo, "sleep", early_sleep)
    monkeypatch.setattr(serial, "Serial", lambda *a, **kw: transport)
    assert demo.main(["--port", "/fake", "--count", "2", "--output", str(tmp_path / "out.jsonl")]) == 0
    assert attempts == [0, 100_000_000]
