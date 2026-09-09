import asyncio
import copy
import json
import os
import threading
import time

import numpy as np
import pytest

from dispread.frames.synthetic_source import render_display
from dispread.layout import DisplayLayout
from dispread.workbench import fields
from dispread.workbench.auth import Sessions
from dispread.workbench.controller import MAX_GEOMETRY_CYCLES, Controller
from dispread.workbench.profiles import DEFAULT, atomic_json, validate


@pytest.mark.parametrize(
    "patch",
    [
        {"schema_version": 4},
        {"roi": [-0.1, 0, 0.5, 0.5]},
        {"roi": [0, 0, 2, 1]},
        {"ocr_box": [0.2, 0.2, 0.9, 0.5]},
        {"confirmed": True},
        {"role": "unknown"},
        {"version": -1},
    ],
)
def test_profile_validation(patch):
    profile = copy.deepcopy(DEFAULT)
    profile.update(patch)
    with pytest.raises(ValueError):
        validate(profile)


def test_profiles_external_conflict_and_invalid_file(tmp_path):
    c = Controller(tmp_path)
    c.applied = c.revision
    c.command("profile.save")
    c.command("camera.set", {"key": "Contrast", "value": 1.4})
    disk = copy.deepcopy(c.saved)
    disk["camera"]["controls"]["Contrast"] = 0.8
    atomic_json(c.path, disk)
    c.watch_profile()
    c.watch_profile()
    assert c.conflict
    assert c.config["camera"]["controls"]["Contrast"] == 1.4
    with pytest.raises(ValueError):
        c.command("profile.save")
    c.command("profile.resolve", {"value": "disk"})
    assert c.config["camera"]["controls"]["Contrast"] == 0.8
    assert not c.dirty
    c.path.write_text("{")
    c.watch_profile()
    c.watch_profile()
    assert c.config["camera"]["controls"]["Contrast"] == 0.8
    assert any("nicht übernommen" in x["message"] for x in c.logs)


def test_frozen_annotation_matches_original(tmp_path):
    c = Controller(tmp_path)
    image = np.full((100, 200, 3), 100, np.uint8)
    c.publish(image, {"SensorTimestamp": 123456, "timebase": "sensor_boottime", "uncertainty_ns": None})
    c.command("mode", {"value": "annotate"})
    frozen = c.command("freeze")
    assert len(frozen["ocr_grid"]["cells"]) == c.config["layout"]["digits"]
    assert frozen["ocr_grid"]["sign"] is not None
    assert len(frozen["ocr_grid"]["samples"]) == 7
    assert frozen["ocr_grid"]["decimal_after"] == 2
    c.publish(np.zeros_like(image), {"timebase": "synthetic"})
    c.command("roi", {"id": frozen["id"], "roi": [0.1, 0.2, 0.5, 0.5]})
    annotation = next((tmp_path / "annotations").glob("*/annotation.json"))
    data = json.loads(annotation.read_text())
    assert data["schema_version"] == 2
    assert data["frame_sequence"] == 1
    assert data["metadata"]["SensorTimestamp"] == 123456
    import cv2

    saved = cv2.imread(str(annotation.parent / "image.png"))
    assert np.array_equal(saved, image)
    assert data["roi"] == pytest.approx([0.1, 0.2, 0.5, 0.5])
    np.testing.assert_allclose(data["roi_quad"], [[0.1, 0.2], [0.6, 0.2], [0.6, 0.7], [0.1, 0.7]])
    assert data["coordinate_system"] == "normalized_quad_tl_tr_br_bl"
    assert data["ocr_box"] == pytest.approx([0, 0, 1, 1])
    assert data["ocr_box_coordinate_system"] == "rectified_roi_normalized_xywh"


def test_profile_v1_rectangle_is_migrated_to_quad():
    profile = copy.deepcopy(DEFAULT)
    profile.pop("roi_quad")
    profile.pop("ocr_box")
    profile["schema_version"] = 1
    profile["roi"] = [0.1, 0.2, 0.5, 0.4]
    profile["confirmed"] = True

    migrated = validate(profile)
    assert migrated["schema_version"] == 3
    np.testing.assert_allclose(migrated["roi_quad"], [[0.1, 0.2], [0.6, 0.2], [0.6, 0.6], [0.1, 0.6]])
    np.testing.assert_allclose(migrated["ocr_box"], [0, 0, 1, 1])


def test_profile_v2_is_migrated_with_full_ocr_box():
    profile = copy.deepcopy(DEFAULT)
    profile.pop("ocr_box")
    profile["schema_version"] = 2

    migrated = validate(profile)

    assert migrated["schema_version"] == 3
    np.testing.assert_allclose(migrated["ocr_box"], [0, 0, 1, 1])


def test_self_intersecting_quad_is_rejected():
    profile = copy.deepcopy(DEFAULT)
    profile["roi"] = [0.1, 0.1, 0.8, 0.8]
    profile["roi_quad"] = [[0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.1, 0.9]]
    profile["confirmed"] = True
    with pytest.raises(ValueError, match="konvex"):
        validate(profile)


def test_edit_refuses_changed_profile(tmp_path):
    c = Controller(tmp_path)
    c.publish(np.zeros((100, 200, 3), np.uint8), {"timebase": "synthetic"})
    frozen = c.command("freeze")
    c.command("camera.set", {"key": "Contrast", "value": 1.2})
    with pytest.raises(ValueError):
        c.command("roi", {"id": frozen["id"], "roi": [0, 0, 1, 1]})


def test_frozen_edit_tracks_layout_changes_and_remains_confirmable(tmp_path):
    c = Controller(tmp_path)
    c.publish(np.zeros((100, 200, 3), np.uint8), {"timebase": "synthetic"})
    frozen = c.command("freeze")

    c.command("layout.set", {"key": "digits", "value": 4})
    changed = c.command("layout.set", {"key": "decimals", "value": 1})

    assert len(changed["ocr_grid"]["cells"]) == 4
    assert changed["ocr_grid"]["decimal_after"] == 2
    result = c.command(
        "roi",
        {"id": frozen["id"], "quad": frozen["quad"], "ocr_box": frozen["ocr_box"]},
    )
    assert result["config"]["layout"]["digits"] == 4
    assert result["config"]["layout"]["decimals"] == 1


def test_roi_command_accepts_perspective_quad(tmp_path):
    c = Controller(tmp_path)
    c.publish(np.zeros((100, 200, 3), np.uint8), {"timebase": "synthetic"})
    frozen = c.command("freeze")
    quad = [[0.1, 0.2], [0.8, 0.1], [0.9, 0.7], [0.2, 0.8]]

    result = c.command("roi", {"id": frozen["id"], "quad": quad, "ocr_box": [0.1, 0.2, 0.8, 0.6]})

    np.testing.assert_allclose(result["config"]["roi_quad"], quad)
    np.testing.assert_allclose(result["config"]["roi"], [0.1, 0.1, 0.8, 0.7])
    np.testing.assert_allclose(result["config"]["ocr_box"], [0.1, 0.2, 0.8, 0.6])
    assert result["config"]["confirmed"] is True


def test_mode_and_unsupported_controls(tmp_path):
    c = Controller(tmp_path)
    with pytest.raises(ValueError):
        c.command("mode", {"value": "run"})
    c.capabilities = {"Contrast": [0, 4, 1]}
    with pytest.raises(ValueError):
        c.command("camera.set", {"key": "LensPosition", "value": 2})


def test_camera_set_many_is_one_atomic_revision(tmp_path):
    """Aufloesungswechsel darf nur einen Stream-Neuaufbau kosten (OQ-22:
    jeder Neuaufbau ist ein RP2040-Power-Zyklus, das Budget ist begrenzt).
    camera.set_many muss Breite und Hoehe in EINER Revision setzen statt
    zwei getrennten camera.set-Aufrufen, die der Worker als zwei
    Geometrieaenderungen sehen wuerde.
    """
    c = Controller(tmp_path)
    before = c.revision
    result = c.command("camera.set_many", {"values": {"width": 1280, "height": 960}})
    assert result["revision"] == before + 1
    assert (result["config"]["camera"]["width"], result["config"]["camera"]["height"]) == (1280, 960)
    assert result["config"]["confirmed"] is False


def test_geometry_budget_blocks_change_but_allows_same_value(tmp_path):
    """OQ-22: der RP2040-Bridge-Chip haengt sich nach ~20-25 Power-Zyklen auf.
    Ist das Budget erschoepft, muss eine echte Aufloesungs-/Bildraten-
    aenderung verweigert werden - ein Wiederwaehlen der bereits aktiven
    Werte (kein neuer Zyklus) darf dagegen weiter funktionieren.
    """
    c = Controller(tmp_path)
    c.geometry_cycles = MAX_GEOMETRY_CYCLES
    width, height = c.config["camera"]["width"], c.config["camera"]["height"]
    with pytest.raises(ValueError, match="Power-Zyklus-Budget"):
        c.command("camera.set_many", {"values": {"width": width + 1, "height": height}})
    # Dieselbe Aufloesung erneut waehlen loest keinen neuen Zyklus aus und
    # bleibt deshalb erlaubt.
    result = c.command("camera.set_many", {"values": {"width": width, "height": height}})
    assert result["config"]["camera"]["width"] == width


def test_geometry_cycles_survive_process_restart_same_boot(tmp_path):
    """OQ-22: der RP2040-Zyklenzaehler gehoert zum Boot, nicht zum Prozess.
    Ein Controller-Neustart (gleicher Host, gleiche Boot-ID) darf den
    Zaehler nicht auf 0 zuruecksetzen - sonst waeren nach einem
    dispread-Neustart faelschlich wieder volle 15 Zyklen "frei", obwohl der
    RP2040 sie laengst verbraucht hat.
    """
    first = Controller(tmp_path)
    if first.boot_id is None:
        pytest.skip("keine Boot-ID auf diesem System verfuegbar")
    first.geometry_cycles = 10
    first._save_geometry_cycles()

    second = Controller(tmp_path)
    assert second.geometry_cycles == 10


def test_geometry_cycles_reset_on_new_boot(tmp_path):
    """Eine andere Boot-ID (echter Reboot) muss den Zaehler zuruecksetzen."""
    (tmp_path / "camera_cycles.json").write_text('{"boot_id": "not-the-real-one", "cycles": 999}')
    c = Controller(tmp_path)
    assert c.geometry_cycles == 0


def test_session_expiry_rate_limit():
    s = Sessions()
    for _ in range(5):
        assert s.allow_attempt("local")
    assert not s.allow_attempt("local")
    token = s.create()
    assert s.get(token)
    s.sessions[token]["created"] -= 9 * 3600
    assert s.get(token) is None


def test_shell_persistence_resize_and_cleanup(tmp_path):
    from dispread.workbench.terminals import Terminals

    async def check():
        manager = Terminals(tmp_path, tmp_path / "control.sock")
        terminal = manager.create()
        try:
            terminal.resize(92, 28)
            await terminal.write(b"printf 'WORKBENCH_OK\\n'; stty size\n")
            deadline = time.monotonic() + 3
            while b"28 92" not in terminal.buffer and time.monotonic() < deadline:
                await asyncio.sleep(0.02)
            assert b"WORKBENCH_OK" in terminal.buffer
            assert b"28 92" in terminal.buffer
            # No WebSocket attached; shell remains available.
            assert terminal.exit_code is None
            await terminal.write(b"sleep 20\n")
            await asyncio.sleep(0.1)
            await terminal.write(b"\x03")
            await terminal.write(b"echo AFTER_INTERRUPT\n")
            deadline = time.monotonic() + 3
            while b"AFTER_INTERRUPT" not in terminal.buffer and time.monotonic() < deadline:
                await asyncio.sleep(0.02)
            assert b"AFTER_INTERRUPT" in terminal.buffer
        finally:
            await manager.close()
        with pytest.raises(ProcessLookupError):
            os.kill(terminal.pid, 0)

    asyncio.run(check())


def ready_controller(tmp_path, live=True, confirmed=True):
    """Controller mit Capabilities, bestaetigter ROI und Livebild - ohne Kamera."""
    c = Controller(tmp_path / "data", simulate=True)
    c.capabilities = {
        "AeEnable": [False, True, True],
        "ExposureTime": [100, 100000, 10000],
        "AnalogueGain": [1.0, 16.0, 1.0],
        "Contrast": [0.1, 4.0, 1.0],
    }
    if confirmed:
        c.config["roi"], c.config["confirmed"] = [0.2, 0.3, 0.6, 0.3], True
    if live:
        c.publish(
            np.full((720, 960, 3), 120, np.uint8),
            {"timebase": "synthetic", "ExposureTime": 9000, "AnalogueGain": 1.5},
        )
    c.applied = c.revision
    return c


def test_freeze_starts_from_last_detected_candidate(tmp_path, monkeypatch):
    """Ein frisches, nie bestaetigtes Profil startet beim Editieren an der
    zuletzt sichtbaren gelben Vorschlagsbox statt an einer festen Standardbox -
    sonst verliert der Bediener beim Editieren-Start die bereits erkannte
    Position (Bedienerrueckmeldung)."""
    c = ready_controller(tmp_path, live=False, confirmed=False)
    monkeypatch.setattr("dispread.workbench.controller.find_display_candidates", lambda *_: [(96, 72, 480, 288)])
    c.publish(np.full((720, 960, 3), 120, np.uint8), {"timebase": "synthetic"})

    frozen = c.command("freeze")

    assert frozen["roi"] == pytest.approx([0.1, 0.1, 0.5, 0.4])
    assert [pt for corner in frozen["quad"] for pt in corner] == pytest.approx([0.1, 0.1, 0.6, 0.1, 0.6, 0.5, 0.1, 0.5])


def test_field_rows_offer_only_valid_choices(tmp_path):
    c = ready_controller(tmp_path)
    state = c.snapshot()
    table = {row["key"]: row for row in fields.rows(state)}
    assert {
        "mode",
        "role",
        "resolution",
        "fps",
        "AeEnable",
        "focus",
        "profile",
        "roi",
        "layout.digits",
        "layout.decimals",
        "layout.has_sign",
        "layout.unit",
        "layout.sign_cell_ratio",
        "reading.value",
        "reading.gate",
        "reading.evidence",
    } <= set(table)
    for row in table.values():
        if row["kind"] == "choice":
            assert len(row["options"]) >= (1 if row["key"] == "profile" else 2)
            assert row["value"] in [option["value"] for option in row["options"]], row["key"]
        elif row["kind"] == "number":
            assert row["min"] <= float(row["value"]) <= row["max"], row["key"]
            assert row["presets"]
    assert table["mode"]["value"] == "setup"
    assert table["profile"]["value"] == "default"


def test_every_offered_option_is_accepted_by_controller(tmp_path):
    """Keine angebotene Auswahl darf am Controller scheitern."""
    reference = ready_controller(tmp_path)
    for row in fields.rows(reference.snapshot()):
        if row["kind"] == "choice":
            cases = [option["ops"] for option in row["options"] if not option["disabled"]]
        elif row["kind"] == "number":
            cases = [[[row["op"], {"key": row["arg"], "value": preset["raw"]}]] for preset in row["presets"]]
        else:
            cases = []
        for index, operations in enumerate(cases):
            c = ready_controller(tmp_path / f"{row['key']}-{index}")
            if row["disabled"]:
                continue
            for op, args in operations:
                c.command(op, args)


def test_manual_exposure_rows_locked_until_automatic_is_off(tmp_path):
    c = ready_controller(tmp_path)
    locked = {row["key"]: row for row in fields.rows(c.snapshot())}
    assert locked["ExposureTime"]["disabled"] and locked["ExposureTime"]["reason"]
    assert locked["AnalogueGain"]["disabled"]
    assert not locked["Contrast"]["disabled"]
    c.command("camera.set", {"key": "AeEnable", "value": False})
    c.applied = c.revision
    free = {row["key"]: row for row in fields.rows(c.snapshot())}
    assert not free["ExposureTime"]["disabled"]
    assert float(free["ExposureTime"]["value"]) == c.config["camera"]["controls"]["ExposureTime"]
    assert fields.run_blocked(c.snapshot()) is None
    assert not [option for option in free["mode"]["options"] if option["disabled"]]


def test_actions_are_gated_like_the_controller(tmp_path):
    c = ready_controller(tmp_path)
    gate = {action["hotkey"]: action for action in fields.actions(c.snapshot())}
    assert gate["a"]["enabled"] and gate["s"]["enabled"]
    assert not gate["y"]["enabled"] and not gate["c"]["enabled"]
    assert not gate["d"]["enabled"] and not gate["r"]["enabled"]
    with pytest.raises(ValueError):
        c.command("auto.accept")
    c.auto = {"state": "proposal", "controls": {"AeEnable": True, "Contrast": 1.0}}
    assert next(a for a in fields.actions(c.snapshot()) if a["hotkey"] == "y")["enabled"]
    c.command("auto.accept")
    c.applied = c.revision
    assert next(a for a in fields.actions(c.snapshot()) if a["hotkey"] == "r")["enabled"]
    c.conflict = copy.deepcopy(c.config)
    conflicted = {action["hotkey"]: action for action in fields.actions(c.snapshot())}
    assert conflicted["d"]["enabled"] and conflicted["l"]["enabled"]
    assert not conflicted["s"]["enabled"]


def test_profile_list_skips_invalid_names(tmp_path):
    c = ready_controller(tmp_path)
    c.command("profile.save")
    c.command("profile.save", {"name": "gsv-2asd"})
    atomic_json(tmp_path / "data" / "profiles" / "nicht gueltig.json", DEFAULT)
    names = c.snapshot()["profiles"]
    assert names == ["default", "gsv-2asd"]
    profile_row = next(row for row in fields.rows(c.snapshot()) if row["key"] == "profile")
    assert [option["value"] for option in profile_row["options"]] == names


def test_layout_rows_preserve_custom_unit_and_disable_impossible_formats(tmp_path):
    c = ready_controller(tmp_path)
    c.command("layout.set", {"key": "unit", "value": "psi"})
    c.command("layout.set", {"key": "decimals", "value": 4})
    table = {row["key"]: row for row in fields.rows(c.snapshot())}

    assert "psi" in [option["value"] for option in table["layout.unit"]["options"]]
    digit_three = next(option for option in table["layout.digits"]["options"] if option["value"] == "3")
    assert digit_three["disabled"]
    assert digit_three["reason"]


@pytest.mark.parametrize(
    ("key", "value"),
    [("digits", 0), ("decimals", 5), ("unknown", 1)],
)
def test_layout_set_rejects_impossible_format(tmp_path, key, value):
    c = ready_controller(tmp_path)
    with pytest.raises(ValueError):
        c.command("layout.set", {"key": key, "value": value})


def test_publish_reads_synthetic_display_and_exposes_evidence(tmp_path):
    layout = DisplayLayout(digits=5, decimals=2, has_sign=True, unit="mV")
    image, _, area = render_display(-12.34, layout)
    x, y, width, height = area
    image_height, image_width = image.shape[:2]

    c = Controller(tmp_path)
    c.config["layout"] = layout.to_dict()
    c.config["roi"] = [x / image_width, y / image_height, width / image_width, height / image_height]
    c.config["confirmed"] = True
    # Die Vorschau verlangt seit GATE_CONFIRM_FRAMES eine Mehrbildbestaetigung
    # gegen Displayflackern; last_ocr_at zuruecksetzen umgeht die 5-Hz-Drosselung,
    # damit der Test nicht auf echte Zeit warten muss.
    for _ in range(3):
        c.last_ocr_at = 0.0
        c.publish(image, {"timebase": "synthetic"})

    reading = c.snapshot()["reading"]
    assert reading["raw_text"] == "-012.34"
    assert reading["value"] == -12.34
    assert reading["unit"] == "mV"
    assert reading["unit_source"] == "profile"
    assert reading["digits"] == ["0", "1", "2", "3", "4"]
    assert len(reading["segments"]) == 5
    assert reading["gate_status"] == "valid"
    assert reading["gate_reasons"] == []
    assert reading["confidence_calibrated"] is False
    assert reading["released"] is False

    table = {row["key"]: row for row in fields.rows(c.snapshot())}
    assert "-012.34" in table["reading.value"]["display"]
    assert table["reading.gate"]["display"] == "valid; nicht freigegeben"
    assert "Stellen=01234" in table["reading.evidence"]["display"]


def test_inner_ocr_box_calibrates_grid_inside_padded_roi(tmp_path):
    layout = DisplayLayout(digits=5, decimals=2, has_sign=True, unit="mV")
    image, _, area = render_display(-12.34, layout)
    x, y, width, height = area
    image_height, image_width = image.shape[:2]
    padding_x, padding_y = 30, 20
    outer = [x - padding_x, y - padding_y, width + 2 * padding_x, height + 2 * padding_y]

    c = Controller(tmp_path)
    c.config["layout"] = layout.to_dict()
    c.config["roi"] = [
        outer[0] / image_width,
        outer[1] / image_height,
        outer[2] / image_width,
        outer[3] / image_height,
    ]
    c.config["ocr_box"] = [padding_x / outer[2], padding_y / outer[3], width / outer[2], height / outer[3]]
    c.config["confirmed"] = True

    c.publish(image, {"timebase": "synthetic"})

    assert c.snapshot()["reading"]["value"] == -12.34


def test_unknown_decimal_position_is_rejected_without_guessing(tmp_path):
    layout = DisplayLayout(digits=5, decimals=None, has_sign=True, unit="mV")
    image, _, area = render_display(-12, layout)
    x, y, width, height = area
    image_height, image_width = image.shape[:2]

    c = Controller(tmp_path)
    c.config["layout"] = layout.to_dict()
    c.config["roi"] = [x / image_width, y / image_height, width / image_width, height / image_height]
    c.config["confirmed"] = True
    c.publish(image, {"timebase": "synthetic"})

    reading = c.snapshot()["reading"]
    assert reading["value"] is None
    assert reading["released"] is False
    assert reading["gate_status"] == "unreadable"
    assert "decimal_point_unknown" in reading["gate_reasons"]
    assert "no_value" in reading["gate_reasons"]


def test_perspective_quad_is_rectified_before_reading(tmp_path):
    import cv2

    layout = DisplayLayout(digits=5, decimals=2, has_sign=True, unit="mV")
    image, _, area = render_display(-12.34, layout)
    height, width = image.shape[:2]
    source_corners = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    destination_corners = np.float32([[25, 15], [width - 20, 2], [width - 5, height - 8], [8, height - 20]])
    transform = cv2.getPerspectiveTransform(source_corners, destination_corners)
    warped = cv2.warpPerspective(image, transform, (width, height))
    x, y, roi_width, roi_height = area
    area_corners = np.float32([[[x, y], [x + roi_width, y], [x + roi_width, y + roi_height], [x, y + roi_height]]])
    quad = cv2.perspectiveTransform(area_corners, transform)[0]

    c = Controller(tmp_path)
    c.config["layout"] = layout.to_dict()
    c.config["roi_quad"] = [[float(px / width), float(py / height)] for px, py in quad]
    c.config["roi"] = [
        float(quad[:, 0].min() / width),
        float(quad[:, 1].min() / height),
        float(np.ptp(quad[:, 0]) / width),
        float(np.ptp(quad[:, 1]) / height),
    ]
    c.config["confirmed"] = True
    c.publish(warped, {"timebase": "synthetic"})

    assert c.snapshot()["reading"]["value"] == -12.34


def test_confirmed_roi_skips_full_frame_candidate_search(tmp_path, monkeypatch):
    c = ready_controller(tmp_path, live=False, confirmed=True)

    def unexpected(*_):
        raise AssertionError("bestaetigte ROI darf keine Vollbildsuche mehr ausloesen")

    monkeypatch.setattr("dispread.workbench.controller.find_display_candidates", unexpected)
    c.publish(np.full((720, 960, 3), 120, np.uint8), {"timebase": "synthetic"})


def test_snapshot_remains_responsive_during_image_processing(tmp_path, monkeypatch):
    c = ready_controller(tmp_path, live=False, confirmed=False)
    entered, release = threading.Event(), threading.Event()

    def slow_search(*_):
        entered.set()
        assert release.wait(2)
        return ()

    monkeypatch.setattr("dispread.workbench.controller.find_display_candidates", slow_search)
    worker = threading.Thread(
        target=c.publish,
        args=(np.full((720, 960, 3), 120, np.uint8), {"timebase": "synthetic"}),
    )
    worker.start()
    assert entered.wait(1)
    started = time.monotonic()
    c.snapshot()
    elapsed = time.monotonic() - started
    release.set()
    worker.join(2)

    assert elapsed < 0.05
    assert not worker.is_alive()


def test_cli_stop_uses_local_shutdown_command(monkeypatch, capsys):
    from dispread.workbench import cli

    calls = []

    async def fake_request(op, args=None, socket_path=None):
        calls.append((op, args, socket_path))
        return {"stopping": True}

    monkeypatch.setattr(cli, "request", fake_request)
    assert cli.main(["stop"]) == 0
    assert calls == [("server.stop", {}, None)]
    assert "stopping" in capsys.readouterr().out


def test_tui_uses_choices_and_reports_blocked_actions(tmp_path, monkeypatch):
    from dispread.workbench import tui

    state = ready_controller(tmp_path).snapshot()
    calls = []

    async def fake_request(op, args=None):
        calls.append((op, args))
        return state

    monkeypatch.setattr(tui, "request", fake_request)

    async def check():
        app = tui.WorkbenchTUI()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("enter")  # erste Zeile: modus
            await pilot.pause()
            assert isinstance(app.screen, tui.ChoiceScreen)
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            assert [args for op, args in calls if op == "mode"], calls
            await pilot.press("s")
            await pilot.pause()
            assert ("profile.save", {}) in calls
            await pilot.press("y")  # kein Vorschlag: nur Hinweis, kein Kommando
            await pilot.pause()
            assert not [op for op, _ in calls if op == "auto.accept"]

    asyncio.run(check())


def test_capture_request_release_on_failure(tmp_path):
    c = Controller(tmp_path)

    class Request:
        released = False

        def make_array(self, _):
            raise RuntimeError("failed")

        def release(self):
            self.released = True

    class Camera:
        request = Request()

        def capture_request(self, **_):
            return self.request

    camera = Camera()
    with pytest.raises(RuntimeError):
        c._capture(camera)
    assert camera.request.released


def test_auto_cancel_restores_original_controls(tmp_path, monkeypatch):
    c = Controller(tmp_path)
    c.config["roi"] = [0, 0, 1, 1]
    c.config["confirmed"] = True
    c.cancel_auto.set()
    calls = []

    class Camera:
        def set_controls(self, controls):
            calls.append(copy.deepcopy(controls))

    monkeypatch.setattr(c, "_capture", lambda _: (np.zeros((30, 60, 3), np.uint8), {"timebase": "synthetic"}))
    c._automatic(Camera())
    assert c.auto["state"] == "cancelled"
    assert calls[-1] == c.config["camera"]["controls"]
    assert c.applied == -1


def test_control_settle_requires_real_metadata(tmp_path, monkeypatch):
    c = Controller(tmp_path)
    monkeypatch.setattr(c, "_capture", lambda _: (None, {"ExposureTime": 100, "AnalogueGain": 1.0}))
    with pytest.raises(ValueError):
        c._settle(None, {"AeEnable": False, "ExposureTime": 20000, "AnalogueGain": 1.0})
    assert c._settle(None, {"AeEnable": False, "ExposureTime": 100, "AnalogueGain": 1.0})["ExposureTime"] == 100


def test_tls_shell_websocket_reconnect_and_logout(tmp_path):
    import ssl
    import subprocess

    import aiohttp
    from aiohttp import web

    from dispread.workbench.server import make_app
    from dispread.workbench.terminals import Terminals

    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )

    async def check():
        c = Controller(tmp_path / "data", simulate=True)
        terminals = Terminals(tmp_path, tmp_path / "control.sock")
        runner = web.AppRunner(make_app(c, terminals, verifier=lambda p: p == "test-only"))
        await runner.setup()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        base = f"https://127.0.0.1:{port}"
        headers = {"Origin": base}
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False), cookie_jar=aiohttp.CookieJar(unsafe=True)
            ) as client:
                login = await client.get(base + "/login")
                assert "password" in await login.text()
                assert (
                    await client.post(base + "/login", json={"password": "test-only"}, headers=headers)
                ).status == 200
                status = await (await client.get(base + "/status")).json()
                assert [row["key"] for row in status["setup"]["rows"]][:2] == ["mode", "role"]
                assert [action["hotkey"] for action in status["setup"]["actions"]][:1] == ["a"]
                headers["X-CSRF-Token"] = status["csrf"]
                data = await (await client.post(base + "/terminals", headers=headers)).json()
                url = base + "/terminals/" + data["id"] + "/ws"
                with pytest.raises(aiohttp.WSServerHandshakeError):
                    await client.ws_connect(url, headers={"Origin": "https://evil.invalid"})
                socket = await client.ws_connect(url, headers=headers)
                await socket.receive_json()  # reset
                await socket.send_bytes(b"printf 'WSS_ROUNDTRIP\\n'\n")
                output = b""
                async with asyncio.timeout(3):
                    while b"WSS_ROUNDTRIP" not in output:
                        message = await socket.receive()
                        if message.type == aiohttp.WSMsgType.BINARY:
                            output += message.data
                await socket.close()
                terminal = terminals.items[data["id"]]
                assert terminal.exit_code is None
                second = await client.ws_connect(url, headers=headers)
                assert (await second.receive_json())["reset"]
                assert (await client.post(base + "/logout", headers=headers)).status == 200
                async with asyncio.timeout(3):
                    async for _ in second:
                        pass
                assert terminal.exit_code is None
                assert (await client.get(base + "/status")).status == 401
        finally:
            await terminals.close()
            await runner.cleanup()

    asyncio.run(check())
