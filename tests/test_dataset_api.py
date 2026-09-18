"""Geschuetzte Vorschau- und Export-Endpunkte des Sammelmodus (Aufgabe 3).

Folgt demselben Testmuster wie ``test_camera_preview.py``: echter aiohttp-
Testclient gegen ``make_app()``, kein Mock der Middleware.
"""

from __future__ import annotations

import asyncio
import zipfile
from io import BytesIO

import cv2
import numpy as np
from aiohttp.test_utils import TestClient, TestServer

from dispread.workbench.controller import Controller
from dispread.workbench.server import make_app
from dispread.workbench.terminals import Terminals


def _image(fill=100, width=200, height=100):
    return np.full((height, width, 3), fill, np.uint8)


async def _authenticated_client(tmp_path, controller):
    terminals = Terminals(tmp_path, tmp_path / "control.sock")
    client = TestClient(TestServer(make_app(controller, terminals, lambda password: password == "test-only")))
    await client.start_server()
    headers = {"Host": "test.local", "Origin": "https://test.local"}
    login = await client.post("/login", json={"password": "test-only"}, headers=headers)
    assert login.status == 200
    headers["Cookie"] = "dispread_session=" + login.cookies["dispread_session"].value
    status = await (await client.get("/status", headers=headers)).json()
    headers["X-CSRF-Token"] = status["csrf"]
    return client, terminals, headers


async def _command(client, headers, op, args=None):
    response = await client.post("/command", json={"op": op, "args": args or {}}, headers=headers)
    return response


def _device_payload():
    device_args = {
        "name": "Pruefling 1",
        "model": "GSV-2ASD",
        "family": "gsv2asd",
        "technology": "LED",
        "split": "development",
        "identity_confirmed": True,
        "identity_evidence": "Laborsicht: Typenschild abgeglichen",
    }
    return device_args


def test_dataset_routes_require_authentication(tmp_path):
    async def check():
        c = Controller(tmp_path, simulate=True)
        terminals = Terminals(tmp_path, tmp_path / "control.sock")
        client = TestClient(TestServer(make_app(c, terminals, lambda password: password == "test-only")))
        await client.start_server()
        try:
            assert (await client.get("/dataset/captures/" + "a" * 32 + ".jpg")).status == 401
            assert (await client.get("/dataset/exports/" + "a" * 32 + ".zip")).status == 401
        finally:
            await terminals.close()
            await client.close()

    asyncio.run(check())


def test_dataset_command_without_csrf_is_rejected(tmp_path):
    async def check():
        c = Controller(tmp_path, simulate=True)
        client, terminals, headers = await _authenticated_client(tmp_path, c)
        try:
            no_csrf = dict(headers)
            del no_csrf["X-CSRF-Token"]
            response = await client.post(
                "/command", json={"op": "dataset.device.create", "args": _device_payload()}, headers=no_csrf
            )
            assert response.status == 403
        finally:
            c.stop.set()
            await terminals.close()
            await client.close()

    asyncio.run(check())


def test_full_capture_preview_and_export_download_roundtrip(tmp_path):
    async def check():
        c = Controller(tmp_path, simulate=True)
        # Bewusst NICHT "timebase": "synthetic" - dieser Test prueft den
        # vollen Exportpfad, und synthetische Fixtures zaehlen seit Aufgabe 6
        # nie zur realen Exportabdeckung (Konzept, Exportvertrag).
        c.publish(_image(fill=42), {"timebase": "file_mtime"})
        client, terminals, headers = await _authenticated_client(tmp_path, c)
        try:
            device = await (await _command(client, headers, "dataset.device.create", _device_payload())).json()
            group = await (
                await _command(client, headers, "dataset.group.begin", {"device_id": device["id"], "change_note": "Situation 1"})
            ).json()
            captured = await (
                await _command(
                    client, headers, "dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]}
                )
            ).json()

            preview = await client.get(f"/dataset/captures/{captured['token']}.jpg", headers=headers)
            assert preview.status == 200
            assert preview.content_type == "image/jpeg"
            decoded = cv2.imdecode(np.frombuffer(await preview.read(), np.uint8), cv2.IMREAD_COLOR)
            assert (decoded == 42).all()

            save_response = await _command(
                client,
                headers,
                "dataset.save",
                {
                    "token": captured["token"],
                    "bbox": [10, 10, 40, 20],
                    "target_label": "oben",
                    "label_state": "readable",
                    "expected_text": "-01.25",
                    "conditions": ["frontal"],
                },
            )
            assert save_response.status == 200

            export = await (await _command(client, headers, "dataset.export")).json()
            zip_response = await client.get(f"/dataset/exports/{export['export_id']}.zip", headers=headers)
            assert zip_response.status == 200
            assert zip_response.content_type == "application/zip"
            archive = zipfile.ZipFile(BytesIO(await zip_response.read()))
            names = archive.namelist()
            assert "manifest.json" in names
            assert "coverage.json" in names
            assert any(name.startswith("images/") for name in names)
        finally:
            c.stop.set()
            await terminals.close()
            await client.close()

    asyncio.run(check())


def test_unknown_capture_token_and_export_id_are_rejected_without_leaking(tmp_path):
    async def check():
        c = Controller(tmp_path, simulate=True)
        client, terminals, headers = await _authenticated_client(tmp_path, c)
        try:
            response = await client.get("/dataset/captures/" + "a" * 32 + ".jpg", headers=headers)
            assert response.status == 400
            response = await client.get("/dataset/exports/" + "a" * 32 + ".zip", headers=headers)
            assert response.status == 400
            # Kein Pfadparameter darf durchgereicht werden.
            response = await client.get("/dataset/exports/../../etc/passwd.zip", headers=headers)
            assert response.status in (400, 404)
        finally:
            c.stop.set()
            await terminals.close()
            await client.close()

    asyncio.run(check())
