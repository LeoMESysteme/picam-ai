"""Formular „Neuen Sensor hinzufügen“: sammelt die Angaben für ``request.json`` des Onboardings.

Das Formular prüft nur die Eingaben (``validate_form``, reine Funktion); angelegt wird nichts. Ergebnis ist
das request-Dict nach Vertrag (``onboarding-contract.md``) oder ``None`` bei Abbruch.
"""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from .. import probes
from ..ui import MUTED, TONE, P, fade_in
from ..widgets import ChipSelector, badge, header

CELLS = 16
FAMILY = 'hd44780_5x8'
FAMILY_LABEL = 'Punktraster 16×1 (HD44780)'
CONNECTIONS = (('rs232', 'RS232'), ('usb', 'USB'), ('none', 'keiner'))
ASSISTANT_LABELS = {'claude': 'Claude', 'codex': 'Codex', 'none': 'Ohne KI'}
LOGIN_COMMANDS = {'claude': ['claude'], 'codex': ['codex', 'login']}
UNSUPPORTED = ('Weitere Anzeigearten (7-Segment, Grafik-LCD, mehrzeilig, Leuchtanzeigen, helle Ziffern auf '
               'dunkel) werden noch nicht unterstützt.')
EXAMPLE_HELP = ('So, wie die 16 Zellen gerade aussehen; Leerzellen als Leerzeichen, zum Beispiel '
                '„+ 1.2345 mV/V   “. Leer lassen, wenn die Anzeige gerade nichts Lesbares zeigt.')


def assistant_state(info: dict | None) -> str | None:
    """None = nutzbar, sonst der Grund (Text für die Meldung)."""
    if not info or not info.get('installed'):
        return 'nicht installiert'
    if info.get('logged_in') is False:
        return 'nicht angemeldet'
    return None


def validate_form(values: dict, assistants: dict) -> tuple[dict | None, dict[str, str]]:
    """Eingaben prüfen. Rückgabe (request oder None, Fehler je Feld auf Deutsch)."""
    errors: dict[str, str] = {}
    name = str(values.get('name', '')).strip()
    if not name:
        errors['name'] = 'Name fehlt: bitte die Bezeichnung des Sensors eintragen.'
    elif len(name) > 60 or any(ord(c) < 32 for c in name):
        errors['name'] = 'Name ungültig: höchstens 60 Zeichen, keine Steuerzeichen.'
    example = str(values.get('example', ''))
    if example.strip():
        if len(example) > CELLS:
            errors['example'] = f'Beispiel zu lang: {len(example)} Zeichen, die Anzeige hat {CELLS} Zellen.'
        elif any(not c.isprintable() for c in example):
            errors['example'] = 'Beispiel enthält nicht druckbare Zeichen.'
    unit = str(values.get('unit', '')).strip()
    if len(unit) > 12:
        errors['unit'] = 'Einheit zu lang (höchstens 12 Zeichen).'
    connection = values.get('connection', 'none')
    if connection not in dict(CONNECTIONS):
        errors['connection'] = 'Anschlussart unbekannt.'
    assistant = values.get('assistant', 'none')
    if assistant not in ASSISTANT_LABELS:
        errors['assistant'] = 'KI-Assistent unbekannt.'
    elif assistant != 'none':
        reason = assistant_state(assistants.get(assistant))
        if reason:
            errors['assistant'] = (f'{ASSISTANT_LABELS[assistant]} ist {reason}: bitte anmelden oder '
                                   '„Ohne KI“ wählen.')
    if errors:
        return None, errors
    port = values.get('port') or None
    request = {
        'v': 1, 'name': name, 'manufacturer': str(values.get('manufacturer', '')).strip(),
        'display_family': FAMILY,
        'unit': unit,
        'connection': {'kind': connection, 'port': port if connection != 'none' else None,
                       'hint': str(values.get('hint', '')).strip() or None},
        'assistant': assistant, 'notes': str(values.get('notes', '')).strip(),
    }
    if example.strip():
        request['example'] = example.ljust(CELLS)
    return request, {}


def cell_preview(example: str) -> Text:
    """Die 16 Zellen als Raster mit Zellennummern darunter."""
    cells, numbers = Text(no_wrap=True), Text(no_wrap=True, style=MUTED)
    shown = example[:CELLS].ljust(CELLS)
    for index, char in enumerate(shown):
        style = f'{P.text} on {P.inset}' if index % 2 == 0 else f'{P.text} on {P.surface}'
        cells.append(f' {char} ', style=style)
        numbers.append(f' {index:X} ')
    if len(example) > CELLS:
        cells.append(' +' + str(len(example) - CELLS), style=TONE[probes.FAIL])
    return Text('\n').join([cells, numbers])


class SensorWizardScreen(ModalScreen[dict | None]):
    """Formular; Esc oder „Abbrechen“ schließt ohne Ergebnis."""

    BINDINGS = [Binding('escape', 'cancel', show=False)]
    DEFAULT_CSS = '''
    SensorWizardScreen { align: center middle; }
    #wiz { width: 84; max-width: 96%; height: 94%; max-height: 46; padding: 1 2; background: $picam-raised; }
    /* Nur der Formularteil scrollt; Titel, Fehlermeldung und Knöpfe bleiben auch in kleinen Fenstern sichtbar. */
    #wiz-body { height: 1fr; scrollbar-size-vertical: 1; }
    #wiz .wiz-label { height: auto; margin: 1 0 0 0; color: $picam-text-soft; }
    #wiz .wiz-note { height: auto; margin: 0; }
    #wiz Input { height: 1; border: none; padding: 0 1; background: $picam-field; }
    #wiz Input:focus { background: $picam-field-focus; }
    #wiz-preview { height: 2; margin: 1 0 0 0; }
    #wiz-error { height: auto; margin: 1 0 0 0; }
    #wiz-buttons { height: auto; margin: 1 0 0 0; align-horizontal: right; }
    #wiz-buttons Button { margin: 0 0 0 2; }
    '''

    def __init__(self, assistants: dict | None = None, ports: list[dict] | None = None):
        super().__init__()
        self.assistants = assistants or {}
        self.ports = ports or []
        usable = [n for n in ('claude', 'codex') if assistant_state(self.assistants.get(n)) is None]
        self.assistant = usable[0] if usable else 'none'
        self.connection = 'rs232'
        self.port: str | None = None

    # ------------------------------------------------------------ Aufbau
    def compose(self):
        with Vertical(id='wiz'):
            yield Static(id='wiz-title')
            with VerticalScroll(id='wiz-body'):
                yield Static('Name *', classes='wiz-label')
                yield Input(id='wiz-name', placeholder='z. B. GSV-2TSD-DI')
                yield Static('Hersteller', classes='wiz-label')
                yield Input(id='wiz-maker', placeholder='z. B. ME-Meßsysteme')
                yield Static('Anzeigeart', classes='wiz-label')
                yield ChipSelector(id='wiz-family')
                yield Static(Text(UNSUPPORTED, style=MUTED), classes='wiz-note')
                yield Static('Anzeige-Beispiel (16 Zellen)', classes='wiz-label')
                yield Input(id='wiz-example', placeholder='+ 1.2345 mV/V   ')
                yield Static(id='wiz-preview')
                yield Static(Text(EXAMPLE_HELP, style=MUTED), classes='wiz-note')
                yield Static('Einheit', classes='wiz-label')
                yield Input(id='wiz-unit', placeholder='z. B. mV/V')
                yield Static('Anschluss', classes='wiz-label')
                yield ChipSelector(id='wiz-conn')
                yield ChipSelector(id='wiz-port')
                yield Input(id='wiz-hint', placeholder='Ortsangabe, z. B. USB oben links')
                yield Static('KI-Assistent', classes='wiz-label')
                yield ChipSelector(id='wiz-assist')
                yield Static(id='wiz-assist-note', classes='wiz-note')
            yield Static(id='wiz-error')
            with Horizontal(id='wiz-buttons'):
                yield Button('Anmelden', id='wiz-login')
                yield Button('Abbrechen', id='wiz-cancel')
                yield Button('Sensor einrichten', id='wiz-ok', variant='primary')

    def on_mount(self) -> None:
        fade_in(self.query_one('#wiz'))
        self.query_one('#wiz-title', Static).update(header('setup', 'Neuen Sensor hinzufügen', None, 76))
        self.query_one('#wiz-family', ChipSelector).set_items([('template', FAMILY_LABEL, None)], 0)
        self.query_one('#wiz-conn', ChipSelector).set_items(
            [('uart' if key == 'rs232' else 'connect' if key == 'usb' else 'off', label, None)
             for key, label in CONNECTIONS], 0)
        self._draw_ports()
        self._draw_assistants()
        self._draw_preview()
        self.query_one('#wiz-name', Input).focus()

    # ------------------------------------------------------------ Anzeige
    def _draw_ports(self) -> None:
        selector = self.query_one('#wiz-port', ChipSelector)
        items = [('off', 'Automatisch finden', None)] + [('uart', p['label'], None) for p in self.ports]
        keys = [None] + [p['port'] for p in self.ports]
        selector.set_items(items, keys.index(self.port) if self.port in keys else 0)
        selector.display = self.connection != 'none'
        self.query_one('#wiz-hint', Input).display = self.connection != 'none'

    def _draw_assistants(self) -> None:
        items = []
        for name in ('claude', 'codex', 'none'):
            reason = None if name == 'none' else assistant_state(self.assistants.get(name))
            mark = badge(probes.OFF, reason, 'off') if reason else None
            items.append(('on' if name != 'none' else 'off', ASSISTANT_LABELS[name], mark))
        order = ('claude', 'codex', 'none')
        self.query_one('#wiz-assist', ChipSelector).set_items(items, order.index(self.assistant))
        reason = None if self.assistant == 'none' else assistant_state(self.assistants.get(self.assistant))
        note = self.query_one('#wiz-assist-note', Static)
        login = self.query_one('#wiz-login', Button)
        if self.assistant == 'none':
            note.update(Text('Ohne KI führt die Konsole mit festen Schritten durch die Einrichtung.', style=MUTED))
        elif reason:
            note.update(Text(f'{ASSISTANT_LABELS[self.assistant]} ist {reason}. '
                             + ('Mit „Anmelden“ im Terminal anmelden.' if reason == 'nicht angemeldet'
                                else 'Bitte installieren oder „Ohne KI“ wählen.'), style=TONE[probes.WARN]))
        else:
            note.update(Text(f'{ASSISTANT_LABELS[self.assistant]} hilft beim Erkennen und Einrichten; '
                             'es schreibt nur in die Laufmappe und das lokale Sensorpaket.', style=MUTED))
        login.display = reason == 'nicht angemeldet'
        login.label = f'{ASSISTANT_LABELS.get(self.assistant, "")} anmelden'.strip()

    def _draw_preview(self) -> None:
        self.query_one('#wiz-preview', Static).update(cell_preview(self.query_one('#wiz-example', Input).value))

    def _show_errors(self, errors: dict[str, str]) -> None:
        text = Text()
        for line in errors.values():
            text.append(('' if not text else '\n') + line, style=TONE[probes.FAIL])
        self.query_one('#wiz-error', Static).update(text)

    # ------------------------------------------------------------ Ereignisse
    @on(Input.Changed, '#wiz-example')
    def _example_changed(self) -> None:
        self._draw_preview()

    @on(Input.Submitted)
    def _submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.focus_next()

    @on(ChipSelector.Selected, '#wiz-conn')
    def _conn_selected(self, event: ChipSelector.Selected) -> None:
        self.connection = CONNECTIONS[event.index][0]
        self._draw_ports()

    @on(ChipSelector.Selected, '#wiz-port')
    def _port_selected(self, event: ChipSelector.Selected) -> None:
        self.port = None if event.index == 0 else self.ports[event.index - 1]['port']

    @on(ChipSelector.Selected, '#wiz-assist')
    def _assist_selected(self, event: ChipSelector.Selected) -> None:
        self.assistant = ('claude', 'codex', 'none')[event.index]
        self._draw_assistants()

    @on(Button.Pressed, '#wiz-login')
    def _login(self) -> None:
        command = LOGIN_COMMANDS.get(self.assistant)
        if command:
            self.app.run_in_terminal(command, f'{ASSISTANT_LABELS[self.assistant]}: Anmeldung')
            self.refresh_assistants()

    def refresh_assistants(self) -> None:
        from .. import sensor_client

        self.assistants = sensor_client.detect_assistants()
        self._draw_assistants()

    @on(Button.Pressed, '#wiz-cancel')
    def action_cancel(self) -> None:
        self.dismiss(None)

    def values(self) -> dict:
        get = lambda sel: self.query_one(sel, Input).value  # noqa: E731
        return {'name': get('#wiz-name'), 'manufacturer': get('#wiz-maker'), 'example': get('#wiz-example'),
                'unit': get('#wiz-unit'), 'connection': self.connection,
                'port': self.port if self.connection != 'none' else None, 'hint': get('#wiz-hint'),
                'assistant': self.assistant}

    @on(Button.Pressed, '#wiz-ok')
    def submit(self) -> None:
        request, errors = validate_form(self.values(), self.assistants)
        self._show_errors(errors)
        if request is not None:
            self.dismiss(request)
