"""Bedienhinweis "Rahmenbereich dauerhaft unstimmig" (TC 2026-11-11), reine Diagnose."""

import math

import pytest

from dispread.live import region_hint as rh
from dispread.live.frame_tracking import FrameTrackingConfig
from dispread.live.region_hint import RegionConsistency, empty_region_summary

CENTRES = [(100.0 + 40 * i, 200.0) for i in range(8)]
LIMIT = FrameTrackingConfig().max_inlier_residual_px


def _feed(window, frames, bad=None, *, bad_value=1.2, every=1, good=0.2, missing=()):
    for frame in range(frames):
        row = [good] * len(CENTRES)
        if bad is not None and frame % every == 0:
            row[bad] = bad_value
        for index in missing:
            row[index] = None
        window.observe(row)


def test_konstanten_und_grenze_aus_der_pruefung():
    # Gleiche Grenze wie die Laufzeitpruefung, nicht dupliziert.
    assert LIMIT == 0.65
    assert rh.WINDOW_FRAMES == 300 and rh.MIN_FRAMES == 150
    assert rh.MIN_SHARE == 0.30 and rh.MAX_REST_MEDIAN_PX == 0.40
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    assert window.snapshot() is None
    assert window.summary() == {**empty_region_summary(), 'limit_px': LIMIT}


def test_dauerhaft_unstimmiger_bereich_wird_1_basiert_gemeldet():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed(window, 300, bad=5, every=2)  # jedes zweite Bild: 50 %
    hint = window.snapshot()
    assert hint['regions'] == [{'number': 6, 'index': 5, 'centre': [300.0, 200.0],
                                'share': 0.5, 'median_px': pytest.approx(0.7), 'frames': 300}]
    assert hint['rest_median_px'] == pytest.approx(0.2)
    assert hint['frames'] == 300 and hint['limit_px'] == LIMIT
    # Unabhaengige Kopie: Aenderungen am Ergebnis wirken nicht zurueck.
    hint['regions'][0]['number'] = 99
    assert window.snapshot()['regions'][0]['number'] == 6


def test_ausreisser_zaehlt_wie_gerissene_grenze():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed(window, 300, bad=2, bad_value=2.4)
    assert window.snapshot()['regions'][0]['number'] == 3


@pytest.mark.parametrize('every,expected', [(3, True), (4, False)])
def test_anteilsgrenze_30_prozent(every, expected):
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed(window, 300, bad=1, every=every)  # 34 % bzw. 25 %
    assert (window.snapshot() is not None) is expected


def test_genau_an_der_grenze_reisst_nicht():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed(window, 300, bad=1, bad_value=LIMIT)
    assert window.snapshot() is None


def test_kein_hinweis_wenn_der_rest_ebenfalls_streut():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed(window, 300, bad=4, good=0.45)
    assert window.snapshot() is None


def test_kein_hinweis_vor_genug_bildern_und_ohne_belege():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed(window, 149, bad=0)
    assert window.snapshot() is None
    other = RegionConsistency(CENTRES, limit_px=LIMIT)
    # Ohne Treffer kein Residuum: nicht als unstimmig zaehlen.
    _feed(other, 300, bad=0, bad_value=None)
    assert other.snapshot() is None


def test_fenster_vergisst_und_zusammenfassung_bleibt():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed(window, 300, bad=5)
    assert window.snapshot() is not None
    _feed(window, 300)
    assert window.snapshot() is None
    summary = window.summary()
    assert summary['evaluations'] == 20
    assert summary['last'] is None
    (region,) = summary['regions']
    assert region['number'] == 6 and region['centre'] == [300.0, 200.0]
    assert region['max_share'] == 1.0 and region['median_px'] == pytest.approx(1.2)
    assert 1 <= region['flagged_evaluations'] < summary['evaluations']


def test_mehrere_bereiche_nach_anteil_sortiert():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    for frame in range(300):
        row = [0.2] * len(CENTRES)
        row[4] = 0.9 if frame % 2 else 0.3
        row[5] = 1.4
        window.observe(row)
    assert [r['number'] for r in window.snapshot()['regions']] == [6, 5]


def test_ungueltige_zeilen_werden_ignoriert():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    window.observe([0.1])  # falsche Laenge
    window.observe([math.nan] * len(CENTRES))
    window.observe(['x'] * len(CENTRES))
    assert window.summary()['frames'] == 1  # nur die NaN-Zeile ist formal gueltig
    assert window.snapshot() is None
