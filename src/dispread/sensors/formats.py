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


def _cells_from_value(text: str, definition) -> str | None:
    """Getippten Wert ("0.1489", "+0,1489", "0.1489 mV/V") in die Zellen des Pakets setzen.

    Nur eindeutige Faelle: Vorzeichen fehlt -> das einzige erlaubte Vorzeichen;
    die Zahl steht rechtsbuendig im Zahlenblock (fuehrende Leerzellen wie an
    der Anzeige). Alles andere bleibt None und wird abgelehnt, nicht geraten.
    """
    display = definition.display
    value = text.strip().replace(',', '.')
    unit = definition.unit
    if unit and value.lower().endswith(unit.lower()):
        value = value[: -len(unit)].rstrip()
    match = re.fullmatch(rf'(?P<sign>[+-]?) *(?P<number>{_NUMBER})', value)
    if match is None:
        return None
    sign, number = match['sign'], match['number']
    roles = display.roles
    if roles.sign:
        allowed = display.format.sign_chars
        if not sign:
            if len(allowed) != 1:
                return None
            sign = allowed[0]
        if len(roles.sign) != 1:
            return None
    elif sign:
        return None
    width = len(roles.number)
    if len(number) > width:
        return None
    cells = [' '] * display.classified_cells
    if roles.sign:
        cells[roles.sign[0]] = sign
    for cell, ch in zip(roles.number, number.rjust(width), strict=True):
        cells[cell] = ch
    return ''.join(cells)


def setup_reference(text: str, definition) -> str:
    """Prueft die Bedienereingabe gegen die festgelegten Zellgrenzen.

    Angenommen werden der Zellentext wie angezeigt ("+ 0.1489 mV/V") und ein
    getippter Wert ("0.1489", "+0,1489"), der eindeutig in die Zellen passt.
    """
    from dispread.ocr.dotmatrix import parse_char_number

    display = definition.display
    end = display.classified_cells
    typed = _cells_from_value(text, definition)
    if typed is not None and parse_char_number(typed, display) is not None:
        exact = text[:end] if len(text) >= end else None
        if exact is None or parse_char_number(exact, display) is None:
            return typed
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
