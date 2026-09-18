"""Experiment scoring must not certify decimal errors or data leakage."""
import hashlib
import json

import pytest

from dispread.experimental.evaluation import compare_text, load_manifest, screening


@pytest.mark.parametrize(('expected', 'actual', 'outcome', 'errors'), [
    ('-28,80', '-28.80', 'correct', []),
    ('28.80', '288.0', 'wrong', ['decimal']),
    ('-28.80', '288.0', 'wrong', ['sign', 'decimal']),
    ('28.80', '28.81', 'wrong', ['digit']),
    ('28.80', None, 'rejected', []),
    (None, '28.80', 'wrong', ['unreadable_accepted']),
    (None, None, 'rejected', []),
])
def test_exact_text_preserves_decimal_and_sign(expected, actual, outcome, errors):
    assert compare_text(expected, actual) == {'outcome': outcome, 'errors': errors}


def manifest_at(tmp_path, samples):
    image = tmp_path / 'frame.png'
    image.write_bytes(b'fixture')
    for sample in samples:
        sample.update(path='frame.png', sha256=hashlib.sha256(b'fixture').hexdigest(),
                      family='meter', technology='LCD', source='test', license='test',
                      expected_text='12.3', bbox=[1, 2, 30, 10], conditions=[])
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps({'schema_version': 1, 'samples': samples}))
    return path


def sample(id='a', device='dev-a', split='development', group='g1'):
    return dict(id=id, device_id=device, identity_verified=True, split=split, independence_group=group)


def test_relative_paths_are_manifest_relative_not_cwd(tmp_path, monkeypatch):
    path = manifest_at(tmp_path, [sample()])
    monkeypatch.chdir('/')
    data = load_manifest(path)
    assert data['samples'][0]['resolved_path'] == str(tmp_path / 'frame.png')


def test_physical_device_overlap_rejected_even_when_sample_names_differ(tmp_path):
    path = manifest_at(tmp_path, [sample(), sample('b', split='heldout', group='g2')])
    with pytest.raises(ValueError, match='device'):
        load_manifest(path)


def test_unknown_identity_cannot_enter_heldout(tmp_path):
    item = sample(split='heldout')
    item['identity_verified'] = False
    path = manifest_at(tmp_path, [item])
    with pytest.raises(ValueError, match='identity'):
        load_manifest(path)


def test_duplicate_images_cannot_masquerade_as_independent(tmp_path):
    path = manifest_at(tmp_path, [sample(), sample('b', 'dev-b', 'heldout', 'g2')])
    with pytest.raises(ValueError, match='duplicate|hash'):
        load_manifest(path)


def test_file_changes_invalidate_frozen_manifest(tmp_path):
    path = manifest_at(tmp_path, [sample()])
    (tmp_path / 'frame.png').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash'):
        load_manifest(path)


def test_perfect_but_tiny_dataset_cannot_qualify():
    metrics = dict(correct=2, wrong=0, total=2, geometry_failures=0,
                   detection_p95_ms=30, processing_p95_ms=40)
    coverage = dict(devices=6, families=3, technologies=['LED', 'LCD'],
                    heldout_devices=2, heldout_independent_images=2)
    result = screening(metrics, coverage, pi_measured=True)
    assert not result['qualified']
    assert 'insufficient_coverage' in result['reasons']


def test_crop_accuracy_cannot_pass_without_geometry_or_pi_measurement():
    metrics = dict(correct=30, wrong=0, total=30, geometry_failures=1,
                   detection_p95_ms=30, processing_p95_ms=40)
    coverage = dict(devices=6, families=3, technologies=['LED', 'LCD'],
                    heldout_devices=2, heldout_independent_images=30)
    result = screening(metrics, coverage, pi_measured=False)
    assert not result['qualified']
    assert {'geometry_unresolved', 'pi_unmeasured'} <= set(result['reasons'])


def test_scoring_matches_regions_without_passing_labels_to_detector():
    from dispread.experimental.runner import match_target
    # Region 0 is a neighboring row; region 1 covers the requested display.
    predictions = [{'bbox': [10, 80, 100, 20]}, {'bbox': [10, 10, 100, 20]}]
    assert match_target(predictions, [10, 10, 100, 20], .5) == 1
    assert match_target(predictions, [200, 200, 30, 10], .5) is None


def test_summary_keeps_misses_rejections_and_wrong_decimal_separate():
    from dispread.experimental.runner import summarize
    rows = [
        dict(outcome='correct', errors=[], detected=True, geometry_ready=False,
             detection_ms=10., processing_ms=20., total_ms=30.),
        dict(outcome='wrong', errors=['decimal'], detected=True, geometry_ready=False,
             detection_ms=10., processing_ms=20., total_ms=30.),
        dict(outcome='missed', errors=[], detected=False, geometry_ready=False,
             detection_ms=10., processing_ms=None, total_ms=10.),
    ]
    summary = summarize(rows)
    assert (summary['correct'], summary['wrong'], summary['rejected'], summary['missed']) == (1, 1, 0, 1)
    assert summary['errors'] == {'decimal': 1}
    assert summary['detection_recall'] == pytest.approx(2/3)
    assert summary['geometry_failures'] == 3


def test_leading_decimal_display_is_preserved(tmp_path):
    path = manifest_at(tmp_path, [sample()])
    data = json.loads(path.read_text())
    data['samples'][0]['expected_text'] = '.000'
    path.write_text(json.dumps(data))
    assert load_manifest(path)['samples'][0]['expected_text'] == '.000'
    assert compare_text('-.123', '-.123')['outcome'] == 'correct'
    assert compare_text('.123', '1.23')['errors'] == ['decimal']


def test_correlated_heldout_frames_cannot_inflate_screening(tmp_path):
    path = manifest_at(tmp_path, [sample(split='heldout'), sample('b', split='heldout')])
    data = json.loads(path.read_text())
    (tmp_path/'other.png').write_bytes(b'other image')
    data['samples'][1].update(path='other.png', sha256=hashlib.sha256(b'other image').hexdigest())
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='independence'):
        load_manifest(path)


@pytest.mark.parametrize('bad', [float('nan'), float('inf')])
def test_nonfinite_geometry_is_rejected(tmp_path, bad):
    path = manifest_at(tmp_path, [sample()])
    data = json.loads(path.read_text())
    data['samples'][0]['bbox'][0] = bad
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='box'):
        load_manifest(path)


def test_invalid_candidate_is_rejected_without_aborting_frame(tmp_path):
    import cv2
    import numpy as np

    from dispread.detect import DisplayCandidate
    from dispread.experimental.runner import _measure_sample

    path = tmp_path/'image.png'
    cv2.imwrite(str(path), np.zeros((100, 200, 3), np.uint8))

    class Locator:
        def locate(self, frame):
            return (DisplayCandidate(((10,10),(50,10),(50,10),(10,40)), 1., 'fixture'),)

    class Reader:
        def read(self, crop):
            raise AssertionError('invalid geometry must not reach reader')

    item = dict(resolved_path=str(path), id='fixture', device_id='one', conditions=[],
                split='development', expected_text='12.3', bbox=[10,10,40,30])
    row, _ = _measure_sample(item, Reader(), Locator(), 'full_frame', .5)
    assert row['outcome'] == 'rejected'
    assert not row['geometry_ready']
    assert row['predictions'][0]['geometry']['uncertainty'].startswith('rectification_failed')
