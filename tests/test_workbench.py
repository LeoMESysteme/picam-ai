import asyncio
import copy
import json
import os
import time

import numpy as np
import pytest

from dispread.workbench import fields
from dispread.workbench.auth import Sessions
from dispread.workbench.controller import Controller
from dispread.workbench.profiles import DEFAULT, atomic_json, validate


@pytest.mark.parametrize(
    "patch",
    [
        {"schema_version": 2},
        {"roi": [-0.1, 0, 0.5, 0.5]},
        {"roi": [0, 0, 2, 1]},
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
    c.publish(np.zeros_like(image), {"timebase": "synthetic"})
    c.command("roi", {"id": frozen["id"], "roi": [0.1, 0.2, 0.5, 0.5]})
    annotation = next((tmp_path / "annotations").glob("*/annotation.json"))
    data = json.loads(annotation.read_text())
    assert data["frame_sequence"] == 1
    assert data["metadata"]["SensorTimestamp"] == 123456
    import cv2

    saved = cv2.imread(str(annotation.parent / "image.png"))
    assert np.array_equal(saved, image)
    assert data["roi"] == [0.1, 0.2, 0.5, 0.5]


def test_edit_refuses_changed_profile(tmp_path):
    c = Controller(tmp_path)
    c.publish(np.zeros((100, 200, 3), np.uint8), {"timebase": "synthetic"})
    frozen = c.command("freeze")
    c.command("camera.set", {"key": "Contrast", "value": 1.2})
    with pytest.raises(ValueError):
        c.command("roi", {"id": frozen["id"], "roi": [0, 0, 1, 1]})


def test_mode_and_unsupported_controls(tmp_path):
    c = Controller(tmp_path)
    with pytest.raises(ValueError):
        c.command("mode", {"value": "run"})
    c.capabilities = {"Contrast": [0, 4, 1]}
    with pytest.raises(ValueError):
        c.command("camera.set", {"key": "LensPosition", "value": 2})


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


def test_field_rows_offer_only_valid_choices(tmp_path):
    c = ready_controller(tmp_path)
    state = c.snapshot()
    table = {row["key"]: row for row in fields.rows(state)}
    assert {"mode", "role", "resolution", "fps", "AeEnable", "focus", "profile", "roi"} <= set(table)
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
    assert [option["value"] for option in fields.rows(c.snapshot())[-3]["options"]] == names


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
