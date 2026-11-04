"""Nur fuer Playwright: HTTPS-Werkbank mit skriptbarem Live-Status, ohne Hardware."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
import ssl
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from aiohttp import web

from dispread.charcells import CharGrid
from dispread.live import RELEASE_NOTICE
from dispread.live.preview import PreviewFrame
from dispread.live.service import OVERLAYS
from dispread.records import TimeBaseKind, Timestamp
from dispread.workbench.fields import REASONS, live_cause
from dispread.workbench.server import make_app

HOST = "127.0.0.1"
PORT = 8767
FIXTURES = Path(__file__).parent / "fixtures" / "live"
SCENES = (
    "idle", "setup_focus", "setup_focus_done", "setup_standbilder", "setup_ready_warnung",
    "running_valid", "running_transition", "running_rahmen_verdeckt", "running_stalled",
    "running_anzeige_bewegt", "stopped",
)
# Aus live-20261030T133635Z/setup; keine Laufzeitabhaengigkeit von var/.
FOCUS_SAMPLES = [[48, 630.3558194010419], [56, 273.53271242939513], [40, 201.1113182858314],
                 [42, 301.5480297000838], [44, 442.0887939597047], [46, 542.9752734088474],
                 [50, 607.4170064667126], [52, 525.0128897387846], [54, 391.07734162279286]]
REGION_CENTRES = [[873, 385], [915, 737], [1256, 422], [1485, 658], [829, 411], [822, 737],
                  [1310, 437], [1457, 635], [877, 459], [858, 742], [1291, 391], [1321, 707]]
# Zwoelf echte Bereiche lassen im 2-KB-HUD Platz fuer alle 16 Zellen.
QUAD = [[810, 511], [1369, 511], [1377, 580], [814, 591]]
CAMERA_SOURCE = {"model": "logitech_streamcam", "usb_id": "046d:0893", "size": [1920, 1080],
                 "fourcc": "YUYV", "fps": 30, "device": "/dev/video0", "controls": {
                     "focus_absolute": 48, "exposure_time_absolute": 300,
                     "white_balance_temperature": 4742, "gain": 10}}


def scene_state(name):
    """Deterministische Szenen; synthetische Zeiten sind keine Messbelege."""
    if name not in SCENES:
        raise ValueError(f"Unbekannte Szene: {name}")
    if name == "idle":
        return {"state": name}
    if name == "stopped":
        return {**scene_state("setup_ready_warnung"), "state": name}
    focus = name in ("setup_focus", "setup_focus_done")
    ready = name == "setup_ready_warnung" or name.startswith("running_")
    step = "fokus" if focus else "vorschlag" if ready else "standbilder"
    keys = ["fokus", "kamera", "belichtung", "standbilder", "vorschlag"]
    durations = [21.3, 2.0, 4.1, 9.0, 1.0]
    steps = [{"key": key, "state": "done" if ready or i < keys.index(step) else (
        "running" if key == step else "pending"),
        "elapsed_s": (5.0 if focus else durations[i]) if ready or i <= keys.index(step) else None}
        for i, key in enumerate(keys)]
    setup = {
        "grid": None,
        "step": step, "elapsed_s": 5.0 if focus else 36.4,
        "focus": {"method": "climb", "samples": copy.deepcopy(FOCUS_SAMPLES[:3] if name == "setup_focus"
                                                               else FOCUS_SAMPLES),
                  "verify": None if name == "setup_focus" else {
                      "score": 624.465370104453, "threshold": 0.85 * FOCUS_SAMPLES[0][1]}},
        "exposure": {"target": 130, "band": [115, 150], "rounds": [] if focus else [
            {"level": 124.0, "controls": copy.deepcopy(CAMERA_SOURCE["controls"])}]},
        "progress": {"steps": steps, "attempt": 1, "attempts_max": 3,
                     "phase": None if focus or ready else "stabilitaet",
                     "wait": None if focus or ready else {"elapsed_s": 9, "total_s": 15}},
        "checks_live": {} if focus else {"kontrast": {"status": "OK", "reason": None}},
    }
    if ready:
        grid = CharGrid(n_cells=16, left=0, pitch=25, top=17.78, bottom=160)
        setup["grid"] = {"target_size": [400, 160],
                         "cell_boxes": [[round(float(v), 2) for v in box] for box in grid.cell_boxes()],
                         "source": "dot_lattice"}
        checks = dict.fromkeys(("kontrast", "kanten", "rahmen", "glanz", "belichtung", "aufloesung",
                                "stabilitaet", "rasterversatz", "gegenlesen", "displayfehler", "nachfuehrung"), "OK")
        setup.update(overall="WARNUNG", checks={**checks, "raster": "WARNUNG"},
                     overlays=list(OVERLAYS), proposal_revision="b358259f721241f0b9e6af42d4fdb390",
                     regions=[{"centre": c.copy(), "size": 15} for c in REGION_CENTRES],
                     auswahl="automatisch", centre_results=[])
    state = {"state": "setup_ready" if ready else "setup_running", "setup": setup}
    if not name.startswith("running_"):
        return state
    status = "transition" if name == "running_transition" else (
        "unreadable" if name in ("running_rahmen_verdeckt", "running_anzeige_bewegt") else "valid")
    reasons = [] if status == "valid" else ["anzeige_wechselt" if status == "transition"
                                           else "tracking_lost:rahmen_unstimmig"]
    age = 2.0 if name == "running_stalled" else 0.04
    state.update(state="running", run={
        "latest": {"frame_sequence": 51233, "status": status, "value": 0.62427 if status == "valid" else None,
                   "unit": "mV/V", "raw_text": "+0.62427", "reject_reasons": reasons,
                   "frames_confirmed": 3 if status == "valid" else 0, "confirmation_span_ns": 100_000_000,
                   "capture_timestamp": Timestamp(value_ns=1_730_000_000_000, base=TimeBaseKind.SYNTHETIC).to_dict()},
        "summary": {"marks": 0, "by_status": {"valid": 842, "transition": 12, "unreadable": 4},
                    "transition_display_changing": 12, "frames_read": 858, "tolerance_frames": 0,
                    "frames_skipped": 2, "frame_gaps": 0, "frame_gaps_owner_total": 0, "audit_errors": 0,
                    "tracking_lost": 4, "tracking_coarse_retries": 0, "tracking_coarse_accepted": 0,
                    "tracking_lost_reasons": {}, "tracking_hints": {"count": 0,
                        "by_kind": {"anzeige_bewegt": 0, "rahmen_verdeckt": 0, "unbekannt": 0}, "max_shift_px": None},
                    "track_score": {"min": 0.43, "median": 0.93, "max": 0.98, "n": 858},
                    "camera_error": None, "end_reason": None},
        "counts": {"valid": 842, "transition": 12, "unreadable": 4, "stale": 0},
        "recent": [[0, "v", 0.62427], [250, "v", 0.62427], [500, status[0],
                    0.62427 if status == "valid" else None]], "recent_now_ms": 2500 if age > 0.5 else 540,
        "dir": "run-01", "latest_age_s": age, "guess": None,
        "tracking": {"mode": "frame_local", "profile_mode": "frame_local", "version": 1,
                     "regions": len(REGION_CENTRES)},
        "tracking_hint": None,
        "rejection_causes": {"window_s": 10.0, "frames": 10, "limited": False, "causes": []},
    })
    state["diagnostics"] = {"enabled": False, "reason": "vom Bediener deaktiviert", "saved": 0,
                            "bytes": 0, "dropped_queue": 0, "dropped_limit": 0, "dropped_memory": 0,
                            "dropped_mark_rate": 0, "write_errors": 0, "first_error": None,
                            "staging": None, "copied": False}
    if name == "running_anzeige_bewegt":
        state["run"]["tracking_hint"] = {"kind": "anzeige_bewegt", "shift_px": 19,
                                         "region_shift_px": 27, "rotation_deg": -2.23, "since_s": 3}
    if name == "running_stalled":
        state["camera"] = {"running": True, "stalled": True, "frames": 51234, "gaps": 0,
                           "error": "Streamstillstand: kein Bild seit 2.0 s",
                           "source": copy.deepcopy(CAMERA_SOURCE), "last_start": None}
    return state


class FakeController:
    def snapshot(self):
        return {"live": False}


class FakeTerminals:
    def list(self):
        return []


class FakeLiveService:
    def __init__(self, image_path):
        self._lock = threading.Lock()
        self._image_path = image_path
        image = np.zeros((24, 48, 3), dtype=np.uint8)
        self._legacy_image = image
        cv2.imwrite(str(image_path), image)
        self._jpeg = cv2.imencode(".jpg", image)[1].tobytes()
        self._scene_image = cv2.resize(cv2.imread(str(FIXTURES / "still.jpg")), (1920, 1080))
        self._scene_jpeg = cv2.imencode(".jpg", cv2.resize(self._scene_image, (960, 540)),
                                       [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
        self._scene = None
        self._sequence = 51234
        self._frame_due = 0.0
        self.set_state({})

    def set_state(self, state):
        with self._lock:
            self._scene = None
            cv2.imwrite(str(self._image_path), self._legacy_image)
            self._status = {
                "state": "idle", "error": None, "setup": None, "run": None, "reader_tolerance": None,
                "session_id": "test-session", "release_notice": "Validiert nur: Testaufbau",
                "camera": {"running": True, "stalled": False, "error": None, "frames": 1, "gaps": 0,
                           "source": copy.deepcopy(CAMERA_SOURCE), "last_start": None}, "diagnostic_leftovers": [],
                "storage": {"free_bytes": 4_200_000_000, "reserve_bytes": 2_000_000_000, "level": "warn",
                            "message": "4.20 GB frei"},
                "step": None, "simulate": False, "profile": None, "run_block": None, "test_run": None,
                "diagnostics": {"enabled": False, "reason": "kein Diagnoselauf"},
                "diagnose_kopie": False, "last_mark": None,
                "reference": {"enabled": False, "reason": "kein Referenzlauf"},
                **copy.deepcopy(state),
            }

    def set_scene(self, name):
        self.set_state(scene_state(name))
        with self._lock:
            self._scene = name
            self._sequence += 1  # Auch der letzte Teil einer Stallszene traegt deren HUD.
            self._status["release_notice"] = RELEASE_NOTICE
            # Alte Playwright-Hooks behalten ihr 48x24-Overlay. Szenen haben
            # Quellbildkoordinaten fuer das echte 1920x1080-Standbild.
            cv2.imwrite(str(self._image_path), self._scene_image)
            self._frame_due = 0.0

    def bump_revision(self):
        from dispread.live.service import LiveError

        with self._lock:
            setup = self._status.get("setup") or {}
            if not setup.get("proposal_revision"):
                raise LiveError("Kein aktueller Vorschlag zum Bearbeiten")
            setup["proposal_revision"] += "-bump"
            return setup["proposal_revision"]

    def status(self, *, full=False):
        with self._lock:
            data = copy.deepcopy(self._status)
            if full:
                data["tracking_reasons"] = REASONS.copy()
            if data.get("run") is not None:
                data["run"].setdefault("tracking_hint", None)
                window = data["run"].setdefault("rejection_causes",
                    {"window_s": 10.0, "frames": 0, "limited": False, "causes": []})
                window["causes"] = [live_cause(c) for c in window["causes"]]
            return data

    def start_setup(self, *, cell_text=None):
        self.set_scene("setup_focus")

    def edit_regions(self, *, proposal_revision, add, remove):
        from dispread.live.service import LiveError, LiveInputError

        with self._lock:
            setup = self._status.get("setup")
            if self._status["state"] != "setup_ready" or not setup:
                raise LiveError("Kein aktueller Vorschlag zum Bearbeiten")
            if proposal_revision != setup.get("proposal_revision"):
                raise LiveError("Vorschlag hat sich geaendert")
            if not isinstance(add, list) or not isinstance(remove, list) or not (add or remove):
                raise LiveInputError("Bereichsaenderung braucht Listen add und remove mit mindestens einer Aenderung")
            if (any(type(index) is not int or not 0 <= index < len(setup['regions']) for index in remove)
                    or len(set(remove)) != len(remove)):
                raise LiveInputError("Ungueltiger oder doppelter Bereichsindex")
            height, width = cv2.imread(str(self._image_path)).shape[:2]
            for point in add:
                if (not isinstance(point, list) or len(point) != 2
                        or any(type(value) not in (int, float) or (type(value) is float and not math.isfinite(value))
                               for value in point)):
                    raise LiveInputError("Bereich braucht zwei endliche Pixelkoordinaten")
                if not (0 <= point[0] < width and 0 <= point[1] < height):
                    raise LiveInputError("Bereichskoordinaten liegen ausserhalb des Quellbilds")
            regions = [region for index, region in enumerate(setup["regions"]) if index not in remove]
            # Wie proposal_from_regions: erst die behaltenen, dann die neuen Punkte;
            # ein Punkt im Anzeige-Viereck wird mit im_zeichenbereich abgelehnt
            # und nie als Bereich verwendet.
            results = [{"requested_centre": r["centre"], "centre": r["centre"],
                        "used_centre": r["centre"], "ok": True, "reason": None} for r in regions]
            quad = np.array(QUAD, dtype=np.float32)
            for point in add:
                inside = bool(self._scene) and cv2.pointPolygonTest(quad, (float(point[0]), float(point[1])), False) >= 0
                results.append({"requested_centre": point, "centre": point, "used_centre": point,
                                "ok": not inside, "reason": "im_zeichenbereich" if inside else None})
                if not inside:
                    regions.append({"centre": point, "size": 5})
            setup["regions"] = regions
            setup["proposal_revision"] += "-edit"
            setup["auswahl"] = "manuell"
            setup["centre_results"] = results
            setup["checks"]["nachfuehrung"] = setup["overall"] = "OK" if regions else "FEHLER"
            return {"proposal_revision": setup["proposal_revision"], "centre_results": setup["centre_results"]}

    def confirm(self, *, session_id, **kwargs):
        from dispread.live.service import LiveError

        with self._lock:
            setup = self._status.get("setup") or {}
            if (session_id != self._status["session_id"]
                    or ("proposal_revision" in kwargs and kwargs["proposal_revision"] != setup.get("proposal_revision"))):
                raise LiveError("Vorschlag hat sich geaendert — bitte neu pruefen")
            self._status["state"] = "confirmed"

    def start_run(self, *, test_override=False, reference=True, norm_schedule=None, diagnostics=False, output=None):
        self.set_scene("running_valid")
        with self._lock:
            self._status["diagnostics"] = {"enabled": diagnostics, "saved": 0,
                        "bytes": 0, "dropped_queue": 0, "dropped_limit": 0, "dropped_memory": 0,
                        "dropped_mark_rate": 0, "write_errors": 0}
            if test_override:
                self._status["test_run"] = {"testlauf": True, "run_block": "Lauf gesperrt: Gegenlesen WARNUNG",
                                            "confirmed_by": "Test", "started_at_utc": "2026-11-04T12:00:00Z",
                                            "hinweis": "Lesesperre uebergangen. Werte nicht freigegeben, nicht fuer Messungen verwenden."}
                latest = self._status["run"]["latest"]
                latest.update(status="unreadable", value=None, reject_reasons=["testlauf_keine_freigabe"])
                self._status["run"]["counts"] = {"valid": 0, "transition": 0, "unreadable": 858, "stale": 0}
                self._status["run"]["recent"] = [[0, "u", None], [250, "u", None], [500, "u", None]]

    def mark(self, text):
        with self._lock:
            self._status['last_mark'] = {'text': text, 'zeit': 'meldezeit_bediener',
                                         'received_at_utc': '2026-10-21T10:00:00Z'}

    def stop_run(self):
        self.set_state({"state": "stopped"})

    def start_camera(self):
        pass

    def setup_file(self, name):
        with self._lock:
            overlays = (self._status.get("setup") or {}).get("overlays", [])
            return self._image_path if name in overlays else None

    def preview_jpeg(self):
        return self.preview_frame().jpeg

    def preview_frame(self):
        with self._lock:
            now = time.monotonic()
            if now >= self._frame_due and self._scene != "running_stalled":
                self._sequence += 1
                self._frame_due = now + 1 / 15
            seq = self._sequence
            cap_ns = 1_730_000_000_000 + (seq - 51234) * 66_666_667
            run = self._status.get("run") if self._status["state"] == "running" else None
            rec = track = cells = proc = None
            if run and run.get("latest"):
                latest = run["latest"]
                age = run.get("latest_age_s")
                rec = {"seq": latest["frame_sequence"], "status": "stale" if age is not None and age > 0.5
                       else latest["status"], "text": latest["raw_text"], "unit": latest["unit"],
                       "reasons": latest["reject_reasons"], "age_s": age}
                lost = self._scene in ("running_rahmen_verdeckt", "running_anzeige_bewegt")
                track = {"quad": copy.deepcopy(QUAD), "score": 0.43 if lost else 0.93,
                         "shift_px": 0.4, "rotation_deg": 0.0, "reason": "rahmen_unstimmig" if lost else None,
                         "correcting": False, "regions": [
                             {"c": c.copy(), "s": 15, "peak": 0.3 if lost and 4 <= i < 8 else 0.92,
                              "ok": not (lost and 4 <= i < 8)} for i, c in enumerate(REGION_CENTRES)]}
                cells = [{"i": i, "best": char, "margin": 0.41, "uncertain": False}
                         for i, char in enumerate("+ 0.62427 mV/V  ")]
                proc = {"fps": 14.8, "latency_ms": None, "skipped_recent": 0.02}
            hud = {"seq": seq, "cap_ns": cap_ns, "w": 1920, "h": 1080, "rec": rec,
                   "track": track, "cells": cells, "proc": proc, "preview": {"fps": 15, "throttled": None}}
            jpeg = self._scene_jpeg if self._scene else self._jpeg
            return PreviewFrame(seq=seq, cap_ns=cap_ns, jpeg=jpeg, hud=copy.deepcopy(hud))


def make_test_app(image_path):
    live = FakeLiveService(image_path)
    app = make_app(FakeController(), FakeTerminals(), verifier=lambda p: p == "test-only", live=live)

    async def state(request):
        live.set_state(await request.json())
        return web.json_response({"ok": True})

    # Ausschliesslich hier registriert; der Produktionsserver kennt diese Route nicht.
    # Der normale Sitzungs-, Origin- und CSRF-Schutz bleibt auch hier aktiv.
    app.router.add_post("/__test__/state", state)

    delays = {}
    offline = False
    online = asyncio.Event()
    online.set()

    @web.middleware
    async def controls(request, handler):
        if offline and request.path == "/live/status":
            # Keine Antwort bis zur Rueckkehr; wartende Polls dann ebenfalls freigeben.
            await online.wait()
        delay = delays.pop(request.path, 0) if request.method == "POST" else 0
        response = await handler(request)
        if delay:
            await asyncio.sleep(delay / 1000)
        return response

    async def scene(request):
        live.set_scene((await request.json())["name"])
        return web.json_response({"ok": True})

    async def revision(_request):
        from dispread.live.service import LiveError

        try:
            return web.json_response({"proposal_revision": live.bump_revision()})
        except LiveError as exc:
            return web.json_response({"error": str(exc)}, status=409)

    async def delay(request):
        data = await request.json()
        path, ms = data["path"], data["ms"]
        if not isinstance(path, str) or not path.startswith("/live/") or type(ms) is not int or not 0 <= ms <= 60_000:
            raise ValueError("Verzoegerung braucht Live-Pfad und 0 bis 60000 ms")
        delays[path] = ms
        return web.json_response({"ok": True})

    async def set_offline(request):
        nonlocal offline
        value = (await request.json())["on"]
        if type(value) is not bool:
            raise ValueError("Offline braucht on als Boolean")
        offline = value
        if offline:
            online.clear()
        else:
            online.set()
        return web.json_response({"ok": True})

    # Hinter dem bestehenden Sitzungs-, Origin- und CSRF-Schutz.
    app.middlewares.append(controls)
    app.router.add_post("/test/scene", scene)
    app.router.add_post("/test/revision", revision)
    app.router.add_post("/test/delay", delay)
    app.router.add_post("/test/offline", set_offline)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-scenes", nargs="?", const=FIXTURES, type=Path)
    args = parser.parse_args()
    if args.dump_scenes is not None:
        dump_scenes(args.dump_scenes)
        return
    with tempfile.TemporaryDirectory(prefix="dispread-live-ui-") as directory:
        scratch = Path(directory)
        cert, key = scratch / "cert.pem", scratch / "key.pem"
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
            "-keyout", str(key), "-out", str(cert), "-subj", "/CN=localhost",
        ], check=True, capture_output=True)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        web.run_app(make_test_app(scratch / "overlay.png"), host=HOST, port=PORT,
                    ssl_context=context, access_log=None)


def dump_scenes(directory):
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dispread-scenes-") as scratch:
        live = FakeLiveService(Path(scratch) / "overlay.png")
        for name in SCENES:
            live.set_scene(name)
            (directory / f"scene-{name}.json").write_text(
                json.dumps(live.status(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
