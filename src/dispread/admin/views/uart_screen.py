"""UART-Ports ändern in der Konsole (wie die Kalibrierung ein eigener Bildschirm).

1. ``UartPortsScreen``: Stiftleiste mit Pinwahl (Pfeiltasten oder Maus). Für den gewählten Pin öffnet sich ein
   Dropdown mit den **wählbaren** UART-Funktionen (``uart_ports.choices``: aktiv, braucht config.txt und Neustart);
   nicht wählbare Funktionen stehen mit ihrem Grund daneben. Getrennt davon die Referenz (USB-RS232-Adapter,
   ``reference_choices``) als Dropdown mit den stabilen by-id-Namen. „Prüfen“ erstellt den Plan
   (``plan_change``).
2. ``UartApplyScreen``: Prüfseite (Warnungen, Diff für config.txt und Konfiguration, was neu startet), ausdrückliche
   Bestätigung, sudo-Passwort (maskiert, nie protokolliert), ``apply_change`` im Worker, Ergebnis. Ein nötiger
   Pi-Neustart wird nur als Befehl gezeigt und **nie** von picam ausgeführt.

Pegelhinweis bleibt sichtbar: Pi-Pegel sind 3,3 V, nie direkt mit RS-232 verbinden.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group
from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Select, Static

from .. import probes, uart_ports
from ..ui import ACCENT, MUTED, SOFT, TONE, Confirmation, fade_in
from ..widgets import CardBox, SectionCard, badge, fields, header, help_line, value
from .uart import PIN_NAMES, header_graphic, output_function, used_pins
from .worker_screen import DONE, FAILED, RUNNING, SKIPPED, WAITING, Step, WorkerScreen, reason_block

LEVEL_NOTE = 'Pi-Pegel sind 3,3 V: nie direkt an RS-232 anschließen (Pegelwandler nötig, OQ-09).'
STATUS_WORDS = {'active': 'aktiv', 'reboot_required': 'braucht config.txt + Pi-Neustart'}
REBOOT_COMMAND = 'sudo systemctl reboot'
MAX_DIFF_LINES = 40


def diff_text(diff: str, limit: int = MAX_DIFF_LINES) -> Text:
    """Unified Diff farbig (+ grün, - rot, @@ gedämpft), gekürzt auf ``limit`` Zeilen."""
    text = Text()
    lines = diff.splitlines()
    for number, line in enumerate(lines[:limit]):
        if number:
            text.append('\n')
        if line.startswith('+') and not line.startswith('+++'):
            style = TONE[probes.OK]
        elif line.startswith('-') and not line.startswith('---'):
            style = TONE[probes.FAIL]
        else:
            style = MUTED
        text.append(line, style=style)
    if len(lines) > limit:
        text.append(f'\n… {len(lines) - limit} weitere Zeilen', style=MUTED)
    return text


def device_name(by_id: str) -> str:
    return by_id.rsplit('/', 1)[-1]


class PinChanged(Message):
    def __init__(self, header_widget: Static, pin: int) -> None:
        super().__init__()
        self.header_widget = header_widget
        self.pin = pin


class PinHeader(Static, can_focus=True):
    """Stiftleiste als Auswahl: ↑/↓ Pinpaar, ←/→ Spalte, Klick wählt, Enter übernimmt."""

    BINDINGS = [Binding('up', 'move(-1, 0)', show=False), Binding('down', 'move(1, 0)', show=False),
                Binding('left', 'move(0, -1)', show=False), Binding('right', 'move(0, 1)', show=False),
                Binding('home', 'jump(1)', show=False), Binding('end', 'jump(40)', show=False)]
    DEFAULT_CSS = 'PinHeader { width: auto; height: auto; }'
    LEFT_COLUMN_END = 18   # Zeichen: Name, Nummer und linker Punkt gehören zum ungeraden Pin

    def __init__(self, pin: int, choices=frozenset(), **kwargs):
        super().__init__(**kwargs)
        self.pin = pin
        self.pin_choices = frozenset(choices)
        self.used = (None, None, None, None)

    def render_graphic(self) -> None:
        full, unused_full, short, unused_short = self.used
        self.update(header_graphic(20, used_full=full, unused_full=unused_full, used_short=short,
                                   unused_short=unused_short, selected=self.pin, choices=self.pin_choices))

    def set_pin(self, pin: int, *, notify: bool = True) -> None:
        pin = max(1, min(40, pin))
        if pin != self.pin:
            self.pin = pin
            self.render_graphic()
            self.scroll_to_pin()
        if notify:
            self.post_message(PinChanged(self, self.pin))

    def scroll_to_pin(self) -> None:
        body = self.parent_scroll()
        if body is None or not self.is_mounted:
            return
        line = (self.pin + 1) // 2           # 0 = Rahmen, 1..20 = Pinpaare
        y = self.region.y - body.region.y + body.scroll_y + line
        if y < body.scroll_y + 1:
            body.scroll_to(y=max(0, y - 2), animate=False)
        elif y >= body.scroll_y + body.size.height - 1:
            body.scroll_to(y=y - body.size.height + 3, animate=False)

    def parent_scroll(self):
        for node in self.ancestors:
            if isinstance(node, VerticalScroll):
                return node
        return None

    def action_move(self, rows: int, columns: int) -> None:
        row, column = (self.pin + 1) // 2, 0 if self.pin % 2 else 1
        if rows and not 1 <= row + rows <= 20:      # am Rand: Fokus weiter (Dropdown darunter / Tastenleiste)
            (self.screen.focus_next if rows > 0 else self.screen.focus_previous)()
            return
        row += rows
        column = min(1, max(0, column + columns))
        self.set_pin(2 * row - 1 + column)

    def action_jump(self, pin: int) -> None:
        self.set_pin(pin)

    def on_click(self, event) -> None:
        line = event.y
        if not 1 <= line <= 20:
            return
        self.focus()
        self.set_pin(2 * line - 1 + (0 if event.x < self.LEFT_COLUMN_END else 1))


class UartPortsScreen(ModalScreen[None]):
    BINDINGS = [Binding('escape,q', 'cancel', show=False)]
    DEFAULT_CSS = '''
    UartPortsScreen { background: $picam-canvas; }
    #up { height: 1fr; width: 1fr; max-width: 120; padding: 0 2; }
    #up-title { height: 1; margin: 1 0 0 0; }
    #up-body { height: 1fr; scrollbar-size-vertical: 1; }
    #up-row { height: auto; }
    #up-pins-card { width: auto; height: auto; }
    #up-pins-scroll { width: auto; height: 10; scrollbar-size-vertical: 1; }
    #up-side { width: 1fr; height: auto; }
    #up-row.side #up-side { padding: 0 0 0 2; }
    #up-body Select { margin: 1 0 0 0; }
    #up-body .detail { height: auto; width: 1fr; }
    #up-error { height: auto; margin: 1 0 0 0; padding: 0 1; display: none; background: $picam-tint-fail;
                border-left: wide $error; }
    #up-hint { height: 1; margin: 1 0 0 0; }
    #up-buttons { height: 1; margin: 1 0 0 0; }
    #up-buttons Button { margin: 0 2 0 0; }
    '''

    def __init__(self, instance, ports=None, apply=None, sudo=None):
        super().__init__()
        self.instance = instance
        self.ports = ports or uart_ports.UartPorts(instance)
        self.apply = apply
        self.sudo = sudo
        self.function = output_function(instance.output_port)
        self.output: str | None = None              # gewählte UART-Funktion (None: unverändert)
        self.reference: str | None = None           # gewählter Referenzpfad (None: unverändert)
        self.current_choices: tuple = ()
        self.reference_options: tuple = ()
        self.error = ''
        self._syncing = False

    def compose(self):
        start = self.function.tx_pin if self.function else 8
        with Vertical(id='up'):
            yield Static(id='up-title')
            with VerticalScroll(id='up-body'):
                with Horizontal(id='up-row'):
                    with CardBox(id='up-pins-card'):
                        yield Static(id='up-pins-head')
                        with VerticalScroll(id='up-pins-scroll'):
                            yield PinHeader(start, id='up-pins')
                    with Vertical(id='up-side'):
                        with CardBox(id='up-out'):
                            yield Static(id='up-out-head', classes='detail')
                            yield Select([], id='up-out-select', allow_blank=True, prompt='Ausgang wählen …')
                            yield Static(id='up-out-info', classes='detail')
                        with CardBox(id='up-ref'):
                            yield Static(id='up-ref-head', classes='detail')
                            yield Select([], id='up-ref-select', allow_blank=True, prompt='Referenzadapter wählen …')
                            yield Static(id='up-ref-info', classes='detail')
                yield SectionCard(id='up-sum')
            yield Static(id='up-error')
            yield Static(id='up-hint')
            with Horizontal(id='up-buttons'):
                yield Button('Abbrechen', id='up-cancel')
                yield Button('Prüfen und weiter', id='up-next', variant='primary')

    def on_mount(self) -> None:
        fade_in(self.query_one('#up'))
        pins = self.query_one('#up-pins', PinHeader)
        pins.used = used_pins(self.function)
        self.load_reference()
        self.load_pin(pins.pin)
        pins.pin_choices = frozenset(p for f in uart_ports.UARTS for p in (f.tx_pin,))
        pins.render_graphic()
        self.update_view()
        pins.focus()

    def on_resize(self, event) -> None:
        self.update_view()

    # ------------------------------------------------------------ Daten
    def load_pin(self, pin: int) -> None:
        try:
            self.current_choices = tuple(self.ports.choices(pin))
        except (OSError, ValueError) as error:
            self.current_choices = ()
            self.set_error(str(error))
        select = self.query_one('#up-out-select', Select)
        options = [(self.choice_label(c), c.function.uart) for c in self.current_choices if c.selectable]
        self._syncing = True
        select.set_options(options)
        wanted = self.output or (self.function.uart if self.function and any(
            c.function.uart == self.function.uart and c.selectable for c in self.current_choices) else None)
        if wanted and any(wanted == o[1] for o in options):
            select.value = wanted
        self._syncing = False

    @staticmethod
    def choice_label(choice) -> str:
        function = choice.function
        gpio = function.tx_gpio if choice.signal == 'TX' else function.rx_gpio
        where = f'{choice.signal} Pin {choice.pin}, GPIO{gpio}'
        status = STATUS_WORDS.get(choice.status, choice.status)
        if choice.status == 'active' and choice.device:
            status = f'aktiv, {choice.device.path}'
        return f'{function.uart.upper()} · {where} · {status}'

    def load_reference(self) -> None:
        try:
            self.reference_options = tuple(self.ports.reference_choices())
        except (OSError, ValueError) as error:
            self.reference_options = ()
            self.set_error(str(error))
        select = self.query_one('#up-ref-select', Select)
        options = [(device_name(c.value), c.value) for c in self.reference_options if c.selectable]
        self._syncing = True
        select.set_options(options)
        current = self.instance.reference_port
        match = next((c.value for c in self.reference_options if c.selectable and current in (
            c.value, c.device.path, *c.device.by_id)), None)
        if match:
            select.value = match
        self._syncing = False

    def set_error(self, text: str) -> None:
        self.error = text
        error = self.query_one('#up-error', Static)
        error.display = bool(text)
        error.update(Text(text, style=TONE[probes.FAIL]))

    # ------------------------------------------------------------ Ereignisse
    @on(PinChanged)
    def _pin_changed(self, event) -> None:
        self.set_error('')
        self.load_pin(event.pin)
        self.update_view()

    @on(Select.Changed, '#up-out-select')
    def _output_changed(self, event: Select.Changed) -> None:
        if self._syncing:
            return
        self.output = None if event.value is Select.BLANK else str(event.value)
        self.set_error('')
        self.update_view()

    @on(Select.Changed, '#up-ref-select')
    def _reference_changed(self, event: Select.Changed) -> None:
        if self._syncing:
            return
        chosen = None if event.value is Select.BLANK else str(event.value)
        current = next((c.value for c in self.reference_options if self.instance.reference_port in (
            c.value, c.device.path, *c.device.by_id)), None)
        self.reference = chosen if chosen != current else None
        self.set_error('')
        self.update_view()

    def changed(self) -> bool:
        output = self.output is not None and self.output != (self.function.uart if self.function else None)
        return output or self.reference is not None

    @on(Button.Pressed, '#up-cancel')
    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, '#up-next')
    def _next(self) -> None:
        if not self.changed():
            return
        try:
            plan = self.ports.plan_change(output=self.output if self.output != (
                self.function.uart if self.function else None) else None, reference=self.reference)
        except (OSError, ValueError) as error:
            self.set_error(str(error))
            return
        self.set_error('')
        self.app.push_screen(UartApplyScreen(self.instance, plan, apply=self.apply, sudo=self.sudo),
                             callback=self._applied)

    def _applied(self, _result) -> None:
        self.dismiss(None)

    # ------------------------------------------------------------ Anzeige
    def _width(self, widget) -> int:
        width = widget.content_size.width or widget.size.width
        return width if width > 0 else max(40, self.size.width - 6)

    def update_view(self) -> None:
        if not self.is_mounted:
            return
        row = self.query_one('#up-row', Horizontal)
        side = self.size.width >= 116
        row.styles.layout = 'horizontal' if side else 'vertical'
        row.set_class(side, 'side')
        self.query_one('#up-pins-card').styles.width = 'auto' if side else '1fr'
        free = self.size.height - (12 if side else 24)
        self.query_one('#up-pins-scroll').styles.height = max(6, min(22, free + 6 if side else free + 10))
        title = self.query_one('#up-title', Static)
        title.update(header('uart', 'UART-Ports ändern', badge(probes.WARN, 'noch nichts geändert'),
                            self._width(title)))
        pins = self.query_one('#up-pins', PinHeader)
        pin = pins.pin
        graphic_w = 58
        self.query_one('#up-pins-head', Static).update(
            header('pins', 'Stiftleiste', None, graphic_w if side else self._width(self.query_one('#up-pins-card'))))
        card_w = self._width(self.query_one('#up-out'))
        self.query_one('#up-out-head', Static).update(
            header('output', f'Ausgang · Pin {pin}', None, card_w, note=PIN_NAMES[pin]))
        select = self.query_one('#up-out-select', Select)
        lines: list = []
        if not self.current_choices:
            select.display = False
            lines.append(Text('Dieser Pin hat keine UART-Funktion; Ausgang ist ein TX-Pin (z. B. Pin 8).',
                              style=SOFT))
        else:
            select.display = any(c.selectable for c in self.current_choices)
            for choice in self.current_choices:
                for warning in choice.warnings:
                    lines.append(Text(f'▲ {warning}', style=TONE[probes.WARN]))
                if not choice.selectable:
                    lines.append(Text(f'{choice.function.uart.upper()} ({choice.signal} Pin {choice.pin}): '
                                      f'nicht wählbar – {choice.reason}', style=MUTED))
            if pin == 8 or any(c.signal == 'TX' for c in self.current_choices):
                lines.append(Text('Masse: Pin 6 (GND)', style=MUTED))
        self.query_one('#up-out-info', Static).update(Group(*lines) if lines else Text(''))
        self.query_one('#up-ref-head', Static).update(
            header('connect', 'Referenz (USB-RS232)', None, card_w, note='Messverstärker'))
        info = []
        if not self.reference_options:
            info.append(Text('Kein USB-RS232-Adapter gefunden.', style=SOFT))
        for choice in self.reference_options:
            if not choice.selectable:
                info.append(Text(f'{device_name(choice.value)}: nicht wählbar – {choice.reason}', style=MUTED))
        self.query_one('#up-ref-select', Select).display = any(c.selectable for c in self.reference_options)
        self.query_one('#up-ref-info', Static).update(Group(*info) if info else Text(''))
        summary = self.query_one('#up-sum', SectionCard)
        width = self._width(summary)
        old_out = self.instance.output_port
        new_out = self.output if self.output and self.output != (self.function.uart if self.function else None) \
            else None
        rows = [('Ausgang', value(old_out + (f'  →  {new_out}' if new_out else '  (unverändert)')), True),
                ('Referenz', value(device_name(self.instance.reference_port) + (
                    f'  →  {device_name(self.reference)}' if self.reference else '  (unverändert)')), True)]
        summary.show(header('check', 'Auswahl', badge(probes.OK if self.changed() else probes.OFF,
                                                      'bereit zur Prüfung' if self.changed() else 'keine Änderung'),
                            width),
                     fields(rows, width, label_w=11), help_line(LEVEL_NOTE))
        self.query_one('#up-next', Button).disabled = not self.changed()
        self.query_one('#up-hint', Static).update(help_line(
            'Pfeile oder Klick: Pin · Tab: Dropdown, Knöpfe · Esc: Abbruch'))


# ------------------------------------------------------------------ Prüfseite und Anwenden
@dataclass
class UartResult:
    outcome: str = 'failed'            # ok | partial | failed | cancelled
    change: object | None = None       # uart_ports.ChangeResult
    reason: str = ''


RESULT_WORDS = {'ok': (probes.OK, 'angewendet'), 'partial': (probes.WARN, 'gespeichert, Folgeschritt offen'),
                'failed': (probes.FAIL, 'fehlgeschlagen'), 'cancelled': (probes.WARN, 'abgebrochen')}
STEP_LABELS = {'pruefen': 'Plan erneut prüfen', 'schreiben': 'Sicherung anlegen und Konfiguration schreiben',
               'dienst': 'Werkbank-Dienst neu starten'}


class UartApplyScreen(WorkerScreen):
    GROUP = 'uart'
    TITLE_ICON = 'uart'
    PROGRESS_LABEL = 'Schritte'
    STEP_STARTS_RUN = False

    def __init__(self, instance, plan, *, apply=None, sudo=None):
        super().__init__(instance, 'UART-Ports ändern')
        self.change_plan = plan
        self.apply_fn = apply or (lambda p: uart_ports.apply_change(p, confirmed=True))
        self.sudo = sudo or uart_ports
        keys = ['pruefen', 'schreiben'] + (['dienst'] if plan.service_restart else [])
        self.steps = [Step(key, STEP_LABELS[key]) for key in keys]
        self.plan = ('Prüfseite', [])

    @property
    def OK_LABEL(self) -> str:  # noqa: N802
        return 'Änderung anwenden'

    # ------------------------------------------------------------ Ablauf
    def obtain_sudo(self) -> bool:
        if not self.sudo.sudo_needed(self.change_plan) or self.sudo.sudo_cached():
            return True
        return self.ask_password(self.sudo.sudo_validate,
                                 head='config.txt (Bootpartition) und gegebenenfalls der Dienst brauchen sudo.')

    def run_job(self, console) -> None:
        result = UartResult()
        console.last_result = result
        if not console.confirm('UART-Änderung anwenden?', ['Sicherungen werden angelegt.'], None):
            result.outcome, result.reason = 'cancelled', 'Abgebrochen, nichts geändert.'
            console.mark(probes.WARN, result.reason)
            return
        console.step(STEP_LABELS['pruefen'], key='pruefen')
        console.step(STEP_LABELS['schreiben'], key='schreiben')
        try:
            change = self.apply_fn(self.change_plan)
        except (OSError, ValueError) as error:
            result.reason = str(error)
            console.mark(probes.FAIL, result.reason)
            return
        result.change = change
        if change.backup:
            console.line(f'Sicherung: {change.backup}')
        if self.change_plan.service_restart:
            console.step(STEP_LABELS['dienst'], key='dienst')
        result.outcome = 'partial' if change.reboot_required or change.restart_error or \
            self.change_plan.restart_manually else 'ok'
        console.mark(probes.OK if result.outcome == 'ok' else probes.WARN, change.message)
        if change.restart_error:
            console.mark(probes.WARN, f'Dienstneustart: {change.restart_error}')

    def collect_result(self, console, failure):
        result = console.last_result
        if failure and not result.reason:
            result.reason = failure
        return result

    # ------------------------------------------------------------ Hooks
    def finish_steps(self, result: UartResult) -> None:
        change = result.change
        for step in self.steps:
            if step.state == WAITING:
                step.state = SKIPPED
            elif step.state == RUNNING:
                if step.key == 'dienst':
                    step.state = DONE if change is not None and change.service_restarted else FAILED
                elif step.key == 'pruefen' and result.outcome == 'cancelled':
                    step.state = SKIPPED
                else:
                    step.state = DONE if result.outcome in ('ok', 'partial') else FAILED

    def result_badge(self, result: UartResult) -> tuple[str, str]:
        if result.outcome == 'partial' and result.change is not None and result.change.reboot_required:
            return probes.WARN, 'gespeichert, Pi-Neustart nötig'
        return RESULT_WORDS[result.outcome]

    def after_finished(self, result: UartResult) -> None:
        level, word = self.result_badge(result)
        app = self.app
        app.message(level, f'UART-Ports: {word}.')
        if result.outcome in ('ok', 'partial'):
            from ..instance import discover

            try:
                app.instance = discover(app.instance.config)
            except Exception:  # noqa: BLE001
                pass
        app._setup_at = 0.0
        app.action_refresh()

    def cancel_confirmation(self) -> Confirmation:
        return Confirmation('Vorgang abbrechen?', ['Schreiben und Neustart laufen zu Ende, sobald sie begonnen haben.'],
                            [], 'Abbruch anfordern', danger=True)

    def hint_text(self) -> str:
        if self.finished:
            return 'Esc oder Enter schließt. Der Befund der Konsole wird neu geladen.'
        if self.pending is not None:
            return 'Enter bestätigt, Esc bricht ab (nichts wird geändert).'
        return 'Schreiben läuft; bitte warten.'

    # ------------------------------------------------------------ Anzeige
    def draw_plan(self) -> None:
        card = self.query_one('#kal-plan', SectionCard)
        card.display = self.phase in ('prep', 'confirm')
        plan = self.change_plan
        width = self._width(card)
        rows = [('Ausgang', value(f'{plan.previous_output}  →  {plan.output}' if plan.output != plan.previous_output
                                  else f'{plan.output} (unverändert)'), True),
                ('Referenz', value(f'{device_name(plan.previous_reference)}  →  {device_name(plan.reference)}'
                                   if plan.reference != plan.previous_reference
                                   else f'{device_name(plan.reference)} (unverändert)'), True)]
        notes = Text()
        follow = []
        if plan.reboot_required:
            follow.append(badge(probes.WARN, 'Pi-Neustart nötig'))
        if plan.service_restart:
            follow.append(badge(probes.WARN, 'Werkbank-Dienst wird neu gestartet'))
        if plan.restart_manually:
            follow.append(badge(probes.WARN, 'Werkbank von Hand neu starten'))
        if plan.sudo_required:
            follow.append(badge(probes.OFF, 'sudo nötig'))
        for item in follow:
            notes.append_text(item)
            notes.append(' ')
        parts: list = [fields([(label, content) for label, content, _ in rows], width, label_w=11)]
        if follow:
            parts += [Text(''), notes]
        for warning in plan.warnings:
            parts.append(Text(f'▲ {warning}', style=TONE[probes.WARN]))
        if plan.boot:
            parts += [Text(''), Text(f'{plan.boot.path}  (wird ergänzt, Sicherung zuerst)', style=f'bold {ACCENT}'),
                      diff_text(plan.boot_diff)]
        if plan.config:
            parts += [Text(''), Text(f'{plan.config.path}  (Instanzkonfiguration)', style=f'bold {ACCENT}'),
                      diff_text(plan.config_diff)]
        parts += [Text(''), Text(LEVEL_NOTE, style=SOFT)]
        card.show(header('uart', 'Prüfseite', None, width, note='Änderungen vor dem Schreiben'), Group(*parts), None)

    def draw_result(self) -> None:
        card = self.query_one('#kal-result', SectionCard)
        result = self.result
        card.display = result is not None
        if result is None:
            return
        width = self._width(card)
        level, word = self.result_badge(result)
        change = result.change
        plan = self.change_plan
        rows: list = []
        if change is not None:
            rows.append(('Ausgang', value(plan.output), True))
            rows.append(('Referenz', value(device_name(plan.reference)), True))
            if change.backup:
                rows.append(('Sicherung', value(str(change.backup)), True))
            if plan.service_restart:
                rows.append(('Dienst', badge(probes.OK, 'neu gestartet') if change.service_restarted
                             else badge(probes.WARN, 'Neustart steht aus')))
            if change.reboot_required:
                rows.append(('Pi-Neustart', badge(probes.WARN, 'nötig')))
                rows.append(('Befehl', value(REBOOT_COMMAND), True))
        else:
            rows.append(('Folge', badge(probes.OFF, 'nichts geändert')))
        body = fields(rows, width, label_w=13)
        text = result.reason or (change.message if change is not None else '')
        parts = [body]
        if text:
            parts.append(reason_block(text, 'Grund' if result.outcome == 'failed' else 'Meldung'))
        if change is not None and change.restart_error:
            parts.append(reason_block(change.restart_error, 'Dienstneustart'))
        help_text = None
        if change is not None and change.reboot_required:
            help_text = help_line('picam startet den Pi nie selbst: Befehl im Terminal ausführen, wenn es passt. '
                                  'Danach Gerätenamen und TX prüfen.')
        elif change is not None and change.restart_error:
            help_text = help_line('Gespeichert. Dienst von Hand neu starten: picam restart.')
        card.show(header('values', 'Ergebnis', badge(level, word), width), Group(*parts), help_text)
