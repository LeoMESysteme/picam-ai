"""Provisorisches ASCII-CSV-Format zum Testen der Ausgabekette.

WARNUNG: Dieses Format ist frei erfunden. Es ist NICHT das GSVmulti-Telegramm
und darf nicht als solches ausgegeben oder in Messberichten als
protokollkonform bezeichnet werden. `capabilities.provisional` ist True und
wandert in jedes Runartefakt.

Zweck: die Kette Wert -> Telegramm -> serielle Leitung -> Gegenstelle laesst
sich damit vollstaendig testen, bevor OQ-07 geklaert ist. Alle Achsen, die
Konzept.md §8 als klaerungsbeduerftig nennt - Trennzeichen, Dezimalzeichen,
Zeilenende, Einheit, Kanal, Behandlung ungueltiger Werte - sind konfigurierbar,
damit das echte Format spaeter nur eine andere Parametrierung oder ein neuer
Formatter ist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from dispread.records import InvalidValuePolicy, ValueRecord, ValueStatus
from dispread.sink.protocol import FormatterCapabilities


@dataclass
class AsciiCsvFormatter:
    """Konfigurierbares ASCII-CSV.

    Die Standardwerte sind Vermutungen ueber verbreitete Konventionen, keine
    Spezifikation. Insbesondere `decimal_separator="."` ist bewusst gesetzt:
    Konzept.md §8 nennt das Dezimaltrennzeichen ausdruecklich als zu klaerenden
    Punkt, und ein Komma waere in einem komma-separierten Format doppelt
    belegt.
    """

    field_separator: str = ";"
    decimal_separator: str = "."
    line_ending: str = "\r\n"
    decimals: int = 3
    include_unit: bool = True
    include_status: bool = True
    include_capture_timestamp: bool = True
    channel: int = 1
    invalid_policy: InvalidValuePolicy = InvalidValuePolicy.STATUS_FLAG
    encoding: str = "ascii"

    @property
    def capabilities(self) -> FormatterCapabilities:
        return FormatterCapabilities(
            format_id="ascii_csv/provisional",
            carries_capture_timestamp=self.include_capture_timestamp,
            timestamp_resolution_ns=1,
            supported_invalid_policies=frozenset(
                {
                    InvalidValuePolicy.OMIT_RECORD,
                    InvalidValuePolicy.SEND_NAN,
                    InvalidValuePolicy.STATUS_FLAG,
                }
            ),
            channel_count=1,
            provisional=True,
        )

    def format(self, record: ValueRecord) -> bytes | None:
        is_valid = record.status is ValueStatus.VALID

        if not is_valid and self.invalid_policy is InvalidValuePolicy.OMIT_RECORD:
            # Datensatz entfaellt. Der Aufrufer haelt das im TxReceipt fest,
            # damit die Luecke nachvollziehbar bleibt und nicht als
            # Uebertragungsfehler missverstanden wird.
            return None

        if record.value is None:
            value_text = "NaN" if self.invalid_policy is InvalidValuePolicy.SEND_NAN else ""
        elif math.isnan(record.value):
            value_text = "NaN"
        else:
            value_text = f"{record.value:.{self.decimals}f}"
            if self.decimal_separator != ".":
                value_text = value_text.replace(".", self.decimal_separator)

        fields: list[str] = [str(self.channel), str(record.frame_sequence), value_text]
        if self.include_unit:
            fields.append(record.unit or "")
        if self.include_status:
            fields.append(record.status.value)
        if self.include_capture_timestamp:
            # Zeitbasis mitgeben, nicht nur die Zahl. Ein Zeitstempel ohne
            # Zeitbasis ist nach Konzept.md §6 keine verwertbare Angabe.
            fields.append(str(record.capture_timestamp.value_ns))
            fields.append(record.capture_timestamp.base.value)

        line = self.field_separator.join(fields) + self.line_ending
        return line.encode(self.encoding, errors="replace")
