"""Rastergeometrie aus einem einmal getippten Sollwert bestimmen.

Der Bediener bestaetigt die Anzeige und tippt einmal, was darauf steht. Statt
`ziffernabstand`, `vorzeichenbreite` und die uebrigen Verhaeltnisse von Hand zu
justieren, sucht diese Funktion den Parametersatz, der genau diesen Text
dekodiert - und unter mehreren passenden den mit der groessten Trennschaerfe.

Warum Trennschaerfe und nicht blosse Uebereinstimmung: an sechs realen
Aufnahmen eines Geraets erreichen `thickness=0.20/inset=0.05` und
`thickness=0.12/inset=0.10` dieselbe Trefferzahl (Messung 2026-09-11,
docs/VALIDATION.md). Ein Autofit auf "stimmt" wuerde davon einen beliebigen
nehmen. Passt keiner, wird das gemeldet - nichts wird teilweise geraten.

Angepasst wird auf dem Bestaetigungsbild. Bewertet wird spaeter auf
Clipframes, die diese Anpassung nie gesehen haben (OQ-23 verbietet
Nachstimmen und Bewerten am selben Bild).

Bewusst ohne Abhaengigkeit von `dispread.workbench.controller`: Task 5 laesst
den Controller `fit_layout` importieren. Wuerde dieses Modul umgekehrt aus dem
Controller importieren, entstuende ein Kreisimport. Deshalb reimplementiert
`_crop_box` unten die dortige `crop_box`-Logik lokal, statt sie zu importieren.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import cv2
import numpy as np

from dispread.layout import DisplayLayout
from dispread.ocr.sevenseg import SevenSegmentReader

__all__ = ["AutofitResult", "parse_expected", "fit_layout"]

#: Zielgroesse des Leserausschnitts. Muss zu
#: `dispread.workbench.controller.CROP_SIZE` passen - beide skalieren auf das
#: Format, gegen das der 7-Segment-Leser sein Raster abtastet.
CROP_SIZE = (400, 160)

#: Kandidaten je Parameter. Bewusst fest aufgezaehlt statt kontinuierlich
#: optimiert: die Suche bleibt deterministisch und nachvollziehbar.
_CANDIDATES: dict[str, tuple[float, ...]] = {
    "digit_gap_ratio": (0.0, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0, 1.4),
    "sign_cell_ratio": (0.3, 0.4, 0.5, 0.6, 0.8, 1.0),
    "thickness_ratio": (0.08, 0.10, 0.12, 0.14, 0.16, 0.20, 0.25),
    "inset_ratio": (0.0, 0.05, 0.10, 0.15, 0.20),
}
#: Verschiebung und Skalierung des OCR-Rahmens, relativ zu seiner eigenen
#: Groesse. Eng begrenzt: der Rahmen ist vom Bediener bestaetigt, der Autofit
#: zieht ihn nur nach, er sucht ihn nicht neu (sonst erbt er die
#: Haupt-/Nebenanzeige-Verwechslung aus OQ-25).
_BOX_SHIFTS = (-0.06, -0.03, 0.0, 0.03, 0.06)
_BOX_SCALES = (0.90, 0.95, 1.0, 1.05, 1.10)
_PASSES = 2
#: Unterschied in der Trennschaerfe, unterhalb dessen das Optimum als flach
#: gilt. Vorabdefault.
_FLAT_DELTA = 0.05
#: Sortierbares Mass fuer "diese Kombination dekodiert den Sollwert nicht
#: exakt". Kleiner als jeder erreichbare `min_margin` (0..1).
_NO_MATCH = -1.0


@dataclass(frozen=True, slots=True)
class AutofitResult:
    matched: bool
    layout: DisplayLayout
    ocr_box: tuple[float, float, float, float]
    #: Kleinster Segmentabstand zur Entscheidungsschwelle im besten Treffer.
    #: KEINE Fehlerwahrscheinlichkeit - nur ein Trennschaerfemass.
    separation: float
    #: Derselbe Wert fuer den zweitbesten, deutlich anderen Parametersatz.
    runner_up: float
    #: True, wenn bester und zweitbester Satz sich kaum unterscheiden - das
    #: Optimum ist dann flach und die Geometrie unterbestimmt.
    flat_optimum: bool
    evaluated: int
    reason: str | None


def parse_expected(text: str) -> tuple[str, bool, int, int]:
    """'-000,13' -> ('00013', True, 5, 2).

    Komma und Punkt gelten beide als Dezimaltrenner - Bediener tippen im
    deutschen Layout mit Komma, der Leser liefert einen Punkt.
    """
    cleaned = text.strip().replace(",", ".").replace(" ", "")
    minus = cleaned.startswith("-")
    body = cleaned.lstrip("+-")
    if not body or not all(c.isdigit() or c == "." for c in body) or body.count(".") > 1:
        raise ValueError(f"Unlesbarer Sollwert: {text!r}")
    whole, _, fraction = body.partition(".")
    digits = whole + fraction
    if not digits.isdigit():
        raise ValueError(f"Unlesbarer Sollwert: {text!r}")
    return digits, minus, len(digits), len(fraction) if "." in body else 0


def _crop_box(image: np.ndarray, box: tuple[float, float, float, float]) -> np.ndarray:
    """Normierten Innenausschnitt schneiden und auf Leserformat skalieren.

    Lokale Nachbildung von `dispread.workbench.controller.crop_box` - siehe
    Modul-Docstring, warum das keine Abhaengigkeit von dort werden darf.
    """
    height, width = image.shape[:2]
    x, y, box_width, box_height = box
    left, top = int(round(x * width)), int(round(y * height))
    right, bottom = int(round((x + box_width) * width)), int(round((y + box_height) * height))
    cropped = image[max(0, top) : min(height, bottom), max(0, left) : min(width, right)]
    if cropped.size == 0:
        raise ValueError("OCR-Rahmen ist leer")
    return cv2.resize(cropped, CROP_SIZE, interpolation=cv2.INTER_LINEAR)


def _evaluate(
    crop: np.ndarray,
    reader: SevenSegmentReader,
    base: DisplayLayout,
    params: dict[str, float],
    box: tuple[float, float, float, float],
    expected: str,
    minus: bool,
) -> float:
    """Sortierbares Mass fuer einen Parametersatz.

    `-1.0`, wenn die Ziffernfolge nicht exakt stimmt oder das Vorzeichen nicht
    passt (das schliesst `value is None` - abgelehnt - und jede unlesbare
    Stelle "?" automatisch ein, weil deren Text nie zu `expected` passt).
    Sonst `min_margin` aus den Diagnosen: die vorhandene, genau dafuer
    gedachte Trennschaerfe.
    """
    try:
        reader_crop = _crop_box(crop, box)
    except ValueError:
        return _NO_MATCH
    trial_layout = replace(base, **params)
    read = reader.read(reader_crop, trial_layout)
    if read.value is None:
        return _NO_MATCH
    digits_read = read.raw_text.lstrip("-").replace(".", "")
    if digits_read != expected or read.sign_detected != minus:
        return _NO_MATCH
    return float(read.diagnostics.get("min_margin", 0.0))


def _box_candidates(
    ocr_box: tuple[float, float, float, float],
) -> tuple[tuple[float, float, float, float], ...]:
    """Verschobene/skalierte Varianten von `ocr_box`, relativ zu seiner eigenen
    Groesse (siehe `_BOX_SHIFTS`/`_BOX_SCALES`).

    Kein voller Kreuzprodukt aus Verschiebung x, Verschiebung y und Skalierung
    - das waere bei fuenf Werten je Achse 125 Auswertungen allein fuer den
    Rahmen. Stattdessen je ein Durchlauf pro Freiheitsgrad (x verschieben, y
    verschieben, gleichmaessig skalieren), skalieren zentriert um die
    Rahmenmitte. Deterministisch, doppelte Kandidaten (u. a. die
    unveraenderte Ausgangsbox, die in allen drei Durchlaeufen als "kein
    Versatz"/"keine Skalierung" vorkommt) werden entfernt.
    """
    x, y, w, h = ocr_box
    seen: set[tuple[float, float, float, float]] = set()
    candidates: list[tuple[float, float, float, float]] = []

    def add(candidate: tuple[float, float, float, float]) -> None:
        if candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

    for shift in _BOX_SHIFTS:
        add((x + shift * w, y, w, h))
    for shift in _BOX_SHIFTS:
        add((x, y + shift * h, w, h))
    for scale in _BOX_SCALES:
        new_w, new_h = w * scale, h * scale
        add((x - (new_w - w) / 2.0, y - (new_h - h) / 2.0, new_w, new_h))

    return tuple(candidates)


def fit_layout(
    crop: np.ndarray,
    text: str,
    layout: DisplayLayout,
    ocr_box: tuple[float, float, float, float],
    *,
    reader: Any = None,
) -> AutofitResult:
    reader = reader or SevenSegmentReader()
    expected, minus, digits, decimals = parse_expected(text)

    base = replace(
        layout,
        digits=digits,
        decimals=decimals,
        # Nur ein Minuszeichen beweist eine Vorzeichenstelle. Seine Abwesenheit
        # beweist nichts - die Einstellung des Bedieners bleibt stehen.
        has_sign=True if minus else layout.has_sign,
    )

    state = {name: getattr(base, name) for name in _CANDIDATES}
    box = tuple(float(v) for v in ocr_box)
    best = _evaluate(crop, reader, base, state, box, expected, minus)
    runner_up = _NO_MATCH
    evaluated = 1

    for _ in range(_PASSES):
        for name, values in _CANDIDATES.items():
            for value in values:
                trial = dict(state, **{name: value})
                if trial == state:
                    # Identisch zum aktuellen Satz - kein "zweitbester,
                    # deutlich anderer" Kandidat (AutofitResult.runner_up).
                    continue
                score = _evaluate(crop, reader, base, trial, box, expected, minus)
                evaluated += 1
                if score > best:
                    runner_up, best, state = best, score, trial
                elif score > runner_up:
                    runner_up = score
        for box_candidate in _box_candidates(box):
            if box_candidate == box:
                continue
            score = _evaluate(crop, reader, base, state, box_candidate, expected, minus)
            evaluated += 1
            if score > best:
                runner_up, best, box = best, score, box_candidate
            elif score > runner_up:
                runner_up = score

    matched = best >= 0.0
    if not matched:
        # Koordinatenabstieg kann in einem lokalen Optimum landen; ein
        # erfolgloser Autofit meldet das ehrlich und liefert das UNVERAENDERTE
        # Eingabelayout zurueck - nie eine Teilvermutung.
        return AutofitResult(
            matched=False,
            layout=layout,
            ocr_box=ocr_box,
            separation=_NO_MATCH,
            runner_up=runner_up,
            flat_optimum=False,
            evaluated=evaluated,
            reason=(
                f"Kein Parametersatz aus {evaluated} Auswertungen dekodiert "
                f"{text!r} exakt (erwartete Ziffern {expected!r}, "
                f"Vorzeichen={minus})."
            ),
        )

    return AutofitResult(
        matched=True,
        layout=replace(base, **state),
        ocr_box=box,
        separation=best,
        runner_up=runner_up,
        flat_optimum=(best - runner_up) < _FLAT_DELTA,
        evaluated=evaluated,
        reason=None,
    )
