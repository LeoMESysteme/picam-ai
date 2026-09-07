"""Anzeige lokalisieren.

Primaerpfad ist die vom Bediener bestaetigte ROI (`manual_roi`), nicht die
IMX500-Detektion. Begruendung (docs/project_history.md): die 23 mitgelieferten
.rpk sind COCO-/ImageNet-Modelle - gemessen liefern sie Labels wie "person"
und "tv" -, eigene Modelle sind nur off-Pi konvertierbar, und Konzept.md §10
Ph. 2 nennt den manuellen Ausschnitt selbst als Rueckfalloption. Diese
Umkehrung der Prioritaet ist die einzige, die die Werterkennung nicht
blockiert.

`locate` und `update` sind getrennt, weil Lokalisierung und OCR laut
Konzept.md §3 nicht mit derselben Frequenz arbeiten muessen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from dispread.frames.types import Frame

__all__ = ["DisplayCandidate", "DisplayLocator", "TrackResult"]

Quad = tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]


@dataclass(frozen=True, slots=True)
class DisplayCandidate:
    """Eine gefundene Anzeige, als Viereck im Bildkoordinatensystem."""

    #: Eckpunkte, im Uhrzeigersinn ab oben links.
    quad: Quad
    score: float
    locator_id: str
    locator_version: str = "1"
    #: "main" oder "secondary". Konzept.md §7 nennt die Verwechslung von
    #: Haupt- und Nebenanzeige als kritischen Fehler - die Rolle muss also
    #: benennbar sein und darf nicht implizit bleiben.
    role_hint: str | None = None


@dataclass(frozen=True, slots=True)
class TrackResult:
    candidate: DisplayCandidate | None
    #: True, wenn die Anzeige verloren ging. Dann muss der Wert ungueltig
    #: werden (Konzept.md §4) - nicht der letzte bekannte weiterlaufen.
    lost: bool
    relocalize_needed: bool = False


@runtime_checkable
class DisplayLocator(Protocol):
    def locate(self, frame: Frame) -> tuple[DisplayCandidate, ...]: ...

    @property
    def locator_id(self) -> str: ...
