"""sync-record-Dateien und Werteplan-Zuordnung fuer Offline-Auswertungen."""

from __future__ import annotations

import bisect
import json
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from dispread.records import to_boottime_ns

REPO_ROOT = Path(__file__).resolve().parents[3]


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


def _output_path(path):
    if path is not None and path.resolve().is_relative_to((REPO_ROOT / "var").resolve()):
        raise ValueError("Ausgabe unter var/ ist nicht erlaubt")


def _seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Ungueltige Zeitmarke")
    return float(value)


@dataclass(frozen=True)
class SyncRecording:
    directory: Path
    session: dict
    frames: list[dict]
    serial: list[dict]
    steps: list[tuple[float, str]]


def load_recording(recording_dir, *, allow_no_plan=False):
    """Fehlende Befehlsdatei optional als Segment ohne_plan zulassen.

    Vorhandene, aber ungueltige Befehlsdateien bleiben Fehler. Die bestehende
    Integritaets- und Zeitbasispruefung gilt auch ohne Werteplan.
    """
    recording_dir = Path(recording_dir)
    session = json.loads((recording_dir / "session.json").read_text(encoding="utf-8"))
    if not isinstance(session, dict):
        raise ValueError("Session muss ein JSON-Objekt sein")
    offsets = session.get("clock_offset_boottime_minus_monotonic_ns")
    if offsets is not None and (not isinstance(offsets, dict)
            or any(offsets.get(key) is not None and not isinstance(offsets[key], int) for key in ("start", "end"))):
        raise ValueError("Ungueltiger clock_offset_boottime_minus_monotonic_ns")
    frames = _rows(recording_dir / "frames.jsonl")
    commands_path = recording_dir / "commands.jsonl"
    without_plan = allow_no_plan and not commands_path.exists()
    commands = [] if without_plan else _rows(commands_path)
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
            steps.append((_seconds(entry["t_boot"]), factor))
        elif entry.get("event") == "resume_transmission" and label == "restore":
            steps.append((_seconds(entry["t_boot"]), "restore"))
    if without_plan:
        first_stamp = frames[0]["capture_timestamp"]
        steps = [(to_boottime_ns(first_stamp, session) / 1e9, "ohne_plan")]
    if not any(factor != "restore" for _, factor in steps):
        raise ValueError("Keine schedule-Wiederanlaufmarken")
    starts = [step[0] for step in steps]
    serial_times = [_seconds(entry["t_boot"]) for entry in serial]
    if starts != sorted(starts) or serial_times != sorted(serial_times):
        raise ValueError("Zeitmarken nicht aufsteigend")
    return SyncRecording(recording_dir, session, frames, serial, steps)


def recorded_frames(recording, reference_shape):
    """Dateireihenfolge, BGR und originale Aufnahmezeitstempel beibehalten."""
    starts = [step[0] for step in recording.steps]
    serial_times = [_seconds(entry["t_boot"]) for entry in recording.serial]
    previous_ns = None
    for frame in recording.frames:
        stamp = frame["capture_timestamp"]
        if (not isinstance(stamp, dict) or type(stamp.get("value_ns")) is not int
                or stamp["value_ns"] < 0):
            raise ValueError("Ungueltiger Aufnahmezeitstempel")
        uncertainty = stamp.get("uncertainty_ns")
        if uncertainty is not None and (type(uncertainty) is not int or uncertainty < 0):
            raise ValueError("Ungueltige Zeitunsicherheit; unbekannt muss null sein")
        if not isinstance(frame["file"], str):
            raise ValueError("Bilddateiname muss Text sein")
        boot_ns = to_boottime_ns(stamp, recording.session)
        if previous_ns is not None and boot_ns < previous_ns:
            raise ValueError("Aufnahmezeitstempel nicht aufsteigend")
        previous_ns = boot_ns
        seconds = boot_ns / 1e9
        index = bisect.bisect_right(starts, seconds)-1
        serial_index = bisect.bisect_right(serial_times, seconds)-1
        image = _image(recording.directory / "frames" / frame["file"])
        if image.shape != reference_shape:
            raise ValueError(f"Bildgroesse weicht ab: {frame['file']}")
        row = {"file": frame["file"], "capture_timestamp": stamp, "t_boottime_ns": boot_ns,
               "factor": recording.steps[index][1] if index >= 0 else "vor_plan",
               "settled": index >= 0 and recording.steps[index][1] != "restore" and seconds-starts[index] > 1.5,
               "serial": recording.serial[serial_index]["text"] if serial_index >= 0 else None, "window": index}
        yield row, image
