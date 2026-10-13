from dispread.live.clock import ClockLog, measure_clock_offset_ns
from dispread.records import TimeBaseKind, Timestamp, to_boottime_ns


def test_measure_uses_median_of_bracketed_samples():
    values = iter([100, 1100, 102, 200, 1205, 202, 300, 1300, 302])  # je (MONO, BOOT, MONO)
    # Einzelversaetze: 1100-101=999, 1205-201=1004, 1300-301=999 -> Median 999
    assert measure_clock_offset_ns(samples=3, clock=lambda _clk: next(values)) == 999


def test_clock_log_session_dict_and_boottime_conversion():
    offsets, ticks = iter([5, 7]), iter([10, 20])
    log = ClockLog(measure=lambda: next(offsets), monotonic_ns=lambda: next(ticks))
    assert log.last_sample_monotonic_ns is None
    assert log.to_session(ended=False) == {"start": None, "end": None, "samples": []}
    assert log.to_session(ended=True) == {"start": None, "end": None, "samples": []}
    assert log.sample() == 5
    assert log.last_sample_monotonic_ns == 10
    assert log.to_session(ended=False) == {"start": 5, "end": None, "samples": [[10, 5]]}
    assert log.sample() == 7
    assert log.last_sample_monotonic_ns == 20
    assert log.to_session(ended=False) == {
        "start": 5,
        "end": None,
        "samples": [[10, 5], [20, 7]],
    }
    session = {"clock_offset_boottime_minus_monotonic_ns": log.to_session(ended=True)}
    assert session["clock_offset_boottime_minus_monotonic_ns"] == {
        "start": 5,
        "end": 7,
        "samples": [[10, 5], [20, 7]],
    }
    stamp = Timestamp(value_ns=1_000, base=TimeBaseKind.V4L2_MONOTONIC).to_dict()
    assert to_boottime_ns(stamp, session) == 1_005
