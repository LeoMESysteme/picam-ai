"""HTTPS und lokaler privater Steuer-Socket fuer die Workbench."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import pwd
import ssl
from pathlib import Path

import cv2
from aiohttp import WSMsgType, web

from .auth import Sessions, authenticate
from .controller import Controller
from .fields import actions, rows
from .terminals import Terminals

STATIC = Path(__file__).parent / "static"
COOKIE = "dispread_session"


def same_origin(request):
    return request.headers.get("Origin") == f"https://{request.host}"


def make_app(controller, terminals, verifier=authenticate):
    sessions = Sessions()

    @web.middleware
    async def guard(request, handler):
        public = request.path in ("/login", "/static/login.css", "/static/login.js")
        session = sessions.get(request.cookies.get(COOKIE))
        if not public and not session:
            if request.path == "/":
                raise web.HTTPFound("/login")
            raise web.HTTPUnauthorized()
        if request.method not in ("GET", "HEAD"):
            if not same_origin(request):
                raise web.HTTPForbidden(text="Origin rejected")
            if not public and request.headers.get("X-CSRF-Token") != session["csrf"]:
                raise web.HTTPForbidden(text="CSRF rejected")
        try:
            response = await handler(request)
        except (ValueError, KeyError, TypeError, OSError) as error:
            response = web.json_response({"error": str(error)}, status=400)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'",
            }
        )
        return response

    app = web.Application(middlewares=[guard], client_max_size=64 * 1024)

    async def login(request):
        if request.method == "GET":
            return web.FileResponse(STATIC / "login.html")
        if not sessions.allow_attempt(request.remote):
            raise web.HTTPTooManyRequests(text="Bitte spaeter erneut versuchen")
        data = await request.json()
        password = data.get("password", "")
        if not isinstance(password, str) or not password or len(password) > 1024:
            raise web.HTTPUnauthorized()
        valid = await asyncio.to_thread(verifier, password)
        if not valid:
            raise web.HTTPUnauthorized(text="Anmeldung fehlgeschlagen")
        token = sessions.create()
        response = web.json_response({"ok": True})
        response.set_cookie(COOKIE, token, secure=True, httponly=True, samesite="Strict", max_age=8 * 3600)
        return response

    async def logout(request):
        sessions.sessions.pop(request.cookies.get(COOKIE), None)
        response = web.json_response({"ok": True})
        response.del_cookie(COOKIE)
        return response

    async def index(_):
        return web.FileResponse(STATIC / "index.html")

    async def status(request):
        result = controller.snapshot()
        result["csrf"] = sessions.get(request.cookies.get(COOKIE))["csrf"]
        result["terminals"] = terminals.list()
        result["setup"] = {"rows": rows(result), "actions": actions(result)}
        return web.json_response(result)

    async def command(request):
        data = await request.json()
        return web.json_response(controller.command(data["op"], data.get("args")))

    async def frozen(request):
        with controller.lock:
            image = controller.frames[request.match_info["id"]]["image"]
            ok, jpeg = cv2.imencode(".jpg", image)
        if not ok:
            raise ValueError("JPEG fehlgeschlagen")
        return web.Response(body=jpeg.tobytes(), content_type="image/jpeg")

    async def stream(request):
        if not controller.snapshot()["live"]:
            raise web.HTTPServiceUnavailable()
        response = web.StreamResponse(
            headers={"Content-Type": "multipart/x-mixed-replace; boundary=frame", "Cache-Control": "no-store"}
        )
        await response.prepare(request)
        previous = -1
        try:
            while sessions.get(request.cookies.get(COOKIE)):
                with controller.lock:
                    live = controller.snapshot()["live"]
                    sequence, jpeg = controller.sequence, controller.jpeg
                if not live:
                    break
                if previous != sequence:
                    await asyncio.wait_for(
                        response.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                            + str(len(jpeg)).encode()
                            + b"\r\n\r\n"
                            + jpeg
                            + b"\r\n"
                        ),
                        2,
                    )
                    previous = sequence
                await asyncio.sleep(0.03)
        except (ConnectionError, TimeoutError):
            pass
        return response

    async def new_terminal(_):
        return web.json_response({"id": terminals.create().id})

    async def close_terminal(request):
        terminal = terminals.items.pop(request.match_info["id"])
        await terminal.close()
        return web.json_response({"ok": True})

    async def websocket(request):
        if not same_origin(request):
            raise web.HTTPForbidden(text="Origin rejected")
        terminal = terminals.items[request.match_info["id"]]
        ws = web.WebSocketResponse(heartbeat=15, max_msg_size=32768)
        await ws.prepare(request)
        token = request.cookies.get(COOKIE)

        async def output():
            position = terminal.offset
            await ws.send_json({"reset": True, "truncated": terminal.offset > 0})
            while not ws.closed and sessions.get(token) and not terminal.closed:
                if position < terminal.offset:
                    position = terminal.offset
                    await ws.send_json({"reset": True, "truncated": True})
                start = position - terminal.offset
                data = bytes(terminal.buffer[start : start + 65536])
                if data:
                    await ws.send_bytes(data)
                    position += len(data)
                elif terminal.exit_code is not None:
                    await ws.send_json({"exit_code": terminal.exit_code})
                    break
                await asyncio.sleep(0.03)
            await ws.close()

        task = asyncio.create_task(output())
        try:
            async for message in ws:
                if not sessions.get(token):
                    break
                if message.type == WSMsgType.BINARY:
                    await terminal.write(message.data)
                elif message.type == WSMsgType.TEXT:
                    data = json.loads(message.data)
                    if data.get("type") == "resize":
                        terminal.resize(int(data["cols"]), int(data["rows"]))
                elif message.type == WSMsgType.ERROR:
                    break
        except (ValueError, OSError):
            pass
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, ConnectionError):
                await task
            await ws.close()
        return ws

    app.router.add_route("GET", "/login", login)
    app.router.add_route("POST", "/login", login)
    app.router.add_post("/logout", logout)
    app.router.add_get("/", index)
    app.router.add_get("/status", status)
    app.router.add_post("/command", command)
    app.router.add_get("/frozen/{id}.jpg", frozen)
    app.router.add_get("/stream.mjpg", stream)
    app.router.add_post("/terminals", new_terminal)
    app.router.add_delete("/terminals/{id}", close_terminal)
    app.router.add_get("/terminals/{id}/ws", websocket)
    app.router.add_static("/static", STATIC)
    return app


async def serve(args):
    if os.geteuid() == 0 or pwd.getpwuid(os.geteuid()).pw_name != "me-systeme":
        raise ValueError("Workbench als me-systeme starten, nicht mit sudo")
    import signal

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    runtime = Path(args.socket).parent
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    if runtime.stat().st_uid != os.getuid() or runtime.stat().st_mode & 0o077:
        raise ValueError("Socket-Verzeichnis muss dem Benutzer gehoeren und Modus 0700 haben")
    # Prevent two camera owners without blindly removing a live socket.
    import fcntl

    lockfile = (runtime / "workbench.lock").open("a")
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise ValueError("Workbench laeuft bereits") from error
    socket_path = Path(args.socket)
    socket_path.unlink(missing_ok=True)
    controller = Controller(args.data, args.camera, args.simulate)
    data = controller.snapshot()["config"]
    for name in ("width", "height", "fps"):
        if getattr(args, name, None) is not None:
            data["camera"][name] = getattr(args, name)
    for name in data["detection"]:
        if getattr(args, name, None) is not None:
            data["detection"][name] = getattr(args, name)
    if data != controller.config:
        controller._change(data)
    terminals = Terminals(Path.cwd(), socket_path)
    runner = web.AppRunner(make_app(controller, terminals), access_log=None)
    local = web.Application()

    async def control(request):
        try:
            data = await request.json()
            if data["op"] == "server.stop":
                stop.set()
                return web.json_response({"stopping": True})
            return web.json_response(controller.command(data["op"], data.get("args")))
        except (ValueError, KeyError, TypeError, OSError) as error:
            return web.json_response({"error": str(error)}, status=400)

    local.router.add_post("/command", control)
    unix = web.AppRunner(local, access_log=None)

    async def watch():
        while not stop.is_set():
            try:
                controller.watch_profile()
            except OSError as error:
                controller.log("error", f"Profil-Watcher: {error}")
            await asyncio.sleep(0.5)

    watcher = None
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_alpn_protocols(["http/1.1"])
        context.load_cert_chain(args.cert, args.key)
        await runner.setup()
        await unix.setup()
        await web.UnixSite(unix, str(socket_path)).start()
        os.chmod(socket_path, 0o600)
        await web.TCPSite(runner, args.host, args.port, ssl_context=context).start()
        controller.start()
        watcher = asyncio.create_task(watch())
        print(f"Workbench: https://{args.host}:{args.port} | Anmeldung: me-systeme", flush=True)
        await stop.wait()
    finally:
        if watcher:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher
        await terminals.close()
        await asyncio.to_thread(controller.close)
        await runner.cleanup()
        await unix.cleanup()
        socket_path.unlink(missing_ok=True)
        lockfile.close()
