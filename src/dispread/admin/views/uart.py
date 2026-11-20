"""Tab UART: Stiftleiste des Pi mit den benutzten Pins, Warnungen und Befund."""

from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from .. import probes
from ..ui import ACCENT, MUTED, Action, P, ascii_mode
from ..widgets import (
    ActionBar,
    CardBox,
    SectionCard,
    TabBody,
    badge,
    detail_rows,
    fact_badge,
    fact_help,
    fields,
    header,
    help_line,
    join,
    value,
    wrap_rows,
)
from .base import FactView

#: Stiftleiste des Pi 5 (Standard-40-Pin), Pin → Beschriftung.
PIN_NAMES = {
    1: '3V3', 2: '5V', 3: 'GPIO2', 4: '5V', 5: 'GPIO3', 6: 'GND', 7: 'GPIO4', 8: 'GPIO14 TXD0',
    9: 'GND', 10: 'GPIO15 RXD0', 11: 'GPIO17', 12: 'GPIO18', 13: 'GPIO27', 14: 'GND', 15: 'GPIO22',
    16: 'GPIO23', 17: '3V3', 18: 'GPIO24', 19: 'GPIO10', 20: 'GND', 21: 'GPIO9', 22: 'GPIO25',
    23: 'GPIO11', 24: 'GPIO8', 25: 'GND', 26: 'GPIO7', 27: 'ID_SD', 28: 'ID_SC', 29: 'GPIO5',
    30: 'GND', 31: 'GPIO6', 32: 'GPIO12', 33: 'GPIO13', 34: 'GND', 35: 'GPIO19', 36: 'GPIO16',
    37: 'GPIO26', 38: 'GPIO20', 39: 'GND', 40: 'GPIO21',
}
USED = {6: 'benutzt', 8: 'benutzt (Senden)'}
UNUSED = {10: 'nicht benutzt'}
#: Kurzfassung für schmale Terminals (die Erklärung steht in der Karte „Anschluss“)
USED_SHORT = {6: 'benutzt', 8: 'sendet'}
UNUSED_SHORT = {10: 'frei'}
FULL_W = 58  # Breite der Stiftleiste mit langen Vermerken (plus Rand)
POWER_5V = P.pin_5v
POWER_3V3 = P.pin_3v3


def header_graphic(rows: int, compact: bool = False) -> Text:
    """Stiftleiste: Pin 1 oben links, ungerade Pins links. ``rows`` = Pinpaare (20 = ganz).

    ``compact``: kurze Vermerke („sendet“, „frei“), damit die Leiste in 60 Spalten passt.
    """
    used, unused = (USED_SHORT, UNUSED_SHORT) if compact else (USED, UNUSED)
    ascii_only = ascii_mode()
    tl, tm, tr = ('+', '+', '+') if ascii_only else ('┌', '┬', '┐')
    bl, bm, br = ('+', '+', '+') if ascii_only else ('└', '┴', '┘')
    side, dot_on, dot_off = ('|', '*', 'o') if ascii_only else ('│', '●', '○')
    arrow = '<' if ascii_only else '◀'
    text = Text(no_wrap=True)
    pad = ' ' * 11
    text.append(f'{pad}{tl}───{tm}───{tr}\n'.replace('─', '-' if ascii_only else '─'), style=MUTED)
    for row in range(1, rows + 1):
        left, right = 2 * row - 1, 2 * row

        def tone(pin: int) -> str:
            name = PIN_NAMES[pin]
            if pin in USED:
                return f'bold {ACCENT}'
            if name == 'GND':
                return MUTED
            if name == '5V':
                return POWER_5V
            if name == '3V3':
                return POWER_3V3
            return MUTED if pin not in UNUSED else ''

        text.append(PIN_NAMES[left].rjust(7), style=tone(left))
        text.append(f' {left:>2} ', style=tone(left))
        text.append(side, style=MUTED)
        text.append(f' {dot_on} ', style=tone(left) if left in USED else tone(left))
        text.append(side, style=MUTED)
        right_dot = dot_off if right in UNUSED else dot_on
        text.append(f' {right_dot} ', style=tone(right))
        text.append(side, style=MUTED)
        text.append(f' {right:<2}  ', style=tone(right))
        text.append(PIN_NAMES[right], style=tone(right))
        if right in used:
            text.append(f'  {arrow} {used[right]}', style=f'bold {ACCENT}')
        elif right in unused:
            text.append(f'  {arrow} {unused[right]}', style=MUTED)
        text.append('\n')
    if rows < 20:
        text.append(f"{pad}{side} {':' if ascii_only else '·'} {side} {':' if ascii_only else '·'} {side}"
                    f'   Pins {2 * rows + 1}–40 nicht benutzt\n', style=MUTED)
    text.append(f'{pad}{bl}───{bm}───{br}'.replace('─', '-' if ascii_only else '─'), style=MUTED)
    return text


SIDE = 116  # ab dieser Breite steht die ganze Stiftleiste neben den Karten (darunter: Anschlusskarte voll breit statt schmaler Spalte)


class UartView(FactView):
    TAB_ID, TITLE, KEY = 'uart', 'UART', '9'
    FACTS = ('uart',)
    INFO_TITLE = 'UART'
    ABOUT = ('Über den UART am Stiftfeld sendet der Pi die Werte an GSVmulti: Pin 8 (GPIO14, TXD0) sendet, '
             'Pin 6 ist Masse. Empfangen wird nichts (Pin 10 bleibt frei).',
             'Die Pegel des Pi sind 3,3 V. Nie direkt an RS-232 anschließen (Pegelwandler nötig, OQ-09). '
             'Den 6-poligen Kabelblock nicht auf die Stiftleiste stecken; die Kontaktfolge passt nicht. '
             'Zwei Jumper: Block GND an Pin 6, Block RXD an Pin 8.',
             'Daten fließen über /dev/ttyAMA0; /dev/serial0 zeigt auf ttyAMA10, den 3-Pin-Debug-Header. '
             'Port ändern ist nicht vorgesehen: GSVmulti ist fest an /dev/ttyAMA0 angebunden.')
    INFO_FACTS = FACTS

    DEFAULT_CSS = """
    UartView #uart-row { height: auto; width: 1fr; max-width: 120; }
    UartView #uart-pins-card { width: auto; }
    UartView #uart-pins-card > Static { width: auto; }
    UartView #uart-side { width: 1fr; height: auto; }
    UartView #uart-row.side #uart-side { padding: 0 0 0 2; }
    """

    def compose(self):
        with TabBody(classes='tab-body'):
            yield SectionCard(id='uart-fact')
            with Horizontal(id='uart-row'):
                with CardBox(id='uart-pins-card'):
                    yield Static(id='uart-pins-head')
                    yield Static(id='uart-pins')
                with Vertical(id='uart-side'):
                    yield SectionCard(id='uart-use')
                    yield SectionCard(id='uart-ports')
        yield ActionBar()

    def actions(self) -> list[Action]:
        return super().actions() + [Action('p', 'Port ändern', lambda: None, icon='uart',
                                           blocked='fest auf /dev/ttyAMA0 für GSVmulti')]

    def update_view(self) -> None:
        side = (self.size.width or self.app.size.width) >= SIDE
        row = self.query_one('#uart-row', Horizontal)
        row.styles.layout = 'horizontal' if side else 'vertical'
        row.set_class(side, 'side')
        self.query_one('#uart-pins-card').styles.width = 'auto' if side else '1fr'
        fact = self.app.fact('uart')
        card = self.query_one('#uart-fact', SectionCard)
        width = self.card_width(card)
        card.show(header('uart', 'UART', fact_badge(fact), width, note='Werte an GSVmulti'),
                  fields(detail_rows(fact), width, label_w=12, columns=2 if width >= 60 else 1),
                  fact_help(fact, 'Pi-Pegel sind 3,3 V: nie direkt an RS-232.'))
        graphic = header_graphic(20 if side else 5, compact=not side and width < FULL_W)
        self.query_one('#uart-pins-head', Static).update(
            header('pins', 'Stiftleiste', None, graphic.cell_len if side else width))
        self.query_one('#uart-pins', Static).update(graphic)
        use = self.query_one('#uart-use', SectionCard)
        side_w = self.card_width(use)
        rows = [('Pin 6', value('GND', tone=ACCENT, bold=True), 'Masse zu GSVmulti'),
                ('Pin 8', value('GPIO14/TXD0', tone=ACCENT, bold=True), 'der Pi sendet; nur TX an RX von GSVmulti'),
                ('Pin 10', value('GPIO15/RXD0'), 'nicht benutzt, nicht bestätigt'),
                ('RS-232', badge(probes.WARN, 'nie direkt'), '3,3 V am Pi: Pegelwandler nötig (OQ-09)'),
                ('Kabelblock', badge(probes.WARN, 'nicht aufstecken'),
                 '2 Jumper: GND → Pin 6, RXD → Pin 8')]
        if not side:  # breit genug: Nachsatz in derselben Zeile
            rows = [(label, join(content, f'  {note}')) for label, content, note in rows]
        use.show(header('connect', 'Anschluss', None, side_w), wrap_rows(rows, label_w=11 if side else 12),
                 help_line('Laut Hardwareprofil, nicht unabhängig bestätigt.'))
        rows = [('Datenport', value('/dev/ttyAMA0', tone=ACCENT, bold=True), 'für GSVmulti'),
                ('Debug', value('/dev/serial0'), 'zeigt auf ttyAMA10, den 3-Pin-Debug-Header')]
        if not side:
            rows = [(label, join(content, f'  {note}')) for label, content, note in rows]
        self.query_one('#uart-ports', SectionCard).show(
            header('file', 'Ports', None, side_w), wrap_rows(rows, label_w=11 if side else 12),
            help_line('Port ändern ist nicht vorgesehen.', 'i', 'mehr'))
        self.sync_buttons()
