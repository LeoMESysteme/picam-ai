"""Tab UART: Stiftleiste des Pi mit den benutzten Pins, Warnungen und Befund."""

from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from dispread.hardware_ports import same_port, uart_devices

from .. import probes, uart_ports
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


def used_pins(function) -> tuple[dict[int, str], dict[int, str], dict[int, str], dict[int, str]]:
    """Vermerke der Stiftleiste für die konfigurierte UART-Funktion: (benutzt, frei, kurz benutzt, kurz frei).

    ``function`` ist eine ``uart_ports.UartFunction`` oder ``None`` (Vorgabe: UART0, Pin 8/10, Masse Pin 6).
    """
    tx, rx = (function.tx_pin, function.rx_pin) if function is not None else (8, 10)
    return ({6: 'benutzt', tx: 'benutzt (Senden)'}, {rx: 'nicht benutzt'},
            {6: 'benutzt', tx: 'sendet'}, {rx: 'frei'})


def header_graphic(rows: int, compact: bool = False, *, used_full=None, unused_full=None, used_short=None,
                   unused_short=None, selected: int | None = None, choices=frozenset()) -> Text:
    """Stiftleiste: Pin 1 oben links, ungerade Pins links. ``rows`` = Pinpaare (20 = ganz).

    ``compact``: kurze Vermerke („sendet“, „frei“), damit die Leiste in 60 Spalten passt.
    ``selected``: gewählter Pin (Auswahlfläche); ``choices``: Pins, die eine UART-Funktion haben
    (Aus­wahl­punkt ``▸`` statt Punkt). Ohne die Vermerk-Angaben gilt die Vorgabe (Pin 6 und 8 benutzt).
    """
    used_all = USED if used_full is None else used_full
    unused_all = UNUSED if unused_full is None else unused_full
    used, unused = ((USED_SHORT if used_short is None else used_short),
                    (UNUSED_SHORT if unused_short is None else unused_short)) if compact else (used_all, unused_all)
    ascii_only = ascii_mode()
    tl, tm, tr = ('+', '+', '+') if ascii_only else ('┌', '┬', '┐')
    bl, bm, br = ('+', '+', '+') if ascii_only else ('└', '┴', '┘')
    side, dot_on, dot_off = ('|', '*', 'o') if ascii_only else ('│', '●', '○')
    arrow = '<' if ascii_only else '◀'
    pick = '>' if ascii_only else '◆'
    text = Text(no_wrap=True)
    pad = ' ' * 11
    text.append(f'{pad}{tl}───{tm}───{tr}\n'.replace('─', '-' if ascii_only else '─'), style=MUTED)
    chosen = f'bold {P.select_fg} on {P.select_bg}'
    for row in range(1, rows + 1):
        left, right = 2 * row - 1, 2 * row

        def tone(pin: int) -> str:
            name = PIN_NAMES[pin]
            if pin == selected:
                return chosen
            if pin in used_all:
                return f'bold {ACCENT}'
            if name == 'GND':
                return MUTED
            if name == '5V':
                return POWER_5V
            if name == '3V3':
                return POWER_3V3
            return MUTED if pin not in unused_all else ''

        def dot(pin: int, default: str) -> str:
            return pick if pin in choices else default

        text.append(PIN_NAMES[left].rjust(7), style=tone(left))
        text.append(f' {left:>2} ', style=tone(left))
        text.append(side, style=MUTED)
        text.append(f' {dot(left, dot_on)} ', style=tone(left))
        text.append(side, style=MUTED)
        right_dot = dot(right, dot_off if right in unused_all else dot_on)
        text.append(f' {right_dot} ', style=tone(right))
        text.append(side, style=MUTED)
        text.append(f' {right:<2}  ', style=tone(right))
        text.append(PIN_NAMES[right], style=tone(right))
        if right in used:
            text.append(f'  {arrow} {used[right]}', style=f'bold {ACCENT}')
        elif right in unused:
            text.append(f'  {arrow} {unused[right]}', style=MUTED)
        if left in used and left != 6:
            text.append(f'  {arrow} Pin {left}: {used[left]}', style=f'bold {ACCENT}')
        text.append('\n')
    if rows < 20:
        text.append(f"{pad}{side} {':' if ascii_only else '·'} {side} {':' if ascii_only else '·'} {side}"
                    f'   Pins {2 * rows + 1}–40 nicht benutzt\n', style=MUTED)
    text.append(f'{pad}{bl}───{bm}───{br}'.replace('─', '-' if ascii_only else '─'), style=MUTED)
    return text


def output_function(output_port: str, mapped: dict[str, str] | None = None):
    """``UartFunction`` zum konfigurierten Ausgang (``uartN`` oder Gerätepfad); None, wenn unbekannt."""
    if output_port.startswith('uart'):
        return next((f for f in uart_ports.UARTS if f.uart == output_port), None)
    mapped = uart_devices() if mapped is None else mapped
    name = next((key for key, port in mapped.items() if same_port(port, output_port)), None)
    if name is None and output_port == '/dev/ttyAMA0':
        name = 'uart0'
    return next((f for f in uart_ports.UARTS if f.uart == name), None)


def output_label(output_port: str) -> str:
    """Anzeige des Ausgangs: Gerätepfad, bei ``uartN`` mit aufgelöstem Gerät oder Hinweis."""
    if not output_port.startswith('uart'):
        return output_port
    device = uart_devices().get(output_port)
    return f'{output_port} ({device or uart_ports.CHECK_AFTER_REBOOT})'


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
             'Standard ist /dev/ttyAMA0 (UART0); /dev/serial0 zeigt auf ttyAMA10, den 3-Pin-Debug-Header. '
             'Mit „Port ändern“ wählen Sie einen anderen freien UART-Ausgang und den USB-RS232-Adapter '
             'der Referenz; config.txt und Konfiguration werden erst nach Prüfseite und Bestätigung '
             'geschrieben, ein Pi-Neustart kann nötig sein.')
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
        return super().actions() + [Action('p', 'Port ändern', self.change_ports, icon='uart',
                                           blocked=self.change_blocker())]

    def change_blocker(self) -> str | None:
        instance = self.app.instance
        if instance.problem:
            return instance.problem
        if not instance.config:
            return 'Instanz ohne config.toml'
        return self.app.blocker

    def change_ports(self) -> None:
        if self.change_blocker() is None:
            from .uart_screen import UartPortsScreen

            self.app.push_screen(UartPortsScreen(self.app.instance))

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
        instance = self.app.instance
        function = output_function(instance.output_port)
        full, unused_full, short, unused_short = used_pins(function)
        tx, rx = (function.tx_pin, function.rx_pin) if function else (8, 10)
        graphic = header_graphic(20 if side else max(5, (max(tx, rx) + 1) // 2), compact=not side and width < FULL_W,
                                 used_full=full, unused_full=unused_full, used_short=short,
                                 unused_short=unused_short)
        self.query_one('#uart-pins-head', Static).update(
            header('pins', 'Stiftleiste', None, graphic.cell_len if side else width))
        self.query_one('#uart-pins', Static).update(graphic)
        use = self.query_one('#uart-use', SectionCard)
        side_w = self.card_width(use)
        gpio_tx = function.tx_gpio if function else 14
        gpio_rx = function.rx_gpio if function else 15
        rows = [('Pin 6', value('GND', tone=ACCENT, bold=True), 'Masse zu GSVmulti'),
                (f'Pin {tx}', value(f'GPIO{gpio_tx}' + ('/TXD0' if tx == 8 else ''), tone=ACCENT, bold=True),
                 'der Pi sendet; nur TX an RX von GSVmulti'),
                (f'Pin {rx}', value(f'GPIO{gpio_rx}' + ('/RXD0' if rx == 10 else '')),
                 'nicht benutzt, nicht bestätigt'),
                ('RS-232', badge(probes.WARN, 'nie direkt'), '3,3 V am Pi: Pegelwandler nötig (OQ-09)'),
                ('Kabelblock', badge(probes.WARN, 'nicht aufstecken'),
                 f'2 Jumper: GND → Pin 6, RXD → Pin {tx}')]
        if not side:  # breit genug: Nachsatz in derselben Zeile
            rows = [(label, join(content, f'  {note}')) for label, content, note in rows]
        use.show(header('connect', 'Anschluss', None, side_w), wrap_rows(rows, label_w=11 if side else 12),
                 help_line('Laut Hardwareprofil, nicht unabhängig bestätigt.'))
        rows = [('Datenport', value(output_label(instance.output_port), tone=ACCENT, bold=True), 'für GSVmulti'),
                ('Referenz', value(instance.reference_port), 'USB-RS232-Adapter am Messverstärker'),
                ('Debug', value('/dev/serial0'), 'zeigt auf ttyAMA10, den 3-Pin-Debug-Header')]
        if not side:
            rows = [(label, join(content, f'  {note}')) for label, content, note in rows]
        self.query_one('#uart-ports', SectionCard).show(
            header('file', 'Ports', None, side_w), wrap_rows(rows, label_w=11 if side else 12),
            help_line('Port ändern: Taste p.', 'i', 'mehr'))
        self.sync_buttons()
