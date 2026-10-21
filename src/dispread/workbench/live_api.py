"""HTTP-Routen der Live-Seite. Nur Weiterreichen an LiveService."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from aiohttp import web

from dispread.live.service import LiveError

STATIC = Path(__file__).parent / "static"


def add_live_routes(app: web.Application, service, csrf_of: Callable[[web.Request], str]) -> None:
    async def page(_request):
        return web.FileResponse(STATIC / "live.html")

    async def status(request):
        data = await asyncio.to_thread(service.status)
        data["csrf"] = csrf_of(request)
        return web.json_response(data)

    async def _call(fn, **kwargs):
        try:
            await asyncio.to_thread(fn, **kwargs)
        except LiveError as exc:
            return web.json_response({"error": str(exc)}, status=409)
        return web.json_response({"ok": True})

    async def setup(request):
        data = await request.json() if request.can_read_body else {}
        return await _call(service.start_setup, cell_text=data.get("cell_text"))

    async def confirm(request):
        data = await request.json()
        return await _call(
            service.confirm,
            session_id=data.get("session_id", ""),
            confirmed_by=str(data.get("confirmed_by", "")),
            format_checked=bool(data.get("format_checked")),
            acknowledge_warning=bool(data.get("acknowledge_warning")),
            use_tolerance=bool(data.get("use_tolerance", False)),
        )

    async def run_start(request):
        data = await request.json() if request.can_read_body else {}
        return await _call(service.start_run, test_override=bool(data.get("test_override")))

    async def run_stop(_request):
        return await _call(service.stop_run)

    async def camera_start(_request):
        return await _call(service.start_camera)

    async def setup_image(request):
        path = service.setup_file(request.match_info["name"])
        if path is None:
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def preview(_request):
        jpeg = await asyncio.to_thread(service.preview_jpeg)
        if jpeg is None:
            raise web.HTTPServiceUnavailable()
        return web.Response(body=jpeg, content_type="image/jpeg")

    app.router.add_get("/live", page)
    app.router.add_get("/live/status", status)
    app.router.add_post("/live/setup", setup)
    app.router.add_post("/live/confirm", confirm)
    app.router.add_post("/live/run/start", run_start)
    app.router.add_post("/live/run/stop", run_stop)
    app.router.add_post("/live/camera/start", camera_start)
    app.router.add_get("/live/setup/{name}.png", setup_image)
    app.router.add_get("/live/preview.jpg", preview)
