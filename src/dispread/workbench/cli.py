"""CLI und lokaler API-Client fuer denselben Kameradienst."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
from pathlib import Path


def default_socket():
    return os.environ.get("DISPREAD_SOCKET", f"/tmp/dispread-{os.getuid()}/control.sock")


async def request(op, args=None, socket_path=None):
    import aiohttp

    async with aiohttp.ClientSession(connector=aiohttp.UnixConnector(path=socket_path or default_socket())) as client:
        async with client.post("http://localhost/command", json={"op": op, "args": args or {}}) as response:
            data = await response.json()
            if response.status != 200:
                raise ValueError(data.get("error", str(response.status)))
            return data


def init_tls(directory, host):
    import ipaddress

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    cert, key = directory / "cert.pem", directory / "key.pem"
    if cert.exists() or key.exists():
        raise ValueError("Zertifikat/Schluessel existiert bereits; nicht ueberschrieben")
    try:
        ipaddress.ip_address(host)
        san = "IP:" + host
    except ValueError:
        if not all(c.isalnum() or c in ".-" for c in host):
            raise ValueError("Ungueltiger Hostname") from None
        san = "DNS:" + host
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:3072",
            "-nodes",
            "-days",
            "365",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=dispread-workbench",
            "-addext",
            f"subjectAltName={san},DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
    )
    key.chmod(0o600)
    print(f"Zertifikat: {cert}\nVor Anmeldung auf Windows vertrauen. Fingerabdruck:")
    subprocess.run(["openssl", "x509", "-in", str(cert), "-noout", "-fingerprint", "-sha256"], check=True)


def parser():
    root = argparse.ArgumentParser(description="Kamera-Workbench und TUI")
    sub = root.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="100.122.154.35")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--camera", type=int, default=0)
    serve.add_argument("--data", default="var/workbench")
    serve.add_argument("--socket", default=default_socket())
    serve.add_argument("--cert", default="var/workbench/tls/cert.pem")
    serve.add_argument("--key", default="var/workbench/tls/key.pem")
    serve.add_argument("--simulate", action="store_true", help="Testbilder; kein Kamerazugriff")
    for name, kind in (("width", int), ("height", int), ("fps", float)):
        serve.add_argument("--" + name, type=kind)
    for name in ("min-area", "max-area", "min-aspect", "max-aspect", "min-rectangularity"):
        serve.add_argument("--" + name, type=float)
    sub.add_parser("tui")
    sub.add_parser("status")
    sub.add_parser("stop", help="laufenden Dienst ueber den lokalen Socket sauber beenden")
    mode = sub.add_parser("mode")
    mode.add_argument("value", choices=["setup", "run", "annotate"])
    profile = sub.add_parser("profile")
    profile.add_argument("action", choices=["load", "save", "revert", "resolve", "role"])
    profile.add_argument("value", nargs="?")
    camera = sub.add_parser("camera")
    camera.add_argument("action", choices=["get", "set", "auto-setup", "accept", "cancel", "focus"])
    camera.add_argument("key", nargs="?")
    camera.add_argument("value", nargs="?")
    tls = sub.add_parser("init-tls")
    tls.add_argument("--directory", default="var/workbench/tls")
    tls.add_argument("--host", default="100.122.154.35")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "serve":
            from .server import serve

            asyncio.run(serve(args))
            return 0
        if args.command == "init-tls":
            init_tls(args.directory, args.host)
            return 0
        if args.command == "tui":
            from .tui import WorkbenchTUI

            WorkbenchTUI().run()
            return 0
        op, values = ("server.stop" if args.command == "stop" else args.command), {}
        if args.command == "mode":
            values = {"value": args.value}
        elif args.command == "profile":
            op = "profile." + args.action
            if args.action == "load" and not args.value:
                raise ValueError("Profilname fehlt")
            values = {"name": args.value} if args.action in ("save", "load") else {"value": args.value}
        elif args.command == "camera":
            if args.action == "get":
                op = "status"
            elif args.action == "set":
                if not args.key or args.value is None:
                    raise ValueError("camera set KEY JSON-WERT, z.B. AeEnable false")
                op, values = "camera.set", {"key": args.key, "value": json.loads(args.value)}
            elif args.action == "focus":
                if args.key not in ("on", "off"):
                    raise ValueError("camera focus on|off")
                op, values = "focus", {"value": args.key == "on"}
            else:
                op = {"auto-setup": "auto.start", "accept": "auto.accept", "cancel": "auto.cancel"}[args.action]
        print(json.dumps(asyncio.run(request(op, values)), indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, ImportError, subprocess.CalledProcessError) as error:
        print(f"dispread: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
