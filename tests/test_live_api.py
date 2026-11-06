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

    def cancel_setup(self):
        raise LiveError("Keine Einrichtung laeuft")

    def confirm(self, **kw):
        raise LiveError("Kein Vorschlag zum Bestaetigen")

    def start_run(self, *, test_override=False, reference=True, norm_schedule=None, diagnostics=False, output=None):
        self.calls.append(("run", test_override))
        self.output = output

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


def _preview_service(tmp_path, *, latest=None):
    from types import SimpleNamespace

    from test_live_preview import camera_frame, frame_info

    from dispread.live.service import LiveService

    service = LiveService(SimpleNamespace(latest=latest or (lambda: (7, camera_frame()))), tmp_path,
                          diagnostic_staging_root=tmp_path / "staging")
    service._state = "running"
    service._session = SimpleNamespace(frame_info=frame_info)
    return service


def _run_preview(check):
    from concurrent.futures import ThreadPoolExecutor

    # Worker ausserhalb des Loops beenden: auch dessen Shutdown-Weckung
    # ueber socketpair ist im Sandbox gesperrt.
    with ThreadPoolExecutor() as executor:
        loop = asyncio.new_event_loop()
        loop.set_default_executor(executor)
        try:
            return loop.run_until_complete(check)
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()


async def _preview_handler(service, *, transport=...):
    from contextlib import suppress
    from unittest.mock import Mock

    from aiohttp.test_utils import make_mocked_request

    app = web.Application()
    add_live_routes(app, service, csrf_of=lambda _r: "tok")

    if transport is ...:
        transport = Mock()
        transport.is_closing.return_value = False
    request = make_mocked_request("GET", "/live/preview.mjpg", app=app,
                                  transport=transport, protocol=Mock(transport=transport))
    match = await app.router.resolve(request)
    task = asyncio.create_task(match.handler(request))
    try:
        # Der Sandbox sperrt auch die Socketpair-Weckung von to_thread.
        # Timer halten hier den echten Eventloop und echte Worker benutzbar.
        while not task.done():
            await asyncio.wait((task,), timeout=0.01)
        return await task
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def _capture_preview(monkeypatch, *, limit=1):
    import time

    responses = []

    class CaptureResponse(web.StreamResponse):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.parts = []
            responses.append(self)

        async def prepare(self, request):
            return None

        async def write(self, data):
            self.parts.append((time.monotonic(), data))
            if limit is not None and len(self.parts) >= limit:
                raise ConnectionResetError("Betrachter getrennt")

    monkeypatch.setattr("dispread.workbench.live_api.web.StreamResponse", CaptureResponse)
    return responses


def _check_preview_part(part):
    import json

    header, body = part.split(b"\r\n\r\n", 1)
    lines = header.split(b"\r\n")
    assert lines[0] == b"--frame"
    headers = dict(line.split(b": ", 1) for line in lines[1:])
    assert headers[b"Content-Type"] == b"image/jpeg"
    assert body.startswith(b"\xff\xd8") and body.endswith(b"\xff\xd9\r\n")
    assert len(body) - 2 == int(headers[b"Content-Length"])
    hud_bytes = headers[b"X-Hud"]
    assert hud_bytes.isascii() and len(hud_bytes) <= 2048
    hud = json.loads(hud_bytes)
    assert hud["seq"] == int(headers[b"X-Frame-Sequence"]) == 7
    assert hud["cap_ns"] == int(headers[b"X-Capture-Ns"]) == 123463
    assert hud["rec"]["seq"] == 6
    return hud


def test_preview_mjpg_parts_carry_hud_headers(tmp_path):
    async def check():
        app = web.Application()
        add_live_routes(app, _preview_service(tmp_path), csrf_of=lambda _r: "tok")
        async with TestClient(TestServer(app)) as client:
            async with client.get("/live/preview.mjpg") as response:
                assert response.status == 200
                assert response.headers["Content-Type"] == "multipart/x-mixed-replace; boundary=frame"
                header = await asyncio.wait_for(response.content.readuntil(b"\r\n\r\n"), 1)
                length = int(dict(line.split(b": ", 1) for line in header.split(b"\r\n")[1:-2])[b"Content-Length"])
                body = await response.content.readexactly(length + 2)
                _check_preview_part(header + body)

    asyncio.run(check())


def test_preview_mjpg_headers_and_encoding_thread_without_socket(tmp_path, monkeypatch):
    import threading

    import cv2

    responses = _capture_preview(monkeypatch)
    encode = cv2.imencode
    threads = []

    def spy(*args):
        threads.append(threading.get_ident())
        return encode(*args)

    monkeypatch.setattr(cv2, "imencode", spy)
    service = _preview_service(tmp_path)
    # Auch Nicht-ASCII im HUD muss eine einzelne ASCII-Kopfzeile bleiben.
    from test_live_preview import frame_info

    info = frame_info()
    info["rec"]["reasons"] = ["Pr\u00fcfung\r\n"]
    service._session.frame_info = lambda: info
    response = _run_preview(_preview_handler(service))
    hud = _check_preview_part(responses[0].parts[0][1])
    assert hud["rec"]["reasons"] == ["Pr\u00fcfung\r\n"]
    assert response.headers["Cache-Control"] == "no-store"
    assert threads and all(t != threading.get_ident() for t in threads)


def test_two_streams_share_encoding(tmp_path, monkeypatch):
    import itertools
    import time
    from types import SimpleNamespace
    from unittest.mock import Mock

    import cv2
    from test_live_preview import camera_frame

    from dispread.live import preview

    responses = _capture_preview(monkeypatch, limit=None)
    calls = []
    encode = cv2.imencode
    # Lastmessung von der zufaelligen CPU-Last des Testrechners trennen.
    monkeypatch.setattr(preview, "time", SimpleNamespace(monotonic=time.monotonic, perf_counter=lambda: 0.0))

    def spy(*args):
        calls.append(time.monotonic())
        return encode(*args)

    monkeypatch.setattr(cv2, "imencode", spy)
    seqs = itertools.count(7)
    image = camera_frame()
    service = _preview_service(tmp_path, latest=lambda: (next(seqs), image))
    transport = Mock()
    transport.is_closing.return_value = False

    async def check():
        first = asyncio.create_task(_preview_handler(service, transport=transport))
        await asyncio.sleep(0.015)
        second = asyncio.create_task(_preview_handler(service, transport=transport))
        await asyncio.sleep(0.485)
        for task in (first, second):
            task.cancel()
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert all(isinstance(result, asyncio.CancelledError) for result in results)

    start = time.monotonic()
    _run_preview(asyncio.wait_for(check(), 1))
    elapsed = time.monotonic() - start
    assert len(responses) == 2 and all(len(r.parts) >= 3 for r in responses)
    assert len(calls) <= int(elapsed / (1 / 15)) + 1


def test_preview_mjpg_slow_client_ends_stream(tmp_path, monkeypatch):
    import time
    from unittest.mock import Mock

    from test_live_camera import FakeSource

    from dispread.live.camera import CameraOwner
    from dispread.live.service import LiveService

    transport = Mock()
    transport.is_closing.return_value = False
    writing = asyncio.Event()

    class BlockedResponse(web.StreamResponse):
        async def prepare(self, request):
            return None

        async def write(self, data):
            writing.set()
            await asyncio.Future()

    monkeypatch.setattr("dispread.workbench.live_api.web.StreamResponse", BlockedResponse)
    owner = CameraOwner(lambda: FakeSource([1], endless=True))
    service = LiveService(owner, tmp_path, diagnostic_staging_root=tmp_path / "staging")
    owner.start()
    assert owner.wait_newer(0, 1.0) is not None

    async def check():
        start = time.monotonic()
        task = asyncio.create_task(_preview_handler(service, transport=transport))
        await asyncio.wait_for(writing.wait(), 1)
        before = owner.latest()[0]
        await asyncio.wait_for(task, 2.5)
        assert time.monotonic() - start <= 2.5
        assert owner.latest()[0] > before and owner.status()["running"]
        transport.close.assert_called_once()

    try:
        _run_preview(check())
    finally:
        owner.stop()


@pytest.mark.parametrize("missing", [False, True])
def test_preview_mjpg_disconnect_without_new_frames(tmp_path, monkeypatch, missing):
    from unittest.mock import Mock

    responses = _capture_preview(monkeypatch, limit=None)
    service = _preview_service(tmp_path)
    service.preview_frame = Mock(return_value=None)
    transport = None if missing else Mock()
    if transport is not None:
        # Die Kamera liefert kein Bild; danach trennt sich der Betrachter.
        transport.is_closing.side_effect = [False, True]
    _run_preview(asyncio.wait_for(_preview_handler(service, transport=transport), 0.1))
    if missing:
        service.preview_frame.assert_not_called()
    else:
        service.preview_frame.assert_called_once()
    assert responses[0].parts == []


def test_preview_mjpg_write_failure_closes_transport(tmp_path, monkeypatch):
    from unittest.mock import Mock

    _capture_preview(monkeypatch)
    transport = Mock()
    transport.is_closing.return_value = False
    _run_preview(_preview_handler(_preview_service(tmp_path), transport=transport))
    transport.close.assert_called_once()


@pytest.mark.parametrize("first_write_s", [0.015, 0.3])
def test_preview_mjpg_reaches_target_rate_with_instant_encoding(monkeypatch, first_write_s):
    from types import SimpleNamespace

    from dispread.live.preview import PreviewFrame
    from dispread.workbench import live_api

    now = [0.0]
    sent = []
    monkeypatch.setattr(live_api, "time", SimpleNamespace(monotonic=lambda: now[0]))

    async def sleep(delay):
        now[0] += max(delay, 1e-9)

    async def to_thread(fn):
        return fn()

    class Response(web.StreamResponse):
        async def prepare(self, request):
            return None

        async def write(self, data):
            if now[0] >= 1:
                raise ConnectionResetError()
            sent.append(now[0])
            # Schreibdauer darf den Zeitplan nicht pro Bild verschieben.
            now[0] += first_write_s if len(sent) == 1 else 0.015

    monkeypatch.setattr(live_api.asyncio, "sleep", sleep)
    monkeypatch.setattr(live_api.asyncio, "to_thread", to_thread)
    monkeypatch.setattr(live_api.web, "StreamResponse", Response)
    service = SimpleNamespace(preview_frame=lambda: PreviewFrame(
        seq=len(sent), cap_ns=0, jpeg=b"jpeg", hud={"preview": {"fps": 15}}))
    _run_preview(_preview_handler(service))
    assert len(sent) >= (14 if first_write_s == 0.015 else 11)
    assert sent[1] == pytest.approx(max(first_write_s, 1 / 15))
    assert all(b - a == pytest.approx(1 / 15) for a, b in zip(sent[1:], sent[2:], strict=False))


def test_preview_mjpg_limits_rate_and_sends_only_new_sequences(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    from test_live_preview import camera_frame, frame_info

    responses = _capture_preview(monkeypatch, limit=3)
    seqs = iter([7, 7, 8, 9])
    service = _preview_service(tmp_path, latest=lambda: (next(seqs, 9), camera_frame()))
    info = frame_info()
    info["proc"]["skipped_recent"] = 0.2
    service._session = SimpleNamespace(frame_info=lambda: info)
    _run_preview(asyncio.wait_for(_preview_handler(service), 2))
    parts = responses[0].parts
    huds = [json.loads(data.split(b"X-Hud: ")[1].split(b"\r\n")[0]) for _, data in parts]
    assert [h["seq"] for h in huds] == [7, 8, 9]
    assert all(h["preview"] == {"fps": 5, "throttled": "messung"} for h in huds)
    assert all(parts[i][0] - parts[i - 1][0] >= 0.2 for i in (1, 2))


def test_preview_mjpg_expires_after_600s_without_repeating_frame(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from dispread.workbench import live_api

    responses = _capture_preview(monkeypatch, limit=None)
    now = [0.0]
    monkeypatch.setattr(live_api, "time", SimpleNamespace(monotonic=lambda: now[0]), raising=False)

    async def sleep(delay):
        now[0] += 300.0

    monkeypatch.setattr(live_api.asyncio, "sleep", sleep)
    _run_preview(asyncio.wait_for(_preview_handler(_preview_service(tmp_path)), 1))
    assert len(responses[0].parts) == 1 and now[0] == 600.0


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


def test_stream_stall_and_blocked_reconnect_reach_api_without_socket(tmp_path, monkeypatch):
    import json

    from aiohttp.test_utils import make_mocked_request
    from test_live_camera import BlockingSource, FakeSource

    from dispread.live.camera import CameraOwner
    from dispread.live.service import LiveService

    async def direct(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', direct)
    blocked = BlockingSource(emit=False)
    sources = iter([blocked, FakeSource([1], endless=True)])
    owner = CameraOwner(lambda: next(sources))
    service = LiveService(owner, tmp_path, diagnostic_staging_root=tmp_path / 'staging')
    app = web.Application()
    add_live_routes(app, service, csrf_of=lambda _r: 'tok')
    monkeypatch.setattr('dispread.live.camera.STREAM_STALL_TIMEOUT_S', 0.0)
    # Die Quelle liefert kein Bild: es gilt die Anlauffrist.
    monkeypatch.setattr('dispread.live.camera.STREAM_START_TIMEOUT_S', 0.0)
    owner.start()

    async def call(method, path):
        request = make_mocked_request(method, path, app=app)
        match = await app.router.resolve(request)
        return await match.handler(request)

    async def check():
        status = json.loads((await call('GET', '/live/status')).text)
        assert status['camera']['running'] is True
        assert status['camera']['stalled'] is True
        assert 'Streamstillstand' in status['camera']['error']
        response = await call('POST', '/live/camera/start')
        assert response.status == 409
        message = json.loads(response.text)['error']
        assert 'Kamera hängt' in message and 'warten' in message and 'neu stecken' in message
        blocked.release.set()
        assert owner.stop(timeout=1.0) is True
        monkeypatch.setattr('dispread.live.camera.STREAM_STALL_TIMEOUT_S', 2.0)
        monkeypatch.setattr('dispread.live.camera.STREAM_START_TIMEOUT_S', 5.0)
        assert (await call('POST', '/live/camera/start')).status == 200
        assert owner.wait_newer(0, 1.0) is not None
        status = json.loads((await call('GET', '/live/status')).text)
        assert status['camera']['stalled'] is False
        assert status['camera']['error'] is None

    try:
        assert blocked.reading.wait(1.0)
        asyncio.run(check())
    finally:
        blocked.release.set()
        owner.stop(timeout=1.0)


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

    from dispread.workbench.fields import LIVE_CAUSE_TEXT

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
            assert data["cause_texts"] == LIVE_CAUSE_TEXT
        else:
            assert "tracking_reasons" not in data
            assert "cause_texts" not in data
        assert "tracking_reasons" not in service.status()
        assert "cause_texts" not in service.status()

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
        for path in ("/live/status", "/live/preview.jpg", "/static/live/app.js"):
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
        for path in ('/live/run/start', '/live/run/mark', '/live/setup/regions', '/live/setup/cancel'):
            with pytest.raises(web.HTTPForbidden):
                await handle('POST', path, headers)
        headers["Origin"] = "https://localhost"
        for path in ('/live/run/start', '/live/run/mark', '/live/setup/regions', '/live/setup/cancel'):
            with pytest.raises(web.HTTPForbidden):
                await handle('POST', path, headers)
        headers["X-CSRF-Token"] = csrf
        assert (await handle("POST", "/live/run/start", headers)).status == 200
        assert service.calls == [("run", False)]
        assert (await handle('POST', '/live/run/mark', headers, {'text': 'Abdeckung'})).status == 200
        assert service.calls[-1] == ('mark', 'Abdeckung')
        assert (await handle("POST", "/live/run/stop", headers)).status == 409
        assert (await handle("POST", "/live/setup/cancel", headers)).status == 409

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
        owner.start.assert_called_once_with(reason="serverstart")
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
        image, _, proposal = _propose(tmp_path)
        service = ready_service(tmp_path, proposal)
        service._stability_frames = tuple(image.copy() for _ in range(8))
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


@pytest.mark.parametrize('conflict', [
    'running', 'no_proposal', 'outdated_revision', 'no_overlay_evidence', 'no_stability_frames',
])
def test_region_edit_state_conflicts_still_return_409(tmp_path, monkeypatch, conflict):
    from unittest.mock import AsyncMock

    from aiohttp.test_utils import make_mocked_request
    from test_live_service import ready_service
    from test_live_setup_tracking import _propose

    async def direct(fn, **kwargs):
        return fn(**kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', direct)
    image, _, proposal = _propose(tmp_path)
    service = ready_service(tmp_path, proposal)
    service._stability_frames = tuple(image.copy() for _ in range(8))
    revision = proposal['live_tracking']['proposal_revision']
    if conflict == 'running':
        service._state = 'running'
    elif conflict == 'no_proposal':
        service._proposal = None
    elif conflict == 'no_overlay_evidence':
        del service._proposal['overlay_evidence']
    elif conflict == 'no_stability_frames':
        service._stability_frames = ()
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
        elif conflict == 'no_stability_frames':
            assert 'Stabilitaets-Einzelbilder' in response.text and 'neu einrichten' in response.text
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


SCENE_NAMES = (
    'idle', 'setup_focus', 'setup_focus_done', 'setup_standbilder', 'setup_ready_warnung',
    'running_valid', 'running_transition', 'running_rahmen_verdeckt', 'running_stalled',
    'running_anzeige_bewegt', 'stopped',
)


def _assert_real_keys(fake, real, path='status'):
    if isinstance(real, dict):
        assert isinstance(fake, dict), path
        assert fake.keys() >= real.keys(), f'{path}: missing {real.keys() - fake.keys()}'
        for key, value in real.items():
            _assert_real_keys(fake[key], value, f'{path}.{key}')
    elif isinstance(real, list) and real and isinstance(real[0], dict):
        for item in fake:
            _assert_real_keys(item, real[0], f'{path}[]')


def test_fake_full_status_carries_cause_texts(tmp_path):
    from live_ui_server import FakeLiveService

    from dispread.workbench.fields import LIVE_CAUSE_TEXT

    expected = LIVE_CAUSE_TEXT.copy()
    service = FakeLiveService(tmp_path / 'overlay.png')
    for name in SCENE_NAMES:
        service.set_scene(name)
        assert 'cause_texts' not in service.status()
        texts = service.status(full=True)['cause_texts']
        assert texts == expected
        texts['no_value'] = 'geaendert'
        texts.pop('kontrast')
        assert service.status(full=True)['cause_texts'] == expected
        assert 'cause_texts' not in service.status()


def test_fake_status_has_all_real_keys_for_every_scene(tmp_path):
    from live_ui_server import FakeLiveService
    from test_live_session import _session, embed

    from dispread.live.service import LiveService

    session = _session(tmp_path, [embed('+ 1.2345 ')] * 3)
    session.start()
    try:
        session.step()
        real = LiveService(session._owner, tmp_path, diagnostic_staging_root=tmp_path / 'staging')
        fake = FakeLiveService(tmp_path / 'overlay.png')
        for name in SCENE_NAMES:
            fake.set_scene(name)
            status = fake.status(full=True)
            real._state = status['state']
            real._setup_started_at = 0.0 if status['setup'] else None
            real._proposal = None
            if name == 'setup_ready_warnung' or status['run']:
                real._proposal = {'setup_checks': {'overall': 'WARNUNG', 'checks': {
                    'raster': {'status': 'WARNUNG'}, 'gegenlesen': {'status': 'OK'}}},
                    'live_tracking': {'proposal_revision': 'v1', 'proposal': {}}}
            real._session = session if status['run'] else None
            real._run_dir = tmp_path / 'run-01'
            _assert_real_keys(status, real.status(full=True), name)
    finally:
        session.stop()


def test_fake_setup_grid_for_every_scene(tmp_path):
    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'overlay.png')
    for name in SCENE_NAMES:
        service.set_scene(name)
        setup = service.status()['setup']
        if name == 'idle':
            assert setup is None
        elif name in ('setup_focus', 'setup_focus_done', 'setup_standbilder'):
            assert setup['grid'] is None
        else:
            grid = setup['grid']
            assert grid['quad'] == [[810.0, 511.0], [1369.0, 511.0], [1377.0, 580.0], [814.0, 591.0]]
            assert grid['target_size'] == [400, 160]
            assert grid['source'] == 'dot_lattice'
            assert len(grid['cell_boxes']) == 16
            assert grid['cell_boxes'][0] == [0.0, 18.0, 25.0, 142.0]
            assert grid['cell_boxes'][-1] == [375.0, 18.0, 25.0, 142.0]
            grid['cell_boxes'][0][0] = -1
            grid['quad'][0][0] = -1
            assert service.status()['setup']['grid']['quad'][0] == [810.0, 511.0]
            assert service.status()['setup']['grid']['cell_boxes'][0][0] == 0.0


def test_fake_dump_scenes_matches_committed_fixtures(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    fixtures = Path(__file__).parent / 'fixtures' / 'live'
    subprocess.run([sys.executable, str(Path(__file__).with_name('live_ui_server.py')),
                    '--dump-scenes', str(tmp_path)], check=True, env={**os.environ, 'PYTHONPATH': 'src'})
    expected = {f'scene-{name}.json' for name in SCENE_NAMES}
    assert {p.name for p in tmp_path.glob('scene-*.json')} == expected
    assert {p.name for p in fixtures.glob('scene-*.json')} == expected
    for name in expected:
        assert (fixtures / name).read_bytes() == (tmp_path / name).read_bytes(), name
    source = Path('docs/superpowers/specs/2026-11-04-werkbank-redesign-mock/img/still.jpg')
    assert (fixtures / 'still.jpg').read_bytes() == source.read_bytes()


def test_fake_scene_values_and_hud(tmp_path):
    import json

    import cv2
    import numpy as np
    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'overlay.png')
    for name, samples in [('setup_focus', 3), ('setup_focus_done', 9)]:
        service.set_scene(name)
        focus = service.status()['setup']['focus']
        assert [p[0] for p in focus['samples']] == [48, 56, 40, 42, 44, 46, 50, 52, 54][:samples]
        assert [round(p[1]) for p in focus['samples']] == [630, 274, 201, 302, 442, 543, 607, 525, 391][:samples]
        assert (focus['verify'] is None) == (samples == 3)
    service.set_scene('setup_standbilder')
    progress = service.status()['setup']['progress']
    assert progress['phase'] == 'stabilitaet'
    assert progress['wait'] == {'elapsed_s': 9, 'total_s': 15}
    assert service.status()['setup']['exposure']['rounds'] == [{
        'level': 124.0, 'controls': {'focus_absolute': 48, 'exposure_time_absolute': 300,
                                  'white_balance_temperature': 4742, 'gain': 10},
    }]
    for name in SCENE_NAMES:
        service.set_scene(name)
        frame = service.preview_frame()
        hud = frame.hud
        assert frame.seq == hud['seq'] and frame.cap_ns == hud['cap_ns']
        assert hud['w'] == 1920 and hud['h'] == 1080
        assert hud['preview'] == {'fps': 15, 'throttled': None}
        assert len(json.dumps(hud, ensure_ascii=True, separators=(',', ':')).encode('ascii')) <= 2048
        image = cv2.imdecode(np.frombuffer(frame.jpeg, np.uint8), cv2.IMREAD_COLOR)
        assert image.shape == (540, 960, 3)
        if not name.startswith('running_'):
            assert hud['track'] is hud['cells'] is hud['rec'] is None
        else:
            assert hud['track']['quad'] == [[810, 511], [1369, 511], [1377, 580], [814, 591]]
            assert len(hud['cells']) == 16
            assert len(hud['track']['regions']) == len(service.status()['setup']['regions'])
        if name == 'running_rahmen_verdeckt':
            # Hand von rechts (Mock 8a): die Bereiche rechts der Anzeige verlieren ihren Treffer.
            assert [i + 1 for i, r in enumerate(hud['track']['regions']) if not r['ok']] == [4, 7, 8, 12]
        if name == 'running_anzeige_bewegt':
            assert not any(r['ok'] for r in hud['track']['regions'])
        if name == 'running_stalled':
            assert hud['rec']['status'] == 'stale' and hud['rec']['age_s'] > 0.5
            camera = service.status()['camera']
            assert camera['stalled'] and camera['running'] and 'Streamstillstand' in camera['error']
            assert service.preview_frame().seq == frame.seq
        if name == 'running_anzeige_bewegt':
            hint = service.status()['run']['tracking_hint']
            assert hint['kind'] == 'anzeige_bewegt' and hint['since_s'] == 3
            assert service.status()['run']['tracking_hint'] == hint
    with pytest.raises(ValueError):
        service.set_scene('unknown')


def test_fake_controls_without_socket(tmp_path, monkeypatch):
    import json
    from unittest.mock import AsyncMock

    from aiohttp.test_utils import make_mocked_request
    from live_ui_server import make_test_app

    async def direct(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', direct)
    app = make_test_app(tmp_path / 'overlay.png')
    app.freeze()
    auth = {}

    async def call(path, data=None, *, method='POST', authenticated=True):
        headers = {'Host': 'localhost', 'Origin': 'https://localhost'}
        if authenticated:
            headers.update(auth)
        request = make_mocked_request(method, path, headers=headers, app=app)
        request.json = AsyncMock(return_value=data)
        return await app._handle(request)

    async def check():
        # Prueft Middleware und Handler gemeinsam, ohne lokale Sockets.
        with pytest.raises(web.HTTPUnauthorized):
            await call('/test/scene', {'name': 'idle'}, authenticated=False)
        response = await call('/login', {'password': 'test-only'}, authenticated=False)
        auth['Cookie'] = f"dispread_session={response.cookies['dispread_session'].value}"
        response = await call('/live/status', method='GET')
        auth['X-CSRF-Token'] = json.loads(response.text)['csrf']
        assert (await call('/test/scene', {'name': 'setup_ready_warnung'})).status == 200
        before = json.loads((await call('/live/status', method='GET')).text)
        revision = before['setup']['proposal_revision']
        changed = json.loads((await call('/test/revision')).text)['proposal_revision']
        assert changed != revision
        stale = await call('/live/setup/regions', {'proposal_revision': revision, 'add': [], 'remove': [0]})
        assert stale.status == 409 and 'geaendert' in json.loads(stale.text)['error']
        sleeps = []

        async def sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(asyncio, 'sleep', sleep)
        assert (await call('/test/delay', {'path': '/live/setup/regions', 'ms': 1000})).status == 200
        for rev in (changed, changed + '-edit'):
            response = await call('/live/setup/regions', {'proposal_revision': rev, 'add': [[100, 100]], 'remove': []})
            assert response.status == 200, response.text
        assert sleeps == [1.0]  # Genau die naechste POST-Antwort.
        assert (await call('/test/offline', {'on': True})).status == 200
        pending = asyncio.create_task(call('/live/status', method='GET'))
        await asyncio.wait((pending,), timeout=0.02)
        assert not pending.done()
        assert (await call('/test/offline', {'on': False})).status == 200
        assert (await call('/live/status', method='GET')).status == 200
        assert (await asyncio.wait_for(pending, 0.1)).status == 200
        assert (await call('/test/scene', {'name': 'unknown'})).status == 400
        assert (await call('/test/delay', {'path': '/live/setup', 'ms': -1})).status == 400
        assert (await call('/test/offline', {'on': 'yes'})).status == 400
        # Der alte Hook bleibt nutzbar, einschliesslich seiner Bildabmessungen.
        assert (await call('/__test__/state', {'state': 'idle'})).status == 200
        import cv2

        assert cv2.imread(str(tmp_path / 'overlay.png')).shape == (24, 48, 3)
        with pytest.raises(web.HTTPForbidden):
            token = auth.pop('X-CSRF-Token')
            try:
                await call('/test/scene', {'name': 'idle'})
            finally:
                auth['X-CSRF-Token'] = token

    asyncio.run(check())


def test_fake_mjpeg_parts_and_cadence_without_socket(tmp_path, monkeypatch):
    import json

    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'overlay.png')
    service.set_scene('running_rahmen_verdeckt')
    responses = _capture_preview(monkeypatch, limit=3)
    _run_preview(_preview_handler(service))
    parts = responses[0].parts
    sequences = []
    for _, part in parts:
        header, body = part.split(b'\r\n\r\n', 1)
        headers = dict(line.split(b': ', 1) for line in header.split(b'\r\n')[1:])
        assert header.startswith(b'--frame\r\n')
        assert headers[b'Content-Type'] == b'image/jpeg'
        assert len(body) - 2 == int(headers[b'Content-Length'])
        assert body.startswith(b'\xff\xd8') and body.endswith(b'\xff\xd9\r\n')
        assert headers[b'X-Hud'].isascii() and len(headers[b'X-Hud']) <= 2048
        hud = json.loads(headers[b'X-Hud'])
        assert hud['seq'] == int(headers[b'X-Frame-Sequence'])
        assert hud['cap_ns'] == int(headers[b'X-Capture-Ns'])
        assert [i for i, r in enumerate(hud['track']['regions']) if not r['ok']] == [3, 6, 7, 11]
        sequences.append(hud['seq'])
    assert sequences == sorted(set(sequences)) and len(sequences) == 3
    elapsed = parts[-1][0] - parts[0][0]
    assert elapsed >= 2 / 15 - 0.02
    assert elapsed < 0.5


def test_fake_scene_confirmation_preserves_proposal_and_rejects_old_revision(tmp_path):
    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'overlay.png')
    service.set_scene('setup_ready_warnung')
    revision = service.status()['setup']['proposal_revision']
    service.bump_revision()
    with pytest.raises(LiveError, match='geaendert'):
        service.confirm(session_id='test-session', proposal_revision=revision)
    proposal = service.status()['setup']
    service.confirm(session_id='test-session', proposal_revision=proposal['proposal_revision'])
    assert service.status()['state'] == 'confirmed'
    assert service.status()['setup'] == proposal
    service.start_run(test_override=True)
    run = service.status()['run']
    assert run['latest']['status'] == 'unreadable' and run['latest']['value'] is None
    assert all(item[2] is None for item in run['recent'])
    assert service.preview_frame().hud['rec']['status'] == 'unreadable'


def test_fake_run_timing_reference_and_stopped_eval(tmp_path):
    from live_ui_server import SCENES, FakeLiveService

    service = FakeLiveService(tmp_path / 'overlay.png')
    assert service.status()['reference_eval'] is None
    assert service.status()['reference']['latest'] is None
    for scene in SCENES:
        if not scene.startswith('running_'):
            continue
        service.set_scene(scene)
        status = service.status()
        assert status['run']['started_at_utc'] == '2026-11-04T12:00:00+00:00'
        assert status['run']['elapsed_s'] == 60.0
        assert status['run']['ended_at_utc'] is None
        assert status['reference']['latest'] == {
            'cell_text': '+ 0.62427', 'raw': '+00.62427 mV/V', 'value': .62427, 'age_s': .1}
        assert status['reference']['schedule_step'] == {'index': 1, 'factor': 2.0, 'since_s': 12.0}
        assert status['reference_eval'] is None
    before = service.status()['run']['recent']
    service.stop_run()
    status = service.status()
    assert status['run']['recent'] == before
    assert status['run']['ended_at_utc'] == '2026-11-04T12:01:00+00:00'
    assert status['reference_eval'] == {'state': 'done', 'misreads': 0, 'compared_valid': 842,
                                      'undecided_valid': 0, 'uncovered_valid': 0}
    service.set_scene('stopped')
    assert service.status()['run']['ended_at_utc'] == '2026-11-04T12:01:00+00:00'
    assert service.status()['reference_eval']['misreads'] == 0
    service.set_scene('stopped', test_run=True)
    assert service.status()['run']['latest']['value'] is None
    assert service.status()['reference_eval'] == {
        'state': 'error', 'error': 'Abgleich abgelehnt: Testlauf: keine freigegebenen Messwerte '
                                   'fuer einen Referenznachweis'}
    service.set_scene('running_valid', test_run=True)
    service.stop_run()
    assert service.status()['reference_eval']['state'] == 'error'


def test_run_start_forwards_output_configuration():
    async def check(client, service):
        config = {"transport": "tcp", "tcp_port": 5001}
        response = await client.post("/live/run/start", json={"output": config})
        assert response.status == 200
        assert service.output == config

    _run(check)


@pytest.mark.parametrize('config', [
    None, {'transport': 'off'}, {'port': '/fake/output'},
    {'transport': 'serial', 'port': '/fake/output'},
    {'transport': 'uart'}, {'transport': 'tcp'}, {'transport': 'unknown'},
])
def test_unified_output_route_forwards_unchanged_without_socket(monkeypatch, config):
    import json
    from unittest.mock import AsyncMock, Mock

    from aiohttp.test_utils import make_mocked_request

    async def direct(fn, **kwargs):
        return fn(**kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', direct)

    async def check():
        service = FakeService()
        app = web.Application()
        add_live_routes(app, service, csrf_of=lambda _r: 'tok')
        request = make_mocked_request('POST', '/live/run/start', app=app, payload=Mock(at_eof=lambda: False))
        request.json = AsyncMock(return_value={'output': config})
        match = await app.router.resolve(request)
        response = await match.handler(request)
        assert response.status == 200, json.loads(response.text)
        assert service.output == config

    asyncio.run(check())


def test_setup_cancel_route_returns_conflict_and_success_without_socket(tmp_path, monkeypatch):
    import json

    from aiohttp.test_utils import make_mocked_request
    from test_live_service import FakeOwner

    from dispread.live.service import LiveService

    async def direct(fn, **kwargs):
        return fn(**kwargs)

    monkeypatch.setattr(asyncio, 'to_thread', direct)
    service = LiveService(FakeOwner(), tmp_path)
    app = web.Application()
    add_live_routes(app, service, csrf_of=lambda _: 'tok')

    async def check():
        request = make_mocked_request('POST', '/live/setup/cancel', app=app)
        match = await app.router.resolve(request)
        response = await match.handler(request)
        assert response.status == 409
        assert json.loads(response.text) == {'error': 'Keine Einrichtung laeuft'}
        service._state = 'setup_running'
        response = await match.handler(request)
        assert response.status == 200
        assert json.loads(response.text) == {'ok': True}
        assert service._setup_cancel.is_set()

    asyncio.run(check())


@pytest.mark.parametrize('scene', SCENE_NAMES)
def test_fake_setup_cancel(tmp_path, scene):
    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'overlay.png')
    service.set_scene(scene)
    if scene in ('setup_focus', 'setup_focus_done', 'setup_standbilder'):
        service.cancel_setup()
        status = service.status()
        assert status['state'] == 'setup_failed'
        assert status['error'] == 'Einrichtung abgebrochen'
        assert any(step['state'] == 'failed' for step in status['setup']['progress']['steps'])
        service.start_setup()
        assert service.status()['state'] == 'setup_running'
    else:
        with pytest.raises(LiveError, match='Keine Einrichtung laeuft'):
            service.cancel_setup()


def test_fake_focus_roi_in_source_coordinates(tmp_path):
    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'overlay.png')
    for scene in ('setup_focus', 'setup_focus_done'):
        service.set_scene(scene)
        roi = service.status()['setup']['focus']['roi']
        assert roi == [640, 360, 640, 360]
        roi[0] = -1
        assert service.status()['setup']['focus']['roi'][0] == 640


def test_fake_system_cpu_is_available_in_every_scene(tmp_path):
    from live_ui_server import FakeLiveService

    service = FakeLiveService(tmp_path / 'overlay.png')
    for scene in SCENE_NAMES:
        service.set_scene(scene)
        system = service.status()['system']
        assert system == {'cpu_percent': 37.5, 'cpu_window_s': 1.0}
        system['cpu_percent'] = -1
        assert service.status()['system']['cpu_percent'] == 37.5
