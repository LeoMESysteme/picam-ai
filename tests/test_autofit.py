"""Rastergeometrie aus einem einmal getippten Sollwert bestimmen."""

from __future__ import annotations

import pytest

from dispread.frames.synthetic_source import render_display
from dispread.layout import DisplayLayout
from dispread.ocr.autofit import fit_layout, parse_expected


@pytest.mark.parametrize(
    ("text", "digits_text", "minus", "digits", "decimals"),
    [
        ("28,80", "2880", False, 4, 2),
        ("28.80", "2880", False, 4, 2),
        ("-000.13", "00013", True, 5, 2),
        ("1234", "1234", False, 4, 0),
    ],
)
def test_getippter_wert_wird_zerlegt(text, digits_text, minus, digits, decimals):
    assert parse_expected(text) == (digits_text, minus, digits, decimals)


def test_positiver_wert_beweist_keine_fehlende_vorzeichenstelle():
    """Nur ein Minuszeichen beweist eine Vorzeichenstelle - seine Abwesenheit nicht."""
    layout = DisplayLayout(digits=4, decimals=2, has_sign=True, unit="V")
    image, _, area = render_display(28.80, layout)
    x, y, w, h = area
    result = fit_layout(image[y : y + h, x : x + w], "28,80", layout, (0.0, 0.0, 1.0, 1.0))
    assert result.layout.has_sign is True  # unveraendert uebernommen


def test_autofit_findet_ein_abweichendes_raster(recwarn):
    """Start mit den Defaults, Anzeige mit deutlichem Ziffernabstand."""
    real = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V", digit_gap_ratio=0.65)
    image, _, area = render_display(12.34, real)
    x, y, w, h = area
    crop = image[y : y + h, x : x + w]

    start = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V")  # gap 0.0
    assert start.digit_gap_ratio == 0.0

    result = fit_layout(crop, "12,34", start, (0.0, 0.0, 1.0, 1.0))
    assert result.matched, result.reason
    assert result.layout.digit_gap_ratio == pytest.approx(0.65, abs=0.2)
    assert result.separation > 0.0


def test_autofit_ist_deterministisch():
    layout = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V", digit_gap_ratio=0.65)
    image, _, area = render_display(12.34, layout)
    x, y, w, h = area
    crop = image[y : y + h, x : x + w]
    start = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V")
    first = fit_layout(crop, "12,34", start, (0.0, 0.0, 1.0, 1.0))
    second = fit_layout(crop, "12,34", start, (0.0, 0.0, 1.0, 1.0))
    assert first == second


def test_erfolgloser_autofit_liefert_das_eingabelayout_unveraendert():
    """Kein Teilraten: was nicht passt, wird als nicht passend gemeldet."""
    layout = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V")
    image, _, area = render_display(12.34, layout)
    x, y, w, h = area
    result = fit_layout(image[y : y + h, x : x + w], "99,99", layout, (0.0, 0.0, 1.0, 1.0))
    assert not result.matched
    assert result.layout == layout
    assert result.reason
