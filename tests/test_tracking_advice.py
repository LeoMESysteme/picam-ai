"""Bedienhinweise sind vom Messpfad getrennt und zeitlich begrenzt."""

import json
import threading
from pathlib import Path

import cv2
import numpy as np
import pytest
from frame_tracking_helpers import reference_scene

from dispread.live.tracking_advice import DisplayMotionEstimator, TrackingAdvice


def transformed_scene(dx=15, dy=0, angle=2.25):
    reference, quad = reference_scene()
    quad = np.asarray(quad, dtype=np.float32)
    matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), angle, 1)
    matrix[:, 2] += (dx, dy)
    moved = cv2.warpAffine(reference, matrix, reference.shape[1::-1])
    # Nur das Geraet bewegt sich; der Hintergrund bleibt unveraendert.
    centre = quad.mean(axis=0)
    polygon = (quad - centre) * [1.6, 3.0] + centre
    mask = np.zeros(reference.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, polygon.astype(np.int32), 255)
    target_mask = cv2.warpAffine(mask, matrix, reference.shape[1::-1])
    result = reference.copy()
    result[(mask | target_mask) != 0] = moved[(mask | target_mask) != 0]
    return reference, quad, result


def collect(advice, now):
    if advice._future is not None:
        advice._future.result(timeout=5)
    return advice.snapshot(now)


@pytest.mark.parametrize('dx,dy,angle', [(15, 0, 2.25), (-65, 35, -4), (0, 0, 5), (15, 0, 0)])
def test_local_motion_of_fixture_has_right_magnitude(dx, dy, angle):
    reference, quad, moved = transformed_scene(dx, dy, angle)
    advice = TrackingAdvice(reference, quad)
    try:
        advice.observe(moved, lost=True, now=0)
        assert advice.snapshot(2.99) is None
        advice.observe(moved, lost=True, now=3)
        hint = collect(advice, 3)
        assert hint['kind'] == 'anzeige_bewegt'
        matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), angle, 1)
        matrix[:, 2] += (dx, dy)
        expected = np.linalg.norm(quad @ matrix[:, :2].T + matrix[:, 2] - quad, axis=1).max()
        assert hint['shift_px'] == pytest.approx(expected, abs=3)
        assert hint['rotation_deg'] == pytest.approx(-angle, abs=0.6)
        assert hint['since_s'] == 3
        assert advice.summary()['count'] == 1
        assert advice.summary()['max_shift_px'] == pytest.approx(expected, abs=3)
        advice.observe(reference, lost=False, now=4)
        assert advice.snapshot(4) is None
    finally:
        advice.close()


@pytest.mark.parametrize('occlusion', ['full', 'frame', 'noise', 'partial'])
def test_occlusion_never_claims_motion(occlusion):
    reference, quad = reference_scene()
    image = reference.copy()
    quad = np.asarray(quad)
    centre = quad.mean(axis=0)
    mask = np.zeros(image.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, np.int32((quad - centre) * [1.6, 3] + centre), 255)
    if occlusion == 'partial':
        mask[:, :int(centre[0])] = 0
    if occlusion == 'full':
        mask[:] = 255
    image[mask != 0] = (np.random.default_rng(13).integers(0, 256, image.shape, dtype=np.uint8)[mask != 0]
                        if occlusion == 'noise' else 110)
    advice = TrackingAdvice(reference, quad)
    try:
        advice.observe(image, lost=True, now=0)
        advice.observe(image, lost=True, now=3)
        assert collect(advice, 3) is None
        advice.observe(image, lost=True, now=10)
        hint = collect(advice, 10)
        assert hint['kind'] in ('rahmen_verdeckt', 'unbekannt')
        assert hint['shift_px'] is None and hint['rotation_deg'] is None
    finally:
        advice.close()


def test_no_estimation_while_tracking_fine_and_continuous_loss_restarts(monkeypatch):
    reference, quad, moved = transformed_scene()
    calls = []
    monkeypatch.setattr(DisplayMotionEstimator, 'estimate', lambda self, image: calls.append(1))
    advice = TrackingAdvice(reference, quad)
    try:
        for now in (0, 3, 10, 100):
            advice.observe(reference, lost=False, now=now)
            assert advice.snapshot(now) is None
        advice.observe(moved, lost=True, now=101)
        advice.observe(reference, lost=False, now=103)
        advice.observe(moved, lost=True, now=104)
        advice.observe(moved, lost=True, now=106.99)
        assert calls == []
        advice.observe(moved, lost=True, now=107)
        collect(advice, 107)
        assert calls == [1]
    finally:
        advice.close()


def test_fake_clock_bounds_estimation_and_counts_episodes(monkeypatch):
    reference, quad = reference_scene()
    calls = []
    now = [0.0]
    def estimate(self, image):
        calls.append(now[0])
        return (19.0, -2.23, 27.0)
    monkeypatch.setattr(DisplayMotionEstimator, 'estimate', estimate)
    advice = TrackingAdvice(reference, quad)
    try:
        for tick in range(101):
            now[0] = tick / 10
            advice.observe(reference, lost=True, now=now[0])
            collect(advice, now[0])
        assert calls == [3, 5, 7, 9]
        assert advice.summary()['count'] == 1
        advice.observe(reference, lost=False, now=11)
        advice.observe(reference, lost=True, now=12)
        advice.observe(reference, lost=True, now=15)
        collect(advice, 15)
        assert advice.summary()['count'] == 2
    finally:
        advice.close()


def test_slow_worker_never_queues_frames_or_revives_recovered_hint(monkeypatch):
    reference, quad = reference_scene()
    entered, finish = threading.Event(), threading.Event()
    calls = []
    def estimate(self, image):
        calls.append(1)
        entered.set()
        assert finish.wait(5)
        return (19.0, 2.23, 27.0)
    monkeypatch.setattr(DisplayMotionEstimator, 'estimate', estimate)
    advice = TrackingAdvice(reference, quad)
    try:
        advice.observe(reference, lost=True, now=0)
        advice.observe(reference, lost=True, now=3)
        assert entered.wait(2)
        for now in (5, 7, 9):
            advice.observe(reference, lost=True, now=now)
        advice.observe(reference, lost=False, now=10)
        advice.observe(reference, lost=True, now=11)
        finish.set()
        assert collect(advice, 11) is None
        assert calls == [1]
        assert advice.summary()['count'] == 0
    finally:
        finish.set()
        advice.close()


def test_estimator_failure_only_degrades_advice(monkeypatch):
    reference, quad = reference_scene()
    def fail(self, image):
        raise RuntimeError('Diagnose ausgefallen')
    monkeypatch.setattr(DisplayMotionEstimator, 'estimate', fail)
    advice = TrackingAdvice(reference, quad)
    try:
        advice.observe(reference, lost=True, now=0)
        advice.observe(reference, lost=True, now=10)
        # Fehler des Workers duerfen nicht den Lauf beenden.
        try:
            advice._future.result(timeout=5)
        except RuntimeError:
            pass
        assert advice.snapshot(10)['kind'] == 'unbekannt'
    finally:
        advice.close()


def test_delayed_worker_keeps_two_second_spacing_after_completion(monkeypatch):
    reference, quad = reference_scene()
    entered, finish = threading.Event(), threading.Event()
    calls = []
    now = [0.0]
    def estimate(self, image):
        calls.append(now[0])
        assert image.ndim == 2
        assert image.shape == advice._estimator._reference.shape
        assert max(image.shape) > 640
        entered.set()
        assert finish.wait(5)
        return (19.0, 2.23, 27.0)
    monkeypatch.setattr(DisplayMotionEstimator, 'estimate', estimate)
    advice = TrackingAdvice(reference, quad)
    try:
        advice.observe(reference, lost=True, now=0)
        now[0] = 3
        advice.observe(reference, lost=True, now=now[0])
        assert entered.wait(2)
        now[0] = 9
        finish.set()
        collect(advice, now[0])
        advice.observe(reference, lost=True, now=now[0])
        collect(advice, now[0])
        assert calls == [3]
        now[0] = 11
        advice.observe(reference, lost=True, now=now[0])
        collect(advice, now[0])
        assert calls == [3, 11]
    finally:
        finish.set()
        advice.close()


REAL_MOTION = Path(__file__).parent / 'fixtures/r13/display-motion-20261023'


@pytest.mark.parametrize('resolution', [1, 2])
@pytest.mark.parametrize('name', ['moved-0121', 'moved-0161', 'moved-0201', 'unmoved', 'occluded'])
def test_real_move_native_crop(name, resolution):
    note = json.loads((REAL_MOTION / 'sources.json').read_text())
    reference = cv2.imread(str(REAL_MOTION / 'reference.jpg'))
    image = cv2.imread(str(REAL_MOTION / f'{name}.jpg'))
    if resolution != 1:
        reference = cv2.resize(reference, None, fx=resolution, fy=resolution)
        image = cv2.resize(image, None, fx=resolution, fy=resolution)
    advice = TrackingAdvice(reference, np.array(note['quad']) * resolution,
                            region_centres=np.array(note['region_centres']) * resolution)
    try:
        advice.observe(image, lost=True, now=0)
        advice.observe(image, lost=True, now=3)
        hint = collect(advice, 3)
        if name.startswith('moved'):
            assert hint['kind'] == 'anzeige_bewegt'
            assert hint['shift_px'] == pytest.approx(19 * resolution, abs=3 * resolution)
            assert 20 * resolution < hint['region_shift_px'] < 30 * resolution
            assert hint['rotation_deg'] == pytest.approx(-2.23, abs=0.3)
        else:
            assert hint is None or hint['kind'] != 'anzeige_bewegt'
            advice.observe(image, lost=True, now=10)
            assert collect(advice, 10)['kind'] in ('unbekannt', 'rahmen_verdeckt')
    finally:
        advice.close()


def test_rotation_with_small_centre_shift_exceeds_region_search_radius():
    # Centre stays still and corners stay within 12 px, but confirmed regions
    # outside the quad move past the search radius under a 2.2-degree rotation.
    reference, quad, moved = transformed_scene(dx=0, angle=2.2)
    centres = [quad.mean(axis=0) + (400, 0)]
    advice = TrackingAdvice(reference, quad, region_centres=centres)
    try:
        advice.observe(moved, lost=True, now=0)
        advice.observe(moved, lost=True, now=3)
        hint = collect(advice, 3)
        assert hint['kind'] == 'anzeige_bewegt'
        assert hint['region_shift_px'] > 12
    finally:
        advice.close()
