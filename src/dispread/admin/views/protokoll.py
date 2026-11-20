"""Protokoll des Dienstes: mitlaufend, Filter „nur Probleme“."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import RichLog, Static

from .. import probes
from ..ui import ACCENT, MUTED, TONE, Action
from .base import TabView

LOG_LIMIT = 2000


class ProtokollView(TabView):
    TAB_ID, TITLE, KEY = 'protokoll', 'Protokoll', 'l'
    INFO_TITLE = 'Protokoll'
    INFO = ('Die Meldungen des Dienstes aus dem Systemprotokoll (journald), neueste unten. Im Terminal: '
            'picam logs -f.',)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.follow = True
        self.errors_only = False

    def compose(self):
        yield Static(id='log-head')
        yield RichLog(id='log', max_lines=LOG_LIMIT, wrap=True, markup=False, auto_scroll=True, min_width=20)

    def update_view(self) -> None:
        head = Text()
        head.append('Protokoll', style='bold')
        head.append(f'   {self.app.instance.unit or "–"}', style=MUTED)
        state = ['läuft mit' if self.follow else 'angehalten']
        if self.errors_only:
            state.append('nur Warnungen und Fehler')
        head.append('   ' + ' · '.join(state), style=ACCENT if self.follow else TONE[probes.WARN])
        self.query_one('#log-head', Static).update(head)

    def actions(self) -> list[Action]:
        return [Action('f', 'mitlaufen ' + ('aus' if self.follow else 'an'), self.toggle_follow),
                Action('e', 'alle' if self.errors_only else 'nur Probleme', self.toggle_errors)]

    def shows(self, line) -> bool:
        return not self.errors_only or line.level in ('fehler', 'warnung')

    def add_log(self, line, row) -> None:
        if self.shows(line):
            self.query_one('#log', RichLog).write(row, scroll_end=self.follow)

    def clear_log(self) -> None:
        self.query_one('#log', RichLog).clear()

    def toggle_follow(self) -> None:
        self.follow = not self.follow
        log = self.query_one('#log', RichLog)
        log.auto_scroll = self.follow
        if self.follow:
            log.scroll_end(animate=False)
        self.update_view()
        self.app.refresh_footer()

    def toggle_errors(self) -> None:
        self.errors_only = not self.errors_only
        log = self.query_one('#log', RichLog)
        log.clear()
        for line in self.app.log_lines:
            if self.shows(line):
                log.write(self.app.log_row(line), scroll_end=False)
        if self.follow:
            log.scroll_end(animate=False)
        self.update_view()
        self.app.refresh_footer()
