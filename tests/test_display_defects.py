import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from dotmatrix_helpers import render

from dispread.setup_checks import GRID

QUAD = [[0., 0.], [399., 0.], [399., 159.], [0., 159.]]


def _scene():
    return render('+0.60972 ', grid=GRID)


def _check(images):
    from dispread.setup_checks import display_defect_check

    return display_defect_check(images, QUAD)


@pytest.mark.parametrize('kind,level,cell', [('hell', 255, 14), ('dunkel', 0, 14), ('hell', 255, 8)])
def test_fixed_speck_is_warning_with_cell_position_and_strength(kind, level, cell):
    image = _scene()
    image[80:83, cell * 25 + 8:cell * 25 + 11] = level
    result = _check([image, image.copy()])
    assert result.status == 'WARNUNG'
    defects = result.metrics['defects']
    assert any(d['cell'] == cell and d['kind'] == kind and d['strength'] > 0
               and len(d['dot_position']) == 2 for d in defects)
    assert 'Kamera leicht verschieben, Glas reinigen oder Reflex abschatten' in result.reason
    assert result.metrics['stills'] == 2


def test_speck_must_be_present_in_every_still():
    dirty = _scene()
    dirty[80:83, 358:361] = 255
    assert _check([dirty]).status == 'WARNUNG'
    assert _check([dirty, _scene()]).status == 'OK'
    assert _check([_scene(), dirty]).status == 'OK'
    assert _check([dirty, dirty.copy(), _scene()]).status == 'OK'
    shifted = _scene()
    shifted[80:83, 368:371] = 255
    assert _check([shifted]).status == 'WARNUNG'
    assert _check([dirty, shifted]).status == 'OK'


def test_dark_dot_pattern_in_digit_cells_is_not_a_defect():
    assert _check([_scene(), _scene()]).status == 'OK'


@pytest.mark.parametrize('filename', ['reference.jpg', 'faktor-0_5.jpg', 'faktor-1_0.jpg',
                                     'faktor-2_0.jpg', 'faktor-5_0.jpg', 'faktor-10_0.jpg'])
def test_clean_r13_fixture_does_not_warn(filename):
    from dispread.setup_checks import display_defect_check

    metadata = json.loads(Path('tests/fixtures/r13/r13-fixtures.json').read_text())
    image = cv2.imread(str(Path('tests/fixtures/r13') / filename))
    result = display_defect_check([image], metadata['quad'])
    assert result.status == 'OK'
    assert result.metrics['defects'] == []


@pytest.mark.parametrize('cell', [0, 1, 2, 5, 9, 10, 11, 12])
@pytest.mark.parametrize('level', [0, 255])
def test_character_and_unknown_cells_are_never_searched_for_defects(cell, level):
    from dispread.setup_checks import display_defect_check

    image = _scene()
    image[80:83, cell * 25 + 8:cell * 25 + 11] = level
    result = display_defect_check([image], QUAD, cell_text='+0.60972 ')
    assert result.status == 'OK'
    assert result.metrics['defects'] == []


@pytest.mark.parametrize('text,expected', [('+ 1.2345 ', 'WARNUNG'), ('+?1.2345 ', 'OK'),
                                         ('+01.2345 ', 'OK'), (None, 'OK')])
@pytest.mark.parametrize('level', [0, 255])
def test_additional_blank_cells_require_explicit_setup_space(text, expected, level):
    from dispread.setup_checks import display_defect_check

    image = render('+ 1.2345 ', grid=GRID)
    image[80:83, 33:36] = level
    result = display_defect_check([image], QUAD, cell_text=text)
    assert result.status == expected
    if expected == 'WARNUNG':
        assert any(d['cell'] == 1 for d in result.metrics['defects'])


def test_live_setup_still_reports_scratch_near_cell_14():
    from dispread.setup_checks import display_defect_check

    folder = Path('var/live/live-20261023T075343Z')
    if not (folder / 'setup/still.png').is_file():
        pytest.skip('Live-Standbild lokal nicht vorhanden')
    profile = json.loads((folder / 'profile.json').read_text())
    image = cv2.imread(str(folder / 'setup/still.png'))
    result = display_defect_check([image], profile['quad'])
    assert result.status == 'WARNUNG'
    assert any(d['cell'] == 14 and d['kind'] == 'hell' for d in result.metrics['defects'])


def test_defects_marked_on_source_and_rectified_overlays(tmp_path):
    from dispread.live.setup import write_overlays

    image = _scene()
    image[80:83, 358:361] = 255
    check = _check([image])
    assert check.status == 'WARNUNG'
    source = np.full((300, 600), 200, np.uint8)
    source[30:190, 50:450] = image
    quad = [[50., 30.], [449., 30.], [449., 189.], [50., 189.]]
    write_overlays(source, quad, GRID, tmp_path, display_defects=check.metrics['defects'])
    for name, x_offset, y_offset in (('overlay_source.png', 50, 30), ('overlay_rectified.png', 0, 0)):
        overlay = cv2.imread(str(tmp_path / name))
        region = overlay[75 + y_offset:89 + y_offset, 352 + x_offset:367 + x_offset]
        assert np.any(np.all(region == (0, 180, 255), axis=2)), name


def test_live_scratch_is_fixed_across_both_setup_stills():
    from dispread.setup_checks import display_defect_check

    folder = Path('var/live/live-20261023T075343Z')
    if not (folder / 'setup/stability.png').is_file():
        pytest.skip('Live-Standbilder lokal nicht vorhanden')
    quad = json.loads((folder / 'profile.json').read_text())['quad']
    images = [cv2.imread(str(folder / 'setup' / name)) for name in ('still.png', 'stability.png')]
    check = display_defect_check(images, quad)
    assert check.status == 'WARNUNG'
    assert any(d['cell'] == 14 and d['kind'] == 'hell' for d in check.metrics['defects'])


def test_local_setup_sweep_reports_all_remaining_warnings():
    from dispread.setup_checks import BLANK_CELLS, display_defect_check

    stills = sorted(Path('var/live').glob('*/setup/still.png'))
    if not stills:
        pytest.skip('Keine lokalen Live-Standbilder vorhanden')
    counts = {'OK': 0, 'WARNUNG': 0, 'missing_geometry': 0, 'stills': 0}
    warnings = []
    for still in stills:
        geometry_path = next((p for p in (still.parent / 'proposal.json', still.parents[1] / 'profile.json')
                              if p.is_file()), None)
        if geometry_path is None:
            counts['missing_geometry'] += 1
            continue
        geometry = json.loads(geometry_path.read_text())
        text_path = still.parent / 'cell-text.json'
        text = None
        if text_path.is_file():
            entries = json.loads(text_path.read_text())
            attempt = geometry.get('setup_attempt') or max(e['attempt'] for e in entries)
            texts = [e['masked'] for e in entries if e['attempt'] == attempt and e.get('masked')]
            if texts:
                text = ''.join(' ' if all(i < len(t) and t[i] == ' ' for t in texts) else '?'
                               for i in range(max(map(len, texts))))
        paths = [still]
        stability = still.parent / 'stability.png'
        if stability.is_file():
            paths.append(stability)
        images = [cv2.imread(str(p)) for p in paths]
        assert all(image is not None for image in images), paths
        result = display_defect_check(images, geometry['quad'], cell_text=text)
        assert result.status in ('OK', 'WARNUNG')
        blank = set(BLANK_CELLS) | {i for i, ch in enumerate(text or '') if ch == ' '}
        assert all(d['cell'] in blank for d in result.metrics['defects'])
        counts[result.status] += 1
        counts['stills'] += len(images)
        if result.status == 'WARNUNG':
            warnings.append({'setup': str(still.parent), 'images': [p.name for p in paths],
                             'findings': result.metrics['defects']})
    if not counts['stills']:
        pytest.skip('Keine lokalen Standbilder mit gespeicherter Geometrie vorhanden')
    print('\nSETUP_SWEEP ' + json.dumps({'counts': counts, 'warnings': warnings}, ensure_ascii=False))
