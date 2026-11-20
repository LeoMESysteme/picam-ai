"""Geführte Installation: ``./install.sh`` ohne Angaben in einem Terminal.

Prüft das System, fragt nur, was sich nicht ableiten lässt (Art, Konto,
Adresse, Port, optionale Komponenten), zeigt den Plan und installiert erst
nach Bestätigung. Danach optional: ``picam``-Befehl verlinken und Dienst
starten – beides nur nach eigener Rückfrage. Standardbibliothek, Python >= 3.9,
keine Produktimporte.

Im Terminal sind alle Auswahlen Menüs (``tui.Menus``: Pfeiltasten, Enter,
Leertaste, Ziffern, Esc), dazu ein kurzes ME-Logo und Spinner. Ohne Terminal,
mit ``TERM=dumb`` oder mit übergebenem ``input_`` (Tests) gilt die nummerierte
Texteingabe; optionale Komponenten werden dort nicht gefragt, sondern mit ihrer
Vorgabe in den Plan übernommen (abwählbar mit ``--without-fastfetch``).
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from . import engine, fastfetch
from .platform import probe_system
from .tui import Menus, Out, play_intro

__all__ = ['Out', 'run', 'apply', 'guided_apply_main']

READY_TIMEOUT_S = 60


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


class Typed:
    """Bisherige Texteingabe (ohne Terminal, TERM=dumb, Tests). Gleiche Schnittstelle wie ``tui.Menus``.

    Prüffehler bei Freitext beenden den Ablauf (``ValueError``) statt erneut zu
    fragen – wie vorher; nur im Terminal wird direkt neu gefragt.
    """

    menus = False

    def __init__(self, out, input_):
        self.out, self.input_ = out, input_

    def choose(self, label, options, default=1):
        return choose(label, options, default, input_=self.input_, out=self.out)

    def confirm(self, question, default=False):
        return yes(question, default, input_=self.input_)

    def text(self, label, default=None, validate=None):
        value = ask(label, default, input_=self.input_)
        error = validate(value) if validate is not None else None
        if error:
            raise ValueError(error)
        return value

    def multi(self, label, items):
        return {key for key, _, _, on in items if on}


def make_ui(out, input_):
    """Menüs nur im echten Terminal und ohne übergebenes ``input_``."""
    if input_ is None and out.caps.interactive:
        return Menus(out)
    return Typed(out, input_ or input)


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


def operator_accounts():
    """Anmeldefähige Konten mit eigenem Home (UID ≥ 1000, ohne nologin/false)."""
    try:
        import pwd

        entries = pwd.getpwall()
    except (ImportError, OSError):
        return []
    found = []
    for entry in entries:
        if (1000 <= entry.pw_uid < 65534 and not entry.pw_shell.endswith(('nologin', 'false'))
                and os.path.isdir(entry.pw_dir)):
            found.append(entry.pw_name)
    return sorted(set(found))


# ---------------------------------------------------------------- Prüfungen für Eingaben
def check_account(name):
    try:
        engine.account(name)
    except ValueError as error:
        return str(error)
    return None


def check_host(host):
    try:
        engine.valid_host(host)
    except ValueError as error:
        return str(error)
    return None


def check_port(host):
    def check(raw):
        if not raw.isdigit():
            return 'Port muss eine Zahl sein'
        if not 1 <= int(raw) <= 65535:
            return 'Port muss zwischen 1 und 65535 liegen'
        if not port_free(host, int(raw)):
            return f'Port {raw} ist auf {host} schon belegt'
        return None
    return check


def check_prefix(raw):
    path = Path(raw).expanduser()
    if not path.is_absolute():
        return 'Absoluten Ordner angeben, z. B. ~/picam'
    if engine.socket_too_long(path / 'run'):
        return ('Installationsordner zu tief verschachtelt: der Steuerungssocket wäre länger als Unix '
                'erlaubt. Kürzeren Ordner wählen, z. B. ~/picam.')
    if path.exists() or path.is_symlink():
        return f'{path} besteht bereits; einen neuen Ordner wählen'
    return None


def check_source(raw):
    if raw.startswith('https://'):
        return None
    if not Path(raw).expanduser().is_file():
        return f'{raw} nicht gefunden'
    return None


def check_sha(raw):
    return None if re.fullmatch(r'[0-9a-fA-F]{64}', raw) else 'SHA-256 hat 64 Hexadezimalzeichen'


# ---------------------------------------------------------------- Plan
def fastfetch_rows(component):
    """Planzeilen der Komponente me-fastfetch (Pfad, Text)."""
    home = component['home']

    def short(path):
        return '~' + path[len(home):] if path.startswith(home + '/') else path

    states = {'neu': '', 'gleich': ' (unverändert vorhanden)', 'erneuern': ' (ältere Fassung ersetzen)',
              'sichern': ' (vorhandene wird vorher gesichert)'}
    rows = []
    for entry in component['files']:
        rows.append((short(entry['path']), 'me-fastfetch' + states.get(entry['state'], '')))
    bashrc = {'fehlt': 'markierter Block für SSH-Logins (Sicherung vorher)',
              'veraltet': 'markierten Block erneuern (Sicherung vorher)',
              'aktuell': 'markierter Block schon aktuell',
              'fremd': 'ruft fastfetch schon selbst auf, bleibt unverändert'}[component['bashrc']['state']]
    rows.append((short(component['bashrc']['path']), bashrc))
    if component['package'] == 'installieren':
        rows.append(('apt: fastfetch', 'Debian-Paket nur für me-fastfetch'))
    return rows


def plan_lines(result, mode, link, extra=()):
    paths = result['paths']
    rows = [(paths['prefix'] + '/releases/' + result['release_id'], 'Code und eigene Python-Umgebung'),
            (paths['data'], 'Daten: Identität, Zertifikat, Läufe, Kalibrierung'),
            (paths['config'], 'Konfiguration')]
    if paths.get('unit'):
        rows.append((paths['unit'], 'Dienst – erst nach eigener Rückfrage gestartet'))
    if link:
        rows.append((str(link), 'Befehl picam (Verwaltung)'))
    rows += list(extra)
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


def expected_steps(args, package_missing=False):
    """Geschätzte Schrittzahl für den Gesamtbalken (wächst mit, falls mehr kommen)."""
    count = 7  # Ordner, Entpacken, venv, Selbsttest, Konfiguration, Zertifikat, Aktivieren
    count += bool(getattr(args, 'install_packages', False))
    count += args.mode != 'portable'
    if getattr(args, 'fastfetch', None):
        count += 1 + bool(package_missing and args.mode == 'system')
    return count


def run(argv=None, input_=None, out=None, runner=subprocess.run, installer=engine.install,
        installer_root=None, execvp=os.execvp, ui=None):
    """Geführter Ablauf. Rückgabe: Exit-Code. ``ui`` nur für Tests (z. B. ``Menus`` mit Tastenfolge)."""
    out = out or Out()
    ui = ui or make_ui(out, input_)
    given = argparse.Namespace(**{k: None for k in ('source', 'sha256', 'mode', 'user', 'host', 'port',
                                                    'prefix', 'fastfetch')})
    if argv:
        early = argparse.ArgumentParser(add_help=False)
        for name in ('source', 'sha256', 'mode', 'user', 'host', 'prefix'):
            early.add_argument('--' + name)
        early.add_argument('--port', type=int)
        early.add_argument('--with-fastfetch', dest='fastfetch', action='store_true', default=None)
        early.add_argument('--without-fastfetch', dest='fastfetch', action='store_false')
        given, _ = early.parse_known_args(argv, given)
    root = installer_root or Path(__file__).resolve().parents[2]
    try:
        if ui.menus:
            play_intro(out)
        out.rule('picam installieren')
        out.line(out.dim('  Prüft zuerst, fragt dann wenige Angaben ab und installiert erst nach Bestätigung.'))

        # 1. System
        python = sys.executable if not os.path.exists('/usr/bin/python3') else '/usr/bin/python3'
        with out.task('System prüfen', quiet=True):
            info = probe_system(python, runner=runner)
        version = '.'.join(map(str, info.version))
        system_ok = info.system == 'Linux' and info.version >= (3, 13)
        out.rule('System')
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
        out.rule('Release')
        source = given.source or find_source(root, Path.cwd())
        if source is None:
            out.status('ask', 'Archiv', 'kein picam-*.tar.gz gefunden')
            source = ui.text('Pfad oder HTTPS-Adresse des Releasearchivs', validate=check_source)
        source = str(Path(source).expanduser()) if not str(source).startswith('https://') else str(source)
        sha = given.sha256
        if source.startswith('https://') and not sha:
            sha = ui.text('SHA-256 des Archivs (getrennt erhalten)', validate=check_sha)
        from .archive import load_source

        with out.task('Archiv prüfen', quiet=True):
            bundle = load_source(source, sha)
        out.status('ok', 'Archiv', f'{Path(source).name} · Release {bundle.release_id}')
        with out.task('Debian-Pakete prüfen', quiet=True):
            missing = engine.missing_packages(bundle, runner) if info.apt else []
            fastfetch_present = fastfetch.package_installed(runner) if info.apt else True
        if missing:
            out.status('warn', 'Pakete', f'{len(missing)} fehlen: ' + ', '.join(missing))
        else:
            out.status('ok', 'Pakete', 'alle Debian-Pakete vorhanden' if info.apt else 'kein apt – manuell prüfen')
        if info.missing_modules and not missing:
            out.status('fail', 'Python-Module', ', '.join(info.missing_modules))
            return 1

        # 3. Fragen
        out.rule('Angaben')
        modes = [('system', 'Systemdienst – startet beim Booten, Code in /opt/picam (empfohlen)'),
                 ('user', 'Benutzerdienst – alles im Home-Verzeichnis, ohne sudo'),
                 ('portable', 'Portabel – ohne Dienst, manuell starten')]
        if not info.systemd:
            modes = modes[2:]
        mode = given.mode or ui.choose('Installationsart', modes)
        user = given.user or ask_account(ui)
        owner = engine.account(user)
        host = given.host
        if not host:
            candidates = addresses(runner)
            options = [(address, f'{address} – {name}' if ui.menus else f'{address:<18} {name}')
                       for address, name in candidates]
            options.append((None, 'andere Adresse eingeben'))
            if not ui.menus:
                out.line('  Adresse, unter der Windows den Pi erreicht (steht im Zertifikat):')
            host = ui.choose('Adresse (Windows → Pi, steht im Zertifikat)' if ui.menus else 'Adresse', options)
            if host is None:
                host = ui.text('Adresse', validate=check_host)
        engine.valid_host(host)
        port = given.port
        if not port:
            suggestion = next((p for p in range(8080, 8090) if port_free(host, p)), 8080)
            port = int(ui.text('Port', str(suggestion), validate=check_port(host)))
        bridge = hardware
        prefix = given.prefix
        if mode == 'portable' and not prefix:
            prefix = ui.text('Installationsordner', str(Path(owner.pw_dir) / 'picam'), validate=check_prefix)
        with_fastfetch = given.fastfetch
        if with_fastfetch is None:
            chosen = ui.multi('Optionale Komponenten', [
                ('fastfetch', 'me-fastfetch', 'ME-Logo und Systemübersicht beim SSH-Login', True)])
            with_fastfetch = 'fastfetch' in chosen
        component = None
        if with_fastfetch:
            try:
                component = fastfetch.plan(owner.pw_dir, fastfetch.sources(bundle.files),
                                           package_present=fastfetch_present,
                                           can_install_package=mode == 'system' and info.apt)
            except (OSError, ValueError) as error:
                out.status('warn', 'me-fastfetch', f'{error} – wird nicht eingerichtet')
                with_fastfetch = False

        args = engine.parser().parse_args(['--source', source, '--mode', mode, '--user', user, '--host', host,
                                           '--port', str(port)] + (['--sha256', sha] if sha else [])
                                          + ([] if bridge else ['--without-bridge'])
                                          + (['--prefix', str(Path(prefix).expanduser())] if prefix else [])
                                          + (['--install-packages'] if missing and mode == 'system' else [])
                                          + (['--with-fastfetch'] if with_fastfetch else ['--without-fastfetch']))
        missing = missing if mode == 'system' else []
        if missing and mode != 'system':
            if info.missing_modules:
                out.line(f'    Fehlende Pakete zuerst installieren: sudo apt-get install {" ".join(missing)}')
                return 1
            out.line('    ' + out.dim(f'Optional fehlt: {", ".join(missing)} (später: sudo apt-get install '
                                     f'{" ".join(missing)})'))

        # 4. Plan
        with out.task('Plan erstellen', quiet=True):
            plan = installer(args, runner=runner)
        component = plan.get('fastfetch') or component
        if plan.get('paths', {}).get('runtime') and engine.socket_too_long(plan['paths']['runtime']):
            raise ValueError('Installationsordner zu tief verschachtelt: der Steuerungssocket '
                             f'{plan["paths"]["runtime"]}/control.sock wäre länger als Unix erlaubt. '
                             'Kürzeren Ordner wählen, z. B. ~/picam.')
        link = link_target(mode, owner)
        if link is not None and (link.exists() or link.is_symlink()):
            link = None
        out.rule('Plan')
        for line in plan_lines(plan, mode, link, fastfetch_rows(component) if component else ()):
            out.line('  ' + line)
        if missing:
            out.line('  ' + out.dim('vorher: apt-get install ' + ' '.join(missing)))
        for note in (component or {}).get('notes', []):
            if not note.startswith(component['bashrc']['path']):  # steht schon in der Planzeile
                out.line('  ' + out.dim(note))
        if component and not ui.menus and given.fastfetch is None:
            out.line('  ' + out.dim('me-fastfetch ist optional: abwählen mit --without-fastfetch'))
        out.line('  ' + out.dim(f'Werkbank danach unter {plan["url"]}'))
        out.line()
        if not ui.confirm('Installieren?'):
            out.line('  Abgebrochen, nichts geändert.')
            return 130
        needs_root = mode == 'system' and os.geteuid() != 0
        if needs_root:
            flags = ['--guided-apply', '--source', str(Path(source).resolve()) if not source.startswith('https://')
                     else source, '--mode', mode, '--user', user, '--host', host, '--port', str(port)]
            flags += (['--sha256', sha] if sha else []) + ([] if bridge else ['--without-bridge'])
            flags += ['--install-packages'] if missing else []
            flags += ['--with-fastfetch'] if with_fastfetch else ['--without-fastfetch']
            package_root = str(Path(__file__).resolve().parents[1])  # packaging/ oder picam-install.pyz
            bootstrap = ('import sys; sys.path.insert(0, sys.argv.pop(1)); '
                         'from picam_installer.engine import main; raise SystemExit(main())')
            out.line('  ' + out.dim('Für die Systeminstallation fragt sudo nach dem Passwort.'))
            execvp('sudo', ['sudo', sys.executable, '-c', bootstrap, package_root] + flags)
            return 1  # nur erreicht, wenn execvp ersetzt wurde (Tests)
        return apply(args, out=out, input_=input_, runner=runner, installer=installer, ui=ui,
                     package_missing=not fastfetch_present)
    except KeyboardInterrupt:
        out.line()
        out.line('  Abgebrochen.')
        return 130
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        out.status('fail', 'Fehler', str(error))
        return 1


def ask_account(ui):
    """Menü, wenn mehrere Konten in Frage kommen; sonst Eingabe mit Vorgabe."""
    default = default_user()
    candidates = operator_accounts() if ui.menus else []
    if len(candidates) > 1:
        if default in candidates:
            candidates.remove(default)
            candidates.insert(0, default)
        options = [(name, f'{name} – aufrufendes Konto' if name == default else name) for name in candidates]
        options.append((None, 'anderes Konto eingeben'))
        chosen = ui.choose('Dienstkonto (Anmeldung an der Werkbank)', options)
        if chosen is not None:
            error = check_account(chosen)
            if error:
                raise ValueError(error)
            return chosen
        default = None
    return ui.text('Dienstkonto (Anmeldung an der Werkbank)', default, validate=check_account)


def apply(args, out=None, input_=None, runner=subprocess.run, installer=engine.install, ui=None,
          package_missing=None):
    """Installation ausführen, danach Befehl verlinken und optional Dienst starten."""
    out = out or Out()
    ui = ui or make_ui(out, input_)
    args.apply = True
    out.rule('Installation')
    if package_missing is None and getattr(args, 'fastfetch', None):
        package_missing = not fastfetch.package_installed(runner)
    with out.progress(expected_steps(args, package_missing)) as progress:
        result = installer(args, runner=runner, progress=progress.step)
    out.status('ok', 'Installiert', f'Release {result["release_id"]}')
    owner = engine.account(args.user)
    paths = result['paths']
    component = result.get('fastfetch')
    if component and component.get('applied'):
        out.status('ok', 'me-fastfetch', f'eingerichtet für {args.user}, zeigt sich beim nächsten SSH-Login')
        for backup in component.get('backups', []):
            out.line('    ' + out.dim(f'Sicherung: {backup}'))
    elif component and component.get('error'):
        out.status('warn', 'me-fastfetch', f'nicht eingerichtet: {component["error"]}')
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
        if ui.confirm('Dienst jetzt starten und beim Booten automatisch starten?', default=True):
            command = ['systemctl', *user_flag, 'enable', '--now', 'picam-werkbank.service']
            if not out.live:
                out.step(shlex.join(command))
            with out.task('Dienst starten: ' + shlex.join(command), quiet=True):
                try:
                    runner(['systemctl', *user_flag, 'daemon-reload'], check=False, timeout=30)
                    done = runner(command, check=False, capture_output=True, text=True, timeout=90)
                except (OSError, subprocess.SubprocessError) as error:
                    done = SimpleNamespace(returncode=1, stderr=str(error))
            if done.returncode != 0:
                out.status('fail', 'Dienst', (done.stderr or '').strip() or f'Exit {done.returncode}')
            else:
                with out.task(f'Warte auf HTTPS-Antwort von {args.host}:{args.port}', quiet=True):
                    ready = wait_ready(args.host, args.port)
                if ready:
                    out.status('ok', 'Dienst', f'läuft, {result["url"]} antwortet')
                    started = True
                else:
                    out.status('warn', 'Dienst', 'gestartet, antwortet aber noch nicht – picam logs')
    out.rule('Nächste Schritte')
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
    if component and component.get('applied') and component.get('package') == 'fehlt':
        steps.append('Für me-fastfetch das Paket nachinstallieren: sudo apt-get install fastfetch')
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
