"""Der interne Datensatz aus Konzept.md §8 und die Zeitstempel-Semantik aus §6.

Dies ist der stabile Vertrag zwischen den Verarbeitungsstufen. Alle Datenklassen
sind frozen: ein einmal erzeugter ValueRecord ist Beweismittel dafuer, was das
System erkannt hat, und wird nachtraeglich von niemandem veraendert - vom
Ausgabeadapter am allerwenigsten.

Bilddaten reisen ausschliesslich im Frame (siehe frames/types.py), nie hier.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

SCHEMA_VERSION = 1


class TimeBaseKind(str, Enum):
    """Herkunft und damit Belastbarkeit eines Aufnahmezeitstempels.

    Pflichtfeld in jedem Frame und jedem ValueRecord. Es wird nie geschoent:
    eine synthetische Quelle darf keine Sensorqualitaet behaupten. Damit ist im
    Datenstrom immer erkennbar, ob ein Zeitstempel eine Zeitaussage traegt -
    Konzept.md §6 strukturell durchgesetzt statt nur dokumentarisch.
    """

    #: libcamera SensorTimestamp. Auf diesem Pi 5 in der CLOCK_BOOTTIME-Domaene
    #: (gemessen 2026-09-07, siehe docs/TIMING.md).
    SENSOR_BOOTTIME = "sensor_boottime"
    #: Aus einer Aufnahmesession zurueckgelesener, originaler SensorTimestamp.
    #: Traegt die Zeitaussage der Aufnahme, aber nicht die des Abspielzeitpunkts.
    REPLAY_RECORDED = "replay_recorded"
    #: Generiert. Traegt KEINE Zeitaussage.
    SYNTHETIC = "synthetic"
    #: Aus der Dateizeit abgeleitet. Traegt praktisch keine Zeitaussage.
    FILE_MTIME = "file_mtime"

    @property
    def carries_time_information(self) -> bool:
        """Darf aus diesem Zeitstempel eine Latenz- oder Zeitaussage werden?"""
        return self in (TimeBaseKind.SENSOR_BOOTTIME, TimeBaseKind.REPLAY_RECORDED)


class TimestampSemantics(str, Enum):
    """Worauf sich ein Zeitstempel physikalisch bezieht.

    Platzhalter fuer Messung M2 (docs/TIMING.md). Vor der Messung steht hier
    UNKNOWN, danach der belegte Wert. Ohne dieses Feld muesste die halbe
    Pipeline angefasst werden, sobald die Semantik geklaert ist.
    """

    UNKNOWN = "unknown"
    EXPOSURE_START = "exposure_start"
    EXPOSURE_MID = "exposure_mid"
    READOUT_END = "readout_end"
    HOST_DEQUEUE = "host_dequeue"


class ValueStatus(str, Enum):
    """Zustandslogik aus Konzept.md §7.

    TRANSITION und UNREADABLE sind ausdruecklich keine Fehler des Systems,
    sondern Aussagen ueber die Anzeige. STALE bedeutet: es gibt keinen
    aktuellen Wert - der letzte bekannte darf nicht als aktueller gelten.
    """

    VALID = "valid"
    TRANSITION = "transition"
    UNREADABLE = "unreadable"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class Timestamp:
    """Zeitpunkt mit dokumentierter Zeitbasis, Bedeutung und Unsicherheit.

    Konzept.md §6 verlangt, Bedeutung und Genauigkeit getrennt zu fuehren.
    `uncertainty_ns` ist None, solange sie nicht gemessen wurde - nicht 0.
    Eine unbekannte Unsicherheit als 0 auszugeben waere eine Falschaussage.
    """

    value_ns: int
    base: TimeBaseKind
    semantics: TimestampSemantics = TimestampSemantics.UNKNOWN
    uncertainty_ns: int | None = None

    @classmethod
    def now_monotonic(cls) -> Timestamp:
        """Jetzt, in der monotonen Domaene - fuer Verarbeitungsmarken."""
        return cls(
            value_ns=time.monotonic_ns(),
            base=TimeBaseKind.SENSOR_BOOTTIME,
            semantics=TimestampSemantics.HOST_DEQUEUE,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "value_ns": self.value_ns,
            "base": self.base.value,
            "semantics": self.semantics.value,
            "uncertainty_ns": self.uncertainty_ns,
        }


@dataclass(frozen=True, slots=True)
class PipelineTrace:
    """Verarbeitungsmarken je Frame, alle in CLOCK_MONOTONIC.

    Ab Tag 1 mitgefuehrt, weil sich diese Instrumentierung nachtraeglich nicht
    ohne Umbau einziehen laesst (Messung M4 in docs/TIMING.md). Die Umrechnung
    nach UTC passiert ausschliesslich in timebase.py, nie hier.
    """

    t_dequeue_ns: int
    t_locate_done_ns: int | None = None
    t_rectify_done_ns: int | None = None
    t_read_done_ns: int | None = None
    t_gate_done_ns: int | None = None
    t_record_built_ns: int | None = None
    queue_depth: int = 0
    #: Verworfene Frames werden gezaehlt, nicht stillschweigend ignoriert.
    dropped_frames: int = 0

    def stage_durations_us(self) -> dict[str, float]:
        """Dauer je Stufe in Mikrosekunden, soweit die Marken gesetzt sind."""
        marks = [
            ("locate", self.t_dequeue_ns, self.t_locate_done_ns),
            ("rectify", self.t_locate_done_ns, self.t_rectify_done_ns),
            ("read", self.t_rectify_done_ns, self.t_read_done_ns),
            ("gate", self.t_read_done_ns, self.t_gate_done_ns),
            ("build", self.t_gate_done_ns, self.t_record_built_ns),
        ]
        out: dict[str, float] = {}
        for name, start, end in marks:
            if start is not None and end is not None:
                out[name] = (end - start) / 1000.0
        if self.t_record_built_ns is not None:
            out["total"] = (self.t_record_built_ns - self.t_dequeue_ns) / 1000.0
        return out

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ValueRecord:
    """Der interne Datensatz aus Konzept.md §8, plus Nachvollziehbarkeit.

    Die neun Pflichtfelder des Konzepts stehen zuerst. Die uebrigen Felder sind
    eine bewusste Erweiterung: ohne sie ist im Nachhinein nicht rekonstruierbar,
    warum ein Wert freigegeben oder abgelehnt wurde.

    Erzeuger und Schreibrechte (siehe docs/project_history.md):

    ==========================  =========================  ====================
    Feld                        Erzeuger                   darf aendern
    ==========================  =========================  ====================
    frame_sequence              FrameSource                niemand
    capture_timestamp           FrameSource + TimeBase     niemand, nie Adapter
    value, unit, raw_text       ValueReader                niemand
    status, confidence, ...     ReleaseGate                niemand
    profile_id                  Session / ProfileStore     niemand
    trigger_sequence            FrameSource / Trigger      niemand
    result_timestamp            Pipeline beim Abschluss    niemand
    ==========================  =========================  ====================

    Adapterzustand (Kanal, Sendezeit, Telegrammtext, Retries) gehoert
    ausdruecklich NICHT hierher, sondern in TxReceipt. Der Datensatz belegt,
    was das System erkannt hat; der Receipt, was ueber die Leitung ging.
    Vermischt sind beide als Nachweis unbrauchbar.
    """

    # --- Konzept.md §8, Pflichtfelder ---------------------------------------
    frame_sequence: int
    capture_timestamp: Timestamp
    value: float | None
    unit: str | None
    status: ValueStatus
    confidence: float
    profile_id: str
    trigger_sequence: int | None
    result_timestamp: Timestamp | None

    # --- Nachvollziehbarkeit ------------------------------------------------
    schema_version: int = SCHEMA_VERSION
    #: Exakt wie gelesen, inklusive Vorzeichen und Dezimalzeichen.
    raw_text: str | None = None
    #: Maschinenlesbare Ablehnungsgruende. Bei status != VALID nie leer.
    reject_reasons: tuple[str, ...] = ()
    #: Anzahl Frames der Mehrbildbestaetigung ...
    frames_confirmed: int = 1
    #: ... und die Zeitspanne, die sie gekostet hat. Konzept.md §7 verlangt,
    #: diese Verzoegerung zu dokumentieren und im Zeitbezug zu beruecksichtigen.
    confirmation_span_ns: int = 0
    trace: PipelineTrace | None = None
    component_versions: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Invariante: ein nicht freigegebener Wert muss einen Grund nennen.
        if self.status is not ValueStatus.VALID and not self.reject_reasons:
            raise ValueError(f"status={self.status.value} ohne reject_reasons - Grund ist Pflicht")
        # Invariante aus Konzept.md §7: ein veralteter oder unlesbarer Zustand
        # darf keinen Zahlenwert als aktuellen gueltigen Wert mitfuehren.
        if self.status in (ValueStatus.STALE, ValueStatus.UNREADABLE) and self.value is not None:
            raise ValueError(
                f"status={self.status.value} mit value={self.value!r}: ein veralteter oder "
                "unlesbarer Wert darf nicht als Zahlenwert weiterlaufen (Konzept.md §7)"
            )

    def to_dict(self) -> dict[str, Any]:
        """Flache, JSON-serialisierbare Abbildung fuer das JSONL-Log."""
        return {
            "schema_version": self.schema_version,
            "frame_sequence": self.frame_sequence,
            "capture_timestamp": self.capture_timestamp.to_dict(),
            "value": self.value,
            "unit": self.unit,
            "status": self.status.value,
            "confidence": self.confidence,
            "profile_id": self.profile_id,
            "trigger_sequence": self.trigger_sequence,
            "result_timestamp": self.result_timestamp.to_dict() if self.result_timestamp else None,
            "raw_text": self.raw_text,
            "reject_reasons": list(self.reject_reasons),
            "frames_confirmed": self.frames_confirmed,
            "confirmation_span_ns": self.confirmation_span_ns,
            "trace": self.trace.to_dict() if self.trace else None,
            "component_versions": dict(self.component_versions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ValueRecord:
        """Umkehrung von to_dict - muss verlustfrei sein (Testkriterium P0)."""

        def _ts(raw: dict[str, Any] | None) -> Timestamp | None:
            if raw is None:
                return None
            return Timestamp(
                value_ns=raw["value_ns"],
                base=TimeBaseKind(raw["base"]),
                semantics=TimestampSemantics(raw["semantics"]),
                uncertainty_ns=raw["uncertainty_ns"],
            )

        trace_raw = data.get("trace")
        capture = _ts(data["capture_timestamp"])
        assert capture is not None  # capture_timestamp ist Pflichtfeld
        return cls(
            frame_sequence=data["frame_sequence"],
            capture_timestamp=capture,
            value=data["value"],
            unit=data["unit"],
            status=ValueStatus(data["status"]),
            confidence=data["confidence"],
            profile_id=data["profile_id"],
            trigger_sequence=data["trigger_sequence"],
            result_timestamp=_ts(data.get("result_timestamp")),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            raw_text=data.get("raw_text"),
            reject_reasons=tuple(data.get("reject_reasons", ())),
            frames_confirmed=data.get("frames_confirmed", 1),
            confirmation_span_ns=data.get("confirmation_span_ns", 0),
            trace=PipelineTrace(**trace_raw) if trace_raw else None,
            component_versions=dict(data.get("component_versions", {})),
        )


class InvalidValuePolicy(str, Enum):
    """Wie ungueltige Werte nach aussen abgebildet werden.

    Konzept.md §11 Frage 6 ist offen (OQ-06): welche Variante GSVmulti und die
    Kalibrierauswertung tatsaechlich brauchen, ist unbekannt. Deshalb ist das
    ein austauschbarer Adapterparameter und keine harte Entscheidung im Code.
    """

    #: Datensatz gar nicht senden.
    OMIT_RECORD = "omit_record"
    #: NaN als Wert senden.
    SEND_NAN = "send_nan"
    #: Wert weglassen, aber ein Statusfeld mitsenden.
    STATUS_FLAG = "status_flag"


@dataclass(frozen=True, slots=True)
class TxReceipt:
    """Was tatsaechlich ueber die Leitung ging - adapterlokal.

    Absichtlich getrennt vom ValueRecord: hier steht der Sendezeitpunkt, dort
    der Aufnahmezeitpunkt. Wer beides in einem Objekt fuehrt, kann spaeter
    nicht mehr belegen, welche Zeit welche war.
    """

    frame_sequence: int
    tx_sequence: int
    format_id: str
    #: Genau die Bytes auf der Leitung. Beweismittel bei Formatstreitigkeiten.
    wire_bytes: bytes | None
    t_enqueue_ns: int
    t_complete_ns: int | None
    channel: int | None = None
    retry_count: int = 0
    invalid_policy: InvalidValuePolicy | None = None
    omitted: bool = False

    @property
    def duration_us(self) -> float | None:
        if self.t_complete_ns is None:
            return None
        return (self.t_complete_ns - self.t_enqueue_ns) / 1000.0
