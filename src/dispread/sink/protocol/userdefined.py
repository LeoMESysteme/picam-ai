"""Einkanaliger GSVmulti-UserDefined-Prototyp, noch ohne Windows-Abnahme.

Grundlage: docs/GSVMULTI_PROTOCOL.md, ME v2.6 S. 118–121. ASCII und CRLF
sind feste Formatregeln. FormatterCapabilities besitzt keine Felder für
Präfix, Kodierung oder Zeilenende; diese werden hier nicht hinzuerfunden.
Die Policy omit_record beschreibt nur die lokale Auslassung, keine belegte
Ungültigwirkung in GSVmulti (OQ-06). Kein natives GSV-Geräteprotokoll.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from dispread.records import InvalidValuePolicy, ValueRecord, ValueStatus
from dispread.sink.protocol import FormatterCapabilities

_NUMBER = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?", flags=re.ASCII)
_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class UserDefinedFormatter:
    """Unveränderter Anzeigetext ohne ASCII-Leerzellen, ohne Rundung.

    Konsistenz bedeutet Decimal(text) == Decimal(str(record.value)). Dadurch
    werden zusätzliche Dezimalziffern nicht durch float(text) verschluckt.
    Der Rückgabevertrag hat kein Grundfeld: Ablehnungsgründe gehen ins Log,
    SerialSink hält die Auslassung separat im TxReceipt fest.
    """

    prefix: str = "%"
    invalid_policy: ClassVar[InvalidValuePolicy] = InvalidValuePolicy.OMIT_RECORD

    def __post_init__(self) -> None:
        if (len(self.prefix) != 1 or not "!" <= self.prefix <= "~"
                or self.prefix in "+-.0123456789"):
            raise ValueError("Präfix muss ein druckbares ASCII-Zeichen ohne Ziffer, +, -, Punkt oder Leerzeichen sein")

    @property
    def capabilities(self) -> FormatterCapabilities:
        return FormatterCapabilities(
            format_id="gsvmulti_userdefined_v0",
            carries_capture_timestamp=False,
            timestamp_resolution_ns=None,
            supported_invalid_policies=frozenset({InvalidValuePolicy.OMIT_RECORD}),
            requires_device_commands=False,
            channel_count=1,
            provisional=True,
        )

    def format(self, record: ValueRecord) -> bytes | None:
        if record.status is not ValueStatus.VALID:
            _LOG.debug("UserDefined frame=%s ausgelassen: status=%s", record.frame_sequence, record.status)
            return None
        text = (record.raw_text or "").replace(" ", "")
        if _NUMBER.fullmatch(text) is None:
            _LOG.warning("UserDefined frame=%s ausgelassen: ungültiger Dezimaltext", record.frame_sequence)
            return None
        if (record.value is None or not math.isfinite(record.value)
                or Decimal(text) != Decimal(str(record.value))):
            _LOG.warning("UserDefined frame=%s ausgelassen: Text/Wert inkonsistent", record.frame_sequence)
            return None
        return f"{self.prefix}{text}\r\n".encode("ascii")
