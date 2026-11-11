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


@pytest.mark.parametrize("status", [ValueStatus.VALID, ValueStatus.UNREADABLE])
def test_test_release_never_offers_synthetic_time_base(tmp_path, status):
    state = OutputState(tmp_path, release=TEST_RELEASE)
    state.start()
    state.publish(real(1))
    state.publish(record(2, status))  # SYNTHETIC: keine echte Kamerazeitbasis
    reply = poll(state)
    assert reply["type"] == "idle"
    state.stop()
    events = [json.loads(line) for line in (tmp_path / "output.jsonl").read_text().splitlines()]
    assert not any(e["event"] == "offered" for e in events)
    assert any(e["event"] == "release_time_base_rejected" for e in events)


# --- B2 (2026-11-11): Vierkanal-Takt ueber die Bruecke -------------------------------

class TickClocks:
    """Gemeinsame Monoton-/Realzeit fuer Ticker und Zeitbasis, ohne Wartezeit."""

    def __init__(self):
        self.now = 0
        self.wall_offset = 1_794_397_184_000_000_000

    def read(self, kind):
        import time

        return self.now + (self.wall_offset if kind == time.CLOCK_REALTIME else 0)


def tick_state(tmp_path, *, release="test_unaccepted", rate=10, max_age_ns=500_000_000):
    from dispread.live.clock import ClockLog
    from dispread.live.tick import TickTimebase

    clocks = TickClocks()
    log = ClockLog(measure=lambda: 1000, monotonic_ns=lambda: clocks.now)
    log.sample()
    timebase = TickTimebase(log, clock=clocks.read, ntp_status="yes")
    state = OutputState(tmp_path, release=release, clock=lambda: clocks.now, tick_rate_hz=rate,
                        tick_max_frame_age_ns=max_age_ns, timebase=timebase, tick_thread=False)
    state.start()
    return state, clocks


def camera(seq, capture_ns, status=ValueStatus.VALID, text="1.2345"):
    return ValueRecord(seq, Timestamp(capture_ns, TimeBaseKind.V4L2_MONOTONIC),
                       float(text) if status is ValueStatus.VALID else None, "mV/V", status, 1.0, "test",
                       None, None, raw_text=text,
                       reject_reasons=() if status is ValueStatus.VALID else ("unreadable",))


def advance(state, clocks, ticks=1, period=100_000_000):
    produced = []
    for _ in range(ticks):
        clocks.now += period
        produced.append(state.step_ticks())
    return produced


def tick_ack(reply, **changes):
    return dict(version=1, type="tick_ack", request_id=reply["request_id"], run_id=reply["run_id"],
                seq=reply["seq"], outcome="written", filled=0) | changes


def events(tmp_path):
    return [json.loads(line) for line in (tmp_path / "output.jsonl").read_text().splitlines()]


def test_tick_mode_without_release_generates_and_offers_nothing(tmp_path):
    state, clocks = tick_state(tmp_path, release=None)
    state.publish(camera(1, 50_000_000))
    assert advance(state, clocks, 3) == [None, None, None]
    reply = poll(state)
    assert reply["type"] == "idle" and reply["release_block"]
    assert state.status()["tick"]["total"] == 0
    assert not any(e["event"].startswith("tick") for e in events(tmp_path))


def test_ticks_are_offered_in_order_without_latest_only_loss(tmp_path):
    state, clocks = tick_state(tmp_path)
    state.publish(camera(1, 50_000_000))
    advance(state, clocks)                               # Takt 1 gueltig
    advance(state, clocks)                               # Takt 2 ohne neues Bild
    state.publish(camera(2, 250_000_000, status=ValueStatus.UNREADABLE))
    advance(state, clocks)                               # Takt 3 ungueltig
    state.publish(camera(3, 350_000_000, text="1.2345"))
    advance(state, clocks)                               # Takt 4 gleicher Wert, neues Bild
    replies = []
    for index in range(4):
        reply = poll(state, f"r{index}")
        assert reply["type"] == "tick" and reply["release"] == "test_unaccepted"
        replies.append(reply)
        assert state.handle_v1(tick_ack(reply)) is None
    assert [r["seq"] for r in replies] == [1, 2, 3, 4]
    assert [r["valid"] for r in replies] == [True, False, False, True]
    assert replies[0]["value_text"] == "1.2345" and replies[0]["frame_sequence"] == 1
    assert replies[1]["value_text"] is None and replies[1]["frame_sequence"] is None
    origin = replies[0]["origin_unix_ns"]
    assert replies[1]["time_unix_ns"] == origin + 200_000_000      # Nominalzeit des Takts
    assert replies[0]["time_unix_ns"] == origin + 50_000_000       # Erfassungszeit des Bilds
    assert replies[0]["rate_hz"] == 10
    assert poll(state, "empty")["type"] == "idle"
    tick = state.status()["tick"]
    assert (tick["offered"], tick["acknowledged"], tick["lost"], tick["queued"]) == (4, 4, 0, 0)


def test_ticks_older_than_window_are_lost_and_visible_in_sequence(tmp_path):
    state, clocks = tick_state(tmp_path)
    advance(state, clocks, 60)
    reply = poll(state)
    assert reply["seq"] == 11
    tick = state.status()["tick"]
    assert tick["lost"] == 10 and tick["queued"] == 49 and tick["seq"] == 60
    lost = [e for e in events(tmp_path) if e["event"] == "tick_lost"]
    assert sum(e["count"] for e in lost) == 10 and lost[-1]["last_seq"] == 10


def test_tick_is_audited_before_it_can_be_offered(tmp_path):
    state, clocks = tick_state(tmp_path)
    advance(state, clocks)
    reply = poll(state)
    kinds = [(e["event"], e.get("seq")) for e in events(tmp_path)]
    assert kinds.index(("tick", 1)) < kinds.index(("tick_offered", 1))
    tick_event = next(e for e in events(tmp_path) if e["event"] == "tick")
    assert {k: tick_event[k] for k in ("valid", "value_text", "time_unix_ns", "frame_sequence")} == \
        {k: reply[k] for k in ("valid", "value_text", "time_unix_ns", "frame_sequence")}


def test_tick_audit_failure_never_enqueues(tmp_path):
    state, clocks = tick_state(tmp_path)

    class Broken:
        def write(self, _):
            raise OSError("disk full")

        def flush(self):
            pass

        def close(self):
            pass
    state._events = Broken()
    with pytest.raises(OSError):
        advance(state, clocks)
    assert state.status()["state"] == "audit_failed"
    assert poll(state)["type"] == "ended"                # nie ein unauditierter Takt
    assert state.status()["tick"]["queued"] == 0


def test_tick_ack_outcomes_and_strict_binding(tmp_path):
    state, clocks = tick_state(tmp_path)
    advance(state, clocks, 4)
    first = poll(state, "a")
    for wrong in ({"seq": 2}, {"request_id": "x"}, {"run_id": "other"}):
        with pytest.raises(ValueError):
            state.handle_v1(tick_ack(first, **wrong))
    with pytest.raises(ValueError):  # eine Wertquittung passt nie auf einen Takt
        state.handle_v1(dict(version=1, type="ack", request_id="a", run_id=first["run_id"],
                             frame_sequence=1, barrier_id=None, outcome="written"))
    state.handle_v1(tick_ack(first))
    second = poll(state, "b")
    state.handle_v1(tick_ack(second, outcome="expired"))
    third = poll(state, "c")
    state.abandon_pending()                              # Verbindung verloren
    fourth = poll(state, "d")
    assert fourth["seq"] == 4 and third["seq"] == 3      # nie erneut angeboten
    state.handle_v1(tick_ack(fourth, outcome="failed"))
    tick = state.status()["tick"]
    assert (tick["acknowledged"], tick["lost"], tick["unconfirmed"]) == (1, 1, 2)


def test_tick_mode_rejects_non_camera_time_base_as_invalid_tick(tmp_path):
    state, clocks = tick_state(tmp_path)
    state.publish(record())                              # synthetische Zeitbasis
    advance(state, clocks)
    reply = poll(state)
    assert reply["valid"] is False
    assert any(e["event"] == "release_time_base_rejected" for e in events(tmp_path))


def test_tick_stop_accounts_for_every_generated_tick(tmp_path):
    state, clocks = tick_state(tmp_path)
    state.drain_timeout_s = 0
    advance(state, clocks, 5)
    state.handle_v1(tick_ack(poll(state, "a")))
    poll(state, "b")
    state.stop()
    tick = state.status()["tick"]
    assert tick["total"] == 5
    assert tick["acknowledged"] + tick["unconfirmed"] + tick["lost"] + tick["queued"] == tick["total"]
    assert (tick["acknowledged"], tick["unconfirmed"], tick["lost"], tick["queued"]) == (1, 1, 3, 0)
    assert poll(state, "c")["type"] == "ended"


def test_tick_mode_metadata_and_constraints(tmp_path):
    state, _ = tick_state(tmp_path)
    meta = state.metadata()
    assert meta["format"] == "4ch" and meta["rate_hz"] == 10
    assert meta["formatter"]["format_id"] == "gsvmulti_userdefined_4ch_v1"
    assert meta["formatter"]["supported_invalid_policies"] == ["mark_record"]
    assert meta["tick"]["time_base"] == "unix_realtime_from_monotonic"
    with pytest.raises(ValueError):
        OutputState(tmp_path, demo=True, tick_rate_hz=10)
    with pytest.raises(ValueError):
        OutputState(tmp_path, release="test_unaccepted", tick_rate_hz=11)


def test_tick_thread_failure_is_visible_not_silent(tmp_path):
    state, clocks = tick_state(tmp_path)

    def broken():
        raise RuntimeError("ticker defect")
    state.step_ticks = broken
    state._tick_loop()
    assert state.status()["state"] == "tick_failed" and "ticker defect" in state.status()["error"]
