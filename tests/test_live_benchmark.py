from dotmatrix_helpers import LAYOUT, QUAD, embed, synthetic_reader

from dispread.live.benchmark import time_read_chain


def test_time_read_chain_reports_stats_and_reads_value():
    ticks = iter(range(0, 10_000_000_000, 2_000_000))  # jeder Aufruf +2 ms
    stats = time_read_chain(
        synthetic_reader(), embed("+ 1.2345 "), QUAD, LAYOUT, repeats=5, clock=lambda: next(ticks)
    )
    assert stats["repeats"] == 5
    assert stats["median_ms"] == 2.0 and stats["p95_ms"] == 2.0 and stats["max_ms"] == 2.0
    assert stats["last_value"] == 1.2345 and stats["last_reject"] is None
