"""Update und Rückweg in der Konsole (statt im pausierten Terminal).

Derselbe Ablauf wie ``picam update`` (``update.run_update``), mit eigener Konsole: Plan, Bestätigung,
Schrittliste mit Fortschritt, Protokoll und Ergebnis (alte → neue Version, Rückweg ausgelöst?) stehen als
Karten in diesem Bildschirm. Die Grundlage (Worker-Thread, Rückfragen, sudo-Passwort, Abbruch) ist
``WorkerScreen``.

Nach einem Erfolg bietet der Bildschirm an, die Konsole mit der neuen Version neu zu starten
(``app.relaunch``; ``tui.run`` ruft nach dem Beenden ``os.execv`` auf den gemeldeten Pfad auf).
Das sudo-Passwort wird nur an ``update.sudo_validate`` gereicht.
"""

from __future__ import annotations

import subprocess
from dataclasses import replace
from functools import partial
from pathlib import Path

from rich.console import Group
from rich.text import Text

from .. import probes, update
from ..ui import SOFT, Confirmation, ConfirmScreen
from ..widgets import SectionCard, badge, fields, header, help_line, value
from .worker_screen import DONE, FAILED, RUNNING, SKIPPED, WAITING, Step, WorkerScreen, reason_block

MODES = {'update': 'Update installieren', 'rollback': 'Zurück auf die vorige Version',
         'activate': 'Version umschalten'}


class UpdateScreen(WorkerScreen):
    """Plan, Lauf und Ergebnis eines Updates (``update``), Rückwegs (``rollback``) oder Umschaltens (``activate``)."""

    GROUP = 'update'
    ASK_DANGER = False
    TITLE_ICON = 'update'
    PROGRESS_LABEL = 'Schritte'

    def __init__(self, instance, mode: str = 'update', *, source: str | None = None, sha256: str | None = None,
                 release_id: str | None = None, deps: update.Deps | None = None, runner=None):
        super().__init__(instance, MODES[mode])
        self.mode = mode
        self.source = source
        self.sha256 = sha256
        self.release_id = release_id
        self.base_deps = deps
        self.runner = runner or update.run_update
        keys = (('umschalten', 'dienst_neustart', 'bereit') if release_id is not None
                else [key for key in update.STEPS if key != 'rueckweg'])
        self.steps = [Step(key, update.STEPS[key]) for key in keys]
        self.plan = ('Plan', self._plan_lines())
        self.old_version: str | None = None

    @property
    def OK_LABEL(self) -> str:  # noqa: N802 - je Modus
        return {'update': 'Installieren', 'rollback': 'Zurückschalten'}.get(self.mode, 'Umschalten')

    def _plan_lines(self) -> list[str]:
        if self.release_id is not None:
            lines = [f'Aktive Version wird auf {self.release_id} umgeschaltet; der Dienst wird neu gestartet.']
            if self.mode == 'rollback':
                lines.append('Die jetzige Version bleibt installiert; Daten, Einstellungen und Kopplungen bleiben.')
            return lines
        return [f'Archiv: {self.source}',
                'Die neue Version wird neben der laufenden vorbereitet und geprüft (eigene Umgebung, Selbsttest), '
                'dann umgeschaltet und der Dienst neu gestartet.',
                'Antwortet sie nicht, schaltet picam auf die jetzige zurück. Daten, Einstellungen und Kopplungen '
                'bleiben.']

    def progress_text(self, elapsed: float, total: float) -> str:
        return f' {elapsed:.0f} / {total:.0f}'

    # ------------------------------------------------------------ Ablauf
    def run_job(self, console) -> None:
        base = self.base_deps or update.Deps()
        restart = base.restart or partial(update._restart_and_wait, output=subprocess.DEVNULL)
        deps = replace(base, cancelled=self.cancel_event.is_set, restart=restart)
        self.runner(self.instance, self.source, self.sha256, console, deps, release_id=self.release_id)

    def collect_result(self, console, failure):
        result = console.last_result
        if result is None:
            result = update.Result('failed', new_version=self.release_id, reason=failure or 'ohne Ergebnis beendet',
                                   message=failure or 'ohne Ergebnis beendet')
        return result

    def obtain_sudo(self) -> bool:
        if not update.sudo_needed(self.instance) or update.sudo_cached():
            return True
        return self.ask_password(update.sudo_validate, head='Der Werkbank-Dienst wird mit sudo neu gestartet.')

    # ------------------------------------------------------------ Hooks
    def on_step(self, key, text) -> None:
        if key == 'rueckweg' and not any(s.key == key for s in self.steps):
            for step in self.steps:
                if step.state == RUNNING:
                    step.state = FAILED
        super().on_step(key, text)

    def finish_steps(self, result: update.Result) -> None:
        for step in self.steps:
            if step.state == WAITING:
                step.state = SKIPPED
            elif step.state == RUNNING:
                if step.key == 'rueckweg':
                    step.state = DONE if result.rollback_ok else FAILED
                else:
                    step.state = DONE if result.outcome == 'ok' else FAILED
        if result.outcome == 'ok':
            for step in self.steps:
                if step.state == FAILED:
                    step.state = DONE

    def result_badge(self, result: update.Result) -> tuple[str, str]:
        if result.outcome == 'ok':
            return probes.OK, 'zurückgeschaltet' if self.mode == 'rollback' else 'aktualisiert'
        if result.rollback_triggered:
            return (probes.WARN, 'zurückgerollt') if result.rollback_ok else (probes.FAIL, 'Rückweg ohne Antwort')
        return {'blocked': (probes.WARN, 'gesperrt'), 'cancelled': (probes.WARN, 'abgebrochen')}.get(
            result.outcome, (probes.FAIL, 'fehlgeschlagen'))

    def after_finished(self, result: update.Result) -> None:
        from ..instance import discover

        app = self.app
        level, word = self.result_badge(result)
        app.message(level, f'{self.title_text}: {word}.')
        if result.outcome in ('ok', 'failed'):
            try:
                app.instance = discover(app.instance.config)
            except Exception:  # noqa: BLE001 - die Anzeige bleibt mit der alten Instanz benutzbar
                pass
        app._setup_at = 0.0
        app.action_refresh()
        if result.outcome == 'ok' and self.restart_path(result):
            self.app.push_screen(ConfirmScreen(Confirmation(
                'Konsole mit der neuen Version neu starten?',
                [f'Diese Konsole läuft noch mit der alten Version ({result.old_version or "–"}). '
                 f'Neu gestartet nutzt sie {result.new_version or "die neue Version"}.',
                 'Es ändert sich nichts an der Werkbank; nur diese Konsole wird neu geöffnet.'],
                [self.restart_path(result)], 'Konsole neu starten')), callback=self._relaunch(result))

    def restart_path(self, result: update.Result) -> str | None:
        path = result.restart_command
        return path if path and Path(path).exists() else None

    def _relaunch(self, result: update.Result):
        def callback(yes: bool | None) -> None:
            if yes:
                command = [self.restart_path(result)]
                if self.instance.config:
                    command += ['--config', self.instance.config]
                self.app.relaunch = command
                self.app.exit(0)
        return callback

    def cancel_confirmation(self) -> Confirmation:
        return Confirmation(
            'Update abbrechen?',
            ['Ein angefangener Vorbereitungsschritt läuft bis zur nächsten Prüfstelle zu Ende. Eine fertig '
             'vorbereitete Version bleibt liegen und lässt sich später aktivieren.',
             'Nach dem Umschalten lässt sich nicht mehr abbrechen: Neustart und gegebenenfalls Rückweg laufen '
             'zu Ende.'],
            [], 'Abbruch anfordern', danger=True)

    def cancel_hint(self) -> str:
        return 'Abbruch angefordert: wirkt an der nächsten Prüfstelle, vor dem Umschalten bleibt alles beim Alten.'

    def hint_text(self) -> str:
        if self.finished:
            return 'Esc oder Enter schließt. Der Befund der Konsole wird neu geladen.'
        if self.pending is not None:
            return 'Enter bestätigt, Esc bricht ab (nichts wird geändert).'
        if self.cancel_requested:
            return 'Nach dem Umschalten laufen Neustart und Rückweg zu Ende.'
        if self.phase == 'running':
            return 'Esc fordert den Abbruch an (nur bis zum Umschalten wirksam).'
        return 'Esc bricht ab, solange nichts geändert ist.'

    # ------------------------------------------------------------ Anzeige
    def draw_plan(self) -> None:
        card = self.query_one('#kal-plan', SectionCard)
        card.display = self.plan is not None and self.phase in ('prep', 'confirm')
        if self.plan is None:
            return
        width = self._width(card)
        notes = Text()
        notes.append_text(badge(probes.WARN, 'Dienst wird neu gestartet'))
        body = [notes, Text('')] + [Text(line, style=SOFT) for line in self.plan[1]]
        card.show(header('update', 'Plan', None, width, note=MODES[self.mode]), Group(*body), None)

    def draw_result(self) -> None:
        card = self.query_one('#kal-result', SectionCard)
        result = self.result
        card.display = result is not None
        if result is None:
            return
        width = self._width(card)
        level, word = self.result_badge(result)
        old = result.old_version or '–'
        new = result.new_version or '–'
        rows: list = [('Version', value(f'{old} → {new}' if result.outcome == 'ok' else f'{old} (aktiv)'))]
        if result.outcome == 'ok':
            rows.append(('Dienst', badge(probes.OK, 'antwortet')))
        if result.rollback_triggered:
            rows.append(('Rückweg', badge(probes.OK, f'{old} läuft wieder') if result.rollback_ok
                         else badge(probes.FAIL, 'vorige Version antwortet nicht')))
        text = result.reason if result.reason and result.outcome != 'ok' else result.message
        help_text = None
        if result.outcome == 'ok':
            help_text = help_line('Diese Konsole läuft noch in der alten Version; mit picam neu öffnen.')
        elif result.rollback_triggered:
            help_text = help_line('Protokoll ansehen: picam logs.')
        elif result.outcome in ('blocked', 'cancelled'):
            help_text = help_line('Nichts umgeschaltet; die aktive Version ist unverändert.')
        body = fields(rows, width, label_w=14, columns=1)
        if text:
            body = Group(body, reason_block(text, 'Grund' if result.outcome != 'ok' else 'Meldung'))
        card.show(header('values', 'Ergebnis', badge(level, word), width), body, help_text)
