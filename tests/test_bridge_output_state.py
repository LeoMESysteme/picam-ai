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


# R1 (2026-11-09): bestaetigte Testfreigabe echter Werte.
from dispread.bridge.output_state import RELEASE_BLOCK, TEST_RELEASE  # noqa: E402


def real(seq=1, status=ValueStatus.VALID):
    base = record(seq, status)
    return ValueRecord(seq, Timestamp(seq * 1000, TimeBaseKind.V4L2_MONOTONIC), base.value, "mV/V", status,
                       1.0, "test", None, None, raw_text=base.raw_text, reject_reasons=base.reject_reasons)


def test_unconfirmed_real_state_stays_blocked_and_never_offers(tmp_path):
    state = OutputState(tmp_path)
    state.publish(real())
    reply = poll(state)
    assert reply["type"] == "idle" and reply["release_block"] == RELEASE_BLOCK and "release" not in reply
    assert state.release is None
    assert state.metadata()["release_block"] == RELEASE_BLOCK and state.metadata()["release"] is None


def test_confirmed_test_release_offers_real_values_marked_without_age(tmp_path):
    state = OutputState(tmp_path, release=TEST_RELEASE)
    state.start()
    assert state.metadata()["release_block"] is None and state.metadata()["release"] == TEST_RELEASE
    assert state.status()["release_block"] is None and state.status()["release"] == TEST_RELEASE
    assert poll(state, "empty") == dict(version=1, request_id="empty", run_id=state.run_id, demo=False,
                                        type="idle", release_block=None, release=TEST_RELEASE)
    state.publish(real(7))
    offered = poll(state)
    assert (offered["type"], offered["demo"], offered["release"]) == ("record", False, TEST_RELEASE)
    assert offered["frame_age_ns"] is None and offered["barrier_id"] is None
    assert offered["record"] == real(7).to_dict()
    assert state.handle_v1(ack(offered)) is None
    after = poll(state, "after")
    assert after["type"] == "idle" and after["release"] == TEST_RELEASE
    state.stop()
    events = [json.loads(line) for line in (tmp_path / "output.jsonl").read_text().splitlines()]
    assert events[0]["release"] == TEST_RELEASE and events[0]["release_block"] is None
    assert any(e["event"] == "offered" and e["release"] == TEST_RELEASE for e in events)


def test_test_release_barrier_is_acknowledged_as_omission_never_as_com_write(tmp_path):
    state = OutputState(tmp_path, release=TEST_RELEASE)
    state.publish(real(1))
    state.publish(real(2, ValueStatus.UNREADABLE))
    barrier = poll(state)
    assert barrier["record"]["status"] == "unreadable" and barrier["barrier_id"] == 1
    with pytest.raises(ValueError, match="VALID"):
        state.handle_v1(ack(barrier))  # "written" fuer eine Ungueltigkeit: nie an COM
    state.handle_v1(ack(barrier, outcome="omitted"))
    # Der aeltere gueltige Wert 1 kommt nach der Invalidierung nie mehr.
    assert poll(state, "next")["type"] == "idle"
    state.publish(real(3))
    assert poll(state, "new")["record"]["frame_sequence"] == 3


@pytest.mark.parametrize("demo", [True, False])
def test_invalid_latest_is_carried_only_by_its_barrier(tmp_path, demo):
    state = OutputState(tmp_path, demo=demo, release=None if demo else TEST_RELEASE)
    make = record if demo else real
    state.publish(make(1))
    state.publish(make(2, ValueStatus.UNREADABLE))
    barrier = poll(state)
    state.handle_v1(ack(barrier, outcome="written" if demo else "omitted"))
    assert poll(state, "next")["type"] == "idle"


def test_demo_never_accepts_omission_ack(tmp_path):
    state = OutputState(tmp_path, demo=True)
    state.publish(record(1, ValueStatus.UNREADABLE))
    with pytest.raises(ValueError):
        state.handle_v1(ack(poll(state), outcome="omitted"))


def test_test_release_never_offers_a_value_older_than_the_freshness_limit(tmp_path):
    now = [0]
    state = OutputState(tmp_path, release=TEST_RELEASE, max_offer_age_ns=1_000_000_000, clock=lambda: now[0])
    state.start()
    state.publish(real(1))
    now[0] = 1_000_000_001
    assert poll(state)["type"] == "idle"
    state.publish(real(2))
    assert poll(state, "fresh")["record"]["frame_sequence"] == 2
    state.stop()
    events = [json.loads(line) for line in (tmp_path / "output.jsonl").read_text().splitlines()]
    assert any(e["event"] == "stale_skipped" and e["frame_sequence"] == 1 for e in events)


@pytest.mark.parametrize("kwargs", [dict(release="accepted"), dict(demo=True, release=TEST_RELEASE)])
def test_release_marker_is_exact_and_never_for_demo(tmp_path, kwargs):
    with pytest.raises(ValueError):
        OutputState(tmp_path, **kwargs)
