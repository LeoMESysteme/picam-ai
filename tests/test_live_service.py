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
        service.confirm(session_id=service.status()["session_id"], confirmed_by="Leonhard Hentschke", format_checked=False)
    with pytest.raises(LiveError, match="WARNUNG"):
        service.confirm(session_id=service.status()["session_id"], confirmed_by="Leonhard Hentschke", format_checked=True)


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
        "setup_checks": {"overall": "OK", "checks": {"rasterversatz": {"status": "OK"}, "gegenlesen": {"status": "OK"}}},
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
        "overall": overall, "checks": {"rasterversatz": "OK", "gegenlesen": "OK"}, "overlays": ["overlay_source"],
        "step": "vorschlag", "elapsed_s": service.status()["setup"]["elapsed_s"],
    }
    service.confirm(session_id=service.status()["session_id"], confirmed_by="Leonhard Hentschke", format_checked=True, acknowledge_warning=True)
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
        service.confirm(session_id=service.status()["session_id"], confirmed_by="x", format_checked=format_checked, acknowledge_warning=True)
    assert "--" not in str(error.value)
    assert service.status()["state"] == "setup_ready"


@pytest.mark.parametrize("name,min_px,message", [("  ", 5.0, "Name"), ("x", 2.0, "Aufloesung")])
def test_confirmation_refuses_missing_name_and_insufficient_resolution(tmp_path, proposal, name,
                                                                    min_px, message):
    proposal["min_native_dot_column_px"] = min_px
    service = ready_service(tmp_path, proposal)
    with pytest.raises(LiveError, match=message):
        service.confirm(session_id=service.status()["session_id"], confirmed_by=name, format_checked=True)
    assert service.status()["state"] == "setup_ready"
    assert not (tmp_path / service.status()["session_id"] / "profile.json").exists()


def test_start_run_reports_blocked_camera_restart(tmp_path, proposal):
    class BlockedOwner(FakeOwner):
        def restart(self, factory=None):
            raise RuntimeError("Kamera-Neustart abgelehnt: Lesethread noch nicht beendet")

    service = ready_service(tmp_path, proposal)
    service.confirm(session_id=service.status()["session_id"], confirmed_by="x", format_checked=True)
    service._owner = BlockedOwner()
    with pytest.raises(LiveError, match="Kamera.*nicht.*gestartet"):
        service.start_run()
    assert service.status()["state"] == "confirmed"
    assert service.status()["run"] is None


def test_run_start_refused_is_operator_error(tmp_path, monkeypatch):
    from dispread.live.session import StartRefused

    class RefusingSession:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            raise StartRefused("Timing-Kalibrierung fehlt")

    monkeypatch.setattr("dispread.live.service.LiveSession", RefusingSession)
    service = LiveService(FakeOwner(), tmp_path)
    service._state, service._profile_path = "confirmed", tmp_path / "profile.json"
    with pytest.raises(LiveError, match="Kalibrierung"):
        service.start_run()
    assert service.status()["state"] == "confirmed"


def test_retry_note_extends_current_step_message_only(tmp_path):
    service = LiveService(FakeOwner(), tmp_path)
    service._setup_progress("Punktraster-Startsuche: Versuch 1/3")
    service._setup_note("neuer Versuch 2/5")
    assert service._setup_message == "Punktraster-Startsuche: Versuch 1/3 - neuer Versuch 2/5"
    service._setup_progress("Fokus: Bergsteigen")
    service._report("standbilder")
    service._setup_note("neuer Versuch 2/5")
    assert service._setup_message == "neuer Versuch 2/5"


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
    result = SimpleNamespace(first=image, second=image, first_text='+ 1.23?5 ', fit=object(), offset_check=object(),
                             final_checks=object(), stability_elapsed_s=30.0, reader_check=object(), setup_attempt=2)

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

    def focus(cam, hint, *, start_focus, info):
        assert info == service._setup_progress
        assert hint is None
        assert start_focus == 48
        events.append("focus")
        measured = FocusMeasurements()
        measured.append((48, 1.0))
        return camera, measured

    def assist(cam, **kwargs):
        assert kwargs["stability_s"] == kwargs["min_stability_s"] == 15.0
        assert kwargs["stack_frames"] == 8 and kwargs["fit_attempts"] == 3
        assert kwargs["expected_size"] == camera.size
        assert kwargs["templates"] == service._config.templates
        assert kwargs["templates_sha256"] == service._config.templates_sha256
        assert kwargs["reference_kind"] == ("seriell" if cell_text is None else "eingabe")
        if cell_text is not None:
            assert kwargs["cell_text"](lambda: image)[1] == cell_text
        events.append("assist")
        if fail:
            raise live_setup.SetupError("Standbild abgelehnt")
        return result

    def propose(first, **kwargs):
        assert first is image
        assert kwargs['cell_text'] == result.first_text
        assert kwargs["camera_settings"] == camera
        assert kwargs["offset_check"] is result.offset_check
        assert kwargs["final_checks"] is result.final_checks
        assert kwargs["stability_elapsed_s"] == 30.0
        assert kwargs["stability_min_elapsed_s"] == 15.0
        assert kwargs["setup_attempt"] == 2
        assert kwargs["live_tracking"] is True
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
    def __init__(self, owner, profile_path, config, out_dir, *, test_run=None, reader_d_max_factor=1.0, reader_tolerance=None, reference_recorder=None, diagnostics=False, diagnostic_staging_root=None):
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
        def __init__(self, *args, **kwargs):
            if stage == "constructor":
                raise OSError("Datei nicht schreibbar")
            super().__init__(*args, **kwargs)

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
    service.confirm(session_id=service.status()["session_id"], confirmed_by="Tester", format_checked=True, acknowledge_warning=acknowledged)
    directory = tmp_path / service.status()["session_id"]
    confirmation = json.loads((directory / "confirmation.json").read_text())
    profile = json.loads((directory / "profile.json").read_text())
    assert confirmation == {
        "confirmed_by": "Tester", "confirmed_at_utc": profile["confirmed_at_utc"],
        "unit": "mV/V", "format_id": "gsv2as_v1", "format_checked": True,
        "warning_acknowledged": acknowledged, "setup_overall": overall, "run_block": None, "reader_tolerance": None,
    }
    assert datetime.fromisoformat(confirmation["confirmed_at_utc"]).utcoffset().total_seconds() == 0


@pytest.mark.parametrize("plain_list", [False, True])
def test_setup_reuses_only_last_confirmed_focus_across_failed_retries(tmp_path, proposal, monkeypatch, plain_list):
    import json

    from dispread.camera_settings import CameraSettings
    from dispread.live import setup as live_setup

    proposal["camera"]["controls"]["focus_absolute"] = 68
    service = ready_service(tmp_path, proposal)
    starts = []

    def focus(cam, hint, *, start_focus, info):
        assert info == service._setup_progress
        starts.append(start_focus)
        measured = FocusMeasurements("sweep")
        measured.append((100, 1.0))
        return CameraSettings.from_dict(proposal["camera"]), list(measured) if plain_list else measured

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
    service.confirm(session_id=service.status()["session_id"], confirmed_by="Test", format_checked=True)
    for _ in range(2):
        service.start_setup(cell_text="+ 1.2345 ")
        assert _wait_state(service, {"setup_failed"}) == "setup_failed"
    assert starts == [48, 68, 68]
    path = tmp_path / service.status()["session_id"] / "setup" / "camera-settings.json"
    assert json.loads(path.read_text())["focus_method"] == "sweep"


@pytest.mark.parametrize("fail", [False, True])
def test_setup_elapsed_uses_monotonic_and_freezes(tmp_path, fail):
    import threading

    entered, finish = threading.Event(), threading.Event()
    clock = [100.0]

    def runner(*, report, **kwargs):
        report("standbilder")
        entered.set()
        assert finish.wait(2)
        if fail:
            raise ValueError("test failure")
        return {"setup_checks": {"overall": "OK", "checks": {}}}

    service = LiveService(FakeOwner(), tmp_path, setup_runner=runner, monotonic=lambda: clock[0])
    try:
        service.start_setup()
        assert entered.wait(1)
        clock[0] = 107.5
        assert service.status()["setup"]["step"] == "standbilder"
        assert service.status()["setup"]["elapsed_s"] == 7.5
    finally:
        finish.set()
        service._setup_thread.join(2)
    clock[0] = 200.0
    assert service.status()["setup"]["elapsed_s"] == 7.5


@pytest.mark.parametrize("failed_step", ["fokus", "kamera", "seriell"])
def test_setup_early_failure_writes_diagnostic(tmp_path, proposal, monkeypatch, failed_step):
    import json
    from datetime import datetime

    from dispread.camera_settings import CameraSettings
    from dispread.live import setup as live_setup

    def fail():
        raise RuntimeError("early failure")

    camera = CameraSettings.from_dict(proposal["camera"])
    monkeypatch.setattr(live_setup, "focus_camera", lambda *a, **kw:
                        fail() if failed_step == "fokus" else (camera, FocusMeasurements()))
    owner = FakeOwner()
    if failed_step == "kamera":
        owner.restart = lambda *a: fail()
    service = LiveService(owner, tmp_path, serial_opener=fail)
    service.start_setup()
    service._setup_thread.join(2)
    assert service.status()["state"] == "setup_failed"
    failure = json.loads((tmp_path / service.status()["session_id"] / "setup" / "failure.json").read_text())
    assert json.loads((tmp_path / service.status()["session_id"] / "setup" / "cell-text.json").read_text()) == []
    assert failure["step"] == ("kamera" if failed_step == "seriell" else failed_step)
    assert "early failure" in failure["reason"]
    assert datetime.fromisoformat(failure["created_at_utc"]).tzinfo is not None


@pytest.mark.parametrize("source", ["seriell", "eingabe"])
@pytest.mark.parametrize("fit_rejected", [False, True])
def test_failed_search_saves_every_attempt_cell_text(tmp_path, proposal, monkeypatch, source, fit_rejected):
    import json
    from dataclasses import replace

    import numpy as np

    from dispread.camera_settings import CameraSettings
    from dispread.live import setup as live_setup

    camera = replace(CameraSettings.from_dict(proposal["camera"]), size=(3, 2))
    monkeypatch.setattr(live_setup, "focus_camera", lambda *a, **kw: (camera, FocusMeasurements()))
    monkeypatch.setattr("dispread.live.service.OwnerSetupCamera.fresh_still",
                        lambda *a, **kw: np.zeros((2, 3, 3), np.uint8))
    monkeypatch.setattr(live_setup, "find_green_hint_box", lambda image: None)
    if fit_rejected:
        monkeypatch.setattr(live_setup, "find_green_hint_box", lambda image: (0, 0, 1, 1))
        reasons = iter(["keine_startlage", "startlage_mehrdeutig", "vorzeichen_kein_plus"])
        monkeypatch.setattr(live_setup, "fit_lattice", lambda *a, **kw: next(reasons))
    texts = iter(text for n in range(1, 4) for _ in range(5)
                 for text in (f"+ {n}.2345 ", f"+ {n}.2346 "))
    monkeypatch.setattr(live_setup, "serial_cell_text", lambda port: next(texts))

    class Port:
        closed = False

        def close(self):
            self.closed = True

    port = Port()
    service = LiveService(FakeOwner(), tmp_path, serial_opener=lambda: port)
    service.start_setup(cell_text="+ 1.2345 " if source == "eingabe" else None)
    service._setup_thread.join(2)
    assert service.status()["state"] == "setup_failed"
    setup_dir = tmp_path / service.status()["session_id"] / "setup"
    entries = json.loads((setup_dir / "cell-text.json").read_text())
    assert len(entries) == 3
    for attempt, entry in enumerate(entries, 1):
        assert entry["attempt"] == attempt and entry["source"] == source
        assert entry["still"] == "still"
        if fit_rejected:
            assert entry["fit"] == ["keine_startlage", "startlage_mehrdeutig", "vorzeichen_kein_plus"][attempt - 1]
        if source == "seriell":
            assert entry["unmasked"] == [f"+ {attempt}.2345 ", f"+ {attempt}.2346 "]
            assert entry["masked"] == f"+ {attempt}.234? "
            assert entry["tries"] == 5
        else:
            assert entry["unmasked"] == ["+ 1.2345 "]
            assert entry["masked"] == "+ 1.2345 "
            assert entry["tries"] == 1
    failure = json.loads((setup_dir / "failure.json").read_text())
    assert ("vorzeichen_kein_plus" if fit_rejected else "Kein gruener Bereich") in failure["reason"]
    assert failure["step"] == service.status()["setup"]["step"] == "standbilder"
    message = service.status()["setup"]["message"]
    # Wiederholte Aufnahmen ergaenzen die Meldung, der Suchversuch bleibt sichtbar.
    assert "Startsuche: Versuch 3/3" in message
    if source == "seriell":
        assert "neuer Versuch 5/5" in message
    if source == "seriell":
        assert port.closed


@pytest.mark.parametrize("offset_status", ["FEHLER", "OK"])
def test_setup_saves_cross_masked_text_before_2j_failure_or_success(tmp_path, proposal, monkeypatch, offset_status):
    import json
    from dataclasses import replace
    from types import SimpleNamespace

    import numpy as np

    from dispread.camera_settings import CameraSettings
    from dispread.live import setup as live_setup

    camera = replace(CameraSettings.from_dict(proposal["camera"]), size=(3, 2))
    monkeypatch.setattr(live_setup, "focus_camera", lambda *a, **kw: (camera, FocusMeasurements()))
    monkeypatch.setattr("dispread.live.service.OwnerSetupCamera.fresh_still",
                        lambda *a, **kw: np.zeros((2, 3, 3), np.uint8))
    monkeypatch.setattr(live_setup, "find_green_hint_box", lambda image: (0, 0, 1, 1))
    fit = SimpleNamespace(quad=[[0, 0], [3, 0], [3, 2], [0, 2]])
    fits = iter(["retry", fit])
    monkeypatch.setattr(live_setup, "fit_lattice", lambda *a, **kw: next(fits))
    checks = SimpleNamespace(overall="OK", checks={}, to_dict=lambda: {})
    monkeypatch.setattr(live_setup, "check_setup", lambda *a, **kw: checks)

    def refine(*a):
        raise ValueError("kein Feinschliff")

    monkeypatch.setattr(live_setup, "refine_quad", refine)
    offset = SimpleNamespace(status=offset_status, to_dict=lambda: {"status": offset_status})
    monkeypatch.setattr(live_setup, "raster_offset_check", lambda *a: offset)
    monkeypatch.setattr(live_setup, "propose_with_fit", lambda *a, **kw: proposal)
    monkeypatch.setattr(live_setup.time, "sleep", lambda s: None)
    texts = iter(["+0.60970 ", "+0.60970 "] + ["+0.60971 ", "+0.60972 "] * 5 + ["+0.61971 ", "+0.61971 "])
    monkeypatch.setattr(live_setup, "serial_cell_text", lambda port: next(texts))
    service = LiveService(FakeOwner(), tmp_path, serial_opener=lambda: SimpleNamespace(close=lambda: None))
    service.start_setup()
    service._setup_thread.join(2)
    assert service.status()["state"] == ("setup_failed" if offset_status == "FEHLER" else "setup_ready")
    setup_dir = tmp_path / service.status()["session_id"] / "setup"
    assert json.loads((setup_dir / "cell-text.json").read_text()) == [
        {"attempt": 1, "still": "still", "source": "seriell", "unmasked": ["+0.60970 ", "+0.60970 "], "masked": "+0.60970 ", "fit": "retry", "tries": 1},
        {"attempt": 2, "still": "still", "source": "seriell", "unmasked": ["+0.60971 ", "+0.60972 "], "masked": "+0.6?97? ", "fit": "ok", "tries": 5},
        {"attempt": 2, "still": "stability", "source": "seriell", "unmasked": ["+0.61971 ", "+0.61971 "], "masked": "+0.6?97? ", "tries": 1},
    ]
    if offset_status == "FEHLER":
        assert "Rasterversatz 2j meldet FEHLER" in json.loads((setup_dir / "failure.json").read_text())["reason"]
    else:
        assert not (setup_dir / "failure.json").exists()


@pytest.mark.parametrize("error_type", [OSError, TypeError, ValueError])
def test_failure_diagnostic_write_keeps_original_outcome(tmp_path, monkeypatch, error_type):
    from pathlib import Path

    write_text = Path.write_text

    def write(path, *args, **kwargs):
        if path.name == "failure.json":
            raise error_type("diagnostic blocked")
        return write_text(path, *args, **kwargs)

    def runner(*, report, **kwargs):
        report("standbilder")
        raise ValueError("original setup failure")

    monkeypatch.setattr(Path, "write_text", write)
    service = LiveService(FakeOwner(), tmp_path, setup_runner=runner)
    service.start_setup()
    service._setup_thread.join(2)
    status = service.status()
    assert status["state"] == "setup_failed"
    assert status["error"] == "original setup failure"
    assert "failure.json" in status["setup"]["diagnostics_error"]


@pytest.mark.parametrize("failed_write", [1, 2])
@pytest.mark.parametrize("error_type", [OSError, TypeError, ValueError])
def test_cell_diagnostic_write_does_not_fail_setup(tmp_path, proposal, monkeypatch, failed_write, error_type):
    from pathlib import Path
    from types import SimpleNamespace

    from dispread.camera_settings import CameraSettings
    from dispread.live import setup as live_setup

    write_text = Path.write_text
    writes = []

    def write(path, *args, **kwargs):
        if path.name == "cell-text.json":
            writes.append(path)
            if len(writes) == failed_write:
                raise error_type("diagnostic blocked")
        return write_text(path, *args, **kwargs)

    def assist(*args, **kwargs):
        kwargs["info"]("Startsuche Versuch 1")
        assert service.status()["setup"]["step"] == "standbilder"
        assert service.status()["setup"]["message"] == "Startsuche Versuch 1"
        kwargs["on_attempt"]({"attempt": 1, "still": "still", "masked": "+ 1.2345 "})
        return SimpleNamespace(first=None, second=None, first_text='+ 1.2345 ', fit=None, offset_check=None,
                               final_checks=None, stability_elapsed_s=15, reader_check=None, setup_attempt=1)

    camera = CameraSettings.from_dict(proposal["camera"])
    monkeypatch.setattr(Path, "write_text", write)
    monkeypatch.setattr(live_setup, "focus_camera", lambda *a, **kw: (camera, FocusMeasurements()))
    monkeypatch.setattr(live_setup, "assist_measure", assist)
    monkeypatch.setattr(live_setup, "propose_with_fit", lambda *a, **kw: proposal)
    service = LiveService(FakeOwner(), tmp_path)
    service.start_setup(cell_text="+ 1.2345 ")
    service._setup_thread.join(2)
    assert service.status()["state"] == "setup_ready"
    assert "cell-text.json" in service.status()["setup"]["diagnostics_error"]


@pytest.mark.parametrize("failure", ["length", "read_before", "read_after"])
def test_setup_records_text_when_serial_capture_fails(tmp_path, proposal, monkeypatch, failure):
    import json
    from types import SimpleNamespace

    import numpy as np

    from dispread.camera_settings import CameraSettings
    from dispread.live import setup as live_setup

    camera = CameraSettings.from_dict(proposal["camera"])
    monkeypatch.setattr(live_setup, "focus_camera", lambda *a, **kw: (camera, FocusMeasurements()))
    monkeypatch.setattr("dispread.live.service.OwnerSetupCamera.fresh_still",
                        lambda *a, **kw: np.zeros((2, 3, 3), np.uint8))
    texts = iter([OSError("serial read failed")] if failure == "read_before" else
                 ["abc", OSError("serial read failed") if failure == "read_after" else "abcd"])

    def read(port):
        value = next(texts)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(live_setup, "serial_cell_text", read)
    service = LiveService(FakeOwner(), tmp_path, serial_opener=lambda: SimpleNamespace(close=lambda: None))
    service.start_setup()
    service._setup_thread.join(2)
    assert service.status()["state"] == "setup_failed"
    setup_dir = tmp_path / service.status()["session_id"] / "setup"
    entries = json.loads((setup_dir / "cell-text.json").read_text())
    assert len(entries) == 1
    assert entries[0]["unmasked"] == ([] if failure == "read_before" else
                                      ["abc"] if failure == "read_after" else ["abc", "abcd"])
    assert entries[0]["masked"] is None
    assert entries[0]["error"] == service.status()["error"]
    assert json.loads((setup_dir / "failure.json").read_text())["step"] == "standbilder"


@pytest.mark.parametrize("session_id", ["old-session", "", None])
def test_confirmation_refuses_unseen_session(tmp_path, proposal, session_id):
    service = ready_service(tmp_path, proposal)
    with pytest.raises(LiveError, match="Vorschlag hat sich geaendert"):
        service.confirm(session_id=session_id, confirmed_by="Operator", format_checked=True)
    assert service.status()["state"] == "setup_ready"
    assert not (tmp_path / service.status()["session_id"] / "profile.json").exists()


def test_minus_sign_failure_has_positive_value_hint():
    from dispread.live.service import _setup_error_for_page

    assert _setup_error_for_page("Punktraster abgelehnt: vorzeichen_kein_plus") == (
        "Punktraster abgelehnt: vorzeichen_kein_plus — "
        "Anzeige zeigt kein Plus — Wert positiv einstellen und neu einrichten"
    )


@pytest.mark.parametrize("reader_status", ["OK", "WARNUNG", "FEHLER", None])
def test_run_block_reason_only_depends_on_reader(reader_status):
    from dispread.live.service import run_block_reason

    checks = {} if reader_status is None else {"gegenlesen": {
        "status": reader_status,
        "metrics": {"frames": 2, "read_count": 0, "rejection_reasons": {"zelle_unbekannt": 2}},
    }}
    reason = run_block_reason({"setup_checks": {"overall": "WARNUNG", "checks": checks}})
    if reader_status == "OK":
        assert reason is None
    elif reader_status is None:
        assert reason == "Lauf gesperrt: Einrichtung ohne Gegenlesen. Neu einrichten."
    else:
        assert f"0 von 2 Standbildern gelesen (Gegenlesen {reader_status}: zelle_unbekannt x2)" in reason


def test_block_survives_confirmation_and_override_is_audited(tmp_path, proposal, monkeypatch):
    import json
    from unittest.mock import Mock

    proposal["setup_checks"]["checks"]["gegenlesen"] = {
        "status": "WARNUNG", "metrics": {"frames": 2, "read_count": 0, "rejection_reasons": {}},
    }
    service = ready_service(tmp_path, proposal)
    reason = service.status()["run_block"]
    assert "Gegenlesen WARNUNG: -" in reason
    service.confirm(session_id=service.status()["session_id"], confirmed_by="Operator", format_checked=True)
    session_dir = tmp_path / service.status()["session_id"]
    assert json.loads((session_dir / "confirmation.json").read_text())["run_block"] == reason
    with pytest.raises(LiveError, match="Lauf gesperrt"):
        service.start_run()
    assert not list(session_dir.glob("run-*"))
    session = Mock(latest=None, summary={}, latest_guess={"text": "guess"},
                   tracking={"mode": "ecc_alt", "version": None, "regions": None})
    session.latest_age_s.return_value = None
    session.rejection_causes.return_value = {"frames": 0, "window_s": 10.0, "limited": False, "causes": []}
    session.run.side_effect = lambda stop: stop.wait()
    factory = Mock(return_value=session)
    monkeypatch.setattr("dispread.live.service.LiveSession", factory)
    service.start_run(test_override=True)
    try:
        marker = json.loads((session_dir / "run-01" / "TESTLAUF.json").read_text())
        assert marker["testlauf"] is True and marker["run_block"] == reason
        assert marker["confirmed_by"] == "Operator"
        assert factory.call_args.kwargs["test_run"] == marker
        assert service.status()["test_run"] == marker
        assert service.status()["run"]["guess"] == {"text": "guess"}
    finally:
        service.stop_run()
    assert service.status()["run_block"] == reason
    assert service.status()["test_run"] == marker


def test_override_without_block_stays_normal_and_new_setup_clears_markers(tmp_path, monkeypatch):
    service = _confirmed_service(tmp_path, monkeypatch)
    service._test_run = {"testlauf": True}
    service.start_run(test_override=True)
    try:
        assert service.status()["test_run"] is None
        assert service.status()["run"]["guess"] is None
        assert not list(tmp_path.glob("run-*/TESTLAUF.json"))
    finally:
        service.stop_run()
    service._run_block = "old block"
    service._test_run = {"testlauf": True}
    service.start_setup()
    service._setup_thread.join(2)
    assert service.status()["test_run"] is None
    assert service.status()["run_block"] != "old block"
    assert service.status()["run"] is None


def test_run_block_reason_explains_reference_contradiction():
    from dispread.live.service import run_block_reason

    reason = run_block_reason({"setup_checks": {"checks": {"gegenlesen": {
        "status": "FEHLER", "metrics": {
            "rejection_reasons": {"zelle_widerspricht_referenz": 1},
            "contradictions": [{"frame": 0, "cell": 7, "read": "3", "reference": "2"}],
        },
    }}}})
    assert reason == ("Lauf gesperrt: Der Leser widerspricht bei der Einrichtung dem Referenzwert "
                      "des GSV-2AS (Zelle 7: gelesen '3', Referenz '2'). Neu einrichten.")


def test_reader_contradiction_refuses_confirmation(tmp_path, proposal):
    proposal["setup_checks"]["overall"] = "FEHLER"
    proposal["setup_checks"]["checks"]["gegenlesen"] = {"status": "FEHLER"}
    service = ready_service(tmp_path, proposal)
    with pytest.raises(LiveError, match="Einrichtung meldet FEHLER - nicht bestaetigbar"):
        service.confirm(session_id=service.status()["session_id"], confirmed_by="Operator",
                        format_checked=True, acknowledge_warning=True)
    assert service.status()["state"] == "setup_ready"


def test_setup_pads_manual_cell_text_and_keeps_mask(tmp_path):
    observed = []

    def runner(**kwargs):
        observed.append(kwargs['cell_text'])
        return {"setup_checks": {"overall": "WARNUNG", "checks": {}}}

    service = LiveService(FakeOwner(), tmp_path, setup_runner=runner)
    service.start_setup(cell_text="+0.4678?")
    service._setup_thread.join(2)
    assert service.status()["state"] == "setup_ready"
    assert observed == ["+0.4678? "]


@pytest.mark.parametrize('use_tolerance', [False, True])
def test_confirm_adaptive_tolerance_marks_artifacts_and_run(tmp_path, proposal, monkeypatch, use_tolerance):
    import json

    metrics = {'hinweis': 'Schatten entfernen.', 'tolerance': {
        'possible': True, 'factor': 1.44, 'd_max': 1.92, 'max_d_best': 2.2}}
    proposal['setup_checks'].update(overall='WARNUNG')
    proposal['setup_checks']['checks']['gegenlesen'] = {'status': 'WARNUNG', 'metrics': metrics}
    service = ready_service(tmp_path, proposal)
    assert 'Schatten entfernen.' in service.status()['run_block']
    assert service.status()['setup']['gegenlesen']['metrics'] == metrics
    kwargs = dict(session_id=service.status()['session_id'], confirmed_by='Operator', format_checked=True,
                  use_tolerance=use_tolerance)
    with pytest.raises(LiveError, match='WARNUNG'):
        service.confirm(**kwargs)
    service.confirm(**kwargs, acknowledge_warning=True)
    status = service.status()
    confirmation = json.loads((tmp_path / status['session_id'] / 'confirmation.json').read_text())
    assert confirmation['reader_tolerance'] == status['reader_tolerance']
    if use_tolerance:
        tolerance = status['reader_tolerance']
        assert tolerance['factor'] == 1.44
        assert tolerance['d_max_templates'] == 1.92
        assert tolerance['d_max_run'] == 1.92 * 1.44
        assert tolerance['max_d_best'] == 2.2
        assert 'nicht validiert' in tolerance['hinweis']
        assert status['run_block'] is None
        captured = []

        class Session(MarkerSession):
            def __init__(self, *a, **kw):
                captured.append(kw)
                super().__init__(*a, **kw)
        monkeypatch.setattr('dispread.live.service.LiveSession', Session)
        try:
            service.start_run()
            assert captured[0]['reader_d_max_factor'] == 1.44
            assert captured[0]['reader_tolerance'] == tolerance
            assert captured[0]['test_run'] is None
        finally:
            service.close()
    else:
        assert status['reader_tolerance'] is None
        assert status['run_block']
        captured = []

        class Session(MarkerSession):
            def __init__(self, *a, **kw):
                captured.append(kw)
                super().__init__(*a, **kw)
        monkeypatch.setattr('dispread.live.service.LiveSession', Session)
        try:
            # Ohne Toleranz nur als Testlauf - und dann mit dem strengen Leser.
            service.start_run(test_override=True)
            assert captured[0]['reader_d_max_factor'] == 1.0
            assert captured[0]['reader_tolerance'] is None
            assert captured[0]['test_run'] is not None
        finally:
            service.close()
    service.start_setup()
    assert service.status()['reader_tolerance'] is None
    service.close()


def test_cannot_choose_tolerance_without_verified_proposal(tmp_path, proposal):
    service = ready_service(tmp_path, proposal)
    with pytest.raises(LiveError, match='Angepasste Toleranz fuer diesen Vorschlag nicht moeglich'):
        service.confirm(session_id=service.status()['session_id'], confirmed_by='Operator', format_checked=True,
                        use_tolerance=True)
    assert service.status()['state'] == 'setup_ready'


@pytest.mark.parametrize('missing', [False, True])
def test_reference_start_falls_back_and_metadata_matches_status(tmp_path, monkeypatch, missing):
    import json

    from dotmatrix_helpers import embed
    from test_live_reference import FakePort
    from test_live_session import _session

    port = FakePort([b'partial\n', b'+01.2345 mV/V\n'])
    def opener():
        if missing:
            raise OSError('kein GSV-2AS')
        return port
    def factory(owner, profile, config, out_dir, **kw):
        session = _session(tmp_path, [embed('+ 1.2345 ')], **kw)
        session._out_dir = out_dir
        session.session_path = out_dir / 'session.json'
        session.records_path = out_dir / 'records.jsonl'
        return session
    monkeypatch.setattr('dispread.live.service.LiveSession', factory)
    service = LiveService(FakeOwner(), tmp_path, serial_opener=opener)
    service._state, service._profile_path = 'confirmed', tmp_path / 'profile.json'
    service.start_run()
    status = service.status()
    assert status['state'] == 'running'
    assert status['reference']['enabled'] is (not missing)
    if missing:
        assert 'kein GSV-2AS' in status['reference']['reason']
    service.stop_run()
    metadata = json.loads(service._session.session_path.read_text())
    assert metadata['reference'] == service.status()['reference']
    if not missing:
        assert port.closed and not port.writes


def test_stop_run_waits_for_restoration_and_reports_error(tmp_path, monkeypatch):
    import threading
    entered, finished = threading.Event(), threading.Event()
    class RestoringSession(MarkerSession):
        restoring = False
        def reference_status(self):
            return {'enabled': True, 'restoring': self.restoring,
                    'error': None if self.restoring else 'Rückstellung nicht bestätigt – Gerät prüfen (gsv-registers.py)'}
        def stop(self, reason='bediener'):
            self.restoring = True
            entered.set()
            finished.wait(1)
            self.restoring = False
    service = _confirmed_service(tmp_path, monkeypatch, RestoringSession)
    service.start_run()
    stopper = threading.Thread(target=service.stop_run)
    stopper.start()
    assert entered.wait(1)
    assert service.status()['state'] == 'running'
    assert service.status()['reference']['restoring']
    finished.set()
    stopper.join(1)
    assert service.status()['state'] == 'stopped'
    assert service.status()['error'] == 'Rückstellung nicht bestätigt – Gerät prüfen (gsv-registers.py)'


def test_reference_stop_requested_before_waiting_for_camera_thread(tmp_path, monkeypatch):
    called = []
    class Session(MarkerSession):
        def request_reference_stop(self):
            called.append('reference')
        def stop(self, reason='bediener'):
            called.append('session')
    class Thread:
        def join(self, timeout):
            assert called == ['reference']
        def is_alive(self):
            return False
    service = _confirmed_service(tmp_path, monkeypatch, Session)
    service.start_run()
    thread = service._run_thread
    service._run_stop.set()
    thread.join(1)
    service._run_thread = Thread()
    service.stop_run()
    assert called == ['reference', 'session']


@pytest.mark.parametrize('schedule,reference', [('0.1:2', True), ('1:2', False)])
def test_invalid_reference_schedule_creates_no_run_directory(tmp_path, monkeypatch, schedule, reference):
    service = _confirmed_service(tmp_path, monkeypatch)
    with pytest.raises(LiveError):
        service.start_run(norm_schedule=schedule, reference=reference)
    assert list(tmp_path.glob('run-*')) == []


@pytest.mark.parametrize('point_text', [None, '{broken', '{}', 'null'])
def test_missing_or_invalid_restore_point_is_live_error(tmp_path, monkeypatch, point_text):
    from test_live_session import _session

    point = tmp_path / 'restore.json'
    if point_text is not None:
        point.write_text(point_text)
    monkeypatch.setattr('dispread.live.reference.DEFAULT_RESTORE_POINT', point)
    def factory(owner, profile, config, out_dir, **kw):
        return _session(tmp_path, [], **kw)
    monkeypatch.setattr('dispread.live.service.LiveSession', factory)
    service = LiveService(FakeOwner(), tmp_path, serial_opener=lambda: pytest.fail('Port opened'))
    service._state, service._profile_path = 'confirmed', tmp_path / 'profile.json'
    with pytest.raises(LiveError, match='Lauf nicht gestartet'):
        service.start_run(norm_schedule='2:20')
    assert service.status()['state'] == 'confirmed'


@pytest.mark.parametrize('mismatch', [False, True])
def test_server_close_restores_active_schedule_or_retains_read_only_abort(tmp_path, monkeypatch, mismatch):
    import json

    from test_live_reference import RegisterPort, _wait_for
    from test_live_session import _session

    port = RegisterPort()
    if mismatch:
        port.dp = 2
    point = tmp_path / 'restore.json'
    point.write_text(json.dumps({'register': {'norm': {'daten': [80, 27, 228]}, 'dpoint': {'daten': [1]}}}))
    monkeypatch.setattr('dispread.live.reference.DEFAULT_RESTORE_POINT', point)
    monkeypatch.setattr('dispread.gsv2as_serial._sleep', lambda _s: None)
    def factory(owner, profile, config, out_dir, **kw):
        return _session(tmp_path, [], **kw)
    monkeypatch.setattr('dispread.live.service.LiveSession', factory)
    service = LiveService(FakeOwner(), tmp_path, serial_opener=lambda: port)
    service._state, service._profile_path = 'confirmed', tmp_path / 'profile.json'
    try:
        service.start_run(norm_schedule='2:20')
        if mismatch:
            _wait_for(lambda: bool(service.status()['reference'].get('schedule_aborted')))
            assert service.status()['reference']['enabled'] and not port.closed
        else:
            _wait_for(lambda: port.norm != [80, 27, 228])
    finally:
        service.close()
    assert port.closed
    meta = json.loads(service._session.session_path.read_text())
    if mismatch:
        assert 'Rueckstellpunkt' in meta['reference']['schedule_aborted']
        assert not any(b[0] in (16, 17) for b in port.writes)
    else:
        assert port.norm == [80, 27, 228] and port.dp == 1
        assert meta['reference']['restore_verification']['matches_restore_point']


def test_confirmation_refuses_outdated_revision_in_same_session(tmp_path, proposal):
    # Ein neuer Versuch kann dieselbe Sitzungs-ID tragen.
    proposal["live_tracking"] = {"proposal_revision": "current"}
    service = ready_service(tmp_path, proposal)
    status = service.status()
    assert status["setup"]["proposal_revision"] == "current"
    for revision in ("previous", None):
        with pytest.raises(LiveError, match="geaendert"):
            service.confirm(session_id=status["session_id"], proposal_revision=revision,
                            confirmed_by="Operator", format_checked=True)
    assert service.status()["state"] == "setup_ready"
    assert not (tmp_path / status["session_id"] / "profile.json").exists()


def test_confirmation_refused_while_running_even_with_current_proposal(tmp_path, proposal):
    service = ready_service(tmp_path, proposal)
    status = service.status()
    service._state = "running"
    with pytest.raises(LiveError):
        service.confirm(session_id=status["session_id"], confirmed_by="Operator", format_checked=True)
    with pytest.raises(LiveError, match="Lauf zuerst beenden"):
        service.start_setup()
    assert service.status()["state"] == "running"
    assert not (tmp_path / status["session_id"] / "profile.json").exists()


def test_current_revision_confirms_and_tracking_status_reaches_page(tmp_path):
    from test_live_setup_tracking import _propose

    _, _, proposal = _propose(tmp_path)
    service = ready_service(tmp_path, proposal)
    status = service.status()
    assert status["setup"]["checks"]["nachfuehrung"] == "OK"
    assert service.status(full=True)["tracking_reasons"]["rahmen_mehrdeutig"] == "rahmenmerkmale nicht eindeutig zugeordnet"
    service.confirm(session_id=status["session_id"], proposal_revision=status["setup"]["proposal_revision"],
                    confirmed_by="Operator", format_checked=True)
    assert service.status()["state"] == "confirmed"
    assert service.status()["run"] is None
    assert service.status()["profile"]["tracking_mode"] == "rahmenbereiche"
    from dispread.session_profile import SessionProfile

    profile = SessionProfile.load(tmp_path / status["session_id"] / "profile.json")
    assert profile.live_tracking == proposal["live_tracking"]

    from types import SimpleNamespace

    tracking = {"mode": "rahmenbereiche", "version": 1,
                "regions": len(profile.live_tracking["proposal"]["regions"])}
    service._session = SimpleNamespace(latest=None, summary={}, tracking=tracking, latest_age_s=lambda: None)
    service._run_dir = tmp_path / "run-01"
    assert service.status()["run"]["tracking"] == tracking


def test_tracking_failure_reason_reaches_setup_status(tmp_path, proposal):
    proposal["setup_checks"]["checks"]["nachfuehrung"] = {
        "status": "FEHLER", "reason": "zu wenige geeignete Rahmenbereiche",
    }
    proposal["setup_checks"]["overall"] = "FEHLER"
    service = ready_service(tmp_path, proposal)
    status = service.status()
    assert status["setup"]["check_reasons"]["nachfuehrung"] == "zu wenige geeignete Rahmenbereiche"
    with pytest.raises(LiveError, match="FEHLER"):
        service.confirm(session_id=status["session_id"], confirmed_by="Operator", format_checked=True)


def test_old_confirmed_profile_exposes_tracking_mode_before_run(tmp_path, proposal):
    service = ready_service(tmp_path, proposal)
    service.confirm(session_id=service.status()["session_id"], confirmed_by="Operator", format_checked=True)
    status = service.status()
    assert status["run"] is None
    assert status["profile"]["tracking_mode"] == "ecc_alt"


def test_tracking_reasons_only_in_explicit_full_status(tmp_path):
    from dispread.workbench.fields import REASONS

    service = LiveService(FakeOwner(), tmp_path)
    assert "tracking_reasons" not in service.status()
    assert service.status(full=True)["tracking_reasons"] == REASONS
    assert "tracking_reasons" not in service.status()


@pytest.mark.parametrize('enabled', [False, True])
def test_diagnostics_option_and_mark_status(tmp_path, monkeypatch, enabled):
    class Session(MarkerSession):
        def __init__(self, *args, diagnostics=False, **kw):
            super().__init__(*args, **kw)
            self.enabled = diagnostics
            self.last_mark = None
            self.diagnose_kopie = False

        def mark(self, text):
            self.last_mark = {'text': text, 'zeit': 'meldezeit_bediener'}

        def diagnostics_status(self):
            return {'enabled': self.enabled, 'saved': 3}

    service = _confirmed_service(tmp_path, monkeypatch, Session)
    with pytest.raises(LiveError, match='kein Lauf'):
        service.mark('zu frueh')
    service.start_run(reference=False, diagnostics=enabled)
    try:
        service.mark('Abdeckung')
        status = service.status()
        assert status['diagnostics'] == {'enabled': enabled, 'saved': 3}
        assert status['last_mark'] == {'text': 'Abdeckung', 'zeit': 'meldezeit_bediener'}
        assert status['diagnose_kopie'] is False
        service._session.diagnose_kopie = True
        assert service.status()['diagnose_kopie'] is True
    finally:
        service.stop_run()
    with pytest.raises(LiveError, match='kein Lauf'):
        service.mark('zu spaet')


def test_diagnostic_copy_stays_visible_during_new_setup(tmp_path, monkeypatch):
    from types import SimpleNamespace

    service = LiveService(FakeOwner(), tmp_path, setup_runner=lambda **kw: {})
    previous = SimpleNamespace(diagnose_kopie=True)
    service._session = previous
    service.start_setup()
    assert service.status()['diagnose_kopie'] is True
    previous.diagnose_kopie = False
    assert service.status()['diagnose_kopie'] is False


def test_leftover_diagnostics_are_reported_on_start_and_in_status(tmp_path, caplog):
    staging = tmp_path / 'shm'
    abandoned = staging / 'dispread-diagnose-old-run-01'
    abandoned.mkdir(parents=True)
    (abandoned / '0001.png').write_bytes(b'png')
    (abandoned / 'images.jsonl').write_bytes(b'index')
    service = LiveService(FakeOwner(), tmp_path / 'live', diagnostic_staging_root=staging)
    assert str(abandoned) in caplog.text and '8' in caplog.text
    assert service.status()['diagnostic_leftovers'] == [{'path': str(abandoned), 'bytes': 8}]
    (abandoned / '0002.png').write_bytes(b'next')
    assert service.status()['diagnostic_leftovers'][0]['bytes'] == 12
    service.close()
    assert abandoned.is_dir()


def test_close_waits_for_previous_and_current_diagnostic_copies(tmp_path, monkeypatch):
    import threading

    from test_live_session import _session, embed

    from dispread.live import diagnostics

    monkeypatch.setattr(diagnostics, 'read_mem_available', lambda: 2_000_000_000, raising=False)
    entered, release = threading.Event(), threading.Event()
    original_copy = diagnostics.shutil.copyfile
    def delayed_copy(src, dst):
        entered.set()
        assert release.wait(3)
        return original_copy(src, dst)
    monkeypatch.setattr(diagnostics.shutil, 'copyfile', delayed_copy)
    sessions = []
    for n in range(2):
        root = tmp_path / str(n)
        root.mkdir()
        session = _session(root, [embed('+ 1.2345 ')], diagnostics=True, diagnostic_staging_root=root)
        session.start()
        session.step()
        session.mark('Test')
        if n == 0:
            session.stop()
        sessions.append(session)
    service = LiveService(FakeOwner(), tmp_path, diagnostic_staging_root=tmp_path)
    service._diagnostic_copies, service._session = sessions[:1], sessions[1]
    service._state, service._run_stop = 'running', threading.Event()
    closed = threading.Event()
    def close():
        try:
            service.close()
        finally:
            closed.set()
    thread = threading.Thread(target=close)
    try:
        assert entered.wait(1)
        thread.start()
        assert not closed.wait(0.05)
    finally:
        release.set()
        thread.join(3)
    assert closed.is_set()
    for session in sessions:
        assert session._diagnostics.wait(3)
        assert session.diagnostics_status()['copied']
        assert not session._diagnostics.staging.exists()


def test_close_uses_one_bounded_copy_deadline_and_logs_timeout(tmp_path, monkeypatch, caplog):
    from types import SimpleNamespace

    from dispread.live import service as module

    monkeypatch.setattr(module, 'DIAGNOSTIC_CLOSE_TIMEOUT_S', 0.05, raising=False)
    waits = []
    def stalled(timeout):
        waits.append(timeout)
        time.sleep(timeout)
        return False
    service = LiveService(FakeOwner(), tmp_path, diagnostic_staging_root=tmp_path)
    first = SimpleNamespace(diagnose_kopie=True, wait_diagnostics=stalled)
    second = SimpleNamespace(diagnose_kopie=True, wait_diagnostics=stalled)
    service._diagnostic_copies, service._session = [first], second
    start = time.monotonic()
    service.close()
    assert waits and sum(waits) <= 0.05
    assert time.monotonic() - start < 0.3
    assert 'Diagnose' in caplog.text and 'Zeitlimit' in caplog.text


def test_edit_regions_revises_checks_overlays_and_confirmed_profile(tmp_path):
    import json

    import cv2
    import numpy as np
    from test_live_setup_tracking import _propose

    from dispread.session_profile import SessionProfile

    image, quad, proposal = _propose(tmp_path)
    service = ready_service(tmp_path, proposal)
    status = service.status()
    revision = status['setup']['proposal_revision']
    regions = proposal['live_tracking']['proposal']['regions']
    centres = [r['centre'] for r in regions]
    source = tmp_path / status['session_id'] / 'setup' / 'overlay_source.png'
    original = source.read_bytes()
    # Alle Bereiche entfernen: echtes FEHLER-Urteil samt neuem Overlay.
    result = service.edit_regions(proposal_revision=revision, add=[], remove=list(range(len(regions))))
    status = service.status()
    assert status['setup']['checks']['nachfuehrung'] == status['setup']['overall'] == 'FEHLER'
    assert source.read_bytes() != original
    assert result['proposal_revision'] == status['setup']['proposal_revision'] != revision
    assert status['setup']['regions'] == []
    assert result['centre_results'] == []
    with pytest.raises(LiveError, match='geaendert'):
        service.edit_regions(proposal_revision=revision, add=centres, remove=[])
    # Dasselbe Standbild reparieren, strukturfreien Zeichenpunkt ablehnen.
    middle = list(np.rint(np.asarray(quad).mean(axis=0)).astype(int).tolist())
    result = service.edit_regions(proposal_revision=result['proposal_revision'], add=centres + [middle], remove=[])
    assert result['centre_results'][-1]['reason'] == 'zu_wenig_struktur'
    assert service.status()['setup']['overall'] == 'OK'
    assert service.status()['setup']['regions'] == regions
    assert service.status()['setup']['centre_results'] == result['centre_results']
    saved = json.loads((source.parent / 'proposal.json').read_text())
    assert saved['live_tracking']['auswahl'] == 'manuell'
    assert len(saved['live_tracking']['edits']) == 2 * len(regions) + 1
    assert all(edit['at_utc'].endswith('+00:00') for edit in saved['live_tracking']['edits'])
    assert saved['live_tracking']['frame_sha256'] == proposal['live_tracking']['frame_sha256']
    service.confirm(session_id=status['session_id'], proposal_revision=result['proposal_revision'],
                    confirmed_by='Operator', format_checked=True)
    profile = SessionProfile.load(source.parent.parent / 'profile.json')
    assert profile.live_tracking == saved['live_tracking']
    assert cv2.imread(str(tmp_path / 'still.png')).shape == image.shape


@pytest.mark.parametrize('state', ['idle', 'running', 'setup_running', 'setup_failed'])
def test_edit_regions_refuses_missing_or_busy_proposal(tmp_path, state):
    service = LiveService(FakeOwner(), tmp_path)
    service._state = state
    with pytest.raises(LiveError):
        service.edit_regions(proposal_revision='old', add=[[1, 2]], remove=[])


@pytest.mark.parametrize(('add', 'remove'), [
    ([[1, 2]] * 25, []), ([[1, 2]] * 51, []), ([], [999]), ([], [-1]), ([], [True]),
    ([], [0, 0]), ([[float('nan'), 2]], []), ([[True, 2]], []), ([[1]], []), ('bad', []), ([], 'bad'), ([], []),
])
def test_edit_regions_refuses_invalid_edits_without_revision_change(tmp_path, add, remove):
    from test_live_setup_tracking import _propose

    _, _, proposal = _propose(tmp_path)
    service = ready_service(tmp_path, proposal)
    before = service.status()
    with pytest.raises(LiveError):
        service.edit_regions(proposal_revision=before['setup']['proposal_revision'], add=add, remove=remove)
    assert service.status()['setup']['proposal_revision'] == before['setup']['proposal_revision']


def test_edit_regions_enforces_cumulative_edit_limit_and_still_hash(tmp_path):
    from test_live_setup_tracking import _propose

    _, _, proposal = _propose(tmp_path)
    service = ready_service(tmp_path, proposal)
    block = proposal['live_tracking']
    block['edits'] = [{'action': 'add'}] * 50
    with pytest.raises(LiveError, match='50'):
        service.edit_regions(proposal_revision=block['proposal_revision'], add=[], remove=[0])
    block['edits'] = []
    (tmp_path / 'still.png').write_bytes(b'changed')
    with pytest.raises(LiveError, match='Einrichtungsbild'):
        service.edit_regions(proposal_revision=block['proposal_revision'], add=[], remove=[0])


def test_region_edits_require_current_tracking_proposal_and_are_blocked_during_run(tmp_path, proposal):
    service = ready_service(tmp_path, proposal)
    with pytest.raises(LiveError, match='Rahmenvorschlag'):
        service.edit_regions(proposal_revision='missing', add=[[1, 2]], remove=[])
    proposal['live_tracking'] = {'proposal_revision': 'current'}
    service._state = 'running'
    with pytest.raises(LiveError, match='Lauf zuerst beenden'):
        service.edit_regions(proposal_revision='current', add=[[1, 2]], remove=[])
    assert service._proposal == proposal


def test_run_status_explains_recent_reader_cause(tmp_path):
    from types import SimpleNamespace

    service = LiveService(FakeOwner(), tmp_path)
    service._run_dir = tmp_path / 'run'
    service._session = SimpleNamespace(
        latest=None, summary={}, latest_age_s=lambda: None,
        rejection_causes=lambda: {'frames': 4, 'window_s': 10.0, 'limited': False,
                                 'causes': [{'reason': 'leser:leerzelle_gestoert:14', 'count': 1, 'fraction': 0.25}]},
    )
    result = service.status()['run']['rejection_causes']
    assert result['frames'] == 4
    assert result['causes'][0]['cell'] == 14
    assert result['causes'][0]['fraction'] == 0.25
    assert 'Kratzer' in result['causes'][0]['explanation']
