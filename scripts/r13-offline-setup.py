#!/usr/bin/env python3
"""R13-Einrichtung aus sync-record-Bildern; kein Kamera- oder Serialzugriff.

Benutzt assist_measure und propose_with_fit der Live-Einrichtung. Die beiden
Einzelbilder ersetzen Aufnahme/Mittelung; ihre Aufnahmezeiten ersetzen das
Warten. Ein Offline-Profil ist keine Freigabe fuer einen Live-Lauf.
"""

from __future__ import annotations

import argparse
import bisect
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import cv2
from _devdata import input_path

from dispread.camera_settings import SETTABLE_CONTROLS, CameraSettings
from dispread.gsv2as_cell_text import cell_text_from_telegram, validate_offline_cell_text
from dispread.live import LIVE_CV_THREADS
from dispread.live import setup as live_setup
from dispread.live.recording import _image, _output_path, load_recording
from dispread.live.reference_eval import MAX_GAP_NS
from dispread.live.session import LiveConfig
from dispread.records import to_boottime_ns
from dispread.setup_checks import RESOLUTION_ERROR_PX

# Dasselbe Minimum wie LiveService._run_setup, gemessen an Aufnahmezeiten.
STABILITY_S = 15.0


def select_stills(recording, frame=None, cell_text=None):
    """Erstes ruhiges Faktor-1-Bild und unabhaengiges Bild im selben Schritt."""
    window = next((i for i, (_, factor) in enumerate(recording.steps) if factor == "1.0"), None)
    if window is None and frame is None:
        raise ValueError("Kein schedule-Schritt mit Faktor 1")
    starts = [step[0] for step in recording.steps]
    rows = []
    previous = -1
    for entry in recording.frames:
        stamp = entry["capture_timestamp"]
        if type(stamp["value_ns"]) is not int or stamp["value_ns"] < 0:
            raise ValueError("Ungueltiger Aufnahmezeitstempel")
        ns = to_boottime_ns(stamp, recording.session)
        if ns < previous:
            raise ValueError("Aufnahmezeitstempel nicht aufsteigend")
        previous = ns
        path = (recording.directory / "frames" / entry["file"]).resolve()
        if not path.is_relative_to((recording.directory / "frames").resolve()):
            raise ValueError("Bild ausserhalb der Aufnahme")
        seconds = ns / 1e9
        index = bisect.bisect_right(starts, seconds) - 1
        rows.append({**entry, "path": path, "t_boottime_ns": ns, "window": index})
    if frame is None:
        first = next((row for row in rows if row["window"] == window
                      and row["t_boottime_ns"] / 1e9 - starts[window] > 2.0), None)
    else:
        requested = Path(frame)
        if not requested.is_absolute():
            requested = recording.directory / "frames" / requested
        first = next((row for row in rows if row["path"] == requested.resolve()), None)
    if first is None:
        raise ValueError("Kein passendes eingeschwungenes Standbild in frames.jsonl")
    window = first["window"]
    if (window < 0 or recording.steps[window][1] == "restore"
            or first["t_boottime_ns"] / 1e9 - starts[window] <= 2.0):
        raise ValueError("Standbild liegt nicht >2 s in einem schedule-Schritt")
    second = next((row for row in rows if row["window"] == window
                   and row["t_boottime_ns"] - first["t_boottime_ns"] >= round(STABILITY_S * 1e9)), None)
    if second is None:
        raise ValueError("Kein Stabilitaetsbild mindestens 15 s spaeter im selben schedule-Schritt")
    serial_times = [entry["t_boot"] for entry in recording.serial]
    for row in (first, second):
        if cell_text is not None:
            row["cell_text"] = validate_offline_cell_text(cell_text)
        else:
            index = bisect.bisect_right(serial_times, row["t_boottime_ns"] / 1e9) - 1
            if index < 0 or row["t_boottime_ns"] / 1e9 - serial_times[index] > MAX_GAP_NS / 1e9:
                raise ValueError("Kein frisches serielles Telegramm am Standbild (hoechstens 1 s alt)")
            row["serial"] = recording.serial[index]["text"]
            row["cell_text"] = cell_text_from_telegram(row["serial"])
    return first, second


def camera_settings(recording):
    """Nur aufgezeichnete Regler uebernehmen, keine Defaults erfinden."""
    camera = recording.session["camera"]
    return CameraSettings.from_dict({
        "model": camera["camera_model"], "usb_id": camera["usb_id"], "size": camera["size"],
        "fourcc": camera["fourcc"], "fps": camera["fps"],
        "controls": {name: camera["controls_readback"][name] for name in SETTABLE_CONTROLS},
        **({"device": camera["device"]} if "device" in camera else {}),
    })


class RecordedStills:
    """Zwei Einzelbilder statt Kamera; Steuereingriffe sind nicht implementiert."""

    def __init__(self, rows):
        self.rows = iter(rows)
        self.current = None

    def fresh_still(self, discard=10):
        self.current = next(self.rows)
        return _image(self.current["path"])

    def text_source(self, capture):
        image = capture()
        return image, self.current["cell_text"]

    def monotonic(self):
        return self.current["t_boottime_ns"] / 1e9


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording_dir", type=input_path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--frame", type=input_path)
    parser.add_argument("--cell-text")
    args = parser.parse_args(argv)
    out = args.out.resolve()
    result = {"schema": "r13-offline-setup/1", "offline": True,
              "recording": str(args.recording_dir.resolve()), "stage": "auswahl", "checks": {}, "attempts": []}
    try:
        _output_path(out)
        if out.is_relative_to(args.recording_dir.resolve()):
            raise ValueError("Ausgabe darf nicht in der Aufnahme liegen")
        # Keine alten Profile nach fehlgeschlagenem Wiederholungsversuch stehen lassen.
        if out.exists() and any(out.iterdir()):
            raise ValueError("Ausgabeverzeichnis muss leer sein")
        out.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        print(f"auswahl: FEHLER: {exc}", file=sys.stderr)
        return 1

    def report(checks):
        result["checks"].update(checks.get("checks", {}))

    try:
        recording = load_recording(args.recording_dir)
        settings = camera_settings(recording)
        first, second = select_stills(recording, args.frame, args.cell_text)
        if any(row["path"].suffix.lower() in (".jpg", ".jpeg") for row in (first, second)):
            print("WARNUNG: JPEG-Quellbilder verzerren den Rasterfit; Offline-Einrichtungsergebnisse "
                  "auf JPEG-Aufnahmen sind fuer die Live-Einrichtung nicht repraesentativ.", file=sys.stderr)
        elapsed = (second["t_boottime_ns"] - first["t_boottime_ns"]) / 1e9
        result.update(first={k: v for k, v in first.items() if k != "path"},
                      second={k: v for k, v in second.items() if k != "path"}, stability_elapsed_s=elapsed)
        # Beide Originale auch bei abgelehntem Fit als Diagnose erhalten.
        for name, row in (("first", first), ("second", second)):
            shutil.copyfile(row["path"], out / f"source-{name}{row['path'].suffix}")
        config = LiveConfig()
        camera = RecordedStills((first, second))
        result["stage"] = "assist_measure"
        measured = live_setup.assist_measure(
            camera, cell_text=camera.text_source, expected_size=settings.size, out_dir=out,
            stability_s=elapsed, min_stability_s=STABILITY_S,
            templates=config.templates, templates_sha256=config.templates_sha256,
            reference_kind="seriell" if args.cell_text is None else "eingabe",
            on_attempt=result["attempts"].append, report=report, info=print,
            sleep=lambda _seconds: None, monotonic=camera.monotonic,
        )
        result["stage"] = "propose_with_fit"
        proposal = live_setup.propose_with_fit(
            measured.first, fit=measured.fit, frame_path=out / "still.png", camera_settings=settings,
            device_id="gsv-sensor-161a", session_id=f"offline-{args.recording_dir.name}", out_dir=out,
            cell_text=measured.first_text, offset_check=measured.offset_check, final_checks=measured.final_checks,
            stability_image_bgr=measured.second, stability_elapsed_s=measured.stability_elapsed_s,
            stability_min_elapsed_s=STABILITY_S, setup_attempt=measured.setup_attempt,
            reader_check=measured.reader_check, live_tracking=True,
        )
        result["checks"] = proposal["setup_checks"]["checks"]
        result["stage"] = "confirm_proposal"
        profile = live_setup.confirm_proposal(
            proposal, confirmed_by="offline-auswertung", resolution_threshold_px=RESOLUTION_ERROR_PX,
        )
        replace(profile, offline=True).save(out / "profile.json")
        result.update(stage="fertig", status="OK", profile=str(out / "profile.json"))
    except (OSError, ValueError, KeyError, TypeError, cv2.error) as exc:
        result.update(status="FEHLER", reason=str(exc))
    result["not_checked"] = [name for name in ("rasterversatz", "gegenlesen", "nachfuehrung", "displayfehler")
                             if name not in result["checks"]]
    (out / "setup-result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    cv2.setNumThreads(LIVE_CV_THREADS)
    raise SystemExit(main())
