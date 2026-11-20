"""Tab Netzwerk: Schnittstellen, Tailscale, Werkbank-Adresse und Uhr (nur lesen)."""

from __future__ import annotations

from rich.text import Text

from .. import probes
from ..ui import MUTED
from ..widgets import (
    ActionBar,
    SectionCard,
    TabBody,
    badge,
    detail_rows,
    fact_badge,
    fact_help,
    fields,
    header,
    help_line,
    shorten,
    value,
)
from .base import FactView

STATE = {'up': (probes.OK, 'up', 'on'), 'down': (probes.OFF, 'down', 'off')}
LABEL_W = 12
TAILSCALE = {'Running': probes.OK, 'Stopped': probes.OFF, 'NeedsLogin': probes.WARN}


class NetzwerkView(FactView):
    TAB_ID, TITLE, KEY = 'netzwerk', 'Netzwerk', '8'
    FACTS = ('netzwerk', 'uhr')
    INFO_TITLE = 'Netzwerk'
    ABOUT = ('Die Werkbank ist unter einer festen Adresse erreichbar, die im Zertifikat steht. Liegt diese '
             'Adresse auf keiner Schnittstelle, finden Browser und Brücke den Pi nicht.',
             'Diese Ansicht ist nur zum Lesen. Ändern: WLAN/LAN mit nmcli (z. B. nmcli device status), '
             'Tailscale in der Tailscale-App oder mit tailscale up. Es wird nichts bei fremden Diensten '
             'abgefragt, auch keine öffentliche IP.')
    INFO_FACTS = FACTS

    def compose(self):
        with TabBody(classes='tab-body'):
            yield SectionCard(id='net-ifaces')
            yield SectionCard(id='net-addr')
            yield SectionCard(id='net-tailscale')
            yield SectionCard(id='net-clock')
        yield ActionBar()

    def actions(self):
        return []

    def update_view(self) -> None:
        info = self.app.network
        cards = {n: self.query_one(f'#net-{n}', SectionCard) for n in ('ifaces', 'addr', 'tailscale', 'clock')}
        width = self.card_width(cards['ifaces'])
        waiting = Text('wird ermittelt …', style=MUTED)
        if info is None:
            body = waiting
        else:
            body = fields([('Hostname', value(info.get('hostname')))], width, label_w=LABEL_W)
            body.append('\n')
            body.append_text(self._ifaces(info.get('interfaces') or [], width))
        cards['ifaces'].show(header('network', 'Dieser Pi', None, width), body,
                             help_line('Nur zum Ansehen. Ändern mit nmcli (Netz) oder der Tailscale-App.'))
        self._address(cards['addr'], info, width)
        tailscale = (info or {}).get('tailscale')
        if info is None:
            cards['tailscale'].show(header('tailscale', 'Tailscale', None, width), waiting)
        elif tailscale is None:
            cards['tailscale'].show(header('tailscale', 'Tailscale', badge(probes.OFF, 'nicht erkannt'), width),
                                    None, help_line('Nicht installiert oder nicht erkannt.'))
        else:
            state = str(tailscale.get('state') or '–')
            level = TAILSCALE.get(state, probes.UNKNOWN)
            rows = [('Name', value(tailscale.get('name')), True),
                    ('Adressen', value(', '.join(tailscale.get('addresses') or []) or None), True)]
            cards['tailscale'].show(
                header('tailscale', 'Tailscale', badge(level, state, 'on' if level == probes.OK else None), width),
                fields(rows, width, label_w=LABEL_W))
        clock = self.app.fact('uhr')
        cards['clock'].show(header('clock', 'Uhrzeit', fact_badge(clock), width),
                            fields(detail_rows(clock), width, label_w=LABEL_W), fact_help(clock))
        self.sync_buttons()

    def _ifaces(self, interfaces: list, width: int) -> Text:
        if not interfaces:
            return Text('keine Schnittstellen erkannt', style=MUTED)
        name_w = max(LABEL_W, max(len(str(i.get('name') or '?')) for i in interfaces) + 2)
        states = [badge(*self._state(item)) for item in interfaces]
        addresses = [value(', '.join(item.get('addresses') or []) or None) for item in interfaces]
        state_w = max(s.cell_len for s in states) + 2
        addr_w = max(a.cell_len for a in addresses) + 3
        wide = name_w + state_w + addr_w + 19 <= width
        text = Text(no_wrap=True)
        for index, item in enumerate(interfaces):
            if index:
                text.append('\n')
            text.append(str(item.get('name') or '?').ljust(name_w), style=MUTED)
            text.append_text(states[index])
            text.append(' ' * (state_w - states[index].cell_len))
            field = shorten(addresses[index], max(6, width - name_w - state_w))
            text.append_text(field)
            if wide:
                text.append(' ' * (addr_w - field.cell_len))
                text.append_text(value(item.get('mac'), tone=MUTED))
        return text

    @staticmethod
    def _state(item: dict) -> tuple[str, str, str]:
        return STATE.get(item.get('state'), (probes.UNKNOWN, 'unbekannt', 'unknown'))

    def _address(self, card: SectionCard, info, width: int) -> None:
        fact = self.app.fact('netzwerk')
        if fact is None:
            card.show(header('address', 'Adresse der Werkbank', fact_badge(None), width))
            return
        address = self.app.instance.host or dict(fact.detail).get('Werkbank-Adresse')
        on = None
        if info is not None and address:
            on = next((i['name'] for i in info.get('interfaces') or []
                       if any(a.split('/')[0] == address for a in i.get('addresses') or [])), None)
        if on:
            where = badge(probes.OK, f'liegt auf {on}')
        elif info is not None and fact.level == probes.OK:
            where = badge(probes.OK, 'ist ein Name dieses Pi')
        elif info is not None:
            where = badge(probes.FAIL, 'liegt auf keiner Schnittstelle')
        else:
            where = value(None)
        rows = [('Adresse', value(address)), ('Erreichbar', where)]
        card.show(header('address', 'Adresse der Werkbank', fact_badge(fact), width),
                  fields(rows, width, label_w=LABEL_W, columns=2 if width >= 60 else 1),
                  fact_help(fact, 'Steht im Zertifikat und in den Kopplungen.'))
