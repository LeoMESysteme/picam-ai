#!/usr/bin/env python3
"""R13-23: Baseline/Kandidat auf zwei Live-Laeufen und DEV, nur Offline.

PYTHONPATH=src DISPREAD_DEV_DATA=/mnt/ssd/picam-dev ./.venv/bin/python \
    scripts/r13-coarse-eval.py --baseline /tmp/claude-1000/r13-23/frame_tracking_baseline.py \
    --threads both --quad-tolerance-px 0.0001

Baseline ist eine unveraenderte Kopie des alten frame_tracking-Moduls.
Ergebnisse ausschliesslich unter /tmp/claude-1000/r13-23. Laufzeiten sind
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

OUTPUT_ROOT = Path('/tmp/claude-1000/r13-23')
QUAD_TOLERANCE_PX = 0.0


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def distribution(values):
    return {'n': len(values), 'median': float(np.median(values)), 'max': float(max(values))} if values else None


def instrument(tracker):
    """Grobschaetzung plus zweiter Feinversuch; ohne ersten Versuch/Graukonversion."""
    retry_ms, estimate_ms = [], []
    original_estimate, original_fine = tracker._estimate_coarse, tracker._fine_update
    original_image = tracker._coarse_image
    parts = {name: [] for name in ('preprocess', 'phase_and_checks', 'fine1', 'fine2')}
    retry_started = None

    def coarse_image(gray):
        start = perf_counter_ns()
        result = original_image(gray)
        parts['preprocess'].append((perf_counter_ns()-start)/1e6)
        return result

    def estimate(gray):
        nonlocal retry_started
        preprocess_count = len(parts['preprocess'])
        retry_started = perf_counter_ns()
        result = original_estimate(gray)
        estimate_ms.append((perf_counter_ns() - retry_started) / 1e6)
        if len(parts['preprocess']) == preprocess_count:
            parts['preprocess'].append(0.0)  # Kleine Ausschnitte: Grobsuche deaktiviert.
        parts['phase_and_checks'].append(estimate_ms[-1]-parts['preprocess'][-1])
        return result

    def fine(gray, offset=(0, 0), **kwargs):
        start = perf_counter_ns()
        result = original_fine(gray, offset, **kwargs)
        second = offset != (0, 0) or kwargs.get('similarity')
        parts['fine2' if second else 'fine1'].append((perf_counter_ns()-start)/1e6)
        if second:
            retry_ms.append((perf_counter_ns() - retry_started) / 1e6)
        return result

    tracker._estimate_coarse, tracker._fine_update = estimate, fine
    tracker._coarse_image = coarse_image
    return retry_ms, estimate_ms, parts


def compare(before, after, frames, *, reader=None, layout=None, profile=None, references=(), session=None):
    results = []
    old_retry_ms, old_estimate_ms, old_parts = instrument(before)
    retry_ms, estimate_ms, parts = instrument(after)
    paired = {name: [] for name in ('update', 'second_pass', 'coarse', *parts)}
    for index, (meta, image) in enumerate(frames):
        measured = {}
        counts = {'second_pass': (len(old_retry_ms), len(retry_ms)),
                  'coarse': (len(old_estimate_ms), len(estimate_ms)),
                  **{k: (len(old_parts[k]), len(parts[k])) for k in parts}}
        # AB/BA, im selben Prozess und auf demselben bereits geladenen Bild.
        order = (('before', before), ('after', after))
        for name, tracker in (order if index % 2 == 0 else order[::-1]):
            start = perf_counter_ns()
            result = tracker.update(image)
            measured[name] = result, (perf_counter_ns()-start)/1e6
        old, old_ms = measured['before']
        new, new_ms = measured['after']
        paired['update'].append(new_ms/old_ms)
        for name, (old_values, values) in {'second_pass': (old_retry_ms, retry_ms),
                                         'coarse': (old_estimate_ms, estimate_ms),
                                         **{k: (old_parts[k], parts[k]) for k in parts}}.items():
            old_n, new_n = counts[name]
            if len(old_values) > old_n and len(values) > new_n and old_values[-1] > 0:
                paired[name].append(values[-1]/old_values[-1])
        entry = {'image': meta.get('image', meta.get('file')), 'before': asdict(old), 'after': asdict(new),
                 'before_ms': old_ms, 'after_ms': new_ms, 'identical': old == new,
                 'coarse_before': asdict(before.last_coarse) if before.last_coarse else None,
                 'coarse': asdict(after.last_coarse) if after.last_coarse else None}
        entry['quad_error_px'] = (float(np.linalg.norm(np.asarray(old.quad)-new.quad, axis=1).max())
                                  if old.quad is not None and new.quad is not None else None)
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
    summary['parts_ms'] = {k: {'before': distribution(old_parts[k]), 'after': distribution(parts[k])} for k in parts}
    summary['paired_ratio_after_before'] = {k: distribution(v) for k, v in paired.items()}
    for name in ('before', 'after'):
        readings = [r['read'][name] for r in results if name in r.get('read', {})]
        summary[name] = {'accepted': sum(r[name]['quad'] is not None for r in results),
                         'reasons': dict(Counter(r[name]['reason'] or 'ok' for r in results)),
                         'reader_values': sum(r['value'] is not None for r in readings),
                         'reader_rejected': sum(r['value'] is None for r in readings),
                         'misreads': sum(r['reference_match'] is False for r in readings)}
    summary['previously_accepted_changed'] = [r['image'] for r in results
                                             if r['before']['quad'] is not None and not r['identical']]
    summary['changed_results'] = [r['image'] for r in results if not r['identical']]
    summary['lost'] = [r['image'] for r in results if r['before']['quad'] is not None and r['after']['quad'] is None]
    summary['quad_tolerance_px'] = QUAD_TOLERANCE_PX
    summary['quads_outside_tolerance'] = [r['image'] for r in results
                                         if r['quad_error_px'] is not None and r['quad_error_px'] > QUAD_TOLERANCE_PX]
    summary['max_quad_error_px'] = max((r['quad_error_px'] or 0 for r in results), default=0)
    summary['changed_readings'] = [r['image'] for r in results if r.get('read', {}).get('before') is not None
                                    and r['read']['before'] != r['read'].get('after')]
    summary['newly_accepted'] = [{'image': r['image'], 'displacement_px': r['after']['displacement_px'],
                                'scale': r['coarse']['scale'] if r['coarse'] else None,
                                'read': r.get('read', {}).get('after')}
                                 for r in results if r['before']['quad'] is None and r['after']['quad'] is not None]
    summary['coarse_retries_before'] = sum(bool(r['coarse_before'] and r['coarse_before']['used']) for r in results)
    summary['coarse_retries'] = sum(bool(r['coarse'] and r['coarse']['used']) for r in results)
    summary['coarse_accepted'] = sum(bool(r['coarse'] and r['coarse']['used'] and r['after']['quad']) for r in results)
    return {'summary': summary, 'frames': results}


def profile_coarse_parts(before, after, run):
    """60 Bilder, AB/BA; Vorverarbeitung gegen die echten Methoden geprueft.

    Zeitstempel trennen resize (samt Float-Konversion), Laplace und Maske.
    """
    names = ('resize', 'laplace', 'mask', 'phase')
    samples = {side: {part: [] for part in names} for side in ('before', 'after')}
    for index, meta in enumerate(rows(run / 'diagnose/images.jsonl')[:60]):
        gray = cv2.cvtColor(cv2.imread(str(run / 'diagnose' / meta['image'])), cv2.COLOR_BGR2GRAY)
        order = (('before', before), ('after', after))
        for side, tracker in (order if index % 2 == 0 else order[::-1]):
            start = perf_counter_ns()
            crop = cv2.resize(gray[tracker._coarse_crop], tracker._coarse_mask.shape[::-1],
                              interpolation=cv2.INTER_AREA).astype(np.float32)
            resized = perf_counter_ns()
            laplace = cv2.Laplacian(crop, cv2.CV_32F)
            filtered = perf_counter_ns()
            image = laplace*tracker._coarse_mask
            masked = perf_counter_ns()
            for part, ns in zip(names, (resized-start, filtered-resized, masked-filtered), strict=False):
                samples[side][part].append(ns/1e6)
            assert np.array_equal(image, tracker._coarse_image(gray)), 'Profiler passt nicht zur Vorverarbeitung'
            start = perf_counter_ns()
            cv2.phaseCorrelate(tracker._coarse_reference, image)
            samples[side]['phase'].append((perf_counter_ns()-start)/1e6)
    def ratios(a, b):
        return distribution([x/y for x, y in zip(a, b, strict=True)])

    return {'ms': {side: {name: distribution(values) for name, values in parts.items()}
                    for side, parts in samples.items()},
            'paired_ratio_after_before': {name: ratios(samples['after'][name], samples['before'][name]) for name in names},
            'samples_ms': samples}

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
    parts = profile_coarse_parts(before, after, run)
    (OUTPUT_ROOT / f'live-{name}-parts.json').write_text(json.dumps(parts, indent=2, allow_nan=False)+'\n')
    live['summary']['parts_profile'] = {k: v for k, v in parts.items() if not k.endswith('samples_ms')}
    (OUTPUT_ROOT / f'live-{name}.json').write_text(json.dumps(live, indent=2, allow_nan=False)+'\n')
    print(f'LIVE {name}', json.dumps(live['summary']), flush=True)
    return live['summary']


def evaluate(baseline, *, live_only=False):
    lives = {name: evaluate_live(baseline, name) for name in ('110248Z', '121101Z')}
    if live_only:
        return {'host': platform.uname()._asdict(), 'opencv': cv2.__version__,
                'opencv_threads': cv2.getNumThreads(), 'live': lives, 'dev': None,
                'timing_basis': 'perf_counter_ns: monotone Host-Verarbeitungsdauer'}
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
    global OUTPUT_ROOT, QUAD_TOLERANCE_PX
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=OUTPUT_ROOT)
    parser.add_argument('--threads', choices=('1', 'standard', 'both'), default='1')
    parser.add_argument('--quad-tolerance-px', type=float, default=0.0)
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--live-only', action='store_true')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('r19b_baseline', args.baseline)
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = baseline
    spec.loader.exec_module(baseline)
    output = args.output.resolve()
    if not output.is_relative_to(Path('/tmp')):
        parser.error('--output muss unter /tmp liegen')
    if not np.isfinite(args.quad_tolerance_px) or args.quad_tolerance_px < 0:
        parser.error('Quad-Toleranz muss endlich und nicht negativ sein')
    QUAD_TOLERANCE_PX = args.quad_tolerance_px
    if args.repeats < 1:
        parser.error('--repeats muss positiv sein')
    standard_threads = cv2.getNumThreads()
    modes = ('1', 'standard') if args.threads == 'both' else (args.threads,)
    failed = False
    for repeat in range(args.repeats):
        for mode in modes:
            cv2.setNumThreads(1 if mode == '1' else standard_threads)
            OUTPUT_ROOT = output / mode
            if args.repeats > 1:
                OUTPUT_ROOT /= f'repeat-{repeat+1}'
            OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
            result = evaluate(baseline, live_only=args.live_only)
            result['baseline'] = str(args.baseline)
            result['timing_order'] = 'AB/BA pro Bild, gleicher Prozess; parallele CI-Last moeglich'
            (OUTPUT_ROOT / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
            failed |= any(live['after']['misreads'] or live['lost'] or live['quads_outside_tolerance']
                          or live['changed_readings'] for live in result['live'].values())
            if result['dev'] is not None:
                failed |= bool(result['dev']['changed_results'])
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
