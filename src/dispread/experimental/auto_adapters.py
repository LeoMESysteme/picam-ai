"""Offline experimental adapters; never used by production release/output paths.

Neither detection nor recognition accepts labels, reference values, or a device
layout. Geometric scores are heuristics, not probabilities. OCR text supplies no
segment evidence, even when it parses as a number.
"""
from __future__ import annotations

import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from dispread.detect import DisplayCandidate, Quad
from dispread.frames.types import Frame
from dispread.ocr import ReadResult
from dispread.rectify import DisplayCrop
from dispread.workbench.vision import (
    DetectionConfig,
    _cluster_by_vertical_center,
    _digit_blobs,
    _threshold_variants,
    find_display_candidates,
    fit_quad_in_region,
)


class GeometricLocator:
    """Untuned rectangular-region proposals in original image coordinates.

    Multiple rows stay separate candidates; rectangle shape cannot tell which
    row the user wants, or even whether an object is a numeric display.
    """
    locator_id = "experimental-geometric"

    def __init__(self, config: DetectionConfig = DetectionConfig()):
        self.config = config

    def locate(self, frame: Frame) -> tuple[DisplayCandidate, ...]:
        image = frame.image
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        height, width = image.shape[:2]
        found = []
        for x, y, w, h in find_display_candidates(image, self.config):
            normalized = fit_quad_in_region(image, (x / width, y / height, w / width, h / height), self.config)
            if normalized is None:
                quad = ((x, y), (x + w - 1, y), (x + w - 1, y + h - 1), (x, y + h - 1))
            else:
                quad = tuple((float(px * width), float(py * height)) for px, py in normalized)
            # Rotated min-area rectangles can extend beyond the raw frame.
            if any(px < 0 or py < 0 or px > width - 1 or py > height - 1 for px, py in quad):
                continue
            found.append(DisplayCandidate(quad=quad, score=0.0, locator_id=self.locator_id))
        return tuple(found)


def rectify_candidate(image: np.ndarray, candidate: DisplayCandidate) -> DisplayCrop:
    """Warp directly from raw pixels, retaining the longest opposing edges.

    Pixel-center coordinates are inclusive: a 0..300 edge spans 301 pixels.
    The returned homography maps original coordinates to crop coordinates.
    DisplayCandidate already supplies cyclic TL/TR/BR/BL order. Preserve that
    order: sum/difference ordering duplicates vertices for 45-degree diamonds.
    """
    points = np.asarray(candidate.quad, dtype=np.float32)
    h, w = image.shape[:2]
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError("invalid quadrilateral")
    if ((points < 0).any() or (points[:, 0] > w - 1).any() or (points[:, 1] > h - 1).any()):
        raise ValueError("quadrilateral lies outside original image")
    if not cv2.isContourConvex(points) or cv2.contourArea(points) < 1:
        raise ValueError("degenerate quadrilateral")
    top, right, bottom, left = (float(np.linalg.norm(points[(i + 1) % 4] - points[i])) for i in range(4))
    size = (max(2, int(round(max(top, bottom))) + 1), max(2, int(round(max(left, right))) + 1))
    width, height = size
    destination = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
    matrix = cv2.getPerspectiveTransform(points, destination)
    warped = cv2.warpPerspective(image, matrix, size, flags=cv2.INTER_LINEAR)
    gray = warped if warped.ndim == 2 else cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    return DisplayCrop(
        image=warped, source_quad=candidate.quad,
        homography=tuple(float(value) for value in matrix.ravel()),
        sharpness=float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        saturated_fraction=float((gray >= 250).mean()),
        clipped_dark_fraction=float((gray <= 5).mean()),
        diagnostics={"target_size": [width, height], "enhanced": False, "original_quad_order": True},
    )


@dataclass(frozen=True, slots=True)
class GeometryResult:
    """Tentative digit boxes in crop pixels; no inferred unlit segments.

    This first adapter identifies blob rows, not seven-segment topology. The
    digit boxes are proposals only; ready stays false until topology is solved.
    """
    digit_quads: tuple[Quad, ...]
    segment_quads: tuple[Quad, ...]
    ready: bool
    uncertainty: str


def infer_geometry(crop: np.ndarray) -> GeometryResult:
    """Expose only image-supported tentative digit extents, never a text grid."""
    if crop.size == 0:
        return GeometryResult((), (), False, "empty crop")
    gray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    height, _ = gray.shape
    rows = []
    for mask in _threshold_variants(gray):
        blobs = _digit_blobs(mask, height * .15, height * .95, max(3, round(height * .04)))
        blobs = [box for box in blobs if .12 <= box[2] / box[3] <= 1.0]
        rows.extend(row for row in _cluster_by_vertical_center(blobs, height) if len(row) >= 2)
    if len(rows) != 1:
        return GeometryResult((), (), False, "ambiguous or missing digit row")
    quads = tuple(
        ((float(x), float(y)), (float(x + w - 1), float(y)),
         (float(x + w - 1), float(y + h - 1)), (float(x), float(y + h - 1)))
        for x, y, w, h in sorted(rows[0])
    )
    return GeometryResult(quads, (), False, "tentative digit blobs only; segment topology unresolved")


def numeric_result(raw: str, backend_id: str, backend_version: str = "1", reason: str | None = None) -> ReadResult:
    """Parse complete numeric OCR output without discarding unknown characters.

    ``decimal_point_index`` identifies the preceding digit, counting from zero;
    -1 explicitly denotes a leading decimal point with no preceding digit.
    """
    text = raw.strip()
    accepted = reason is None and re.fullmatch(r"[+-]?(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)", text) is not None
    value = float(text.replace(",", ".")) if accepted else None
    if value is not None and not math.isfinite(value):
        accepted, value = False, None
    unsigned = text.lstrip("+-").replace(",", ".")
    decimal_index = unsigned.index(".") - 1 if accepted and "." in unsigned else None
    return ReadResult(
        raw_text=text, value=value, sign_detected=accepted and text.startswith("-"),
        sign_region_readable=accepted, decimal_point_detected=decimal_index is not None,
        decimal_point_index=decimal_index, unit_text=None, status_flags=frozenset(),
        glyphs=(), backend_id=backend_id, backend_version=backend_version,
        diagnostics={"experimental": True, "declares_confidence_calibrated": False,
                     "segment_evidence": "unavailable",
                     "rejection_reason": None if accepted else reason or "non_numeric_or_ambiguous_text"},
    )


class TesseractAdapter:
    """Strict numeric OCR subprocess with independent state for every crop.

    No character whitelist: suppressing unknown text can turn an invalid input
    into a plausible number. PSM 7 is a frozen single-row development default.
    """
    declares_confidence_calibrated = False
    backend_version = "1"

    def __init__(self, model_path: Path, timeout_s: float = 5.0):
        self.model_path = Path(model_path).resolve()
        if not self.model_path.is_file():
            raise FileNotFoundError(self.model_path)
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("timeout must be positive and finite")
        self.timeout_s = timeout_s
        self.backend_id = f"experimental-tesseract-{self.model_path.stem}"

    def _result(self, raw: str, reason: str | None = None) -> ReadResult:
        result = numeric_result(raw, self.backend_id, self.backend_version, reason)
        result.diagnostics["psm"] = 7
        return result

    def read(self, crop: np.ndarray) -> ReadResult:
        if crop.size == 0:
            return self._result("", "empty_crop")
        gray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if float(gray.std()) < 1.0:
            return self._result("", "insufficient_image_contrast")
        encoded, data = cv2.imencode(".png", crop)
        if not encoded:
            return self._result("", "image_encoding_failed")
        command = ["tesseract", "stdin", "stdout", "--tessdata-dir", str(self.model_path.parent),
                   "-l", self.model_path.stem, "--oem", "1", "--psm", "7"]
        try:
            completed = subprocess.run(command, input=data.tobytes(), capture_output=True, timeout=self.timeout_s,
                                       check=False)
        except subprocess.TimeoutExpired:
            return self._result("", "timeout")
        except OSError:
            return self._result("", "tesseract_unavailable")
        if completed.returncode:
            return self._result("", "tesseract_failed")
        return self._result(completed.stdout.decode("utf-8", errors="replace"))
