"""CLI und lokaler API-Client fuer denselben Kameradienst."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from dispread.defaults import BRIDGE_DIR, LIVE_DATA_DIR, SERVE_PORT, TLS_CERT, TLS_DIR, TLS_KEY, WORKBENCH_DATA_DIR

if TYPE_CHECKING:
    from dispread.admin.instance import Instance


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


TLS_DAYS = 365
TLS_SUBJECT = "/CN=dispread-workbench"


def _host_san(host):
    import ipaddress

    if not host or not host.strip():
        raise ValueError('Adresse angeben, unter der Windows den Pi erreicht (--host <adresse>)')
    try:
        ipaddress.ip_address(host)
        return "IP:" + host
    except ValueError:
        if not all(c.isalnum() or c in ".-" for c in host):
            raise ValueError("Ungueltiger Hostname") from None
        return "DNS:" + host


def _openssl_certificate(key_args, cert, san, days=TLS_DAYS):
    """Selbstsigniertes Zertifikat wie bei init-tls; ``key_args`` waehlt neuen oder vorhandenen Schluessel."""
    subprocess.run(
        ["openssl", "req", "-x509", *key_args, "-days", str(days), "-out", str(cert),
         "-subj", TLS_SUBJECT, "-addext", f"subjectAltName={san}"],
        check=True,
    )


def init_tls(directory, host):
    san = _host_san(host)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    cert, key = directory / "cert.pem", directory / "key.pem"
    if cert.exists() or key.exists():
        raise ValueError("Zertifikat/Schluessel existiert bereits; nicht ueberschrieben")
    _openssl_certificate(["-newkey", "rsa:3072", "-nodes", "-keyout", str(key)], cert,
                         f"{san},DNS:localhost,IP:127.0.0.1")
    key.chmod(0o600)
    print(f"Zertifikat: {cert}\nVor Anmeldung auf Windows vertrauen. Fingerabdruck:")
    subprocess.run(["openssl", "x509", "-in", str(cert), "-noout", "-fingerprint", "-sha256"], check=True)


def _san_entries(cert):
    from cryptography import x509

    try:
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return []
    san = []
    for name in names:
        if isinstance(name, x509.DNSName):
            san.append(f'DNS:{name.value}')
        elif isinstance(name, x509.IPAddress):
            san.append(f'IP:{name.value}')
        elif isinstance(name, x509.UniformResourceIdentifier):
            san.append(f'URI:{name.value}')
    return san


def renew_tls(directory, host=None, days=TLS_DAYS, *, now=None):
    """Zertifikat von init-tls mit DEMSELBEN Schluessel neu ausstellen.

    Das alte ``cert.pem`` bleibt als ``cert.pem.bak-<UTC-Zeit>`` erhalten,
    ``key.pem`` wird nicht veraendert. SAN: ``--host`` plus localhost und
    127.0.0.1, sonst die DNS-/IP-Eintraege des alten Zertifikats. Der
    SHA-256-Fingerabdruck aendert sich trotzdem: Browser muessen dem neuen
    Zertifikat erneut vertrauen. Fuer die Brueckenidentitaet nicht zustaendig.
    """
    import stat
    import tempfile
    from datetime import UTC, datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    directory = Path(directory)
    cert, key = directory / "cert.pem", directory / "key.pem"
    for path in (directory, cert, key):
        if path.is_symlink():
            raise ValueError(f"{path} ist ein Symlink; nicht erneuert")
    if not cert.is_file():
        raise ValueError(f"{cert} fehlt; zuerst init-tls")
    if not key.is_file():
        raise ValueError(f"{key} fehlt. Ohne eigenen Schluessel ist {cert} vermutlich der Export der "
                         "Brueckenidentitaet; deren Erneuerung bricht die Windows-Kopplung und ist hier nicht moeglich")
    old = x509.load_pem_x509_certificate(cert.read_bytes())
    private = serialization.load_pem_private_key(key.read_bytes(), password=None)
    if not isinstance(private, rsa.RSAPrivateKey):
        raise ValueError("Schluessel ist kein RSA-Schluessel; nicht erneuert")
    if private.public_key().public_numbers() != old.public_key().public_numbers():
        raise ValueError("cert.pem und key.pem passen nicht zusammen; nicht erneuert")
    if host is not None:
        san = f"{_host_san(host)},DNS:localhost,IP:127.0.0.1"
    else:
        entries = [entry for entry in _san_entries(old) if entry.startswith(("DNS:", "IP:"))]
        if not entries:
            raise ValueError("Altes Zertifikat ohne DNS-/IP-SAN; --host angeben")
        san = ",".join(entries)
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    backup = directory / f"cert.pem.bak-{stamp}"
    mode = stat.S_IMODE(cert.stat().st_mode)
    fd, temporary = tempfile.mkstemp(prefix=".cert-", suffix=".pem", dir=directory)
    os.close(fd)
    try:
        _openssl_certificate(["-new", "-key", str(key)], temporary, san, days)
        new = x509.load_pem_x509_certificate(Path(temporary).read_bytes())
        if new.public_key().public_numbers() != old.public_key().public_numbers():
            raise ValueError("Neues Zertifikat traegt einen anderen Schluessel; nicht uebernommen")
        os.chmod(temporary, mode)
        # Sicherung exklusiv anlegen: eine vorhandene gleichnamige Sicherung bleibt unangetastet.
        with open(cert, "rb") as source, open(backup, "xb") as target:
            target.write(source.read())
            target.flush()
            os.fsync(target.fileno())
        os.chmod(backup, mode)
        os.replace(temporary, cert)
    finally:
        Path(temporary).unlink(missing_ok=True)
    result = {"certificate": str(cert), "backup": str(backup), "key_unchanged": str(key),
              "san": _san_entries(new), "not_after_utc": new.not_valid_after_utc.isoformat(),
              "certificate_sha256": new.fingerprint(hashes.SHA256()).hex(),
              "previous_certificate_sha256": old.fingerprint(hashes.SHA256()).hex(), "time_basis": "UTC",
              "notes": ["Fingerabdruck geaendert: Browser/Windows muessen dem neuen Zertifikat erneut vertrauen.",
                        "Laufende Werkbank liest das Zertifikat erst nach einem Neustart."]}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def show_tls(directory):
    """SANs und Ablaufzeit lesen, auch ohne Zugriff auf den privaten Schluessel."""
    from cryptography import x509

    cert_path = Path(directory) / 'cert.pem'
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    print(json.dumps({'certificate': str(cert_path), 'san': _san_entries(cert),
                      'not_after_utc': cert.not_valid_after_utc.isoformat(), 'time_basis': 'UTC'}, indent=2))


def positive_days(value):
    days = int(value)
    if days <= 0:
        raise argparse.ArgumentTypeError('Tage muessen positiv sein')
    return days


@dataclass(frozen=True)
class BridgeRenewalResult:
    pi_id: str
    previous_certificate_sha256: str
    certificate_sha256: str
    not_after_utc: str
    backup: Path
    certificate_export: Path | None
    profile_url: str | None
    profile_export_command: tuple[str, ...]
    profile_filename: str = 'pi.dispread'
    restart_required: bool = True
    repair_required: bool = True


def renew_bridge_identity(instance: Instance, *, confirmed: bool, collect=None,
                          hardware_id=None, now=None) -> BridgeRenewalResult:
    """Renew for the service account; the caller must restart and re-pair afterwards."""
    from dispread.admin import probes
    from dispread.bridge.identity import DeviceIdentity, local_hardware_id

    from .config import load_config

    if confirmed is not True:
        raise ValueError('Erneuerung erfordert ausdrückliche Bestätigung (--yes). Windows-Brücken müssen neu gekoppelt werden.')
    if instance.problem or not instance.bridge_directory:
        raise ValueError(instance.problem or 'Keine Brückenidentität für diese Werkbank konfiguriert.')
    collect = collect or probes.collect

    def check_idle():
        if instance.unit is None and not instance.socket:
            raise ValueError('Erneuerung gesperrt: Laufstatus unbekannt (keine lokale Steuerung)')
        snapshot = collect(instance, include_setup=False)
        blocker = snapshot.stop_blocker
        if (instance.unit is None and snapshot.live is None and instance.socket
                and Path(instance.socket).exists()):
            blocker = 'Laufstatus unbekannt (Steuerung nicht erreichbar)'
        if blocker:
            raise ValueError(f'Erneuerung gesperrt: {blocker}')

    settings = load_config(Path(instance.config))[0] if instance.config else {}
    directory = Path(instance.bridge_directory)
    export = Path(settings['cert']) if settings.get('cert') else None
    if export is not None and (not export.is_file() or (settings.get('key') and Path(settings['key']).is_file())):
        export = None  # Only refresh the installer’s public export of the bridge identity.
    result = DeviceIdentity.renew(directory, (hardware_id or local_hardware_id)(), confirmed=confirmed,
                                  check_idle=check_idle, certificate_export=export, now=now)
    command = [sys.executable, '-m', 'dispread.workbench.cli', 'bridge', 'export-profile',
               '--directory', str(directory), '--output', 'pi.dispread', '--name',
               instance.bridge_name or 'Dispread Pi']
    endpoints = settings.get('bridge_endpoint', ())
    if not endpoints and instance.url:
        endpoints = (instance.url.removesuffix('/live') + '/bridge/v2',)
    for endpoint in endpoints:
        command.extend(['--endpoint', endpoint])
    return BridgeRenewalResult(**asdict(result), profile_url=instance.url + '/bridge/profile' if instance.url else None,
                               profile_export_command=tuple(command))


def bridge_command(args):
    """Local OS-authorized provisioning/export only; never start a measurement."""
    from dispread.bridge.identity import DeviceIdentity, local_hardware_id
    from dispread.bridge.pairing import PairingStore
    from dispread.bridge.protocol import parse_profile
    from dispread.bridge.types import BridgeProfile

    if args.action in ('prepare-uart', 'stop-uart', 'status'):
        print(json.dumps(asyncio.run(request('bridge.' + args.action, socket_path=args.socket)), indent=2))
        return
    if args.action == "identity" and args.renew:
        from dispread.admin.instance import discover

        if args.host is not None or args.export_certificate is not None:
            raise ValueError('--renew übernimmt die vorhandenen SANs und aktualisiert die konfigurierte Zertifikatkopie.')
        if not args.yes:
            raise ValueError('Erneuerung erfordert ausdrückliche Bestätigung (--yes). Windows-Brücken müssen neu gekoppelt werden.')
        instance = discover(args.config)
        if args.directory != str(BRIDGE_DIR) and (
            not instance.bridge_directory or Path(args.directory).resolve() != Path(instance.bridge_directory).resolve()
        ):
            raise ValueError('--directory muss zur verwalteten Werkbank passen (--config).')
        print(json.dumps(asdict(renew_bridge_identity(instance, confirmed=args.yes)),
                         default=os.fspath, indent=2, ensure_ascii=False))
        return
    directory = Path(args.directory or BRIDGE_DIR)
    if args.action == "revoke":
        PairingStore(directory / "pairing").revoke(args.client_id)
        print("Client-Zugang widerrufen")
        return
    host = getattr(args, "host", None) if args.action == "identity" else None
    if host is not None and not getattr(args, "provision", False):
        raise ValueError("--host erfordert --provision; bestehende Zertifikate werden nicht erneuert")
    load = DeviceIdentity.load_or_create if args.action == "identity" and args.provision else DeviceIdentity.load
    identity = load(directory, local_hardware_id(), **({"host": host} if host is not None else {}))
    if args.action == "identity":
        export_path = getattr(args, "export_certificate", None)
        if export_path is not None:
            fd = os.open(export_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(identity.certificate_pem.encode("ascii"))
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                Path(export_path).unlink(missing_ok=True)
                raise
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
    serve.add_argument("--config", help="Explizite TOML-Konfiguration; CLI-Angaben haben Vorrang")
    serve.add_argument("--pam-user", default=None, help="PAM-Konto; sonst DISPREAD_PAM_USER oder lokales Dienstkonto")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=SERVE_PORT)
    serve.add_argument("--bridge-directory", help="Bestehende Pi-Identitaet als HTTPS-/Bridge-Identitaet laden; keine Provisionierung")
    serve.add_argument("--bridge-endpoint", action="append", default=[], help="Expliziter LAN-/Tailscale-HTTPS/WSS-Endpunkt fuer das Profil")
    serve.add_argument("--bridge-name", default="Dispread Pi")
    serve.add_argument("--bridge-discovery", action="store_true", help="Oeffentliche DNS-SD-Hinweise mit optionalem python3-zeroconf anbieten")
    serve.add_argument("--camera", type=int, default=0)
    serve.add_argument("--data", default=str(WORKBENCH_DATA_DIR))
    serve.add_argument("--live-data", default=str(LIVE_DATA_DIR))
    serve.add_argument("--socket", default=default_socket())
    serve.add_argument("--cert", default=str(TLS_CERT))
    serve.add_argument("--key", default=str(TLS_KEY))
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
    live_sub.add_parser("status").add_argument('--socket', help='Sonst DISPREAD_SOCKET oder lokaler Standardsocket')
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
    tls.add_argument("--directory", default=str(TLS_DIR))
    tls.add_argument("--host", help="Adresse, unter der Windows den Pi erreicht; bei Erzeugung erforderlich")
    tls.add_argument("--show", action="store_true", help="SAN-Adressen und Ablaufdatum des vorhandenen Zertifikats anzeigen")
    renew = sub.add_parser("renew-tls", help="Zertifikat von init-tls mit demselben Schluessel neu ausstellen; "
                                             "altes cert.pem bleibt als Sicherung. Nicht fuer die Brueckenidentitaet")
    renew.add_argument("--directory", default=str(TLS_DIR))
    renew.add_argument("--host", help="Neue Adresse fuer den SAN; sonst DNS-/IP-SAN des alten Zertifikats")
    renew.add_argument("--days", type=positive_days, default=TLS_DAYS)
    bridge = sub.add_parser("bridge", help="Pi-Identitaet und lokale Kopplung ohne Messstart")
    bridge_sub = bridge.add_subparsers(dest="action", required=True)
    for action in ('prepare-uart', 'stop-uart', 'status'):
        local = bridge_sub.add_parser(action)
        local.add_argument('--socket', default=default_socket())
    identity = bridge_sub.add_parser("identity")
    identity.add_argument("--directory", default=str(BRIDGE_DIR))
    identity.add_argument("--config", help="Werkbank-Konfiguration für die Erneuerung und Laufsperre")
    action = identity.add_mutually_exclusive_group()
    action.add_argument("--provision", action="store_true", help="Neue Identitaet nur bei fehlender Einrichtung erzeugen")
    action.add_argument("--renew", action="store_true", help="Neu ausstellen und danach alle Windows-Brücken neu koppeln")
    identity.add_argument("--yes", action="store_true", help="Neukopplung bei --renew ausdrücklich bestätigen")
    identity.add_argument("--host", help="DNS-/IP-SAN bei expliziter Erstprovisionierung; keine Erneuerung")
    identity.add_argument("--export-certificate", help="Nur oeffentliches Zertifikat exklusiv exportieren; Elternverzeichnis muss existieren")
    export = bridge_sub.add_parser("export-profile")
    export.add_argument("--directory", default=str(BRIDGE_DIR))
    export.add_argument("--output", required=True)
    export.add_argument("--name", required=True)
    export.add_argument("--endpoint", action="append", default=[])
    export.add_argument("--pair", action="store_true", help="Einmalangebot fuer 300 Sekunden hinzufuegen")
    export.add_argument("--transport", choices=["network", "uart"], default="network")
    export.add_argument("--client-id")
    revoke = bridge_sub.add_parser("revoke")
    revoke.add_argument("--directory", default=str(BRIDGE_DIR))
    revoke.add_argument("client_id")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        from .config import apply_config

        apply_config(args, argv)
        if args.command == "bridge":
            bridge_command(args)
            return 0
        if args.command == "serve":
            from .server import serve

            asyncio.run(serve(args))
            return 0
        if args.command == "init-tls":
            if args.show:
                show_tls(args.directory)
            else:
                init_tls(args.directory, args.host)
            return 0
        if args.command == "renew-tls":
            renew_tls(args.directory, args.host, args.days)
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
        request_options = {'socket_path': args.socket} if getattr(args, 'socket', None) is not None else {}
        result = asyncio.run(request(op, values, **request_options))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if op == 'live.aufraeumen' and result.get('failed'):
            return 1
        return 0
    except (ValueError, OSError, ImportError, subprocess.CalledProcessError) as error:
        print(f"dispread: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
