#!/usr/bin/env python3
"""Leserlaufzeit und Pi-Schutz auf gespeicherten Bildern messen.

    PYTHONPATH=src ./.venv/bin/python scripts/live-reader-benchmark.py \
        --still var/live/<lauf>/setup/still.png \
        --proposal var/live/<lauf>/setup/proposal.json --duration 60

Zielrate 30 Bilder/s; --target-fps 0 misst den maximalen Durchsatz.
CPU > 150 %, SoC >= 75 Grad oder Drosselbits fuehren zu Exit 1.
Fehlende Sensoren werden als null ausgewiesen (kein Schutz-Nachweis).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import cv2
from _devdata import input_path

from dispread.charcells import CharGrid
from dispread.layout import CharLayout
from dispread.live import DEFAULT_TEMPLATES, DEFAULT_TEMPLATES_SHA256, LIVE_CV_THREADS
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.rectify import rectify


def evaluate_limits(cpu_percent: float, temperature_c: float | None, throttled: int | None) -> list[str]:
    violations = []
    if cpu_percent > 150:
        violations.append("CPU > 150 %")
    if temperature_c is not None and temperature_c >= 75:
        violations.append("SoC >= 75 Grad")
    if throttled is not None and throttled != 0:
        violations.append(f"Drosselung: {hex(throttled)}")
    return violations


def read_temperature(path: Path = Path('/sys/class/thermal/thermal_zone0/temp')) -> float | None:
    try:
        return float(path.read_text().strip()) / 1000
    except (OSError, ValueError):
        return None


def read_throttled() -> int | None:
    command = shutil.which('vcgencmd')
    if command is None:
        return None
    try:
        result = subprocess.run([command, 'get_throttled'], capture_output=True, text=True, check=True, timeout=1)
        return int(result.stdout.strip().split('=', 1)[1], 16)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def _cpu_seconds() -> float:
    usage = os.times()
    return usage.user + usage.system


def measure_run(reader, image, quad, layout, *, repeats: int, duration: float | None, target_fps: float) -> dict:
    """Lesen, Entzerren und Prozesslast mit regelmaessigen Sensorproben messen."""
    reader_ms, chain_ms, cpu_samples = [], [], []
    temperatures, throttle_samples = [], []
    violations: list[str] = []
    start = last_sample = time.perf_counter()
    cpu_start = last_cpu = _cpu_seconds()
    result = None

    def sample(now):
        nonlocal last_sample, last_cpu
        cpu = _cpu_seconds()
        elapsed = now - last_sample
        # os.times hat eine grobe Tick-Aufloesung. Ein winziger Rest
        # nach der letzten Sekunde darf keinen falschen CPU-Peak erzeugen.
        percent = 100 * (cpu - last_cpu) / elapsed if elapsed >= 0.1 else 0.0
        cpu_samples.append(percent)
        temperature, throttled = read_temperature(), read_throttled()
        if temperature is not None:
            temperatures.append(temperature)
        if throttled is not None:
            throttle_samples.append(throttled)
        for violation in evaluate_limits(percent, temperature, throttled):
            if violation not in violations:
                violations.append(violation)
        last_sample, last_cpu = now, cpu

    # Temperatur und Drosselbits auch vor dem ersten Lesen erfassen.
    sample(start)
    while (time.perf_counter() - start < duration if duration is not None else len(reader_ms) < repeats):
        t0 = time.perf_counter()
        crop = rectify(image, quad, target_size=(400, 160))
        t_read = time.perf_counter()
        result = reader.read(crop.image, layout)
        end = time.perf_counter()
        reader_ms.append((end - t_read) * 1000)
        chain_ms.append((end - t0) * 1000)
        if target_fps > 0:
            remaining = start + len(reader_ms) / target_fps - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
        now = time.perf_counter()
        if now - last_sample >= 1:
            sample(now)
            if violations:
                break
    end = time.perf_counter()
    sample(end)
    elapsed = end - start
    cpu_average = 100 * (_cpu_seconds() - cpu_start) / elapsed if elapsed > 0 else 0.0
    for violation in evaluate_limits(cpu_average, None, None):
        if violation not in violations:
            violations.append(violation)
    if not reader_ms:
        raise ValueError('Keine Bilder gemessen')
    return {
        'repeats': len(reader_ms),
        'elapsed_s': elapsed,
        'target_fps': target_fps,
        'frames_per_second': len(reader_ms) / elapsed,
        'reader_median_ms': statistics.median(reader_ms),
        'reader_p90_ms': sorted(reader_ms)[max(0, round(0.9 * len(reader_ms)) - 1)],
        'median_ms': statistics.median(chain_ms),
        'p90_ms': sorted(chain_ms)[max(0, round(0.9 * len(chain_ms)) - 1)],
        'p95_ms': sorted(chain_ms)[max(0, round(0.95 * len(chain_ms)) - 1)],
        'max_ms': max(chain_ms),
        'cpu_percent': cpu_average,
        'cpu_percent_max': max(cpu_average, max(cpu_samples)),
        'temperature_c_max': max(temperatures, default=None),
        'throttled': hex(_or_bits(throttle_samples)) if throttle_samples else None,
        'sensor_samples': len(cpu_samples),
        'violations': violations,
        'last_value': None if result is None else result.value,
        'last_reject': None if result is None else result.diagnostics.get('reject_reason'),
    }


def _or_bits(values: list[int]) -> int:
    bits = 0
    for value in values:
        bits |= value
    return bits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--still', type=input_path, default='var/diagnostics/sc7-assist/still.png')
    parser.add_argument('--proposal', type=input_path, default='var/diagnostics/sc7-assist/proposal.json')
    parser.add_argument('--templates', type=input_path, default=DEFAULT_TEMPLATES)
    parser.add_argument('--templates-sha256', default=DEFAULT_TEMPLATES_SHA256)
    parser.add_argument('--repeats', type=int, default=200)
    parser.add_argument('--duration', type=float, help='Messdauer in Sekunden, statt --repeats')
    parser.add_argument('--target-fps', type=float, default=30.0)
    args = parser.parse_args(argv)
    if args.repeats < 1 or (args.duration is not None and args.duration <= 0) or args.target_fps < 0:
        parser.error('Wiederholungen/Dauer muessen positiv sein, Zielrate darf nicht negativ sein')
    image = cv2.imread(str(args.still))
    if image is None:
        print(f'Bild nicht lesbar: {args.still}', file=sys.stderr)
        return 2
    proposal = json.loads(args.proposal.read_text(encoding='utf-8'))
    layout = CharLayout(grid=CharGrid.from_dict(proposal['grid']), unit='mV/V')
    previous_threads = cv2.getNumThreads()
    cv2.setNumThreads(LIVE_CV_THREADS)
    try:
        reader = DotMatrixReader.from_file(args.templates, args.templates_sha256)
        stats = measure_run(reader, image, proposal['quad'], layout, repeats=args.repeats,
                            duration=args.duration, target_fps=args.target_fps)
    finally:
        cv2.setNumThreads(previous_threads)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    return 1 if stats['violations'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
