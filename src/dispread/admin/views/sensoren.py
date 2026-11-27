"""Tab „Sensoren“: aktiver Sensor, Liste der Sensorpakete, Marktplatz-Platzhalter, Einrichtungsassistent."""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual import on, work
from textual.containers import Vertical
from textual.widgets import Input, Static

from .. import probes, sensor_client
from ..edit_input import EDIT_HINT, EditInput
from ..ui import MUTED, TONE, Action, AskScreen, Confirmation, ConfirmScreen
from ..widgets import (
    ActionBar,
    CardBox,
    ChipSelector,
    SectionCard,
    TabBody,
    badge,
    fields,
    header,
    help_line,
    value,
)
from .base import TabView

MARKET_BADGE = 'Marktplatz'
CONSENT_LINES = ('Paketdateien (Format, Vorlagen, keine Bilder) werden an das Firmen-Forgejo gesendet und '
                 'erscheinen öffentlich im Katalog.',
                 'Das Paket wird dort automatisch geprüft; erst danach ist es im Marktplatz sichtbar.')


class TokenScreen(AskScreen):
    """Eingabe des Forgejo-Tokens, maskiert (der Wert erscheint nirgends im Klartext)."""

    def on_mount(self) -> None:
        super().on_mount()
        self.query_one('#ask-input', Input).password = True


def status_badge(status: str) -> Text:
    if status == 'verified':
        return badge(probes.OK, 'verifiziert')
    if status == 'provisional':
        return badge(probes.WARN, 'vorläufig')
    return badge(probes.OFF, status or '–')


def matches(row: dict, query: str) -> bool:
    """Suche über Name, Hersteller, Alias und Kennung (Groß-/Kleinschreibung egal, alle Wörter)."""
    haystack = ' '.join([row.get('display_name', ''), row.get('manufacturer', ''), row.get('id', ''),
                         *row.get('aliases', [])]).lower()
    return all(word in haystack for word in query.lower().split())


class SensorenView(TabView):
    TAB_ID, TITLE, KEY = 'sensoren', 'Sensoren', 'o'
    FEATURE = sensor_client.FEATURE_NAME   # Tab nur sichtbar, wenn der Schalter in den Einstellungen an ist
    INFO_TITLE = 'Sensoren'
    OWN_BAR = True
    ABOUT = ('Ein Sensorpaket beschreibt eine Anzeige (Raster, Zeichen, Format) samt eingefrorenen Vorlagen. '
             'Mitgelieferte Pakete sind verifiziert; selbst angelegte sind vorläufig, ihre Werte werden in '
             'Läufen und im Audit als vorläufig markiert.',
             '„Neuen Sensor hinzufügen“ führt durch die Einrichtung (mit oder ohne KI-Assistent). Der neue '
             'Sensor muss danach in der Werkbank unter /live eingerichtet werden.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows: list[dict] = []
        self.market_count = 0
        self.token_saved = False
        self.shown: list[dict] = []
        self.load_error: str | None = None
        self.loaded = False

    def compose(self):
        with TabBody(classes='tab-body'):
            yield SectionCard(id='sen-active')
            with CardBox(id='sen-list'):
                yield Static(id='sen-list-head')
                with Vertical(classes='field'):   # Feldstil des Bestands (tui.py: .field Input)
                    yield EditInput(id='sen-filter', placeholder='Suche: Name, Hersteller, Alias')
                yield ChipSelector(id='sen-chips')
                yield Static(id='sen-list-help')
            yield SectionCard(id='sen-detail')
            yield SectionCard(id='sen-market')
        yield ActionBar()

    def on_mount(self) -> None:
        bar = self.query_one(ActionBar)
        for action in self.actions():
            bar.mount(self.action_button(action))
        self.reload()

    # ------------------------------------------------------------ Daten
    def reload(self) -> None:
        self.load_error = None
        try:
            rows = sensor_client.list_sensors(self.app.instance)
        except Exception as error:  # noqa: BLE001 - Registry-Fehler zeigen, nicht abstürzen
            rows, self.load_error = [], f'{type(error).__name__}: {error}'
        errors = [r['error'] for r in rows if r.get('error')]
        if errors:
            self.load_error = ' '.join(errors)
        self.rows = [r for r in rows if r.get('id')]
        self.add_market_rows()
        self.loaded = True
        self.apply_filter()

    def add_market_rows(self) -> None:
        """Katalogeinträge (Zwischenspeicher, ohne Netz) hinter die lokalen Sensoren; lokale gehen vor."""
        entries = sensor_client.catalog_entries(self.app.instance)
        self.market_count = len(entries)
        known = {r['id'] for r in self.rows}
        for entry in entries:
            if entry['id'] in known:
                continue
            self.rows.append({'id': entry['id'], 'display_name': entry.get('display_name') or entry['id'],
                              'manufacturer': entry.get('manufacturer') or '',
                              'aliases': list(entry.get('aliases') or []), 'status': entry.get('status') or '',
                              'unit': entry.get('unit') or '', 'active': False, 'local': False, 'market': True,
                              'version': entry.get('version')})

    def apply_filter(self, keep: str | None = None) -> None:
        chips = self.query_one('#sen-chips', ChipSelector)
        if keep is None and self.shown and chips.selected < len(self.shown):
            keep = self.shown[chips.selected]['id']
        query = self.query_one('#sen-filter', EditInput).value.strip()
        self.shown = [r for r in self.rows if matches(r, query)]
        index = next((i for i, r in enumerate(self.shown) if r['id'] == keep), 0)
        items = [('on' if r['active'] else 'template', r['display_name'], self.chip_mark(r)) for r in self.shown]
        chips.set_items(items, index)
        if self.is_mounted:
            self.draw()

    @staticmethod
    def chip_mark(row: dict) -> Text | None:
        if row.get('market'):
            return badge(probes.OFF, MARKET_BADGE, 'off')
        return None if row['status'] == 'verified' else badge(probes.WARN, 'vorläufig')

    def selected(self) -> dict | None:
        chips = self.query_one('#sen-chips', ChipSelector)
        return self.shown[chips.selected] if self.shown and chips.selected < len(self.shown) else None

    # ------------------------------------------------------------ Anzeige
    def update_view(self) -> None:
        if not self.loaded:
            self.reload()
            return
        self.draw()
        self.sync_buttons()

    def draw(self) -> None:
        inst = self.app.instance
        active_id = sensor_client.active_sensor_id(inst)
        row = next((r for r in self.rows if r['id'] == active_id), None)
        card = self.query_one('#sen-active', SectionCard)
        width = self.card_width(card)
        if row is None:
            rows = [('Sensor', value(active_id, tone=None), True),
                    ('Hinweis', value('nicht in der Liste gefunden'), True)]
            right = badge(probes.WARN, 'unbekannt')
        else:
            rows = [('Sensor', value(row['display_name'], bold=True), True),
                    ('Kennung', value(row['id']), True), ('Einheit', value(row['unit']))]
            right = status_badge(row['status'])
        card.show(header('template', 'Aktiver Sensor', right, width), fields(rows, width, label_w=10),
                  help_line('Die Werkbank liest mit diesem Paket; Wechsel wirkt nach Neustart der Werkbank.'))
        box = self.query_one('#sen-list')
        lwidth = self.card_width(box)
        count = badge(probes.OFF, f'{len(self.shown)} von {len(self.rows)}', 'off')
        self.query_one('#sen-list-head', Static).update(header('template', 'Sensoren', count, lwidth))
        editing = self.query_one('#sen-filter', EditInput).editing
        if self.load_error:
            note = Text(f'Sensorpakete: {self.load_error}', style=TONE[probes.FAIL])
        elif not self.shown:
            note = Text('Keine Treffer.' if self.rows else 'Keine Sensorpakete gefunden.', style=MUTED)
        else:
            note = help_line(EDIT_HINT if editing else '← → wählt, Suche filtert nach Name, Hersteller und Alias.')
        self.query_one('#sen-list-help', Static).update(note)
        sel = self.selected()
        detail = self.query_one('#sen-detail', SectionCard)
        dwidth = self.card_width(detail)
        if sel is None:
            detail.show(header('info', 'Details', None, dwidth), Text('Kein Sensor gewählt.', style=MUTED), None)
        else:
            drows = [('Name', value(sel['display_name'], bold=True), True),
                     ('Hersteller', value(sel['manufacturer'] or None), True),
                     ('Einheit', value(sel['unit'] or None)),
                     ('Aliase', value(', '.join(sel['aliases']) or None), True),
                     ('Kennung', value(sel['id']), True),
                     ('Herkunft', value(MARKET_BADGE + ' (nicht installiert)' if sel.get('market')
                                        else 'lokal angelegt' if sel.get('local') else 'mitgeliefert'))]
            hint = (help_line('Installieren (v) lädt das Paket vorläufig; Werte werden als vorläufig markiert.')
                    if sel.get('market') else
                    help_line('Vorläufig: Werte werden als vorläufig markiert.') if sel['status'] != 'verified'
                    else None)
            detail.show(header('info', 'Details', status_badge(sel['status']), dwidth),
                        fields(drows, dwidth, label_w=11), hint)
        market = self.query_one('#sen-market', SectionCard)
        mwidth = self.card_width(market)
        self.token_saved = sensor_client.token_status(inst)
        mrows = [('Katalog', value(f'{self.market_count} Einträge' if self.market_count else 'nicht geladen (k)'),
                  True),
                 ('Token', value('gespeichert' if self.token_saved else 'fehlt – wird beim Einreichen erfragt'),
                  True)]
        market.show(header('network', 'Marktplatz', badge(probes.OFF, 'experimentell', 'off'), mwidth),
                    fields(mrows, mwidth, label_w=9),
                    help_line('Suche zeigt lokale Sensoren und Katalog (k lädt ihn). Einreichen sendet an das '
                              'Firmen-Forgejo (nur im Firmennetz/Tailscale).'))

    @on(EditInput.Changed, '#sen-filter')
    def _filter_changed(self) -> None:
        self.apply_filter()

    @on(EditInput.EditingChanged)
    def _editing_changed(self, event: EditInput.EditingChanged) -> None:
        event.stop()
        self.draw()

    @on(ChipSelector.Selected, '#sen-chips')
    def _selected(self) -> None:
        self.draw()
        self.sync_buttons()

    # ------------------------------------------------------------ Aktionen
    def actions(self) -> list[Action]:
        sel = self.selected() if self.is_mounted and self.query('#sen-chips') else None
        if sel is None:
            block = 'kein Sensor gewählt'
        elif sel.get('market'):
            block = 'erst installieren (v)'
        elif sel['active']:
            block = 'ist bereits aktiv'
        else:
            block = None
        install_block = ('kein Marktplatz-Eintrag gewählt' if sel is None or not sel.get('market') else None)
        if sel is None:
            submit_block = 'kein Sensor gewählt'
        elif sel.get('market'):
            submit_block = 'nur lokale Pakete sind einreichbar'
        elif not sel.get('local'):
            submit_block = 'mitgelieferte Pakete sind schon im Release'
        elif sel['status'] == 'verified':
            submit_block = 'nur vorläufige Pakete werden eingereicht'
        else:
            submit_block = None
        return [Action('n', 'Neuer Sensor', self.add_sensor, icon='setup'),
                Action('a', 'Aktiv setzen', self.activate_selected, icon='check', blocked=block),
                Action('r', 'Neu lesen', self.reload, icon='restart'),
                Action('k', 'Katalog laden', self.refresh_catalog, icon='network'),
                Action('v', 'Installieren', self.install_selected, icon='setup', blocked=install_block),
                Action('u', 'Einreichen', self.submit_selected, icon='check', blocked=submit_block),
                Action('s', 'Ausstehende senden', self.send_pending, icon='restart')]

    @work(exclusive=True, group='sensor-catalog')
    async def refresh_catalog(self) -> None:
        app = self.app
        app.message(probes.OFF, 'Katalog wird geladen …')
        ok, message = await asyncio.to_thread(sensor_client.catalog_refresh, app.instance)
        app.message(probes.OK if ok else probes.FAIL, message)
        self.reload()

    @work(exclusive=True, group='sensor-install')
    async def install_selected(self) -> None:
        app = self.app
        sel = self.selected()
        if sel is None or not sel.get('market'):
            return
        lines = [f'„{sel["display_name"]}“ ({sel["id"]}) wird aus dem Marktplatz geladen.',
                 'Es wird als vorläufig installiert, auch wenn der Katalog „verifiziert“ nennt; Werte sind in '
                 'Läufen und im Audit als vorläufig markiert.']
        ok = await app.push_screen_wait(ConfirmScreen(Confirmation('Sensor installieren', lines, [], 'Installieren')))
        if not ok:
            return
        done, message = await asyncio.to_thread(sensor_client.catalog_install, app.instance, sel['id'])
        app.message(probes.OK if done else probes.FAIL, message)
        if done:
            self.reload()
            self.apply_filter(keep=sel['id'])

    @work(exclusive=True, group='sensor-submit')
    async def submit_selected(self) -> None:
        app = self.app
        sel = self.selected()
        if sel is None or sel.get('market') or not sel.get('local') or sel['status'] == 'verified':
            return
        lines = [f'„{sel["display_name"]}“ ({sel["id"]}) einreichen.', *CONSENT_LINES]
        consent = await app.push_screen_wait(ConfirmScreen(Confirmation(
            'Sensor einreichen', lines, [], 'Einverstanden und senden')))
        if not consent:
            return
        if not await asyncio.to_thread(sensor_client.token_status, app.instance):
            token = await app.push_screen_wait(TokenScreen(
                'Forgejo-Token', ['Zum Einreichen braucht es ein Forgejo-Token (Eingabe wird nicht angezeigt).',
                                  'Es wird geprüft und nur auf diesem Gerät gespeichert.'],
                placeholder='Token'))
            if not token:
                app.message(probes.OFF, 'Abgebrochen: kein Token.')
                return
            saved, message = await asyncio.to_thread(sensor_client.save_token, app.instance, token)
            del token
            if not saved:
                app.message(probes.FAIL, message)
                return
        done, message = await asyncio.to_thread(sensor_client.submit_sensor, app.instance, sel['id'], consent=True)
        app.message(probes.OK if done else probes.FAIL, message)
        self.draw()

    @work(exclusive=True, group='sensor-pending')
    async def send_pending(self) -> None:
        app = self.app
        done, message = await asyncio.to_thread(sensor_client.submit_pending, app.instance)
        app.message(probes.OK if done else probes.FAIL, message)

    @work(exclusive=True, group='sensor-add')
    async def add_sensor(self) -> None:
        from .sensor_onboarding_screen import SensorOnboardingScreen
        from .sensor_wizard_screen import SensorWizardScreen

        app = self.app
        assistants = await asyncio.to_thread(sensor_client.detect_assistants, app.instance)
        ports = await asyncio.to_thread(sensor_client.list_ports, app.instance)
        request = await app.push_screen_wait(SensorWizardScreen(assistants, ports))
        if request is None:
            return
        try:
            run = sensor_client.create_run(request, app.instance)
        except (OSError, ValueError) as error:
            app.message(probes.FAIL, f'Laufmappe nicht angelegt: {error}')
            return
        await app.push_screen_wait(SensorOnboardingScreen(app.instance, run, request['assistant']))
        self.reload()
        app.action_refresh()

    @work(exclusive=True, group='sensor-activate')
    async def activate_selected(self) -> None:
        app = self.app
        sel = self.selected()
        if sel is None or sel['active'] or sel.get('market'):
            return
        lines = [f'Die Werkbank liest künftig mit „{sel["display_name"]}“ ({sel["id"]}).',
                 'Wirksam nach einem Neustart der Werkbank; ein laufender Lauf bleibt unverändert.']
        provisional = sel['status'] != 'verified'
        if provisional:
            lines.insert(0, 'vorläufig – Werte werden als vorläufig markiert (Läufe und Audit).')
        ok = await app.push_screen_wait(ConfirmScreen(Confirmation(
            'Sensor als aktiv setzen', lines, [], 'Als aktiv setzen', danger=provisional)))
        if not ok:
            return
        done, message = await asyncio.to_thread(sensor_client.activate, sel['id'], app.instance)
        if not done:
            app.message(probes.FAIL, message)
            return
        app.instance.sensor = sel['id']
        if app.instance.config:
            try:
                from ..instance import discover

                app.instance = discover(app.instance.config)
            except Exception:  # noqa: BLE001 - Anzeige bleibt beim gesetzten Wert
                pass
        app.message(probes.OK, message)
        self.reload()

