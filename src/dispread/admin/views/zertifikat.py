"""Tab Zertifikat: Ausweis der Werkbank für HTTPS und die Windows-Brücke."""

from __future__ import annotations

import os
import shlex
import sys
from datetime import datetime
from pathlib import Path

from .. import probes
from ..ui import Action, Confirmation, ConfirmScreen
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
            'merkt sich seinen Fingerabdruck. Ein neues Zertifikat würde jede Kopplung brechen und darum '
            'wird es dort nicht angeboten.',
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
        if bridge:
            return 'Brückenidentität: Erneuern bräche alle Kopplungen'
        if self.cert_directory() is None:
            return 'Ort des Zertifikats unbekannt'
        return None

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
            renew = join(badge(probes.OK, 'möglich', 'ok'), '  derselbe Schlüssel; Browser müssen wieder vertrauen')
            hint = help_line('Danach den Dienst neu starten, erst dann gilt das neue Zertifikat.')
        rows = [('Erneuern', renew, True),
                ('Abschalten', join(badge(probes.OFF, 'nicht vorgesehen', 'off'),
                                    '  Brücke und Anmeldung verlangen TLS'), True)]
        self.query_one('#cert-renew', SectionCard).show(
            header('restart', 'Erneuern und Abschalten', None, width), fields(rows, width, label_w=18), hint)
        self.sync_buttons()

    def actions(self) -> list[Action]:
        return [Action('n', 'Erneuern', self.renew, blocked=self.renew_blocker(), icon='restart')]

    def renew_command(self) -> list[str]:
        command = [sys.executable, '-m', 'dispread.workbench.cli', 'renew-tls', '--directory',
                   str(self.cert_directory())]
        if self.app.instance.scope == 'system' and os.geteuid() != 0:
            command = ['sudo', *command]
        return command

    def renew(self) -> None:
        if self.renew_blocker() is None:
            self.app.run_worker(self.confirm_and_renew(), group='renew', exclusive=True)

    async def confirm_and_renew(self) -> None:
        app = self.app
        command = self.renew_command()
        ok = await app.push_screen_wait(ConfirmScreen(Confirmation(
            'Zertifikat erneuern',
            ['Stellt das Zertifikat mit demselben Schlüssel neu aus; das alte bleibt als Sicherung liegen.',
             'Browser und Windows müssen dem neuen Zertifikat wieder vertrauen. Die Werkbank muss danach '
             'neu gestartet werden, erst dann liefert sie das neue aus.'],
            [shlex.join(command)], 'Erneuern', danger=True)))
        if not ok:
            return
        code = app.run_in_terminal(command, 'Zertifikat erneuern')
        if code == 0:
            app.message(probes.OK, 'Zertifikat erneuert. Dienst neu starten, Browser müssen wieder vertrauen.')
        else:
            app.message(probes.FAIL, f'Erneuern fehlgeschlagen (Exit {code}).')
        app.action_refresh()
