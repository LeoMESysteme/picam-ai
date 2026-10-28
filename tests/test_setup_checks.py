"""Setup checks use only synthetic images and existing read-only stills."""

import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from devdata_helpers import local_recording

from dispread.dotlattice import LatticeFit
from dispread.ocr.dotmatrix_font import COLS, ROWS, rom_vector
from dispread.setup_checks import CheckResult, check_setup, raster_offset_check

QUAD = [[0, 0], [400, 0], [400, 160], [0, 160]]
OFFSET_QUAD = np.array([[120., 150.], [760., 120.], [770., 215.], [110., 240.]], np.float32)
OFFSET_TEXT = '+0.46781 '


def offset_image(text=OFFSET_TEXT):
    """Render ROM dots at the nominal grid, then project into a source still."""
    scale = 4
    width, height = 400 * scale, 160 * scale
    high = np.full((height, width), 200, np.uint8)
    sx, sy = (width - 1) / 399, (height - 1) / 159
    col_width = 25 / 6 * sx
    row_height = (160 - 160 / 9) / ROWS * sy
    for cell, char in enumerate(text):
        dots = rom_vector(char).reshape(ROWS, COLS)
        for row, column in zip(*np.nonzero(dots), strict=True):
            x = cell * 25 * sx + (column + .5) * col_width
            y = 160 / 9 * sy + (row + .5) * row_height
            cv2.rectangle(high, (int(x - .4 * col_width), int(y - .4 * row_height)),
                          (int(x + .4 * col_width), int(y + .4 * row_height)), 60, -1)
    source = np.array([[0, 0], [399, 0], [399, 159], [0, 159]], np.float32)
    hom = cv2.getPerspectiveTransform(source, OFFSET_QUAD) @ np.diag([1 / sx, 1 / sy, 1.])
    return cv2.warpPerspective(high, hom, (900, 420), flags=cv2.INTER_AREA, borderValue=200)


def test_raster_offset_accepts_aligned_dots_and_serializes_without_text():
    result = raster_offset_check([(offset_image(), OFFSET_TEXT)], OFFSET_QUAD)
    report = result.to_dict()
    assert report['status'] == 'OK'
    assert report['metrics']['max_abs_dx_cols'] < .15
    assert report['metrics']['max_abs_dy_rows'] < .15
    assert report['metrics']['half_cell_count'] >= 3
    assert report['metrics']['full_cell_count'] >= 3
    assert report['metrics']['source']['kind'] == 'known_cell_text'
    assert OFFSET_TEXT not in json.dumps(report)
    json.dumps(report, allow_nan=False)


def test_raster_offset_skips_changing_cell_and_keeps_reliable_coverage():
    result = raster_offset_check([(offset_image(), '+0.4?781 ')], OFFSET_QUAD)
    assert result.status == 'OK'
    assert result.metrics['max_abs_dx_cols'] < .15
    assert all(row['full_cells'] >= 3 for row in result.metrics['frame_coverage'])
    assert 4 not in {row['cell'] for row in result.metrics['full_offsets']}


def test_raster_offset_rejects_changing_cells_when_coverage_is_too_sparse():
    result = raster_offset_check([(offset_image(), '+0???????')], OFFSET_QUAD)
    assert result.status == 'FEHLER'
    assert result.reason == 'zu_wenige_belastbare_zellen_im_bild'
    assert result.metrics['max_abs_dx_cols'] is None


def test_raster_offset_detects_sheared_quad():
    wrong = OFFSET_QUAD.copy()
    wrong[3, 0] -= 8
    result = raster_offset_check([(offset_image(), OFFSET_TEXT)], wrong)
    assert result.status == 'FEHLER'
    assert result.metrics['max_abs_dx_cols'] > .25


def test_raster_offset_detects_too_small_pitch():
    wrong = OFFSET_QUAD.copy()
    wrong[1, 0] -= 12
    wrong[2, 0] -= 12
    result = raster_offset_check([(offset_image(), OFFSET_TEXT)], wrong)
    assert result.status == 'FEHLER'
    assert result.metrics['max_abs_dx_cols'] > .25


@pytest.mark.parametrize('frames', [[], [(np.full((420, 900), 200, np.uint8), OFFSET_TEXT)],
                                     [(offset_image('+' + ' ' * 15), '+' + ' ' * 15)]])
def test_raster_offset_rejects_missing_unreliable_or_sparse_data(frames):
    result = raster_offset_check(frames, OFFSET_QUAD)
    assert result.status == 'FEHLER'
    assert result.reason is not None
    assert result.metrics['max_abs_dx_cols'] is None
    assert result.metrics['max_abs_dy_rows'] is None
    json.dumps(result.to_dict(), allow_nan=False)


def test_raster_offset_requires_reliable_cells_in_each_still():
    valid = offset_image()
    unreadable = np.full_like(valid, 200)
    result = raster_offset_check([(valid, OFFSET_TEXT), (unreadable, OFFSET_TEXT)], OFFSET_QUAD)
    assert result.status == 'FEHLER'
    assert result.reason == 'zu_wenige_belastbare_zellen_im_bild'
    assert result.metrics['max_abs_dx_cols'] is None
    assert result.metrics['max_abs_dy_rows'] is None


def test_optional_offset_result_participates_in_setup_total():
    image = display()
    baseline = check_setup(image, fit())
    from dispread.setup_checks import CheckResult
    warning = CheckResult('WARNUNG', {'max_abs_dx_cols': .2})
    with_offset = check_setup(image, fit(), offset_check=warning)
    assert 'rasterversatz' not in baseline.checks
    assert with_offset.checks['rasterversatz'] is warning
    assert with_offset.overall == ('FEHLER' if baseline.overall == 'FEHLER' else 'WARNUNG')


def test_ab4_regridded_profile_clears_real_still_offset():
    frame = local_recording('diagnostics/ab4-still/frames/frame_000016.png')
    old = local_recording('diagnostics/ab4-profile')
    regridded = local_recording('diagnostics/ab4-profile-regrid1.json')

    image = cv2.imread(str(frame))
    assert image is not None
    # Display text was independently recorded in ab4-still/serial.jsonl.
    observations = [(image, '+0.46780 ')]
    old_check = raster_offset_check(observations, json.loads(old.read_text())['quad'])
    new_check = raster_offset_check(observations, json.loads(regridded.read_text())['quad'])
    assert old_check.status == 'FEHLER'
    assert old_check.metrics['max_abs_dx_cols'] > .25
    assert new_check.status == 'OK'
    assert new_check.metrics['max_abs_dx_cols'] < .15
    assert new_check.metrics['max_abs_dy_rows'] < .15


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


def test_independent_offset_demotes_rms_proxy_to_warning():
    image = display()
    lattice = fit(rms_cols=.31, rms_rows=.35)
    offset = CheckResult('OK', {'max_abs_dx_cols': .05, 'max_abs_dy_rows': .06})
    result = check_setup(image, lattice, offset_check=offset)
    assert result.checks['raster'].status == 'WARNUNG'
    assert result.checks['raster'].metrics['rms_cols'] == .31
    assert result.overall in ('OK', 'WARNUNG')
    assert check_setup(image, lattice).checks['raster'].status == 'FEHLER'


def test_independent_offset_check_prevents_low_assignment_from_failing_setup():
    image = cv2.cvtColor(offset_image(), cv2.COLOR_GRAY2BGR)
    lattice = LatticeFit(OFFSET_QUAD.tolist(), 454, 315, .1, .15,
                         tuple(range(16)), (0.,) * 7, (0.,) * 16)
    offset = raster_offset_check([(image, OFFSET_TEXT)], OFFSET_QUAD)
    assert offset.status == 'OK'
    result = check_setup(image, lattice, offset_check=offset)
    assert result.checks['raster'].metrics['assigned_fraction'] == pytest.approx(315 / 454)
    assert result.checks['raster'].status in ('OK', 'WARNUNG')
    assert result.overall in ('OK', 'WARNUNG')


def test_low_assignment_without_independent_offset_still_fails_setup():
    image = cv2.cvtColor(offset_image(), cv2.COLOR_GRAY2BGR)
    lattice = LatticeFit(OFFSET_QUAD.tolist(), 454, 315, .1, .15,
                         tuple(range(16)), (0.,) * 7, (0.,) * 16)
    result = check_setup(image, lattice)
    assert result.checks['raster'].status == 'FEHLER'
    assert result.overall == 'FEHLER'


def test_stability_requires_elapsed_time_and_warns_if_unreliable():
    image = display()
    short = check_setup(image, fit(), stability_image_bgr=image, stability_elapsed_s=29)
    assert short.checks['stabilitaet'].status == 'FEHLER'
    unreliable = check_setup(image, fit(), stability_image_bgr=image, stability_elapsed_s=30)
    assert unreliable.checks['stabilitaet'].status == 'WARNUNG'
    assert unreliable.checks['stabilitaet'].metrics['max_corner_shift_px'] is None


@pytest.mark.parametrize('name,frame_number,expected,step_cell_8', [
    ('sc3', 17, [], 4.0), ('sc4', 17, [], 1.0), ('sc5', 17, [], 2.0),
    ('ab1', 17, [], 2.5), ('ab2', 17, [8], 9.0), ('sc6', 15, [], 2.0),
])
def test_real_still_edge_regression(name, frame_number, expected, step_cell_8):
    frame = local_recording(f'diagnostics/{name}-still/frames/frame_{frame_number:06d}.png')
    profile = local_recording(f'diagnostics/{name}-profile')

    image = cv2.imread(str(frame))
    data = json.loads(profile.read_text())
    result = check_setup(image, fit(quad=data['quad']))
    cells = result.checks['kanten'].cells
    assert result.checks['kanten'].metrics['cell_step'][8] == pytest.approx(step_cell_8, abs=0.1)
    for cell in expected:
        assert cell in cells
    if not expected:
        assert cells == ()
        assert result.checks['kanten'].status == 'OK'
    else:
        assert result.checks['kanten'].status == 'FEHLER'


@pytest.mark.parametrize('name,frame_number,point_contrast,reader_contrast', [
    ('sc5', 17, 19.1, 0.284), ('sc6', 15, 19.7, 0.338),
])
def test_real_still_good_point_contrast_is_ok(name, frame_number, point_contrast, reader_contrast):
    frame = local_recording(f'diagnostics/{name}-still/frames/frame_{frame_number:06d}.png')
    profile = local_recording(f'diagnostics/{name}-profile')

    image = cv2.imread(str(frame))
    quad = json.loads(profile.read_text())['quad']
    result = check_setup(image, fit(quad=quad)).checks['kontrast']
    assert result.metrics['punktkontrast'] == pytest.approx(point_contrast, abs=0.1)
    assert result.metrics['leser_kontrast'] == pytest.approx(reader_contrast, abs=0.01)
    assert result.status == 'OK'


def test_sc6_validated_still_has_clear_border():
    frame = local_recording('diagnostics/sc6-still/frames/frame_000015.png')
    profile = local_recording('diagnostics/sc6-profile')

    image = cv2.imread(str(frame))
    quad = json.loads(profile.read_text())['quad']
    border = check_setup(image, fit(quad=quad)).checks['rahmen']
    assert border.status == 'OK'
    assert border.cells == ()
    assert border.metrics['minimum_border_ratio'] == pytest.approx(0.959, abs=0.02)


def test_dark_outer_column_in_blank_cell_fails_but_clean_border_passes():
    clean = np.full((160, 400, 3), 100, np.uint8)
    assert check_setup(clean, fit()).checks['rahmen'].status == 'OK'
    covered = clean.copy()
    covered[20:160, 391:400] = 44
    check = check_setup(covered, fit()).checks['rahmen']
    assert check.status == 'FEHLER'
    assert 15 in check.cells
    assert check.metrics['minimum_border_ratio'] < 0.7


def test_dark_outer_row_in_blank_cell_fails():
    image = np.full((160, 400, 3), 100, np.uint8)
    image[24:31, 200:225] = 45
    check = check_setup(image, fit()).checks['rahmen']
    assert check.status == 'FEHLER'
    assert 8 in check.cells


def test_dark_left_column_in_blank_first_cell_fails():
    image = np.full((160, 400, 3), 100, np.uint8)
    image[20:160, :5] = 44
    check = check_setup(image, fit()).checks['rahmen']
    assert check.status == 'FEHLER'
    assert 0 in check.cells


def test_dark_left_column_with_plus_in_first_cell_fails():
    clean = np.full((160, 400, 3), 100, np.uint8)
    for row in range(7):
        for column in range(5):
            if row == 3 or column == 2 and 1 <= row <= 5:
                x = round((column + .5) * 25 / 6)
                y = round(160 / 9 + (row + .5) * (160 * 7 / 9) / 7)
                cv2.circle(clean, (x, y), 2, (45, 45, 45), -1)
    assert check_setup(clean, fit()).checks['rahmen'].status == 'OK'
    covered = clean.copy()
    covered[20:160, :5] = np.minimum(covered[20:160, :5], 44)
    check = check_setup(covered, fit()).checks['rahmen']
    assert check.status == 'FEHLER'
    assert 0 in check.cells


@pytest.mark.parametrize('reason,reference,read_text,expected,read_count', [
    ('zelle_unbekannt', '+0.6097? ', '+0.6097? ', 'OK', 1),
    ('zelle_mehrdeutig', '+0.6097? ', '+0.6097? ', 'OK', 1),
    ('zelle_unbekannt', '+0.60972 ', '+0.6097? ', 'WARNUNG', 0),
    ('kontrast', '+0.6097? ', '+0.6097? ', 'WARNUNG', 0),
    ('ueberbelichtet', '+0.6097? ', '+0.6097? ', 'WARNUNG', 0),
    ('format', '+0.6097? ', '+0.60972 ', 'WARNUNG', 0),
    ('format', '+0.6097? ', '+0.6097? ', 'OK', 1),
    # Maskierte Mischziffer als ' ' oder '.' gelesen: Formatfehler nur dort.
    ('format', '+0.6097? ', '+0.6097  ', 'OK', 1),
    ('format', '+0.6097? ', '+0.6097. ', 'OK', 1),
    (None,'+0.60972 ', '+0.60973 ', 'FEHLER', 0),
    ('zelle_unbekannt', '+0.60972 ', '+0.609?3 ', 'FEHLER', 0),
    (None, '+0.60??? ', '+0.60972 ', 'WARNUNG', 0),
    (None, '+0.609?? ', '+0.60972 ', 'OK', 1),
])
def test_reader_diagnostic_compares_only_unmasked_cells(
        monkeypatch, tmp_path, reason, reference, read_text, expected, read_count):
    from types import SimpleNamespace

    from dispread import setup_checks

    diagnostics = {
        'reject_reason': reason, 'blank_cells_ok': True,
        'cells': [{'text': None if ch == '?' else ch,
                   'reason': 'zelle_unbekannt' if ch == '?' else None} for ch in read_text],
    }
    reader = SimpleNamespace(read=lambda *_: SimpleNamespace(diagnostics=diagnostics))
    monkeypatch.setattr(setup_checks.DotMatrixReader, 'from_file', lambda *_: reader)
    result = setup_checks.diagnose_reader([(display(), reference)], QUAD, tmp_path / 't.json', 'a' * 64)
    assert result.status == expected
    assert result.metrics['read_count'] == read_count
    assert result.metrics['frames'] == 1
    assert result.metrics['read_rate'] == read_count
    assert result.metrics['masked_cells'] == [[i for i, ch in enumerate(reference) if ch == '?']]
    if expected == 'FEHLER':
        assert result.metrics['contradictions'] == [
            {'frame': 0, 'cell': 7, 'read': '3', 'reference': '2'}]
        assert result.metrics['rejection_reasons'] == {'zelle_widerspricht_referenz': 1}
    elif reference == '+0.60??? ':
        assert result.metrics['rejection_reasons'] == {'zu_wenige_vergleichbare_zellen': 1}


def test_reader_diagnostic_requires_every_still_and_checks_blank_cells(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from dispread import setup_checks

    diags = iter([
        {'reject_reason': None, 'blank_cells_ok': True,
         'cells': [{'text': ch, 'reason': None} for ch in '+0.60972 ']},
        {'reject_reason': 'zelle_unbekannt', 'blank_cells_ok': False,
         'cells': [{'text': None if ch == '?' else ch, 'reason': None} for ch in '+0.6097? ']},
    ])
    reader = SimpleNamespace(read=lambda *_: SimpleNamespace(diagnostics=next(diags)))
    monkeypatch.setattr(setup_checks.DotMatrixReader, 'from_file', lambda *_: reader)
    result = setup_checks.diagnose_reader([(display(), '+0.6097? ')] * 2, QUAD, tmp_path / 't.json', 'a' * 64)
    assert result.status == 'WARNUNG'
    assert result.metrics['read_count'] == 1
    assert result.metrics['rejection_reasons'] == {'format': 1}


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


def test_workbench_stability_minimum_keeps_cli_default():
    image = np.full((160, 400), 180, np.uint8)
    default = check_setup(image, fit(), stability_image_bgr=image, stability_elapsed_s=15)
    assert default.checks['stabilitaet'].reason == 'abstand_zu_kurz'
    bench = check_setup(image, fit(), stability_image_bgr=image, stability_elapsed_s=15,
                        stability_min_elapsed_s=15)
    assert bench.checks['stabilitaet'].status != 'FEHLER'
    short = check_setup(image, fit(), stability_image_bgr=image, stability_elapsed_s=14.9,
                        stability_min_elapsed_s=15)
    assert short.checks['stabilitaet'].reason == 'abstand_zu_kurz'


@pytest.mark.parametrize('rest_char,expected', [(' ', 'OK'), ('0', 'WARNUNG')])
def test_reader_diagnostic_real_reader_mask_keeps_blank_check(monkeypatch, tmp_path, rest_char, expected):
    from dotmatrix_helpers import GRID as test_grid
    from dotmatrix_helpers import render, synthetic_reader

    from dispread import setup_checks

    reader = synthetic_reader()
    monkeypatch.setattr(setup_checks, 'GRID', test_grid)
    monkeypatch.setattr(setup_checks.DotMatrixReader, 'from_file', lambda *_: reader)
    chars = list('+0.6097° ' + ' ' * 7)
    chars[14] = rest_char
    image = render(''.join(chars), grid=setup_checks.GRID)
    result = setup_checks.diagnose_reader(
        [(image, '+0.6097? ')], [[0, 0], [399, 0], [399, 159], [0, 159]], tmp_path / 't.json', 'a' * 64,
    )
    assert result.status == expected
    assert result.metrics['read_count'] == (1 if expected == 'OK' else 0)


@pytest.mark.parametrize('depths,edge', [([.4] * 4 + [.68] * 4 + [0], [3, 4]),
                                        ([.7] * 8 + [0], None)])
def test_lighting_hint_is_informational(monkeypatch, tmp_path, depths, edge):
    from types import SimpleNamespace

    from dispread import setup_checks

    diag = {'reject_reason': None, 'blank_cells_ok': True,
            'cells': [{'text': ch} for ch in '+0.60972 ']}
    monkeypatch.setattr(setup_checks.DotMatrixReader, 'from_file',
                        lambda *_: SimpleNamespace(read=lambda *_: SimpleNamespace(diagnostics=diag)))
    monkeypatch.setattr(setup_checks, 'raw_cell_depths', lambda _: np.array(depths))
    result = setup_checks.diagnose_reader([(display(), '+0.60972 ')], QUAD, tmp_path / 't', 'sha')
    assert result.status == 'OK'
    if edge:
        assert result.metrics['lighting']['edge_between'] == edge
        assert result.metrics['lighting']['max_ratio'] == pytest.approx(1.7)
        assert 'Zelle 3 und 4' in result.metrics['hinweis']
    else:
        assert 'hinweis' not in result.metrics


def test_raw_cell_depths_uses_second_darkest_zero_shift():
    from dispread.ocr.dotmatrix_sampling import SHIFTS, SampledImage, raw_cell_depths

    raw = np.full((9, len(SHIFTS), 40), 100, np.float32)
    raw[:, SHIFTS.index((0, 0)), :2] = [1, 60]
    sampled = SampledImage(raw, np.full(9, 100), 1, .99, 0)
    assert raw_cell_depths(sampled) == pytest.approx([.4] * 9)


@pytest.mark.parametrize('kind,best,gap,distance,blank,possible,reason', [
    ('seriell', '2', 1.3, 2.2, True, True, None),
    ('eingabe', '2', 1.3, 2.2, True, False, 'nur_mit_seriellem_referenzwert'),
    ('seriell', '3', 1.3, 2.2, True, False, 'beste_vermutung_widerspricht_referenz'),
    ('seriell', '2', .5, 2.2, True, False, 'abstand_zur_zweitbesten_zu_klein'),
    ('seriell', '2', 1.3, 3.2, True, False, 'faktor_ueber_2'),
    ('seriell', '2', 1.3, 2.2, False, False, 'gegenprobe_nicht_gelesen'),
])
def test_tolerance_requires_serial_correct_candidates_and_verified_reread(
        monkeypatch, tmp_path, kind, best, gap, distance, blank, possible, reason):
    from types import SimpleNamespace

    from dispread import setup_checks

    factors = []

    def factory(*args, d_max_factor=1.0):
        factors.append(d_max_factor)
        read_count = 0

        def read(*_):
            nonlocal read_count
            read_count += 1
            cells = [{'text': ch, 'best': ch, 'd_best': .5, 'd_second': 2, 'reason': None}
                     for ch in '+0.60972 ']
            cells[7].update(text=None if d_max_factor == 1 else best, best=best,
                            d_best=distance, d_second=distance + gap,
                            reason='zelle_unbekannt' if d_max_factor == 1 else None)
            # Maskierte Zelle darf weder Kandidatenvergleich noch Maximum beeinflussen.
            cells[6].update(best='8', d_best=99, d_second=99.01)
            diag = {'cells': cells, 'blank_cells_ok': blank if d_max_factor != 1 and read_count == 2 else True,
                    'reject_reason': 'zelle_unbekannt' if d_max_factor == 1 else None}
            return SimpleNamespace(diagnostics=diag)
        return SimpleNamespace(read=read, _t=SimpleNamespace(d_max=1.92, margin_min=.93))

    monkeypatch.setattr(setup_checks.DotMatrixReader, 'from_file', factory)
    result = setup_checks.diagnose_reader([(display(), '+0.609?2 ')] * 2, QUAD, tmp_path / 't', 'sha',
                                         reference_kind=kind)
    assert result.status == 'WARNUNG'
    tolerance = result.metrics['tolerance']
    assert tolerance['possible'] is possible
    assert tolerance['reason'] == reason
    if possible:
        assert tolerance['factor'] == 1.44
        assert tolerance['max_d_best'] == 2.2
        assert factors == [1, 1.44]
        assert 'Toleranz x1.44' in result.metrics['hinweis']
