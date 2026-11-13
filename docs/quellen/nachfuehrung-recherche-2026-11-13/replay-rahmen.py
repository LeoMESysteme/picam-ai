"""Offline: PYTHONPATH=src ./.venv/bin/python replay-rahmen.py <Lauf-ID> ..."""
import json
import statistics
import sys
from pathlib import Path

import cv2

from dispread.live.frame_tracking import FrameTracker, FrameTrackingConfig, RegionProposal

for ident in sys.argv[1:]:
    root = Path('var/live') / ('live-' + ident)
    profile = json.loads((root / 'profile.json').read_text())
    block = profile['live_tracking']
    tracker = FrameTracker(cv2.imread(str(root / 'setup/still.png')), profile['quad'],
                           RegionProposal.from_dict(block['proposal']), FrameTrackingConfig.from_dict(block['config']))
    images = root / 'run-01/diagnose'
    rows = [json.loads(line) for line in (images / 'images.jsonl').read_text().splitlines()]
    scales = []
    mismatch = retries = 0
    for row in rows:
        image = cv2.imread(str(images / row['image']))
        if image is None:
            raise ValueError(f"Bild fehlt: {row['image']}")
        result = tracker.update(image)
        coarse = tracker.last_coarse
        if coarse and coarse.used:
            retries += 1
            if coarse.scale is not None:
                scales.append(coarse.scale)
        mismatch += result.reason != row['tracking']['reason']
    print(ident, 'n', len(rows), 'retry', retries, 'scale n', len(scales), 'min median max',
          (min(scales), statistics.median(scales), max(scales)) if scales else None, 'mismatch', mismatch, flush=True)
