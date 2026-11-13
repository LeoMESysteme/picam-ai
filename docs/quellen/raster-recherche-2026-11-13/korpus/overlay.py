#!/usr/bin/env python3
"""Save inspectable rectification and grid for selected stored result paths."""
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np

cv2.setNumThreads(1)
manifest = {row['path']: row for row in (json.loads(line) for line in
            (Path(__file__).parent / 'manifest.jsonl').read_text().splitlines())}
out = Path(__file__).parent / 'overlays'
out.mkdir(exist_ok=True)
for line in Path(sys.argv[1]).read_text().splitlines():
    rec = json.loads(line)
    if rec.get('result') != 'fit' or not any(x in rec['path'] for x in sys.argv[2:]):
        continue
    path = Path(rec['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != rec['sha256']:
        raise ValueError(f'image changed: {path}')
    label = path.parent / 'cell-text.json'
    if hashlib.sha256(label.read_bytes()).hexdigest() != manifest[rec['path']]['cell_text_sha256']:
        raise ValueError(f'cell text changed: {label}')
    image = cv2.imread(str(path))
    # Output coordinates preserve the 399/159 pixel-centre quad convention.
    target = np.float32([[0, 0], [1596, 0], [1596, 636], [0, 636]])
    transform = cv2.getPerspectiveTransform(np.float32(rec['fit']['quad']), target)
    rectified = cv2.warpPerspective(image, transform, (1600, 640))
    grid = rectified.copy()
    for cell in range(16):
        cv2.line(grid, (cell * 100, 0), (cell * 100, 639), (0, 180, 255), 1)
        for col in range(5):
            for row in range(7):
                x = round((cell * 25 + (col + .5) * 25 / 6) * 4)
                y = round((160 / 9 + (row + .5) * 160 / 9) * 4)
                cv2.circle(grid, (x, y), 3, (255, 80, 0), 1)
        cv2.putText(grid, str(cell), (cell * 100 + 3, 25), cv2.FONT_HERSHEY_SIMPLEX,
                    .55, (0, 180, 255), 1, cv2.LINE_AA)
    text = (rec.get('label') or {}).get('masked', 'no label')
    caption = np.full((50, 1600, 3), 245, np.uint8)
    cv2.putText(caption, f'{path.parent.parent.name}/{path.name}  serial: {text}',
                (10, 32), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 0, 0), 2, cv2.LINE_AA)
    output = out / f'{path.parent.parent.name}-{path.stem}.png'
    cv2.imwrite(str(output), np.vstack((caption, rectified, grid)))
    print(output)
