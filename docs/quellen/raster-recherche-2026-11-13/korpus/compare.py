#!/usr/bin/env python3
"""Compare stored per-image results; new fits require independent review."""
import glob
import json
import math
import sys
from pathlib import Path


def load(pattern):
    items = {}
    for file in sorted({name for part in pattern.split(",") for name in glob.glob(part)}):
        for line in Path(file).read_text().splitlines():
            r = json.loads(line)
            if r['path'] in items:
                raise ValueError(f'duplicate: {r["path"]}')
            items[r['path']] = r
    return items

base, variant = map(load, sys.argv[1:3])
if base.keys() != variant.keys():
    raise ValueError(f'mismatching corpus: baseline-only={len(base.keys()-variant.keys())}, variant-only={len(variant.keys()-base.keys())}')
for path in sorted(base):
    a, b = base[path], variant[path]
    if a['sha256'] != b['sha256'] or a.get('label') != b.get('label'):
        raise ValueError(f'changed image or label: {path}')
    old, new = a.get('result'), b.get('result')
    result = {'path': path, 'baseline': old, 'variant': new}
    if old == new == 'fit':
        result['max_corner_shift_px'] = max(math.dist(x, y) for x, y in zip(a['fit']['quad'], b['fit']['quad'], strict=True))
    elif old != 'fit' and new == 'fit':
        result['needs_independent_truth_review'] = True
        result['serial_offset'] = b.get('serial_offset')
    print(json.dumps(result, ensure_ascii=False))
