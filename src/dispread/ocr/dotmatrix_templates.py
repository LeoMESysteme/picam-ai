"""Vorlagen, Zellentscheidung und Schwellen des Dot-Matrix-Lesers.

Spec Abschnitt 2 (Schritte 5-6) und Abschnitt 3 (Formel `thresholds_v1`).
Die Vorlagen entstehen offline und werden eingefroren; im Betrieb wird nichts
nachgelernt. `margin` ist ein Beleg, keine Fehlerwahrscheinlichkeit
(Konzept.md §7).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from dispread.ocr.dotmatrix_font import CLASSES, COLS, N_DOTS, ROWS, rom_vector

FORMAT_VERSION = 2
THRESHOLD_FORMULA = "thresholds_v1"
SIGMA_FLOOR = 0.05
ROM_CHECK = "rom_check_v2"
#: Toleranz der ROM-Gegenprobe in Punkten je Zeichen (Nutzerentscheidung
#: OQ-42, Spec-Aenderung 2026-09-25). Der kleinste Abstand zweier Zeichen
#: des Satzes betraegt 4 Punkte - eine einzelne Abweichung ist bei weicher
#: Schaerfe beobachtet (Aufstellung `auf2`, VALIDATION.md 2026-09-24) und
#: kein Hinweis auf ein falsches Label, zwei oder mehr Abweichungen schon.
ROM_TOLERANCE_DOTS = 1


@dataclass(frozen=True)
class Templates:
    mean: dict[str, np.ndarray]
    std: dict[str, np.ndarray]
    d_max: float
    margin_min: float
    groups: tuple[str, ...]
    counts: dict[str, int]


@dataclass(frozen=True)
class CellDecision:
    text: str | None
    best: str
    second: str
    d_best: float
    d_second: float
    shift_index: int
    reason: str | None
    margin: float


def distance(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> float:
    return float(np.sqrt(np.mean(((x - mean) / np.maximum(std, SIGMA_FLOOR)) ** 2)))


def _best_per_class(vectors: np.ndarray, mean, std) -> dict[str, tuple[float, int]]:
    out = {}
    for ch in mean:
        ds = [distance(v, mean[ch], std[ch]) for v in vectors]
        j = int(np.argmin(ds))
        out[ch] = (ds[j], j)
    return out


def _decide(vectors, mean, std, d_max, margin_min) -> CellDecision:
    per = _best_per_class(vectors, mean, std)
    order = sorted(per, key=lambda c: per[c][0])
    best, second = order[0], order[1]
    d_best, j = per[best]
    d_second = per[second][0]
    gap = d_second - d_best
    margin = min(d_max - d_best, gap - margin_min)
    reason = None
    if d_best > d_max:
        reason = "zelle_unbekannt"
    elif gap < margin_min:
        reason = "zelle_mehrdeutig"
    return CellDecision(None if reason else best, best, second, d_best, d_second, j, reason, float(margin))


def classify(vectors: np.ndarray, t: Templates) -> CellDecision:
    return _decide(vectors, t.mean, t.std, t.d_max, t.margin_min)


def _require_classes(keys) -> None:
    missing = [c for c in CLASSES if c not in keys]
    if missing:
        raise ValueError(f"Klasse(n) ohne Daten: {missing!r}")


def fit_templates(samples: dict[str, list[np.ndarray]], groups: tuple[str, ...]):
    _require_classes([c for c in samples if samples[c]])
    mean, std = {}, {}
    for ch in CLASSES:
        rom = rom_vector(ch)
        chosen = [v[int(np.argmin(np.linalg.norm(v - rom, axis=1)))] for v in samples[ch]]
        arr = np.stack(chosen)
        mean[ch] = arr.mean(axis=0).astype(np.float32)
        std[ch] = arr.std(axis=0).astype(np.float32)
    return mean, std


def rom_deviations(mean: dict[str, np.ndarray]) -> dict[str, int]:
    """Zahl der Punkte je Zeichen, in denen die bei 0,5 binarisierte Vorlage
    vom ROM-Muster abweicht - Grundlage von `rom_check` und fuer Berichte
    (`scripts/dotmatrix-train.py`, `scripts/dotmatrix-eval.py`)."""
    return {ch: int(np.sum((mean[ch] >= 0.5) != (rom_vector(ch) >= 0.5))) for ch in CLASSES}


def rom_check(mean: dict[str, np.ndarray]) -> list[str]:
    """Zeichen, deren binarisierte Vorlage in mehr als `ROM_TOLERANCE_DOTS`
    Punkten vom ROM-Muster abweicht (`rom_check_v2`, OQ-42)."""
    deviations = rom_deviations(mean)
    return [ch for ch in CLASSES if deviations[ch] > ROM_TOLERANCE_DOTS]


def binarized_pattern(vec: np.ndarray) -> list[str]:
    """`vec` (40 Punktwerte) bei 0,5 binarisiert, zeilenweise als Bitmuster -
    fuer den Bericht bei einer gescheiterten ROM-Gegenprobe (Task 7,
    Trainings-/Entwicklungsmessung): zeigt gelerntes und ROM-Muster
    nebeneinander, ohne dass Training oder Schwellen daraufhin angepasst
    werden (das waere Nachbesserung an geheimen Daten, nicht erlaubt)."""
    bits = (vec >= 0.5).astype(int)
    return ["".join(str(b) for b in bits[r * COLS : (r + 1) * COLS]) for r in range(ROWS)]


def compute_thresholds(samples, mean, std) -> tuple[float, float]:
    correct_d, correct_gap, wrong_gap = [], [], []
    for ch in CLASSES:
        for v in samples[ch]:
            per = _best_per_class(v, mean, std)
            order = sorted(per, key=lambda c: per[c][0])
            gap = per[order[1]][0] - per[order[0]][0]
            if order[0] == ch:
                correct_d.append(per[ch][0])
                correct_gap.append(gap)
            else:
                wrong_gap.append(gap)
    d_max = 1.25 * float(np.percentile(correct_d, 99.5))
    margin_min = max(0.2 * float(np.median(correct_gap)), 1.25 * max(wrong_gap, default=0.0))
    return d_max, margin_min


def build_templates(samples, groups: tuple[str, ...]) -> Templates:
    mean, std = fit_templates(samples, groups)
    bad = rom_check(mean)
    if bad:
        raise ValueError(f"ROM-Gegenprobe gescheitert fuer {bad!r} - Labels oder Raster pruefen")
    d_max, margin_min = compute_thresholds(samples, mean, std)
    return Templates(mean, std, d_max, margin_min, tuple(groups), {c: len(samples[c]) for c in CLASSES})


def save_templates(t: Templates, path: Path) -> str:
    data = {
        "format_version": FORMAT_VERSION,
        "threshold_formula": THRESHOLD_FORMULA,
        "rom_check": ROM_CHECK,
        "rom_deviations": rom_deviations(t.mean),
        "d_max": t.d_max,
        "margin_min": t.margin_min,
        "groups": list(t.groups),
        "counts": t.counts,
        "mean": {c: [float(x) for x in t.mean[c]] for c in CLASSES},
        "std": {c: [float(x) for x in t.std[c]] for c in CLASSES},
    }
    blob = json.dumps(data, indent=1, sort_keys=True).encode("utf-8")
    Path(path).write_bytes(blob)
    return hashlib.sha256(blob).hexdigest()


def load_templates(path: Path, expected_sha256: str | None = None) -> Templates:
    """Laedt eine Vorlagendatei. Wirft `ValueError` statt eines fail-open
    Verhaltens bei jeder Beschaedigung, die die Klassifikation lautlos
    verfaelschen wuerde: fehlende Pflichtfelder, nicht-endliche oder
    unplausible Schwellen (`d_max`/`margin_min` muessen > 0 sein), nicht-
    endliche `mean`-Werte und nicht-endliche oder negative `std`-Werte (eine
    negative Streuung ist kein gueltiges Modell, `distance()` erwartet
    `std >= 0`). Konzept.md §7: Unlesbares/Unplausibles wird abgelehnt, nie
    stillschweigend weiterverwendet."""
    blob = Path(path).read_bytes()
    if expected_sha256 is not None and hashlib.sha256(blob).hexdigest() != expected_sha256:
        raise ValueError(f"Pruefsumme von {path} weicht ab")
    data = json.loads(blob)
    if data.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"format_version {data.get('format_version')!r} statt {FORMAT_VERSION}")
    if data.get("threshold_formula") != THRESHOLD_FORMULA:
        raise ValueError(f"threshold_formula {data.get('threshold_formula')!r} statt {THRESHOLD_FORMULA}")
    if data.get("rom_check") != ROM_CHECK:
        raise ValueError(f"rom_check {data.get('rom_check')!r} statt {ROM_CHECK}")

    for key in ("d_max", "margin_min", "groups", "counts"):
        if key not in data:
            raise ValueError(f"Feld {key!r} fehlt in {path}")

    d_max = data["d_max"]
    margin_min = data["margin_min"]
    if not isinstance(d_max, (int, float)) or not math.isfinite(d_max) or d_max <= 0:
        raise ValueError(f"d_max {d_max!r} ist nicht endlich oder <= 0")
    if not isinstance(margin_min, (int, float)) or not math.isfinite(margin_min) or margin_min <= 0:
        raise ValueError(f"margin_min {margin_min!r} ist nicht endlich oder <= 0")

    for key in ("mean", "std"):
        if key not in data:
            raise ValueError(f"Feld {key!r} fehlt in {path}")
        _require_classes(data[key])
        for c in CLASSES:
            values = data[key][c]
            if len(values) != N_DOTS:
                raise ValueError(f"{key}[{c!r}] hat nicht {N_DOTS} Werte")
            for x in values:
                if not isinstance(x, (int, float)) or not math.isfinite(x):
                    raise ValueError(f"{key}[{c!r}] enthaelt einen nicht endlichen Wert")
                if key == "std" and x < 0:
                    raise ValueError(f"std[{c!r}] enthaelt einen negativen Wert")

    return Templates(
        mean={c: np.asarray(data["mean"][c], np.float32) for c in CLASSES},
        std={c: np.asarray(data["std"][c], np.float32) for c in CLASSES},
        d_max=float(d_max),
        margin_min=float(margin_min),
        groups=tuple(data["groups"]),
        counts=dict(data["counts"]),
    )
