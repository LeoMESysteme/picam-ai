#!/usr/bin/env python3
"""Offline corpus inventory and fit evaluation; JSONL is append-flushed per image."""
import dataclasses
import hashlib
import json
import os
import re
import time
from pathlib import Path

import cv2

import dispread.dotlattice as dotlattice_module
from dispread.dotlattice import LatticeFit, fit_lattice
from dispread.setup_checks import raster_offset_check
from dispread.setup_hint import find_green_hint_box

cv2.setNumThreads(1)
HYPOTHESIS_SHA256 = hashlib.sha256(Path(dotlattice_module.__file__).read_bytes()).hexdigest()
expected_code = os.environ.get('RASTER_CODE_SHA256')
if not expected_code or expected_code != HYPOTHESIS_SHA256:
    raise ValueError(f'RASTER_CODE_SHA256 mismatch: loaded {dotlattice_module.__file__} ({HYPOTHESIS_SHA256})')

ROOT = Path.cwd()
OUT = Path(__file__).resolve().parent
EMPTY = (8, 13, 14, 15)
paths = sorted(ROOT.glob('var/live/*/setup/still*.png'))
dev = Path(os.environ.get('DISPREAD_DEV_DATA', '/mnt/ssd/picam-dev'))
paths += sorted((dev / 'regression/2026-11-11').glob('*/still.png'))
variant = os.environ.get('RASTER_VARIANT', 'baseline')
if not re.fullmatch(r'[a-zA-Z0-9_-]+', variant):
    raise ValueError('invalid RASTER_VARIANT')
shard = int(os.environ.get('RASTER_SHARD', '0'))
shards = int(os.environ.get('RASTER_SHARDS', '1'))
output = OUT / f'{variant}-shard-{shard}.jsonl'
manifest = [json.loads(line) for line in (OUT / 'manifest.jsonl').read_text().splitlines()]
expected = {r['path']: r for r in manifest}
if len(expected) != len(manifest):
    raise ValueError('manifest contains duplicate paths')


def path_key(path):
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


# Check the whole corpus before looking at any existing output or shard.
# This also checks paths already present in a resumed result file.
discovered = {path_key(path) for path in paths}
if len(discovered) != len(paths) or discovered != expected.keys():
    raise ValueError(f'manifest path mismatch: missing={sorted(expected.keys() - discovered)}, '
                     f'extra={sorted(discovered - expected.keys())}')
for path in paths:
    entry = expected[path_key(path)]
    labels = path.parent / 'cell-text.json'
    image_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    label_hash = hashlib.sha256(labels.read_bytes()).hexdigest() if labels.exists() else None
    if image_hash != entry['sha256'] or label_hash != entry['cell_text_sha256']:
        raise ValueError(f'manifest mismatch: {path_key(path)}')


def validate_row(row):
    if row.get('hypothesis_sha256') != HYPOTHESIS_SHA256:
        raise ValueError('variant output belongs to a different or unlabeled hypothesis')
    entry = expected.get(row.get('path'))
    if entry is None or row.get('sha256') != entry['sha256']:
        raise ValueError(f'manifest mismatch in variant output: {row.get("path")}')


# A variant name identifies all of its shards, not just this process's shard.
# Other processes can be appending; an incomplete last line is read later.
existing = sorted(OUT.glob(f'{variant}-shard-*.jsonl'))
if variant == 'baseline' and (OUT / 'results.jsonl').exists():
    existing.append(OUT / 'results.jsonl')
prior = []
for file in existing:
    data = file.read_text()
    if data and not data.endswith('\n') and (file == output or file.name == 'results.jsonl'):
        raise ValueError(f'incomplete variant output: {file}')
    lines = data.splitlines()
    if data and not data.endswith('\n'):
        try:
            json.loads(lines[-1])
        except json.JSONDecodeError:  # other shard may still be writing
            lines.pop()
    for line in lines:
        row = json.loads(line)
        validate_row(row)
        if file == output or file.name == 'results.jsonl':
            prior.append(row)
done = {r['path'] for r in prior}
first_by_hash = {}
for item in manifest:
    first_by_hash.setdefault((item['sha256'], item['cell_text_sha256']), item['path'])
with output.open('a') as out:
    for i, path in enumerate(paths, 1):
        if (i - 1) % shards != shard:
            continue
        if (str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)) in done:
            continue
        raw = path.read_bytes()
        rec = {'path': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'hypothesis_sha256': HYPOTHESIS_SHA256}
        labels = path.parent / 'cell-text.json'
        entries = json.loads(labels.read_text()) if labels.exists() else []
        attempts = [e for e in entries if e.get('still') == 'still']
        match = re.fullmatch(r'still-versuch-(\d+)', path.stem)
        attempt = int(match.group(1)) if match else max((e.get('attempt', 0) for e in attempts), default=0)
        labels_for_attempt = [e for e in attempts if e.get('attempt') == attempt]
        rec.update(attempt=attempt or None, label=labels_for_attempt[-1] if labels_for_attempt else None)
        if expected.get(rec['path'], {}).get('sha256') != rec['sha256'] or (hashlib.sha256(labels.read_bytes()).hexdigest() if labels.exists() else None) != expected[rec['path']]['cell_text_sha256']:
            raise ValueError(f"manifest mismatch: {rec['path']}")
        original = first_by_hash[(rec['sha256'], expected[rec['path']]['cell_text_sha256'])]
        if original != rec['path']:
            # Earlier input has identical image and text hashes. Wait for the
            # responsible shard instead of fitting the same image twice.
            while True:
                found = None
                files = list(OUT.glob(f'{variant}-shard-*.jsonl')) + ([OUT / 'results.jsonl'] if variant == 'baseline' else [])
                for f in files:
                    if not f.exists():
                        continue
                    for line in f.read_text().splitlines():
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:  # another shard is writing
                            continue
                        if row.get('path') == original:
                            validate_row(row)
                            found = row
                            break
                    if found:
                        break
                if found:
                    found['path'] = rec['path']
                    found['reused_from'] = original
                    out.write(json.dumps(found, ensure_ascii=False) + '\n')
                    out.flush()
                    print(f'{i}/{len(paths)} {rec["path"]}: reused {original}', flush=True)
                    break
                time.sleep(2)
            continue
        try:
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError('imread failed')
            rec['shape'] = list(image.shape)
            hint = find_green_hint_box(image)
            rec['hint_box'] = list(hint) if hint is not None else None
            if hint is None:
                rec['result'] = 'no_hint'
            else:
                fit = fit_lattice(image, hint, empty_cells=EMPTY)
                if isinstance(fit, LatticeFit):
                    rec['result'] = 'fit'
                    rec['fit'] = {k: v for k, v in dataclasses.asdict(fit).items() if k not in ('assigned_points', 'rejected_points')}
                    label = rec['label']
                    if os.environ.get('RASTER_CHECK_OFFSET') == '1' and label and label.get('source') == 'seriell' and label.get('masked') and '?' not in label['masked']:
                        check = raster_offset_check([(image, label['masked'])], fit.quad)
                        rec['serial_offset'] = {'status': check.status, 'reason': check.reason, 'metrics': check.metrics}
                else:
                    rec['result'] = fit
        except Exception as exc:
            rec['error'] = f'{type(exc).__name__}: {exc}'
        out.write(json.dumps(rec, ensure_ascii=False, default=lambda x: x.item() if hasattr(x, 'item') else str(x)) + '\n')
        out.flush()
        print(f'{i}/{len(paths)} {rec["path"]}: {rec.get("result", rec.get("error"))}', flush=True)
