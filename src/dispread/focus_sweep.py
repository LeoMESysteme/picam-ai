"""Software-Fokussuche fuer die Logitech StreamCam (USB/UVC, 046d:0893).

Die StreamCam hat keine Autofokus-Logik, die fuer den Messpfad reproduzierbar
waere - `focus_absolute` (0..255) wird deshalb einmal je Sitzung von
`scripts/harvest-setup.py focus` per Bergsteigen bestimmt; bei flachem Start
bleibt der Vollsweep als Rueckfall. `measure()` selbst (eine
Kamera anfahren, warten, ein Bild lesen, `sharpness()` darauf anwenden) bleibt
Sache des Aufrufers - dieses Modul kennt weder Kamera noch Datei-I/O, das ist
die Voraussetzung dafuer, dass `sweep_focus` ohne Hardware testbar ist.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import cv2
import numpy as np

DEFAULT_FOCUS_START = 48
FOCUS_FINE_RADIUS = 6


class FocusMeasurements(list[tuple[int, float]]):
    """Messungen in Reihenfolge, mit der tatsaechlich verwendeten Suchmethode."""

    def __init__(self, focus_method: str = "climb") -> None:
        super().__init__()
        self.focus_method = focus_method
        self.focus_verify: dict[str, int | float | str] | None = None


def climb_focus(
    measure: Callable[[int], float],
    start: int = DEFAULT_FOCUS_START,
    step: int = 8,
    fine_step: int = 2,
    lo: int = 0,
    hi: int = 255,
    flat_tolerance: float = 0.05,
    peak_ratio: float = 2.0,
    on_fallback: Callable[[], None] | None = None,
) -> tuple[int, FocusMeasurements]:
    """Bergsteigen: ab `start` in Schritten `step` in die Richtung, in der die
    Schaerfe steigt; faellt sie nach einem Anstieg, ist der Gipfel ueberschritten.
    Danach das ganze Fenster +/-6 um den Grob-Gipfel aufsteigend mit
    `fine_step` (Vorgabe 2) messen, ohne Abbruch bei einem Abfall; das
    Fein-Maximum gewinnt. Die Kamera-Anfahrt von unten sichert der Aufrufer.
    Ein Fokuswert wird nie zweimal gemessen. Kein Anstieg in beiden Richtungen (flach, Unterschied
    < `flat_tolerance` relativ) -> Rueckfall auf `sweep_focus` mit denselben
    Messungen als Startbestand (keine Wiederholung schon gemessener Werte).
    Nach Grob- und Feinlauf muss der Gipfel mindestens `peak_ratio` mal so
    hoch wie die kleinste gemessene Schaerfe sein, sonst ebenfalls Rueckfall.
    Rueckgabe wie `sweep_focus`: (bester Fokus, Messungen in Reihenfolge).
    """
    measured = FocusMeasurements()
    seen: dict[int, float] = {}

    def sample(focus: int) -> float:
        if focus not in seen:
            seen[focus] = measure(focus)
            measured.append((focus, seen[focus]))
        return seen[focus]

    def fallback() -> tuple[int, FocusMeasurements]:
        if on_fallback is not None:
            on_fallback()
        measured.focus_method = "sweep"
        sweep_focus(sample, coarse=(*seen, *range(lo, hi + 1, step)), fine_radius=FOCUS_FINE_RADIUS,
                    fine_step=fine_step, lo=lo, hi=hi)
        return max(measured, key=lambda pair: pair[1])[0], measured

    start = max(lo, min(hi, start))
    initial = sample(start)
    threshold = abs(initial) * flat_tolerance
    right, left = min(hi, start + step), max(lo, start - step)
    right_score = sample(right)
    direction = 0
    best, best_score = start, initial
    if right_score > initial + threshold:
        direction, best, best_score = 1, right, right_score
    else:
        left_score = sample(left)
        if left_score > initial + threshold:
            direction, best, best_score = -1, left, left_score
        elif abs(right_score - initial) <= threshold and abs(left_score - initial) <= threshold:
            return fallback()

    position = best
    while direction:
        following = max(lo, min(hi, position + direction * step))
        if following == position:
            break
        score = sample(following)
        if score < best_score - abs(best_score) * flat_tolerance:
            break
        if score > best_score:
            best, best_score = following, score
        position = following

    # Die Richtungsschwelle darf ein knapp besseres Grob-Ergebnis nicht als
    # Mittelpunkt der Feinsuche ausschliessen.
    best, best_score = max(measured, key=lambda pair: pair[1])
    fine_values = sorted({best, *range(max(lo, best - FOCUS_FINE_RADIUS),
                                     min(hi, best + FOCUS_FINE_RADIUS) + 1, fine_step)})
    for focus in fine_values:
        score = sample(focus)
        if score > best_score:
            best, best_score = focus, score
    if best_score < peak_ratio * min(seen.values()):
        return fallback()
    return best, measured


def sharpness(gray_roi: np.ndarray) -> float:
    """Varianz des Laplace-Bildes (`cv2.Laplacian`, `CV_64F`) - je hoeher,
    desto schaerfer. `gray_roi` ist ein Graustufen-Ausschnitt (ein Kanal)."""
    return float(cv2.Laplacian(gray_roi, cv2.CV_64F).var())


def sweep_focus(
    measure: Callable[[int], float],
    coarse: Sequence[int] = range(0, 256, 8),
    fine_radius: int = 8,
    fine_step: int = 2,
    lo: int = 0,
    hi: int = 255,
) -> tuple[int, list[tuple[int, float]]]:
    """Sucht den Fokuswert mit dem hoechsten `measure(focus)`-Ergebnis.

    `measure(focus)` setzt den Fokus am Geraet und liefert die gemessene
    Schaerfe - das ist Sache des Aufrufers (Kamera, Wartezeit, Bildlesen),
    dieses Modul kennt keine Hardware.

    Ablauf: erst grob ueber `coarse`, dann fein im Fenster
    `[best - fine_radius, best + fine_radius]` (auf `[lo, hi]` begrenzt) mit
    Schrittweite `fine_step`, wobei `best` das bislang beste Ergebnis ist.
    Ein Fokuswert wird nie zweimal gemessen (jede reale Messung ist eine
    Kamera-Ansteuerung mit Wartezeit) - liegt ein Fein-Sweep-Wert schon in
    `coarse`, wird er uebersprungen, nicht erneut gemessen.

    Bei Gleichstand gewinnt der zuerst gemessene Wert (strikt "> best",
    nie ">="). Rueckgabe: `(bester Fokus, alle Messungen in Messreihenfolge)`.
    """
    measured: list[tuple[int, float]] = []
    seen: set[int] = set()
    best_focus: int | None = None
    best_score: float | None = None

    def _measure_once(focus: int) -> None:
        nonlocal best_focus, best_score
        if focus in seen:
            return
        seen.add(focus)
        score = measure(focus)
        measured.append((focus, score))
        if best_score is None or score > best_score:
            best_score = score
            best_focus = focus

    for focus in coarse:
        _measure_once(focus)

    if best_focus is None:
        raise ValueError("sweep_focus: 'coarse' war leer, kein Grob-Maximum gefunden")

    fine_lo = max(lo, best_focus - fine_radius)
    fine_hi = min(hi, best_focus + fine_radius)
    for focus in range(fine_lo, fine_hi + 1, fine_step):
        _measure_once(focus)

    return best_focus, measured
