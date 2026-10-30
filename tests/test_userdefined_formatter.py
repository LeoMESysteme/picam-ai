"""UserDefined-Prototyp: strikte Zahlenlexik und Bytes bis zum pty."""

import os
import select
from dataclasses import replace

import pytest

from dispread.records import InvalidValuePolicy, TimeBaseKind, Timestamp, ValueRecord, ValueStatus
from dispread.sink.protocol import TelegramFormatter
from dispread.sink.serial_out import SerialSink


def record(text="+ 1.7643", value=1.7643, status=ValueStatus.VALID):
    return ValueRecord(
        frame_sequence=1, capture_timestamp=Timestamp(0, TimeBaseKind.SYNTHETIC),
        value=value, unit=None, status=status, confidence=1.0, profile_id="demo",
        trigger_sequence=None, result_timestamp=None, raw_text=text,
        reject_reasons=() if status is ValueStatus.VALID else (status.value,),
    )


@pytest.fixture
def formatter():
    from dispread.sink.protocol.userdefined import UserDefinedFormatter

    return UserDefinedFormatter()


@pytest.mark.parametrize("text,value,expected", [
    ("+ 1.7643", 1.7643, b"%+1.7643\r\n"),
    ("-012.50", -12.5, b"%-012.50\r\n"),
    ("0", 0.0, b"%0\r\n"), ("-0.000", -0.0, b"%-0.000\r\n"),
    ("+000.00", 0.0, b"%+000.00\r\n"),
    (" 12 3.45 ", 123.45, b"%123.45\r\n"),
])
def test_exact_bytes(formatter, text, value, expected):
    assert formatter.format(record(text, value)) == expected


@pytest.mark.parametrize("text", [
    None, "", " ", "NaN", "inf", "1e0", "1_0", "1,0", ".5", "1.",
    "--1", "1\n", "1\r\n", "1\t", "１", "١", "1\u00a0", "%1", "1;2",
])
def test_unknown_text_is_omitted_with_reason(formatter, text, caplog):
    assert formatter.format(record(text, 1.0)) is None
    assert caplog.records  # Grund ohne Erweiterung des Formatter-Vertrags.


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -float("inf"), 1.00001])
def test_inconsistent_value_is_omitted(formatter, value):
    assert formatter.format(record("1", value)) is None


def test_decimal_comparison_does_not_hide_float_rounding(formatter):
    assert formatter.format(record("1.00000000000000001", 1.0)) is None
    assert formatter.format(record("0.10000000000000001", 0.1)) is None


@pytest.mark.parametrize("status", [ValueStatus.TRANSITION, ValueStatus.UNREADABLE, ValueStatus.STALE])
def test_non_valid_never_produces_frame(formatter, status):
    value = 1.0 if status is ValueStatus.TRANSITION else None
    assert formatter.format(record("1", value, status)) is None


@pytest.mark.parametrize("prefix", ["", "%%", "0", "9", "+", "-", ".", " ", "\t", "\n", "\x7f", "ä"])
def test_invalid_prefix(prefix):
    from dispread.sink.protocol.userdefined import UserDefinedFormatter

    with pytest.raises(ValueError, match="Präfix"):
        UserDefinedFormatter(prefix=prefix)


def test_custom_prefix_and_capabilities(formatter):
    assert replace(formatter, prefix="#").format(record()) == b"#+1.7643\r\n"
    assert isinstance(formatter, TelegramFormatter)
    caps = formatter.capabilities
    assert caps.format_id == "gsvmulti_userdefined_v0"
    assert caps.provisional and caps.channel_count == 1
    assert not caps.requires_device_commands and not caps.carries_capture_timestamp
    assert caps.timestamp_resolution_ns is None
    assert caps.supported_invalid_policies == frozenset({InvalidValuePolicy.OMIT_RECORD})
    assert formatter.invalid_policy is InvalidValuePolicy.OMIT_RECORD


def test_serial_sink_pty_and_omission_receipts(formatter):
    master, slave = os.openpty()
    sink = SerialSink(os.ttyname(slave), formatter)
    try:
        sink.open()
        sent = sink.emit(record())
        assert select.select([master], [], [], 2)[0]
        assert os.read(master, 4096) == b"%+1.7643\r\n"
        assert sent.wire_bytes == b"%+1.7643\r\n" and not sent.omitted
        for rejected in [record("1", 2.0), record(None, None, ValueStatus.STALE)]:
            receipt = sink.emit(rejected)
            assert receipt.omitted and receipt.wire_bytes is None
            assert receipt.invalid_policy is InvalidValuePolicy.OMIT_RECORD
        os.set_blocking(master, False)
        with pytest.raises(BlockingIOError):
            os.read(master, 4096)
        assert sink.health().sent == 1 and sink.health().omitted == 2
    finally:
        sink.close()
        os.close(master)
        os.close(slave)


def test_non_valid_logging_is_debug_but_inconsistency_warns(formatter, caplog):
    import logging

    with caplog.at_level(logging.DEBUG, logger='dispread.sink.protocol.userdefined'):
        formatter.format(record('1', None, ValueStatus.UNREADABLE))
        formatter.format(record('1', 2.0))
    assert [r.levelno for r in caplog.records] == [logging.DEBUG, logging.WARNING]


def test_saturated_pty_timeout_latches_without_purging_or_followup():
    import subprocess
    import sys
    from pathlib import Path

    script = """
import os
from test_userdefined_formatter import record
from dispread.sink.protocol.userdefined import UserDefinedFormatter
from dispread.sink.serial_out import SerialSink
master, slave = os.openpty()
sink = SerialSink(os.ttyname(slave), UserDefinedFormatter(), write_timeout=.05)
try:
    sink.open()
    fd = sink._serial.fileno()
    while True:
        try:
            os.write(fd, b'x' * 65536)
        except BlockingIOError:
            break
    receipt = sink.emit(record())
    assert receipt.error and receipt.t_complete_ns is None
    assert receipt.bytes_written is None  # pySerial cannot report partial bytes on timeout.
    assert sink.health().errors == 1
    following = sink.emit(record())
    assert following.dropped and following.drop_reason == 'output_failed'
    assert following.bytes_written == 0
finally:
    sink.close()
    os.close(master)
    os.close(slave)
"""
    root = Path(__file__).parents[1]
    subprocess.run([sys.executable, '-c', script], check=True, timeout=20,
                   env={**os.environ, 'PYTHONPATH': f'{root / "src"}:{root / "tests"}'})
