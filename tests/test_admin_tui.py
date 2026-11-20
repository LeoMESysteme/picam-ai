"""picam-Konsole headless (Textual run_test): Navigation, Sperren, Dialoge, Größen."""

import asyncio
import time

from textual.widgets import Button, Input, OptionList, RichLog

from dispread.admin import probes
from dispread.admin.instance import Instance
from dispread.admin.service import LogLine
from dispread.admin.tui import ConfirmScreen, PicamApp

F = probes.Fact


def facts(state='idle'):
    data = {
        'dienst': F('dienst', 'Dienst', probes.OK, 'läuft', [('Unit', 'u')]),
        'lauf': F('lauf', 'Lauf', probes.OK, 'kein Lauf'),
        'kamera': F('kamera', 'Kamera', probes.OK, 'bereit'),
        'ausgabe': F('ausgabe', 'Ausgabe', probes.OFF, 'aus'),
        'bruecke': F('bruecke', 'Brücke', probes.OK, 'wartet'),
        'zertifikat': F('zertifikat', 'Zertifikat', probes.OK, 'bis 11/2027'),
        'speicher': F('speicher', 'Speicher', probes.WARN, '2,5 GB frei', hint='Wird knapp.',
                      command='true'),
        'vorlage': F('vorlage', 'Lesevorlage', probes.OK, 'geprüft'),
        'kalibrierung': F('kalibrierung', 'Kalibrierung', probes.FAIL, 'fehlt', hint='Messen.'),
        'uart': F('uart', 'UART', probes.OK, 'aktiv'),
        'konto': F('konto', 'Konto', probes.OK, 'labor'),
        'uhr': F('uhr', 'Uhrzeit', probes.OK, 'synchron'),
        'version': F('version', 'Version', probes.OK, '1.0.0'),
    }
    if state == 'run':
        data['lauf'] = F('lauf', 'Lauf', probes.OK, 'Lauf aktiv')
    return data


def collector(state='idle'):
    live = {'state': 'running' if state == 'run' else 'idle', 'diagnose_kopie': False}

    def collect(instance, include_setup=True, **_):
        return probes.Snapshot(instance, facts(state), live, time.time())
    return collect


def dev(**extra):
    values = dict(kind='dev', unit='dispread-werkbank-bruecke', scope='user', argv=['/py', '-m', 'x'],
                  workdir='/r')
    values.update(extra)
    return Instance(**values)


def drive(test, *, size=(100, 30), state='idle', instance=None, runner=None, journal=None):
    async def main():
        app = PicamApp(instance or dev(), collect=collector(state), journal_source=journal,
                       service_runner=runner, auto_refresh=False)
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.2)
            await test(app, pilot)
    asyncio.run(main())


def nav_text(app):
    nav = app.query_one('#nav', OptionList)
    return [str(nav.get_option_at_index(i).prompt) for i in range(nav.option_count)]


def test_overview_counts_problems_and_nav_shows_words():
    async def check(app, pilot):
        rows = nav_text(app)
        assert any('Übersicht' in r and '✗ 2' in r for r in rows)
        assert any('Speicher' in r and '2,5 GB frei' in r for r in rows)
        assert app.selected == 'uebersicht'
    drive(check)


def test_restart_dialog_starts_on_cancel_and_enter_cancels():
    calls = []

    async def check(app, pilot):
        await pilot.press('r')
        await pilot.pause(0.2)
        assert isinstance(app.screen, ConfirmScreen)
        assert app.focused.id == 'cancel'
        await pilot.press('enter')
        await pilot.pause(0.2)
        assert not isinstance(app.screen, ConfirmScreen)
    drive(check, runner=lambda c: calls.append(c) or 0)
    assert calls == []


def test_confirmed_restart_runs_plan_without_sudo_for_dev():
    calls = []

    async def check(app, pilot):
        await pilot.press('r')
        await pilot.pause(0.2)
        await pilot.press('right', 'enter')
        for _ in range(30):
            await pilot.pause(0.1)
            if app._busy is None and calls:
                break
    drive(check, runner=lambda c: calls.append(c) or 0)
    assert calls[0] == ['systemctl', '--user', 'stop', 'dispread-werkbank-bruecke']
    assert calls[1][0] == 'systemd-run' and calls[1][-3:] == ['/py', '-m', 'x']


def test_running_measurement_disables_service_actions():
    calls = []

    async def check(app, pilot):
        footer = str(app.query_one('#footer').render())
        assert 'neu starten' not in footer
        assert 'gesperrt' in str(app.query_one('#status').render())
        await pilot.press('r')
        await pilot.pause(0.2)
        assert isinstance(app.screen, ConfirmScreen)
        assert app.screen.query_one('#ok', Button).disabled
    drive(check, state='run', runner=lambda c: calls.append(c) or 0)
    assert calls == []


def test_narrow_terminal_stacks_and_escape_returns():
    async def check(app, pilot):
        assert app.screen.has_class('stacked')
        await pilot.press('down', 'down', 'down', 'enter')
        await pilot.pause(0.1)
        assert app.screen.has_class('open') and app.selected == 'kamera'  # Kopfzeilen werden übersprungen
        await pilot.press('escape')
        await pilot.pause(0.1)
        assert not app.screen.has_class('open')
    drive(check, size=(60, 20))


def test_too_small_terminal_shows_message():
    async def check(app, pilot):
        assert app.screen.has_class('too-small')
    drive(check, size=(40, 12))


def test_log_view_and_problem_filter():
    lines = [LogLine('10:00:00', 'info', 'Kamerastart'), LogLine('10:00:01', 'fehler', 'Rahmen verdeckt'),
             LogLine('10:00:02', 'warnung', 'Brücke getrennt')]

    async def check(app, pilot):
        await pilot.press('l')
        await pilot.pause(0.3)
        log = app.query_one('#log', RichLog)
        assert app.selected == 'protokoll' and len(log.lines) >= 3
        await pilot.press('e')
        await pilot.pause(0.2)
        assert app._errors_only
        text = '\n'.join(str(line.text) for line in log.lines)
        assert 'Kamerastart' not in text and 'Rahmen verdeckt' in text
    drive(check, journal=lambda: lines)


def test_config_change_writes_after_confirmation(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('[workbench]\npam_user = "labor"\nhost = "192.168.1.9"\nport = 8080\n'
                      'bridge_endpoint = ["https://192.168.1.9:8080/bridge/v2"]\n')
    instance = Instance(kind='portable', unit=None, scope='user', config=str(config), host='192.168.1.9',
                        port=8080, pam_user='labor')

    async def check(app, pilot):
        await pilot.press('c')
        await pilot.pause(0.3)
        port = app.query_one('#cfg-port', Input)
        assert app.focused is port
        port.value = '8443'
        app.query_one('#config-check', Button).press()
        await pilot.pause(0.3)
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press('right', 'enter')
        await pilot.pause(0.3)
    drive(check, instance=instance)
    text = config.read_text()
    assert 'port = 8443' in text and 'https://192.168.1.9:8443/bridge/v2' in text


def test_q_in_input_is_text_not_quit(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('[workbench]\nbridge_name = "a"\n')
    instance = Instance(kind='portable', unit=None, scope='user', config=str(config), bridge_name='a')

    async def check(app, pilot):
        await pilot.press('c')
        await pilot.pause(0.2)
        app.query_one('#cfg-bridge_name', Input).focus()
        await pilot.press('end', 'q')
        await pilot.pause(0.1)
        assert app.is_running and app.query_one('#cfg-bridge_name', Input).value == 'aq'
    drive(check, instance=instance)
