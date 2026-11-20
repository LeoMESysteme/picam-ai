"""Tab Zertifikat: Ausweis der Werkbank für HTTPS und die Windows-Brücke."""

from __future__ import annotations

import os
import shlex
import sys
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual.containers import Horizontal
from textual.widgets import Static

from .. import probes
from ..ui import MUTED, Action, Confirmation, ConfirmScreen, fact_title, hint_block, kv_table, section
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
    INFO = ('Das Zertifikat ist der Ausweis der Werkbank: Browser und Windows-Brücke prüfen damit, dass sie '
            'wirklich mit diesem Pi sprechen, und die Verbindung ist verschlüsselt (HTTPS).',
            'Läuft es ab oder passt der Name nicht zur Adresse, warnen Browser. Nach dem Erneuern müssen '
            'Browser dem neuen Zertifikat wieder vertrauen, und die Werkbank braucht einen Neustart.',
            'Mit gekoppelter Windows-Brücke ist das Zertifikat zugleich die Identität des Pi: die Brücke '
            'merkt sich seinen Fingerabdruck. Ein neues Zertifikat würde jede Kopplung brechen und darum '
            'wird es dort nicht angeboten.',
            'HTTPS lässt sich nicht abschalten: die Brücke und die Anmeldung verlangen verschlüsselte Verbindungen.')
    SCOPED_CSS = False
    DEFAULT_CSS = """
    ZertifikatView #cert-intro { margin: 1 0 0 0; }
    ZertifikatView #cert-note { margin: 1 0 0 0; color: $text-muted; max-width: 100; }
    """

    def compose(self):
        yield Static(Text('Ausweis der Werkbank für HTTPS und die Windows-Brücke.', style=MUTED), id='cert-intro')
        yield Static(id='cert-state', classes='fact-title')
        yield Static(id='cert-hint', classes='hint')
        yield Static(id='cert-rows')
        yield section('Erneuern und Abschalten')
        yield Static(id='cert-note')
        yield Horizontal(id='buttons', classes='buttons')

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
        state, hint = self.query_one('#cert-state', Static), self.query_one('#cert-hint', Static)
        if fact is None:
            state.update(Text('Zertifikat', style='bold'))
            hint.display = False
            self.query_one('#cert-rows', Static).update(Text('Wird geprüft …', style=MUTED))
        else:
            state.update(fact_title(fact))
            block = hint_block(fact)
            hint.display = block is not None
            if block is not None:
                hint.update(block)
                hint.set_class(fact.level == probes.FAIL, 'fail')
            detail = dict(fact.detail)
            left = days_left(fact)
            until = detail.get('Gültig bis') or DASH
            if left is not None:
                until += f' (noch {left} Tage)' if left >= 0 else f' (seit {-left} Tagen abgelaufen)'
            bridge = self.is_bridge_identity()
            directory = self.cert_directory()
            rows = [('Adresse', detail.get('Adresse') or app.instance.url or DASH),
                    ('Namen', detail.get('Namen') or DASH), ('Gültig bis', until),
                    ('Identität', detail.get('Identität') or DASH),
                    ('Datei', str(directory / 'cert.pem') if directory else DASH),
                    ('Brückenidentität', DASH if bridge is None else 'ja' if bridge else 'nein')]
            self.query_one('#cert-rows', Static).update(kv_table(rows))
        reason = self.renew_blocker()
        note = Text()
        note.append('Erneuern: ' + ('nicht möglich – ' + reason + '.' if reason else
                                    'stellt das Zertifikat mit demselben Schlüssel neu aus; Browser müssen '
                                    'wieder vertrauen, danach Dienst neu starten.'))
        note.append('\nAbschalten: nicht vorgesehen – die Windows-Brücke verlangt TLS und das Anmelden '
                    'geschieht nur verschlüsselt.')
        self.query_one('#cert-note', Static).update(note)
        self.sync_buttons()

    def actions(self) -> list[Action]:
        return [Action('n', 'Erneuern', self.renew, blocked=self.renew_blocker())]

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
