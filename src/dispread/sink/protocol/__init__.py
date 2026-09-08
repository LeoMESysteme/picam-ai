"""Telegrammformate - die Naht, an der das GSVmulti-Format eingesetzt wird.

Das konkrete Telegramm, das die eingesetzte GSVmulti-Version akzeptiert, ist
unbekannt (OQ-07: nicht lokal verfuegbar, me-systeme.de blockt automatische
Abrufe mit HTTP 403, muss intern von einem Menschen beschafft werden).

Deshalb ist das Format hier eine austauschbare Komponente und nicht fest in
die Pipeline verdrahtet. Konzept.md §8 nennt CSV-Dateiimport, ASCII-Streaming
und die Emulation eines GSV-Geraets als drei verschiedene Schnittstellenfaelle -
alle drei sind hinter dieser Schnittstelle abbildbar.

**Kein Erfinden von Protokollen.** Der ASCII-CSV-Formatter unten ist ein
ausdruecklich als provisorisch gekennzeichneter Platzhalter zum Testen der
Kette, keine Vermutung darueber, was GSVmulti akzeptiert.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from dispread.records import InvalidValuePolicy, ValueRecord

__all__ = ["FormatterCapabilities", "TelegramFormatter"]


@dataclass(frozen=True, slots=True)
class FormatterCapabilities:
    """Was ein Format kann - explizit, nicht implizit."""

    format_id: str
    #: Traegt das Telegramm den Aufnahmezeitstempel?
    #:
    #: Das ist die Kernfrage aus Konzept.md §6: wenn GSVmulti uebermittelte
    #: Aufnahmezeiten nicht verwendet, beseitigt ein interner Pi-Zeitstempel
    #: die zeitliche Verschiebung dort nicht. Messung M8 in docs/TIMING.md
    #: klaert es; bis dahin ist der Wert eine Behauptung des Formats, nicht
    #: eine Aussage ueber GSVmulti.
    carries_capture_timestamp: bool
    timestamp_resolution_ns: int | None
    supported_invalid_policies: frozenset[InvalidValuePolicy]
    requires_device_commands: bool = False
    channel_count: int = 1
    #: True, solange das Format nicht gegen eine echte Spezifikation geprueft
    #: wurde. Wandert in jedes Runartefakt, damit kein Messergebnis
    #: versehentlich als protokollkonform gilt.
    provisional: bool = True


@runtime_checkable
class TelegramFormatter(Protocol):
    """Bildet einen ValueRecord auf Bytes ab."""

    @property
    def capabilities(self) -> FormatterCapabilities: ...

    def format(self, record: ValueRecord) -> bytes | None:
        """Telegramm erzeugen, oder None wenn der Datensatz entfallen soll."""
        ...
