#!/usr/bin/env python3
"""Performance-Bericht: Latenz je Stufe, Lesegeschwindigkeit, Qualitaet, Betriebswerte.

    ./.venv/bin/python scripts/perf-report.py                       # messen, JSON + Tabelle
    ./.venv/bin/python scripts/perf-report.py --compare perf/baseline.json
    ./.venv/bin/python scripts/perf-report.py --update-baseline

Aufbau (nichts neu erfunden):
  * Stufenzeiten kommen aus dem PipelineTrace jedes ValueRecord
    (dispread.pipeline, Marken t_dequeue ... t_record_built; docs/TIMING.md M4).
  * Durchsatz nutzt measure_run aus scripts/live-reader-benchmark.py
    (Sensorproben, Drosselbits, CPU) mit --target-fps 0 und 30.
  * Qualitaet: Anteil richtig freigegebener Werte auf denselben Bildern,
    getrennt von falsch freigegebenen und abgelehnten (wie dispread.benchmark).

Messquelle "synthetic" (Standard) braucht keine Hardware und keine Daten
ausserhalb des Repos: tests/dotmatrix_helpers (Renderer + Leser mit festem
Seed). Quelle "dev" misst Latenz/Durchsatz auf einem gespeicherten Bild
(--still/--proposal, DISPREAD_DEV_DATA beachtet) ohne Wahrheitswerte, also
ohne Qualitaetsmetrik. Jede Wiederholung laeuft in einem frischen Prozess
(Kaltstart, eigene RSS-Messung); der Bericht nimmt je Metrik den Median.

Exit-Codes: 0 gut, 1 Regression gegen die Baseline, 2 Aufruf-/Umgebungsfehler,
3 Lauf ungueltig (Drosselung, SoC >= 75 Grad, fremde CPU-Last): dann wird
bewusst keine Regression gemeldet.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
PERF_DIR = REPO / "perf"
SCHEMA = 1
STAGES = ("locate", "rectify", "read", "gate", "build")
PERCENTILES = (50, 95, 99)
EXIT_OK, EXIT_REGRESSION, EXIT_ERROR, EXIT_INVALID = 0, 1, 2, 3

#: Toleranzen (Begruendung: perf/README.md, Abschnitt Toleranz).
DEFAULT_TOLERANCE = {
    "latency_p95_pct": 15.0,  # p95 darf um bis zu 15 % steigen
    "latency_abs_floor_ms": 0.05,  # ... mindestens aber um 0,05 ms (Zeitgeber-Rauschen kleiner Stufen)
    "throughput_pct": 15.0,  # Bilder/s duerfen um bis zu 15 % sinken
    "recognition_points": 0.5,  # Erkennungsrate darf um 0,5 Prozentpunkte sinken
    "dropped_points": 1.0,  # verworfener Anteil bei 30 fps darf um 1 Punkt steigen
}
#: Ungueltig-Schwellen. Aktuelle Drosselbits (Bit 0-3) zaehlen, die
#: "seit Boot"-Bits (16-19) nur als Hinweis: sie bleiben bis zum Neustart gesetzt.
MAX_SOC_C = 75.0
THROTTLE_NOW_MASK = 0xF
MAX_FOREIGN_CPU_PERCENT = 40.0  # fremde Last in Prozent eines Kerns


# --------------------------------------------------------------------------
# Reine Logik (ohne Hardware testbar)
# --------------------------------------------------------------------------


def percentile(values: list[float], p: float) -> float:
    """Nearest-Rank-Perzentil: immer ein tatsaechlich gemessener Wert."""
    if not values:
        raise ValueError("Keine Werte")
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def distribution(values_ms: list[float]) -> dict[str, float]:
    out = {f"p{p}": percentile(values_ms, p) for p in PERCENTILES}
    out["max"] = max(values_ms)
    return out


def invalid_reasons(
    temperature_c_max: float | None,
    throttled: int | None,
    foreign_cpu_percent: float | None,
    *,
    max_foreign_cpu: float = MAX_FOREIGN_CPU_PERCENT,
) -> list[str]:
    """Gruende, aus denen ein Lauf nicht vergleichbar ist. Leer = gueltig."""
    reasons = []
    if throttled is not None and throttled & THROTTLE_NOW_MASK:
        reasons.append(f"Drosselung aktiv ({hex(throttled & THROTTLE_NOW_MASK)})")
    if temperature_c_max is not None and temperature_c_max >= MAX_SOC_C:
        reasons.append(f"SoC {temperature_c_max:.1f} Grad >= {MAX_SOC_C:.0f}")
    if foreign_cpu_percent is not None and foreign_cpu_percent > max_foreign_cpu:
        reasons.append(f"fremde CPU-Last {foreign_cpu_percent:.0f} % > {max_foreign_cpu:.0f} %")
    return reasons


def aggregate(runs: list[dict]) -> dict:
    """Median je Metrik ueber gueltige Wiederholungen, dazu Streuung (min/max)."""
    valid = [r for r in runs if not r["invalid"]]
    if not valid:
        return {}
    keys = sorted(valid[0]["metrics"])
    metrics, spread = {}, {}
    for key in keys:
        vals = [r["metrics"][key] for r in valid if r["metrics"].get(key) is not None]
        if vals:
            metrics[key] = statistics.median(vals)
            spread[key] = [min(vals), max(vals)]
    return {"metrics": metrics, "spread": spread}


# Metrikbeschreibung: (Schluessel, Richtung, Gruppe). "lower" = kleiner ist besser.
def gated_metrics(metrics: dict[str, float]) -> list[tuple[str, str]]:
    keys = [(f"latency.{s}.p95_ms", "lower") for s in (*STAGES, "total") if f"latency.{s}.p95_ms" in metrics]
    keys += [("throughput.max_fps", "higher"), ("throughput.fps30.achieved_fps", "higher")]
    keys += [("throughput.fps30.dropped_percent", "lower_points"), ("quality.recognition_percent", "higher_points")]
    return [(k, d) for k, d in keys if k in metrics]


def compare(baseline: dict, current: dict, tol: dict | None = None) -> list[dict]:
    """Zeilen 'Metrik | Baseline | Jetzt | Abweichung | Grenze' mit Urteil je Zeile."""
    tol = {**DEFAULT_TOLERANCE, **(tol or {})}
    rows = []
    for key, direction in gated_metrics(baseline):
        if key not in current:
            rows.append({"metric": key, "baseline": baseline[key], "current": None, "ok": False,
                         "deviation": "fehlt", "limit": "-"})
            continue
        base, now = baseline[key], current[key]
        if direction == "lower":
            limit = max(base * (1 + tol["latency_p95_pct"] / 100), base + tol["latency_abs_floor_ms"])
            ok = now <= limit
            dev = f"{_pct(now, base)}"
            limit_s = f"<= {limit:.3f} (+{tol['latency_p95_pct']:g} %, min. +{tol['latency_abs_floor_ms']:g} ms)"
        elif direction == "higher":
            limit = base * (1 - tol["throughput_pct"] / 100)
            ok = now >= limit
            dev = f"{_pct(now, base)}"
            limit_s = f">= {limit:.2f} (-{tol['throughput_pct']:g} %)"
        elif direction == "higher_points":
            limit = base - tol["recognition_points"]
            ok = now >= limit - 1e-9
            dev = f"{now - base:+.2f} Pkt"
            limit_s = f">= {limit:.2f} (-{tol['recognition_points']:g} Pkt)"
        else:  # lower_points
            limit = base + tol["dropped_points"]
            ok = now <= limit + 1e-9
            dev = f"{now - base:+.2f} Pkt"
            limit_s = f"<= {limit:.2f} (+{tol['dropped_points']:g} Pkt)"
        rows.append({"metric": key, "baseline": base, "current": now, "ok": ok, "deviation": dev, "limit": limit_s})
    return rows


def _pct(now: float, base: float) -> str:
    return f"{(now / base - 1) * 100:+.1f} %" if base else "n/a"


def probable_cause(rows: list[dict]) -> list[str]:
    """Lesbarer Ursachenhinweis aus den verletzten Zeilen."""
    bad = [r["metric"] for r in rows if not r["ok"]]
    hints = []
    stages = [m.split(".")[1] for m in bad if m.startswith("latency.") and ".total." not in m]
    if stages:
        worst = max(
            (r for r in rows if not r["ok"] and r["metric"].startswith("latency.") and ".total." not in r["metric"]),
            key=lambda r: (r["current"] or 0) - r["baseline"],
        )
        hints.append(f"Latenz: groesster Zuwachs in Stufe '{worst['metric'].split('.')[1]}' "
                     f"(verletzt: {', '.join(sorted(set(stages)))}) - dort zuerst suchen.")
    elif "latency.total.p95_ms" in bad:
        hints.append("Gesamtlatenz gestiegen, aber keine Einzelstufe ueber Grenze: Streuung oder Summe kleiner Zuwaechse.")
    if any(m.startswith("throughput.") for m in bad):
        hints.append("Durchsatz/Verwerfung: meist Lesekette (rectify/read) oder CV-Threads/Last; Stufenlatenz gegenpruefen.")
    if "quality.recognition_percent" in bad:
        hints.append("Erkennungsrate gesunken: Leser/Vorlagen/Entzerrung geaendert - Qualitaet vor Geschwindigkeit pruefen.")
    return hints


def host_mismatch(baseline_host: dict, host: dict) -> list[str]:
    return [f"{k}: Baseline {baseline_host.get(k)!r} != jetzt {host.get(k)!r}"
            for k in ("model", "cores", "source") if baseline_host.get(k) != host.get(k)]


def format_compare(rows: list[dict]) -> str:
    lines = ["| Metrik | Baseline | Jetzt | Abweichung | Grenze | Urteil |", "|---|---:|---:|---:|---|---|"]
    for r in rows:
        cur = "-" if r["current"] is None else f"{r['current']:.3f}"
        lines.append(f"| {r['metric']} | {r['baseline']:.3f} | {cur} | {r['deviation']} | {r['limit']} | "
                     f"{'ok' if r['ok'] else 'REGRESSION'} |")
    return "\n".join(lines)


def format_report(report: dict) -> str:
    m = report["metrics"]
    out = [f"## Performance-Bericht {report['commit']}", "",
           f"Quelle: {report['host']['source']} - {report['host']['model']} ({report['host']['cores']} Kerne) - "
           f"{report['repetitions_valid']}/{report['repetitions']} gueltige Wiederholungen, Median", "",
           "### Latenz je Stufe (ms)", "", "| Stufe | p50 | p95 | p99 | max |", "|---|---:|---:|---:|---:|"]
    for s in (*STAGES, "total"):
        if f"latency.{s}.p50_ms" in m:
            out.append(f"| {s} | " + " | ".join(f"{m[f'latency.{s}.{q}_ms']:.3f}" for q in ("p50", "p95", "p99", "max")) + " |")
    out += ["", "### Lesegeschwindigkeit, Qualitaet, Betrieb", "", "| Metrik | Wert |", "|---|---:|"]
    for key in sorted(k for k in m if not k.startswith("latency.")):
        out.append(f"| {key} | {m[key]:.3f} |")
    for name, text in report.get("operating", {}).items():
        out.append(f"| {name} | {text} |")
    if report.get("open_items"):
        out += ["", "### Nicht gemessen (offen)", ""] + [f"- {x}" for x in report["open_items"]]
    return "\n".join(out)


OPEN_ITEMS = [
    "Echte Kamera-Latenz und Aufnahme-bis-Wert (M2/M5, docs/TIMING.md): braucht Kamera/Kalibriermaschine.",
    "Startzeit inkl. Vorlagen laden, Kamera oeffnen und Setup: nur Pipeline-Kaltstart bis erster VALID gemessen.",
    "Erkennungsrate auf realen Geraeten/Lichtbedingungen: nur synthetische Bilder (reale Daten liegen nicht im Repo).",
    "Speicherwachstum ueber Stunden: nur wenige Minuten Lauf, Leck unterhalb dieser Dauer nicht auszuschliessen.",
]


# --------------------------------------------------------------------------
# Messung (Worker, ein frischer Prozess je Wiederholung)
# --------------------------------------------------------------------------


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _rss_mb() -> float:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return float("nan")


def _system_busy_seconds() -> float | None:
    try:
        fields = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
    except (OSError, ValueError):
        return None
    user, nice, system, _idle, _iowait, irq, softirq, steal = fields[:8]
    return (user + nice + system + irq + softirq + steal) / os.sysconf("SC_CLK_TCK")


def _freq_ratio() -> float | None:
    """Aktueller CPU-Takt / Maximaltakt; Ersatz-Hinweis auf Drosselung, wenn vcgencmd fehlt."""
    base = Path("/sys/devices/system/cpu/cpu0/cpufreq")
    try:
        return int((base / "scaling_cur_freq").read_text()) / int((base / "cpuinfo_max_freq").read_text())
    except (OSError, ValueError, ZeroDivisionError):
        return None


def _cpu_own_seconds() -> float:
    t = os.times()
    return t.user + t.system + t.children_user + t.children_system


def _build_source(args):
    """Liefert (reader, layout, quad, image, frames, expected) fuer die gewaehlte Quelle."""
    sys.path.insert(0, str(SCRIPTS))
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "tests"))
    import cv2
    import numpy as np

    if args.source == "dev":
        from _devdata import input_path

        from dispread.charcells import CharGrid
        from dispread.layout import CharLayout
        from dispread.live import DEFAULT_TEMPLATES, DEFAULT_TEMPLATES_SHA256
        from dispread.ocr.dotmatrix import DotMatrixReader

        image = cv2.imread(str(input_path(args.still)))
        if image is None:
            raise SystemExit(f"Bild nicht lesbar: {args.still}")
        proposal = json.loads(input_path(args.proposal).read_text(encoding="utf-8"))
        layout = CharLayout(grid=CharGrid.from_dict(proposal["grid"]), unit="mV/V")
        reader = DotMatrixReader.from_file(input_path(DEFAULT_TEMPLATES), DEFAULT_TEMPLATES_SHA256)
        return reader, layout, proposal["quad"], image, [image], None

    from dotmatrix_helpers import LAYOUT, QUAD, embed, render, synthetic_reader

    texts = ["+ 1.2345 ", "+0.60972 ", "+ 67.890 ", "+  988.5 ", "+ 3456.7 ", "+0.11111 "]
    rng = np.random.default_rng(11)
    frames, expected = [], []
    for i in range(24):
        text = texts[i % len(texts)]
        img = render(text, blur=0.3 + 0.7 * ((i * 7) % 10) / 10)
        img = np.clip(img + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
        frames.append(embed(img))
        expected.append(float(text.replace(' ', '')))
    return synthetic_reader(), LAYOUT, QUAD, frames[0], frames, expected


def _worker(args) -> dict:
    sys.path.insert(0, str(SCRIPTS))
    bench = _load("live_reader_benchmark", SCRIPTS / "live-reader-benchmark.py")
    import cv2

    from dispread.detect.manual_roi import ManualRoiLocator
    from dispread.frames.types import Frame
    from dispread.live import LIVE_CV_THREADS
    from dispread.pipeline import Pipeline, PipelineConfig
    from dispread.records import TimeBaseKind, Timestamp, TimestampSemantics, ValueStatus
    from dispread.validate import GateConfig, ReleaseGate

    cv2.setNumThreads(LIVE_CV_THREADS)
    reader, layout, quad, image, frames, expected = _build_source(args)

    def make_frame(i: int) -> Frame:
        stamp = Timestamp(time.monotonic_ns(), TimeBaseKind.HOST_MONOTONIC, TimestampSemantics.HOST_DEQUEUE)
        return Frame(frame_sequence=i, image=frames[i % len(frames)], capture_timestamp=stamp, source_id="perf")

    def make_pipeline() -> Pipeline:
        return Pipeline(source=types.SimpleNamespace(source_id="perf"), locator=ManualRoiLocator(quad), reader=reader,
                        gate=ReleaseGate(GateConfig(expected_unit=None)), sinks=[],
                        config=PipelineConfig(profile_id="perf", layout=layout))

    busy0, own0, wall0 = _system_busy_seconds(), _cpu_own_seconds(), time.perf_counter()
    temps = [t for t in [bench.read_temperature()] if t is not None]
    throttle = bench.read_throttled()
    rss_start = _rss_mb()

    # Kaltstart: Pipeline bauen bis erster freigegebener Wert (Leser schon geladen).
    t0 = time.perf_counter()
    pipe = make_pipeline()
    first_valid_ms, i = None, 0
    while first_valid_ms is None and i < 50:
        rec = pipe.process(make_frame(i))
        i += 1
        if rec.status is ValueStatus.VALID:
            first_valid_ms = (time.perf_counter() - t0) * 1000

    # Latenz je Stufe + Qualitaet ueber dieselben Frames.
    pipe = make_pipeline()
    for j in range(30):  # Aufwaermen, nicht gewertet
        pipe.process(make_frame(j))
    per_stage: dict[str, list[float]] = {s: [] for s in STAGES}
    total, tally = [], {"correct": 0, "wrong": 0, "rejected": 0}
    for j in range(args.frames):
        rec = pipe.process(make_frame(j))
        d = rec.trace.stage_durations_us()
        for s in STAGES:
            if s in d:
                per_stage[s].append(d[s] / 1000)
        total.append((rec.trace.t_record_built_ns - rec.trace.t_dequeue_ns) / 1e6)
        if rec.status is not ValueStatus.VALID:
            tally["rejected"] += 1
        elif expected is None:
            pass
        elif abs(rec.value - expected[j % len(frames)]) < 1e-9:
            tally["correct"] += 1
        else:
            tally["wrong"] += 1
    temps.append(bench.read_temperature())
    freqs = [_freq_ratio()]
    metrics: dict[str, float] = {}
    for s, vals in (*per_stage.items(), ("total", total)):
        if vals:
            for q, v in distribution(vals).items():
                metrics[f"latency.{s}.{q}_ms"] = v
    if expected is not None:
        metrics["quality.recognition_percent"] = 100 * tally["correct"] / args.frames
        metrics["quality.wrong_percent"] = 100 * tally["wrong"] / args.frames
        metrics["quality.rejected_percent"] = 100 * tally["rejected"] / args.frames

    # Lesegeschwindigkeit: maximal und bei 30 Bildern/s.
    runs = {}
    for name, fps in (("max", 0.0), ("fps30", 30.0)):
        runs[name] = bench.measure_run(reader, image, quad, layout, repeats=1, duration=args.duration, target_fps=fps)
        if fps == 0:  # nur unter Volllast aussagekraeftig (DVFS-Stufen im Leerlauf)
            freqs.append(_freq_ratio())
    metrics["throughput.max_fps"] = runs["max"]["frames_per_second"]
    f30 = runs["fps30"]
    offered = max(1.0, f30["elapsed_s"] * 30.0)
    metrics["throughput.fps30.achieved_fps"] = f30["frames_per_second"]
    metrics["throughput.fps30.dropped_percent"] = max(0.0, 100 * (offered - f30["repeats"]) / offered)

    # Betriebswerte und Gueltigkeit.
    wall = time.perf_counter() - wall0
    own = (_cpu_own_seconds() - own0) / wall * 100
    busy1 = _system_busy_seconds()
    system = None if busy1 is None or busy0 is None else (busy1 - busy0) / wall * 100
    foreign = None if system is None else max(0.0, system - own)
    all_temps = temps + [r["temperature_c_max"] for r in runs.values() if r["temperature_c_max"] is not None]
    t_max = max((t for t in all_temps if t is not None), default=None)
    bits = [bench._or_bits([int(r["throttled"], 16)]) for r in runs.values() if r["throttled"] is not None]
    if throttle is not None:
        bits.append(throttle)
    throttled = bench._or_bits(bits) if bits else None
    metrics["ops.cpu_percent_own"] = own
    metrics["ops.cpu_percent_foreign"] = foreign if foreign is not None else None
    metrics["ops.rss_growth_mb"] = _rss_mb() - rss_start
    metrics["ops.rss_start_mb"] = rss_start
    metrics["ops.rss_end_mb"] = _rss_mb()
    if first_valid_ms is not None:
        metrics["startup.first_valid_ms"] = first_valid_ms
    if t_max is not None:
        metrics["ops.soc_c_max"] = t_max
    freq_min = min((f for f in freqs if f is not None), default=None)
    if freq_min is not None:
        metrics["ops.cpu_freq_ratio_min"] = freq_min
    reasons = invalid_reasons(t_max, throttled, foreign, max_foreign_cpu=args.max_foreign_cpu)
    return {
        "metrics": {k: v for k, v in metrics.items() if v is not None},
        "invalid": reasons,
        "throttled": None if throttled is None else hex(throttled),
        "sensors": {"soc": t_max is not None, "vcgencmd": throttled is not None},
    }


# --------------------------------------------------------------------------
# Treiber
# --------------------------------------------------------------------------


def host_info(source: str) -> dict:
    try:
        model = Path("/proc/device-tree/model").read_bytes().rstrip(b"\0").decode()
    except OSError:
        model = platform.machine() or "unbekannt"
    try:
        import cv2

        cv = cv2.__version__
    except ImportError:
        cv = None
    return {"model": model, "cores": os.cpu_count(), "python": platform.python_version(),
            "opencv": cv, "source": source, "hostname_hash": None}


def git_commit() -> str:
    def run(*a):
        return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True, timeout=10)

    try:
        head = run("rev-parse", "--short", "HEAD")
        if head.returncode != 0:
            return "nogit"
        dirty = run("status", "--porcelain", "--untracked-files=no").stdout.strip()
        return head.stdout.strip() + ("-dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return "nogit"


def measure(args) -> dict:
    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", "--source", args.source,
           "--frames", str(args.frames), "--duration", str(args.duration),
           "--max-foreign-cpu", str(args.max_foreign_cpu), "--still", str(args.still), "--proposal", str(args.proposal)]
    runs = []
    for n in range(args.repetitions):
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(f"Wiederholung {n + 1} fehlgeschlagen:\n{proc.stderr[-2000:]}")
        runs.append(json.loads(proc.stdout.strip().splitlines()[-1]))
        print(f"Wiederholung {n + 1}/{args.repetitions}: "
              f"{'ungueltig: ' + '; '.join(runs[-1]['invalid']) if runs[-1]['invalid'] else 'gueltig'}", file=sys.stderr)
    agg = aggregate(runs)
    sensors = runs[0]["sensors"]
    operating = {
        "ops.soc_sensor": "verfuegbar" if sensors["soc"] else "nicht verfuegbar",
        "ops.throttle_bits": (", ".join(sorted({r["throttled"] for r in runs if r["throttled"]})) or "-")
        if sensors["vcgencmd"] else "nicht verfuegbar (vcgencmd fehlt oder nicht ausfuehrbar; CPU-Takt nur als Information, ohne Ungueltig-Wirkung)",
    }
    return {
        "schema": SCHEMA, "commit": git_commit(),
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": host_info(args.source),
        "repetitions": args.repetitions,
        "repetitions_valid": sum(1 for r in runs if not r["invalid"]),
        "invalid_reasons": sorted({x for r in runs for x in r["invalid"]}),
        "metrics": agg.get("metrics", {}), "spread": agg.get("spread", {}),
        "operating": operating, "open_items": OPEN_ITEMS,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=("synthetic", "dev"), default="synthetic")
    ap.add_argument("--still", default="var/diagnostics/sc7-assist/still.png")
    ap.add_argument("--proposal", default="var/diagnostics/sc7-assist/proposal.json")
    ap.add_argument("--repetitions", type=int, default=3)
    ap.add_argument("--frames", type=int, default=400, help="Bilder fuer die Stufenlatenz je Wiederholung")
    ap.add_argument("--duration", type=float, default=5.0, help="Sekunden je Durchsatzmessung")
    ap.add_argument("--max-foreign-cpu", type=float, default=MAX_FOREIGN_CPU_PERCENT)
    ap.add_argument("--compare", type=Path, help="Baseline-JSON; Exit 1 bei Regression")
    ap.add_argument("--update-baseline", action="store_true", help="schreibt perf/baseline.json")
    ap.add_argument("--output-dir", type=Path, default=PERF_DIR / "results")
    ap.add_argument("--summary-file", type=Path, help="Markdown anhaengen (CI-Step-Summary)")
    ap.add_argument("--tol-latency-pct", type=float, default=DEFAULT_TOLERANCE["latency_p95_pct"])
    ap.add_argument("--tol-throughput-pct", type=float, default=DEFAULT_TOLERANCE["throughput_pct"])
    ap.add_argument("--tol-recognition-points", type=float, default=DEFAULT_TOLERANCE["recognition_points"])
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.worker:
        print(json.dumps(_worker(args)))
        return 0
    if args.repetitions < 1 or args.frames < 10 or args.duration <= 0:
        ap.error("Wiederholungen >= 1, Bilder >= 10, Dauer > 0")

    try:
        report = measure(args)
    except (RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"Messung fehlgeschlagen: {exc}", file=sys.stderr)
        return EXIT_ERROR
    markdown = format_report(report) if report["metrics"] else "## Performance-Bericht\n\nAlle Wiederholungen ungueltig."
    invalid = report["repetitions_valid"] == 0
    if report["invalid_reasons"]:
        markdown += "\n\nUngueltige Wiederholungen: " + "; ".join(report["invalid_reasons"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / f"{report['commit']}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    code = EXIT_OK
    if invalid:
        markdown += "\n\n**Lauf ungueltig** - keine Regressionsaussage (Exit 3)."
        code = EXIT_INVALID
    elif args.update_baseline:
        if report["repetitions_valid"] < report["repetitions"]:
            print("Baseline nicht geschrieben: nicht alle Wiederholungen gueltig.", file=sys.stderr)
            return EXIT_INVALID
        base = {**report, "created_for": "baseline"}
        base.pop("commit_dirty", None)
        (PERF_DIR / "baseline.json").write_text(json.dumps(base, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        markdown += f"\n\nBaseline geschrieben: {PERF_DIR / 'baseline.json'}"
    if args.compare and not invalid:
        baseline = json.loads(args.compare.read_text(encoding="utf-8"))
        mismatch = host_mismatch(baseline["host"], report["host"])
        if mismatch:
            print("Baseline nicht vergleichbar (anderer Runner/Quelle):\n  " + "\n  ".join(mismatch), file=sys.stderr)
            return EXIT_ERROR
        tol = {"latency_p95_pct": args.tol_latency_pct, "throughput_pct": args.tol_throughput_pct,
               "recognition_points": args.tol_recognition_points}
        rows = compare(baseline["metrics"], report["metrics"], tol)
        markdown += "\n\n### Vergleich mit " + str(args.compare) + "\n\n" + format_compare(rows)
        if any(not r["ok"] for r in rows):
            hints = probable_cause(rows)
            markdown += "\n\n**Regression.** Wahrscheinliche Ursache:\n" + "\n".join(f"- {h}" for h in hints)
            code = EXIT_REGRESSION
    print(markdown)
    if args.summary_file:
        with args.summary_file.open("a", encoding="utf-8") as fh:
            fh.write(markdown + "\n")
    print(f"JSON: {out_path}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
