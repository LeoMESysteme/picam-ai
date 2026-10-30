#!/usr/bin/env python3
"""Offline-Raster des R13-23-Reviews gegen eine unveraenderte HEAD-Kopie.

PYTHONPATH=src ./.venv/bin/python scripts/r13-coarse-sweep.py \
    --baseline /tmp/r13-correction/baseline.py --output /tmp/r13-correction/sweep.json

Je Referenz 285 grosse und 729 kleine bekannte Aehnlichkeiten (R13-24);
klein: dx/dy -3..3 px, Massstab 0.996..1.004. Keine Aufnahme oder Hardware.
Exit 1 bei verlorenen Baseline-Tracks oder Quadeckenfehler >1 Rohpixel.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict
from itertools import product
from pathlib import Path

import cv2
import numpy as np
from _devdata import input_path

from dispread.live import frame_tracking as current


def translation_accuracy(trackers, reference):
    """Reine Translation wie synth.py des Reviews, auch gebrochene Rohpixel."""
    gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    errors, responses = ({side: [] for side in trackers} for _ in range(2))
    for dx in np.arange(-16, 17, 2.5):
        for dy in np.arange(-12, 13, 1.75):
            image = cv2.warpAffine(gray, np.float32([[1, 0, dx], [0, 1, dy]]),
                                   gray.shape[::-1], borderMode=cv2.BORDER_REPLICATE)
            for side, tracker in trackers.items():
                estimate = tracker._estimate_coarse(image)
                errors[side].append((estimate.dx-dx, estimate.dy-dy))
                responses[side].append(estimate.response)
    return {side: {'cases': len(values), 'bias_xy_px': np.mean(values, axis=0).tolist(),
                   'max_component_error_px': float(np.abs(values).max()),
                   'max_vector_error_px': float(np.linalg.norm(values, axis=1).max()),
                   'median_vector_error_px': float(np.median(np.linalg.norm(values, axis=1))),
                   'median_response': float(np.median(responses[side])),
                   'min_response': float(min(responses[side]))}
            for side, values in errors.items()}


def sweep(baseline, name):
    root = input_path(f'live/{name}' if name.startswith('live-') else f'live/live-20261028T{name}')
    profile = json.loads((root / 'profile.json').read_text())
    reference = cv2.imread(str(input_path(profile['reference_frame']['path'])))
    block = profile['live_tracking']
    quad = np.asarray(profile['quad'], dtype=float)
    trackers = {
        side: module.FrameTracker(reference, quad, module.RegionProposal.from_dict(block['proposal']),
                                  module.FrameTrackingConfig.from_dict(block['config']))
        for side, module in (('before', baseline), ('after', current))
    }
    cases = []
    motions = [(*motion, 'large') for motion in product(
        (-19, -14, -9, 6, 11, 17), (-13, -7, 5, 12), (-2.5, -1.2, 0, 1.2, 2.5), (0.996, 1.0, 1.004))
        if np.hypot(*motion[:2]) <= 20]
    small_shifts = (-3, -2, -1, -0.5, 0, 0.5, 1, 2, 3)
    motions += [(*motion, 'small') for motion in product(
        small_shifts, small_shifts, (0,), (0.996, 0.997, 0.998, 0.999, 1.0, 1.001, 1.002, 1.003, 1.004))]
    for dx, dy, angle, scale, group in motions:
        matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), angle, scale)
        matrix[:, 2] += (dx, dy)
        image = cv2.warpAffine(reference, matrix, reference.shape[1::-1],
                               borderMode=cv2.BORDER_REPLICATE)
        expected = quad @ matrix[:, :2].T + matrix[:, 2]
        case = {'dx': dx, 'dy': dy, 'angle': angle, 'scale': scale, 'group': group}
        for side, tracker in trackers.items():
            result = tracker.update(image)
            case[side] = {'result': asdict(result),
                          'coarse': asdict(tracker.last_coarse) if tracker.last_coarse else None,
                          'accepted': result.quad is not None,
                          'corner_error_px': float(np.linalg.norm(np.asarray(result.quad)-expected,
                                                                axis=1).max())
                          if result.quad is not None else None}
        cases.append(case)
    summary = {'cases': len(cases),
               'only_before': sum(c['before']['accepted'] and not c['after']['accepted'] for c in cases),
               'only_after': sum(c['after']['accepted'] and not c['before']['accepted'] for c in cases)}
    for side in trackers:
        errors = [c[side]['corner_error_px'] for c in cases if c[side]['accepted']]
        summary[side] = {'accepted': len(errors), 'false_quads': sum(e > 1 for e in errors),
                         'max_corner_error_px': max(errors, default=0)}
    return {'summary': summary, 'cases': cases, 'translation_accuracy': translation_accuracy(trackers, reference)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--run', action='append', help='Referenz live-YYYYMMDDThhmmssZ; wiederholbar')
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(Path('/tmp')):
        parser.error('--output muss unter /tmp liegen')
    spec = importlib.util.spec_from_file_location('r13_sweep_baseline', args.baseline)
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = baseline
    spec.loader.exec_module(baseline)
    cv2.setNumThreads(args.threads)
    result = {'baseline': str(args.baseline), 'opencv': cv2.__version__, 'threads': cv2.getNumThreads(),
              'runs': {name: sweep(baseline, name) for name in (args.run or ('110248Z', '121101Z'))}}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    for name, run in result['runs'].items():
        print(name, json.dumps(run['summary']), flush=True)
    return int(any(run['summary']['only_before'] or run['summary']['after']['false_quads']
                   for run in result['runs'].values()))


if __name__ == '__main__':
    raise SystemExit(main())
