"""Bedienhinweis "Rahmenbereich dauerhaft unstimmig", reine Diagnose (TC 2026-11-11).

Liest ausschliesslich die Erstfit-Residuen, die ``FrameTracker`` je Bild in
``last_regions`` ablegt (``res1``: euklidischer Abstand des gefundenen
Bereichs zum starren Erstfit in Rohpixeln, ``None`` ohne Treffer oder ohne
Fit). Es gibt keinen Rueckweg in den Messpfad: Freigabe, Schwellen, RANSAC,
Akzeptanzentscheidung und ValueRecord-Felder bleiben unberuehrt. Der Hinweis
sagt nur, welcher Bereich wiederholt Werte kostet, und dass Werte geschuetzt
bleiben.

Warum der Erstfit: er laeuft fuer jedes Bild gleich (starr, ohne
Grobschaetzung). Der Zweitfit laeuft nur nach einer Ablehnung; ihn
mitzuzaehlen wuerde die Stichprobe vom Ergebnis abhaengig machen. Die
Zweitfit-Residuen stehen weiter je Bild in diagnose/images.jsonl.

Regel je Bereich ueber die letzten ``WINDOW_FRAMES`` Bilder:

* Grenze ist ``FrameTrackingConfig.max_inlier_residual_px`` (0,65 px) des
  laufenden Trackers, nicht dupliziert. "Reisst" heisst ``res1 > Grenze``,
  genau wie die Laufzeitpruefung ablehnt. Ein RANSAC-Ausreisser liegt ueber
  der Toleranz 1,5 px und damit auch ueber der Grenze; er zaehlt mit.
* Auffaellig, wenn der Bereich in mindestens ``MIN_SHARE`` seiner
  Bilder mit Residuum reisst UND der Median aller uebrigen Bereiche im
  selben Fenster unter ``MAX_REST_MEDIAN_PX`` liegt. Die zweite Bedingung
  trennt einen einzelnen nicht starren Bereich von echter Bewegung,
  Massstabsdrift oder Unschaerfe, die alle Bereiche zugleich treffen.
* Erst ab ``MIN_FRAMES`` Bildern mit Residuum fuer diesen Bereich.

Begruendung der Zahlen (Lauf live-20261111T103604Z, Diagnosebericht TC):
300 Bilder sind bei 30 fps etwa 10 s, so lang wie das Ursachenfenster der
Werkbank. 150 Bilder (5 s) vermeiden Hinweise aus kurzen Stoerungen wie
einer Hand vor dem Rahmen. Erstfit-Residuen der 222 Diagnosebilder: der
Glanzbereich R5 (0-basiert, in der Werkbank Bereich 6) reisst die Grenze in
90 % seiner Bilder (Median 1,31 px), der schwache Fasenbereich R4
(Bereich 5) in 24 % (Median 0,41 px), alle uebrigen in hoechstens 4 %
(Median 0,10 bis 0,32 px). 30 % trennen damit den eindeutig kranken
Bereich mit Abstand vom Rest und melden den Grenzfall R4 noch nicht.
0,40 px liegt ueber dem Median gesunder Bereiche (gesamt 0,18 px):
streut der Rest im Median staerker, ist die Ursache nicht ein einzelner
Bereich, und der Hinweis schweigt. Ausgewertet wird alle
``EVALUATE_EVERY`` Bilder (etwa einmal je Sekunde).

Nummern sind 1-basiert wie in der Werkbank (Lauf-HUD, Nachfuehrungstabelle
und Bereichsbearbeitung der Einrichtung): Nummer = Index im Vorschlag + 1.

TB 2026-11-11, automatische Stilllegung: Dieselbe Fensterauswertung schlaegt
zusaetzlich einen Bereich zur Stilllegung fuer den Rest des Laufs vor, wenn
strengere Bedingungen gelten (benannte Konstanten unten):

* das Fenster ist seit Laufbeginn bzw. seit der letzten Stilllegung voll
  (``DEACTIVATE_MIN_WINDOW`` = 300 Bilder);
* der Bereich reisst in mindestens ``DEACTIVATE_MIN_SHARE`` (50 %) seiner
  Bilder die Grenze, also deutlich ueber der Hinweisschwelle von 30 %;
* die uebrigen Bereiche liegen im Median unter ``DEACTIVATE_MAX_REST_MEDIAN_PX``
  (0,40 px, wie beim Hinweis);
* der Bereich bewegt sich mit keinem anderen Bereich gleichlaeufig: fuer jeden
  anderen Bereich mit mindestens ``MIN_FRAMES`` gemeinsamen Bildern liegt der
  Median des Abstands beider Abweichungsvektoren (gefundene Lage minus
  Erstfit) ueber ``COORDINATED_MAX_RATIO`` (0,5) mal dem groesseren der beiden
  Median-Abweichungsbetraege (symmetrisch: auch ein schwaecher mitlaufender
  Partner gilt als gleichlaeufig). Eine koordinierte Verschiebung mehrerer Bereiche ist so
  nie ein Stilllegungsgrund; laesst sich der Gleichlauf nicht pruefen (keine
  Vektoren, zu wenig gemeinsame Bilder), bleibt der Bereich aktiv.

Begruendung: In den Diagnosebildern der Laeufe 103604Z, 122753Z und 095426Z
liegt das Verhaeltnis fuer die Glanz- und Fasenbereiche bei 0,59 bis 0,75;
eine echte gemeinsame Verschiebung liegt nahe 0. Je Auswertung wird hoechstens
ein Bereich vorgeschlagen; nach einer Stilllegung beginnt das Fenster leer,
weil sich der Fit und damit alle Residuen aendern. Ob stillgelegt wird,
entscheidet ``FrameTracker.disable_refusal`` mit den harten Grenzen
(Hoechstzahl, Mindestzahl, Streuung, Reserve). Stillgelegte Bereiche liefern
keine Residuen mehr und erscheinen weder im Hinweis noch in der Liste fuer die
naechste Einrichtung (``summary()['regions']``), sondern unter ``deactivated``.
"""

from __future__ import annotations

import math
from copy import deepcopy
from threading import Lock

import numpy as np

WINDOW_FRAMES = 300
MIN_FRAMES = 150
MIN_SHARE = 0.30
MAX_REST_MEDIAN_PX = 0.40
EVALUATE_EVERY = 30
# TB 2026-11-11: Stilllegung im Lauf (strenger als der Hinweis, siehe Modultext).
DEACTIVATE_MIN_WINDOW = WINDOW_FRAMES
DEACTIVATE_MIN_SHARE = 0.50
DEACTIVATE_MAX_REST_MEDIAN_PX = MAX_REST_MEDIAN_PX
COORDINATED_MAX_RATIO = 0.5


def empty_region_summary() -> dict:
    """Zusammenfassung ohne Rahmenbereich-Nachfuehrung (z. B. ECC-Altmodus)."""
    return {'window_frames': WINDOW_FRAMES, 'min_frames': MIN_FRAMES, 'min_share': MIN_SHARE,
            'max_rest_median_px': MAX_REST_MEDIAN_PX, 'limit_px': None, 'frames': 0,
            'evaluations': 0, 'regions': [], 'last': None,
            'deactivation': {'min_window': DEACTIVATE_MIN_WINDOW, 'min_share': DEACTIVATE_MIN_SHARE,
                             'max_rest_median_px': DEACTIVATE_MAX_REST_MEDIAN_PX,
                             'coordinated_max_ratio': COORDINATED_MAX_RATIO},
            'deactivated': [], 'deactivation_refused': []}


def _row(residuals, count):
    if len(residuals) != count:
        return None
    try:
        return np.array([math.nan if value is None else float(value) for value in residuals], dtype=float)
    except (TypeError, ValueError):
        return None


def _vector_row(vectors, count):
    # Fehlende oder kaputte Vektoren sind NaN: der Gleichlauf gilt dann als
    # nicht pruefbar, und der Bereich bleibt aktiv.
    row = np.full((count, 2), math.nan)
    if vectors is None or len(vectors) != count:
        return row
    for index, vector in enumerate(vectors):
        try:
            if vector is not None and len(vector) == 2:
                row[index] = [float(vector[0]), float(vector[1])]
        except (TypeError, ValueError):
            continue
    return row


class RegionConsistency:
    """Thread-sicheres Fenster; observe im Leserthread, snapshot im Statusabruf."""

    def __init__(self, centres, *, limit_px: float):
        self._centres = [[float(x), float(y)] for x, y in centres]
        self._limit = float(limit_px)
        self._buffer = np.full((WINDOW_FRAMES, len(self._centres)), math.nan)
        self._vectors = np.full((WINDOW_FRAMES, len(self._centres), 2), math.nan)
        self._lock = Lock()
        self._next = 0
        self._filled = 0
        self._since = 0
        self._frames = 0
        self._evaluations = 0
        self._hint: dict | None = None
        self._history: dict[int, dict] = {}
        self._disabled: set[int] = set()
        self._candidate: dict | None = None
        self._deactivated: list[dict] = []
        self._refused: list[dict] = []

    def observe(self, residuals, vectors=None) -> None:
        row = _row(residuals, len(self._centres))
        if row is None:
            return
        vector_row = _vector_row(vectors, len(self._centres))
        with self._lock:
            self._buffer[self._next] = row
            self._vectors[self._next] = vector_row
            self._next = (self._next + 1) % WINDOW_FRAMES
            self._filled = min(self._filled + 1, WINDOW_FRAMES)
            self._frames += 1
            self._since += 1
            if self._since >= EVALUATE_EVERY:
                self._since = 0
                self._evaluate()

    def _evaluate(self) -> None:
        data = self._buffer[:self._filled]
        finite = np.isfinite(data)
        flagged = []
        rest_median = None
        rest_by_index = {}
        for index in range(data.shape[1]):
            if index in self._disabled:
                continue
            mine = data[finite[:, index], index]
            if len(mine) < MIN_FRAMES:
                continue
            share = float(np.mean(mine > self._limit))
            if share < MIN_SHARE:
                continue
            others = np.delete(data, index, axis=1)
            others = others[np.isfinite(others)]
            if not others.size:
                continue
            median_rest = float(np.median(others))
            if median_rest >= MAX_REST_MEDIAN_PX:
                continue
            rest_median = median_rest if rest_median is None else max(rest_median, median_rest)
            rest_by_index[index] = (median_rest, share)
            flagged.append({'number': index + 1, 'index': index, 'centre': list(self._centres[index]),
                            'share': round(share, 3), 'median_px': round(float(np.median(mine)), 3),
                            'frames': int(len(mine))})
        flagged.sort(key=lambda item: (-item['share'], item['index']))
        self._evaluations += 1
        self._hint = None if not flagged else {
            'regions': flagged, 'rest_median_px': round(rest_median, 3),
            'frames': int(self._filled), 'limit_px': self._limit}
        for item in flagged:
            seen = self._history.setdefault(item['index'], {
                'number': item['number'], 'index': item['index'], 'centre': list(item['centre']),
                'flagged_evaluations': 0, 'max_share': 0.0, 'median_px': None})
            seen['flagged_evaluations'] += 1
            if item['share'] > seen['max_share']:
                seen['max_share'], seen['median_px'] = item['share'], item['median_px']
        self._candidate = self._deactivation_candidate(flagged, rest_by_index)

    def _coordination_ratio(self, index) -> float | None:
        """Kleinstes Verhaeltnis Median|v_i - v_j| / max(Median|v_i|, Median|v_j|) ueber aktive j.

        None, wenn kein anderer Bereich genug gemeinsame Vektoren hat: dann ist
        Gleichlauf nicht ausgeschlossen.
        """
        vectors = self._vectors[:self._filled]
        own = vectors[:, index]
        own_ok = np.isfinite(own).all(axis=1)
        best = None
        for other in range(vectors.shape[1]):
            if other == index or other in self._disabled:
                continue
            both = own_ok & np.isfinite(vectors[:, other]).all(axis=1)
            if int(both.sum()) < MIN_FRAMES:
                continue
            # Symmetrisch: der groessere der beiden Abweichungsbetraege ist der Massstab,
            # sonst koennte der schwaecher mitlaufende Partner einzeln stillgelegt werden.
            size = max(float(np.median(np.linalg.norm(own[both], axis=1))),
                       float(np.median(np.linalg.norm(vectors[both, other], axis=1))))
            apart = float(np.median(np.linalg.norm(own[both] - vectors[both, other], axis=1)))
            ratio = apart / size if size > 0 else 0.0
            best = ratio if best is None else min(best, ratio)
        return best

    def _deactivation_candidate(self, flagged, rest_by_index) -> dict | None:
        if self._filled < DEACTIVATE_MIN_WINDOW:
            return None
        for item in flagged:  # nach Anteil absteigend
            rest, share = rest_by_index[item['index']]  # ungerundet
            if share < DEACTIVATE_MIN_SHARE or rest >= DEACTIVATE_MAX_REST_MEDIAN_PX:
                continue
            ratio = self._coordination_ratio(item['index'])
            if ratio is None or ratio <= COORDINATED_MAX_RATIO:
                continue
            return {**deepcopy(item), 'rest_median_px': round(rest, 3), 'coordination_ratio': round(ratio, 3),
                    'window_frames': int(self._filled)}
        return None

    def deactivation_candidate(self) -> dict | None:
        """Vorschlag der letzten Auswertung (hoechstens einer), unabhaengige Kopie."""
        with self._lock:
            return deepcopy(self._candidate)

    def note_deactivated(self, event: dict) -> None:
        """Stilllegung uebernehmen: Bereich ausklammern, Fenster leeren.

        Der bisherige Hinweisverlauf des Bereichs wandert in das Ereignis; die
        naechste Einrichtung soll ihn nicht mehr zum Entfernen vorschlagen.
        """
        index = event['index']
        with self._lock:
            self._disabled.add(index)
            entry = deepcopy(event)
            entry['hint_history'] = self._history.pop(index, None)
            self._deactivated.append(entry)
            self._buffer[:] = math.nan
            self._vectors[:] = math.nan
            self._next = self._filled = self._since = 0
            self._hint = None
            self._candidate = None

    def note_refused(self, index: int, reason: str, frame_sequence, *, detail=None) -> None:
        """Verweigerte Stilllegung je Bereich und Grund einmal festhalten."""
        with self._lock:
            self._candidate = None
            if any(item['index'] == index and item['reason'] == reason for item in self._refused):
                return
            self._refused.append({'index': index, 'number': index + 1, 'reason': reason,
                                  'frame_sequence': frame_sequence, 'detail': deepcopy(detail)})

    def deactivated(self) -> list[dict]:
        """Stilllegungen dieses Laufs in Reihenfolge, unabhaengige Kopie."""
        with self._lock:
            return deepcopy(self._deactivated)

    def snapshot(self) -> dict | None:
        """Letzte Auswertung oder None; unabhaengige Kopie."""
        with self._lock:
            return deepcopy(self._hint)

    def summary(self) -> dict:
        """Fuer session.json: jeder Bereich, der im Lauf je auffaellig war."""
        with self._lock:
            return {**empty_region_summary(), 'limit_px': self._limit, 'frames': self._frames,
                    'evaluations': self._evaluations,
                    'regions': [deepcopy(self._history[index]) for index in sorted(self._history)],
                    'last': deepcopy(self._hint),
                    'deactivated': deepcopy(self._deactivated), 'deactivation_refused': deepcopy(self._refused)}
