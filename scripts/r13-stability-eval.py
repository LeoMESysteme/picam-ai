#!/usr/bin/env python3
"""R13-25: Einrichtung neu berechnen, HEAD-Tracking und Leser offline vergleichen.

Nur lesende Eingaben; alle Ausgaben zwingend unter /tmp. Keine Hardware.
Host-Verarbeitungsdauern via perf_counter, keine Aufnahme-/DUT-Latenzen.
Die Referenz erreicht ausschliesslich den nachgelagerten Zahlenvergleich.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from _devdata import diagnose_dir, input_path

from dispread.layout import CharLayout
from dispread.live import frame_tracking as ft
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.records import to_boottime_ns
from dispread.rectify import rectify
from dispread.session_profile import SessionProfile

SPEC = importlib.util.spec_from_file_location('coarse_eval', Path(__file__).with_name('r13-coarse-eval.py'))
coarse_eval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coarse_eval)


def image(path):
    result = cv2.imread(str(path))
    if result is None:
        raise ValueError(f'Bild nicht lesbar: {path}')
    return result


def calibration_stats(peaks, usable, *, probe_count, min_peak):
    """Einzelbild-Nutzung getrennt auf Probe und spaeterem Holdout ausweisen."""
    valid = (np.asarray(peaks) >= min_peak) & np.asarray(usable)
    return {"all_usable_share": valid.mean(axis=0).tolist(),
            "holdout_usable_share": valid[probe_count:].mean(axis=0).tolist(),
            "holdout_frames": len(valid)-probe_count}


def integer_align(raw, displacement):
    """Nur ganzzahlige Translation fuer historische Probe-Ersatzbilder; kein Mitteln."""
    dx, dy = np.rint(displacement).astype(int)
    return cv2.warpAffine(raw, np.float32([[1, 0, -dx], [0, 1, -dy]]), raw.shape[1::-1],
                          flags=cv2.INTER_NEAREST)


def diagnostic_probe_samples(reference, quad, config, block, samples):
    """Im Lauf bereits bewegte Bilder auf die stationaere Setup-Situation beziehen.

    Grobe Rahmen-Phasenkorrelation, danach Median eindeutiger Patchversätze.
    Nur ganze Pixel verschieben: das Einzelbildrauschen bleibt unangetastet.
    Diese Offline-Ersatzmessung ist keine neue Aufnahme oder unabhaengige Abnahme.
    """
    baseline = ft.FrameTracker(reference, quad, ft.RegionProposal.from_dict(block['proposal']), config)
    # Alle bereits geometrisch geeigneten Kandidaten; keine Auswahl aus spaeteren Bildern.
    candidates = ft.propose_regions(reference, quad, replace(config, max_regions=config.max_candidates))
    gray = ft._gray(reference)
    aligned, offsets = [], []
    for raw in samples:
        estimate = baseline._estimate_coarse(ft._gray(raw))
        offset = np.rint((estimate.dx, estimate.dy)).astype(int)
        adjusted = ft._gray(integer_align(raw, offset))
        deltas = []
        for region in candidates.regions:
            patch = ft._window(gray, region.centre, config.patch_size//2)
            search = ft._window(adjusted, region.centre, config.patch_size//2+config.search_radius_px)
            position, peak, ambiguous = ft._peak(cv2.matchTemplate(search, patch, cv2.TM_CCOEFF_NORMED), config)
            if peak >= config.min_peak and not ambiguous:
                deltas.append(position-config.search_radius_px)
        if len(deltas) >= config.min_regions:
            offset += np.rint(np.median(deltas, axis=0)).astype(int)
        aligned.append(integer_align(raw, offset))
        offsets.append(offset.tolist())
    return aligned, offsets


def region_match(gray, centre, patch, config):
    search = ft._window(gray, centre, config.patch_size//2+config.search_radius_px)
    if search is None:
        return 0.0, False
    position, peak, ambiguous = ft._peak(cv2.matchTemplate(search, patch, cv2.TM_CCOEFF_NORMED), config)
    usable = not ambiguous and bool(np.all(position > 0) and np.all(position < 2*config.search_radius_px))
    return peak, usable


def evaluate(root, output, recording='run-01'):
    setup, run = root / 'setup', root / recording
    if not all((setup / name).is_file() for name in ('still.png', 'stability.png')):
        return {'skipped': 'Einrichtungsbilder fehlen'}
    profile = SessionProfile.load(root / 'profile.json')
    data = json.loads((root / 'profile.json').read_text())
    reference = image(setup / 'still.png')
    metadata = coarse_eval.rows(diagnose_dir(run) / 'images.jsonl')
    if len(metadata) <= 8:
        return {'skipped': 'Mindestens acht Probe-Ersatzbilder und spaetere Diagnosebilder erforderlich'}
    # Historische Setup-Einzelbilder fehlen. Erste acht Diagnose-Einzelbilder
    # als Ersatz, alle spaeteren Bilder bleiben aus der Vorschlagsbildung heraus.
    probe_run = root / 'run-01'
    probe_metadata = coarse_eval.rows(diagnose_dir(probe_run) / 'images.jsonl')[:8]
    if len(probe_metadata) != 8:
        return {'skipped': 'Acht Probe-Ersatzbilder aus run-01 fehlen'}
    samples = [image(diagnose_dir(probe_run) / meta['image']) for meta in probe_metadata]
    probe_count = 8 if recording == 'run-01' else 0
    block = data['live_tracking']
    config = ft.FrameTrackingConfig.from_dict(block['config'])
    samples, probe_offsets = diagnostic_probe_samples(reference, data['quad'], config, block, samples)
    # AB/BA, drei Wiederholungen, nur die Einrichtung wird gemessen.
    durations = {'single': [], 'independent': []}
    for iteration in range(3):
        order = ('single', 'independent') if iteration % 2 == 0 else ('independent', 'single')
        for name in order:
            start = perf_counter()
            proposal = ft.propose_regions(reference, data['quad'], config,
                                         stability_images=samples if name == 'independent' else None)
            durations[name].append((perf_counter() - start) * 1000)
            if name == 'independent':
                selected = proposal
    if not selected.ok:
        return {'proposal_ok': False, 'proposal_reasons': selected.reasons,
                'regions': len(selected.regions), 'side_counts': selected.metrics['regions_per_axis_side'], 'probe_offsets': probe_offsets}
    trackers = {
        'before': ft.FrameTracker(reference, data['quad'], ft.RegionProposal.from_dict(block['proposal']), config),
        'after': ft.FrameTracker(reference, data['quad'], selected, config),
    }
    session = json.loads((run / 'session.json').read_text())
    reader = DotMatrixReader.from_file(input_path(session['templates']['path']), session['templates']['sha256'])
    layout = CharLayout.from_profile(profile, session['gate']['expected_unit'])
    references = coarse_eval.rows(run / 'reference.jsonl')
    reasons = {name: Counter() for name in trackers}
    phases = {name: Counter() for name in trackers}
    reads = {name: Counter() for name in trackers}
    lost, newly, records = [], [], []
    peaks = [[] for _ in selected.regions]
    usability = []
    fixed_peaks, fixed_usability = [], []
    local = (np.asarray([r.centre for r in selected.regions])-ft._normalise_quad(data['quad']).mean(axis=0)) @ ft._axes(ft._normalise_quad(data['quad'])).T
    limits = np.asarray(selected.metrics['proposal_spread_limits_px'])
    sides = np.array([local[:, 0] <= -limits[0, 0], local[:, 1] <= -limits[0, 1],
                      local[:, 0] >= limits[1, 0], local[:, 1] >= limits[1, 1]])
    side_counts, fixed_side_counts = [], []
    original_spread = ft._spread
    spread_failures = []

    def spread(*args):
        ok = original_spread(*args)
        if not ok:
            spread_failures.append(True)
        return ok

    ft._spread = spread
    try:
        for meta in metadata:
            frame = image(diagnose_dir(run) / meta['image'])
            gray = ft._gray(frame)
            entry = {'image': meta['image']}
            for name, tracker in trackers.items():
                spread_failures.clear()
                result = tracker.update(frame)
                reasons[name][result.reason or 'ok'] += 1
                phase = 'second' if tracker.last_coarse and tracker.last_coarse.used else 'first'
                detail = 'spread' if spread_failures and result.quad is None else result.reason or 'ok'
                phases[name][f'{phase}:{detail}'] += 1
                entry[name] = asdict(result)
                if result.quad is not None:
                    reading = reader.read(rectify(frame, result.quad, target_size=profile.target_size).image, layout)
                    time_ns = to_boottime_ns(meta['capture_timestamp'], session)
                    allowed = coarse_eval.allowed_reference_values(references, time_ns)
                    match = (coarse_eval.reference_match(reading.raw_text, allowed)
                             if reading.value is not None and allowed else None)
                    reads[name]['values' if reading.value is not None else 'rejected'] += 1
                    reads[name]['misreads'] += match is False
                    reads[name]['uncompared'] += reading.value is not None and match is None
                    entry[name]['read'] = {'raw': reading.raw_text, 'value': reading.value,
                                           'reference_match': match, 'allowed': sorted(allowed)}
            if entry['before']['quad'] is not None and entry['after']['quad'] is None:
                lost.append(meta['image'])
            if entry['before']['quad'] is None and entry['after']['quad'] is not None:
                newly.append(meta['image'])
            usable = []
            fixed_p, fixed_u = [], []
            estimate = trackers['after']._estimate_coarse(gray)
            offset = np.rint((estimate.dx, estimate.dy)).astype(int) if estimate.response > config.coarse_min_response else np.zeros(2, dtype=int)
            for region, patch, values in zip(selected.regions, trackers['after'].patches, peaks, strict=True):
                peak, valid = region_match(gray, region.centre, patch, config)
                fixed_p.append(peak)
                fixed_u.append(valid)
                peak, valid = region_match(gray, np.asarray(region.centre)+offset, patch, config)
                values.append(peak)
                usable.append(valid)
            usability.append(usable)
            fixed_peaks.append(fixed_p)
            fixed_usability.append(fixed_u)
            side_counts.append((sides & (np.array(usable) & (np.array([v[-1] for v in peaks]) >= config.min_peak))).sum(axis=1).tolist())
            fixed_side_counts.append((sides & (np.array(fixed_u) & (np.array(fixed_p) >= config.min_peak))).sum(axis=1).tolist())
            records.append(entry)
    finally:
        ft._spread = original_spread
    summary = {'recording': recording, 'frames': len(records), 'proposal_ok': selected.ok, 'proposal_reasons': selected.reasons,
               'regions': len(selected.regions), 'side_counts': selected.metrics['regions_per_axis_side'],
               'stability_rejected': selected.metrics['stability_rejected_candidates'],
               'setup_ms': {name: {'samples': values, 'median': float(np.median(values)), 'max': max(values)}
                            for name, values in durations.items()},
               'lost': lost, 'newly_accepted': newly}
    for name in trackers:
        summary[name] = {'accepted': reasons[name]['ok'], 'reasons': dict(reasons[name]),
                         'phases': dict(phases[name]), **reads[name]}
    calibration = calibration_stats(np.asarray(peaks).T, usability, probe_count=probe_count, min_peak=config.min_peak)
    fixed_calibration = calibration_stats(fixed_peaks, fixed_usability, probe_count=probe_count, min_peak=config.min_peak)
    fixed_calibration['min_live_per_side'] = np.min(fixed_side_counts, axis=0).tolist()
    fixed_calibration['side_frames_below_reserve'] = (np.asarray(fixed_side_counts) < config.min_inliers_per_side+config.reserve_regions).sum(axis=0).tolist()
    calibration['fixed_window'] = fixed_calibration
    calibration['per_region'] = [
        {'centre': region.centre, 'probe_kth_peak': probe_peak,
         'all_usable_share': share, 'holdout_usable_share': holdout,
         'fixed_all_usable_share': fixed_share, 'fixed_holdout_usable_share': fixed_holdout,
         'live_min': min(values), 'live_max': max(values)}
        for region, probe_peak, share, holdout, fixed_share, fixed_holdout, values in zip(
            selected.regions, selected.metrics['stability_peaks'], calibration['all_usable_share'],
            calibration['holdout_usable_share'], fixed_calibration['all_usable_share'], fixed_calibration['holdout_usable_share'], peaks, strict=True)]
    calibration['side_order'] = ['-x', '-y', '+x', '+y']
    calibration['min_live_per_side'] = np.min(side_counts, axis=0).tolist()
    calibration['side_frames_below_reserve'] = (np.asarray(side_counts) < config.min_inliers_per_side+config.reserve_regions).sum(axis=0).tolist()
    summary['calibration'] = {key: value for key, value in calibration.items() if key != 'per_region'}
    artifact = {'summary': summary, 'proposal': selected.to_dict(), 'calibration': calibration,
                'probe_recording': 'run-01', 'probe_images': [meta['image'] for meta in probe_metadata], 'probe_integer_offsets': probe_offsets, 'frames': records}
    (output / f'{root.name}.json').write_text(json.dumps(artifact, indent=2, allow_nan=False) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-root', type=Path, required=True)
    parser.add_argument('--run', action='append', required=True)
    parser.add_argument('--recording', default='run-01', help='Aufzeichnung innerhalb der Sitzung, z. B. run-02')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(Path('/tmp')):
        parser.error('--output muss unter /tmp liegen')
    if not args.recording.startswith('run-') or not args.recording[4:].isdigit():
        parser.error('--recording muss run-<Nummer> sein')
    args.output.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(args.threads)
    summaries = {}
    for name in args.run:
        if Path(name).name != name or name in ('.', '..'):
            parser.error('--run muss ein Sitzungsname sein')
        summaries[name] = evaluate(args.live_root / name, args.output, args.recording)
        print(name, json.dumps(summaries[name]), flush=True)
    (args.output / 'summary.json').write_text(json.dumps(summaries, indent=2) + '\n')
    return int(any(result.get('skipped') or result.get('lost') or result.get('after', {}).get('misreads')
                   or result.get('after', {}).get('uncompared') or result.get('proposal_ok') is False
                   for result in summaries.values()))


if __name__ == '__main__':
    raise SystemExit(main())
