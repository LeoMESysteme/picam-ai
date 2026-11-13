"""GSVmulti UserDefined: vier Kanaele, Fehlwert explizit, OQ-43 provisional."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import TYPE_CHECKING

from dispread.records import InvalidValuePolicy
from dispread.sink.protocol import FormatterCapabilities

if TYPE_CHECKING:
    from dispread.live.tick import Tick

_NUMBER = re.compile(r'[+-]?[0-9]+(?:\.[0-9]+)?', flags=re.ASCII)
INVALID_TEXT = '99999999.0'


def checked_value_text(text: str | None) -> str:
    """Nur dezimaler Anzeigetext; auch numerische Fehlwert-Aliase sperren."""
    compact = (text or '').replace(' ', '')
    if _NUMBER.fullmatch(compact) is None or Decimal(compact) == Decimal(INVALID_TEXT):
        raise ValueError('Ungültiger oder reservierter Anzeigetext')
    return compact


class TickFormatter:
    """Vierkanal-Takt. Ungültiger Takt: ``gültig = 0`` markiert, Kanal 1 hält den letzten
    gültigen Wert dieses Laufs (Entscheidung Leonhard 2026-11-13: GSVmulti-Anzeige blieb
    sonst bei 20-24 % Lesefehlern nicht ablesbar). Vor dem ersten gültigen Wert gibt es
    nichts zu halten, dann steht der Fehlwert ``99999999.0``. Ausgewertet wird nur mit
    Kanal 2; ein gehaltener Wert ist nie eine Messung (GSVMULTI_PROTOCOL.md, Ausnahme).
    """
    invalid_policy = InvalidValuePolicy.MARK_RECORD

    def __init__(self):
        self.held_text: str | None = None   # nur fuer ``format`` (SerialSink, ein Formatter je Lauf)

    @property
    def capabilities(self) -> FormatterCapabilities:
        return FormatterCapabilities(
            format_id='gsvmulti_userdefined_4ch_v1', carries_capture_timestamp=True,
            timestamp_resolution_ns=1000, supported_invalid_policies=frozenset({self.invalid_policy}),
            channel_count=4, provisional=True,
        )

    def format_tick(self, tick: Tick, held_text: str | None = None) -> bytes:
        """Rein: ``held_text`` ist der letzte gültige Wert vor diesem Takt (oder None)."""
        if tick.valid:
            text = checked_value_text(tick.value_text)
        else:
            text = checked_value_text(held_text) if held_text is not None else INVALID_TEXT
        # Ganzzahlig auf Mikrosekunden runden: keine float-Rundung bei Unix-ns.
        micros = (tick.time_unix_ns + 500) // 1000
        seconds, fraction = divmod(micros, 1_000_000)
        return f'%{text};{int(tick.valid)};{tick.seq};{seconds}.{fraction:06d}\r\n'.encode('ascii')

    def format(self, tick: Tick) -> bytes:
        """SerialSink-Vertrag; der Adapter bekommt einen Takt, keinen ValueRecord. Hält Kanal 1."""
        payload = self.format_tick(tick, self.held_text)
        if tick.valid:
            self.held_text = checked_value_text(tick.value_text)
        return payload
