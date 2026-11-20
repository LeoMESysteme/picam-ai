"""Dienstaktionen und Protokoll für picam.

Starten, Stoppen und Neustarten betreffen nur den Werkbankdienst, nie einen
Messlauf direkt. Stoppen ist gesperrt, solange ein Lauf, eine Einrichtung
oder eine Diagnosekopie aktiv ist oder der Laufstatus unbekannt ist (gleiche
Regel wie ``scripts/werkbank-dienst.sh``); ``force`` überstimmt das bewusst.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .instance import DEV_UNIT, Instance
from .probes import Snapshot, peer_certificate, systemctl

READY_TIMEOUT_S = 60
COMMAND_TIMEOUT_S = 120  # Stopp darf TimeoutStopSec (30 s) plus Start überdauern


@dataclass
class Plan:
    action: str
    commands: list[list[str]]
    blocker: str | None = None
    note: str | None = None
    force: bool = False

    def shell(self) -> list[str]:
        import shlex

        return [shlex.join(command) for command in self.commands]


def _privileged(instance: Instance, command: list[str]) -> list[str]:
    if instance.scope == 'system' and os.geteuid() != 0:
        return ['sudo'] + command
    return command


def _dev_start(instance: Instance) -> list[list[str]]:
    if not instance.argv:
        raise ValueError('Startbefehl unbekannt: Dienst einmal mit scripts/werkbank-dienst.sh starten.')
    workdir = instance.workdir or instance.root or str(Path.cwd())
    return [['systemd-run', '--user', f'--unit={DEV_UNIT}', f'--working-directory={workdir}',
             f'--setenv=PYTHONPATH={workdir}/src', '--property=TimeoutStopSec=20s', '--', *instance.argv]]


def plan(action: str, instance: Instance, snapshot: Snapshot | None = None, force: bool = False) -> Plan:
    if instance.unit is None:
        raise ValueError(instance.problem or 'Kein verwalteter Dienst (portable Installation).')
    base = systemctl(instance)
    stop = [_privileged(instance, base + ['stop', instance.unit])]
    if instance.kind == 'dev':
        start = _dev_start(instance) if action in ('start', 'restart') else []
    else:
        start = [_privileged(instance, base + ['start', instance.unit])]
    blocker = None
    if action in ('stop', 'restart') and not force:
        # Ohne geprüften Laufstatus kein Stopp (fail closed).
        blocker = snapshot.stop_blocker if snapshot is not None else 'Laufstatus noch nicht geprüft'
    commands = {'start': start, 'stop': stop, 'restart': stop + start}[action]
    note = None
    if action in ('start', 'restart'):
        note = f'Wartet bis zu {READY_TIMEOUT_S} s, bis {instance.url} antwortet.'
    return Plan(action, commands, blocker, note, force)


def current_blocker(instance: Instance) -> str | None:
    from .probes import collect

    return collect(instance, include_setup=False).stop_blocker


def execute(plan_: Plan, instance: Instance, interactive: bool = True, wait_ready: bool = True,
            run=None, echo=print, recheck=None) -> tuple[bool, str]:
    """Plan ausführen. ``interactive``: Terminal geerbt (sudo kann fragen).

    Vor Stopp/Neustart wird die Laufsperre unmittelbar vor dem ersten Befehl
    erneut geprüft: zwischen Anzeige und Bestätigung kann ein Lauf begonnen haben.
    """
    if plan_.blocker:
        return False, f'Gesperrt: {plan_.blocker}'
    if plan_.action in ('stop', 'restart') and not plan_.force:
        blocker = (recheck or (lambda: current_blocker(instance)))()
        if blocker:
            return False, f'Gesperrt: {blocker}'
    for command in plan_.commands:
        echo('$ ' + ' '.join(command))
        try:
            if run is not None:
                code = run(command)
            elif interactive:
                code = subprocess.call(command)
            else:
                code = subprocess.run(command, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_S).returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, f'Befehl nicht abgeschlossen ({error}): {" ".join(command)}'
        if code != 0:
            if instance.kind == 'dev' and 'stop' in command:
                subprocess.call(systemctl(instance) + ['reset-failed', instance.unit],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return False, f'Befehl fehlgeschlagen (Exit {code}): {" ".join(command)}'
        if instance.kind == 'dev' and 'stop' in command:
            subprocess.call(systemctl(instance) + ['reset-failed', instance.unit],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _ensure_socket_dir(instance)
    if plan_.action == 'stop' or not wait_ready:
        return True, {'stop': 'Dienst gestoppt.', 'start': 'Dienst gestartet.',
                      'restart': 'Dienst neu gestartet.'}[plan_.action]
    if wait_until_ready(instance):
        return True, f'Dienst läuft, {instance.url} antwortet.'
    return False, f'{instance.url} antwortet nicht innerhalb von {READY_TIMEOUT_S} s – Protokoll prüfen.'


def _ensure_socket_dir(instance: Instance) -> None:
    if instance.kind != 'dev' or not instance.socket:
        return
    directory = Path(instance.socket).parent
    if directory.is_symlink():
        return
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_uid == os.getuid():
        directory.chmod(0o700)


def wait_until_ready(instance: Instance, timeout: float = READY_TIMEOUT_S, sleep=time.sleep) -> bool:
    if not instance.host or not instance.port:
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            peer_certificate(instance.host, instance.port, timeout=2)
            return True
        except (OSError, ValueError):
            sleep(1)
    return False


# ------------------------------------------------------------------ Protokoll

@dataclass
class LogLine:
    time: str
    level: str      # fehler | warnung | info | debug
    text: str


_PRIORITY = {0: 'fehler', 1: 'fehler', 2: 'fehler', 3: 'fehler', 4: 'warnung', 5: 'info', 6: 'info', 7: 'debug'}


def _level(priority: int, text: str) -> str:
    lowered = text.lower()
    if priority <= 3 or 'traceback' in lowered or lowered.startswith(('error', 'fehler')):
        return 'fehler'
    if priority == 4 or 'warn' in lowered[:40]:
        return 'warnung'
    return _PRIORITY.get(priority, 'info')


def journal_command(instance: Instance, lines: int = 200, follow: bool = False, as_json: bool = True):
    if instance.unit is None:
        raise ValueError('Kein Dienst mit Journal (portable Installation).')
    command = ['journalctl'] + (['--user'] if instance.scope == 'user' else []) + [
        '-u', instance.unit, '-n', str(lines), '--no-pager']
    if as_json:
        command += ['-o', 'json']
    else:
        command += ['-o', 'short-iso']
    if follow:
        command.append('-f')
    return command


_SYSTEMD = {'Started': 'Dienst gestartet', 'Stopped': 'Dienst gestoppt', 'Starting': 'Dienst startet',
            'Stopping': 'Dienst wird gestoppt'}


def _systemd_message(message: str) -> str:
    """systemd-Zeilen mit vollständigem Startbefehl auf das Ereignis kürzen."""
    match = re.match(r'^(Started|Stopped|Starting|Stopping) (\S+?)(?:\.service)?(?: - .*)?\.?$', message)
    if match:
        return f'{_SYSTEMD[match.group(1)]} ({match.group(2)})'
    return message


def parse_journal(text: str) -> list[LogLine]:
    result = []
    for raw in text.splitlines():
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        message = entry.get('MESSAGE')
        if isinstance(message, list):  # Binärnachricht
            message = bytes(message).decode('utf-8', 'replace')
        if not isinstance(message, str):
            continue
        try:
            stamp = datetime.fromtimestamp(int(entry.get('__REALTIME_TIMESTAMP', 0)) / 1e6)
            when = stamp.strftime('%H:%M:%S')
        except (TypeError, ValueError, OverflowError):
            when = '--:--:--'
        priority = int(entry.get('PRIORITY', 6)) if str(entry.get('PRIORITY', '6')).isdigit() else 6
        if entry.get('SYSLOG_IDENTIFIER') == 'systemd':
            message = _systemd_message(message)
        for part in message.splitlines() or ['']:
            result.append(LogLine(when, _level(priority, part), part))
    return result


def read_journal(instance: Instance, lines: int = 200, run=None) -> tuple[list[LogLine], str | None]:
    try:
        command = journal_command(instance, lines)
    except ValueError as error:
        return [], str(error)
    try:
        if run is not None:
            code, out, err = run(command)
        else:
            done = subprocess.run(command, capture_output=True, text=True, timeout=10)
            code, out, err = done.returncode, done.stdout, done.stderr
    except (OSError, subprocess.TimeoutExpired) as error:
        return [], str(error)
    if code != 0:
        return [], (err.strip() or f'journalctl Exit {code}')
    return parse_journal(out), None
