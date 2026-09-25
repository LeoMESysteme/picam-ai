"""Software-Fokussuche fuer die Logitech StreamCam (USB/UVC, 046d:0893).

Die StreamCam hat keine Autofokus-Logik, die fuer den Messpfad reproduzierbar
waere - `focus_absolute` (0..255) wird deshalb einmal je Sitzung von
`scripts/harvest-setup.py focus` per Software-Sweep bestimmt: grob ueber den
ganzen Bereich, dann fein um das gefundene Maximum. `measure()` selbst (eine
Kamera anfahren, warten, ein Bild lesen, `sharpness()` darauf anwenden) bleibt
Sache des Aufrufers - dieses Modul kennt weder Kamera noch Datei-I/O, das ist
die Voraussetzung dafuer, dass `sweep_focus` ohne Hardware testbar ist.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import cv2
import numpy as np


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
