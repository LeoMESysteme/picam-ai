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
from dispread.ocr.dotmatrix_templates import Templates, classify, load_templates

BACKEND_ID = "dotmatrix"
BACKEND_VERSION = "1"
MAX_SATURATED = 0.02

# Zellen 1-7: 0-2 Leerzellen, dann 6 Ziffern mit genau einem Punkt, die Ziffer
# vor dem Punkt ist nie leer (OQ-41, gsv2as_leading_zero_v2); Zelle 8 leer.
_NUMBER = re.compile(r"^( {0,2})(\d[\d.]*)$")


def parse_gsv2as(cells: str) -> tuple[str, float] | None:
    if len(cells) != 9 or cells[0] != "+" or cells[8] != " ":
        return None
    m = _NUMBER.match(cells[1:8])
    if m is None:
        return None
    body = m.group(2)
    if body.count(".") != 1 or body.startswith(".") or body.endswith("."):
        return None
    if sum(ch.isdigit() for ch in body) + len(m.group(1)) != 6:
        return None
    raw = "+" + body
    return raw, float(body)


class DotMatrixReader:
    def __init__(self, templates: Templates) -> None:
        self._t = templates

    @classmethod
    def from_file(cls, path: Path, expected_sha256: str | None = None) -> DotMatrixReader:
        return cls(load_templates(path, expected_sha256))

    @property
    def backend_id(self) -> str:
        return BACKEND_ID

    @property
    def declares_confidence_calibrated(self) -> bool:
        return False

    def read(self, crop: np.ndarray, layout: CharLayout) -> ReadResult:
        gray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        cells = range(layout.classified_cells)
        sampled = sample_image(gray, layout.grid, cells)
        diag: dict = {
            "contrast": sampled.contrast,
            "saturated_fraction": sampled.saturated_fraction,
            "templates_groups": list(self._t.groups),
            "format_id": layout.format_id,
        }
        if sampled.saturated_fraction > MAX_SATURATED:
            return self._reject("ueberbelichtet", diag, layout)
        if sampled.contrast < MIN_CONTRAST:
            return self._reject("kontrast", diag, layout)

        norm = normalized(sampled)
        decisions = [classify(norm[i], self._t) for i in range(len(cells))]
        diag["cells"] = [
            {
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
        first_reject = next((d.reason for d in decisions if d.reason), None)
        sign_ok = decisions[0].text == "+"
        if not sign_ok:
            reason = first_reject if decisions[0].text is None else "vorzeichen"
            return self._reject(reason, diag, layout, glyphs, sign_readable=False)
        if first_reject:
            return self._reject(first_reject, diag, layout, glyphs)
        cells_text = "".join(d.text for d in decisions)
        parsed = parse_gsv2as(cells_text)
        if parsed is None:
            return self._reject("format", diag, layout, glyphs)
        raw, value = parsed
        diag["reject_reason"] = None
        return ReadResult(
            raw_text=raw, value=value, sign_detected=False, sign_region_readable=True,
            decimal_point_detected=True, decimal_point_index=cells_text[1:8].index(".") - 1,
            unit_text=layout.unit, status_flags=frozenset(), glyphs=glyphs,
            backend_id=BACKEND_ID, backend_version=BACKEND_VERSION, diagnostics=diag,
        )

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
