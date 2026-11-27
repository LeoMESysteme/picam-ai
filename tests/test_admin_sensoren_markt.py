"""Marktplatz im Tab „Sensoren“, Feature-Schalter und ausgeblendeter Tab (Textual-Pilot, Fakes).

Kein Netz, kein Forgejo: ``sensor_client`` wird ersetzt; geprüft wird, was die Oberfläche anzeigt, fragt und
aufruft (Einwilligung vor Token, Token maskiert, nie in Meldungen).
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime

import admin_fakes
import pytest
from textual.widgets import Checkbox, Input

from dispread.admin import sensor_client
from dispread.admin.ui import ConfirmScreen
from dispread.admin.views import TABS, visible_tabs
from dispread.admin.views.einstellungen import EinstellungenView
from dispread.admin.views.sensor_detail_screen import SensorDetailScreen
from dispread.admin.views.sensoren import SensorenView, TokenScreen

ROWS = [
    {'id': 'gsv2as-161a', 'display_name': 'GSV-2AS', 'manufacturer': 'ME', 'aliases': [], 'status': 'verified',
     'unit': 'mV/V', 'active': True, 'local': False, 'origin': 'bundled', 'version': 1, 'connection': 'rs232',
     'family': 'hd44780_5x8', 'polarity': 'dark_on_light', 'cells': 16, 'rows': 1, 'example': '+0.00000 mV/V'},
    {'id': 'astra-1', 'display_name': 'Astra Messbox', 'manufacturer': 'Astra', 'aliases': ['AST-1'],
     'status': 'provisional', 'unit': 'N', 'active': False, 'local': True, 'origin': 'local', 'version': 1,
     'connection': 'usb', 'family': 'hd44780_5x8', 'polarity': 'dark_on_light', 'cells': 16, 'rows': 1,
     'example': '+0.00000 N'},
]


def entry(sensor_id, name, manufacturer, status, unit, connection, version=1, aliases=(), runs=3):
    return {'id': sensor_id, 'display_name': name, 'manufacturer': manufacturer, 'aliases': list(aliases),
            'status': status, 'unit': unit, 'connection': connection, 'family': 'hd44780_5x8',
            'polarity': 'dark_on_light', 'example': f'+0.00000 {unit}', 'version': version,
            'submitted': '2026-11-20T09:12:00Z', 'checks': {'runs': runs}, 'files': {}}


CATALOG = [
    entry('astra-1', 'Astra Messbox', 'Astra', 'provisional', 'N', 'usb'),   # lokal vorhanden: installiert
    entry('zeta-9', 'Zeta Anzeige', 'Zeta', 'verified', 'kg', 'rs232', version=2, aliases=['ZX']),
    entry('kern-2', 'Kern Waage', 'Kern', 'verified', 'g', 'usb'),
    entry('digi-3', 'Digitron', 'Digitron', 'provisional', 'bar', 'unknown'),
]
TOKEN = 'geheim-token-123'


def text_of(widget) -> str:
    from rich.console import Console

    content = getattr(widget, '_content', None) or getattr(widget, 'renderable', None) or widget.render()
    console = Console(width=200, record=True, file=open('/dev/null', 'w'))
    console.print(content)
    return console.export_text()


async def press_button(pilot, app, selector):
    """Knopf im aktuellen Dialog auslösen, sobald er aufgebaut ist (Klicks direkt nach dem
    Öffnen trafen unter Last gelegentlich ins Leere)."""
    from textual.widgets import Button

    await until(pilot, lambda: bool(app.screen.query(selector)))
    app.screen.query_one(selector, Button).press()
    await pilot.pause(0.05)


async def until(pilot, predicate, limit_s=10.0):
    for _ in range(int(limit_s / 0.05)):
        if predicate():
            return
        await pilot.pause(0.05)
    raise AssertionError('Bedingung nicht eingetreten')


@pytest.fixture
def market(monkeypatch):
    monkeypatch.setattr(admin_fakes.INSTANCE, 'sensor', 'gsv2as-161a', raising=False)   # Aktivieren ändert sie
    state = {'enabled': True, 'token': False, 'calls': [], 'catalog': [], 'submit': (True, 'Eingereicht: x/1')}

    def rec(name, result):
        def fn(*args, **kwargs):
            state['calls'].append((name, args[1:] if args else (), kwargs))
            return result() if callable(result) else result
        return fn

    monkeypatch.setattr(sensor_client, 'feature_enabled', lambda instance=None: state['enabled'])
    monkeypatch.setattr(sensor_client, 'list_sensors',
                        lambda instance=None: [dict(r) for r in state.get('rows', ROWS)])
    monkeypatch.setattr(sensor_client, 'catalog_entries', lambda instance=None: [dict(e) for e in state['catalog']])
    monkeypatch.setattr(sensor_client, 'catalog_info', lambda instance=None: {
        'entries': [dict(e) for e in state['catalog']], 'generated': None, 'fetched': state.get('fetched')})
    monkeypatch.setattr(sensor_client, 'pending_count', lambda instance=None: state.get('pending', 0))
    monkeypatch.setattr(sensor_client, 'token_status', lambda instance=None: state['token'])
    def do_refresh():
        if state.get('refresh_wait') is not None:
            state['refresh_wait'].wait(10)
        result = state.get('refresh_result')
        if result is None:
            state.update(catalog=CATALOG, fetched=datetime.now().astimezone())
            return True, 'Katalog aktualisiert: 4'
        return result

    monkeypatch.setattr(sensor_client, 'catalog_refresh', rec('refresh', do_refresh))
    monkeypatch.setattr(sensor_client, 'catalog_install', rec('install', (True, 'zeta-9 installiert (vorläufig).')))
    monkeypatch.setattr(sensor_client, 'save_token',
                        rec('save_token', lambda: state.update(token=True) or (True, 'Token gespeichert.')))
    monkeypatch.setattr(sensor_client, 'submit_sensor', rec('submit', lambda: state['submit']))
    monkeypatch.setattr(sensor_client, 'submit_pending', rec('pending', (True, 'Ausstehende gesendet: 0.')))
    monkeypatch.setattr(sensor_client, 'set_feature',
                        lambda instance, value: state.update(enabled=value) or (True, 'Gespeichert.', False))
    return state


def test_tab_hidden_when_feature_off(market):
    market['enabled'] = False

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.3)
            assert 'sensoren' not in app.tab_ids() and 'einstellungen' in app.tab_ids()
            assert not app.query('#sensoren')
            await pilot.press('o')          # Taste tut nichts
            await pilot.pause(0.2)
            assert app.current == 'dashboard'
            for _ in range(len(app.tab_ids())):   # Tab-Taste kommt an allen vorbei
                await pilot.press('tab')
                await pilot.pause(0.05)
            assert app.current == 'dashboard'
    asyncio.run(main())


def test_visible_tabs_filters_by_feature():
    assert SensorenView in TABS
    assert SensorenView not in visible_tabs(None, enabled=False)
    assert SensorenView in visible_tabs(None, enabled=True)
    assert len(visible_tabs(None, enabled=False)) == len(TABS) - 1


def test_settings_switch_shows_and_hides_tab(market):
    market['enabled'] = False

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('c')
            await until(pilot, lambda: bool(app.query('#cfg-feature')))
            box = app.query_one('#cfg-feature', Checkbox)
            assert box.value is False
            box.value = True
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await press_button(pilot, app, '#ok')
            await until(pilot, lambda: 'sensoren' in app.tab_ids())
            assert market['enabled'] is True
            # abbrechen stellt den Schalter zurück
            box.value = False
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await press_button(pilot, app, '#cancel')
            await until(pilot, lambda: box.value is True)
            assert 'sensoren' in app.tab_ids()
            # ausschalten blendet den Tab wieder aus
            box.value = False
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await press_button(pilot, app, '#ok')
            await until(pilot, lambda: 'sensoren' not in app.tab_ids())
            assert market['enabled'] is False and isinstance(app.query_one(EinstellungenView), EinstellungenView)
    asyncio.run(main())


def test_settings_switch_failure_reverts(market, monkeypatch):
    market['enabled'] = False
    monkeypatch.setattr(sensor_client, 'set_feature', lambda instance, value: (False, 'Schalter: kaputt', False))

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('c')
            await until(pilot, lambda: bool(app.query('#cfg-feature')))
            box = app.query_one('#cfg-feature', Checkbox)
            box.value = True
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await until(pilot, lambda: bool(app.screen.query('#ok')))
            await press_button(pilot, app, '#ok')
            await until(pilot, lambda: box.value is False and not isinstance(app.screen, ConfirmScreen))
            assert 'sensoren' not in app.tab_ids()
    asyncio.run(main())


def open_sensors(app):
    return app.query_one(SensorenView)


def ids(view):
    return [r['id'] for r in view.shown]


def test_market_page_auto_loads_catalog_and_marks_installed(market):
    """Beim Öffnen des Marktplatzes lädt der Katalog im Hintergrund; installierte Einträge tragen die Marke."""
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = open_sensors(app)
            assert view.page == 'mine' and not market['calls']      # Meine Sensoren lädt nichts aus dem Netz
            assert [c.key for c in view.grid().cards] == ['gsv2as-161a', 'astra-1']
            await pilot.press('m')
            await until(pilot, lambda: view.page == 'market' and any(c[0] == 'refresh' for c in market['calls']))
            await until(pilot, lambda: len(view.shown) == 4)
            assert ids(view) == ['astra-1', 'digi-3', 'kern-2', 'zeta-9']     # nach Name sortiert
            head = text_of(view.query_one('#sen-market-head'))
            assert '4 von 4' in head and 'Katalog von' in head
            cards = {c.key: c for c in view.query_one('#sen-grid-market').cards}
            assert 'installiert' in cards['astra-1'].marker.plain and cards['zeta-9'].marker is None
            # Zurück und wieder hin: innerhalb der Pause kein zweiter Abruf
            await pilot.press('m')
            await pilot.press('m')
            await pilot.pause(0.3)
            assert [c[0] for c in market['calls']].count('refresh') == 1
    asyncio.run(main())


def test_market_offline_keeps_cache_with_hint(market):
    market['catalog'] = CATALOG
    market['fetched'] = datetime(2026, 11, 27, 9, 14).astimezone()
    market['refresh_result'] = (False, 'Katalog nicht geladen: Forgejo nicht erreichbar')

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            await pilot.press('m')
            view = open_sensors(app)
            await until(pilot, lambda: view.catalog_state == 'offline')
            assert len(view.shown) == 4                       # zwischengespeicherter Stand bleibt
            head = text_of(view.query_one('#sen-market-head'))
            assert 'offline' in head and '09:14' in head and 'zwischengespeichert' in head
    asyncio.run(main())


def test_market_offline_without_cache_shows_empty_state(market):
    market['refresh_result'] = (False, 'Katalog nicht geladen: Forgejo nicht erreichbar')

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            await pilot.press('m')
            view = open_sensors(app)
            await until(pilot, lambda: view.catalog_state == 'offline')
            grid = text_of(view.query_one('#sen-grid-market'))
            assert 'Kein Katalog' in grid and 'k versucht es erneut' in grid
            assert view.shown == [] and 'offline, kein Katalog' in text_of(view.query_one('#sen-market-head'))
    asyncio.run(main())


def test_market_does_not_block_ui_while_loading(market):
    """Der Abruf läuft im Hintergrund: die Seite reagiert, während er noch läuft."""
    release = threading.Event()
    market['refresh_wait'] = release

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            await pilot.press('m')
            view = open_sensors(app)
            await until(pilot, lambda: view.catalog_state == 'loading')
            assert 'wird geladen' in text_of(view.query_one('#sen-market-head'))
            await pilot.press('m')                      # Seitenwechsel geht trotz laufendem Abruf
            await until(pilot, lambda: view.page == 'mine')
            release.set()
            await until(pilot, lambda: view.catalog_state == 'ok')
    asyncio.run(main())


def test_active_sensor_is_marked_in_band_and_card(market):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = open_sensors(app)
            band = text_of(view.query_one('#sen-active'))
            assert 'AKTIVER SENSOR' in band and 'GSV-2AS' in band and 'RS232' in band and 'mV/V' in band
            assert 'Punktraster' in band and 'dunkel auf hell' in band and 'verifiziert' in band
            cards = view.grid().cards
            assert cards[0].active and not cards[1].active and 'AKTIV' in cards[0].marker.plain
            assert 'AKTIV' in text_of(view.grid())
            await pilot.press('m')                    # das Band steht auf beiden Seiten
            await pilot.pause(0.3)
            assert 'AKTIVER SENSOR' in text_of(view.query_one('#sen-active'))
            assert view.app.focused is view.grid()
    asyncio.run(main())


def test_activate_shows_restart_hint(market, monkeypatch):
    monkeypatch.setattr(sensor_client, 'activate', lambda sid, instance=None: (True, 'aktiv gesetzt'))

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = open_sensors(app)
            assert 'Neustart' not in text_of(view.query_one('#sen-active'))
            view.grid()._select(1)
            await pilot.pause(0.1)
            view.activate_selected()
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await press_button(pilot, app, '#ok')
            await until(pilot, lambda: 'Neustart der Werkbank nötig' in text_of(view.query_one('#sen-active')))
    asyncio.run(main())


def test_pages_switch_by_key_arrows_and_click(market):
    market['catalog'] = CATALOG

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = open_sensors(app)
            sub = view.query_one('#sen-sub')
            assert view.query_one('#sen-page-market').display is False
            await pilot.press('m')
            await until(pilot, lambda: view.page == 'market')
            assert view.query_one('#sen-page-mine').display is False and view.query_one('#sen-page-market').display
            await pilot.press('m')
            await until(pilot, lambda: view.page == 'mine')
            sub.focus()
            await pilot.press('right')
            await until(pilot, lambda: view.page == 'market')
            await pilot.press('left')
            await until(pilot, lambda: view.page == 'mine')
            await pilot.click('#sen-sub', offset=(40, 0))   # zweites Segment
            await until(pilot, lambda: view.page == 'market')
    asyncio.run(main())


def test_market_filters_search_connection_status_and_new_only(market):
    market['catalog'] = CATALOG

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            await pilot.press('m')
            view = open_sensors(app)
            await until(pilot, lambda: len(view.shown) == 4)
            bar = view.query_one('#sen-filters')
            search = view.query_one('#sen-filter')
            search.value = 'zx'                                   # Alias
            await pilot.pause(0.2)
            assert ids(view) == ['zeta-9']
            search.value = 'kern'                                 # Hersteller
            await pilot.pause(0.2)
            assert ids(view) == ['kern-2']
            search.value = ''
            await pilot.pause(0.2)
            bar.values['connection'] = 'usb'                      # Anschluss
            bar.post_message(bar.Changed(bar))
            await pilot.pause(0.2)
            assert ids(view) == ['astra-1', 'kern-2']
            bar.values['status'] = 'verified'                     # Status
            bar.post_message(bar.Changed(bar))
            await pilot.pause(0.2)
            assert ids(view) == ['kern-2']
            bar.values['connection'] = ''
            bar.values['status'] = ''
            bar.values['new'] = 'new'                             # nur nicht installierte
            bar.post_message(bar.Changed(bar))
            await pilot.pause(0.2)
            assert ids(view) == ['digi-3', 'kern-2', 'zeta-9']
            assert '3 von 4' in text_of(view.query_one('#sen-market-head'))
            bar.values['kind'] = 'nichts'                         # unbekannter Wert wird zurückgesetzt
            bar.reset()
            await pilot.pause(0.2)
            assert len(view.shown) == 4
    asyncio.run(main())


def test_filter_bar_keys_cycle_values(market):
    market['catalog'] = CATALOG

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            await pilot.press('m')
            view = open_sensors(app)
            await until(pilot, lambda: len(view.shown) == 4)
            bar = view.query_one('#sen-filters')
            bar.focus()
            await pilot.press('enter')                            # Anschluss: erste Option nach „alle“
            await pilot.pause(0.2)
            assert bar.active() == {'connection': 'rs232'} and ids(view) == ['zeta-9']
            await pilot.press('right', 'enter')                   # Status: verifiziert
            await pilot.pause(0.2)
            assert bar.active() == {'connection': 'rs232', 'status': 'verified'}
            await pilot.press('backspace')                        # Status zurück auf „alle“
            await pilot.pause(0.2)
            assert bar.active() == {'connection': 'rs232'}
    asyncio.run(main())


def test_detail_popup_shows_fields_and_installs(market):
    market['catalog'] = CATALOG

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            await pilot.press('m')
            view = open_sensors(app)
            await until(pilot, lambda: len(view.shown) == 4)
            view.grid()._select(ids(view).index('zeta-9'))
            await pilot.press('enter')
            await until(pilot, lambda: isinstance(app.screen, SensorDetailScreen))
            await pilot.pause(0.2)
            screen = app.screen
            body = text_of(screen.query_one('#det-fields')) + text_of(screen.query_one('#det-title'))
            for expected in ('Zeta Anzeige', 'verifiziert', 'Punktraster',
                             'dunkel auf hell', 'RS232', 'kg', 'Zeta', 'zeta-9', '2', '20.11.2026', 'Marktplatz',
                             'nicht installiert'):
                assert expected in body, expected
            cells = text_of(screen.query_one('#det-preview')).splitlines()[0]
            assert ''.join(cells.split()) == '+0.00000kg'              # Formatvorschau der 16 Zellen
            assert 'vorläufig installiert' in text_of(screen.query_one('#det-notes'))
            labels = [str(b.label) for b in screen.query('#det-buttons Button')]
            assert labels == ['Installieren', 'Schließen']
            await press_button(pilot, app, '#det-btn-0')
            await until(pilot, lambda: any(c[0] == 'install' for c in market['calls']))
            assert market['calls'][-1][1] == ('zeta-9',) and market['calls'][-1][2] == {'overwrite': False}
            await until(pilot, lambda: not isinstance(app.screen, SensorDetailScreen))
    asyncio.run(main())


def test_detail_popup_installed_and_update_buttons(market):
    market['catalog'] = [*CATALOG[:1], entry('zeta-9', 'Zeta Anzeige', 'Zeta', 'verified', 'kg', 'rs232', version=2)]
    market['refresh_result'] = (True, 'Katalog aktualisiert')
    rows = [*ROWS, {**ROWS[1], 'id': 'zeta-9', 'display_name': 'Zeta Anzeige', 'origin': 'market', 'version': 1,
                    'active': False}]
    market['rows'] = rows

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = open_sensors(app)
            view.reload()
            await pilot.press('m')
            await pilot.pause(0.2)
            assert ids(view) == ['astra-1', 'zeta-9']
            view.show_detail(view.shown[0])                       # installiert, gleiche Version
            await until(pilot, lambda: isinstance(app.screen, SensorDetailScreen))
            first = app.screen.query_one('#det-btn-0')
            assert str(first.label) == 'Installiert' and first.disabled
            await pilot.press('escape')
            await until(pilot, lambda: not isinstance(app.screen, SensorDetailScreen))
            view.show_detail(view.shown[1])                       # neuere Version im Katalog
            await until(pilot, lambda: isinstance(app.screen, SensorDetailScreen))
            first = app.screen.query_one('#det-btn-0')
            assert str(first.label) == 'Aktualisieren' and not first.disabled
            await press_button(pilot, app, '#det-btn-0')
            await until(pilot, lambda: any(c[0] == 'install' for c in market['calls']))
            assert market['calls'][-1][2] == {'overwrite': True}
    asyncio.run(main())


def test_detail_popup_of_own_sensor_activates_and_submits(market):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = open_sensors(app)
            view.grid()._select(1)
            await pilot.press('enter')
            await until(pilot, lambda: isinstance(app.screen, SensorDetailScreen))
            labels = [str(b.label) for b in app.screen.query('#det-buttons Button')]
            assert labels == ['Als aktiv setzen', 'Einreichen', 'Schließen']
            assert 'lokal angelegt' in text_of(app.screen.query_one('#det-fields'))
            await press_button(pilot, app, '#det-btn-1')                # Einreichen führt zur Einwilligung
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert 'öffentlich im Katalog' in str(app.screen.c.lines)
            await press_button(pilot, app, '#cancel')
            await pilot.pause(0.2)
            assert market['calls'] == []
            view.grid()._select(0)                                      # aktiver Sensor: nur Schließen sinnvoll
            await pilot.press('enter')
            await until(pilot, lambda: isinstance(app.screen, SensorDetailScreen))
            first = app.screen.query_one('#det-btn-0')
            assert str(first.label) == 'Ist aktiv' and first.disabled
            assert [str(b.label) for b in app.screen.query('#det-buttons Button')] == ['Ist aktiv', 'Schließen']
    asyncio.run(main())


def test_click_on_card_opens_popup(market):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            await pilot.click('#sen-grid-mine', offset=(60, 2))        # zweite Spalte, erste Zeile
            await until(pilot, lambda: isinstance(app.screen, SensorDetailScreen))
            assert 'Astra Messbox' in text_of(app.screen.query_one('#det-title'))
    asyncio.run(main())


def test_card_grid_columns_follow_width_and_scroll(market):
    many = [{**ROWS[1], 'id': f'sensor-{n:02d}', 'display_name': f'Sensor {n:02d}', 'active': False}
            for n in range(30)]
    market['rows'] = many

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.4)
            grid = open_sensors(app).grid()
            assert grid._geometry[0] == 3                               # 120 Spalten: drei Karten nebeneinander
            grid.action_jump(-1)
            await pilot.pause(0.2)
            assert grid.selected == 29 and grid._top > 0                # Auswahl bleibt sichtbar
            await pilot.press('home')
            await pilot.pause(0.2)
            assert grid.selected == 0 and grid._top == 0
    asyncio.run(main())


@pytest.mark.parametrize('page', ['mine', 'market'])
def test_small_terminal_keeps_buttons_and_popup_visible(market, page):
    market['catalog'] = CATALOG

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.4)
            view = open_sensors(app)
            if page == 'market':
                await pilot.press('m')
                await until(pilot, lambda: len(view.shown) == 4)
            await pilot.pause(0.3)
            for key in [a.key for a in view.actions()]:
                button = view.query_one(f'#act-{key}')
                assert button.region.height > 0 and button.region.y + button.region.height <= 24, key
            grid = view.grid()
            assert grid.region.height >= 6                              # mindestens eine Kartenzeile sichtbar
            await pilot.press('enter')
            await until(pilot, lambda: isinstance(app.screen, SensorDetailScreen))
            await pilot.pause(0.3)
            for button in app.screen.query('#det-buttons Button'):
                region = button.region
                assert region.height > 0 and region.bottom <= 24 and region.right <= 80, (button.id, region)
    asyncio.run(main())



def test_submit_asks_consent_then_masked_token(market):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = app.query_one(SensorenView)
            view.grid()._select(1)
            await pilot.pause(0.2)
            assert {a.key: a for a in view.actions()}['u'].blocked is None
            view.submit_selected()
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert 'öffentlich im Katalog' in str(app.screen.c.lines)
            assert 'keine Bilder' in str(app.screen.c.lines)
            await press_button(pilot, app, '#ok')
            await until(pilot, lambda: isinstance(app.screen, TokenScreen))
            field = app.screen.query_one('#ask-input', Input)
            assert field.password is True
            field.value = TOKEN
            await press_button(pilot, app, '#ok')
            await until(pilot, lambda: any(c[0] == 'submit' for c in market['calls']))
            names = [c[0] for c in market['calls']]
            assert names.index('save_token') < names.index('submit')
            assert market['calls'][-1][2] == {'consent': True}
            assert TOKEN not in repr([m for m in getattr(app, 'messages', [])])
    asyncio.run(main())


def test_submit_with_saved_token_skips_token_dialog(market):
    market['token'] = True

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = app.query_one(SensorenView)
            view.grid()._select(1)
            await pilot.pause(0.2)
            view.submit_selected()
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await press_button(pilot, app, '#ok')
            await until(pilot, lambda: any(c[0] == 'submit' for c in market['calls']))
            assert not any(c[0] == 'save_token' for c in market['calls'])
    asyncio.run(main())


def test_submit_declined_sends_nothing(market):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = app.query_one(SensorenView)
            view.grid()._select(1)
            await pilot.pause(0.2)
            view.submit_selected()
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await press_button(pilot, app, '#cancel')
            await pilot.pause(0.3)
            assert market['calls'] == []
    asyncio.run(main())


def test_submit_blocked_for_bundled_and_pending_runs(market):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = app.query_one(SensorenView)
            assert {a.key: a for a in view.actions()}['u'].blocked   # GSV-2AS ist mitgeliefert
            view.send_pending()
            await until(pilot, lambda: any(c[0] == 'pending' for c in market['calls']))
    asyncio.run(main())





# ------------------------------------------------------------ Wrapper ohne Backend

def test_client_reports_missing_backend(monkeypatch):
    import builtins

    real = builtins.__import__

    def deny(name, *args, **kwargs):
        if name == 'dispread.sensors' and args and args[2] and ('catalog' in args[2] or 'features' in args[2]):
            raise ImportError(name)
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', deny)
    assert sensor_client.feature_enabled(None) is False
    ok, message, _ = sensor_client.set_feature(None, True)
    assert not ok and sensor_client.BACKEND_MISSING in message
    assert sensor_client.catalog_entries(None) == []
    ok, message = sensor_client.catalog_refresh(None)
    assert not ok and sensor_client.BACKEND_MISSING in message


def test_client_save_token_never_echoes_token(monkeypatch):
    class Fake:
        @staticmethod
        def save_token(instance, token):
            raise ValueError(f'abgelehnt: {token}')

    monkeypatch.setattr(sensor_client, '_catalog', lambda: Fake)
    ok, message = sensor_client.save_token(None, TOKEN)
    assert not ok and TOKEN not in message
