import json
from dataclasses import replace

import pytest

from dispread.gsv_transport import JsonLineReader, OutputConfig, OutputPublisher, encode_message
from dispread.records import InvalidValuePolicy, TimeBaseKind, Timestamp, ValueRecord, ValueStatus
from dispread.sink.protocol.user_defined import UserDefinedFormatter


def record(seq=1, status=ValueStatus.VALID):
    return ValueRecord(
        seq,
        Timestamp(1, TimeBaseKind.SYNTHETIC),
        0.12345 if status is ValueStatus.VALID else None,
        "mV/V",
        status,
        1.0,
        "test",
        None,
        None,
        raw_text="+0.12345",
        reject_reasons=() if status is ValueStatus.VALID else ("unreadable",),
    )


def test_formatter_keeps_original_precision_and_rejects_mismatch():
    fmt = UserDefinedFormatter()
    assert fmt.format(record()) == b"%+0.12345\r\n"
    assert fmt.format(record(status=ValueStatus.UNREADABLE)) is None
    with pytest.raises(ValueError):
        fmt.format(replace(record(), value=0.2))
    with pytest.raises(ValueError):
        UserDefinedFormatter(invalid_policy=InvalidValuePolicy.SEND_NAN)
    assert (
        UserDefinedFormatter(invalid_policy=InvalidValuePolicy.SEND_NAN, demo=True).format(
            record(status=ValueStatus.UNREADABLE)
        )
        == b"%NaN\r\n"
    )


@pytest.mark.parametrize("raw", ["1e2", "1_0", " NaN", "1\n2", "+inf", "+0.12345 "])
def test_formatter_rejects_unrecognized_input(raw):
    with pytest.raises(ValueError):
        UserDefinedFormatter().format(replace(record(), raw_text=raw))


def test_framing_fragmented_first_line_and_oversized_complete_frame():
    decoder = JsonLineReader()
    data = encode_message({"version": 1, "type": "poll", "request_id": "first"})
    assert decoder.feed(data[:4]) == []
    assert decoder.feed(data[4:] + data) == [json.loads(data)] * 2
    with pytest.raises(ValueError):
        JsonLineReader().feed(b'{"x":"' + b"a" * 65536 + b'"}\n')


def test_config_validates_no_unknown_fields_or_reference_port():
    assert OutputConfig.from_dict(None).transport == "off"
    for raw in [
        {"transport": "bogus"},
        {"transport": "uart", "serial_port": "/dev/ttyUSB0"},
        {"transport": "tcp", "tcp_port": 0},
        {"transport": "tcp", "surprise": 1},
    ]:
        with pytest.raises(ValueError):
            OutputConfig.from_dict(raw)


def test_real_output_stays_locked_even_for_valid_record(tmp_path):
    publisher = OutputPublisher(OutputConfig(transport="tcp"), tmp_path)
    publisher.publish(record())
    reply = publisher.handle({"version": 1, "type": "poll", "request_id": "x"})
    assert reply["type"] == "idle"
    assert "record" not in reply
    assert publisher.status()["release_block"]


def test_invalid_barrier_survives_new_valid_and_wrong_ack(tmp_path):
    publisher = OutputPublisher(OutputConfig(transport="tcp"), tmp_path, demo=True)
    publisher.publish(record(status=ValueStatus.UNREADABLE))
    publisher.publish(record(2))
    request = {"version": 1, "type": "poll", "request_id": "x"}
    reply = publisher.handle(request)
    assert reply["record"]["status"] == "unreadable"
    ack = {
        "version": 1,
        "type": "ack",
        "request_id": "wrong",
        "run_id": reply["run_id"],
        "frame_sequence": reply["record"]["frame_sequence"],
        "barrier_id": reply["barrier_id"],
        "outcome": "written",
    }
    with pytest.raises(ValueError):
        publisher.handle(ack)
    publisher.handle(dict(ack, request_id="x"))
    current = publisher.handle(dict(request, request_id="next"))
    assert current["record"]["frame_sequence"] == 2
    assert current["barrier_id"] is None


def test_demo_never_accepts_real_capture(tmp_path):
    publisher = OutputPublisher(OutputConfig(transport="tcp"), tmp_path, demo=True)
    with pytest.raises(ValueError):
        publisher.publish(replace(record(), capture_timestamp=Timestamp(1, TimeBaseKind.V4L2_MONOTONIC)))


def test_metadata_serializes_and_confirmed_record_is_not_repeated(tmp_path):
    publisher = OutputPublisher(OutputConfig(transport="tcp"), tmp_path, demo=True)
    json.dumps(publisher.metadata())
    publisher.publish(record())
    reply = publisher.handle({"version": 1, "type": "poll", "request_id": "once"})
    publisher.handle(
        {
            "version": 1,
            "type": "ack",
            "request_id": "once",
            "run_id": reply["run_id"],
            "frame_sequence": 1,
            "barrier_id": None,
            "outcome": "written",
        }
    )
    assert publisher.handle({"version": 1, "type": "poll", "request_id": "again"})["type"] == "idle"


def test_tcp_actual_handshake_and_stop_release_port(tmp_path):
    import socket
    import time

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    publisher = OutputPublisher(OutputConfig(transport="tcp", tcp_host="127.0.0.1", tcp_port=port), tmp_path)
    publisher.start()
    try:
        deadline = time.monotonic() + 2
        while True:
            try:
                connection = socket.create_connection(("127.0.0.1", port), timeout=0.2)
                break
            except ConnectionRefusedError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
        with connection:
            connection.sendall(encode_message({"version": 1, "type": "poll", "request_id": "real"}))
            reply = JsonLineReader().feed(connection.recv(4096))[0]
            assert reply["type"] == "idle" and reply["release_block"]
    finally:
        publisher.stop()
    assert not publisher._thread.is_alive()


def test_output_audit_failure_is_visible_to_publisher_and_closes_log(tmp_path):
    class BrokenLog:
        closed = False

        def write(self, _):
            raise OSError("disk full")

        def close(self):
            self.closed = True

    publisher = OutputPublisher(OutputConfig(transport="tcp"), tmp_path)
    log = BrokenLog()
    publisher._events = log
    with pytest.raises(OSError):
        publisher._event("test")
    assert publisher.status()["state"] == "audit_failed"
    with pytest.raises(OSError):
        publisher.publish(record())
    with pytest.raises(OSError):
        publisher.stop()
    assert log.closed


def test_lost_ack_has_frame_level_unconfirmed_receipt(tmp_path):
    import io

    publisher = OutputPublisher(OutputConfig(transport="tcp"), tmp_path, demo=True)
    publisher._events = io.StringIO()
    publisher.publish(record())
    publisher.handle({"version": 1, "type": "poll", "request_id": "lost"})
    publisher.abandon_pending()
    events = [json.loads(line) for line in publisher._events.getvalue().splitlines()]
    assert events[0]["event"] == "offered"
    assert events[1]["event"] == "unconfirmed"
    assert events[1]["frame_sequence"] == 1
    assert events[1]["request_id"] == "lost"


def test_unconfirmed_numeric_never_reoffered_after_reconnect(tmp_path):
    publisher = OutputPublisher(OutputConfig(transport="tcp"), tmp_path, demo=True)
    publisher.publish(record())
    publisher.handle({"version": 1, "type": "poll", "request_id": "lost"})
    publisher.abandon_pending()
    assert publisher.handle({"version": 1, "type": "poll", "request_id": "reconnect"})["type"] == "idle"


def test_event_clock_is_a_declared_time_base(tmp_path):
    import io

    publisher = OutputPublisher(OutputConfig(), tmp_path)
    publisher._events = io.StringIO()
    publisher._event("test")
    assert TimeBaseKind(json.loads(publisher._events.getvalue())["time_base"]).carries_time_information


def test_v1_bridge_uart_uses_shared_rate_and_rejects_gsv_rate():
    assert OutputConfig(transport='uart').baudrate == 460800
    with pytest.raises(ValueError):
        OutputConfig(transport='uart', baudrate=115200)
