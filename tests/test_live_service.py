import time

import pytest

from dispread.focus_sweep import FocusMeasurements
from dispread.live.service import LiveError, LiveService


class FakeOwner:
    source_id = "fake"

    def __init__(self):
        self.restarts = 0

    def status(self):
        return {"running": True, "error": None, "frames": 1, "gaps": 0, "source": {"device": "/dev/fake"}}

    def latest(self):
        return None

    def wait_newer(self, after, timeout):
        time.sleep(min(timeout, 0.01))
        return None

    def restart(self, factory=None):
        self.restarts += 1

    def start(self):
        pass


def _wait_state(service, states, timeout=2.0):
    deadline = time.monotonic() + timeout
    while service.status()["state"] not in states and time.monotonic() < deadline:
        time.sleep(0.01)
    return service.status()["state"]


def test_simulate_refuses_setup_with_clear_reason(tmp_path):
    service = LiveService(FakeOwner(), tmp_path, simulate=True)
    with pytest.raises(LiveError, match="StreamCam"):
        service.start_setup()


def test_bad_operator_cell_text_is_refused_before_camera(tmp_path):
    called = []
    service = LiveService(FakeOwner(), tmp_path, setup_runner=lambda **kw: called.append(kw))
    with pytest.raises(LiveError, match="Zellentext"):
        service.start_setup(cell_text="zu kurz")
    assert called == [] and service.status()["state"] == "idle"


def test_setup_runner_result_leads_to_ready_then_confirm_rules(tmp_path):
    def runner(*, session_dir, cell_text, report):
        report("vorschlag")
        (session_dir / "setup").mkdir(parents=True, exist_ok=True)
        return {"setup_checks": {"overall": "WARNUNG", "checks": {}}, "frame": "x"}

    service = LiveService(FakeOwner(), tmp_path, setup_runner=runner)
    service.start_setup()
    assert _wait_state(service, {"setup_ready"}) == "setup_ready"
    with pytest.raises(LiveError, match="Format"):
        service.confirm(confirmed_by="Leonhard Hentschke", format_checked=False)
    with pytest.raises(LiveError, match="WARNUNG"):
        service.confirm(confirmed_by="Leonhard Hentschke", format_checked=True)


def test_setup_failure_is_reported(tmp_path):
    def runner(**_kw):
        raise ValueError("Punktraster abgelehnt: keine_startlage")

    service = LiveService(FakeOwner(), tmp_path, setup_runner=runner)
    service.start_setup()
    assert _wait_state(service, {"setup_failed"}) == "setup_failed"
    assert "keine_startlage" in service.status()["error"]


def test_run_rules_double_start_stop_without_run_and_setup_while_running(tmp_path, monkeypatch):
    service = LiveService(FakeOwner(), tmp_path)
    with pytest.raises(LiveError, match="kein Lauf"):
        service.stop_run()
    with pytest.raises(LiveError, match="bestaetig"):
        service.start_run()

    class FakeSession:
        def __init__(self, *a, **kw):
            self.latest, self.summary, self.end_reason = None, {}, None
            self.session_path = tmp_path / "s.json"

        def latest_age_s(self):
            return None

        def start(self):
            pass

        def run(self, stop):
            stop.wait()

        def stop(self, reason="bediener"):
            self.end_reason = reason
            return {"end_reason": reason}

    monkeypatch.setattr("dispread.live.service.LiveSession", FakeSession)
    service._state, service._profile_path = "confirmed", tmp_path / "profile.json"
    service._profile_camera = None
    service.start_run()
    assert service.status()["state"] == "running"
    with pytest.raises(LiveError, match="laeuft bereits"):
        service.start_run()
    with pytest.raises(LiveError, match="Lauf zuerst beenden"):
        service.start_setup()
    service.stop_run()
    assert service.status()["state"] == "stopped"
    service.start_run()
    service.close()
    assert service.status()["state"] == "stopped"
    assert service.status()["run"]["summary"] == {}
    service.close()


def test_camera_loss_during_run_is_shown(tmp_path, monkeypatch):
    class LosingSession:
        def __init__(self, *a, **kw):
            self.latest, self.summary, self.end_reason = None, {}, None
            self.session_path = tmp_path / "s.json"

        def latest_age_s(self):
            return None

        def start(self):
            pass

        def run(self, stop):
            self.end_reason = "kamera: kein Bild"

        def stop(self, reason="bediener"):
            return {"end_reason": self.end_reason}

    monkeypatch.setattr("dispread.live.service.LiveSession", LosingSession)
    service = LiveService(FakeOwner(), tmp_path)
    service._state, service._profile_path, service._profile_camera = "confirmed", tmp_path / "p.json", None
    service.start_run()
    assert _wait_state(service, {"stopped"}) == "stopped"
    assert "kein Bild" in service.status()["error"]


@pytest.fixture
def proposal(tmp_path):
    from dispread.camera_settings import CameraSettings
    from dispread.live import setup as live_setup

    frame = tmp_path / "still.png"
    frame.write_bytes(b"png")
    camera = CameraSettings(
        model="logitech_streamcam", usb_id="046d:0893", size=(1920, 1080),
        fourcc="YUYV", fps=30, controls={"focus_absolute": 48, "exposure_time_absolute": 156,
                                         "white_balance_temperature": 4600, "gain": 10},
    )
    return {
        "frame": str(frame), "device_id": "gsv-sensor-161a", "session_id": "live-test",
        "quad": [[0, 0], [400, 0], [400, 160], [0, 160]], "target_size": [400, 160],
        "grid": live_setup.LATTICE_GRID.to_dict(), "grid_source": "dot_lattice",
        "scaler_crop": None, "min_source_dot_column_px": 5.0, "native_scale": 1.0,
        "min_native_dot_column_px": 5.0, "camera": camera.to_dict(),
        "setup_checks": {"overall": "OK", "checks": {"rasterversatz": {"status": "OK"}}},
    }


def ready_service(tmp_path, proposal):
    def runner(*, session_dir, **kwargs):
        (session_dir / "setup").mkdir(parents=True)
        (session_dir / "setup" / "overlay_source.png").write_bytes(b"png")
        return proposal

    service = LiveService(FakeOwner(), tmp_path, setup_runner=runner)
    service.start_setup()
    assert _wait_state(service, {"setup_ready", "setup_failed"}) == "setup_ready"
    return service


@pytest.mark.parametrize("overall", ["OK", "WARNUNG"])
def test_confirmation_saves_profile_and_warning_acknowledgement(tmp_path, proposal, overall):
    from dispread.session_profile import SessionProfile

    proposal["setup_checks"]["overall"] = overall
    service = ready_service(tmp_path, proposal)
    assert service.status()["setup"] == {
        "overall": overall, "checks": {"rasterversatz": "OK"}, "overlays": ["overlay_source"],
    }
    service.confirm(confirmed_by="Leonhard Hentschke", format_checked=True, acknowledge_warning=True)
    status = service.status()
    profile = SessionProfile.load(tmp_path / status["session_id"] / "profile.json")
    assert profile.resolution_ok and profile.confirmed_by == "Leonhard Hentschke"
    assert status["state"] == "confirmed"
    assert status["profile"]["warning_acknowledged"] == (overall == "WARNUNG")
    assert status["release_notice"]
    assert service.setup_file("../profile") is None
    assert service.setup_file("still") is None
    assert service.setup_file("overlay_source").read_bytes() == b"png"


@pytest.mark.parametrize("overall,format_checked,message", [
    ("FEHLER", True, "FEHLER"), ("OK", False, "Format"),
])
def test_confirmation_refuses_before_cli_confirmation(tmp_path, proposal, monkeypatch,
                                                     overall, format_checked, message):
    from dispread.live import setup as live_setup

    proposal["setup_checks"]["overall"] = overall
    service = ready_service(tmp_path, proposal)

    def forbidden(*args, **kwargs):
        pytest.fail("CLI-Bestaetigung darf nicht erreicht werden")

    monkeypatch.setattr(live_setup, "confirm_proposal", forbidden)
    with pytest.raises(LiveError, match=message) as error:
        service.confirm(confirmed_by="x", format_checked=format_checked, acknowledge_warning=True)
    assert "--" not in str(error.value)
    assert service.status()["state"] == "setup_ready"


@pytest.mark.parametrize("name,min_px,message", [("  ", 5.0, "Name"), ("x", 2.0, "Aufloesung")])
def test_confirmation_refuses_missing_name_and_insufficient_resolution(tmp_path, proposal, name,
                                                                    min_px, message):
    proposal["min_native_dot_column_px"] = min_px
    service = ready_service(tmp_path, proposal)
    with pytest.raises(LiveError, match=message):
        service.confirm(confirmed_by=name, format_checked=True)
    assert service.status()["state"] == "setup_ready"
    assert not (tmp_path / service.status()["session_id"] / "profile.json").exists()


def test_start_run_reports_blocked_camera_restart(tmp_path, proposal):
    class BlockedOwner(FakeOwner):
        def restart(self, factory=None):
            raise RuntimeError("Kamera-Neustart abgelehnt: Lesethread noch nicht beendet")

    service = ready_service(tmp_path, proposal)
    service.confirm(confirmed_by="x", format_checked=True)
    service._owner = BlockedOwner()
    with pytest.raises(LiveError, match="Kamera.*nicht.*gestartet"):
        service.start_run()
    assert service.status()["state"] == "confirmed"
    assert service.status()["run"] is None


def test_run_start_refused_is_operator_error(tmp_path, monkeypatch):
    from dispread.live.session import StartRefused

    class RefusingSession:
        def __init__(self, *args):
            pass

        def start(self):
            raise StartRefused("Timing-Kalibrierung fehlt")

    monkeypatch.setattr("dispread.live.service.LiveSession", RefusingSession)
    service = LiveService(FakeOwner(), tmp_path)
    service._state, service._profile_path = "confirmed", tmp_path / "profile.json"
    with pytest.raises(LiveError, match="Kalibrierung"):
        service.start_run()
    assert service.status()["state"] == "confirmed"


def test_setup_in_background_reports_progress_and_refuses_second_setup(tmp_path):
    import threading

    entered, finish = threading.Event(), threading.Event()

    def runner(*, report, **kwargs):
        report("standbilder")
        entered.set()
        assert finish.wait(2)
        return {"setup_checks": {"overall": "OK", "checks": {}}}

    service = LiveService(FakeOwner(), tmp_path, setup_runner=runner)
    try:
        service.start_setup()
        assert entered.wait(1)
        assert service.status()["step"] == "standbilder"
        with pytest.raises(LiveError, match="Einrichtung laeuft bereits"):
            service.start_setup()
    finally:
        finish.set()
        service._setup_thread.join(2)
    assert service.status()["state"] == "setup_ready"


def test_real_setup_camera_restart_failure_becomes_setup_failed(tmp_path, proposal, monkeypatch):
    from dispread.camera_settings import CameraSettings
    from dispread.live import setup as live_setup

    class BlockedOwner(FakeOwner):
        def restart(self, factory=None):
            raise RuntimeError("Lesethread noch nicht beendet")

    camera = CameraSettings.from_dict(proposal["camera"])
    monkeypatch.setattr(live_setup, "focus_camera", lambda *args, **kwargs: (camera, FocusMeasurements()))
    service = LiveService(BlockedOwner(), tmp_path)
    service.start_setup()
    assert _wait_state(service, {"setup_failed"}) == "setup_failed"
    assert service.status()["error"] == "Lesethread noch nicht beendet"


def test_owner_setup_camera_discards_frames_and_copies_image():
    from types import SimpleNamespace

    import numpy as np

    from dispread.live.service import OwnerSetupCamera

    image = np.zeros((2, 3, 3), np.uint8)

    class Owner(FakeOwner):
        def latest(self):
            return 7, SimpleNamespace(image=image)

        def wait_newer(self, after, timeout):
            assert timeout == 2.0
            image[:] = after
            return after + 1, SimpleNamespace(image=image)

    result = OwnerSetupCamera(Owner()).fresh_still(discard=2)
    assert (result == 9).all()
    assert not np.shares_memory(result, image)


def test_owner_setup_camera_reports_missing_control_target_and_frame():
    from dispread.frames.uvc_source import UvcError
    from dispread.live import setup as live_setup
    from dispread.live.service import OwnerSetupCamera

    owner = FakeOwner()
    owner.control_target = lambda: None
    camera = OwnerSetupCamera(owner)
    with pytest.raises(live_setup.SetupError, match="Regler"):
        camera.set_controls([])
    with pytest.raises(UvcError, match="frisches Bild"):
        camera.fresh_still(discard=0)


@pytest.mark.parametrize("cell_text,fail", [("+ 1.2345 ", False), (None, False), (None, True)])
def test_real_setup_uses_fixed_camera_and_closes_serial(tmp_path, proposal, monkeypatch, cell_text, fail):
    import json
    from types import SimpleNamespace

    import numpy as np

    from dispread.camera_settings import CameraSettings
    from dispread.live import setup as live_setup

    events = []
    camera = CameraSettings.from_dict(proposal["camera"])
    image = np.zeros((2, 2, 3), np.uint8)
    result = SimpleNamespace(first=image, second=image, fit=object(), offset_check=object(),
                             final_checks=object(), stability_elapsed_s=30.0, reader_check=object())

    class Owner(FakeOwner):
        def restart(self, factory=None):
            assert factory() == camera
            events.append("restart")

    class Port:
        def close(self):
            events.append("serial_closed")

    port = Port()

    def open_serial():
        events.append("serial_opened")
        return port

    def focus(cam, hint, *, start_focus):
        assert hint is None
        assert start_focus == 48
        events.append("focus")
        measured = FocusMeasurements()
        measured.append((48, 1.0))
        return camera, measured

    def assist(cam, **kwargs):
        assert kwargs["expected_size"] == camera.size
        assert kwargs["templates"] == service._config.templates
        assert kwargs["templates_sha256"] == service._config.templates_sha256
        if cell_text is not None:
            assert kwargs["cell_text"](lambda: image)[1] == cell_text
        events.append("assist")
        if fail:
            raise live_setup.SetupError("Standbild abgelehnt")
        return result

    def propose(first, **kwargs):
        assert first is image
        assert kwargs["camera_settings"] == camera
        assert kwargs["offset_check"] is result.offset_check
        assert kwargs["final_checks"] is result.final_checks
        assert kwargs["stability_elapsed_s"] == 30.0
        assert kwargs["device_id"] == "gsv-sensor-161a"
        events.append("proposal")
        return proposal

    monkeypatch.setattr(live_setup, "focus_camera", focus)
    monkeypatch.setattr(live_setup, "assist_measure", assist)
    monkeypatch.setattr(live_setup, "propose_with_fit", propose)
    service = LiveService(Owner(), tmp_path, source_for=lambda settings: settings, serial_opener=open_serial)
    service.start_setup(cell_text=cell_text)
    expected = "setup_failed" if fail else "setup_ready"
    assert _wait_state(service, {"setup_ready", "setup_failed"}) == expected
    service._setup_thread.join(1)
    assert events[:2] == ["focus", "restart"]
    if cell_text is None:
        assert events[2:5] == ["serial_opened", "assist", "serial_closed"]
    else:
        assert events[2:] == ["assist", "proposal"]
    settings = tmp_path / service.status()["session_id"] / "setup" / "camera-settings.json"
    assert json.loads(settings.read_text())["camera"] == camera.to_dict()
    assert json.loads(settings.read_text())["focus_method"] == "climb"
    if fail:
        assert service.status()["error"] == "Standbild abgelehnt"
    else:
        assert events[-1] == "proposal"


def test_start_camera_wraps_failure(tmp_path):
    class Owner(FakeOwner):
        def start(self):
            raise RuntimeError("belegt")

    with pytest.raises(LiveError, match="Kamera nicht gestartet: belegt"):
        LiveService(Owner(), tmp_path).start_camera()


class MarkerSession:
    def __init__(self, owner, profile_path, config, out_dir):
        self.latest, self.summary, self.end_reason = None, {}, None
        self.session_path = out_dir / "session.json"
        self.records_path = out_dir / "records.jsonl"
        self.profile_path = profile_path

    def start(self):
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_path.write_text(self.session_path.parent.name)
        with self.records_path.open("a") as stream:
            stream.write("record\n")

    def run(self, stop):
        stop.wait()

    def stop(self, reason="bediener"):
        self.end_reason = reason

    def latest_age_s(self):
        return 1.25


def _confirmed_service(tmp_path, monkeypatch, session_class=MarkerSession):
    monkeypatch.setattr("dispread.live.service.LiveSession", session_class)
    service = LiveService(FakeOwner(), tmp_path, setup_runner=lambda **kw: {})
    service._state, service._profile_path = "confirmed", tmp_path / "profile.json"
    service._profile_path.write_text("confirmed profile")
    return service


@pytest.mark.parametrize("existing, first_name, second_name", [
    (False, "run-01", "run-02"), (True, "run-02", "run-03"),
])
def test_each_run_preserves_previous_artifacts(tmp_path, monkeypatch, existing, first_name, second_name):
    service = _confirmed_service(tmp_path, monkeypatch)
    # Bereits vorhandene Laufnummern werden nicht wiederverwendet.
    if existing:
        (tmp_path / "run-01").mkdir()
    try:
        service.start_run()
        assert service.status()["run"]["dir"] == first_name
        service.stop_run()
        first = tmp_path / first_name
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in first.iterdir()}
        service.start_run()
        assert service.status()["run"]["dir"] == second_name
        service.stop_run()
        assert {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in first.iterdir()} == before
        assert (tmp_path / second_name / "records.jsonl").read_text() == "record\n"
        assert (tmp_path / "profile.json").read_text() == "confirmed profile"
    finally:
        service.close()


def test_concurrent_setup_starts_only_one_worker(tmp_path):
    import threading
    from datetime import UTC, datetime

    in_wall, release_wall, release_runner = threading.Event(), threading.Event(), threading.Event()
    second_wall = threading.Event()
    calls, errors = [], []

    def wall():
        if in_wall.is_set():
            second_wall.set()
        in_wall.set()
        assert release_wall.wait(2)
        return datetime(2026, 10, 13, tzinfo=UTC)

    def runner(**kw):
        calls.append(kw)
        assert release_runner.wait(2)
        return {}

    service = LiveService(FakeOwner(), tmp_path, setup_runner=runner, wall=wall)

    def start():
        try:
            service.start_setup()
        except LiveError as exc:
            errors.append(str(exc))

    first, second = threading.Thread(target=start), threading.Thread(target=start)
    try:
        first.start()
        assert in_wall.wait(1)
        second.start()
        # Der zweite Aufruf trifft auf die noch laufende erste Operation.
        second_wall.wait(0.1)
        assert service.status()["state"] == "idle"
        release_wall.set()
        first.join(1)
        second.join(1)
        assert not first.is_alive() and not second.is_alive()
        assert errors == ["Einrichtung laeuft bereits"]
    finally:
        release_wall.set()
        release_runner.set()
        first.join(1)
        second.join(1)
        if service._setup_thread is not None:
            service._setup_thread.join(1)
    assert len(calls) == 1


@pytest.mark.parametrize("background", [False, True])
def test_stop_failure_leaves_stopped_and_allows_setup(tmp_path, monkeypatch, background):
    class FailingStopSession(MarkerSession):
        def run(self, stop):
            if background:
                self.end_reason = "kamera: kein Bild"
            else:
                stop.wait()

        def stop(self, reason="bediener"):
            raise OSError("Audit nicht geschlossen")

    service = _confirmed_service(tmp_path, monkeypatch, FailingStopSession)
    service.start_run()
    if background:
        assert _wait_state(service, {"stopped"}) == "stopped"
        service._run_thread.join(1)
    else:
        with pytest.raises(LiveError, match="Lauf nicht beendet.*Audit nicht geschlossen"):
            service.stop_run()
    assert service.status()["state"] == "stopped"
    assert "Audit nicht geschlossen" in service.status()["error"]
    service.start_setup()
    assert _wait_state(service, {"setup_ready"}) == "setup_ready"
    service._setup_thread.join(1)


@pytest.mark.parametrize("stage", ["constructor", "start"])
def test_start_run_converts_unexpected_session_errors(tmp_path, monkeypatch, stage):
    class FailingStartSession(MarkerSession):
        def __init__(self, *args):
            if stage == "constructor":
                raise OSError("Datei nicht schreibbar")
            super().__init__(*args)

        def start(self):
            raise OSError("Datei nicht schreibbar")

    service = _confirmed_service(tmp_path, monkeypatch, FailingStartSession)
    with pytest.raises(LiveError, match="Lauf nicht gestartet.*Datei nicht schreibbar"):
        service.start_run()
    assert service.status()["state"] == "confirmed"


def test_stop_timeout_is_reported(tmp_path, monkeypatch):
    service = _confirmed_service(tmp_path, monkeypatch)
    service.start_run()
    thread = service._run_thread
    thread.join(0.01)
    joins = []
    monkeypatch.setattr(thread, "join", lambda timeout: joins.append(timeout))
    monkeypatch.setattr(thread, "is_alive", lambda: True)
    service.stop_run()
    assert joins == [3.0]
    assert service.status()["state"] == "stopped"
    assert service.status()["error"] == "Lesethread haengt"
    # Den echten Worker nach dem simulierten Timeout aufraeumen.
    import threading
    threading.Thread.join(thread, 1)


def test_status_exposes_latest_age(tmp_path, monkeypatch):
    service = _confirmed_service(tmp_path, monkeypatch)
    try:
        service.start_run()
        assert service.status()["run"]["latest_age_s"] == 1.25
    finally:
        service.close()


def test_preview_without_frame_is_unavailable(tmp_path):
    service = LiveService(FakeOwner(), tmp_path)
    assert service.preview_jpeg() is None


def test_preview_resizes_and_draws_quad_without_changing_camera_image(tmp_path):
    from types import SimpleNamespace

    import cv2
    import numpy as np

    image = np.zeros((100, 200, 3), dtype=np.uint8)
    owner = FakeOwner()
    owner.latest = lambda: (1, SimpleNamespace(image=image))
    service = LiveService(owner, tmp_path)
    service._session = SimpleNamespace(_pipeline=SimpleNamespace(locator=SimpleNamespace(
        last_track=SimpleNamespace(quad=((20, 20), (180, 20), (180, 80), (20, 80)))
    )))
    jpeg = service.preview_jpeg(width=100)
    preview = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert preview.shape == (50, 100, 3)
    assert preview[10, 50, 1] > 150
    assert not image.any()


@pytest.mark.parametrize("message,expected", [
    ("Punktraster: startlage_mehrdeutig; bitte --hint-box angeben",
     "Punktraster: startlage_mehrdeutig; Anzeige mittig ins Bild bringen — "
     "Kamera senkrecht auf Displaymitte stellen und neu einrichten"),
    ("Punktraster: keine_startlage",
     "Punktraster: keine_startlage — Kamera senkrecht auf Displaymitte stellen und neu einrichten"),
    ("Punktraster abgelehnt: keine_startlage; Hinweisbox pruefen oder --hint-box angeben",
     "Punktraster abgelehnt: keine_startlage; Anzeige mittig ins Bild bringen — "
     "Kamera senkrecht auf Displaymitte stellen und neu einrichten"),
    ("Pruefung: --override-reason oder --accept-default-grid", "Pruefung: oder"),
    ("Standbild abgelehnt", "Standbild abgelehnt"),
])
def test_setup_errors_use_browser_wording(tmp_path, message, expected):
    from dispread.live.setup import SetupError

    def runner(**kwargs):
        raise SetupError(message)

    service = LiveService(FakeOwner(), tmp_path, setup_runner=runner)
    service.start_setup()
    assert _wait_state(service, {"setup_failed"}) == "setup_failed"
    assert service.status()["error"] == expected


def test_setup_refuses_stopped_camera_before_starting_worker(tmp_path):
    owner = FakeOwner()
    owner.status = lambda: {"running": False, "error": "USB-Verbindung verloren"}
    service = LiveService(owner, tmp_path)
    with pytest.raises(LiveError) as error:
        service.start_setup()
    assert str(error.value) == "Kamera laeuft nicht: USB-Verbindung verloren — 'Kamera neu verbinden'"
    assert service.status()["state"] == "idle"
    assert service._setup_thread is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("overall,acknowledged", [("OK", False), ("OK", True), ("WARNUNG", True)])
def test_confirmation_persists_operator_checks(tmp_path, proposal, overall, acknowledged):
    import json
    from datetime import datetime

    proposal["setup_checks"]["overall"] = overall
    service = ready_service(tmp_path, proposal)
    service.confirm(confirmed_by="Tester", format_checked=True, acknowledge_warning=acknowledged)
    directory = tmp_path / service.status()["session_id"]
    confirmation = json.loads((directory / "confirmation.json").read_text())
    profile = json.loads((directory / "profile.json").read_text())
    assert confirmation == {
        "confirmed_by": "Tester", "confirmed_at_utc": profile["confirmed_at_utc"],
        "unit": "mV/V", "format_id": "gsv2as_v1", "format_checked": True,
        "warning_acknowledged": acknowledged, "setup_overall": overall,
    }
    assert datetime.fromisoformat(confirmation["confirmed_at_utc"]).utcoffset().total_seconds() == 0


def test_setup_reuses_only_last_confirmed_focus_across_failed_retries(tmp_path, proposal, monkeypatch):
    import json

    from dispread.camera_settings import CameraSettings
    from dispread.live import setup as live_setup

    proposal["camera"]["controls"]["focus_absolute"] = 68
    service = ready_service(tmp_path, proposal)
    starts = []

    def focus(cam, hint, *, start_focus):
        starts.append(start_focus)
        measured = FocusMeasurements("sweep")
        measured.append((100, 1.0))
        return CameraSettings.from_dict(proposal["camera"]), measured

    def fail_after_focus(*args, **kwargs):
        raise live_setup.SetupError("Standbild abgelehnt")

    monkeypatch.setattr(live_setup, "focus_camera", focus)
    monkeypatch.setattr(live_setup, "assist_measure", fail_after_focus)
    service._setup_runner = service._run_setup
    # Ein unbestaetigter Vorschlag darf keinen Startwert vorgeben.
    service.start_setup(cell_text="+ 1.2345 ")
    assert _wait_state(service, {"setup_failed"}) == "setup_failed"
    assert starts == [48]
    # Dieselbe Service-Instanz bestaetigt nun das Profil mit Fokus 68.
    service._proposal, service._state = proposal, "setup_ready"
    service.confirm(confirmed_by="Test", format_checked=True)
    for _ in range(2):
        service.start_setup(cell_text="+ 1.2345 ")
        assert _wait_state(service, {"setup_failed"}) == "setup_failed"
    assert starts == [48, 68, 68]
    path = tmp_path / service.status()["session_id"] / "setup" / "camera-settings.json"
    assert json.loads(path.read_text())["focus_method"] == "sweep"
