"""Die Verarbeitungskette aus Konzept.md §3.

    Frame -> Lokalisierung -> Entzerrung -> Werterkennung -> Freigabe
          -> ValueRecord -> Ausgabe(n)

Die Instrumentierung laeuft von Anfang an mit: je Frame werden die Marken aller
Stufen in CLOCK_MONOTONIC erfasst und im PipelineTrace mitgefuehrt. Das ist der
Teil, der sich nachtraeglich nicht ohne Umbau einziehen laesst (Messung M4).

Was diese Kette bewusst NICHT kennt: den Referenzwert der Kalibriermaschine.
Konzept.md §7 verbietet, ihn zur Korrektur des DUT-Werts zu benutzen.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from dispread import __version__
from dispread.detect import DisplayLocator
from dispread.frames import Frame, FrameSource
from dispread.layout import DisplayLayout
from dispread.ocr import ValueReader
from dispread.records import (
    PipelineTrace,
    Timestamp,
    TimestampSemantics,
    TxReceipt,
    ValueRecord,
    ValueStatus,
)
from dispread.rectify import rectify
from dispread.sink import ValueSink
from dispread.validate import ReleaseGate


@dataclass
class PipelineConfig:
    profile_id: str
    layout: DisplayLayout
    target_size: tuple[int, int] = (400, 160)
    #: Nur jeden n-ten Frame neu lokalisieren. Konzept.md §3: Lokalisierung und
    #: OCR muessen nicht mit derselben Frequenz arbeiten.
    locate_every: int = 30
    #: CLAHE vor der Werterkennung anwenden (`rectify.enhance`). Seit
    #: 2026-09-10 Default `True`: an 28 bestehenden Sicherheitstests, der
    #: synthetischen Stoerungsreihe (Rauschen/Unschaerfe/Glanz/Perspektive)
    #: und allen realen Annotationen validiert, keine Zeile regressiert
    #: (Glanz sogar verbessert: 2/40 -> 1/40 stille Fehlablesungen) - siehe
    #: `docs/open-questions.md` OQ-23 und `docs/VALIDATION.md`. Weiterhin ein
    #: expliziter Parameter, kein stillschweigend fester Codepfad: `False`
    #: setzen, falls ein Aufrufer die alten Rohwerte braucht.
    apply_enhance: bool = True


@dataclass
class PipelineStats:
    frames: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    receipts: list[TxReceipt] = field(default_factory=list)

    def note(self, status: ValueStatus) -> None:
        self.by_status[status.value] = self.by_status.get(status.value, 0) + 1


class Pipeline:
    def __init__(
        self,
        source: FrameSource,
        locator: DisplayLocator,
        reader: ValueReader,
        gate: ReleaseGate,
        sinks: list[ValueSink],
        config: PipelineConfig,
    ) -> None:
        self.source = source
        self.locator = locator
        self.reader = reader
        self.gate = gate
        self.sinks = sinks
        self.config = config
        self.stats = PipelineStats()
        self._candidate = None
        self._frames_since_locate = 0

    def component_versions(self) -> dict[str, str]:
        return {
            "dispread": __version__,
            "locator": self.locator.locator_id,
            "reader": f"{self.reader.backend_id}",
            "gate": "1",
            "source": self.source.source_id,
        }

    def process(self, frame: Frame) -> ValueRecord:
        """Einen Frame verarbeiten und den Datensatz erzeugen."""
        t_dequeue = time.monotonic_ns()

        # --- Lokalisierung (nicht in jedem Frame) ---------------------------
        if self._candidate is None or self._frames_since_locate >= self.config.locate_every:
            candidates = self.locator.locate(frame)
            self._candidate = candidates[0] if candidates else None
            self._frames_since_locate = 0
        else:
            self._frames_since_locate += 1
        t_locate = time.monotonic_ns()

        if self._candidate is None:
            # Anzeige nicht gefunden. Der Wert wird ungueltig - der letzte
            # bekannte laeuft nicht weiter (Konzept.md §4).
            return self._build_record(
                frame,
                value=None,
                unit=None,
                raw_text=None,
                status=ValueStatus.UNREADABLE,
                confidence=0.0,
                reasons=("display_not_located",),
                frames_confirmed=0,
                confirmation_span_ns=0,
                trace=PipelineTrace(t_dequeue_ns=t_dequeue, t_locate_done_ns=t_locate),
            )

        # --- Entzerrung ------------------------------------------------------
        crop = rectify(
            frame.image,
            self._candidate.quad,
            target_size=self.config.target_size,
            apply_enhance=self.config.apply_enhance,
        )
        t_rectify = time.monotonic_ns()

        # --- Werterkennung ---------------------------------------------------
        read = self.reader.read(crop.image, self.config.layout)
        t_read = time.monotonic_ns()

        # --- Freigabe --------------------------------------------------------
        decision = self.gate.evaluate(read, frame.capture_timestamp.value_ns)
        t_gate = time.monotonic_ns()

        # Ein nicht freigegebener Wert wird nicht mitgeschickt. Das ist die
        # Invariante aus Konzept.md §7 - der ValueRecord-Konstruktor erzwingt
        # sie zusaetzlich fuer STALE und UNREADABLE.
        value = read.value if decision.status is ValueStatus.VALID else None
        unit = read.unit_text if decision.status is ValueStatus.VALID else None

        return self._build_record(
            frame,
            value=value,
            unit=unit,
            raw_text=read.raw_text,
            status=decision.status,
            confidence=decision.confidence,
            reasons=decision.reject_reasons,
            frames_confirmed=decision.frames_confirmed,
            confirmation_span_ns=decision.confirmation_span_ns,
            trace=PipelineTrace(
                t_dequeue_ns=t_dequeue,
                t_locate_done_ns=t_locate,
                t_rectify_done_ns=t_rectify,
                t_read_done_ns=t_read,
                t_gate_done_ns=t_gate,
            ),
        )

    def _build_record(
        self,
        frame: Frame,
        *,
        value: float | None,
        unit: str | None,
        raw_text: str | None,
        status: ValueStatus,
        confidence: float,
        reasons: tuple[str, ...],
        frames_confirmed: int,
        confirmation_span_ns: int,
        trace: PipelineTrace,
    ) -> ValueRecord:
        built = time.monotonic_ns()
        trace = PipelineTrace(
            t_dequeue_ns=trace.t_dequeue_ns,
            t_locate_done_ns=trace.t_locate_done_ns,
            t_rectify_done_ns=trace.t_rectify_done_ns,
            t_read_done_ns=trace.t_read_done_ns,
            t_gate_done_ns=trace.t_gate_done_ns,
            t_record_built_ns=built,
        )
        return ValueRecord(
            frame_sequence=frame.frame_sequence,
            # Der Aufnahmezeitstempel wird unveraendert uebernommen, inklusive
            # seiner Zeitbasis. Er wird nie durch eine Verarbeitungszeit
            # ersetzt (Konzept.md §6).
            capture_timestamp=frame.capture_timestamp,
            value=value,
            unit=unit,
            status=status,
            confidence=confidence,
            profile_id=self.config.profile_id,
            trigger_sequence=frame.trigger_sequence,
            result_timestamp=Timestamp(
                value_ns=built,
                base=frame.capture_timestamp.base,
                semantics=TimestampSemantics.HOST_DEQUEUE,
            ),
            raw_text=raw_text,
            reject_reasons=reasons,
            frames_confirmed=frames_confirmed,
            confirmation_span_ns=confirmation_span_ns,
            trace=trace,
            component_versions=self.component_versions(),
        )

    def run(self, limit: int | None = None) -> Iterator[ValueRecord]:
        """Kette laufen lassen und Datensaetze ausgeben."""
        self.source.open()
        for sink in self.sinks:
            sink.open()
        try:
            for frame in self.source.frames():
                record = self.process(frame)
                self.stats.frames += 1
                self.stats.note(record.status)
                for sink in self.sinks:
                    self.stats.receipts.append(sink.emit(record))
                yield record
                if limit is not None and self.stats.frames >= limit:
                    break
        finally:
            for sink in self.sinks:
                sink.close()
            self.source.close()
