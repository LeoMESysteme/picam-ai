"""Bestaetigte ROI aus dem Geraeteprofil - der Primaerpfad.

Der Bediener positioniert Geraet und Kamera, bestaetigt einmalig den
Ziffernbereich, die Einheit und das Zahlenformat (Konzept.md §4). Dieses Modul
liefert den bestaetigten Bereich danach unveraendert zurueck.

Bewusst schlicht: es findet nichts, es erinnert sich. Damit ist es der einzige
Pfad, der ohne Modell, ohne Training und ohne Datensatz funktioniert - und
damit der Pfad, mit dem die uebrige Kette entwickelt und gemessen werden kann.
"""

from __future__ import annotations

from dispread.detect import DisplayCandidate, Quad
from dispread.frames.types import Frame

LOCATOR_ID = "manual_roi"


def quad_from_box(x: int, y: int, w: int, h: int) -> Quad:
    """Achsparalleles Rechteck als Viereck (oben links beginnend)."""
    return (
        (float(x), float(y)),
        (float(x + w), float(y)),
        (float(x + w), float(y + h)),
        (float(x), float(y + h)),
    )


class ManualRoiLocator:
    """Gibt die bestaetigte ROI zurueck.

    `role_hint` ist Pflicht, damit die Verwechslung von Haupt- und
    Nebenanzeige (Konzept.md §7) nicht implizit bleibt.
    """

    def __init__(self, quad: Quad, *, role_hint: str = "main", confirmed_by: str | None = None) -> None:
        self.quad = quad
        self.role_hint = role_hint
        self.confirmed_by = confirmed_by

    @property
    def locator_id(self) -> str:
        return LOCATOR_ID

    def locate(self, frame: Frame) -> tuple[DisplayCandidate, ...]:
        # Der Frame wird nicht ausgewertet - die ROI ist bestaetigt. Ob sie
        # noch passt, entscheidet der Tracker bzw. die Bildqualitaetspruefung
        # in der Freigabe.
        del frame
        return (
            DisplayCandidate(
                quad=self.quad,
                score=1.0,
                locator_id=LOCATOR_ID,
                role_hint=self.role_hint,
            ),
        )
