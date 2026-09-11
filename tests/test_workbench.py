import asyncio
import copy
import json
import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from dispread.frames import open_source
from dispread.frames.synthetic_source import render_display
from dispread.layout import DisplayLayout
from dispread.rectify import rectify
from dispread.workbench import fields
from dispread.workbench.auth import Sessions
from dispread.workbench.controller import CLIP_QUEUE_DEPTH, MAX_GEOMETRY_CYCLES, Controller
from dispread.workbench.profiles import DEFAULT, atomic_json, validate
from dispread.workbench.vision import fit_ocr_box, fit_quad_in_region


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


def _frame():
    """Ein Livebild wie es publish() waehrend einer Clipaufnahme erhaelt."""
    return np.full((720, 960, 3), 120, np.uint8)


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


def test_freeze_returns_all_current_candidates(tmp_path, monkeypatch):
    """Bedienerwunsch: alle gerade erkannten Kandidaten sollen im Editor
    einzeln anklickbar sein, nicht nur die eine beste Vermutung."""
    c = ready_controller(tmp_path, live=False, confirmed=False)
    boxes = [(96, 72, 480, 288), (10, 10, 100, 50)]
    monkeypatch.setattr("dispread.workbench.controller.find_display_candidates", lambda *_a, **_k: boxes)
    c.publish(np.full((720, 960, 3), 120, np.uint8), {"timebase": "synthetic"})

    frozen = c.command("freeze")

    np.testing.assert_allclose(frozen["candidates"], [[x / 960, y / 720, w / 960, h / 720] for x, y, w, h in boxes])


def test_freeze_populates_candidates_even_when_none_were_cached(tmp_path, monkeypatch):
    """Nach einer Bestaetigung in derselben Sitzung pflegt publish() keine
    Kandidaten mehr (nur waehrend unbestaetigt). Ein erneutes Editieren muss
    trotzdem anklickbare Kandidaten zeigen - freeze() holt sie dann einmalig
    nach, statt mit einer leeren Liste dazustehen."""
    c = ready_controller(tmp_path, live=True, confirmed=True)
    assert c.candidates == ()  # bestaetigt: publish() haelt keine Kandidaten
    boxes = [(96, 72, 480, 288)]
    monkeypatch.setattr("dispread.workbench.controller.find_display_candidates", lambda *_a, **_k: boxes)

    frozen = c.command("freeze")

    np.testing.assert_allclose(frozen["candidates"], [[96 / 960, 72 / 720, 480 / 960, 288 / 720]])


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


def test_confirmed_roi_in_run_mode_skips_full_frame_candidate_search(tmp_path, monkeypatch):
    """Im run-Modus bleibt jede Vergleichssuche abgeschaltet - der
    Produktionsmodus braucht die volle Bildrate, keinen visuellen
    Geometrie-Vergleich (OQ-24)."""
    c = ready_controller(tmp_path, live=False, confirmed=True)
    c.mode = "run"

    def unexpected(*_a, **_k):
        raise AssertionError("run-Modus darf keine Vergleichssuche ausloesen")

    monkeypatch.setattr("dispread.workbench.controller.find_display_candidates", unexpected)
    monkeypatch.setattr("dispread.workbench.controller.fit_quad_in_region", unexpected)
    c.publish(np.full((720, 960, 3), 120, np.uint8), {"timebase": "synthetic"})


def test_confirmed_roi_throttles_verification_search_outside_run_mode(tmp_path, monkeypatch):
    """Bedienerrueckmeldung: nach einem Neustart mit bereits bestaetigter ROI
    lief die Vergleichssuche nie mehr - kein visueller Hinweis mehr, ob die
    alte Geometrie noch zur aktuellen Szene passt. Sie muss deshalb in
    setup/annotate weiterlaufen, aber gedrosselt statt bei jedem Bild
    (CANDIDATE_INTERVAL_S), sonst kehrt die mit OQ-24 behobene
    Vollbildsuche-pro-Bild-Kosten zurueck."""
    c = ready_controller(tmp_path, live=False, confirmed=True)
    calls = []
    monkeypatch.setattr(
        "dispread.workbench.controller.fit_quad_in_region",
        lambda *_a, **_k: calls.append(1) or None,
    )
    image = np.full((720, 960, 3), 120, np.uint8)

    c.publish(image, {"timebase": "synthetic"})
    assert len(calls) == 1  # erstes Bild nach dem Laden: sofort verglichen

    c.publish(image, {"timebase": "synthetic"})
    assert len(calls) == 1  # innerhalb der Drosselfrist kein zweiter Aufruf

    c.last_candidates_at = 0.0  # Drosselfenster simuliert abgelaufen
    c.publish(image, {"timebase": "synthetic"})
    assert len(calls) == 2


def test_confirmed_roi_never_triggers_the_whole_frame_candidate_search(tmp_path, monkeypatch):
    """Bedienerbefund: die wieder aktivierte Vergleichssuche zeigte gelbe
    Boxen um andere Anzeigen/Objekte im Bild, weil sie das ganze Bild
    absuchte statt nur die Umgebung der bestaetigten ROI. Eine bestaetigte
    Geometrie darf deshalb nie wieder `find_display_candidates` (Vollbild)
    ausloesen - nur die auf `config["roi"]` eingegrenzte `fit_quad_in_region`."""
    c = ready_controller(tmp_path, live=False, confirmed=True)

    def unexpected(*_a, **_k):
        raise AssertionError("bestaetigte ROI darf keine Vollbildsuche mehr ausloesen")

    monkeypatch.setattr("dispread.workbench.controller.find_display_candidates", unexpected)
    image = np.full((720, 960, 3), 120, np.uint8)

    c.publish(image, {"timebase": "synthetic"})
    c.last_candidates_at = 0.0
    c.publish(image, {"timebase": "synthetic"})


def test_confirmed_roi_verification_search_is_scoped_to_the_confirmed_region(tmp_path, monkeypatch):
    """Die Vergleichssuche bekommt die bestaetigte ROI als Suchfenster
    (`fit_quad_in_region`'s `hint_box`), nicht das ganze Bild - genau das
    grenzt Nebenanzeigen/andere Objekte aus (Konzept.md §7)."""
    c = ready_controller(tmp_path, live=False, confirmed=True)
    seen_hints = []
    monkeypatch.setattr(
        "dispread.workbench.controller.fit_quad_in_region",
        lambda _image, hint_box, layout=None: seen_hints.append(hint_box) or None,
    )

    c.publish(np.full((720, 960, 3), 120, np.uint8), {"timebase": "synthetic"})

    assert seen_hints == [c.config["roi"]]


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


def test_loading_a_confirmed_profile_warns_about_unverified_geometry(tmp_path):
    """Bedienerrueckmeldung: nach einem Neustart wirkte eine bereits
    bestaetigte Geometrie wie stillschweigend weiter gueltig, ohne jeden
    Hinweis, dass sie noch nicht gegen die aktuelle Szene verglichen wurde."""
    root = tmp_path / "data"
    c = Controller(root)
    c.publish(np.zeros((100, 200, 3), np.uint8), {"timebase": "synthetic"})
    frozen = c.command("freeze")
    c.command("roi", {"id": frozen["id"], "roi": [0.1, 0.2, 0.5, 0.5]})
    c.applied = c.revision
    c.command("profile.save")

    reloaded = Controller(root)

    assert any("noch nicht gegen die aktuelle Szene verglichen" in x["message"] for x in reloaded.logs)


def test_startup_requires_re_confirmation_of_a_previously_confirmed_profile(tmp_path):
    """Bedienerwunsch: jede Sitzung soll frisch mit laufender Erkennung
    beginnen statt eine alte Bestaetigung stillschweigend fuer den
    run-Modus weiterzuverwenden (Konzept.md §4 - Bestaetigung ist der Akt
    eines Menschen, auch nach einem Neustart). roi/roi_quad/ocr_box bleiben
    als Startpunkt fuer eine schnelle erneute Bestaetigung erhalten, und die
    gespeicherte Datei selbst bleibt unveraendert."""
    root = tmp_path / "data"
    c = Controller(root)
    c.publish(np.zeros((100, 200, 3), np.uint8), {"timebase": "synthetic"})
    frozen = c.command("freeze")
    quad = [[0.1, 0.2], [0.6, 0.2], [0.6, 0.7], [0.1, 0.7]]
    c.command("roi", {"id": frozen["id"], "quad": quad, "ocr_box": [0.1, 0.1, 0.8, 0.8]})
    c.applied = c.revision
    c.command("profile.save")
    saved_on_disk = json.loads((root / "profiles" / "default.json").read_text())
    assert saved_on_disk["confirmed"] is True  # gespeicherte Datei bleibt unveraendert

    reloaded = Controller(root)

    assert reloaded.config["confirmed"] is False
    np.testing.assert_allclose(reloaded.config["roi_quad"], quad)
    assert reloaded.config["ocr_box"] == pytest.approx([0.1, 0.1, 0.8, 0.8])
    assert reloaded.dirty is True
    assert any("muss diese Sitzung erneut" in x["message"] for x in reloaded.logs)
    with pytest.raises(ValueError):
        reloaded.command("mode", {"value": "run"})


def test_startup_does_not_touch_an_already_unconfirmed_profile(tmp_path):
    """Nur eine tatsaechlich geladene Bestaetigung wird zurueckgesetzt - ein
    frisches, nie bestaetigtes Profil darf nicht faelschlich als 'dirty'
    oder mit einer irrefuehrenden Warnung starten."""
    root = tmp_path / "data"
    c = Controller(root)
    c.applied = c.revision
    c.command("profile.save")

    reloaded = Controller(root)

    assert reloaded.config["confirmed"] is False
    assert reloaded.dirty is False
    assert not any("muss diese Sitzung erneut" in x["message"] for x in reloaded.logs)


def test_freeze_offers_a_smaller_default_ocr_box_without_persisting_it(tmp_path):
    """Bedienerbefund: der unberuehrte [0,0,1,1]-Default deckt sich direkt nach
    einer frischen roi-Bestaetigung mit roi_quad - das Verklicken beim
    Verschieben. `freeze` bietet deshalb im Editierzustand einen kleineren
    Startwert an, ohne self.config oder eine Bestaetigung zu aendern."""
    c = Controller(tmp_path)
    c.publish(np.zeros((100, 200, 3), np.uint8), {"timebase": "synthetic"})

    frozen = c.command("freeze")

    assert frozen["ocr_box"] == pytest.approx([0.15, 0.15, 0.7, 0.7])
    assert c.config["ocr_box"] == DEFAULT["ocr_box"]


def test_freeze_keeps_a_confirmed_ocr_box_unchanged(tmp_path):
    c = Controller(tmp_path)
    c.config["ocr_box"] = [0.2, 0.3, 0.4, 0.4]
    c.publish(np.zeros((100, 200, 3), np.uint8), {"timebase": "synthetic"})

    frozen = c.command("freeze")

    assert frozen["ocr_box"] == pytest.approx([0.2, 0.3, 0.4, 0.4])


def _mask_iou(mask_a, mask_b):
    intersection = int((mask_a & mask_b).sum())
    union = int((mask_a | mask_b).sum())
    return intersection / union if union else 0.0


def test_fit_quad_in_region_finds_a_panel_within_the_hint():
    """Grober Bedienerhinweis (Taste R) um ein achsparalleles Panel - das
    Quad muss die Panelflaeche gut treffen und geordnet (TL/TR/BR/BL) sein."""
    width, height = 500, 300
    image = np.full((height, width, 3), 30, np.uint8)
    x, y, w, h = 150, 80, 220, 120
    cv2.rectangle(image, (x, y), (x + w, y + h), (200, 200, 200), -1)
    hint = [(x - 20) / width, (y - 20) / height, (w + 40) / width, (h + 40) / height]

    quad = fit_quad_in_region(image, hint)

    assert quad is not None
    pixel_quad = np.array([[px * width, py * height] for px, py in quad], dtype=np.int32)
    mask_a = np.zeros((height, width), np.uint8)
    cv2.fillPoly(mask_a, [pixel_quad], 1)
    mask_b = np.zeros((height, width), np.uint8)
    mask_b[y : y + h, x : x + w] = 1
    assert _mask_iou(mask_a, mask_b) > 0.85


def test_fit_quad_in_region_follows_a_tilted_panel():
    """Nicht nur achsparallel - roi_quad muss ein echtes, ggf. rotiertes
    Viereck liefern (Konzept: manual_roi bleibt Primaerpfad, hier nur der
    Vorschlag fuer eine perspektivisch verzerrte Anzeige)."""
    width, height = 500, 300
    image = np.full((height, width, 3), 30, np.uint8)
    panel = np.array([[160, 70], [365, 90], [375, 210], [140, 195]], dtype=np.int32)
    cv2.fillConvexPoly(image, panel, (200, 200, 200))
    hint = [100 / width, 50 / height, 300 / width, 200 / height]

    quad = fit_quad_in_region(image, hint)

    assert quad is not None
    pixel_quad = np.array([[px * width, py * height] for px, py in quad], dtype=np.int32)
    mask_a = np.zeros((height, width), np.uint8)
    cv2.fillPoly(mask_a, [pixel_quad], 1)
    mask_b = np.zeros((height, width), np.uint8)
    cv2.fillPoly(mask_b, [panel], 1)
    assert _mask_iou(mask_a, mask_b) > 0.85


def test_fit_quad_in_region_returns_none_without_a_candidate():
    """Ein Fehlschlag ist inert - kein Kandidat im markierten Bereich darf nie
    zu einer erfundenen Geometrie fuehren (AGENTS.md: kein Raten)."""
    image = np.full((300, 500, 3), 30, np.uint8)

    assert fit_quad_in_region(image, [0.2, 0.2, 0.3, 0.3]) is None


def test_fit_quad_in_region_uses_layout_to_widen_aspect_tolerance():
    """Mit Profil/Layout wird das erwartete Seitenverhaeltnis zusaetzlich aus
    `DisplayLayout.n_cells` abgeleitet statt nur der festen 1.5..8.0-Spanne
    (hier: neun Ziffernstellen plus Vorzeichen, Seitenverhaeltnis > 8)."""
    width, height = 600, 200
    image = np.full((height, width, 3), 30, np.uint8)
    x, y, w, h = 30, 40, 500, 60
    cv2.rectangle(image, (x, y), (x + w, y + h), (200, 200, 200), -1)
    hint = [(x - 10) / width, (y - 10) / height, (w + 20) / width, (h + 20) / height]
    layout = DisplayLayout(digits=9, decimals=2, has_sign=True, unit=None)

    assert fit_quad_in_region(image, hint) is None
    assert fit_quad_in_region(image, hint, layout=layout) is not None


def test_fit_quad_in_region_ignores_unrelated_objects_outside_the_hint():
    """Bedienerbefund: die auf eine grosszuegig bestaetigte ROI eingegrenzte
    Vergleichssuche schlug andere Bildschirme im Bild vor. Ursache: die
    Aufweitung um ~25% des Hinweisbereichs kann bei einem grosszuegigen
    Hinweis genug Raum fuer ein unbeteiligtes, zufaellig rechteckigeres
    Objekt lassen - eine reine (Rechteckigkeit, Flaeche)-Bewertung zieht dann
    ein kleines, perfektes Rechteck einem grossen, aber leicht unregelmaessig
    geformten Pruefling vor. Ein Kandidat muss deshalb zusaetzlich den
    ungepolsterten Hinweisbereich selbst ausreichend ueberdecken."""
    width, height = 960, 720
    image = np.full((height, width, 3), 40, np.uint8)

    # Pruefling mit gekappten Ecken - realistisch unregelmaessiger als eine
    # ideale Box, damit seine Rechteckigkeit unter der eines sauberen
    # Ablenkerobjekts liegt.
    dx, dy, dw, dh = 270, 100, 460, 290
    cut = 60
    device_points = np.array(
        [
            [dx + cut, dy], [dx + dw - cut, dy], [dx + dw, dy + cut], [dx + dw, dy + dh - cut],
            [dx + dw - cut, dy + dh], [dx + cut, dy + dh], [dx, dy + dh - cut], [dx, dy + cut],
        ],
        np.int32,
    )
    cv2.fillConvexPoly(image, device_points, (200, 200, 200))
    hint = [dx / width, dy / height, dw / width, dh / height]

    # Kleines, perfekt rechteckiges Ablenkerobjekt ("anderer Bildschirm") im
    # aufgeweiteten Suchfenster, aber ausserhalb des Hinweisbereichs selbst.
    mx, my, mw, mh = 159, 32, 100, 350
    assert mx + mw < dx  # keine Ueberlappung mit dem Pruefling
    cv2.rectangle(image, (mx, my), (mx + mw, my + mh), (220, 220, 220), -1)

    quad = fit_quad_in_region(image, hint)

    assert quad is not None
    pixel_quad = np.array([[px * width, py * height] for px, py in quad], dtype=np.int32)
    mask_a = np.zeros((height, width), np.uint8)
    cv2.fillPoly(mask_a, [pixel_quad], 1)
    mask_device = np.zeros((height, width), np.uint8)
    cv2.fillConvexPoly(mask_device, device_points, 1)
    mask_distractor = np.zeros((height, width), np.uint8)
    mask_distractor[my : my + mh, mx : mx + mw] = 1
    assert _mask_iou(mask_a, mask_device) > 0.85
    assert _mask_iou(mask_a, mask_distractor) == 0.0


def _box_iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    intersection = max(0.0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0.0, min(ay + ah, by + bh) - max(ay, by))
    union = aw * ah + bw * bh - intersection
    return intersection / union if union else 0.0


@pytest.mark.parametrize(
    ("value", "digits", "decimals", "has_sign", "unit"),
    [
        (-12.34, 5, 2, True, "mV"),
        (12.34, 5, 2, True, "mV"),
        (0.5, 4, 1, False, "N"),
        (-999.9, 4, 1, True, None),
    ],
)
def test_fit_ocr_box_matches_the_rendered_digit_area(value, digits, decimals, has_sign, unit):
    """Auf dem entzerrten Ausschnitt muss der Vorschlag Vorzeichen+Ziffern
    treffen und Einheitentext/Rand aussparen - ohne beide zu kennen."""
    layout = DisplayLayout(digits=digits, decimals=decimals, has_sign=has_sign, unit=unit)
    image, _, area = render_display(value, layout)
    height, width = image.shape[:2]
    x, y, area_w, area_h = area
    quad = [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]
    crop = rectify(image, quad, target_size=(400, 160))

    box = fit_ocr_box(crop.image, layout=layout)

    assert box is not None
    expected = (x / width, y / height, area_w / width, area_h / height)
    assert _box_iou(box, expected) > 0.6


def test_fit_ocr_box_returns_none_for_a_blank_crop():
    """Zu wenig Evidenz (kein Blob) - Ablehnung statt Raten."""
    blank = np.full((160, 400), 40, np.uint8)

    assert fit_ocr_box(blank) is None


_REAL_ANNOTATIONS = [
    Path("var/workbench/annotations/6ffc561bb18f47f0aa14648b1f904dcd"),
    Path("var/workbench/annotations/8a18ee05e31241b9b6702c5bb904ec97"),
]


@pytest.mark.skipif(
    not all(p.exists() for p in _REAL_ANNOTATIONS),
    reason="reale Annotationen aus var/ nicht im Checkout vorhanden (nicht versioniert)",
)
@pytest.mark.parametrize("folder", _REAL_ANNOTATIONS, ids=lambda p: p.name)
def test_fit_ocr_box_against_real_annotations(folder):
    """Validierung gegen die zwei realen Aufnahmen aus dieser Sitzung
    (docs/PLAN_2026-09-10-workbench-editor.md). Gemessenes Ergebnis: IoU 0,0
    auf beiden Bildern, siehe docs/VALIDATION.md und OQ-25 - der Ausschnitt
    enthaelt neben der Hauptanzeige "V" eine baugleiche Nebenanzeige "A"
    (Konzept.md §7: Haupt-/Nebenanzeige-Verwechslung ist ohne weiteren
    Bedienerhinweis strukturell nicht aufloesbar), und in einem Bild zusaetzlich
    einen grossflaechigen Glanzfleck. Die Schwelle ist die **gemessene**, nicht
    eine vorab erhoffte - dieser Test bewacht nur, dass die Funktion an echten
    Daten nicht abstuerzt und ein plausibel geformtes Ergebnis liefert."""
    annotation = json.loads((folder / "annotation.json").read_text())
    image = cv2.imread(str(folder / "image.png"))
    height, width = image.shape[:2]
    quad_px = [(px * width, py * height) for px, py in annotation["roi_quad"]]
    layout = DisplayLayout.from_dict(annotation["profile"]["layout"])
    crop = rectify(image, quad_px, target_size=(400, 160))

    box = fit_ocr_box(crop.image, layout=layout)

    assert box is not None
    x, y, w, h = box
    assert 0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1
    iou = _box_iou(box, annotation["ocr_box"])
    assert iou >= 0.0  # gemessener Bestand, siehe docs/VALIDATION.md


def test_command_rejects_the_removed_roi_suggest_op(tmp_path):
    """R-Zug samt eigenem Hinweisbereich ist durch das anklickbare
    Kandidaten-Browsing in Stufe A ersetzt (siehe Plan
    wen-ich-die-roi-logical-sphinx) - der Op bleibt bewusst entfernt."""
    c = Controller(tmp_path)
    with pytest.raises(ValueError, match="Unbekannter Befehl: roi.suggest"):
        c.command("roi.suggest", {"id": "irrelevant", "hint_box": [0.2, 0.2, 0.3, 0.3]})


def test_ocr_suggest_returns_a_box_for_the_given_quad_without_persisting(tmp_path):
    layout = DisplayLayout(digits=5, decimals=2, has_sign=True, unit="mV")
    image, _, area = render_display(-12.34, layout)
    image_height, image_width = image.shape[:2]
    x, y, w, h = area
    # ROI mit etwas Rand um den Ziffernbereich, wie ein Bediener sie ziehen
    # wuerde (analog test_inner_ocr_box_calibrates_grid_inside_padded_roi) -
    # belegt die Vorschlagsqualitaet, nicht nur die Antwortform.
    padding_x, padding_y = 30, 20
    outer = [x - padding_x, y - padding_y, w + 2 * padding_x, h + 2 * padding_y]
    c = Controller(tmp_path)
    c.config["layout"] = layout.to_dict()
    c.publish(image, {"timebase": "synthetic"})
    frozen = c.command("freeze")
    quad = [
        [outer[0] / image_width, outer[1] / image_height],
        [(outer[0] + outer[2]) / image_width, outer[1] / image_height],
        [(outer[0] + outer[2]) / image_width, (outer[1] + outer[3]) / image_height],
        [outer[0] / image_width, (outer[1] + outer[3]) / image_height],
    ]

    result = c.command("ocr.suggest", {"id": frozen["id"], "quad": quad})

    assert result["ocr_box"] is not None
    assert c.config["ocr_box"] == DEFAULT["ocr_box"]
    expected = (padding_x / outer[2], padding_y / outer[3], w / outer[2], h / outer[3])
    assert _box_iou(result["ocr_box"], expected) > 0.6


def test_ocr_suggest_reports_no_candidate_without_raising(tmp_path):
    c = Controller(tmp_path)
    c.publish(np.full((300, 500, 3), 30, np.uint8), {"timebase": "synthetic"})
    frozen = c.command("freeze")
    quad = [[0, 0], [1, 0], [1, 1], [0, 1]]

    result = c.command("ocr.suggest", {"id": frozen["id"], "quad": quad})

    assert result["ocr_box"] is None
    assert any("kein Kandidat" in x["message"] for x in c.logs)


def test_ocr_suggest_does_not_hold_the_controller_lock_during_detection(tmp_path, monkeypatch):
    """Kernbehebung des gemeldeten Bugs: die OpenCV-Arbeit lief zuvor
    vollstaendig innerhalb des Controller-Locks (anders als publish()) - ein
    langsamer Suchlauf liess so genug Zeit fuer eine Bedienereingabe, die die
    eintreffende Vermutung ueberschrieb. `status` muss waehrenddessen sofort
    antworten."""
    layout = DisplayLayout(digits=5, decimals=2, has_sign=True, unit="mV")
    image, _, _ = render_display(-12.34, layout)
    c = Controller(tmp_path)
    c.config["layout"] = layout.to_dict()
    c.publish(image, {"timebase": "synthetic"})
    frozen = c.command("freeze")
    entered, release = threading.Event(), threading.Event()

    def slow_fit_ocr_box(*_a, **_k):
        entered.set()
        assert release.wait(2)
        return None

    monkeypatch.setattr("dispread.workbench.controller.fit_ocr_box", slow_fit_ocr_box)
    quad = [[0, 0], [1, 0], [1, 1], [0, 1]]
    worker = threading.Thread(target=c.command, args=("ocr.suggest", {"id": frozen["id"], "quad": quad}))
    worker.start()
    assert entered.wait(1)
    started = time.monotonic()
    c.command("status")
    elapsed = time.monotonic() - started
    release.set()
    worker.join(2)

    assert elapsed < 0.05
    assert not worker.is_alive()


def test_ground_truth_text_is_stored_with_the_annotation(tmp_path):
    """Stufe 3: getippter Anzeigewert macht (Bild, roi_quad, ocr_box, layout,
    Ground Truth)-Tupel moeglich - rein additiv, keine Erkennungsgarantie."""
    c = Controller(tmp_path)
    c.publish(np.zeros((100, 200, 3), np.uint8), {"timebase": "synthetic"})
    c.command("mode", {"value": "annotate"})
    frozen = c.command("freeze")

    c.command("roi", {"id": frozen["id"], "roi": [0.1, 0.2, 0.5, 0.5], "ground_truth_text": " -012.34 mV "})

    annotation = json.loads(next((tmp_path / "annotations").glob("*/annotation.json")).read_text())
    assert annotation["ground_truth_text"] == " -012.34 mV "


def test_ground_truth_text_defaults_to_none_when_not_supplied(tmp_path):
    c = Controller(tmp_path)
    c.publish(np.zeros((100, 200, 3), np.uint8), {"timebase": "synthetic"})
    c.command("mode", {"value": "annotate"})
    frozen = c.command("freeze")

    c.command("roi", {"id": frozen["id"], "roi": [0.1, 0.2, 0.5, 0.5]})

    annotation = json.loads(next((tmp_path / "annotations").glob("*/annotation.json")).read_text())
    assert annotation["ground_truth_text"] is None


def test_clip_schreibt_manifest_mit_einem_label_fuer_alle_frames(tmp_path):
    controller = ready_controller(tmp_path)
    controller.command("mode", {"value": "annotate"})
    controller.command(
        "clip.start",
        {"device_id": "geraet-1", "ground_truth_text": "28,80", "seconds": 60},
    )
    for _ in range(3):
        controller.publish(_frame(), {"timebase": "synthetic", "uncertainty_ns": None})
    controller.command("clip.stop")
    controller.drain_clip_writer()  # deterministisch statt sleep

    clips = sorted((controller.root / "clips").iterdir())
    assert len(clips) == 1
    manifest = json.loads((clips[0] / "clip.json").read_text())
    assert manifest["schema_version"] == 1
    assert manifest["ground_truth_text"] == "28,80"
    assert manifest["device_id"] == "geraet-1"
    assert len(manifest["frames"]) == 3
    assert manifest["dropped_frames"] == 0
    for entry in manifest["frames"]:
        assert (clips[0] / entry["file"]).exists()


def test_clip_braucht_bestaetigte_geometrie_und_geraeteangabe(tmp_path):
    controller = ready_controller(tmp_path / "unconfirmed", live=False, confirmed=False)
    with pytest.raises(ValueError, match="bestaetigt"):
        controller.command("clip.start", {"device_id": "g", "ground_truth_text": "1", "seconds": 5})

    controller = ready_controller(tmp_path / "confirmed")
    controller.command("mode", {"value": "annotate"})
    with pytest.raises(ValueError, match="Geraetekennung"):
        controller.command("clip.start", {"device_id": "", "ground_truth_text": "1", "seconds": 5})
    with pytest.raises(ValueError, match="Sollwert"):
        controller.command("clip.start", {"device_id": "g", "ground_truth_text": "  ", "seconds": 5})


def test_clip_ist_ueber_replay_wieder_lesbar(tmp_path):
    """Aufnahme und Wiedergabe muessen dasselbe Format meinen."""
    controller = ready_controller(tmp_path)
    controller.command("mode", {"value": "annotate"})
    controller.command(
        "clip.start", {"device_id": "geraet-1", "ground_truth_text": "11,00", "seconds": 60}
    )
    controller.publish(_frame(), {"timebase": "synthetic", "uncertainty_ns": None})
    controller.command("clip.stop")
    controller.drain_clip_writer()

    clip = next(iter(sorted((controller.root / "clips").iterdir())))
    source = open_source(f"replay://{clip}")
    source.open()
    frames = list(source.frames())
    source.close()
    assert len(frames) == 1
    assert frames[0].raw_metadata["ground_truth"]["text"] == "11,00"


def test_clip_zaehlt_frame_bei_revisionswechsel_waehrend_der_gedrosselten_ocr(tmp_path, monkeypatch):
    """Aendert sich revision zwischen der Bildarbeit ausserhalb des Locks und
    dem naechsten gesperrten Abschnitt (z. B. durch layout.set/roi/
    camera.set_many waehrend eine Aufnahme laeuft), darf publish() den
    uebersprungenen Frame nicht stillschweigend verlieren - er muss in
    clip["dropped"] auftauchen (Review-Fund, Important 2). Dieser Test trifft
    den FRUEHEN Abbruch innerhalb des should_read-Zweigs (direkt um die
    OCR-Auswertung), der zweite Revisionswechsel-Test unten trifft den
    SPAETEN Abbruch am Ende von publish()."""
    controller = ready_controller(tmp_path, confirmed=True)
    controller.command("mode", {"value": "annotate"})
    controller.command("clip.start", {"device_id": "geraet-1", "ground_truth_text": "3,00", "seconds": 60})
    # OCR_INTERVAL_S-Drossel erzwungen aufgehoben, damit should_read in
    # publish() sicher True ist - der zu treffende Zweig liegt VOR diesem
    # "haette-die-Drossel-verpasst"-Fall.
    controller.last_ocr_at = 0.0

    import dispread.workbench.controller as controller_module

    original_roi_quad = controller_module.roi_quad

    def bump_revision_then_compute(image, config):
        # should_read ist hier True (last_ocr_at auf 0 erzwungen) - die
        # Revision aendert sich also VOR dem ersten gesperrten Abschnitt in
        # publish() (Zeile ~864).
        controller.revision += 1
        return original_roi_quad(image, config)

    monkeypatch.setattr(controller_module, "roi_quad", bump_revision_then_compute)

    controller.publish(_frame(), {"timebase": "synthetic", "uncertainty_ns": None})

    snap = controller.snapshot()
    assert snap["clip"]["frames"] == 0
    assert snap["clip"]["dropped"] == 1


def test_clip_zaehlt_frame_bei_revisionswechsel_am_ende_von_publish(tmp_path, monkeypatch):
    """Wie oben, aber should_read ist diesmal False (OCR_INTERVAL_S noch nicht
    abgelaufen) - die Revision aendert sich dann erst kurz vor dem SPAETEN,
    gesperrten Abschnitt am Ende von publish(). Auch dieser Pfad darf den
    Frame nicht stillschweigend verlieren."""
    controller = ready_controller(tmp_path, confirmed=True)  # live=True: erste Ablesung schon gecacht
    controller.command("mode", {"value": "annotate"})
    controller.command("clip.start", {"device_id": "geraet-1", "ground_truth_text": "4,00", "seconds": 60})

    import dispread.workbench.controller as controller_module

    original_roi_quad = controller_module.roi_quad

    def bump_revision_then_compute(image, config):
        controller.revision += 1
        return original_roi_quad(image, config)

    monkeypatch.setattr(controller_module, "roi_quad", bump_revision_then_compute)

    # Direkt nach ready_controller() liegt last_ocr_at im selben Sekundenbruchteil -
    # should_read (Drossel OCR_INTERVAL_S=0.2s) ist also False, der Frueh-Abbruch
    # in should_read wird gar nicht erst betreten.
    controller.publish(_frame(), {"timebase": "synthetic", "uncertainty_ns": None})

    snap = controller.snapshot()
    assert snap["clip"]["frames"] == 0
    assert snap["clip"]["dropped"] == 1


def test_clip_zaehlt_verworfene_bilder_statt_zu_blockieren_wenn_die_queue_voll_laeuft(tmp_path, monkeypatch):
    """Der eigentliche Grund fuer den Schreib-Thread/die begrenzte Queue: laeuft
    sie voll, weil der Schreiber (hier absichtlich blockiert) nicht mitkommt,
    muss publish() zaehlen statt zu warten oder still zu verwerfen - und das
    Manifest muss dieselbe Zahl tragen wie der Live-Status waehrend der
    Aufnahme."""
    block = threading.Event()
    original_imwrite = cv2.imwrite

    def blocking_imwrite(path, image):
        block.wait(timeout=5)
        return original_imwrite(path, image)

    monkeypatch.setattr(cv2, "imwrite", blocking_imwrite)

    controller = ready_controller(tmp_path)
    controller.command("mode", {"value": "annotate"})
    controller.command(
        "clip.start",
        {"device_id": "geraet-1", "ground_truth_text": "1,00", "seconds": 60},
    )
    try:
        # Der Schreiber haengt im ersten Bild; deutlich mehr Bilder als
        # CLIP_QUEUE_DEPTH fuellen die Queue sicher, unabhaengig von Timing.
        for _ in range(CLIP_QUEUE_DEPTH + 20):
            controller.publish(_frame(), {"timebase": "synthetic", "uncertainty_ns": None})

        dropped_live = controller.snapshot()["clip"]["dropped"]
        assert dropped_live > 0
    finally:
        block.set()

    controller.command("clip.stop")
    controller.drain_clip_writer()

    clips = sorted((controller.root / "clips").iterdir())
    manifest = json.loads((clips[0] / "clip.json").read_text())
    assert manifest["dropped_frames"] == dropped_live
    assert len(manifest["frames"]) + manifest["dropped_frames"] == CLIP_QUEUE_DEPTH + 20
    for entry in manifest["frames"]:
        assert (clips[0] / entry["file"]).exists()


def test_close_beendet_eine_laufende_aufnahme_ohne_bereits_eingereihte_bilder_zu_verlieren(tmp_path, monkeypatch):
    """Ruling 1 (Review-Fund, jetzt als Test statt Ad-hoc-Skript): close() muss
    auf den Schreib-Thread warten, bevor der Prozess beendet - sonst koennte
    er enden, waehrend im gerade geschriebenen clip.json gelistete Bilder noch
    nicht auf der Platte liegen. Kein vorheriger clip.stop/drain_clip_writer -
    close() muss das selbststaendig sauber abschliessen."""
    original_imwrite = cv2.imwrite

    def slow_imwrite(path, image):
        time.sleep(0.05)
        return original_imwrite(path, image)

    monkeypatch.setattr(cv2, "imwrite", slow_imwrite)

    controller = ready_controller(tmp_path)
    controller.command("mode", {"value": "annotate"})
    controller.command(
        "clip.start", {"device_id": "geraet-1", "ground_truth_text": "5,00", "seconds": 60}
    )
    for _ in range(5):
        controller.publish(_frame(), {"timebase": "synthetic", "uncertainty_ns": None})

    controller.close()

    clips = sorted((controller.root / "clips").iterdir())
    manifest = json.loads((clips[0] / "clip.json").read_text())
    assert manifest["dropped_frames"] == 0
    assert len(manifest["frames"]) == 5
    for entry in manifest["frames"]:
        assert (clips[0] / entry["file"]).exists()


def test_rasches_stop_start_verwechselt_schreiber_und_warteschlange_nicht(tmp_path, monkeypatch):
    """Ruling 2 (Review-Fund, jetzt als Test statt reiner Codeinspektion): der
    Schreiber liest die ihm beim Start uebergebene Queue, nicht self.clip_queue.
    Ohne diese Bindung wuerde ein Stop/Start-Paar kurz hintereinander den noch
    leerraeumenden alten Thread auf die neue Queue umbiegen - die alte Aufnahme
    liesse dann im eigenen Manifest gelistete Bilder unbeschrieben zurueck."""
    original_imwrite = cv2.imwrite

    def slow_imwrite(path, image):
        time.sleep(0.03)
        return original_imwrite(path, image)

    monkeypatch.setattr(cv2, "imwrite", slow_imwrite)

    controller = ready_controller(tmp_path)
    controller.command("mode", {"value": "annotate"})

    controller.command(
        "clip.start", {"device_id": "geraet-a", "ground_truth_text": "1,00", "seconds": 60}
    )
    for _ in range(5):
        controller.publish(_frame(), {"timebase": "synthetic", "uncertainty_ns": None})
    controller.command("clip.stop")  # Sentinel eingereiht; der alte Schreiber laeuft noch

    controller.command(
        "clip.start", {"device_id": "geraet-b", "ground_truth_text": "2,00", "seconds": 60}
    )
    for _ in range(3):
        controller.publish(_frame(), {"timebase": "synthetic", "uncertainty_ns": None})
    controller.command("clip.stop")

    controller.drain_clip_writer()  # muss BEIDE Threads einsammeln, nicht nur den letzten

    clip_dirs = sorted((controller.root / "clips").iterdir())
    assert len(clip_dirs) == 2
    for directory in clip_dirs:
        manifest = json.loads((directory / "clip.json").read_text())
        assert manifest["dropped_frames"] == 0
        assert len(manifest["frames"]) > 0
        for entry in manifest["frames"]:
            assert (directory / entry["file"]).exists()
