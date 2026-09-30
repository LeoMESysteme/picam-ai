import importlib

import pytest

from dispread.gsv2as_cell_text import (
    cell_text_from_telegram,
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


def test_offline_text_preserves_positions_and_blanks_question_marks():
    assert validate_offline_cell_text("+?2.45?7 ") == "+ 2.45 7 "


@pytest.mark.parametrize("text", ["+12.34567", "+12.3456?", "+12.34x67", "+12.3456"])
def test_offline_text_rejects_invalid_length_or_characters(text):
    with pytest.raises(ValueError):
        validate_offline_cell_text(text)
