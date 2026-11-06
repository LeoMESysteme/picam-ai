"""HTTPS und lokaler privater Steuer-Socket fuer die Workbench."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import pwd
import re
import ssl
import tempfile
from pathlib import Path

import cv2
from aiohttp import WSMsgType, web

from dispread.camera_settings import preview_settings
from dispread.frames import open_source
from dispread.frames.uvc_source import UvcSource
from dispread.live import LIVE_CV_THREADS, LIVE_DATA_DIR
from dispread.live.camera import CameraOwner
from dispread.live.service import LiveError, LiveService

from .auth import Sessions, authenticate, pam_username
from .controller import Controller
from .datasets import zip_export
from .fields import actions, rows
from .live_api import add_live_routes
from .terminals import Terminals

_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")

STATIC = Path(__file__).parent / "static"
COOKIE = "dispread_session"


def same_origin(request):
    return request.headers.get("Origin") == f"https://{request.host}"


def make_app(controller, terminals, verifier=authenticate, live=None, *,
             bridge_identity=None, bridge_pairing_store=None, bridge_hub=None,
             bridge_endpoints=(), bridge_name="Dispread Pi"):
    bridge_public_paths = frozenset()
    if bridge_identity is not None:
        from dispread.bridge.routes import PUBLIC_PATHS, add_bridge_routes
        bridge_public_paths = PUBLIC_PATHS

    sessions = Sessions()

    @web.middleware
    async def guard(request, handler):
        bridge_public = request.path in bridge_public_paths
        if bridge_public:
            # These TLS endpoints enforce their own scoped credential/offer auth;
            # browser cookies and browser CSRF do not authorize them.
            return await handler(request)
        public = request.path in ("/login", "/static/login.css", "/static/login.js")
        session = sessions.get(request.cookies.get(COOKIE))
        if not public and not session:
            if request.method in ("GET", "HEAD") and request.path == "/live":
                raise web.HTTPFound("/login?next=/live")
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
        target = request.query.get("next", "/")
        if (not target.startswith("/") or target.startswith("//")
                or "\\" in target or any(ord(char) <= 32 or ord(char) == 127 for char in target)):
            target = "/"
        response = web.json_response({"ok": True, "next": target})
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

    async def dataset_capture_preview(request):
        token = request.match_info["token"]
        if not _TOKEN_RE.fullmatch(token):
            raise ValueError("Ungueltiger Aufnahme-Token")
        with controller.lock:
            image = controller.dataset_captures.get(token)["image"]
            ok, jpeg = cv2.imencode(".jpg", image)
        if not ok:
            raise ValueError("JPEG fehlgeschlagen")
        return web.Response(body=jpeg.tobytes(), content_type="image/jpeg")

    async def dataset_export_download(request):
        export_id = request.match_info["id"]
        export_dir = controller.dataset_store.get_export_dir(export_id)

        def build():
            with tempfile.TemporaryDirectory() as scratch:
                zip_path = Path(scratch) / f"{export_id}.zip"
                zip_export(export_dir, zip_path)
                return zip_path.read_bytes()

        data = await asyncio.to_thread(build)
        return web.Response(
            body=data,
            content_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{export_id}.zip"'},
        )

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
    app.router.add_get("/dataset/captures/{token}.jpg", dataset_capture_preview)
    app.router.add_get("/dataset/exports/{id}.zip", dataset_export_download)
    app.router.add_get("/stream.mjpg", stream)
    app.router.add_post("/terminals", new_terminal)
    app.router.add_delete("/terminals/{id}", close_terminal)
    app.router.add_get("/terminals/{id}/ws", websocket)
    app.router.add_static("/static", STATIC)
    if live is not None:
        add_live_routes(app, live, csrf_of=lambda request: sessions.get(request.cookies.get(COOKIE))["csrf"])
    if bridge_identity is not None:
        if bridge_pairing_store is None:
            raise ValueError("Bridge identity requires its pairing store")

        def authorize_operator(request):
            session = sessions.get(request.cookies.get(COOKIE))
            if session is None:
                raise web.HTTPUnauthorized()
            if request.method not in ("GET", "HEAD"):
                if not same_origin(request) or request.headers.get("X-CSRF-Token") != session["csrf"]:
                    raise web.HTTPForbidden(text="CSRF rejected")

        add_bridge_routes(app, bridge_identity, bridge_pairing_store, bridge_hub,
                          authorize_operator, endpoints=bridge_endpoints, name=bridge_name)
    return app


def service_pam_user(configured=None):
    username = pam_username(configured)
    if os.geteuid() == 0 or pwd.getpwuid(os.geteuid()).pw_name != username:
        raise ValueError("Workbench ohne sudo unter dem konfigurierten PAM-Konto starten")
    return username


def bridge_service_config(args):
    """Explicit opt-in: load existing identity, never provision or replace TLS."""
    directory = getattr(args, "bridge_directory", None)
    if directory is None:
        if getattr(args, "bridge_endpoint", ()) or getattr(args, "bridge_discovery", False):
            raise ValueError("Bridge endpoints/discovery require --bridge-directory")
        return {}, None
    from dispread.bridge.identity import DeviceIdentity, local_hardware_id
    from dispread.bridge.pairing import PairingStore

    identity = DeviceIdentity.load(Path(directory), local_hardware_id())
    return dict(bridge_identity=identity, bridge_pairing_store=PairingStore(identity.directory / "pairing"),
                bridge_endpoints=tuple(getattr(args, "bridge_endpoint", ())),
                bridge_name=getattr(args, "bridge_name", "Dispread Pi")), identity.tls_context()


async def handle_local_op(op, args, controller, live, bridge_hub=None):
    """Lokale Live-Steuerung; Bestaetigung und Laufstart bleiben auf /live."""
    try:
        if op.startswith('bridge.'):
            if bridge_hub is None:
                raise ValueError('Bridge hub not configured')
            if args:
                raise ValueError('Bridge local action takes no arguments')
            if op == 'bridge.prepare-uart':
                return web.json_response(await asyncio.to_thread(bridge_hub.prepare_uart))
            if op == 'bridge.stop-uart':
                return web.json_response(await asyncio.to_thread(bridge_hub.stop_uart))
            if op == 'bridge.status':
                return web.json_response(bridge_hub.status())
            raise ValueError('Unknown bridge action')
        if not op.startswith("live."):
            return web.json_response(controller.command(op, args))
        if op == "live.status":
            return web.json_response(await asyncio.to_thread(live.status))
        if op == 'live.aufraeumen':
            return web.json_response(await asyncio.to_thread(live.cleanup, **(args or {})))
        if op == "live.setup":
            status = await asyncio.to_thread(live.status)
            if status["state"] in {"setup_ready", "confirmed"} and not (args or {}).get("force"):
                raise LiveError("Vorschlag vorhanden - auf /live pruefen oder live setup --force verwenden")
            await asyncio.to_thread(live.start_setup, cell_text=(args or {}).get("cell_text"))
        elif op == "live.stop":
            await asyncio.to_thread(live.stop_run)
        elif op == 'live.mark':
            await asyncio.to_thread(live.mark, text=(args or {}).get('text'))
        elif op == "live.camera":
            await asyncio.to_thread(live.start_camera)
        else:
            return web.json_response(
                {"error": "Live-Operation lokal nicht erlaubt; Bestaetigung und Laufstart auf der Seite /live."},
                status=400,
            )
        return web.json_response({"ok": True})
    except LiveError as error:
        return web.json_response({"error": str(error)}, status=409)
    except (ValueError, KeyError, TypeError, OSError) as error:
        return web.json_response({"error": str(error)}, status=400)


async def serve(args):
    username = service_pam_user(getattr(args, "pam_user", None))
    bridge_config, bridge_tls = bridge_service_config(args)
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
    # Einmal vor jedem Kamera-/Lesethread: OpenCV-Threads begrenzen, damit
    # der Pi bedienbar bleibt. Nie waehrend laufender OpenCV-Threads
    # umschalten (Thread-Pool wird dabei neu aufgebaut).
    cv2.setNumThreads(LIVE_CV_THREADS)
    if args.simulate:
        owner = CameraOwner(lambda: open_source("synthetic://seven-seg"), max_fps=10)
    else:
        owner = CameraOwner(lambda: UvcSource(preview_settings(), apply_controls=False))
    bridge_hub = None
    if bridge_config:
        from dispread.bridge.hub import BridgeHub
        bridge_hub = BridgeHub(bridge_config['bridge_identity'].pi_id,
                               Path(getattr(args, 'live_data', LIVE_DATA_DIR)) / 'bridge',
                               identity=bridge_config['bridge_identity'],
                               pairing_store=bridge_config['bridge_pairing_store'])
        bridge_config['bridge_hub'] = bridge_hub
    live = LiveService(owner, Path(getattr(args, "live_data", LIVE_DATA_DIR)),
                       simulate=args.simulate, bridge_hub=bridge_hub)
    controller = Controller(args.data, args.camera, args.simulate, owner=owner)
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
    runner = web.AppRunner(make_app(controller, terminals, live=live,
                                   verifier=lambda password: authenticate(password, username=username),
                                   **bridge_config), access_log=None)
    local = web.Application()

    async def control(request):
        try:
            data = await request.json()
            if data["op"] == "server.stop":
                stop.set()
                return web.json_response({"stopping": True})
            return await handle_local_op(data["op"], data.get("args"), controller, live, bridge_hub)
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
    publication = None
    try:
        context = bridge_tls
        if context is None:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(args.cert, args.key)
        context.set_alpn_protocols(["http/1.1"])
        await runner.setup()
        await unix.setup()
        await web.UnixSite(unix, str(socket_path)).start()
        os.chmod(socket_path, 0o600)
        await web.TCPSite(runner, args.host, args.port, ssl_context=context).start()
        if getattr(args, "bridge_discovery", False):
            from dispread.bridge.discovery import publish_service
            try:
                publication = await asyncio.to_thread(
                    publish_service, bridge_config["bridge_identity"], bridge_config["bridge_endpoints"],
                    name=bridge_config["bridge_name"],
                )
            except (ImportError, OSError, ValueError) as error:
                controller.log("error", f"Bridge discovery unavailable: {type(error).__name__}; configured endpoints remain usable")
        controller.start()
        try:
            owner.start(reason="serverstart")
        except Exception as error:  # noqa: BLE001 - Server laeuft weiter, Seite zeigt den Fehler
            controller.log("error", f"Kamera: {error}")
        watcher = asyncio.create_task(watch())
        print(f"Workbench: https://{args.host}:{args.port} | Anmeldung: {username}", flush=True)
        await stop.wait()
    finally:
        if publication is not None:
            # Optional discovery must not prevent camera/socket shutdown.
            with contextlib.suppress(Exception):
                await asyncio.to_thread(publication.close)
        if watcher:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher
        # Reihenfolge ist sicherheitsrelevant fuer ein saubers Beenden: solange
        # runner/unix noch Verbindungen annehmen, kann "POST /terminals" (oder
        # der lokale Steuersocket) zwischen SIGINT und hier eine neue Shell
        # anlegen, die terminals.close() nie zu Gesicht bekommt. Ihr
        # Reap-Task (asyncio.to_thread(subprocess.wait)) haengt dann fuer
        # immer in einem Worker-Thread des Default-Executors - und genau den
        # joint asyncio.run() beim eigenen, unterbrechungsfreien Abbau nach
        # dem Ende dieser Funktion. Ergebnis: der Prozess reagiert auf kein
        # weiteres Ctrl+C mehr, weil der Event-Loop und sein Signal-Handler zu
        # diesem Zeitpunkt schon weg sind (beobachteter Bug: eine ueber die
        # Werkbank-Oberflaeche angelegte Shell blieb so als Zombie-Aufnahme
        # zurueck). Erst wenn runner/unix nichts mehr annehmen, ist
        # terminals.close() garantiert vollstaendig.
        await runner.cleanup()
        await unix.cleanup()
        await terminals.close()
        await asyncio.to_thread(controller.close)
        try:
            await asyncio.to_thread(live.close)
        except Exception as error:  # noqa: BLE001 - Kamera und Socket trotzdem freigeben
            controller.log("error", f"Live: {error}")
        if bridge_hub is not None:
            try:
                await asyncio.to_thread(bridge_hub.close)
            except Exception:
                controller.log('error', 'Bridge cleanup failed')
        await asyncio.to_thread(owner.stop)
        socket_path.unlink(missing_ok=True)
        lockfile.close()
