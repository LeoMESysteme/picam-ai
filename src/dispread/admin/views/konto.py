"""Tab Konto: Anmeldung an der Werkbank, Gruppen und Benutzerdienst."""

from __future__ import annotations

from rich.text import Text

from .. import probes
from ..ui import MUTED, TEXT, Action, P
from ..widgets import (
    ActionBar,
    SectionCard,
    TabBody,
    badge,
    fact_badge,
    fact_help,
    fields,
    header,
    help_line,
    join,
    value,
)
from .base import FactView

GROUP_WHY = (('video', 'Kamera (/dev/video…)'), ('dialout', 'serielle Schnittstelle (/dev/ttyAMA0)'))


class KontoView(FactView):
    TAB_ID, TITLE, KEY = 'konto', 'Konto', '0'
    FACTS = ('konto', 'linger')
    INFO_TITLE = 'Konto und Anmeldung'
    ABOUT = ('An der Werkbank im Browser meldet man sich mit dem Linux-Konto des Dienstes an, mit dessen '
             'Linux-Passwort. Es gibt kein eigenes Werkbank-Passwort.',
             'Passwort ändern: im Terminal passwd eingeben. Das gilt dann auch für die SSH-Anmeldung. '
             'Die Konsole speichert und ändert keine Passwörter.',
             'Das Konto braucht die Gruppen video (Kamera) und dialout (UART).')
    INFO_FACTS = FACTS

    def compose(self):
        with TabBody(classes='tab-body'):
            yield SectionCard(id='kt-login')
            yield SectionCard(id='kt-groups')
            yield SectionCard(id='kt-linger')
            yield SectionCard(id='kt-passwd')
        yield ActionBar()

    def actions(self) -> list[Action]:
        return super().actions() + [Action('p', 'Passwort ändern', lambda: None, icon='key',
                                           blocked='im Terminal mit passwd, nicht in der Konsole')]

    def _user(self) -> str | None:
        user = self.app.instance.pam_user
        if user:
            return user
        fact = self.app.fact('konto')
        return dict(fact.detail).get('Konto') if fact is not None else None

    def update_view(self) -> None:
        card = self.query_one('#kt-login', SectionCard)
        width = self.card_width(card)
        user = self._user()
        login = Text()
        login.append('Benutzer ', style=MUTED)
        # Name ohne Polster im Wertfeld: der Satz bleibt wörtlich lesbar
        login.append(user or '–', style=f'bold {TEXT} on {P.inset}')
        login.append(' mit dem Linux-Passwort dieses Kontos', style=TEXT)
        card.show(header('account', 'Anmeldung an der Werkbank', None, width), login,
                  help_line('Ein eigenes Werkbank-Passwort gibt es nicht.'))

        fact = self.app.fact('konto')
        if fact is None:
            state, rows = fact_badge(None), []
        else:
            have = {g.strip() for g in dict(fact.detail).get('Gruppen', '').split(',')}
            missing = [name for name, _ in GROUP_WHY if name not in have]
            state = badge(probes.FAIL, f'fehlt: {", ".join(missing)}') if missing else badge(probes.OK, 'vollständig')
            rows = [(name, join(badge(probes.OK, 'vorhanden') if name in have else badge(probes.FAIL, 'fehlt'),
                                f'  {why}')) for name, why in GROUP_WHY]
        self.query_one('#kt-groups', SectionCard).show(
            header('system', 'Gruppen', state, width), fields(rows, width, label_w=12),
            fact_help(fact, 'Das Konto braucht video (Kamera) und dialout (UART).', always=False))

        linger = self.app.fact('linger')
        box = self.query_one('#kt-linger', SectionCard)
        box.display = linger is not None
        if linger is not None:
            box.show(header('service', 'Nach Abmeldung', fact_badge(linger), width), None,
                     fact_help(linger, 'Benutzerdienst: läuft nach dem Abmelden weiter und startet beim Booten.'))

        self.query_one('#kt-passwd', SectionCard).show(
            header('key', 'Passwort ändern', None, width),
            join(value('passwd', bold=True), '  im Terminal eingeben', muted=False),
            help_line('Das ändert auch die SSH-Anmeldung; die Konsole ändert keine Passwörter.'))
        self.sync_buttons()
