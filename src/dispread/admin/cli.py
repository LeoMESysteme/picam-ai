"""``picam``: Werkbank verwalten – Status, Diagnose, Dienst, Protokoll, Konfiguration.

Ohne Befehl öffnet sich in einem Terminal die Verwaltungskonsole, sonst gibt
es den Status als Text aus. Ergebnisse gehen nach stdout, Meldungen nach
stderr. Exit-Codes: 0 in Ordnung, 1 Fehler, 2 Warnung (nur ``doctor``),
3 gesperrt (z. B. Stoppen während eines Laufs), 64 Aufruffehler, 130 Abbruch.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

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


def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--config', default=argparse.SUPPRESS,
                        help='config.toml der Instanz (sonst automatisch erkannt)')
    common.add_argument('--no-color', action='store_true', default=argparse.SUPPRESS,
                        help='ohne Farben (auch NO_COLOR)')
    common.add_argument('--ascii', action='store_true', default=argparse.SUPPRESS, help='nur 7-Bit-Zeichen')
    root = argparse.ArgumentParser(prog='picam', parents=[common],
                                   description='Werkbank verwalten: Status, Diagnose, Dienst, Protokoll, '
                                   'Konfiguration. Ohne Befehl: Verwaltungskonsole.')
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
        command = args.command
        interactive = sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get('TERM') != 'dumb'
        if command == 'tui' or (command is None and interactive and not args.ascii):
            from .tui import run

            return run(instance)
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
    except KeyboardInterrupt:
        return EXIT_ABORT
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return EXIT_OK
    return EXIT_USAGE


if __name__ == '__main__':
    raise SystemExit(main())
