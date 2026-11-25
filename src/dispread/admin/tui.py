"""picam-Konsole: Verwaltung und Fehlersuche für die Werkbank (Textual 2.x).

Oben die Tabs (Dashboard, Lauf, Dienst, Kamera, Ausgabe, Zertifikat,
Speicher, Netzwerk, UART, Konto, Protokoll, Einstellungen), darunter der
Inhalt, unten Statuszeile und Tastenleiste. Die Tabs liegen in
``dispread.admin.views``; hier stehen Datenabruf, Aktionen mit Bestätigung,
Fehler-Popups und das Startbild.

Die Konsole ist kein zweites Bedienpult: Läufe und Einrichtung steuert die
Werkbank im Browser. Dienst- und Kameraaktionen sind gesperrt, solange ein
Lauf, eine Einrichtung oder eine Diagnosekopie aktiv ist.
"""

from __future__ import annotations

import json
import os
import select
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import ContentSwitcher, Input, Static, Tab, Tabs

from . import probes
from .instance import Instance
from .ui import (  # noqa: F401  (für Tests und Tabs erneut exportiert)
    ACCENT,
    MUTED,
    SOFT,
    SPINNER,
    TEXT,
    THEME,
    TONE,
    AskScreen,
    Canvas,
    Choice,
    Confirmation,
    ConfirmScreen,
    InfoScreen,
    P,
    ascii_mode,
    fade_in,
    symbol,
)
from .views import TABS

MIN_WIDTH, MIN_HEIGHT = 48, 14
SPLIT_WIDTH = 76
TALL_HEIGHT = 34
REFRESH_S = 5.0
SETUP_REFRESH_S = 60.0
STORAGE_REFRESH_S = 60.0
NETWORK_REFRESH_S = 30.0
LOG_LIMIT = 2000
SERVICE_WORDS = {'start': ('Werkbank starten', 'Starten'), 'stop': ('Werkbank stoppen', 'Stoppen'),
                 'restart': ('Werkbank neu starten', 'Neu starten')}
#: Befunde, deren Wechsel auf Fehler ein Popup öffnet.
ALERT_FACTS = ('dienst', 'kamera', 'ausgabe', 'lauf')

CSS_PATH_FREE = """
Screen { background: $picam-canvas; layers: base overlay; }
#top { height: 1; background: $picam-band; }
#brand { width: auto; padding: 0 1; height: 1; background: $picam-accent-deep; color: $picam-on-accent-deep;
         text-style: bold; }
#tabs { width: 1fr; height: 1; background: $picam-band; }
#tabs Tab { padding: 0 1; height: 1; color: $picam-text-soft; text-style: none; }
#tabs Tab.-active { color: $picam-on-accent; text-style: bold underline; background: $picam-accent-strong; }
#tabs Tab:hover { color: $picam-text; background: $picam-control; }
#tabs Tab.-active:hover { color: $picam-on-accent; background: $picam-accent; }
#tabs .underline--bar { color: $picam-accent-strong; background: $picam-band; }
#rule { height: 1; }
#body { height: 1fr; padding: 0 2; }
TabView { height: 1fr; scrollbar-size-vertical: 1; }
TabView > Static { width: 1fr; max-width: 120; }
TabView.own-bar { overflow-y: hidden; }
.tab-body { height: 1fr; width: 1fr; scrollbar-size-vertical: 1; }
.actionbar Button { margin: 0 2 0 0; padding: 0 1 0 0; min-width: 8; width: auto; }
.actionbar.-grid Button { width: 100%; margin: 0; content-align: left middle; text-align: left; }
.buttons { height: auto; margin: 1 0 1 0; }
.buttons Button { margin: 0 2 0 0; }
#dash { height: auto; }
#dash-left { width: 1fr; height: auto; padding: 1 2 0 0; }
#dash-right { width: 42; height: auto; padding: 0 0 0 0; }
#dash-logo { height: auto; margin: 1 0 0 0; }
#dash-run { height: auto; margin: 1 0 0 0; }
#dash-warn { height: auto; margin: 1 0 0 0; }
#dash-areas { height: auto; margin: 1 0 0 0; padding: 0 1; background: $picam-surface; }
#dash-areas.plain { background: $picam-canvas; padding: 0; }
#areas-head { height: 1; width: 1fr; }
#dash-warn, #dash-run, #tail-head { width: 1fr; }
#dash-list { height: auto; max-height: 20; border: none; background: transparent; padding: 0; }
#dash-list:focus { border: none; background-tint: 0%; }
#dash-list > .option-list--option { padding: 0 1; }
#dash-tail { display: none; height: auto; margin: 1 0 0 0; padding: 0 1; background: $picam-surface; }
#tail-head { height: 1; }
#tail-log { height: 12; background: transparent; border: none; scrollbar-size-vertical: 1; padding: 0;
            overflow-x: hidden; }
Screen.tall #dash-tail { display: block; }
Screen.stacked #dash { layout: vertical; }
Screen.stacked #dash-right { width: 1fr; padding: 0; }
Screen.stacked #dash-logo { display: none; }
#log-head { height: 1; margin: 1 0 0 0; }
#log { height: 1fr; background: $picam-surface; border: none; border-left: wide $picam-surface;
       scrollbar-size-vertical: 1; padding: 0 1; overflow-x: hidden; }
#log:focus { border-left: wide $picam-accent-strong; background-tint: 0%; }
ProtokollView { overflow-y: hidden; }
#log, #tail-log { scrollbar-background: $picam-surface; scrollbar-background-hover: $picam-surface;
                 scrollbar-background-active: $picam-surface; }
#dash-tail:focus-within #tail-log { scrollbar-background: $picam-raised; }
.field { height: auto; margin: 1 0 0 0; }
.field-label { color: $picam-text-muted; }
.field-risk { margin: 0; }
.field Input { width: 40; height: 1; margin: 0; padding: 0 1; border: none; background: $picam-field;
               color: $picam-text; }
.field Input:focus { border: none; background: $picam-field-focus; }
.field Checkbox { margin: 0; height: 1; padding: 0; border: none; background: transparent; }
.field Checkbox:focus { border: none; background-tint: 0%; }
.field Checkbox > .toggle--button { background: $picam-field; color: $picam-field; }
.field Checkbox.-on > .toggle--button { background: $picam-accent-strong; color: $picam-on-accent; }
.field Checkbox:focus > .toggle--label { text-style: bold underline; background: transparent; }
#status { height: 1; width: 1fr; padding: 0 1; background: $picam-band; }
#footer { height: 1; width: 1fr; padding: 0 1; background: $picam-band; }
#small { display: none; width: 1fr; height: 1fr; content-align: center middle; color: $picam-text-muted; }
Screen.too-small #small { display: block; }
Screen.too-small #top, Screen.too-small #body, Screen.too-small #status, Screen.too-small #footer {
    display: none; }
ConfirmScreen, AskScreen, InfoScreen { align: center middle; background: $picam-backdrop; }
#dialog { width: 76; max-width: 95%; height: auto; padding: 1 2; background: $picam-raised;
          border: none; border-top: tall $picam-accent-strong; }
#dialog.fail { border-top: tall $error; }
#dialog.warn { border-top: tall $warning; }
#dialog-title { margin: 0 0 1 0; }
.dialog-line { margin: 0 0 1 0; }
#dialog-cmd { margin: 0 0 1 0; padding: 0 1; background: $picam-field; color: $picam-text-soft; }
#dialog-blocker { margin: 0 0 1 0; }
#ask-input { height: 1; border: none; padding: 0 1; margin: 0 0 1 0; background: $picam-field; }
#ask-input:focus { background: $picam-field-focus; }
#dialog-buttons { height: auto; align-horizontal: right; }
#dialog-buttons Button { margin: 0 0 0 2; }
Button { border: none; height: 1; min-width: 12; padding: 0 2; background: $picam-control; color: $picam-text;
         text-style: none; }
Button:hover { background: $picam-control-hover; }
Button:focus { background: $picam-accent-strong; color: $picam-on-accent; text-style: bold; background-tint: 0%; }
Button.-primary { background: $picam-accent-deep; color: $picam-on-accent-deep; }
Button.-primary:focus { background: $picam-accent-strong; color: $picam-on-accent; }
Button.-error { color: $error; }
Button.-error:focus { background: $error; color: $picam-on-accent; }
Button:disabled { color: $picam-disabled-fg; background: $picam-disabled-bg; }
Intro { layer: overlay; width: 1fr; height: 1fr; align: center middle; background: $picam-canvas; }
Intro:focus { background-tint: 0%; }
#intro-row { width: 1fr; height: auto; align: center top; }
#intro-logo { margin: 0 5 0 0; }
#intro-side { width: auto; height: auto; }
#intro-lcd { width: auto; height: auto; margin: 0 0 1 0; }
#intro-tag { width: auto; margin: 0 0 1 0; }
#intro-checks { width: 46; height: 3; }
#intro-hint { width: 1fr; content-align: center middle; margin: 1 0 0 0; }
"""


class HelpScreen(InfoScreen):
    KEYS = (
        ('Tab  ⇧Tab', 'nächster / voriger Tab (oder Klick auf den Tab)'),
        ('1 … 9  0', 'Dashboard, Lauf, Dienst, Kamera, Ausgabe, Zertifikat, Speicher, Netzwerk, UART, Konto'),
        ('l   c', 'Protokoll, Einstellungen'),
        ('↑ ↓ ← →', 'im Tab: Knopf, Listeneintrag oder Feld wählen'),
        ('Enter', 'Knopf oder Listeneintrag auslösen'),
        ('i', 'Erklärung zum aktuellen Tab'),
        ('g', 'jetzt neu prüfen'),
        ('Esc', 'zurück zum Dashboard / Dialog schließen'),
        ('q  Ctrl+C', 'beenden'),
    )

    def __init__(self):
        table = Table.grid(padding=(0, 3))
        table.add_column(style=f'bold {ACCENT}', no_wrap=True)
        table.add_column()
        for key, text in self.KEYS:
            table.add_row(key, text)
        note = Text('Die Tasten des aktuellen Tabs stehen in der untersten Zeile. Messläufe und Einrichtung '
                    'laufen in der Werkbank im Browser.', style=MUTED)
        super().__init__('Tasten', [table, note])


class PicamApp(App[int]):
    TITLE = 'picam'
    CSS = CSS_PATH_FREE

    BINDINGS = [
        Binding('q', 'quit_app', 'Ende'),
        Binding('ctrl+c', 'quit_app', 'Ende', show=False, priority=True),
        Binding('question_mark,f1', 'help', 'Hilfe'),
        Binding('i', 'info', 'Info', show=False),
        Binding('g', 'refresh', 'Prüfen', show=False),
        Binding('escape', 'go_back', 'Zurück', show=False),
        Binding('tab', 'tab_step(1)', 'Tabs', show=False, priority=True),
        Binding('shift+tab', 'tab_step(-1)', show=False, priority=True),
        Binding('up,left', 'focus_step(-1)', show=False),
        Binding('down,right', 'focus_step(1)', show=False),
        *[Binding(view.KEY, f'open_tab("{view.TAB_ID}")', show=False) for view in TABS if view.KEY],
    ]

    def __init__(self, instance: Instance, collect=probes.collect, journal_source=None,
                 service_runner=None, auto_refresh: bool = True, intro: bool = False,
                 socket_request=None, metrics_source=None, storage_source=None, network_source=None,
                 popups: bool = True):
        super().__init__()
        self.instance = instance
        self._collect = collect
        self._journal_source = journal_source
        self._service_runner = service_runner
        self._auto_refresh = auto_refresh
        self._intro_enabled = intro
        self._socket = socket_request or probes.socket_request
        self._metrics_source = metrics_source or probes.system_metrics
        self._storage_source = storage_source or probes.storage_usage
        self._network_source = network_source or probes.network_info
        self._popups = popups
        self.snapshot: probes.Snapshot | None = None
        self._setup_facts: dict[str, probes.Fact] = {}
        self._setup_at = 0.0
        self.metrics: dict = {}
        self.storage: dict | None = None
        self.network: dict | None = None
        self._busy: str | None = None
        self._message: tuple[str, str] | None = None
        self.log_lines: list = []
        self._log_thread: threading.Thread | None = None
        self._log_process: subprocess.Popen | None = None
        self._alerted: dict[str, tuple[str, str]] = {}
        self._spin = 0
        self._spinner_timer = None
        self.current = 'dashboard'

    def get_theme_variable_defaults(self) -> dict[str, str]:
        """Palettenvariablen ($picam-…) schon vor dem Umschalten aufs picam-Theme bekannt machen."""
        return {**super().get_theme_variable_defaults(), **P.variables()}

    @property
    def main_screen(self):
        """Konsolenbildschirm, auch während ein Dialog darüber liegt."""
        return self.screen_stack[0] if self.screen_stack else self.screen

    # ------------------------------------------------------------ Aufbau
    def compose(self) -> ComposeResult:
        with Horizontal(id='top'):
            yield Static(Text('picam', style='bold'), id='brand')
            yield Tabs(*[Tab(view.TITLE, id=f'tab-{view.TAB_ID}') for view in TABS], id='tabs')
        with ContentSwitcher(id='body', initial='dashboard'):
            for view in TABS:
                yield view(id=view.TAB_ID)
        yield Canvas(id='status')
        yield Canvas(id='footer')
        yield Static(f'Terminal zu klein – mindestens {MIN_WIDTH}×{MIN_HEIGHT}.\n'
                     'Alternativ: picam status', id='small')
        if self._intro_enabled:
            from .intro import Intro

            yield Intro(self.instance.label, None, ascii_mode(), self.animation_level != 'none', id='intro')

    def on_mount(self) -> None:
        self.register_theme(THEME)
        self.theme = 'picam'
        self._apply_size()
        self.metrics = self._metrics_source()
        self._render_status()
        self.refresh_footer()
        self.view().update_view()
        tabs = self.main_screen.query_one('#tabs', Tabs)
        tabs.can_focus = False  # Tabs per Tab-Taste/Ziffer/Maus; Pfeile bleiben im Tab
        if not self._intro_enabled:
            self.call_after_refresh(self.focus_view)
        if self._intro_enabled:
            intro = self.main_screen.query_one('#intro')
            intro.set_lines(self._intro_lines())
            intro.on_done = self._end_intro
            intro.focus()
        self._spinner_timer = self.set_interval(0.1, self._spin_tick, pause=True)
        self._sync_spinner()
        self.action_refresh()
        if not self._intro_enabled:
            self._start_background()

    def _start_background(self) -> None:
        """Protokoll, Speicher und Netzwerk erst nach dem Startbild laden (sonst ruckelt es)."""
        if getattr(self, '_background_started', False):
            return
        self._background_started = True
        self._start_log()
        if self._auto_refresh:
            self.set_interval(REFRESH_S, self.action_refresh)
            self.set_interval(STORAGE_REFRESH_S, self._storage_worker)
            self.set_interval(NETWORK_REFRESH_S, self._network_worker)
        self._storage_worker()
        self._network_worker()

    # ------------------------------------------------------------ Tabs
    def view(self, tab_id: str | None = None):
        return self.main_screen.query_one(f'#{tab_id or self.current}')

    def open_tab(self, tab_id: str) -> None:
        self.main_screen.query_one('#tabs', Tabs).active = f'tab-{tab_id}'

    def action_open_tab(self, tab_id: str) -> None:
        if isinstance(self.focused, Input):
            return
        self.open_tab(tab_id)

    def action_tab_step(self, step: int) -> None:
        if len(self.screen_stack) > 1:  # im Dialog: Tab bewegt wie gewohnt den Fokus
            (self.screen.focus_next if step > 0 else self.screen.focus_previous)()
            return
        if self.main_screen.query('#intro'):
            return
        ids = [view.TAB_ID for view in TABS]
        self.open_tab(ids[(ids.index(self.current) + step) % len(ids)])

    def _view_focusables(self) -> list:
        view = self.view()
        return [widget for widget in self.main_screen.focus_chain
                if widget is not view and view in widget.ancestors]

    def focus_view(self) -> None:
        """Fokus auf das erste bedienbare Element des Tabs (sonst nirgends)."""
        widgets = self._view_focusables()
        if widgets:
            widgets[0].focus()
        else:
            self.set_focus(None)

    def action_focus_step(self, step: int) -> None:
        """Pfeiltasten: nächstes/voriges Element im Tab (Knöpfe, Liste, Felder)."""
        if len(self.screen_stack) > 1:
            (self.screen.focus_next if step > 0 else self.screen.focus_previous)()
            return
        widgets = self._view_focusables()
        if not widgets:
            return
        if self.focused not in widgets:
            widgets[0 if step > 0 else -1].focus()
            return
        index = widgets.index(self.focused) + step
        if 0 <= index < len(widgets):
            widgets[index].focus()
            widgets[index].scroll_visible()

    @on(Tabs.TabActivated, '#tabs')
    def _tab_activated(self, event: Tabs.TabActivated) -> None:
        tab_id = (event.tab.id or 'tab-dashboard')[4:]
        switcher = self.main_screen.query_one('#body', ContentSwitcher)
        if tab_id == self.current and switcher.current == tab_id:
            return
        self.current = tab_id
        switcher.current = tab_id
        view = self.view()
        view.update_view()
        fade_in(view, start=0.35, duration=0.15)
        self.call_after_refresh(view.focus_first if tab_id == 'einstellungen' else self.focus_view)
        self.refresh_footer()

    def action_go_back(self) -> None:
        if self.current != 'dashboard':
            self.open_tab('dashboard')
        else:
            self.focus_view()

    def action_info(self) -> None:
        if isinstance(self.focused, Input):
            return
        view = self.view()
        if view.INFO:
            self.show_info(view.INFO_TITLE or view.TITLE, list(view.INFO))

    def on_key(self, event) -> None:
        """Tasten des aktuellen Tabs (stehen in der Tastenleiste)."""
        if isinstance(self.focused, Input) or len(self.screen_stack) > 1:
            return
        if self.main_screen.query('#intro'):
            return
        for action in self.view().actions():
            if action.key == event.key:
                event.stop()
                if action.blocked:
                    self.message(probes.WARN, f'{action.label}: {action.blocked}')
                else:
                    action.run()
                return

    # ------------------------------------------------------------ Größe
    def on_resize(self) -> None:
        self._apply_size()
        self.refresh_footer()
        self.view().update_view()

    def _apply_size(self) -> None:
        width, height = self.size
        screen = self.main_screen
        screen.set_class(width < MIN_WIDTH or height < MIN_HEIGHT, 'too-small')
        screen.set_class(width < SPLIT_WIDTH, 'stacked')
        screen.set_class(height >= TALL_HEIGHT and width >= SPLIT_WIDTH, 'tall')

    # ------------------------------------------------------------ Kopf/Fuß
    def refresh_footer(self) -> None:
        width = self.size.width - 2
        text = Text()
        pieces = []
        chip, chip_dim = f'bold {ACCENT} on {P.raised}', f'{P.disabled_fg} on {P.band}'
        view = self.view()
        for action in ([] if view.OWN_BAR else view.actions()):
            dim = action.blocked is not None
            pieces.append((action.key, action.label, chip_dim if dim else chip, P.disabled_fg if dim else TEXT))
        pieces += [(key, label, chip, SOFT) for key, label in
                   (('Tab', 'Tabs'), ('↑↓', 'Auswahl'), ('i', 'Info'), ('?', 'Hilfe'), ('q', 'Ende'))]
        for key, label, key_style, label_style in pieces:
            piece = Text()
            piece.append(f' {key} ', style=key_style)
            piece.append(' ' + label + '  ', style=label_style)
            if text.cell_len + piece.cell_len > width:
                break
            text.append_text(piece)
        footer = self._line('#footer')
        if footer is not None:
            footer.show(text)

    def _render_status(self) -> None:
        text = Text()
        if self._busy:
            text.append(f'{self._spinner()} {self._busy}', style=ACCENT)
        elif self._message:
            level, message = self._message
            text.append(f'{symbol(level)} {message}', style=TONE[level])
        elif self.snapshot is None:
            text.append(f'{self._spinner()} prüfe Dienst, Kamera und Einrichtung …', style=MUTED)
        else:
            service = self.snapshot.facts['dienst']
            text.append(f'{symbol(service.level)} ', style=TONE[service.level])
            text.append(f'Werkbank {service.value}', style=MUTED)
            if self.instance.url:
                text.append(f'  ·  {self.instance.url}', style=MUTED)
            blocker = self.snapshot.stop_blocker
            if blocker and service.level == probes.OK:
                text.append(f'  ·  Dienstaktionen gesperrt: {blocker}', style=TONE[probes.WARN])
        status = self._line('#status')
        if status is not None:
            status.show(text)

    # ------------------------------------------------------------ Startbild
    def _intro_lines(self) -> list[tuple[str, str, str, str]]:
        level = probes.WARN if self.instance.problem else probes.OK
        lines = [(symbol(level), TONE[level], 'Instanz', self.instance.label)]
        if self.snapshot is None:
            return lines + [('spin', '', 'Dienst', 'prüfe …'), ('spin', '', 'Einrichtung', 'prüfe …')]
        service = self.snapshot.facts['dienst']
        lines.append((symbol(service.level), TONE[service.level], 'Dienst', service.value))
        problems = self.problems()
        if problems:
            worst = problems[0].level
            lines.append((symbol(worst), TONE[worst], 'Hinweise', f'{len(problems)} offen'))
        else:
            lines.append((symbol(probes.OK), TONE[probes.OK], 'Einrichtung', 'alles in Ordnung'))
        return lines

    def _end_intro(self) -> None:
        intro = self.main_screen.query('#intro')
        if not intro:
            return
        widget = intro.first()

        def reveal() -> None:
            widget.remove()
            self.call_after_refresh(self._start_background)
            self.call_after_refresh(self._sync_spinner)
            self.call_after_refresh(self.focus_view)
            for selector in ('#top', '#body', '#status', '#footer'):
                fade_in(self.main_screen.query_one(selector), duration=0.3)
            self.call_after_refresh(self._maybe_alert)

        if self.animation_level == 'none':
            reveal()
        else:
            widget.styles.animate('opacity', 0.0, duration=0.22, easing='in_cubic', on_complete=reveal)

    # ------------------------------------------------------------ Bewegung
    def _sync_spinner(self) -> None:
        if self._spinner_timer is None:
            return
        active = ((self._busy is not None or self.snapshot is None) and self.animation_level != 'none'
                  and not self.main_screen.query('#intro'))
        if active:
            self._spinner_timer.resume()
        else:
            self._spinner_timer.pause()

    def _spin_tick(self) -> None:
        self._spin = (self._spin + 1) % len(SPINNER)
        self._render_status()

    def _spinner(self) -> str:
        if ascii_mode() or self.animation_level == 'none':
            return '…'
        return SPINNER[self._spin]

    # ------------------------------------------------------------ Daten für Tabs
    def fact(self, key: str) -> probes.Fact | None:
        if self.snapshot is not None and key in self.snapshot.facts:
            return self.snapshot.facts[key]
        return self._setup_facts.get(key)

    _fact = fact

    def setup_facts(self) -> dict[str, probes.Fact]:
        return dict(self._setup_facts)

    def first_setup_tab(self) -> str:
        homes = {'netzwerk': 'netzwerk', 'uhr': 'netzwerk', 'vorlage': 'kamera', 'kalibrierung': 'kamera',
                 'uart': 'uart', 'konto': 'konto', 'linger': 'konto', 'version': 'dienst'}
        for key, fact in self._setup_facts.items():
            if fact.level in (probes.FAIL, probes.WARN):
                return homes.get(key, 'dashboard')
        return 'dienst'

    def problems(self) -> list[probes.Fact]:
        facts = list(self.snapshot.facts.values()) if self.snapshot else []
        facts += [f for k, f in self._setup_facts.items() if not self.snapshot or k not in self.snapshot.facts]
        problems = [f for f in facts if f.level in (probes.FAIL, probes.WARN)]
        return sorted(problems, key=lambda f: probes.LEVEL_ORDER[f.level])

    @property
    def blocker(self) -> str | None:
        if self.snapshot is None:
            return 'Laufstatus noch nicht geprüft'
        return self.snapshot.stop_blocker

    def installed(self) -> bool:
        root = self.instance.root or ''
        return self.instance.kind in ('system', 'user') and Path(root).parent.name == 'releases'

    def ascii(self) -> bool:
        return ascii_mode()

    def _line(self, selector: str):
        """Status-/Tastenzeile oder None (z. B. beim Beenden, wenn ein Worker spät antwortet)."""
        found = self.main_screen.query(selector)
        return found.first() if found else None

    def message(self, level: str, message: str) -> None:
        self._message = (level, message)
        self._render_status()
        status = self._line('#status')
        if status is not None:
            fade_in(status, start=0.2, duration=0.2)
        self.set_timer(8 if level in (probes.OK, probes.OFF) else 20, self._clear_message)

    _show_message = message

    def _clear_message(self) -> None:
        self._message = None
        self._render_status()

    def show_info(self, title: str, lines: list, choices=None, tone=None, callback=None) -> None:
        self.push_screen(InfoScreen(title, lines, choices, tone), callback=callback)

    # ------------------------------------------------------------ Abruf
    def action_refresh(self) -> None:
        self._collect_worker()

    @work(thread=True, exclusive=True, group='collect')
    def _collect_worker(self) -> None:
        try:
            with_setup = time.time() - self._setup_at > SETUP_REFRESH_S or not self._setup_facts
            snapshot = self._collect(self.instance, include_setup=with_setup)
            metrics = self._metrics_source()
        except Exception as error:  # noqa: BLE001 - Anzeige statt Absturz
            self.call_from_thread(self.message, probes.FAIL, f'Prüfung fehlgeschlagen: {error}')
            return
        self.call_from_thread(self._apply_snapshot, snapshot, with_setup, metrics)

    def _apply_snapshot(self, snapshot: probes.Snapshot, with_setup: bool, metrics: dict | None = None) -> None:
        if with_setup:
            self._setup_facts = {k: snapshot.facts[k] for k in probes.SETUP if k in snapshot.facts}
            self._setup_at = time.time()
        self.snapshot = snapshot
        if metrics is not None:
            self.metrics = metrics
        self._render_status()
        self._sync_spinner()
        self._update_views()
        if self._intro_enabled and self.main_screen.query('#intro'):
            intro = self.main_screen.query_one('#intro')
            version = self.fact('version')
            if version is not None:
                intro.version = version.value
            intro.ready(self._intro_lines())
        else:
            self._maybe_alert()

    def _update_views(self) -> None:
        self.view().update_view()
        if self.current != 'dashboard':
            self.view('dashboard').update_view()
        self.refresh_footer()

    @work(thread=True, exclusive=True, group='storage')
    def _storage_worker(self) -> None:
        try:
            usage = self._storage_source(self.instance)
        except Exception:  # noqa: BLE001 - nur Anzeige
            return
        self.call_from_thread(self._apply_extra, 'storage', usage)

    @work(thread=True, exclusive=True, group='network')
    def _network_worker(self) -> None:
        try:
            info = self._network_source()
        except Exception:  # noqa: BLE001 - nur Anzeige
            return
        self.call_from_thread(self._apply_extra, 'network', info)

    def _apply_extra(self, name: str, value) -> None:
        setattr(self, name, value)
        self.view().update_view()

    # ------------------------------------------------------------ Fehler-Popups
    ALERTS = {
        'dienst': ('Die Werkbank ist ausgefallen',
                   'Der Dienst läuft nicht mehr. Browser und Windows-Brücke erreichen den Pi nicht; ein '
                   'laufender Messlauf ist damit beendet.',
                   [Choice('Protokoll ansehen', 'protokoll', primary=True), Choice('Neu starten', 'restart'),
                    Choice('Schließen', 'close')]),
        'kamera': ('Kamera-Fehler',
                   'Die Werkbank bekommt keine Bilder. Ohne Kamera kann sie nicht lesen.',
                   [Choice('Kamera neu starten', 'camera', primary=True), Choice('Kamera-Tab', 'kamera'),
                    Choice('Schließen', 'close')]),
        'ausgabe': ('Ausgabe-Fehler',
                    'Die Werte erreichen GSVmulti nicht. Der Lauf zeichnet weiter auf, sendet aber nicht.',
                    [Choice('Ausgabe-Tab', 'ausgabe', primary=True), Choice('Protokoll ansehen', 'protokoll'),
                     Choice('Schließen', 'close')]),
        'lauf': ('Lauf-Fehler',
                 'Der Lauf meldet einen Fehler. Details und Abhilfe in der Werkbank im Browser.',
                 [Choice('Lauf-Tab', 'lauf', primary=True), Choice('Protokoll ansehen', 'protokoll'),
                  Choice('Schließen', 'close')]),
    }

    def _maybe_alert(self) -> None:
        if not self._popups or self.snapshot is None or len(self.screen_stack) > 1:
            return
        if self.main_screen.query('#intro'):
            return
        for key in ALERT_FACTS:
            fact = self.snapshot.facts.get(key)
            if fact is None:
                continue
            state = (fact.level, fact.value)
            previous = self._alerted.get(key)
            self._alerted[key] = state
            if fact.level != probes.FAIL or previous == state:
                continue
            title, meaning, choices = self.ALERTS[key]
            lines = [Text(f'{symbol(fact.level)} {fact.label}: {fact.value}', style=f'bold {TONE[fact.level]}'),
                     meaning]
            if fact.hint:
                lines.append(fact.hint)
            self.show_info(title, lines, choices, tone='fail', callback=self._alert_choice)
            return

    def _alert_choice(self, value: str | None) -> None:
        if value in (None, 'close'):
            return
        if value == 'restart':
            self.service_action('restart')
        elif value == 'camera':
            self.camera_restart()
        else:
            self.open_tab(value)

    # ------------------------------------------------------------ Dienst
    @work(exclusive=True, group='service')
    async def service_action(self, action: str) -> None:
        from . import service

        if self.instance.unit is None or self._busy:
            return
        try:
            plan = service.plan(action, self.instance, self.snapshot)
        except ValueError as error:
            self.message(probes.FAIL, str(error))
            return
        title, label = SERVICE_WORDS[action]
        lines = []
        if action in ('stop', 'restart'):
            lines.append('Die Werkbank ist danach kurz nicht erreichbar; verbundene Browser und die '
                         'Brücke verbinden sich neu.')
        if action == 'stop':
            lines.append('Gestoppt bleibt sie aus, bis jemand sie wieder startet.')
        if plan.note:
            lines.append(plan.note)
        ok = await self.push_screen_wait(ConfirmScreen(Confirmation(
            title, lines, plan.shell(), label, danger=action == 'stop', blocker=plan.blocker)))
        if not ok:
            return
        if any(cmd and cmd[0] == 'sudo' for cmd in plan.commands):
            with self.suspend():
                print(f'\n{title} – sudo fragt gegebenenfalls nach dem Passwort.\n')
                result = service.execute(plan, self.instance, interactive=True, run=self._service_runner,
                                         recheck=self._recheck)
            self._finish_service(result)
        else:
            self._busy = {'start': 'starte Werkbank, warte auf HTTPS', 'stop': 'stoppe Werkbank',
                          'restart': 'starte Werkbank neu, warte auf HTTPS'}[action]
            self._sync_spinner()
            self._render_status()
            self._service_thread(plan)

    @work(thread=True, exclusive=True, group='service-run')
    def _service_thread(self, plan) -> None:
        from . import service

        result = service.execute(plan, self.instance, interactive=False, run=self._service_runner,
                                 echo=lambda _line: None, recheck=self._recheck)
        self.call_from_thread(self._finish_service, result)

    def _recheck(self) -> str | None:
        return self._collect(self.instance, include_setup=False).stop_blocker

    def _finish_service(self, result: tuple[bool, str]) -> None:
        ok, message = result
        self._busy = None
        self._sync_spinner()
        self.message(probes.OK if ok else probes.FAIL, message)
        self._setup_at = 0.0
        self.action_refresh()

    # ------------------------------------------------------------ Steuerungsbefehle
    @work(exclusive=True, group='socket')
    async def socket_action(self, op: str, title: str, lines: list[str], label: str, *, danger: bool = False,
                            guarded: bool = True, done: str = 'Erledigt.') -> None:
        """Steuerungsbefehl der Werkbank nach Bestätigung (``guarded``: gesperrt wie Dienstaktionen)."""
        ok = await self.push_screen_wait(ConfirmScreen(Confirmation(
            title, lines, [f'Steuerung: {op}'], label, danger=danger,
            blocker=self.blocker if guarded else None)))
        if not ok:
            return
        self._busy = title
        self._sync_spinner()
        self._render_status()
        self._socket_thread(op, done, guarded)

    @work(thread=True, exclusive=True, group='socket-run')
    def _socket_thread(self, op: str, done: str, guarded: bool) -> None:
        if guarded:
            blocker = self._recheck()
            if blocker:
                self.call_from_thread(self._finish_socket, False, f'Abgebrochen: {blocker}')
                return
        try:
            reply = self._socket(self.instance.socket, op, timeout=20.0)
        except Exception as error:  # noqa: BLE001
            reply = {'error': str(error)}
        if not isinstance(reply, dict):
            self.call_from_thread(self._finish_socket, False, 'Steuerung nicht erreichbar.')
        elif reply.get('error'):
            self.call_from_thread(self._finish_socket, False, str(reply['error']))
        else:
            self.call_from_thread(self._finish_socket, True, done)

    def _finish_socket(self, ok: bool, text: str) -> None:
        self._busy = None
        self._sync_spinner()
        self.message(probes.OK if ok else probes.FAIL, text)
        self.action_refresh()

    def camera_connect(self) -> None:
        self.socket_action('live.camera', 'Kamera verbinden',
                           ['Öffnet die Kamera, falls sie gerade nicht läuft (z. B. nach dem Einstecken).'],
                           'Verbinden', guarded=False, done='Kamera wird verbunden.')

    def camera_restart(self) -> None:
        self.socket_action('live.camera.restart', 'Kamera neu starten',
                           ['Schließt die Kamera und öffnet sie neu. Die Vorschau im Browser setzt kurz aus.',
                            'Hilft, wenn die Kamera hängt oder nach dem Umstecken keine Bilder liefert.'],
                           'Neu starten', done='Kamera neu gestartet.')

    def bridge_prepare(self) -> None:
        self.socket_action('bridge.prepare-uart', 'Brücke: UART-Empfang vorbereiten',
                           ['Öffnet den UART-Empfang für die Windows-Brücke, damit sie Werte über das '
                            'Kabel bekommt. Ein Laufstart mit anderer Ausgabe beendet ihn wieder.'],
                           'Vorbereiten', guarded=False, done='UART-Empfang vorbereitet.')

    def bridge_stop(self) -> None:
        self.socket_action('bridge.stop-uart', 'Brücke: UART-Empfang beenden',
                           ['Schließt den vorbereiteten UART-Empfang der Brücke.'],
                           'Beenden', danger=True, done='UART-Empfang beendet.')

    # ------------------------------------------------------------ Abhilfe
    @work(exclusive=True, group='fix')
    async def run_fix(self, fact: probes.Fact) -> None:
        if not fact.command:
            return
        ok = await self.push_screen_wait(ConfirmScreen(Confirmation(
            f'{fact.label}: Befehl ausführen', [fact.hint] if fact.hint else [], [fact.command], 'Ausführen')))
        if not ok:
            return
        with self.suspend():
            print(f'\n$ {fact.command}\n')
            from .cli import run_hint_command

            code = run_hint_command(fact.command, self.instance)
            print(f'\nExit {code}. Enter drücken, um zur Konsole zurückzukehren.')
            try:
                input()
            except EOFError:
                pass
        self.message(probes.OK if code == 0 else probes.FAIL, f'{fact.command} → Exit {code}')
        self._setup_at = 0.0
        self.action_refresh()

    # ------------------------------------------------------------ Update, Deinstallation
    def _newest_archive(self) -> str:
        candidates = []
        for base in (Path.home(), Path.home() / 'Downloads', Path.cwd()):
            try:
                candidates += [p for p in base.glob('picam*.tar.gz') if p.is_file()]
            except OSError:
                continue
        return str(max(candidates, key=lambda p: p.stat().st_mtime)) if candidates else ''

    def run_cli(self, argv: list[str], title: str) -> int:
        command = [sys.executable, '-m', 'dispread.admin.cli', *argv]
        if self.instance.config:
            command[3:3] = ['--config', self.instance.config]
        return self.run_in_terminal(command, title)

    _run_cli = run_cli

    def run_in_terminal(self, command: list[str], title: str) -> int:
        """Befehl im normalen Terminal ausführen (Konsole pausiert), danach Enter."""
        with self.suspend():
            print(f'\n{title}\n')
            code = subprocess.call(command)
            print(f'\nExit {code}. Enter drücken, um zur Konsole zurückzukehren.')
            try:
                input()
            except EOFError:
                pass
        return code

    @work(exclusive=True, group='update')
    async def start_update(self) -> None:
        if not self.installed():
            return
        if self.blocker:
            self.message(probes.WARN, f'Update gesperrt: {self.blocker}')
            return
        source = await self.push_screen_wait(AskScreen(
            'Update installieren',
            ['Neue Version wird neben der laufenden vorbereitet und geprüft (eigene Umgebung, Selbsttest), '
             'dann umgeschaltet und der Dienst neu gestartet. Antwortet sie nicht, schaltet picam auf die '
             'jetzige zurück. Daten, Einstellungen und Kopplungen bleiben.',
             'Pfad oder HTTPS-Adresse des Releasearchivs:'],
            value=self._newest_archive(), placeholder='/home/…/picam-1.1.0.tar.gz'))
        if not source:
            return
        ok = await self.push_screen_wait(ConfirmScreen(Confirmation(
            'Update installieren', [f'Archiv: {source}', 'Dienst wird neu gestartet.'],
            [f'picam update --source {shlex.quote(source)}'], 'Installieren')))
        if not ok:
            return
        self._after_update(self.run_cli(['update', '--source', source, '--yes'], 'picam update'))

    @work(exclusive=True, group='update')
    async def start_rollback(self) -> None:
        fact = self.fact('version')
        if not self.installed() or fact is None:
            return
        previous = dict(fact.detail).get('Vorige')
        if not previous:
            self.message(probes.OFF, 'Keine vorige Version vorhanden.')
            return
        ok = await self.push_screen_wait(ConfirmScreen(Confirmation(
            f'Zurück auf {previous}', ['Schaltet auf die vorige Version um und startet den Dienst neu.'],
            ['picam update --rollback'], 'Zurückschalten', blocker=self.blocker)))
        if ok:
            self._after_update(self.run_cli(['update', '--rollback', '--yes'], 'picam update --rollback'))

    def _after_update(self, code: int) -> None:
        from .instance import discover

        self.instance = discover(self.instance.config)
        self._setup_at = 0.0
        self.message(probes.OK if code == 0 else probes.FAIL,
                     'Update abgeschlossen.' if code == 0 else f'Update nicht abgeschlossen (Exit {code}).')
        self.action_refresh()

    def _uninstall_command(self) -> list[str]:
        script = Path(self.instance.root or '') / 'install.sh'
        command = [str(script), '--uninstall', '--mode', 'system' if self.instance.scope == 'system' else 'user']
        if self.instance.scope == 'system' and os.geteuid() != 0:
            command.insert(0, 'sudo')
        return command

    def uninstall_blocker(self) -> str | None:
        if not self.installed():
            return 'nur für eine installierte Werkbank'
        if not (Path(self.instance.root or '') / 'install.sh').is_file():
            return 'install.sh fehlt in der aktiven Version'
        return self.blocker

    @work(exclusive=True, group='uninstall')
    async def start_uninstall(self) -> None:
        blocker = self.uninstall_blocker()
        if blocker:
            self.message(probes.WARN, f'Deinstallieren: {blocker}')
            return
        command = self._uninstall_command()
        ok = await self.push_screen_wait(ConfirmScreen(Confirmation(
            'Werkbank deinstallieren',
            ['Stoppt den Dienst und entfernt Dienst, Programmversionen und den Befehl picam.',
             'Läufe, Einstellungen, Kopplungen und Kalibrierung bleiben erhalten (eine Neuinstallation '
             'findet sie wieder). Endgültig löschen nur im Terminal mit --purge-data.',
             'Zuerst zeigt der Installer den genauen Plan; erst danach wird gefragt.'],
            [' '.join(shlex.quote(c) for c in command)], 'Plan zeigen', danger=True)))
        if not ok:
            return
        with self.suspend():
            print('\nDeinstallation – Plan:\n')
            subprocess.call(command)
            try:
                answer = input('\nJetzt so deinstallieren? Tippe „deinstallieren“ zum Bestätigen: ').strip()
            except EOFError:
                answer = ''
            code = None
            if answer == 'deinstallieren':
                code = subprocess.call([*command, '--apply'])
                print(f'\nExit {code}.')
            else:
                print('\nNicht deinstalliert.')
            try:
                input('Enter drücken …')
            except EOFError:
                pass
        if code == 0:
            self.exit(0)  # Programm und Befehl sind entfernt: Konsole beenden
        elif code is not None:
            self.message(probes.FAIL, f'Deinstallation nicht abgeschlossen (Exit {code}).')

    # ------------------------------------------------------------ Protokoll
    def _start_log(self) -> None:
        if self._log_thread is not None and self._log_thread.is_alive():
            return
        self.view('protokoll').clear_log()
        self.view('dashboard').clear_log()
        self.log_lines.clear()
        self._log_thread = threading.Thread(target=self._log_reader, daemon=True)
        self._log_thread.start()

    def _log_reader(self) -> None:
        """Protokoll lesen; endet still, wenn die Konsole beendet wird (raspi01: Exception beim Beenden)."""
        try:
            self._read_journal()
        except (RuntimeError, ValueError, OSError):
            # App schon beendet (call_from_thread) oder Pipe beim Beenden geschlossen.
            return

    def _read_journal(self) -> None:
        from . import service

        if self._journal_source is not None:
            self.call_from_thread(self._add_logs, list(self._journal_source()))
            return
        try:
            command = service.journal_command(self.instance, 300, follow=True)
            # stderr in denselben Strom: kein Volllaufen einer zweiten Pipe.
            self._log_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                 text=True, bufsize=1)
        except (ValueError, OSError) as error:
            self.call_from_thread(self._add_log, service.LogLine('', 'fehler', f'Protokoll nicht lesbar: {error}'))
            return
        assert self._log_process.stdout is not None
        stream = self._log_process.stdout
        batch: list = []
        last = time.monotonic()
        while True:
            ready = select.select([stream], [], [], 0.25)[0]
            if ready:
                raw = stream.readline()
                if not raw:
                    break
                if not raw.lstrip().startswith('{'):
                    if raw.strip():
                        batch.append(service.LogLine('', 'fehler', raw.strip()))
                else:
                    batch.extend(service.parse_journal(raw))
            # gebündelt an die Oberfläche: höchstens 4× pro Sekunde
            if batch and (not ready or time.monotonic() - last > 0.25):
                self.call_from_thread(self._add_logs, batch)
                batch, last = [], time.monotonic()
        if batch:
            self.call_from_thread(self._add_logs, batch)

    def log_row(self, line) -> Table:
        style = {'fehler': TONE[probes.FAIL], 'warnung': TONE[probes.WARN], 'debug': MUTED}.get(line.level, '')
        row = Table.grid(padding=(0, 2), expand=True)
        row.add_column(width=8, style=MUTED, no_wrap=True)
        row.add_column(ratio=1, overflow='fold')
        row.add_row(line.time, Text(line.text, style=style))
        return row

    def _add_log(self, line) -> None:
        self._add_logs([line])

    def _add_logs(self, lines: list) -> None:
        self.log_lines.extend(lines)
        if len(self.log_lines) > LOG_LIMIT:
            del self.log_lines[: len(self.log_lines) - LOG_LIMIT]
        dashboard, protokoll = self.view('dashboard'), self.view('protokoll')
        for line in lines[-LOG_LIMIT:]:
            row = self.log_row(line)
            dashboard.add_log(row)
            protokoll.add_log(line, row)

    # ------------------------------------------------------------ Sonstiges
    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_quit_app(self) -> None:
        guard = getattr(self.screen, 'quit_guard', None)
        if guard is not None and guard():  # Kalibrierung läuft: erst Abbruch anfordern, nicht schließen
            return
        self._stop_log()
        self.exit(0)

    def _stop_log(self) -> None:
        process = self._log_process
        if process is not None and process.poll() is None:
            process.terminate()

    def on_unmount(self) -> None:
        self._stop_log()


def intro_wanted(flag: bool = True) -> bool:
    """Startbild zeigen? ``--no-intro`` oder ``PICAM_INTRO=0`` schalten es ab."""
    return flag and os.environ.get('PICAM_INTRO', '1').strip().lower() not in ('0', 'nein', 'no', 'off', 'aus')


def run(instance: Instance, intro: bool = True) -> int:
    app = PicamApp(instance, intro=intro_wanted(intro))
    result = app.run()
    return 0 if result is None else int(result)


def snapshot_json(app: PicamApp) -> str:
    return json.dumps(app.snapshot.to_json() if app.snapshot else {}, ensure_ascii=False)
