"""Faktorplan fuer Normierungsspruenge des GSV-2AS (`set norm`, Befehl 16).

Seit 2026-11-20 im Paket (vorher nur in `scripts/harvest.py`), damit Ernte
und `picam kalibrieren` denselben Plan erzeugen. Unveraendert uebernommen:
log-uniform verteilte Faktoren, 4 signifikante Stellen, im dokumentierten
Geraetebereich (`dispread.gsv2as_serial.NORM_MIN/NORM_MAX`, CLAUDE.md) und
je Schritt mindestens um den Faktor 1,3 vom vorigen entfernt.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from dispread.gsv2as_serial import NORM_MAX, NORM_MIN

#: Zwei aufeinanderfolgende Faktoren im Plan muessen mindestens diesen
#: Faktor auseinanderliegen, damit jeder Schritt ein grosser Wechsel ist
#: (docs/superpowers/plans/2026-09-23-ernte-phase1.md, Task 4).
MIN_STEP_RATIO = 1.3

#: Vorgabebereich der Faktoren, wie bei Ernte und Kalibrieraufnahme
#: `sc3-cal-b` (docs/VALIDATION.md 2026-09-29).
DEFAULT_FACTOR_LO = 0.5
DEFAULT_FACTOR_HI = 9000.0

#: Zieltakt der geschriebenen Bilder (`record --frame-rate`), wie bei der
#: Ernte (final-review.md I-1): fest, unabhaengig von der Kamera-fps.
RECORD_FRAME_RATE = 15.0

#: Zwischenablage im RAM (`record --staging-root`), gegen die am 2026-09-29
#: gemessenen Schreibhaenger der SD-Karte (siehe `dispread.calibration.record`).
RECORD_STAGING_ROOT = Path("/dev/shm")


class ScheduleError(RuntimeError):
    """Kein gueltiger Faktorplan moeglich."""


def round_sig(value: float, digits: int) -> float:
    """Rundet `value` auf `digits` signifikante Stellen."""
    if value == 0:
        return 0.0
    shift = digits - int(math.floor(math.log10(abs(value)))) - 1
    return round(value, shift)


def plan_factors(
    n_steps: int, seed: int, lo: float = DEFAULT_FACTOR_LO, hi: float = DEFAULT_FACTOR_HI
) -> list[float]:
    """Erzeugt `n_steps` log-uniform verteilte Normierungsfaktoren.

    Deterministisch je `seed`. Jeder Faktor ist auf 4 signifikante Stellen
    gerundet, liegt im Geraetebereich (0,15...1 580 000) und mindestens um
    den Faktor 1,3 vom vorherigen entfernt.
    """
    if n_steps < 1:
        raise ValueError(f"n_steps muss >= 1 sein, ist {n_steps}")
    if not (0 < lo < hi):
        raise ValueError(f"0 < lo < hi verletzt: lo={lo}, hi={hi}")

    rng = random.Random(seed)
    log_lo, log_hi = math.log(lo), math.log(hi)
    factors: list[float] = []
    max_attempts = 100_000
    attempts = 0
    while len(factors) < n_steps:
        attempts += 1
        if attempts > max_attempts:
            raise ScheduleError(
                f"plan_factors: nach {max_attempts} Versuchen keine {n_steps} "
                "gueltigen Faktoren gefunden (Bereich/Mindestabstand zu eng?)"
            )
        candidate = round_sig(math.exp(rng.uniform(log_lo, log_hi)), 4)
        if not (NORM_MIN <= candidate <= NORM_MAX):
            continue
        if factors:
            prev = factors[-1]
            ratio = max(candidate, prev) / min(candidate, prev)
            if ratio < MIN_STEP_RATIO:
                continue
        factors.append(candidate)
    return factors


def format_num(value: float) -> str:
    """Kompakte Zahlendarstellung ohne unnoetige Nachkommastellen/Exponenten,
    kompatibel mit `gsv2as_serial._parse_norm_schedule` (nutzt `float()`)."""
    return f"{value:.10g}"


def build_schedule(factors: list[float], hold_s: float) -> str:
    """Baut den `--norm-schedule`-String `'f1:hold,f2:hold,...'`."""
    hold_text = format_num(hold_s)
    return ",".join(f"{format_num(f)}:{hold_text}" for f in factors)
