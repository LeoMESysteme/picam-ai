"""JSON-Lines-Audit-Log.

Laeuft immer parallel zur eigentlichen Ausgabe. Begruendung: wenn GSVmulti
uebermittelte Aufnahmezeiten nicht verwendet (Konzept.md §6, Messung M8), ist
dieses Log die einzige Quelle, aus der sich die zeitliche Zuordnung
nachtraeglich rekonstruieren laesst. Es enthaelt jeden Datensatz, auch die
abgelehnten - gerade die abgelehnten, denn sie belegen, dass das System
Unsicherheit erkannt und nicht geraten hat.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from dispread.records import TxReceipt, ValueRecord
from dispread.sink import SinkHealth


class JsonlSink:
    """Schreibt je Datensatz eine JSON-Zeile.

    Rotiert bei `max_bytes`, behaelt `keep` Generationen. Begrenzte Puffer und
    Groessen sind Pflicht - Konzept.md §5 nennt Dauerbetrieb mit begrenzten
    Puffern, und auf diesem Pi sind nur 34 GB frei.
    """

    def __init__(self, path: Path | str, *, max_bytes: int = 64 * 1024 * 1024, keep: int = 5) -> None:
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.keep = keep
        self._fh = None
        self._sent = 0
        self._errors = 0
        self._last_error: str | None = None
        self._tx_seq = 0

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def _rotate_if_needed(self) -> None:
        if self._fh is None or self.max_bytes <= 0:
            return
        if self._fh.tell() < self.max_bytes:
            return
        self._fh.close()
        for i in range(self.keep - 1, 0, -1):
            src = self.path.with_suffix(self.path.suffix + f".{i}")
            if src.exists():
                src.replace(self.path.with_suffix(self.path.suffix + f".{i + 1}"))
        self.path.replace(self.path.with_suffix(self.path.suffix + ".1"))
        self._fh = self.path.open("a", encoding="utf-8")

    def emit(self, record: ValueRecord) -> TxReceipt:
        t0 = time.monotonic_ns()
        self._tx_seq += 1
        if self._fh is None:
            raise RuntimeError("JsonlSink.open() wurde nicht aufgerufen")
        line = json.dumps(record.to_dict(), ensure_ascii=False, separators=(",", ":"))
        try:
            self._fh.write(line + "\n")
            self._fh.flush()
            self._rotate_if_needed()
            self._sent += 1
            error = None
        except OSError as exc:  # Platte voll, Rechte, ...
            self._errors += 1
            self._last_error = str(exc)
            error = exc
        return TxReceipt(
            frame_sequence=record.frame_sequence,
            tx_sequence=self._tx_seq,
            format_id="jsonl",
            wire_bytes=None if error else line.encode("utf-8"),
            t_enqueue_ns=t0,
            t_complete_ns=None if error else time.monotonic_ns(),
        )

    def health(self) -> SinkHealth:
        return SinkHealth(
            open=self._fh is not None,
            sent=self._sent,
            omitted=0,
            errors=self._errors,
            last_error=self._last_error,
        )
