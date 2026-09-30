"""Measured GSV-2AS leading-zero suppression shared by text consumers."""

from __future__ import annotations

MAX_VERIFIED_SUPPRESSED_ZEROS = 2


def count_suppressed_leading_zeros(rest: str) -> int:
    """Count leading zeroes before the last digit of the integer part."""
    int_len = 0
    while int_len < len(rest) and rest[int_len].isdigit():
        int_len += 1
    zeros = 0
    while zeros < int_len - 1 and rest[zeros] == "0":
        zeros += 1
    return zeros


def map_suppressed_leading_zeros(text: str, *, blank_cells: bool) -> str | None:
    """Replace suppressed zeroes with blanks, or remove them for display labels.

    Return None for three or more suppressed zeroes: that case has no glass
    measurement. This maps characters only; callers validate telegram syntax.
    """
    if not text:
        return text
    sign = text[0] if text[0] in "+-" else ""
    rest = text[len(sign) :]
    zeros = count_suppressed_leading_zeros(rest)
    if zeros > MAX_VERIFIED_SUPPRESSED_ZEROS:
        return None
    replacement = " " * zeros if blank_cells else ""
    return sign + replacement + rest[zeros:]
