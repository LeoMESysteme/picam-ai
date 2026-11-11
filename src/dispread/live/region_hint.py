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


def empty_region_summary() -> dict:
    """Zusammenfassung ohne Rahmenbereich-Nachfuehrung (z. B. ECC-Altmodus)."""
    return {'window_frames': WINDOW_FRAMES, 'min_frames': MIN_FRAMES, 'min_share': MIN_SHARE,
            'max_rest_median_px': MAX_REST_MEDIAN_PX, 'limit_px': None, 'frames': 0,
            'evaluations': 0, 'regions': [], 'last': None}


def _row(residuals, count):
    if len(residuals) != count:
        return None
    try:
        return np.array([math.nan if value is None else float(value) for value in residuals], dtype=float)
    except (TypeError, ValueError):
        return None


class RegionConsistency:
    """Thread-sicheres Fenster; observe im Leserthread, snapshot im Statusabruf."""

    def __init__(self, centres, *, limit_px: float):
        self._centres = [[float(x), float(y)] for x, y in centres]
        self._limit = float(limit_px)
        self._buffer = np.full((WINDOW_FRAMES, len(self._centres)), math.nan)
        self._lock = Lock()
        self._next = 0
        self._filled = 0
        self._since = 0
        self._frames = 0
        self._evaluations = 0
        self._hint: dict | None = None
        self._history: dict[int, dict] = {}

    def observe(self, residuals) -> None:
        row = _row(residuals, len(self._centres))
        if row is None:
            return
        with self._lock:
            self._buffer[self._next] = row
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
        for index in range(data.shape[1]):
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
                    'last': deepcopy(self._hint)}
