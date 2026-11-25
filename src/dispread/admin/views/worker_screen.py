"""Gemeinsame Grundlage der Konsolen-Bildschirme mit Worker-Thread (Kalibrieren, Update, UART-Ports, Zertifikat).

Ein ``WorkerScreen`` zeigt Karten (Vorprüfung, Plan, Rückfrage, Ergebnis, Schrittliste) über einem
Protokollfeld. Die Arbeit läuft in einem Worker-Thread (``run_job``); jede Änderung der Oberfläche geht
über ``thread_call`` (``app.call_from_thread``). Rückfragen blockieren den Worker (``ask``) und erscheinen
als Karte im Bildschirm, auch das sudo-Passwort (maskiertes Feld, nur an die Prüffunktion gereicht,
nirgends protokolliert oder behalten). Abbruch ist kooperativ (``cancel_event``).

Unterklassen setzen ``TITLE_ICON``, ``OK_LABEL``, ``GROUP`` und überschreiben ``run_job``,
``collect_result``, ``result_badge``, ``finish_steps``, ``cancel_confirmation``, ``draw_result`` und die
Hinweiszeilen. Die Kennungen der Widgets (``#kal-…``) stammen aus dem ersten Bildschirm dieser Art und
bleiben aus Gründen der Kompatibilität gleich.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
from dataclasses import dataclass

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from .. import probes
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
    header,
    help_line,
    icon,
)

WAITING, RUNNING, DONE, FAILED, SKIPPED, ABORTED = ('wartet', 'läuft', 'fertig', 'fehlgeschlagen',
                                                     'übersprungen', 'abgebrochen')
log = logging.getLogger(__name__)
POLL_S = 0.15
SUDO_ATTEMPTS = 3
_LEVEL_ICON = {probes.OK: 'ok', probes.WARN: 'warn', probes.FAIL: 'fail', probes.OFF: 'off',
               probes.UNKNOWN: 'unknown'}


def reason_block(reason: str, label: str = 'Grund') -> Text:
    """Längerer Grund oder längere Meldung: umbrechend unter den Wertfeldern (``fields`` kürzt Sätze)."""
    text = Text('\n')
    text.append(f'{label}: ', style=MUTED)
    text.append(reason.replace('\n', ' · '), style=SOFT)
    return text


@dataclass
class Step:
    key: str
    label: str
    state: str = WAITING


class LogWriter:
    """Dateiähnlich (write/flush): komplette Zeilen gehen in das Protokollfeld."""

    def __init__(self, screen: WorkerScreen, err: bool):
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


class ProgressHook:
    """Fortschrittsmelder: nur Zustand merken; ein Zeitgeber der Oberfläche zeichnet."""

    def __init__(self, screen: WorkerScreen):
        self.screen = screen

    def __call__(self, elapsed: float, total: float) -> None:
        self.screen.progress = (float(elapsed), float(total))

    def finish(self) -> None:
        pass


class ScreenHooks:
    """Console-Hooks (``line``, ``mark``, ``step``, ``progress``, ``loud``), alle im Worker-Thread.

    Als Mischklasse vor ``calibrate.Console`` verwendbar oder allein als Konsole für ``update.run_update``.
    """

    def __init__(self, screen: WorkerScreen):
        self.screen = screen
        self.out, self.err = LogWriter(screen, False), LogWriter(screen, True)
        self.last_result = None

    def line(self, text: str = '', stream=None) -> None:
        if text.strip():
            self.screen.thread_call(self.screen.log_line, text, stream is self.err)

    def mark(self, level: str, text: str, stream=None) -> None:
        self.screen.thread_call(self.screen.log_mark, level, text)

    def step(self, text: str, *, key=None) -> None:
        self.screen.thread_call(self.screen.on_step, key, text)

    def progress(self, tty: bool):
        return ProgressHook(self.screen)

    def loud(self, lines: list[str]) -> None:
        self.screen.thread_call(self.screen.on_loud, list(lines))

    def confirm(self, title: str, lines: list[str], expected: str | None, *, deps=None) -> bool:
        screen = self.screen
        try:
            answer = screen.ask(title=title, lines=lines, expected=expected)
            accepted = answer == expected if expected is not None else answer is True
            if accepted and expected is None and not screen.obtain_sudo():
                accepted = False
        except Exception:  # noqa: BLE001 - gescheiterte Rückfrage = nicht bestätigt (sicherer Ausgang)
            log.exception('Rückfrage %r gescheitert, gilt als nicht bestätigt', title)
            screen.thread_call(screen.log_line, 'Rückfrage gescheitert, nicht bestätigt.', True)
            return False
        if accepted:
            screen.thread_call(screen.set_phase, 'running')
        return accepted


class WorkerScreen(ModalScreen[None]):
    """Grundlage: Aufbau, Worker, Rückfragen, Schrittliste, Protokoll, Abbruch."""

    TITLE_ICON = 'clock'
    OK_LABEL = 'Ja'
    ASK_DANGER = True       # Rückfragen mit rotem Knopf; Aktionen ohne Datenverlust setzen False
    GROUP = 'worker'
    PROGRESS_LABEL = 'Fortschritt'
    #: True: der erste Schritt schaltet auf „läuft“ (Plan/Rückfrage kamen vorher); False: erst die Bestätigung tut es
    STEP_STARTS_RUN = True
    BINDINGS = [Binding('escape,q', 'back', show=False), Binding('left,right', 'switch', show=False),
                Binding('up', 'scroll_top(-1)', show=False), Binding('down', 'scroll_top(1)', show=False),
                Binding('pageup', 'scroll_top(-5)', show=False), Binding('pagedown', 'scroll_top(5)', show=False)]
    DEFAULT_CSS = '''
    WorkerScreen { background: $picam-canvas; }
    #kal { height: 1fr; width: 1fr; max-width: 120; padding: 0 2; }
    #kal-title { height: 1; margin: 1 0 0 0; }
    #kal-alarm { display: none; height: auto; max-height: 9; margin: 1 0 0 0; padding: 0 1;
                 background: $picam-tint-fail; border-left: wide $error; }
    #kal-top { height: auto; max-height: 60%; scrollbar-size-vertical: 1; }
    WorkerScreen.-asking #kal-log { display: none; }
    WorkerScreen.-asking #kal-top { height: 1fr; max-height: 100%; }
    #kal-ask Static { height: auto; width: 1fr; }
    #kal-input { height: 1; border: none; padding: 0 1; margin: 1 0 0 0; background: $picam-field; }
    #kal-input:focus { background: $picam-field-focus; }
    #kal-log { height: 1fr; min-height: 3; margin: 1 0 0 0; padding: 0 1; background: $picam-surface;
               border: none; scrollbar-size-vertical: 1; overflow-x: hidden; }
    #kal-hint { height: 1; margin: 1 0 0 0; }
    #kal-buttons { height: 1; margin: 1 0 0 0; }
    #kal-buttons Button { margin: 0 2 0 0; }
    '''

    def __init__(self, instance, title_text: str):
        super().__init__()
        self.instance = instance
        self.title_text = title_text
        # Zustand (nur im UI-Thread verändert; ``progress`` schreibt der Worker, die Anzeige liest)
        self.phase = 'prep'          # prep | confirm | running | done
        self.pre = None
        self.plan: tuple[str, list[str]] | None = None
        self.steps: list[Step] = []
        self.progress: tuple[float, float] | None = None
        self.alarms: list[list[str]] = []
        self.result = None
        self.pending: dict | None = None      # offene Rückfrage {future, title, lines, ok_label, ...}
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
        self.worker = self.run_worker(self._thread_main, thread=True, group=self.GROUP, exit_on_error=False)

    # ------------------------------------------------------------ Worker-Thread
    def make_console(self):
        return ScreenHooks(self)

    def run_job(self, console) -> None:
        raise NotImplementedError

    def collect_result(self, console, failure: str | None):
        raise NotImplementedError

    def _thread_main(self) -> None:
        console = self.make_console()
        failure: str | None = None
        try:
            self.run_job(console)
        except Exception as error:  # noqa: BLE001 - nie ohne Ergebnis enden
            failure = f'{type(error).__name__}: {error}'
            console.mark(probes.FAIL, failure)
        finally:
            for writer in (console.out, console.err):
                tail = writer._buffer.strip()
                if tail:
                    self.thread_call(self.log_line, tail, writer.err)
        self.thread_call(self.on_finished, self.collect_result(console, failure))

    def ask(self, *, title: str, lines: list[str], expected: str | None = None, ok_label: str | None = None,
            entry: str | None = None, danger: bool | None = None, error: str = '', head: str = '') -> object:
        """Rückfrage im Bildschirm; blockiert den Worker. ``True``/Text, ``None`` bei Abbruch."""
        future: concurrent.futures.Future = concurrent.futures.Future()
        if expected is not None:
            entry, ok_label = 'text', ok_label or 'Übernehmen'
        else:
            ok_label = ok_label or self.OK_LABEL
        spec = dict(future=future, title=title, lines=lines, expected=expected, ok_label=ok_label,
                    entry=entry, danger=self.ASK_DANGER if danger is None else danger, error=error, head=head)
        if not self.thread_call(self.open_ask, spec):
            return None
        while not self.gone.is_set():
            try:
                return future.result(timeout=0.2)
            except concurrent.futures.TimeoutError:
                continue
        return None

    def ask_password(self, validate, *, head: str, attempts: int = SUDO_ATTEMPTS) -> bool:
        """sudo-Passwort per maskiertem Feld holen; ``validate(passwort) -> (ok, meldung)``."""
        import getpass

        account = getpass.getuser()
        error = ''
        for _ in range(attempts):
            password = self.ask(
                title='sudo-Passwort', ok_label='Weiter', entry='password', danger=False, error=error, head=head,
                lines=[f'Passwort des Linux-Kontos „{account}“ (das Konto, mit dem picam läuft; nicht das '
                       'Login der Werkbank). Es wird nur an sudo übergeben und nirgends gespeichert.'])
            if password is None:
                self.thread_call(self.log_line, 'sudo-Anmeldung abgebrochen, nichts geändert.', True)
                return False
            ok, message = validate(str(password))
            del password
            if ok:
                return True
            error = message or 'sudo-Anmeldung fehlgeschlagen.'
        self.thread_call(self.log_line, f'sudo: {error} Nach {attempts} Versuchen abgebrochen.', True)
        return False

    def obtain_sudo(self) -> bool:
        return True

    # ------------------------------------------------------------ Hooks der Unterklassen
    def result_badge(self, result) -> tuple[str, str]:
        raise NotImplementedError

    def finish_steps(self, result) -> None:
        """Zustand der Schritte nach dem Ende (laufende, wartende) festlegen."""

    def after_finished(self, result) -> None:
        """Meldung an die App, Neuladen des Befunds."""

    def draw_result(self) -> None:
        """Ergebniskarte zeichnen."""

    def draw_checks(self) -> None:
        card = self.query_one('#kal-checks', SectionCard)
        card.display = False

    def draw_plan(self) -> None:
        card = self.query_one('#kal-plan', SectionCard)
        card.display = False

    def step_extras(self, width: int, running) -> list:
        return []

    def cancel_confirmation(self) -> Confirmation:
        return Confirmation('Vorgang abbrechen?', ['Der Abbruch wirkt an der nächsten Schrittgrenze.'], [],
                            'Abbruch anfordern', danger=True)

    def hint_text(self) -> str:
        if self.finished:
            return 'Esc oder Enter schließt.'
        if self.pending is not None:
            return 'Enter bestätigt, Esc bricht ab (nichts wird geändert).'
        if self.cancel_requested:
            return 'Der Abbruch wirkt an der nächsten Schrittgrenze.'
        if self.phase == 'running':
            return 'Esc fordert den Abbruch an.'
        return 'Vorprüfung läuft. Esc bricht ab.'

    def running_phase_label(self) -> str:
        return 'läuft'

    def on_finished(self, result) -> None:
        self.result = result
        self.pending = None
        self.finish_steps(result)
        self.phase, self.finished = 'done', True
        self.update_view()
        self.after_finished(result)
        self.call_after_refresh(self.update_view)   # Karten messen ihre Breite erst nach dem ersten Layout
        self.query_one('#kal-cancel', Button).focus()
        self.call_after_refresh(self.query_one('#kal-top', VerticalScroll).scroll_home, animate=False)

    # ------------------------------------------------------------ Abbruch
    def action_back(self) -> None:
        if self.pending is not None:
            self._resolve(None)
        elif self.finished:
            self.dismiss(None)
        elif self.phase == 'running':
            if not self.cancel_requested:
                self.app.push_screen(ConfirmScreen(self.cancel_confirmation()), callback=self._cancel_confirmed)
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

    # ------------------------------------------------------------ Anzeige
    def update_view(self) -> None:
        if not self.is_mounted:
            return
        self.set_class(self.phase in ('prep', 'confirm') and not self.finished, '-asking')
        self.set_class(self.finished, '-done')
        self._draw_title()
        self._draw_alarm()
        self.draw_checks()
        self.draw_plan()
        self._draw_ask()
        self._draw_steps()
        self.draw_result()
        self._draw_hint()
        self._draw_buttons()

    def _phase_badge(self) -> Text:
        if self.result is not None:
            level, word = self.result_badge(self.result)
            return badge(level, word)
        if self.cancel_requested:
            return badge(probes.WARN, 'Abbruch angefordert')
        return {'prep': badge('busy', 'prüft', 'busy'), 'confirm': badge(probes.WARN, 'wartet auf Sie'),
                'running': badge('busy', self.running_phase_label(), 'busy')}.get(self.phase,
                                                                                  badge(probes.OFF, '–'))

    def _draw_title(self) -> None:
        title = self.query_one('#kal-title', Static)
        title.update(header(self.TITLE_ICON, self.title_text, self._phase_badge(), self._width(title)))

    def _draw_hint(self) -> None:
        self.query_one('#kal-hint', Static).update(help_line(self.hint_text()))

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
            line = Text(f'{self.PROGRESS_LABEL} ', style=MUTED)
            line.append_text(bar(elapsed / total if total else 1.0, room))
            line.append(self.progress_text(elapsed, total), style=SOFT)
            parts += [Text(''), line]
        running = next((s for s in self.steps if s.state == RUNNING), None)
        parts += self.step_extras(width, running)
        hint = None
        if self.cancel_requested and not self.finished:
            hint = help_line(self.cancel_hint())
        done = sum(s.state in (DONE, SKIPPED) for s in self.steps)
        right = badge('busy', f'{done} / {len(self.steps)}', 'busy') if not self.finished else \
            badge(probes.OFF, f'{done} / {len(self.steps)}')
        card.show(header('run', 'Ablauf', right, width), Group(*parts), hint)

    def progress_text(self, elapsed: float, total: float) -> str:
        return f' {elapsed:4.0f} / {total:.0f} s'

    def cancel_hint(self) -> str:
        return 'Abbruch angefordert: wirkt an der nächsten Schrittgrenze, danach wird aufgeräumt.'


    def on_unmount(self) -> None:
        self.gone.set()
        self.cancel_event.set()

    def thread_call(self, fn, *args) -> bool:
        """Aus dem Worker in die Oberfläche. ``False``, wenn der Aufruf nicht ausgeführt wurde.

        Schließt die App gerade, scheitert der Aufruf still. Wirft der Hook selbst, wird das nicht
        verschluckt: Eintrag im Log und eine Fehlerzeile im Protokollfeld; der Worker läuft weiter,
        der Aufrufer sieht ``False`` (Rückfragen gelten dann als nicht bestätigt)."""
        if self.gone.is_set():
            return False
        try:
            self.app.call_from_thread(fn, *args)
            return True
        except Exception as exc:  # noqa: BLE001 - Anzeigefehler dürfen den Worker nicht beenden
            if self.gone.is_set():
                return False
            name = getattr(fn, '__name__', repr(fn))
            log.exception('UI-Hook %s im Worker gescheitert', name)
            try:
                self.app.call_from_thread(
                    self.log_line, f'Anzeigefehler ({name}): {type(exc).__name__}: {exc}', True)
            except Exception:  # noqa: BLE001 - die Fehlerzeile selbst darf nicht erneut werfen
                log.exception('Fehlerzeile konnte nicht angezeigt werden')
            return False

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

    def on_loud(self, lines: list[str]) -> None:
        text = [line for line in lines if line.strip('! ')]
        self.alarms.append(text)
        for line in text:
            self._log(Text(f'{icon("warn")} {line}', style=f'bold {TONE[probes.FAIL]}'))
        self.update_view()

    def on_step(self, key: str | None, text: str) -> None:
        if self.STEP_STARTS_RUN and self.phase in ('prep', 'confirm'):
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

    def quit_guard(self) -> bool:
        """Von der App bei Ctrl+C aufgerufen: während des Laufs nicht beenden, sondern Abbruch anfordern."""
        if self.finished or self.gone.is_set():
            return False
        self.action_back()
        return True

    def _on_tick(self) -> None:
        animated = self.app.animation_level != 'none'
        if animated:
            self._tick += 1
        busy = any(s.state == RUNNING for s in self.steps)
        if self.progress != self._drawn_progress or (animated and busy):
            self._draw_steps()

    def on_resize(self, event) -> None:
        self.update_view()

    def _width(self, widget) -> int:
        width = widget.content_size.width or widget.size.width
        return width if width > 0 else max(40, self.size.width - 4)

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
