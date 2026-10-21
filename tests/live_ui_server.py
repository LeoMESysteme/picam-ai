"""Nur fuer Playwright: HTTPS-Werkbank mit skriptbarem Live-Status, ohne Hardware."""

from __future__ import annotations

import copy
import ssl
import subprocess
import tempfile
import threading
from pathlib import Path

import cv2
import numpy as np
from aiohttp import web

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
                "state": "idle", "error": None, "setup": None, "run": None,
                "session_id": "test-session", "release_notice": "Validiert nur: Testaufbau",
                "camera": {"running": True, "frames": 1, "gaps": 0},
                **copy.deepcopy(state),
            }

    def status(self):
        with self._lock:
            return copy.deepcopy(self._status)

    def start_setup(self, *, cell_text=None):
        self.set_state({"state": "setup_running", "setup": {"step": "fokus", "elapsed_s": 0.0}})

    def confirm(self, *, session_id, **kwargs):
        if session_id != self.status()["session_id"]:
            from dispread.live.service import LiveError

            raise LiveError("Vorschlag hat sich geaendert — bitte neu pruefen")
        self.set_state({"state": "confirmed"})

    def start_run(self, *, test_override=False):
        self.set_state({"state": "running"})

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
