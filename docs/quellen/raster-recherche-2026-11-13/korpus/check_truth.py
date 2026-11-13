#!/usr/bin/env python3
"""Check already computed quads by serial text, without repeating the fit.

Usage: check_truth.py results.jsonl [path-fragment ...]
"""
import hashlib
import json
import sys
from pathlib import Path

import cv2

from dispread.setup_checks import diagnose_reader, raster_offset_check

cv2.setNumThreads(1)
templates = Path('var/dotmatrix/templates-stufe2c-2026-09-30.json')
template_hash = hashlib.sha256(templates.read_bytes()).hexdigest() if templates.exists() else None
manifest = {row['path']: row for row in (json.loads(line) for line in (Path(__file__).parent / 'manifest.jsonl').read_text().splitlines())}
for line in Path(sys.argv[1]).read_text().splitlines():
    rec = json.loads(line)
    if rec.get('result') != 'fit' or (len(sys.argv) > 2 and not any(x in rec['path'] for x in sys.argv[2:])):
        continue
    label = rec.get('label') or {}
    text = label.get('masked')
    if label.get('source') != 'seriell' or not text or '?' in text:
        print(json.dumps({'path': rec['path'], 'truth': 'not_checked', 'reason': 'missing_complete_serial_label'}))
        continue
    path = Path(rec['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != rec['sha256']:
        raise ValueError(f'image changed: {path}')
    labels = path.parent / 'cell-text.json'
    label_hash = hashlib.sha256(labels.read_bytes()).hexdigest() if labels.exists() else None
    if label_hash != manifest[rec['path']]['cell_text_sha256']:
        raise ValueError(f'cell text changed: {labels}')
    image = cv2.imread(str(path))
    quad = rec['fit']['quad']
    check = raster_offset_check([(image, text)], quad)
    result = {'path': str(path), 'offset': {'status': check.status, 'reason': check.reason, 'metrics': check.metrics}, 'templates_sha256': template_hash}
    if templates.exists():
        reader = diagnose_reader([(image, text)], quad, templates, template_hash)
        result['reader'] = {'status': reader.status, 'reason': reader.reason, 'metrics': reader.metrics}
    print(json.dumps(result, ensure_ascii=False, default=lambda x: x.item() if hasattr(x, 'item') else str(x)))
