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

import concurrent.futures
import getpass
import io
import re
import threading
from dataclasses import dataclass, replace
from pathlib import Path

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from .. import calibrate, probes
from ..cli import Style
from ..ui import (
    MUTED,
    SOFT,
    SPINNER,
    TONE,
    Confirmation,
    ConfirmScreen,
    P,
    ReflowLog,
    ascii_mode,
    bar,
    fade_in,
)
from ..widgets import (
    CardBox,
    SectionCard,
    badge,
    fields,
    header,
    help_line,
    icon,
    value,
    wrap_rows,
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
WAITING, RUNNING, DONE, FAILED, SKIPPED, ABORTED = ('wartet', 'läuft', 'fertig', 'fehlgeschlagen',
                                                     'übersprungen', 'abgebrochen')
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
SUDO_ATTEMPTS = 3
POLL_S = 0.15


@dataclass
class Step:
    key: str
    label: str
    state: str = WAITING


class _LogWriter:
    """Dateiähnlich (write/flush): kompletten Zeilen gehen in das Protokollfeld."""

    def __init__(self, screen: KalibrierenScreen, err: bool):
        self.screen, self.err = screen, err
        self._buffer = ''
        self._lock = threading.Lock()

    def write(self, data: str) -> int:
        with self._lock:
            self._buffer += data.replace('\r\n', '\n').replace('\r', '\n')
            *lines, self._buffer = self._buffer.split('\n')
        for line in lines:
            if line.strip():
                self.screen.thread_call(self.screen.log_line, line.rstrip(), self.err)
        return len(data)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


class _Progress:
    """``calibrate.ProgressReporter``: nur Zustand merken; ein Zeitgeber der Oberfläche zeichnet."""

    def __init__(self, screen: KalibrierenScreen):
        self.screen = screen

    def __call__(self, elapsed: float, total: float) -> None:
        self.screen.progress = (float(elapsed), float(total))

    def finish(self) -> None:
        pass


class ScreenConsole(calibrate.Console):
    """``calibrate.Console`` für die Oberfläche. Alle Hooks laufen im Worker-Thread."""

    def __init__(self, screen: KalibrierenScreen):
        super().__init__(Style(io.StringIO(), color=False), out=_LogWriter(screen, False),
                         err=_LogWriter(screen, True))
        self.screen = screen

    def line(self, text: str = '', stream=None) -> None:
        if text.strip():
            self.screen.thread_call(self.screen.log_line, text, stream is self.err)

    def mark(self, level: str, text: str, stream=None) -> None:
        self.screen.thread_call(self.screen.log_mark, level, text)

    def step(self, text: str, *, key=None) -> None:
        self.screen.thread_call(self.screen.on_step, key, text)

    def progress(self, tty: bool):
        return _Progress(self.screen)

    def checks(self, pre: calibrate.Preflight) -> None:
        self.screen.thread_call(self.screen.on_checks, pre)

    def plan(self, title: str, lines: list[str]) -> None:
        self.screen.thread_call(self.screen.on_plan, title, list(lines))

    def loud(self, lines: list[str]) -> None:
        self.screen.thread_call(self.screen.on_loud, list(lines))

    def confirm(self, title: str, lines: list[str], expected: str | None, *, deps: calibrate.Deps) -> bool:
        screen = self.screen
        answer = screen.ask(title=title, lines=lines, expected=expected)
        if expected is not None:
            accepted = answer == expected
        else:
            accepted = answer is True
        if accepted and expected is None and not screen.obtain_sudo():
            accepted = False
        if accepted:
            screen.thread_call(screen.set_phase, 'running')
        return accepted


class KalibrierenScreen(ModalScreen[None]):
    """Vorprüfung, Plan, Lauf und Ergebnis der Kalibrierung (oder Prüfen/Importieren einer Datei)."""

    BINDINGS = [Binding('escape,q', 'back', show=False), Binding('left,right', 'switch', show=False),
                Binding('up', 'scroll_top(-1)', show=False), Binding('down', 'scroll_top(1)', show=False),
                Binding('pageup', 'scroll_top(-5)', show=False), Binding('pagedown', 'scroll_top(5)', show=False)]
    DEFAULT_CSS = '''
    KalibrierenScreen { background: $picam-canvas; }
    #kal { height: 1fr; width: 1fr; max-width: 120; padding: 0 2; }
    #kal-title { height: 1; margin: 1 0 0 0; }
    #kal-alarm { display: none; height: auto; max-height: 9; margin: 1 0 0 0; padding: 0 1;
                 background: $picam-tint-fail; border-left: wide $error; }
    #kal-top { height: auto; max-height: 60%; scrollbar-size-vertical: 1; }
    KalibrierenScreen.-asking #kal-log { display: none; }
    KalibrierenScreen.-asking #kal-top { height: 1fr; max-height: 100%; }
    #kal-ask Static { height: auto; width: 1fr; }
    #kal-input { height: 1; border: none; padding: 0 1; margin: 1 0 0 0; background: $picam-field; }
    #kal-input:focus { background: $picam-field-focus; }
    #kal-log { height: 1fr; min-height: 3; margin: 1 0 0 0; padding: 0 1; background: $picam-surface;
               border: none; scrollbar-size-vertical: 1; overflow-x: hidden; }
    #kal-hint { height: 1; margin: 1 0 0 0; }
    #kal-buttons { height: 1; margin: 1 0 0 0; }
    #kal-buttons Button { margin: 0 2 0 0; }
    '''

    def __init__(self, instance, mode: str = 'kalibrieren', *, path: str | Path | None = None,
                 options: calibrate.Options | None = None, deps: calibrate.Deps | None = None):
        super().__init__()
        self.instance = instance
        self.mode = mode
        self.path = Path(path).expanduser() if path else None
        self.options = options or calibrate.Options()
        self.base_deps = deps
        self.title_text = MODES[mode]
        # Zustand (nur im UI-Thread verändert; ``progress`` schreibt der Worker, die Anzeige liest)
        self.phase = 'prep'          # prep | confirm | running | done
        self.pre: calibrate.Preflight | None = None
        self.plan: tuple[str, list[str]] | None = None
        self.steps: list[Step] = []
        self.progress: tuple[float, float] | None = None
        self.alarms: list[list[str]] = []
        self.result: calibrate.Result | None = None
        self.pending: dict | None = None      # offene Rückfrage {fut, title, lines, ok_label, ...}
        self.cancel_requested = False
        self.analysis_cancel = False
        self.cancel_event = threading.Event()
        self.gone = threading.Event()
        self.finished = False
        self._tick = 0
        self._drawn_progress: tuple | None = None
        self._log_has_text = False

    # ------------------------------------------------------------ Aufbau
    def compose(self):
        with Vertical(id='kal'):
            yield Static(id='kal-title')
            yield Static(id='kal-alarm')
            with VerticalScroll(id='kal-top'):
                yield SectionCard(id='kal-checks')
                yield SectionCard(id='kal-plan')
                with CardBox(id='kal-ask'):
                    yield Static(id='kal-ask-head')
                    yield Static(id='kal-ask-text')
                    yield Input(id='kal-input')
                    yield Static(id='kal-ask-error')
                yield SectionCard(id='kal-result')   # vor dem Ablauf: am Ende steht das Ergebnis oben
                yield SectionCard(id='kal-steps')
            yield ReflowLog(id='kal-log', max_lines=2000, wrap=True, markup=False, auto_scroll=True,
                            highlight=False, min_width=20)
            yield Static(id='kal-hint')
            with Horizontal(id='kal-buttons'):
                yield Button('Abbrechen', id='kal-cancel')
                yield Button('OK', id='kal-ok')

    def on_mount(self) -> None:
        fade_in(self.query_one('#kal'))
        self.set_interval(POLL_S, self._on_tick)
        self.update_view()
        self.query_one('#kal-cancel', Button).focus()
        self.worker = self.run_worker(self._thread_main, thread=True, group='kalibrieren', exit_on_error=False)

    def on_unmount(self) -> None:
        self.gone.set()
        self.cancel_event.set()

    # ------------------------------------------------------------ Worker-Thread
    def thread_call(self, fn, *args) -> bool:
        """Aus dem Worker in die Oberfläche; scheitert still, wenn die App schon schließt."""
        try:
            self.app.call_from_thread(fn, *args)
            return True
        except Exception:  # noqa: BLE001 - Aufräumen im Worker darf nicht an der Oberfläche scheitern
            return False

    def _thread_main(self) -> None:
        console = ScreenConsole(self)
        base = self.base_deps or calibrate.Deps()
        deps = replace(base, cancelled=self.cancel_event.is_set, service_interactive=False,
                       out=console.out, err=console.err, isatty=lambda: True)
        failure: str | None = None
        try:
            if self.mode == 'kalibrieren':
                calibrate.calibrate(self.instance, self.options, console, deps)
            elif self.mode == 'import':
                calibrate.import_file(self.instance, self.path, console, deps)
            else:
                calibrate.check_file(self.instance, self.path, console)
        except Exception as error:  # noqa: BLE001 - nie ohne Ergebnis enden
            failure = f'{type(error).__name__}: {error}'
            console.mark(probes.FAIL, failure)
        finally:
            for writer in (console.out, console.err):
                tail = writer._buffer.strip()
                if tail:
                    self.thread_call(self.log_line, tail, writer.err)
        result = console.last_result
        if result is None:
            result = calibrate.Result('fehler', calibrate.EXIT_FAIL, reason=failure or 'ohne Ergebnis beendet')
        self.thread_call(self.on_finished, result)

    def ask(self, *, title: str, lines: list[str], expected: str | None = None, ok_label: str | None = None,
            entry: str | None = None, danger: bool = True, error: str = '', head: str = '') -> object:
        """Rückfrage im Bildschirm; blockiert den Worker. ``True``/Text, ``None`` bei Abbruch."""
        future: concurrent.futures.Future = concurrent.futures.Future()
        if expected is not None:
            entry, ok_label = 'text', ok_label or 'Übernehmen'
        else:
            ok_label = ok_label or ('Kalibrierung starten' if self.mode == 'kalibrieren' else 'Ja')
        spec = dict(future=future, title=title, lines=lines, expected=expected, ok_label=ok_label,
                    entry=entry, danger=danger, error=error, head=head)
        if not self.thread_call(self.open_ask, spec):
            return None
        while not self.gone.is_set():
            try:
                return future.result(timeout=0.2)
            except concurrent.futures.TimeoutError:
                continue
        return None

    def obtain_sudo(self) -> bool:
        """Passwort für den Dienststopp holen, falls nötig und nicht gecacht (Systeminstanz)."""
        pre = self.pre
        if pre is None or pre.snapshot is None:
            return True
        if not calibrate.sudo_needed(self.instance, pre.snapshot) or calibrate.sudo_cached():
            return True
        account = getpass.getuser()
        error = ''
        for _ in range(SUDO_ATTEMPTS):
            password = self.ask(
                title='sudo-Passwort', ok_label='Weiter', entry='password', danger=False, error=error,
                head='Der Werkbank-Dienst wird mit sudo gestoppt.',
                lines=[f'Passwort des Linux-Kontos „{account}“ (das Konto, mit dem picam läuft; nicht das '
                       'Login der Werkbank). Es wird nur an sudo übergeben und nirgends gespeichert.'])
            if password is None:
                self.thread_call(self.log_line, 'sudo-Anmeldung abgebrochen, nichts geändert.', True)
                return False
            ok, message = calibrate.sudo_validate(str(password))
            del password
            if ok:
                return True
            error = message or 'sudo-Anmeldung fehlgeschlagen.'
        self.thread_call(self.log_line, f'sudo: {error} Nach {SUDO_ATTEMPTS} Versuchen abgebrochen.', True)
        return False

    # ------------------------------------------------------------ Hooks (UI-Thread)
    def set_phase(self, phase: str) -> None:
        self.phase = phase
        self.update_view()

    def log_line(self, text: str, err: bool = False) -> None:
        self._log(Text(text, style=TONE[probes.FAIL] if err else ''))

    def log_mark(self, level: str, text: str) -> None:
        line = Text()
        line.append(f'{icon(_LEVEL_ICON.get(level, "unknown"))} ', style=TONE.get(level, MUTED))
        line.append(text)
        self._log(line)
        if level == probes.FAIL:
            for step in self.steps:
                if step.state == RUNNING:
                    step.state = ABORTED if self.cancel_requested else FAILED
            self.update_view()

    def _log(self, text: Text) -> None:
        self.query_one('#kal-log', ReflowLog).add(text)

    def on_checks(self, pre: calibrate.Preflight) -> None:
        self.pre = pre
        if not pre.problems and self.mode == 'kalibrieren':
            keys = [k for k in STEP_LABELS if pre.service_running or k not in ('dienst_stop', 'dienst_start')]
            self.steps = [Step(k, STEP_LABELS[k]) for k in keys]
        self.update_view()

    def on_plan(self, title: str, lines: list[str]) -> None:
        self.plan = (title, lines)
        self.update_view()

    def on_loud(self, lines: list[str]) -> None:
        text = [line for line in lines if line.strip('! ')]
        self.alarms.append(text)
        for line in text:
            self._log(Text(f'{icon("warn")} {line}', style=f'bold {TONE[probes.FAIL]}'))
        self.update_view()

    def on_step(self, key: str | None, text: str) -> None:
        if self.phase in ('prep', 'confirm'):
            self.phase = 'running'
        index = next((i for i, s in enumerate(self.steps) if s.key == key), None)
        if index is None:
            self.steps.append(Step(key or text, text))
            index = len(self.steps) - 1
        for position, step in enumerate(self.steps):
            if position < index:
                if step.state == WAITING:
                    step.state = SKIPPED
                elif step.state == RUNNING:
                    step.state = DONE
        current = self.steps[index]
        current.state = RUNNING
        if key != 'auswertung':
            current.label = text
        self._log(Text(text, style=f'bold {SOFT}'))
        self.update_view()

    def open_ask(self, spec: dict) -> None:
        self.pending = spec
        self.phase = 'confirm' if self.phase == 'prep' else self.phase
        field = self.query_one('#kal-input', Input)
        field.value = ''
        field.password = spec['entry'] == 'password'
        field.placeholder = (f'„{spec["expected"]}“ eintippen' if spec['expected']
                             else 'Passwort' if spec['entry'] == 'password' else '')
        self.update_view()
        (field if spec['entry'] else self.query_one('#kal-cancel', Button)).focus()
        if spec['entry']:
            self.call_after_refresh(self._scroll_to_ask)

    def _scroll_to_ask(self) -> None:
        self.query_one('#kal-top', VerticalScroll).scroll_to_widget(self.query_one('#kal-ask'), animate=False)

    def on_finished(self, result: calibrate.Result) -> None:
        self.result = result
        self.pending = None
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
        self.phase, self.finished = 'done', True
        self.update_view()
        level, word = OUTCOMES.get(result.outcome, (probes.FAIL, result.outcome))
        if result.outcome == 'gesperrt':
            text = f'{self.title_text}: nicht möglich, nichts geändert.'
        else:
            text = f'{self.title_text}: {word}.'
        app = self.app
        app.message(level, text)
        app._setup_at = 0.0
        app.action_refresh()
        self.query_one('#kal-cancel', Button).focus()
        self.call_after_refresh(self.query_one('#kal-top', VerticalScroll).scroll_home, animate=False)

    # ------------------------------------------------------------ Eingaben
    def _resolve(self, answer) -> None:
        spec, self.pending = self.pending, None
        field = self.query_one('#kal-input', Input)
        field.value = ''  # Passwort nicht im Widget behalten
        if spec is not None and not spec['future'].done():
            spec['future'].set_result(answer)
        self.update_view()

    @on(Button.Pressed, '#kal-ok')
    def _ok(self) -> None:
        spec = self.pending
        if spec is None:
            return
        self._resolve(self.query_one('#kal-input', Input).value if spec['entry'] else True)

    @on(Input.Submitted, '#kal-input')
    def _submitted(self) -> None:
        self._ok()

    @on(Button.Pressed, '#kal-cancel')
    def _cancel_pressed(self) -> None:
        self.action_back()

    def action_switch(self) -> None:
        self.focus_next(Button)

    def action_scroll_top(self, rows: int) -> None:
        top = self.query_one('#kal-top', VerticalScroll)
        top.scroll_to(y=max(0, top.scroll_y + int(rows)), animate=False)

    def action_back(self) -> None:
        if self.pending is not None:
            self._resolve(None)
        elif self.finished:
            self.dismiss(None)
        elif self.phase == 'running':
            if not self.cancel_requested:
                self.app.push_screen(ConfirmScreen(Confirmation(
                    'Kalibrierung abbrechen?',
                    ['Der Abbruch wirkt an der nächsten Schrittgrenze. Die Normierung des Messverstärkers wird '
                     'zurückgestellt und die Werkbank wieder gestartet; das kann einen Moment dauern.',
                     'Die Auswertung kann nicht unterbrochen werden: bricht man dort ab, läuft sie zu Ende, '
                     'danach wird nichts übernommen.'],
                    [], 'Abbruch anfordern', danger=True)), callback=self._cancel_confirmed)
        else:
            self._request_cancel()

    def _cancel_confirmed(self, yes: bool | None) -> None:
        if yes:
            self._request_cancel()

    def _request_cancel(self) -> None:
        self.cancel_requested = True
        running = next((s for s in self.steps if s.state == RUNNING), None)
        self.analysis_cancel = running is not None and running.key == 'auswertung'
        self.cancel_event.set()
        self.update_view()

    def quit_guard(self) -> bool:
        """Von der App bei Ctrl+C aufgerufen: während des Laufs nicht beenden, sondern Abbruch anfordern."""
        if self.finished or self.gone.is_set():
            return False
        self.action_back()
        return True

    # ------------------------------------------------------------ Zeitgeber
    def _on_tick(self) -> None:
        animated = self.app.animation_level != 'none'
        if animated:
            self._tick += 1
        busy = any(s.state == RUNNING for s in self.steps)
        if self.progress != self._drawn_progress or (animated and busy):
            self._draw_steps()

    # ------------------------------------------------------------ Anzeige
    def on_resize(self, event) -> None:
        self.update_view()

    def update_view(self) -> None:
        if not self.is_mounted:
            return
        self.set_class(self.phase in ('prep', 'confirm') and not self.finished, '-asking')
        self.set_class(self.finished, '-done')
        self._draw_title()
        self._draw_alarm()
        self._draw_checks()
        self._draw_plan()
        self._draw_ask()
        self._draw_steps()
        self._draw_result()
        self._draw_hint()
        self._draw_buttons()

    def _width(self, widget) -> int:
        width = widget.content_size.width or widget.size.width
        return width if width > 0 else max(40, self.size.width - 4)

    def _phase_badge(self) -> Text:
        if self.result is not None:
            level, word = OUTCOMES.get(self.result.outcome, (probes.FAIL, self.result.outcome))
            return badge(level, word)
        if self.cancel_requested:
            return badge(probes.WARN, 'Abbruch angefordert')
        return {'prep': badge('busy', 'prüft', 'busy'), 'confirm': badge(probes.WARN, 'wartet auf Sie'),
                'running': badge('busy', 'läuft', 'busy')}.get(self.phase, badge(probes.OFF, '–'))

    def _draw_title(self) -> None:
        title = self.query_one('#kal-title', Static)
        title.update(header('clock', self.title_text, self._phase_badge(), self._width(title)))

    def _draw_alarm(self) -> None:
        alarm = self.query_one('#kal-alarm', Static)
        alarm.display = bool(self.alarms)
        text = Text()
        for number, lines in enumerate(self.alarms):
            if number:
                text.append('\n')
            for index, line in enumerate(lines):
                if index:
                    text.append('\n')
                prefix = f'{icon("warn")} ' if index == 0 else '  '
                text.append(prefix + line, style=f'bold {TONE[probes.FAIL]}' if index == 0 else TONE[probes.FAIL])
        alarm.update(text)

    def _draw_checks(self) -> None:
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

    def _draw_plan(self) -> None:
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

    def _draw_ask(self) -> None:
        card = self.query_one('#kal-ask', CardBox)
        spec = self.pending
        card.display = spec is not None
        if spec is None:
            return
        width = self._width(card)
        danger = spec['danger']
        glyph = 'key' if spec['entry'] == 'password' else ('warn' if danger else 'help')
        title = spec['title']
        card.query_one('#kal-ask-head', Static).update(
            header('key' if glyph == 'key' else 'check', title, badge(probes.WARN if danger else 'busy',
                                                                      'Bestätigung nötig' if danger else 'Eingabe'),
                   width))
        lines = []
        if spec.get('head'):
            lines.append(Text(spec['head'], style=SOFT))
        if spec['lines'] and (self.plan is None or spec['entry'] == 'password'):
            lines += [Text(line, style=SOFT) for line in spec['lines']]
        if spec['expected']:
            lines.append(Text(f'Zum Übernehmen „{spec["expected"]}“ eintippen und Enter drücken.', style=SOFT))
        elif not spec['entry']:
            lines.append(Text('Bis zur Bestätigung ist nichts geändert.', style=SOFT))
        card.query_one('#kal-ask-text', Static).update(Group(*lines) if lines else Text(''))
        card.query_one('#kal-input', Input).display = bool(spec['entry'])
        error = card.query_one('#kal-ask-error', Static)
        error.display = bool(spec['error'])
        error.update(Text(f'{icon("fail")} {spec["error"]}', style=TONE[probes.FAIL]))

    def _spinner(self) -> str:
        if ascii_mode() or self.app.animation_level == 'none':
            return icon('busy')
        return SPINNER[self._tick % len(SPINNER)]

    def _draw_steps(self) -> None:
        card = self.query_one('#kal-steps', SectionCard)
        show = bool(self.steps) and self.phase in ('running', 'done')
        card.display = show
        self._drawn_progress = self.progress
        if not show:
            return
        width = self._width(card)
        table = Table.grid(padding=(0, 1))
        table.add_column(no_wrap=True, width=1)
        table.add_column(ratio=1, overflow='fold')
        table.add_column(no_wrap=True, justify='right')
        tones = {WAITING: MUTED, RUNNING: f'bold {P.accent_strong}', DONE: TONE[probes.OK],
                 FAILED: TONE[probes.FAIL], SKIPPED: MUTED, ABORTED: TONE[probes.WARN]}
        for step in self.steps:
            mark = {WAITING: icon('off'), RUNNING: self._spinner(), DONE: icon('ok'), FAILED: icon('fail'),
                    SKIPPED: '-' if ascii_mode() else '–', ABORTED: icon('warn')}[step.state]
            tone = tones[step.state]
            table.add_row(Text(mark, style=tone), Text(step.label, style=tone if step.state != DONE else SOFT),
                          Text(step.state, style=tone))
        parts: list = [table]
        if self.progress is not None:
            elapsed, total = self.progress
            room = max(10, min(40, width - 28))
            line = Text('Aufnahme ', style=MUTED)
            line.append_text(bar(elapsed / total if total else 1.0, room))
            line.append(f' {elapsed:4.0f} / {total:.0f} s', style=SOFT)
            parts += [Text(''), line]
        running = next((s for s in self.steps if s.state == RUNNING), None)
        if running is not None and running.key == 'auswertung':
            line = Text('Auswertung ', style=MUTED)
            line.append_text(self._indeterminate(max(10, min(40, width - 36))))
            line.append(' ')
            line.append_text(badge(probes.WARN, 'nicht abbrechbar'))
            parts += [Text(''), line]
        hint = None
        if self.cancel_requested and not self.finished:
            hint = help_line('Abbruch angefordert: die Auswertung läuft zu Ende, danach wird nichts übernommen.'
                             if self.analysis_cancel else
                             'Abbruch angefordert: wirkt an der nächsten Schrittgrenze, danach wird aufgeräumt.')
        done = sum(s.state in (DONE, SKIPPED) for s in self.steps)
        right = badge('busy', f'{done} / {len(self.steps)}', 'busy') if not self.finished else \
            badge(probes.OFF, f'{done} / {len(self.steps)}')
        card.show(header('run', 'Ablauf', right, width), Group(*parts), hint)

    def _indeterminate(self, width: int) -> Text:
        fill, empty = ('#', '.') if ascii_mode() else ('█', '░')
        block = 5
        text = Text()
        if self.app.animation_level == 'none':
            text.append(empty * width, P.line)
            return text
        span = width - block
        position = self._tick % (2 * span)
        position = position if position <= span else 2 * span - position
        text.append(empty * position, P.line)
        text.append(fill * block, P.accent_strong)
        text.append(empty * (span - position), P.line)
        return text

    def _draw_result(self) -> None:
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

    def _draw_hint(self) -> None:
        hint = self.query_one('#kal-hint', Static)
        if self.finished:
            text = help_line('Esc oder Enter schließt. Der Befund der Konsole wird neu geladen.')
        elif self.pending is not None:
            text = help_line('Enter bestätigt, Esc bricht ab (nichts wird geändert).')
        elif self.cancel_requested:
            text = help_line('Die Konsole schließt erst, wenn die Rückstellung und der Dienststart durch sind.')
        elif self.phase == 'running':
            text = help_line('Esc fordert den Abbruch an; die Konsole bleibt offen, bis aufgeräumt ist.')
        else:
            text = help_line('Vorprüfung läuft. Esc bricht ab.')
        hint.update(text)

    def _draw_buttons(self) -> None:
        cancel = self.query_one('#kal-cancel', Button)
        ok = self.query_one('#kal-ok', Button)
        spec = self.pending
        ok.display = spec is not None
        if spec is not None:
            ok.label = spec['ok_label']
            ok.variant = 'error' if spec['danger'] else 'primary'
        if self.finished:
            cancel.label, cancel.disabled, cancel.variant = 'Schließen', False, 'primary'
        elif spec is not None:
            cancel.label, cancel.disabled, cancel.variant = 'Abbrechen', False, 'default'
        elif self.phase == 'running':
            cancel.label = 'Abbruch angefordert' if self.cancel_requested else 'Abbruch anfordern'
            cancel.disabled, cancel.variant = self.cancel_requested, 'default'
        else:
            cancel.label, cancel.disabled, cancel.variant = 'Abbrechen', False, 'default'


def _plan_note(title: str) -> str:
    """„Plan (Werkbank etwa 5 min nicht erreichbar)“ → Klammerinhalt als Nebentext."""
    found = re.search(r'\((.*)\)', title)
    return found.group(1) if found else ''


_LEVEL_ICON = {probes.OK: 'ok', probes.WARN: 'warn', probes.FAIL: 'fail', probes.OFF: 'off',
               probes.UNKNOWN: 'unknown'}
