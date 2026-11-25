"""``picam``: Werkbank verwalten – Status, Diagnose, Dienst, Protokoll, Konfiguration.

Ohne Befehl öffnet sich in einem Terminal die Verwaltungskonsole, sonst gibt
es den Status als Text aus. Ergebnisse gehen nach stdout, Meldungen nach
stderr. Exit-Codes: 0 in Ordnung, 1 Fehler, 2 Warnung (nur ``doctor``),
3 gesperrt (z. B. Stoppen während eines Laufs oder fehlende Voraussetzung beim
Kalibrieren), 64 Aufruffehler, 130 Abbruch.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from . import probes
from .instance import discover

EXIT_OK, EXIT_FAIL, EXIT_WARN, EXIT_BLOCKED, EXIT_USAGE, EXIT_ABORT = 0, 1, 2, 3, 64, 130

SYMBOLS = {probes.OK: '✓', probes.WARN: '!', probes.FAIL: '✗', probes.OFF: '○', probes.UNKNOWN: '?'}
ASCII_SYMBOLS = {probes.OK: '+', probes.WARN: '!', probes.FAIL: 'x', probes.OFF: '-', probes.UNKNOWN: '?'}
COLORS = {probes.OK: '32', probes.WARN: '33', probes.FAIL: '31', probes.OFF: '2', probes.UNKNOWN: '35'}


class Style:
    def __init__(self, stream, color: bool | None = None, ascii_only: bool = False):
        if color is None:
            color = stream.isatty() and not os.environ.get('NO_COLOR') and os.environ.get('TERM') != 'dumb'
        self.color = color
        self.ascii = ascii_only

    def paint(self, text: str, code: str) -> str:
        return f'\033[{code}m{text}\033[0m' if self.color else text

    def symbol(self, level: str) -> str:
        return self.paint((ASCII_SYMBOLS if self.ascii else SYMBOLS)[level], COLORS[level])

    def dim(self, text: str) -> str:
        return self.paint(text, '2')

    def bold(self, text: str) -> str:
        return self.paint(text, '1')

    def text(self, value: str) -> str:
        if not self.ascii:
            return value
        table = str.maketrans({'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss',
                               '–': '-', '→': '->', '×': 'x', '…': '...', '·': '-'})
        return value.translate(table).encode('ascii', 'replace').decode()


def headline(snapshot: probes.Snapshot) -> str:
    instance = snapshot.instance
    service = snapshot.facts['dienst']
    parts = [f'Werkbank {service.value}']
    version = snapshot.facts.get('version')
    if version is not None:
        parts.append(version.value)
    if instance.url:
        parts.append(instance.url)
    return ' · '.join(parts)


def print_status(snapshot: probes.Snapshot, style: Style, keys=probes.OVERVIEW, out=None) -> None:
    out = out or sys.stdout
    out.write(style.text(style.bold(headline(snapshot))) + '\n')
    width = max(len(snapshot.facts[k].label) for k in keys if k in snapshot.facts)
    for key in keys:
        fact = snapshot.facts.get(key)
        if fact is None:
            continue
        out.write(style.text(f'  {style.symbol(fact.level)} {fact.label:<{width}}  {fact.value}') + '\n')


def print_doctor(snapshot: probes.Snapshot, style: Style, out=None) -> None:
    out = out or sys.stdout
    out.write(style.text(style.bold(headline(snapshot))) + '\n')
    width = max(len(f.label) for f in snapshot.facts.values())
    for title, keys in (('Betrieb', probes.OVERVIEW), ('Einrichtung', probes.SETUP)):
        out.write('\n' + style.text(style.dim(title)) + '\n')
        for key in keys:
            fact = snapshot.facts.get(key)
            if fact is None:
                continue
            out.write(style.text(f'  {style.symbol(fact.level)} {fact.label:<{width}}  {fact.value}') + '\n')
            if fact.level in (probes.FAIL, probes.WARN, probes.UNKNOWN):
                pad = ' ' * (width + 6)
                if fact.hint:
                    out.write(style.text(f'{pad}{fact.hint}') + '\n')
                if fact.command:
                    out.write(style.text(f'{pad}{style.dim("→")} {fact.command}') + '\n')
    problems = [f for f in snapshot.facts.values() if f.level in (probes.FAIL, probes.WARN)]
    out.write('\n')
    if not problems:
        out.write(style.text(f'{style.symbol(probes.OK)} Alles in Ordnung.') + '\n')
    else:
        fails = sum(f.level == probes.FAIL for f in problems)
        warns = len(problems) - fails
        summary = ', '.join(part for part in (f'{fails} Fehler' if fails else '',
                                              f'{warns} Warnung{"en" if warns != 1 else ""}' if warns else '')
                            if part)
        out.write(style.text(f'{style.symbol(probes.FAIL if fails else probes.WARN)} {summary}') + '\n')


def doctor_exit(snapshot: probes.Snapshot) -> int:
    levels = {f.level for f in snapshot.facts.values()}
    if probes.FAIL in levels:
        return EXIT_FAIL
    if probes.WARN in levels or probes.UNKNOWN in levels:
        return EXIT_WARN
    return EXIT_OK


def confirm(question: str) -> bool:
    if not sys.stdin.isatty():
        print(f'{question} – keine Rückfrage möglich (kein Terminal); mit --yes bestätigen.', file=sys.stderr)
        return False
    try:
        answer = input(f'{question} [j/N] ')
    except EOFError:
        return False
    return answer.strip().lower() in ('j', 'ja', 'y', 'yes')


def cmd_service(args, instance) -> int:
    from . import service

    snapshot = probes.collect(instance, include_setup=False) if args.command != 'start' else None
    try:
        plan = service.plan(args.command, instance, snapshot, force=args.force)
    except ValueError as error:
        print(f'picam: {error}', file=sys.stderr)
        return EXIT_FAIL
    if plan.blocker:
        print(f'picam: {args.command} gesperrt: {plan.blocker}. '
              f'Nur bewusst überstimmen: --force (kann einen Lauf abbrechen).', file=sys.stderr)
        return EXIT_BLOCKED
    if args.command == 'start' and probes.fact_service(instance).level == probes.OK:
        print('Dienst läuft bereits.', file=sys.stderr)
        return EXIT_OK
    for line in plan.shell():
        print(f'  {line}', file=sys.stderr)
    if not args.yes and not confirm({'start': 'Dienst starten?', 'stop': 'Dienst stoppen?',
                                     'restart': 'Dienst neu starten?'}[args.command]):
        print('Abgebrochen.', file=sys.stderr)
        return EXIT_ABORT
    ok, message = service.execute(plan, instance, echo=lambda _line: None)
    if not ok and message.startswith('Gesperrt'):
        print(f'picam: {message}', file=sys.stderr)
        return EXIT_BLOCKED
    print(message, file=sys.stderr if not ok else sys.stdout)
    return EXIT_OK if ok else EXIT_FAIL


def cmd_logs(args, instance) -> int:
    from . import service

    try:
        command = service.journal_command(instance, args.lines, args.follow, as_json=False)
    except ValueError as error:
        print(f'picam: {error}', file=sys.stderr)
        return EXIT_FAIL
    try:
        return subprocess.call(command)
    except KeyboardInterrupt:
        return EXIT_ABORT


def cmd_config(args, instance) -> int:
    from . import configedit

    if instance.config is None:
        print('picam: Diese Instanz hat keine config.toml (Entwicklungsbetrieb); '
              'Werte stehen im Startbefehl.', file=sys.stderr)
        if args.action in (None, 'get'):
            for key in ('host', 'port', 'socket', 'data', 'live_data', 'bridge_directory'):
                print(f'{key} = {getattr(instance, key)!r}')
            return EXIT_OK
        return EXIT_FAIL
    if args.action in (None, 'get'):
        if args.key:
            value = getattr(instance, args.key, None)
            if value is None and args.key not in configedit.EDITABLE:
                print(f'picam: unbekannter Schlüssel {args.key}', file=sys.stderr)
                return EXIT_USAGE
            print(json.dumps(value, ensure_ascii=False))
            return EXIT_OK
        print(open(instance.config).read(), end='')
        return EXIT_OK
    if not args.key or args.value is None:
        print('picam: config set SCHLÜSSEL WERT', file=sys.stderr)
        return EXIT_USAGE
    try:
        new_text, changes = configedit.propose(instance.config, args.key, args.value)
    except (ValueError, OSError) as error:
        print(f'picam: {error}', file=sys.stderr)
        return EXIT_FAIL
    if not changes:
        print('Keine Änderung.')
        return EXIT_OK
    for change in changes:
        print(f'  {change.text}', file=sys.stderr)
    print('  Wirksam nach: picam restart', file=sys.stderr)
    if not args.yes and not confirm('Übernehmen?'):
        print('Abgebrochen.', file=sys.stderr)
        return EXIT_ABORT
    try:
        configedit.apply(instance.config, new_text)
    except PermissionError as error:
        print(f'picam: {error}: sudo picam config set {args.key} {args.value}', file=sys.stderr)
        return EXIT_FAIL
    print(f'{instance.config} geändert. Mit „picam restart“ wirksam machen.')
    return EXIT_OK


def cmd_update(args, instance) -> int:
    from . import update

    try:
        if not (args.source or args.check or args.rollback or args.activate):
            from .calibrate import Console

            def authorize():
                print('Für die Systeminstallation fragt sudo nach dem Passwort.', file=sys.stderr)
                return subprocess.call(['sudo', '-v']) == 0

            class UpdateConsole(Console):
                def confirm(self, title, lines, expected, *, deps):
                    return confirm(title)

                def mark(self, level, text, stream=None):
                    self.line(text, stream or (sys.stdout if level == probes.OK else sys.stderr))

            console = UpdateConsole(Style(sys.stderr, color=False if args.no_color else None, ascii_only=args.ascii),
                                    out=sys.stderr)
            deps = update.Deps(authorize=authorize)
            return update.run_update(instance, None, args.sha256, console, deps, yes=args.yes).exit_code
        update.prefix_of(instance)
        if args.check:
            state = update.versions(instance)
            print(f"aktiv:      {state['current']}")
            print(f"vorige:     {state['previous'] or '–'}")
            print(f"installiert: {', '.join(state['installed'])}")
            return EXIT_OK
        target = None
        if args.rollback:
            target = update.versions(instance)['previous']
            if not target:
                print('picam: keine vorige Version vorhanden', file=sys.stderr)
                return EXIT_FAIL
        elif args.activate:
            target = args.activate
        question = (f'Auf Version {target} umschalten und den Dienst neu starten?' if target else
                    f'Version aus {args.source} installieren, umschalten und den Dienst neu starten?')
        if not args.yes and not confirm(question):
            print('Abgebrochen.', file=sys.stderr)
            return EXIT_ABORT
        if update.needs_root(instance):
            argv = (['--config', instance.config] if instance.config else []) + ['update'] + (['--source', os.path.abspath(args.source) if '://' not in args.source
                                  else args.source] if args.source else []) + (
                ['--sha256', args.sha256] if args.sha256 else []) + (
                ['--rollback'] if args.rollback else []) + (['--activate', args.activate] if args.activate else []) + [
                '--yes']
            print('Für die Systeminstallation fragt sudo nach dem Passwort.', file=sys.stderr)
            return subprocess.call(update.sudo_command(argv))
        echo = lambda text: print(text, file=sys.stderr)  # noqa: E731
        if target:
            ok, message = update.switch(instance, target, echo=echo)
        else:
            ok, message = update.install_update(instance, args.source, args.sha256, echo=echo)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'picam: {error}', file=sys.stderr)
        return EXIT_FAIL
    print(message, file=sys.stdout if ok else sys.stderr)
    if not ok and ('gesperrt' in message):
        return EXIT_BLOCKED
    return EXIT_OK if ok else EXIT_FAIL


def cmd_calibrate(args, instance, style) -> int:
    """``picam kalibrieren``: messen, prüfen, importieren oder zurückstellen."""
    from . import calibrate

    console = calibrate.Console(style)
    options = calibrate.Options(duration_s=args.dauer, hold_s=args.halten,
                                port=args.port if args.port is not None else instance.reference_port,
                                baudrate=args.baudrate,
                                profile=Path(args.profil) if args.profil else None, seed=args.seed, yes=args.yes)
    if args.pruefen is not None:
        return calibrate.check_file(instance, Path(args.pruefen) if args.pruefen else None, console)
    if args.import_datei:
        return calibrate.import_file(instance, Path(args.import_datei), console, yes=args.yes)
    if args.rueckstellen:
        return calibrate.restore_from_file(Path(args.rueckstellen), options, console)
    return calibrate.calibrate(instance, options, console)


def run_hint_command(command: str, instance) -> int:
    """Empfohlenen Befehl ausführen; picam-Befehle ohne Shell im selben Interpreter."""
    import shlex

    if command.startswith('picam '):
        argv = [sys.executable, '-m', 'dispread.admin.cli']
        if instance.config:
            argv += ['--config', instance.config]
        return subprocess.call(argv + shlex.split(command)[1:])
    return subprocess.call(command, shell=True, cwd=instance.root or None)


def setup_calibration(instance, style, ask=input, run=None, interactive: bool | None = None) -> int:
    """Einrichtungsschritt Kalibrierung: neu messen, Datei prüfen/importieren oder später."""
    from . import calibrate

    run = run or (lambda argv: run_hint_command(shlex.join(['picam', *argv]), instance))
    adapter = calibrate.adapter_present(instance.reference_port)
    if adapter:
        print(style.text(f'      [k] neu kalibrieren (Adapter an {instance.reference_port} gefunden, '
                         'Werkbank kurz aus)'))
    else:
        print(style.text('      Neu kalibrieren braucht einen USB-RS232-Adapter am RS232-Ausgang des '
                         f'Messverstärkers ({instance.reference_port} fehlt): Adapter stecken, dann '
                         '„picam kalibrieren“.'))
    print(style.text('      [p] vorhandene Datei prüfen oder importieren'))
    print(style.text('      [s] später'))
    if not (sys.stdin.isatty() if interactive is None else interactive):
        return EXIT_WARN
    try:
        choice = ask('      Auswahl: ').strip().lower()
    except EOFError:
        return EXIT_WARN
    if choice == 'k' and adapter:
        code = run(['kalibrieren'])
    elif choice == 'p':
        default = instance.calibration or ''
        try:
            path = ask(f'      Datei [{default}]: ').strip() or default
        except EOFError:
            return EXIT_WARN
        if not path:
            return EXIT_WARN
        same = bool(instance.calibration) and os.path.realpath(path) == os.path.realpath(instance.calibration)
        code = run(['kalibrieren', '--pruefen', path] if same else ['kalibrieren', '--import', path])
    else:
        print(style.text(style.dim('      Später: picam kalibrieren')))
        return EXIT_WARN
    print(style.text(f'      {style.symbol(probes.OK if code == 0 else probes.FAIL)} Exit {code}'))
    return code


def cmd_setup(args, instance, style) -> int:
    snapshot = probes.collect(instance)
    print(style.text(style.bold(headline(snapshot))))
    problems = [f for f in snapshot.facts.values() if f.level in (probes.FAIL, probes.WARN)]
    problems.sort(key=lambda f: probes.LEVEL_ORDER[f.level])
    if not problems:
        print(style.text(f'{style.symbol(probes.OK)} Nichts offen.'))
        return EXIT_OK
    done = 0
    for index, fact in enumerate(problems, 1):
        print()
        print(style.text(f'{index}/{len(problems)}  {style.symbol(fact.level)} {fact.label}: {fact.value}'))
        if fact.hint:
            print(style.text(f'      {fact.hint}'))
        if fact.key == 'kalibrierung':
            done += setup_calibration(instance, style) == 0
            continue
        if not fact.command:
            print(style.text(style.dim('      Von Hand erledigen.')))
            continue
        print(style.text(f'      {style.dim("Befehl:")} {fact.command}'))
        if not sys.stdin.isatty():
            continue
        if confirm('      Ausführen?'):
            code = run_hint_command(fact.command, instance)
            print(style.text(f'      {style.symbol(probes.OK if code == 0 else probes.FAIL)} Exit {code}'))
            done += code == 0
    print()
    print(style.text(f'{done} erledigt, {len(problems) - done} offen. Nochmal prüfen: picam doctor'))
    return EXIT_OK if done == len(problems) else EXIT_WARN


def cmd_cleanup(args, instance) -> int:
    request = {'days': args.tage, 'diagnostics_only': args.nur_diagnose, 'execute': False}
    listing = probes.socket_request(instance.socket, 'live.aufraeumen', args=request, timeout=60)
    if listing is None:
        print('picam: Werkbank nicht erreichbar; Aufräumen läuft über den Dienst (picam start).', file=sys.stderr)
        return EXIT_FAIL
    entries = listing.get('entries') or []
    if not entries:
        print(f'Nichts älter als {args.tage} Tage.')
        return EXIT_OK
    for entry in entries:
        print(f"  {entry.get('mb', 0):>8.1f} MB  {entry.get('path')}")
    total = listing.get('total_mb', 0)
    print(f'{len(entries)} {"Lauf" if len(entries) == 1 else "Läufe"}, zusammen {total:.0f} MB.')
    if not args.yes and not confirm('Diese Läufe endgültig löschen? (vorher sichern)'):
        print('Nichts gelöscht.', file=sys.stderr)
        return EXIT_ABORT
    result = probes.socket_request(instance.socket, 'live.aufraeumen', args=dict(request, execute=True),
                                   timeout=300)
    if result is None or result.get('failed'):
        print('picam: Löschen unvollständig; Werkbank-Protokoll prüfen (picam logs).', file=sys.stderr)
        return EXIT_FAIL
    print(f'{total:.0f} MB freigegeben.')
    return EXIT_OK


def choose_color_system(environ=os.environ) -> str | None:
    """Echtfarben für die Konsole, wenn das Terminal es nur nicht ansagt.

    SSH aus Windows (cmd, PowerShell, Windows Terminal) und viele tmux-Sitzungen
    setzen ``COLORTERM`` nicht; Textual rechnet dann alle Farben auf 256 herunter
    und die Flächenstufen fallen zusammen. Heutige Terminals können 24 Bit, und
    tmux rechnet selbst um, falls sein Client es nicht kann. ``PICAM_COLORS=256``
    (oder ``TEXTUAL_COLOR_SYSTEM``) überstimmt; reine Textkonsolen bleiben unberührt.
    """
    if 'TEXTUAL_COLOR_SYSTEM' in environ or environ.get('NO_COLOR'):
        return None
    wanted = environ.get('PICAM_COLORS', '').strip().lower()
    if wanted in ('256', 'standard', 'truecolor'):
        environ['TEXTUAL_COLOR_SYSTEM'] = {'256': '256'}.get(wanted, wanted)
        return environ['TEXTUAL_COLOR_SYSTEM']
    if environ.get('COLORTERM', '').strip().lower() in ('truecolor', '24bit'):
        return None
    if environ.get('TERM', '') in ('', 'dumb', 'linux', 'vt100', 'vt220'):
        return None
    environ['TEXTUAL_COLOR_SYSTEM'] = 'truecolor'
    return 'truecolor'


def parser() -> argparse.ArgumentParser:
    from . import calibrate

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--config', default=argparse.SUPPRESS,
                        help='config.toml der Instanz (sonst automatisch erkannt)')
    common.add_argument('--no-color', action='store_true', default=argparse.SUPPRESS,
                        help='ohne Farben (auch NO_COLOR)')
    common.add_argument('--ascii', action='store_true', default=argparse.SUPPRESS, help='nur 7-Bit-Zeichen')
    common.add_argument('--no-intro', action='store_true', default=argparse.SUPPRESS,
                        help='Konsole ohne Startbild (auch PICAM_INTRO=0)')
    common.add_argument('--onboarding', action='store_true', default=argparse.SUPPRESS,
                        help='Einrichtungsassistent der Konsole jetzt öffnen')
    root = argparse.ArgumentParser(prog='picam', parents=[common],
                                   description='Werkbank verwalten: Status, Diagnose, Dienst, Protokoll, '
                                   'Konfiguration. Ohne Befehl: Verwaltungskonsole.')
    root.add_argument('--version', action='store_true', help='picam-Version anzeigen')
    sub = root.add_subparsers(dest='command')
    real_add = sub.add_parser
    sub.add_parser = lambda *a, **k: real_add(*a, parents=[common], **k)
    status = sub.add_parser('status', help='Kurzstatus')
    status.add_argument('--json', action='store_true')
    doctor = sub.add_parser('doctor', help='alle Prüfungen mit Abhilfe (Exit 0/1/2)')
    doctor.add_argument('--json', action='store_true')
    logs = sub.add_parser('logs', help='Protokoll des Dienstes')
    logs.add_argument('-n', '--lines', type=int, default=100)
    logs.add_argument('-f', '--follow', action='store_true')
    for name, text in (('start', 'Dienst starten'), ('stop', 'Dienst stoppen'), ('restart', 'Dienst neu starten')):
        action = sub.add_parser(name, help=text)
        action.add_argument('--yes', '-y', action='store_true', help='ohne Rückfrage')
        action.add_argument('--force', action='store_true', help='Laufsperre überstimmen (kann Lauf abbrechen)')
    config = sub.add_parser('config', help='Konfiguration lesen oder ändern')
    config.add_argument('action', nargs='?', choices=('get', 'set'))
    config.add_argument('key', nargs='?')
    config.add_argument('value', nargs='?')
    config.add_argument('--yes', '-y', action='store_true')
    upd = sub.add_parser('update', help='neueste stabile Version installieren und neu starten (mit Rückweg)')
    group = upd.add_mutually_exclusive_group()
    group.add_argument('--source', help='Releasearchiv oder HTTPS-Adresse')
    group.add_argument('--rollback', action='store_true', help='zurück auf die vorige Version')
    group.add_argument('--activate', metavar='VERSION', help='vorbereitete Version aktivieren')
    group.add_argument('--check', action='store_true', help='installierte Versionen zeigen')
    upd.add_argument('--sha256', help='SHA-256 des Archivs (Pflicht bei HTTPS)')
    upd.add_argument('--yes', '-y', action='store_true')
    clean = sub.add_parser('aufraeumen', help='alte Läufe auflisten und nach Rückfrage löschen')
    clean.add_argument('--tage', type=int, default=14, help='älter als N Tage (Standard 14)')
    clean.add_argument('--nur-diagnose', action='store_true', help='nur Diagnoseaufnahmen')
    clean.add_argument('--yes', '-y', action='store_true')
    sub.add_parser('setup', help='offene Einrichtungspunkte nacheinander durchgehen')
    cal = sub.add_parser('kalibrieren', help='Timing-Kalibrierung messen (USB-RS232-Adapter nötig), prüfen '
                         'oder importieren')
    mode = cal.add_mutually_exclusive_group()
    mode.add_argument('--pruefen', nargs='?', const='', default=None, metavar='DATEI',
                      help='Kalibrierdatei prüfen und Werte zeigen (ohne DATEI: die aktive)')
    mode.add_argument('--import', dest='import_datei', metavar='DATEI',
                      help='woanders gemessene Datei prüfen und nach Bestätigung übernehmen')
    mode.add_argument('--rueckstellen', metavar='RUECKSTELLPUNKT',
                      help='Normierung/Dezimalpunkt des GSV aus einem Rückstellpunkt zurückschreiben')
    cal.add_argument('--dauer', type=float, default=calibrate.DEFAULT_DURATION_S,
                     help=f'Aufnahmedauer in Sekunden (Standard {calibrate.DEFAULT_DURATION_S:g})')
    cal.add_argument('--halten', type=float, default=calibrate.DEFAULT_HOLD_S,
                     help=f'Haltezeit je Normierungsstufe (Standard {calibrate.DEFAULT_HOLD_S:g} s)')
    cal.add_argument('--port', default=None,
                     help='USB-RS232-Adapter (Standard: der konfigurierte Referenzport der Instanz, '
                          f'sonst {calibrate.REFERENCE_PORT})')
    cal.add_argument('--baudrate', type=int, default=calibrate.REFERENCE_BAUDRATE)
    cal.add_argument('--profil', help='bestätigtes Werkbank-Profil (Standard: neueste Einrichtung)')
    cal.add_argument('--seed', type=int, help='Startwert des Faktorplans (Standard: Uhrzeit)')
    cal.add_argument('--yes', '-y', action='store_true', help='ohne Rückfrage (Import: ohne Eingabe)')
    sub.add_parser('url', help='Adresse der Werkbank')
    sub.add_parser('tui', help='Verwaltungskonsole öffnen')
    return root


def main(argv=None) -> int:
    try:
        args = parser().parse_args(argv)
    except SystemExit as error:
        return EXIT_USAGE if error.code not in (0, None) else EXIT_OK
    for name, default in (('config', None), ('no_color', False), ('ascii', False)):
        if not hasattr(args, name):
            setattr(args, name, default)
    if args.no_color:
        os.environ['NO_COLOR'] = '1'
    try:
        instance = discover(args.config)
        if args.version:
            print(f'picam {probes.fact_version(instance).value}')
            return EXIT_OK
        command = args.command
        interactive = sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get('TERM') != 'dumb'
        if command == 'tui' or (command is None and interactive and not args.ascii):
            choose_color_system()
            from .tui import run

            return run(instance, intro=not getattr(args, 'no_intro', False),
                       onboarding='force' if getattr(args, 'onboarding', False) else 'auto')
        style = Style(sys.stdout, color=False if args.no_color else None, ascii_only=args.ascii)
        if command in (None, 'status'):
            snapshot = probes.collect(instance, include_setup=False)
            if getattr(args, 'json', False):
                print(json.dumps(snapshot.to_json(), ensure_ascii=False, indent=2))
            else:
                print_status(snapshot, style)
            return EXIT_OK
        if command == 'doctor':
            snapshot = probes.collect(instance)
            if args.json:
                print(json.dumps(snapshot.to_json(), ensure_ascii=False, indent=2))
            else:
                print_doctor(snapshot, style)
            return doctor_exit(snapshot)
        if command == 'url':
            if not instance.url:
                print('picam: Adresse unbekannt', file=sys.stderr)
                return EXIT_FAIL
            print(instance.url)
            return EXIT_OK
        if command == 'logs':
            return cmd_logs(args, instance)
        if command in ('start', 'stop', 'restart'):
            return cmd_service(args, instance)
        if command == 'config':
            return cmd_config(args, instance)
        if command == 'update':
            return cmd_update(args, instance)
        if command == 'aufraeumen':
            return cmd_cleanup(args, instance)
        if command == 'setup':
            return cmd_setup(args, instance, style)
        if command == 'kalibrieren':
            return cmd_calibrate(args, instance, style)
    except KeyboardInterrupt:
        return EXIT_ABORT
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return EXIT_OK
    return EXIT_USAGE


if __name__ == '__main__':
    raise SystemExit(main())
