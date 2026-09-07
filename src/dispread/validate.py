"""Freigabelogik: Konzept.md §7 in pruefbaren Regeln.

Die Freigabe bekommt ausschliesslich das Leseergebnis, das Profil und die
eigene Historie. Insbesondere bekommt sie **nicht** den Referenzwert der
Kalibriermaschine - Konzept.md §7 verbietet, ihn zur Korrektur des DUT-Werts
zu benutzen, und diese Signatur macht es strukturell unmoeglich.

Ebenso verankert: ein alter Wert laeuft nie unmarkiert weiter. Bleibt eine
Freigabe aus, wechselt der Status nach `stale_after_ns` zwingend auf STALE, und
ein STALE-Datensatz darf keinen Zahlenwert mitfuehren (erzwungen im
ValueRecord-Konstruktor).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dispread.ocr import ReadResult
from dispread.records import ValueStatus


@dataclass(frozen=True, slots=True)
class GateDecision:
    """Freigabeentscheidung samt Begruendung."""

    status: ValueStatus
    #: Aggregierte Qualitaetskennzahl. Ausdruecklich KEINE
    #: Fehlerwahrscheinlichkeit (Konzept.md §7).
    confidence: float
    #: Maschinenlesbare Gruende. Bei status != VALID nie leer.
    reject_reasons: tuple[str, ...]
    frames_confirmed: int
    #: Zeitspanne der Mehrbildbestaetigung. Konzept.md §7 verlangt, diese
    #: Verzoegerung zu dokumentieren und im Zeitbezug zu beruecksichtigen.
    confirmation_span_ns: int
    gate_version: str = "1"


@dataclass
class GateConfig:
    """Schwellen der Freigabe.

    Alle Werte sind Vorabdefaults, keine validierten Grenzen. Konzept.md §7
    verlangt, die Freigabeschwellen an realen, auch unbekannten Gerätetypen zu
    validieren - das steht als OQ-14 offen und ist Aufgabe von Phase P3.
    """

    #: Mindestabstand der knappsten Segmentmessung zur Schwelle (0..1).
    min_margin: float = 0.15
    #: Mindestkontrast zwischen aktiven und inaktiven Segmenten (0..1).
    min_contrast: float = 0.10
    #: Anzahl uebereinstimmender Frames vor der Freigabe. 1 = keine
    #: Mehrbildbestaetigung, also keine zusaetzliche Verzoegerung.
    confirm_frames: int = 1
    #: Ohne Freigabe innerhalb dieser Zeit gilt der letzte Wert als veraltet.
    stale_after_ns: int = 500_000_000
    #: Betriebszustaende, die einen Zahlenwert ausschliessen.
    blocking_flags: frozenset[str] = field(default_factory=lambda: frozenset({"overflow", "menu", "hold", "glare"}))
    #: Erwartete Einheit aus dem bestaetigten Profil.
    expected_unit: str | None = None


@dataclass
class _Candidate:
    value: float
    count: int
    first_ns: int


class ReleaseGate:
    """Zustandsbehaftete Freigabe mit Mehrbildbestaetigung und Veralterung."""

    def __init__(self, config: GateConfig | None = None) -> None:
        self.config = config or GateConfig()
        self._candidate: _Candidate | None = None
        self._last_valid_ns: int | None = None

    def reset(self) -> None:
        self._candidate = None
        self._last_valid_ns = None

    def evaluate(self, read: ReadResult, capture_ns: int) -> GateDecision:
        cfg = self.config
        reasons: list[str] = []

        contrast = float(read.diagnostics.get("contrast", 0.0))
        min_margin = float(read.diagnostics.get("min_margin", 0.0))

        # --- Betriebszustaende: kein Zahlenwert, aber auch kein Defekt -------
        blocking = read.status_flags & cfg.blocking_flags
        if blocking:
            reasons.extend(f"state:{flag}" for flag in sorted(blocking))

        # --- Lesbarkeit ------------------------------------------------------
        if contrast < cfg.min_contrast:
            reasons.append("low_contrast")
        unreadable_cells = int(read.diagnostics.get("unreadable_cells", 0))
        if unreadable_cells:
            reasons.append(f"unreadable_cells:{unreadable_cells}")
        if min_margin < cfg.min_margin:
            reasons.append("low_segment_margin")

        # --- Vorzeichen: eigenstaendiges Kriterium ---------------------------
        # Ein nicht auswertbarer Vorzeichenbereich fuehrt zur Ablehnung, nicht
        # zu "positiv". Konzept.md §7 nennt fehlendes Minuszeichen kritisch.
        if not read.sign_region_readable:
            reasons.append("sign_region_unreadable")

        # --- Dezimalpunkt: eigenstaendiges Kriterium -------------------------
        if not read.decimal_point_detected:
            reasons.append("decimal_point_unknown")

        # --- Einheit: bestaetigt oder abgelehnt ------------------------------
        if cfg.expected_unit is not None and read.unit_text != cfg.expected_unit:
            reasons.append(f"unit_mismatch:{read.unit_text}")

        if read.value is None and "no_value" not in reasons:
            reasons.append("no_value")

        if reasons:
            self._candidate = None
            status = self._stale_or_unreadable(capture_ns, blocking)
            return GateDecision(
                status=status,
                confidence=0.0,
                reject_reasons=tuple(reasons),
                frames_confirmed=0,
                confirmation_span_ns=0,
            )

        # --- Mehrbildbestaetigung -------------------------------------------
        assert read.value is not None
        if self._candidate is not None and self._candidate.value == read.value:
            self._candidate.count += 1
        else:
            # Ein anderer Wert setzt die Bestaetigung zurueck. Der Wert selbst
            # wird NICHT geglaettet oder gemittelt - echte Spruenge duerfen
            # nach Konzept.md §7 nicht verschwinden.
            self._candidate = _Candidate(value=read.value, count=1, first_ns=capture_ns)

        span = capture_ns - self._candidate.first_ns
        if self._candidate.count < cfg.confirm_frames:
            return GateDecision(
                status=ValueStatus.TRANSITION,
                confidence=0.0,
                reject_reasons=("awaiting_confirmation",),
                frames_confirmed=self._candidate.count,
                confirmation_span_ns=span,
            )

        self._last_valid_ns = capture_ns
        return GateDecision(
            status=ValueStatus.VALID,
            confidence=min(1.0, min_margin),
            reject_reasons=(),
            frames_confirmed=self._candidate.count,
            confirmation_span_ns=span,
        )

    def _stale_or_unreadable(self, capture_ns: int, blocking: frozenset[str]) -> ValueStatus:
        """UNREADABLE, solange die Ablehnung frisch ist - danach STALE.

        Der Unterschied ist wichtig: UNREADABLE heisst "gerade nicht lesbar",
        STALE heisst "es gibt keinen aktuellen Wert mehr". In beiden Faellen
        laeuft der alte Wert nicht unmarkiert weiter.
        """
        if blocking:
            return ValueStatus.UNREADABLE
        if self._last_valid_ns is None:
            return ValueStatus.UNREADABLE
        if capture_ns - self._last_valid_ns > self.config.stale_after_ns:
            return ValueStatus.STALE
        return ValueStatus.UNREADABLE
