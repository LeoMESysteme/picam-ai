"""Protokoll des Dienstes: mitlaufend, Filter „nur Probleme“."""

from __future__ import annotations

from textual.widgets import Static

from .. import probes
from ..ui import Action, ReflowLog
from ..widgets import badge, badges, header
from .base import TabView

LOG_LIMIT = 2000


class ProtokollView(TabView):
    TAB_ID, TITLE, KEY = 'protokoll', 'Protokoll', 'l'
    INFO_TITLE = 'Protokoll'
    ABOUT = ('Die Meldungen des Dienstes aus dem Systemprotokoll (journald), neueste unten. Im Terminal: '
            'picam logs -f.',)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.follow = True
        self.errors_only = False

    def compose(self):
        yield Static(id='log-head')
        yield ReflowLog(id='log', max_lines=LOG_LIMIT, wrap=True, markup=False, auto_scroll=True, min_width=20)

    def update_view(self) -> None:
        self.query_one('#log', ReflowLog).sync()
        # Zustand der Ansicht, keine Aussage über den Dienst: „läuft mit“ in der Leitfarbe, nie grün
        state = [badge('busy', 'läuft mit', 'on') if self.follow else badge(probes.WARN, 'angehalten', 'stop')]
        if self.errors_only:
            state.append(badge('busy', 'nur Probleme', 'filter'))
        width = min(120, self.size.width or self.app.size.width - 4)
        self.query_one('#log-head', Static).update(
            header('log', 'Protokoll', badges(*state), width, note=self.app.instance.unit or '–'))

    def actions(self) -> list[Action]:
        return [Action('f', 'mitlaufen ' + ('aus' if self.follow else 'an'), self.toggle_follow,
                       icon='stop' if self.follow else 'start'),
                Action('e', 'alle' if self.errors_only else 'nur Probleme', self.toggle_errors, icon='filter')]

    def shows(self, line) -> bool:
        return not self.errors_only or line.level in ('fehler', 'warnung')

    def add_log(self, line, row) -> None:
        if self.shows(line):
            self.query_one('#log', ReflowLog).add(row, scroll_end=self.follow)

    def clear_log(self) -> None:
        self.query_one('#log', ReflowLog).reset()

    def toggle_follow(self) -> None:
        self.follow = not self.follow
        log = self.query_one('#log', ReflowLog)
        log.auto_scroll = self.follow
        if self.follow:
            log.scroll_end(animate=False)
        self.update_view()
        self.app.refresh_footer()

    def toggle_errors(self) -> None:
        self.errors_only = not self.errors_only
        log = self.query_one('#log', ReflowLog)
        log.replace([self.app.log_row(line) for line in self.app.log_lines if self.shows(line)])
        if self.follow:
            log.scroll_end(animate=False)
        self.update_view()
        self.app.refresh_footer()
