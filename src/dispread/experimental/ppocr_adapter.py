"""Experimental PP-OCRv5 mobile ONNX input/output boundary, CPU only.

Pre/postprocessing follows PaddleOCR at dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf:
ppocr/data/imaug/operators.py (DetResizeForTest), tools/infer/predict_rec.py,
and ppocr/postprocess/{db,rec}_postprocess.py, Apache-2.0. This implementation
uses only NumPy/OpenCV; rectangular DB unclip is evaluated analytically instead
of requiring Shapely/Clipper. See docs/automatic-seven-segment-candidates.md.
No training framework is imported, no reference value is accepted, and no
segment locations are inferred from the output string.
"""
from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path

import cv2
import numpy as np

from dispread.detect import DisplayCandidate
from dispread.experimental.auto_adapters import numeric_result
from dispread.frames.types import Frame
from dispread.ocr import ReadResult

BACKEND_ID = "experimental-ppocrv5-mobile-onnx"
LOCATOR_ID = "experimental-ppocrv5-mobile-db"


def _bgr(image: np.ndarray) -> np.ndarray:
    if image.dtype != np.uint8 or image.size == 0 or image.ndim not in (2, 3):
        raise ValueError("expected nonempty uint8 image")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] != 3:
        raise ValueError("expected BGR or grayscale image")
    return image


def prepare_detection(image: np.ndarray) -> np.ndarray:
    """Pinned config: long side 960, round up to stride 128, BGR CHW."""
    image = _bgr(image)
    height, width = image.shape[:2]
    if height + width < 64:
        raise ValueError("image too small for full-frame detection")
    scale = 960 / max(height, width)
    output_h = max(128, ((int(height * scale) + 127) // 128) * 128)
    output_w = max(128, ((int(width * scale) + 127) // 128) * 128)
    resized = cv2.resize(image, (output_w, output_h)).astype(np.float32) / 255
    normalized = (resized - np.array([.485, .456, .406], np.float32)) / np.array([.229, .224, .225], np.float32)
    return np.ascontiguousarray(normalized.transpose(2, 0, 1)[None])


def prepare_recognition(image: np.ndarray) -> np.ndarray:
    """Pinned dynamic-width recognizer, height 48 and at least 320 columns."""
    image = _bgr(image)
    height, width = image.shape[:2]
    resized_w = math.ceil(48 * width / height)
    if resized_w > 3200:
        raise ValueError("crop too wide for bounded recognition")
    resized = cv2.resize(image, (resized_w, 48)).astype(np.float32)
    normalized = resized.transpose(2, 0, 1) / 127.5 - 1
    tensor = np.zeros((1, 3, 48, max(320, resized_w)), np.float32)
    tensor[0, :, :, :resized_w] = normalized
    return tensor


def decode_numeric_ctc(
    predictions: np.ndarray,
    characters: tuple[str, ...],
    min_character_score: float = .9,
) -> ReadResult:
    """CTC argmax with blank/repeat removal; unknown characters are rejected.

    The lowest retained character score gates the reading so a weak sign or
    decimal cannot hide behind confident digits. This is an uncalibrated
    engineering threshold, not a probability of a correct reading.
    """
    if (predictions.ndim != 3 or predictions.shape[0] != 1
            or predictions.shape[2] != len(characters) or not np.isfinite(predictions).all()
            or predictions.shape[1] == 0 or not characters):
        return numeric_result("", BACKEND_ID, reason="invalid_model_output")
    indices = predictions[0].argmax(axis=1)
    scores = predictions[0].max(axis=1)
    keep = np.ones(len(indices), dtype=bool)
    keep[1:] = indices[1:] != indices[:-1]
    keep &= indices != 0
    text = "".join(characters[int(index)] for index in indices[keep])
    selected = scores[keep]
    minimum = float(selected.min()) if selected.size else 0.0
    reason = "low_character_score" if minimum < min_character_score else None
    result = numeric_result(text, BACKEND_ID, reason=reason)
    result.diagnostics.update({"minimum_character_score": minimum,
                               "mean_character_score": float(selected.mean()) if selected.size else 0.0,
                               "min_character_threshold": min_character_score})
    return result


def _ordered_rectangle(points: np.ndarray) -> np.ndarray:
    # Sorting paired left/right corners avoids duplicate corners for diamonds.
    ordered = points[np.argsort(points[:, 0], kind="stable")]
    left = ordered[:2][np.argsort(ordered[:2, 1])]
    right = ordered[2:][np.argsort(ordered[2:, 1])]
    return np.array([left[0], right[0], right[1], left[1]], dtype=np.float32)


def boxes_from_map(probability: np.ndarray, original_size: tuple[int, int]) -> tuple[DisplayCandidate, ...]:
    """DB quad mode: thresholds .3/.6, unclip 1.5, max 1000 contours.

    Paddle's quad mode first fits a rectangle, offsets its boundary by
    area*1.5/perimeter, then fits a rectangle again. A rectangle expanded by
    that distance on each side has the same enclosing geometry, without
    polygon offset dependencies. Floating-point output avoids integer Clipper
    quantization; this intentional difference is recorded in the report.
    """
    width, height = original_size
    if (probability.ndim != 2 or probability.size == 0 or not np.isfinite(probability).all()
            or width < 2 or height < 2):
        return ()
    map_h, map_w = probability.shape
    contours, _ = cv2.findContours((probability > .3).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours[:1000]:
        center, (box_w, box_h), angle = cv2.minAreaRect(contour)
        if min(box_w, box_h) < 3:
            continue
        points = cv2.boxPoints((center, (box_w, box_h), angle))
        xmin = max(0, int(np.floor(points[:, 0].min())))
        ymin = max(0, int(np.floor(points[:, 1].min())))
        xmax = min(map_w - 1, int(np.ceil(points[:, 0].max())))
        ymax = min(map_h - 1, int(np.ceil(points[:, 1].max())))
        mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
        local = (points - [xmin, ymin]).astype(np.int32)
        cv2.fillPoly(mask, [local], 1)
        score = float(cv2.mean(probability[ymin:ymax + 1, xmin:xmax + 1], mask)[0])
        if score < .6:
            continue
        distance = box_w * box_h * 1.5 / (2 * (box_w + box_h))
        expanded_size = (box_w + 2 * distance, box_h + 2 * distance)
        if min(expanded_size) < 5:
            continue
        points = _ordered_rectangle(cv2.boxPoints((center, expanded_size, angle)))
        points[:, 0] = np.clip(points[:, 0] * width / map_w, 0, width - 1)
        points[:, 1] = np.clip(points[:, 1] * height / map_h, 0, height - 1)
        if not cv2.isContourConvex(points) or cv2.contourArea(points) < 1:
            continue
        quad = tuple((float(x), float(y)) for x, y in points)
        candidates.append(DisplayCandidate(quad=quad, score=score, locator_id=LOCATOR_ID))
    return tuple(candidates)


class PPOCRAdapter:
    """Optional offline reader/detector using pinned official ONNX artifacts.

    Importing this module does not require ONNX Runtime. Constructing this
    explicit experimental adapter loads both CPU sessions; inference never
    opens a camera or performs network access. All crops come from the caller.
    """

    backend_id = BACKEND_ID
    locator_id = LOCATOR_ID
    backend_version = "1"
    declares_confidence_calibrated = False

    def __init__(self, models_dir: Path):
        start = time.perf_counter_ns()
        models_dir = Path(models_dir)
        det_model = models_dir / "PP-OCRv5_mobile_det_onnx/inference.onnx"
        rec_model = models_dir / "PP-OCRv5_mobile_rec_onnx/inference.onnx"
        rec_config = models_dir / "PP-OCRv5_mobile_rec_onnx/inference.yml"
        for artifact in (det_model, rec_model, rec_config):
            if not artifact.is_file():
                raise FileNotFoundError(artifact)
        import onnxruntime as ort
        import yaml

        dictionary = yaml.safe_load(rec_config.read_text(encoding="utf-8"))["PostProcess"]["character_dict"]
        if not isinstance(dictionary, list) or not all(isinstance(char, str) for char in dictionary):
            raise ValueError("invalid recognition dictionary")
        # Official exported dictionary omits CTC blank and trailing space.
        self.characters = ("", *dictionary, " ")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.log_severity_level = 3  # Suppress unused-initializer notices.
        self.detector = ort.InferenceSession(str(det_model), sess_options=options, providers=["CPUExecutionProvider"])
        self.recognizer = ort.InferenceSession(str(rec_model), sess_options=options, providers=["CPUExecutionProvider"])
        if self.recognizer.get_outputs()[0].shape[-1] != len(self.characters):
            raise ValueError("model output and recognition dictionary disagree")
        self.model_hashes = {str(path.relative_to(models_dir)): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in (det_model, rec_model, rec_config)}
        self.runtime_version = ort.__version__
        self.last_detection_error: str | None = None
        self.init_duration_ms = (time.perf_counter_ns() - start) / 1e6

    def locate(self, frame: Frame) -> tuple[DisplayCandidate, ...]:
        self.last_detection_error = None
        try:
            tensor = prepare_detection(frame.image)
            prediction = self.detector.run(None, {self.detector.get_inputs()[0].name: tensor})[0]
            if prediction.ndim != 4 or prediction.shape[:2] != (1, 1):
                raise ValueError("unexpected detector output")
            return boxes_from_map(prediction[0, 0], frame.size)
        except Exception as error:
            # The optional native runtime is an external boundary: a failed
            # frame must not reuse the previous frame's detections.
            self.last_detection_error = type(error).__name__
            return ()

    def read(self, crop: np.ndarray) -> ReadResult:
        try:
            image = _bgr(crop)
            if float(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).std()) < 1:
                return numeric_result("", BACKEND_ID, reason="insufficient_image_evidence")
            tensor = prepare_recognition(image)
            output = self.recognizer.run(None, {self.recognizer.get_inputs()[0].name: tensor})[0]
            return decode_numeric_ctc(output, self.characters)
        except Exception as error:
            return numeric_result("", BACKEND_ID, reason=f"inference_failed:{type(error).__name__}")
