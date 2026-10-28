#!/usr/bin/env python3
"""R13-19c: R13-19b/R13-19c auf zwei Live-Laeufen und DEV, nur Offline.

PYTHONPATH=src DISPREAD_DEV_DATA=/mnt/ssd/picam-dev ./.venv/bin/python \
    scripts/r13-coarse-eval.py --baseline /tmp/claude-1000/r13-19c/frame_tracking_before.py

Baseline ist eine unveraenderte Kopie des alten frame_tracking-Moduls.
Ergebnisse ausschliesslich unter /tmp/claude-1000/r13-19c. Laufzeiten sind
Host-Verarbeitungsdauern mit perf_counter_ns, keine Aufnahmelatenzen.
Die GSV-Referenz wird erst nach Tracking und Lesen zum Vergleich benutzt.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns

import cv2
import numpy as np
from _devdata import input_path

from dispread.layout import CharLayout
from dispread.live import frame_tracking as current
from dispread.live.recording import load_recording, recorded_frames
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.records import to_boottime_ns
from dispread.rectify import rectify
from dispread.session_profile import SessionProfile

OUTPUT_ROOT = Path('/tmp/claude-1000/r13-19c')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def distribution(values):
    return {'n': len(values), 'median': float(np.median(values)), 'max': float(max(values))} if values else None


def instrument(tracker):
    """Grobschaetzung plus zweiter Feinversuch; ohne ersten Versuch/Graukonversion."""
    retry_ms, estimate_ms = [], []
    original_estimate, original_fine = tracker._estimate_coarse, tracker._fine_update
    retry_started = None

    def estimate(gray):
        nonlocal retry_started
        retry_started = perf_counter_ns()
        result = original_estimate(gray)
        estimate_ms.append((perf_counter_ns() - retry_started) / 1e6)
        return result

    def fine(gray, offset=(0, 0), **kwargs):
        result = original_fine(gray, offset, **kwargs)
        if offset != (0, 0) or kwargs.get('similarity'):
            retry_ms.append((perf_counter_ns() - retry_started) / 1e6)
        return result

    tracker._estimate_coarse, tracker._fine_update = estimate, fine
    return retry_ms, estimate_ms


def compare(before, after, frames, *, reader=None, layout=None, profile=None, references=(), session=None):
    results = []
    old_retry_ms, old_estimate_ms = instrument(before)
    retry_ms, estimate_ms = instrument(after)
    for meta, image in frames:
        start = perf_counter_ns()
        old = before.update(image)
        old_ms = (perf_counter_ns() - start) / 1e6
        start = perf_counter_ns()
        new = after.update(image)
        new_ms = (perf_counter_ns() - start) / 1e6
        entry = {'image': meta.get('image', meta.get('file')), 'before': asdict(old), 'after': asdict(new),
                 'before_ms': old_ms, 'after_ms': new_ms, 'identical': old == new,
                 'coarse_before': asdict(before.last_coarse) if before.last_coarse else None,
                 'coarse': asdict(after.last_coarse) if after.last_coarse else None}
        for name, result in (('before', old), ('after', new)):
            entry[name]['displacement_px'] = ((np.asarray(result.quad).mean(axis=0)-after.quad.mean(axis=0)).tolist()
                                               if result.quad is not None else None)
        if reader is not None:
            time_ns = to_boottime_ns(meta['capture_timestamp'], session)
            # Gemeinsame CLOCK_BOOTTIME; Fenster ist Vergleichstoleranz,
            # keine Aussage ueber Belichtungs- oder DUT-Messzeit.
            allowed = {ref['raw'].split()[0] for ref in references
                       if time_ns-1_500_000_000 <= ref['t_boottime_ns'] <= time_ns+1_000_000_000}
            entry['reference_values'] = sorted(allowed)
            entry['read'] = {}
            for name, result in (('before', old), ('after', new)):
                if result.quad is None:
                    continue
                read = reader.read(rectify(image, result.quad, target_size=profile.target_size).image, layout)
                entry['read'][name] = {'raw_text': read.raw_text, 'value': read.value,
                                       'reasons': read.diagnostics.get('reason'),
                                       'reference_match': read.raw_text in allowed if read.value is not None else None}
        results.append(entry)
    summary = {'frames': len(results), 'second_pass_ms': distribution(retry_ms),
               'before_second_pass_ms': distribution(old_retry_ms),
               'coarse_estimate_ms': distribution(estimate_ms),
               'before_coarse_estimate_ms': distribution(old_estimate_ms)}
    for name in ('before', 'after'):
        readings = [r['read'][name] for r in results if name in r.get('read', {})]
        summary[name] = {'accepted': sum(r[name]['quad'] is not None for r in results),
                         'reasons': dict(Counter(r[name]['reason'] or 'ok' for r in results)),
                         'reader_values': sum(r['value'] is not None for r in readings),
                         'reader_rejected': sum(r['value'] is None for r in readings),
                         'misreads': sum(r['reference_match'] is False for r in readings)}
    summary['previously_accepted_changed'] = [r['image'] for r in results
                                             if r['before']['quad'] is not None and not r['identical']]
    summary['newly_accepted'] = [{'image': r['image'], 'displacement_px': r['after']['displacement_px'],
                                'scale': r['coarse']['scale'] if r['coarse'] else None,
                                'read': r.get('read', {}).get('after')}
                                 for r in results if r['before']['quad'] is None and r['after']['quad'] is not None]
    summary['coarse_retries'] = sum(bool(r['coarse'] and r['coarse']['used']) for r in results)
    summary['coarse_accepted'] = sum(bool(r['coarse'] and r['coarse']['used'] and r['after']['quad']) for r in results)
    return {'summary': summary, 'frames': results}


def evaluate_live(baseline, name):
    root = input_path(f'live/live-20261028T{name}')
    run = root / 'run-01'
    data = json.loads((root / 'profile.json').read_text())
    reference = cv2.imread(str(input_path(data['reference_frame']['path'])))
    block = data['live_tracking']
    before = baseline.FrameTracker(reference, data['quad'], baseline.RegionProposal.from_dict(block['proposal']),
                                    baseline.FrameTrackingConfig.from_dict(block['config']))
    after = current.FrameTracker(reference, data['quad'], current.RegionProposal.from_dict(block['proposal']),
                                 current.FrameTrackingConfig.from_dict(block['config']))
    session = json.loads((run / 'session.json').read_text())
    profile = SessionProfile.load(root / 'profile.json')
    reader = DotMatrixReader.from_file(input_path(session['templates']['path']), session['templates']['sha256'])
    live = compare(before, after, ((row, cv2.imread(str(run / 'diagnose' / row['image'])))
                                   for row in rows(run / 'diagnose/images.jsonl')),
                   reader=reader, layout=CharLayout.from_profile(profile, session['gate']['expected_unit']),
                   profile=profile, references=rows(run / 'reference.jsonl'), session=session)
    (OUTPUT_ROOT / f'live-{name}.json').write_text(json.dumps(live, indent=2, allow_nan=False)+'\n')
    print(f'LIVE {name}', json.dumps(live['summary']), flush=True)
    return live['summary']


def evaluate(baseline):
    lives = {name: evaluate_live(baseline, name) for name in ('110248Z', '121101Z')}
    # Wie r13-tracker-eval.py: Vorschlag frisch am DEV-Referenzbild,
    # jeweils mit den unveraenderten Defaults der beiden Codeversionen.
    dev_profile = json.loads(input_path('live/live-20261021T151835Z/profile.json').read_text())
    dev_reference = cv2.imread(str(input_path(dev_profile['reference_frame']['path'])))
    quad = dev_profile['quad']
    before = baseline.FrameTracker(dev_reference, quad, baseline.propose_regions(dev_reference, quad))
    after = current.FrameTracker(dev_reference, quad, current.propose_regions(dev_reference, quad))
    recording = load_recording(input_path('diagnostics/r13-werteplan-20261021'))
    dev = compare(before, after, recorded_frames(recording, dev_reference.shape))
    (OUTPUT_ROOT / 'dev.json').write_text(json.dumps(dev, indent=2, allow_nan=False)+'\n')
    print('DEV', json.dumps(dev['summary']), flush=True)
    return {'host': platform.uname()._asdict(), 'opencv': cv2.__version__, 'opencv_threads': cv2.getNumThreads(),
            'timing_basis': 'perf_counter_ns: monotone Host-Verarbeitungsdauer',
            'config': current.FrameTrackingConfig().to_dict(), 'live': lives, 'dev': dev['summary']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('r19b_baseline', args.baseline)
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = baseline
    spec.loader.exec_module(baseline)
    cv2.setNumThreads(1)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    result = evaluate(baseline)
    (OUTPUT_ROOT / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return int(any(live['after']['misreads'] or live['previously_accepted_changed'] for live in result['live'].values())
               or bool(result['dev']['previously_accepted_changed']))


if __name__ == '__main__':
    raise SystemExit(main())
