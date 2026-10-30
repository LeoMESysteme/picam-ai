"""Gespeicherte R13-Entwicklungsbilder fuer Integrationstests, ohne Hardware."""

import hashlib
import json
from pathlib import Path

import cv2

from dispread.live.frame_tracking import FrameTrackingConfig, propose_regions

FIXTURES = Path(__file__).parent / "fixtures" / "r13"


def reference_scene():
    image = cv2.imread(str(FIXTURES / "reference.jpg"))
    quad = json.loads((FIXTURES / "r13-fixtures.json").read_text())["quad"]
    return image, quad


def tracking_block(image, quad, frame_path, revision="review-1"):
    return {
        "version": 1, "method": "rahmenbereiche", "config": FrameTrackingConfig().to_dict(),
        "proposal": propose_regions(image, quad).to_dict(),
        "frame_sha256": hashlib.sha256(frame_path.read_bytes()).hexdigest(),
        "proposal_revision": revision,
    }
