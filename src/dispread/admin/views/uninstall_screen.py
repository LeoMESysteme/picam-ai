"""Vorschau der Deinstallation in der Konsole.

Zeigt den schreibfreien Plan des Installers (``uninstall.plan_uninstall``): was entfernt wird, was
erhalten bleibt (mit Pfaden), ob sudo nötig ist und wie Daten endgültig gelöscht werden
(``--purge-data``). Hier wird nichts geändert. Bestätigt der Bediener ausdrücklich, schließt der
Bildschirm mit ``True``; die App beendet dann die Konsole, und die eigentliche Deinstallation läuft
anschließend im Terminal (geführt, mit Eintippen von „deinstallieren“).
"""

from __future__ import annotations

from rich.console import Group
from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from .. import probes, uninstall
from ..ui import MUTED, SOFT, fade_in
from ..widgets import SectionCard, badge, header, help_line, wrap_rows


class UninstallScreen(ModalScreen[bool]):
    BINDINGS = [Binding('escape,q', 'cancel', show=False), Binding('left,right', 'switch', show=False),
                Binding('up', 'scroll(-1)', show=False), Binding('down', 'scroll(1)', show=False),
                Binding('pageup', 'scroll(-5)', show=False), Binding('pagedown', 'scroll(5)', show=False)]
    DEFAULT_CSS = '''
    UninstallScreen { background: $picam-canvas; }
    #un { height: 1fr; width: 1fr; max-width: 120; padding: 0 2; }
    #un-title { height: 1; margin: 1 0 0 0; }
    #un-top { height: 1fr; scrollbar-size-vertical: 1; }
    #un-hint { height: 1; margin: 1 0 0 0; }
    #un-buttons { height: 1; margin: 1 0 0 0; }
    #un-buttons Button { margin: 0 2 0 0; }
    '''

    def __init__(self, instance, plan_fn=None, describe_fn=None):
        super().__init__()
        self.instance = instance
        self.plan_fn = plan_fn or uninstall.plan_uninstall
        self.describe_fn = describe_fn or uninstall.describe
        self.plan: dict | None = None
        self.view: dict | None = None
        self.error: str | None = None

    def compose(self):
        with Vertical(id='un'):
            yield Static(id='un-title')
            with VerticalScroll(id='un-top'):
                yield SectionCard(id='un-remove')
                yield SectionCard(id='un-keep')
                yield SectionCard(id='un-notes')
            yield Static(id='un-hint')
            with Horizontal(id='un-buttons'):
                yield Button('Abbrechen', id='un-cancel')
                yield Button('Deinstallieren …', id='un-ok', variant='error')

    def on_mount(self) -> None:
        fade_in(self.query_one('#un'))
        try:
            self.plan = self.plan_fn(self.instance)
            self.view = self.describe_fn(self.instance, self.plan)
        except (OSError, ValueError) as error:
            self.error = str(error)
        self.update_view()
        self.query_one('#un-cancel', Button).focus()  # Fokus nie auf der gefährlichen Aktion

    def on_resize(self, event) -> None:
        self.update_view()

    def _width(self, widget) -> int:
        width = widget.content_size.width or widget.size.width
        return width if width > 0 else max(40, self.size.width - 4)

    def update_view(self) -> None:
        if not self.is_mounted:
            return
        title = self.query_one('#un-title', Static)
        right = (badge(probes.FAIL, 'nicht möglich') if self.error
                 else badge(probes.WARN, 'wartet auf Ihre Bestätigung') if self.view
                 else badge('busy', 'liest den Plan', 'busy'))
        title.update(header('remove', 'Werkbank deinstallieren', right, self._width(title)))
        remove, keep, notes = (self.query_one(f'#un-{name}', SectionCard) for name in ('remove', 'keep', 'notes'))
        if self.error or self.view is None:
            remove.display = keep.display = False
            notes.display = self.error is not None
            if self.error:
                notes.show(header('check', 'Nicht möglich', badge(probes.FAIL, 'nichts geändert'), self._width(notes)),
                           Text(self.error, style=SOFT), None)
        else:
            width = self._width(remove)
            remove.display = keep.display = notes.display = True
            service = self.view['service']
            remove.show(header('remove', 'Wird entfernt', badge(probes.WARN, 'endgültig'), width),
                        wrap_rows([(label, Text(text, style=SOFT)) for label, text in self.view['remove']], label_w=19),
                        help_line('Der laufende Werkbank-Dienst wird dabei gestoppt.') if service else None)
            if self.view['keep']:
                keep.show(header('storage', 'Bleibt erhalten', badge(probes.OK, 'unberührt'), width),
                          wrap_rows([(label, Text(text, style=SOFT)) for label, text in self.view['keep']], label_w=19),
                          help_line('Eine Neuinstallation findet Läufe, Einstellungen und Kopplungen wieder.'))
            else:
                keep.display = False
            lines: list = []
            access = ('Die Deinstallation braucht Administratorrechte: sudo fragt im Terminal nach dem Passwort.'
                      if self.view['needs_root'] else 'Keine Administratorrechte nötig.')
            lines.append(Text(access, style=SOFT))
            if not self.plan['purge_data']:
                lines.append(Text('Läufe, Kalibrierung, Kopplungen und Einstellungen endgültig löschen: im Terminal '
                                  'install.sh --uninstall --purge-data (vorher sichern).', style=SOFT))
            lines += [Text(note, style=MUTED) for note in self.view['notes']]
            notes.show(header('info', 'Ablauf', None, width), Group(*lines),
                       help_line('Danach schließt die Konsole; im Terminal tippen Sie „deinstallieren“ zur Bestätigung.'))
        self.query_one('#un-ok', Button).disabled = self.view is None
        self.query_one('#un-hint', Static).update(help_line(
            'Hier ändert sich noch nichts. Enter bestätigt den Knopf im Fokus, Esc bricht ab.'))

    @on(Button.Pressed, '#un-ok')
    def _ok(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, '#un-cancel')
    def _cancel(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_switch(self) -> None:
        self.focus_next(Button)

    def action_scroll(self, rows: int) -> None:
        top = self.query_one('#un-top', VerticalScroll)
        top.scroll_to(y=max(0, top.scroll_y + int(rows)), animate=False)
