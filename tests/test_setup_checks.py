"""Setup checks use only synthetic images and existing read-only stills."""

import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from dispread.setup_checks import check_setup

ROOT = Path('/home/me-systeme/picam-ai/var/diagnostics')
QUAD = [[0, 0], [400, 0], [400, 160], [0, 160]]


def fit(**updates):
    data = dict(quad=QUAD, n_dots=200, n_assigned=190,
                rms_cols=0.1, rms_rows=0.15, cells=tuple(range(16)),
                row_bias=(0.0,) * 7, cell_bias=(0.0,) * 16)
    data.update(updates)
    return SimpleNamespace(**data)


def display():
    image = np.full((160, 400, 3), 100, np.uint8)
    for cell in (0, 1, 3, 4, 5, 6, 7, 9, 10, 11, 12):
        for row in range(7):
            for column in range(5):
                if (row + column + cell) % 3 != 0:
                    x = round(cell * 25 + (column + .5) * 25 / 6)
                    y = round(160 / 9 + (row + .5) * (160 * 7 / 9) / 7)
                    cv2.circle(image, (x, y), 2, (45, 45, 45), -1)
    return image


def test_reports_both_contrast_measures_and_serializes():
    result = check_setup(display(), fit())
    report = result.to_dict()
    assert report['overall'] in ('OK', 'WARNUNG', 'FEHLER')
    assert report['checks']['kontrast']['metrics']['punktkontrast'] > 15
    assert report['checks']['kontrast']['metrics']['leser_kontrast'] > 0.1
    assert report['checks']['stabilitaet']['status'] is None


def test_low_point_contrast_fails():
    image = display()
    image[image == 45] = 92
    result = check_setup(image, fit())
    assert result.checks['kontrast'].status == 'FEHLER'
    assert result.overall == 'FEHLER'


def test_edge_in_blank_cell_is_reported_but_soft_gradient_is_clear():
    image = display()
    image[:, 207:225] = np.clip(image[:, 207:225].astype(int) - 28, 0, 255)
    edged = check_setup(image, fit()).checks['kanten']
    assert edged.status in ('WARNUNG', 'FEHLER')
    assert 8 in edged.cells
    soft = display()
    soft = np.clip(soft.astype(float) + np.linspace(0, -10, 400)[None, :, None], 0, 255).astype('uint8')
    assert check_setup(soft, fit()).checks['kanten'].status == 'OK'


def test_saturated_glare_fails():
    image = display()
    image[35:95, 35:155] = 255
    check = check_setup(image, fit()).checks['glanz']
    assert check.status == 'FEHLER'
    assert check.metrics['saturated_fraction'] > .02


def test_low_resolution_fails():
    result = check_setup(display(), fit(quad=[[0, 0], [240, 0], [240, 160], [0, 160]]))
    assert result.checks['aufloesung'].status == 'FEHLER'


def test_bad_lattice_fails_and_bias_warns():
    image = display()
    assert check_setup(image, fit(rms_cols=.26)).checks['raster'].status == 'FEHLER'
    assert check_setup(image, fit(n_assigned=150)).checks['raster'].status == 'FEHLER'
    assert check_setup(image, fit(row_bias=(.09,) + (0,) * 6)).checks['raster'].status == 'WARNUNG'


def test_stability_requires_elapsed_time_and_warns_if_unreliable():
    image = display()
    short = check_setup(image, fit(), stability_image_bgr=image, stability_elapsed_s=29)
    assert short.checks['stabilitaet'].status == 'FEHLER'
    unreliable = check_setup(image, fit(), stability_image_bgr=image, stability_elapsed_s=30)
    assert unreliable.checks['stabilitaet'].status == 'WARNUNG'
    assert unreliable.checks['stabilitaet'].metrics['max_corner_shift_px'] is None


@pytest.mark.parametrize('name,expected,step_cell_8', [('sc5', [], 8.0), ('ab1', [], 4.0), ('ab2', [8], 14.0)])
def test_real_still_edge_regression(name, expected, step_cell_8):
    frame = ROOT / f'{name}-still/frames/frame_000017.png'
    profile = ROOT / f'{name}-profile'
    if not frame.exists() or not profile.exists():
        pytest.skip('diagnostic still unavailable')
    image = cv2.imread(str(frame))
    data = json.loads(profile.read_text())
    result = check_setup(image, fit(quad=data['quad']))
    cells = result.checks['kanten'].cells
    assert result.checks['kanten'].metrics['cell_step'][8] == pytest.approx(step_cell_8, abs=0.1)
    for cell in expected:
        assert cell in cells
    if not expected:
        assert cells == ()


def test_bright_connected_glare_without_saturation_fails():
    image = display()
    image[35:55, 35:55] = 240
    check = check_setup(image, fit()).checks['glanz']
    assert check.status == 'FEHLER'
    assert check.metrics['saturated_fraction'] == 0
    assert check.metrics['bright_blob_area_px'] >= 100


@pytest.mark.parametrize('shift,expected', [(0.1, 'OK'), (0.3, 'WARNUNG'), (0.6, 'FEHLER')])
def test_reliable_stability_thresholds(monkeypatch, shift, expected):
    from dispread import setup_checks
    from dispread.frame_alignment import AlignmentEstimate

    def aligned(_reference, _current, _quad):
        return AlignmentEstimate(True, None, shift, QUAD)

    monkeypatch.setattr(setup_checks, 'estimate_quad_shift', aligned)
    image = display()
    result = check_setup(image, fit(), stability_image_bgr=image, stability_elapsed_s=30)
    assert result.checks['stabilitaet'].status == expected
    assert result.checks['stabilitaet'].metrics['max_corner_shift_px'] == shift


def test_rejects_missing_or_invalid_lattice_measurements():
    with pytest.raises((AttributeError, ValueError)):
        check_setup(display(), fit(n_dots=-1))
    with pytest.raises(ValueError, match='Quad'):
        check_setup(display(), fit(quad=[[0, 0], [1, 1]]))


def test_rejects_nonfinite_quality_measures():
    with pytest.raises(ValueError, match='Rasterbefund'):
        check_setup(display(), fit(rms_cols=float('nan')))


def test_edge_through_occupied_cell_is_reported():
    image = display()
    image[:, 257:275] = np.clip(image[:, 257:275].astype(int) - 28, 0, 255)
    check = check_setup(image, fit()).checks['kanten']
    assert 10 in check.cells
    assert check.status in ('WARNUNG', 'FEHLER')


def test_dark_monitor_reflection_on_right_blank_cells_is_reported():
    image = display()
    image[:, 330:365] = np.clip(image[:, 330:365].astype(int) - 28, 0, 255)
    check = check_setup(image, fit()).checks['kanten']
    assert check.status == 'FEHLER'
    assert 13 in check.cells
    assert 14 in check.cells
