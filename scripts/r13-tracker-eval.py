#!/usr/bin/env python3
"""R13 offline: ECC und Rahmenstruktur auf einer sync-record-Aufnahme.

Settled bedeutet > 1,5 s nach resume_transmission eines schedule-Schritts.
Die Faktorzuordnung ist eine Bedienmarke, keine Latenzmessung. Zeitstempel
werden mit dem belegten Session-Versatz nach CLOCK_BOOTTIME umgerechnet.
Nur update() wird gemessen, ohne Bildlesen, Vorschlag und Overlay.
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
from _devdata import input_path

from dispread.live.frame_tracking import FrameTracker, FrameTrackingConfig, propose_regions
from dispread.live.recording import (
    REPO_ROOT,
    _image,
    _output_path,
    load_recording,
    recorded_frames,
)
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
                "frames": len(entries), "kept": kept, "rejected": len(entries)-kept,
                "kept_share": kept / len(entries),
                "reasons": dict(Counter(entry["reason"] or "ok" for entry in entries)),
                "score_kept_frames": _distribution([entry["score"] for entry in entries if entry["kept"]]),
                "corner_deviation_px": _distribution([entry["corner_deviation_px"] for entry in entries if entry["kept"]]),
            }
    return result


def evaluate(recording_dir, profile_path, tracker="both", *, overlay_path=None):
    _output_path(overlay_path)
    recording_dir, profile_path = input_path(recording_dir), input_path(profile_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or not isinstance(profile.get("reference_frame"), dict):
        raise ValueError("Profil und reference_frame muessen JSON-Objekte sein")
    reference_path = profile["reference_frame"]["path"]
    if not isinstance(reference_path, str) or not reference_path:
        raise ValueError("Referenzpfad muss ein nichtleerer Text sein")
    reference = _image(REPO_ROOT / input_path(reference_path))
    try:
        quad = np.asarray(profile["quad"], dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("Ungueltiges Referenzquad") from error
    if quad.shape != (4, 2) or not np.isfinite(quad).all():
        raise ValueError("Ungueltiges Referenzquad")
    recording = load_recording(recording_dir)
    config = FrameTrackingConfig()
    proposal = propose_regions(reference, quad, config)
    trackers = {}
    if tracker in ("ecc", "both"):
        trackers["ecc"] = QuadTracker(reference, quad)
    if tracker in ("frame", "both"):
        trackers["frame"] = FrameTracker(reference, quad, proposal, config)
    timings = defaultdict(list)
    rows = []
    for row, image in recorded_frames(recording, reference.shape):
        row.pop("window")
        row["trackers"] = {}
        for name, instance in trackers.items():
            started = perf_counter_ns()
            result = instance.update(image)
            elapsed_ms = (perf_counter_ns()-started) / 1e6
            timings[name].append(elapsed_ms)
            deviation = None if result.quad is None else float(np.linalg.norm(np.asarray(result.quad)-quad, axis=1).max())
            row["trackers"][name] = {"kept": result.quad is not None, "reason": result.reason,
                                     "score": result.score, "shift": result.shift, "rotation_deg": result.rotation_deg,
                                     "corner_deviation_px": deviation, "update_ms": elapsed_ms}
        rows.append(row)
    summary = {"all": _summary(rows, trackers), "settled": _summary([row for row in rows if row["settled"]], trackers),
               "timing_ms": {name: {"median": float(np.median(values)), "p90": float(np.percentile(values, 90))}
                             for name, values in timings.items()}}
    if overlay_path is not None:
        overlay = draw_overlay(reference, quad, proposal, config)
        if not cv2.imwrite(str(overlay_path), overlay):
            raise ValueError("Overlay konnte nicht geschrieben werden")
    return {"recording": str(recording_dir), "profile": str(profile_path), "config": asdict(config),
            "proposal": {"ok": proposal.ok, "reasons": proposal.reasons, "metrics": proposal.metrics},
            "summary": summary, "frames": rows}


def draw_overlay(reference, quad, proposal, config):
    image = reference.copy()
    for polygon, colour in ((proposal.outer_limit, (255, 150, 0)), (proposal.character_zone, (0, 0, 255)),
                            (quad, (255, 255, 255))):
        cv2.polylines(image, [np.rint(polygon).astype(np.int32)], True, colour, 2)
    for index, region in enumerate(proposal.regions):
        x, y = region.centre
        h = region.size // 2
        r = h + config.search_radius_px + config.interpolation_guard_px
        cv2.rectangle(image, (x-r, y-r), (x+r, y+r), (0, 180, 255), 1)
        cv2.rectangle(image, (x-h, y-h), (x+h, y+h), (255, 0, 255), 1)
        cv2.putText(image, str(index+1), (x+r, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 0, 255), 1)
    for edge in proposal.edges:
        point = tuple(np.rint(edge.point).astype(int))
        cv2.circle(image, point, 2, (0, 255, 255), -1)
    cv2.putText(image, "Weiss: OCR | Rot: Zeichen-Sperre | Blau: Aussengrenze", (20, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
    cv2.putText(image, "Magenta: Patch | Orange: Suche + Interpolation | Gelb: LCD-Rand", (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)
    return image


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording_dir", type=input_path)
    parser.add_argument("--profile", type=input_path, required=True)
    parser.add_argument("--tracker", choices=("ecc", "frame", "both"), default="both")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--overlay", type=Path)
    args = parser.parse_args(argv)
    try:
        _output_path(args.out)
        _output_path(args.overlay)
        result = evaluate(args.recording_dir, args.profile, args.tracker, overlay_path=args.overlay)
        if args.out:
            args.out.write_text(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False)+"\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, cv2.error) as error:
        print(f"Profil/Aufnahme unvollstaendig oder ungueltig: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result["summary"], indent=2, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
