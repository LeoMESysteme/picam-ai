import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from dispread.live.service import LiveError
from dispread.workbench.live_api import add_live_routes


class FakeService:
    def __init__(self):
        self.calls = []

    def status(self, *, full=False):
        data = {"state": "idle", "release_notice": "Validiert nur: …"}
        if full:
            data["tracking_reasons"] = {"lcd_rand_fehlt": "LCD-Rand nicht ausreichend bestaetigt"}
        return data

    def start_setup(self, *, cell_text=None):
        self.calls.append(("setup", cell_text))

    def confirm(self, **kw):
        raise LiveError("Kein Vorschlag zum Bestaetigen")

    def start_run(self, *, test_override=False, reference=True, norm_schedule=None, diagnostics=False):
        self.calls.append(("run", test_override))

    def stop_run(self):
        raise LiveError("kein Lauf aktiv")

    def mark(self, text):
        self.calls.append(('mark', text))

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


def test_status_transports_only_rejected_test_run_records_without_socket(tmp_path, monkeypatch):
    import json

    from aiohttp.test_utils import make_mocked_request
    from dotmatrix_helpers import embed
    from test_live_session import _session

    from dispread.live.service import LiveService

    async def direct(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', direct)
    marker = {'testlauf': True}
    session = _session(tmp_path, [embed('+ 1.2345 ')] * 2, test_run=marker)
    session.start()
    service = LiveService(session._owner, tmp_path)
    service._state, service._session, service._test_run = 'running', session, marker
    service._run_dir = session.records_path.parent
    app = web.Application()
    add_live_routes(app, service, csrf_of=lambda _request: 'tok')

    async def check():
        session.step()
        session.step()
        for path in ('/live/status', '/live/status?full=1'):
            request = make_mocked_request('GET', path, app=app)
            match = await app.router.resolve(request)
            response = await match.handler(request)
            assert response.status == 200
            data = json.loads(response.text)
            assert data['test_run'] == marker
            assert data['run']['latest']['status'] == 'unreadable'
            assert data['run']['latest']['value'] is None
            assert data['run']['latest']['reject_reasons'][0] == 'testlauf_keine_freigabe'
            assert data['run']['guess']['gate_status'] == 'valid'

    try:
        asyncio.run(check())
    finally:
        session.stop()


@pytest.mark.parametrize("full", [False, True])
def test_playwright_service_status_without_socket(tmp_path, monkeypatch, full):
    import json

    from aiohttp.test_utils import make_mocked_request
    from live_ui_server import FakeLiveService

    async def direct(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", direct)
    service = FakeLiveService(tmp_path / "overlay.png")
    app = web.Application()
    add_live_routes(app, service, csrf_of=lambda _r: "tok")
    path = "/live/status?full=1" if full else "/live/status"
    request = make_mocked_request("GET", path, app=app)

    async def check():
        match = await app.router.resolve(request)
        response = await match.handler(request)
        assert response.status == 200
        data = json.loads(response.text)
        assert data["state"] == "idle"
        assert data["csrf"] == "tok"
        if full:
            assert data["tracking_reasons"]["lcd_rand_fehlt"] == "lcd-rand nicht ausreichend bestaetigt"
        else:
            assert "tracking_reasons" not in data
        assert "tracking_reasons" not in service.status()

    asyncio.run(check())


def test_playwright_fake_preserves_tracking_hint_without_socket(tmp_path):
    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'overlay.png')
    hint = {'kind': 'anzeige_bewegt', 'shift_px': 19, 'region_shift_px': 27, 'rotation_deg': -2.23, 'since_s': 3}
    for full in (False, True):
        service.set_state({'state': 'running', 'run': {'tracking_hint': hint}})
        assert service.status(full=full)['run']['tracking_hint'] == hint
        service.set_state({'state': 'running', 'run': {}})
        assert service.status(full=full)['run']['tracking_hint'] is None


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
        assert "tracking_reasons" not in data
        full = json.loads((await call("GET", "/live/status?full=1")).text)
        assert full["tracking_reasons"] == {"lcd_rand_fehlt": "LCD-Rand nicht ausreichend bestaetigt"}
        assert "tracking_reasons" not in json.loads((await call("GET", "/live/status")).text)
        assert (await call("POST", "/live/setup", {"cell_text": "+0.60972 "})).status == 200
        assert service.calls == [("setup", "+0.60972 ")]
        assert (await call("POST", "/live/setup")).status == 200
        assert service.calls[-1] == ("setup", None)
        assert (await call("POST", "/live/run/start")).status == 200
        assert service.calls[-1] == ("run", False)
        assert (await call("POST", "/live/run/start", {"test_override": True})).status == 200
        assert service.calls[-1] == ("run", True)
        assert (await call("POST", "/live/camera/start")).status == 200
        assert service.calls[-2:] == [("run", True), ("camera",)]
        marks = []
        service.mark = lambda **kw: marks.append(kw)
        assert (await call("POST", "/live/run/mark", {"text": "Abdeckung"})).status == 200
        assert marks == [{"text": "Abdeckung"}]
        for path in ("/live/confirm", "/live/run/stop"):
            response = await call("POST", path)
            assert response.status == 409
            assert "error" in json.loads(response.text)

        def blocked(**kwargs):
            raise LiveError("Lauf gesperrt: Gegenlesen WARNUNG")

        forwarded = []
        service.start_run = lambda **kwargs: forwarded.append(kwargs)
        assert (await call("POST", "/live/run/start")).status == 200
        assert forwarded[-1]['diagnostics'] is False
        assert (await call("POST", "/live/run/start", {"reference": False})).status == 200
        assert forwarded[-1] == {"test_override": False, "reference": False, "norm_schedule": None, "diagnostics": False}
        assert (await call("POST", "/live/run/start", {
            "reference": True, "norm_schedule": "1:20,2:20", "diagnostics": True,
        })).status == 200
        assert forwarded[-1] == {"test_override": False, "reference": True, "norm_schedule": "1:20,2:20", "diagnostics": True}
        service.start_run = blocked
        response = await call("POST", "/live/run/start")
        assert response.status == 409
        assert json.loads(response.text)["error"] == "Lauf gesperrt: Gegenlesen WARNUNG"
        confirmed = []
        service.confirm = lambda **kwargs: confirmed.append(kwargs)
        assert (await call("POST", "/live/confirm", {
            "session_id": "reviewed", "confirmed_by": "Operator", "format_checked": True, "acknowledge_warning": True,
        })).status == 200
        assert confirmed == [{"session_id": "reviewed", "confirmed_by": "Operator", "format_checked": True,
                              "acknowledge_warning": True, "use_tolerance": False}]
        assert (await call("POST", "/live/confirm", {"use_tolerance": True})).status == 200
        assert confirmed[-1]['use_tolerance'] is True
        assert (await call('POST', '/live/confirm', {'proposal_revision': 'review-2'})).status == 200
        assert confirmed[-1]['proposal_revision'] == 'review-2'
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

        for method in ("GET", "HEAD"):
            with pytest.raises(web.HTTPFound) as redirect:
                await handle(method, "/live")
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
        for path in ('/live/run/start', '/live/run/mark', '/live/setup/regions'):
            with pytest.raises(web.HTTPForbidden):
                await handle('POST', path, headers)
        headers["Origin"] = "https://localhost"
        for path in ('/live/run/start', '/live/run/mark', '/live/setup/regions'):
            with pytest.raises(web.HTTPForbidden):
                await handle('POST', path, headers)
        headers["X-CSRF-Token"] = csrf
        assert (await handle("POST", "/live/run/start", headers)).status == 200
        assert service.calls == [("run", False)]
        assert (await handle('POST', '/live/run/mark', headers, {'text': 'Abdeckung'})).status == 200
        assert service.calls[-1] == ('mark', 'Abdeckung')
        assert (await handle("POST", "/live/run/stop", headers)).status == 409

    asyncio.run(check())


def test_serve_cli_live_data_default_and_override():
    from dispread.workbench.cli import parser

    assert parser().parse_args(["serve"]).live_data == "var/live"
    assert parser().parse_args(["serve", "--live-data", "custom/live"]).live_data == "custom/live"


@pytest.mark.parametrize(("op", "args", "method", "kwargs"), [
    ("live.status", None, "status", {}),
    ("live.setup", None, "start_setup", {"cell_text": None}),
    ("live.setup", {"cell_text": "+0.60972 "}, "start_setup", {"cell_text": "+0.60972 "}),
    ("live.stop", {}, "stop_run", {}),
    ("live.mark", {"text": "Abdeckung"}, "mark", {"text": "Abdeckung"}),
    ("live.camera", {}, "start_camera", {}),
    ("live.aufraeumen", {"days": 10, "execute": True}, "cleanup", {"days": 10, "execute": True}),
])
def test_local_live_routes_use_service_in_thread(monkeypatch, op, args, method, kwargs):
    import json
    from unittest.mock import AsyncMock, Mock

    from dispread.workbench.server import handle_local_op

    controller, service = Mock(), Mock()
    service.status.return_value = {"state": "idle"}

    async def direct(fn, **values):
        return fn(**values)

    to_thread = AsyncMock(side_effect=direct)
    monkeypatch.setattr(asyncio, "to_thread", to_thread)
    result = {"state": "idle"} if method == "status" else {"dry_run": False, "entries": []} if method == "cleanup" else None
    getattr(service, method).return_value = result
    response = asyncio.run(handle_local_op(op, args, controller, service))
    assert response.status == 200
    assert json.loads(response.text) == (result if method in ('status', 'cleanup') else {"ok": True})
    assert to_thread.await_args_list[-1].args == (getattr(service, method),)
    assert to_thread.await_args_list[-1].kwargs == kwargs
    assert service.method_calls == ([("status", (), {})] if op == "live.setup" else []) + [(method, (), kwargs)]
    controller.command.assert_not_called()


@pytest.mark.parametrize("op", ["live.status", "live.setup", "live.stop", "live.camera", "live.mark"])
def test_local_live_errors_are_409(monkeypatch, op):
    import json
    from unittest.mock import Mock

    from dispread.workbench.server import handle_local_op

    async def direct(fn, **values):
        return fn(**values)

    monkeypatch.setattr(asyncio, "to_thread", direct)
    service = Mock()
    for name in ("status", "start_setup", "stop_run", "start_camera", "mark"):
        getattr(service, name).side_effect = LiveError("Kamera belegt")
    response = asyncio.run(handle_local_op(op, {}, Mock(), service))
    assert response.status == 409
    assert json.loads(response.text) == {"error": "Kamera belegt"}


@pytest.mark.parametrize("op", ["live.confirm", "live.run", "live.run.start", "live.unknown"])
def test_local_live_refuses_ui_operations_and_unknown_ops(op):
    import json
    from unittest.mock import Mock

    from dispread.workbench.server import handle_local_op

    controller, service = Mock(), Mock()
    response = asyncio.run(handle_local_op(op, {"confirmed_by": "Operator"}, controller, service))
    assert response.status == 400
    assert "/live" in json.loads(response.text)["error"]
    assert not service.method_calls
    controller.command.assert_not_called()


def test_local_legacy_command_still_uses_controller():
    import json
    from unittest.mock import Mock

    from dispread.workbench.server import handle_local_op

    controller, service = Mock(), Mock()
    controller.command.return_value = {"mode": "setup"}
    response = asyncio.run(handle_local_op("mode", {"value": "setup"}, controller, service))
    assert response.status == 200 and json.loads(response.text) == {"mode": "setup"}
    controller.command.assert_called_once_with("mode", {"value": "setup"})
    assert not service.method_calls


@pytest.mark.parametrize(("argv", "op", "args"), [
    (["live", "status"], "live.status", {}),
    (["live", "setup"], "live.setup", {}),
    (["live", "setup", "--force"], "live.setup", {"force": True}),
    (["live", "setup", "--cell-text", "+0.60972 "], "live.setup", {"cell_text": "+0.60972 "}),
    (["live", "stop"], "live.stop", {}),
    (["live", "mark", "Abdeckung"], "live.mark", {"text": "Abdeckung"}),
    (["live", "camera"], "live.camera", {}),
])
def test_live_cli_requests_local_op_and_prints_json(monkeypatch, capsys, argv, op, args):
    import json

    from dispread.workbench import cli

    calls = []

    async def request(operation, values):
        calls.append((operation, values))
        return {"state": "idle"}

    monkeypatch.setattr(cli, "request", request)
    assert cli.main(argv) == 0
    assert calls == [(op, args)]
    output = capsys.readouterr()
    assert json.loads(output.out) == {"state": "idle"} and output.err == ""


@pytest.mark.parametrize("action", ["confirm", "run"])
def test_live_cli_has_no_confirmation_or_run_start(action):
    from dispread.workbench.cli import parser

    with pytest.raises(SystemExit) as error:
        parser().parse_args(["live", action])
    assert error.value.code == 2


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


@pytest.mark.parametrize("state", ["setup_ready", "confirmed"])
@pytest.mark.parametrize("force", [False, True])
def test_local_setup_requires_force_to_replace_reviewed_proposal(monkeypatch, state, force):
    import json
    from unittest.mock import Mock

    from dispread.workbench.server import handle_local_op

    async def direct(fn, **kwargs):
        return fn(**kwargs)

    monkeypatch.setattr(asyncio, "to_thread", direct)
    service = Mock()
    service.status.return_value = {"state": state}
    response = asyncio.run(handle_local_op("live.setup", {"force": force}, Mock(), service))
    assert response.status == (200 if force else 409)
    if force:
        service.start_setup.assert_called_once_with(cell_text=None)
    else:
        assert "--force" in json.loads(response.text)["error"]
        service.start_setup.assert_not_called()


@pytest.mark.parametrize('body', ['', 'null', '[]', '42', '"text"', '{broken'])
def test_mark_malformed_body_is_german_400(body):
    import json
    from unittest.mock import AsyncMock

    from aiohttp.test_utils import make_mocked_request

    async def check():
        service = FakeService()
        service.mark = lambda **kw: pytest.fail('invalid mark reached service')
        app = web.Application()
        add_live_routes(app, service, csrf_of=lambda _r: 'tok')
        request = make_mocked_request('POST', '/live/run/mark', app=app)
        request.json = AsyncMock(side_effect=lambda: json.loads(body))
        match = await app.router.resolve(request)
        response = await match.handler(request)
        assert response.status == 400
        assert 'JSON-Objekt' in json.loads(response.text)['error']
    asyncio.run(check())


def test_region_edit_route_without_socket(monkeypatch):
    import json
    from unittest.mock import AsyncMock

    from aiohttp.test_utils import make_mocked_request

    async def direct(fn, **kwargs):
        return fn(**kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', direct)

    async def check():
        service = FakeService()
        app = web.Application()
        add_live_routes(app, service, csrf_of=lambda _r: 'tok')

        async def call(body):
            request = make_mocked_request('POST', '/live/setup/regions', app=app)
            request.json = AsyncMock(return_value=body)
            match = await app.router.resolve(request)
            return await match.handler(request)

        forwarded = []

        def edit(**kwargs):
            forwarded.append(kwargs)
            return {'proposal_revision': 'new', 'centre_results': [{'ok': False, 'reason': 'zu_nah'}]}

        service.edit_regions = edit
        response = await call({'proposal_revision': 'old', 'add': [[123, 456]], 'remove': [0]})
        assert response.status == 200
        assert json.loads(response.text) == {'ok': True, 'proposal_revision': 'new',
                                             'centre_results': [{'ok': False, 'reason': 'zu_nah'}]}
        assert forwarded == [{'proposal_revision': 'old', 'add': [[123, 456]], 'remove': [0]}]

        def blocked(**kwargs):
            raise LiveError('Vorschlag hat sich geaendert')

        service.edit_regions = blocked
        response = await call({'proposal_revision': 'old', 'add': [], 'remove': [1]})
        assert response.status == 409 and 'geaendert' in json.loads(response.text)['error']
        assert (await call([])).status == 400
        assert (await call(None)).status == 400

    asyncio.run(check())


def test_playwright_fake_region_edit_contract(tmp_path):
    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'overlay.png')
    service.set_state({'state': 'setup_ready', 'setup': {
        'proposal_revision': 'v1', 'regions': [{'centre': [10, 10], 'size': 5}],
        'checks': {'nachfuehrung': 'OK'}, 'overall': 'OK',
    }})
    result = service.edit_regions(proposal_revision='v1', add=[[30, 12]], remove=[])
    assert result['proposal_revision'] != 'v1'
    assert result['centre_results'][-1] == {
        'requested_centre': [30, 12], 'centre': [30, 12], 'used_centre': [30, 12], 'ok': True, 'reason': None,
    }
    assert service.status()['setup']['auswahl'] == 'manuell'
    with pytest.raises(LiveError, match='geaendert'):
        service.edit_regions(proposal_revision='v1', add=[], remove=[0])
    service.edit_regions(proposal_revision=result['proposal_revision'], add=[], remove=[0, 1])
    assert service.status()['setup']['overall'] == 'FEHLER'


@pytest.mark.parametrize('fake', [False, True], ids=['real_service', 'playwright_fake'])
@pytest.mark.parametrize(('add', 'remove'), [
    (None, []), ('bad', []), ({}, []), ([[1]], []), ([[True, 2]], []), ([[1, '2']], []),
    ([[1, None]], []), ([[float('inf'), 2]], []), ([[float('nan'), 2]], []),
    ([[1e300, 2]], []), ([[-0.1, 2]], []), ([[1280, 2]], []), ([[2, 780]], []),
    pytest.param([[10**400, 2]], [], id='huge_integer'),
    ([], None), ([], 'bad'), ([], [True]), ([], [[0]]), ([], [999]), ([], [0, 0]), ([], []),
])
def test_region_edit_input_errors_are_400_without_mutation(tmp_path, monkeypatch, add, remove, fake):
    import copy
    import json
    from unittest.mock import AsyncMock

    from aiohttp.test_utils import make_mocked_request
    from live_ui_server import FakeLiveService
    from test_live_service import ready_service
    from test_live_setup_tracking import _propose

    async def direct(fn, **kwargs):
        return fn(**kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', direct)
    if fake:
        service = FakeLiveService(tmp_path / 'overlay.png')
        service.set_state({'state': 'setup_ready', 'setup': {
            'proposal_revision': 'v1', 'regions': [{'centre': [10, 10], 'size': 5}],
            'checks': {'nachfuehrung': 'OK'}, 'overall': 'OK',
        }})
    else:
        _, _, proposal = _propose(tmp_path)
        service = ready_service(tmp_path, proposal)
    original = copy.deepcopy(service._status if fake else service._proposal)
    revision = service.status()['setup']['proposal_revision']
    app = web.Application()
    add_live_routes(app, service, csrf_of=lambda _r: 'tok')

    async def check():
        request = make_mocked_request('POST', '/live/setup/regions', app=app)
        request.json = AsyncMock(return_value={'proposal_revision': revision, 'add': add, 'remove': remove})
        match = await app.router.resolve(request)
        response = await match.handler(request)
        assert response.status == 400, response.text
        assert json.loads(response.text)['error']

    asyncio.run(check())
    assert (service._status if fake else service._proposal) == original
    assert service.status()['setup']['proposal_revision'] == revision


@pytest.mark.parametrize('conflict', ['running', 'no_proposal', 'outdated_revision', 'no_overlay_evidence'])
def test_region_edit_state_conflicts_still_return_409(tmp_path, monkeypatch, conflict):
    from unittest.mock import AsyncMock

    from aiohttp.test_utils import make_mocked_request
    from test_live_service import ready_service
    from test_live_setup_tracking import _propose

    async def direct(fn, **kwargs):
        return fn(**kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', direct)
    _, _, proposal = _propose(tmp_path)
    service = ready_service(tmp_path, proposal)
    revision = proposal['live_tracking']['proposal_revision']
    if conflict == 'running':
        service._state = 'running'
    elif conflict == 'no_proposal':
        service._proposal = None
    elif conflict == 'no_overlay_evidence':
        del service._proposal['overlay_evidence']
    else:
        revision = 'outdated'
    app = web.Application()
    add_live_routes(app, service, csrf_of=lambda _r: 'tok')

    async def check():
        request = make_mocked_request('POST', '/live/setup/regions', app=app)
        request.json = AsyncMock(return_value={'proposal_revision': revision, 'add': [[1, 1]], 'remove': []})
        match = await app.router.resolve(request)
        response = await match.handler(request)
        assert response.status == 409
        if conflict == 'no_overlay_evidence':
            assert 'Vorschlag ohne Overlay-Belege - neu einrichten' in response.text
            assert service._proposal['live_tracking']['proposal_revision'] == revision

    asyncio.run(check())


@pytest.mark.parametrize('options', [[], ['--nur-diagnose'], ['--nur-diagnose', '--ausfuehren']])
def test_cleanup_cli_requests_service_and_prints_sizes(monkeypatch, capsys, options):
    import json

    from dispread.workbench import cli

    calls = []
    async def request(op, args):
        calls.append((op, args))
        return {'dry_run': not args['execute'], 'entries': [{'path': 'run-01', 'bytes': 12, 'mb': 0.000012}]}

    monkeypatch.setattr(cli, 'request', request)
    assert cli.main(['live', 'aufraeumen', '--aelter-als', '10', *options]) == 0
    assert calls == [('live.aufraeumen', {'days': 10, 'diagnostics_only': '--nur-diagnose' in options,
                                        'execute': '--ausfuehren' in options})]
    output = capsys.readouterr()
    assert json.loads(output.out)['entries'][0]['bytes'] == 12 and output.err == ''


def test_cleanup_local_route_returns_listing_without_socket(tmp_path, monkeypatch):
    import json

    from test_live_service import FakeOwner
    from test_live_storage import NOW, run_tree

    from dispread.live.service import LiveService
    from dispread.workbench.server import handle_local_op

    run = run_tree(tmp_path)
    async def direct(fn, **kwargs):
        return fn(**kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', direct)
    service = LiveService(FakeOwner(), tmp_path, wall=lambda: NOW)
    response = asyncio.run(handle_local_op('live.aufraeumen', {'days': 10}, None, service))
    assert response.status == 200
    data = json.loads(response.text)
    assert data['dry_run'] is True and data['entries'][0]['path'] == str(run)
    assert run.exists()


@pytest.mark.parametrize('age', ['0', '-1', 'no', '1.5'])
def test_cleanup_cli_rejects_bad_age_before_request(monkeypatch, age):
    from dispread.workbench import cli

    monkeypatch.setattr(cli, 'request', lambda *a: pytest.fail('invalid cleanup reached service'))
    with pytest.raises(SystemExit) as caught:
        cli.parser().parse_args(['live', 'aufraeumen', '--aelter-als', age])
    assert caught.value.code == 2


def test_cleanup_cli_reports_all_results_and_exits_nonzero_on_partial_failure(tmp_path, monkeypatch, capsys):
    import json
    import shutil

    from test_live_service import FakeOwner
    from test_live_storage import NOW, run_tree

    from dispread.live.service import LiveService
    from dispread.workbench import cli
    from dispread.workbench.server import handle_local_op

    runs = [run_tree(tmp_path, run=f'run-{i:02}') for i in range(1, 4)]
    service = LiveService(FakeOwner(), tmp_path, wall=lambda: NOW)
    rmtree = shutil.rmtree

    def fail_middle(target):
        if target == runs[1]:
            raise PermissionError('Loeschen verweigert')
        rmtree(target)

    async def direct(fn, **kwargs):
        return fn(**kwargs)

    async def request(op, args):
        response = await handle_local_op(op, args, None, service)
        assert response.status == 200
        return json.loads(response.text)

    monkeypatch.setattr(shutil, 'rmtree', fail_middle)
    monkeypatch.setattr(asyncio, 'to_thread', direct)
    monkeypatch.setattr(cli, 'request', request)
    assert cli.main(['live', 'aufraeumen', '--aelter-als', '10', '--ausfuehren']) == 1
    output = capsys.readouterr()
    data = json.loads(output.out)
    assert output.err == '' and data['failed'] is True
    assert [entry['path'] for entry in data['entries']] == [str(run) for run in runs]
    assert [entry['status'] for entry in data['entries']] == ['deleted', 'failed', 'deleted']
    assert data['entries'][1]['error'] == 'Loeschen verweigert'
    assert not runs[0].exists() and runs[1].exists() and not runs[2].exists()


def test_run_start_output_reaches_service_without_socket(monkeypatch):
    from aiohttp.test_utils import make_mocked_request

    async def direct(fn, **kwargs):
        return fn(**kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', direct)
    service = FakeService()
    received = []

    def start_run(**kwargs):
        received.append(kwargs)

    service.start_run = start_run
    app = web.Application()
    add_live_routes(app, service, csrf_of=lambda _: 'tok')
    output = {'port': '/dev/pts/123', 'baudrate': 115200, 'prefix': '#'}

    async def body(_request):
        return {'reference': False, 'output': output}

    monkeypatch.setattr(web.Request, 'json', body)
    monkeypatch.setattr(web.Request, 'can_read_body', property(lambda _: True))

    async def check():
        request = make_mocked_request('POST', '/live/run/start', app=app)
        match = await app.router.resolve(request)
        response = await match.handler(request)
        assert response.status == 200
        assert received == [{'test_override': False, 'reference': False, 'norm_schedule': None,
                             'diagnostics': False, 'output': output}]

    asyncio.run(check())
