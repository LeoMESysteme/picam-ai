"""Geführte Installation: ``./install.sh`` ohne Angaben in einem Terminal.

Prüft das System, fragt nur, was sich nicht ableiten lässt (Art, Konto,
Adresse, Port), zeigt den Plan und installiert erst nach ``j``. Danach
optional: ``picam``-Befehl verlinken und Dienst starten – beides nur nach
eigener Rückfrage. Standardbibliothek, Python >= 3.9, keine Produktimporte.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from . import engine
from .platform import probe_system

READY_TIMEOUT_S = 60


class Out:
    """Zeilen mit Statuszeichen; Farbe nur im Terminal und ohne NO_COLOR."""

    def __init__(self, stream=None, color=None):
        self.stream = stream or sys.stdout
        if color is None:
            color = (getattr(self.stream, 'isatty', lambda: False)() and not os.environ.get('NO_COLOR')
                     and os.environ.get('TERM') != 'dumb')
        self.color = color
        utf8 = 'UTF-8' in (os.environ.get('LANG', '') + os.environ.get('LC_ALL', '')).upper()
        self.sym = ({'ok': '✓', 'warn': '!', 'fail': '✗', 'step': '·', 'ask': '?'} if utf8 else
                    {'ok': '+', 'warn': '!', 'fail': 'x', 'step': '-', 'ask': '?'})

    def paint(self, text, code):
        return f'\033[{code}m{text}\033[0m' if self.color else text

    def line(self, text=''):
        self.stream.write(text + '\n')
        self.stream.flush()

    def title(self, text):
        self.line()
        self.line(self.paint(text, '1'))

    def status(self, kind, label, text):
        code = {'ok': '32', 'warn': '33', 'fail': '31', 'step': '36', 'ask': '36'}[kind]
        self.line(f'  {self.paint(self.sym[kind], code)} {label:<16} {text}')

    def step(self, text):
        self.line(f'  {self.paint(self.sym["step"], "36")} {text}')

    def dim(self, text):
        return self.paint(text, '2')


def ask(prompt, default=None, input_=input, out=None):
    suffix = f' [{default}]' if default not in (None, '') else ''
    try:
        answer = input_(f'  {prompt}{suffix}: ').strip()
    except EOFError:
        raise KeyboardInterrupt from None
    return answer or (default or '')


def yes(prompt, default=False, input_=input):
    hint = 'J/n' if default else 'j/N'
    try:
        answer = input_(f'  {prompt} [{hint}] ').strip().lower()
    except EOFError:
        raise KeyboardInterrupt from None
    if not answer:
        return default
    return answer in ('j', 'ja', 'y', 'yes')


def choose(prompt, options, default=1, input_=input, out=None):
    """``options``: Liste (wert, text). Rückgabe: Wert oder None für „anderes“."""
    for index, (_, text) in enumerate(options, 1):
        out.line(f'    {index}) {text}')
    while True:
        raw = ask(prompt, str(default), input_=input_)
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        out.line(f'    Bitte 1–{len(options)} eingeben.')


def addresses(runner=subprocess.run):
    """IPv4-Adressen je Schnittstelle (ohne lo), dazu <hostname>.local."""
    found = []
    try:
        result = runner(['ip', '-j', '-4', 'addr', 'show'], capture_output=True, text=True, timeout=5)
        for link in json.loads(result.stdout or '[]'):
            name = link.get('ifname', '')
            if name == 'lo':
                continue
            for info in link.get('addr_info', []):
                if info.get('family') == 'inet' and info.get('local'):
                    found.append((info['local'], name))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    host = socket.gethostname()
    if host and host != 'localhost':
        found.append((f'{host}.local', 'mDNS-Name'))
    return found


def port_free(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return False
    except OSError:
        return True


def find_source(installer_root: Path, cwd: Path):
    """Neuestes picam-*.tar.gz neben dem Installer oder im Arbeitsverzeichnis."""
    candidates = []
    for base in {installer_root, installer_root.parent, cwd}:
        try:
            candidates += [p for p in base.glob('picam*.tar.gz') if p.is_file()]
        except OSError:
            continue
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def default_user():
    if os.environ.get('SUDO_USER') and os.environ['SUDO_USER'] != 'root':
        return os.environ['SUDO_USER']
    name = getpass.getuser()
    return '' if name == 'root' else name


def plan_lines(result, mode, link):
    paths = result['paths']
    rows = [(paths['prefix'] + '/releases/' + result['release_id'], 'Code und eigene Python-Umgebung'),
            (paths['data'], 'Daten: Identität, Zertifikat, Läufe, Kalibrierung'),
            (paths['config'], 'Konfiguration')]
    if paths.get('unit'):
        rows.append((paths['unit'], 'Dienst – erst nach eigener Rückfrage gestartet'))
    if link:
        rows.append((str(link), 'Befehl picam (Verwaltung)'))
    width = max(len(path) for path, _ in rows)
    return [f'{path:<{width}}  {text}' for path, text in rows]


def link_target(mode, owner):
    if mode == 'system':
        return Path('/usr/local/bin/picam')
    if mode == 'user':
        return Path(owner.pw_dir) / '.local/bin/picam'
    return None


def wait_ready(host, port, timeout=READY_TIMEOUT_S, sleep=time.sleep):
    import ssl

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2) as raw:
                with context.wrap_socket(raw, server_hostname=host):
                    return True
        except OSError:
            sleep(1)
    return False


def run(argv=None, input_=input, out=None, runner=subprocess.run, installer=engine.install,
        installer_root=None, execvp=os.execvp):
    """Geführter Ablauf. Rückgabe: Exit-Code."""
    out = out or Out()
    given = argparse.Namespace(**{k: None for k in ('source', 'sha256', 'mode', 'user', 'host', 'port',
                                                    'prefix')})
    if argv:
        early = argparse.ArgumentParser(add_help=False)
        for name in ('source', 'sha256', 'mode', 'user', 'host', 'prefix'):
            early.add_argument('--' + name)
        early.add_argument('--port', type=int)
        given, _ = early.parse_known_args(argv, given)
    root = installer_root or Path(__file__).resolve().parents[2]
    try:
        out.title('picam installieren')
        out.line(out.dim('  Prüft zuerst, fragt dann wenige Angaben ab und installiert erst nach Bestätigung.'))

        # 1. System
        info = probe_system(sys.executable if not os.path.exists('/usr/bin/python3') else '/usr/bin/python3',
                            runner=runner)
        version = '.'.join(map(str, info.version))
        system_ok = info.system == 'Linux' and info.version >= (3, 13)
        out.title('System')
        out.status('ok' if system_ok else 'fail', 'Betriebssystem',
                   f'{info.os_id} {info.os_version} · {info.machine} · Python {version}')
        if not system_ok:
            out.line('    Die Werkbank braucht Linux mit Python 3.13 (Raspberry Pi OS 13 „Trixie“).')
            return 1
        out.status('ok' if info.systemd else 'warn', 'Dienstverwaltung',
                   'systemd' if info.systemd else 'kein systemd – nur portable Installation')
        hardware = engine.hardware_id_available()
        out.status('ok' if hardware else 'warn', 'Pi-Kennung',
                   'vorhanden (Windows-Brücke möglich)' if hardware else 'fehlt – Werkbank ohne Brücke')

        # 2. Release
        out.title('Release')
        source = given.source or find_source(root, Path.cwd())
        if source is None:
            out.status('ask', 'Archiv', 'kein picam-*.tar.gz gefunden')
            source = ask('Pfad oder HTTPS-Adresse des Releasearchivs', input_=input_)
        source = str(source)
        sha = given.sha256
        if source.startswith('https://') and not sha:
            sha = ask('SHA-256 des Archivs (getrennt erhalten)', input_=input_)
        from .archive import load_source

        bundle = load_source(source, sha)
        out.status('ok', 'Archiv', f'{Path(source).name} · Release {bundle.release_id}')
        missing = engine.missing_packages(bundle, runner) if info.apt else []
        if missing:
            out.status('warn', 'Pakete', f'{len(missing)} fehlen: ' + ', '.join(missing))
        else:
            out.status('ok', 'Pakete', 'alle Debian-Pakete vorhanden' if info.apt else 'kein apt – manuell prüfen')
        if info.missing_modules and not missing:
            out.status('fail', 'Python-Module', ', '.join(info.missing_modules))
            return 1

        # 3. Fragen
        out.title('Angaben')
        modes = [('system', 'Systemdienst – startet beim Booten, Code in /opt/picam (empfohlen)'),
                 ('user', 'Benutzerdienst – alles im Home-Verzeichnis, ohne sudo'),
                 ('portable', 'Portabel – ohne Dienst, manuell starten')]
        if not info.systemd:
            modes = modes[2:]
        mode = given.mode or choose('Installationsart', modes, input_=input_, out=out)
        user = given.user or ask('Dienstkonto (Anmeldung an der Werkbank)', default_user(), input_=input_)
        owner = engine.account(user)
        host = given.host
        if not host:
            candidates = addresses(runner)
            options = [(address, f'{address:<18} {name}') for address, name in candidates]
            options.append((None, 'andere Adresse eingeben'))
            out.line('  Adresse, unter der Windows den Pi erreicht (steht im Zertifikat):')
            host = choose('Adresse', options, input_=input_, out=out)
            if host is None:
                host = ask('Adresse', input_=input_)
        engine.valid_host(host)
        port = given.port
        if not port:
            suggestion = next((p for p in range(8080, 8090) if port_free(host, p)), 8080)
            raw = ask('Port', str(suggestion), input_=input_)
            if not raw.isdigit():
                raise ValueError('Port muss eine Zahl sein')
            port = int(raw)
        bridge = hardware
        prefix = given.prefix
        if mode == 'portable' and not prefix:
            prefix = ask('Installationsordner', str(Path(owner.pw_dir) / 'picam'), input_=input_)

        args = engine.parser().parse_args(['--source', source, '--mode', mode, '--user', user, '--host', host,
                                           '--port', str(port)] + (['--sha256', sha] if sha else [])
                                          + ([] if bridge else ['--without-bridge'])
                                          + (['--prefix', str(Path(prefix).expanduser())] if prefix else [])
                                          + (['--install-packages'] if missing and mode == 'system' else []))
        missing = missing if mode == 'system' else []
        if missing and mode != 'system':
            if info.missing_modules:
                out.line(f'    Fehlende Pakete zuerst installieren: sudo apt-get install {" ".join(missing)}')
                return 1
            out.line('    ' + out.dim(f'Optional fehlt: {", ".join(missing)} (später: sudo apt-get install '
                                     f'{" ".join(missing)})'))

        # 4. Plan
        plan = installer(args, runner=runner)
        if plan.get('paths', {}).get('runtime') and engine.socket_too_long(plan['paths']['runtime']):
            raise ValueError('Installationsordner zu tief verschachtelt: der Steuerungssocket '
                             f'{plan["paths"]["runtime"]}/control.sock wäre länger als Unix erlaubt. '
                             'Kürzeren Ordner wählen, z. B. ~/picam.')
        link = link_target(mode, owner)
        if link is not None and (link.exists() or link.is_symlink()):
            link = None
        out.title('Plan')
        for line in plan_lines(plan, mode, link):
            out.line('  ' + line)
        if missing:
            out.line('  ' + out.dim('vorher: apt-get install ' + ' '.join(missing)))
        out.line('  ' + out.dim(f'Werkbank danach unter {plan["url"]}'))
        out.line()
        if not yes('Installieren?', input_=input_):
            out.line('  Abgebrochen, nichts geändert.')
            return 130
        needs_root = mode == 'system' and os.geteuid() != 0
        if needs_root:
            flags = ['--guided-apply', '--source', str(Path(source).resolve()) if not source.startswith('https://')
                     else source, '--mode', mode, '--user', user, '--host', host, '--port', str(port)]
            flags += (['--sha256', sha] if sha else []) + ([] if bridge else ['--without-bridge'])
            flags += ['--install-packages'] if missing else []
            package_root = str(Path(__file__).resolve().parents[1])  # packaging/ oder picam-install.pyz
            bootstrap = ('import sys; sys.path.insert(0, sys.argv.pop(1)); '
                         'from picam_installer.engine import main; raise SystemExit(main())')
            out.line('  ' + out.dim('Für die Systeminstallation fragt sudo nach dem Passwort.'))
            execvp('sudo', ['sudo', sys.executable, '-c', bootstrap, package_root] + flags)
            return 1  # nur erreicht, wenn execvp ersetzt wurde (Tests)
        return apply(args, out=out, input_=input_, runner=runner, installer=installer)
    except KeyboardInterrupt:
        out.line()
        out.line('  Abgebrochen.')
        return 130
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        out.status('fail', 'Fehler', str(error))
        return 1


def apply(args, out=None, input_=input, runner=subprocess.run, installer=engine.install):
    """Installation ausführen, danach Befehl verlinken und optional Dienst starten."""
    out = out or Out()
    args.apply = True
    out.title('Installation')
    result = installer(args, runner=runner, progress=out.step)
    out.status('ok', 'Installiert', f'Release {result["release_id"]}')
    owner = engine.account(args.user)
    paths = result['paths']
    venv_picam = Path(paths['prefix']) / 'current/.venv/bin/picam'
    link = link_target(args.mode, owner)
    if link is not None and not link.exists() and not link.is_symlink() and venv_picam.exists():
        try:
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(venv_picam)
            out.status('ok', 'Befehl', f'picam → {link}')
        except OSError as error:
            out.status('warn', 'Befehl', f'picam nicht verlinkt: {error}')
    started = False
    if args.mode != 'portable':
        user_flag = ['--user'] if args.mode == 'user' else []
        out.line()
        if yes('Dienst jetzt starten und beim Booten automatisch starten?', default=True, input_=input_):
            command = ['systemctl', *user_flag, 'enable', '--now', 'picam-werkbank.service']
            out.step(shlex.join(command))
            try:
                runner(['systemctl', *user_flag, 'daemon-reload'], check=False, timeout=30)
                done = runner(command, check=False, capture_output=True, text=True, timeout=90)
            except (OSError, subprocess.SubprocessError) as error:
                done = SimpleNamespace(returncode=1, stderr=str(error))
            if done.returncode != 0:
                out.status('fail', 'Dienst', (done.stderr or '').strip() or f'Exit {done.returncode}')
            elif wait_ready(args.host, args.port):
                out.status('ok', 'Dienst', f'läuft, {result["url"]} antwortet')
                started = True
            else:
                out.status('warn', 'Dienst', 'gestartet, antwortet aber noch nicht – picam logs')
    out.title('Nächste Schritte')
    steps = []
    if not started and args.mode != 'portable':
        steps.append('Dienst starten: picam start')
    if args.mode == 'portable':
        steps.append('Starten: ' + shlex.join(result.get('start_command', [])))
    steps += [f'Im Browser öffnen: {result["url"]}',
              f'Anmelden mit Benutzer „{args.user}“ und dem Linux-Passwort dieses Kontos '
              f'(dasselbe wie für SSH; ändern mit: sudo passwd {args.user})',
              'Auf Windows dem Zertifikat vertrauen: ' + paths['data'] + '/workbench/tls/cert.pem',
              'Offene Einrichtung durchgehen (Kamera, UART, Kalibrierung): ' + (
                  'picam setup' if args.mode != 'portable' else
                  f'{paths["prefix"]}/current/.venv/bin/picam --config {paths["config"]}')]
    for index, step in enumerate(steps, 1):
        out.line(f'  {index}. {step}')
    return 0


def guided_apply_main(argv):
    """Zweiter Teil nach ``sudo``: Angaben stehen fest, Plan wurde schon bestätigt."""
    parser = engine.parser()
    parser.add_argument('--guided-apply', action='store_true')
    args = parser.parse_args(argv)
    out = Out()
    try:
        return apply(args, out=out)
    except KeyboardInterrupt:
        out.line('  Abgebrochen.')
        return 130
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        out.status('fail', 'Fehler', str(error))
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            detail = error.stderr if isinstance(error.stderr, str) else error.stderr.decode(errors='replace')
            out.line(detail[-2000:])
        return 1

