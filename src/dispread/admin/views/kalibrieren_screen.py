"""Bildschirm der Timing-Kalibrierung in der Konsole (statt im pausierten Terminal).

Derselbe Ablauf wie ``picam kalibrieren`` (``calibrate.calibrate``, ``check_file``,
``import_file``), nur mit einer eigenen ``Console``: Vorprüfung, Plan, Bestätigung,
Schrittliste, Fortschritt, Protokoll und Ergebnis erscheinen als Karten in diesem
Bildschirm. Der Ablauf läuft in einem Worker-Thread; jede Änderung der Oberfläche
geht über ``app.call_from_thread``. Rohmeldungen der Aufnahme (``deps.out/err``)
landen im Protokollfeld, nie auf dem echten Terminal.

Regeln:

* Abbruch ist kooperativ (``deps.cancelled``). Aufräumen (Normierung zurückstellen,
  Dienst starten) läuft immer; der Bildschirm schließt erst, wenn der Worker zurück ist.
  Esc oder q während des Laufs fordert den Abbruch nur an (nach Rückfrage).
* Die Auswertung ist nicht abbrechbar; ein Abbruch währenddessen verhindert nur die
  Übernahme.
* Das sudo-Passwort (nur Systeminstanz, nur wenn nötig und nicht gecacht) kommt aus
  einem maskierten Feld, wird nur an ``calibrate.sudo_validate`` gereicht und weder
  protokolliert noch im Zustand des Bildschirms behalten.
"""

from __future__ import annotations

import io
import re
from dataclasses import replace
from pathlib import Path

from rich.console import Group
from rich.text import Text

from .. import calibrate, probes
from ..cli import Style
from ..ui import (
    MUTED,
    SOFT,
    Confirmation,
)
from ..widgets import (
    SectionCard,
    badge,
    fields,
    header,
    help_line,
    value,
    wrap_rows,
)
from .worker_screen import (  # noqa: F401 - Namen bleiben hier erreichbar
    ABORTED,
    DONE,
    FAILED,
    RUNNING,
    SKIPPED,
    SUDO_ATTEMPTS,
    WAITING,
    LogWriter,
    ProgressHook,
    ScreenHooks,
    Step,
    WorkerScreen,
)

#: Schlüssel → Beschriftung, in der Reihenfolge des Ablaufs.
STEP_LABELS = {
    'dienst_stop': 'Werkbank-Dienst stoppen',
    'kamera': 'Kamera freigeben',
    'rueckstellpunkt': 'Rückstellpunkt lesen',
    'aufnahme': 'Aufnahme',
    'normierung': 'Normierung prüfen',
    'dienst_start': 'Werkbank-Dienst starten',
    'pruefen': 'Aufnahme prüfen',
    'auswertung': 'Auswertung (kann einige Minuten dauern)',
    'bauen': 'Kalibrierung bauen und prüfen',
}
SUCCESS = {'installiert', 'importiert', 'gueltig', 'bereits aktiv'}
#: Ergebnis → (Stufe, Wort im Abzeichen)
OUTCOMES = {
    'installiert': (probes.OK, 'installiert'), 'importiert': (probes.OK, 'importiert'),
    'gueltig': (probes.OK, 'gültig'), 'bereits aktiv': (probes.OK, 'bereits aktiv'),
    'abgebrochen': (probes.WARN, 'abgebrochen'), 'nicht erkannt': (probes.FAIL, 'nicht erkannt'),
    'gesperrt': (probes.FAIL, 'nicht möglich'), 'ungueltig': (probes.FAIL, 'ungültig'),
    'fehler': (probes.FAIL, 'Fehler'),
}
MODES = {'kalibrieren': 'Timing-Kalibrierung', 'pruefen': 'Kalibrierdatei prüfen',
         'import': 'Kalibrierdatei importieren'}


class ScreenConsole(ScreenHooks, calibrate.Console):
    """``calibrate.Console`` für die Oberfläche. Alle Hooks laufen im Worker-Thread."""

    def __init__(self, screen: KalibrierenScreen):
        calibrate.Console.__init__(self, Style(io.StringIO(), color=False), out=LogWriter(screen, False),
                                   err=LogWriter(screen, True))
        self.screen = screen

    def checks(self, pre: calibrate.Preflight) -> None:
        self.screen.thread_call(self.screen.on_checks, pre)

    def plan(self, title: str, lines: list[str]) -> None:
        self.screen.thread_call(self.screen.on_plan, title, list(lines))

    def confirm(self, title: str, lines: list[str], expected: str | None, *, deps: calibrate.Deps) -> bool:
        return ScreenHooks.confirm(self, title, lines, expected, deps=deps)


class KalibrierenScreen(WorkerScreen):
    """Vorprüfung, Plan, Lauf und Ergebnis der Kalibrierung (oder Prüfen/Importieren einer Datei)."""

    GROUP = 'kalibrieren'
    PROGRESS_LABEL = 'Aufnahme'

    def __init__(self, instance, mode: str = 'kalibrieren', *, path: str | Path | None = None,
                 options: calibrate.Options | None = None, deps: calibrate.Deps | None = None):
        super().__init__(instance, MODES[mode])
        self.mode = mode
        self.path = Path(path).expanduser() if path else None
        self.options = options or calibrate.Options()
        self.base_deps = deps

    @property
    def OK_LABEL(self) -> str:  # noqa: N802 - Klassenattribut der Grundklasse, hier je Modus
        return 'Kalibrierung starten' if self.mode == 'kalibrieren' else 'Ja'

    # ------------------------------------------------------------ Ablauf
    def make_console(self):
        return ScreenConsole(self)

    def run_job(self, console) -> None:
        base = self.base_deps or calibrate.Deps()
        deps = replace(base, cancelled=self.cancel_event.is_set, service_interactive=False,
                       out=console.out, err=console.err, isatty=lambda: True)
        if self.mode == 'kalibrieren':
            calibrate.calibrate(self.instance, self.options, console, deps)
        elif self.mode == 'import':
            calibrate.import_file(self.instance, self.path, console, deps)
        else:
            calibrate.check_file(self.instance, self.path, console)

    def collect_result(self, console, failure):
        result = console.last_result
        if result is None:
            result = calibrate.Result('fehler', calibrate.EXIT_FAIL, reason=failure or 'ohne Ergebnis beendet')
        return result

    def obtain_sudo(self) -> bool:
        """Passwort für den Dienststopp holen, falls nötig und nicht gecacht (Systeminstanz)."""
        pre = self.pre
        if pre is None or pre.snapshot is None:
            return True
        if not calibrate.sudo_needed(self.instance, pre.snapshot) or calibrate.sudo_cached():
            return True
        return self.ask_password(calibrate.sudo_validate, head='Der Werkbank-Dienst wird mit sudo gestoppt.')

    # ------------------------------------------------------------ Hooks (UI-Thread)
    def on_checks(self, pre: calibrate.Preflight) -> None:
        self.pre = pre
        if not pre.problems and self.mode == 'kalibrieren':
            keys = [k for k in STEP_LABELS if pre.service_running or k not in ('dienst_stop', 'dienst_start')]
            self.steps = [Step(k, STEP_LABELS[k]) for k in keys]
        self.update_view()

    def on_plan(self, title: str, lines: list[str]) -> None:
        self.plan = (title, lines)
        self.update_view()

    def finish_steps(self, result: calibrate.Result) -> None:
        for step in self.steps:
            if step.state == WAITING:
                step.state = SKIPPED
            elif step.state == RUNNING:
                # Aufräumschritte zählen nach ihrem eigenen Ergebnis, nicht nach dem des Laufs
                if step.key == 'dienst_start':
                    step.state = DONE if result.service_restarted else FAILED
                elif step.key == 'normierung':
                    step.state = DONE if result.norm_restored else FAILED
                else:
                    step.state = DONE if result.outcome in SUCCESS else (ABORTED if self.cancel_requested
                                                                         else FAILED)
        for step in self.steps:
            if step.key == 'dienst_start' and result.service_restarted is False:
                step.state = FAILED
            if step.key == 'normierung' and result.norm_restored is False:
                step.state = FAILED

    def result_badge(self, result: calibrate.Result) -> tuple[str, str]:
        return OUTCOMES.get(result.outcome, (probes.FAIL, result.outcome))

    def after_finished(self, result: calibrate.Result) -> None:
        level, word = self.result_badge(result)
        if result.outcome == 'gesperrt':
            text = f'{self.title_text}: nicht möglich, nichts geändert.'
        else:
            text = f'{self.title_text}: {word}.'
        app = self.app
        app.message(level, text)
        app._setup_at = 0.0
        app.action_refresh()

    def cancel_confirmation(self) -> Confirmation:
        return Confirmation(
            'Kalibrierung abbrechen?',
            ['Der Abbruch wirkt an der nächsten Schrittgrenze. Die Normierung des Messverstärkers wird '
             'zurückgestellt und die Werkbank wieder gestartet; das kann einen Moment dauern.',
             'Die Auswertung kann nicht unterbrochen werden: bricht man dort ab, läuft sie zu Ende, '
             'danach wird nichts übernommen.'],
            [], 'Abbruch anfordern', danger=True)

    def cancel_hint(self) -> str:
        return ('Abbruch angefordert: die Auswertung läuft zu Ende, danach wird nichts übernommen.'
                if self.analysis_cancel else
                'Abbruch angefordert: wirkt an der nächsten Schrittgrenze, danach wird aufgeräumt.')

    def step_extras(self, width: int, running) -> list:
        if running is not None and running.key == 'auswertung':
            line = Text('Auswertung ', style=MUTED)
            line.append_text(self._indeterminate(max(10, min(40, width - 36))))
            line.append(' ')
            line.append_text(badge(probes.WARN, 'nicht abbrechbar'))
            return [Text(''), line]
        return []

    # ------------------------------------------------------------ Anzeige
    def draw_checks(self) -> None:
        card = self.query_one('#kal-checks', SectionCard)
        pre = self.pre
        problems = bool(pre and pre.problems)
        card.display = pre is not None and (self.phase in ('prep', 'confirm') or problems)
        if pre is None:
            return
        width = self._width(card)
        rows = []
        for check in pre.checks:
            cell = Text()
            cell.append_text(badge(probes.OK if check.ok else probes.FAIL, 'ok' if check.ok else 'Problem'))
            cell.append(f' {check.text}', style=SOFT)
            rows.append((check.label, cell))
        right = badge(probes.FAIL, 'nicht möglich') if problems else badge(probes.OK, 'bestanden')
        hint = help_line('Nichts geändert. Ursache beheben, dann erneut starten.') \
            if problems else None
        compact = self.phase == 'confirm' and not problems  # Platz für Plan und Frage
        card.show(header('check', 'Vorprüfung', right, width), None if compact else wrap_rows(rows, label_w=16), hint)

    def draw_plan(self) -> None:
        card = self.query_one('#kal-plan', SectionCard)
        card.display = self.plan is not None and self.phase in ('prep', 'confirm')
        if self.plan is None:
            return
        title, lines = self.plan
        width = self._width(card)
        notes = Text()
        if self.pre is not None and self.pre.service_running:
            notes.append_text(badge(probes.WARN, 'Werkbank-Dienst wird gestoppt'))
            notes.append(' ')
        notes.append_text(badge(probes.WARN, 'Normierung des Messverstärkers wird verändert und zurückgestellt'))
        body = [notes, Text('')]
        body += [Text(line, style=SOFT) for line in lines]
        card.show(header('clock', 'Plan', None, width, note=_plan_note(title)), Group(*body), None)

    def draw_result(self) -> None:
        card = self.query_one('#kal-result', SectionCard)
        result = self.result
        card.display = result is not None
        if result is None:
            return
        width = self._width(card)
        level, word = OUTCOMES.get(result.outcome, (probes.FAIL, result.outcome))
        rows: list = []
        if result.outcome == 'gesperrt':
            rows.append(('Folge', badge(probes.OFF, 'nichts geändert')))
        if result.reason:
            rows.append(('Grund', value(result.reason.replace('\n', ' · ')), True))
        rows += [(label, value(text), len(text) > 40) for label, text in result.metrics]
        if self.mode == 'kalibrieren':
            if result.norm_restored is None:
                rows.append(('Normierung', value('nicht verändert')))
            else:
                rows.append(('Normierung', badge(probes.OK, 'zurückgestellt') if result.norm_restored
                             else badge(probes.FAIL, 'NICHT zurückgestellt')))
            if result.service_restarted is None:
                rows.append(('Werkbank-Dienst', value('nicht gestoppt')))
            else:
                rows.append(('Werkbank-Dienst', badge(probes.OK, 'wieder gestartet') if result.service_restarted
                             else badge(probes.FAIL, 'NICHT gestartet')))
        if result.run_dir:
            rows.append(('Ordner' if self.mode != 'kalibrieren' else 'Laufordner', value(str(result.run_dir)), True))
        help_text = None
        if result.outcome == 'abgebrochen' and self.mode == 'kalibrieren':
            help_text = help_line('Nichts übernommen; die vorhandene Kalibrierung ist unverändert.')
        elif result.outcome in SUCCESS and self.mode == 'kalibrieren':
            help_text = help_line('Die Werkbank liest die neue Kalibrierung beim nächsten Laufstart.')
        card.show(header('values', 'Ergebnis', badge(level, word), width),
                  fields(rows, width, label_w=17, columns=2 if width >= 90 else 1), help_text)

    def hint_text(self) -> str:
        if self.finished:
            return 'Esc oder Enter schließt. Der Befund der Konsole wird neu geladen.'
        if self.pending is not None:
            return 'Enter bestätigt, Esc bricht ab (nichts wird geändert).'
        if self.cancel_requested:
            return 'Die Konsole schließt erst, wenn die Rückstellung und der Dienststart durch sind.'
        if self.phase == 'running':
            return 'Esc fordert den Abbruch an; die Konsole bleibt offen, bis aufgeräumt ist.'
        return 'Vorprüfung läuft. Esc bricht ab.'


def _plan_note(title: str) -> str:
    """„Plan (Werkbank etwa 5 min nicht erreichbar)“ → Klammerinhalt als Nebentext."""
    found = re.search(r'\((.*)\)', title)
    return found.group(1) if found else ''


