"""Tab „Sensoren“: aktiver Sensor, Liste der Sensorpakete, Marktplatz-Platzhalter, Einrichtungsassistent."""

from __future__ import annotations

import asyncio

from rich.text import Text
from textual import on, work
from textual.containers import Vertical
from textual.widgets import Static

from .. import probes, sensor_client
from ..edit_input import EDIT_HINT, EditInput
from ..ui import MUTED, SOFT, TONE, Action, Confirmation, ConfirmScreen
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

MARKET_NOTE = 'Online-Katalog folgt – Suche zeigt vorerst lokale und mitgelieferte Sensoren.'


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
        self.loaded = True
        self.apply_filter()

    def apply_filter(self, keep: str | None = None) -> None:
        chips = self.query_one('#sen-chips', ChipSelector)
        if keep is None and self.shown and chips.selected < len(self.shown):
            keep = self.shown[chips.selected]['id']
        query = self.query_one('#sen-filter', EditInput).value.strip()
        self.shown = [r for r in self.rows if matches(r, query)]
        index = next((i for i, r in enumerate(self.shown) if r['id'] == keep), 0)
        items = [('on' if r['active'] else 'template', r['display_name'], None if r['status'] == 'verified'
                  else badge(probes.WARN, 'vorläufig')) for r in self.shown]
        chips.set_items(items, index)
        if self.is_mounted:
            self.draw()

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
                     ('Herkunft', value('lokal angelegt' if sel.get('local') else 'mitgeliefert'))]
            hint = (help_line('Vorläufig: Werte werden als vorläufig markiert.') if sel['status'] != 'verified'
                    else None)
            detail.show(header('info', 'Details', status_badge(sel['status']), dwidth),
                        fields(drows, dwidth, label_w=11), hint)
        market = self.query_one('#sen-market', SectionCard)
        market.show(header('network', 'Marktplatz', badge(probes.OFF, 'folgt', 'off'), self.card_width(market)),
                    Text(MARKET_NOTE, style=SOFT), None)

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
        elif sel['active']:
            block = 'ist bereits aktiv'
        else:
            block = None
        return [Action('n', 'Neuen Sensor hinzufügen', self.add_sensor, icon='setup'),
                Action('a', 'Als aktiv setzen', self.activate_selected, icon='check', blocked=block),
                Action('r', 'Aktualisieren', self.reload, icon='restart')]

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
        if sel is None or sel['active']:
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

