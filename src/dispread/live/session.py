"""Live-Sitzung: bestaetigtes Profil -> Pipeline -> ValueRecord -> JSONL.

Spec 2026-10-12 §2/§4. Liest immer das neueste Bild des CameraOwner,
ueberspringt aeltere und zaehlt sie. Jeder Datensatz traegt die Aufnahmezeit
des gelesenen Bilds. Die Timing-Kalibrierung ist Pflicht und wird in
session.json aufgezeichnet, aber nicht angewandt.
Werkbank-Schreibsequenzen sperren VALID vor Audit/Ausgabe als TRANSITION
mit geraet_umkonfiguriert; Referenzwerte gehen weiterhin nicht ins Gate.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import Counter, deque
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from statistics import median
from typing import Any

import cv2

from dispread.bridge.protocol import TEST_RELEASE
from dispread.bridge.publisher import PairedOutputPublisher
from dispread.gsv_transport import OutputConfig
from dispread.layout import CharLayout
from dispread.live import (
    DEFAULT_CALIBRATION,
    DEFAULT_TEMPLATES,
    DEFAULT_TEMPLATES_SHA256,
    RELEASE_NOTICE,
)
from dispread.live.causes import RejectionWindow
from dispread.live.clock import ClockLog
from dispread.live.diagnostics import DiagnosticRecorder
from dispread.live.frame_tracking import FrameTrackingConfig
from dispread.live.output import (
    BRIDGE_4CH_RELEASE_NOTE,
    BRIDGE_RELEASE_NOTE,
    SERIAL_4CH_RELEASE_NOTE,
    SERIAL_RELEASE_NOTE,
    LiveOutput,
    bridge_config,
    bridge_tick_options,
    normalize_output,
    require_output_acknowledgement,
)
from dispread.live.recent import RecentStrip
from dispread.live.region_hint import RegionConsistency
from dispread.live.tracking import ConfirmedRegionLocator, TrackedQuadLocator
from dispread.live.tracking_advice import TrackingAdvice, empty_summary
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.pipeline import Pipeline, PipelineConfig
from dispread.records import ValueRecord, ValueStatus, to_boottime_ns
from dispread.session_profile import SessionProfile, require_live_profile
from dispread.sink.jsonl import JsonlSink
from dispread.sink.protocol.userdefined_4ch import checked_value_text
from dispread.timing_calibration import load_calibration
from dispread.validate import ReleaseGate, default_gate_config

SCHEMA = "live-session/1"
_LOG = logging.getLogger(__name__)


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


#: Felder, die nur die Auswahl bei der Einrichtung steuern, nie den Lauf.
_SETUP_ONLY_TRACKING_FIELDS = frozenset({
    "proposal_stability_peak_margin",
    # TB 2026-11-11: strengere Auswahl; aeltere Profile bleiben startbar.
    "proposal_min_peak_curvature", "proposal_max_photometric_shift_px",
})


def _run_start_tracking_config(config: dict) -> dict:
    # Diese Grenzen bewerten nur Einrichtungsbilder, nicht bestaetigte Bereiche im Lauf.
    return {key: value for key, value in config.items() if key not in _SETUP_ONLY_TRACKING_FIELDS}


def build_live_pipeline(
    source: Any,
    profile_path: Path,
    cfg: LiveConfig,
    *,
    reader_factory: Callable[..., Any] = DotMatrixReader.from_file,
    locator_factory: Callable[[Any, list], Any] | None = None,
    reader_d_max_factor: float = 1.0,
    allow_offline: bool = False,
    reference_loaded: Callable[[Any, SessionProfile], None] | None = None,
) -> tuple[Pipeline, SessionProfile, Any, dict]:
    """Identischer, schreibfreier Aufbau fuer Live-Sitzung und Offline-Replay."""
    tracking = {"mode": "ecc_alt", "version": None, "regions": None}
    try:
        profile = SessionProfile.load(profile_path)
        if not allow_offline:
            require_live_profile(profile)
        layout = CharLayout.from_profile(profile, cfg.unit)
    except (OSError, ValueError, KeyError) as exc:
        raise StartRefused(f"Profil {profile_path}: {exc}") from exc
    try:
        reader = reader_factory(cfg.templates, cfg.templates_sha256, d_max_factor=reader_d_max_factor)
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
    if isinstance(block, dict):
        try:
            # Optionale Vorschlags-/Grobschaetzungsfelder ergaenzen; Profildatei bleibt unveraendert.
            # Eigener Import: der Vergleich unten nutzt das (in Tests ersetzbare)
            # Modulattribut FrameTrackingConfig als "aktuelle Defaults", das
            # Ergaenzen des gespeicherten Dicts dagegen immer die echte Klasse.
            from dispread.live.frame_tracking import FrameTrackingConfig as StoredTrackingConfig

            block = {**block, "config": StoredTrackingConfig.from_dict(block["config"]).to_dict()}
        except (ValueError, KeyError, TypeError) as exc:
            raise StartRefused(f"Rahmenkonfiguration ungueltig: {exc} - neu einrichten") from exc
    if block is not None:
        if (not isinstance(block, dict) or block.get("version") != 1 or block.get("method") != "rahmenbereiche"
                or block.get("frame_sha256") != reference["sha256"]
                or _run_start_tracking_config(block["config"])
                != _run_start_tracking_config(FrameTrackingConfig().to_dict())):
            raise StartRefused("Rahmenbereiche oder Pruefversion passen nicht zum Profil - neu einrichten")
        try:
            locator = ConfirmedRegionLocator(image, profile.quad, block)
        except (ValueError, KeyError, TypeError) as exc:
            raise StartRefused(f"Rahmenbereiche ungueltig: {exc} - neu einrichten") from exc
        tracking = {"mode": "rahmenbereiche", "version": 1,
                    "regions": len(block["proposal"]["regions"]), "auswahl": block.get("auswahl", "automatisch")}
    else:
        locator = None
    # Die bisherige Zwei-Argument-Factory bleibt fuer injizierte Locators erhalten.
    if locator_factory is not None:
        locator = locator_factory(image, profile.quad)
        tracking = {"mode": "injiziert", "profile_mode": tracking["mode"],
                    "version": None, "regions": None}
    elif locator is None:
        locator = TrackedQuadLocator(image, profile.quad)
    gate = ReleaseGate(
        default_gate_config("dotmatrix", confirm_frames=cfg.confirm_frames, expected_unit=cfg.unit)
    )
    pipeline = Pipeline(
        source=source,
        locator=locator,
        reader=reader,
        gate=gate,
        sinks=[],
        config=PipelineConfig(
            profile_id=f"{profile.device_id}/{profile.session_id}", layout=layout, locate_every=0
        ),
    )
    if reference_loaded is not None:
        reference_loaded(image, profile)
    return pipeline, profile, calibration, tracking


class ProbeProcess:
    """Schutzprobe in einem eigenen Interpreter (kein GIL, nice 19); poll() blockiert nie.

    Ein Hilfsthread uebergibt den Auftrag per stdin und wartet nur auf E/A; der
    Leserthread fragt mit poll() ab. cancel() beendet den Prozess (Laufende).
    """

    def __init__(self, payload, base, index, *, command=None):
        import pickle
        import subprocess
        import sys

        self.base, self.index = frozenset(base), index
        self._outcome = None
        self._cancelled = False
        self._process = subprocess.Popen(command or [sys.executable, '-m', 'dispread.live.region_probe'],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL)
        job = pickle.dumps((payload, sorted(self.base), sorted(self.base | {index})))

        def talk():
            try:
                out, _ = self._process.communicate(job)
                self._outcome = (pickle.loads(out) if out else
                                 ('error', f'Probenprozess ohne Ergebnis beendet (Code {self._process.returncode})'))
            except Exception as exc:  # noqa: BLE001 - ohne Probe keine Stilllegung
                self._outcome = ('error', f'{type(exc).__name__}: {exc}')

        self._thread = threading.Thread(target=talk, name='rahmen-schutzprobe', daemon=True)
        self._thread.start()

    @property
    def pid(self) -> int:
        return self._process.pid

    def poll(self):
        """None solange die Probe laeuft, sonst ('ok', Ergebnis) oder ('error', Text)."""
        if self._thread.is_alive():
            return None
        if self._cancelled:
            return ('error', 'abgebrochen')
        return self._outcome

    def cancel(self) -> None:
        self._cancelled = True
        if self._process.poll() is None:
            self._process.kill()
        self._thread.join(2)


class _ProbeThread:
    """Nur fuer Attrappen ohne probe_payload (Tests): dieselbe Schnittstelle im Thread."""

    def __init__(self, tracker, base, index):
        self.base, self.index = frozenset(base), index
        self._outcome = None
        self._stop = threading.Event()

        def work():
            try:
                self._outcome = ('ok', tracker.bias_probe(self.base, self.base | {index}))
            except Exception as exc:  # noqa: BLE001 - ohne Probe keine Stilllegung
                self._outcome = ('error', f'{type(exc).__name__}: {exc}')

        self.thread = threading.Thread(target=work, name='rahmen-schutzprobe', daemon=True)
        self.thread.start()

    def poll(self):
        return None if self.thread.is_alive() else self._outcome

    def cancel(self) -> None:
        self._stop.set()


class LiveSession:
    def __init__(
        self,
        owner: Any,
        profile_path: Path,
        config: LiveConfig,
        out_dir: Path,
        *,
        test_run: dict | None = None,
        output_factory: Callable[..., Any] = partial(PairedOutputPublisher, hub=None),
        reference_recorder: Any = None,
        output: dict | OutputConfig | None = None,
        diagnostics: bool = False,
        diagnostic_staging_root: Path = Path('/dev/shm'),
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
        self._reference_started = False
        self._test_run = test_run
        self._testlauf_unterdrueckt = 0
        self._reconfiguration_suppressed = 0
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
        self._output_config = normalize_output(output.to_dict() if isinstance(output, OutputConfig) else output)
        self._output_transport = self._output_config['transport']
        if test_run is not None and self._output_transport != 'off':
            raise StartRefused('Testlauf erlaubt keine externe Ausgabe')
        try:
            require_output_acknowledgement(self._output_config)
        except ValueError as exc:
            raise StartRefused(str(exc)) from exc
        self._output = None
        self._bridge_acknowledged = False
        if self._output_transport == 'serial':
            options = {key: value for key, value in self._output_config.items()
                       if key not in ('transport', 'acknowledge_unaccepted')}
            self._output = LiveOutput(options, self._out_dir / 'tx.jsonl')
        elif self._output_transport != 'off':
            # Testfreigabe nur aus der Laufbestaetigung des Pi-Bedieners (R1).
            self._bridge_acknowledged = self._output_config['acknowledge_unaccepted'] is True
            self._output = output_factory(bridge_config(self._output_config), self._out_dir,
                                          **({'release': TEST_RELEASE} if self._bridge_acknowledged else {}),
                                          **bridge_tick_options(self._output_config))
            if self._bridge_acknowledged and getattr(self._output, 'release', None) != TEST_RELEASE:
                raise StartRefused('Ausgabe: Testfreigabe vom Brückenweg nicht übernommen')
        self._output_error_saved = False
        self._diagnostics = DiagnosticRecorder(self._out_dir, enabled=diagnostics,
                                               staging_root=diagnostic_staging_root, monotonic=monotonic)
        self._marks = 0
        self.last_mark: dict | None = None
        self._reader_factory = reader_factory
        self._locator_factory = locator_factory
        self._clock = clock or ClockLog()
        self._monotonic = monotonic
        self._wall = wall or (lambda: datetime.now(UTC))
        self._bridge_acknowledged_at_utc = (self._wall().isoformat()
                                            if self._bridge_acknowledged else None)
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
        self.recent = RecentStrip()
        self._frame_info: tuple[float, dict] | None = None
        self._frame_info_warned = False
        self._processing_window: deque[tuple[float, int]] = deque()
        #: TRANSITION wegen Ziffernwechsel (Grund anzeige_wechselt), getrennt
        #: gezaehlt, damit Laeufe mit frueheren vergleichbar bleiben.
        self._display_changing = 0
        self._rejection_window = RejectionWindow()
        self._tracking_advice: TrackingAdvice | None = None
        self._tracking_advice_warned = False
        # TC 2026-11-11: Bereichshinweis, reine Diagnose ohne Rueckweg in den Messpfad.
        self._region_consistency: RegionConsistency | None = None
        self._region_consistency_warned = False
        # TB 2026-11-11: laufende Schutzprobe und Ergebnisse je (Satz, Bereich).
        self._region_probe = None
        self._region_probe_cache: dict = {}
        self._region_event_attempted: set = set()
        self._frame_disabled: frozenset = frozenset()
        self._region_disable_errors = 0
        self._region_disable_warned = False
        self._frames_read = 0
        self._frames_skipped = 0
        self._frame_gaps_start = 0
        self._audit_errors = 0
        self._tracking_lost = 0
        self._tracking_coarse_retries = 0
        self._tracking_coarse_accepted = 0
        self._tracking_lost_reasons: Counter[str] = Counter()
        self._track_scores: deque[float] = deque(maxlen=10_000)
        self._track_score_n = 0
        self._track_score_min: float | None = None
        self._track_score_max: float | None = None
        self._stop_lock = threading.Lock()
        self._stopped = False
        self._last_clock = 0.0
        self._started_monotonic: float | None = None
        self._ended_monotonic: float | None = None
        self._ended_at_utc: str | None = None
        self._frozen_recent: tuple[list[list], float] | None = None

    def _prepare_tracking_advice(self, image, profile):
        centres = [region['centre'] for region in
                   (profile.live_tracking or {}).get('proposal', {}).get('regions', [])]
        # Bereits geladenes Referenzbild; kein Ergebnis geht zur Pipeline zurueck.
        self._tracking_advice = TrackingAdvice(image, profile.quad, region_centres=centres)

    # -- Start ---------------------------------------------------------------
    def start(self) -> None:
        cfg = self._config
        self._pipeline, profile, calibration, self.tracking = build_live_pipeline(
            self._owner, self._profile_path, cfg,
            reader_factory=self._reader_factory, locator_factory=self._locator_factory,
            reader_d_max_factor=self._reader_d_max_factor,
            reference_loaded=self._prepare_tracking_advice,
        )
        self._out_dir.mkdir(parents=True, exist_ok=True)
        owner_status = self._owner.status()
        self._frame_gaps_start = owner_status.get("gaps", 0)
        self._started_monotonic = self._monotonic()
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
            "audit": {"rotation": False, "path": "records.jsonl"},
        }
        confirmation_path = self._profile_path.parent / "confirmation.json"
        if confirmation_path.exists():
            self._meta["confirmation"] = json.loads(confirmation_path.read_text(encoding="utf-8"))
        latest = self._owner.latest() if hasattr(self._owner, "latest") else None
        self._seen = latest[0] if latest else 0
        if latest is None and hasattr(self._owner, "last_sequence"):
            # Nach einem Kameraneustart ist latest() leer, die Bildnummer
            # laeuft aber weiter: Luecken erst ab dem Laufstart zaehlen.
            self._seen = self._owner.last_sequence()
        self._clock.sample()
        self._last_clock = self._monotonic()
        self._write_session(ended=False)
        # Vollstaendiger Audit je Lauf; Standardrotation verwirft alte Belege.
        self._sink = JsonlSink(self.records_path, max_bytes=0)
        self._sink.open()
        if self._output is not None:
            try:
                if self._output_transport == 'serial':
                    self._output.start(reference_port=getattr(self._reference_recorder, 'port', None),
                                       **({'clock_log': self._clock}
                                          if self._output_config.get('format') == '4ch' else {}))
                else:
                    self._output.start(**({'clock_log': self._clock}
                                          if self._output_config.get('format') == '4ch' else {}))
            except Exception as exc:
                self.stop(reason='start_failed')
                raise StartRefused(f'Ausgabe nicht gestartet: {exc}') from exc
        if self._reference_recorder is not None:
            try:
                self._reference_started = True  # Auch teilweise gestarteten Recorder bereinigen.
                self._reference_recorder.start()
            except Exception:
                self.stop(reason="start_failed")
                raise
        self._diagnostics.start(profile_sha256=self._meta['profile']['sha256'],
                                reference_sha256=profile.reference_frame['sha256'])
        try:
            self._write_session(ended=False)
        except Exception:
            self.stop(reason='start_failed')
            raise

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
            if (self._output_transport == 'serial' and not self._output_error_saved
                    and self._output.failed_event.is_set()):
                # Im Leserthread schreiben: kein Session-Dateirennen oder Lock/Join-Deadlock.
                self._write_session(ended=False)
                self._output_error_saved = True
            if got is None:
                status = self._owner.status()
                if status.get("stalled") or not status["running"]:
                    raise CameraLost(status.get("error") or "Kamera gestoppt")
                return None
            sequence, frame = got
            skipped = max(0, sequence - self._seen - 1)
            self._seen = sequence
            self._frames_skipped += skipped
            record = self._pipeline.process(frame, dropped_frames=skipped)
            if self._output_config.get('format') == '4ch' and record.status is ValueStatus.VALID:
                try:
                    checked_value_text(record.raw_text)
                except ValueError:
                    record = replace(record, status=ValueStatus.UNREADABLE, value=None,
                                     reject_reasons=('reserved_output_value',))
            # Testlauf sperrt die Freigabe vor Audit und jeder weiteren Ausgabe.
            gate_record = record
            suppressed = self._test_run is not None and record.status is ValueStatus.VALID
            if suppressed:
                record = replace(record, status=ValueStatus.UNREADABLE, value=None,
                                 reject_reasons=('testlauf_keine_freigabe', *record.reject_reasons))
            reconfiguration_suppressed = False
            if record.status is ValueStatus.VALID and getattr(
                self._reference_recorder, 'reconfiguration_enabled', False
            ):
                try:
                    # Frischen Versatz pruefen: ein Suspend darf nicht bis zur
                    # naechsten periodischen Auditprobe unbemerkt bleiben.
                    capture_ns = to_boottime_ns(record.capture_timestamp.to_dict(), {
                        'clock_offset_boottime_minus_monotonic_ns': self._clock.checked_offset_bounds(),
                    })
                    reconfiguration_suppressed = self._reference_recorder.is_reconfiguring(capture_ns)
                except ValueError:
                    # Ohne sicheren Zeitbezug keine Freigabe bei aktivem Werteplan.
                    reconfiguration_suppressed = True
                if reconfiguration_suppressed:
                    record = replace(record, status=ValueStatus.TRANSITION, value=None,
                                     reject_reasons=('geraet_umkonfiguriert', *record.reject_reasons))
            if record.reject_reasons and record.reject_reasons[0].startswith("tracking_lost:"):
                self._tracking_lost += 1
                self._tracking_lost_reasons[record.reject_reasons[0].split(":", 1)[1]] += 1
            track = getattr(self._pipeline.locator, "last_track", None)
            coarse = getattr(getattr(self._pipeline.locator, "_tracker", None), "last_coarse", None)
            if coarse is not None and coarse.used:
                self._tracking_coarse_retries += 1
                self._tracking_coarse_accepted += int(track is not None and track.quad is not None)
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
            if self._output is not None:
                if self._output_transport == 'serial':
                    self._output.submit(record)
                else:
                    self._output.publish(record)
            self._frames_read += 1
            if suppressed:
                self._testlauf_unterdrueckt += 1
            if reconfiguration_suppressed:
                self._reconfiguration_suppressed += 1
            self._by_status[record.status.value] = self._by_status.get(record.status.value, 0) + 1
            if record.reject_reasons and record.reject_reasons[0] == "anzeige_wechselt":
                self._display_changing += 1
            if self._reader_tolerance is not None and gate_record.status is ValueStatus.VALID:
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
                latest_guess = None
                if (isinstance(cells, list) and cells
                        and all(isinstance(c, dict) and isinstance(c.get("best"), str)
                                and isinstance(c.get("margin"), (int, float)) for c in cells)):
                    text = "".join(c["best"] for c in cells)
                    latest_guess = {
                        "text": text, "uncertain": [i for i, c in enumerate(cells) if c["margin"] < 0],
                        "reject_reason": diag.get("reject_reason"),
                    }
                    self._guesses[text] += 1
                if suppressed:
                    if latest_guess is None:
                        latest_guess = {'text': gate_record.raw_text, 'uncertain': [], 'reject_reason': None}
                    latest_guess['gate_status'] = gate_record.status.value
                self.latest_guess = latest_guess
            self.latest = record
            self.latest_monotonic = self._monotonic()
            self._rejection_window.observe(self.latest_monotonic, record.status, record.reject_reasons)
            if self._tracking_advice is not None:
                lost = bool(record.reject_reasons and record.reject_reasons[0].startswith('tracking_lost:'))
                try:
                    self._tracking_advice.observe(frame.image, lost=lost, now=self.latest_monotonic)
                except Exception as exc:  # noqa: BLE001 - Bedienhilfe darf keinen Lauf abbrechen
                    if not self._tracking_advice_warned:
                        _LOG.warning('Bewegungsdiagnose ausgefallen: %s', exc)
                        self._tracking_advice_warned = True
                    self._tracking_advice.failed(self.latest_monotonic)
            regions = self._observe_regions(record.frame_sequence)
            self._diagnostics.observe(frame, record, track, owner_sequence=sequence, mode=self.tracking['mode'],
                                      regions=regions)
            if self._monotonic() - self._last_clock >= self._config.clock_interval_s:
                self._clock.sample()
                self._last_clock = self._monotonic()
                self._write_session(ended=False)
            # Nur kleine Metadaten nach erfolgreichem Audit, keine Bildkopien.
            # Ein Anzeigeproblem darf weder Messung noch Ausgabe unterbrechen.
            try:
                now = self.latest_monotonic
                self.recent.observe(now, record.status.value, record.value)
                while self._processing_window and self._processing_window[0][0] <= now - 2.0:
                    self._processing_window.popleft()
                self._processing_window.append((now, skipped))
                self._frame_info = (now, self._build_frame_info(sequence, record, track, coarse))
            except Exception as exc:  # noqa: BLE001 - Messung hat Vorrang vor Anzeige
                self._frame_info = None
                if not self._frame_info_warned:
                    _LOG.warning('Laufanzeige ausgefallen: %s', exc)
                    self._frame_info_warned = True
            return record

    def _observe_regions(self, frame_sequence=None) -> list | None:
        """Residuen je Rahmenbereich ins Hinweisfenster; erst nach geschriebenem Record.

        Der Hinweis ist reine Bedienhilfe. Die Stilllegung (TB 2026-11-11) wirkt
        erst ab dem naechsten Bild und nur ueber FrameTracker.disable_region mit
        dessen harten Grenzen. Jeder Fehler hier laesst alle Bereiche aktiv
        (strengster Zustand) und bricht den Lauf nicht ab.
        """
        try:
            tracker = getattr(self._pipeline.locator, '_tracker', None)
            regions = getattr(tracker, 'last_regions', None)
            if not regions:
                return None
            if self._region_consistency is None:
                self._region_consistency = RegionConsistency(
                    tracker.sources, limit_px=tracker.config.max_inlier_residual_px)
            self._region_consistency.observe([region.get('res1') for region in regions],
                                             [region.get('v1') for region in regions])
            # Satz, mit dem DIESES Bild bewertet wurde; eine Stilllegung wirkt erst ab dem naechsten.
            disabled = frozenset(getattr(tracker, 'disabled', None) or ())
            self._frame_disabled = disabled
            try:
                self._maybe_disable_region(tracker, frame_sequence)
            except Exception as exc:  # noqa: BLE001 - ohne Stilllegung weitermessen
                self._region_disable_errors += 1
                if not self._region_disable_warned:
                    _LOG.warning('Stilllegung ausgefallen, alle Bereiche bleiben aktiv: %s', exc)
                    self._region_disable_warned = True
            if disabled:
                # images.jsonl: stillgelegte Bereiche additiv kennzeichnen.
                regions = [{**region, 'off': True} if index in disabled else region
                           for index, region in enumerate(regions)]
            return regions
        except Exception as exc:  # noqa: BLE001 - Bedienhilfe darf keinen Lauf abbrechen
            if not self._region_consistency_warned:
                _LOG.warning('Bereichsdiagnose ausgefallen: %s', exc)
                self._region_consistency_warned = True
            return None

    def _maybe_disable_region(self, tracker, frame_sequence) -> None:
        """Vorschlag des Fensters pruefen; Schutzprobe im Hintergrund; erst auditieren, dann stilllegen.

        Ablauf (TB 2026-11-11): Das Fenster schlaegt hoechstens einen Bereich vor.
        disable_refusal prueft Hoechstzahl und Reserve. Danach laeuft die
        Schutzprobe (FrameTracker.bias_probe, etwa eine Minute CPU) in einem
        eigenen Prozess mit nice 19, ohne den Messprozess zu bremsen. Erst wenn
        sie bestanden ist UND das Fenster denselben Bereich weiter vorschlaegt,
        wird das Ereignis geschrieben und der Bereich stillgelegt. Jede
        Unsicherheit laesst alle Bereiche aktiv; ein Ereignis wird je Satz und
        Bereich hoechstens einmal versucht.
        """
        window = self._region_consistency
        if not callable(getattr(tracker, 'disable_region', None)):
            return
        pending = self._region_probe
        if pending is not None:
            outcome = pending.poll()
            if outcome is None:
                return
            self._region_probe = None
            kind, value = outcome
            self._region_probe_cache[(pending.base, pending.index)] = value if kind == 'ok' else None
            if kind != 'ok':
                window.note_refused(pending.index, 'schutzprobe_fehler', frame_sequence, detail=value)
                return
        candidate = window.deactivation_candidate()
        if candidate is None:
            return
        index = candidate['index']
        refusal = tracker.disable_refusal(index)
        if refusal is not None:
            window.note_refused(index, refusal, frame_sequence)
            return
        base = frozenset(tracker.disabled)
        key = (base, index)
        if key not in self._region_probe_cache:
            self._region_probe = self._probe_runner(tracker, base, index)
            return
        probe = self._region_probe_cache[key]
        if probe is None:
            return  # Probe ist gescheitert; Grund steht schon in deactivation_refused
        if not probe.get('ok'):
            window.note_refused(index, 'schutzprobe_verletzt', frame_sequence, detail=probe)
            return
        if key in self._region_event_attempted:
            return  # Audit fuer genau diese Stilllegung schon einmal gescheitert: nie doppelt
        self._region_event_attempted.add(key)
        event = {'event': 'rahmenbereich_stillgelegt', 'frame_sequence': frame_sequence,
                 'utc': self._wall().isoformat(), **candidate,
                 'disabled_count': len(base) + 1, 'disabled_limit': tracker.disable_limit(), 'probe': probe}
        path = self._out_dir / 'tracking_events.jsonl'
        created = not path.exists()
        # Eine Zeile in einem Schreibaufruf; ohne geschriebenes Ereignis keine Stilllegung.
        line = (json.dumps(event, ensure_ascii=False) + '\n').encode('utf-8')
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            if os.write(descriptor, line) != len(line):
                raise OSError('Ereignis unvollstaendig geschrieben')
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if created:
            directory = os.open(self._out_dir, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        if not tracker.disable_region(index, probe):
            raise RuntimeError(f'Stilllegung von Bereich {index + 1} unerwartet verweigert')
        window.note_deactivated(event)
        _LOG.info('Rahmenbereich %d automatisch stillgelegt (%.0f %% unstimmig, Bild %s)',
                  index + 1, 100 * candidate['share'], frame_sequence)

    def _probe_runner(self, tracker, base, index):
        """Schutzprobe starten: echter Tracker im eigenen Prozess, sonst (Testattrappen) im Thread."""
        if callable(getattr(tracker, 'probe_payload', None)):
            return ProbeProcess(tracker.probe_payload(), base, index)
        return _ProbeThread(tracker, base, index)

    def _cancel_region_probe(self) -> None:
        pending, self._region_probe = self._region_probe, None
        if pending is not None:
            pending.cancel()

    def region_deactivations(self) -> list[dict]:
        """Stilllegungen dieses Laufs fuer Status und Werkbank; leer ohne Rahmenbereiche."""
        window = self._region_consistency
        return [] if window is None else window.deactivated()

    def _build_frame_info(self, sequence, record, track, coarse) -> dict:
        pipeline = self._pipeline
        tracker = getattr(pipeline.locator, '_tracker', None)
        regions = getattr(tracker, 'last_regions', None) or []
        # Satz, mit dem dieses Bild bewertet wurde (Review G3), nicht der danach gesetzte.
        disabled = self._frame_disabled
        read = pipeline.last_read
        diagnostics = read.diagnostics if read is not None and read.backend_id == 'dotmatrix' else {}
        cells = diagnostics.get('cells')
        if not (isinstance(cells, list) and cells
                and all(isinstance(c, dict) and isinstance(c.get('best'), str)
                        and isinstance(c.get('margin'), (int, float)) for c in cells)):
            cells = []
        trace = record.trace
        latency = (None if trace is None or trace.t_record_built_ns is None else
                   (trace.t_record_built_ns - trace.t_dequeue_ns) / 1e6)
        count = len(self._processing_window)
        skipped = sum(item[1] for item in self._processing_window)
        return {
            'rec': {'seq': sequence, 'status': record.status.value,
                    'text': record.raw_text, 'unit': record.unit,
                    'reasons': list(record.reject_reasons), 'age_s': 0.0},
            'track': {
                'quad': None if track is None or track.quad is None else
                        [[float(x), float(y)] for x, y in track.quad],
                'score': None if track is None else float(track.score),
                'shift_px': None if track is None else float(track.shift),
                'rotation_deg': None if track is None else float(track.rotation_deg),
                'reason': None if track is None else track.reason,
                'correcting': bool(coarse is not None and coarse.used),
                # TB: 'off' nur an stillgelegten Bereichen (additiv, wenige Bytes im X-Hud).
                'regions': [{'c': list(region['c']), 's': region['s'],
                             'peak': float(region['peak']), 'ok': bool(region['ok']),
                             **({'off': True} if index in disabled else {})}
                            for index, region in enumerate(regions)],
            },
            'cells': [{'i': i, 'best': cell['best'], 'margin': cell['margin'],
                       'uncertain': cell['margin'] < 0} for i, cell in enumerate(cells)],
            'proc': {'fps': count / 2.0, 'latency_ms': latency,
                     'skipped_recent': skipped / (count + skipped)},
        }

    def frame_info(self) -> dict | None:
        """Unabhaengiges Abbild des letzten auditierten Bilds, ohne Bilddaten."""
        snapshot = self._frame_info
        if snapshot is None:
            return None
        observed, data = snapshot
        info = deepcopy(data)
        # Nur die Ansicht altert; Datensatz und gespeichertes Abbild bleiben gleich.
        age = max(0.0, self._monotonic() - observed)
        info['rec']['age_s'] = age
        if age > 0.5:
            info['rec']['status'] = 'stale'
        return info

    def rejection_causes(self) -> dict:
        """Hauptursachen aller verarbeiteten Bilder der letzten zehn Sekunden."""
        return self._rejection_window.snapshot(self._monotonic())

    def tracking_hint(self) -> dict | None:
        """Bedienhilfe mit monotoner Verlustdauer; kein Freigabeentscheid."""
        return None if self._tracking_advice is None else self._tracking_advice.snapshot(self._monotonic())

    def region_hint(self) -> dict | None:
        """Bereich(e) dauerhaft unstimmig, letzte Auswertung; auch nach dem Stopp. Kein Freigabeentscheid."""
        window = self._region_consistency
        return None if window is None else window.snapshot()

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
    def mark(self, text: str) -> None:
        # Host-Eingang vor dem Warten auf einen laufenden Leseschritt festhalten.
        received = {'zeit': 'meldezeit_bediener', 't_boottime_ns': time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                    'received_at_utc': datetime.now(UTC).isoformat()}
        if not isinstance(text, str) or not text.strip() or len(text) > 200:
            raise ValueError('Ereignismarke braucht 1 bis 200 Zeichen')
        with self._stop_lock:
            if self._stopped or self._sink is None:
                raise ValueError('kein Lauf aktiv')
            entry = {**received, 'text': text, 'number': self._marks + 1}
            with (self._out_dir / 'marks.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
            self._marks += 1
            self.last_mark = entry
            number = self._marks
        # Der Rohbild-Snapshot braucht den Pipeline-/Stop-Lock nicht.
        self._diagnostics.mark(number)
        with self._stop_lock:
            if not self._stopped:
                self._write_session(ended=False)

    def diagnostics_status(self) -> dict:
        return self._diagnostics.status()

    @property
    def diagnose_kopie(self) -> bool:
        return self._diagnostics.copying

    def wait_diagnostics(self, timeout: float) -> bool:
        return self._diagnostics.wait(timeout)

    def _diagnostics_done(self) -> None:
        with self._stop_lock:
            # Nur Diagnose ergaenzen: Kamera/Clock koennen bereits zum Folgelauf gehoeren.
            data = json.loads(self.session_path.read_text(encoding='utf-8'))
            data['diagnostics'] = self.diagnostics_status()
            self._save_session(data)

    def timing_status(self) -> dict:
        end = self._ended_monotonic if self._ended_monotonic is not None else self._monotonic()
        return {'started_at_utc': self._meta.get('started_at_utc'),
                'elapsed_s': None if self._started_monotonic is None else end - self._started_monotonic,
                'ended_at_utc': self._ended_at_utc}

    def recent_snapshot(self) -> tuple[list[list], float]:
        if self._frozen_recent is None:
            return self.recent.snapshot(self._monotonic())
        entries, now_ms = self._frozen_recent
        return [list(entry) for entry in entries], now_ms

    def stop(self, reason: str = "bediener") -> dict:
        with self._stop_lock:
            if self._stopped:
                return self.summary
            if self.end_reason is None:
                self.end_reason = reason
            try:
                if self._reference_started:
                    self._reference_recorder.stop()
            except Exception as exc:  # noqa: BLE001 - Abschluss bleibt erhalten
                self._reference_error = str(exc)
            finally:
                self._clock.sample()
                try:
                    try:
                        if self._output is not None:
                            self._output.stop()
                    finally:
                        if self._sink is not None:
                            self._sink.close()
                finally:
                    try:
                        self._ended_monotonic = self._monotonic()
                        self._ended_at_utc = self._wall().isoformat()
                        self._frozen_recent = self.recent.snapshot(self._ended_monotonic)
                        self._write_session(ended=True)
                    finally:
                        if self._tracking_advice is not None:
                            self._tracking_advice.close()
                        self._cancel_region_probe()
                        self._stopped = True
                        self._diagnostics.stop(on_done=self._diagnostics_done)
                        if not self._diagnostics.copying and self.diagnostics_status()['write_errors']:
                            # Auch ein fehlgeschlagener Finisher-Start muss im Artefakt stehen.
                            data = json.loads(self.session_path.read_text(encoding='utf-8'))
                            data['diagnostics'] = self.diagnostics_status()
                            self._save_session(data)
            return self.summary

    def request_reference_stop(self) -> None:
        if self._reference_started:
            self._reference_recorder.request_stop()

    def reference_status(self) -> dict:
        if self._reference_recorder is None:
            return {"enabled": False, "reason": "vom Bediener deaktiviert"}
        status = self._reference_recorder.status()
        if self._reference_error is not None:
            status['error'] = self._reference_error
        return status

    def reference_live_status(self) -> dict:
        recorder = self._reference_recorder
        return {**self.reference_status(),
                'latest': None if recorder is None else recorder.latest_status(),
                'schedule_step': None if recorder is None else recorder.schedule_step_status()}

    def output_status(self) -> dict | None:
        """P4-3-Status unveraendert; Brueckenstatus mit Konfiguration."""
        if self._output is None:
            return None
        status = self._output.status()
        if self._output_transport == 'serial':
            return status
        note = BRIDGE_4CH_RELEASE_NOTE if self._output_config.get('format') == '4ch' else BRIDGE_RELEASE_NOTE
        return {**status, 'config': dict(self._output_config), 'acceptance': 'fehlt',
                **({'release_note': note} if self._bridge_acknowledged else {})}

    def unified_output_status(self) -> dict:
        """serial_ready: lokaler P4-3-Treiber bereit, kein GSVmulti-Empfang.

        failed: permanenter P4-3-Fehler ohne Wiederverbindung bis Laufende.
        audit_failed: Tx-Audit ausgefallen. last_ack belegt ausschliesslich
        lokale Treiberannahme, keinen GSVmulti-Empfang.
        """
        if self._output is None:
            return {'transport': 'off', 'state': 'off'}
        status = self.output_status()
        if self._output_transport != 'serial':
            return status
        return {
            'transport': 'serial',
            **self._output.delivery_status(),
            **({'tick': status['tick']} if 'tick' in status else {}),
            'config': dict(self._output_config),
            'error': status['first_error'],
            'release_block': None,
            'acceptance': 'fehlt',
            'release_note': SERIAL_4CH_RELEASE_NOTE if 'tick' in status else SERIAL_RELEASE_NOTE,
        }

    def _write_session(self, *, ended: bool) -> None:
        if self._stopped and not ended:
            return
        owner_status = self._owner.status()
        self.tracking_hint()  # Fertige Diagnose vor dem Zusammenfassen abholen, nie darauf warten.
        self.summary = {
            "marks": self._marks,
            "by_status": dict(self._by_status),
            "transition_display_changing": self._display_changing,
            "frames_read": self._frames_read,
            "tolerance_frames": self._tolerance_frames,
            "frames_skipped": self._frames_skipped,
            "frame_gaps": owner_status.get("gaps", 0) - self._frame_gaps_start,
            "frame_gaps_owner_total": owner_status.get("gaps", 0),
            "audit_errors": self._audit_errors,
            "tracking_lost": self._tracking_lost,
            "tracking_coarse_retries": self._tracking_coarse_retries,
            "tracking_coarse_accepted": self._tracking_coarse_accepted,
            "tracking_lost_reasons": dict(self._tracking_lost_reasons),
            "tracking_hints": (self._tracking_advice.summary() if self._tracking_advice is not None else
                               empty_summary()),
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
        if hasattr(self, "bridge_run_id"):
            data["run_id"] = self.bridge_run_id
        if self._output_transport == 'serial':
            data['output'] = {**self.output_status(), 'acceptance': 'fehlt', 'acknowledged_unaccepted': True}
        elif self._output is not None:
            data['output'] = {**self._output.metadata(), 'status': self.unified_output_status(),
                              'acceptance': 'fehlt',
                              'acknowledged_unaccepted': self._bridge_acknowledged,
                              'acknowledged_at_utc': self._bridge_acknowledged_at_utc,
                              'acknowledged_by': (getattr(self, 'bridge_acknowledged_by', None)
                                                  if self._bridge_acknowledged else None)}
        data["reference"] = self.reference_status()
        data['diagnostics'] = self.diagnostics_status()
        data['last_mark'] = self.last_mark
        data["clock_offset_boottime_minus_monotonic_ns"] = self._clock.to_session(ended=ended)
        data["summary"] = self.summary
        if self._region_consistency is not None:
            # Nur mit Rahmenbereich-Nachfuehrung; andere Modi behalten ihre bisherigen Bytes.
            self.summary['tracking_region_hint'] = {**self._region_consistency.summary(),
                                                    'deactivation_errors': self._region_disable_errors}
        if getattr(self._reference_recorder, 'reconfiguration_enabled', False):
            self.summary['reconfiguration_suppressed'] = self._reconfiguration_suppressed
        if self._test_run is not None:
            self.summary['testlauf_unterdrueckt'] = self._testlauf_unterdrueckt
            data["test_run"] = self._test_run
            data["guesses"] = {"frames": self._guesses.total(), "top": self._guesses.most_common(10)}
        if ended:
            data["ended_at_utc"] = self._ended_at_utc
        self._save_session(data)

    def _save_session(self, data: dict) -> None:
        tmp = self.session_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.session_path)
