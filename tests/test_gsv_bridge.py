"""Bridge safety: only demos, bounded writes, independently auditable ACKs."""
from __future__ import annotations

import io
import json
import threading

import pytest

from dispread.gsv_bridge import BridgeError, BridgeSession, demo_records, send_demo
from dispread.records import TimeBaseKind, Timestamp, ValueRecord, ValueStatus


def record(status=ValueStatus.VALID):
    return ValueRecord(7, Timestamp(1, TimeBaseKind.SYNTHETIC),
                       0.12345 if status is ValueStatus.VALID else None,
                       "mV/V", status, 1.0, "demo", None, None,
                       raw_text="+0.12345", reject_reasons=() if status is ValueStatus.VALID else ("demo",))


class Link:
    def __init__(self, reply):
        self.reply, self.messages = reply, []

    def send(self, message):
        self.messages.append(message)

    def receive(self):
        return dict(self.reply, request_id=self.messages[-1]["request_id"])


class Com:
    write_timeout = None

    def __init__(self, short=False):
        self.payloads, self.short = [], short

    def write(self, payload):
        self.payloads.append(payload)
        return len(payload) - int(self.short)


def reply(status=ValueStatus.VALID, **changes):
    return dict(version=1, type="record", run_id="run-1", record=record(status).to_dict(),
                frame_age_ns=None, barrier_id=None, demo=True) | changes


def test_demo_preserves_precision_and_ack_is_driver_only():
    link, com, log = Link(reply()), Com(), io.StringIO()
    BridgeSession(log=log).exchange(link, com)
    assert com.payloads == [b"%+0.12345\r\n"]
    assert link.messages[-1]["type"] == "ack"
    assert link.messages[-1]["outcome"] == "written"
    event = json.loads(log.getvalue().splitlines()[-1])
    assert event["completion_stage"] == "com_driver_write"
    assert event["time_base"] == "host_monotonic"
    assert event["provisional"] is True


def test_real_dut_is_locked_even_if_valid():
    link, com = Link(reply(demo=False)), Com()
    with pytest.raises(BridgeError, match="DUT"):
        BridgeSession().exchange(link, com)
    assert not com.payloads


def test_invalid_demo_is_not_silently_omitted():
    link, com = Link(reply(ValueStatus.UNREADABLE, barrier_id=12)), Com()
    BridgeSession().exchange(link, com)
    assert com.payloads == [b"%NaN\r\n"]
    assert link.messages[-1]["barrier_id"] == 12


def test_partial_write_is_failed_and_never_retried():
    link, com = Link(reply()), Com(short=True)
    with pytest.raises(BridgeError, match="COM"):
        BridgeSession().exchange(link, com)
    assert len(com.payloads) == 1
    assert link.messages[-1]["outcome"] == "failed"


def test_nonce_mismatch_cannot_write():
    class WrongNonce(Link):
        def receive(self):
            return dict(self.reply, request_id="wrong")
    com = Com()
    with pytest.raises(BridgeError, match="request_id"):
        BridgeSession().exchange(WrongNonce(reply()), com)
    assert not com.payloads


@pytest.mark.parametrize("changes", [{"version": 9}, {"demo": "true"}, {"run_id": ""},
                                     {"frame_age_ns": -1}, {"barrier_id": "bad"}])
def test_malformed_reply_cannot_write(changes):
    com = Com()
    with pytest.raises(BridgeError):
        BridgeSession().exchange(Link(reply(**changes)), com)
    assert not com.payloads


def test_idle_is_a_legitimate_pause():
    link, com = Link(dict(version=1, type="idle", run_id="run-1", demo=True)), Com()
    assert BridgeSession().exchange(link, com) == "idle"
    assert not com.payloads


def test_finite_standalone_demo_has_unique_values():
    values = list(demo_records(600))
    assert len(values) == 600
    assert len({r.value for r in values}) == 600
    assert all(r.capture_timestamp.base is TimeBaseKind.SYNTHETIC for r in values)
    com = Com()
    send_demo(com, count=3, rate_hz=10, stop=threading.Event(), wait=lambda _: False)
    assert len(com.payloads) == 3
    assert all(p.startswith(b"%") and p.endswith(b"\r\n") for p in com.payloads)


def test_expired_budget_cannot_submit_to_com():
    ticks = iter([0, 2_000_000_000])
    link, com = Link(reply()), Com()
    assert BridgeSession(clock=lambda: next(ticks)).exchange(link, com) == "expired"
    assert not com.payloads
    assert link.messages[-1]["outcome"] == "expired"


def test_duplicate_reply_after_reconnect_does_not_resubmit_value():
    com, session = Com(), BridgeSession()
    session.exchange(Link(reply()), com)
    session.exchange(Link(reply()), com)
    assert len(com.payloads) == 1


def test_socket_framing_preserves_first_complete_reply():
    import socket

    from dispread.gsv_bridge import _Link
    from dispread.gsv_transport import encode_message
    left, right = socket.socketpair()
    try:
        left.settimeout(1)
        data = encode_message(dict(reply(), request_id="first"))
        right.sendall(data[:3])
        right.sendall(data[3:])
        assert _Link(left).receive()["request_id"] == "first"
    finally:
        left.close()
        right.close()


def test_actual_demo_cli_stdout_and_audit(tmp_path):
    import subprocess
    import sys
    path = tmp_path / "bridge.jsonl"
    result = subprocess.run([sys.executable, "-m", "dispread.gsv_bridge", "--demo", "--stdout",
                             "--count", "3", "--rate-hz", "100", "--log", str(path)],
                            capture_output=True, check=True, timeout=5)
    assert result.stdout == b"%-000.001\r\n%+000.000\r\n%+000.001\r\n"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(events) == 3
    assert all(event["demo"] and event["provisional"] for event in events)


def test_demo_flag_cannot_unlock_a_real_capture():
    message = reply(frame_age_ns=100)
    message["record"]["capture_timestamp"]["base"] = TimeBaseKind.V4L2_MONOTONIC.value
    com = Com()
    with pytest.raises(BridgeError, match="synthetic"):
        BridgeSession().exchange(Link(message), com)
    assert not com.payloads


def _socket_server(publisher):
    import socket
    left, right = socket.socketpair()
    right.settimeout(.05)
    left.settimeout(1)
    errors = []

    def serve():
        try:
            publisher._serve(right, tcp=True)
        except (OSError, ConnectionError):
            pass
        except Exception as exc:
            errors.append(exc)
        finally:
            right.close()

    thread = threading.Thread(target=serve)
    thread.start()
    return left, thread, errors


def test_actual_socket_publisher_preserves_invalid_barrier_before_valid(tmp_path):
    from dataclasses import replace

    from dispread.gsv_bridge import _Link
    from dispread.gsv_transport import OutputConfig, OutputPublisher
    publisher = OutputPublisher(OutputConfig(transport="tcp"), tmp_path, demo=True)
    publisher.publish(record(ValueStatus.UNREADABLE))
    publisher.publish(replace(record(), frame_sequence=8))
    client, thread, errors = _socket_server(publisher)
    try:
        bridge, com = BridgeSession(), Com()
        link = _Link(client)
        assert bridge.exchange(link, com) == "written"
        assert bridge.exchange(link, com) == "written"
        assert com.payloads == [b"%NaN\r\n", b"%+0.12345\r\n"]
    finally:
        client.close()
        thread.join(2)
    assert not thread.is_alive()
    assert not errors


def test_actual_socket_lost_ack_does_not_replay_on_reconnect(tmp_path):
    from dispread.gsv_bridge import _Link
    from dispread.gsv_transport import OutputConfig, OutputPublisher
    publisher = OutputPublisher(OutputConfig(transport="tcp"), tmp_path, demo=True)
    publisher.publish(record())
    client, thread, errors = _socket_server(publisher)
    session, com = BridgeSession(), Com()

    class LoseAck(_Link):
        def send(self, message):
            if message["type"] == "ack":
                raise ConnectionError("ACK lost")
            super().send(message)

    try:
        with pytest.raises(ConnectionError):
            session.exchange(LoseAck(client), com)
    finally:
        client.close()
        thread.join(2)
    assert not thread.is_alive()
    second, second_thread, second_errors = _socket_server(publisher)
    try:
        assert session.exchange(_Link(second), com) == "idle"
        assert com.payloads == [b"%+0.12345\r\n"]
    finally:
        second.close()
        second_thread.join(2)
    assert not second_thread.is_alive()
    assert not errors + second_errors


def test_publisher_demo_cli_help_and_bounded_unconnected_run(tmp_path):
    import subprocess
    import sys
    help_result = subprocess.run([sys.executable, "scripts/gsv-publisher-demo.py", "--help"],
                                 capture_output=True, timeout=5)
    assert help_result.returncode == 0
    assert b"--transport" in help_result.stdout
    out = tmp_path / "unconnected"
    result = subprocess.run([sys.executable, "scripts/gsv-publisher-demo.py", "--transport", "tcp",
                             "--tcp-port", "54321", "--out-dir", str(out), "--connect-timeout", "0.05"],
                            capture_output=True, timeout=5)
    assert result.returncode == 1
    meta = json.loads((out / "session.json").read_text())
    assert meta["completed"] == 0
    assert meta["demo"] and meta["provisional"]
    assert meta["output_status"]["state"] == "stopped"
    assert "TimeoutError" in meta["end_reason"]


def test_publisher_demo_subprocess_reaches_bridge_with_exact_finite_count(tmp_path):
    import socket
    import subprocess
    import sys
    import time

    from dispread.gsv_bridge import _Link
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    out = tmp_path / "demo"
    process = subprocess.Popen([sys.executable, "scripts/gsv-publisher-demo.py", "--transport", "tcp",
                                "--tcp-host", "127.0.0.1", "--tcp-port", str(port), "--count", "3",
                                "--rate-hz", "100", "--out-dir", str(out), "--connect-timeout", "3"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    connection = None
    try:
        deadline = time.monotonic() + 5
        while connection is None and time.monotonic() < deadline:
            try:
                connection = socket.create_connection(("127.0.0.1", port), timeout=.2)
            except OSError:
                time.sleep(.02)
        assert connection is not None
        connection.settimeout(1)
        bridge, com, link = BridgeSession(), Com(), _Link(connection)
        while len(com.payloads) < 3 and time.monotonic() < deadline:
            bridge.exchange(link, com)
            time.sleep(.01)
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, (stdout, stderr)
        assert len(com.payloads) == 3
        meta = json.loads((out / "session.json").read_text())
        assert meta["completed"] == 3
        assert meta["end_reason"] == "completed"
        assert len((out / "records.jsonl").read_text().splitlines()) == 3
    finally:
        if connection is not None:
            connection.close()
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


def test_uart_reader_drains_available_bytes_without_waiting_for_4096():
    from dispread.gsv_bridge import _Link
    from dispread.gsv_transport import encode_message

    class ReadySerial:
        def __init__(self):
            self.data = encode_message({"version": 1, "type": "idle", "request_id": "ready"})

        @property
        def in_waiting(self):
            return len(self.data)

        def read(self, size):
            assert size <= len(self.data), "read would wait until timeout unnecessarily"
            data, self.data = self.data[:size], self.data[size:]
            return data

    assert _Link(ReadySerial(), serial=True).receive()["request_id"] == "ready"


def test_stdout_demo_receipt_does_not_claim_com_submission(tmp_path):
    import subprocess
    import sys

    path = tmp_path / "stdout.jsonl"
    subprocess.run([sys.executable, "-m", "dispread.gsv_bridge", "--demo", "--stdout",
                    "--count", "1", "--rate-hz", "100", "--log", str(path)],
                   capture_output=True, check=True, timeout=5)
    assert json.loads(path.read_text())["completion_stage"] == "stdout_write"


def test_publisher_stop_error_still_closes_audit_and_saves_session(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("gsv_publisher_demo", "scripts/gsv-publisher-demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    closed = []

    class Publisher:
        def __init__(self, *args, **kwargs):
            pass

        def metadata(self):
            return {"demo": True}

        def start(self):
            raise OSError("start failure")

        def stop(self):
            raise OSError("stop failure")

        def status(self):
            return {"state": "audit_failed"}

    class Audit:
        def __init__(self, *args, **kwargs):
            pass

        def open(self):
            pass

        def close(self):
            closed.append(True)

    monkeypatch.setattr(module, "OutputPublisher", Publisher)
    monkeypatch.setattr(module, "JsonlSink", Audit)
    out = tmp_path / "cleanup"
    result = module.main(["--transport", "tcp", "--out-dir", str(out)])
    assert result != 0
    assert closed == [True]
    meta = json.loads((out / "session.json").read_text())
    assert "start failure" in meta["end_reason"]
    assert any("stop failure" in error for error in meta["cleanup_errors"])
    assert meta["output_status"]["state"] == "audit_failed"


def test_durable_hooks_commit_intent_before_com_and_result_before_ack():
    steps = []
    class Journal:
        def begin_attempt(self, pi, run, sequence, barrier, payload):
            assert (pi, run, sequence, barrier, payload) == (
                'pi-1', 'run-1', 7, None, b'%+0.12345\r\n')
            steps.append('intent')
            return 'attempt'
        def finish_attempt(self, attempt, outcome):
            assert (attempt, outcome) == ('attempt', 'written')
            steps.append('result')
    class OrderedCom(Com):
        def write(self, payload):
            steps.append('com')
            return super().write(payload)
    class OrderedLink(Link):
        def send(self, message):
            if message['type'] == 'ack':
                steps.append('ack')
            super().send(message)
    BridgeSession(journal=Journal(), pi_id='pi-1').exchange(OrderedLink(reply()), OrderedCom())
    assert steps == ['intent', 'com', 'result', 'ack']


@pytest.mark.parametrize('status,barrier', [(ValueStatus.VALID, 3),
                                          (ValueStatus.UNREADABLE, None)])
def test_durable_metadata_is_validated_before_intent(status, barrier):
    class Journal:
        def begin_attempt(self, *args):
            pytest.fail('malformed barrier reached durable intent')
    com = Com()
    with pytest.raises(BridgeError, match='barrier'):
        BridgeSession(journal=Journal(), pi_id='pi-1').exchange(
            Link(reply(status, barrier_id=barrier)), com)
    assert com.payloads == []


def test_cli_separates_pi_uart_from_gsv_output_rate(tmp_path, monkeypatch):
    from dispread import gsv_bridge
    opened = []
    class Port:
        def close(self): pass
    def serial(port, baudrate):
        opened.append((port, baudrate))
        return Port()
    monkeypatch.setattr(gsv_bridge, '_serial', serial)
    def stop(*args): raise KeyboardInterrupt
    monkeypatch.setattr(gsv_bridge.BridgeSession, 'exchange', stop)
    assert gsv_bridge.main(['--uart-port', 'COM9', '--com-port', 'COM4', '--log', str(tmp_path / 'cli.log')]) == 0
    assert opened == [('COM4', 115200), ('COM9', 460800)]
# --- B2 (2026-11-11): Taktnachricht, Auffuellen verlorener Takte auf Windows ---------

ORIGIN = 1_794_397_184_000_000_000


def tick_reply(seq, *, valid=True, text="0.63956", frame=None, time_ns=None, **changes):
    return dict(version=1, type="tick", run_id="run-1", seq=seq, valid=valid,
                value_text=text if valid else None,
                frame_sequence=(frame if frame is not None else seq) if valid else None,
                time_unix_ns=time_ns if time_ns is not None else ORIGIN + seq * 100_000_000 - 40_000_000,
                origin_unix_ns=ORIGIN, rate_hz=10, release="test_unaccepted") | changes


class SeqLink(Link):
    def __init__(self, replies):
        super().__init__(None)
        self.replies = list(replies)

    def receive(self):
        return dict(self.replies.pop(0), request_id=self.messages[-1]["request_id"])


def tick_session(tmp_path, **kwargs):
    from dispread_bridge_app.delivery_journal import DeliveryJournal

    journal = DeliveryJournal(tmp_path / "audit.sqlite")
    kwargs.setdefault("release_gate", lambda link, run: run == "run-1")
    return BridgeSession(journal=journal, pi_id="pi-1", **kwargs), journal


def run_ticks(session, replies, com=None):
    com = com or Com()
    link = SeqLink(replies)
    outcomes = [session.exchange(link, com) for _ in replies]
    return outcomes, com, [m for m in link.messages if m["type"] == "tick_ack"]


def test_tick_is_written_as_four_channel_line_and_acknowledged(tmp_path):
    session, journal = tick_session(tmp_path)
    outcomes, com, acks = run_ticks(session, [tick_reply(1), tick_reply(2, valid=False)])
    assert outcomes == ["written", "written"]
    assert com.payloads == [b"%0.63956;1;1;1794397184.060000\r\n",
                            b"%99999999.0;0;2;1794397184.160000\r\n"]
    assert [(a["seq"], a["outcome"], a["filled"]) for a in acks] == [(1, "written", 0), (2, "written", 0)]
    assert set(acks[0]) == {"version", "type", "request_id", "run_id", "seq", "outcome", "filled"}
    assert session.tick_stats() == dict(run_id="run-1", ticks_written=2, ticks_invalid=1, ticks_filled=0,
                                         tick_disturbed=False)


def test_sequence_jump_is_filled_with_nominal_time_invalid_lines(tmp_path):
    from dispread.live.tick import nominal_unix_ns

    session, journal = tick_session(tmp_path)
    outcomes, com, acks = run_ticks(session, [tick_reply(1), tick_reply(5)])
    lines = [p.decode() for p in com.payloads]
    assert [line.split(";")[2] for line in lines] == ["1", "2", "3", "4", "5"]
    for seq in (2, 3, 4):
        micros = (nominal_unix_ns(ORIGIN, 10, seq) + 500) // 1000
        assert lines[seq - 1] == f"%99999999.0;0;{seq};{micros // 1_000_000}.{micros % 1_000_000:06d}\r\n"
    assert acks[-1]["filled"] == 3
    assert [(row.seq, row.kind, row.outcome) for row in journal.tick_attempts()] == [
        (1, "tick", "written"), (2, "fill", "written"), (3, "fill", "written"),
        (4, "fill", "written"), (5, "tick", "written")]
    assert session.tick_stats()["ticks_filled"] == 3


def test_first_tick_after_late_start_is_filled_from_one(tmp_path):
    session, _ = tick_session(tmp_path)
    _, com, acks = run_ticks(session, [tick_reply(4)])
    assert [p.split(b";")[2] for p in com.payloads] == [b"1", b"2", b"3", b"4"]
    assert acks[0]["filled"] == 3


def test_gap_above_window_is_not_filled_and_marks_disturbed(tmp_path):
    session, journal = tick_session(tmp_path)
    _, com, acks = run_ticks(session, [tick_reply(1), tick_reply(53)])
    assert [p.split(b";")[2] for p in com.payloads] == [b"1", b"53"]      # 51 fehlende > 50
    assert acks[-1]["filled"] == 0
    assert journal.tick_gaps("pi-1", "run-1") == ((53, 51),)
    assert session.tick_stats()["tick_disturbed"] is True
    _, com2, _ = run_ticks(session, [tick_reply(54)])
    assert session.tick_stats()["tick_disturbed"] is True                  # bleibt im Lauf


def test_gap_of_exactly_window_is_filled(tmp_path):
    session, _ = tick_session(tmp_path)
    _, com, acks = run_ticks(session, [tick_reply(1), tick_reply(52)])
    assert len(com.payloads) == 52 and acks[-1]["filled"] == 50
    assert session.tick_stats()["tick_disturbed"] is False


def test_journal_precedes_every_com_line(tmp_path):
    session, journal = tick_session(tmp_path)

    class CheckingCom(Com):
        def write(self, payload):
            pending = [row for row in journal.tick_attempts() if row.outcome == "pending"]
            assert len(pending) == 1 and payload.split(b";")[2] == str(pending[0].seq).encode()
            return super().write(payload)
    run_ticks(session, [tick_reply(1), tick_reply(4)], CheckingCom())
    assert journal.unresolved_ticks() == ()


def test_tick_never_writes_without_test_release(tmp_path):
    session, _ = tick_session(tmp_path)
    for reply in (tick_reply(1, run_id="other"), tick_reply(1, release=None)):
        com = Com()
        with pytest.raises(BridgeError, match="gesperrt"):
            session.exchange(SeqLink([reply]), com)
        assert com.payloads == []


def test_tick_requires_durable_journal():
    com = Com()
    session = BridgeSession(release_gate=lambda link, run: True)
    with pytest.raises(BridgeError):
        session.exchange(SeqLink([tick_reply(1)]), com)
    assert com.payloads == []


@pytest.mark.parametrize("changes", [
    {"value_text": "1E+300"}, {"value_text": "NaN"}, {"value_text": "99999999.0"},
    {"valid": False, "value_text": "1.0"}, {"seq": 0}, {"rate_hz": 20}, {"time_unix_ns": -5},
])
def test_malformed_tick_never_reaches_journal_or_com(tmp_path, changes):
    session, journal = tick_session(tmp_path)
    com = Com()
    with pytest.raises(BridgeError):
        session.exchange(SeqLink([tick_reply(1) | changes]), com)
    assert com.payloads == [] and journal.tick_attempts() == ()


def test_out_of_order_or_repeated_tick_is_never_written_twice(tmp_path):
    session, journal = tick_session(tmp_path)
    run_ticks(session, [tick_reply(1), tick_reply(3)])
    outcomes, com, acks = run_ticks(session, [tick_reply(3)])   # Wiederholung: nur erneute Quittung
    assert outcomes == ["written"] and com.payloads == [] and acks[0]["outcome"] == "written"
    with pytest.raises(BridgeError, match="order"):
        run_ticks(session, [tick_reply(2)])                    # bereits aufgefuellt


def test_expired_tick_is_acknowledged_and_later_filled(tmp_path):
    now = [0]
    session, journal = tick_session(tmp_path, clock=lambda: now[0])

    class SlowLink(SeqLink):
        def receive(self):
            now[0] += 2_000_000_000                              # Budget von 1 s verbraucht
            return super().receive()
    com = Com()
    assert session.exchange(SlowLink([tick_reply(1)]), com) == "expired"
    assert com.payloads == []
    _, com2, acks = run_ticks(session, [tick_reply(2)])
    assert [p.split(b";")[:3] for p in com2.payloads] == [[b"%99999999.0", b"0", b"1"], [b"%0.63956", b"1", b"2"]]
    assert acks[0]["filled"] == 1


def test_com_failure_marks_line_unknown_and_blocks(tmp_path):
    from dispread.gsv_bridge import DeliveryUncertainError

    session, journal = tick_session(tmp_path)
    with pytest.raises(BridgeError, match="COM"):
        session.exchange(SeqLink([tick_reply(1)]), Com(short=True))
    assert [row.outcome for row in journal.tick_attempts()] == ["unknown"]
    com = Com()
    with pytest.raises(DeliveryUncertainError):
        session.exchange(SeqLink([tick_reply(2)]), com)
    assert com.payloads == []


def test_tick_stats_reset_on_new_run(tmp_path):
    session, _ = tick_session(tmp_path, release_gate=lambda link, run: True)
    run_ticks(session, [tick_reply(1), tick_reply(60)])
    assert session.tick_stats()["tick_disturbed"] is True
    run_ticks(session, [tick_reply(1, run_id="run-2")])
    assert session.tick_stats() == dict(run_id="run-2", ticks_written=1, ticks_invalid=0, ticks_filled=0,
                                        tick_disturbed=False)
