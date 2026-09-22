"""OCR-Backend fuer Zeichen-/dot-matrix-LCDs ueber die tesseract-CLI.

Ergaenzt sevenseg.py, ersetzt es nicht: sevenseg dekodiert 7-Segment-
Balkenmuster (DIGIT_SEGMENTS), kennt aber keine Buchstaben/Symbole und keine
Punktraster-Glyphen. Der GSV-Sensor (technology=LCD) ist eine dot-matrix-
Zeichen-LCD (HD44780-artig, z. B. "+1.05000 mV/V") - strukturell nicht mit
sevenseg lesbar, unabhaengig von jeder Geometrie-/Schwellenkalibrierung
(2026-09-21, siehe docs/superpowers/specs/2026-09-21-tesseract-backend-design.md).

Ruft die tesseract-Binary als Subprozess auf (kein pytesseract - siehe
Design-Spec: keine neue Abhaengigkeit fuer etwas, das ein Subprozessaufruf
genauso leistet). Wie sevenseg gilt: Unlesbares wird abgelehnt, nie geraten
(Konzept.md §7). Die Konfidenzschwelle (`_MIN_WORD_CONFIDENCE`) ist ein
unvalidierter Vorabdefault, wie `sevenseg._MIN_CONTRAST` einer ist - manuelle
Stichproben zeigten, dass die Tesseract-Wortkonfidenz stark von der
Vorverarbeitung abhaengt, zu wenige Datenpunkte fuer eine echte Kalibrierung.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import replace

import cv2
import numpy as np

from dispread.layout import DisplayLayout
from dispread.ocr import GlyphEvidence, ReadResult

BACKEND_ID = "tesseract_cli"

#: Zielmindesthoehe (Pixel) vor der Tesseract-Erkennung. Kleine Ausschnitte
#: erkennt Tesseract schlecht - Vorabdefault, nicht an mehreren Geraeten
#: validiert.
_MIN_HEIGHT_PX = 120

#: Unterhalb dieser mittleren Wortkonfidenz (0..100) wird abgelehnt, selbst
#: wenn das erkannte Muster zur erwarteten Ziffernzahl passt - ein
#: unvalidierter Vorabdefault (siehe Modul-Docstring).
_MIN_WORD_CONFIDENCE = 40.0

#: Tesseract-Subprozess-Zeitlimit in Sekunden.
_TIMEOUT_S = 10


def _tesseract_version() -> str:
    """`tesseract --version`s erste Zeile in eine kurze Versionskennung zerlegen."""
    result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, timeout=_TIMEOUT_S)
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    parts = first_line.split()
    return parts[1] if len(parts) > 1 else "unbekannt"


def _whitelist_for(layout: DisplayLayout) -> str:
    """Erlaubtes Zeichenset ausschliesslich aus dem bestaetigten Profil bauen.

    Nie geraten: nur Ziffern/Punkt immer, Vorzeichen nur wenn `has_sign`, die
    Zeichen der bestaetigten `unit` (nie gemessen, siehe Konzept.md §7/OQ-17)
    plus ein Leerzeichen als Worttrenner.

    Bekannte Grenze (Abschluss-Review, 2026-09-21): die Einheit steht in
    derselben Textzeile wie die Zahl (z. B. "+1.05000 mV/V"), ihre Zeichen
    gehen deshalb mit in die Whitelist. `read()` fuegt aber alle erkannten
    Woerter ohne Trenner zusammen (`"".join(...)`), sodass die Einheit direkt
    an die Ziffernfolge klebt (z. B. "+1.05000mV/V"). Der nachfolgende
    Formatcheck (`digits_only.isdigit()`) lehnt das dann als
    "ziffernzahl_stimmt_nicht" ab - fail-safe (nie ein falscher Wert), aber
    ein Nebeneffekt der Ziffernzahlpruefung, keine bewusste Trennung von
    Einheit und Zahl. Absichtlich nicht behoben in dieser Fix-Runde
    (Finding 8: nur dokumentiert, Verhalten unveraendert).
    """
    chars = set("0123456789.")
    if layout.has_sign:
        chars |= {"+", "-"}
    if layout.unit:
        chars |= set(layout.unit)
    chars.add(" ")
    return "".join(sorted(chars))


def _preprocess(crop: np.ndarray, layout: DisplayLayout) -> np.ndarray:
    """Graustufen, Polaritaet normieren, hochskalieren, binarisieren.

    `bright_on_dark` (LED-Default) wird invertiert - Tesseract erwartet
    dunklen Text auf hellem Grund. `dark_on_bright` (LCD) bleibt unveraendert.
    """
    gray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if layout.polarity == "bright_on_dark":
        gray = 255 - gray
    height, width = gray.shape[:2]
    if height < _MIN_HEIGHT_PX:
        scale = _MIN_HEIGHT_PX / height
        gray = cv2.resize(gray, (int(round(width * scale)), _MIN_HEIGHT_PX), interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _run_tesseract(image: np.ndarray, *, whitelist: str) -> list[tuple[float, str]]:
    """`image` an die tesseract-CLI uebergeben, Wortebene (TSV) zurueckgeben.

    TSV statt zweier getrennter Aufrufe fuer Text und Konfidenz - eine
    Tesseract-Ausfuehrung liefert beides. Nur Ebene 5 (Wort) wird behalten;
    Seiten-/Block-/Absatz-/Zeilenebenen tragen `conf=-1` und keinen Text.
    """
    descriptor, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(descriptor)
    try:
        cv2.imwrite(tmp_path, image)
        result = subprocess.run(
            [
                "tesseract",
                tmp_path,
                "stdout",
                "--psm",
                "7",
                "-c",
                f"tessedit_char_whitelist={whitelist}",
                "tsv",
            ],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
        )
    finally:
        os.unlink(tmp_path)

    words: list[tuple[float, str]] = []
    lines = result.stdout.splitlines()
    for line in lines[1:]:  # erste Zeile ist der TSV-Spaltenkopf
        columns = line.split("\t")
        if len(columns) != 12:
            continue
        level, conf, text = columns[0], columns[10], columns[11]
        if level != "5":
            continue
        try:
            confidence = float(conf)
        except ValueError:
            continue
        if confidence < 0:  # -1 auf Nicht-Wort-Ebenen
            continue
        words.append((confidence, text))
    return words


def _empty_result(layout: DisplayLayout, backend_version: str, *, reason: str, raw_text: str = "") -> ReadResult:
    return ReadResult(
        raw_text=raw_text,
        value=None,
        sign_detected=False,
        sign_region_readable=not layout.has_sign,
        decimal_point_detected=layout.decimals is not None,
        decimal_point_index=layout.decimal_point_index(),
        unit_text=layout.unit,
        status_flags=frozenset(),
        glyphs=tuple(GlyphEvidence(text="?", confidence=0.0) for _ in range(layout.digits)),
        backend_id=BACKEND_ID,
        backend_version=backend_version,
        diagnostics={"unit_source": "profile", "reject_reason": reason},
    )


class TesseractReader:
    """OCR-Leser fuer Zeichen-/dot-matrix-LCDs ueber die tesseract-CLI."""

    backend_id = BACKEND_ID

    def __init__(self) -> None:
        if shutil.which("tesseract") is None:
            raise RuntimeError(
                "tesseract-Binary nicht gefunden (PATH) - 'sudo apt install tesseract-ocr' (OQ-15)"
            )
        self._version = _tesseract_version()

    @property
    def declares_confidence_calibrated(self) -> bool:
        # Keine Kalibriermessung gegen echte Fehlerraten - Konzept.md §7.
        return False

    def read(self, crop: np.ndarray, layout: DisplayLayout) -> ReadResult:
        processed = _preprocess(crop, layout)
        whitelist = _whitelist_for(layout)
        words = _run_tesseract(processed, whitelist=whitelist)

        if not words:
            return _empty_result(layout, self._version, reason="kein_text_erkannt")

        confidences = [confidence for confidence, _text in words]
        overall_confidence = sum(confidences) / len(confidences)
        full_text = "".join(text for _confidence, text in words)

        sign_detected = False
        sign_region_readable = True
        rest = full_text
        if layout.has_sign:
            if full_text[:1] in ("+", "-"):
                sign_detected = full_text[0] == "-"
                rest = full_text[1:]
            else:
                sign_region_readable = False
                return replace(
                    _empty_result(layout, self._version, reason="vorzeichen_nicht_erkannt", raw_text=full_text),
                    sign_region_readable=False,
                )

        digits_only = rest.replace(".", "")
        if len(digits_only) != layout.digits or not digits_only.isdigit():
            return replace(
                _empty_result(layout, self._version, reason="ziffernzahl_stimmt_nicht", raw_text=full_text),
                sign_detected=sign_detected,
                sign_region_readable=True,
            )

        if overall_confidence < _MIN_WORD_CONFIDENCE:
            return replace(
                _empty_result(layout, self._version, reason="konfidenz_zu_niedrig", raw_text=full_text),
                sign_detected=sign_detected,
                sign_region_readable=True,
            )

        dp_index = layout.decimal_point_index()
        body = digits_only if dp_index is None else digits_only[: dp_index + 1] + "." + digits_only[dp_index + 1 :]
        raw_text = ("-" if sign_detected else "") + body
        value = float(raw_text)

        glyphs = tuple(GlyphEvidence(text=ch, confidence=overall_confidence / 100.0) for ch in digits_only)
        return ReadResult(
            raw_text=raw_text,
            value=value,
            sign_detected=sign_detected,
            sign_region_readable=sign_region_readable,
            decimal_point_detected=dp_index is not None,
            decimal_point_index=dp_index,
            unit_text=layout.unit,
            status_flags=frozenset(),
            glyphs=glyphs,
            backend_id=BACKEND_ID,
            backend_version=self._version,
            diagnostics={
                "unit_source": "profile",
                "word_confidence": overall_confidence,
                "raw_ocr_text": full_text,
            },
        )
