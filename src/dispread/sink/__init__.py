"""Ausgabe: JSONL-Audit-Log, serielle Strecke, Telegrammformate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from dispread.records import TxReceipt, ValueRecord

__all__ = ["SinkHealth", "ValueSink"]


@dataclass(frozen=True, slots=True)
class SinkHealth:
    open: bool
    sent: int
    omitted: int
    errors: int
    last_error: str | None = None


@runtime_checkable
class ValueSink(Protocol):
    """Eine Ausgabe.

    `emit` gibt einen TxReceipt zurueck und liefert damit den Beleg fuer das,
    was ueber die Leitung ging - getrennt vom ValueRecord, der belegt, was das
    System erkannt hat.
    """

    def open(self) -> None: ...

    def close(self) -> None: ...

    def emit(self, record: ValueRecord) -> TxReceipt: ...

    def health(self) -> SinkHealth: ...
