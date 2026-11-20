"""Tab Ausgabe: die vier Wege der Werte (Aus, UART direkt, UART über Brücke, Netzwerk) mit Einzelheiten.

Die Wege sind eine reine Auswahl der Ansicht: ← → oder Klick zeigen die
Einzelheiten eines Wegs. Welcher Weg im Lauf benutzt wird, trägt das Abzeichen
„● im Lauf“; gewählt wird er beim Laufstart in der Werkbank.

Karte „Ausgabe“ (Lauf), darunter eine Karte mit Auswahlleiste und den
Einzelheiten des gewählten Wegs.
"""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.widgets import Static

from dispread.bridge.baud import UART_BAUD
from dispread.hardware_ports import DIRECT_UART_BAUD, GSV_UART_PORT

from .. import probes
from ..ui import Action
from ..widgets import (
    ActionBar,
    CardBox,
    ChipSelector,
    SectionCard,
    TabBody,
    badge,
    clip,
    fact_badge,
    fields,
    header,
    help_line,
    value,
)
from .base import FactView

DASH = '–'
#: (Schlüssel in live.status.output.transport, lange Beschriftung, kurze Beschriftung, Zeichen)
PATHS = (('off', 'Aus', 'Aus', 'off'), ('serial', 'UART direkt', 'UART', 'uart'),
         ('uart', 'UART über Brücke', 'Brücke UART', 'bridge'),
         ('tcp', 'Netzwerk (Brücke)', 'Brücke Netz', 'network'))
UART_STATES = {'unprepared': 'nicht vorbereitet', 'prepared': 'vorbereitet', 'ready': 'bereit'}
UART_LEVELS = {'nicht vorbereitet': probes.OFF, 'vorbereitet': probes.OK, 'bereit': probes.OK}
NOTES = ('Werte werden nur aufgezeichnet, nicht an GSVmulti gesendet.',
         'Direkt vom Pi zu GSVmulti; RS-232 nur über Pegelwandler.',
         'Über das Kabel zur Windows-Brücke; sie gibt die Werte an GSVmulti weiter.',
         'Über das Netzwerk zur gekoppelten Windows-Brücke (verschlüsselt, HTTPS).')
CHOSEN_AT_START = 'Den Weg wählt man beim Laufstart in der Werkbank; hier nur ansehen.'


class AusgabeView(FactView):
    TAB_ID, TITLE, KEY = 'ausgabe', 'Ausgabe', '5'
    FACTS = ('ausgabe', 'bruecke')
    OWN_BAR = True
    INFO_TITLE = 'Ausgabe und Brücke'
    INFO = ('Die Ausgabe ist der Weg, auf dem die gelesenen Werte zu GSVmulti kommen. Es gibt vier Wege: '
            '„Aus“ (nur aufzeichnen), „UART direkt“ (Kabel vom Pi zu GSVmulti), „UART über Brücke“ '
            '(Kabel zur Windows-Brücke) und „Netzwerk (Brücke)“ (Windows-Brücke per Netzwerk).',
            'Den Weg wählt man beim Laufstart in der Werkbank; er wird nicht im Dienst gespeichert. Hier '
            'sieht man, welcher Weg im laufenden Lauf benutzt wird („● im Lauf“), und die Einzelheiten jedes Wegs.',
            'Mit ← → oder der Maus wählt man, welcher Weg hier gezeigt wird. Das ändert nichts am Lauf.',
            'Pi-Pegel nie direkt an RS-232 anschließen: dafür gehört ein Pegelwandler dazwischen.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path_sel: int | None = None

    def compose(self):
        with TabBody(classes='tab-body'):
            yield SectionCard(id='out-active')
            with CardBox(id='out-paths'):
                yield ChipSelector(id='paths')
                yield Static(id='out-body')
        yield ActionBar()

    # ------------------------------------------------------------ Zustand
    def _live(self) -> dict | None:
        return self.app.snapshot.live if self.app.snapshot is not None else None

    def active_index(self) -> int | None:
        live = self._live()
        if not live or live.get('state') != 'running':
            return None
        transport = (live.get('output') or {}).get('transport') or 'off'
        for index, path in enumerate(PATHS):
            if path[0] == transport:
                return index
        return None

    def selected_index(self) -> int:
        if self.path_sel is not None:
            return self.path_sel
        active = self.active_index()
        return active if active is not None else 1

    def choose(self, index: int) -> None:
        self.path_sel = index % len(PATHS)
        self.update_view()

    @on(ChipSelector.Selected, '#paths')
    def _chip_selected(self, event: ChipSelector.Selected) -> None:
        if event.index != self.selected_index():
            self.choose(event.index)

    # ------------------------------------------------------------ Inhalte
    def _run_state(self, active: int | None) -> tuple[Text, list]:
        """Abzeichen und Zeilen zum Lauf (welcher Weg, Zustand, Fehler)."""
        app = self.app
        live = self._live()
        output = (live or {}).get('output') or {}
        if app.snapshot is None:
            return badge(probes.UNKNOWN, 'wird geprüft', 'busy'), []
        if not live:
            return badge(probes.UNKNOWN, 'Werkbank nicht erreichbar'), [('Weg im Lauf', value(None))]
        if active is None:
            return badge(probes.OFF, 'kein Lauf'), [('Weg im Lauf', value(None))]
        rows = [('Weg im Lauf', value(PATHS[active][1])), ('Zustand', value(output.get('state')))]
        if output.get('error'):
            rows.append(('Fehler', badge(probes.FAIL, str(output['error'])), True))
            return badge(probes.FAIL, 'Fehler'), rows
        return badge(probes.OK, 'Lauf aktiv', 'on'), rows

    def _bridge_rows(self) -> list:
        app = self.app
        bridge = app.fact('bruecke')
        detail = dict(bridge.detail) if bridge is not None else {}
        out = dict(app.fact('ausgabe').detail) if app.fact('ausgabe') is not None else {}
        state = out.get('Brücke')
        connected = state == 'verbunden' or (bridge is not None and bridge.value == 'verbunden')
        if connected:
            link = badge(probes.OK, 'verbunden', 'on')
        elif bridge is None or bridge.level == probes.FAIL:
            link = fact_badge(bridge)
        else:
            # Grün nur bei stehender Verbindung: braucht der Lauf die Brücke, ist „nicht
            # verbunden“ eine Warnung, sonst nur ein grauer Ruhezustand.
            live = self._live() or {}
            needed = live.get('state') == 'running' and (live.get('output') or {}).get('transport') in ('uart', 'tcp')
            link = badge(probes.WARN if needed else probes.OFF, 'nicht verbunden', 'off')
        rows = [('Verbindung', link)]
        if bridge is not None and bridge.level != probes.FAIL:
            paired = bridge.value in ('verbunden', 'gekoppelt')
            rows.append(('Kopplung', badge(probes.OK if paired else bridge.level,
                                           'gekoppelt' if paired else str(bridge.value), 'on' if paired else None)))
        return rows + [('Kopplungen', value(detail.get('Kopplungen'))), ('Pi-ID', value(detail.get('Pi-ID')))]

    def _path_rows(self, chosen: int) -> list:
        """Einzelheiten eines Wegs; „im Lauf“ steht an der Auswahl, der Zustand in der Karte „Ausgabe“."""
        app = self.app
        status: list = []
        if chosen == 0:
            return status
        if chosen == 1:
            uart = dict(app.fact('uart').detail) if app.fact('uart') is not None else {}
            return [*status, ('Port', value(GSV_UART_PORT)),
                    ('Baudrate', value(DIRECT_UART_BAUD, 'Bd · Standard, je Lauf wählbar')),
                    ('Gerät', value(uart.get('Gerät'))), ('Boot', value(uart.get('Boot')))]
        if chosen == 2:
            bridge = app.fact('bruecke')
            raw = dict(bridge.detail).get('UART-Empfang') if bridge is not None else None
            prepared = UART_STATES.get(raw, raw)
            receive = badge(UART_LEVELS.get(prepared, probes.UNKNOWN), prepared) if prepared else value(None)
            return [*status, ('Port', value(GSV_UART_PORT)), ('Baudrate', value(UART_BAUD, 'Bd')),
                    ('UART-Empfang', receive), *self._bridge_rows()]
        return [*status, ('Werkbank', value(app.instance.url), True), *self._bridge_rows()]

    # ------------------------------------------------------------ Anzeige
    def update_view(self) -> None:
        active, chosen = self.active_index(), self.selected_index()
        card = self.query_one('#out-active', SectionCard)
        width = self.card_width(card)
        state, rows = self._run_state(active)
        card.show(header('output', 'Ausgabe', state, width), fields(rows, width, label_w=14, columns=2),
                  help_line(CHOSEN_AT_START))
        selector = self.query_one('#paths', ChipSelector)
        long = sum(len(p[1]) + 6 for p in PATHS) + 12 <= width
        items = [(glyph, (label if long else short), badge(probes.OK, 'im Lauf', 'on') if i == active else None)
                 for i, (_, label, short, glyph) in enumerate(PATHS)]
        selector.set_items(items, chosen)
        # Der Zustand des Wegs im Lauf steht schon in der Karte „Ausgabe“
        body = fields(self._path_rows(chosen), width, label_w=14, columns=2)
        text = Text()
        if body.plain:
            text.append_text(body)
            text.append('\n')
        text.append_text(clip(help_line(NOTES[chosen]), width))
        self.query_one('#out-body', Static).update(text)
        self.sync_buttons()

    # ------------------------------------------------------------ Aktionen
    def actions(self) -> list[Action]:
        app = self.app
        actions = []
        if self.selected_index() == 2:
            service = app.fact('dienst')
            down = None if service is not None and service.level in (probes.OK, probes.WARN) \
                else 'Werkbank läuft nicht'
            bridge = app.fact('bruecke')
            state = dict(bridge.detail).get('UART-Empfang') if bridge is not None else None
            ready = state in ('vorbereitet', 'bereit')
            actions += [Action('p', 'UART-Empfang vorbereiten', app.bridge_prepare, icon='bridge',
                               blocked=down or ('schon vorbereitet' if ready else None)),
                        Action('e', 'UART-Empfang beenden', app.bridge_stop, danger=True, icon='stop',
                               blocked=down or app.blocker or (None if ready else 'nicht vorbereitet'))]
        return actions + super().actions()
