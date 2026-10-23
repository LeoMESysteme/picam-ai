"""Zustandsautomat der Live-Seite: Einrichtung, Bestaetigung, Lauf.

Kein Web-Code. Die Werkbank ruft diese Methoden auf und zeigt `status()` an;
alle Entscheidungen (Freigabe, Ablehnung, Bestaetigungsregeln) fallen hier
oder tiefer (Spec 2026-10-12 §1/§3).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from dispread.camera_settings import CameraSettings
from dispread.focus_sweep import DEFAULT_FOCUS_START
from dispread.frames import FrameSource
from dispread.frames.uvc_source import UvcError, UvcSource
from dispread.gsv2as_cell_text import validate_offline_cell_text
from dispread.live import RELEASE_NOTICE
from dispread.live import setup as live_setup
from dispread.live.diagnostics import staging_leftovers
from dispread.live.reference import ReferenceRecorder, parse_norm_schedule
from dispread.live.session import LiveConfig, LiveSession
from dispread.session_profile import SessionProfile
from dispread.setup_checks import RESOLUTION_ERROR_PX
from dispread.workbench.fields import REASONS, live_cause

OVERLAYS = ("still", "stability", "overlay_source", "overlay_sampling", "overlay_rectified")
DEVICE_ID = "gsv-sensor-161a"
DIAGNOSTIC_CLOSE_TIMEOUT_S = 60.0
_LOG = logging.getLogger(__name__)


class LiveError(ValueError):
    """Bedienfehler oder abgelehnter Schritt; Meldung fuer die Seite."""


class LiveInputError(LiveError):
    """Ungueltige Anfrage; HTTP 400 statt eines Zustandskonflikts."""


def run_block_reason(proposal: dict | None) -> str | None:
    """Nur erfolgreiches Gegenlesen erlaubt einen normalen Lauf."""
    check = (proposal or {}).get("setup_checks", {}).get("checks", {}).get("gegenlesen")
    if not isinstance(check, dict):
        return "Lauf gesperrt: Einrichtung ohne Gegenlesen. Neu einrichten."
    status = check.get("status")
    if status == "OK":
        return None
    metrics = check.get("metrics", {})
    hint = f" {metrics['hinweis']}" if metrics.get("hinweis") else ""
    if metrics.get("rejection_reasons", {}).get("zelle_widerspricht_referenz") and metrics.get("contradictions"):
        first = metrics["contradictions"][0]
        return (
            "Lauf gesperrt: Der Leser widerspricht bei der Einrichtung dem Referenzwert des GSV-2AS "
            f"(Zelle {first['cell']}: gelesen '{first['read']}', Referenz '{first['reference']}'). Neu einrichten.{hint}"
        )
    reasons = ", ".join(f"{name} x{count}" for name, count in metrics.get("rejection_reasons", {}).items()) or "-"
    return (
        f"Lauf gesperrt: Der Leser hat bei der Einrichtung {metrics.get('read_count', 0)} von "
        f"{metrics.get('frames', 0)} Standbildern gelesen (Gegenlesen {status}: {reasons}). "
        "Mit dieser Aufstellung liefert der Lauf nur UNREADABLE. Kamera senkrecht auf die "
        f"Displaymitte ausrichten und neu einrichten.{hint}"
    )


def _setup_error_for_page(message: str) -> str:
    """CLI-Hinweise durch Bedienschritte der Live-Seite ersetzen."""
    for wording in ("bitte --hint-box angeben", "Hinweisbox pruefen oder --hint-box angeben"):
        message = message.replace(wording, "Anzeige mittig ins Bild bringen")
    for option in ("--override-reason", "--accept-default-grid"):
        message = message.replace(option, "")
    message = " ".join(message.split())
    if "startlage_mehrdeutig" in message or "keine_startlage" in message:
        message += " — Kamera senkrecht auf Displaymitte stellen und neu einrichten"
    if "vorzeichen_kein_plus" in message:
        message += " — Anzeige zeigt kein Plus — Wert positiv einstellen und neu einrichten"
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
        monotonic: Callable[[], float] | None = None,
        diagnostic_staging_root: Path = Path('/dev/shm'),
    ) -> None:
        self._owner = owner
        self._data_dir = Path(data_dir)
        self._config = config
        self._simulate = simulate
        self._source_for = source_for or (lambda settings: UvcSource(settings))
        self._serial_opener = serial_opener or self._open_serial
        self._setup_runner = setup_runner or self._run_setup
        self._wall = wall or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.monotonic
        self._diagnostic_staging_root = diagnostic_staging_root
        self._diagnostic_copies: list[LiveSession] = []
        for leftover in staging_leftovers(self._diagnostic_staging_root):
            _LOG.warning('Verbliebene Diagnose-Ablage: %s (%s Bytes)', leftover['path'], leftover['bytes'])
        self._setup_started_at: float | None = None
        self._setup_elapsed_s: float | None = None
        self._setup_step: str | None = None
        self._setup_message: str | None = None
        self._diagnostics_error: str | None = None
        self._operation_lock = threading.Lock()
        self._lock = threading.Lock()
        self._state = "idle"
        self._step: str | None = None
        self._error: str | None = None
        self._session_dir: Path | None = None
        self._proposal: dict | None = None
        self._run_block: str | None = None
        self._test_run: dict | None = None
        self._reader_tolerance: dict | None = None
        self._profile_path: Path | None = None
        self._profile_camera: CameraSettings | None = None
        self._last_confirmed_focus: int = DEFAULT_FOCUS_START
        self._profile_info: dict | None = None
        self._run_dir: Path | None = None
        self._session: LiveSession | None = None
        self._run_stop: threading.Event | None = None
        self._run_thread: threading.Thread | None = None
        self._setup_thread: threading.Thread | None = None

    # -- Anzeige -------------------------------------------------------------
    def status(self, *, full: bool = False) -> dict:
        with self._lock:
            setup = None
            if self._proposal is not None:
                checks = self._proposal.get("setup_checks", {})
                setup = {
                    "overall": checks.get("overall"),
                    "checks": {n: c.get("status") for n, c in checks.get("checks", {}).items()},
                    "overlays": [n for n in OVERLAYS if self.setup_file(n) is not None],
                }
                block = self._proposal.get("live_tracking")
                if block is not None:
                    setup["proposal_revision"] = block.get("proposal_revision")
                    setup["regions"] = block.get("proposal", {}).get("regions", [])
                    setup["auswahl"] = block.get("auswahl", "automatisch")
                    setup["centre_results"] = block.get("proposal", {}).get("metrics", {}).get("centre_results", [])
                check_reasons = {
                    name: check["reason"] for name, check in checks.get("checks", {}).items() if check.get("reason")
                }
                if check_reasons:
                    setup["check_reasons"] = check_reasons
                gegenlesen = checks.get("checks", {}).get("gegenlesen", {})
                metrics = gegenlesen.get("metrics", {})
                if metrics.get("hinweis") or "tolerance" in metrics:
                    setup["gegenlesen"] = {"status": gegenlesen.get("status"), "metrics": {
                        key: metrics[key] for key in ("hinweis", "tolerance") if key in metrics}}
            if self._setup_started_at is not None:
                setup = setup or {}
                setup["step"] = self._setup_step
                if self._setup_message is not None:
                    setup["message"] = self._setup_message
                if self._diagnostics_error is not None:
                    setup["diagnostics_error"] = self._diagnostics_error
                setup["elapsed_s"] = (
                    self._monotonic() - self._setup_started_at
                    if self._state == "setup_running" else self._setup_elapsed_s
                )
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
                    "guess": self._session.latest_guess if self._test_run is not None else None,
                    "tracking": dict(getattr(self._session, "tracking", {})),
                }
                if hasattr(self._session, "rejection_causes"):
                    causes = self._session.rejection_causes()
                    run["rejection_causes"] = {**causes, "causes": [live_cause(c) for c in causes["causes"]]}
            return {
                "state": self._state,
                **({"tracking_reasons": REASONS} if full else {}),
                "step": self._step,
                "error": self._error,
                "simulate": self._simulate,
                "camera": self._owner.status(),
                "release_notice": RELEASE_NOTICE,
                "session_id": None if self._session_dir is None else self._session_dir.name,
                "setup": setup,
                "profile": self._profile_info,
                "run_block": self._run_block,
                "test_run": self._test_run,
                "reader_tolerance": self._reader_tolerance,
                "run": run,
                "diagnostics": (self._session.diagnostics_status()
                                if self._session is not None and hasattr(self._session, 'diagnostics_status')
                                else {'enabled': False, 'reason': 'kein Diagnoselauf'}),
                "diagnose_kopie": any(getattr(s, 'diagnose_kopie', False)
                                      for s in [*self._diagnostic_copies, self._session]),
                "diagnostic_leftovers": staging_leftovers(self._diagnostic_staging_root, exclude={
                    s.diagnostics_status().get('staging')
                    for s in [*self._diagnostic_copies, self._session]
                    if s is not None and hasattr(s, 'diagnostics_status')
                    and (getattr(s, 'diagnose_kopie', False) or (s is self._session and self._state == 'running'))
                }),
                "last_mark": getattr(self._session, 'last_mark', None),
                "reference": (self._session.reference_status()
                              if self._session is not None and hasattr(self._session, "reference_status")
                              else {"enabled": False, "reason": "kein Referenzlauf"}),
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
                self._setup_started_at = self._monotonic()
                self._setup_elapsed_s = None
                self._setup_step = "start"
                self._setup_message = self._setup_message_base = self._diagnostics_error = None
                self._session_dir, self._proposal = session_dir, None
                self._run_block = self._test_run = self._reader_tolerance = None
                self._profile_path = self._profile_camera = self._profile_info = None
                self._diagnostic_copies = [s for s in [*self._diagnostic_copies, self._session]
                                           if getattr(s, 'diagnose_kopie', False)]
                self._session = None
            self._setup_thread = threading.Thread(
                target=self._setup_worker, args=(session_dir, text), name="live-setup", daemon=True
            )
            self._setup_thread.start()

    def _report(self, step: str) -> None:
        with self._lock:
            self._step = self._setup_step = step
            self._setup_message = self._setup_message_base = None

    def _setup_progress(self, message: str) -> None:
        with self._lock:
            self._setup_message_base = self._setup_message = message

    def _setup_note(self, note: str) -> None:
        """Zusatz zum laufenden Schritt, ohne dessen Meldung (z. B. Suchversuch) zu verlieren."""
        with self._lock:
            base = getattr(self, "_setup_message_base", None)
            self._setup_message = f"{base} - {note}" if base else note

    def _write_setup_diagnostic(self, path: Path, data: Any) -> None:
        """Diagnosefehler duerfen den Einrichtungsausgang nicht veraendern."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except (OSError, TypeError, ValueError) as exc:
            with self._lock:
                self._diagnostics_error = f"{path.name}: {type(exc).__name__}: {str(exc)[:160]}"

    def _setup_worker(self, session_dir: Path, text: str | None) -> None:
        try:
            proposal = self._setup_runner(session_dir=session_dir, cell_text=text, report=self._report)
        except Exception as exc:  # noqa: BLE001 - jeder Abbruch geht als Meldung an die Seite
            with self._lock:
                step = self._setup_step
                self._setup_elapsed_s = self._monotonic() - self._setup_started_at
                self._state, self._error = "setup_failed", _setup_error_for_page(str(exc))
            self._write_setup_diagnostic(
                session_dir / "setup" / "failure.json",
                {"step": step, "reason": str(exc), "created_at_utc": self._wall().isoformat()},
            )
            return
        with self._lock:
            self._setup_elapsed_s = self._monotonic() - self._setup_started_at
            self._setup_step = "vorschlag"
            self._proposal, self._state, self._step = proposal, "setup_ready", "vorschlag"
            self._run_block = run_block_reason(proposal)

    def _open_serial(self) -> Any:
        import serial

        return serial.Serial(live_setup.SERIAL_PORT, live_setup.SERIAL_BAUDRATE, timeout=2.0)

    def _run_setup(self, *, session_dir: Path, cell_text: str | None, report: Callable[[str], None]) -> dict:
        """Echter Ablauf: Fokus -> Kamera mit festen Reglern -> Standbilder -> Vorschlag."""
        setup_dir = session_dir / "setup"
        setup_dir.mkdir(parents=True, exist_ok=True)
        self._write_setup_diagnostic(setup_dir / "cell-text.json", [])
        cell_texts: list[dict] = []
        raw_texts: list[str] = []
        capture_tries = 1

        def save_attempt(entry: dict) -> None:
            previous = next((item for item in cell_texts
                             if (item["attempt"], item["still"]) == (entry["attempt"], entry["still"])), None)
            if previous is None:
                cell_texts.append({**entry, "source": "seriell" if cell_text is None else "eingabe",
                                   "unmasked": list(raw_texts), "tries": capture_tries})
            else:
                previous.update(entry)
            self._write_setup_diagnostic(setup_dir / "cell-text.json", cell_texts)

        def save_raw(before: str | None, after: str | None, tries: int) -> None:
            nonlocal capture_tries
            capture_tries = tries
            raw_texts[:] = [value for value in (before, after) if value is not None]

        report("fokus")
        with self._lock:
            start_focus = self._last_confirmed_focus
        settings, sweep = live_setup.focus_camera(
            OwnerSetupCamera(self._owner), None, start_focus=start_focus, info=self._setup_progress,
        )
        (setup_dir / "camera-settings.json").write_text(
            json.dumps({"camera": settings.to_dict(), "focus_sweep": [[f, s] for f, s in sweep],
                        "focus_method": getattr(sweep, "focus_method", "sweep"),
                        "created_at_utc": self._wall().isoformat()}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        report("kamera")
        self._owner.restart(lambda: self._source_for(settings))
        port = None
        try:
            if cell_text is None:
                self._setup_progress("Serielle Verbindung oeffnen")
                try:
                    port = self._serial_opener()
                except Exception as exc:  # noqa: BLE001
                    raise live_setup.SetupError(
                        f"kein GSV-2AS an {live_setup.SERIAL_PORT} ({exc}) - Zellentext eingeben"
                    ) from exc
                def text_source(capture):
                    return live_setup.capture_with_text(
                        capture, port, on_text=save_raw, info=self._setup_note,
                    )
            else:
                raw_texts[:] = [cell_text]
                text_source = live_setup.offline_text_source(cell_text)
            report("standbilder")
            result = live_setup.assist_measure(
                OwnerSetupCamera(self._owner),
                cell_text=text_source,
                expected_size=settings.size,
                out_dir=setup_dir,
                stability_s=15.0,
                min_stability_s=15.0,
                stack_frames=8,
                fit_attempts=3,
                on_attempt=save_attempt,
                templates=self._config.templates,
                templates_sha256=self._config.templates_sha256,
                reference_kind="seriell" if cell_text is None else "eingabe",
                info=self._setup_progress,
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
            cell_text=result.first_text,
            offset_check=result.offset_check,
            final_checks=result.final_checks,
            stability_image_bgr=result.second,
            stability_elapsed_s=result.stability_elapsed_s,
            stability_min_elapsed_s=15.0,
            setup_attempt=result.setup_attempt,
            reader_check=result.reader_check,
            live_tracking=True,
        )

    def edit_regions(self, *, proposal_revision, add, remove) -> dict:
        """Nur den aktuellen Vorschlag bearbeiten, nie waehrend eines Laufs."""
        with self._operation_lock:
            with self._lock:
                if self._state == "running":
                    raise LiveError("Lauf zuerst beenden - Rahmenbereiche nicht bearbeitbar")
                if self._state != "setup_ready" or self._proposal is None or self._session_dir is None:
                    raise LiveError("Kein aktueller Vorschlag zum Bearbeiten")
                block = self._proposal.get("live_tracking")
                if block is None:
                    raise LiveError("Kein aktueller Rahmenvorschlag - neu einrichten")
                if proposal_revision is None or proposal_revision != block.get("proposal_revision"):
                    raise LiveError("Vorschlag hat sich geaendert - Rahmenbereiche bitte neu pruefen")
                proposal, session_dir = self._proposal, self._session_dir
            try:
                updated = live_setup.edit_regions(
                    proposal, add=add, remove=remove, out_dir=session_dir / "setup",
                    at_utc=self._wall().astimezone(UTC).isoformat(),
                )
            except live_setup.SetupInputError as exc:
                raise LiveInputError(str(exc)) from exc
            except (live_setup.SetupError, ValueError, OSError) as exc:
                raise LiveError(str(exc)) from exc
            with self._lock:
                self._proposal = updated
                self._run_block = run_block_reason(updated)
            return {"proposal_revision": updated["live_tracking"]["proposal_revision"],
                    "centre_results": updated["live_tracking"]["proposal"]["metrics"]["centre_results"]}

    def confirm(self, *, session_id: str, confirmed_by: str, format_checked: bool, acknowledge_warning: bool = False,
                use_tolerance: bool = False, proposal_revision: str | int | None = None) -> None:
        with self._operation_lock:
            with self._lock:
                if self._state != "setup_ready" or self._proposal is None or self._session_dir is None:
                    raise LiveError("Kein Vorschlag zum Bestaetigen")
                if session_id != self._session_dir.name:
                    raise LiveError("Vorschlag hat sich geaendert — bitte neu pruefen")
                block = self._proposal.get("live_tracking")
                if block is not None and (proposal_revision is None or proposal_revision != block.get("proposal_revision")):
                    raise LiveError("Vorschlag hat sich geaendert - Rahmenbereiche bitte neu pruefen")
                proposal, session_dir = self._proposal, self._session_dir
            if not format_checked:
                raise LiveError("Einheit mV/V und Format gsv2as_v1 muessen geprueft sein")
            overall = proposal.get("setup_checks", {}).get("overall")
            if overall == "FEHLER":
                raise LiveError("Einrichtung meldet FEHLER - nicht bestaetigbar")
            if overall == "WARNUNG" and not acknowledge_warning:
                raise LiveError("Einrichtung meldet WARNUNG - ausdruecklich zur Kenntnis nehmen")
            reader_tolerance = None
            if use_tolerance:
                tolerance = proposal.get("setup_checks", {}).get("checks", {}).get("gegenlesen", {}).get(
                    "metrics", {}).get("tolerance", {})
                if tolerance.get("possible") is not True:
                    raise LiveError("Angepasste Toleranz fuer diesen Vorschlag nicht moeglich")
                reader_tolerance = {
                    "factor": tolerance["factor"], "d_max_templates": tolerance["d_max"],
                    "d_max_run": tolerance["d_max"] * tolerance["factor"],
                    "max_d_best": tolerance["max_d_best"],
                    "hinweis": "Angepasste Lesetoleranz: Lesung nur in dieser Aufstellung gegen den "
                               "Referenzwert geprueft, nicht validiert.",
                }
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
                "run_block": None if reader_tolerance else run_block_reason(proposal),
                "reader_tolerance": reader_tolerance,
            }
            (session_dir / "confirmation.json").write_text(
                json.dumps(confirmation, indent=2, ensure_ascii=False), encoding="utf-8",
            )
            with self._lock:
                self._profile_path, self._profile_camera = path, profile.camera
                self._last_confirmed_focus = profile.camera.controls["focus_absolute"]
                self._profile_info = {"confirmed_by": profile.confirmed_by,
                                      "confirmed_at_utc": profile.confirmed_at_utc,
                                      "warning_acknowledged": overall == "WARNUNG",
                                      "tracking_mode": "rahmenbereiche" if profile.live_tracking is not None else "ecc_alt"}
                self._run_block = confirmation["run_block"]
                self._reader_tolerance = reader_tolerance
                self._state = "confirmed"

    # -- Lauf ----------------------------------------------------------------
    def start_run(self, *, test_override: bool = False, reference: bool = True, norm_schedule=None,
                  diagnostics: bool = False) -> None:
        try:
            schedule = parse_norm_schedule(norm_schedule)
            if schedule is not None and not reference:
                raise ValueError("Werteplan braucht Referenzaufzeichnung")
        except (TypeError, ValueError) as exc:
            raise LiveError(str(exc)) from exc
        with self._operation_lock:
            with self._lock:
                if self._state == "running":
                    raise LiveError("Lauf laeuft bereits")
                if self._state not in ("confirmed", "stopped") or self._profile_path is None:
                    raise LiveError("Erst einrichten und bestaetigen")
                profile_path, camera = self._profile_path, self._profile_camera
                block = self._run_block
                confirmed_by = (self._profile_info or {}).get("confirmed_by")
                if block is not None and not test_override:
                    raise LiveError(block)
            number = 1
            while True:
                out_dir = profile_path.parent / f"run-{number:02d}"
                try:
                    out_dir.mkdir(parents=True)
                    break
                except FileExistsError:
                    number += 1
            test_run = None
            if block is not None:
                test_run = {
                    "testlauf": True, "run_block": block,
                    "confirmed_by": confirmed_by,
                    "started_at_utc": self._wall().isoformat(),
                    "hinweis": "Lesesperre uebergangen. Werte nicht freigegeben, nicht fuer Messungen verwenden.",
                }
                (out_dir / "TESTLAUF.json").write_text(
                    json.dumps(test_run, indent=2, ensure_ascii=False), encoding="utf-8",
                )
            if camera is not None:
                try:
                    self._owner.restart(lambda: self._source_for(camera))
                except RuntimeError as exc:
                    raise LiveError(f"Kamera nicht neu gestartet: {exc}") from exc
            try:
                recorder = (ReferenceRecorder(self._serial_opener, out_dir / "reference.jsonl",
                                              norm_schedule=schedule) if reference else None)
                session = LiveSession(
                    self._owner, profile_path, self._config, out_dir, test_run=test_run,
                    reader_d_max_factor=(self._reader_tolerance or {}).get("factor", 1.0),
                    reader_tolerance=self._reader_tolerance,
                    reference_recorder=recorder,
                    diagnostics=diagnostics, diagnostic_staging_root=self._diagnostic_staging_root,
                )
                session.start()
            except Exception as exc:  # noqa: BLE001 - Meldung fuer die Seite
                raise LiveError(f"Lauf nicht gestartet: {exc}") from exc
            stop = threading.Event()
            with self._lock:
                self._diagnostic_copies = [s for s in [*self._diagnostic_copies, self._session]
                                           if getattr(s, 'diagnose_kopie', False)]
                self._session, self._run_stop, self._state, self._error = session, stop, "running", None
                self._run_dir = out_dir
                self._test_run = test_run
            self._run_thread = threading.Thread(target=self._run_worker, args=(session, stop), name="live-run",
                                                daemon=True)
            self._run_thread.start()

    def _run_worker(self, session: LiveSession, stop: threading.Event) -> None:
        session.run(stop)
        if not stop.is_set():  # Kamera ausgefallen, nicht vom Bediener beendet
            error = session.end_reason
            try:
                session.stop(session.end_reason or "kamera")
                if hasattr(session, "reference_status"):
                    error = session.reference_status().get("error") or error
            except Exception as exc:  # noqa: BLE001 - auch Audit-Abschluss kann scheitern
                error = f"Lauf nicht beendet: {exc}"
            finally:
                with self._lock:
                    if self._session is session and not stop.is_set():
                        self._state, self._error = "stopped", error

    def stop_run(self) -> None:
        with self._operation_lock:
            self._stop_run()

    def mark(self, text: str) -> None:
        with self._lock:
            if self._state != 'running' or self._session is None:
                raise LiveError('kein Lauf aktiv')
            session = self._session
        try:
            session.mark(text)
        except (ValueError, OSError) as exc:
            raise LiveError(str(exc)) from exc

    def _stop_run(self) -> None:
        with self._lock:
            if self._state != "running" or self._run_stop is None or self._session is None:
                raise LiveError("kein Lauf aktiv")
            stop, session, thread = self._run_stop, self._session, self._run_thread
        stop.set()
        if hasattr(session, "request_reference_stop"):
            session.request_reference_stop()
        error = None
        try:
            if thread is not None:
                thread.join(3.0)
                if thread.is_alive():
                    reference_status = session.reference_status() if hasattr(session, "reference_status") else {}
                    if not reference_status.get("restoring"):
                        error = "Lesethread haengt"
            try:
                session.stop("bediener")
                if hasattr(session, "reference_status"):
                    error = session.reference_status().get("error") or error
            except Exception as exc:  # noqa: BLE001 - Zustand auch bei Abschlussfehler freigeben
                message = f"Lauf nicht beendet: {exc}"
                error = message if error is None else f"{error}; {message}"
                raise LiveError(error) from exc
        finally:
            with self._lock:
                self._state, self._error = "stopped", error

    def close(self) -> None:
        deadline = time.monotonic() + min(DIAGNOSTIC_CLOSE_TIMEOUT_S, 60.0)
        with self._operation_lock:
            with self._lock:
                running = self._state == "running"
            try:
                if running:
                    self._stop_run()
            finally:
                # Gemeinsames Zeitbudget fuer alte Kopien und den aktuellen Lauf.
                for session in [*self._diagnostic_copies, self._session]:
                    if session is None or not hasattr(session, 'wait_diagnostics'):
                        continue
                    if not session.wait_diagnostics(max(0.0, deadline - time.monotonic())):
                        _LOG.warning('Diagnosekopie: Zeitlimit beim Dienstende; RAM-Ablage zur Rettung behalten')
