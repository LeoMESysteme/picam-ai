"""Experimental adapters never turn missing evidence into a current reading."""
import subprocess

import cv2
import numpy as np
import pytest

from dispread.detect import DisplayCandidate, DisplayLocator
from dispread.experimental import auto_adapters as adapters
from dispread.frames.types import Frame
from dispread.records import TimeBaseKind, Timestamp


def candidate(quad):
    return DisplayCandidate(quad=quad, score=1.0, locator_id="test")


def test_rectification_preserves_original_pixel_scale_and_round_trip():
    image = np.zeros((300, 500, 3), dtype=np.uint8)
    image[80:181, 100:401] = (20, 100, 200)
    display = candidate(((100., 80.), (400., 80.), (400., 180.), (100., 180.)))
    crop = adapters.rectify_candidate(image, display)
    assert crop.image.shape == (101, 301, 3)
    assert tuple(crop.image[50, 150]) == (20, 100, 200)
    matrix = np.array(crop.homography).reshape(3, 3)
    projected = cv2.perspectiveTransform(np.array([[[0., 0.], [300., 100.]]]), np.linalg.inv(matrix))
    np.testing.assert_allclose(projected, [[[100., 80.], [400., 180.]]], atol=1e-5)


@pytest.mark.parametrize("quad", [((0., 0.),) * 4, ((-5., 0.), (20., 0.), (20., 10.), (-5., 10.))])
def test_rectification_rejects_degenerate_or_out_of_frame_quad(quad):
    with pytest.raises(ValueError):
        adapters.rectify_candidate(np.zeros((50, 50, 3), np.uint8), candidate(quad))


def test_locator_reports_original_coordinates_for_multiple_rows():
    image = np.zeros((600, 1000, 3), np.uint8)
    cv2.rectangle(image, (250, 100), (650, 200), (255, 255, 255), 3)
    cv2.rectangle(image, (250, 300), (650, 400), (255, 255, 255), 3)
    frame = Frame(0, image, Timestamp(0, TimeBaseKind.SYNTHETIC), "test")
    locator = adapters.GeometricLocator()
    assert isinstance(locator, DisplayLocator)
    found = locator.locate(frame)
    assert len(found) == 2
    centers = sorted(np.mean(item.quad, axis=0).tolist() for item in found)
    np.testing.assert_allclose(centers, [[450, 150], [450, 350]], atol=5)
    assert all(item.role_hint is None for item in found)


@pytest.mark.parametrize("raw, value, negative, decimal_index", [
    ("-12,30\n", -12.3, True, 1), ("+0.04\n", 0.04, False, 0), ("123\n", 123., False, None),
    (".123\n", .123, False, -1), ("-.123\n", -.123, True, -1),
])
def test_numeric_parsing_preserves_sign_and_decimal(monkeypatch, tmp_path, raw, value, negative, decimal_index):
    model = tmp_path / "ssd.traineddata"
    model.write_bytes(b"test fixture")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0, raw.encode(), b""))
    reader = adapters.TesseractAdapter(model)
    result = reader.read(np.tile(np.arange(80, dtype=np.uint8), (30, 1)))
    assert result.value == value
    assert result.sign_detected is negative
    assert result.decimal_point_index == decimal_index
    assert result.raw_text == raw.strip()
    assert not reader.declares_confidence_calibrated
    assert not result.glyphs  # A recognized string is not measured segment evidence.


@pytest.mark.parametrize("raw", ["1 23", "12V", "1.2.3", "12\n34", "--1", "", "1e3", "NaN", ".", "-.", ","])
def test_unknown_or_ambiguous_text_is_rejected_without_cleanup(monkeypatch, tmp_path, raw):
    model = tmp_path / "ssd.traineddata"
    model.write_bytes(b"test fixture")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0, raw.encode(), b""))
    result = adapters.TesseractAdapter(model).read(np.tile(np.arange(80, dtype=np.uint8), (30, 1)))
    assert result.value is None
    assert not result.sign_region_readable
    assert result.diagnostics["rejection_reason"]


def test_read_after_timeout_does_not_reuse_last_value(monkeypatch, tmp_path):
    model = tmp_path / "ssd.traineddata"
    model.write_bytes(b"test fixture")
    responses = iter([b"12.3\n", None])
    def execute(*args, **kwargs):
        output = next(responses)
        if output is None:
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
        return subprocess.CompletedProcess(args[0], 0, output, b"")
    monkeypatch.setattr(subprocess, "run", execute)
    reader = adapters.TesseractAdapter(model)
    image = np.tile(np.arange(80, dtype=np.uint8), (30, 1))
    assert reader.read(image).value == 12.3
    failed = reader.read(image)
    assert failed.value is None
    assert failed.raw_text == ""
    assert failed.diagnostics["rejection_reason"] == "timeout"


def test_geometry_keeps_missing_segment_evidence_missing():
    image = np.zeros((100, 200), np.uint8)
    cv2.rectangle(image, (20, 20), (40, 80), 255, -1)
    cv2.rectangle(image, (70, 20), (90, 80), 255, -1)
    result = adapters.infer_geometry(image)
    assert len(result.digit_quads) == 2
    assert not result.segment_quads
    assert not result.ready
    assert result.uncertainty


def test_geometry_ambiguous_rows_are_unready():
    image = np.zeros((200, 200), np.uint8)
    for y in (20, 120):
        for x in (20, 70):
            cv2.rectangle(image, (x, y), (x + 20, y + 50), 255, -1)
    result = adapters.infer_geometry(image)
    assert not result.ready
    assert not result.digit_quads
    assert "row" in result.uncertainty


def test_blank_geometry_is_unready():
    result = adapters.infer_geometry(np.zeros((100, 200), np.uint8))
    assert not result.ready
    assert not result.digit_quads
    assert not result.segment_quads


def test_uniform_image_rejects_numeric_hallucination(monkeypatch, tmp_path):
    model = tmp_path / "ssd.traineddata"
    model.write_bytes(b"test fixture")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0, b"1\n", b""))
    result = adapters.TesseractAdapter(model).read(np.full((80, 240), 255, np.uint8))
    assert result.value is None
    assert result.diagnostics["rejection_reason"] == "insufficient_image_contrast"


def test_rectification_preserves_all_corners_for_real_development_diamond():
    # PP-OCR detection on rnd-1100, candidate 33. Sum/difference ordering
    # picked the same vertex twice even though this ordered quad is convex.
    quad = ((833.4375610351562, 119.25003051757812),
            (839.8126220703125, 125.62503051757812),
            (833.9063110351562, 131.53126525878906),
            (827.53125, 125.15628051757812))
    image = np.full((720, 960, 3), (20, 100, 200), dtype=np.uint8)
    crop = adapters.rectify_candidate(image, candidate(quad))
    assert crop.image.shape == (9, 10, 3)
    matrix = np.asarray(crop.homography).reshape(3, 3)
    projected = cv2.perspectiveTransform(np.array([quad]), matrix)
    np.testing.assert_allclose(projected, [[[0, 0], [9, 0], [9, 8], [0, 8]]], atol=1e-4)
    assert tuple(crop.image[4, 5]) == (20, 100, 200)
