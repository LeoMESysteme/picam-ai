import hashlib
import json
import threading

import cv2
import pytest
from dotmatrix_helpers import GRID, QUAD, embed, synthetic_reader

from dispread.camera_settings import CameraSettings
from dispread.detect.manual_roi import ManualRoiLocator
from dispread.frames import Frame
from dispread.live.clock import ClockLog
from dispread.live.session import AuditFailed, CameraLost, LiveConfig, LiveSession, StartRefused
from dispread.records import TimeBaseKind, Timestamp, ValueStatus
from dispread.session_profile import SessionProfile

_CAMERA = CameraSettings(model="logitech_streamcam", usb_id="046d:0893", size=(800, 400), fourcc="YUYV", fps=30,
                         controls={"focus_absolute": 48, "exposure_time_absolute": 156,
                                   "white_balance_temperature": 4600, "gain": 10})


@pytest.fixture(autouse=True)
def diagnostic_memory_available(monkeypatch):
    monkeypatch.setattr('dispread.live.diagnostics.read_mem_available', lambda: 2_000_000_000)


class FakeOwner:
    source_id = "fake"

    def __init__(self, images):
        self.items = [(i, img) for i, img in enumerate(images, start=1)]
        self.running = True

    def wait_newer(self, after, timeout):
        newer = [item for item in self.items if item[0] > after]
        if not newer:
            return None
        seq, image = newer[0]
        ts = Timestamp(value_ns=seq * 33_333_333, base=TimeBaseKind.V4L2_MONOTONIC)
        return seq, Frame(frame_sequence=seq, image=image, capture_timestamp=ts, source_id="fake")

    def status(self):
        return {"running": self.running, "error": None if self.running else "kein Bild", "frames": len(self.items),
                "gaps": 0, "source": {"device": "/dev/fake"}}


def _files(tmp_path, *, reference_ok=True):
    still = tmp_path / "still.png"
    cv2.imwrite(str(still), embed("+ 1.2345 "))
    digest = hashlib.sha256(still.read_bytes()).hexdigest() if reference_ok else "0" * 64
    profile = SessionProfile(
        schema_version=3, device_id="gsv-sensor-161a", session_id="live-test", quad=QUAD, target_size=(400, 160),
        grid=GRID, scaler_crop=None, min_source_dot_column_px=5.0, native_scale=1.0,
        min_native_dot_column_px=5.0, resolution_threshold_px=2.6, resolution_ok=True,
        confirmed_by="tester", confirmed_at_utc="2026-10-12T12:00:00+00:00", camera=_CAMERA,
        reference_frame={"path": str(still), "sha256": digest},
    )
    profile.save(tmp_path / "profile.json")
    calibration = tmp_path / "timing.json"
    calibration.write_text(json.dumps({
        "schema_version": 1, "camera_usb_id": "046d:0893", "guard_margin_ms": 325.9,
        "display_offset_ms": 89.6, "measured_at_utc": "2026-09-29T00:00:00+00:00", "sources": [],
    }))
    templates = tmp_path / "templates.json"
    templates.write_text("{}")
    return tmp_path / "profile.json", LiveConfig(templates=templates, templates_sha256="x", calibration=calibration)


def _session(tmp_path, images, *, reference_ok=True, **kw):
    profile_path, config = _files(tmp_path, reference_ok=reference_ok)
    offsets = iter(range(1000, 2000))
    return LiveSession(
        FakeOwner(images), profile_path, config, kw.pop("out_dir", tmp_path / "run"),
        reader_factory=lambda _p, _s, **kw: synthetic_reader(),
        locator_factory=lambda _ref, quad: ManualRoiLocator(tuple(tuple(p) for p in quad)),
        clock=ClockLog(measure=lambda: next(offsets), monotonic_ns=lambda: 0),
        **kw,
    )


def test_new_value_is_transition_then_valid_and_audited(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 "), embed("+ 1.2345 ")])
    session.start()
    first, second = session.step(), session.step()
    assert first.status is ValueStatus.TRANSITION and first.value is None
    assert second.status is ValueStatus.VALID and second.value == 1.2345
    assert second.capture_timestamp.base is TimeBaseKind.V4L2_MONOTONIC
    assert second.capture_timestamp.value_ns == 2 * 33_333_333
    assert second.frames_confirmed == 2
    assert second.confirmation_span_ns == 33_333_333
    summary = session.stop()
    lines = session.records_path.read_text().splitlines()
    assert len(lines) == 2 and summary["by_status"] == {"transition": 1, "valid": 1}
    assert [json.loads(line) for line in lines] == [first.to_dict(), second.to_dict()]
    data = json.loads(session.session_path.read_text())
    assert data["clock_offset_boottime_minus_monotonic_ns"]["start"] == 1000
    assert data["clock_offset_boottime_minus_monotonic_ns"]["end"] == 1001
    assert data["timing_calibration"]["applied"] is False
    assert data["timing_calibration"]["display_offset_ms"] == 89.6
    assert data["timing_calibration"]["guard_margin_ms"] == 325.9
    assert data["timing_calibration"]["sha256"] == hashlib.sha256((tmp_path / "timing.json").read_bytes()).hexdigest()
    assert data["release_notice"].startswith("Validiert nur:")
    assert data["reader_tolerance"] is None
    assert summary["tolerance_frames"] == 0


def test_unreadable_frame_is_rejected_not_guessed(tmp_path):
    blank = embed("+ 1.2345 ") * 0 + 200
    session = _session(tmp_path, [blank])
    session.start()
    record = session.step()
    assert record.status is ValueStatus.UNREADABLE and record.value is None and record.reject_reasons
    session.stop()
    assert json.loads(session.records_path.read_text()) == record.to_dict()


def test_start_refused_when_reference_still_changed(tmp_path):
    session = _session(tmp_path, [], reference_ok=False)
    with pytest.raises(StartRefused, match="Referenzbild"):
        session.start()


def test_start_refused_without_calibration(tmp_path):
    session = _session(tmp_path, [])
    (tmp_path / "timing.json").unlink()
    with pytest.raises(StartRefused, match="Timing-Kalibrierung"):
        session.start()


def test_camera_loss_ends_session_with_reason(tmp_path):
    session = _session(tmp_path, [])
    session.start()
    session._owner.running = False
    with pytest.raises(CameraLost, match="kein Bild"):
        session.step(timeout=0.01)
    session.stop()


def test_running_camera_without_new_frame_returns_none(tmp_path):
    session = _session(tmp_path, [])
    session.start()
    assert session.step(timeout=0.01) is None
    assert session.latest is None
    summary = session.stop()
    assert summary["frames_read"] == 0
    assert session.records_path.read_text() == ""


def test_run_records_camera_loss_and_stop_preserves_reason(tmp_path):
    session = _session(tmp_path, [])
    session.start()
    session._owner.running = False
    session.run(threading.Event())
    assert session.end_reason == "kamera: kein Bild"
    summary = session.stop("bediener")
    assert summary["end_reason"] == "kamera: kein Bild"
    assert summary["camera_error"] == "kein Bild"
    assert json.loads(session.session_path.read_text())["summary"] == summary


def test_run_obeys_already_set_stop_event(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 ")])
    session.start()
    stop = threading.Event()
    stop.set()
    session.run(stop)
    assert session.latest is None
    assert session.stop()["frames_read"] == 0


def test_periodic_clock_sample_keeps_end_unset_until_stop(tmp_path):
    now = [0.0]
    session = _session(tmp_path, [embed("+ 1.2345 ")], monotonic=lambda: now[0])
    session.start()
    now[0] = 60.0
    session.step()
    data = json.loads(session.session_path.read_text())
    offsets = data["clock_offset_boottime_minus_monotonic_ns"]
    assert offsets == {"start": 1000, "end": None, "samples": [[0, 1000], [0, 1001]]}
    assert data["summary"]["frames_read"] == 1
    session.stop()
    offsets = json.loads(session.session_path.read_text())["clock_offset_boottime_minus_monotonic_ns"]
    assert offsets["end"] == 1002
    assert len(offsets["samples"]) == 3


def test_skipped_frames_are_counted_and_written_to_trace(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 ")] * 4)
    session.start()
    session.step()
    session._owner.items = session._owner.items[3:]
    record = session.step()
    assert record.frame_sequence == 4
    assert record.trace.dropped_frames == 2
    assert session.latest is record
    summary = session.stop()
    assert summary["frames_read"] == 2
    assert summary["frames_skipped"] == 2


def test_start_ignores_camera_frames_from_before_start(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 ")] * 2)
    session._owner.latest = lambda: session._owner.items[0]
    session.start()
    assert session.step().frame_sequence == 2
    assert session.stop()["frames_skipped"] == 0


def test_start_refused_for_wrong_templates_checksum(tmp_path):
    profile_path, config = _files(tmp_path)
    session = LiveSession(FakeOwner([]), profile_path, config, tmp_path / "run")
    with pytest.raises(StartRefused, match="Vorlagen"):
        session.start()
    assert not session.session_path.exists()
    assert not session.records_path.exists()


def test_start_refused_for_calibration_of_another_camera(tmp_path):
    session = _session(tmp_path, [])
    calibration = tmp_path / "timing.json"
    data = json.loads(calibration.read_text())
    data["camera_usb_id"] = "wrong-camera"
    calibration.write_text(json.dumps(data))
    with pytest.raises(StartRefused, match="Timing-Kalibrierung gilt fuer"):
        session.start()
    assert not session.session_path.exists()


def _fail_audit(session, monkeypatch):
    def fail_rotation():
        raise OSError("Platte voll")

    monkeypatch.setattr(session._sink, "_rotate_if_needed", fail_rotation)


def test_audit_write_error_raises_and_is_counted(tmp_path, monkeypatch):
    session = _session(tmp_path, [embed("+ 1.2345 ")])
    session.start()
    _fail_audit(session, monkeypatch)
    try:
        with pytest.raises(RuntimeError, match="Audit.*Platte voll") as caught:
            session.step()
        assert type(caught.value).__name__ == "AuditFailed"
        assert session.latest is None
    finally:
        summary = session.stop()
    assert summary["audit_errors"] == 1


def test_run_returns_normally_on_audit_failure(tmp_path, monkeypatch):
    session = _session(tmp_path, [embed("+ 1.2345 ")] * 2)
    session.start()
    _fail_audit(session, monkeypatch)
    session._owner.running = False
    session.run(threading.Event())
    summary = session.stop("bediener")
    assert summary["end_reason"].startswith("audit: ")
    assert "Platte voll" in summary["end_reason"]
    assert summary["audit_errors"] == 1
    assert session._seen == 1


def test_run_returns_normally_on_reader_crash(tmp_path, monkeypatch):
    reader = synthetic_reader()

    def fail_read(*args, **kwargs):
        raise ValueError("Leser defekt")

    monkeypatch.setattr(reader, "read", fail_read)
    session = _session(tmp_path, [embed("+ 1.2345 ")])
    session._reader_factory = lambda _p, _s, **kw: reader
    session.start()
    try:
        session.run(threading.Event())
    finally:
        summary = session.stop("bediener")
    assert summary["end_reason"] == "fehler: ValueError: Leser defekt"
    assert session.records_path.read_text() == ""


def test_frame_gaps_count_only_this_session(tmp_path, monkeypatch):
    session = _session(tmp_path, [])
    status = session._owner.status()
    status["gaps"] = 7
    monkeypatch.setattr(session._owner, "status", lambda: dict(status))
    session.start()
    assert session.summary["frame_gaps"] == 0
    status["gaps"] = 10
    summary = session.stop()
    assert summary["frame_gaps"] == 3
    assert summary["frame_gaps_owner_total"] == 10


def test_stop_twice_preserves_end_sample_and_session_file(tmp_path):
    session = _session(tmp_path, [])
    session.start()
    first = session.stop("kamera")
    contents = session.session_path.read_bytes()
    mtime = session.session_path.stat().st_mtime_ns
    second = session.stop("bediener")
    assert second is first
    assert second["end_reason"] == "kamera"
    assert session.session_path.read_bytes() == contents
    assert session.session_path.stat().st_mtime_ns == mtime
    offsets = session._clock.to_session(ended=True)
    assert offsets["end"] == 1001
    assert len(offsets["samples"]) == 2


def test_step_before_start_raises_runtime_error(tmp_path):
    session = _session(tmp_path, [])
    with pytest.raises(RuntimeError, match=r"start\(\)"):
        session.step()


def test_latest_age_uses_monotonic_and_keeps_record_on_timeout(tmp_path):
    now = [10.0]
    session = _session(tmp_path, [embed("+ 1.2345 ")] * 2, monotonic=lambda: now[0])
    assert session.latest_age_s() is None
    session.start()
    session.step()
    now[0] = 10.25
    latest = session.step()
    assert latest.status is ValueStatus.VALID
    assert session.latest_monotonic == 10.25
    assert session.latest_age_s() == 0.0
    now[0] = 10.875
    assert session.step(timeout=0.01) is None
    assert session.latest_age_s() == 0.625
    assert session.latest is latest
    assert session.stop()["frames_read"] == 2


def test_skips_before_first_frame_are_counted(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 ")] * 4)
    session._owner.items = session._owner.items[3:]
    session.start()
    record = session.step()
    summary = session.stop()
    assert record.trace.dropped_frames == 3
    assert summary["frames_skipped"] == 3


def test_failed_start_never_leaves_open_audit_sink(tmp_path, monkeypatch):
    session = _session(tmp_path, [])

    def fail_write(*, ended):
        raise OSError("Metadaten nicht schreibbar")

    monkeypatch.setattr(session, "_write_session", fail_write)
    with pytest.raises(OSError, match="Metadaten"):
        session.start()
    assert session._sink is None or not session._sink.health().open


def test_tracking_quality_is_saved_for_successful_and_lost_tracks(tmp_path):
    from types import SimpleNamespace

    class Locator(ManualRoiLocator):
        last_track = None
        last_reason = "tracking_lost:test"

        def locate(self, frame):
            self.last_track = SimpleNamespace(score={1: 0.9, 2: 0.2, 3: 0.7}[frame.frame_sequence])
            return () if frame.frame_sequence == 2 else super().locate(frame)

    session = _session(tmp_path, [embed("+ 1.2345 ")] * 3)
    session._locator_factory = lambda ref, quad: Locator(quad)
    session.start()
    try:
        for _ in range(3):
            session.step()
    finally:
        summary = session.stop()
    assert summary["tracking_lost"] == 1
    assert summary["tracking_lost_reasons"] == {"test": 1}
    assert summary["track_score"] == {"min": 0.2, "median": 0.7, "max": 0.9, "n": 3}
    assert json.loads(session.session_path.read_text())["summary"] == summary


def test_locator_without_track_has_empty_quality_stats(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 ")])
    session.start()
    session.step()
    summary = session.stop()
    assert summary["tracking_lost"] == 0
    assert summary["track_score"] == {"min": None, "median": None, "max": None, "n": 0}


@pytest.mark.parametrize("exists", [True, False])
def test_session_copies_confirmation_from_profile_directory(tmp_path, exists):
    session = _session(tmp_path, [])
    confirmation = {
        "confirmed_by": "tester", "confirmed_at_utc": "2026-10-12T12:00:00+00:00",
        "unit": "mV/V", "format_id": "gsv2as_v1", "format_checked": True,
        "warning_acknowledged": False, "setup_overall": "OK",
    }
    if exists:
        (tmp_path / "confirmation.json").write_text(json.dumps(confirmation))
    session.start()
    started = json.loads(session.session_path.read_text())
    session.stop()
    ended = json.loads(session.session_path.read_text())
    for data in (started, ended):
        if exists:
            assert data["confirmation"] == confirmation
        else:
            assert "confirmation" not in data


def test_late_step_after_stop_leaves_records_latest_and_session_untouched(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 ")] * 2)
    session.start()
    session.step()
    session.stop("fertig")
    latest, summary = session.latest, dict(session.summary)
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns)
              for p in (session.session_path, session.records_path)}
    assert session.step() is None
    assert session.latest is latest
    assert session.end_reason == "fertig" and session.summary == summary
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before} == before


def test_periodic_session_write_after_stop_preserves_final_artifact(tmp_path):
    session = _session(tmp_path, [])
    session.start()
    session.stop("fertig")
    before = session.session_path.read_bytes(), session.session_path.stat().st_mtime_ns
    session._write_session(ended=False)
    assert (session.session_path.read_bytes(), session.session_path.stat().st_mtime_ns) == before
    assert session.summary["end_reason"] == "fertig"


@pytest.mark.parametrize("error", [CameraLost("spaet"), AuditFailed("spaet"), RuntimeError("spaet")])
def test_run_preserves_stop_reason_when_pending_step_raises(tmp_path, monkeypatch, error):
    session = _session(tmp_path, [])
    session.start()

    def step():
        session.stop("fertig")
        raise error

    monkeypatch.setattr(session, "step", step)
    session.run(threading.Event())
    assert session.end_reason == "fertig"
    assert json.loads(session.session_path.read_text())["summary"]["end_reason"] == "fertig"


def test_step_waiting_for_frame_observes_completed_stop(tmp_path, monkeypatch):
    session = _session(tmp_path, [embed("+ 1.2345 ")])
    session.start()
    wait_newer = session._owner.wait_newer

    def wait(after, timeout):
        session.stop("fertig")
        return wait_newer(after, timeout)

    monkeypatch.setattr(session._owner, "wait_newer", wait)
    assert session.step() is None
    assert session.latest is None
    assert session.summary["frames_read"] == 0
    assert session.records_path.read_text() == ""


def test_track_scores_keep_bounded_memory_and_all_time_extrema(tmp_path, monkeypatch):
    from dataclasses import replace
    from types import SimpleNamespace

    image = embed("+ 1.2345 ")
    session = _session(tmp_path, [image], monotonic=lambda: 0.0)
    session.start()
    template = session.step()

    def process(frame, **kwargs):
        session._pipeline.locator.last_track = SimpleNamespace(score=0.1 if frame.frame_sequence == 2 else 0.9)
        return replace(template, frame_sequence=frame.frame_sequence, capture_timestamp=frame.capture_timestamp)

    monkeypatch.setattr(session._pipeline, "process", process)
    try:
        for sequence in range(2, 10_003):
            session._owner.items = [(sequence, image)]
            session.step()
        assert len(session._track_scores) <= 10_000
    finally:
        summary = session.stop()
    assert summary["track_score"] == {"min": 0.1, "median": 0.9, "max": 0.9, "n": 10_001}


@pytest.mark.parametrize("test_mode", [False, True])
def test_guesses_are_diagnostic_only_and_cleared_when_not_located(tmp_path, monkeypatch, test_mode):
    from dataclasses import replace

    marker = {"testlauf": True} if test_mode else None
    session = _session(tmp_path, [embed("+ 1.2345 ")] * 3, test_run=marker)
    session.start()
    base = session._pipeline.reader.read(embed("+ 1.2345 ")[:160, :400], session._pipeline.config.layout)
    read = replace(base, raw_text=None, value=None, diagnostics={
        "cells": [{"best": "9", "margin": -1}, {"best": "8", "margin": 1}],
        "reject_reason": "zelle_unbekannt",
    })
    monkeypatch.setattr(session._pipeline.reader, "read", lambda *args: read)
    records = [session.step(), session.step()]
    assert session._pipeline.last_read is read
    assert session.latest_guess == ({"text": "98", "uncertain": [0], "reject_reason": "zelle_unbekannt"}
                                    if test_mode else None)
    monkeypatch.setattr(session._pipeline.locator, "locate", lambda *args: [])
    records.append(session.step())
    assert session._pipeline.last_read is None
    assert session.latest_guess is None
    session.stop()
    contents = session.records_path.read_text()
    assert [json.loads(line) for line in contents.splitlines()] == [r.to_dict() for r in records]
    assert all(r.value is None and r.raw_text is None and r.status is ValueStatus.UNREADABLE for r in records)
    assert '"98"' not in contents and '"guess"' not in contents
    meta = json.loads(session.session_path.read_text())
    if test_mode:
        assert meta["test_run"] == marker
        assert meta["guesses"] == {"frames": 2, "top": [["98", 2]]}
    else:
        assert "guesses" not in meta


@pytest.mark.parametrize("diagnostics,backend", [({}, "dotmatrix"),
    ({"cells": [{"best": "9", "margin": -1}]}, "other"),
    ({"cells": [{"best": "9"}]}, "dotmatrix"),
])
def test_test_run_ignores_missing_or_non_dotmatrix_diagnostics(tmp_path, monkeypatch, diagnostics, backend):
    from dataclasses import replace

    session = _session(tmp_path, [embed("+ 1.2345 ")], test_run={"testlauf": True})
    session.start()
    reader = session._pipeline.reader
    read = reader.read(embed("+ 1.2345 ")[:160, :400], session._pipeline.config.layout)
    monkeypatch.setattr(reader, "read", lambda *args: replace(read, diagnostics=diagnostics, backend_id=backend))
    session.step()
    session.stop()
    assert session.latest_guess is None
    assert json.loads(session.session_path.read_text())["guesses"] == {"frames": 0, "top": []}


@pytest.mark.parametrize('factor,tolerance', [
    (1.44, None), (1.0, {'factor': 1.44}), (1.2, {'factor': 1.44}),
])
def test_reader_factor_must_match_recorded_tolerance(tmp_path, factor, tolerance):
    # Eine Lockerung ohne passende Markierung in session.json darf es nicht geben.
    with pytest.raises(ValueError, match='reader_tolerance'):
        _session(tmp_path, [embed('+ 1.2345 ')], reader_d_max_factor=factor, reader_tolerance=tolerance)


@pytest.mark.parametrize('needs_tolerance', [False, True])
def test_tolerance_counts_only_valid_frames_above_template_threshold(tmp_path, needs_tolerance):
    from dataclasses import replace

    from dotmatrix_helpers import LAYOUT, render

    from dispread.ocr.dotmatrix import DotMatrixReader

    base = synthetic_reader()
    maximum = max(c['d_best'] for c in base.read(render('+ 1.2345 '), LAYOUT).diagnostics['cells'])
    templates = replace(base._t, d_max=maximum / 1.4) if needs_tolerance else base._t
    tolerance = {'factor': 1.44, 'd_max_templates': templates.d_max, 'd_max_run': templates.d_max * 1.44,
                 'max_d_best': maximum, 'hinweis': 'nicht validiert'}
    session = _session(tmp_path, [embed('+ 1.2345 ')] * 2,
                       reader_d_max_factor=1.44, reader_tolerance=tolerance)
    factors = []

    def factory(path, sha, *, d_max_factor):
        factors.append(d_max_factor)
        return DotMatrixReader(templates, d_max_factor=d_max_factor)

    session._reader_factory = factory
    session.start()
    first, second = session.step(), session.step()
    assert first.status is ValueStatus.TRANSITION
    assert second.status is ValueStatus.VALID
    summary = session.stop()
    assert factors == [1.44]
    assert summary['tolerance_frames'] == int(needs_tolerance)
    data = json.loads(session.session_path.read_text())
    assert data['reader_tolerance'] == tolerance
    assert [json.loads(line) for line in session.records_path.read_text().splitlines()] == [
        first.to_dict(), second.to_dict()]


def test_session_never_switches_opencv_threads(tmp_path, monkeypatch):
    # Umschalten waehrend laufender Kamera-Threads kann OpenCV abstuerzen
    # lassen; die Grenze setzt `dispread serve` einmal beim Start.
    calls = []
    monkeypatch.setattr(cv2, "setNumThreads", calls.append)
    session = _session(tmp_path, [])
    session.start()
    session.stop()
    assert calls == []


def test_serve_limits_opencv_threads_before_any_camera_thread():
    import inspect

    from dispread.workbench.server import serve

    source = inspect.getsource(serve)
    assert "cv2.setNumThreads(LIVE_CV_THREADS)" in source
    assert source.index("cv2.setNumThreads(LIVE_CV_THREADS)") < source.index("CameraOwner(")


def test_reference_audit_leaves_records_byte_identical(tmp_path, monkeypatch):
    from test_live_reference import FakePort

    from dispread.live.reference import ReferenceRecorder

    # Laufzeitdiagnosen auf dieselben Werte festlegen; keine Referenz gelangt ins Gate.
    monkeypatch.setattr('time.monotonic_ns', lambda: 123456789)
    monkeypatch.setattr('time.clock_gettime_ns', lambda _kind: 123456789)
    images = [embed('+ 1.2345 '), embed('+ 1.2345 ')]
    plain = _session(tmp_path, images)
    plain.start()
    plain.step()
    plain.step()
    plain.stop()
    expected = plain.records_path.read_bytes()
    port = FakePort([b'partial\n', b'+09.8765 mV/V\n'])
    recorder = ReferenceRecorder(lambda: port, tmp_path / 'with-reference' / 'reference.jsonl')
    recorded = _session(tmp_path, images, reference_recorder=recorder)
    recorded._out_dir = tmp_path / 'with-reference'
    recorded.session_path = recorded._out_dir / 'session.json'
    recorded.records_path = recorded._out_dir / 'records.jsonl'
    recorded.start()
    recorded.step()
    recorded.step()
    recorded.stop()
    assert recorded.records_path.read_bytes() == expected
    meta = json.loads(recorded.session_path.read_text())
    assert meta['reference']['enabled'] and meta['reference']['lines'] == 1
    assert port.closed and not port.writes


def test_diagnostics_and_marks_leave_records_byte_identical(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from dispread.live import diagnostics

    monkeypatch.setattr('time.monotonic_ns', lambda: 123456789)
    monkeypatch.setattr('time.clock_gettime_ns', lambda _kind: 123456789)
    monkeypatch.setattr(diagnostics.shutil, 'disk_usage', lambda root: SimpleNamespace(free=2_000_000_000))
    images = [embed('+ 1.2345 '), embed('+ 1.2345 ')]
    plain = _session(tmp_path, images)
    plain.start()
    plain.step()
    plain.step()
    plain.stop()
    expected = plain.records_path.read_bytes()
    recorded = _session(tmp_path, images, diagnostics=True, diagnostic_staging_root=tmp_path,
                        out_dir=tmp_path / "with-diagnostics", monotonic=lambda: 0.0)
    recorded.start()
    recorded.mark('vor erstem Bild')
    recorded.step()
    recorded.mark('Abdeckung')
    recorded.mark('Ende')
    recorded.step()
    assert recorded.stop()['marks'] == 3
    assert recorded._diagnostics.wait(3)
    assert recorded.records_path.read_bytes() == expected
    marks = [json.loads(line) for line in (recorded._out_dir / 'marks.jsonl').read_text().splitlines()]
    assert [m['text'] for m in marks] == ['vor erstem Bild', 'Abdeckung', 'Ende']
    assert all(m['zeit'] == 'meldezeit_bediener' and m['t_boottime_ns'] == 123456789
               and m['received_at_utc'].endswith('+00:00') for m in marks)
    meta = json.loads(recorded.session_path.read_text())
    assert meta['diagnostics']['saved'] == 1 and meta['diagnostics']['copied']
    assert meta['diagnostics']['dropped_mark_rate'] == 2
    assert meta['summary']['marks'] == 3 and recorded.last_mark == marks[-1]
    entries = [json.loads(line) for line in (recorded._out_dir / 'diagnose' / 'images.jsonl').read_text().splitlines()]
    assert [e['mark'] for e in entries] == [1]
    assert all(e['trigger'] == 'operator_mark' for e in entries)


@pytest.mark.parametrize('text', ['', ' ', 'x' * 201, None, 42])
def test_mark_rejects_invalid_text(tmp_path, text):
    session = _session(tmp_path, [])
    session.start()
    with pytest.raises(ValueError, match='1 bis 200'):
        session.mark(text)
    assert session.stop()['marks'] == 0


def test_marks_without_diagnostics_and_refusal_after_stop(tmp_path):
    session = _session(tmp_path, [])
    session.start()
    session.mark('x' * 200)
    assert session.stop()['marks'] == 1
    assert not json.loads(session.session_path.read_text())['diagnostics']['enabled']
    with pytest.raises(ValueError, match='kein Lauf'):
        session.mark('zu spaet')


def test_diagnostic_copy_does_not_hold_session_stop_and_updates_final_metadata(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from dispread.live import diagnostics

    monkeypatch.setattr(diagnostics.shutil, 'disk_usage', lambda root: SimpleNamespace(free=2_000_000_000))
    entered, release = threading.Event(), threading.Event()
    copy = diagnostics.shutil.copyfile

    def slow(src, dst):
        entered.set()
        assert release.wait(3)
        return copy(src, dst)

    monkeypatch.setattr(diagnostics.shutil, 'copyfile', slow)
    session = _session(tmp_path, [embed('+ 1.2345 ')], diagnostics=True, diagnostic_staging_root=tmp_path)
    session.start()
    session.step()
    session.mark('Kopie')
    try:
        session.stop()
        assert entered.wait(1)
        assert session.diagnose_kopie
        meta = json.loads(session.session_path.read_text())
        assert meta['ended_at_utc'] and not meta['diagnostics']['copied']
        assert session.step() is None
        # Die Kamera kann vor Kopierende schon fuer den naechsten Lauf arbeiten.
        monkeypatch.setattr(session._owner, 'status', lambda: {'gaps': 999, 'error': 'neuer Lauf'})
    finally:
        release.set()
    assert session._diagnostics.wait(3)
    final = json.loads(session.session_path.read_text())
    assert final['ended_at_utc'] == meta['ended_at_utc']
    assert final['summary'] == meta['summary']
    assert final['diagnostics']['copied'] and not session.diagnose_kopie


def test_restore_timeout_is_saved_in_session_json(tmp_path, monkeypatch):
    from test_live_reference import RegisterPort, _wait_for

    from dispread.live.reference import RESTORE_ERROR, ReferenceRecorder

    release = threading.Event()
    port = RegisterPort()
    recorder = None
    ticks = [0.0]
    def sleep(seconds):
        ticks[0] += seconds
        if recorder.status()['restoring']:
            release.wait(1)
    monkeypatch.setattr('dispread.gsv2as_serial._sleep', sleep)
    monkeypatch.setattr('dispread.live.reference.JOIN_TIMEOUT_S', 0.05)
    point = {'register': {'norm': {'daten': [80, 27, 228]}, 'dpoint': {'daten': [1]}}}
    recorder = ReferenceRecorder(lambda: port, tmp_path / 'run' / 'reference.jsonl',
                                 norm_schedule=[(2, 20)], restore_point=point,
                                 monotonic=lambda: ticks[0])
    session = _session(tmp_path, [], reference_recorder=recorder)
    session.start()
    _wait_for(lambda: any(b[0] == 16 for b in port.writes))
    try:
        session.stop()
        meta = json.loads(session.session_path.read_text())
        assert meta['reference']['error'] == RESTORE_ERROR
        assert not meta['reference']['restoring']
        assert port.closed
    finally:
        release.set()
        recorder._reader.join(1)
        recorder._writer.join(1)


def test_reference_stop_failure_still_closes_sink_and_finalizes_metadata(tmp_path, monkeypatch):
    class Recorder:
        def start(self):
            pass
        def stop(self):
            raise OSError('recorder stop failed')
        def status(self):
            return {'enabled': True}
    session = _session(tmp_path, [], reference_recorder=Recorder())
    session.start()
    closed = []
    original_close = session._sink.close
    def close():
        original_close()
        closed.append(True)
    monkeypatch.setattr(session._sink, 'close', close)
    session.stop()
    assert closed == [True]
    meta = json.loads(session.session_path.read_text())
    assert meta['reference']['error'] == 'recorder stop failed'
    assert meta['ended_at_utc']
    assert meta['summary']['end_reason'] == 'bediener'


def _region_session(tmp_path, images=None, **kwargs):
    from frame_tracking_helpers import reference_scene, tracking_block

    image, quad = reference_scene()
    path, config = _files(tmp_path)
    still = tmp_path / "still.png"
    cv2.imwrite(str(still), image)
    data = json.loads(path.read_text())
    data["quad"] = quad
    data["camera"]["size"] = list(image.shape[1::-1])
    data["reference_frame"]["sha256"] = hashlib.sha256(still.read_bytes()).hexdigest()
    data["live_tracking"] = tracking_block(image, quad, still)
    path.write_text(json.dumps(data))
    session = LiveSession(
        FakeOwner(images if images is not None else [image]), path, config, tmp_path / "run",
        reader_factory=lambda *args, **kw: synthetic_reader(), **kwargs,
    )
    return session, data


def test_region_run_uses_confirmed_locator_and_marks_artifact(tmp_path):
    from dispread.live.tracking import ConfirmedRegionLocator

    session, data = _region_session(tmp_path)
    session.start()
    try:
        assert isinstance(session._pipeline.locator, ConfirmedRegionLocator)
        assert session._pipeline.locator._tracker.proposal.to_dict() == data["live_tracking"]["proposal"]
        assert session.tracking == {"mode": "rahmenbereiche", "version": 1,
                                    "regions": len(data["live_tracking"]["proposal"]["regions"]), "auswahl": "automatisch"}
    finally:
        session.stop()
    artifact = json.loads(session.session_path.read_text())
    assert artifact["tracking"] == session.tracking
    assert artifact["summary"]["tracking_lost_reasons"] == {}


@pytest.mark.parametrize("tamper", ["frame_sha256", "config", "version", "method", "proposal_config", "gray_hash"])
def test_region_run_refuses_wrong_reference_config_or_version(tmp_path, tamper):
    session, data = _region_session(tmp_path)
    block = data["live_tracking"]
    if tamper == "config":
        block["config"]["min_peak"] = 0.99
    elif tamper == "proposal_config":
        block["proposal"]["config"]["min_peak"] = 0.99
    elif tamper == "gray_hash":
        block["proposal"]["reference_sha256"] = "0" * 64
    else:
        block[tamper] = "wrong"
    session._profile_path.write_text(json.dumps(data))
    with pytest.raises(StartRefused, match="neu einrichten"):
        session.start()
    assert not session.records_path.exists()


def test_region_run_compares_against_current_defaults(tmp_path, monkeypatch):
    from dataclasses import replace

    from dispread.live import session as session_module
    from dispread.live.frame_tracking import FrameTrackingConfig

    session, _ = _region_session(tmp_path)
    monkeypatch.setattr(session_module, "FrameTrackingConfig", lambda: replace(FrameTrackingConfig(), min_peak=0.99))
    with pytest.raises(StartRefused, match="neu einrichten"):
        session.start()


def test_confirmed_profile_honours_injected_two_argument_locator_factory(tmp_path):
    calls = []

    def locator(reference, quad):
        calls.append((reference, quad))
        return ManualRoiLocator(quad)

    session, data = _region_session(tmp_path, locator_factory=locator)
    session.start()
    try:
        assert len(calls) == 1 and calls[0][1] == data["quad"]
        assert isinstance(session._pipeline.locator, ManualRoiLocator)
        assert session.tracking == {"mode": "injiziert", "profile_mode": "rahmenbereiche",
                                    "version": None, "regions": None}
        assert json.loads(session.session_path.read_text())["tracking"] == session.tracking
    finally:
        session.stop()


def test_old_profile_uses_ecc_and_marks_old_mode(tmp_path):
    from dispread.live.tracking import TrackedQuadLocator

    path, config = _files(tmp_path)
    session = LiveSession(FakeOwner([]), path, config, tmp_path / "run",
                          reader_factory=lambda *args, **kw: synthetic_reader())
    session.start()
    try:
        assert isinstance(session._pipeline.locator, TrackedQuadLocator)
    finally:
        session.stop()
    assert json.loads(session.session_path.read_text())["tracking"] == {
        "mode": "ecc_alt", "version": None, "regions": None,
    }


def test_visible_frame_with_hidden_digits_never_releases_value(tmp_path):
    import numpy as np
    from frame_tracking_helpers import reference_scene

    from dispread.ocr import ReadResult

    reference, _ = reference_scene()
    session, data = _region_session(tmp_path)
    hidden = reference.copy()
    cv2.fillConvexPoly(hidden, np.rint(data["live_tracking"]["proposal"]["character_zone"]).astype(np.int32),
                       (120, 120, 120))
    session._owner = FakeOwner([hidden] * 3)
    reads = []
    unreadable = ReadResult(
        raw_text="", value=None, glyphs=(), sign_detected=False, sign_region_readable=False,
        decimal_point_detected=False, decimal_point_index=None, unit_text=None, status_flags=frozenset(),
        backend_id="dotmatrix", backend_version="test",
    )

    class Reader:
        backend_id = "dotmatrix"

        def read(self, crop, layout):
            reads.append(crop.copy())
            return unreadable

    session._reader_factory = lambda *args, **kwargs: Reader()
    session.start()
    try:
        for _ in range(3):
            record = session.step()
            assert session._pipeline.locator.last_track.quad is not None
            assert record.status is not ValueStatus.VALID and record.value is None
    finally:
        summary = session.stop()
    assert len(reads) == 3
    assert summary["tracking_lost"] == 0
    assert summary["tracking_lost_reasons"] == {}


def test_region_tracking_counts_each_loss_reason(tmp_path):
    from frame_tracking_helpers import reference_scene

    image, _ = reference_scene()
    session, _ = _region_session(tmp_path, images=[image * 0, image[:100, :100], image * 0])
    session.start()
    try:
        reasons = [session.step().reject_reasons[0].split(":", 1)[1] for _ in range(3)]
    finally:
        summary = session.stop()
    assert reasons == ["zu_wenig_rahmenmerkmale", "bildgroesse_abweichend", "zu_wenig_rahmenmerkmale"]
    assert summary["tracking_lost"] == 3
    assert summary["tracking_lost_reasons"] == {"zu_wenig_rahmenmerkmale": 2, "bildgroesse_abweichend": 1}


@pytest.mark.parametrize("value", [15.0, True])
@pytest.mark.parametrize("config_path", ["block", "proposal"])
def test_region_run_refuses_hand_edited_config_types(tmp_path, value, config_path):
    session, data = _region_session(tmp_path)
    key = "patch_size" if type(value) is float else "interpolation_guard_px"
    block = data["live_tracking"]
    config = block["config"] if config_path == "block" else block["proposal"]["config"]
    config[key] = value
    session._profile_path.write_text(json.dumps(data))
    with pytest.raises(StartRefused, match="neu einrichten"):
        session.start()
    assert not session.records_path.exists()


@pytest.mark.parametrize("block", [[], "rahmenbereiche", 1, True])
def test_region_run_refuses_non_dict_tracking_block(tmp_path, block):
    session, data = _region_session(tmp_path)
    data["live_tracking"] = block
    session._profile_path.write_text(json.dumps(data))
    with pytest.raises(StartRefused, match="neu einrichten"):
        session.start()
    assert not session.records_path.exists()


def test_region_run_reports_reconfigure_instruction_once(tmp_path):
    session, data = _region_session(tmp_path)
    data["live_tracking"]["proposal"]["ok"] = False
    session._profile_path.write_text(json.dumps(data))
    with pytest.raises(StartRefused) as error:
        session.start()
    assert str(error.value) == "Rahmenbereiche ungueltig: Rahmenvorschlag ungeeignet - neu einrichten"


def test_region_run_guards_injected_non_dict_profile_block(tmp_path, monkeypatch):
    session, _ = _region_session(tmp_path)
    profile = SessionProfile.load(session._profile_path)
    from dataclasses import replace

    monkeypatch.setattr(SessionProfile, "load", lambda path: replace(profile, live_tracking=[]))
    with pytest.raises(StartRefused) as error:
        session.start()
    assert str(error.value) == "Rahmenbereiche oder Pruefversion passen nicht zum Profil - neu einrichten"


@pytest.mark.parametrize('resource,reason', [('space', 'Platz'), ('memory', 'MemAvailable')])
def test_insufficient_diagnostic_ram_still_starts_and_records_reason(tmp_path, monkeypatch, resource, reason):
    from types import SimpleNamespace

    from dispread.live import diagnostics

    monkeypatch.setattr(diagnostics.shutil, 'disk_usage', lambda root: SimpleNamespace(
        free=100 if resource == 'space' else 2_000_000_000))
    monkeypatch.setattr(diagnostics, 'read_mem_available', lambda: 1_099_999_999)
    session = _session(tmp_path, [embed('+ 1.2345 ')], diagnostics=True, diagnostic_staging_root=tmp_path)
    session.start()
    assert session.step() is not None
    session.stop()
    status = json.loads(session.session_path.read_text())['diagnostics']
    assert status == session.diagnostics_status()
    assert not status['enabled'] and reason in status['reason']
    assert status['saved'] == 0 and status['staging'] is None


def test_mark_snapshot_does_not_hold_pipeline_stop_lock(tmp_path, monkeypatch):
    from dispread.live import diagnostics

    monkeypatch.setattr(diagnostics, 'read_mem_available', lambda: 2_000_000_000, raising=False)
    session = _session(tmp_path, [embed('+ 1.2345 ')], diagnostics=True, diagnostic_staging_root=tmp_path)
    session.start()
    session.step()
    entered, release = threading.Event(), threading.Event()
    original = session._diagnostics._enqueue
    def delayed_snapshot(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original(*args, **kwargs)
    monkeypatch.setattr(session._diagnostics, '_enqueue', delayed_snapshot)
    thread = threading.Thread(target=session.mark, args=('Marke',))
    thread.start()
    try:
        assert entered.wait(1)
        acquired = session._stop_lock.acquire(timeout=0.1)
        if acquired:
            session._stop_lock.release()
        assert acquired, 'mark snapshot held the pipeline stop lock'
    finally:
        release.set()
        thread.join(3)
        session.stop()
        assert session._diagnostics.wait(3)


def test_loss_and_periodic_diagnostics_leave_records_byte_identical(tmp_path, monkeypatch):
    from dispread.live import diagnostics

    monkeypatch.setattr('time.monotonic_ns', lambda: 123456789)
    monkeypatch.setattr('time.clock_gettime_ns', lambda _kind: 123456789)
    monkeypatch.setattr(diagnostics, 'read_mem_available', lambda: 2_000_000_000, raising=False)
    monkeypatch.setattr(diagnostics, 'PERIODIC_INTERVAL_S', 0.25)
    images = [embed('+ 1.2345 ')] * 5
    outputs = []
    for enabled in (False, True):
        now = [0.0]
        session = _session(tmp_path, images, diagnostics=enabled, diagnostic_staging_root=tmp_path,
                           monotonic=lambda now=now: now[0], out_dir=tmp_path / str(enabled))
        session.start()
        locator = session._pipeline.locator
        original_locate = locator.locate
        def locate(frame, original=original_locate, locator=locator):
            locator.last_reason = 'tracking_lost:abdeckung' if frame.frame_sequence in (2, 3) else None
            return () if locator.last_reason else original(frame)
        monkeypatch.setattr(locator, 'locate', locate)
        for step in range(5):
            now[0] = (step + 1) * 0.5
            session.step()
        session.stop()
        assert session._diagnostics.wait(3)
        outputs.append(session.records_path.read_bytes())
    assert outputs[0] == outputs[1]
    entries = [json.loads(line) for line in (session._out_dir / 'diagnose' / 'images.jsonl').read_text().splitlines()]
    assert [e['trigger'] for e in entries] == ['periodic', 'tracking_loss', 'tracking_recovered', 'periodic']
    assert [e['frame_sequence'] for e in entries] == [1, 2, 4, 5]


def test_memory_drops_are_saved_in_session_diagnostics(tmp_path, monkeypatch):
    from dispread.live import diagnostics

    available, now = [2_000_000_000], [0.0]
    monkeypatch.setattr(diagnostics, 'read_mem_available', lambda: available[0])
    session = _session(tmp_path, [embed('+ 1.2345 ')], diagnostics=True,
                       diagnostic_staging_root=tmp_path, monotonic=lambda: now[0])
    session.start()
    session.step()
    available[0], now[0] = 499_999_999, 1.0
    session.mark('RAM knapp')
    session.stop()
    assert session.wait_diagnostics(3)
    status = json.loads(session.session_path.read_text())['diagnostics']
    assert status['saved'] == 0 and status['dropped_memory'] == 1
    assert status == session.diagnostics_status()


def test_finisher_start_error_is_saved_and_session_stop_still_succeeds(tmp_path, monkeypatch):
    session = _session(tmp_path, [embed('+ 1.2345 ')], diagnostics=True, diagnostic_staging_root=tmp_path)
    session.start()
    session.step()
    session.mark('Threadmangel')
    start = threading.Thread.start
    def fail_copy(thread):
        if thread.name == 'diagnose-copy':
            raise RuntimeError('kein Thread verfuegbar')
        return start(thread)
    monkeypatch.setattr(threading.Thread, 'start', fail_copy)
    assert session.stop()['marks'] == 1
    session._diagnostics._worker.join(3)
    assert not session.diagnose_kopie
    status = json.loads(session.session_path.read_text())['diagnostics']
    assert status['first_error'] == 'RuntimeError: kein Thread verfuegbar'
    assert not status['copied'] and session._diagnostics.staging.exists()


@pytest.mark.parametrize('selection', ['automatisch', 'manuell'])
def test_region_selection_origin_is_in_session_artifact(tmp_path, selection):
    session, data = _region_session(tmp_path)
    data['live_tracking']['auswahl'] = selection
    data['live_tracking']['edits'] = []
    session._profile_path.write_text(json.dumps(data))
    session.start()
    session.stop()
    artifact = json.loads(session.session_path.read_text())
    assert artifact['tracking']['auswahl'] == selection


def test_session_counts_every_processed_frame_in_live_causes(tmp_path):
    session = _session(tmp_path, [embed('+ 1.2345 '), embed('+ 1.2345 ')])
    session.start()
    try:
        session.step()
        session.step()
        causes = session.rejection_causes()
        assert causes['frames'] == 2
        assert causes['causes'] == [{'reason': 'awaiting_confirmation', 'count': 1, 'fraction': 0.5}]
    finally:
        session.stop()
