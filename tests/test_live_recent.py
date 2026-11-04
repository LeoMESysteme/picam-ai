import pytest


def test_recent_strip_buckets_worst_status():
    from dispread.live.recent import RecentStrip

    strip = RecentStrip()
    strip.observe(100.01, 'valid', 1.0)
    strip.observe(100.02, 'unreadable', None)
    strip.observe(100.03, 'valid', 2.0)
    strip.observe(100.26, 'transition', None)
    assert strip.to_list(100.3) == [[0, 'u', 2.0], [250, 't', None]]


def test_recent_strip_drops_older_than_window():
    from dispread.live.recent import RecentStrip

    strip = RecentStrip(window_s=1.0)
    strip.observe(10.0, 'valid', 1.0)
    strip.observe(10.25, 'stale', None)
    strip.observe(10.5, 'valid', 3.0)
    assert strip.to_list(11.25) == [[0, 'v', 3.0]]
    assert strip.to_list(12.0) == []


def test_recent_strip_snapshot_anchors_now_after_last_observation():
    from dispread.live.recent import RecentStrip

    strip = RecentStrip()
    assert strip.snapshot(0.0) == ([], 0)
    strip.observe(0.0, 'valid', 1.0)
    strip.observe(2.0, 'valid', 2.0)
    entries, now_ms = strip.snapshot(5.0)
    assert entries == [[0, 'v', 1.0], [2000, 'v', 2.0]]
    assert now_ms == 5000
    assert now_ms - entries[-1][0] >= 3000 - 250
    assert strip.snapshot(61.0) == ([[0, 'v', 2.0]], 59000)
    assert strip.snapshot(62.0) == ([], 0)
    # Bereits gelieferte Ansichten bleiben unabhaengig vom Ablauf.
    assert entries == [[0, 'v', 1.0], [2000, 'v', 2.0]]


@pytest.mark.parametrize('statuses,worst', [
    (['valid', 'transition'], 't'), (['transition', 'unreadable'], 'u'),
    (['stale', 'unreadable', 'valid'], 's'),
])
def test_recent_strip_status_priority_and_copies(statuses, worst):
    from dispread.live.recent import RecentStrip

    strip = RecentStrip()
    for status in statuses:
        strip.observe(0.0, status, 4.0 if status == 'valid' else 99.0)
    result = strip.to_list(0.1)
    assert result == [[0, worst, 4.0 if 'valid' in statuses else None]]
    result[0][1] = 'v'
    assert strip.to_list(0.1)[0][1] == worst
