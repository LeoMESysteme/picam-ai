"""Marktplatz im Tab „Sensoren“, Feature-Schalter und ausgeblendeter Tab (Textual-Pilot, Fakes).

Kein Netz, kein Forgejo: ``sensor_client`` wird ersetzt; geprüft wird, was die Oberfläche anzeigt, fragt und
aufruft (Einwilligung vor Token, Token maskiert, nie in Meldungen).
"""

from __future__ import annotations

import asyncio

import admin_fakes
import pytest
from textual.widgets import Checkbox, Input

from dispread.admin import sensor_client
from dispread.admin.ui import ConfirmScreen
from dispread.admin.views import TABS, visible_tabs
from dispread.admin.views.einstellungen import EinstellungenView
from dispread.admin.views.sensoren import SensorenView, TokenScreen

ROWS = [
    {'id': 'gsv2as-161a', 'display_name': 'GSV-2AS', 'manufacturer': 'ME', 'aliases': [], 'status': 'verified',
     'unit': 'mV/V', 'active': True, 'local': False},
    {'id': 'astra-1', 'display_name': 'Astra Messbox', 'manufacturer': 'Astra', 'aliases': ['AST-1'],
     'status': 'provisional', 'unit': 'N', 'active': False, 'local': True},
]
CATALOG = [
    {'id': 'astra-1', 'display_name': 'Astra Messbox', 'status': 'provisional'},   # lokal vorhanden: kein Doppel
    {'id': 'zeta-9', 'display_name': 'Zeta Anzeige', 'manufacturer': 'Zeta', 'aliases': ['ZX'],
     'status': 'verified', 'unit': 'kg', 'version': 2},
]
TOKEN = 'geheim-token-123'


def text_of(widget) -> str:
    from rich.console import Console

    content = getattr(widget, '_content', None) or getattr(widget, 'renderable', None) or widget.render()
    console = Console(width=200, record=True, file=open('/dev/null', 'w'))
    console.print(content)
    return console.export_text()


async def until(pilot, predicate, limit_s=10.0):
    for _ in range(int(limit_s / 0.05)):
        if predicate():
            return
        await pilot.pause(0.05)
    raise AssertionError('Bedingung nicht eingetreten')


@pytest.fixture
def market(monkeypatch):
    state = {'enabled': True, 'token': False, 'calls': [], 'catalog': [], 'submit': (True, 'Eingereicht: x/1')}

    def rec(name, result):
        def fn(*args, **kwargs):
            state['calls'].append((name, args[1:] if args else (), kwargs))
            return result() if callable(result) else result
        return fn

    monkeypatch.setattr(sensor_client, 'feature_enabled', lambda instance=None: state['enabled'])
    monkeypatch.setattr(sensor_client, 'list_sensors', lambda instance=None: [dict(r) for r in ROWS])
    monkeypatch.setattr(sensor_client, 'catalog_entries', lambda instance=None: [dict(e) for e in state['catalog']])
    monkeypatch.setattr(sensor_client, 'token_status', lambda instance=None: state['token'])
    monkeypatch.setattr(sensor_client, 'catalog_refresh',
                        rec('refresh', lambda: state.update(catalog=CATALOG) or (True, 'Katalog aktualisiert: 2')))
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
            await pilot.pause(0.3)
            box = app.query_one('#cfg-feature', Checkbox)
            assert box.value is False
            box.value = True
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.click('#ok')
            await until(pilot, lambda: 'sensoren' in app.tab_ids())
            assert market['enabled'] is True
            # abbrechen stellt den Schalter zurück
            box.value = False
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.click('#cancel')
            await until(pilot, lambda: box.value is True)
            assert 'sensoren' in app.tab_ids()
            # ausschalten blendet den Tab wieder aus
            box.value = False
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.click('#ok')
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
            await pilot.click('#ok')
            await until(pilot, lambda: box.value is False and not isinstance(app.screen, ConfirmScreen))
            assert 'sensoren' not in app.tab_ids()
    asyncio.run(main())


def test_search_covers_catalog_and_install(market):
    market['catalog'] = CATALOG

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = app.query_one(SensorenView)
            assert [r['id'] for r in view.shown] == ['gsv2as-161a', 'astra-1', 'zeta-9']   # kein Doppel astra-1
            assert 'Marktplatz' in text_of(view.query_one('#sen-chips'))
            view.query_one('#sen-filter').value = 'zx'   # Alias eines Katalogeintrags
            await pilot.pause(0.2)
            assert [r['id'] for r in view.shown] == ['zeta-9']
            assert 'nicht installiert' in text_of(view.query_one('#sen-detail'))
            keys = {a.key: a for a in view.actions()}
            assert keys['v'].blocked is None and keys['a'].blocked and keys['u'].blocked
            view.install_selected()
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert 'vorläufig' in str(app.screen.c.lines)
            await pilot.click('#ok')
            await until(pilot, lambda: any(c[0] == 'install' for c in market['calls']))
            assert market['calls'][-1][1] == ('zeta-9',)
    asyncio.run(main())


def test_refresh_catalog_action(market):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = app.query_one(SensorenView)
            assert [r['id'] for r in view.shown] == ['gsv2as-161a', 'astra-1']
            assert 'nicht geladen' in text_of(view.query_one('#sen-market'))
            view.refresh_catalog()
            await until(pilot, lambda: 'zeta-9' in [r['id'] for r in view.shown])
            assert '2 Einträge' in text_of(view.query_one('#sen-market'))
    asyncio.run(main())


def test_submit_asks_consent_then_masked_token(market):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = app.query_one(SensorenView)
            view.query_one('#sen-chips').choose(1)
            await pilot.pause(0.2)
            assert {a.key: a for a in view.actions()}['u'].blocked is None
            view.submit_selected()
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert 'öffentlich im Katalog' in str(app.screen.c.lines)
            assert 'keine Bilder' in str(app.screen.c.lines)
            await pilot.click('#ok')
            await until(pilot, lambda: isinstance(app.screen, TokenScreen))
            field = app.screen.query_one('#ask-input', Input)
            assert field.password is True
            field.value = TOKEN
            await pilot.click('#ok')
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
            view.query_one('#sen-chips').choose(1)
            await pilot.pause(0.2)
            view.submit_selected()
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.click('#ok')
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
            view.query_one('#sen-chips').choose(1)
            await pilot.pause(0.2)
            view.submit_selected()
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            await pilot.click('#cancel')
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


def test_small_terminal_keeps_buttons_visible(market):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.4)
            view = app.query_one(SensorenView)
            for key in 'nark vus'.replace(' ', ''):
                button = view.query_one(f'#act-{key}')
                assert button.region.height > 0 and button.region.y + button.region.height <= 24
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
