import json

import pytest

from dispread.bridge.output_state import OutputState
from dispread.records import TimeBaseKind, Timestamp, ValueRecord, ValueStatus


def record(seq=1, status=ValueStatus.VALID):
    return ValueRecord(
        seq,
        Timestamp(1, TimeBaseKind.SYNTHETIC),
        1.0 if status is ValueStatus.VALID else None,
        "mV/V",
        status,
        1.0,
        "test",
        None,
        None,
        raw_text="1.0",
        reject_reasons=() if status is ValueStatus.VALID else ("unreadable",),
    )


def poll(state, request="req"):
    return state.handle_v1(dict(version=1, type="poll", request_id=request))


def ack(reply, **changes):
    return (
        dict(
            version=1,
            type="ack",
            request_id=reply["request_id"],
            run_id=reply["run_id"],
            frame_sequence=reply["record"]["frame_sequence"],
            barrier_id=reply["barrier_id"],
            outcome="written",
        )
        | changes
    )


def test_invalid_barrier_survives_disconnect_and_new_valid(tmp_path):
    state = OutputState(tmp_path, demo=True)
    state.publish(record(status=ValueStatus.UNREADABLE))
    first = poll(state)
    state.abandon_pending()
    state.publish(record(2))
    again = poll(state, "again")
    assert again["record"]["status"] == "unreadable"
    assert again["barrier_id"] == first["barrier_id"]
    state.handle_v1(ack(again))
    assert poll(state, "new")["record"]["frame_sequence"] == 2


def test_uncertain_write_never_reoffers_same_numeric_frame(tmp_path):
    state = OutputState(tmp_path, demo=True)
    state.start()
    state.publish(record())
    poll(state)
    state.abandon_pending()
    assert poll(state, "again")["type"] == "idle"
    state.stop()
    events = [json.loads(line) for line in (tmp_path / "output.jsonl").read_text().splitlines()]
    assert any(e["event"] == "unconfirmed" and e["frame_sequence"] == 1 for e in events)


@pytest.mark.parametrize("changes", [{"run_id": "wrong"}, {"request_id": "wrong"}, {"barrier_id": 99}])
def test_wrong_run_request_barrier_ack_is_rejected(tmp_path, changes):
    state = OutputState(tmp_path, demo=True)
    state.publish(record(status=ValueStatus.UNREADABLE))
    reply = poll(state)
    with pytest.raises(ValueError):
        state.handle_v1(ack(reply, **changes))
    state.handle_v1(ack(reply))


def test_new_invalid_generation_survives_older_barrier_ack(tmp_path):
    state = OutputState(tmp_path, demo=True)
    state.publish(record(status=ValueStatus.UNREADABLE))
    old = poll(state)
    state.publish(record(2, ValueStatus.STALE))
    state.handle_v1(ack(old))
    assert poll(state, "next")["record"]["frame_sequence"] == 2


def test_non_demo_remains_blocked_and_state_opens_no_transport(tmp_path):
    state = OutputState(tmp_path)
    state.start()
    state.publish(record())
    assert poll(state)["release_block"]
    assert state.metadata()["formatter"]["provisional"]
    assert state.status()["release_block"]
    state.stop()
    assert poll(state, "end")["type"] == "ended"
