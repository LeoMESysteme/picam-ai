"""picam-Konsole: ruhige Verwaltungsoberfläche für die Werkbank (Textual 2.x).

Aufbau (ab 76 Spalten): links die Liste der Bereiche mit je einem Zeichen
und einem Wort, rechts der gewählte Bereich mit Befund, Abhilfe und Aktionen.
Schmaler wird daraus ein Stapel: Liste, Enter öffnet, Esc zurück.

Die Konsole verwaltet nur den Dienst und seine Einrichtung. Sie startet
keinen Messlauf und zeigt keine Messwerte; Dienstaktionen sind gesperrt,
solange ein Lauf, eine Einrichtung oder eine Diagnosekopie aktiv ist.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass

from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Button, Checkbox, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from . import probes
from .instance import Instance

MIN_WIDTH, MIN_HEIGHT = 48, 14
SPLIT_WIDTH = 76
REFRESH_S = 5.0
SETUP_REFRESH_S = 60.0
LOG_LIMIT = 2000

SYMBOL = {probes.OK: '✓', probes.WARN: '!', probes.FAIL: '✗', probes.OFF: '○', probes.UNKNOWN: '?'}
ASCII_SYMBOL = {probes.OK: '+', probes.WARN: '!', probes.FAIL: 'x', probes.OFF: '-', probes.UNKNOWN: '?'}
#: Semantische Farben, passend zum Theme (Status: genau ein Zeichen + eine Farbe).
TONE = {probes.OK: '#8fbf8f', probes.WARN: '#e5b567', probes.FAIL: '#e5787a', probes.OFF: '#7d8590',
        probes.UNKNOWN: '#b799d4'}
MUTED = '#7d8590'
ACCENT = '#6cb6c4'

THEME = Theme(
    name='picam',
    primary=ACCENT,
    secondary='#8aa4c8',
    accent=ACCENT,
    warning=TONE[probes.WARN],
    error=TONE[probes.FAIL],
    success=TONE[probes.OK],
    foreground='#d6dae0',
    background='#0e1116',
    surface='#151a21',
    panel='#1b2129',
    dark=True,
    variables={
        'footer-key-foreground': ACCENT,
        'footer-description-foreground': '#9aa3ad',
        'footer-background': '#0e1116',
        'block-cursor-background': '#1f3a40',
        'block-cursor-foreground': '#e8eef2',
        'block-cursor-text-style': 'none',
        'block-cursor-blurred-background': '#1a252b',
        'block-cursor-blurred-text-style': 'none',
        'scrollbar': '#252c35',
        'scrollbar-background': '#0e1116',
        'scrollbar-background-hover': '#0e1116',
        'scrollbar-background-active': '#0e1116',
        'scrollbar-corner-color': '#0e1116',
        'scrollbar-hover': '#2f3842',
        'scrollbar-active': ACCENT,
        'input-cursor-background': ACCENT,
    },
)

TOOLS = (('protokoll', 'Protokoll'), ('konfiguration', 'Konfiguration'))
SERVICE_WORDS = {'start': ('Dienst starten', 'Starten'), 'stop': ('Dienst stoppen', 'Stoppen'),
                 'restart': ('Dienst neu starten', 'Neu starten')}


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
                yield Static(line, classes='dialog-line')
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


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding('escape,q,question_mark,f1', 'close', show=False)]

    KEYS = (
        ('↑ ↓  j k', 'Bereich wählen'),
        ('Enter', 'Bereich öffnen (schmales Terminal)'),
        ('Esc', 'zurück / Dialog schließen'),
        ('s', 'Dienst starten oder stoppen'),
        ('r', 'Dienst neu starten'),
        ('l', 'Protokoll'),
        ('c', 'Konfiguration'),
        ('a', 'empfohlenen Befehl ausführen (mit Rückfrage)'),
        ('g', 'jetzt neu prüfen'),
        ('f', 'Protokoll: mitlaufen an/aus'),
        ('e', 'Protokoll: nur Warnungen und Fehler'),
        ('o', 'Werkbank-Adresse anzeigen'),
        ('q  Ctrl+C', 'beenden'),
    )

    def compose(self) -> ComposeResult:
        table = Table.grid(padding=(0, 3))
        table.add_column(style=f'bold {ACCENT}', no_wrap=True)
        table.add_column()
        for key, text in self.KEYS:
            table.add_row(key, text)
        with Vertical(id='dialog'):
            yield Static(Text('Tasten', style='bold'), id='dialog-title')
            yield Static(table)
            yield Static(Text('picam verwaltet den Dienst. Messläufe und Einrichtung der Anzeige '
                              'laufen in der Werkbank im Browser.', style=MUTED), classes='dialog-line')

    def action_close(self) -> None:
        self.dismiss(None)

    def on_click(self) -> None:
        self.dismiss(None)


# ----------------------------------------------------------------- Bereiche

class Detail(VerticalScroll):
    """Rechter Bereich für einen Befund oder die Übersicht."""

    can_focus = False


class LogPane(Vertical):
    pass


class ConfigPane(VerticalScroll):
    pass


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
        text.append('→ ', style=MUTED)
        text.append(fact.command, style=ACCENT)
    return text


class PicamApp(App[int]):
    TITLE = 'picam'
    CSS = """
    Screen { background: $background; layers: base overlay; }
    #top { height: 1; padding: 0 1; background: $background; }
    #main { height: 1fr; }
    #nav { width: 30; height: 1fr; border: none; padding: 0 0 0 0; background: $background;
           scrollbar-size-vertical: 1; }
    #nav:focus { border: none; background-tint: 0%; }
    #nav > .option-list--option { padding: 0 1; }
    #nav > .option-list--option-disabled { color: $text-muted; text-style: bold; padding: 0 1; }
    #nav > .option-list--separator { color: $background; }
    #pane { width: 1fr; height: 1fr; padding: 0 2 0 2; border-left: vkey #252c35; }
    Detail { height: 1fr; scrollbar-size-vertical: 1; }
    Detail > Static { width: 1fr; }
    .title { margin: 1 0 1 0; }
    .hint { border-left: wide $warning; padding: 0 1; margin: 0 0 1 0; background: #16140f; }
    .hint.fail { border-left: wide $error; background: #191212; }
    .hint.info { border-left: wide $primary; background: #11171a; }
    .section { color: $text-muted; text-style: bold; margin: 1 0 0 0; }
    .actions { color: $text-muted; margin: 1 0 0 0; }
    LogPane { height: 1fr; }
    #log-head { height: 1; margin: 1 0 0 0; }
    #log { height: 1fr; background: $background; border: none; scrollbar-size-vertical: 1; padding: 0;
           overflow-x: hidden; }
    ConfigPane { height: 1fr; }
    .field { height: auto; margin: 1 0 0 0; }
    .field-label { color: $text-muted; }
    .field Input { width: 40; height: 1; margin: 0; padding: 0 1; border: none; background: $surface; }
    .field Input:focus { border: none; background: #1a2a2f; }
    .field Checkbox { margin: 0; height: 1; padding: 0; border: none; background: $background; }
    .field Checkbox:focus { border: none; background-tint: 0%; }
    .field Checkbox > .toggle--button { background: #252c35; color: #252c35; }
    .field Checkbox.-on > .toggle--button { background: $primary; color: #0e1116; }
    .field Checkbox:focus > .toggle--label { text-style: bold underline; background: transparent; }
    .note { color: $text-muted; margin: 1 0 0 0; }
    #config-check { margin: 1 0 0 0; }
    #status { height: 1; padding: 0 1; color: $text-muted; }
    #footer { height: 1; padding: 0 1; background: $background; }
    #small { display: none; width: 1fr; height: 1fr; content-align: center middle; color: $text-muted; }
    Screen.too-small #small { display: block; }
    Screen.too-small #top, Screen.too-small #main, Screen.too-small #status, Screen.too-small #footer {
        display: none; }
    Screen.stacked #nav { width: 1fr; }
    Screen.stacked #pane { display: none; border-left: none; padding: 0 1; }
    Screen.stacked.open #nav { display: none; }
    Screen.stacked.open #pane { display: block; }
    ConfirmScreen, HelpScreen { align: center middle; background: rgba(5, 7, 10, 0.72); }
    #dialog { width: 72; max-width: 95%; height: auto; padding: 1 2; background: $panel; border: none; }
    #dialog-title { margin: 0 0 1 0; }
    .dialog-line { margin: 0 0 1 0; }
    #dialog-cmd { margin: 0 0 1 0; padding: 0 1; background: $background; }
    #dialog-blocker { margin: 0 0 1 0; }
    #dialog-buttons { height: auto; align-horizontal: right; }
    #dialog-buttons Button { margin: 0 0 0 2; }
    Button { border: none; height: 1; min-width: 14; padding: 0 2; background: #252c35; color: $foreground;
             text-style: none; }
    Button:hover { background: #2f3842; }
    Button:focus { background: $primary; color: #0e1116; text-style: bold; background-tint: 0%; }
    Button.-primary:focus { background: $primary; }
    Button.-error { color: $error; }
    Button.-error:focus { background: $error; color: #0e1116; }
    Button:disabled { color: #4a525c; background: #1b2129; }
    """

    BINDINGS = [
        Binding('q', 'quit_app', 'Ende'),
        Binding('ctrl+c', 'quit_app', 'Ende', show=False, priority=True),
        Binding('question_mark,f1', 'help', 'Hilfe'),
        Binding('s', 'toggle_service', 'Start/Stopp'),
        Binding('r', 'restart', 'Neustart'),
        Binding('l', 'show("protokoll")', 'Protokoll'),
        Binding('c', 'show("konfiguration")', 'Konfig.'),
        Binding('a', 'run_fix', 'Ausführen', show=False),
        Binding('g', 'refresh', 'Prüfen', show=False),
        Binding('o', 'open_url', 'Adresse', show=False),
        Binding('f', 'toggle_follow', 'Mitlaufen', show=False),
        Binding('e', 'toggle_errors', 'Nur Probleme', show=False),
        Binding('escape', 'go_back', 'Zurück', show=False),
        Binding('j', 'nav_down', show=False),
        Binding('k', 'nav_up', show=False),
    ]

    selected: reactive[str] = reactive('uebersicht', init=False)

    def __init__(self, instance: Instance, collect=probes.collect, journal_source=None,
                 service_runner=None, auto_refresh: bool = True):
        super().__init__()
        self.instance = instance
        self._collect = collect
        self._journal_source = journal_source
        self._service_runner = service_runner
        self._auto_refresh = auto_refresh
        self.snapshot: probes.Snapshot | None = None
        self._setup_facts: dict[str, probes.Fact] = {}
        self._setup_at = 0.0
        self._busy: str | None = None
        self._message: tuple[str, str] | None = None
        self._follow = True
        self._errors_only = False
        self._log_lines: list = []
        self._log_thread: threading.Thread | None = None
        self._log_process: subprocess.Popen | None = None
        self._config_draft: dict = {}
        self._rendered_detail: str | None = None

    # ------------------------------------------------------------ Aufbau
    def compose(self) -> ComposeResult:
        yield Static(id='top')
        with Horizontal(id='main'):
            yield OptionList(id='nav')
            with Vertical(id='pane'):
                yield Detail(id='detail')
                with LogPane(id='logpane'):
                    yield Static(id='log-head')
                    yield RichLog(id='log', max_lines=LOG_LIMIT, wrap=True, markup=False, auto_scroll=True,
                                  min_width=20)
                yield ConfigPane(id='configpane')
        yield Static(id='status')
        yield Static(id='footer')
        yield Static(f'Terminal zu klein – mindestens {MIN_WIDTH}×{MIN_HEIGHT}.\n'
                     'Alternativ: picam status', id='small')

    def on_mount(self) -> None:
        self.register_theme(THEME)
        self.theme = 'picam'
        self._build_nav()
        self.query_one('#logpane').display = False
        self.query_one('#configpane').display = False
        self._apply_size()
        self._render_top()
        self._render_footer()
        self._render_detail()
        self.query_one('#nav', OptionList).focus()
        self.action_refresh()
        if self._auto_refresh:
            self.set_interval(REFRESH_S, self.action_refresh)

    def on_resize(self) -> None:
        self._apply_size()
        self._render_top()
        if (self.size.height >= 27) != getattr(self, '_nav_gaps', None):
            selected = self.selected
            self._build_nav()
            self._select_nav(selected)
        self._update_nav()
        self._render_footer()

    def _select_nav(self, key: str) -> None:
        nav = self.query_one('#nav', OptionList)
        try:
            nav.highlighted = nav.get_option_index(key)
        except Exception:  # noqa: BLE001 - Option nicht (mehr) vorhanden
            pass

    def _apply_size(self) -> None:
        width, height = self.size
        screen = self.screen
        screen.set_class(width < MIN_WIDTH or height < MIN_HEIGHT, 'too-small')
        stacked = width < SPLIT_WIDTH
        screen.set_class(stacked, 'stacked')
        nav = self.query_one('#nav')
        if not stacked:
            nav.styles.width = 32 if width >= 100 else 29
            screen.remove_class('open')

    # ------------------------------------------------------------ Liste
    def _nav_entries(self):
        yield 'uebersicht', 'Übersicht', None
        yield '#betrieb', 'Betrieb', None
        for key in probes.OVERVIEW:
            yield key, None, None
        yield '#einrichtung', 'Einrichtung', None
        for key in probes.SETUP:
            if key == 'linger' and self.instance.scope != 'user':
                continue
            yield key, None, None
        yield '#werkzeuge', 'Werkzeuge', None
        for key, label in TOOLS:
            yield key, label, None

    def _nav_width(self) -> int:
        """Nutzbare Zellen einer Zeile (Breite minus Innenabstand links/rechts)."""
        nav = self.query_one('#nav')
        width = nav.size.width or (30 if self.size.width >= 100 else 28)
        return max(16, width - 3)

    def _fact(self, key: str) -> probes.Fact | None:
        if self.snapshot is not None and key in self.snapshot.facts:
            return self.snapshot.facts[key]
        return self._setup_facts.get(key)

    _NAV_LABELS = {'dienst': 'Dienst', 'lauf': 'Lauf', 'kamera': 'Kamera', 'ausgabe': 'Ausgabe',
                   'bruecke': 'Brücke', 'zertifikat': 'Zertifikat', 'speicher': 'Speicher',
                   'vorlage': 'Lesevorlage', 'kalibrierung': 'Kalibrierung', 'uart': 'UART',
                   'konto': 'Konto', 'linger': 'Nach Abmeldung', 'uhr': 'Uhrzeit', 'version': 'Version'}

    def _nav_prompt(self, key: str, label: str | None) -> Text:
        width = self._nav_width()
        if key.startswith('#'):
            return Text(label.upper() if label else '', style=f'bold {MUTED}')

        def row(left: Text, right: Text) -> Text:
            room = width - left.cell_len - 1
            if right.cell_len > room:
                right.truncate(max(1, room), overflow='ellipsis')
            left.append(' ' * max(1, width - left.cell_len - right.cell_len))
            left.append_text(right)
            return left

        if label is not None:  # Übersicht, Werkzeuge
            left = Text('  ' + label)
            if key == 'uebersicht' and self.snapshot is not None:
                problems = self._problems()
                if problems:
                    worst = min((f.level for f in problems), key=probes.LEVEL_ORDER.__getitem__)
                    return row(left, Text(f'{symbol(worst)} {len(problems)}', style=TONE[worst]))
            return left
        fact = self._fact(key)
        name = self._NAV_LABELS.get(key, key)
        if fact is None:
            return row(Text('  ' + name), Text('·', style=MUTED))
        left = Text()
        left.append(symbol(fact.level) + ' ', style=TONE[fact.level])
        left.append(name)
        quiet = fact.level in (probes.OK, probes.OFF)
        return row(left, Text(fact.value, style=MUTED if quiet else TONE[fact.level]))

    def _build_nav(self) -> None:
        nav = self.query_one('#nav', OptionList)
        options = []
        first = True
        self._nav_gaps = self.size.height >= 27
        for key, label, _ in self._nav_entries():
            if key.startswith('#'):
                if not first and self._nav_gaps:
                    options.append(Option('', id=f'{key}-gap', disabled=True))
                options.append(Option(self._nav_prompt(key, label), id=key, disabled=True))
            else:
                options.append(Option(self._nav_prompt(key, label), id=key))
            first = False
        nav.clear_options()
        nav.add_options(options)
        nav.highlighted = 0

    def _update_nav(self) -> None:
        nav = self.query_one('#nav', OptionList)
        for key, label, _ in self._nav_entries():
            try:
                nav.replace_option_prompt(key, self._nav_prompt(key, label))
            except Exception:  # noqa: BLE001 - Option fehlt (z. B. linger), Liste neu bauen
                self._build_nav()
                return

    @on(OptionList.OptionHighlighted, '#nav')
    def _highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id and not event.option.id.startswith('#'):
            if not self.screen.has_class('stacked'):
                self.selected = event.option.id

    @on(OptionList.OptionSelected, '#nav')
    def _chosen(self, event: OptionList.OptionSelected) -> None:
        if event.option.id and not event.option.id.startswith('#'):
            self.selected = event.option.id
            if self.screen.has_class('stacked'):
                self.screen.add_class('open')
                self._render_footer()
            if self.selected == 'konfiguration':
                self._request_config_focus()

    def watch_selected(self) -> None:
        self._rendered_detail = None
        logpane, configpane, detail = (self.query_one('#logpane'), self.query_one('#configpane'),
                                       self.query_one('#detail'))
        logpane.display = self.selected == 'protokoll'
        configpane.display = self.selected == 'konfiguration'
        detail.display = self.selected not in ('protokoll', 'konfiguration')
        if self.selected == 'protokoll':
            self._start_log()
            self._render_log_head()
        elif self.selected == 'konfiguration':
            self._render_config()
        else:
            self._render_detail()
            detail.scroll_home(animate=False)
        self._render_footer()

    # ------------------------------------------------------------ Kopf/Fuß
    def _render_top(self) -> None:
        top = Text()
        top.append('picam', style=f'bold {ACCENT}')
        top.append('  ')
        snap = self.snapshot
        if snap is None:
            top.append('prüfe …', style=MUTED)
        else:
            service = snap.facts['dienst']
            top.append(symbol(service.level) + ' ', style=TONE[service.level])
            top.append(f'Werkbank {service.value}')
            version = self._fact('version')
            room = self.size.width - 2
            for part in ([version.value] if version is not None else []) + (
                    [self.instance.url] if self.instance.url else []):
                piece = Text('  ·  ' + part, style=MUTED)
                if top.cell_len + piece.cell_len > room:
                    break
                top.append_text(piece)
        self.query_one('#top', Static).update(top)

    def _keys(self) -> list[tuple[str, str]]:
        stacked = self.screen.has_class('stacked')
        open_ = self.screen.has_class('open')
        keys = []
        if stacked and not open_:
            keys.append(('enter', 'öffnen'))
        if stacked and open_:
            keys.append(('esc', 'zurück'))
        service = self._fact('dienst')
        blocked = self.snapshot is not None and self.snapshot.stop_blocker is not None
        if service is not None and self.instance.unit is not None and not blocked:
            keys.append(('s', 'stoppen' if service.level in (probes.OK, probes.WARN) else 'starten'))
            keys.append(('r', 'neu starten'))
        if self.selected == 'protokoll':
            keys += [('f', 'mitlaufen ' + ('aus' if self._follow else 'an')),
                     ('e', 'alle' if self._errors_only else 'nur Probleme')]
        else:
            fact = self._fact(self.selected)
            if fact is not None and fact.command and fact.level in (probes.WARN, probes.FAIL):
                keys.append(('a', 'Befehl ausführen'))
            keys += [('l', 'Protokoll'), ('c', 'Konfig.')]
        keys += [('?', 'Hilfe'), ('q', 'Ende')]
        return keys

    def _render_footer(self) -> None:
        width = self.size.width - 2
        text = Text()
        for key, label in self._keys():
            piece = Text()
            piece.append(key, style=f'bold {ACCENT}')
            piece.append(' ' + label + '   ', style='#9aa3ad')
            if text.cell_len + piece.cell_len > width:
                break
            text.append_text(piece)
        self.query_one('#footer', Static).update(text)

    def _render_status(self) -> None:
        text = Text()
        if self._busy:
            text.append('… ' + self._busy, style=ACCENT)
        elif self._message:
            level, message = self._message
            text.append(f'{symbol(level)} {message}', style=TONE[level])
        elif self.snapshot is not None:
            blocker = self.snapshot.stop_blocker
            if blocker and self._fact('dienst') and self._fact('dienst').level == probes.OK:
                text.append(f'Dienstaktionen gesperrt: {blocker}', style=MUTED)
        self.query_one('#status', Static).update(text)

    # ------------------------------------------------------------ Inhalte
    def _problems(self) -> list[probes.Fact]:
        facts = list(self.snapshot.facts.values()) if self.snapshot else []
        facts += [f for k, f in self._setup_facts.items() if not self.snapshot or k not in self.snapshot.facts]
        problems = [f for f in facts if f.level in (probes.FAIL, probes.WARN)]
        return sorted(problems, key=lambda f: probes.LEVEL_ORDER[f.level])

    def _overview(self) -> list:
        parts: list = []
        snap = self.snapshot
        parts.append(Static(Text('Übersicht', style='bold'), classes='title'))
        if snap is None:
            parts.append(Static(Text('Prüfe Dienst, Kamera und Einrichtung …', style=MUTED)))
            return parts
        rows = [('Instanz', self.instance.label)]
        if self.instance.url:
            rows.append(('Werkbank', self.instance.url))
        if self.instance.config:
            rows.append(('Konfiguration', self.instance.config))
        run = snap.facts.get('lauf')
        if run is not None:
            rows.append(('Lauf', run.value))
        if self.instance.problem:
            parts.append(Static(Text(self.instance.problem), classes='hint'))
        problems = self._problems()
        if not problems:
            parts.append(Static(Text(f'{symbol(probes.OK)} Alles in Ordnung.', style=TONE[probes.OK]),
                                classes='hint info'))
        else:
            parts.append(Static(Text(f'{len(problems)} Punkt{"e" if len(problems) != 1 else ""} '
                                     'brauchen Aufmerksamkeit', style='bold')))
            for fact in problems:
                block = Text()
                block.append(f'{symbol(fact.level)} {fact.label}', style=f'bold {TONE[fact.level]}')
                block.append(f'  {fact.value}', style=TONE[fact.level])
                hint = hint_block(fact)
                if hint is not None:
                    block.append('\n')
                    block.append_text(hint)
                parts.append(Static(block, classes='hint fail' if fact.level == probes.FAIL else 'hint'))
        parts.append(Static(Text('INSTANZ', style=f'bold {MUTED}'), classes='section'))
        parts.append(Static(kv_table(rows)))
        return parts

    def _fact_view(self, fact: probes.Fact) -> list:
        parts: list = [Static(fact_title(fact), classes='title')]
        hint = hint_block(fact)
        if hint is not None:
            cls = 'hint fail' if fact.level == probes.FAIL else ('hint' if fact.level == probes.WARN
                                                                  else 'hint info')
            parts.append(Static(hint, classes=cls))
        if fact.detail:
            parts.append(Static(kv_table(fact.detail)))
        actions = self._fact_actions(fact)
        if actions:
            parts.append(Static(actions, classes='actions'))
        return parts

    def _fact_actions(self, fact: probes.Fact) -> Text | None:
        text = Text()
        if fact.key == 'dienst' and self.instance.unit is not None:
            running = fact.level in (probes.OK, probes.WARN)
            text.append('s', style=f'bold {ACCENT}')
            text.append(' stoppen   ' if running else ' starten   ')
            text.append('r', style=f'bold {ACCENT}')
            text.append(' neu starten   ')
            text.append('l', style=f'bold {ACCENT}')
            text.append(' Protokoll')
        elif fact.command and fact.level in (probes.WARN, probes.FAIL):
            text.append('a', style=f'bold {ACCENT}')
            text.append(' Befehl ausführen (mit Rückfrage)')
        elif fact.key == 'lauf':
            text.append('Messläufe startet und beendet die Werkbank im Browser.', style=MUTED)
        return text if text.plain else None

    def _render_detail(self) -> None:
        detail = self.query_one('#detail', Detail)
        if self.selected == 'uebersicht':
            parts = self._overview()
        else:
            fact = self._fact(self.selected)
            if fact is None:
                parts = [Static(Text(self._NAV_LABELS.get(self.selected, self.selected), style='bold'),
                                classes='title'),
                         Static(Text('Wird geprüft …', style=MUTED))]
            else:
                parts = self._fact_view(fact)
        signature = repr([p.renderable if hasattr(p, 'renderable') else p for p in parts])
        if signature == self._rendered_detail:
            return
        self._rendered_detail = signature
        self.call_next(self._swap, detail, parts)

    async def _swap(self, container, parts) -> None:
        with self.batch_update():
            await container.remove_children()
            await container.mount_all(parts)
        if container.id == 'configpane' and self.selected == 'konfiguration' and self._focus_config_pending:
            self._focus_config_pending = False
            self._focus_config()

    # ------------------------------------------------------------ Daten
    def action_refresh(self) -> None:
        self._collect_worker()

    @work(thread=True, exclusive=True, group='collect')
    def _collect_worker(self) -> None:
        import time as _time

        try:
            with_setup = _time.time() - self._setup_at > SETUP_REFRESH_S or not self._setup_facts
            snapshot = self._collect(self.instance, include_setup=with_setup)
        except Exception as error:  # noqa: BLE001 - Anzeige statt Absturz
            self.call_from_thread(self._show_message, probes.FAIL, f'Prüfung fehlgeschlagen: {error}')
            return
        self.call_from_thread(self._apply_snapshot, snapshot, with_setup)

    def _apply_snapshot(self, snapshot: probes.Snapshot, with_setup: bool) -> None:
        import time as _time

        if with_setup:
            self._setup_facts = {k: snapshot.facts[k] for k in probes.SETUP if k in snapshot.facts}
            self._setup_at = _time.time()
        self.snapshot = snapshot
        self._update_nav()
        self._render_top()
        self._render_status()
        self._render_footer()
        if self.selected not in ('protokoll', 'konfiguration'):
            self._render_detail()

    def _show_message(self, level: str, message: str) -> None:
        self._message = (level, message)
        self._render_status()
        self.set_timer(8 if level == probes.OK else 20, self._clear_message)

    def _clear_message(self) -> None:
        self._message = None
        self._render_status()

    # ------------------------------------------------------------ Dienst
    def action_toggle_service(self) -> None:
        service = self._fact('dienst')
        if service is None:
            return
        self._service('stop' if service.level in (probes.OK, probes.WARN) else 'start')

    def action_restart(self) -> None:
        self._service('restart')

    @work(exclusive=True, group='service')
    async def _service(self, action: str) -> None:
        from . import service

        if self.instance.unit is None or self._busy:
            return
        try:
            plan = service.plan(action, self.instance, self.snapshot)
        except ValueError as error:
            self._show_message(probes.FAIL, str(error))
            return
        title, label = SERVICE_WORDS[action]
        lines = []
        if action in ('stop', 'restart'):
            lines.append('Die Werkbank ist danach kurz nicht erreichbar; verbundene Browser und die '
                         'Brücke verbinden sich neu.')
        if plan.note:
            lines.append(plan.note)
        ok = await self.push_screen_wait(ConfirmScreen(Confirmation(
            title, lines, plan.shell(), label, danger=action == 'stop', blocker=plan.blocker)))
        if not ok:
            return
        needs_terminal = any(cmd and cmd[0] == 'sudo' for cmd in plan.commands)
        if needs_terminal:
            with self.suspend():
                print(f'\n{title} – sudo fragt gegebenenfalls nach dem Passwort.\n')
                result = service.execute(plan, self.instance, interactive=True, run=self._service_runner)
            self._finish_service(result)
        else:
            self._busy = {'start': 'starte Dienst, warte auf HTTPS', 'stop': 'stoppe Dienst',
                          'restart': 'starte Dienst neu, warte auf HTTPS'}[action]
            self._render_status()
            self._service_thread(plan)

    @work(thread=True, exclusive=True, group='service-run')
    def _service_thread(self, plan) -> None:
        from . import service

        result = service.execute(plan, self.instance, interactive=False, run=self._service_runner,
                                 echo=lambda _line: None)
        self.call_from_thread(self._finish_service, result)

    def _finish_service(self, result: tuple[bool, str]) -> None:
        ok, message = result
        self._busy = None
        self._show_message(probes.OK if ok else probes.FAIL, message)
        self._setup_at = 0.0
        self.action_refresh()

    # ------------------------------------------------------------ Abhilfe
    @work(exclusive=True, group='fix')
    async def action_run_fix(self) -> None:
        fact = self._fact(self.selected)
        if fact is None or not fact.command or fact.level not in (probes.WARN, probes.FAIL):
            return
        ok = await self.push_screen_wait(ConfirmScreen(Confirmation(
            f'{fact.label}: Befehl ausführen', [fact.hint] if fact.hint else [], [fact.command],
            'Ausführen')))
        if not ok:
            return
        with self.suspend():
            print(f'\n$ {fact.command}\n')
            code = subprocess.call(fact.command, shell=True, cwd=self.instance.root or None)
            print(f'\nExit {code}. Enter drücken, um zur Konsole zurückzukehren.')
            try:
                input()
            except EOFError:
                pass
        self._show_message(probes.OK if code == 0 else probes.FAIL,
                           f'{fact.command} → Exit {code}')
        self._setup_at = 0.0
        self.action_refresh()

    # ------------------------------------------------------------ Protokoll
    def _start_log(self) -> None:
        if self._log_thread is not None and self._log_thread.is_alive():
            return
        log = self.query_one('#log', RichLog)
        log.clear()
        self._log_lines.clear()
        self._log_thread = threading.Thread(target=self._log_reader, daemon=True)
        self._log_thread.start()

    def _log_reader(self) -> None:
        from . import service

        if self._journal_source is not None:
            for line in self._journal_source():
                self.call_from_thread(self._add_log, line)
            return
        try:
            command = service.journal_command(self.instance, 300, follow=True)
            self._log_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                 text=True, bufsize=1)
        except (ValueError, OSError) as error:
            self.call_from_thread(self._add_log, service.LogLine('', 'fehler', f'Protokoll nicht lesbar: {error}'))
            return
        assert self._log_process.stdout is not None
        for raw in self._log_process.stdout:
            for line in service.parse_journal(raw):
                self.call_from_thread(self._add_log, line)
        err = self._log_process.stderr.read() if self._log_process.stderr else ''
        if err.strip():
            self.call_from_thread(self._add_log, service.LogLine('', 'fehler', err.strip()))

    def _log_text(self, line) -> Table:
        style = {'fehler': TONE[probes.FAIL], 'warnung': TONE[probes.WARN], 'debug': MUTED}.get(line.level, '')
        row = Table.grid(padding=(0, 2), expand=True)
        row.add_column(width=8, style=MUTED, no_wrap=True)
        row.add_column(ratio=1, overflow='fold')
        row.add_row(line.time, Text(line.text, style=style))
        return row

    def _add_log(self, line) -> None:
        self._log_lines.append(line)
        if len(self._log_lines) > LOG_LIMIT:
            del self._log_lines[: len(self._log_lines) - LOG_LIMIT]
        if self._errors_only and line.level not in ('fehler', 'warnung'):
            return
        log = self.query_one('#log', RichLog)
        log.write(self._log_text(line), scroll_end=self._follow)

    def _render_log_head(self) -> None:
        head = Text()
        head.append('Protokoll', style='bold')
        unit = self.instance.unit or '–'
        head.append(f'   {unit}', style=MUTED)
        state = []
        state.append('läuft mit' if self._follow else 'angehalten')
        if self._errors_only:
            state.append('nur Warnungen und Fehler')
        head.append('   ' + ' · '.join(state), style=ACCENT if self._follow else TONE[probes.WARN])
        self.query_one('#log-head', Static).update(head)

    def action_toggle_follow(self) -> None:
        if self.selected != 'protokoll':
            return
        self._follow = not self._follow
        log = self.query_one('#log', RichLog)
        log.auto_scroll = self._follow
        if self._follow:
            log.scroll_end(animate=False)
        self._render_log_head()
        self._render_footer()

    def action_toggle_errors(self) -> None:
        if self.selected != 'protokoll':
            return
        self._errors_only = not self._errors_only
        log = self.query_one('#log', RichLog)
        log.clear()
        for line in self._log_lines:
            if not self._errors_only or line.level in ('fehler', 'warnung'):
                log.write(self._log_text(line), scroll_end=False)
        if self._follow:
            log.scroll_end(animate=False)
        self._render_log_head()
        self._render_footer()

    # ------------------------------------------------------------ Konfiguration
    def _render_config(self) -> None:
        from . import configedit

        pane = self.query_one('#configpane', ConfigPane)
        parts: list = [Static(Text('Konfiguration', style='bold'), classes='title')]
        inst = self.instance
        if inst.config is None:
            parts.append(Static(Text('Entwicklungsbetrieb: Werte stammen aus dem Startbefehl des Dienstes '
                                     '(scripts/werkbank-dienst.sh). Eine installierte Werkbank hat dafür '
                                     'eine config.toml, die hier änderbar ist.'), classes='hint info'))
            rows = [('Adresse', inst.host or '–'), ('Port', str(inst.port or '–')),
                    ('Steuerung', inst.socket or '–'), ('Daten', inst.data or '–'),
                    ('Laufdaten', inst.live_data or '–'), ('Brücke', inst.bridge_directory or '–'),
                    ('Code', inst.root or '–')]
            parts.append(Static(kv_table(rows)))
        else:
            rows = [('Datei', inst.config), ('Adresse', inst.host or '–'), ('Anmeldung', inst.pam_user or '–'),
                    ('Daten', inst.data or '–'), ('Laufdaten', inst.live_data or '–')]
            parts.append(Static(kv_table(rows)))
            parts.append(Static('Die Adresse steht im Zertifikat und in den Kopplungen und wird nur '
                                'bei einer Neuinstallation gewählt.', classes='note'))
            labels = {'port': 'Port der Werkbank (1–65535)', 'bridge_name': 'Name des Pi in der Windows-Brücke',
                      'bridge_discovery': 'Im Netzwerk ankündigen (Windows-App findet den Pi selbst)'}
            for key in configedit.EDITABLE:
                label = labels[key]
                current = getattr(inst, key)
                field = Vertical(classes='field')
                field.compose_add_child(Static(label, classes='field-label'))
                if key == 'bridge_discovery':
                    field.compose_add_child(Checkbox('angekündigt', value=bool(current), id=f'cfg-{key}'))
                else:
                    field.compose_add_child(Input(value='' if current is None else str(current),
                                                  id=f'cfg-{key}', placeholder='nicht gesetzt'))
                parts.append(field)
            parts.append(Button('Änderung prüfen …', id='config-check'))
        self.call_next(self._swap, pane, parts)

    _focus_config_pending = False

    def _request_config_focus(self) -> None:
        self._focus_config_pending = True
        self.call_after_refresh(self._focus_config_if_ready)

    def _focus_config_if_ready(self) -> None:
        if self.query('#cfg-port'):
            self._focus_config_pending = False
            self._focus_config()

    def _focus_config(self) -> None:
        try:
            self.query_one('#cfg-port', Input).focus()
        except Exception:  # noqa: BLE001 - keine Felder (Entwicklungsbetrieb)
            pass

    @on(Button.Pressed, '#config-check')
    def _config_check(self) -> None:
        self._config_flow()

    @work(exclusive=True, group='config')
    async def _config_flow(self) -> None:
        from . import configedit

        inst = self.instance
        if inst.config is None:
            return
        proposals = []
        for key in configedit.EDITABLE:
            widget = self.query_one(f'#cfg-{key}')
            raw = ('true' if widget.value else 'false') if isinstance(widget, Checkbox) else widget.value
            current = getattr(inst, key)
            if key != 'bridge_discovery' and raw.strip() == ('' if current is None else str(current)):
                continue
            if key == 'bridge_discovery' and bool(widget.value) == bool(current):
                continue
            proposals.append((key, raw))
        if not proposals:
            self._show_message(probes.OFF, 'Keine Änderung.')
            return
        text_lines, commands = [], []
        try:
            new_text = None
            for key, raw in proposals:
                new_text, changes = configedit.propose(inst.config, key, raw)
                text_lines += [c.text for c in changes]
                commands.append(f'picam config set {key} {shlex.quote(raw)}')
                if len(proposals) > 1:
                    break
        except (ValueError, OSError) as error:
            self._show_message(probes.FAIL, str(error))
            return
        if len(proposals) > 1:
            self._show_message(probes.WARN, 'Bitte ein Feld nach dem anderen ändern.')
            return
        writable = os.access(inst.config, os.W_OK)
        lines = text_lines + ['Wirksam nach einem Neustart des Dienstes (r).']
        if not writable:
            lines.append('Die Datei gehört root: picam führt die Änderung mit sudo aus.')
        ok = await self.push_screen_wait(ConfirmScreen(Confirmation(
            'Konfiguration ändern', lines, commands if not writable else [], 'Übernehmen')))
        if not ok:
            return
        key, raw = proposals[0]
        if writable:
            try:
                configedit.apply(inst.config, new_text)
            except OSError as error:
                self._show_message(probes.FAIL, str(error))
                return
            code = 0
        else:
            command = ['sudo', sys.executable, '-m', 'dispread.admin.cli', '--config', inst.config,
                       'config', 'set', key, raw, '--yes']
            with self.suspend():
                code = subprocess.call(command)
        if code == 0:
            from .instance import discover

            self.instance = discover(inst.config)
            self._render_config()
            self._show_message(probes.OK, 'Gespeichert. Mit r neu starten, damit es wirkt.')
        else:
            self._show_message(probes.FAIL, f'Nicht gespeichert (Exit {code}).')

    # ------------------------------------------------------------ Tasten
    def action_show(self, key: str) -> None:
        nav = self.query_one('#nav', OptionList)
        try:
            nav.highlighted = nav.get_option_index(key)
        except Exception:  # noqa: BLE001
            return
        self.selected = key
        if self.screen.has_class('stacked'):
            self.screen.add_class('open')
        self._render_footer()
        if key == 'konfiguration':
            self._request_config_focus()

    def action_go_back(self) -> None:
        if self.screen.has_class('stacked') and self.screen.has_class('open'):
            self.screen.remove_class('open')
            self.query_one('#nav', OptionList).focus()
            self._render_footer()
        elif self.focused is not None and self.focused.id != 'nav':
            self.query_one('#nav', OptionList).focus()

    def action_nav_down(self) -> None:
        if isinstance(self.focused, Input):
            return
        self.query_one('#nav', OptionList).action_cursor_down()

    def action_nav_up(self) -> None:
        if isinstance(self.focused, Input):
            return
        self.query_one('#nav', OptionList).action_cursor_up()

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_open_url(self) -> None:
        if self.instance.url:
            self._show_message(probes.OK, self.instance.url)

    def action_quit_app(self) -> None:
        self._stop_log()
        self.exit(0)

    def _stop_log(self) -> None:
        process = self._log_process
        if process is not None and process.poll() is None:
            process.terminate()

    def on_unmount(self) -> None:
        self._stop_log()


def run(instance: Instance) -> int:
    app = PicamApp(instance)
    result = app.run()
    return 0 if result is None else int(result)


def snapshot_json(app: PicamApp) -> str:
    return json.dumps(app.snapshot.to_json() if app.snapshot else {}, ensure_ascii=False)
