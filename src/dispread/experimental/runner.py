"""Reproducible offline comparison; development selection precedes heldout use.

No camera, release gate, serial sink, tracking or reference-value autofit is used.
Candidate/target matching is scoring, simulating a user's click after detection;
all regions are read before this scorer sees their target location or text.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import multiprocessing
import platform
import resource
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np

from dispread.experimental.evaluation import compare_text, coverage_summary, load_manifest, screening
from dispread.frames.types import Frame
from dispread.records import TimeBaseKind, Timestamp
from dispread.workbench.vision import box_iou


def match_target(predictions: list[dict], target: list, threshold: float) -> int | None:
    overlaps = [box_iou(p['bbox'], target) for p in predictions]
    if not overlaps or max(overlaps) < threshold:
        return None
    return int(np.argmax(overlaps))


def summarize(rows: list[dict]) -> dict:
    counts = Counter(r['outcome'] for r in rows)
    result = {key: counts[key] for key in ('correct', 'wrong', 'rejected', 'missed')}
    result.update(total=len(rows), errors=dict(Counter(e for r in rows for e in r['errors'])),
                  geometry_failures=sum(not r['geometry_ready'] for r in rows),
                  detection_recall=sum(r['detected'] for r in rows) / len(rows) if rows else None)
    for key in ('detection', 'processing', 'total'):
        durations = [r[f'{key}_ms'] for r in rows if r[f'{key}_ms'] is not None]
        for percentile in (50, 95):
            result[f'{key}_p{percentile}_ms'] = float(np.percentile(durations, percentile)) if durations else None
    total_ms = sum(r['total_ms'] for r in rows)
    result['throughput_images_s'] = len(rows) * 1000 / total_ms if total_ms else None
    # Single-target annotations cannot label unrelated detections as false.
    result['false_detections'] = None
    result['wrong_row_selection'] = None
    return result


def _bbox(candidate):
    points = np.asarray(candidate.quad)
    left, top = points.min(axis=0)
    right, bottom = points.max(axis=0)
    return [float(left), float(top), float(right-left), float(bottom-top)]


def _read_dict(read):
    return {'text': read.raw_text, 'accepted': read.value is not None,
            'diagnostics': read.diagnostics, 'status_flags': sorted(read.status_flags),
            'sign_detected': read.sign_detected, 'decimal_point_index': read.decimal_point_index,
            'confidence_calibrated': False}


def _measure_sample(sample, adapter, locator, mode, iou_threshold):
    from dispread.experimental.auto_adapters import infer_geometry, rectify_candidate

    image = cv2.imread(sample['resolved_path'])
    if image is None:
        raise ValueError(f'unreadable image: {sample["id"]}')
    x, y, w, h = sample['bbox']
    if x+w > image.shape[1] or y+h > image.shape[0]:
        raise ValueError(f'target outside image: {sample["id"]}')
    begin = time.perf_counter_ns()
    predictions = []
    if mode == 'full_frame':
        frame = Frame(0, image, Timestamp(0, TimeBaseKind.SYNTHETIC), 'offline-experiment')
        candidates = locator.locate(frame)
        detection_ms = (time.perf_counter_ns()-begin)/1e6
        for candidate in candidates:
            start = time.perf_counter_ns()
            try:
                crop = rectify_candidate(image, candidate)
            except (ValueError, cv2.error) as error:
                predictions.append({'bbox': _bbox(candidate), 'quad': candidate.quad, 'read': None,
                                    'geometry': {'digit_quads': [], 'segment_quads': [], 'ready': False,
                                                 'uncertainty': f'rectification_failed:{type(error).__name__}'},
                                    'processing_ms': (time.perf_counter_ns()-start)/1e6})
                continue
            geometry = infer_geometry(crop.image)
            read = adapter.read(crop.image) if adapter is not None else None
            predictions.append({'bbox': _bbox(candidate), 'quad': candidate.quad,
                                'read': _read_dict(read) if read else None,
                                'geometry': asdict(geometry),
                                'processing_ms': (time.perf_counter_ns()-start)/1e6})
        selected = match_target(predictions, sample['bbox'], iou_threshold)
    else:
        # This mode deliberately uses annotated crop; never qualifies a workflow.
        x0, y0 = int(x), int(y)
        x1, y1 = int(np.ceil(x+w)), int(np.ceil(y+h))
        crop_image = image[y0:y1, x0:x1]
        detection_ms = 0.
        start = time.perf_counter_ns()
        geometry = infer_geometry(crop_image)
        if adapter is None and sample.get('baseline_profile'):
            from dispread.benchmark import read_frame
            from dispread.ocr.sevenseg import SevenSegmentReader
            # Reuse only image-to-reader path, never the legacy scorer/identity logic.
            read = read_frame(image, sample['baseline_profile'], SevenSegmentReader())
        else:
            read = adapter.read(crop_image) if adapter is not None else None
        predictions.append({'bbox': sample['bbox'], 'read': _read_dict(read) if read else None,
                            'geometry': asdict(geometry), 'processing_ms': (time.perf_counter_ns()-start)/1e6})
        selected = 0
    elapsed = (time.perf_counter_ns()-begin)/1e6
    prediction = predictions[selected] if selected is not None else None
    actual = prediction['read'] if prediction else None
    score = compare_text(sample['expected_text'], actual['text'] if actual and actual['accepted'] else None)
    if selected is None:
        score = {'outcome': 'missed', 'errors': []}
    return {
        'sample_id': sample['id'], 'device_id': sample['device_id'], 'conditions': sample['conditions'],
        'split': sample['split'], 'mode': mode, 'expected_text': sample['expected_text'],
        **score, 'detected': selected is not None, 'selected_prediction': selected,
        'selection_semantics': 'scorer_target_match_after_inference' if mode == 'full_frame' else 'annotated_crop',
        'geometry_ready': bool(prediction and prediction['geometry']['ready']),
        'detection_ms': detection_ms, 'processing_ms': prediction['processing_ms'] if prediction else None,
        'total_ms': elapsed, 'predictions': predictions,
        'baseline_limitation': 'requires_supplied_profile; no_automatic_grid' if adapter is None else None,
    }, image


def _overlay(image, sample, row, destination):
    drawn = image.copy()
    x, y, w, h = [round(v) for v in sample['bbox']]
    cv2.rectangle(drawn, (x,y), (x+w,y+h), (0,200,0), 2)
    for index, prediction in enumerate(row['predictions']):
        bx, by, bw, bh = [round(v) for v in prediction['bbox']]
        cv2.rectangle(drawn, (bx,by), (bx+bw,by+bh), (0,165,255), 2)
        read = prediction['read']
        text = read['text'] if read else 'no automatic grid'
        cv2.putText(drawn, f'{index}: {text[:30]}', (bx,max(20,by-5)), cv2.FONT_HERSHEY_SIMPLEX,.6,(0,165,255),2)
    scale = min(1., 1000/drawn.shape[1])
    drawn = cv2.resize(drawn, None, fx=scale, fy=scale)
    cv2.putText(drawn, f'{row["outcome"]}; geometry unready; green=truth orange=prediction',
                (10,25), cv2.FONT_HERSHEY_SIMPLEX,.45,(255,100,100),1)
    if not cv2.imwrite(str(destination), drawn):
        raise OSError(f'could not write {destination}')


def _environment():
    model_path = Path('/proc/device-tree/model')
    pi_model = model_path.read_text().strip('\x00') if model_path.exists() else None
    versions = {name: importlib.metadata.version(name) for name in
                ('numpy', 'onnxruntime', 'PyYAML', 'flatbuffers', 'protobuf', 'pytest', 'ruff')}
    return {'runtime_versions': versions, 'python': platform.python_version(), 'machine': platform.machine(), 'platform': platform.platform(),
            'pi_model': pi_model, 'numpy': np.__version__, 'numpy_path': np.__file__,
            'opencv': cv2.__version__, 'opencv_path': cv2.__file__,
            'clock': 'time.perf_counter_ns / CLOCK_MONOTONIC', 'duration_uncertainty_ns': None,
            'capture_latency_ms': None, 'frame_timebase': 'SYNTHETIC',
            'tesseract': subprocess.run(['tesseract','--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0]}


def _worker(candidate_id, samples, models, config, output):
    from dispread.experimental.auto_adapters import GeometricLocator, TesseractAdapter

    rows = []
    overlays = output / "overlays"
    start = time.perf_counter_ns()
    locator = GeometricLocator()
    if candidate_id == 'baseline':
        adapter = None
    elif candidate_id == 'ppocr':
        from dispread.experimental.ppocr_adapter import PPOCRAdapter
        adapter = PPOCRAdapter(models)
        locator = adapter
    else:
        adapter = TesseractAdapter(models/f'{candidate_id}.traineddata')
    initialization_ms = (time.perf_counter_ns()-start)/1e6
    written = set()
    for sample in samples:
        for mode in ('full_frame', 'known_crop'):
            row, image = _measure_sample(sample, adapter, locator, mode, config['match_iou'])
            row['candidate'] = candidate_id
            row['initial_detection_ms'] = initialization_ms + row['detection_ms']
            row['initialization_scope'] = 'adapter_constructor; tesseract_model_load_in_each_read'
            row['independence_group'] = sample['independence_group']
            row['provisional'] = True
            rows.append(row)
            # Keep incremental records if an external runtime fails later.
            with (output/'readings.jsonl').open('a') as stream:
                stream.write(json.dumps(row, allow_nan=False)+'\n')
            key = (mode,row['outcome'])
            if key not in written:
                name = f'{candidate_id}-{sample["split"]}-{mode}-{row["outcome"]}.jpg'
                _overlay(image, sample, row, overlays/name)
                (overlays/(name+'.json')).write_text(json.dumps({
                    'sample_id': sample['id'], 'source': sample['source'], 'license': sample['license'],
                    'attribution': sample.get('attribution'), 'original_sha256': sample['sha256'],
                    'modification': 'evaluation rectangles/text; resized to max 1000 pixels wide',
                    'provisional': True}, indent=2)+'\n')
                written.add(key)
    memory = {"parent_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "largest_child_peak_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}
    (output / "worker-result.json").write_text(json.dumps({"rows": rows, "initialization_ms": initialization_ms, "memory": memory}))


def run(manifest_path: Path, config_path: Path, output: Path, frozen_path: Path | None = None):
    manifest = load_manifest(manifest_path)
    config = json.loads(config_path.read_text())
    models = (config_path.parent/config['models_dir']).resolve()
    output.mkdir(parents=True, exist_ok=False)
    overlays = output/'overlays'
    overlays.mkdir()
    environment = _environment()
    rows, initializations, candidate_memory = [], {}, {}
    candidates_path = config_path.parent/'candidates.json'
    candidate_metadata = json.loads(candidates_path.read_text())
    # Auxiliary download metadata are irrelevant; hash precisely reproducible artifacts.
    model_hashes = {}
    for candidate in candidate_metadata['candidates']:
        for artifact in candidate.get('artifacts', []):
            key = str(Path(artifact['path']).relative_to('models'))
            model_hashes[key] = hashlib.sha256((models/key).read_bytes()).hexdigest()
    source_root = Path(__file__).resolve().parents[2]
    source_hashes = {str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(source_root.rglob('*.py'))}
    for candidate in (candidate_metadata or {}).get('candidates', []):
        for artifact in candidate.get('artifacts', []):
            key = str(Path(artifact['path']).relative_to('models'))
            if model_hashes.get(key) != artifact['sha256']:
                raise ValueError(f'pinned model hash mismatch: {key}')

    def evaluate(candidate_id, samples):
        process = multiprocessing.get_context('spawn').Process(
            target=_worker, args=(candidate_id, samples, models, config, output))
        process.start()
        process.join()
        if process.exitcode != 0:
            raise RuntimeError(f'candidate worker failed: {candidate_id}; exit {process.exitcode}')
        payload = json.loads((output/'worker-result.json').read_text())
        rows.extend(payload['rows'])
        initializations.setdefault(candidate_id, []).append(payload['initialization_ms'])
        candidate_memory.setdefault(candidate_id, []).append(payload['memory'])
        (output/'worker-result.json').unlink()

    development = [s for s in manifest['samples'] if s['split'] == 'development']
    heldout = [s for s in manifest['samples'] if s['split'] == 'heldout']
    for candidate_id in ['baseline', *config['tesseract_variants'], *config['additional_candidates']]:
        evaluate(candidate_id, development)
    # Full-frame reading coverage first; ties broken by wrong count, then measured processing time.
    def rank(candidate_id):
        summary = summarize([r for r in rows if r['candidate'] == candidate_id and r['mode'] == 'full_frame'])
        return (-summary['correct'], summary['wrong'], summary['processing_p95_ms'] or float('inf'), candidate_id)
    selected = min(config['tesseract_variants'], key=rank)
    if frozen_path is not None:
        previous = json.loads(frozen_path.read_text())
        for key, value in [('config', config), ('manifest_sha256', manifest['sha256']),
                           ('model_sha256', model_hashes), ('source_sha256', source_hashes),
                           ('runtime_versions', environment['runtime_versions'])]:
            if previous[key] != value:
                raise ValueError(f'frozen replay mismatch: {key}')
        selected = previous['selected_tesseract']
        if selected not in config['tesseract_variants']:
            raise ValueError('invalid frozen tesseract variant')
    frozen = {'schema_version': 1, 'config': config, 'manifest_sha256': manifest['sha256'],
              'source_sha256': source_hashes, 'model_sha256': model_hashes, 'selected_tesseract': selected,
              'runtime_versions': environment['runtime_versions'],
              'selection_rule': 'development_full_frame_correct_then_wrong_then_processing_p95',
              'heldout_device_ids': sorted({s['device_id'] for s in heldout}),
              'frozen_before_heldout_inference': True}
    (output/'frozen.json').write_text(json.dumps(frozen,indent=2)+'\n')
    for candidate_id in ['baseline', selected, *config['additional_candidates']]:
        evaluate(candidate_id, heldout)
    summaries = []
    coverage = coverage_summary(manifest['samples'])
    for candidate_id, split, mode in sorted({(r['candidate'], r['split'], r['mode']) for r in rows}):
        subset = [r for r in rows if (r['candidate'],r['split'],r['mode']) == (candidate_id,split,mode)]
        summary = summarize(subset)
        summary.update(candidate=candidate_id, split=split, mode=mode,
                       by_device={str(d): summarize([r for r in subset if r['device_id']==d]) for d in {r['device_id'] for r in subset}},
                       by_condition={c: summarize([r for r in subset if c in r['conditions']]) for c in {c for r in subset for c in r['conditions']}})
        if split == 'heldout' and mode == 'full_frame':
            summary['initial_detection_p95_ms'] = float(np.percentile([r['initial_detection_ms'] for r in subset], 95))
            screening_metrics = dict(summary, detection_p95_ms=summary['initial_detection_p95_ms'])
            summary['screening'] = screening(screening_metrics,coverage,pi_measured=bool(environment['pi_model']))
            summary['screening']['qualified'] = False
            summary['screening']['reasons'].append('selection_tracking_and_condition_coverage_unvalidated')
        summaries.append(summary)
    report = {'schema_version': 1, 'experimental': True, 'production_release_eligible': False,
              'telegram_formatter': None, 'provisional': True, 'serial_output': False,
              'environment': environment, 'coverage': coverage, 'frozen': frozen,
              'candidates': candidate_metadata, 'executable': sys.executable, 'initialization_ms': initializations,
              'candidate_memory': candidate_memory,
              'memory': {'parent_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                         'largest_child_peak_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                         'scope': 'whole_comparison_not_attributable_to_individual_candidates'},
              'summaries': summaries,
              'limitations': ['single_target_annotations_false_detections_unmeasured',
                              'no_selection_tracking_workflow_tested', 'geometry_segment_assignment_unresolved',
                              'single_pass_processing_timings_not_capture_latency']}
    (output/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--frozen', type=Path, help='Replay the saved selection, verifying source/model/data hashes')
    args = parser.parse_args()
    report = run(args.manifest,args.config,args.output,args.frozen)
    print(json.dumps({'coverage':report['coverage'], 'selected_tesseract': report['frozen']['selected_tesseract'],
                      'screening':[{k:s[k] for k in ('candidate','screening')} for s in report['summaries'] if 'screening' in s]},indent=2))


if __name__ == '__main__':
    main()
