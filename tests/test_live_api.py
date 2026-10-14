import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from dispread.live.service import LiveError
from dispread.workbench.live_api import add_live_routes


class FakeService:
    def __init__(self):
        self.calls = []

    def status(self):
        return {"state": "idle", "release_notice": "Validiert nur: …"}

    def start_setup(self, *, cell_text=None):
        self.calls.append(("setup", cell_text))

    def confirm(self, **kw):
        raise LiveError("Kein Vorschlag zum Bestaetigen")

    def start_run(self):
        self.calls.append(("run",))

    def stop_run(self):
        raise LiveError("kein Lauf aktiv")

    def start_camera(self):
        self.calls.append(("camera",))

    def setup_file(self, name):
        return None

    def preview_jpeg(self):
        return None


def _run(check):
    async def main():
        app = web.Application()
        service = FakeService()
        add_live_routes(app, service, csrf_of=lambda _r: "tok")
        async with TestClient(TestServer(app)) as client:
            await check(client, service)

    asyncio.run(main())


def test_status_carries_csrf_and_notice():
    async def check(client, _service):
        data = await (await client.get("/live/status")).json()
        assert data["csrf"] == "tok" and data["release_notice"].startswith("Validiert nur")

    _run(check)


def test_setup_passes_cell_text_and_errors_become_409():
    async def check(client, service):
        assert (await client.post("/live/setup", json={"cell_text": "+0.60972 "})).status == 200
        assert service.calls == [("setup", "+0.60972 ")]
        response = await client.post("/live/run/stop")
        assert response.status == 409 and "kein Lauf" in (await response.json())["error"]

    _run(check)


def test_unknown_overlay_is_404():
    async def check(client, _service):
        assert (await client.get("/live/setup/etc-passwd.png")).status == 404

    _run(check)


def test_routes_without_socket(tmp_path, monkeypatch):
    """Handler direkt pruefen; Socket-Integration bleibt oben separat."""
    import json
    from unittest.mock import AsyncMock

    from aiohttp.test_utils import make_mocked_request

    async def direct(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", direct)

    async def check():
        service = FakeService()
        app = web.Application()
        add_live_routes(app, service, csrf_of=lambda _r: "tok")

        async def call(method, path, body=None):
            request = make_mocked_request(method, path, app=app)
            match = await app.router.resolve(request)
            request._match_info = match
            request.json = AsyncMock(return_value=body or {})
            # make_mocked_request has no payload; setup needs can_read_body.
            if body is not None:
                from unittest.mock import Mock

                request._payload = Mock()
                request._payload.at_eof.return_value = False
            return await match.handler(request)

        assert (await call("GET", "/live")).status == 200
        data = json.loads((await call("GET", "/live/status")).text)
        assert data["csrf"] == "tok" and data["release_notice"].startswith("Validiert nur")
        assert (await call("POST", "/live/setup", {"cell_text": "+0.60972 "})).status == 200
        assert service.calls == [("setup", "+0.60972 ")]
        assert (await call("POST", "/live/setup")).status == 200
        assert service.calls[-1] == ("setup", None)
        assert (await call("POST", "/live/run/start")).status == 200
        assert (await call("POST", "/live/camera/start")).status == 200
        assert service.calls[-2:] == [("run",), ("camera",)]
        for path in ("/live/confirm", "/live/run/stop"):
            response = await call("POST", path)
            assert response.status == 409
            assert "error" in json.loads(response.text)
        confirmed = []
        service.confirm = lambda **kwargs: confirmed.append(kwargs)
        assert (await call("POST", "/live/confirm", {
            "confirmed_by": "Operator", "format_checked": True, "acknowledge_warning": True,
        })).status == 200
        assert confirmed == [{"confirmed_by": "Operator", "format_checked": True,
                              "acknowledge_warning": True}]
        with pytest.raises(web.HTTPNotFound):
            await call("GET", "/live/setup/etc-passwd.png")
        with pytest.raises(web.HTTPServiceUnavailable):
            await call("GET", "/live/preview.jpg")
        service.preview_jpeg = lambda: b"jpeg"
        response = await call("GET", "/live/preview.jpg")
        assert response.body == b"jpeg" and response.content_type == "image/jpeg"
        overlay = tmp_path / "still.png"
        overlay.write_bytes(b"png")
        service.setup_file = lambda name: overlay if name == "still" else None
        assert (await call("GET", "/live/setup/still.png")).status == 200

    asyncio.run(check())


@pytest.mark.parametrize(("target", "expected"), [
    ("/live", "/live"), ("/live?view=setup", "/live?view=setup"),
    ("//evil.invalid", "/"), ("https://evil.invalid", "/"),
    ("live", "/"), ("/\\evil.invalid", "/"), ("/\nevil.invalid", "/"),
])
def test_live_routes_share_auth_and_csrf_guard(monkeypatch, target, expected):
    import json
    from urllib.parse import quote

    from aiohttp.test_utils import make_mocked_request

    from dispread.workbench.server import make_app

    async def direct(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", direct)

    async def check():
        service = FakeService()
        app = make_app(None, None, verifier=lambda _password: True, live=service)
        guard = app.middlewares[0]

        async def handle(method, path, headers=None, body=None):
            from unittest.mock import AsyncMock

            request = make_mocked_request(method, path, headers=headers or {}, app=app)
            request.json = AsyncMock(return_value=body or {})
            match = await app.router.resolve(request)
            request._match_info = match
            return await guard(request, match.handler)

        with pytest.raises(web.HTTPFound) as redirect:
            await handle("GET", "/live")
        assert redirect.value.location == "/login?next=/live"
        for path in ("/live/status", "/live/preview.jpg", "/static/live.js"):
            with pytest.raises(web.HTTPUnauthorized):
                await handle("GET", path)
        response = await handle("POST", "/login", {"Host": "localhost", "Origin": "https://localhost"},
                                {"password": "test"})
        assert json.loads(response.text)["next"] == "/"
        login = await handle("POST", "/login?next=" + quote(target, safe=""),
                             {"Host": "localhost", "Origin": "https://localhost"},
                             {"password": "test"})
        assert json.loads(login.text)["next"] == expected
        token = response.cookies["dispread_session"].value
        headers = {"Host": "localhost", "Cookie": f"dispread_session={token}"}
        response = await handle("GET", "/live/status", headers)
        csrf = json.loads(response.text)["csrf"]
        assert response.headers["Cache-Control"] == "no-store"
        with pytest.raises(web.HTTPForbidden):
            await handle("POST", "/live/run/start", headers)
        headers["Origin"] = "https://localhost"
        with pytest.raises(web.HTTPForbidden):
            await handle("POST", "/live/run/start", headers)
        headers["X-CSRF-Token"] = csrf
        assert (await handle("POST", "/live/run/start", headers)).status == 200
        assert service.calls == [("run",)]
        assert (await handle("POST", "/live/run/stop", headers)).status == 409

    asyncio.run(check())


def test_serve_cli_live_data_default_and_override():
    from dispread.workbench.cli import parser

    assert parser().parse_args(["serve"]).live_data == "var/live"
    assert parser().parse_args(["serve", "--live-data", "custom/live"]).live_data == "custom/live"


def test_serve_owner_factories_camera_failure_and_cleanup(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from dispread.camera_settings import preview_settings
    from dispread.workbench import server
    from dispread.workbench.cli import parser

    original_open = server.Path.open

    async def check(simulate, close_error):
        runtime = tmp_path / f"{simulate}-{close_error}"
        runtime.mkdir(mode=0o700)
        args = parser().parse_args(["serve", "--socket", str(runtime / "control.sock"),
                                    "--live-data", str(tmp_path / "live")]
                                   + (["--simulate"] if simulate else []))
        signals = []
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "add_signal_handler", lambda _sig, callback: signals.append(callback))
        monkeypatch.setattr(server.os, "geteuid", lambda: 1000)
        monkeypatch.setattr(server.pwd, "getpwuid", lambda _uid: SimpleNamespace(pw_name="me-systeme"))
        controller = Mock(config={"camera": {}, "detection": {}})
        controller.snapshot.return_value = {"config": controller.config}
        controller.start.side_effect = lambda: signals[0]()
        controller_factory = Mock(return_value=controller)
        monkeypatch.setattr(server, "Controller", controller_factory)
        owner = Mock()
        if not simulate:
            owner.start.side_effect = RuntimeError("Kamera belegt / USB2")
        owner_factory = Mock(return_value=owner)
        monkeypatch.setattr(server, "CameraOwner", owner_factory)
        live = Mock()
        shutdown = Mock()
        shutdown.attach_mock(live.close, "live_close")
        shutdown.attach_mock(owner.stop, "owner_stop")
        if close_error:
            live.close.side_effect = LiveError("x")
        lockfiles = []

        def track_open(path, *args, **kwargs):
            handle = original_open(path, *args, **kwargs)
            if path.name == "workbench.lock":
                lockfiles.append(handle)
            return handle

        monkeypatch.setattr(server.Path, "open", track_open)
        live_factory = Mock(return_value=live)
        monkeypatch.setattr(server, "LiveService", live_factory)
        terminals = Mock(close=AsyncMock())
        monkeypatch.setattr(server, "Terminals", Mock(return_value=terminals))
        app_factory = Mock(return_value=web.Application())
        monkeypatch.setattr(server, "make_app", app_factory)
        runner = Mock(setup=AsyncMock(), cleanup=AsyncMock())
        monkeypatch.setattr(server.web, "AppRunner", Mock(return_value=runner))

        async def unix_start():
            runtime.joinpath("control.sock").touch()

        monkeypatch.setattr(server.web, "UnixSite", Mock(return_value=Mock(start=AsyncMock(side_effect=unix_start))))
        monkeypatch.setattr(server.web, "TCPSite", Mock(return_value=Mock(start=AsyncMock())))
        monkeypatch.setattr(server.ssl, "SSLContext", Mock(return_value=Mock()))
        source = object()
        synthetic = Mock(return_value=source)
        uvc = Mock(return_value=source)
        monkeypatch.setattr(server, "open_source", synthetic)
        monkeypatch.setattr(server, "UvcSource", uvc)

        async def direct(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        monkeypatch.setattr(asyncio, "to_thread", direct)
        await server.serve(args)
        factory = owner_factory.call_args.args[0]
        assert factory() is source
        if simulate:
            assert owner_factory.call_args.kwargs == {"max_fps": 10}
            synthetic.assert_called_once_with("synthetic://seven-seg")
            uvc.assert_not_called()
        else:
            assert owner_factory.call_args.kwargs == {}
            uvc.assert_called_once_with(preview_settings(), apply_controls=False)
            controller.log.assert_any_call("error", "Kamera: Kamera belegt / USB2")
        live_factory.assert_called_once_with(owner, tmp_path / "live", simulate=simulate)
        controller_factory.assert_called_once_with(args.data, args.camera, args.simulate, owner=owner)
        app_factory.assert_called_once_with(controller, terminals, live=live)
        owner.start.assert_called_once_with()
        controller.close.assert_called_once_with()
        live.close.assert_called_once_with()
        owner.stop.assert_called_once_with()
        assert [call[0] for call in shutdown.mock_calls] == ["live_close", "owner_stop"]
        assert len(lockfiles) == 1 and lockfiles[0].closed
        if close_error:
            controller.log.assert_any_call("error", "Live: x")
        assert not runtime.joinpath("control.sock").exists()

    for simulate in (True, False):
        for close_error in (False, True):
            asyncio.run(check(simulate, close_error))
