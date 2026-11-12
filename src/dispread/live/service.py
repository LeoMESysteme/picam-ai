"""Zustandsautomat der Live-Seite: Einrichtung, Bestaetigung, Lauf.

Kein Web-Code. Die Werkbank ruft diese Methoden auf und zeigt `status()` an;
alle Entscheidungen (Freigabe, Ablehnung, Bestaetigungsregeln) fallen hier
oder tiefer (Spec 2026-10-12 §1/§3).
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from dispread.camera_settings import CameraSettings
from dispread.charcells import CharGrid
from dispread.focus_sweep import DEFAULT_FOCUS_START
from dispread.frames import FrameSource
from dispread.frames.uvc_source import UvcError, UvcSource
from dispread.gsv2as_cell_text import validate_offline_cell_text
from dispread.live import RELEASE_NOTICE
from dispread.live import setup as live_setup
from dispread.live.diagnostics import MAX_BYTES as DIAGNOSTIC_BUDGET_BYTES
from dispread.live.diagnostics import staging_leftovers
from dispread.live.output import normalize_output, require_output_acknowledgement
from dispread.live.preview import PreviewEncoder, PreviewFrame, RateGovernor
from dispread.live.reference import ReferenceRecorder, parse_norm_schedule
from dispread.live.reference_eval import evaluate_records, validate_reference_session
from dispread.live.region_hint import MIN_SHARE
from dispread.live.session import LiveConfig, LiveSession
from dispread.live.storage import cleanup_runs
from dispread.live.texts import LIVE_CAUSE_TEXT, REASONS, live_cause
from dispread.session_profile import SessionProfile
from dispread.setup_checks import RESOLUTION_ERROR_PX

OVERLAYS = ("still", "stability", "overlay_source", "overlay_sampling", "overlay_rectified")
SETUP_STEPS = ("fokus", "kamera", "belichtung", "standbilder", "vorschlag")
DEVICE_ID = "gsv-sensor-161a"
DIAGNOSTIC_CLOSE_TIMEOUT_S = 60.0
STORAGE_RESERVE_BYTES = 2_000_000_000
STORAGE_WARNING_BYTES = 5_000_000_000
_LOG = logging.getLogger(__name__)

BRIDGE_BUSY_TEXT = ("Die Windows-Brücke führt gerade einen Empfangstest (Demo) aus. Bitte in der Windows-App "
                    "warten, bis er endet (höchstens wenige Sekunden nach dem letzten Wert), dann den Lauf "
                    "erneut starten.")


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
        message += (
            " — Raster nicht gefunden - Kamera gerader vor die Anzeige stellen (weniger schraeg) oder naeher heran; "
            "Anzeige soll mindestens ein Drittel der Bildbreite fuellen. Neu einrichten."
        )
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
                raise UvcError(self._owner.status().get('error') or f"kein frisches Bild von {self.device}")
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
        disk_usage: Callable[[Path], Any] | None = None,
        cpu_reader: Callable[[], str] | None = None,
        bridge_hub=None,
    ) -> None:
        self._owner = owner
        self._bridge_hub = bridge_hub
        self._data_dir = Path(data_dir)
        self._disk_usage = disk_usage or shutil.disk_usage
        self._cpu_reader = cpu_reader or (lambda: Path('/proc/stat').read_text(encoding='ascii'))
        self._cpu_sample_at: float | None = None
        self._cpu_previous: tuple[int, int, float] | None = None
        self._cpu_percent: float | None = None
        self._cpu_window_s = 0.0
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
        self._reset_setup_live()
        self._diagnostics_error: str | None = None
        self._operation_lock = threading.Lock()
        self._lock = threading.Lock()
        self._state = "idle"
        self._step: str | None = None
        self._error: str | None = None
        self._session_dir: Path | None = None
        self._proposal: dict | None = None
        # TC 2026-11-11: auffaellige Bereiche des letzten Laufs fuer die Neueinrichtung, nur Anzeige.
        self._previous_region_hint: dict | None = None
        self._setup_grid: dict | None = None
        self._stability_frames: tuple[np.ndarray, ...] = ()
        self._run_block: str | None = None
        self._test_run: dict | None = None
        self._reader_tolerance: dict | None = None
        self._profile_path: Path | None = None
        self._profile_camera: CameraSettings | None = None
        self._last_confirmed_focus: int = DEFAULT_FOCUS_START
        # OQ-74: Schaerfereferenz der bestaetigten Einrichtung und Pruefung am Laufstart.
        self._focus_reference: dict | None = None
        self._run_focus_check: dict | None = None
        self._profile_info: dict | None = None
        self._run_dir: Path | None = None
        self._session: LiveSession | None = None
        self._run_stop: threading.Event | None = None
        self._run_thread: threading.Thread | None = None
        self._run_reference = False
        self._reference_eval: dict | None = None
        self._setup_cancel = threading.Event()
        self._setup_thread: threading.Thread | None = None
        self._preview = PreviewEncoder(lambda: self._owner.latest(), self._preview_hud,
                                       governor=RateGovernor(self._monotonic))

    # -- Anzeige -------------------------------------------------------------
    def _system_status(self) -> dict:
        """Unter self._lock: Gesamt-CPU aus procfs, hoechstens alle 0,5 s lesen."""
        now = self._monotonic()
        if self._cpu_sample_at is None or now - self._cpu_sample_at >= 0.5:
            self._cpu_sample_at = now
            self._cpu_percent, self._cpu_window_s = None, 0.0
            try:
                fields = self._cpu_reader().splitlines()[0].split()
                if fields[0] != 'cpu' or len(fields) < 5:
                    raise ValueError('Gesamt-CPU fehlt')
                values = [int(value) for value in fields[1:]]
                if any(value < 0 for value in values):
                    raise ValueError('Negativer CPU-Zaehler')
                # guest/guest_nice sind bereits in user/nice enthalten.
                total = sum(values[:8])
                idle = values[3] + (values[4] if len(values) > 4 else 0)
            except (OSError, ValueError, IndexError):
                self._cpu_previous = None
            else:
                previous = self._cpu_previous
                self._cpu_previous = (total, idle, now)
                if previous is not None:
                    delta, idle_delta = total - previous[0], idle - previous[1]
                    if delta > 0 and 0 <= idle_delta <= delta:
                        self._cpu_percent = 100.0 * (delta - idle_delta) / delta
                        self._cpu_window_s = now - previous[2]
        return {'cpu_percent': self._cpu_percent, 'cpu_window_s': self._cpu_window_s}

    def _storage_status(self) -> dict:
        # Vor der ersten Einrichtung existiert var/live eventuell noch nicht.
        path = self._data_dir
        while not path.exists() and path != path.parent:
            path = path.parent
        try:
            free = self._disk_usage(path).free
        except OSError as exc:
            return {"free_bytes": None, "reserve_bytes": STORAGE_RESERVE_BYTES, "level": "error",
                    "message": f"Speicherplatz nicht pruefbar: {exc}"}
        level = "error" if free < STORAGE_RESERVE_BYTES else "warn" if free < STORAGE_WARNING_BYTES else "ok"
        return {"free_bytes": free, "reserve_bytes": STORAGE_RESERVE_BYTES, "level": level,
                "message": f"{free / 1e9:.2f} GB frei"}

    def _require_storage(self, *, diagnostics: bool = False) -> None:
        storage = self._storage_status()
        if storage["free_bytes"] is None:
            raise LiveError(storage["message"])
        needed = STORAGE_RESERVE_BYTES + (DIAGNOSTIC_BUDGET_BYTES if diagnostics else 0)
        if storage["free_bytes"] < needed:
            raise LiveError(f"Zu wenig Speicherplatz: {storage['free_bytes'] / 1e9:.2f} GB frei, "
                            f"{needed / 1e9:.2f} GB benoetigt. Alte Laufdaten pruefen und aufraeumen.")

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
                setup["focus"] = deepcopy(self._setup_focus)
                setup["exposure"] = deepcopy(self._setup_exposure)
                setup["progress"] = self._setup_progress_status()
                if self._proposal is None:
                    setup["checks_live"] = deepcopy(self._setup_checks_live)
                setup["step"] = self._setup_step
                if self._setup_message is not None:
                    setup["message"] = self._setup_message
                if self._diagnostics_error is not None:
                    setup["diagnostics_error"] = self._diagnostics_error
                setup["elapsed_s"] = (
                    self._monotonic() - self._setup_started_at
                    if self._state == "setup_running" else self._setup_elapsed_s
                )
            if setup is not None:
                setup["grid"] = deepcopy(self._setup_grid)
            run = None
            if self._session is not None:
                latest = self._session.latest
                if hasattr(self._session, 'recent_snapshot'):
                    recent, recent_now_ms = self._session.recent_snapshot()
                else:
                    recent, recent_now_ms = (self._session.recent.snapshot(self._monotonic())
                                             if hasattr(self._session, 'recent') else ([], 0.0))
                run = {
                    **(self._session.timing_status() if hasattr(self._session, 'timing_status') else {}),
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
                    "counts": {status: getattr(self._session, '_by_status', {}).get(status, 0)
                               for status in ('valid', 'transition', 'unreadable', 'stale')},
                    "recent": recent,
                    "recent_now_ms": recent_now_ms,
                    "dir": self._run_dir.name,
                    "focus_check": deepcopy(self._run_focus_check),
                    "latest_age_s": self._session.latest_age_s(),
                    "guess": self._session.latest_guess if self._test_run is not None else None,
                    "tracking": dict(getattr(self._session, "tracking", {})),
                    "tracking_hint": (self._session.tracking_hint()
                                      if hasattr(self._session, "tracking_hint") else None),
                    "region_hint": (self._session.region_hint()
                                    if hasattr(self._session, "region_hint") else None),
                    # TB 2026-11-11: automatisch stillgelegte Rahmenbereiche, in Reihenfolge.
                    "region_deactivated": (self._session.region_deactivations()
                                           if hasattr(self._session, "region_deactivations") else []),
                }
                if hasattr(self._session, "rejection_causes"):
                    causes = self._session.rejection_causes()
                    run["rejection_causes"] = {**causes, "causes": [live_cause(c) for c in causes["causes"]]}
            if run is not None and hasattr(self._session, 'output_status'):
                output = self._session.output_status()
                if output is not None:
                    run['output'] = output
            return {
                "state": self._state,
                "storage": self._storage_status(),
                "system": self._system_status(),
                **({"tracking_reasons": REASONS, "cause_texts": LIVE_CAUSE_TEXT.copy()} if full else {}),
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
                "previous_region_hint": deepcopy(self._previous_region_hint),
                "output": (self._session.unified_output_status()
                           if self._session is not None and hasattr(self._session, 'unified_output_status')
                           else {"transport": "off", "state": "off"}),
                "reference_eval": deepcopy(self._reference_eval),
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
                "reference": (self._session.reference_live_status()
                              if self._session is not None and hasattr(self._session, "reference_live_status")
                              else {"latest": None, "schedule_step": None,
                                    **(self._session.reference_status()
                                       if self._session is not None and hasattr(self._session, "reference_status")
                                       else {"enabled": False, "reason": "kein Referenzlauf"})}),
            }

    def _preview_hud(self) -> dict | None:
        session = self._session
        return session.frame_info() if self._state == "running" and session is not None else None

    def preview_frame(self, *, after_seq: int | None = None) -> PreviewFrame | None:
        """Bild und HUD fuer denselben Vorschau-Teil, ohne eingezeichnetes Quad."""
        return self._preview.frame(after_seq=after_seq)

    def preview_jpeg(self) -> bytes | None:
        """Werkzeugzugriff teilt die Kodierung mit dem Vorschau-Strom."""
        frame = self.preview_frame()
        return frame.jpeg if frame is not None else None

    def setup_file(self, name: str) -> Path | None:
        if name not in OVERLAYS or self._session_dir is None:
            return None
        path = self._session_dir / "setup" / f"{name}.png"
        return path if path.is_file() else None

    # -- Kamera --------------------------------------------------------------
    def start_camera(self) -> None:
        with self._operation_lock:
            try:
                self._owner.start(reason="kamera_verbinden")
            except Exception as exc:  # noqa: BLE001 - Meldung fuer die Seite
                raise LiveError(f"Kamera nicht gestartet: {exc}") from exc

    # -- Einrichtung ---------------------------------------------------------
    def _cache_setup_grid(self, proposal: dict) -> None:
        """Leserboxen nur bei einem neuen Vorschlag unter self._lock berechnen."""
        self._setup_grid = None
        try:
            if not all(key in proposal for key in ("grid", "target_size", "grid_source", "quad")):
                return
            grid = CharGrid.from_dict(proposal["grid"])
            self._setup_grid = {
                "target_size": list(proposal["target_size"]),
                "cell_boxes": [[round(float(value), 2) for value in box] for box in grid.cell_boxes()],
                # Vorschlagsreihenfolge OL, OR, UR, UL im Kamerabild beibehalten:
                # rectify bildet sie auf (0,0), (w-1,0), (w-1,h-1), (0,h-1) ab.
                "quad": [[round(float(value), 1) for value in point] for point in proposal["quad"]],
                "source": proposal["grid_source"],
            }
        except Exception as exc:  # noqa: BLE001 - optionaler Anzeigecache darf Einrichtung nicht abbrechen
            _LOG.warning("Rastervorschau nicht verfuegbar: %s", exc)

    def _reset_setup_live(self) -> None:
        """Live-Verlaeufe nur beim Erzeugen oder unter self._lock leeren."""
        self._setup_focus: dict = {"method": "climb", "samples": [], "verify": None, "roi": None,
                                   "roi_source": None, "end_check": None}
        self._setup_exposure: dict = {
            "target": live_setup.EXPOSURE_TARGET, "band": list(live_setup.EXPOSURE_BAND), "rounds": [],
        }
        self._step_times: dict[str, list[float | None]] = {key: [None, None] for key in SETUP_STEPS}
        self._setup_phase: str | None = None
        self._setup_attempt = 1
        self._setup_wait: dict | None = None
        self._setup_checks_live: dict = {}

    def _setup_progress_status(self) -> dict:
        """Schrittzeiten unter self._lock lesen; nur laufende Zeiten wachsen."""
        now = self._monotonic()
        steps = []
        for key, (start, end) in self._step_times.items():
            state = "pending"
            elapsed = None
            if start is not None:
                elapsed = (now if end is None else end) - start
                state = "running" if end is None else "done"
                if self._state == "setup_failed" and key == self._setup_step:
                    state = "failed"
            steps.append({"key": key, "state": state, "elapsed_s": elapsed})
        return {"steps": steps, "attempt": self._setup_attempt, "attempts_max": 3,
                "phase": self._setup_phase, "wait": deepcopy(self._setup_wait)}

    def _finish_setup_step(self, now: float) -> None:
        """Laufenden Schritt unter self._lock abschliessen."""
        times = self._step_times.get(self._setup_step)
        if times is not None and times[0] is not None and times[1] is None:
            times[1] = now

    def _check_setup_cancel(self) -> None:
        live_setup.check_cancelled(self._setup_cancel.is_set)

    def cancel_setup(self) -> None:
        """Nur Abbruch anfordern; der Worker beendet den laufenden Schritt."""
        with self._lock:
            if self._state != "setup_running":
                raise LiveError("Keine Einrichtung laeuft")
            self._setup_cancel.set()

    def _report_setup_phase(self, phase: str, attempt: int) -> None:
        self._check_setup_cancel()
        with self._lock:
            self._setup_phase, self._setup_attempt = phase, attempt
            self._setup_wait = None

    def _report_setup_wait(self, elapsed: float, total: float) -> None:
        self._check_setup_cancel()
        with self._lock:
            self._setup_wait = {"elapsed_s": elapsed, "total_s": total}

    def _report_setup_checks(self, report: dict) -> None:
        with self._lock:
            for name, check in report.get("checks", {}).items():
                self._setup_checks_live[name] = {
                    "status": check.get("status") or "NICHT_GEPRUEFT", "reason": check.get("reason"),
                }

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
            if camera_status.get("stalled") or not camera_status["running"]:
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
            self._require_storage()
            with self._lock:
                self._state, self._step, self._error = "setup_running", "start", None
                self._setup_started_at = self._monotonic()
                self._setup_elapsed_s = None
                self._setup_step = "start"
                self._setup_message = self._setup_message_base = self._diagnostics_error = None
                self._reset_setup_live()
                self._setup_cancel.clear()
                self._session_dir, self._proposal = session_dir, None
                self._setup_grid = None
                self._stability_frames = ()
                self._run_block = self._test_run = self._reader_tolerance = None
                self._profile_path = self._profile_camera = self._profile_info = None
                self._focus_reference = None
                self._diagnostic_copies = [s for s in [*self._diagnostic_copies, self._session]
                                           if getattr(s, 'diagnose_kopie', False)]
                self._session = None
                self._reference_eval = None
                self._run_reference = False
            self._setup_thread = threading.Thread(
                target=self._setup_worker, args=(session_dir, text), name="live-setup", daemon=True
            )
            self._setup_thread.start()

    def _report(self, step: str) -> None:
        with self._lock:
            self._check_setup_cancel()
            if step != self._setup_step:
                now = self._monotonic()
                self._finish_setup_step(now)
                if step in self._step_times:
                    self._step_times[step] = [now, None]
                self._setup_phase = self._setup_wait = None
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

    def _write_setup_image(self, path: Path, image: Any) -> None:
        """Diagnosebild schreiben; Fehler aendern den Einrichtungsausgang nicht."""
        try:
            if image is None or getattr(image, "dtype", None) != np.uint8 or not image.size:
                return
            import cv2

            if not cv2.imwrite(str(path), image):
                raise OSError("cv2.imwrite meldet Fehler")
        except Exception as exc:  # noqa: BLE001 - Diagnose darf die Einrichtung nicht abbrechen
            with self._lock:
                self._diagnostics_error = f"{path.name}: {type(exc).__name__}: {str(exc)[:160]}"

    def _check_run_start_focus(self, camera: CameraSettings, out_dir: Path) -> dict:
        """OQ-74: Schaerfe nach dem Kameraneustart am Laufstart; der Lauf startet in jedem Fall.

        Ergebnis geht nach session.json; eine WARNUNG mit Text erscheint im Laufstatus.
        Ein Kamerafehler bei der Pruefung wird als WARNUNG gemeldet, nicht verschwiegen.
        """
        reference = self._focus_reference
        if not reference:
            return {"status": "NICHT_GEPRUEFT", "reason": "keine_schaerfereferenz"}
        try:
            checked = live_setup.check_focus_at_run_start(
                OwnerSetupCamera(self._owner), reference, target=camera.controls["focus_absolute"],
            )
        except Exception as exc:  # noqa: BLE001 - Lauf startet trotzdem, Befund sichtbar
            _LOG.warning("Fokuspruefung Laufstart fehlgeschlagen: %s", exc)
            return {"status": "WARNUNG", "text": f"Fokus beim Laufstart nicht geprüft: {str(exc)[:160]}",
                    "reference": deepcopy(reference)}
        if checked is None:
            return {"status": "NICHT_GEPRUEFT", "reason": "keine_schaerfereferenz"}
        result, frames = checked
        box = tuple(reference.get("roi_box") or ()) or None
        for name, frame in frames.items():
            crop, rect = live_setup.focus_diagnostic_crop(frame, box)
            result.setdefault("diagnostic_crop", rect)
            self._write_setup_image(out_dir / f"fokus-laufstart-{name.replace('_', '-')}.png", crop)
        return result

    def _focus_preview_image(self) -> Any:
        """Neuestes Vorschaubild fuer die Hinweisbox vor der Fokussuche (OQ-74)."""
        latest = self._owner.latest()
        return None if not latest else getattr(latest[1], "image", None)

    def _setup_worker(self, session_dir: Path, text: str | None) -> None:
        try:
            self._check_setup_cancel()
            proposal = self._setup_runner(session_dir=session_dir, cell_text=text, report=self._report)
            with self._lock:
                self._check_setup_cancel()
                now = self._monotonic()
                self._finish_setup_step(now)
                self._setup_elapsed_s = now - self._setup_started_at
                self._setup_phase = self._setup_wait = None
                self._setup_step = "vorschlag"
                self._cache_setup_grid(proposal)
                self._proposal, self._state, self._step = proposal, "setup_ready", "vorschlag"
                self._run_block = run_block_reason(proposal)
        except Exception as exc:  # noqa: BLE001 - jeder Abbruch geht als Meldung an die Seite
            with self._lock:
                step = self._setup_step
                now = self._monotonic()
                self._finish_setup_step(now)
                self._setup_elapsed_s = now - self._setup_started_at
                self._setup_phase = self._setup_wait = None
                self._state, self._error = "setup_failed", _setup_error_for_page(str(exc))
            self._write_setup_diagnostic(
                session_dir / "setup" / "failure.json",
                {"step": step, "reason": str(exc), "created_at_utc": self._wall().isoformat()},
            )
            return

    def _open_serial(self) -> Any:
        import serial

        return serial.Serial(live_setup.SERIAL_PORT, live_setup.SERIAL_BAUDRATE, timeout=2.0)

    def _run_setup(self, *, session_dir: Path, cell_text: str | None, report: Callable[[str], None]) -> dict:
        """Fokus -> feste Kamera -> Displaybelichtung -> Standbilder -> Vorschlag."""
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

        def focus_sample(focus: int, score: float) -> None:
            self._check_setup_cancel()
            with self._lock:
                self._setup_focus["samples"].append([focus, score])

        def focus_fallback() -> None:
            with self._lock:
                self._setup_focus["method"] = "sweep"

        def exposure_round(entry: dict) -> None:
            self._check_setup_cancel()
            with self._lock:
                self._setup_exposure["rounds"].append(deepcopy(entry))

        report("fokus")
        # OQ-74: Fokus auf der LCD-Hinweisbox messen. Die Box der Einrichtung
        # entsteht erst nach der Fokussuche; deshalb eine billige Vorabsuche
        # (eine Konturensuche, etwa 10-55 ms) auf dem neuesten Vorschaubild.
        focus_hint = live_setup.focus_hint_box(self._focus_preview_image())
        focus_roi = {
            "pixels": live_setup.measurement_roi_pixels(live_setup.FOCUS_SOURCE_SIZE, focus_hint),
            "quelle": "lcd_hinweis" if focus_hint is not None else "mittleres_drittel",
            "hint_box": list(focus_hint) if focus_hint is not None else None,
        }
        with self._lock:
            start_focus = self._last_confirmed_focus
            self._setup_focus["roi"] = list(focus_roi["pixels"])
            self._setup_focus["roi_source"] = focus_roi["quelle"]
        if focus_hint is None:
            self._setup_progress("Fokus: kein LCD-Hinweis im Vorschaubild - mittleres Bilddrittel")
        settings, sweep = live_setup.focus_camera(
            OwnerSetupCamera(self._owner), focus_hint, start_focus=start_focus, info=self._setup_progress,
            on_sample=focus_sample, on_fallback=focus_fallback, should_stop=self._setup_cancel.is_set,
        )
        with self._lock:
            self._setup_focus["method"] = getattr(sweep, "focus_method", "sweep")
            verification = getattr(sweep, "focus_verify", None)
            if verification is not None:
                self._setup_focus["verify"] = {
                    "score": verification["verified"],
                    "threshold": live_setup.FOCUS_VERIFY_RATIO * verification["best_measured"],
                }
        camera_record = {
            "camera": settings.to_dict(), "focus_sweep": [[f, s] for f, s in sweep],
            "focus_method": getattr(sweep, "focus_method", "sweep"),
            "focus_verify": getattr(sweep, "focus_verify", None),
            "focus_roi": focus_roi,
            "focus_sweep_roi_mean": [[f, m] for f, m in getattr(sweep, "roi_means", {}).items()],
            "created_at_utc": self._wall().isoformat(),
        }
        verify_frame = getattr(sweep, "verify_frame", None)
        if verify_frame is not None:
            crop, rect = live_setup.focus_diagnostic_crop(verify_frame, focus_hint)
            camera_record["focus_diagnostic_crop"] = rect
            self._write_setup_image(setup_dir / "fokus-vor-neustart.png", crop)
        (setup_dir / "camera-settings.json").write_text(
            json.dumps(camera_record, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        report("kamera")
        self._owner.restart(lambda: self._source_for(settings), reason="einrichtung_regler")
        report("belichtung")
        self._setup_progress("Belichtung auf die Anzeige abstimmen")

        def apply_exposure(adjusted: CameraSettings) -> None:
            self._owner.restart(lambda: self._source_for(adjusted), reason="einrichtung_belichtung")

        settings, exposure_adjust = live_setup.adjust_exposure(
            OwnerSetupCamera(self._owner), settings, apply=apply_exposure, info=self._setup_progress,
            on_round=exposure_round,
        )
        camera_record.update(camera=settings.to_dict(), exposure_adjust=exposure_adjust)
        (setup_dir / "camera-settings.json").write_text(
            json.dumps(camera_record, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        # OQ-74: Nach dem letzten Kameraneustart auf derselben ROI pruefen, ob
        # die Linse noch am Suchergebnis steht; sonst einmal von unten neu setzen.
        checked = live_setup.check_focus_after_restart(
            OwnerSetupCamera(self._owner), focus_hint, sweep,
            should_stop=self._setup_cancel.is_set, info=self._setup_progress,
        )
        end_check, end_frames = checked if checked is not None else (None, {})
        for name, frame in end_frames.items():
            crop, rect = live_setup.focus_diagnostic_crop(frame, focus_hint)
            camera_record.setdefault("focus_diagnostic_crop", rect)
            self._write_setup_image(setup_dir / f"fokus-{name.replace('_', '-')}.png", crop)
        camera_record["focus_end_check"] = end_check
        (setup_dir / "camera-settings.json").write_text(
            json.dumps(camera_record, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        with self._lock:
            self._setup_focus["end_check"] = None if end_check is None else {
                "status": end_check["status"], "ratio": end_check["after_restart"]["ratio"],
                "reapproach_ratio": (end_check.get("reapproach") or {}).get("ratio"),
            }
        focus_check = live_setup.focus_check(focus_roi, end_check)
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
                report=self._report_setup_checks,
                on_phase=self._report_setup_phase,
                on_wait=self._report_setup_wait,
                should_stop=self._setup_cancel.is_set,
                info=self._setup_progress,
            )
        finally:
            if port is not None:
                port.close()
        report("vorschlag")
        with self._lock:
            self._stability_frames = getattr(result, "stability_frames", ())
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
            stability_images=self._stability_frames,
            stability_elapsed_s=result.stability_elapsed_s,
            stability_min_elapsed_s=15.0,
            setup_attempt=result.setup_attempt,
            reader_check=result.reader_check,
            live_tracking=True,
            exposure_adjust=exposure_adjust,
            focus_check=focus_check,
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
                stability_frames = self._stability_frames
            try:
                updated = live_setup.edit_regions(
                    proposal, add=add, remove=remove, out_dir=session_dir / "setup",
                    at_utc=self._wall().astimezone(UTC).isoformat(),
                    stability_images=stability_frames,
                )
            except live_setup.SetupInputError as exc:
                raise LiveInputError(str(exc)) from exc
            except (live_setup.SetupError, ValueError, OSError) as exc:
                raise LiveError(str(exc)) from exc
            with self._lock:
                self._cache_setup_grid(updated)
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
                self._cache_setup_grid({"grid": profile.grid.to_dict(), "target_size": profile.target_size,
                                        "grid_source": proposal.get("grid_source"), "quad": profile.quad})
                self._profile_path, self._profile_camera = path, profile.camera
                self._last_confirmed_focus = profile.camera.controls["focus_absolute"]
                self._focus_reference = deepcopy(proposal.get("focus_reference"))
                self._profile_info = {"confirmed_by": profile.confirmed_by,
                                      "confirmed_at_utc": profile.confirmed_at_utc,
                                      "warning_acknowledged": overall == "WARNUNG",
                                      "tracking_mode": "rahmenbereiche" if profile.live_tracking is not None else "ecc_alt"}
                self._run_block = confirmation["run_block"]
                self._reader_tolerance = reader_tolerance
                self._state = "confirmed"
                # R13-25 Review: die acht Einzelbilder (~50 MB) braucht nur
                # die Bereichskorrektur vor der Bestaetigung.
                self._stability_frames = ()

    # -- Lauf ----------------------------------------------------------------
    def cleanup(self, *, days: int, diagnostics_only: bool = False, execute: bool = False) -> dict:
        with self._operation_lock:
            with self._lock:
                protected = {self._run_dir} if self._state == 'running' and self._run_dir else set()
                for session in [*self._diagnostic_copies, self._session]:
                    if session is not None and getattr(session, 'diagnose_kopie', False):
                        protected.add(session._out_dir)
            return cleanup_runs(self._data_dir, days=days, diagnostics_only=diagnostics_only,
                                execute=execute, protected=protected, now=self._wall())

    def start_run(self, *, test_override: bool = False, reference: bool = True, norm_schedule=None,
                  diagnostics: bool = False, output=None) -> None:
        try:
            schedule = parse_norm_schedule(norm_schedule)
            if schedule is not None and not reference:
                raise ValueError("Werteplan braucht Referenzaufzeichnung")
            output = normalize_output(output, reference_port=live_setup.SERIAL_PORT if reference else None)
            if test_override and output['transport'] != 'off':
                raise ValueError('Testlauf erlaubt keine externe Ausgabe')
            require_output_acknowledgement(output)
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
                # Nach der Bestaetigung keine Bereichskorrektur mehr: nie
                # Einrichtungs-Einzelbilder durch den Lauf mitschleppen.
                self._stability_frames = ()
            run_id = uuid.uuid4().hex
            previous_state = self._state
            session = None
            from dispread.bridge.hub import BridgeOccupied
            from dispread.bridge.publisher import PairedOutputPublisher

            def output_factory(config, out_dir, *, release=None, **tick):
                # release kommt nur aus der Laufbestaetigung (LiveSession), R1;
                # tick (B2) nur aus format=4ch der Laufkonfiguration.
                return PairedOutputPublisher(config, out_dir, hub=self._bridge_hub, run_id=run_id,
                                             release=release, **tick)

            if output['transport'] in ('tcp', 'uart') and self._bridge_hub is None:
                raise LiveError('paired bridge hub is not configured')
            if self._bridge_hub is not None:
                try:
                    self._bridge_hub.reserve_real_run(run_id)
                except BridgeOccupied as exc:
                    raise LiveError(BRIDGE_BUSY_TEXT) from exc
                except ValueError as exc:
                    raise LiveError(str(exc)) from exc
            try:
                self._require_storage(diagnostics=diagnostics)
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
                        self._owner.restart(lambda: self._source_for(camera), reason="laufstart")
                    except RuntimeError as exc:
                        raise LiveError(f"Kamera nicht neu gestartet: {exc}") from exc
                    focus_check = self._check_run_start_focus(camera, out_dir)
                else:
                    focus_check = None
                try:
                    recorder = (ReferenceRecorder(self._serial_opener, out_dir / "reference.jsonl",
                                                  norm_schedule=schedule, port=live_setup.SERIAL_PORT) if reference else None)
                    session = LiveSession(
                        self._owner, profile_path, self._config, out_dir, test_run=test_run,
                        reader_d_max_factor=(self._reader_tolerance or {}).get("factor", 1.0),
                        reader_tolerance=self._reader_tolerance,
                        reference_recorder=recorder,
                        diagnostics=diagnostics, diagnostic_staging_root=self._diagnostic_staging_root,
                        **({'output': output} if output['transport'] != 'off' else {}),
                        **({'output_factory': output_factory} if output['transport'] in ('tcp', 'uart') else {}),
                    )
                    session.bridge_run_id = run_id
                    session.bridge_acknowledged_by = confirmed_by
                    if focus_check is not None:
                        session.focus_check = focus_check  # Audit in session.json
                    session.start()
                except Exception as exc:  # noqa: BLE001 - Meldung fuer die Seite
                    raise LiveError(f"Lauf nicht gestartet: {exc}") from exc
                stop = threading.Event()
                with self._lock:
                    self._diagnostic_copies = [s for s in [*self._diagnostic_copies, self._session]
                                               if getattr(s, 'diagnose_kopie', False)]
                    self._session, self._run_stop, self._state, self._error = session, stop, "running", None
                    self._run_focus_check = (None if focus_check is None or focus_check.get("text") is None
                                             else {"status": focus_check["status"], "text": focus_check["text"]})
                    self._previous_region_hint = None
                    self._run_dir = out_dir
                    self._test_run = test_run
                    self._run_reference = reference
                    self._reference_eval = None
                self._run_thread = threading.Thread(target=self._run_worker, args=(session, stop), name="live-run",
                                                    daemon=True)
                self._run_thread.start()
            except BaseException:
                try:
                    if session is not None:
                        try:
                            session.stop('startup_failed')
                        except Exception:
                            _LOG.error('Laufstart: Bereinigung fehlgeschlagen; urspruenglichen Fehler erhalten')
                finally:
                    if self._bridge_hub is not None:
                        self._bridge_hub.release_real_run(run_id)
                    with self._lock:
                        self._state = previous_state
                        self._run_thread = None
                raise

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
                        self._finish_run(session, error)

    def _finish_run(self, session: LiveSession, error: str | None) -> None:
        """Unter self._lock, erst nach dem Abschluss der Laufdateien."""
        if self._bridge_hub is not None:
            self._bridge_hub.release_real_run(getattr(session, 'bridge_run_id', None))
        self._state, self._error = 'stopped', error
        summary = getattr(session, 'summary', None)
        hint = summary.get('tracking_region_hint') if isinstance(summary, dict) else None
        # T3: nur dauerhaft Unstimmiges (Anteil und mehrfach markiert) wandert in die Einrichtung;
        # einmal kurz Aufgefallenes ist Rauschen. Das Viereck erlaubt, neue Aufstellungen zu erkennen.
        regions = [r for r in ((hint.get('regions') if isinstance(hint, dict) else None) or [])
                   if r.get('max_share', 0) >= MIN_SHARE and r.get('flagged_evaluations', 0) >= 2]
        grid = self._setup_grid
        self._previous_region_hint = None if not regions else {
            'session_id': None if self._session_dir is None else self._session_dir.name,
            'run': None if self._run_dir is None else self._run_dir.name,
            'quad': deepcopy(grid.get('quad')) if isinstance(grid, dict) else None,
            'regions': [{'number': r['number'], 'centre': list(r['centre']), 'max_share': r['max_share'],
                         'flagged_evaluations': r['flagged_evaluations']} for r in regions]}
        if self._run_reference:
            self._reference_eval = {'state': 'running'}
            threading.Thread(target=self._reference_eval_worker, args=(session, self._run_dir),
                             name='live-reference-eval', daemon=True).start()

    def _reference_eval_worker(self, session: LiveSession, run_dir: Path) -> None:
        def rows(path):
            with path.open(encoding='utf-8') as stream:
                for line in stream:
                    if line.strip():
                        yield json.loads(line)

        try:
            meta = json.loads((run_dir / 'session.json').read_text(encoding='utf-8'))
            validate_reference_session(meta)
            reference = list(rows(run_dir / 'reference.jsonl'))
            counts = evaluate_records(meta, reference, rows(run_dir / 'records.jsonl'))
            result = {'state': 'done', **{key: counts[key] for key in
                      ('misreads', 'compared_valid', 'undecided_valid', 'uncovered_valid')}}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result = {'state': 'error', 'error': f'Abgleich abgelehnt: {exc}'}
        except Exception as exc:  # noqa: BLE001 - Auswertung darf nicht in running verbleiben
            result = {'state': 'error', 'error': f'Abgleich abgelehnt: {exc}'}
        with self._lock:
            # Eine neue Einrichtung oder Sitzung entwertet noch laufende Auswertungen.
            if self._session is session and self._state == 'stopped':
                self._reference_eval = result

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
                self._finish_run(session, error)

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
