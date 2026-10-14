"""Zustandsautomat der Live-Seite: Einrichtung, Bestaetigung, Lauf.

Kein Web-Code. Die Werkbank ruft diese Methoden auf und zeigt `status()` an;
alle Entscheidungen (Freigabe, Ablehnung, Bestaetigungsregeln) fallen hier
oder tiefer (Spec 2026-10-12 §1/§3).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from dispread.camera_settings import CameraSettings
from dispread.frames import FrameSource
from dispread.frames.uvc_source import UvcError, UvcSource
from dispread.gsv2as_cell_text import validate_offline_cell_text
from dispread.live import RELEASE_NOTICE
from dispread.live import setup as live_setup
from dispread.live.session import LiveConfig, LiveSession
from dispread.session_profile import SessionProfile
from dispread.setup_checks import RESOLUTION_ERROR_PX

OVERLAYS = ("still", "stability", "overlay_source", "overlay_sampling", "overlay_rectified")
DEVICE_ID = "gsv-sensor-161a"


class LiveError(ValueError):
    """Bedienfehler oder abgelehnter Schritt; Meldung fuer die Seite."""


def _setup_error_for_page(message: str) -> str:
    """CLI-Hinweise durch Bedienschritte der Live-Seite ersetzen."""
    for wording in ("bitte --hint-box angeben", "Hinweisbox pruefen oder --hint-box angeben"):
        message = message.replace(wording, "Anzeige mittig ins Bild bringen")
    for option in ("--override-reason", "--accept-default-grid"):
        message = message.replace(option, "")
    message = " ".join(message.split())
    if "startlage_mehrdeutig" in message or "keine_startlage" in message:
        message += " — Kamera senkrecht auf Displaymitte stellen und neu einrichten"
    return message


class OwnerSetupCamera:
    """`SetupCamera` ueber den CameraOwner (Bilder aus dem laufenden Strom)."""

    def __init__(self, owner: Any) -> None:
        self._owner = owner
        self.device = owner.status().get("source", {}).get("device") or "?"

    def _target(self) -> Any:
        target = self._owner.control_target()
        if target is None:
            raise live_setup.SetupError("Kamera kann keine Regler setzen (Simulation?)")
        return target

    def set_controls(self, controls: list[tuple[str, int]]) -> None:
        self._target().set_controls(list(controls))

    def get_controls(self, names: list[str]) -> dict[str, int]:
        return self._target().get_controls(list(names))

    def fresh_still(self, discard: int = 10) -> np.ndarray:
        latest = self._owner.latest()
        seen = latest[0] if latest else 0
        got = None
        for _ in range(discard + 1):
            got = self._owner.wait_newer(seen, 2.0)
            if got is None:
                raise UvcError(f"kein frisches Bild von {self.device}")
            seen = got[0]
        return got[1].image.copy()


class LiveService:
    def __init__(
        self,
        owner: Any,
        data_dir: Path,
        *,
        config: LiveConfig = LiveConfig(),
        simulate: bool = False,
        source_for: Callable[[CameraSettings], FrameSource] | None = None,
        serial_opener: Callable[[], Any] | None = None,
        setup_runner: Callable[..., dict] | None = None,
        wall: Callable[[], datetime] | None = None,
    ) -> None:
        self._owner = owner
        self._data_dir = Path(data_dir)
        self._config = config
        self._simulate = simulate
        self._source_for = source_for or (lambda settings: UvcSource(settings))
        self._serial_opener = serial_opener or self._open_serial
        self._setup_runner = setup_runner or self._run_setup
        self._wall = wall or (lambda: datetime.now(UTC))
        self._operation_lock = threading.Lock()
        self._lock = threading.Lock()
        self._state = "idle"
        self._step: str | None = None
        self._error: str | None = None
        self._session_dir: Path | None = None
        self._proposal: dict | None = None
        self._profile_path: Path | None = None
        self._profile_camera: CameraSettings | None = None
        self._last_confirmed_focus: int = 48
        self._profile_info: dict | None = None
        self._run_dir: Path | None = None
        self._session: LiveSession | None = None
        self._run_stop: threading.Event | None = None
        self._run_thread: threading.Thread | None = None
        self._setup_thread: threading.Thread | None = None

    # -- Anzeige -------------------------------------------------------------
    def status(self) -> dict:
        with self._lock:
            setup = None
            if self._proposal is not None:
                checks = self._proposal.get("setup_checks", {})
                setup = {
                    "overall": checks.get("overall"),
                    "checks": {n: c.get("status") for n, c in checks.get("checks", {}).items()},
                    "overlays": [n for n in OVERLAYS if self.setup_file(n) is not None],
                }
            run = None
            if self._session is not None:
                latest = self._session.latest
                run = {
                    "latest": None if latest is None else {
                        "frame_sequence": latest.frame_sequence,
                        "status": latest.status.value,
                        "value": latest.value,
                        "unit": latest.unit,
                        "raw_text": latest.raw_text,
                        "reject_reasons": list(latest.reject_reasons),
                        "frames_confirmed": latest.frames_confirmed,
                        "confirmation_span_ns": latest.confirmation_span_ns,
                        "capture_timestamp": latest.capture_timestamp.to_dict(),
                    },
                    "summary": dict(self._session.summary),
                    "dir": self._run_dir.name,
                    "latest_age_s": self._session.latest_age_s(),
                }
            return {
                "state": self._state,
                "step": self._step,
                "error": self._error,
                "simulate": self._simulate,
                "camera": self._owner.status(),
                "release_notice": RELEASE_NOTICE,
                "session_id": None if self._session_dir is None else self._session_dir.name,
                "setup": setup,
                "profile": self._profile_info,
                "run": run,
            }

    def preview_jpeg(self, width: int = 960) -> bytes | None:
        """Neuestes Bild verkleinert als JPEG; mit Lauf das nachgefuehrte Quad."""
        import cv2

        latest = self._owner.latest()
        if latest is None:
            return None
        image = latest[1].image
        scale = width / image.shape[1]
        small = cv2.resize(image, (width, round(image.shape[0] * scale)))
        session = self._session
        locator = getattr(getattr(session, "_pipeline", None), "locator", None)
        track = getattr(locator, "last_track", None)
        if track is not None and track.quad is not None:
            points = np.array([[x * scale, y * scale] for x, y in track.quad], dtype=np.int32)
            cv2.polylines(small, [points], True, (0, 220, 0), 2)
        ok, encoded = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return encoded.tobytes() if ok else None

    def setup_file(self, name: str) -> Path | None:
        if name not in OVERLAYS or self._session_dir is None:
            return None
        path = self._session_dir / "setup" / f"{name}.png"
        return path if path.is_file() else None

    # -- Kamera --------------------------------------------------------------
    def start_camera(self) -> None:
        with self._operation_lock:
            try:
                self._owner.start()
            except Exception as exc:  # noqa: BLE001 - Meldung fuer die Seite
                raise LiveError(f"Kamera nicht gestartet: {exc}") from exc

    # -- Einrichtung ---------------------------------------------------------
    def start_setup(self, *, cell_text: str | None = None) -> None:
        with self._operation_lock:
            if self._simulate:
                raise LiveError("Einrichtung braucht die StreamCam (Simulation zeigt nur die Vorschau)")
            with self._lock:
                if self._state == "running":
                    raise LiveError("Lauf zuerst beenden")
                if self._state == "setup_running":
                    raise LiveError("Einrichtung laeuft bereits")
            camera_status = self._owner.status()
            if not camera_status["running"]:
                raise LiveError(
                    f"Kamera laeuft nicht: {camera_status.get('error')} — 'Kamera neu verbinden'"
                )
            text = None
            if cell_text is not None and cell_text != "":
                try:
                    text = validate_offline_cell_text(cell_text)
                except ValueError as exc:
                    raise LiveError(f"Zellentext: {exc}") from exc
            session_dir = self._data_dir / ("live-" + self._wall().strftime("%Y%m%dT%H%M%SZ"))
            with self._lock:
                self._state, self._step, self._error = "setup_running", "start", None
                self._session_dir, self._proposal = session_dir, None
                self._profile_path = self._profile_camera = self._profile_info = None
                self._session = None
            self._setup_thread = threading.Thread(
                target=self._setup_worker, args=(session_dir, text), name="live-setup", daemon=True
            )
            self._setup_thread.start()

    def _report(self, step: str) -> None:
        with self._lock:
            self._step = step

    def _setup_worker(self, session_dir: Path, text: str | None) -> None:
        try:
            proposal = self._setup_runner(session_dir=session_dir, cell_text=text, report=self._report)
        except Exception as exc:  # noqa: BLE001 - jeder Abbruch geht als Meldung an die Seite
            with self._lock:
                self._state, self._error = "setup_failed", _setup_error_for_page(str(exc))
            return
        with self._lock:
            self._proposal, self._state, self._step = proposal, "setup_ready", "vorschlag"

    def _open_serial(self) -> Any:
        import serial

        return serial.Serial(live_setup.SERIAL_PORT, live_setup.SERIAL_BAUDRATE, timeout=2.0)

    def _run_setup(self, *, session_dir: Path, cell_text: str | None, report: Callable[[str], None]) -> dict:
        """Echter Ablauf: Fokus -> Kamera mit festen Reglern -> Standbilder -> Vorschlag."""
        setup_dir = session_dir / "setup"
        setup_dir.mkdir(parents=True, exist_ok=True)
        report("fokus")
        with self._lock:
            start_focus = self._last_confirmed_focus
        settings, sweep = live_setup.focus_camera(OwnerSetupCamera(self._owner), None, start_focus=start_focus)
        (setup_dir / "camera-settings.json").write_text(
            json.dumps({"camera": settings.to_dict(), "focus_sweep": [[f, s] for f, s in sweep],
                        "focus_method": sweep.focus_method,
                        "created_at_utc": self._wall().isoformat()}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        report("kamera")
        self._owner.restart(lambda: self._source_for(settings))
        port = None
        try:
            if cell_text is None:
                try:
                    port = self._serial_opener()
                except Exception as exc:  # noqa: BLE001
                    raise live_setup.SetupError(
                        f"kein GSV-2AS an {live_setup.SERIAL_PORT} ({exc}) - Zellentext eingeben"
                    ) from exc
                text_source = live_setup.serial_text_source(port)
            else:
                text_source = live_setup.offline_text_source(cell_text)
            report("standbilder")
            result = live_setup.assist_measure(
                OwnerSetupCamera(self._owner),
                cell_text=text_source,
                expected_size=settings.size,
                out_dir=setup_dir,
                templates=self._config.templates,
                templates_sha256=self._config.templates_sha256,
                info=lambda message: report(message),
            )
        finally:
            if port is not None:
                port.close()
        report("vorschlag")
        return live_setup.propose_with_fit(
            result.first,
            fit=result.fit,
            frame_path=setup_dir / "still.png",
            camera_settings=settings,
            device_id=DEVICE_ID,
            session_id=session_dir.name,
            out_dir=setup_dir,
            offset_check=result.offset_check,
            final_checks=result.final_checks,
            stability_image_bgr=result.second,
            stability_elapsed_s=result.stability_elapsed_s,
            reader_check=result.reader_check,
        )

    def confirm(self, *, confirmed_by: str, format_checked: bool, acknowledge_warning: bool = False) -> None:
        with self._operation_lock:
            with self._lock:
                if self._state != "setup_ready" or self._proposal is None or self._session_dir is None:
                    raise LiveError("Kein Vorschlag zum Bestaetigen")
                proposal, session_dir = self._proposal, self._session_dir
            if not format_checked:
                raise LiveError("Einheit mV/V und Format gsv2as_v1 muessen geprueft sein")
            overall = proposal.get("setup_checks", {}).get("overall")
            if overall == "FEHLER":
                raise LiveError("Einrichtung meldet FEHLER - nicht bestaetigbar")
            if overall == "WARNUNG" and not acknowledge_warning:
                raise LiveError("Einrichtung meldet WARNUNG - ausdruecklich zur Kenntnis nehmen")
            try:
                profile: SessionProfile = live_setup.confirm_proposal(
                    proposal, confirmed_by=confirmed_by, resolution_threshold_px=RESOLUTION_ERROR_PX,
                )
            except live_setup.SetupError as exc:
                raise LiveError(str(exc)) from exc
            if not profile.resolution_ok:
                raise LiveError("Aufloesung unter der Schwelle - Kamera naeher stellen und neu einrichten")
            path = session_dir / "profile.json"
            profile.save(path)
            confirmation = {
                "confirmed_by": profile.confirmed_by,
                "confirmed_at_utc": profile.confirmed_at_utc,
                "unit": "mV/V",
                "format_id": "gsv2as_v1",
                "format_checked": True,
                "warning_acknowledged": bool(acknowledge_warning),
                "setup_overall": overall,
            }
            (session_dir / "confirmation.json").write_text(
                json.dumps(confirmation, indent=2, ensure_ascii=False), encoding="utf-8",
            )
            with self._lock:
                self._profile_path, self._profile_camera = path, profile.camera
                self._last_confirmed_focus = profile.camera.controls["focus_absolute"]
                self._profile_info = {"confirmed_by": profile.confirmed_by,
                                      "confirmed_at_utc": profile.confirmed_at_utc,
                                      "warning_acknowledged": overall == "WARNUNG"}
                self._state = "confirmed"

    # -- Lauf ----------------------------------------------------------------
    def start_run(self) -> None:
        with self._operation_lock:
            with self._lock:
                if self._state == "running":
                    raise LiveError("Lauf laeuft bereits")
                if self._state not in ("confirmed", "stopped") or self._profile_path is None:
                    raise LiveError("Erst einrichten und bestaetigen")
                profile_path, camera = self._profile_path, self._profile_camera
            number = 1
            while True:
                out_dir = profile_path.parent / f"run-{number:02d}"
                try:
                    out_dir.mkdir(parents=True)
                    break
                except FileExistsError:
                    number += 1
            if camera is not None:
                try:
                    self._owner.restart(lambda: self._source_for(camera))
                except RuntimeError as exc:
                    raise LiveError(f"Kamera nicht neu gestartet: {exc}") from exc
            try:
                session = LiveSession(self._owner, profile_path, self._config, out_dir)
                session.start()
            except Exception as exc:  # noqa: BLE001 - Meldung fuer die Seite
                raise LiveError(f"Lauf nicht gestartet: {exc}") from exc
            stop = threading.Event()
            with self._lock:
                self._session, self._run_stop, self._state, self._error = session, stop, "running", None
                self._run_dir = out_dir
            self._run_thread = threading.Thread(target=self._run_worker, args=(session, stop), name="live-run",
                                                daemon=True)
            self._run_thread.start()

    def _run_worker(self, session: LiveSession, stop: threading.Event) -> None:
        session.run(stop)
        if not stop.is_set():  # Kamera ausgefallen, nicht vom Bediener beendet
            error = session.end_reason
            try:
                session.stop(session.end_reason or "kamera")
            except Exception as exc:  # noqa: BLE001 - auch Audit-Abschluss kann scheitern
                error = f"Lauf nicht beendet: {exc}"
            finally:
                with self._lock:
                    if self._session is session and not stop.is_set():
                        self._state, self._error = "stopped", error

    def stop_run(self) -> None:
        with self._operation_lock:
            self._stop_run()

    def _stop_run(self) -> None:
        with self._lock:
            if self._state != "running" or self._run_stop is None or self._session is None:
                raise LiveError("kein Lauf aktiv")
            stop, session, thread = self._run_stop, self._session, self._run_thread
        stop.set()
        error = None
        try:
            if thread is not None:
                thread.join(3.0)
                if thread.is_alive():
                    error = "Lesethread haengt"
            try:
                session.stop("bediener")
            except Exception as exc:  # noqa: BLE001 - Zustand auch bei Abschlussfehler freigeben
                message = f"Lauf nicht beendet: {exc}"
                error = message if error is None else f"{error}; {message}"
                raise LiveError(error) from exc
        finally:
            with self._lock:
                self._state, self._error = "stopped", error

    def close(self) -> None:
        with self._operation_lock:
            with self._lock:
                running = self._state == "running"
            if running:
                self._stop_run()
