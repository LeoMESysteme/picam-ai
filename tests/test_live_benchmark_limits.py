"""Pi-Schutzgrenzen und Messung ohne Hardware pruefen."""

import importlib.util
from pathlib import Path

import pytest
from dotmatrix_helpers import LAYOUT, QUAD, embed, synthetic_reader


@pytest.fixture
def benchmark():
    spec = importlib.util.spec_from_file_location('live_reader_benchmark', Path('scripts/live-reader-benchmark.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('cpu,temp,throttled,violations', [
    (150.0, 74.999, 0, 0),
    (150.001, 40, 0, 1),
    (30, 75.0, 0, 1),
    (30, 76, 0, 1),
    (30, 40, 0x10000, 1),
    (151, 75, 1, 3),
    (50, None, None, 0),
])
def test_limit_evaluation(benchmark, cpu, temp, throttled, violations):
    assert len(benchmark.evaluate_limits(cpu, temp, throttled)) == violations


def test_sensor_readings_and_unavailable_sensors(benchmark, tmp_path, monkeypatch):
    sensor = tmp_path / 'temp'
    sensor.write_text('74500\n')
    assert benchmark.read_temperature(sensor) == 74.5
    assert benchmark.read_temperature(tmp_path / 'absent') is None
    sensor.write_text('kein Sensor')
    assert benchmark.read_temperature(sensor) is None
    monkeypatch.setattr(benchmark.shutil, 'which', lambda _: None)
    assert benchmark.read_throttled() is None
    monkeypatch.setattr(benchmark.shutil, 'which', lambda _: '/usr/bin/vcgencmd')
    class Result:
        stdout = 'throttled=0x50005\n'
    monkeypatch.setattr(benchmark.subprocess, 'run', lambda *a, **kw: Result())
    assert benchmark.read_throttled() == 0x50005


def test_run_records_peak_limits_and_reader_timing(benchmark, monkeypatch):
    monkeypatch.setattr(benchmark, 'read_temperature', lambda: 75.0)
    monkeypatch.setattr(benchmark, 'read_throttled', lambda: 0x10000)
    stats = benchmark.measure_run(synthetic_reader(), embed('+0.60972 '), QUAD, LAYOUT,
                                  repeats=3, duration=None, target_fps=0)
    assert stats['repeats'] == 3
    assert 0 < stats['reader_median_ms'] <= stats['reader_p90_ms']
    assert stats['frames_per_second'] > 0
    assert stats['cpu_percent_max'] >= 0
    assert stats['temperature_c_max'] == 75.0
    assert stats['throttled'] == '0x10000'
    assert len(stats['violations']) == 2


@pytest.mark.parametrize('violations,exit_code', [([], 0), (['CPU > 150 %'], 1)])
def test_main_returns_nonzero_for_limit_violation(benchmark, monkeypatch, tmp_path, violations, exit_code):
    import json

    import cv2
    from dotmatrix_helpers import GRID
    image = tmp_path / 'still.png'
    cv2.imwrite(str(image), embed('+0.60972 '))
    proposal = tmp_path / 'proposal.json'
    proposal.write_text(json.dumps({'grid': GRID.to_dict(), 'quad': QUAD}))
    monkeypatch.setattr(benchmark.DotMatrixReader, 'from_file', lambda *a: object())
    monkeypatch.setattr(benchmark, 'measure_run', lambda *a, **kw: {'violations': violations})
    calls = []
    monkeypatch.setattr(benchmark.cv2, 'getNumThreads', lambda: 6)
    monkeypatch.setattr(benchmark.cv2, 'setNumThreads', calls.append)
    assert benchmark.main(['--still', str(image), '--proposal', str(proposal)]) == exit_code
    assert calls == [2, 6]


def test_cpu_peak_uses_process_time_and_fails_even_if_average_is_lower(benchmark, monkeypatch):
    from types import SimpleNamespace
    clock = iter(i / 4 for i in range(100))
    cpu = iter([0.0, 0.0, 1.75, 1.75, 1.75])
    monkeypatch.setattr(benchmark.time, 'perf_counter', lambda: next(clock))
    monkeypatch.setattr(benchmark, '_cpu_seconds', lambda: next(cpu))
    monkeypatch.setattr(benchmark, 'read_temperature', lambda: 40.0)
    monkeypatch.setattr(benchmark, 'read_throttled', lambda: 0)
    monkeypatch.setattr(benchmark, 'rectify', lambda *a, **kw: SimpleNamespace(image=None))
    reader = SimpleNamespace(read=lambda *a: SimpleNamespace(value=1.0, diagnostics={}))
    stats = benchmark.measure_run(reader, None, None, None, repeats=10, duration=None, target_fps=0)
    assert stats['cpu_percent_max'] == 175.0
    assert stats['cpu_percent'] < 150
    assert stats['violations'] == ['CPU > 150 %']
    assert stats['repeats'] == 1  # Grenze erreicht: Lastlauf vorzeitig beendet


def test_cpu_clock_counts_user_and_system_time(benchmark, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(benchmark.os, 'times', lambda: SimpleNamespace(user=2.0, system=3.0))
    assert benchmark._cpu_seconds() == 5.0


def test_duration_and_target_rate_pace_reads(benchmark, monkeypatch):
    from types import SimpleNamespace
    now = [0.0]
    monkeypatch.setattr(benchmark.time, 'perf_counter', lambda: now[0])
    def advance(seconds):
        now[0] += seconds
    monkeypatch.setattr(benchmark.time, 'sleep', advance)
    monkeypatch.setattr(benchmark, '_cpu_seconds', lambda: 0.0)
    monkeypatch.setattr(benchmark, 'read_temperature', lambda: None)
    monkeypatch.setattr(benchmark, 'read_throttled', lambda: None)
    monkeypatch.setattr(benchmark, 'rectify', lambda *a, **kw: SimpleNamespace(image=None))
    def read(*args):
        advance(0.001)
        return SimpleNamespace(value=1.0, diagnostics={})
    stats = benchmark.measure_run(SimpleNamespace(read=read), None, None, None,
                                  repeats=1, duration=0.09, target_fps=30)
    assert stats['repeats'] == 3  # Dauer ersetzt --repeats
    assert stats['frames_per_second'] == pytest.approx(30)
    assert stats['reader_median_ms'] == pytest.approx(1)
    assert stats['violations'] == []


def test_tiny_final_cpu_interval_does_not_turn_one_clock_tick_into_overload(benchmark, monkeypatch):
    from types import SimpleNamespace
    ticks = iter([0, .25, .5, .75, 1, 1.25, 1.5, 1.75, 2, 2.001])
    cpu = iter([0, 0, .5, 1, 1.01, 1.01])
    monkeypatch.setattr(benchmark.time, 'perf_counter', lambda: next(ticks))
    monkeypatch.setattr(benchmark, '_cpu_seconds', lambda: next(cpu))
    monkeypatch.setattr(benchmark, 'read_temperature', lambda: None)
    monkeypatch.setattr(benchmark, 'read_throttled', lambda: None)
    monkeypatch.setattr(benchmark, 'rectify', lambda *a, **kw: SimpleNamespace(image=None))
    reader = SimpleNamespace(read=lambda *a: SimpleNamespace(value=None, diagnostics={}))
    stats = benchmark.measure_run(reader, None, None, None, repeats=2, duration=None, target_fps=0)
    assert stats['violations'] == []
    assert stats['cpu_percent_max'] < 150
