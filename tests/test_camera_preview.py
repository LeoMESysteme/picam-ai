"""Verhalten des bisherigen Prototyps nach der Workbench-Modularisierung."""

import asyncio
import time

import cv2
import numpy as np

from dispread.workbench.controller import Controller
from dispread.workbench.vision import box_iou, draw_overlay, find_display_candidates


def panel_image():
    image = np.zeros((480, 640, 3), np.uint8)
    cv2.rectangle(image, (140, 160), (500, 280), (200, 200, 200), -1)
    cv2.putText(image, "12345", (160, 245), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 4)
    return image


def test_panel_found_once_and_disappears():
    boxes = find_display_candidates(panel_image())
    assert len(boxes) == 1
    assert box_iou(boxes[0], (140, 160, 361, 121)) > 0.9
    assert find_display_candidates(np.zeros((480, 640, 3), np.uint8)) == []


def test_overlay_does_not_modify_input():
    image = panel_image()
    original = image.copy()
    overlay = draw_overlay(image, find_display_candidates(image))
    assert np.array_equal(image, original)
    assert not np.array_equal(overlay, original)


def test_latest_only_and_stale(tmp_path):
    c = Controller(tmp_path, simulate=True)
    c.publish(panel_image(), {"timebase": "synthetic"})
    assert c.snapshot()["live"]
    c.last_frame -= 3
    assert not c.snapshot()["live"]
    c.publish(panel_image(), {"timebase": "synthetic"})
    assert c.sequence == 2
    c.error = "camera lost"
    assert not c.snapshot()["live"]


def test_simulated_worker_stops(tmp_path):
    c = Controller(tmp_path, simulate=True)
    c.start()
    end = time.monotonic() + 3
    while not c.snapshot()["live"] and time.monotonic() < end:
        time.sleep(0.02)
    assert c.snapshot()["live"]
    c.close()
    assert not c.thread.is_alive()


def test_http_auth_stream_and_camera_failure(tmp_path):
    from aiohttp.test_utils import TestClient, TestServer

    from dispread.workbench.server import make_app
    from dispread.workbench.terminals import Terminals

    async def check():
        c = Controller(tmp_path, simulate=True)
        c.publish(panel_image(), {"timebase": "synthetic"})
        terminals = Terminals(tmp_path, tmp_path / "control.sock")
        client = TestClient(TestServer(make_app(c, terminals, lambda password: password == "test-only")))
        await client.start_server()
        headers = {"Host": "test.local", "Origin": "https://test.local"}
        try:
            assert (await client.get("/status")).status == 401
            assert (await client.post("/terminals", headers=headers)).status == 401
            wrong = await client.post("/login", json={"password": "wrong"}, headers=headers)
            assert wrong.status == 401
            login = await client.post("/login", json={"password": "test-only"}, headers=headers)
            assert login.status == 200
            headers["Cookie"] = "dispread_session=" + login.cookies["dispread_session"].value
            assert login.cookies["dispread_session"]["secure"]
            status = await (await client.get("/status", headers=headers)).json()
            assert status["live"]
            assert (
                await client.post("/command", json={"op": "focus", "args": {"value": True}}, headers=headers)
            ).status == 403
            headers["X-CSRF-Token"] = status["csrf"]
            assert (
                await client.post("/command", json={"op": "focus", "args": {"value": True}}, headers=headers)
            ).status == 200
            c.publish(panel_image(), {"timebase": "synthetic"})
            stream = await client.get("/stream.mjpg", headers=headers)
            assert stream.status == 200
            assert await stream.content.readline() == b"--frame\r\n"
            assert await stream.content.readline() == b"Content-Type: image/jpeg\r\n"
            length = int((await stream.content.readline()).split(b":")[1])
            assert await stream.content.readline() == b"\r\n"
            jpeg = await stream.content.readexactly(length)
            assert cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR) is not None
            stream.close()
            c.error = "camera disconnected"
            assert (await client.get("/stream.mjpg", headers=headers)).status == 503
            assert (await client.post("/logout", headers=headers)).status == 200
            assert (await client.get("/status", headers=headers)).status == 401
        finally:
            c.stop.set()
            await terminals.close()
            await client.close()

    asyncio.run(check())
