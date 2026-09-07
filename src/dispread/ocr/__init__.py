"""Wertleser: austauschbare Backends hinter einer Schnittstelle.

Entscheidend fuer die Austauschbarkeit ist, dass ReadResult Vorzeichen,
Dezimalpunkt und Einheit als eigene, separat pruefbare Felder fuehrt und nicht
nur einen Zahlenwert. Konzept.md §7 nennt fehlendes Minuszeichen, uebersehenen
Dezimalpunkt und falsche Einheit als eigenstaendige kritische Fehler - sie
muessen also eigenstaendig ablehnbar sein.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np

from dispread.layout import DisplayLayout

__all__ = ["GlyphEvidence", "ReadResult", "ValueReader"]


@dataclass(frozen=True, slots=True)
class GlyphEvidence:
    """Belege fuer eine einzelne gelesene Stelle.

    `segments` traegt beim 7-Segment-Backend die tatsaechlich gemessene
    Segmentbelegung. Das ist erklaerbare Evidenz - genau das, was die
    Freigabelogik nach §7 braucht, und was eine generische OCR nicht liefert.
    """

    text: str
    confidence: float
    segments: tuple[bool, ...] | None = None
    #: Andere Ziffern, die zu derselben Messung passen wuerden.
    ambiguous_with: tuple[str, ...] = ()
    #: Abstand der Segmentmessungen zur Entscheidungsschwelle (0..1).
    #: Klein = knapp entschieden.
    margin: float = 0.0


@dataclass(frozen=True, slots=True)
class ReadResult:
    """Was der Leser gesehen hat - noch ohne Freigabeentscheidung."""

    #: Exakt wie gelesen, inklusive Vorzeichen und Dezimalzeichen.
    raw_text: str
    value: float | None
    #: Wurde ein Minuszeichen gesehen?
    sign_detected: bool
    #: War der Vorzeichenbereich ueberhaupt auswertbar? Getrennt von
    #: sign_detected, weil ein nicht sichtbarer Vorzeichenbereich zur
    #: Ablehnung fuehren muss und nicht zu "positiv" (Konzept.md §7).
    sign_region_readable: bool
    decimal_point_detected: bool
    decimal_point_index: int | None
    unit_text: str | None
    #: Erkannte Betriebszustaende: "overflow", "menu", "hold", ...
    status_flags: frozenset[str]
    glyphs: tuple[GlyphEvidence, ...]
    backend_id: str
    backend_version: str
    diagnostics: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ValueReader(Protocol):
    """Ein Wertleser.

    Bekommt ausschliesslich den Bildausschnitt und das bestaetigte Profil -
    insbesondere NICHT den Referenzwert der Kalibriermaschine. Konzept.md §7
    verbietet, den Referenzwert zur Korrektur des DUT-Werts zu benutzen; diese
    Signatur macht es strukturell unmoeglich.
    """

    def read(self, crop: np.ndarray, layout: DisplayLayout) -> ReadResult: ...

    @property
    def backend_id(self) -> str: ...

    @property
    def declares_confidence_calibrated(self) -> bool:
        """Ist die Konfidenz gegen echte Fehlerraten kalibriert?

        Default False. Konzept.md §7: Konfidenzwerte eines Modells sind keine
        nachgewiesenen Fehlerwahrscheinlichkeiten. Nur True, wenn eine
        Kalibriermessung in docs/VALIDATION.md existiert.
        """
        ...
