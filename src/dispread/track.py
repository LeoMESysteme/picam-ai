"""Bounded geometric re-registration tracking for a confirmed display quad.

Two construction rules that prevent common pitfalls:

1. **Always register against the confirmation reference image, never against
   the previous frame.** A chain of frame-to-frame registrations accumulates
   drift; after an hour, the geometry would be far from the confirmed quad
   without any single registration ever violating the bounds.

2. **The working image is rectified in one step directly from the raw image**,
   with `target_size=work_size` — not from the already-CROP_SIZE-rectified
   crop. Otherwise ECC registers on a twice-resampled image and measures
   resampling artifacts as motion (OQ-23 notes the double resize in
   `rectify()`→`crop_box()` as its own sharpness-loss source).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from dispread.detect import Quad
from dispread.rectify import rectify


@dataclass(frozen=True, slots=True)
class TrackConfig:
    #: Allowed shift, as a fraction of working width. Pre-confirmation default.
    max_shift: float = 0.10
    max_rotation_deg: float = 3.0
    min_score: float = 0.60
    work_size: tuple[int, int] = (200, 80)
    iterations: int = 30
    epsilon: float = 1e-4


@dataclass(frozen=True, slots=True)
class TrackResult:
    quad: Quad | None  # None = bound violated, do not correct
    shift: float
    rotation_deg: float
    score: float
    reason: str | None


class QuadTracker:
    """Re-registers a confirmed quad against new images."""

    def __init__(self, image, quad, *, config=TrackConfig()):
        self.config = config
        self.quad = tuple((float(x), float(y)) for x, y in quad)
        self.reference = self._patch(image)

    def _patch(self, image):
        """Rectify the image at the current quad and convert to normalized grayscale."""
        # Single-step rectification directly from the raw image at work_size —
        # not via the already-CROP_SIZE-rectified crop, else ECC measures
        # resampling artifacts as motion.
        crop = rectify(image, self.quad, target_size=self.config.work_size)
        gray = crop.image if crop.image.ndim == 2 else cv2.cvtColor(crop.image, cv2.COLOR_BGR2GRAY)
        return gray.astype(np.float32) / 255.0

    def update(self, image) -> TrackResult:
        """Register the current image and return the adjusted quad if bounds are met."""
        current = self._patch(image)
        warp = np.eye(2, 3, dtype=np.float32)
        try:
            score, warp = cv2.findTransformECC(
                self.reference, current, warp, cv2.MOTION_EUCLIDEAN,
                (
                    cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                    self.config.iterations,
                    self.config.epsilon,
                ),
                None,
                5,
            )
        except cv2.error:
            # ECC diverges when the image no longer structurally matches
            # (display obscured, lights off). This is not an error but the
            # finding "not found" — and leads to rejection.
            return TrackResult(None, 0.0, 0.0, 0.0, "ecc_diverged")

        rotation_deg = float(np.degrees(np.arctan2(warp[1, 0], warp[0, 0])))
        shift = float(np.hypot(warp[0, 2], warp[1, 2])) / self.config.work_size[0]

        # Check bounds first, then score: a violated bound is not corrected
        # but reported. Rejection is the safe direction (Konzept.md §7), and
        # the operator gets the reason in plain text.
        if shift > self.config.max_shift:
            return TrackResult(None, shift, rotation_deg, float(score), "shift_out_of_bounds")
        if abs(rotation_deg) > self.config.max_rotation_deg:
            return TrackResult(None, shift, rotation_deg, float(score), "rotation_out_of_bounds")
        if score < self.config.min_score:
            return TrackResult(None, shift, rotation_deg, float(score), "low_score")

        return TrackResult(self._moved_quad(warp), shift, rotation_deg, float(score), None)

    def _moved_quad(self, warp):
        """Map the motion from work space back to image coordinates.

        `findTransformECC(reference, current, ...)` returns the transformation
        that aligns the current image to the reference. We seek the inverse:
        where the display *is* now. Hence the inverted affine transformation.

        Which direction is which is pinned by `test_kleine_verschiebung_wird_nachgefuehrt`:
        the corrected quad must follow the display. If the sign is wrong, the
        quad tracks backward and the test fails.
        """
        width, height = self.config.work_size
        corners = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
        inverse = cv2.invertAffineTransform(warp)
        # Negate the translation to get the correct direction
        inverse[:, 2] = -inverse[:, 2]
        moved = cv2.transform(corners.reshape(-1, 1, 2), inverse).reshape(-1, 2)
        to_image = cv2.getPerspectiveTransform(corners, np.float32(self.quad))
        points = cv2.perspectiveTransform(moved.reshape(-1, 1, 2).astype(np.float32), to_image)
        return tuple((float(x), float(y)) for x, y in points.reshape(-1, 2))
