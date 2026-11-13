"""Regression der am Verlust-/Wiederkehrwechsel gespeicherten 13.11.-Bilder."""
import json
from pathlib import Path

import cv2
import pytest

from dispread.live.frame_tracking import FrameTracker, FrameTrackingConfig, RegionProposal


def test_13nov_diagnostic_images_keep_recorded_tracking_decisions():
    root = Path('var/live/live-20261113T113119Z')
    index = root / 'run-01/diagnose/images.jsonl'
    if not index.exists():
        pytest.skip('lokale Diagnosebilder nicht vorhanden')
    profile = json.loads((root / 'profile.json').read_text())
    block = profile['live_tracking']
    tracker = FrameTracker(cv2.imread(str(root / 'setup/still.png')), profile['quad'],
                           RegionProposal.from_dict(block['proposal']), FrameTrackingConfig.from_dict(block['config']))
    rows = [json.loads(line) for line in index.read_text().splitlines()]
    assert len(rows) == 216
    for row in rows:
        image = cv2.imread(str(index.parent / row['image']))
        assert image is not None
        assert tracker.update(image).reason == row['tracking']['reason'], row['image']
