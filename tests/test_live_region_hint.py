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


# --- TB 2026-11-11: Vorschlag zur Stilllegung im Lauf ----------------------------------

def _feed_vectors(window, frames, *, bad=(), bad_vector=None, good=0.1, seed=3):
    """Zeilen mit Residuum und Richtung; bad_vector(frame, index) -> (dx, dy) fuer kranke Bereiche."""
    import numpy as np

    rng = np.random.default_rng(seed)
    for frame in range(frames):
        vectors = [list(rng.normal(0, good, 2)) for _ in CENTRES]
        for index in bad:
            vectors[index] = list(bad_vector(frame, index, rng))
        window.observe([float(np.hypot(*v)) for v in vectors], vectors)


def _glint(frame, index, rng):
    # Nicht starr: Betrag 0,9 bis 1,6 px, Richtung je Bild anders.
    import numpy as np

    angle, size = rng.uniform(0, 2*np.pi), rng.uniform(0.9, 1.6)
    return size*np.cos(angle), size*np.sin(angle)


def test_tb_konstanten_der_stilllegung():
    assert rh.DEACTIVATE_MIN_WINDOW == 300 == rh.WINDOW_FRAMES
    assert rh.DEACTIVATE_MIN_SHARE == 0.50 > rh.MIN_SHARE
    assert rh.DEACTIVATE_MAX_REST_MEDIAN_PX == 0.40
    assert rh.COORDINATED_MAX_RATIO == 0.5
    summary = RegionConsistency(CENTRES, limit_px=LIMIT).summary()
    assert summary['deactivated'] == [] and summary['deactivation_refused'] == []
    assert summary['deactivation'] == {'min_window': 300, 'min_share': 0.5, 'max_rest_median_px': 0.4,
                                       'coordinated_max_ratio': 0.5}


def test_tb_einzelner_kranker_bereich_erst_nach_vollem_fenster():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed_vectors(window, 299, bad=(5,), bad_vector=_glint)
    assert window.snapshot() is not None  # Hinweis ja ...
    assert window.deactivation_candidate() is None  # ... Stilllegung erst ab 300 Bildern
    _feed_vectors(window, 1, bad=(5,), bad_vector=_glint, seed=4)
    candidate = window.deactivation_candidate()
    assert candidate['index'] == 5 and candidate['number'] == 6 and candidate['share'] == 1.0
    assert candidate['rest_median_px'] < 0.4 and candidate['coordination_ratio'] > 0.5
    assert candidate['window_frames'] == 300


def test_tb_hinweisschwelle_reicht_nicht_fuer_stilllegung():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    # 40 %: Hinweis, aber keine Stilllegung.
    _feed_vectors(window, 300, bad=(2,), bad_vector=lambda f, i, rng: _glint(f, i, rng) if f % 5 < 2 else (0.1, 0))
    assert [r['index'] for r in window.snapshot()['regions']] == [2]
    assert window.deactivation_candidate() is None


@pytest.mark.parametrize('cluster', [(1, 2), (1, 2, 3), (0, 3, 6, 7)])
@pytest.mark.parametrize('shift', [(0.8, 0.0), (0.0, -1.2), (2.0, 1.0)])
def test_tb_gleichlaeufige_bereiche_nie_vorgeschlagen(cluster, shift):
    """Koordinierte Verschiebung: alle reissen die Grenze, keiner wird vorgeschlagen."""
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed_vectors(window, 600, bad=cluster,
                  bad_vector=lambda f, i, rng: (shift[0] + rng.normal(0, 0.1), shift[1] + rng.normal(0, 0.1)))
    assert {r['index'] for r in window.snapshot()['regions']} == set(cluster)
    assert window.deactivation_candidate() is None


def test_tb_halbe_amplitude_gilt_noch_als_gleichlauf():
    # Ein Partner, der dieselbe Richtung mit halber Amplitude zeigt, blockiert ebenfalls.
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed_vectors(window, 300, bad=(1, 2),
                  bad_vector=lambda f, i, rng: (1.4, 0.0) if i == 1 else (0.75, 0.0))
    assert window.deactivation_candidate() is None


def test_tb_ohne_vektoren_oder_bei_streuendem_rest_kein_vorschlag():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed(window, 300, bad=5, bad_value=1.4)  # nur Betraege: Gleichlauf nicht pruefbar
    assert window.snapshot() is not None and window.deactivation_candidate() is None
    other = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed_vectors(other, 300, bad=(5,), bad_vector=_glint, good=0.5)
    assert other.deactivation_candidate() is None


def test_tb_stilllegung_leert_fenster_und_verschiebt_verlauf():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed_vectors(window, 300, bad=(5,), bad_vector=_glint)
    candidate = window.deactivation_candidate()
    window.note_deactivated({'frame_sequence': 1234, **candidate})
    assert window.snapshot() is None and window.deactivation_candidate() is None
    summary = window.summary()
    # Kein "bitte entfernen" mehr fuer die naechste Einrichtung; Verlauf steht im Ereignis.
    assert summary['regions'] == []
    (event,) = summary['deactivated']
    assert event['index'] == 5 and event['frame_sequence'] == 1234
    assert event['hint_history']['number'] == 6
    assert window.deactivated() == summary['deactivated']
    # Der stillgelegte Bereich liefert keine Residuen mehr; erst ein neues volles Fenster zaehlt.
    _feed_vectors(window, 299, bad=(2,), bad_vector=_glint)
    assert window.deactivation_candidate() is None
    _feed_vectors(window, 1, bad=(2,), bad_vector=_glint)
    assert window.deactivation_candidate()['index'] == 2


def test_tb_verweigerung_einmal_je_bereich_und_grund():
    window = RegionConsistency(CENTRES, limit_px=LIMIT)
    _feed_vectors(window, 300, bad=(5,), bad_vector=_glint)
    window.note_refused(5, 'reserve_verletzt', 10)
    assert window.deactivation_candidate() is None
    window.note_refused(5, 'reserve_verletzt', 40)
    window.note_refused(5, 'schutzprobe_verletzt', 70, detail={'worst_error_px': 3.5})
    assert window.summary()['deactivation_refused'] == [
        {'index': 5, 'number': 6, 'reason': 'reserve_verletzt', 'frame_sequence': 10, 'detail': None},
        {'index': 5, 'number': 6, 'reason': 'schutzprobe_verletzt', 'frame_sequence': 70,
         'detail': {'worst_error_px': 3.5}}]
