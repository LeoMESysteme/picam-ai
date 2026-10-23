"""Nur fuer Playwright: HTTPS-Werkbank mit skriptbarem Live-Status, ohne Hardware."""

from __future__ import annotations

import copy
import math
import ssl
import subprocess
import tempfile
import threading
from pathlib import Path

import cv2
import numpy as np
from aiohttp import web

from dispread.workbench.fields import REASONS, live_cause
from dispread.workbench.server import make_app

HOST = "127.0.0.1"
PORT = 8767


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
        cv2.imwrite(str(image_path), image)
        self._jpeg = cv2.imencode(".jpg", image)[1].tobytes()
        self.set_state({})

    def set_state(self, state):
        with self._lock:
            self._status = {
                "state": "idle", "error": None, "setup": None, "run": None, "reader_tolerance": None,
                "session_id": "test-session", "release_notice": "Validiert nur: Testaufbau",
                "camera": {"running": True, "frames": 1, "gaps": 0}, "diagnostic_leftovers": [],
                **copy.deepcopy(state),
            }

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
        self.set_state({"state": "setup_running", "setup": {"step": "fokus", "elapsed_s": 0.0}})

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
            regions.extend({"centre": point, "size": 5} for point in add)
            setup["regions"] = regions
            setup["proposal_revision"] += "-edit"
            setup["auswahl"] = "manuell"
            setup["centre_results"] = [{"requested_centre": r["centre"], "centre": r["centre"],
                                        "used_centre": r["centre"], "ok": True, "reason": None} for r in regions]
            setup["checks"]["nachfuehrung"] = setup["overall"] = "OK" if regions else "FEHLER"
            return {"proposal_revision": setup["proposal_revision"], "centre_results": setup["centre_results"]}

    def confirm(self, *, session_id, **kwargs):
        if session_id != self.status()["session_id"]:
            from dispread.live.service import LiveError

            raise LiveError("Vorschlag hat sich geaendert — bitte neu pruefen")
        self.set_state({"state": "confirmed"})

    def start_run(self, *, test_override=False, reference=True, norm_schedule=None, diagnostics=False):
        self.set_state({"state": "running", "diagnostics": {"enabled": diagnostics, "saved": 0,
                        "bytes": 0, "dropped_queue": 0, "dropped_limit": 0, "dropped_memory": 0,
                        "dropped_mark_rate": 0, "write_errors": 0}})

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
        return self._jpeg


def make_test_app(image_path):
    live = FakeLiveService(image_path)
    app = make_app(FakeController(), FakeTerminals(), verifier=lambda p: p == "test-only", live=live)

    async def state(request):
        live.set_state(await request.json())
        return web.json_response({"ok": True})

    # Ausschliesslich hier registriert; der Produktionsserver kennt diese Route nicht.
    # Der normale Sitzungs-, Origin- und CSRF-Schutz bleibt auch hier aktiv.
    app.router.add_post("/__test__/state", state)
    return app


def main():
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


if __name__ == "__main__":
    main()
