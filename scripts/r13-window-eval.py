#!/usr/bin/env python3
"""R13 Offline-Vergleich: LCD-Fenster, eingefrorener Rahmen und ECC.

Ohne commands.jsonl: ein Segment ohne_plan ab dem ersten Aufnahmezeitstempel;
settled heisst >1.5 s danach. Mit Plan gilt die schedule-Wiederanlaufmarke.
Zeitbasen und Aufnahmeintegritaet werden durch recording.py geprueft.
Eckenabweichungen sind Abstaende zum festen Referenzquad, KEINE gemessenen
Trackingfehler (keine unabhaengige Frame-Geometrie vorhanden). Nur update()
wird zeitlich gemessen, ohne Bildlesen und Vorschlag. JSON-Ausgaben ausserhalb
var/, keine Bildausgaben oder Aenderungen an Aufnahmen.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns

import cv2
import numpy as np

from dispread.live.frame_tracking import FrameTracker, FrameTrackingConfig, propose_regions
from dispread.live.recording import REPO_ROOT, _image, _output_path, load_recording, recorded_frames
from dispread.live.window_tracking import WindowTracker, WindowTrackingConfig, propose_window
from dispread.track import QuadTracker


def _distribution(values):
    return {"median": float(np.median(values)), "max": float(max(values))} if values else {"median": None, "max": None}


def _summary(rows, names):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["factor"]].append(row)
    result = {}
    for factor, frames in grouped.items():
        result[factor] = {}
        for name in names:
            entries = [frame["trackers"][name] for frame in frames]
            kept = sum(entry["kept"] for entry in entries)
            result[factor][name] = {
                "frames": len(entries), "kept": kept, "kept_share": kept/len(entries),
                "reasons": dict(Counter(entry["reason"] or "ok" for entry in entries)),
                "corner_deviation_px": _distribution([entry["corner_deviation_px"] for entry in entries if entry["kept"]]),
                "timing_ms": _distribution([entry["update_ms"] for entry in entries]),
            }
    return result


def evaluate(recording_dir, profile_path, tracker="all"):
    if tracker not in ("window", "frame", "ecc", "all"):
        raise ValueError("Unbekannter Tracker")
    profile_path, recording_dir = Path(profile_path), Path(recording_dir)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or not isinstance(profile.get("reference_frame"), dict):
        raise ValueError("Profil und reference_frame muessen JSON-Objekte sein")
    reference_path = profile["reference_frame"]["path"]
    if not isinstance(reference_path, str) or not reference_path:
        raise ValueError("Referenzpfad muss ein nichtleerer Text sein")
    reference = _image(REPO_ROOT / reference_path)
    quad = np.asarray(profile["quad"], dtype=float)
    if quad.shape != (4, 2) or not np.isfinite(quad).all():
        raise ValueError("Ungueltiges Referenzquad")
    recording = load_recording(recording_dir, allow_no_plan=True)
    trackers, configs, proposals = {}, {}, {}
    if tracker in ("window", "all"):
        config = WindowTrackingConfig()
        model = propose_window(reference, quad, config)
        trackers["window"] = WindowTracker(reference, quad, model, config)
        configs["window"] = asdict(config)
        proposals["window"] = {"ok": model.ok, "points_per_side": [sum(e.side == side for e in model.edges) for side in range(4)]}
    if tracker in ("frame", "all"):
        config = FrameTrackingConfig()
        proposal = propose_regions(reference, quad, config)
        trackers["frame"] = FrameTracker(reference, quad, proposal, config)
        configs["frame"] = asdict(config)
        proposals["frame"] = {"ok": proposal.ok, "reasons": proposal.reasons, "metrics": proposal.metrics}
    if tracker in ("ecc", "all"):
        trackers["ecc"] = QuadTracker(reference, quad)
        configs["ecc"] = asdict(trackers["ecc"].config)
    rows, timings = [], defaultdict(list)
    for row, image in recorded_frames(recording, reference.shape):
        row.pop("window")
        row["trackers"] = {}
        for name, instance in trackers.items():
            started = perf_counter_ns()
            result = instance.update(image)
            elapsed_ms = (perf_counter_ns()-started)/1e6
            timings[name].append(elapsed_ms)
            deviation = None if result.quad is None else float(np.linalg.norm(np.asarray(result.quad)-quad, axis=1).max())
            row["trackers"][name] = {"kept": result.quad is not None, "reason": result.reason,
                                     "score": result.score, "shift": result.shift, "rotation_deg": result.rotation_deg,
                                     "corner_deviation_px": deviation, "update_ms": elapsed_ms}
        rows.append(row)
    return {"recording": str(recording_dir), "profile": str(profile_path), "config": configs,
            "proposals": proposals, "corner_deviation_basis": "fixed_reference_quad_not_ground_truth",
            "summary": {"all": _summary(rows, trackers),
                        "settled": _summary([row for row in rows if row["settled"]], trackers),
                        "timing_ms": {name: _distribution(values) for name, values in timings.items()}}, "frames": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording_dir", type=Path)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--tracker", choices=("window", "frame", "ecc", "all"), default="all")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        _output_path(args.out)
        result = evaluate(args.recording_dir, args.profile, args.tracker)
        encoded = json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False)
        if args.out:
            args.out.write_text(encoded+"\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, cv2.error) as error:
        print(f"Profil/Aufnahme unvollstaendig oder ungueltig: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result["summary"], indent=2, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
