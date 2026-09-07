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
BACKEND_VERSION = "1"

#: Anteil der Zellenbreite, ueber den ein Segment gemittelt wird.
_SAMPLE_HALFWIDTH = 0.06

#: Unterhalb dieses Kontrasts (0..1, ueber den ganzen Ausschnitt) ist die
#: Anzeige nicht auswertbar. Verhindert, dass in einem gleichmaessig dunklen
#: oder ueberstrahlten Bild Segmente "erkannt" werden.
_MIN_CONTRAST = 0.18


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


def global_threshold(gray: np.ndarray) -> tuple[float, float]:
    """(Schwelle, Kontrast) fuer den ganzen Ausschnitt, beide 0..1.

    Die Schwelle darf NICHT pro Zelle aus deren Min/Max kommen: bei einer "8"
    sind alle sieben Segmente aktiv, der zellinterne Kontrast ist damit null
    und die Zelle wuerde faelschlich als unlesbar verworfen. Otsu ueber den
    gesamten Ausschnitt trennt stattdessen leuchtende Segmente vom Panel.

    Vorausgesetzt ist helle Anzeige auf dunklem Grund (LED). Fuer LCD mit
    umgekehrter Polaritaet fehlt die Behandlung noch - siehe OQ-13.
    """
    import cv2

    thr_abs, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    threshold = float(thr_abs) / 255.0
    lit = gray[gray >= thr_abs]
    dark = gray[gray < thr_abs]
    if lit.size == 0 or dark.size == 0:
        return threshold, 0.0
    contrast = float(lit.mean() - dark.mean()) / 255.0
    return threshold, contrast


def _decode_cell(
    gray: np.ndarray, box: tuple[int, int, int, int], threshold: float, contrast: float
) -> GlyphEvidence:
    """Eine Ziffernzelle gegen die globale Schwelle auswerten."""
    values = {seg: _sample(gray, box, rel) for seg, rel in SEGMENT_SAMPLE_POINTS.items()}

    if contrast < _MIN_CONTRAST:
        # Zu wenig Kontrast: nichts entscheiden. Keine Ziffer raten.
        return GlyphEvidence(text="?", confidence=0.0, segments=None, margin=0.0)

    on = {seg: values[seg] > threshold for seg in SEGMENT_NAMES}
    pattern = frozenset(seg for seg, is_on in on.items() if is_on)
    digit = SEGMENTS_TO_DIGIT.get(pattern)

    # Abstand der knappsten Segmentmessung zur Schwelle, normiert auf den
    # Kontrast. Klein = die Entscheidung haette leicht anders ausfallen koennen.
    margin = min(abs(values[seg] - threshold) for seg in SEGMENT_NAMES) / (contrast / 2.0)
    margin = float(min(1.0, max(0.0, margin)))

    if digit is None:
        # Muster steht in keiner Tabelle. Nicht auf die naechstliegende Ziffer
        # raten - nur festhalten, welche nahe lagen, und ablehnen.
        candidates = tuple(
            SEGMENTS_TO_DIGIT[segs]
            for segs in sorted(SEGMENTS_TO_DIGIT, key=lambda s: len(s ^ pattern))[:2]
        )
        return GlyphEvidence(
            text="?",
            confidence=0.0,
            segments=tuple(on[seg] for seg in SEGMENT_NAMES),
            ambiguous_with=candidates,
            margin=margin,
        )

    return GlyphEvidence(
        text=digit,
        confidence=margin,
        segments=tuple(on[seg] for seg in SEGMENT_NAMES),
        margin=margin,
    )


def _read_sign(
    gray: np.ndarray, layout: DisplayLayout, threshold: float, contrast: float
) -> tuple[bool, bool, float]:
    """(Minus erkannt, Bereich auswertbar, Kontrast) der Vorzeichenstelle.

    Der Bereich gilt als auswertbar, wenn sich Balkenzone und Referenzzonen
    ueberhaupt unterscheiden koennen - sonst ist keine Aussage moeglich und die
    Freigabe muss den Wert ablehnen, statt "positiv" anzunehmen.
    """
    box = layout.sign_box(gray.shape[1], gray.shape[0])
    if box is None:
        return False, True, 1.0

    bar = _sample(gray, box, (0.5, 0.5))

    # Ohne ausreichenden Kontrast im Ausschnitt ist keine Aussage moeglich.
    # Dann muss die Freigabe ablehnen, statt "positiv" anzunehmen -
    # Konzept.md §7 nennt ein fehlendes Minuszeichen als kritischen Fehler.
    readable = contrast >= _MIN_CONTRAST
    detected = readable and bar > threshold
    return detected, readable, contrast


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
        threshold, contrast = global_threshold(gray)

        glyphs = tuple(_decode_cell(gray, box, threshold, contrast) for box in layout.cell_boxes(w, h))
        digits = "".join(g.text for g in glyphs)

        sign_detected, sign_readable, sign_span = _read_sign(gray, layout, threshold, contrast)

        status_flags: set[str] = set()
        # Ueberlauf: alle Stellen zeigen ein Muster, das nur das Mittelsegment
        # aktiv hat. Das ist ein Betriebszustand, kein Zahlenwert.
        if glyphs and all(
            g.segments is not None and g.segments[SEGMENT_NAMES.index("g")] and sum(g.segments) == 1
            for g in glyphs
        ):
            status_flags.add("overflow")

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
                "sign_span": sign_span,
                # Die Einheit stammt aus dem bestaetigten Profil, sie wurde
                # nicht gelesen. Das muss unterscheidbar bleiben.
                "unit_source": "profile",
            },
        )
