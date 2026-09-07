"""Klassische 7-Segment-Auswertung.

Primaeres Backend, nicht Notloesung. Begruendung (docs/project_history.md):
es liefert *erklaerbare* Evidenz - welches Segment wie hell war - und genau das
braucht die Freigabelogik aus Konzept.md §7. Eine generische OCR liefert nur
einen String und eine Konfidenz, die keine Fehlerwahrscheinlichkeit ist.

Verfahren: Der entzerrte Ausschnitt wird nach dem bestaetigten Profilraster in
Ziffernzellen geteilt, in jeder Zelle werden die sieben Segmentpositionen
abgetastet, und das Muster wird in einer Tabelle gesucht. Ein Muster, das in
keiner Tabelle steht, wird abgelehnt und nicht auf die naechstliegende Ziffer
geraten.
"""

from __future__ import annotations

import numpy as np

from dispread.layout import (
    SEGMENT_NAMES,
    SEGMENT_SAMPLE_POINTS,
    SEGMENTS_TO_DIGIT,
    DisplayLayout,
)
from dispread.ocr import GlyphEvidence, ReadResult

BACKEND_ID = "sevenseg"
BACKEND_VERSION = "2"

#: Anteil der Zellenbreite, ueber den ein Segment gemittelt wird.
_SAMPLE_HALFWIDTH = 0.06

#: Unterhalb dieses Kontrasts zwischen aktiven und inaktiven Segmenten (0..1)
#: ist die Anzeige nicht auswertbar. Verhindert, dass in einem gleichmaessig
#: dunklen oder ueberstrahlten Bild Segmente "erkannt" werden.
_MIN_CONTRAST = 0.10

#: Anteil gesaettigter Bildpunkte, ab dem der Ausschnitt als ueberstrahlt gilt.
#: Reflexionen sind laut Konzept.md §9 ein Hauptproblem des Aufbaus - und
#: gemessen der Fall, in dem stille Fehlablesungen entstehen (docs/VALIDATION.md).
_MAX_SATURATED_FRACTION = 0.02


def _to_gray(crop: np.ndarray) -> np.ndarray:
    if crop.ndim == 2:
        return crop
    import cv2

    return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)


def _sample(gray: np.ndarray, box: tuple[int, int, int, int], rel: tuple[float, float]) -> float:
    """Mittlere Helligkeit (0..1) um einen relativen Punkt in einer Zelle."""
    x, y, w, h = box
    cx = x + rel[0] * w
    cy = y + rel[1] * h
    r = max(1.0, _SAMPLE_HALFWIDTH * w)
    x1 = max(0, int(cx - r))
    x2 = min(gray.shape[1], int(cx + r) + 1)
    y1 = max(0, int(cy - r))
    y2 = min(gray.shape[0], int(cy + r) + 1)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return float(gray[y1:y2, x1:x2].mean()) / 255.0


def segment_threshold(samples: np.ndarray) -> tuple[float, float]:
    """(Schwelle, Kontrast) aus den Segmentmessungen selbst, beide 0..1.

    Zwei Fallen, die diese Funktion umgeht:

    1. Die Schwelle darf nicht pro Zelle aus deren Min/Max kommen: bei einer
       "8" sind alle sieben Segmente aktiv, der zellinterne Kontrast waere null
       und die Zelle wuerde faelschlich als unlesbar verworfen.
    2. Sie darf auch nicht aus allen Bildpunkten des Ausschnitts kommen. Eine
       7-Segment-Anzeige hat drei Helligkeitsstufen - Panel, inaktives Segment,
       aktives Segment - und die inaktiven Segmente sind die haeufigste. Otsu
       ueber alle Bildpunkte trennt dann Panel von Segmenten statt inaktiv von
       aktiv (gemessen: Panel 19, inaktiv 34, aktiv 115 von 255).

    Deshalb wird ueber die gepoolten Segmentmessungen aller Stellen
    geschwellt. Bekannte Grenze: zeigt die Anzeige ausschliesslich "8", gibt es
    keine inaktive Klasse, der Kontrast ist klein und der Ausschnitt wird
    abgelehnt. Eine Falschablehnung ist nach Konzept.md §7 die zulaessige
    Richtung - geraten wird nicht. Siehe OQ-13.
    """
    values = np.sort(np.asarray(samples, dtype=float).ravel())
    if values.size < 2:
        return 0.5, 0.0

    # Otsu in einer Dimension: Schnitt maximaler Zwischenklassenvarianz.
    best_threshold = float(values.mean())
    best_variance = -1.0
    best_contrast = 0.0
    for i in range(1, values.size):
        lo, hi = values[:i], values[i:]
        weight = i * (values.size - i)
        variance = weight * (hi.mean() - lo.mean()) ** 2
        if variance > best_variance:
            best_variance = variance
            best_threshold = float((lo.max() + hi.min()) / 2.0)
            best_contrast = float(hi.mean() - lo.mean())
    return best_threshold, best_contrast


def _decode_cell(values: dict[str, float], threshold: float, contrast: float) -> GlyphEvidence:
    """Eine Ziffernzelle aus ihren Segmentmessungen auswerten."""
    if contrast < _MIN_CONTRAST:
        # Zu wenig Kontrast: nichts entscheiden. Keine Ziffer raten.
        return GlyphEvidence(text="?", confidence=0.0, segments=None, margin=0.0)

    on = {seg: values[seg] > threshold for seg in SEGMENT_NAMES}
    pattern = frozenset(seg for seg, is_on in on.items() if is_on)
    segments = tuple(on[seg] for seg in SEGMENT_NAMES)

    # Abstand der knappsten Segmentmessung zur Schwelle, normiert auf den
    # Kontrast. Klein = die Entscheidung haette leicht anders ausfallen koennen.
    margin = min(abs(values[seg] - threshold) for seg in SEGMENT_NAMES) / (contrast / 2.0)
    margin = float(min(1.0, max(0.0, margin)))

    digit = SEGMENTS_TO_DIGIT.get(pattern)
    if digit is None:
        # Muster steht in keiner Tabelle. Nicht auf die naechstliegende Ziffer
        # raten - nur festhalten, welche nahe lagen, und ablehnen.
        candidates = tuple(
            SEGMENTS_TO_DIGIT[segs] for segs in sorted(SEGMENTS_TO_DIGIT, key=lambda s: len(s ^ pattern))[:2]
        )
        return GlyphEvidence(
            text="?",
            confidence=0.0,
            segments=segments,
            ambiguous_with=candidates,
            margin=margin,
        )

    return GlyphEvidence(text=digit, confidence=margin, segments=segments, margin=margin)


class SevenSegmentReader:
    """7-Segment-Leser mit Per-Segment-Evidenz."""

    backend_id = BACKEND_ID

    @property
    def declares_confidence_calibrated(self) -> bool:
        # Es existiert keine Kalibriermessung gegen echte Fehlerraten.
        # Konzept.md §7: Konfidenz ist keine Fehlerwahrscheinlichkeit.
        return False

    def read(self, crop: np.ndarray, layout: DisplayLayout) -> ReadResult:
        gray = _to_gray(crop)
        h, w = gray.shape[:2]

        boxes = layout.cell_boxes(w, h)
        cell_values = [{seg: _sample(gray, box, rel) for seg, rel in SEGMENT_SAMPLE_POINTS.items()} for box in boxes]

        pooled = np.array([v for values in cell_values for v in values.values()])
        threshold, contrast = segment_threshold(pooled)

        glyphs = tuple(_decode_cell(values, threshold, contrast) for values in cell_values)
        digits = "".join(g.text for g in glyphs)

        # Vorzeichenstelle. sign_region_readable wird getrennt gefuehrt, weil
        # ein nicht auswertbarer Bereich zur Ablehnung fuehren muss und nicht
        # zu "positiv" (Konzept.md §7, fehlendes Minuszeichen).
        sign_box = layout.sign_box(w, h)
        sign_readable = contrast >= _MIN_CONTRAST
        sign_value = _sample(gray, sign_box, (0.5, 0.5)) if sign_box else 0.0
        sign_detected = bool(sign_box and sign_readable and sign_value > threshold)
        if sign_box is None:
            sign_readable = True

        # Ueberstrahlung messen: Reflexionen sind der gemessene Fall, in dem
        # stille Fehlablesungen entstehen. Der Leser meldet das als Befund,
        # die Entscheidung darueber trifft die Freigabe (validate.py).
        saturated_fraction = float((gray >= 250).mean())

        status_flags: set[str] = set()
        # Ueberlauf: jede Stelle zeigt ausschliesslich das Mittelsegment. Das
        # ist ein Betriebszustand, kein Zahlenwert.
        g_index = SEGMENT_NAMES.index("g")
        if glyphs and all(g.segments is not None and tuple(g.segments) == tuple(i == g_index for i in range(7)) for g in glyphs):
            status_flags.add("overflow")
        if saturated_fraction > _MAX_SATURATED_FRACTION:
            status_flags.add("glare")

        dp_index = layout.decimal_point_index()
        # Bei festem Format aus dem Profil gilt der Dezimalpunkt als bekannt.
        # Ist er im Profil nicht festgelegt, muesste er gemessen werden - das
        # ist noch nicht implementiert und wird ehrlich als False gemeldet.
        dp_detected = dp_index is not None

        value: float | None = None
        raw_text = digits
        if "?" not in digits and "overflow" not in status_flags and dp_index is not None:
            body = digits[: dp_index + 1] + "." + digits[dp_index + 1 :]
            raw_text = ("-" if sign_detected else "") + body
            try:
                value = float(raw_text)
            except ValueError:
                value = None

        return ReadResult(
            raw_text=raw_text,
            value=value,
            sign_detected=sign_detected,
            sign_region_readable=sign_readable,
            decimal_point_detected=dp_detected,
            decimal_point_index=dp_index,
            unit_text=layout.unit,
            status_flags=frozenset(status_flags),
            glyphs=glyphs,
            backend_id=BACKEND_ID,
            backend_version=BACKEND_VERSION,
            diagnostics={
                "unreadable_cells": sum(1 for g in glyphs if g.text == "?"),
                "min_margin": min((g.margin for g in glyphs), default=0.0),
                "contrast": contrast,
                "threshold": threshold,
                "saturated_fraction": saturated_fraction,
                # Die Einheit stammt aus dem bestaetigten Profil, sie wurde
                # nicht gelesen. Das muss unterscheidbar bleiben.
                "unit_source": "profile",
            },
        )
