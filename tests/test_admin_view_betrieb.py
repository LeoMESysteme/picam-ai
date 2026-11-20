"""Tabs Dienst, Kamera, Ausgabe, Zertifikat der picam-Konsole (Headless)."""

import asyncio
import functools
import io

import admin_fakes
import pytest
from rich.console import Console
from textual.widgets import Button, Static

from dispread.admin.tui import ConfirmScreen, InfoScreen

SIZES = [(80, 24), (60, 20), (100, 30)]


def sync(coroutine_function):
    @functools.wraps(coroutine_function)
    def wrapper(*args, **kwargs):
        asyncio.run(coroutine_function(*args, **kwargs))
    return wrapper


def text_of(app, tab_id):
    view = app.view(tab_id)
    parts = []
    for widget in view.query(Static):
        if not widget.display:
            continue
        content = getattr(widget.render(), '_renderable', None) or widget.render()
        console = Console(width=200, record=True, file=io.StringIO())
        console.print(content)
        parts.append(console.export_text())
    return '\n'.join(parts)


async def open_tab(pilot, key):
    await pilot.press(key)
    await pilot.pause(0.4)


@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('key', ['3', '4', '5', '6'])
@pytest.mark.parametrize('state', ['idle', 'run', 'down'])
@sync
async def test_tabs_render_in_all_sizes(key, size, state):
    app = admin_fakes.make_app(state)
    async with app.run_test(size=size) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, key)
        assert app.current == {'3': 'dienst', '4': 'kamera', '5': 'ausgabe', '6': 'zertifikat'}[key]


@sync
async def test_dienst_content_and_info():
    app = admin_fakes.make_app('idle')
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '3')
        text = text_of(app, 'dienst')
        for expected in ('picam-werkbank.service', 'Systemdienst', 'ja', '1394956', '1.1.0', '1.0.0',
                         '/opt/picam/releases/1.1.0'):
            assert expected in text
        await pilot.press('i')
        await pilot.pause(0.2)
        assert isinstance(app.screen, InfoScreen)


@sync
async def test_dienst_actions_blocked_during_run():
    app = admin_fakes.make_app('run')
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '3')
        actions = {a.key: a for a in app.view().actions()}
        assert actions['s'].blocked and actions['r'].blocked
        assert 'gesperrt' in text_of(app, 'dienst')
        assert app.view().query_one('#act-s', Button).disabled
        await pilot.press('s')
        await pilot.pause(0.2)
        assert not isinstance(app.screen, ConfirmScreen)


@sync
async def test_dienst_stop_confirm_starts_on_cancel():
    app = admin_fakes.make_app('idle')
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '3')
        await pilot.press('s')
        await pilot.pause(0.4)
        assert isinstance(app.screen, ConfirmScreen)
        assert app.screen.focused.id == 'cancel'


@sync
async def test_kamera_content():
    app = admin_fakes.make_app('idle')
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '4')
        text = text_of(app, 'kamera')
        for expected in ('Logitech StreamCam', '046d:0893', 'USB 3', '/dev/video0', '1920×1080 YUYV',
                         '412.000', 'Serverstart', 'Kalibrierung'):
            assert expected in text


@sync
async def test_kamera_restart_blocked_during_run_and_confirm_calls_socket():
    socket = admin_fakes.FakeSocket()
    app = admin_fakes.make_app('run', socket=socket)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '4')
        assert {a.key: a for a in app.view().actions()}['k'].blocked
        await pilot.press('k')
        await pilot.pause(0.2)
        assert 'live.camera.restart' not in socket.calls
    socket = admin_fakes.FakeSocket()
    app = admin_fakes.make_app('idle', socket=socket)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '4')
        await pilot.press('k')
        await pilot.pause(0.4)
        assert isinstance(app.screen, ConfirmScreen)
        assert socket.calls.count('live.camera.restart') == 0
        await pilot.click('#ok')
        await pilot.pause(0.6)
        assert 'live.camera.restart' in socket.calls


@sync
async def test_ausgabe_shows_active_path_in_run():
    app = admin_fakes.make_app('run')
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '5')
        view = app.view()
        assert view.active_index() == 3 and view.selected_index() == 3
        text = text_of(app, 'ausgabe')
        assert 'Weg im Lauf' in text and 'Netzwerk (Brücke)' in text and 'Lauf aktiv' in text
        assert 'sending' in text
        # „im Lauf“ steht an genau dem Weg, der im Lauf benutzt wird
        selector = view.query_one('#paths')
        assert [mark is not None for _, _, mark in selector.items] == [False, False, False, True]


@sync
async def test_ausgabe_off_in_run_and_switching():
    app = admin_fakes.make_app('run')
    app._collect = lambda instance, **_: _off_snapshot(instance)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '5')
        assert app.view().active_index() == 0
        assert 'Werte werden nur aufgezeichnet' in text_of(app, 'ausgabe')


def _off_snapshot(instance):
    import time

    from dispread.admin import probes
    live = admin_fakes.live('run')
    live['output'] = {'transport': 'off', 'state': 'off'}
    return probes.Snapshot(instance, admin_fakes.facts('run'), live, time.time())


@sync
async def test_ausgabe_paths_and_bridge_uart_actions():
    socket = admin_fakes.FakeSocket()
    app = admin_fakes.make_app('idle', socket=socket)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '5')
        view = app.view()
        assert view.active_index() is None
        text = text_of(app, 'ausgabe')
        assert 'kein Lauf' in text and '/dev/ttyAMA0' in text and '115200' in text
        assert 'p' not in {a.key for a in view.actions()}
        # Die Wege sind nur eine Auswahl der Ansicht: kein eigener „Weg wechseln“ mehr
        assert 'w' not in {a.key for a in view.actions()}
        assert app.focused is view.query_one('#paths')
        await pilot.press('right')
        await pilot.pause(0.3)
        assert view.selected_index() == 2
        assert '460800' in text_of(app, 'ausgabe')
        assert {a.key: a for a in view.actions()}['p'].blocked is None
        await pilot.press('p')
        await pilot.pause(0.4)
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.click('#ok')
        await pilot.pause(0.6)
        assert 'bridge.prepare-uart' in socket.calls


@sync
async def test_zertifikat_bridge_identity_cannot_be_renewed():
    app = admin_fakes.make_app('idle')
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '6')
        view = app.view()
        text = text_of(app, 'zertifikat')
        assert 'urn:picam:pi:565e3468' in text and '06.11.2027' in text and 'nicht vorgesehen' in text
        assert 'Brückenidentität' in view.renew_blocker()
        assert view.query_one('#act-n', Button).disabled


@sync
async def test_zertifikat_renew_confirm_for_plain_certificate():
    app = admin_fakes.make_app('idle')
    ran = []
    app.run_in_terminal = lambda command, title: ran.append(command) or 0
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        fact = app.snapshot.facts['zertifikat']
        fact.detail = [(k, v) for k, v in fact.detail if k != 'Identität']
        app.view('zertifikat').update_view()
        await open_tab(pilot, '6')
        assert app.view().renew_blocker() is None
        await pilot.press('n')
        await pilot.pause(0.4)
        assert isinstance(app.screen, ConfirmScreen)
        assert app.screen.focused.id == 'cancel'
        assert not ran
        await pilot.click('#ok')
        await pilot.pause(0.5)
        assert ran and 'renew-tls' in ran[0] and '/var/lib/picam/workbench/tls' in ran[0]


@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('key', ['3', '4', '5', '6'])
@sync
async def test_cards_render_and_actionbar_stays_visible(size, key):
    app = admin_fakes.make_app('run')
    async with app.run_test(size=size) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, key)
        text = text_of(app, app.current)
        expected = {'3': 'WERKBANK-DIENST', '4': '/dev/video0', '5': 'Netzwerk', '6': 'ZERTIFIKAT'}[key]
        assert expected in text
        assert app.view().query_one('#buttons').region.bottom <= size[1] - 2  # Leiste bleibt sichtbar


@sync
async def test_ausgabe_click_on_path_chip_selects_it():
    app = admin_fakes.make_app('idle')
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '5')
        view = app.view()
        selector = view.query_one('#paths')
        line, start, _ = selector._spans[0]
        await pilot.click('#paths', offset=(start + 1, line))
        await pilot.pause(0.3)
        assert view.selected_index() == 0


@sync
async def test_kamera_info_carries_full_hints():
    app = admin_fakes.make_app('idle')
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.4)
        await open_tab(pilot, '4')
        assert any('scripts/timing-calibration.py' in line for line in app.view().INFO)
