"""Frame und Quellen-Faehigkeiten."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from dispread.records import TimeBaseKind, Timestamp


class Capability(str, Enum):
    """Was eine Bildquelle kann.

    Der einzige Ort, an dem die Pipeline Unterschiede zwischen Quellen bemerken
    darf. So wird "Belichtung fixieren" bei einer synthetischen Quelle zu einem
    No-op mit Warnung statt zu einem Fehler.
    """

    LIVE = "live"
    INFERENCE = "inference"
    SEEK = "seek"
    EXPOSURE_CONTROL = "exposure_control"


@dataclass(frozen=True, slots=True)
class InferenceResult:
    """Ergebnis einer On-Sensor-Inferenz (IMX500), unveraendert durchgereicht."""

    tensors: tuple[np.ndarray, ...]
    #: dnn_runtime und dsp_runtime in Mikrosekunden, aus CnnKpiInfo.
    dnn_runtime_us: int | None = None
    dsp_runtime_us: int | None = None
    network_id: str | None = None


@dataclass(frozen=True, slots=True)
class Frame:
    """Ein Bild samt der Metadaten aus derselben Aufnahme.

    Konzept.md §6 verlangt ausdruecklich, Bild und Metadaten aus derselben
    Aufnahme zu verwenden - deshalb reisen sie hier gemeinsam und werden nicht
    getrennt beschafft.
    """

    frame_sequence: int
    #: BGR (HxWx3) oder Graustufen (HxW).
    image: np.ndarray
    #: Aufnahmezeit. Die Zeitbasis im Timestamp sagt, ob sie belastbar ist.
    capture_timestamp: Timestamp
    source_id: str
    exposure_time_us: int | None = None
    frame_duration_us: int | None = None
    analogue_gain: float | None = None
    #: Kameramtadaten unveraendert. Der rohe Sensorzeitstempel wird nie
    #: ueberschrieben, sondern nur ergaenzt.
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    inference: InferenceResult | None = None
    trigger_sequence: int | None = None

    @property
    def timebase(self) -> TimeBaseKind:
        return self.capture_timestamp.base

    @property
    def is_time_bearing(self) -> bool:
        """Darf aus diesem Frame eine Latenzaussage abgeleitet werden?

        Verhindert den Fehler, Replay- oder Synthetik-Latenzen spaeter als
        reale Latenzen zu berichten.
        """
        return self.capture_timestamp.base.carries_time_information

    @property
    def size(self) -> tuple[int, int]:
        """(Breite, Hoehe)."""
        h, w = self.image.shape[:2]
        return w, h
