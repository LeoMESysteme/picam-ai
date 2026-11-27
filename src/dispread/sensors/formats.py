"""Zellrollen und Zahlenformat aus einem bestaetigten Anzeigebeispiel."""

from __future__ import annotations

import re

from . import get_sensor
from .definitions import CHAR_NUMBER_FORMAT_RULE, AnchorDefinition, DisplayDefinition, FormatDefinition, RolesDefinition

_NUMBER = r'[0-9]+(?:\.[0-9]+)?'


def derive_display(example: str, unit: str, sign_chars: str | None = None, digits: int | None = None) -> DisplayDefinition:
    """Leitet das 16-Zellen-Layout ab, einschliesslich fuehrender Leerzellen."""
    if (not isinstance(example, str) or not 1 <= len(example) <= 16
            or any(not ch.isprintable() or (ch.isspace() and ch != ' ') for ch in example)):
        raise ValueError('Anzeigebeispiel braucht bis zu 16 druckbare Zellen')
    if (not isinstance(unit, str) or not unit or unit != unit.strip()
            or any(not ch.isprintable() or (ch.isspace() and ch != ' ') for ch in unit)):
        raise ValueError('Einheit muss ohne aeussere Leerzeichen angegeben werden')

    match = re.fullmatch(rf'(?P<sign>[+-]?)(?P<number> *{_NUMBER})(?P<separator> +){re.escape(unit)} *', example)
    if match is None:
        raise ValueError('Erwartet: optionales Vorzeichen in Zelle 0, Zahl mit Punkt oder Ganzzahl, '
                         'mindestens eine Trennzelle und die angegebene Einheit')
    sign = match['sign']
    allowed = sign if sign_chars is None else sign_chars
    if (not isinstance(allowed, str) or set(allowed) - {'+', '-'} or len(set(allowed)) != len(allowed)
            or bool(allowed) != bool(sign) or (sign and sign not in allowed)):
        raise ValueError('Vorzeichen im Beispiel und erlaubte Vorzeichen (+/-) muessen zusammenpassen')
    number = match['number']
    count = sum(ch in '0123456789' for ch in number)
    if digits is not None and (type(digits) is not int or digits != count):
        raise ValueError(f'Beispiel hat {count} Ziffern, erwartet {digits}')
    capacity = len(number) - ('.' in number)
    limit = capacity if digits is None else digits
    minimum = count if count < limit else None
    start_unit = match.end('separator')
    end_unit = start_unit + len(unit)
    return DisplayDefinition(
        schema=1, family='hd44780_5x8', polarity='dark_on_light', cells=16, rows=1,
        lattice=get_sensor().display.lattice,
        roles=RolesDefinition(tuple(range(len(sign))), tuple(range(*match.span('number'))),
                              tuple(range(*match.span('separator'))), tuple(range(start_unit, end_unit)),
                              tuple(range(end_unit, 16))),
        anchor=AnchorDefinition('+', 0) if sign == '+' and allowed == '+' else None,
        format=FormatDefinition(CHAR_NUMBER_FORMAT_RULE, limit, tuple(allowed), 'leading_spaces',
                                'point' if '.' in number else 'none', minimum),
    )


def required_characters(display: DisplayDefinition) -> set[str]:
    """Einheit und Beschriftungen werden nicht klassifiziert."""
    return set('0123456789 ') | set(display.format.sign_chars) | ({'.'} if display.format.decimal == 'point' else set())


def setup_reference(text: str, definition) -> str:
    """Prueft die Bedienereingabe gegen die festgelegten Zellgrenzen."""
    from dispread.ocr.dotmatrix import parse_char_number

    display = definition.display
    end = display.classified_cells
    if len(text) == end:
        # Die Werkbank kann den klassifizierten Teil senden. Die Einheit
        # wird beim Bestaetigen separat gegen die Paketangabe geprueft.
        cells = text
    else:
        if len(text) > display.cells or text[end:].rstrip(' ') != definition.unit:
            raise ValueError(f'Vollstaendigen Zelltext mit Einheit {definition.unit} eingeben')
        cells = text[:end]
    if parse_char_number(cells, display) is None:
        raise ValueError('Zellentext passt nicht zu Zahl, Vorzeichen oder Trennzellen des aktiven Pakets')
    return cells
