"""Tab Netzwerk: Schnittstellen, Tailscale, Werkbank-Adresse und Uhr (nur lesen)."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.widgets import Static

from .. import probes
from ..ui import ACCENT, MUTED, TONE, Segment, fact_title, hint_block, kv_table, symbol
from .base import FactView, actions_segment

STATE = {'up': (probes.OK, 'up'), 'down': (probes.OFF, 'down')}


class NetzwerkView(FactView):
    TAB_ID, TITLE, KEY = 'netzwerk', 'Netzwerk', '8'
    FACTS = ('netzwerk', 'uhr')
    INFO_TITLE = 'Netzwerk'
    INFO = ('Die Werkbank ist unter einer festen Adresse erreichbar, die im Zertifikat steht. Liegt diese '
            'Adresse auf keiner Schnittstelle, finden Browser und Brücke den Pi nicht.',
            'Diese Ansicht ist nur zum Lesen. Ändern: WLAN/LAN mit nmcli (z. B. nmcli device status), '
            'Tailscale in der Tailscale-App oder mit tailscale up. Es wird nichts bei fremden Diensten '
            'abgefragt, auch keine öffentliche IP.')

    DEFAULT_CSS = """
    NetzwerkView #net-addr, NetzwerkView #net-clock { margin: 0; }
    """

    def compose(self):
        yield Static(Text(self.TITLE, style='bold'), classes='title')
        yield Segment('Dieser Pi', Static(id='net-host'))
        yield Segment('Schnittstellen', Static(id='net-ifaces'))
        yield Segment('Tailscale', Static(id='net-tailscale'))
        yield Segment('Adresse der Werkbank', Static(id='net-addr'), Static(id='net-addr-hint', classes='hint'))
        yield Segment('Uhrzeit', Static(id='net-clock'), Static(id='net-clock-hint', classes='hint'))
        yield Static(id='net-note', classes='note')
        yield actions_segment()

    def on_resize(self) -> None:
        if self.is_mounted:
            self.update_view()

    def actions(self):
        return []

    def update_view(self) -> None:
        info = self.app.network
        host, ifaces, tail = (self.query_one(f'#net-{n}', Static) for n in ('host', 'ifaces', 'tailscale'))
        if info is None:
            for widget in (host, ifaces, tail):
                widget.update(Text('wird ermittelt …', style=MUTED))
        else:
            host.update(kv_table([('Hostname', info.get('hostname') or '–')]))
            ifaces.update(self._ifaces(info.get('interfaces') or []))
            tail.update(self._tailscale(info.get('tailscale')))
        self._address(info)
        clock = self.app.fact('uhr')
        widget = self.query_one('#net-clock', Static)
        hint = self.query_one('#net-clock-hint', Static)
        if clock is None:
            widget.update(Text('Wird geprüft …', style=MUTED))
            hint.display = False
        else:
            widget.update(fact_title(clock))
            block = hint_block(clock)
            hint.display = block is not None
            if block is not None:
                hint.update(block)
        self.query_one('#net-note', Static).update(Text(
            'Nur zum Ansehen. Ändern mit nmcli (Netz) oder der Tailscale-App.', style=MUTED))
        self.sync_buttons()

    def _ifaces(self, interfaces: list) -> Table | Text:
        if not interfaces:
            return Text('keine Schnittstellen erkannt', style=MUTED)
        wide = (self.size.width or 80) >= 84
        table = Table.grid(padding=(0, 2))
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=True)
        table.add_column(overflow='fold', ratio=1)
        if wide:
            table.add_column(no_wrap=True, style=MUTED)
        for item in interfaces:
            level, word = STATE.get(item.get('state'), (probes.UNKNOWN, 'unbekannt'))
            name = Text()
            name.append(f'{symbol(level)} ', style=TONE[level])
            name.append(str(item.get('name') or '?'), style='bold')
            addresses = ', '.join(item.get('addresses') or []) or '–'
            row = [name, Text(word, style=TONE[level]), addresses]
            if wide:
                row.append(item.get('mac') or '–')
            table.add_row(*row)
        return table

    def _tailscale(self, tailscale) -> Text | Table:
        if tailscale is None:
            return Text('nicht installiert oder nicht erkannt', style=MUTED)
        return kv_table([('Zustand', str(tailscale.get('state') or '–')),
                         ('Name', tailscale.get('name') or '–'),
                         ('Adressen', ', '.join(tailscale.get('addresses') or []) or '–')])

    def _address(self, info) -> None:
        widget = self.query_one('#net-addr', Static)
        hint = self.query_one('#net-addr-hint', Static)
        fact = self.app.fact('netzwerk')
        if fact is None:
            widget.update(Text('Wird geprüft …', style=MUTED))
            hint.display = False
            return
        text = Text()
        text.append_text(fact_title(fact))
        address = self.app.instance.host or dict(fact.detail).get('Werkbank-Adresse') or '–'
        on = None
        if info is not None and address != '–':
            on = next((i['name'] for i in info.get('interfaces') or []
                       if any(a.split('/')[0] == address for a in i.get('addresses') or [])), None)
        text.append(f'\nAdresse {address}  ', style=MUTED)
        if on:
            text.append(f'{symbol(probes.OK)} liegt auf {on}', style=TONE[probes.OK])
        elif info is not None and fact.level == probes.OK:
            text.append('ist ein Name dieses Pi', style=ACCENT)
        elif info is not None:
            text.append(f'{symbol(probes.FAIL)} liegt auf keiner Schnittstelle', style=TONE[probes.FAIL])
        widget.update(text)
        block = hint_block(fact)
        hint.display = block is not None
        if block is not None:
            hint.update(block)
            hint.set_class(fact.level == probes.FAIL, 'fail')
            hint.set_class(fact.level not in (probes.FAIL, probes.WARN), 'info')
