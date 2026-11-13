"""Deterministische Takt-/Uhrtests, keine reale Wartezeit."""
from dataclasses import replace

import pytest
from test_userdefined_formatter import record

from dispread.live.clock import ClockLog
from dispread.records import TimeBaseKind, Timestamp, ValueStatus


class Clocks:
    def __init__(self):
        self.now = 0
        self.wall_offset = 1_794_397_184_000_000_000

    def read(self, kind):
        import time

        return self.now + (self.wall_offset if kind == time.CLOCK_REALTIME else 0)


def ticker(rate=10, max_age=100_000_000):
    from dispread.live.tick import Ticker, TickTimebase

    clocks = Clocks()
    log = ClockLog(measure=lambda: 1000, monotonic_ns=lambda: clocks.now)
    log.sample()
    timebase = TickTimebase(log, clock=clocks.read, ntp_status='yes')
    return Ticker(rate, lambda: clocks.now, max_age, timebase=timebase), clocks


def captured(ns, seq=1, **kw):
    return replace(record(), capture_timestamp=Timestamp(ns, TimeBaseKind.V4L2_MONOTONIC),
                   frame_sequence=seq, **kw)


def test_fixed_grid_skips_late_ticks_without_catchup():
    t, _ = ticker()
    assert t.due(99_999_999) is None
    assert t.due(100_000_000).seq == 1
    late = t.due(455_000_000)
    assert late.seq == 4 and not late.valid
    assert t.due(455_000_000) is None
    assert t.due(499_999_999) is None
    assert t.due(500_000_000).seq == 5
    assert t.stats() == {'seq': 5, 'total': 3, 'valid': 0, 'invalid': 3, 'missed': 2}


def test_same_number_new_frame_is_valid_but_old_frame_never_repeats():
    t, _ = ticker()
    t.on_record(captured(90_000_000))
    first = t.due(100_000_000)
    assert first.valid and first.frame_sequence == 1
    assert first.time_unix_ns == 1_794_397_184_090_000_000
    assert not t.due(200_000_000).valid
    t.on_record(captured(290_000_000, seq=2))
    assert t.due(300_000_000).valid
    t.on_record(captured(390_000_000, seq=2))  # same frame cannot be reused
    assert not t.due(400_000_000).valid


@pytest.mark.parametrize('capture,now,max_age', [
    (90_000_000, 100_000_000, 10_000_000),  # age must be BELOW bound
    (101_000_000, 100_000_000, 200_000_000),  # future capture
])
def test_age_and_capture_window(capture, now, max_age):
    t, _ = ticker(max_age=max_age)
    t.on_record(captured(capture))
    assert not t.due(now).valid


@pytest.mark.parametrize('capture,now', [
    (0, 100_000_000),  # aus dem vorigen Takt, noch nicht gesendet
    (150_000_000, 355_000_000),  # aus einem verpassten Takt, jünger als die Altersgrenze
])
def test_unsent_fresh_frame_from_earlier_window_is_valid_with_its_capture_time(capture, now):
    """Auswertung dauert 50-90 ms: ein frisches, noch nicht gesendetes Bild aus dem
    vorigen Fenster ist gültig; der Zeitkanal trägt seine echte Erfassungszeit."""
    t, _ = ticker(max_age=500_000_000)
    t.on_record(captured(capture))
    tick = t.due(now)
    assert tick.valid
    assert tick.time_unix_ns == t.timebase.unix_ns(capture)


def test_invalid_latest_record_is_a_barrier():
    t, _ = ticker()
    t.on_record(captured(80_000_000))
    t.on_record(captured(90_000_000, seq=2, value=None, status=ValueStatus.UNREADABLE,
                         reject_reasons=('unlesbar',)))
    assert not t.due(100_000_000).valid


@pytest.mark.parametrize('base', [TimeBaseKind.SYNTHETIC, TimeBaseKind.FILE_MTIME])
def test_non_time_bearing_capture_is_never_valid(base):
    t, _ = ticker()
    t.on_record(replace(captured(90_000_000), capture_timestamp=Timestamp(90_000_000, base)))
    assert not t.due(100_000_000).valid


def test_boottime_capture_uses_measured_conversion():
    t, _ = ticker()
    t.on_record(replace(captured(90_000_000),
                        capture_timestamp=Timestamp(90_001_000, TimeBaseKind.SENSOR_BOOTTIME)))
    assert t.due(100_000_000).time_unix_ns == 1_794_397_184_090_000_000


def test_realtime_step_does_not_change_output_time_and_is_logged():
    t, clocks = ticker()
    first = t.due(100_000_000)
    clocks.wall_offset += 5_000_000_000
    clocks.now = 200_000_000
    second = t.due(clocks.now)
    assert second.time_unix_ns - first.time_unix_ns == 100_000_000
    meta = t.timebase.status()
    assert meta['realtime_minus_monotonic_ns'] == 1_794_397_184_000_000_000
    assert meta['realtime_jump_detected'] is True
    assert meta['realtime_max_deviation_ns'] == 5_000_000_000
    assert meta['ntp_synchronized'] == 'yes' and meta['time_uncertainty_ns'] is None


@pytest.mark.parametrize('rate', [0, 11, -1, True, '10', float('nan'), float('inf')])
def test_rate_rejected(rate):
    with pytest.raises(ValueError):
        ticker(rate)


@pytest.mark.parametrize('text', ['99999999.0', '+099999999.00', '1e2'])
def test_reserved_or_nondecimal_value_cannot_be_valid(text):
    t, _ = ticker()
    t.on_record(captured(90_000_000, raw_text=text, value=float(text)))
    assert not t.due(100_000_000).valid


def test_suspend_rejects_even_boottime_capture_that_appears_fresh():
    t, _ = ticker()
    t.timebase.clock_log._measure = lambda: 2_001_000  # > 1ms change, suspend
    t.on_record(replace(captured(90_000_000),
                        capture_timestamp=Timestamp(90_001_000, TimeBaseKind.SENSOR_BOOTTIME)))
    assert not t.due(100_000_000).valid


def test_offset_measurement_brackets_realtime_and_records_uncertainty():
    import time

    from dispread.live.tick import TickTimebase

    samples = iter([(time.CLOCK_MONOTONIC, 100), (time.CLOCK_REALTIME, 10_000),
                    (time.CLOCK_MONOTONIC, 120)])

    def clock(kind):
        expected, value = next(samples)
        assert kind == expected
        return value

    log = ClockLog(measure=lambda: 1000, monotonic_ns=lambda: 0)
    log.sample()
    mapping = TickTimebase(log, clock=clock, ntp_status='no')
    assert mapping.status()['realtime_minus_monotonic_ns'] == 9890
    assert mapping.status()['offset_measurement_uncertainty_ns'] == 10
    assert mapping.status()['time_uncertainty_ns'] is None


@pytest.mark.parametrize('result', ['yes', 'no', 'garbage', 'error'])
def test_ntp_probe_preserves_unknown_instead_of_claiming_sync(monkeypatch, result):
    import subprocess
    from types import SimpleNamespace

    from dispread.live.tick import TickTimebase

    def probe(args, **kwargs):
        assert args == ['timedatectl', 'show', '--property=NTPSynchronized', '--value']
        assert kwargs['timeout'] == 1
        if result == 'error':
            raise subprocess.TimeoutExpired(args, 1)
        return SimpleNamespace(stdout=result + '\n')

    monkeypatch.setattr('dispread.live.tick.subprocess.run', probe)
    clocks = Clocks()
    log = ClockLog(measure=lambda: 0, monotonic_ns=lambda: 0)
    mapping = TickTimebase(log, clock=clocks.read)
    assert mapping.status()['ntp_synchronized'] == (result if result in ('yes', 'no') else 'unknown')
