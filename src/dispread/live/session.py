"""Live-Sitzung: bestaetigtes Profil -> Pipeline -> ValueRecord -> JSONL.

Spec 2026-10-12 §2/§4. Liest immer das neueste Bild des CameraOwner,
ueberspringt aeltere und zaehlt sie. Jeder Datensatz traegt die Aufnahmezeit
des gelesenen Bilds. Die Timing-Kalibrierung ist Pflicht und wird in
session.json aufgezeichnet, aber nicht angewandt.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

import cv2

from dispread.layout import CharLayout
from dispread.live import (
    DEFAULT_CALIBRATION,
    DEFAULT_TEMPLATES,
    DEFAULT_TEMPLATES_SHA256,
    RELEASE_NOTICE,
)
from dispread.live.clock import ClockLog
from dispread.live.frame_tracking import FrameTrackingConfig
from dispread.live.tracking import ConfirmedRegionLocator, TrackedQuadLocator
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.pipeline import Pipeline, PipelineConfig
from dispread.records import ValueRecord, ValueStatus
from dispread.session_profile import SessionProfile
from dispread.sink.jsonl import JsonlSink
from dispread.timing_calibration import load_calibration
from dispread.validate import ReleaseGate, default_gate_config

SCHEMA = "live-session/1"


class StartRefused(ValueError):
    """Sitzung startet nicht; die Meldung nennt den Grund."""


class CameraLost(RuntimeError):
    """Die Kamera liefert keine Bilder mehr."""


class AuditFailed(RuntimeError):
    """Ein Datensatz konnte nicht sicher ins Audit geschrieben werden."""


@dataclass(frozen=True)
class LiveConfig:
    templates: Path = DEFAULT_TEMPLATES
    templates_sha256: str = DEFAULT_TEMPLATES_SHA256
    calibration: Path = DEFAULT_CALIBRATION
    unit: str = "mV/V"
    confirm_frames: int = 2
    clock_interval_s: float = 60.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LiveSession:
    def __init__(
        self,
        owner: Any,
        profile_path: Path,
        config: LiveConfig,
        out_dir: Path,
        *,
        test_run: dict | None = None,
        reference_recorder: Any = None,
        reader_d_max_factor: float = 1.0,
        reader_tolerance: dict | None = None,
        reader_factory: Callable[..., Any] = DotMatrixReader.from_file,
        locator_factory: Callable[[Any, list], Any] | None = None,
        clock: ClockLog | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        wall: Callable[[], datetime] | None = None,
    ) -> None:
        self._reference_recorder = reference_recorder
        self._reference_error = None
        self._test_run = test_run
        # Lockerung und ihre Markierung in session.json muessen zusammenpassen.
        expected_factor = 1.0 if reader_tolerance is None else reader_tolerance.get("factor")
        if reader_d_max_factor != expected_factor:
            raise ValueError("reader_d_max_factor passt nicht zu reader_tolerance")
        self._reader_d_max_factor = reader_d_max_factor
        self._reader_tolerance = reader_tolerance
        self._tolerance_frames = 0
        self.latest_guess: dict | None = None
        self._guesses: Counter[str] = Counter()
        self._owner = owner
        self._profile_path = Path(profile_path)
        self._config = config
        self._out_dir = Path(out_dir)
        self._reader_factory = reader_factory
        self._locator_factory = locator_factory
        self._clock = clock or ClockLog()
        self._monotonic = monotonic
        self._wall = wall or (lambda: datetime.now(UTC))
        self.session_path = self._out_dir / "session.json"
        self.records_path = self._out_dir / "records.jsonl"
        self.latest: ValueRecord | None = None
        self.latest_monotonic: float | None = None
        self.end_reason: str | None = None
        self.summary: dict = {}
        self.tracking: dict = {"mode": "ecc_alt", "version": None, "regions": None}
        self._pipeline: Pipeline | None = None
        self._sink: JsonlSink | None = None
        self._meta: dict = {}
        self._seen = 0
        self._by_status: dict[str, int] = {}
        #: TRANSITION wegen Ziffernwechsel (Grund anzeige_wechselt), getrennt
        #: gezaehlt, damit Laeufe mit frueheren vergleichbar bleiben.
        self._display_changing = 0
        self._frames_read = 0
        self._frames_skipped = 0
        self._frame_gaps_start = 0
        self._audit_errors = 0
        self._tracking_lost = 0
        self._tracking_lost_reasons: Counter[str] = Counter()
        self._track_scores: deque[float] = deque(maxlen=10_000)
        self._track_score_n = 0
        self._track_score_min: float | None = None
        self._track_score_max: float | None = None
        self._stop_lock = threading.Lock()
        self._stopped = False
        self._last_clock = 0.0

    # -- Start ---------------------------------------------------------------
    def start(self) -> None:
        cfg = self._config
        try:
            profile = SessionProfile.load(self._profile_path)
            layout = CharLayout.from_profile(profile, cfg.unit)
        except (OSError, ValueError, KeyError) as exc:
            raise StartRefused(f"Profil {self._profile_path}: {exc}") from exc
        try:
            reader = self._reader_factory(cfg.templates, cfg.templates_sha256, d_max_factor=self._reader_d_max_factor)
        except (OSError, ValueError) as exc:
            raise StartRefused(f"Vorlagen {cfg.templates}: {exc}") from exc
        try:
            calibration = load_calibration(cfg.calibration)
        except ValueError as exc:
            raise StartRefused(f"Timing-Kalibrierung fehlt oder ist ungueltig: {exc}") from exc
        if profile.camera is not None and calibration.camera_usb_id != profile.camera.usb_id:
            raise StartRefused(
                f"Timing-Kalibrierung gilt fuer {calibration.camera_usb_id}, Profil nutzt {profile.camera.usb_id}"
            )
        reference = profile.reference_frame or {}
        ref_path = Path(reference.get("path", ""))
        if not ref_path.is_file() or _sha256(ref_path) != reference.get("sha256"):
            raise StartRefused(f"Referenzbild {ref_path} fehlt oder wurde veraendert - neu einrichten")
        image = cv2.imread(str(ref_path))
        if image is None:
            raise StartRefused(f"Referenzbild {ref_path} nicht lesbar - neu einrichten")
        block = profile.live_tracking
        if block is not None:
            if (not isinstance(block, dict) or block.get("version") != 1 or block.get("method") != "rahmenbereiche"
                    or block.get("frame_sha256") != reference["sha256"]
                    or block.get("config") != FrameTrackingConfig().to_dict()):
                raise StartRefused("Rahmenbereiche oder Pruefversion passen nicht zum Profil - neu einrichten")
            try:
                locator = ConfirmedRegionLocator(image, profile.quad, block)
            except (ValueError, KeyError, TypeError) as exc:
                raise StartRefused(f"Rahmenbereiche ungueltig: {exc} - neu einrichten") from exc
            self.tracking = {"mode": "rahmenbereiche", "version": 1,
                             "regions": len(block["proposal"]["regions"])}
        else:
            locator = None
        # Die bisherige Zwei-Argument-Factory bleibt fuer injizierte Locators erhalten.
        if self._locator_factory is not None:
            locator = self._locator_factory(image, profile.quad)
            self.tracking = {"mode": "injiziert", "profile_mode": self.tracking["mode"],
                             "version": None, "regions": None}
        elif locator is None:
            locator = TrackedQuadLocator(image, profile.quad)
        gate = ReleaseGate(
            default_gate_config("dotmatrix", confirm_frames=cfg.confirm_frames, expected_unit=cfg.unit)
        )
        self._pipeline = Pipeline(
            source=self._owner,
            locator=locator,
            reader=reader,
            gate=gate,
            sinks=[],
            config=PipelineConfig(
                profile_id=f"{profile.device_id}/{profile.session_id}", layout=layout, locate_every=0
            ),
        )
        self._out_dir.mkdir(parents=True, exist_ok=True)
        owner_status = self._owner.status()
        self._frame_gaps_start = owner_status.get("gaps", 0)
        self._meta = {
            "schema": SCHEMA,
            "tracking": dict(self.tracking),
            "reader_tolerance": self._reader_tolerance,
            "session_id": profile.session_id,
            "device_id": profile.device_id,
            "profile": {"path": str(self._profile_path), "sha256": _sha256(self._profile_path)},
            "templates": {"path": str(cfg.templates), "sha256": cfg.templates_sha256},
            "timing_calibration": {
                "path": str(cfg.calibration),
                "sha256": _sha256(Path(cfg.calibration)),
                "display_offset_ms": calibration.display_offset_ms,
                "guard_margin_ms": calibration.guard_margin_ms,
                "applied": False,
            },
            "gate": {"backend": "dotmatrix", "confirm_frames": cfg.confirm_frames, "expected_unit": cfg.unit},
            "camera": owner_status.get("source", {}),
            "release_notice": RELEASE_NOTICE,
            "started_at_utc": self._wall().isoformat(),
        }
        confirmation_path = self._profile_path.parent / "confirmation.json"
        if confirmation_path.exists():
            self._meta["confirmation"] = json.loads(confirmation_path.read_text(encoding="utf-8"))
        latest = self._owner.latest() if hasattr(self._owner, "latest") else None
        self._seen = latest[0] if latest else 0
        self._clock.sample()
        self._last_clock = self._monotonic()
        self._write_session(ended=False)
        self._sink = JsonlSink(self.records_path)
        self._sink.open()
        if self._reference_recorder is not None:
            try:
                self._reference_recorder.start()
            except Exception:
                self.stop(reason="start_failed")
                raise
        self._write_session(ended=False)

    # -- Lesen ---------------------------------------------------------------
    def step(self, timeout: float = 0.5) -> ValueRecord | None:
        if self._stopped:
            return None
        if self._pipeline is None or self._sink is None:
            raise RuntimeError("start() zuerst")
        got = self._owner.wait_newer(self._seen, timeout)
        # Warten haelt den Stop nicht auf; Verarbeitung und Abschluss sind serialisiert.
        with self._stop_lock:
            if self._stopped:
                return None
            if got is None:
                status = self._owner.status()
                if not status["running"]:
                    raise CameraLost(status.get("error") or "Kamera gestoppt")
                return None
            sequence, frame = got
            skipped = max(0, sequence - self._seen - 1)
            self._seen = sequence
            self._frames_skipped += skipped
            record = self._pipeline.process(frame, dropped_frames=skipped)
            if record.reject_reasons and record.reject_reasons[0].startswith("tracking_lost:"):
                self._tracking_lost += 1
                self._tracking_lost_reasons[record.reject_reasons[0].split(":", 1)[1]] += 1
            track = getattr(self._pipeline.locator, "last_track", None)
            if track is not None:
                score = float(track.score)
                self._track_scores.append(score)
                self._track_score_n += 1
                self._track_score_min = score if self._track_score_min is None else min(self._track_score_min, score)
                self._track_score_max = score if self._track_score_max is None else max(self._track_score_max, score)
            receipt = self._sink.emit(record)
            health = self._sink.health()
            if receipt.t_complete_ns is None or health.errors:
                self._audit_errors += 1
                raise AuditFailed(f"Audit nicht geschrieben: {health.last_error or 'Schreibfehler'}")
            self._frames_read += 1
            self._by_status[record.status.value] = self._by_status.get(record.status.value, 0) + 1
            if record.reject_reasons and record.reject_reasons[0] == "anzeige_wechselt":
                self._display_changing += 1
            if self._reader_tolerance is not None and record.status is ValueStatus.VALID:
                read = self._pipeline.last_read
                cells = read.diagnostics.get("cells", []) if read is not None else []
                if any(isinstance(c, dict) and isinstance(c.get("d_best"), (int, float))
                       and c["d_best"] > self._reader_tolerance["d_max_templates"] for c in cells):
                    self._tolerance_frames += 1
            # Erst nach geschriebenem Record: Vermutungen zaehlen nur Bilder mit Audit.
            if self._test_run is not None:
                read = self._pipeline.last_read
                diag = read.diagnostics if read is not None and read.backend_id == "dotmatrix" else {}
                cells = diag.get("cells")
                self.latest_guess = None
                if (isinstance(cells, list) and cells
                        and all(isinstance(c, dict) and isinstance(c.get("best"), str)
                                and isinstance(c.get("margin"), (int, float)) for c in cells)):
                    text = "".join(c["best"] for c in cells)
                    self.latest_guess = {
                        "text": text, "uncertain": [i for i, c in enumerate(cells) if c["margin"] < 0],
                        "reject_reason": diag.get("reject_reason"),
                    }
                    self._guesses[text] += 1
            self.latest = record
            self.latest_monotonic = self._monotonic()
            if self._monotonic() - self._last_clock >= self._config.clock_interval_s:
                self._clock.sample()
                self._last_clock = self._monotonic()
                self._write_session(ended=False)
            return record

    def latest_age_s(self) -> float | None:
        """Alter der letzten Ablesung fuer die STALE-Anzeige, ohne neuen Datensatz."""
        latest_monotonic = self.latest_monotonic
        if latest_monotonic is None:
            return None
        return self._monotonic() - latest_monotonic

    def run(self, stop: threading.Event) -> None:
        """Lesen, bis `stop` gesetzt ist oder ein Fehler die Sitzung beendet."""
        reason = None
        try:
            while not stop.is_set() and not self._stopped:
                self.step()
        except CameraLost as exc:
            reason = f"kamera: {exc}"
        except AuditFailed as exc:
            reason = f"audit: {exc}"
        except Exception as exc:
            reason = f"fehler: {type(exc).__name__}: {exc}"
        if reason is not None:
            with self._stop_lock:
                if self.end_reason is None:
                    self.end_reason = reason

    # -- Ende ----------------------------------------------------------------
    def stop(self, reason: str = "bediener") -> dict:
        with self._stop_lock:
            if self._stopped:
                return self.summary
            if self.end_reason is None:
                self.end_reason = reason
            try:
                if self._reference_recorder is not None:
                    self._reference_recorder.stop()
            except Exception as exc:  # noqa: BLE001 - Abschluss bleibt erhalten
                self._reference_error = str(exc)
            finally:
                self._clock.sample()
                try:
                    if self._sink is not None:
                        self._sink.close()
                finally:
                    self._write_session(ended=True)
                    self._stopped = True
            return self.summary

    def request_reference_stop(self) -> None:
        if self._reference_recorder is not None:
            self._reference_recorder.request_stop()

    def reference_status(self) -> dict:
        if self._reference_recorder is None:
            return {"enabled": False, "reason": "vom Bediener deaktiviert"}
        status = self._reference_recorder.status()
        if self._reference_error is not None:
            status['error'] = self._reference_error
        return status

    def _write_session(self, *, ended: bool) -> None:
        if self._stopped and not ended:
            return
        owner_status = self._owner.status()
        self.summary = {
            "by_status": dict(self._by_status),
            "transition_display_changing": self._display_changing,
            "frames_read": self._frames_read,
            "tolerance_frames": self._tolerance_frames,
            "frames_skipped": self._frames_skipped,
            "frame_gaps": owner_status.get("gaps", 0) - self._frame_gaps_start,
            "frame_gaps_owner_total": owner_status.get("gaps", 0),
            "audit_errors": self._audit_errors,
            "tracking_lost": self._tracking_lost,
            "tracking_lost_reasons": dict(self._tracking_lost_reasons),
            "track_score": {
                "min": self._track_score_min,
                # Median der letzten hoechstens 10 000 Tracks; Extremwerte und n ueber alle.
                "median": median(self._track_scores) if self._track_scores else None,
                "max": self._track_score_max,
                "n": self._track_score_n,
            },
            "camera_error": owner_status.get("error"),
            "end_reason": self.end_reason if ended else None,
        }
        data = dict(self._meta)
        data["reference"] = self.reference_status()
        data["clock_offset_boottime_minus_monotonic_ns"] = self._clock.to_session(ended=ended)
        data["summary"] = self.summary
        if self._test_run is not None:
            data["test_run"] = self._test_run
            data["guesses"] = {"frames": self._guesses.total(), "top": self._guesses.most_common(10)}
        if ended:
            data["ended_at_utc"] = self._wall().isoformat()
        tmp = self.session_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.session_path)
