import importlib

import pytest

from dispread.gsv2as_cell_text import (
    cell_text_from_telegram,
    normalize_cell_text,
    validate_offline_cell_text,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"+0.60972 mV/V", "+0.60972 "),
        ("+01.2193 mV/V", "+ 1.2193 "),
        ("+00988.5 mV/V", "+  988.5 "),
        ("+5487.00 mV/V", "+5487.00 "),
    ],
)
def test_telegram_maps_first_nine_positions_without_shifting(raw, expected):
    assert cell_text_from_telegram(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "-0.60972 mV/V",
        "+0.60972mV/V",
        "+0.60x72 mV/V",
        b"+0.60972 \xffV/V",
        "+0.6097 mV/V",
    ],
)
def test_telegram_rejects_unverified_or_malformed_input(raw):
    with pytest.raises(ValueError):
        cell_text_from_telegram(raw)


def test_valid_telegram_with_three_suppressed_zeros_is_unverified():
    # Six digits plus one point: syntax is valid, so this reaches the evidence limit.
    with pytest.raises(ValueError, match="three or more suppressed leading zeros"):
        cell_text_from_telegram("+0009.09 mV/V")


def test_shared_leading_zero_mapping_preserves_positions_or_removes_zeros():
    leading_zeros = importlib.import_module("dispread.leading_zeros")
    assert leading_zeros.map_suppressed_leading_zeros("+00988.5 mV/V", blank_cells=True) == "+  988.5 mV/V"
    assert leading_zeros.map_suppressed_leading_zeros("+00988.5 mV/V", blank_cells=False) == "+988.5 mV/V"


def test_shared_leading_zero_mapping_rejects_three_suppressed_zeros():
    leading_zeros = importlib.import_module("dispread.leading_zeros")
    assert leading_zeros.map_suppressed_leading_zeros("+0009.09 mV/V", blank_cells=True) is None
    assert leading_zeros.map_suppressed_leading_zeros("+0009.09 mV/V", blank_cells=False) is None


def test_offline_text_preserves_positions_and_question_marks():
    assert validate_offline_cell_text("+?2.45?7 ") == "+?2.45?7 "


@pytest.mark.parametrize("text", ["+12.34567", "+12.3456?", "+12.34x67"])
def test_offline_text_rejects_invalid_length_or_characters(text):
    with pytest.raises(ValueError):
        validate_offline_cell_text(text)


@pytest.mark.parametrize("text", ["+12.3456", "+0.4678?", "+0.4678? "])
def test_offline_text_pads_eight_cells(text):
    assert validate_offline_cell_text(text) == text.ljust(9)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Getippter Wert: Komma, Einheit und Plus optional, links auf 6 Ziffern aufgefuellt,
        # fuehrende Nullen leer ausser direkt vor dem Punkt.
        ("0,4678", "+ 0.4678 "),
        ("0.4678", "+ 0.4678 "),
        ("+0.4678 mV/V", "+ 0.4678 "),
        ("1.2193 mv/v", "+ 1.2193 "),
        ("988,5", "+  988.5 "),
        ("5487,00", "+5487.00 "),
        ("00.4678", "+ 0.4678 "),
        ("+0.60972", "+0.60972 "),
        # Abgelesene Zellen mit Leerzellen bleiben genau so.
        (" 1,2193", "+ 1.2193 "),
        ("+ 1.2193 ", "+ 1.2193 "),
        ("+  988.5 ", "+  988.5 "),
        ("+ 0,4678 mV/V", "+ 0.4678 "),
        # '?' markiert schwankende Ziffern und zaehlt als Ziffer.
        ("+0.4678?", "+0.4678? "),
        ("+?2.45?7 ", "+?2.45?7 "),
        ("1?.2345", "+1?.2345 "),
    ],
)
def test_normalize_accepts_values_and_cells_by_display_rules(raw, expected):
    assert normalize_cell_text(raw) == expected


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("-0.4678", "Minuszeichen"),
        ("0.4.678", "mehr als ein Dezimalpunkt"),
        ("04678", "genau ein Dezimalpunkt"),
        ("1 2.345", "Leerzelle zwischen den Ziffern"),
        ("12.34567", "7 Ziffern"),
        ("+12.3456?", "7 Ziffern"),
        ("0,4678 V", "unzulaessiges Zeichen 'V'"),
        ("abc", "unzulaessiges Zeichen 'a'"),
        ("", "kein Wert"),
        ("  0,4678", "8 Zellen nach dem Plus"),
        ("+ 00.467", "fuehrende Null in Zelle 2"),
        ("98.5", "drei oder mehr fuehrende Nullen"),
        ("?.123", "mehrdeutig"),
        (".5", "vor dem Punkt"),
        ("+0.4??? ", "nur 4 vergleichbare Zellen"),
        ("0,4678 mV/V mV/V", "unzulaessiges Zeichen"),
    ],
)
def test_normalize_rejects_anything_that_needs_a_guess(raw, message):
    with pytest.raises(ValueError, match=message):
        normalize_cell_text(raw)


def test_normalize_rejects_non_text():
    with pytest.raises(ValueError, match="Text"):
        normalize_cell_text(0.4678)


def test_normalize_matches_browser_cases():
    """Dieselben Faelle prueft tests/live_cell_text.test.mjs gegen setup/cell-text.js."""
    import json
    from pathlib import Path

    cases = json.loads((Path(__file__).parent / "fixtures" / "cell_text_cases.json").read_text(encoding="utf-8"))
    for raw, expected in cases["accept"]:
        assert normalize_cell_text(raw) == expected
    for raw in cases["reject"]:
        with pytest.raises(ValueError):
            normalize_cell_text(raw)


@pytest.mark.parametrize("reference,read,step", [
    ("+ 0.4679 ", "+ 0.4679 ", None),
    ("+ 0.4679 ", "+ 0.4680 ", 1),
    ("+ 0.4680 ", "+ 0.4679 ", -1),
    ("+ 1.0000 ", "+ 0.9999 ", -1),
    ("+ 9.9999 ", "+10.0000 ", 1),
    ("+ 9.9999 ", "+100.000 ", None),
    ("+ 0.4679 ", "+ 0.4681 ", None),
    ("+ 0.4679 ", "+ 0.4579 ", None),
    ("+ 0.467? ", "+ 0.4678 ", None),
    ("+ 0.4679 ", "+00.4680 ", None),
    ("+ 0.4679 ", "+ 0.4680", None),
])
def test_last_place_step(reference, read, step):
    from dispread.gsv2as_cell_text import last_place_step

    assert last_place_step(reference, read) == step
