"""Gemeinsame Bausteine der picam-Konsole: Farben, Zeichen, Dialoge, Darstellung.

Von ``tui`` (App) und ``views`` (Tabs) benutzt, damit die Tabs ohne
Kreisimport auskommen.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import Button, Input, Static

from . import probes

SPINNER = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'

SYMBOL = {probes.OK: '✓', probes.WARN: '!', probes.FAIL: '✗', probes.OFF: '○', probes.UNKNOWN: '?'}
ASCII_SYMBOL = {probes.OK: '+', probes.WARN: '!', probes.FAIL: 'x', probes.OFF: '-', probes.UNKNOWN: '?'}
#: Palette „ME-Türkis“: eine Leitfarbe (Türkis aus dem ME-Logo), dazu wenige
#: abgestimmte Statustöne. Hintergründe in drei Stufen (Grund, Fläche, Feld).
BG = '#121820'
SURFACE = '#1a222c'
PANEL = '#222c38'
LINE = '#2b3644'
TEXT = '#e3e9f0'
SOFT = '#a9b4c2'
#: Semantische Farben (Status: genau ein Zeichen + eine Farbe).
TONE = {probes.OK: '#7fd1a0', probes.WARN: '#f2c46d', probes.FAIL: '#f2867f', probes.OFF: '#8a96a6',
        probes.UNKNOWN: '#b7a6f2'}
MUTED = '#8a96a6'
ACCENT = '#2ec4b6'
ACCENT_DEEP = '#0f6e68'
SECONDARY = '#7aa7f5'
#: Getönte Flächen für Hinweise (Rand in Statusfarbe, Grund leicht eingefärbt).
TINT = {probes.OK: '#16261f', probes.WARN: '#2a2416', probes.FAIL: '#2c1a1c', 'info': '#13292b'}

THEME = Theme(
    name='picam',
    primary=ACCENT,
    secondary=SECONDARY,
    accent=ACCENT,
    warning=TONE[probes.WARN],
    error=TONE[probes.FAIL],
    success=TONE[probes.OK],
    foreground=TEXT,
    background=BG,
    surface=SURFACE,
    panel=PANEL,
    dark=True,
    variables={
        'footer-key-foreground': ACCENT,
        'footer-description-foreground': SOFT,
        'footer-background': BG,
        'block-cursor-background': '#17403f',
        'block-cursor-foreground': '#f2fbfa',
        'block-cursor-text-style': 'bold',
        'block-cursor-blurred-background': '#1b2c30',
        'block-cursor-blurred-text-style': 'none',
        'scrollbar': LINE,
        'scrollbar-background': BG,
        'scrollbar-background-hover': BG,
        'scrollbar-background-active': BG,
        'scrollbar-corner-color': BG,
        'scrollbar-hover': '#3a4757',
        'scrollbar-active': ACCENT,
        'input-cursor-background': ACCENT,
    },
)



def ascii_mode() -> bool:
    return bool(os.environ.get('PICAM_ASCII')) or 'UTF-8' not in (os.environ.get('LANG', '') +
                                                                   os.environ.get('LC_ALL', '') +
                                                                   os.environ.get('LC_CTYPE', '')).upper()


def symbol(level: str) -> str:
    return (ASCII_SYMBOL if ascii_mode() else SYMBOL)[level]


def fit(text: str, width: int) -> str:
    """Auf Zellbreite kürzen (Rich misst breite Zeichen korrekt)."""
    rendered = Text(text)
    if rendered.cell_len <= width:
        return text
    rendered.truncate(max(1, width), overflow='ellipsis')
    return rendered.plain


def fade_in(widget, start: float = 0.0, duration: float = 0.14) -> None:
    """Kurz einblenden; mit TEXTUAL_ANIMATIONS=none sofort sichtbar."""
    if widget.app.animation_level == 'none':
        return
    widget.styles.opacity = start
    widget.styles.animate('opacity', 1.0, duration=duration, easing='out_cubic')


# ----------------------------------------------------------------- Dialoge



@dataclass
class Confirmation:
    title: str
    lines: list[str]
    commands: list[str]
    action_label: str
    danger: bool = False
    blocker: str | None = None


class ConfirmScreen(ModalScreen[bool]):
    """Bestätigung mit sichtbarem Befehl. Fokus startet auf „Abbrechen“."""

    BINDINGS = [Binding('escape', 'cancel', 'Abbrechen', show=False),
                Binding('left,right', 'switch', show=False)]

    def __init__(self, confirmation: Confirmation):
        super().__init__()
        self.c = confirmation

    def compose(self) -> ComposeResult:
        with Vertical(id='dialog'):
            yield Static(Text(self.c.title, style='bold'), id='dialog-title')
            for line in self.c.lines:
                yield Static(Text(line), classes='dialog-line')
            if self.c.commands:
                yield Static(Text('\n'.join('$ ' + c for c in self.c.commands), style=MUTED), id='dialog-cmd')
            if self.c.blocker:
                yield Static(Text(f'{symbol(probes.WARN)} Gesperrt: {self.c.blocker}', style=TONE[probes.WARN]),
                             id='dialog-blocker')
            with Horizontal(id='dialog-buttons'):
                yield Button('Abbrechen', id='cancel')
                yield Button(self.c.action_label, id='ok', variant='error' if self.c.danger else 'primary',
                             disabled=self.c.blocker is not None)

    def on_mount(self) -> None:
        self.query_one('#cancel', Button).focus()
        fade_in(self.query_one('#dialog'))

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_switch(self) -> None:
        self.focus_next(Button)

    @on(Button.Pressed, '#cancel')
    def _cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, '#ok')
    def _ok(self) -> None:
        self.dismiss(True)


class AskScreen(ModalScreen[str | None]):
    """Eine Eingabe mit Erklärung; Enter übernimmt, Esc bricht ab."""

    BINDINGS = [Binding('escape', 'cancel', 'Abbrechen', show=False)]

    def __init__(self, title: str, lines: list[str], value: str = '', placeholder: str = ''):
        super().__init__()
        self.title_text, self.lines, self.value, self.placeholder = title, lines, value, placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id='dialog'):
            yield Static(Text(self.title_text, style='bold'), id='dialog-title')
            for line in self.lines:
                yield Static(Text(line), classes='dialog-line')
            yield Input(value=self.value, placeholder=self.placeholder, id='ask-input')
            with Horizontal(id='dialog-buttons'):
                yield Button('Abbrechen', id='cancel')
                yield Button('Weiter', id='ok', variant='primary')

    def on_mount(self) -> None:
        self.query_one('#ask-input', Input).focus()
        fade_in(self.query_one('#dialog'))

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted)
    @on(Button.Pressed, '#ok')
    def _ok(self) -> None:
        value = self.query_one('#ask-input', Input).value.strip()
        self.dismiss(value or None)

    @on(Button.Pressed, '#cancel')
    def _cancel(self) -> None:
        self.dismiss(None)




class Cards(Grid):
    """Kartenraster der Übersicht; ``signature`` verhindert unnötiges Neuzeichnen."""

    def __init__(self, cards: list[Static], columns: int, signature: str):
        super().__init__(*cards, classes='cards')
        self.styles.grid_size_columns = columns
        self.signature = signature


CARD_ROWS = 3


def fact_card(fact: probes.Fact) -> Static:
    """Karte: Zeichen, Name, Wert und bis zu drei Detailzeilen, gekürzt statt umbrochen."""
    title = Text(no_wrap=True, overflow='ellipsis')
    title.append(f'{symbol(fact.level)} ', style=TONE[fact.level])
    title.append(fact.label, style='bold')
    title.append(f'  {fact.value}', style=MUTED if fact.level in (probes.OK, probes.OFF) else TONE[fact.level])
    table = Table.grid(padding=(0, 2), expand=True)
    table.add_column(style=MUTED, no_wrap=True)
    table.add_column(style='#b8c0c8', no_wrap=True, overflow='ellipsis', ratio=1)
    detail = [(k, v) for k, v in fact.detail if v and k not in ('Unit', 'Zustand', 'Weg')][:CARD_ROWS]
    for key, value in detail:
        table.add_row(key, str(value))
    for _ in range(CARD_ROWS - len(detail)):
        table.add_row('', '')
    level = {probes.FAIL: ' card-fail', probes.WARN: ' card-warn'}.get(fact.level, '')
    return Static(Group(title, table), classes='card' + level)




def kv_table(rows) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style=MUTED, no_wrap=True)
    table.add_column(overflow='fold')
    for key, value in rows:
        table.add_row(key, value)
    return table


def fact_title(fact: probes.Fact) -> Text:
    title = Text()
    title.append(fact.label, style='bold')
    title.append('   ')
    title.append(f'{symbol(fact.level)} {fact.value}', style=TONE[fact.level])
    return title


def hint_block(fact: probes.Fact) -> Text | None:
    if not fact.hint and not fact.command:
        return None
    text = Text()
    if fact.hint:
        text.append(fact.hint)
    if fact.command:
        if fact.hint:
            text.append('\n')
        text.append('-> ' if ascii_mode() else '→ ', style=MUTED)
        text.append(fact.command, style=ACCENT)
    return text



@dataclass
class Action:
    """Aktion eines Tabs: Taste, Beschriftung, Methode der App oder des Tabs, Sperrgrund."""

    key: str
    label: str
    run: object  # Aufrufbar ohne Argumente
    blocked: str | None = None  # Grund, warum gerade nicht möglich (dann ausgegraut)
    danger: bool = False


@dataclass
class Choice:
    label: str
    value: str
    primary: bool = False
    danger: bool = False


class InfoScreen(ModalScreen[str | None]):
    """Erklärung oder Fehlermeldung mit Wahlmöglichkeiten. Fokus auf der ersten Wahl."""

    BINDINGS = [Binding('escape', 'close', show=False), Binding('left,right', 'switch', show=False)]

    def __init__(self, title: str, lines: list, choices: list[Choice] | None = None, tone: str | None = None):
        super().__init__()
        self.title_text, self.lines, self.tone = title, lines, tone
        self.choices = choices or [Choice('Schließen', 'close', primary=True)]

    def compose(self) -> ComposeResult:
        with Vertical(id='dialog', classes='info' + (f' {self.tone}' if self.tone else '')):
            yield Static(Text(self.title_text, style='bold'), id='dialog-title')
            for line in self.lines:
                yield Static(line if not isinstance(line, str) else Text(line), classes='dialog-line')
            with Horizontal(id='dialog-buttons'):
                for index, choice in enumerate(self.choices):
                    variant = 'error' if choice.danger else 'primary' if choice.primary else 'default'
                    yield Button(choice.label, id=f'choice-{index}', variant=variant)

    def on_mount(self) -> None:
        self.query_one('#choice-0', Button).focus()
        fade_in(self.query_one('#dialog'))

    def action_close(self) -> None:
        self.dismiss(None)

    def action_switch(self) -> None:
        self.focus_next(Button)

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        index = int((event.button.id or 'choice-0').split('-')[1])
        value = self.choices[index].value
        self.dismiss(None if value == 'close' else value)


def section_text(title: str) -> Text:
    """Abschnittskopf: türkiser Balken, Titel in Versalien."""
    text = Text()
    text.append('| ' if ascii_mode() else '▍ ', style=ACCENT)
    text.append(title.upper(), style=f'bold {SOFT}')
    return text


def section(title: str) -> Static:
    return Static(section_text(title), classes='section')


def bar(fraction: float, width: int, tone: str = None, ascii_only: bool | None = None) -> Text:
    """Waagerechter Balken mit Achtelschritten; ``fraction`` 0…1."""
    fraction = min(1.0, max(0.0, fraction))
    ascii_only = ascii_mode() if ascii_only is None else ascii_only
    text = Text()
    if ascii_only:
        filled = round(fraction * width)
        text.append('#' * filled, tone or ACCENT)
        text.append('.' * (width - filled), LINE)
        return text
    eighths = round(fraction * width * 8)
    full, part = divmod(eighths, 8)
    text.append('█' * full, tone or ACCENT)
    if part and full < width:
        text.append(' ▏▎▍▌▋▊▉'[part], tone or ACCENT)
        full += 1
    text.append('░' * (width - full), LINE)
    return text


def status_strip(recent: list, width: int, window_ms: int = 60_000) -> Text:
    """60-s-Band aus ``live.status.run.recent`` ([ms_offset, 'v'|'t'|'u'|'s', wert]).

    Jede Zelle fasst ihren Zeitabschnitt zusammen; der schlechteste Status
    gewinnt (unlesbar vor veraltet vor Übergang vor gültig). Leer = keine Daten.
    """
    rank = {'u': 3, 's': 2, 't': 1, 'v': 0}
    colour = {'v': TONE[probes.OK], 't': TONE[probes.WARN], 's': TONE[probes.UNKNOWN], 'u': TONE[probes.FAIL]}
    cells: list[str | None] = [None] * width
    for entry in recent or []:
        try:
            offset, status = int(entry[0]), str(entry[1])
        except (TypeError, ValueError, IndexError):
            continue
        index = min(width - 1, max(0, offset * width // max(1, window_ms)))
        if cells[index] is None or rank.get(status, 0) > rank.get(cells[index], 0):
            cells[index] = status
    text = Text()
    block = '#' if ascii_mode() else '▇'
    for status in cells:
        text.append(block if status else ('.' if ascii_mode() else '·'), colour.get(status, LINE))
    return text


def sparkline(values: list, width: int, tone: str | None = None) -> Text:
    """Kleiner Verlauf aus Zahlen (None = Lücke), rechts die neuesten."""
    ticks = '_.-=*#' if ascii_mode() else '▁▂▃▄▅▆▇█'
    data = list(values)[-width:]
    known = [v for v in data if v is not None]
    text = Text()
    if not known:
        return Text('–', MUTED)
    low, high = min(known), max(known)
    span = (high - low) or 1.0
    for value in data:
        if value is None:
            text.append(' ')
        else:
            text.append(ticks[min(len(ticks) - 1, int((value - low) / span * (len(ticks) - 1)))], tone or ACCENT)
    return text


class Canvas(Widget):
    """Feste Fläche für Einzelbilder: ``show`` zeichnet neu, ohne das Layout neu zu berechnen."""

    DEFAULT_CSS = 'Canvas { width: auto; height: auto; }'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._content = Text()

    def show(self, content: Text) -> None:
        self._content = content
        self.refresh()

    def render(self) -> Text:
        return self._content
