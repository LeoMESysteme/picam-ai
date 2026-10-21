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
    #: Uebergang statt unlesbar (Konzept.md §7, Anzeigewechsel): hoechstens so
    #: viele unlesbare Zellen, alle lesbaren gleich dem letzten freigegebenen
    #: Zellentext, und dieser hoechstens `transition_window_ns` alt.
    transition_max_cells: int = 3
    transition_window_ns: int = 1_000_000_000
    #: Betriebszustaende, die einen Zahlenwert ausschliessen.
    blocking_flags: frozenset[str] = field(
        default_factory=lambda: frozenset({"overflow", "menu", "hold", "glare", "tracking_lost"})
    )
    #: Erwartete Einheit aus dem bestaetigten Profil.
    expected_unit: str | None = None


_READER_OWN_THRESHOLDS = frozenset({"dotmatrix"})
_KNOWN_BACKENDS = frozenset({"sevenseg", "tesseract_cli"}) | _READER_OWN_THRESHOLDS


def default_gate_config(backend_id: str, **overrides: object) -> GateConfig:
    """Freigabeschwellen je Leser.

    `min_margin`/`min_contrast` sind auf die 7-Segment-Kennzahlen geeicht. Der
    Dot-Matrix-Leser wendet seine eingefrorenen Schwellen (templates.json,
    Formel thresholds_v1) selbst an und lehnt ab - hier doppelt zu schwellen,
    wuerde eine zweite, ungemessene Grenze einfuehren.

    Fuer `backend_id="dotmatrix"` stammt `GateDecision.confidence`
    (`min(1.0, min_margin)` in `ReleaseGate.evaluate`) aus dem `min_margin`
    der Diagnostics, das der Dot-Matrix-Leser in Abstandseinheiten der
    Vorlagen liefert (Templates-Skala, siehe `dotmatrix_templates.py`) - NICHT
    aus der 0..1-Skala des 7-Segment-Lesers. Der Wert ist wie bei sevenseg
    keine Fehlerwahrscheinlichkeit (Konzept.md §7,
    `declares_confidence_calibrated` bleibt `False`).
    """
    if backend_id not in _KNOWN_BACKENDS:
        raise ValueError(f"unbekannter Leser {backend_id!r}")
    if backend_id in _READER_OWN_THRESHOLDS:
        overrides = {"min_margin": 0.0, "min_contrast": 0.0, **overrides}
    return GateConfig(**overrides)


#: Ablehnungsgruende, die bei einem Ziffernwechsel entstehen. Alles andere
#: (Kontrast, Betriebszustand, Einheit, Nachfuehrung) ist nie ein Uebergang.
_TRANSITION_REASONS = frozenset({
    "low_segment_margin", "decimal_point_unknown", "sign_region_unreadable", "no_value",
})


def _cell_texts(read: ReadResult) -> tuple[str, ...] | None:
    cells = read.diagnostics.get("cells")
    if not isinstance(cells, list) or not cells:
        return None
    texts = [c.get("text") if isinstance(c, dict) else None for c in cells]
    if not all(isinstance(t, str) for t in texts):
        return None
    return tuple(texts)


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
        #: Zellentext der letzten Freigabe (nur Leser mit Zelldiagnosen).
        self._last_valid_cells: tuple[str, ...] | None = None

    def reset(self) -> None:
        self._candidate = None
        self._last_valid_ns = None
        self._last_valid_cells = None

    def interrupt(self) -> None:
        """Bestaetigung unterbrechen; letzte Freigabe fuer STALE behalten.

        Nach einer Unterbrechung (z. B. Nachfuehrung verloren) ist ein
        Uebergang nicht mehr belegbar - die Zellen der letzten Freigabe
        verfallen."""
        self._candidate = None
        self._last_valid_cells = None

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
            if status is ValueStatus.UNREADABLE and self._is_transition(read, reasons, capture_ns):
                # Kein Wert, nur eine ehrlichere Kennzeichnung: die Anzeige
                # wechselt gerade (Mischziffern), sie ist nicht verdeckt.
                status = ValueStatus.TRANSITION
                reasons.insert(0, "anzeige_wechselt")
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
        self._last_valid_cells = _cell_texts(read)
        return GateDecision(
            status=ValueStatus.VALID,
            confidence=min(1.0, min_margin),
            reject_reasons=(),
            frames_confirmed=self._candidate.count,
            confirmation_span_ns=span,
        )

    def _is_transition(self, read: ReadResult, reasons: list[str], capture_ns: int) -> bool:
        cfg = self.config
        last = self._last_valid_cells
        if last is None or self._last_valid_ns is None:
            return False
        if capture_ns - self._last_valid_ns > cfg.transition_window_ns:
            return False
        if not all(r.startswith("unreadable_cells:") or r in _TRANSITION_REASONS for r in reasons):
            return False
        cells = read.diagnostics.get("cells")
        if not isinstance(cells, list) or len(cells) != len(last):
            return False
        texts = [c.get("text") if isinstance(c, dict) else None for c in cells]
        unreadable = sum(t is None for t in texts)
        if not 1 <= unreadable <= cfg.transition_max_cells:
            return False
        return all(t is None or t == old for t, old in zip(texts, last, strict=True))

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
