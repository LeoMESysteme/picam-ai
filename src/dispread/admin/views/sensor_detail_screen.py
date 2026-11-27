"""Pop-up mit den Angaben eines Sensors (Meine Sensoren und Marktplatz).

Zeigt Anzeigeart (mit Polarität), Anschluss, Einheit, die 16 Zellen als Formatvorschau, Hersteller, Kennung,
Version, Status, Herkunft und – für Katalogeinträge – Datum und Prüfläufe. Die Knöpfe hängen vom Zustand ab
(Installieren, Installiert, Aktualisieren, Als aktiv setzen, Einreichen); der Bildschirm liefert nur den Wert des
gewählten Knopfes zurück, ausgeführt wird in der Ansicht (mit denselben Rückfragen wie über die Tasten).
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ..ui import MUTED, fade_in
from ..widgets import fields, help_line
from .sensor_wizard_screen import cell_preview


@dataclass
class DetailButton:
    label: str
    result: str            # Rückgabewert (z. B. 'install'); 'close' schließt
    primary: bool = False
    disabled: bool = False
    reason: str | None = None   # Tooltip bei gesperrtem Knopf


class SensorDetailScreen(ModalScreen[str | None]):
    """Eigenschaften eines Sensors; Esc oder „Schließen“ liefert ``None``."""

    BINDINGS = [Binding('escape', 'close', show=False), Binding('left,right', 'switch', show=False)]
    DEFAULT_CSS = '''
    SensorDetailScreen { align: center middle; background: $picam-backdrop; }
    #det { width: 80; max-width: 96%; height: auto; padding: 1 2; background: $picam-raised;
           border: none; border-top: tall $picam-accent-strong; }
    #det-title { height: auto; }
    #det-body { height: auto; scrollbar-size-vertical: 1; }
    #det-fields { height: auto; margin: 1 0 0 0; }
    #det-preview { height: 2; margin: 1 0 0 0; }
    #det-notes { height: auto; margin: 1 0 0 0; }
    #det-buttons { height: auto; margin: 1 0 0 0; align-horizontal: right; }
    #det-buttons Button { margin: 0 0 0 2; }
    '''

    def __init__(self, title: str, badge_text: Text | None, rows: list, example: str,
                 buttons: list[DetailButton], notes: list[str] | None = None):
        super().__init__()
        self.title_text, self.badge_text, self.rows, self.example = title, badge_text, rows, example
        self.buttons, self.notes = buttons, notes or []

    def compose(self) -> ComposeResult:
        with Vertical(id='det'):
            yield Static(id='det-title')
            with VerticalScroll(id='det-body'):
                yield Static(id='det-fields')
                yield Static(id='det-preview')
                yield Static(id='det-notes')
            with Horizontal(id='det-buttons'):
                for index, item in enumerate(self.buttons):
                    button = Button(item.label, id=f'det-btn-{index}', variant='primary' if item.primary else 'default',
                                    disabled=item.disabled)
                    button.tooltip = item.reason
                    yield button

    def inner_width(self) -> int:
        return max(40, min(80, int(self.app.size.width * 0.96)) - 6)

    def on_mount(self) -> None:
        width = self.inner_width()
        head = Text(no_wrap=True, overflow='ellipsis')
        head.append(self.title_text, style='bold')
        if self.badge_text is not None:
            head.append(' ' * max(2, width - head.cell_len - self.badge_text.cell_len))
            head.append_text(self.badge_text)
        self.query_one('#det-title', Static).update(head)
        self.query_one('#det-fields', Static).update(fields(self.rows, width, label_w=12, columns=2))
        self.query_one('#det-preview', Static).update(
            cell_preview(self.example) if self.example.strip() else Text('Formatvorschau: –', style=MUTED))
        notes = self.query_one('#det-notes', Static)
        notes.display = bool(self.notes)
        notes.update(Text('\n').join(help_line(line) for line in self.notes))
        self.query_one('#det-body', VerticalScroll).styles.max_height = max(5, self.app.size.height - 9)
        first = next((b for b in self.query('#det-buttons Button') if not b.disabled), None)
        (first or self.query_one('#det-buttons Button', Button)).focus()
        fade_in(self.query_one('#det'))

    def action_close(self) -> None:
        self.dismiss(None)

    def action_switch(self) -> None:
        self.focus_next(Button)

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        event.stop()
        item = self.buttons[int((event.button.id or 'det-btn-0').rsplit('-', 1)[1])]
        self.dismiss(None if item.result == 'close' else item.result)

