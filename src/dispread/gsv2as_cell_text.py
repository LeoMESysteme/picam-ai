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


#: Ziffern der GSV-2AS-Anzeige (gemessen: immer 6, der Punkt wandert).
DISPLAY_DIGITS = 6
#: Gegenlesen braucht mindestens so viele vergleichbare Zellen 1-7 (setup_checks).
MIN_COMPARABLE_CELLS = 5
_UNIT = re.compile(r"\s*mv/v\s*\Z", re.IGNORECASE | re.ASCII)
_CORE = re.compile(r"[0-9?]*\.[0-9?]*\Z", re.ASCII)


def normalize_cell_text(raw: str) -> str:
    """Bedienereingabe in die neun Zellen 0-8 der Anzeige bringen, ohne zu raten.

    Angenommen werden der Zellentext selbst ("+ 1.2193 ") und ein getippter
    Wert ("0,4678", "+0.4678 mV/V"): Komma wird Punkt, die Einheit mV/V und
    Leerraum am Ende fallen weg, das Plus ist optional. Ein Wert ohne
    fuehrende Leerzellen wird links mit Nullen auf 6 Ziffern aufgefuellt;
    fuehrende Nullen zeigt die Anzeige leer, ausser der direkt vor dem Punkt.
    Fuehrende Leerzellen gelten als abgelesene Zellen und muessen mit dem Rest
    genau 7 Zellen ergeben. '?' markiert eine schwankende Ziffer.

    Abgelehnt (ValueError mit deutschem Text) wird alles, was eine Annahme
    braeuchte: Minus, Buchstaben, Luecken zwischen Ziffern, kein oder mehr als
    ein Punkt, mehr als 6 Ziffern, drei oder mehr fuehrende Nullen (an der
    Anzeige nicht gemessen) und weniger als 5 vergleichbare Zellen.
    """
    if not isinstance(raw, str):
        raise ValueError("Eingabe muss Text sein")
    text = _UNIT.sub("", raw.replace(",", ".")).rstrip()
    stripped = text.lstrip()
    if stripped.startswith("-"):
        raise ValueError("Minuszeichen: negative Werte zeigt dieses GSV-2AS nicht an (Vorzeichenzelle immer '+')")
    if stripped.startswith("+"):
        body = stripped[1:]
    else:
        # Ohne Plus zaehlen fuehrende Leerzeichen als Leerzellen nach der Vorzeichenzelle.
        body = text
    if not body.strip():
        raise ValueError("kein Wert eingegeben")
    if not body.isascii() or any(ch not in "0123456789.? " for ch in body):
        bad = next(ch for ch in body if ch not in "0123456789.? ")
        raise ValueError(f"unzulaessiges Zeichen '{bad}' - erlaubt sind Ziffern, ein Punkt bzw. Komma, Leerzelle und ?")
    core = body.lstrip(" ")
    leading = len(body) - len(core)
    if " " in core:
        raise ValueError("Leerzelle zwischen den Ziffern - die Anzeige zeigt die Ziffern ohne Luecke")
    if core.count(".") != 1:
        raise ValueError("genau ein Dezimalpunkt noetig" if core.count(".") == 0
                         else "mehr als ein Dezimalpunkt")
    if _CORE.fullmatch(core) is None:
        raise ValueError("Format nicht erkannt")
    digits = sum(ch != "." for ch in core)
    if digits > DISPLAY_DIGITS:
        raise ValueError(f"{digits} Ziffern - die Anzeige zeigt genau {DISPLAY_DIGITS}")
    if core.startswith("."):
        raise ValueError("vor dem Punkt steht an der Anzeige immer eine Ziffer")
    if leading:
        # Abgelesene Zellen: genau so uebernehmen, wie der Bediener sie gesehen hat.
        if leading + len(core) != 7:
            raise ValueError(f"{leading + len(core)} Zellen nach dem Plus - die Anzeige hat genau 7 "
                             f"({DISPLAY_DIGITS} Ziffern und der Punkt)")
        integer = core.split(".")[0]
        if len(integer) > 1 and integer[0] == "0":
            raise ValueError(f"fuehrende Null in Zelle {leading + 1} - die Anzeige zeigt sie als Leerzelle")
        block = body
    else:
        padded = "0" * (DISPLAY_DIGITS - digits) + core
        integer = padded.split(".")[0]
        if "?" in integer and len(integer) > 1 and integer[0] == "0":
            # Ob die Anzeige diese Nullen leer zeigt, haengt von der schwankenden Ziffer ab.
            raise ValueError("? vor dem Punkt neben fuehrenden Nullen ist mehrdeutig - "
                             "Zellen genau wie angezeigt eingeben (Leerzellen als Leerzeichen)")
        mapped = map_suppressed_leading_zeros("+" + padded, blank_cells=True)
        if mapped is None:
            raise ValueError("drei oder mehr fuehrende Nullen: wie die Anzeige sie zeigt, ist nicht gemessen - "
                             "Zellen genau wie angezeigt eingeben (Leerzellen als Leerzeichen)")
        block = mapped[1:]
    comparable = sum(ch != "?" for ch in block)
    if comparable < MIN_COMPARABLE_CELLS:
        raise ValueError(f"nur {comparable} vergleichbare Zellen - hoechstens {7 - MIN_COMPARABLE_CELLS} "
                         "Zellen mit ? markieren")
    return validate_offline_cell_text("+" + block + " ")


def validate_offline_cell_text(text: str) -> str:
    """Validate eight/nine-cell operator input; preserve masked cells."""
    if not isinstance(text, str) or len(text) not in (8, 9) or not text.isascii():
        raise ValueError("offline cell text must be eight or nine ASCII characters")
    text = text.ljust(9)
    if text[8] != " ":
        raise ValueError("the ninth cell must be the measured unit separator")
    if "?" in text[8:]:
        raise ValueError("'?' can only mark numeric cells")
    if _OFFLINE.fullmatch(text.replace("?", " ")) is None:
        raise ValueError("offline cell text contains an unsupported character or format")

    block = text[1:8]
    if block.count(".") != 1:
        raise ValueError("offline numeric block must contain one decimal point")
    return text


_STEP_BLOCK = re.compile(r" *[0-9]+\.[0-9]+", re.ASCII)


def _last_place_units(text: str) -> tuple[int, int] | None:
    """(Punktzelle, Wert in Einheiten der letzten Stelle) eines vollstaendigen Zellentexts.

    Nur ein Text, den die Anzeige so zeigen kann: '+', 7 Zellen mit genau
    6 Ziffern (fuehrende Leerzellen zaehlen als unterdrueckte Nullen), ein
    Punkt, Zelle 8 leer, keine sichtbare fuehrende Null vor einer weiteren
    Ziffer vor dem Punkt. '?' oder sonst Unlesbares ergibt None.
    """
    if not isinstance(text, str) or len(text) != 9 or text[0] != "+" or text[8] != " ":
        return None
    block = text[1:8]
    if _STEP_BLOCK.fullmatch(block) is None:
        return None
    integer = block.lstrip(" ").split(".")[0]
    if len(integer) > 1 and integer[0] == "0":
        return None
    return block.index("."), int(block.replace(" ", "0").replace(".", ""))


def last_place_step(reference: str, read: str) -> int | None:
    """+1 bzw. -1, wenn `read` genau eine Einheit der letzten Stelle ueber bzw.
    unter `reference` liegt, sonst None.

    Beide Texte muessen vollstaendige, eindeutige Zellentexte sein (kein '?')
    und den Punkt in derselben Zelle haben. Uebertraege zaehlen mit
    (' 0.4679' -> ' 0.4680', ' 9.9999' -> '10.0000'); wandert der Punkt
    (' 9.9999' -> '100.000'), ist es kein Schritt der letzten Stelle.
    """
    left, right = _last_place_units(reference), _last_place_units(read)
    if left is None or right is None or left[0] != right[0]:
        return None
    step = right[1] - left[1]
    return step if step in (1, -1) else None
