"""Strict offline scoring. Labels stay here, never enter detector/reader calls."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

_NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:[.][0-9]+)?|[.][0-9]+)\Z')


def normalise(text: str) -> str:
    return text.strip().replace(',', '.')


def compare_text(expected: str | None, actual: str | None) -> dict:
    if actual is None:
        return {'outcome': 'rejected', 'errors': []}
    actual = normalise(actual)
    if expected is None:
        return {'outcome': 'wrong', 'errors': ['unreadable_accepted']}
    expected = normalise(expected)
    if actual == expected:
        return {'outcome': 'correct', 'errors': []}
    if not _NUMBER.fullmatch(actual):
        return {'outcome': 'wrong', 'errors': ['invalid_text']}
    errors = []
    def sign(text):
        return text[0] if text[0] in '+-' else ''
    if sign(expected) != sign(actual):
        errors.append('sign')
    lhs, rhs = expected.lstrip('+-'), actual.lstrip('+-')
    def decimal(text):
        return len(text.split('.')[1]) if '.' in text else None
    if decimal(lhs) != decimal(rhs):
        errors.append('decimal')
    digits_l, digits_r = lhs.replace('.', ''), rhs.replace('.', '')
    if len(digits_l) != len(digits_r):
        errors.append('count')
    elif digits_l != digits_r:
        errors.append('digit')
    return {'outcome': 'wrong', 'errors': errors or ['format']}


def load_manifest(path: Path) -> dict:
    path = path.resolve()
    manifest = json.loads(path.read_text())
    if manifest.get('schema_version') != 1:
        raise ValueError('unsupported manifest schema')
    ids, hashes, groups, device_splits = set(), {}, {}, {}
    for sample in manifest['samples']:
        if sample['id'] in ids:
            raise ValueError('duplicate sample id')
        ids.add(sample['id'])
        split = sample['split']
        if split not in {'development', 'heldout', 'excluded'}:
            raise ValueError('unknown split')
        device = sample['device_id']
        verified = sample['identity_verified'] is True and bool(device)
        if split == 'heldout' and not verified:
            raise ValueError('heldout physical identity unverified')
        if split != 'excluded':
            if device and device in device_splits and device_splits[device] != split:
                raise ValueError(f'physical device crosses split: {device}')
            if device:
                device_splits[device] = split
            group = sample['independence_group']
            if not group:
                raise ValueError('missing independence group')
            if group in groups and groups[group] != split:
                raise ValueError('independence group crosses split')
            if split == 'heldout' and group in groups:
                raise ValueError('duplicate heldout independence group')
            groups[group] = split
        resolved = (path.parent / sample['path']).resolve()
        if hashlib.sha256(resolved.read_bytes()).hexdigest() != sample['sha256']:
            raise ValueError(f'image hash mismatch: {sample["id"]}')
        if split != 'excluded':
            digest = sample['sha256']
            if digest in hashes:
                raise ValueError('duplicate image hash in evaluation')
            hashes[digest] = sample['id']
        text = sample['expected_text']
        if text is not None and not _NUMBER.fullmatch(normalise(text)):
            raise ValueError('invalid expected numeric text')
        box = sample['bbox']
        if len(box) != 4 or not all(math.isfinite(v) for v in box) or min(box[:2]) < 0 or min(box[2:]) <= 0:
            raise ValueError('invalid target box')
        sample['resolved_path'] = str(resolved)
    manifest['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def coverage_summary(samples: list[dict]) -> dict:
    verified = [s for s in samples if s['split'] != 'excluded' and s['identity_verified'] and s['device_id']]
    held = [s for s in verified if s['split'] == 'heldout']
    return {
        'devices': len({s['device_id'] for s in verified}),
        'families': len({s['family'] for s in verified}),
        'technologies': sorted({s['technology'] for s in verified}),
        'heldout_devices': len({s['device_id'] for s in held}),
        'heldout_independent_images': len({s['independence_group'] for s in held}),
        'split_counts': dict(Counter(s['split'] for s in samples)),
    }


def screening(metrics: dict, coverage: dict, *, pi_measured: bool) -> dict:
    reasons = []
    if not (coverage['devices'] >= 6 and coverage['families'] >= 3
            and {'LED', 'LCD'} <= set(coverage['technologies'])
            and coverage['heldout_devices'] >= 2 and coverage['heldout_independent_images'] >= 30):
        reasons.append('insufficient_coverage')
    if not metrics['total'] or metrics['correct'] / metrics['total'] < .9:
        reasons.append('complete_reading_coverage')
    if metrics['wrong']:
        reasons.append('wrong_accepted_readings')
    if metrics['geometry_failures']:
        reasons.append('geometry_unresolved')
    if metrics['detection_p95_ms'] is None or metrics['detection_p95_ms'] > 2000:
        reasons.append('detection_time')
    if metrics['processing_p95_ms'] is None or metrics['processing_p95_ms'] > 200:
        reasons.append('processing_time')
    if not pi_measured:
        reasons.append('pi_unmeasured')
    return {'qualified': not reasons, 'reasons': reasons}
