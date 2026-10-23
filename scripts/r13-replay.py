#!/usr/bin/env python3
"""sync-record-Aufnahme offline durch dieselbe Lesekette wie Live verarbeiten.

Keine Kamera, serielle Ausgabe oder Live-Freigabe. Das Gate sieht die
Aufnahmefrequenz (typisch 2-10 Hz), keine hochgerechneten 30 Hz.
Bei etwa 3 Hz filtert die Zweibildbestaetigung ueber rund 333 ms kurzlebige
Fehllesungen heraus, etwa beim Verblassen von LCD-Segmenten. Bei 30 Hz
koennen diese in zwei benachbarten Bildern auftreten und bestaetigt werden:
0 Fehllesungen hier sagt nichts ueber Fehllesungen bei 30 Hz aus.
Die Bewegung zwischen Bildern ist etwa 10-mal groesser, das Tracking wird
seltener aktualisiert; das kann Trackingverluste gegenueber Live erzeugen
oder verbergen. Der Replay prueft Trackingverfuegbarkeit und Leserkorrektheit
je Standbild; er ersetzt keinen 30-Hz-Livelauf.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import cv2
import numpy as np

from dispread.frames import Frame
from dispread.gsv2as_cell_text import cell_text_from_telegram
from dispread.live import LIVE_CV_THREADS
from dispread.live.frame_tracking import FrameTrackingConfig, propose_regions
from dispread.live.recording import _output_path, load_recording, recorded_frames
from dispread.live.reference_eval import evaluate_records
from dispread.live.session import LiveConfig, build_live_pipeline
from dispread.live.tracking import ConfirmedRegionLocator, TrackedQuadLocator
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.records import TimeBaseKind, Timestamp, TimestampSemantics
from dispread.session_profile import SessionProfile


def _summary(rows, session, reference):
    records = [row["record"] for row in rows]
    comparison = evaluate_records(session, reference, records)
    statuses = Counter(record["status"] for record in records)
    reasons = Counter(reason.split(":", 1)[1] for record in records for reason in record["reject_reasons"]
                      if reason.startswith("tracking_lost:"))
    return {
        "frames": len(rows), "by_status": dict(statuses),
        **{f"{status}_share": statuses[status] / len(rows) if rows else None
           for status in ("valid", "transition", "unreadable", "stale")},
        "tracking_loss_reasons": dict(reasons),
        **{key: comparison[key] for key in ("guard_ms", "misreads", "compared_valid", "undecided_valid",
            "uncovered_valid", "changes_after_gap", "stable", "changing", "unknown")},
    }


def evaluate(recording_dir, profile_path, tracker):
    recording = load_recording(recording_dir)
    profile = SessionProfile.load(profile_path)
    regions_source = "profil" if profile.live_tracking is not None else "offline_vorschlag"
    reference_shape = None
    proposal_data = None

    def locator_factory(image, quad):
        nonlocal reference_shape, proposal_data
        reference_shape = image.shape
        if tracker == "ecc":
            return TrackedQuadLocator(image, quad)
        if profile.live_tracking is not None:
            return ConfirmedRegionLocator(image, quad, profile.live_tracking)
        config = FrameTrackingConfig()
        proposal = propose_regions(image, quad, config)
        proposal_data = proposal.to_dict()
        # Nur dieser Offline-Aufruf darf einen unbestaetigten Vorschlag nutzen.
        return ConfirmedRegionLocator(image, quad, {"config": config.to_dict(), "proposal": proposal_data})

    if tracker not in ("ecc", "frame"):
        raise ValueError("Unbekannter Tracker")
    config = LiveConfig()
    pipeline, profile, calibration, _ = build_live_pipeline(
        SimpleNamespace(source_id="sync-record_offline"), Path(profile_path), config,
        reader_factory=DotMatrixReader.from_file, locator_factory=locator_factory,
        reader_d_max_factor=1.0,
        allow_offline=True,
    )
    reference = []
    for entry in recording.serial:
        raw = entry["text"]
        if not isinstance(raw, str):
            raise TypeError("Telegrammtext muss Text sein")
        telegram = {"t_boottime_ns": round(entry["t_boot"] * 1e9), "raw": raw}
        try:
            telegram.update(cell_text=cell_text_from_telegram(raw), value=float(raw.split()[0]))
        except ValueError as error:
            telegram.update(cell_text=None, value=None, error=str(error))
        reference.append(telegram)
    # Referenz vor der Verarbeitung pruefen, auch wenn kein VALID entsteht.
    evaluate_records(recording.session, reference, [])
    rows, timings = [], []
    started = perf_counter()
    for index, (row, image) in enumerate(recorded_frames(recording, reference_shape)):
        stamp = row["capture_timestamp"]
        sequence = recording.frames[index].get("frame_sequence", index + 1)
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise ValueError("Ungueltige Bildsequenz")
        frame = Frame(frame_sequence=sequence, image=image, source_id="sync-record_offline",
                      capture_timestamp=Timestamp(value_ns=stamp["value_ns"], base=TimeBaseKind(stamp["base"]),
                          semantics=TimestampSemantics(stamp.get("semantics", "unknown")),
                          uncertainty_ns=stamp.get("uncertainty_ns")))
        before = perf_counter()
        record = pipeline.process(frame)
        elapsed_ms = (perf_counter() - before) * 1000
        timings.append(elapsed_ms)
        rows.append({**row, "record": record.to_dict(), "process_ms": elapsed_ms})
    wall_s = perf_counter() - started
    summary = _summary(rows, recording.session, reference)
    factors, windows = defaultdict(list), defaultdict(list)
    for row in rows:
        factors[row["factor"]].append(row)
        windows[row["window"]].append(row)
    summary["by_factor"] = {
        factor: {**_summary(group, recording.session, reference),
                 "settled": _summary([row for row in group if row["settled"]], recording.session, reference)}
        for factor, group in factors.items()
    }
    summary["windows"] = [
        {"window": window, "factor": group[0]["factor"],
         "start_boottime_s": recording.steps[window][0] if window >= 0 else None,
         **_summary(group, recording.session, reference),
         "settled": _summary([row for row in group if row["settled"]], recording.session, reference)}
        for window, group in windows.items()
    ]
    summary["processing_fps"] = len(rows) / wall_s
    summary["processing_wall_s"] = wall_s
    summary["frame_time_ms"] = {"median": float(np.median(timings)), "p90": float(np.percentile(timings, 90))}
    capture_span_s = (rows[-1]["t_boottime_ns"] - rows[0]["t_boottime_ns"]) / 1e9
    return {
        "schema": "r13-replay/1", "offline": True, "recording": str(recording_dir), "profile": str(profile_path),
        "tracker": tracker, "regions_source": regions_source if tracker == "frame" else None,
        "offline_proposal": proposal_data,
        "templates": {"path": str(config.templates), "sha256": config.templates_sha256, "d_max_factor": 1.0},
        "calibration": {"path": str(config.calibration), "display_offset_ms": calibration.display_offset_ms,
                        "applied": False},
        "gate": {**asdict(pipeline.gate.config), "blocking_flags": sorted(pipeline.gate.config.blocking_flags)},
        "recording_fps": (len(rows) - 1) / capture_span_s if capture_span_s > 0 else None,
        "timing_note": "Gate mit Aufnahmezeiten und Aufnahmefrequenz, keine 30-Hz-Live-Abnahme. "
                       "Bei etwa 3 Hz filtert Zweibildbestaetigung ueber rund 333 ms kurzlebige Fehllesungen "
                       "(z.B. beim Verblassen von LCD-Segmenten), die bei 30 Hz in zwei benachbarten Bildern "
                       "auftreten und bestaetigt werden koennen. 0 Fehllesungen hier sagt nichts ueber "
                       "Fehllesungen bei 30 Hz aus. Bewegung zwischen Bildern ist etwa 10-mal groesser, "
                       "Tracking wird seltener aktualisiert; das kann Trackingverluste gegenueber Live "
                       "erzeugen oder verbergen. Der Replay prueft Trackingverfuegbarkeit und "
                       "Leserkorrektheit je Standbild; er ersetzt keinen 30-Hz-Livelauf. "
                       "processing_fps: Schleife samt Bildlesen; frame_time_ms: nur Pipeline.process.",
        "reference": {"lines": len(reference), "parse_errors": sum(bool(entry.get("error")) for entry in reference)},
        "summary": summary, "frames": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording_dir", type=Path)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--tracker", choices=("ecc", "frame"), required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        _output_path(args.out)
        # Wie beim Dienststart, einmal fuer diesen Offline-Prozess gesetzt.
        cv2.setNumThreads(LIVE_CV_THREADS)
        result = evaluate(args.recording_dir, args.profile, args.tracker)
        if args.out:
            args.out.write_text(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
                                encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, cv2.error) as error:
        print(f"Profil/Aufnahme unvollstaendig oder ungueltig: {error}", file=sys.stderr)
        return 1
    summary = result["summary"]
    print(f"Offline-Replay {args.tracker}: {summary['frames']} Bilder; "
          f"Fehllesungen {summary['misreads']}/{summary['compared_valid']} entschiedene VALID; "
          f"Regionen: {result['regions_source'] or 'ECC'}")
    print(f"Abgelehnte Referenztelegramme: {result['reference']['parse_errors']}")
    print(f"VALID {summary['valid_share']:.1%}, TRANSITION {summary['transition_share']:.1%}, "
          f"UNREADABLE {summary['unreadable_share']:.1%}, STALE {summary['stale_share']:.1%}; "
          f"Trackingverluste: {summary['tracking_loss_reasons']}")
    print(f"Verarbeitung {summary['processing_fps']:.2f} Bilder/s; Pipeline Median/p90 "
          f"{summary['frame_time_ms']['median']:.2f}/{summary['frame_time_ms']['p90']:.2f} ms")
    return int(summary["misreads"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
