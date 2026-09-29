"""Vorsichtige automatische Hinweisbox fuer gruen hinterleuchtetes Glas."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from dispread.setup_hint import find_green_hint_box


def test_green_display_is_bounded_with_margin():
    image = np.full((200, 400, 3), 100, dtype=np.uint8)
    image[70:120, 80:280] = (30, 160, 45)
    for row in range(3):
        for col in range(12):
            cv2.circle(image, (95 + col * 14, 80 + row * 13), 2, (0, 35, 0), -1)
    box = find_green_hint_box(image)
    assert box is not None
    x, y, w, h = box
    assert x < 80 / 400
    assert y < 80 / 200
    assert x + w > 280 / 400
    assert y + h > 106 / 200


def test_missing_green_area_is_rejected():
    image = np.full((200, 400, 3), 120, dtype=np.uint8)
    assert find_green_hint_box(image) is None


def test_tiny_green_reflection_is_rejected():
    image = np.full((200, 400, 3), 120, dtype=np.uint8)
    image[50:55, 50:55] = (0, 255, 0)
    assert find_green_hint_box(image) is None


def test_plain_green_panel_without_dots_is_rejected():
    image = np.full((200, 400, 3), 100, dtype=np.uint8)
    image[70:120, 80:280] = (30, 160, 45)
    assert find_green_hint_box(image) is None


@pytest.mark.parametrize("name", ["sc3", "sc4", "sc5", "ab1", "ab2"])
def test_real_green_hint_encloses_text_region(name):
    root = Path("/home/me-systeme/picam-ai/var/diagnostics")
    frame = root / f"{name}-still/frames/frame_000017.png"
    profile = root / f"{name if name != 'sc3' else 'sc3b'}-profile"
    if not frame.exists() or not profile.exists():
        pytest.skip("Standbild oder Profil fehlt")
    image = cv2.imread(str(frame))
    box = find_green_hint_box(image)
    assert box is not None
    quad = json.loads(profile.read_text())["quad"]
    ys = [point[1] for point in quad]
    profile_top = (min(ys) - .1 * (max(ys) - min(ys))) / image.shape[0]
    profile_bottom = (max(ys) + .1 * (max(ys) - min(ys))) / image.shape[0]
    assert abs(box[1] - profile_top) < .01
    assert abs(box[1] + box[3] - profile_bottom) < .01
