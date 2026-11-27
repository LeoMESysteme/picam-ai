"""Dot-Matrix-Leser fuer die GSV-2AS-Anzeige (Displaytech 161A, HD44780).

Spec: docs/superpowers/specs/2026-09-24-dotmatrix-reader-design.md. Liest
Zellen 0-8 gegen eingefrorene Vorlagen, lehnt im Zweifel ab und prueft den
ganzen Wert gegen die Formatregel `gsv2as_v1`. Negative Werte werden nie
ausgegeben: es gibt kein einziges Beispiel (Firmware 1.3.07), also kennt der
Leser nur `+`.
"""

from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np

from dispread.layout import CharLayout
from dispread.ocr import GlyphEvidence, ReadResult
from dispread.ocr.dotmatrix_sampling import MIN_CONTRAST, normalized, sample_image
from dispread.ocr.dotmatrix_templates import Templates, classify, load_templates, stack_templates
from dispread.sensors import DisplayDefinition, get_sensor
from dispread.sensors.definitions import GSV2AS_FORMAT_RULE

BACKEND_ID = "dotmatrix"
BACKEND_VERSION = "3"
MAX_SATURATED = 0.02

# Zellen 1-7: 0-2 Leerzellen, dann 6 Ziffern mit genau einem Punkt, die Ziffer
# vor dem Punkt ist nie leer (OQ-41, gsv2as_leading_zero_v2); Zelle 8 leer.
_NUMBER = re.compile(r"^( {0,2})(\d[\d.]*)$")
_DEFAULT_DISPLAY = get_sensor().display


def parse_gsv2as(cells: str, display: DisplayDefinition = _DEFAULT_DISPLAY) -> tuple[str, float] | None:
    roles = display.roles
    if len(cells) != display.classified_cells or not roles.sign:
        return None
    sign = cells[roles.sign[0]]
    if sign != display.anchor.char or any(cells[cell] != " " for cell in roles.separator):
        return None
    m = _NUMBER.match("".join(cells[cell] for cell in roles.number))
    if m is None:
        return None
    body = m.group(2)
    if body.count(".") != 1 or body.startswith(".") or body.endswith("."):
        return None
    if sum(ch.isdigit() for ch in body) + len(m.group(1)) != display.format.digits:
        return None
    raw = sign + body
    return raw, float(body)


FORMAT_RULES = {GSV2AS_FORMAT_RULE: parse_gsv2as}


class DotMatrixReader:
    def __init__(self, templates: Templates, d_max_factor: float = 1.0) -> None:
        if not 1.0 <= d_max_factor <= 2.0:
            raise ValueError("d_max_factor muss zwischen 1.0 und 2.0 liegen")
        self._t = templates
        self._stacked = stack_templates(templates)
        self._d_max_factor = d_max_factor

    @classmethod
    def from_file(cls, path: Path, expected_sha256: str, d_max_factor: float = 1.0) -> DotMatrixReader:
        """Laedt Vorlagen von `path`. `expected_sha256` ist Pflicht (keine
        Default) - ein Betrieb ohne geprueften Bezug auf eine bekannte
        Vorlagendatei waere fail-open (Final-Fix 1)."""
        return cls(load_templates(path, expected_sha256), d_max_factor=d_max_factor)

    @property
    def backend_id(self) -> str:
        return BACKEND_ID

    @property
    def declares_confidence_calibrated(self) -> bool:
        return False

    def read(self, crop: np.ndarray, layout: CharLayout) -> ReadResult:
        parser = FORMAT_RULES.get(layout.format_id)
        if parser is None:
            raise ValueError(f"unbekanntes format_id {layout.format_id!r}, erwartet {', '.join(FORMAT_RULES)}")
        display = layout.display
        sign_cell = display.roles.sign[0]
        separators = display.roles.separator
        gray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        cells = range(layout.classified_cells)
        sampled = sample_image(gray, layout.grid, cells)
        diag: dict = {
            "d_max": self._t.d_max * self._d_max_factor,
            "d_max_factor": self._d_max_factor,
            "contrast": sampled.contrast,
            "saturated_fraction": sampled.saturated_fraction,
            "templates_groups": list(self._t.groups),
            "format_id": layout.format_id,
            "reject_cell": None,
        }
        if sampled.saturated_fraction > MAX_SATURATED:
            return self._reject("ueberbelichtet", diag, layout)
        if sampled.contrast < MIN_CONTRAST:
            return self._reject("kontrast", diag, layout)

        norm = normalized(sampled)
        decisions = [classify(norm[i], self._stacked, d_max_factor=self._d_max_factor) for i in range(len(cells))]
        diag["cells"] = [
            {
                "text": d.text, "reason": d.reason,
                "best": d.best, "second": d.second, "d_best": round(d.d_best, 4),
                "d_second": round(d.d_second, 4), "margin": round(d.margin, 4),
                "dots": [round(float(x), 3) for x in norm[i, d.shift_index]],
            }
            for i, d in enumerate(decisions)
        ]
        diag["min_margin"] = min(d.margin for d in decisions)
        diag["unreadable_cells"] = sum(d.text is None for d in decisions)
        glyphs = tuple(
            GlyphEvidence(
                text=d.text if d.text is not None else "?",
                confidence=0.0,
                segments=None,
                ambiguous_with=(d.second,) if d.reason == "zelle_mehrdeutig" else (),
                margin=d.margin,
            )
            for d in decisions
        )
        # Auch bei Zellablehnung muss die Einrichtung den leeren Rest pruefen koennen.
        blank_cell = self._broken_blank_cell(gray, layout, sampled.ink)
        blank_ok = blank_cell is None
        diag["blank_cells_ok"] = blank_ok
        first_cell = next((i for i, d in enumerate(decisions) if d.reason), None)
        first_reject = decisions[first_cell].reason if first_cell is not None else None
        diag["reject_cell"] = first_cell
        sign_ok = decisions[sign_cell].text == display.anchor.char
        if not sign_ok:
            diag["reject_cell"] = sign_cell
            reason = first_reject if decisions[sign_cell].text is None else "vorzeichen"
            return self._reject(reason, diag, layout, glyphs, sign_readable=False)
        if first_reject:
            if first_cell in separators:
                return self._reject("leerzelle_gestoert", diag, layout, glyphs)
            return self._reject(first_reject, diag, layout, glyphs)
        cells_text = "".join(d.text for d in decisions)
        parsed = parser(cells_text, display)
        blocked_separator = next((cell for cell in separators if decisions[cell].text != " "), None)
        if blocked_separator is not None or not blank_ok:
            diag["reject_cell"] = blocked_separator if blocked_separator is not None else blank_cell
            return self._reject("leerzelle_gestoert", diag, layout, glyphs)
        if parsed is None:
            return self._reject("format", diag, layout, glyphs)
        raw, value = parsed
        diag["reject_reason"] = None
        return ReadResult(
            raw_text=raw, value=value, sign_detected=False, sign_region_readable=True,
            decimal_point_detected=True,
            decimal_point_index="".join(cells_text[cell] for cell in display.roles.number).index(".") - 1,
            unit_text=layout.unit, status_flags=frozenset(), glyphs=glyphs,
            backend_id=BACKEND_ID, backend_version=BACKEND_VERSION, diagnostics=diag,
        )

    def _broken_blank_cell(self, gray: np.ndarray, layout: CharLayout, ink: float) -> int | None:
        """`layout.blank_cells` (Rest, Zellen 13-15) muss sicher als
        Leerzelle erkannt werden. Eigene Abtastung, getrennt von den Zellen
        0-8 - Hintergrund/Punktpegel duerfen sich fuer 0-8 durch diese
        zusaetzliche Pruefung nicht aendern (Final-Fix 3). Der global
        gemessene Tintenpegel `ink` der Zellen 0-8 wird uebernommen statt
        neu (nur ueber 13-15) gemessen: ohne Ziffern in dieser Teilmenge
        waere ihr eigener Tintenpegel praktisch gleich dem Hintergrund, was
        `normalized()` zu einer Rauschverstaerkung statt einer sauberen
        Leerzelle fuehren wuerde (siehe `normalized`-Docstring)."""
        if not layout.blank_cells:
            return None
        sampled = sample_image(gray, layout.grid, layout.blank_cells)
        norm = normalized(sampled, ink=ink)
        decisions = [classify(norm[i], self._stacked, d_max_factor=self._d_max_factor) for i in range(len(layout.blank_cells))]
        return next((cell for cell, d in zip(layout.blank_cells, decisions, strict=True) if d.text != " "), None)

    def _reject(self, reason, diag, layout, glyphs=(), sign_readable=True) -> ReadResult:
        diag["reject_reason"] = reason
        diag.setdefault("min_margin", 0.0)
        diag.setdefault("unreadable_cells", layout.classified_cells)
        return ReadResult(
            raw_text="", value=None, sign_detected=False, sign_region_readable=sign_readable,
            decimal_point_detected=False, decimal_point_index=None, unit_text=layout.unit,
            status_flags=frozenset({"glare"}) if reason == "ueberbelichtet" else frozenset(),
            glyphs=tuple(glyphs), backend_id=BACKEND_ID, backend_version=BACKEND_VERSION,
            diagnostics=diag,
        )
