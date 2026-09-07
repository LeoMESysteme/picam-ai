"""Geometrie einer 7-Segment-Anzeige.

Das Layout kommt im Betrieb aus dem bestaetigten Geraeteprofil - der Bediener
bestaetigt laut Konzept.md §4 einmalig Anzeige, Einheit und Zahlenformat. Der
Dekoder liest also nicht "irgendwie", sondern gegen ein bekanntes Raster.

Dasselbe Layout benutzt der synthetische Generator zum Zeichnen. Das macht die
synthetischen Saetze zu einer brauchbaren Testvorrichtung - aber ausdruecklich
nicht zu einem Nachweis der Genauigkeit an echten Geraeten (Konzept.md §9:
synthetische Daten ergaenzen, sie ersetzen kein reales Testset).
"""

from __future__ import annotations

from dataclasses import dataclass

#: Segmentreihenfolge in allen Masken dieses Projekts.
#:
#:      aaaa
#:     f    b
#:     f    b
#:      gggg
#:     e    c
#:     e    c
#:      dddd
SEGMENT_NAMES = ("a", "b", "c", "d", "e", "f", "g")

#: Ziffer -> aktive Segmente.
DIGIT_SEGMENTS: dict[str, frozenset[str]] = {
    "0": frozenset("abcdef"),
    "1": frozenset("bc"),
    "2": frozenset("abdeg"),
    "3": frozenset("abcdg"),
    "4": frozenset("bcfg"),
    "5": frozenset("acdfg"),
    "6": frozenset("acdefg"),
    "7": frozenset("abc"),
    "8": frozenset("abcdefg"),
    "9": frozenset("abcdfg"),
}

#: Umkehrung fuer den Dekoder: Segmentmuster -> Ziffer.
SEGMENTS_TO_DIGIT: dict[frozenset[str], str] = {v: k for k, v in DIGIT_SEGMENTS.items()}

#: Relative Abtastpunkte je Segment innerhalb einer Ziffernzelle, als Anteil
#: von (Breite, Hoehe). Der Dekoder misst hier die Helligkeit.
SEGMENT_SAMPLE_POINTS: dict[str, tuple[float, float]] = {
    "a": (0.50, 0.08),
    "b": (0.88, 0.28),
    "c": (0.88, 0.72),
    "d": (0.50, 0.92),
    "e": (0.12, 0.72),
    "f": (0.12, 0.28),
    "g": (0.50, 0.50),
}


@dataclass(frozen=True, slots=True)
class DisplayLayout:
    """Zahlenformat und Raster einer Anzeige.

    `digits` zaehlt nur die Ziffernstellen. Die Vorzeichenstelle ist separat,
    weil sie eigenstaendig geprueft und eigenstaendig abgelehnt werden muss
    (Konzept.md §7: fehlendes Minuszeichen ist ein kritischer Fehler).
    """

    digits: int = 5
    #: Nachkommastellen. None = Dezimalpunkt frei, muss erkannt werden.
    decimals: int | None = 2
    has_sign: bool = True
    unit: str | None = "N"
    #: Breite der Vorzeichenstelle als Anteil einer Ziffernzelle.
    sign_cell_ratio: float = 0.6
    #: Segmentdicke als Anteil der Zellenbreite.
    thickness_ratio: float = 0.16
    #: Rand innerhalb einer Zelle als Anteil der Zellenbreite.
    inset_ratio: float = 0.10

    @property
    def n_cells(self) -> float:
        """Zellenbreiten insgesamt, Vorzeichenstelle anteilig."""
        return self.digits + (self.sign_cell_ratio if self.has_sign else 0.0)

    def cell_boxes(self, width: int, height: int) -> list[tuple[int, int, int, int]]:
        """Ziffernzellen als (x, y, w, h) im entzerrten Ausschnitt.

        Index 0 ist die linke Ziffernstelle. Die Vorzeichenstelle liefert
        `sign_box` separat.
        """
        cell_w = width / self.n_cells
        x0 = cell_w * self.sign_cell_ratio if self.has_sign else 0.0
        boxes = []
        for i in range(self.digits):
            x = x0 + i * cell_w
            boxes.append((int(round(x)), 0, int(round(cell_w)), height))
        return boxes

    def sign_box(self, width: int, height: int) -> tuple[int, int, int, int] | None:
        """Bereich der Vorzeichenstelle, oder None wenn das Layout keine hat."""
        if not self.has_sign:
            return None
        cell_w = width / self.n_cells
        return 0, 0, int(round(cell_w * self.sign_cell_ratio)), height

    def decimal_point_index(self) -> int | None:
        """Nach welcher Ziffernstelle steht der Dezimalpunkt?

        None, wenn das Profil ihn nicht festlegt - dann muss er erkannt werden.
        """
        if self.decimals is None:
            return None
        return self.digits - self.decimals - 1

    def format_value(self, value: float) -> str:
        """Wert so darstellen, wie die Anzeige ihn zeigen wuerde."""
        decimals = self.decimals if self.decimals is not None else 0
        text = f"{abs(value):.{decimals}f}".replace(".", "")
        text = text[-self.digits :].rjust(self.digits, "0")
        return text

    def to_dict(self) -> dict[str, object]:
        return {
            "digits": self.digits,
            "decimals": self.decimals,
            "has_sign": self.has_sign,
            "unit": self.unit,
            "sign_cell_ratio": self.sign_cell_ratio,
            "thickness_ratio": self.thickness_ratio,
            "inset_ratio": self.inset_ratio,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DisplayLayout:
        known = {f for f in cls.__slots__}
        return cls(**{k: v for k, v in data.items() if k in known})  # type: ignore[arg-type]
