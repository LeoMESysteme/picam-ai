"""Strict GSV-2AS telegram to displayed-cell conversion."""

from __future__ import annotations

import re

from dispread.leading_zeros import map_suppressed_leading_zeros

_TELEGRAM = re.compile(r"\+([0-9.]{7}) mV/V\Z", re.ASCII)
_OFFLINE = re.compile(r"\+[ 0-9.]{7} ", re.ASCII)


def cell_text_from_telegram(raw: bytes | str) -> str:
    """Return the first nine display cells from a measured GSV-2AS line."""
    if isinstance(raw, bytes):
        try:
            text = raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("telegram is not ASCII") from exc
    elif isinstance(raw, str):
        try:
            raw.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("telegram is not ASCII") from exc
        text = raw
    else:
        raise ValueError("telegram must be bytes or str")

    match = _TELEGRAM.fullmatch(text)
    if match is None:
        raise ValueError("unrecognized GSV-2AS telegram format")

    number = match.group(1)
    if number.count(".") != 1 or sum(ch.isdigit() for ch in number) != 6:
        raise ValueError("numeric block must contain six digits and one decimal point")

    mapped = map_suppressed_leading_zeros("+" + number, blank_cells=True)
    if mapped is None:
        raise ValueError("three or more suppressed leading zeros are unverified")
    return (mapped + " mV/V")[:9]


def validate_offline_cell_text(text: str) -> str:
    """Validate explicit nine-cell operator input; '?' means blank/skip."""
    if not isinstance(text, str) or len(text) != 9 or not text.isascii():
        raise ValueError("offline cell text must be exactly nine ASCII characters")
    if text[8] != " ":
        raise ValueError("the ninth cell must be the measured unit separator")
    if "?" in text[8:]:
        raise ValueError("'?' can only mark numeric cells")
    text = text.replace("?", " ")
    if _OFFLINE.fullmatch(text) is None:
        raise ValueError("offline cell text contains an unsupported character or format")

    block = text[1:8]
    if block.count(".") != 1:
        raise ValueError("offline numeric block must contain one decimal point")
    return text
