"""Tab Zertifikat: Ausweis der Werkbank für HTTPS und die Windows-Brücke."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .. import probes
from ..ui import Action
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
from .zertifikat_screen import ZertifikatErneuernScreen

DASH = '–'


def days_left(fact) -> int | None:
    """Resttage aus „Gültig bis“ (TT.MM.JJJJ); None, wenn unbekannt."""
    value = dict(fact.detail).get('Gültig bis') if fact is not None else None
    try:
        return (datetime.strptime(value, '%d.%m.%Y').date() - datetime.now().date()).days
    except (TypeError, ValueError):
        return None


class ZertifikatView(FactView):
    TAB_ID, TITLE, KEY = 'zertifikat', 'Zertifikat', '6'
    FACTS = ()
    INFO_TITLE = 'Was ist das Zertifikat?'
    ABOUT = ('Das Zertifikat ist der Ausweis der Werkbank: Browser und Windows-Brücke prüfen damit, dass sie '
            'wirklich mit diesem Pi sprechen, und die Verbindung ist verschlüsselt (HTTPS).',
            'Läuft es ab oder passt der Name nicht zur Adresse, warnen Browser. Nach dem Erneuern müssen '
            'Browser dem neuen Zertifikat wieder vertrauen, und die Werkbank braucht einen Neustart.',
            'Mit gekoppelter Windows-Brücke ist das Zertifikat zugleich die Identität des Pi: die Brücke '
            'merkt sich seinen Fingerabdruck. Erneuern stellt es neu aus (gleiche Pi-ID, gleicher Schlüssel); '
            'danach muss jede Windows-Brücke das neue Profil pi.dispread aus der Werkbank laden und neu '
            'koppeln. Erneuern ist nur möglich, wenn kein Lauf aktiv ist.',
            'HTTPS lässt sich nicht abschalten: die Brücke und die Anmeldung verlangen verschlüsselte Verbindungen.')
    INFO_FACTS = ('zertifikat',)

    def compose(self):
        with TabBody(classes='tab-body'):
            yield SectionCard(id='cert-card')
            yield SectionCard(id='cert-renew')
        yield ActionBar()

    def cert_directory(self) -> Path | None:
        data = self.app.instance.data
        return Path(data) / 'tls' if data else None

    def is_bridge_identity(self) -> bool | None:
        """True, wenn das ausgelieferte Zertifikat die Brückenidentität trägt; None, wenn unbekannt."""
        fact = self.app.fact('zertifikat')
        if fact is None or fact.level in (probes.OFF, probes.UNKNOWN) or not fact.detail:
            return None
        return bool(dict(fact.detail).get('Identität'))

    def renew_blocker(self) -> str | None:
        bridge = self.is_bridge_identity()
        if bridge is None:
            return 'Zertifikat nicht lesbar (Werkbank aus?)'
        if bridge and not self.app.instance.bridge_directory:
            return 'Ort der Brückenidentität unbekannt'
        if not bridge and self.cert_directory() is None:
            return 'Ort des Zertifikats unbekannt'
        return self.app.blocker

    def update_view(self) -> None:
        app = self.app
        fact = app.fact('zertifikat')
        card = self.query_one('#cert-card', SectionCard)
        width = self.card_width(card)
        rows: list = []
        if fact is not None:
            detail = dict(fact.detail)
            left = days_left(fact)
            if left is None:
                note = None
            elif left >= 0:
                note = f'noch {left} Tage'
            else:
                note = f'seit {-left} Tagen abgelaufen'
            until = value(detail.get('Gültig bis'), note)
            bridge = self.is_bridge_identity()
            directory = self.cert_directory()
            rows = [('Adresse', value(detail.get('Adresse') or app.instance.url), True),
                    ('Namen', value(detail.get('Namen'))), ('Gültig bis', until),
                    ('Identität', value(detail.get('Identität')), True),
                    ('Datei', value(str(directory / 'cert.pem') if directory else None), True),
                    ('Brückenidentität', value(None if bridge is None else 'ja' if bridge else 'nein'))]
        card.show(header('cert', 'Zertifikat', fact_badge(fact), width),
                  fields(rows, width, label_w=18, columns=2 if width >= 76 else 1),
                  fact_help(fact, 'Ausweis der Werkbank für HTTPS und die Windows-Brücke.'))

        reason = self.renew_blocker()
        if reason:
            renew = join(badge(probes.OFF, 'nicht möglich', 'off'), f'  {reason}')
            hint = help_line('Erneuern stellt das Zertifikat mit demselben Schlüssel neu aus.', 'i', 'mehr')
        else:
            if self.is_bridge_identity():
                renew = join(badge(probes.OK, 'möglich', 'ok'),
                             '  gleiche Pi-ID; alle Windows-Brücken müssen neu koppeln')
                hint = help_line('Der Dienst wird dabei neu gestartet; Browser müssen neu vertrauen.')
            else:
                renew = join(badge(probes.OK, 'möglich', 'ok'), '  derselbe Schlüssel; Browser müssen wieder vertrauen')
                hint = help_line('Der Dienst wird dabei neu gestartet, erst dann gilt das neue Zertifikat.')
        rows = [('Erneuern', renew, True),
                ('Abschalten', join(badge(probes.OFF, 'nicht vorgesehen', 'off'),
                                    '  Brücke und Anmeldung verlangen TLS'), True)]
        self.query_one('#cert-renew', SectionCard).show(
            header('restart', 'Erneuern und Abschalten', None, width), fields(rows, width, label_w=18), hint)
        self.sync_buttons()

    def actions(self) -> list[Action]:
        return [Action('n', 'Erneuern', self.renew, blocked=self.renew_blocker(), icon='restart')]

    def renew(self) -> None:
        if self.renew_blocker() is None:
            mode = 'bridge' if self.is_bridge_identity() else 'tls'
            self.app.push_screen(ZertifikatErneuernScreen(self.app.instance, mode, directory=self.cert_directory(),
                                                         collect=self.app._collect))
