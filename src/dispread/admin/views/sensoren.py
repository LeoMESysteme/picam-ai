"""Tab „Sensoren“: aktiver Sensor, Unterseiten „Meine Sensoren“ und „Marktplatz“, Einrichtungsassistent.

Aufbau (von oben): Kopfband „Aktiver Sensor“ (auf beiden Unterseiten, Akzentbalken), Reiterzeile der Unterseiten
(Taste m, Pfeile, Klick), darunter die Seite:

* Meine Sensoren: Kartenraster der installierten Sensoren (mitgeliefert, lokal, aus dem Marktplatz); Enter oder
  Klick öffnet die Angaben mit „Als aktiv setzen“ und „Einreichen“.
* Marktplatz: Suchzeile und Filterleiste (Anschluss, Status, Anzeigeart, nur nicht installierte) über dem
  Kartenraster des Katalogs; Enter oder Klick öffnet die Angaben mit „Installieren“. Der Katalog wird beim Öffnen
  der Seite im Hintergrund geladen (ohne Netz bleibt der zwischengespeicherte Stand mit Hinweis stehen).
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

from rich.text import Text
from textual import on, work
from textual.containers import Vertical
from textual.widgets import Input, Static

from .. import probes, sensor_client
from ..edit_input import EDIT_HINT, EditInput
from ..ui import MUTED, SOFT, TONE, Action, AskScreen, Confirmation, ConfirmScreen, P
from ..widgets import (
    ActionBar,
    ChipSelector,
    badge,
    help_line,
    icon,
    value,
)
from .base import TabView
from .sensor_cards import Card, CardGrid, FilterBar
from .sensor_detail_screen import DetailButton, SensorDetailScreen

CONSENT_LINES = ('Paketdateien (Format, Vorlagen, keine Bilder) werden an das Firmen-Forgejo gesendet und '
                 'erscheinen öffentlich im Katalog.',
                 'Das Paket wird dort automatisch geprüft; erst danach ist es im Marktplatz sichtbar.')
TIGHT_HEIGHT = 28           # darunter (80×24) entfallen die Leerzeilen zwischen den Blöcken
AUTO_LOAD_PAUSE_S = 30.0     # so oft lädt das Öffnen der Marktplatz-Seite den Katalog höchstens neu

CONNECTION_LABEL = {'rs232': 'RS232', 'usb': 'USB', 'none': 'ohne Anschluss', 'unknown': 'unbekannt'}
FAMILY_LABEL = {'hd44780_5x8': 'Punktraster'}
POLARITY_LABEL = {'dark_on_light': 'dunkel auf hell', 'light_on_dark': 'hell auf dunkel'}
ORIGIN_LABEL = {'bundled': 'mitgeliefert', 'local': 'lokal angelegt', 'market': 'aus dem Marktplatz'}
PAGES = ('mine', 'market')


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


def active_badge() -> Text:
    return Text(f' {icon("on")} AKTIV ', style=f'bold {P.on_accent_deep} on {P.accent_deep}', no_wrap=True)


def matches(row: dict, query: str) -> bool:
    """Suche über Name, Hersteller, Alias und Kennung (Groß-/Kleinschreibung egal, alle Wörter)."""
    haystack = ' '.join([row.get('display_name', ''), row.get('manufacturer', ''), row.get('id', ''),
                         *row.get('aliases', [])]).lower()
    return all(word in haystack for word in query.lower().split())


# ----------------------------------------------------------------- Bezeichnungen
def connection_label(row: dict) -> str:
    return CONNECTION_LABEL.get(row.get('connection') or 'unknown', row.get('connection') or 'unbekannt')


def kind_label(row: dict, *, short: bool = False) -> str:
    """Anzeigeart: Punktraster 16×1, dunkel auf hell (kurz: ohne Zellenzahl)."""
    family = row.get('family') or ''
    if not family:
        return '–'
    text = FAMILY_LABEL.get(family, family)
    if not short and row.get('cells'):
        text += f' {row["cells"]}×{row.get("rows") or 1}'
    polarity = POLARITY_LABEL.get(row.get('polarity') or '', row.get('polarity') or '')
    return f'{text}, {polarity}' if polarity else text


def origin_of(row: dict) -> str:
    return row.get('origin') or ('local' if row.get('local') else 'bundled')


def normalize_local(row: dict) -> dict:
    out = dict(row)
    out.setdefault('connection', 'unknown')
    out['origin'] = origin_of(row)
    out.setdefault('example', '')
    out.setdefault('version', None)
    return out


def market_row(entry: dict, local: dict[str, dict]) -> dict:
    """Katalogeintrag als Zeile; ``installed``/``update`` aus den lokal vorhandenen Paketen."""
    have = local.get(entry['id'])
    version = entry.get('version')
    installed_version = have.get('version') if have else None
    update = bool(have and have.get('origin') == 'market' and version and installed_version
                  and version > installed_version)
    return {'id': entry['id'], 'display_name': entry.get('display_name') or entry['id'],
            'manufacturer': entry.get('manufacturer') or '', 'aliases': list(entry.get('aliases') or []),
            'status': entry.get('status') or '', 'unit': entry.get('unit') or '', 'active': False,
            'local': False, 'market': True, 'version': version, 'connection': entry.get('connection') or 'unknown',
            'family': entry.get('family') or '', 'polarity': entry.get('polarity') or '',
            'example': entry.get('example') or '', 'submitted': entry.get('submitted') or '',
            'runs': (entry.get('checks') or {}).get('runs'), 'installed': have is not None,
            'installed_version': installed_version, 'update': update,
            'origin': 'market'}


def fmt_date(stamp: str | None) -> str | None:
    if not stamp:
        return None
    try:
        return datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ').strftime('%d.%m.%Y')
    except ValueError:
        return stamp


def fmt_time(moment: datetime | None) -> str:
    return moment.strftime('%H:%M') if moment else '–'


class SensorenView(TabView):
    TAB_ID, TITLE, KEY = 'sensoren', 'Sensoren', 'o'
    FEATURE = sensor_client.FEATURE_NAME   # Tab nur sichtbar, wenn der Schalter in den Einstellungen an ist
    INFO_TITLE = 'Sensoren'
    OWN_BAR = True
    DEFAULT_CSS = '''
    SensorenView #sen-body { height: 1fr; width: 1fr; }
    SensorenView #sen-active { height: auto; width: 1fr; max-width: 120; margin: 1 0 0 0; padding: 0 1;
                               background: $picam-raised; border-left: thick $picam-accent-strong; }
    SensorenView #sen-sub { margin: 1 0 0 0; }
    SensorenView #sen-page-mine, SensorenView #sen-page-market { height: 1fr; width: 1fr; }
    SensorenView .sen-head { height: 1; width: 1fr; max-width: 120; margin: 1 0 0 0; }
    SensorenView #sen-filter { width: 1fr; max-width: 120; height: 1; margin: 1 0 0 0; padding: 0 1; border: none;
                               background: $picam-field; color: $picam-text; }
    SensorenView #sen-filter:focus { border: none; background: $picam-field-focus; }
    SensorenView #sen-filters { margin: 1 0 0 0; }
    SensorenView CardGrid { margin: 1 0 0 0; }
    SensorenView.-tight #sen-active, SensorenView.-tight #sen-sub, SensorenView.-tight .sen-head,
    SensorenView.-tight #sen-filter, SensorenView.-tight #sen-filters, SensorenView.-tight CardGrid { margin: 0; }
    SensorenView.-tight #sen-active { margin: 0; }
    SensorenView.-tight ActionBar { margin: 0; }
    '''
    ABOUT = ('Ein Sensorpaket beschreibt eine Anzeige (Raster, Zeichen, Format) samt eingefrorenen Vorlagen. '
             'Mitgelieferte Pakete sind verifiziert; selbst angelegte sind vorläufig, ihre Werte werden in '
             'Läufen und im Audit als vorläufig markiert.',
             '„Meine Sensoren“ zeigt die installierten Sensoren, der „Marktplatz“ den Katalog zum Installieren '
             '(Taste m wechselt). Enter öffnet die Angaben einer Karte. „Neuen Sensor hinzufügen“ führt durch die '
             'Einrichtung; der neue Sensor muss danach in der Werkbank unter /live eingerichtet werden.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows: list[dict] = []            # installierte Sensoren (normalisiert)
        self.market: list[dict] = []          # alle Katalogeinträge (normalisiert, mit installed/update)
        self.shown: list[dict] = []           # Marktplatz nach Filter
        self.page = 'mine'
        self.market_count = 0
        self.token_saved = False
        self.load_error: str | None = None
        self.loaded = False
        self.pending = 0
        self.catalog_time: datetime | None = None
        self.catalog_state = 'idle'           # idle | loading | ok | offline
        self.catalog_note = ''
        self._last_auto = 0.0

    # ------------------------------------------------------------ Aufbau
    def compose(self):
        with Vertical(classes='tab-body', id='sen-body'):
            yield Static(id='sen-active')
            yield ChipSelector(id='sen-sub')
            with Vertical(id='sen-page-mine'):
                yield Static(id='sen-mine-head', classes='sen-head')
                yield CardGrid(id='sen-grid-mine')
            with Vertical(id='sen-page-market'):
                yield EditInput(id='sen-filter', placeholder='Suche: Name, Hersteller, Alias, Kennung')
                yield FilterBar(id='sen-filters')
                yield Static(id='sen-market-head', classes='sen-head')
                yield CardGrid(id='sen-grid-market')
        yield ActionBar()

    def on_mount(self) -> None:
        bar = self.query_one(ActionBar)
        for action in self.actions():
            bar.mount(self.action_button(action))
        self.query_one('#sen-page-market').display = False
        self.reload()

    def on_resize(self, event) -> None:
        self.set_class(self.size.height < TIGHT_HEIGHT, '-tight')   # wenig Platz: Zwischenräume weglassen
        super().on_resize(event)

    def grid(self, page: str | None = None) -> CardGrid:
        return self.query_one('#sen-grid-market' if (page or self.page) == 'market' else '#sen-grid-mine', CardGrid)

    def focus_first(self) -> None:
        """Beim Öffnen des Tabs: Fokus auf das Kartenraster der Seite."""
        self.grid().focus()

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
        self.rows = [normalize_local(r) for r in rows if r.get('id')]
        self.read_catalog()
        try:
            self.pending = sensor_client.pending_count(self.app.instance)
        except Exception:  # noqa: BLE001
            self.pending = 0
        self.loaded = True
        self.apply_market_filter()
        self.draw_mine()
        if self.query('#sen-active'):
            self.draw()

    def read_catalog(self) -> None:
        """Zwischengespeicherten Katalog lesen (ohne Netz) und gegen die installierten Pakete abgleichen."""
        info = sensor_client.catalog_info(self.app.instance) if hasattr(sensor_client, 'catalog_info') else {}
        entries = info.get('entries') or sensor_client.catalog_entries(self.app.instance)
        if info.get('fetched'):
            self.catalog_time = info['fetched']
        local = {r['id']: r for r in self.rows}
        self.market = sorted((market_row(e, local) for e in entries),
                             key=lambda r: r['display_name'].lower())
        self.market_count = len(self.market)

    def filter_groups(self) -> list:
        entries = self.market
        connections = [(c, CONNECTION_LABEL.get(c, c)) for c in ('rs232', 'usb', 'none', 'unknown')
                       if any(r['connection'] == c for r in entries)]
        kinds = sorted({kind_label(r, short=True) for r in entries if r['family']})
        return [('connection', 'Anschluss', [('', 'alle'), *connections]),
                ('status', 'Status', [('', 'alle'), ('verified', 'verifiziert'), ('provisional', 'vorläufig')]),
                ('kind', 'Anzeige', [('', 'alle'), *[(k, k) for k in kinds]]),
                ('new', 'Neu', [('', 'alle'), ('new', 'nur nicht installierte')])]

    def apply_market_filter(self, keep: str | None = None) -> None:
        if not self.query('#sen-filters'):
            return
        bar = self.query_one('#sen-filters', FilterBar)
        bar.set_groups(self.filter_groups())
        query = self.query_one('#sen-filter', EditInput).value.strip()
        active = bar.active()
        self.shown = [r for r in self.market if matches(r, query)
                      and ('connection' not in active or r['connection'] == active['connection'])
                      and ('status' not in active or r['status'] == active['status'])
                      and ('kind' not in active or kind_label(r, short=True) == active['kind'])
                      and ('new' not in active or not r['installed'])]
        grid = self.query_one('#sen-grid-market', CardGrid)
        grid.set_cards([self.market_card(r) for r in self.shown], keep, self.market_empty(bool(query or active)))
        self.draw_market_head()

    # ------------------------------------------------------------ Karten
    @staticmethod
    def mine_card(row: dict) -> Card:
        status = status_badge(row['status'])
        origin = ORIGIN_LABEL.get(row['origin'], row['origin'])
        sub = Text(no_wrap=True)
        sub.append_text(status)
        sub.append(f'  {row["unit"] or "–"}')
        manufacturer = f'{row["manufacturer"]}  ·  {origin}' if row['manufacturer'] else origin
        compact = Text(no_wrap=True)
        compact.append_text(status)
        compact.append(f'  {row["unit"] or "–"}  ·  {connection_label(row)}  ·  {origin}')
        return Card(row['id'], row['display_name'], active_badge() if row['active'] else None,
                    [Text(manufacturer), sub, Text(f'Anschluss {connection_label(row)}'),
                     Text(kind_label(row, short=True))], compact, active=row['active'])

    @staticmethod
    def market_card(row: dict) -> Card:
        status = status_badge(row['status'])
        marker = None
        if row.get('update'):
            marker = badge(probes.WARN, 'Update', 'busy')
        elif row.get('installed'):
            marker = badge(probes.OK, 'installiert')
        sub = Text(no_wrap=True)
        sub.append_text(status)
        sub.append(f'  {row["unit"] or "–"}')
        compact = Text(no_wrap=True)
        compact.append_text(status)
        compact.append(f'  {row["unit"] or "–"}  ·  {connection_label(row)}  ·  {kind_label(row, short=True)}')
        return Card(row['id'], row['display_name'], marker,
                    [Text(row['manufacturer'] or '–'), sub, Text(f'Anschluss {connection_label(row)}'),
                     Text(kind_label(row, short=True))], compact)

    def market_empty(self, filtered: bool) -> list[Text]:
        if self.market:
            return [Text(''), Text('Keine Treffer für diese Suche und Filter.', style=MUTED),
                    Text('Esc leert nichts: Suchfeld und Filter (←→, Enter) zurückstellen.', style=MUTED)] \
                if filtered else []
        if self.catalog_state == 'loading':
            return [Text(''), Text('Katalog wird geladen …', style=MUTED)]
        if self.catalog_state == 'offline':
            return [Text(''), Text('Kein Katalog: nicht erreichbar und noch nichts zwischengespeichert.',
                                   style=TONE[probes.WARN]),
                    Text(self.catalog_note, style=MUTED), Text('k versucht es erneut.', style=MUTED)]
        return [Text(''), Text('Katalog noch nicht geladen.', style=MUTED), Text('k lädt ihn.', style=MUTED)]

    def draw_mine(self) -> None:
        if not self.query('#sen-grid-mine'):
            return
        grid = self.query_one('#sen-grid-mine', CardGrid)
        empty = [Text(''), Text('Keine Sensorpakete gefunden.', style=MUTED)]
        if self.load_error:
            empty = [Text(''), Text(f'Sensorpakete: {self.load_error}', style=TONE[probes.FAIL])]
        grid.set_cards([self.mine_card(r) for r in self.rows], None, empty)

    # ------------------------------------------------------------ Auswahl
    def selected_row(self) -> dict | None:
        if not self.query('#sen-grid-mine'):
            return None
        grid = self.grid()
        card = grid.current()
        if card is None:
            return None
        pool = self.rows if self.page == 'mine' else self.shown
        return next((r for r in pool if r['id'] == card.key), None)

    # ------------------------------------------------------------ Anzeige
    def update_view(self) -> None:
        if not self.loaded:
            self.reload()
            return
        self.draw()
        self.sync_buttons()

    def draw(self) -> None:
        self.draw_active()
        self.draw_sub()
        self.draw_mine_head()
        self.draw_market_head()
        self.token_saved = sensor_client.token_status(self.app.instance)

    def draw_active(self) -> None:
        active_id = sensor_client.active_sensor_id(self.app.instance)
        row = next((r for r in self.rows if r['id'] == active_id), None)
        card = self.query_one('#sen-active', Static)
        width = max(30, card.content_size.width or card.size.width or self.card_width(None, margin=8))
        head = Text(no_wrap=True, overflow='ellipsis')
        head.append(f'{icon("on")} ', style=P.accent_strong)
        head.append('AKTIVER SENSOR', style=f'bold {P.accent_strong}')
        if getattr(self.app, 'sensor_restart_needed', False):
            head.append('   Neustart der Werkbank nötig', style=f'bold {TONE[probes.WARN]}')
        if row is None:
            right = badge(probes.WARN, 'unbekannt')
            name = Text(active_id, style='bold')
            meta = Text('nicht in der Liste gefunden', style=MUTED)
        else:
            right = status_badge(row['status'])
            name = Text(row['display_name'], style=f'bold {P.text}')
            meta = Text(f'{row["unit"] or "–"}  ·  {kind_label(row)}  ·  {connection_label(row)}', style=SOFT)
        gap = width - head.cell_len - right.cell_len
        head.append(' ' * max(1, gap))
        head.append_text(right)
        lines = [head]
        if name.cell_len + 3 + meta.cell_len <= width:
            line = Text(no_wrap=True)
            line.append_text(name)
            line.append('   ')
            line.append_text(meta)
            lines.append(line)
        else:
            lines += [name, meta]
        text = Text('\n').join(lines)
        text.no_wrap, text.overflow = True, 'ellipsis'
        card.update(text)

    def draw_sub(self) -> None:
        chips = self.query_one('#sen-sub', ChipSelector)
        items = [('template', f'Meine Sensoren ({len(self.rows)})', None),
                 ('network', f'Marktplatz ({self.market_count})' if self.market_count else 'Marktplatz', None)]
        chips.set_items(items, PAGES.index(self.page))

    def draw_mine_head(self) -> None:
        head = self.query_one('#sen-mine-head', Static)
        text = Text(no_wrap=True, overflow='ellipsis')
        text.append_text(badge(probes.OFF, f'{len(self.rows)} installiert', 'off'))
        text.append('  ')
        text.append_text(help_line('Pfeile wählen, Enter Angaben, m Marktplatz'))
        head.update(text)

    def draw_market_head(self) -> None:
        if not self.query('#sen-market-head'):
            return
        head = self.query_one('#sen-market-head', Static)
        editing = self.query_one('#sen-filter', EditInput).editing
        text = Text(no_wrap=True, overflow='ellipsis')
        text.append_text(badge(probes.OFF, f'{len(self.shown)} von {self.market_count}', 'off'))
        text.append('  ')
        stamp = fmt_time(self.catalog_time)
        if self.catalog_state == 'loading':
            text.append_text(badge('busy', 'Katalog wird geladen …', 'busy'))
            if self.catalog_time:
                text.append(f'  Stand {stamp}', style=MUTED)
        elif self.catalog_state == 'offline':
            text.append_text(badge(probes.WARN, f'offline, Katalog von {stamp}' if self.catalog_time
                                   else 'offline, kein Katalog'))
            if self.catalog_time:
                text.append('  zwischengespeicherter Stand', style=MUTED)
        elif self.catalog_time:
            text.append(f'Katalog von {stamp}', style=MUTED)
        else:
            text.append('Katalog nicht geladen (k)', style=MUTED)
        if editing:
            text.append('   ')
            text.append_text(help_line(EDIT_HINT))
        head.update(text)

    # ------------------------------------------------------------ Seiten
    def set_page(self, page: str, *, focus: bool = False) -> None:
        if page not in PAGES or (page == self.page and self.query_one('#sen-page-market').display == (page == 'market')):
            if focus:
                self.grid().focus()
            return
        self.page = page
        self.query_one('#sen-page-mine').display = page == 'mine'
        self.query_one('#sen-page-market').display = page == 'market'
        self.draw_sub()
        if page == 'market':
            self.read_catalog()
            self.apply_market_filter()
            self.auto_refresh_catalog()
        self.sync_buttons()
        if focus:
            self.call_after_refresh(self.grid().focus)

    def on_key(self, event) -> None:
        """Taste m wechselt zwischen „Meine Sensoren“ und „Marktplatz“ (Ziffern gehören den Tabs der App)."""
        if event.key == 'm' and not getattr(self.app, 'typing', lambda: False)():
            event.stop()
            self.set_page('mine' if self.page == 'market' else 'market', focus=True)

    @on(ChipSelector.Selected, '#sen-sub')
    def _sub_selected(self, event: ChipSelector.Selected) -> None:
        event.stop()
        self.set_page(PAGES[event.index])

    @on(CardGrid.Selected)
    def _card_selected(self, event: CardGrid.Selected) -> None:
        event.stop()
        self.sync_buttons()

    @on(CardGrid.Opened)
    def _card_opened(self, event: CardGrid.Opened) -> None:
        event.stop()
        self.sync_buttons()
        self.open_detail()

    @on(EditInput.Changed, '#sen-filter')
    def _filter_changed(self) -> None:
        self.apply_market_filter()
        self.sync_buttons()

    @on(FilterBar.Changed)
    def _filters_changed(self, event: FilterBar.Changed) -> None:
        event.stop()
        self.apply_market_filter()
        self.sync_buttons()

    @on(EditInput.EditingChanged)
    def _editing_changed(self, event: EditInput.EditingChanged) -> None:
        event.stop()
        self.draw_market_head()

    # ------------------------------------------------------------ Aktionen
    def actions(self) -> list[Action]:
        sel = self.selected_row()
        actions = [Action('n', 'Neuer Sensor', self.add_sensor, icon='setup')]
        if self.page == 'mine':
            if sel is None:
                block = submit_block = 'kein Sensor gewählt'
            else:
                block = 'ist bereits aktiv' if sel['active'] else None
                if not sel.get('local'):
                    submit_block = 'mitgelieferte Pakete sind schon im Release'
                elif sel['origin'] == 'market':
                    submit_block = 'aus dem Marktplatz installierte Pakete sind schon im Katalog'
                elif sel['status'] == 'verified':
                    submit_block = 'nur vorläufige Pakete werden eingereicht'
                else:
                    submit_block = None
            actions += [Action('a', 'Aktiv setzen', self.activate_selected, icon='check', blocked=block),
                        Action('u', 'Einreichen', self.submit_selected, icon='check', blocked=submit_block)]
            if self.pending:
                actions.append(Action('s', f'Ausstehende senden ({self.pending})', self.send_pending,
                                      icon='restart'))
        else:
            if sel is None:
                label, block = 'Installieren', 'kein Katalogeintrag gewählt'
            elif sel.get('update'):
                label, block = 'Aktualisieren', None
            elif sel.get('installed'):
                label, block = 'Installiert', 'ist bereits installiert'
            else:
                label, block = 'Installieren', None
            actions += [Action('k', 'Katalog laden', self.refresh_catalog, icon='network'),
                        Action('v', label, self.install_selected, icon='setup', blocked=block)]
        return actions

    def open_detail(self) -> None:
        sel = self.selected_row()
        if sel is not None:
            self.show_detail(sel)

    @staticmethod
    def detail_rows(row: dict) -> list:
        market = bool(row.get('market'))
        version = row.get('version')
        if row.get('installed_version') and market and row.get('installed'):
            version_text = f'{version} (installiert: {row["installed_version"]})'
        else:
            version_text = str(version) if version is not None else None
        origin = ('Marktplatz (installiert)' if row.get('installed') else 'Marktplatz (nicht installiert)') \
            if market else ORIGIN_LABEL.get(row['origin'], row['origin'])
        runs = row.get('runs')
        return [('Anzeigeart', value(kind_label(row)), True), ('Anschluss', value(connection_label(row))),
                ('Einheit', value(row['unit'] or None)), ('Hersteller', value(row['manufacturer'] or None), True),
                ('Kennung', value(row['id'])), ('Version', value(version_text)),
                ('Aliase', value(', '.join(row['aliases']) or None), True),
                ('Hinzugefügt', value(fmt_date(row.get('submitted')))),
                ('Prüfläufe', value(str(runs) if runs is not None else None)),
                ('Herkunft', value(origin), True)]

    def detail_buttons(self, row: dict) -> tuple[list[DetailButton], list[str]]:
        close = DetailButton('Schließen', 'close')
        if row.get('market'):
            if row.get('update'):
                main = DetailButton('Aktualisieren', 'update', primary=True)
            elif row.get('installed'):
                main = DetailButton('Installiert', 'none', disabled=True, reason='ist bereits installiert')
            else:
                main = DetailButton('Installieren', 'install', primary=True)
            notes = ['Wird als vorläufig installiert, auch wenn der Katalog „verifiziert“ nennt; Werte sind in '
                     'Läufen und im Audit als vorläufig markiert.'] if not main.disabled else []
            return [main, close], notes
        buttons = [DetailButton('Ist aktiv' if row['active'] else 'Als aktiv setzen', 'activate',
                                primary=not row['active'], disabled=row['active'],
                                reason='ist bereits aktiv' if row['active'] else None)]
        if row.get('local') and row['origin'] == 'local' and row['status'] != 'verified':
            buttons.append(DetailButton('Einreichen', 'submit'))
        notes = ['Vorläufig: Werte werden als vorläufig markiert.'] if row['status'] != 'verified' else []
        return [*buttons, close], notes

    @work(exclusive=True, group='sensor-detail')
    async def show_detail(self, row: dict) -> None:
        buttons, notes = self.detail_buttons(row)
        title = row['display_name']
        choice = await self.app.push_screen_wait(
            SensorDetailScreen(title, status_badge(row['status']), self.detail_rows(row),
                               row.get('example') or '', buttons, notes))
        if choice in ('install', 'update'):
            await self.install_row(row, overwrite=choice == 'update')
        elif choice == 'activate':
            await self.activate_row(row)
        elif choice == 'submit':
            await self.submit_row(row)

    def auto_refresh_catalog(self) -> None:
        if self.catalog_state == 'loading' or time.monotonic() - self._last_auto < AUTO_LOAD_PAUSE_S:
            return
        self._last_auto = time.monotonic()
        self.refresh_catalog(quiet=True)

    @work(exclusive=True, group='sensor-catalog')
    async def refresh_catalog(self, quiet: bool = False) -> None:
        app = self.app
        self.catalog_state = 'loading'
        self.draw_market_head()
        self.apply_market_filter()
        if not quiet:
            app.message(probes.OFF, 'Katalog wird geladen …')
        ok, message = await asyncio.to_thread(sensor_client.catalog_refresh, app.instance)
        self.catalog_state = 'ok' if ok else 'offline'
        self.catalog_note = message
        if ok:
            self.catalog_time = datetime.now().astimezone()
        if not quiet or not ok:
            app.message(probes.OK if ok else probes.WARN, message)
        self.reload()

    def install_selected(self) -> None:
        """Taste v: öffnet die Angaben des gewählten Katalogeintrags (dort „Installieren“ / „Aktualisieren“)."""
        sel = self.selected_row()
        if sel is not None and sel.get('market'):
            self.show_detail(sel)

    async def install_row(self, row: dict, *, overwrite: bool = False) -> None:
        app = self.app
        done, message = await asyncio.to_thread(sensor_client.catalog_install, app.instance, row['id'],
                                                overwrite=overwrite)
        app.message(probes.OK if done else probes.FAIL, message)
        if done:
            self.reload()
            self.apply_market_filter(keep=row['id'])
            self.sync_buttons()

    @work(exclusive=True, group='sensor-submit')
    async def submit_selected(self) -> None:
        sel = self.selected_row()
        if sel is None or sel.get('market') or not sel.get('local') or sel['status'] == 'verified':
            return
        await self.submit_row(sel)

    async def submit_row(self, row: dict) -> None:
        app = self.app
        lines = [f'„{row["display_name"]}“ ({row["id"]}) einreichen.', *CONSENT_LINES]
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
        done, message = await asyncio.to_thread(sensor_client.submit_sensor, app.instance, row['id'], consent=True)
        app.message(probes.OK if done else probes.FAIL, message)
        self.reload()

    @work(exclusive=True, group='sensor-pending')
    async def send_pending(self) -> None:
        app = self.app
        done, message = await asyncio.to_thread(sensor_client.submit_pending, app.instance)
        app.message(probes.OK if done else probes.FAIL, message)
        self.reload()

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
        sel = self.selected_row()
        if sel is None or sel['active'] or sel.get('market'):
            return
        await self.activate_row(sel)

    async def activate_row(self, row: dict) -> None:
        app = self.app
        if row['active'] or row.get('market'):
            return
        lines = [f'Die Werkbank liest künftig mit „{row["display_name"]}“ ({row["id"]}).',
                 'Wirksam nach einem Neustart der Werkbank; ein laufender Lauf bleibt unverändert.']
        provisional = row['status'] != 'verified'
        if provisional:
            lines.insert(0, 'vorläufig – Werte werden als vorläufig markiert (Läufe und Audit).')
        ok = await app.push_screen_wait(ConfirmScreen(Confirmation(
            'Sensor als aktiv setzen', lines, [], 'Als aktiv setzen', danger=provisional)))
        if not ok:
            return
        done, message = await asyncio.to_thread(sensor_client.activate, row['id'], app.instance)
        if not done:
            app.message(probes.FAIL, message)
            return
        app.instance.sensor = row['id']
        if app.instance.config:
            try:
                from ..instance import discover

                app.instance = discover(app.instance.config)
            except Exception:  # noqa: BLE001 - Anzeige bleibt beim gesetzten Wert
                pass
        app.sensor_restart_needed = True
        app.message(probes.OK, message)
        self.reload()
        self.sync_buttons()
