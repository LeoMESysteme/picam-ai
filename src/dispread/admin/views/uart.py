"""Tab UART: Stiftleiste des Pi mit den benutzten Pins, Warnungen und Befund."""

from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from .. import probes
from ..ui import ACCENT, MUTED, TONE, Action, P, Segment, ascii_mode, fact_title, hint_block, kv_table, symbol
from .base import FactView, actions_segment

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
POWER_5V = P.pin_5v
POWER_3V3 = P.pin_3v3


def header_graphic(rows: int) -> Text:
    """Stiftleiste: Pin 1 oben links, ungerade Pins links. ``rows`` = Pinpaare (20 = ganz)."""
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
        if right in USED:
            text.append(f'  {arrow} {USED[right]}', style=f'bold {ACCENT}')
        elif right in UNUSED:
            text.append(f'  {arrow} {UNUSED[right]}', style=MUTED)
        text.append('\n')
    if rows < 20:
        text.append(f"{pad}{side} {':' if ascii_only else '⋮'} {side} {':' if ascii_only else '⋮'} {side}"
                    f'   Pins {2 * rows + 1}–40 nicht benutzt\n', style=MUTED)
    text.append(f'{pad}{bl}───{bm}───{br}'.replace('─', '-' if ascii_only else '─'), style=MUTED)
    return text


class UartView(FactView):
    TAB_ID, TITLE, KEY = 'uart', 'UART', '9'
    FACTS = ('uart',)
    INFO_TITLE = 'UART'
    INFO = ('Über den UART am Stiftfeld sendet der Pi die Werte an GSVmulti: Pin 8 (GPIO14, TXD0) sendet, '
            'Pin 6 ist Masse. Empfangen wird nichts (Pin 10 bleibt frei).',
            'Die Pegel des Pi sind 3,3 V. Nie direkt an RS-232 anschließen (Pegelwandler nötig, OQ-09). '
            'Den 6-poligen Kabelblock nicht auf die Stiftleiste stecken; die Kontaktfolge passt nicht. '
            'Daten fließen über /dev/ttyAMA0; /dev/serial0 zeigt auf ttyAMA10, den 3-Pin-Debug-Header.')

    DEFAULT_CSS = """
    UartView #uart-row { height: auto; width: 1fr; margin: 0; }
    UartView #uart-pins { width: auto; height: auto; }
    UartView #uart-side { width: 1fr; height: auto; padding: 0 0 0 0; }
    UartView #uart-row.side #uart-side { padding: 0 0 0 3; margin: 0; }
    UartView #uart-side Static { width: 1fr; }
    UartView .gap { margin: 1 0 0 0; }
    """

    def compose(self):
        yield Static(Text(self.TITLE, style='bold'), classes='title')
        with Segment(), Horizontal(id='uart-row'):
            yield Static(id='uart-pins')
            with Vertical(id='uart-side'):
                yield Static(id='uart-use')
                yield Static(id='uart-warn', classes='hint gap')
                yield Static(id='uart-ports', classes='gap')
                yield Static(id='f-uart-title', classes='fact-title')
                yield Static(id='f-uart-hint', classes='hint')
                yield Static(id='f-uart-detail')
                yield Static(id='uart-port-change', classes='note')
        yield actions_segment()

    def on_resize(self) -> None:
        if self.is_mounted:
            self.update_view()

    def actions(self) -> list[Action]:
        return super().actions() + [Action('p', 'Port ändern', lambda: None,
                                           blocked='fest auf /dev/ttyAMA0 für GSVmulti')]

    def update_view(self) -> None:
        width = self.size.width or 80
        side = width >= 92
        row = self.query_one('#uart-row', Horizontal)
        row.styles.layout = 'horizontal' if side else 'vertical'
        row.set_class(side, 'side')
        self.query_one('#uart-pins', Static).update(header_graphic(20 if side else 5))
        use = Text()
        use.append('Benutzt', style=f'bold {MUTED}')
        use.append('\nPin 6   GND', style=f'bold {ACCENT}')
        use.append('  Masse zu GSVmulti', style=MUTED)
        use.append('\nPin 8   GPIO14/TXD0', style=f'bold {ACCENT}')
        use.append('  der Pi sendet; nur TX an RX von GSVmulti', style=MUTED)
        use.append('\nPin 10  GPIO15/RXD0', style='bold')
        use.append('  nicht benutzt, nicht bestätigt', style=MUTED)
        use.append('\nAnschluss laut Hardwareprofil, nicht unabhängig bestätigt.', style=MUTED)
        self.query_one('#uart-use', Static).update(use)
        warn = Text()
        warn.append(f'{symbol(probes.WARN)} ', style=TONE[probes.WARN])
        warn.append('Nie direkt an RS-232 anschließen', style='bold')
        warn.append(': Pi-GPIO hat 3,3 V, RS-232 verlangt Pegelwandler (OQ-09).\n'
                    'Den 6-poligen Kabelblock nicht auf die Stiftleiste stecken, die Kontaktfolge passt nicht. '
                    'Zwei Jumper: Block GND an Pin 6, Block RXD an Pin 8.')
        self.query_one('#uart-warn', Static).update(warn)
        ports = Text()
        ports.append('/dev/ttyAMA0', style=f'bold {ACCENT}')
        ports.append('  Datenport für GSVmulti\n')
        ports.append('/dev/serial0', style='bold')
        ports.append('  zeigt auf ttyAMA10, den 3-Pin-Debug-Header, nicht der Datenport')
        self.query_one('#uart-ports', Static).update(ports)
        fact = self.app.fact('uart')
        title = self.query_one('#f-uart-title', Static)
        hint = self.query_one('#f-uart-hint', Static)
        detail = self.query_one('#f-uart-detail', Static)
        if fact is None:
            title.update(Text('Befund UART', style='bold'))
            hint.display = False
            detail.update(Text('Wird geprüft …', style=MUTED))
        else:
            title.update(fact_title(fact))
            block = hint_block(fact)
            hint.display = block is not None
            if block is not None:
                hint.update(block)
                hint.set_class(fact.level == probes.FAIL, 'fail')
            detail.update(kv_table(fact.detail) if fact.detail else Text(''))
        self.query_one('#uart-port-change', Static).update(Text(
            'Port ändern ist nicht vorgesehen: GSVmulti ist fest an /dev/ttyAMA0 angebunden.', style=MUTED))
        self.sync_buttons()
