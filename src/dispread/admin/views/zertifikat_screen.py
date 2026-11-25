"""Zertifikat erneuern in der Konsole (statt im pausierten Terminal).

Zwei Wege, beide mit Laufsperre, Plan, ausdrücklicher Bestätigung, Schrittliste, Protokoll und Ergebnis:

* ``bridge`` – das ausgelieferte Zertifikat ist die Brückenidentität des Pi
  (``workbench.cli.renew_bridge_identity``): neues Zertifikat mit gleicher Pi-ID, gleichem Schlüssel und
  gleichen Namen. Jede Windows-Brücke merkt sich den Fingerabdruck und muss danach das neue Profil laden und
  neu koppeln; Browser müssen neu vertrauen; der Dienst wird neu gestartet.
* ``tls`` – ein gewöhnliches Zertifikat (``renew-tls``, gleicher Schlüssel).

Der Bildschirm startet den Dienst am Ende neu (``service.plan/execute``). Das sudo-Passwort (Systemdienst) kommt
aus dem maskierten Feld, geht nur an ``sudo_validate`` und wird nicht protokolliert.
"""

from __future__ import annotations

import hashlib
import os
import shlex
import ssl
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Group
from rich.text import Text

from .. import calibrate, probes, service
from ..ui import SOFT, Confirmation
from ..widgets import SectionCard, badge, fields, header, help_line, value, wrap_rows
from .worker_screen import ABORTED, DONE, FAILED, RUNNING, SKIPPED, WAITING, Step, WorkerScreen, reason_block

TITLES = {'bridge': 'Zertifikat der Brückenidentität erneuern', 'tls': 'Zertifikat erneuern'}
STEP_LABELS = {'sperre': 'Laufsperre prüfen', 'erneuern': 'Neues Zertifikat ausstellen und prüfen',
               'dienst': 'Werkbank-Dienst neu starten und auf HTTPS warten'}
RESULT_WORDS = {'ok': (probes.OK, 'erneuert'), 'partial': (probes.WARN, 'erneuert, Neustart offen'),
                'blocked': (probes.WARN, 'gesperrt'), 'cancelled': (probes.WARN, 'abgebrochen'),
                'failed': (probes.FAIL, 'fehlgeschlagen')}


@dataclass
class CertResult:
    outcome: str = 'failed'          # ok | partial | blocked | cancelled | failed
    mode: str = 'bridge'
    message: str = ''
    reason: str | None = None
    renewal: object | None = None    # workbench.cli.BridgeRenewalResult
    previous_fingerprint: str | None = None
    fingerprint: str | None = None
    restarted: bool | None = None    # None: nicht versucht
    restart_message: str = ''
    restart_hint: str = ''
    notes: list[str] = field(default_factory=list)


def fingerprint(path: Path) -> str | None:
    """SHA-256 über das DER des Zertifikats in ``path`` (Hex), None wenn nicht lesbar."""
    try:
        der = ssl.PEM_cert_to_DER_cert(Path(path).read_text(encoding='ascii'))
    except (OSError, ValueError, UnicodeError):
        return None
    return hashlib.sha256(der).hexdigest()


def short(digest: str | None) -> str:
    return f'{digest[:16]}…{digest[-8:]}' if digest else '–'


def default_runner(argv: list[str]) -> tuple[int, str, str]:
    try:
        done = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120,
                              check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return 127, '', str(error)
    return done.returncode, done.stdout, done.stderr


def default_restart(instance, collect) -> tuple[bool, str]:
    plan = service.plan('restart', instance, collect(instance, include_setup=False))
    return service.execute(plan, instance, interactive=False, echo=lambda _line: None)


class ZertifikatErneuernScreen(WorkerScreen):
    GROUP = 'zertifikat'
    TITLE_ICON = 'cert'
    ASK_DANGER = True
    PROGRESS_LABEL = 'Schritte'
    STEP_STARTS_RUN = False

    def __init__(self, instance, mode: str = 'bridge', *, directory: Path | None = None, renew=None, restart=None,
                 collect=probes.collect, runner=None, sudo=None):
        super().__init__(instance, TITLES[mode])
        self.mode = mode
        self.directory = Path(directory) if directory else (Path(instance.data) / 'tls' if instance.data else None)
        self.renew_fn = renew
        self.restart_fn = restart or (lambda inst: default_restart(inst, collect))
        self.collect = collect
        self.runner = runner or default_runner
        self.sudo = sudo or calibrate
        self.steps = [Step(key, label) for key, label in STEP_LABELS.items()]
        self.plan = ('Plan', self._plan_lines())
        self.locked: str | None = None   # Laufsperre (aus dem Worker)

    @property
    def OK_LABEL(self) -> str:  # noqa: N802
        return 'Neu ausstellen, neu koppeln' if self.mode == 'bridge' else 'Erneuern'

    # ------------------------------------------------------------ Text
    def _plan_lines(self) -> list[str]:
        if self.mode == 'bridge':
            return [
                'Neues Zertifikat mit derselben Pi-ID, demselben Schlüssel und denselben Namen und Adressen. '
                'Das bisherige wird gesichert (die Sicherung enthält den privaten Schlüssel und ist nur für Sie '
                'lesbar).',
                'Folge: Jede Windows-Brücke merkt sich den Fingerabdruck des alten Zertifikats und verweigert die '
                'Verbindung. Sie muss danach das neue Profil pi.dispread aus der Werkbank laden und neu '
                'koppeln. Browser müssen dem neuen Zertifikat neu vertrauen.',
                'Der Werkbank-Dienst wird neu gestartet (dabei brechen Verbindungen kurz ab). Läuft gerade eine '
                'Messung oder Einrichtung, ist die Erneuerung gesperrt.']
        return ['Stellt das Zertifikat mit demselben Schlüssel neu aus; das alte bleibt als Sicherung liegen.',
                'Browser und Windows müssen dem neuen Zertifikat wieder vertrauen. Der Werkbank-Dienst wird neu '
                'gestartet, erst dann liefert er das neue aus. Läuft gerade eine Messung, ist es gesperrt.']

    def renew_command(self) -> list[str]:
        command = [sys.executable, '-m', 'dispread.workbench.cli', 'renew-tls', '--directory', str(self.directory)]
        if self.instance.scope == 'system' and os.geteuid() != 0:
            command = ['sudo', '-n', *command]
        return command

    # ------------------------------------------------------------ Ablauf
    def sudo_needed(self) -> bool:
        if self.instance.scope != 'system' or os.geteuid() == 0:
            return False
        return self.mode == 'tls' or self.instance.unit is not None

    def obtain_sudo(self) -> bool:
        if not self.sudo_needed() or self.sudo.sudo_cached():
            return True
        return self.ask_password(self.sudo.sudo_validate,
                                 head='Das Zertifikat wird erneuert und der Werkbank-Dienst mit sudo neu gestartet.')

    def run_job(self, console) -> None:
        result = CertResult(mode=self.mode)
        console.last_result = result
        try:
            self._job(console, result)
        except ValueError as error:
            result.outcome = 'blocked' if 'gesperrt' in str(error) else 'failed'
            result.reason = result.message = str(error)
            console.mark(probes.WARN if result.outcome == 'blocked' else probes.FAIL, result.message)

    def _job(self, console, result: CertResult) -> None:
        console.step(STEP_LABELS['sperre'], key='sperre')
        snapshot = self.collect(self.instance, include_setup=False)
        if snapshot.stop_blocker:
            self.thread_call(self.set_locked, snapshot.stop_blocker)
            result.outcome, result.reason = 'blocked', f'Erneuerung gesperrt: {snapshot.stop_blocker}'
            result.message = result.reason
            console.mark(probes.WARN, result.message)
            return
        title = 'Zertifikat der Brückenidentität erneuern?' if self.mode == 'bridge' else 'Zertifikat erneuern?'
        lines = ['Alle Windows-Brücken müssen danach neu koppeln.'] if self.mode == 'bridge' else []
        expected = 'erneuern' if self.mode == 'bridge' else None
        if not console.confirm(title, lines, expected) or (expected is not None and not self.obtain_sudo()):
            result.outcome, result.reason = 'cancelled', 'Abgebrochen, nichts geändert.'
            result.message = result.reason
            console.mark(probes.WARN, result.message)
            return
        console.step(STEP_LABELS['erneuern'], key='erneuern')
        if self.mode == 'bridge':
            self._renew_bridge(console, result)
        else:
            self._renew_tls(console, result)
        if result.outcome not in ('failed',):
            self._restart(console, result)

    def _renew_bridge(self, console, result: CertResult) -> None:
        renew = self.renew_fn
        if renew is None:
            from dispread.workbench.cli import renew_bridge_identity as renew
        try:
            renewal = renew(self.instance, confirmed=True, collect=self.collect)
        except PermissionError as error:
            command = shlex.join(['dispread', 'bridge', 'identity', '--renew', '--yes'])
            result.reason = (f'Keine Berechtigung für die Brückenidentität ({error.filename or error}). Als '
                             f'Dienstkonto ausführen: {command}')
            result.message = result.reason
            console.mark(probes.FAIL, result.message)
            return
        result.renewal = renewal
        result.previous_fingerprint, result.fingerprint = (renewal.previous_certificate_sha256,
                                                           renewal.certificate_sha256)
        result.outcome = 'ok'
        console.mark(probes.OK, f'Neues Zertifikat für {renewal.pi_id} ausgestellt, gültig bis '
                                f'{renewal.not_after_utc}.')
        console.line(f'Sicherung: {renewal.backup}')

    def _renew_tls(self, console, result: CertResult) -> None:
        cert = self.directory / 'cert.pem'
        result.previous_fingerprint = fingerprint(cert)
        code, out, err = self.runner(self.renew_command())
        for line in (out + '\n' + err).splitlines():
            if line.strip():
                console.line(line.rstrip(), stream=console.err if code else None)
        if code != 0:
            result.reason = result.message = f'Erneuern fehlgeschlagen (Exit {code}).'
            console.mark(probes.FAIL, result.message)
            return
        result.fingerprint = fingerprint(cert)
        result.outcome = 'ok'
        console.mark(probes.OK, 'Neues Zertifikat ausgestellt (gleicher Schlüssel).')

    def _restart(self, console, result: CertResult) -> None:
        console.step(STEP_LABELS['dienst'], key='dienst')
        if self.instance.unit is None:
            result.restarted, result.outcome = False, 'partial'
            result.restart_hint = 'Werkbank-Prozess von Hand beenden und neu starten.'
            console.mark(probes.WARN, 'Kein verwalteter Dienst: ' + result.restart_hint)
            return
        try:
            ok, message = self.restart_fn(self.instance)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            ok, message = False, str(error)
        result.restarted, result.restart_message = ok, message
        if ok:
            console.mark(probes.OK, message)
        else:
            result.outcome = 'partial'
            result.restart_hint = 'Dienst von Hand neu starten: picam restart'
            console.mark(probes.WARN, f'{message} {result.restart_hint}')

    def collect_result(self, console, failure):
        result = console.last_result
        if failure and result.outcome == 'failed' and not result.reason:
            result.reason = result.message = failure
        return result

    # ------------------------------------------------------------ Hooks
    def set_locked(self, text: str) -> None:
        self.locked = text
        self.alarms.append([f'Erneuerung gesperrt: {text}', 'Erst beenden, dann erneut versuchen. '
                            'Nichts wurde geändert.'])
        self.update_view()

    def finish_steps(self, result: CertResult) -> None:
        for step in self.steps:
            if step.state == WAITING:
                step.state = SKIPPED
            elif step.state == RUNNING:
                if step.key == 'dienst':
                    step.state = DONE if result.restarted else FAILED
                elif result.outcome == 'cancelled':
                    step.state = ABORTED
                else:
                    step.state = DONE if result.outcome in ('ok', 'partial') else FAILED
        if result.outcome == 'blocked' and self.locked:
            for step in self.steps:
                if step.key == 'sperre':
                    step.state = FAILED

    def result_badge(self, result: CertResult) -> tuple[str, str]:
        return RESULT_WORDS.get(result.outcome, (probes.FAIL, result.outcome))

    def after_finished(self, result: CertResult) -> None:
        app = self.app
        level, word = self.result_badge(result)
        text = f'{self.title_text}: {word}.'
        if result.outcome in ('ok', 'partial') and self.mode == 'bridge':
            text += ' Windows-Brücken neu koppeln, Browser neu vertrauen.'
        app.message(level, text)
        app._setup_at = 0.0
        app.action_refresh()

    def cancel_confirmation(self) -> Confirmation:
        return Confirmation(
            'Erneuerung abbrechen?',
            ['Bis zur Ausstellung ist nichts geändert. Ist das neue Zertifikat schon ausgestellt, läuft der '
             'Vorgang zu Ende (Neustart des Dienstes).'], [], 'Abbruch anfordern', danger=True)

    def hint_text(self) -> str:
        if self.finished:
            return 'Esc oder Enter schließt. Der Befund der Konsole wird neu geladen.'
        if self.pending is not None:
            return 'Enter bestätigt, Esc bricht ab (nichts wird geändert).'
        if self.phase == 'running':
            return 'Der Vorgang läuft zu Ende; Abbrechen nur vor der Ausstellung wirksam.'
        return 'Laufsperre wird geprüft. Esc bricht ab.'

    # ------------------------------------------------------------ Anzeige
    def draw_plan(self) -> None:
        card = self.query_one('#kal-plan', SectionCard)
        card.display = self.plan is not None and self.phase in ('prep', 'confirm')
        width = self._width(card)
        notes = Text()
        if self.mode == 'bridge':
            notes.append_text(badge(probes.WARN, 'Windows-Brücken müssen neu koppeln'))
            notes.append(' ')
        notes.append_text(badge(probes.WARN, 'Dienst wird neu gestartet'))
        body = [notes, Text('')] + [Text(line, style=SOFT) for line in self.plan[1]]
        card.show(header('cert', 'Plan', None, width, note='neues Zertifikat, gleiche Pi-ID'
                         if self.mode == 'bridge' else 'gleicher Schlüssel'), Group(*body), None)

    def draw_checks(self) -> None:
        """Nach dem Erfolg: „Nächste Schritte“ (Windows-Brücken, Browser)."""
        card = self.query_one('#kal-checks', SectionCard)
        result = self.result
        card.display = result is not None and result.outcome in ('ok', 'partial')
        if not card.display:
            return
        width = self._width(card)
        rows: list = []
        renewal = result.renewal
        if self.mode == 'bridge' and renewal is not None:
            where = renewal.profile_url or 'Werkbank im Browser, Windows-Brücke einrichten'
            rows.append(('1. Profil laden', value(f'{renewal.profile_filename}: {where}')))
            rows.append(('   oder auf dem Pi', value(shlex.join(renewal.profile_export_command))))
            rows.append(('2. Windows-Brücke', value('neues Profil importieren und neu koppeln')))
            rows.append(('3. Browser', value('dem neuen Zertifikat neu vertrauen (öffentliche cert.pem)')))
        else:
            rows.append(('1. Browser', value('dem neuen Zertifikat neu vertrauen')))
        if result.restarted is False:
            rows.insert(0, ('0. Dienst', value(result.restart_hint or 'neu starten')))
        card.show(header('check', 'Nächste Schritte', None, width), wrap_rows(rows, label_w=19), None)

    def draw_result(self) -> None:
        card = self.query_one('#kal-result', SectionCard)
        result = self.result
        card.display = result is not None
        if result is None:
            return
        width = self._width(card)
        level, word = self.result_badge(result)
        rows: list = []
        renewal = result.renewal
        if renewal is not None:
            rows.append(('Pi-ID', value(renewal.pi_id, None), True))
        if result.previous_fingerprint or result.fingerprint:
            rows.append(('Fingerabdruck alt', value(short(result.previous_fingerprint)), True))
            rows.append(('Fingerabdruck neu', value(short(result.fingerprint)), True))
        if renewal is not None:
            rows.append(('Gültig bis', value(renewal.not_after_utc)))
            rows.append(('Sicherung', value(str(renewal.backup)), True))
            if renewal.certificate_export:
                rows.append(('Öffentliche Kopie', value(str(renewal.certificate_export)), True))
        if result.restarted is not None:
            rows.append(('Dienst', badge(probes.OK, 'neu gestartet') if result.restarted
                         else badge(probes.WARN, 'NICHT neu gestartet')))
        if result.outcome in ('failed', 'blocked', 'cancelled'):
            rows.append(('Folge', badge(probes.OFF, 'nichts geändert')))
        help_text = None
        if result.outcome == 'ok' and self.mode == 'bridge':
            help_text = help_line('Das neue Zertifikat gilt jetzt; die Windows-Brücken müssen neu koppeln.')
        elif result.outcome == 'partial':
            help_text = help_line('Das neue Zertifikat gilt erst nach dem Neustart des Dienstes.')
        body = fields(rows, width, label_w=19, columns=1)
        if result.reason and result.outcome in ('failed', 'blocked', 'cancelled'):
            body = Group(body, reason_block(result.reason))
        card.show(header('values', 'Ergebnis', badge(level, word), width), body, help_text)
