"""Vergleichslogik, Perzentile und Ungueltig-Erkennung von scripts/perf-report.py (ohne Hardware)."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def perf():
    path = Path(__file__).resolve().parents[1] / "scripts" / "perf-report.py"
    spec = importlib.util.spec_from_file_location("perf_report", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def base_metrics():
    m = {f"latency.{s}.p95_ms": 1.0 for s in ("locate", "rectify", "read", "gate", "build", "total")}
    m.update({
        "throughput.max_fps": 100.0,
        "throughput.fps30.achieved_fps": 30.0,
        "throughput.fps30.dropped_percent": 0.0,
        "quality.recognition_percent": 99.0,
    })
    return m


def test_percentile_nearest_rank(perf):
    values = list(range(1, 101))
    assert perf.percentile(values, 50) == 50
    assert perf.percentile(values, 95) == 95
    assert perf.percentile(values, 99) == 99
    assert perf.percentile([3.0], 99) == 3.0
    assert perf.percentile([5, 1, 3], 50) == 3  # unsortiert erlaubt
    with pytest.raises(ValueError):
        perf.percentile([], 50)


def test_distribution_has_max(perf):
    d = perf.distribution([1.0, 2.0, 10.0])
    assert d == {"p50": 2.0, "p95": 10.0, "p99": 10.0, "max": 10.0}


def test_compare_identical_is_ok(perf):
    rows = perf.compare(base_metrics(), base_metrics())
    assert rows and all(r["ok"] for r in rows)


def test_latency_limit_is_15_percent_with_floor(perf):
    base = base_metrics()
    now = dict(base, **{"latency.read.p95_ms": 1.149})
    assert all(r["ok"] for r in perf.compare(base, now))
    now["latency.read.p95_ms"] = 1.16
    bad = [r for r in perf.compare(base, now) if not r["ok"]]
    assert [r["metric"] for r in bad] == ["latency.read.p95_ms"]
    # kleine Stufe: 15 % von 0,01 ms waeren 0,0015 ms, es gilt der absolute Boden
    base["latency.gate.p95_ms"] = 0.01
    now = dict(base, **{"latency.gate.p95_ms": 0.05})
    assert next(r for r in perf.compare(base, now) if r["metric"] == "latency.gate.p95_ms")["ok"]
    now["latency.gate.p95_ms"] = 0.07
    assert not next(r for r in perf.compare(base, now) if r["metric"] == "latency.gate.p95_ms")["ok"]


def test_throughput_and_quality_limits(perf):
    base = base_metrics()
    assert all(r["ok"] for r in perf.compare(base, dict(base, **{"throughput.max_fps": 85.1})))
    assert not all(r["ok"] for r in perf.compare(base, dict(base, **{"throughput.max_fps": 84.0})))
    assert all(r["ok"] for r in perf.compare(base, dict(base, **{"quality.recognition_percent": 98.5})))
    assert not all(r["ok"] for r in perf.compare(base, dict(base, **{"quality.recognition_percent": 98.4})))
    assert not all(r["ok"] for r in perf.compare(base, dict(base, **{"throughput.fps30.dropped_percent": 1.5})))


def test_missing_metric_is_regression(perf):
    now = base_metrics()
    del now["throughput.max_fps"]
    rows = perf.compare(base_metrics(), now)
    assert [r["metric"] for r in rows if not r["ok"]] == ["throughput.max_fps"]


def test_probable_cause_names_worst_stage(perf):
    base = base_metrics()
    now = dict(base, **{"latency.read.p95_ms": 3.0, "latency.rectify.p95_ms": 1.3, "latency.total.p95_ms": 3.5})
    hints = perf.probable_cause(perf.compare(base, now))
    assert "'read'" in hints[0]


def test_format_compare_has_required_columns(perf):
    table = perf.format_compare(perf.compare(base_metrics(), base_metrics()))
    assert table.splitlines()[0].startswith("| Metrik | Baseline | Jetzt | Abweichung | Grenze")


@pytest.mark.parametrize("temp,throttled,foreign,expected", [
    (50.0, 0, 5.0, 0),
    (74.9, 0x50000, 5.0, 0),  # nur Historienbits: gueltig
    (75.0, 0, 5.0, 1),
    (50.0, 0x1, 5.0, 1),
    (50.0, 0x4, 90.0, 2),
    (None, None, None, 0),  # fehlende Sensoren: nicht ungueltig, aber im Bericht als nicht verfuegbar
])
def test_invalid_reasons(perf, temp, throttled, foreign, expected):
    assert len(perf.invalid_reasons(temp, throttled, foreign)) == expected


def test_aggregate_median_and_skips_invalid(perf):
    runs = [
        {"invalid": [], "metrics": {"a": 1.0}},
        {"invalid": ["Drosselung"], "metrics": {"a": 100.0}},
        {"invalid": [], "metrics": {"a": 3.0}},
        {"invalid": [], "metrics": {"a": 2.0}},
    ]
    agg = perf.aggregate(runs)
    assert agg["metrics"]["a"] == 2.0 and agg["spread"]["a"] == [1.0, 3.0]
    assert perf.aggregate([{"invalid": ["x"], "metrics": {"a": 1.0}}]) == {}


def test_host_mismatch(perf):
    a = {"model": "Pi 5", "cores": 4, "source": "synthetic"}
    assert perf.host_mismatch(a, dict(a)) == []
    assert len(perf.host_mismatch(a, dict(a, cores=8))) == 1
