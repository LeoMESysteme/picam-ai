"""Tab Ausgabe: die vier Wege der Werte (Aus, UART direkt, UART über Brücke, Netzwerk) mit Einzelheiten."""

from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal
from textual.widgets import Static

from dispread.bridge.baud import UART_BAUD
from dispread.hardware_ports import DIRECT_UART_BAUD, GSV_UART_PORT

from .. import probes
from ..ui import MUTED, TONE, Action, Segment, ascii_mode, kv_table, symbol
from .base import FactView, actions_segment

DASH = '–'
#: (Schlüssel in live.status.output.transport, lange Beschriftung, kurze Beschriftung)
PATHS = (('off', 'Aus', 'Aus'), ('serial', 'UART direkt', 'UART'),
         ('uart', 'UART über Brücke', 'Brücke UART'), ('tcp', 'Netzwerk (Brücke)', 'Brücke Netz'))
UART_STATES = {'unprepared': 'nicht vorbereitet', 'prepared': 'vorbereitet', 'ready': 'bereit'}


class PathTab(Static):
    """Ein Unter-Tab; Klick wählt ihn."""

    def __init__(self, index: int):
        super().__init__(id=f'path-{index}', classes='path')
        self.index = index

    def on_click(self) -> None:
        self.query_ancestor(AusgabeView).choose(self.index)


class AusgabeView(FactView):
    TAB_ID, TITLE, KEY = 'ausgabe', 'Ausgabe', '5'
    FACTS = ('ausgabe', 'bruecke')
    INFO_TITLE = 'Ausgabe und Brücke'
    INFO = ('Die Ausgabe ist der Weg, auf dem die gelesenen Werte zu GSVmulti kommen. Es gibt vier Wege: '
            '„Aus“ (nur aufzeichnen), „UART direkt“ (Kabel vom Pi zu GSVmulti), „UART über Brücke“ '
            '(Kabel zur Windows-Brücke) und „Netzwerk (Brücke)“ (Windows-Brücke per Netzwerk).',
            'Den Weg wählt man beim Laufstart in der Werkbank; er wird nicht im Dienst gespeichert. Hier '
            'sieht man, welcher Weg im laufenden Lauf benutzt wird, und die Einzelheiten jedes Wegs.',
            'Mit „w“, den Unter-Tabs oder der Maus wechselt man die Ansicht. Das ändert nichts am Lauf.',
            'Pi-Pegel nie direkt an RS-232 anschließen: dafür gehört ein Pegelwandler dazwischen.')
    SCOPED_CSS = False
    DEFAULT_CSS = """
    AusgabeView #paths { height: 1; margin: 0; }
    AusgabeView .path { width: auto; padding: 0 1; margin: 0 1 0 0; color: $picam-text-soft; }
    AusgabeView .path.-sel { color: $picam-text; background: $picam-raised; text-style: bold underline; }
    AusgabeView .seg:focus-within .path.-sel { background: $picam-surface; }
    AusgabeView #out-active { margin: 0; }
    AusgabeView #out-body { margin: 1 0 0 0; }
    Screen.stacked AusgabeView .buttons { layout: grid; grid-size: 2; grid-gutter: 0 1; grid-rows: 1; }
    Screen.stacked AusgabeView .buttons Button { width: 100%; margin: 0; }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path_sel: int | None = None

    def compose(self):
        yield Static(Text(self.TITLE, style='bold'), classes='title')
        yield Segment(None, Static(id='out-active'))
        yield Segment(None, Horizontal(*[PathTab(i) for i in range(len(PATHS))], id='paths'), Static(id='out-body'))
        yield actions_segment()

    # ------------------------------------------------------------ Zustand
    def active_index(self) -> int | None:
        live = self.app.snapshot.live if self.app.snapshot is not None else None
        if not live or live.get('state') != 'running':
            return None
        transport = (live.get('output') or {}).get('transport') or 'off'
        for index, (key, _, _) in enumerate(PATHS):
            if key == transport:
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
        self.app.refresh_footer()

    def next_path(self) -> None:
        self.choose(self.selected_index() + 1)

    # ------------------------------------------------------------ Anzeige
    def update_view(self) -> None:
        active, chosen = self.active_index(), self.selected_index()
        wide = self.size.width >= 76 or self.size.width == 0
        for index, (_, long, short) in enumerate(PATHS):
            tab = self.query_one(f'#path-{index}', PathTab)
            mark = ('*' if ascii_mode() else '●') if index == active else ' '
            text = Text()
            text.append(mark + ' ', style=TONE[probes.OK] if index == active else MUTED)
            text.append(long if wide else short)
            tab.update(text)
            tab.set_class(index == chosen, '-sel')
        self.query_one('#out-active', Static).update(self._active_line(active))
        self.query_one('#out-body', Static).update(self._body(chosen, active))
        self.sync_buttons()

    def _active_line(self, active: int | None) -> Text:
        app = self.app
        text = Text()
        live = app.snapshot.live if app.snapshot is not None else None
        if app.snapshot is None:
            text.append('Wird geprüft …', style=MUTED)
        elif not live:
            text.append(f'{symbol(probes.UNKNOWN)} Ausgabe unbekannt (Werkbank nicht erreichbar)',
                        style=TONE[probes.UNKNOWN])
        elif active is None:
            text.append(f'{symbol(probes.OFF)} Kein Lauf', style=MUTED)
            text.append(' – den Weg wählt man beim Laufstart in der Werkbank.', style=MUTED)
        else:
            output = live.get('output') or {}
            error = output.get('error')
            if error:
                text.append(f'{symbol(probes.FAIL)} {PATHS[active][1]}: Fehler – {error}', style=TONE[probes.FAIL])
            elif active == 0:
                text.append(f'{symbol(probes.OFF)} Aus', style='bold')
                text.append(' – keine Ausgabe, Werte werden nur aufgezeichnet', style=MUTED)
            else:
                text.append(f'{symbol(probes.OK)} Im Lauf: {PATHS[active][1]}', style=f'bold {TONE[probes.OK]}')
                text.append(f' · Zustand {output.get("state") or DASH}', style=MUTED)
        return text

    def _bridge_rows(self) -> list[tuple[str, str]]:
        bridge = self.app.fact('bruecke')
        detail = dict(bridge.detail) if bridge is not None else {}
        out = dict(self.app.fact('ausgabe').detail) if self.app.fact('ausgabe') is not None else {}
        return [('Brücke', out.get('Brücke') or (bridge.value if bridge is not None else DASH)),
                ('Kopplungen', detail.get('Kopplungen') or DASH),
                ('Pi-ID', detail.get('Pi-ID') or DASH)]

    def _body(self, chosen: int, active: int | None):
        app = self.app
        live = app.snapshot.live if app.snapshot is not None else None
        output = (live or {}).get('output') or {}
        state = str(output.get('state') or DASH) if active == chosen else 'nicht in Benutzung'
        out = Text()
        if chosen == 0:
            out.append('Keine Ausgabe. ', style='bold')
            out.append('Werte werden nur aufgezeichnet und nicht an GSVmulti gesendet. Sinnvoll zum Einrichten '
                       'und Üben.', style=MUTED)
            return out
        bridge = app.fact('bruecke')
        bridge_detail = dict(bridge.detail) if bridge is not None else {}
        if chosen == 1:
            uart = app.fact('uart')
            uart_detail = dict(uart.detail) if uart is not None else {}
            rows = [('Port', GSV_UART_PORT), ('Baudrate', f'{DIRECT_UART_BAUD} (Standard, je Lauf wählbar)'),
                    ('Zustand', state), ('Gerät', uart_detail.get('Gerät') or DASH),
                    ('Boot', uart_detail.get('Boot') or DASH)]
            out_note = 'Direkt vom Pi zu GSVmulti; RS-232 nur über Pegelwandler.'
        elif chosen == 2:
            prepared = UART_STATES.get(bridge_detail.get('UART-Empfang'), bridge_detail.get('UART-Empfang'))
            rows = [('Port', GSV_UART_PORT), ('Baudrate', str(UART_BAUD)), ('Zustand', state),
                    ('UART-Empfang', prepared or DASH), *self._bridge_rows()]
            out_note = 'Über das Kabel zur Windows-Brücke; sie gibt die Werte an GSVmulti weiter.'
        else:
            rows = [('Werkbank', app.instance.url or DASH), ('Zustand', state), *self._bridge_rows()]
            out_note = 'Über das Netzwerk zur gekoppelten Windows-Brücke (verschlüsselt, HTTPS).'
        group = Text()
        group.append(out_note + '\n', style=MUTED)
        from rich.console import Group
        return Group(group, kv_table(rows))

    # ------------------------------------------------------------ Aktionen
    def actions(self) -> list[Action]:
        app = self.app
        actions = [Action('w', 'Weg wechseln', self.next_path)]
        if self.selected_index() == 2:
            service = app.fact('dienst')
            down = None if service is not None and service.level in (probes.OK, probes.WARN) \
                else 'Werkbank läuft nicht'
            bridge = app.fact('bruecke')
            state = dict(bridge.detail).get('UART-Empfang') if bridge is not None else None
            ready = state in ('vorbereitet', 'bereit')
            actions += [Action('p', 'UART-Empfang vorbereiten', app.bridge_prepare,
                               blocked=down or ('schon vorbereitet' if ready else None)),
                        Action('e', 'UART-Empfang beenden', app.bridge_stop, danger=True,
                               blocked=down or app.blocker or (None if ready else 'nicht vorbereitet'))]
        return actions + super().actions()

    def sync_buttons(self) -> None:
        bar = self.query_one('#buttons', Horizontal)
        have = {b.id for b in bar.query('Button.act')}
        shown = {a.key for a in self.actions()}
        for action in self.actions():
            if f'act-{action.key}' not in have:
                bar.mount(self.action_button(action))
        for key in ('p', 'e'):
            for button in self.query(f'#act-{key}'):
                button.display = key in shown
        super().sync_buttons()
