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


def positive_days(value):
    days = int(value)
    if days <= 0:
        raise argparse.ArgumentTypeError('Tage muessen positiv sein')
    return days


def bridge_command(args):
    """Local OS-authorized provisioning/export only; never start a measurement."""
    from dataclasses import asdict

    from dispread.bridge.identity import DeviceIdentity, local_hardware_id
    from dispread.bridge.pairing import PairingStore
    from dispread.bridge.protocol import parse_profile
    from dispread.bridge.types import BridgeProfile

    if args.action in ('prepare-uart', 'stop-uart', 'status'):
        print(json.dumps(asyncio.run(request('bridge.' + args.action, socket_path=args.socket)), indent=2))
        return
    directory = Path(args.directory)
    if args.action == "revoke":
        PairingStore(directory / "pairing").revoke(args.client_id)
        print("Client-Zugang widerrufen")
        return
    load = DeviceIdentity.load_or_create if args.action == "identity" and args.provision else DeviceIdentity.load
    identity = load(directory, local_hardware_id())
    if args.action == "identity":
        print(json.dumps({"pi_id": identity.pi_id, "certificate_sha256": identity.fingerprint}, indent=2))
        return
    profile = BridgeProfile(
        schema=1, pi_id=identity.pi_id, name=args.name,
        certificate_pem=identity.certificate_pem, certificate_sha256=identity.fingerprint,
        endpoints=tuple(args.endpoint), protocol_version=2,
    )
    # Validate all operator-provided configuration before issuing an offer.
    parse_profile(json.dumps(asdict(profile)).encode("utf-8"))
    # Exclusive creation prevents accidental replacement of an exported profile.
    fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            value = asdict(profile)
            if args.pair:
                value["pairing_offer"] = PairingStore(directory / "pairing").create_offer(args.transport, args.client_id)
            raw = json.dumps(value, indent=2, ensure_ascii=False)
            parse_profile(raw.encode("utf-8"))
            stream.write(raw + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        Path(args.output).unlink(missing_ok=True)
        raise
    print(f"Verbindungsprofil: {args.output}")


def parser():
    root = argparse.ArgumentParser(description="Kamera-Workbench und TUI")
    sub = root.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--pam-user", default=None, help="PAM-Konto; sonst DISPREAD_PAM_USER oder lokales Dienstkonto")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--bridge-directory", help="Bestehende Pi-Identitaet als HTTPS-/Bridge-Identitaet laden; keine Provisionierung")
    serve.add_argument("--bridge-endpoint", action="append", default=[], help="Expliziter LAN-/Tailscale-HTTPS/WSS-Endpunkt fuer das Profil")
    serve.add_argument("--bridge-name", default="Dispread Pi")
    serve.add_argument("--bridge-discovery", action="store_true", help="Oeffentliche DNS-SD-Hinweise mit optionalem python3-zeroconf anbieten")
    serve.add_argument("--camera", type=int, default=0)
    serve.add_argument("--data", default="var/workbench")
    serve.add_argument("--live-data", default="var/live")
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
    live = sub.add_parser("live", help="Live-Einrichtung lokal steuern; Bestaetigung und Laufstart auf /live")
    live_sub = live.add_subparsers(dest="action", required=True)
    live_sub.add_parser("status")
    live_setup = live_sub.add_parser("setup")
    live_setup.add_argument("--cell-text")
    live_setup.add_argument("--force", action="store_true")
    live_sub.add_parser("stop")
    live_sub.add_parser("camera")
    live_sub.add_parser('mark').add_argument('text')
    cleanup = live_sub.add_parser('aufraeumen', help='Alte Live-Laeufe listen; Loeschen nur mit --ausfuehren')
    cleanup.add_argument('--aelter-als', type=positive_days, required=True, metavar='TAGE')
    cleanup.add_argument('--nur-diagnose', action='store_true')
    cleanup.add_argument('--ausfuehren', action='store_true')
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
    tls.add_argument("--host", default="127.0.0.1")
    bridge = sub.add_parser("bridge", help="Pi-Identitaet und lokale Kopplung ohne Messstart")
    bridge_sub = bridge.add_subparsers(dest="action", required=True)
    for action in ('prepare-uart', 'stop-uart', 'status'):
        local = bridge_sub.add_parser(action)
        local.add_argument('--socket', default=default_socket())
    identity = bridge_sub.add_parser("identity")
    identity.add_argument("--directory", default="var/workbench/bridge")
    identity.add_argument("--provision", action="store_true", help="Neue Identitaet nur bei fehlender Einrichtung erzeugen")
    export = bridge_sub.add_parser("export-profile")
    export.add_argument("--directory", default="var/workbench/bridge")
    export.add_argument("--output", required=True)
    export.add_argument("--name", required=True)
    export.add_argument("--endpoint", action="append", default=[])
    export.add_argument("--pair", action="store_true", help="Einmalangebot fuer 300 Sekunden hinzufuegen")
    export.add_argument("--transport", choices=["network", "uart"], default="network")
    export.add_argument("--client-id")
    revoke = bridge_sub.add_parser("revoke")
    revoke.add_argument("--directory", default="var/workbench/bridge")
    revoke.add_argument("client_id")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "bridge":
            bridge_command(args)
            return 0
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
        if args.command == "live":
            op = "live." + args.action
            if args.action == "setup" and args.cell_text is not None:
                values = {"cell_text": args.cell_text}
            if args.action == "setup" and args.force:
                values["force"] = True
            if args.action == 'mark':
                values = {'text': args.text}
            if args.action == 'aufraeumen':
                values = {'days': args.aelter_als, 'diagnostics_only': args.nur_diagnose,
                          'execute': args.ausfuehren}
        elif args.command == "mode":
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
        result = asyncio.run(request(op, values))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if op == 'live.aufraeumen' and result.get('failed'):
            return 1
        return 0
    except (ValueError, OSError, ImportError, subprocess.CalledProcessError) as error:
        print(f"dispread: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
