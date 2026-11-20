"""Fresh installs only: no migration, service start or update of existing data."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from .archive import TEMPLATE, load_source
from .platform import MODULES, probe_system
from .platform import SystemInfo as SystemInfo


def parser():
    cli = argparse.ArgumentParser(description='picam: getrennte Neuinstallation; Vorgabe ist ein schreibfreier Plan.',
                                  epilog='Entfernen: --uninstall --help')
    cli.add_argument('--source', required=True, help='Releasearchiv oder HTTPS-Adresse')
    cli.add_argument('--sha256', help='Archiv-SHA256; Pflicht bei HTTPS')
    cli.add_argument('--mode', choices=('system', 'user', 'portable'), default='system')
    cli.add_argument('--user', required=True, help='Vorhandenes Bediener-/Dienstkonto (kein root)')
    cli.add_argument('--host', required=True, help='Von Windows erreichbare Adresse, ohne https://')
    cli.add_argument('--port', type=int, default=8080)
    cli.add_argument('--python', default=sys.executable, help='Produktinterpreter >=3.13 mit passenden Systemmodulen')
    for option in ('prefix', 'data', 'config', 'runtime', 'unit-dir'):
        cli.add_argument('--' + option, help='Absoluter Zielpfad; nur neue Ziele')
    cli.add_argument('--root', help='Getrennte Staging-Wurzel; niemals apt oder Dienstmanager aufrufen')
    cli.add_argument('--apply', action='store_true', help='Plan tatsaechlich ausfuehren; kein Dienststart')
    cli.add_argument('--install-packages', action='store_true', help='Explizit fehlende apt-Pakete installieren (nur system, root)')
    cli.add_argument('--without-bridge', action='store_true', help='Browser-Werkbank ohne Pi-Brueckenidentitaet, z.B. auf anderem Linux-PC')
    cli.add_argument('--json', action='store_true', help='Maschinenlesbarer Plan/Ergebnis auf stdout')
    return cli


def valid_host(host):
    if not host or '%' in host or any(char.isspace() or ord(char) < 32 for char in host):
        raise ValueError('Host ohne Leer- oder Steuerzeichen angeben')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if address.is_unspecified or address.is_multicast:
            raise ValueError('Erreichbare einzelne Hostadresse angeben, keine Wildcard-/Multicast-Adresse')
        return
    if (len(host) > 253 or all(part.isdigit() for part in host.rstrip('.').split('.'))
            or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', p)
                                             for p in host.rstrip('.').split('.'))):
        raise ValueError('Host ohne Schema, Pfad oder Steuerzeichen angeben')


def account(name):
    import pwd
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,63}\$?', name):
        raise ValueError('Ungueltiges Bedienerkonto')
    try:
        value = pwd.getpwnam(name)
    except KeyError as error:
        raise ValueError('Bedienerkonto existiert nicht; zuerst manuell anlegen') from error
    if value.pw_uid == 0:
        raise ValueError('Werkbank darf nicht als root laufen; Bedienerkonto angeben')
    return value


def absolute(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or '..' in path.parts or any(ord(c) < 32 for c in str(path)):
        raise ValueError('Zielpfade muessen absolut und ohne .. oder Steuerzeichen sein')
    return path


def no_symlinks(path):
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError(f'Symlink im Zielpfad: {parent}')


def target_paths(args, owner):
    home = Path(owner.pw_dir)
    if args.mode == 'system':
        prefix, data, config, runtime, unit_dir = (Path('/opt/picam'), Path('/var/lib/picam'),
            Path('/etc/picam/config.toml'), Path('/run/picam'), Path('/etc/systemd/system'))
    elif args.mode == 'user':
        prefix, data, config, runtime, unit_dir = (home / '.local/share/picam', home / '.local/state/picam',
            home / '.config/picam/config.toml', Path('/run/user') / str(owner.pw_uid) / 'picam',
            home / '.config/systemd/user')
    else:
        prefix = absolute(args.prefix) if args.prefix else home / 'picam'
        data, config, runtime, unit_dir = prefix / 'data', prefix / 'config/config.toml', prefix / 'run', None
    if args.mode != 'portable' and args.runtime and absolute(args.runtime) != runtime:
        raise ValueError('--runtime muss zum systemd-RuntimeDirectory picam passen; sonst --mode portable')
    values = {'prefix': prefix, 'data': data, 'config': config, 'runtime': runtime, 'unit_dir': unit_dir}
    for key in values:
        override = getattr(args, key, None)
        if override:
            values[key] = absolute(override)
    if args.root:
        root = absolute(args.root)
        no_symlinks(root)
        if root.exists():
            raise ValueError('Staging-Wurzel besteht bereits; ein neues Verzeichnis verwenden')
        values = {key: root / value.relative_to('/') if value else None for key, value in values.items()}
    unit_directory = values.pop('unit_dir')
    values['unit'] = unit_directory / 'picam-werkbank.service' if unit_directory else None
    return values


SOCKET_PATH_MAX = 100  # Unix-Sockets: sun_path 108 Bytes inkl. Nullbyte, mit Reserve


def socket_too_long(runtime):
    return len(str(Path(runtime) / 'control.sock').encode()) > SOCKET_PATH_MAX


def quote_unit(value):
    return json.dumps(str(value).replace('%', '%%').replace('$', '$$'), ensure_ascii=False)


def path_unit(value):
    """Pfad für Einstellungen wie ``WorkingDirectory=``: systemd entfernt dort keine
    Anführungszeichen (anders als in ``ExecStart=``), daher unquotiert; nur ``%`` maskieren."""
    text = str(value)
    if not text.startswith('/') or any(ord(char) < 32 for char in text):
        raise ValueError(f'Pfad für die systemd-Unit ungültig: {text!r}')
    return text.replace('%', '%%')


def unit_text(*, python, config, user, mode, runtime):
    lines = ['[Unit]', 'Description=picam Werkbank', 'After=network.target', '', '[Service]', 'Type=simple']
    if mode == 'system':
        lines.extend(['User=' + user, 'RuntimeDirectory=picam', 'RuntimeDirectoryMode=0700'])
    else:
        lines.extend(['RuntimeDirectory=picam', 'RuntimeDirectoryMode=0700'])
    lines.extend(['UMask=0077', 'WorkingDirectory=' + path_unit(python.parent.parent.parent),
                  'ExecStart=' + quote_unit(python) + ' -m dispread.workbench.cli serve --config ' + quote_unit(config),
                  'Restart=on-failure', 'RestartSec=3', 'TimeoutStopSec=30', '', '[Install]',
                  'WantedBy=' + ('multi-user.target' if mode == 'system' else 'default.target'), ''])
    return '\n'.join(lines)


def config_text(args, paths, release):
    data = paths['data']
    host = '[' + args.host + ']' if ':' in args.host else args.host
    settings = {'pam_user': args.user, 'host': args.host, 'port': args.port,
                'data': str(data / 'workbench'), 'live_data': str(data / 'live'),
                'socket': str(paths['runtime'] / 'control.sock'),
                'cert': str(data / 'workbench/tls/cert.pem'), 'key': str(data / 'workbench/tls/key.pem')}
    if not args.without_bridge:
        settings.update(bridge_directory=str(data / 'workbench/bridge'),
                        bridge_endpoint=[f'https://{host}:{args.port}/bridge/v2'])
    lines = ['# picam installer; absolute paths; no existing configuration imported.', '[workbench]']
    lines.extend(key + ' = ' + json.dumps(value, ensure_ascii=False) for key, value in settings.items())
    # Ueber current: nach einem Update liest der Dienst die Vorlage der aktiven Version.
    lines.extend(['', '[live]', 'templates = ' + json.dumps(str(release.parent.parent / 'current' / TEMPLATE)),
                  'calibration = ' + json.dumps(str(data / 'calibration/timing-streamcam.json')), ''])
    return '\n'.join(lines)


def checked(command, runner, *, owner=None, **options):
    # Provision as the operator. No privileged product code or root-owned secrets.
    if owner is not None and os.geteuid() == 0:
        command = ['runuser', '-u', owner.pw_name, '--', *map(str, command)]
    return runner(list(map(str, command)), check=True, capture_output=True, text=True, timeout=180, **options)


def missing_packages(bundle, runner):
    packages = []
    for line in bundle.files['packaging/apt-packages.txt'].decode().splitlines():
        name = line.partition('#')[0].strip()
        if not name:
            continue
        if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]+', name):
            raise ValueError('Ungueltiger Paketname im Manifest')
        result = runner(['dpkg-query', '-W', '-f=${Status}', name], capture_output=True, text=True, timeout=10)
        if result.returncode != 0 or result.stdout.strip() != 'install ok installed':
            packages.append(name)
    return packages


def runtime_check(info, args):
    if info.system != 'Linux':
        raise ValueError('Pi-Werkbank benoetigt Linux. Die Windows-Bruecke wird separat installiert.')
    if info.version < (3, 13):
        raise ValueError('Produkt braucht Python >= 3.13 samt ABI-passenden Systempaketen. '
                         'Neues OS-Image oder --python mit passender Laufzeit verwenden; keine automatische OS-Umstellung.')
    if args.mode != 'portable' and not info.systemd:
        raise ValueError('systemd fehlt oder laeuft nicht; --mode portable fuer manuellen Betrieb verwenden')
    if args.mode == 'user' and not info.user_bus:
        raise ValueError('systemd-Benutzerbus fehlt; passende Sitzung herstellen oder --mode portable verwenden')
    if args.install_packages and (args.root or args.mode != 'system' or not info.apt
                                 or Path(info.python).resolve() != Path('/usr/bin/python3').resolve()):
        raise ValueError('apt nur ohne --root im system-Modus mit System-Python; Systemmodule manuell bereitstellen')
    if info.missing_modules and not args.install_packages:
        raise ValueError('Fehlende/inkompatible Python-Systemmodule: ' + ', '.join(info.missing_modules)
                         + '. OS-Pakete passend zu --python bereitstellen; keine pip-Kopien nativer Module.')


def check_destinations(paths, args):
    # Only top-level fresh directories are transaction-owned. Nested paths are allowed.
    for mutable in (paths['data'], paths['config'].parent, paths['runtime']):
        if (paths['prefix'].is_relative_to(mutable)
                or mutable.is_relative_to(paths['prefix'] / 'releases')
                or mutable.is_relative_to(paths['prefix'] / 'current')):
            raise ValueError('Daten/Konfiguration/Runtime duerfen Code nicht enthalten oder im Release liegen')
    roots = [paths['prefix'], paths['data'], paths['config'].parent]
    if args.mode == 'portable':
        roots.append(paths['runtime'])
    roots = sorted(set(roots), key=lambda p: len(p.parts))
    top = []
    for path in roots:
        no_symlinks(path)
        if path == Path('/') or path.exists():
            raise ValueError(f'Ziel besteht bereits; keine automatische Uebernahme oder Aktualisierung: {path}')
        if not any(path.is_relative_to(parent) for parent in top):
            top.append(path)
    if paths['unit']:
        no_symlinks(paths['unit'])
        if paths['unit'].exists():
            raise ValueError('System-Unit vorhanden; keine automatische Uebernahme')
    if any(paths['unit'] and path.is_relative_to(paths['unit']) for path in top):
        raise ValueError('Unitpfad und Datenpfade widersprechen sich')
    return top


def assign_owner(directory, uid, gid):
    for path in (directory, *directory.rglob('*')):
        os.chown(path, uid, gid, follow_symlinks=False)


def hardware_id_available():
    try:
        serial = Path('/sys/firmware/devicetree/base/serial-number').read_bytes().rstrip(b'\0\n').decode('ascii')
        return bool(re.fullmatch(r'[0-9a-fA-F]{8,32}', serial))
    except (OSError, UnicodeError):
        return False


def prepare_release(bundle, release, info, runner, step=lambda _text: None):
    """Neues Releaseverzeichnis: Dateien, eigene venv, Paket, Selbsttest. Gibt die venv zurueck."""
    release.mkdir(parents=True, mode=0o755)
    step(f'Release {bundle.release_id} entpacken')
    for name, content in bundle.files.items():
        destination = release / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(content)
        destination.chmod(0o755 if name.endswith('.sh') else 0o644)
    (release / 'release.json').write_text(json.dumps(bundle.manifest, indent=2) + '\n')
    venv = release / '.venv'
    step('Python-Umgebung anlegen und Paket installieren')
    checked([info.python, '-m', 'venv', '--system-site-packages', venv], runner)
    checked([venv / 'bin/python', '-m', 'pip', '--disable-pip-version-check', 'install', '--no-index',
             '--no-deps', '--no-build-isolation', str(release)], runner)
    code = ('import importlib; ' + '; '.join('importlib.import_module(' + repr(m) + ')' for m in MODULES)
            + '; from dispread.workbench.cli import parser; parser(); '
            + 'from dispread.live.session import LiveConfig; '
            + 'import hashlib; from pathlib import Path; '
            + f'assert hashlib.sha256(Path({str(release / TEMPLATE)!r}).read_bytes()).hexdigest() == '
            + repr(hashlib.sha256(bundle.files[TEMPLATE]).hexdigest()))
    step('Selbsttest: Module und Lesevorlage')
    checked([venv / 'bin/python', '-I', '-c', code], runner)
    return venv


def install(args, runner=subprocess.run, progress=None):
    step = progress or (lambda _text: None)
    valid_host(args.host)
    if not 1 <= args.port <= 65535:
        raise ValueError('Port muss zwischen 1 und 65535 liegen')
    info = probe_system(args.python, runner=runner)
    runtime_check(info, args)
    if not args.without_bridge and not hardware_id_available():
        raise ValueError('Keine gueltige Pi-Hardwarekennung; --without-bridge fuer Browser-Werkbank ohne Bruecke verwenden')
    bundle = load_source(args.source, args.sha256)
    owner = account(args.user)
    if args.mode != 'system' and owner.pw_uid != os.geteuid():
        raise ValueError('Benutzer-/portable Installation ohne sudo unter dem Bedienerkonto ausfuehren')
    paths = target_paths(args, owner)
    roots = check_destinations(paths, args)
    release = paths['prefix'] / 'releases' / bundle.release_id
    result = {'applied': False, 'mode': args.mode, 'release_id': bundle.release_id, 'archive_sha256': bundle.sha256,
              'system': {'os': info.os_id, 'version': info.os_version, 'architecture': info.machine,
                         'python': info.python, 'python_version': list(info.version)},
              'paths': {key: str(value) if value else None for key, value in paths.items()},
              'url': f'https://{("[" + args.host + "]") if ":" in args.host else args.host}:{args.port}/live',
              'service_started': False, 'measurement_ready': False,
              'bridge_enabled': not args.without_bridge,
              'notes': ['Kalibrierung und Hardware separat pruefen.', 'Bestehende Installationen werden nicht migriert.',
                        'Kein automatischer Dienststart; Startbefehl erst auf dem Zielsystem ausfuehren.']}
    if not args.root and socket_too_long(paths['runtime']):
        result['notes'].append('Steuerungssocket-Pfad zu lang fuer Unix-Sockets; kuerzeren --prefix/--runtime waehlen.')
    if not args.apply:
        result['notes'].append('Nur Plan: Zielverzeichnisse, Pakete und Dienste unveraendert.')
        return result
    if args.mode == 'system' and not args.root and os.geteuid() != 0:
        raise ValueError('Systeminstallation braucht root; Plan ohne --apply pruefen, Anwendung spaeter mit sudo')
    # A real listening socket is never stopped or replaced. Do not bind to test it.
    try:
        with socket.create_connection((args.host, args.port), timeout=1):
            raise ValueError('Host/Port ist bereits belegt; bestehende Werkbank bleibt unveraendert')
    except (ConnectionRefusedError, socket.gaierror, TimeoutError, OSError):
        pass
    if args.install_packages:
        step('Fehlende Debian-Pakete installieren (apt)')
        if os.geteuid() != 0:
            raise ValueError('Explizite apt-Installation braucht root')
        needed = missing_packages(bundle, runner)
        if needed:
            checked(['apt-get', 'install', '-y', '--', *needed], runner)
        info = probe_system(args.python, runner=runner)
        if info.missing_modules:
            raise ValueError('Systemmodule nach apt weiterhin unbrauchbar: ' + ', '.join(info.missing_modules))
    created, unit_created = [], False
    try:
        # mkdir without exist_ok claims each root exclusively; parallel installs lose safely.
        step('Zielverzeichnisse anlegen')
        for path in roots:
            parents = []
            parent = path.parent
            while not parent.exists():
                parents.append(parent)
                parent = parent.parent
            for parent in reversed(parents):
                parent.mkdir(mode=0o755)
                created.append(parent)
            path.mkdir(mode=0o700)
            created.append(path)
        venv = prepare_release(bundle, release, info, runner, step)
        for directory in (paths['data'] / 'workbench', paths['data'] / 'live', paths['data'] / 'calibration',
                          paths['data'] / 'workbench/tls', paths['config'].parent):
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if args.mode == 'portable':
            paths['runtime'].mkdir(parents=True, exist_ok=True, mode=0o700)
        step('Konfiguration schreiben')
        with paths['config'].open('x') as stream:
            stream.write(config_text(args, paths, release))
        paths['config'].chmod(0o600)
        if args.mode == 'system' and not args.root:
            for base in (paths['data'], paths['config'].parent):
                assign_owner(base, owner.pw_uid, owner.pw_gid)
            # Code must be traversable by the operator; remains root-owned.
            paths['prefix'].chmod(0o755)
        if args.without_bridge:
            provision = [venv / 'bin/python', '-m', 'dispread.workbench.cli', 'init-tls', '--directory',
                         paths['data'] / 'workbench/tls', '--host', args.host]
        else:
            # Bridge and /live share one listener. Export the actual served
            # pinned certificate with the requested DNS/IP SAN for browser trust.
            provision = [venv / 'bin/python', '-m', 'dispread.workbench.cli', 'bridge', 'identity', '--provision',
                         '--directory', paths['data'] / 'workbench/bridge', '--host', args.host,
                         '--export-certificate', paths['data'] / 'workbench/tls/cert.pem']
        step('Brückenidentität und Zertifikat erzeugen' if not args.without_bridge else 'Zertifikat erzeugen')
        checked(provision, runner, owner=owner if args.mode == 'system' and not args.root else None)
        if paths['unit']:
            step('Dienst-Unit schreiben (nicht gestartet)')
            paths['unit'].parent.mkdir(parents=True, exist_ok=True)
            with paths['unit'].open('x') as stream:
                unit_created = True
                stream.write(unit_text(python=paths['prefix'] / 'current/.venv/bin/python', config=paths['config'],
                                       user=args.user, mode=args.mode, runtime=paths['runtime']))
            paths['unit'].chmod(0o644)
        # Activation is last; no product service is enabled or started here.
        step('Version aktivieren')
        (paths['prefix'] / 'current').symlink_to(release)
        result['applied'] = True
        result['start_command'] = ([str(venv / 'bin/python'), '-m', 'dispread.workbench.cli', 'serve',
                                    '--config', str(paths['config'])] if args.mode == 'portable' else
                                   ['systemctl', *(['--user'] if args.mode == 'user' else []), 'start', 'picam-werkbank.service'])
        return result
    except BaseException:
        if unit_created:
            paths['unit'].unlink(missing_ok=True)
        # Delete only directories exclusively created by this invocation, deepest first.
        for path in reversed(created):
            if path in roots:
                shutil.rmtree(path)
            else:
                try:
                    path.rmdir()
                except OSError:
                    pass
        raise


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if '--uninstall' in argv:
        from .uninstall import main as uninstall_main

        return uninstall_main(argv)
    if '--guided-apply' in argv:
        from .guided import guided_apply_main

        return guided_apply_main(argv)
    required = ('--user', '--host')
    if '--guided' in argv or (sys.stdin.isatty() and sys.stdout.isatty()
                              and not any(flag in argv for flag in required + ('--json', '-h', '--help'))):
        from .guided import run

        return run([arg for arg in argv if arg != '--guided'])
    args = parser().parse_args(argv)
    try:
        result = install(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('picam installer: ' + str(error), file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            detail = error.stderr.decode(errors='replace') if isinstance(error.stderr, bytes) else error.stderr
            print(detail[-2000:], file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(('Installiert, Dienst nicht gestartet: ' if result['applied'] else 'Installationsplan: ') + result['release_id'])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
