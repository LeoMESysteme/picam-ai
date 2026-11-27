"""Tab „Sensoren“, Assistenten-Formular und Onboarding-Bildschirm der Konsole (Textual-Pilot).

Keine echten Agenten, Prozesse oder Kamera: ``sensor_client`` wird ersetzt, der Onboarding-Prozess ist ein
Fake, der Ereignisse in ``events.jsonl`` schreibt wie das Backend.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

import admin_fakes
import pytest

from dispread.admin import sensor_client
from dispread.admin.ui import AskScreen, ConfirmScreen, InfoScreen
from dispread.admin.views.sensor_onboarding_screen import SensorOnboardingScreen
from dispread.admin.views.sensor_wizard_screen import (
    SensorWizardScreen,
    cell_preview,
    validate_form,
)
from dispread.admin.views.sensoren import SensorenView, matches
from dispread.sensors.onboarding import RunDir

ROWS = [
    {'id': 'gsv2as-161a', 'display_name': 'GSV-2AS', 'manufacturer': 'ME-Meßsysteme', 'aliases': ['GSV-2ASD'],
     'status': 'verified', 'unit': 'mV/V', 'active': True, 'local': False, 'origin': 'bundled', 'version': 1,
     'connection': 'rs232', 'family': 'hd44780_5x8', 'polarity': 'dark_on_light', 'cells': 16, 'rows': 1,
     'example': '+0.00000 mV/V'},
    {'id': 'astra-1', 'display_name': 'Astra Messbox', 'manufacturer': 'Astra', 'aliases': ['AST-1'],
     'status': 'provisional', 'unit': 'N', 'active': False, 'local': True, 'origin': 'local', 'version': 1},
]
GOOD = {'claude': {'installed': True, 'logged_in': True}, 'codex': {'installed': True, 'logged_in': False}}


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
def client(monkeypatch):
    calls = {'activate': []}
    monkeypatch.setattr(admin_fakes.INSTANCE, 'sensor', 'gsv2as-161a', raising=False)   # Aktivieren ändert sie
    monkeypatch.setattr(sensor_client, 'feature_enabled', lambda instance=None: True)
    monkeypatch.setattr(sensor_client, 'catalog_entries', lambda instance=None: [])
    monkeypatch.setattr(sensor_client, 'token_status', lambda instance=None: False)
    monkeypatch.setattr(sensor_client, 'list_sensors', lambda instance=None: [dict(r) for r in ROWS])
    monkeypatch.setattr(sensor_client, 'detect_assistants', lambda instance=None: GOOD)
    monkeypatch.setattr(sensor_client, 'list_ports', lambda instance=None: [{'port': '/dev/ttyUSB0',
                                                                            'label': '/dev/ttyUSB0 (FTDI)'}])
    monkeypatch.setattr(sensor_client, 'activate',
                        lambda sid, instance=None: calls['activate'].append(sid) or (True, 'aktiv gesetzt'))
    return calls


# ------------------------------------------------------------ Tab

def test_tab_lists_installed_sensors_as_cards(client):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = app.query_one(SensorenView)
            assert app.current == 'sensoren' and view.page == 'mine'
            assert [c.key for c in view.grid().cards] == ['gsv2as-161a', 'astra-1']
            assert app.focused is view.grid()                         # Fokus beim Öffnen im Raster
            active = text_of(view.query_one('#sen-active'))
            assert 'GSV-2AS' in active and 'verifiziert' in active and 'AKTIVER SENSOR' in active
            grid = text_of(view.grid())
            assert 'Astra Messbox' in grid and 'vorläufig' in grid and 'lokal angelegt' in grid
            assert 'AKTIV' in grid and 'Anschluss unbekannt' in grid    # ohne Angabe: unbekannt, nichts erfunden
            sub = text_of(view.query_one('#sen-sub'))
            assert 'Meine Sensoren (2)' in sub and 'Marktplatz' in sub
            actions = {a.key: a for a in view.actions()}
            assert set(actions) == {'n', 'a', 'u'} and actions['a'].blocked == 'ist bereits aktiv'
    asyncio.run(main())


def test_matches_name_manufacturer_alias():
    assert matches(ROWS[0], 'gsv-2asd') and matches(ROWS[1], 'astra messbox') and matches(ROWS[0], 'me-meß')
    assert not matches(ROWS[0], 'astra')


def test_activate_provisional_warns_and_calls_backend(client):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause(0.3)
            await pilot.press('o')
            await pilot.pause(0.3)
            view = app.query_one(SensorenView)
            actives = {a.key: a for a in view.actions()}
            assert actives['a'].blocked == 'ist bereits aktiv'
            await pilot.press('right')                              # Pfeile wählen die nächste Karte
            await pilot.pause(0.2)
            assert view.selected_row()['id'] == 'astra-1'
            assert {a.key: a for a in view.actions()}['a'].blocked is None
            view.activate_selected()
            await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
            assert 'vorläufig – Werte werden als vorläufig markiert' in str(app.screen.c.lines)
            await pilot.click('#ok')
            await until(pilot, lambda: client['activate'])
            assert client['activate'] == ['astra-1']
    asyncio.run(main())


# ------------------------------------------------------------ Formular

def test_validate_form_messages_and_request():
    request, errors = validate_form({'name': '  '}, GOOD)
    assert request is None and 'Name fehlt' in errors['name']
    _, errors = validate_form({'name': 'X', 'example': 'x' * 17}, GOOD)
    assert '17 Zeichen' in errors['example']
    _, errors = validate_form({'name': 'X', 'assistant': 'codex'}, GOOD)
    assert 'nicht angemeldet' in errors['assistant']
    _, errors = validate_form({'name': 'X', 'assistant': 'claude'}, {})
    assert 'nicht installiert' in errors['assistant']
    request, errors = validate_form({'name': ' GSV-2TSD-DI ', 'manufacturer': 'ME', 'example': '+ 1.2345 mV/V',
                                     'unit': 'mV/V', 'connection': 'rs232', 'port': '/dev/ttyUSB0',
                                     'hint': '', 'assistant': 'claude'}, GOOD)
    assert errors == {} and request['name'] == 'GSV-2TSD-DI' and request['v'] == 1
    assert request['example'] == '+ 1.2345 mV/V   ' and len(request['example']) == 16
    assert request['display_family'] == 'hd44780_5x8'
    assert request['connection'] == {'kind': 'rs232', 'port': '/dev/ttyUSB0', 'hint': None}
    request, _ = validate_form({'name': 'A', 'connection': 'none', 'port': '/dev/x', 'assistant': 'none'}, GOOD)
    assert request['connection']['port'] is None and 'example' not in request


def test_cell_preview_shows_sixteen_cells():
    text = cell_preview('+ 1').plain
    assert text.splitlines()[1].split() == [f'{i:X}' for i in range(16)]


def test_wizard_form_blocks_unusable_assistant_and_returns_request(client):
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(110, 60)) as pilot:
            await pilot.pause(0.3)
            logins = []
            app.run_in_terminal = lambda command, title: logins.append(command) or 0
            result = []
            screen = SensorWizardScreen(GOOD, [{'port': '/dev/ttyUSB0', 'label': '/dev/ttyUSB0 (FTDI)'}])
            app.push_screen(screen, callback=result.append)
            await pilot.pause(0.3)
            await pilot.click('#wiz-ok')
            await pilot.pause(0.2)
            assert 'Name fehlt' in text_of(screen.query_one('#wiz-error')) and not result
            screen.query_one('#wiz-name').value = 'Neu 1'
            screen.query_one('#wiz-example').value = '+ 1.2345 mV/V'
            await pilot.pause(0.2)
            assert 'Sensor' not in text_of(screen.query_one('#wiz-preview')) and '+' in text_of(
                screen.query_one('#wiz-preview'))
            screen.query_one('#wiz-assist').choose(1)   # Codex: installiert, nicht angemeldet
            await pilot.pause(0.2)
            assert screen.query_one('#wiz-login').display
            await pilot.click('#wiz-ok')
            await pilot.pause(0.2)
            assert 'nicht angemeldet' in text_of(screen.query_one('#wiz-error')) and not result
            await pilot.click('#wiz-login')
            assert logins == [['codex', 'login']]
            screen.query_one('#wiz-assist').choose(2)   # Ohne KI
            screen.query_one('#wiz-port').choose(1)
            await pilot.pause(0.2)
            await pilot.click('#wiz-ok')
            await until(pilot, lambda: result)
            request = result[0]
            assert request['name'] == 'Neu 1' and request['assistant'] == 'none'
            assert request['connection']['port'] == '/dev/ttyUSB0'
    asyncio.run(main())


# ------------------------------------------------------------ Onboarding-Bildschirm

class FakeProc:
    """Prozess-Attrappe: führt ``script(run)`` in einem Thread aus und schreibt Ereignisse wie das Backend."""

    pid = None

    def __init__(self, run: RunDir, script):
        self.code = None

        def go():
            try:
                script(run)
            finally:
                self.code = 0
        threading.Thread(target=go, daemon=True).start()

    def poll(self):
        return self.code

    def terminate(self):
        self.code = -15

    kill = terminate


def drive(tmp_path, monkeypatch, script, test, assistant='none'):
    run = RunDir.create(tmp_path, {'v': 1, 'name': 'Neu 1'})
    monkeypatch.setattr(sensor_client, 'start_onboard', lambda r, a, instance=None: FakeProc(r, script))
    monkeypatch.setattr(sensor_client, 'stop_process', lambda proc, kill=False: proc.terminate())

    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause(0.3)
            screen = SensorOnboardingScreen(app.instance, run, assistant)
            app.push_screen(screen)
            await pilot.pause(0.2)
            await test(app, pilot, screen, run)
            screen.cancel_event.set()
    asyncio.run(main())
    return run


def test_events_checklist_question_and_done(tmp_path, monkeypatch):
    answers = []

    def script(run):
        run.step('anfrage', 'done')
        run.step('kamera', 'running', 'Standbild')
        run.log('Anzeige gefunden', 'agent')
        answers.append(run.ask('format', 'choice', 'Welches Format?',
                               [{'label': 'Vorzeichen + Zahl', 'value': 'a'}, {'label': 'Nur Zahl', 'value': 'b'}]))
        answers.append(run.ask('name', 'text', 'Anzeigename?', default='X'))
        answers.append(run.ask('ok', 'confirm', 'Stimmt das?'))
        run.step('paket', 'done')
        run.step('aktivieren', 'done')
        run.done(True, 'Paket angelegt', 'neu-1')

    async def check(app, pilot, screen, run):
        await until(pilot, lambda: isinstance(app.screen, InfoScreen))
        states = {s.key: s.state for s in screen.steps}
        assert states['anfrage'] == 'fertig' and states['kamera'] == 'läuft' and states['paket'] == 'wartet'
        assert 'Anzeige gefunden' in '\n'.join(s.text for s in screen.query_one('#kal-log').lines)
        assert 'Welches Format?' in str(app.screen.lines)
        await pilot.click('#choice-1')
        await until(pilot, lambda: isinstance(app.screen, AskScreen))
        assert json.loads((run.answers_dir / 'format.json').read_text()) == {'value': 'b'}
        await pilot.pause(0.3)
        app.screen.query_one('#ask-input').value = 'Neu 1'
        await pilot.click('#ok')
        await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
        await pilot.pause(0.3)
        await pilot.click('#ok')
        await until(pilot, lambda: screen.finished)
        assert answers == ['b', 'Neu 1', True]
        result = text_of(screen.query_one('#kal-result'))
        assert 'vorläufig angelegt und aktiv' in result and 'neu-1' in result and '/live' in result
        assert 'Paket angelegt' in result

    drive(tmp_path, monkeypatch, script, check)


def test_cancel_writes_cancel_file(tmp_path, monkeypatch):
    def script(run):
        run.step('kamera', 'running')
        while not run.cancelled():
            time.sleep(0.02)
        run.done(False, 'abgebrochen')

    async def check(app, pilot, screen, run):
        await until(pilot, lambda: any(s.state == 'läuft' for s in screen.steps))
        await pilot.press('escape')
        await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
        assert not run.cancelled()
        await pilot.click('#ok')
        await until(pilot, lambda: run.cancelled())
        await until(pilot, lambda: screen.finished)
        assert screen.result.cancelled and not screen.result.ok
        assert 'abgebrochen' in text_of(screen.query_one('#kal-title'))

    drive(tmp_path, monkeypatch, script, check)


def test_process_end_without_done_points_to_log(tmp_path, monkeypatch):
    def script(run):
        run.step('anfrage', 'running')
        run.error('Kamera belegt', 'kamera')

    async def check(app, pilot, screen, run):
        await until(pilot, lambda: screen.finished)
        result = text_of(screen.query_one('#kal-result'))
        assert 'ohne Ergebnis' in result and 'onboard.log' in result
        assert {s.key: s.state for s in screen.steps}['kamera'] == 'fehlgeschlagen'
        assert 'Kamera belegt' in '\n'.join(s.text for s in screen.query_one('#kal-log').lines)

    drive(tmp_path, monkeypatch, script, check)


@pytest.mark.parametrize('size', [(80, 24), (100, 30)])
def test_wizard_buttons_visible_in_small_terminal(client, size):
    # Kleine Terminals: Formular scrollt, Abbrechen/Weiter bleiben sichtbar.
    async def main():
        app = admin_fakes.make_app('idle')
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.3)
            screen = SensorWizardScreen(GOOD, [])
            app.push_screen(screen)
            await pilot.pause(0.3)
            width, height = size
            for button in ('#wiz-ok', '#wiz-cancel'):
                region = screen.query_one(button).region
                assert region.height > 0 and region.y >= 0 and region.bottom <= height, (button, region)
                assert region.right <= width
    asyncio.run(main())
