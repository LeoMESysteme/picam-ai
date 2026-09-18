"""PP-OCR boundary regressions independent of optional model downloads."""
import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest


def adapter_module():
    assert importlib.util.find_spec("dispread.experimental.ppocr_adapter") is not None, "PP-OCR adapter missing"
    from dispread.experimental import ppocr_adapter

    return ppocr_adapter


def test_ctc_preserves_repeated_digits_sign_and_decimal():
    module = adapter_module()
    # Blank=0; adjacent repeats collapse, repeats separated by blank remain.
    characters = ("", "-", "1", ".", "0", "2")
    logits = np.zeros((1, 11, 6), np.float32)
    logits[0, np.arange(11), [1, 1, 2, 2, 0, 2, 3, 3, 4, 5, 0]] = .99
    result = module.decode_numeric_ctc(logits, characters)
    assert result.raw_text == "-11.02"
    assert result.value == -11.02
    assert result.sign_detected
    assert result.decimal_point_index == 1
    assert result.glyphs == ()
    assert result.diagnostics["declares_confidence_calibrated"] is False


@pytest.mark.parametrize("text", ["12 V", "1.2.3", "--12", "1-2", "", "NaN"])
def test_ctc_rejects_unknown_or_ambiguous_text_without_filtering(text):
    module = adapter_module()
    characters = ("", *tuple(dict.fromkeys(text)))
    logits = np.zeros((1, max(1, len(text) * 2), len(characters)), np.float32)
    logits[0, :, 0] = .99
    for index, char in enumerate(text):
        logits[0, index * 2, :] = 0
        logits[0, index * 2, characters.index(char)] = .99
    result = module.decode_numeric_ctc(logits, characters)
    assert result.value is None
    assert result.raw_text == text.strip()


def test_ctc_rejects_uncertain_sign_even_when_mean_score_high():
    module = adapter_module()
    logits = np.zeros((1, 4, 5), np.float32)
    logits[0, np.arange(4), [1, 2, 3, 4]] = [.55, .99, .99, .99]
    result = module.decode_numeric_ctc(logits, ("", "-", "1", "2", "3"))
    assert result.raw_text == "-123"
    assert result.value is None


def test_ctc_rejects_nonfinite_or_wrong_dictionary():
    module = adapter_module()
    for predictions in [np.full((1, 2, 2), np.nan), np.zeros((1, 2, 3))]:
        assert module.decode_numeric_ctc(predictions, ("", "1")).value is None


def test_detector_preprocessing_preserves_bgr_and_stride128():
    module = adapter_module()
    image = np.zeros((480, 640, 3), np.uint8)
    image[:, :, 0] = 255  # Blue input stays in first tensor channel.
    tensor = module.prepare_detection(image)
    assert tensor.shape == (1, 3, 768, 1024)
    assert tensor.dtype == np.float32
    np.testing.assert_allclose(tensor[0, :, 0, 0], [2.2489083, -2.0357143, -1.8044444], rtol=1e-5)


def test_recognition_padding_preserves_aspect_and_normalizes_bgr():
    module = adapter_module()
    image = np.full((24, 48, 3), 255, np.uint8)
    tensor = module.prepare_recognition(image)
    assert tensor.shape == (1, 3, 48, 320)
    assert np.all(tensor[0, :, :, :96] == 1)
    assert np.all(tensor[0, :, :, 96:] == 0)


def test_recognition_does_not_squash_wide_display():
    module = adapter_module()
    tensor = module.prepare_recognition(np.zeros((24, 240, 3), np.uint8))
    assert tensor.shape == (1, 3, 48, 480)
    with pytest.raises(ValueError, match="wide"):
        module.prepare_recognition(np.zeros((10, 1000, 3), np.uint8))


def test_detector_boxes_scale_to_original_pixels_and_keep_rows_separate():
    module = adapter_module()
    probability = np.zeros((100, 200), np.float32)
    probability[10:21, 20:61] = .9
    probability[60:71, 100:141] = .9
    boxes = module.boxes_from_map(probability, (400, 200))
    assert len(boxes) == 2
    centers = sorted(np.asarray(item.quad).mean(axis=0).tolist() for item in boxes)
    np.testing.assert_allclose(centers, [[80, 30], [240, 130]], atol=1)
    # Core box was 80x20 in original image; DB unclip adds 12 per side.
    top = min(boxes, key=lambda item: np.asarray(item.quad)[:, 1].mean())
    np.testing.assert_allclose(np.ptp(np.asarray(top.quad), axis=0), [104, 44], atol=2)
    assert all(item.role_hint is None for item in boxes)


def test_detector_preserves_rotated_quad_and_clips_edges():
    module = adapter_module()
    probability = np.zeros((100, 200), np.float32)
    rectangle = cv2.boxPoints(((100, 50), (70, 12), 15)).astype(np.int32)
    cv2.fillPoly(probability, [rectangle], .95)
    result, = module.boxes_from_map(probability, (400, 200))
    points = np.asarray(result.quad)
    assert abs(points[1, 1] - points[0, 1]) > 10
    assert cv2.isContourConvex(points.astype(np.float32))
    assert ((points >= 0) & (points <= [399, 199])).all()
    assert module.boxes_from_map(np.full((100, 200), np.nan), (400, 200)) == ()


def test_missing_models_fail_with_actionable_error(tmp_path):
    module = adapter_module()
    assert hasattr(module, "PPOCRAdapter"), "runtime adapter missing"
    with pytest.raises(FileNotFoundError, match="inference"):
        module.PPOCRAdapter(tmp_path)


def test_optional_real_onnx_models_read_then_reject_blank():
    module = adapter_module()
    assert hasattr(module, "PPOCRAdapter"), "runtime adapter missing"
    models = Path(__file__).parents[1] / "experiments/automatic_seven_segment/models"
    if not (models / "PP-OCRv5_mobile_rec_onnx/inference.onnx").is_file():
        pytest.skip("optional pinned ONNX weights not downloaded")
    pytest.importorskip("onnxruntime")
    from dispread.frames.types import Frame
    from dispread.records import TimeBaseKind, Timestamp

    adapter = module.PPOCRAdapter(models)
    image = np.full((100, 400, 3), 255, np.uint8)
    cv2.putText(image, "-12.3", (20, 72), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    result = adapter.read(image)
    assert result.raw_text == "-12.3"
    assert result.value == -12.3
    assert result.glyphs == ()
    frame = Frame(1, image, Timestamp(0, TimeBaseKind.SYNTHETIC), "synthetic-test")
    detections = adapter.locate(frame)
    assert len(detections) >= 1
    assert all(item.locator_id == module.LOCATOR_ID for item in detections)
    blank = adapter.read(np.full_like(image, 255))
    assert blank.value is None
    assert blank.raw_text == ""
    assert adapter.declares_confidence_calibrated is False
