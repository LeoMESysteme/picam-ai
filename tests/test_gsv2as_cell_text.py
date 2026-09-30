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
        "+000988.5 mV/V",  # three suppressed zeros are unverified
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


def test_offline_text_preserves_positions_and_blanks_question_marks():
    assert validate_offline_cell_text("+?2.45?7 ") == "+ 2.45 7 "


@pytest.mark.parametrize("text", ["+12.34567", "+12.3456?", "+12.34x67", "+12.3456"])
def test_offline_text_rejects_invalid_length_or_characters(text):
    with pytest.raises(ValueError):
        validate_offline_cell_text(text)
