#!/usr/bin/env python3
"""R13 offline: ECC und Rahmenstruktur auf einer sync-record-Aufnahme.

Settled bedeutet > 1,5 s nach resume_transmission eines schedule-Schritts.
Die Faktorzuordnung ist eine Bedienmarke, keine Latenzmessung. Zeitstempel
werden mit dem belegten Session-Versatz nach CLOCK_BOOTTIME umgerechnet.
Nur update() wird gemessen, ohne Bildlesen, Vorschlag und Overlay.
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns

import cv2
import numpy as np

from dispread.live.frame_tracking import FrameTracker, FrameTrackingConfig, propose_regions
from dispread.records import to_boottime_ns
from dispread.track import QuadTracker

REPO_ROOT = Path(__file__).resolve().parents[1]


def _rows(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"JSON-Objekte erforderlich: {path.name}")
    if not rows:
        raise ValueError(f"Leere Datei: {path.name}")
    return rows


def _image(path):
    if not path.is_file():
        raise ValueError(f"Bild fehlt: {path}")
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Bild nicht lesbar: {path}")
    return image


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


def _output_path(path):
    if path is not None and path.resolve().is_relative_to((REPO_ROOT / "var").resolve()):
        raise ValueError("Ausgabe unter var/ ist nicht erlaubt")


def evaluate(recording_dir, profile_path, tracker="both", *, overlay_path=None):
    _output_path(overlay_path)
    recording_dir, profile_path = Path(recording_dir), Path(profile_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or not isinstance(profile.get("reference_frame"), dict):
        raise ValueError("Profil und reference_frame muessen JSON-Objekte sein")
    reference_path = profile["reference_frame"]["path"]
    if not isinstance(reference_path, str) or not reference_path:
        raise ValueError("Referenzpfad muss ein nichtleerer Text sein")
    reference = _image(REPO_ROOT / reference_path)
    try:
        quad = np.asarray(profile["quad"], dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("Ungueltiges Referenzquad") from error
    if quad.shape != (4, 2) or not np.isfinite(quad).all():
        raise ValueError("Ungueltiges Referenzquad")
    session = json.loads((recording_dir / "session.json").read_text(encoding="utf-8"))
    if not isinstance(session, dict):
        raise ValueError("Session muss ein JSON-Objekt sein")
    offsets = session.get("clock_offset_boottime_minus_monotonic_ns")
    if offsets is not None and (not isinstance(offsets, dict)
            or any(offsets.get(key) is not None and not isinstance(offsets[key], int) for key in ("start", "end"))):
        raise ValueError("Ungueltiger clock_offset_boottime_minus_monotonic_ns")
    frames = _rows(recording_dir / "frames.jsonl")
    commands = _rows(recording_dir / "commands.jsonl")
    serial = _rows(recording_dir / "serial.jsonl")
    for key, entries in (("frames_recorded", frames), ("serial_lines_recorded", serial),
                         ("commands_jsonl_event_count", commands)):
        if key in session and session[key] != len(entries):
            raise ValueError(f"Zeilenzahl passt nicht zu {key}")
    for key in ("frames_dropped_queue_full", "frames_dropped_write_failed", "acquisition_error", "commands_write_error", "aborted"):
        if session.get(key):
            raise ValueError(f"Aufnahme meldet {key}: {session[key]}")
    if session.get("frame_writer_finished") is False:
        raise ValueError("Bildschreiber nicht abgeschlossen")
    steps = []
    for entry in commands:
        label = entry.get("label", "")
        if not isinstance(label, str):
            raise ValueError("Befehlsmarke muss Text sein")
        if entry.get("event") == "resume_transmission" and label.startswith("schedule["):
            _, separator, factor_text = label.partition("factor=")
            if not separator or not np.isfinite(float(factor_text)):
                raise ValueError("Ungueltige schedule-Faktormarke")
            factor = str(float(factor_text))
            steps.append((float(entry["t_boot"]), factor))
        elif entry.get("event") == "resume_transmission" and label == "restore":
            steps.append((float(entry["t_boot"]), "restore"))
    if not any(factor != "restore" for _, factor in steps):
        raise ValueError("Keine schedule-Wiederanlaufmarken")
    starts = [step[0] for step in steps]
    serial_times = [float(entry["t_boot"]) for entry in serial]
    if starts != sorted(starts) or serial_times != sorted(serial_times):
        raise ValueError("Zeitmarken nicht aufsteigend")
    config = FrameTrackingConfig()
    proposal = propose_regions(reference, quad, config)
    trackers = {}
    if tracker in ("ecc", "both"):
        trackers["ecc"] = QuadTracker(reference, quad)
    if tracker in ("frame", "both"):
        trackers["frame"] = FrameTracker(reference, quad, proposal, config)
    timings = defaultdict(list)
    rows = []
    for frame in frames:
        stamp = frame["capture_timestamp"]
        if not isinstance(stamp, dict) or not isinstance(stamp.get("value_ns"), int):
            raise ValueError("Ungueltiger Aufnahmezeitstempel")
        if not isinstance(frame["file"], str):
            raise ValueError("Bilddateiname muss Text sein")
        boot_ns = to_boottime_ns(stamp, session)
        seconds = boot_ns / 1e9
        index = bisect.bisect_right(starts, seconds)-1
        serial_index = bisect.bisect_right(serial_times, seconds)-1
        image = _image(recording_dir / "frames" / frame["file"])
        if image.shape != reference.shape:
            raise ValueError(f"Bildgroesse weicht ab: {frame['file']}")
        row = {"file": frame["file"], "capture_timestamp": stamp, "t_boottime_ns": boot_ns,
               "factor": steps[index][1] if index >= 0 else "vor_plan",
               "settled": index >= 0 and steps[index][1] != "restore" and seconds-starts[index] > 1.5,
               "serial": serial[serial_index]["text"] if serial_index >= 0 else None, "trackers": {}}
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
    parser.add_argument("recording_dir", type=Path)
    parser.add_argument("--profile", type=Path, required=True)
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
