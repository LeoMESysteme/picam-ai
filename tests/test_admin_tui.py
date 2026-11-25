"""picam-Konsole headless (Textual run_test): Tabs, Sperren, Dialoge, Popups, Größen, Startbild."""

import asyncio
import time

import admin_fakes
from textual.widgets import Button, Input, RichLog

from dispread.admin import probes
from dispread.admin.instance import Instance
from dispread.admin.service import LogLine
from dispread.admin.tui import ConfirmScreen, InfoScreen, PicamApp

F = probes.Fact


def dev(**extra):
    values = dict(kind='dev', unit='dispread-werkbank-bruecke', scope='user', argv=['/py', '-m', 'x'],
                  workdir='/r')
    values.update(extra)
    return Instance(**values)


def drive(test, *, size=(100, 30), state='idle', instance=None, runner=None, journal=None, collect=None,
          intro=False, animations=None, popups=False, socket=None):
    async def main():
        app = PicamApp(instance or dev(), collect=collect or admin_fakes.collector(state),
                       journal_source=journal or admin_fakes.journal, service_runner=runner, auto_refresh=False,
                       intro=intro, socket_request=socket or admin_fakes.FakeSocket(),
                       metrics_source=admin_fakes.metrics, storage_source=admin_fakes.storage,
                       network_source=admin_fakes.network, popups=popups)
        if animations is not None:
            app.animation_level = animations
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.3)
            await test(app, pilot)
    asyncio.run(main())


async def wait_gone(app, pilot, selector='#intro', limit_s=3.0):
    """Unter paralleler Testlast braucht das Startbild länger; bis zu ``limit_s`` warten."""
    for _ in range(int(limit_s / 0.1)):
        if not app.query(selector):
            return
        await pilot.pause(0.1)


def text_of(widget) -> str:
    from rich.console import Console

    content = getattr(widget, '_content', None) or getattr(widget, 'renderable', None) or widget.render()
    console = Console(width=200, record=True, file=open('/dev/null', 'w'))
    console.print(content)
    return console.export_text()


# ------------------------------------------------------------ Tabs

def test_starts_on_dashboard_and_number_keys_switch_tabs():
    async def check(app, pilot):
        assert app.current == 'dashboard'
        for key, tab in (('3', 'dienst'), ('4', 'kamera'), ('l', 'protokoll'), ('c', 'einstellungen'),
                         ('1', 'dashboard')):
            if isinstance(app.focused, Input):
                app.set_focus(None)
            await pilot.press(key)
            await pilot.pause(0.1)
            assert app.current == tab, key
    drive(check)


def test_tab_key_cycles_tabs_and_escape_returns_to_dashboard():
    async def check(app, pilot):
        await pilot.press('tab')
        await pilot.pause(0.1)
        assert app.current == 'lauf'
        await pilot.press('shift+tab', 'shift+tab')
        await pilot.pause(0.1)
        assert app.current == 'einstellungen'
        await pilot.press('escape')
        await pilot.pause(0.1)
        assert app.current == 'dashboard'
    drive(check)


def test_arrow_keys_move_between_controls_inside_the_tab():
    async def check(app, pilot):
        await pilot.press('3')
        await pilot.pause(0.2)
        first = app.focused
        assert first is not None and app.view() in first.ancestors
        await pilot.press('right')
        await pilot.pause(0.1)
        assert app.focused is not first and app.current == 'dienst'
        await pilot.press('left')
        await pilot.pause(0.1)
        assert app.focused is first
    drive(check)


def test_info_key_explains_current_tab():
    async def check(app, pilot):
        await pilot.press('6', 'i')
        await pilot.pause(0.2)
        assert isinstance(app.screen, InfoScreen)
        await pilot.press('escape')
        await pilot.pause(0.1)
        assert not isinstance(app.screen, InfoScreen)
    drive(check)


def test_footer_shows_tab_actions():
    async def check(app, pilot):
        # Tabs mit eigener Aktionsleiste: Tasten stehen an den Knöpfen, die Tastenzeile nennt nur
        # die allgemeinen Tasten; nur das Protokoll (ganze Höhe für Meldungen) nennt seine dort
        footer = text_of(app.query_one('#footer'))
        assert 'Hilfe' in footer and 'Neu starten' not in footer
        assert 'Neu starten' in str(app.view().query_one('#act-r').label)
        await pilot.press('3')
        await pilot.pause(0.2)
        footer = text_of(app.query_one('#footer'))
        assert 'Neu starten' not in footer and 'Neu starten' in str(app.view().query_one('#act-r').label)
        await pilot.press('l')
        await pilot.pause(0.2)
        footer = text_of(app.query_one('#footer'))
        assert 'mitlaufen' in footer and 'Hilfe' in footer
    drive(check, size=(140, 30))


# ------------------------------------------------------------ Dienstaktionen

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


def test_running_measurement_blocks_service_actions():
    calls = []

    async def check(app, pilot):
        assert 'gesperrt' in text_of(app.query_one('#status'))
        await pilot.press('r')
        await pilot.pause(0.2)
        assert not isinstance(app.screen, ConfirmScreen)  # gesperrte Aktion öffnet keinen Dialog
        assert 'gesperrt' in text_of(app.query_one('#status')) or 'erst in der Werkbank' in text_of(
            app.query_one('#status'))
    drive(check, state='run', runner=lambda c: calls.append(c) or 0)
    assert calls == []


def test_restart_before_first_status_is_blocked():
    def failing(instance, include_setup=True, **_):
        raise OSError('noch kein Status')

    async def check(app, pilot):
        assert app.snapshot is None
        assert app.blocker == 'Laufstatus noch nicht geprüft'
        await pilot.press('r')
        await pilot.pause(0.2)
        assert not isinstance(app.screen, ConfirmScreen)
    drive(check, collect=failing)


def test_camera_restart_goes_through_confirmation_and_socket():
    socket = admin_fakes.FakeSocket()

    async def check(app, pilot):
        await pilot.press('k')
        await pilot.pause(0.2)
        assert isinstance(app.screen, ConfirmScreen) and app.focused.id == 'cancel'
        await pilot.press('right', 'enter')
        for _ in range(20):
            await pilot.pause(0.1)
            if 'live.camera.restart' in socket.calls:
                break
    drive(check, socket=socket)
    assert 'live.camera.restart' in socket.calls


def test_dialog_text_with_brackets_renders():
    async def check(app, pilot):
        app.show_info('Test', ['Pfad [nicht] gesetzt, Markup [bold]x[/] bleibt Text'])
        await pilot.pause(0.2)
        assert isinstance(app.screen, InfoScreen)
    drive(check)


# ------------------------------------------------------------ Fehler-Popups

def test_new_failure_opens_popup_once():
    state = {'value': 'idle'}

    async def check(app, pilot):
        state['value'] = 'down'
        app.action_refresh()
        await pilot.pause(0.4)
        assert isinstance(app.screen, InfoScreen)
        await pilot.press('escape')
        await pilot.pause(0.1)
        app.action_refresh()
        await pilot.pause(0.4)
        assert not isinstance(app.screen, InfoScreen)  # derselbe Fehler meldet sich nicht erneut

    def collect(instance, include_setup=True, **_):
        return admin_fakes.collector(state['value'])(instance, include_setup)
    drive(check, collect=collect, popups=True)


def test_popup_choice_opens_protokoll():
    async def check(app, pilot):
        await pilot.pause(0.3)
        assert isinstance(app.screen, InfoScreen)
        await pilot.press('enter')  # erste Wahl: Protokoll ansehen
        await pilot.pause(0.2)
        assert app.current == 'protokoll'
    drive(check, state='down', popups=True)


def test_status_arriving_while_dialog_is_open_does_not_crash():
    """Regression: die Prüfung fragte den Dialog statt der Konsole ab (NoMatches)."""
    def slow(instance, include_setup=True, **_):
        time.sleep(0.6)
        return admin_fakes.collector()(instance)

    async def check(app, pilot):
        await pilot.press('question_mark')
        await pilot.pause(0.9)
        assert app.snapshot is not None
        await pilot.press('escape')
    drive(check, collect=slow)


# ------------------------------------------------------------ Größen

def test_narrow_terminal_stacks_dashboard():
    async def check(app, pilot):
        assert app.screen.has_class('stacked')
    drive(check, size=(60, 20))


def test_too_small_terminal_shows_message():
    async def check(app, pilot):
        assert app.screen.has_class('too-small')
    drive(check, size=(40, 12))


def test_tall_terminal_shows_recent_messages_on_dashboard():
    async def check(app, pilot):
        assert app.screen.has_class('tall')
        assert app.query_one('#tail-log', RichLog).lines
    drive(check, size=(120, 40))


# ------------------------------------------------------------ Protokoll, Einstellungen

def test_log_view_and_problem_filter():
    lines = [LogLine('10:00:00', 'info', 'Kamerastart'), LogLine('10:00:01', 'fehler', 'Rahmen verdeckt'),
             LogLine('10:00:02', 'warnung', 'Brücke getrennt')]

    async def check(app, pilot):
        await pilot.press('l')
        await pilot.pause(0.3)
        log = app.query_one('#log', RichLog)
        assert app.current == 'protokoll' and len(log.lines) >= 3
        await pilot.press('e')
        await pilot.pause(0.2)
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
        await pilot.press('enter')  # Navigationszustand -> Bearbeiten
        port.value = '8443'
        await pilot.press('enter')
        await pilot.pause(0.3)
        assert isinstance(app.screen, ConfirmScreen)
        assert 'Risiko' in ' '.join(str(s.render()) for s in app.screen.query('.dialog-line'))
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
        await pilot.press('enter', 'end', 'q', '3')
        await pilot.pause(0.1)
        assert app.is_running and app.query_one('#cfg-bridge_name', Input).value == 'aq3'
        assert app.current == 'einstellungen'
    drive(check, instance=instance)


def test_settings_show_login_account_and_paths():
    async def check(app, pilot):
        await pilot.press('c')
        await pilot.pause(0.2)
        text = text_of(app.query_one('#cfg-paths'))
        assert 'Linux-Passwort' in text and 'journald' in text
    drive(check, instance=admin_fakes.INSTANCE)


def test_uninstall_blocked_for_dev_instance():
    async def check(app, pilot):
        await pilot.press('c')
        await pilot.pause(0.2)
        button = app.query_one('#act-x', Button)
        assert button.disabled
    drive(check)


# ------------------------------------------------------------ Startbild

def test_intro_key_skips_without_triggering_an_action(monkeypatch):
    from dispread.admin import intro
    monkeypatch.setattr(intro.Intro, 'MIN_S', 30)
    monkeypatch.setattr(intro.Intro, 'MAX_S', 30)

    async def check(app, pilot):
        assert app.query('#intro')
        await pilot.press('s')
        await pilot.pause(0.6)
        assert not app.query('#intro')
        assert not isinstance(app.screen, ConfirmScreen)
    drive(check, intro=True)


def test_intro_finishes_by_itself_once_status_is_known(monkeypatch):
    from dispread.admin import intro
    monkeypatch.setattr(intro.Intro, 'MIN_S', 0.2)
    monkeypatch.setattr(intro.Intro, 'HOLD_S', 0.1)

    async def check(app, pilot):
        widget = app.query_one('#intro')
        assert any(name == 'Hinweise' and value.endswith('offen') for _, _, name, value in widget._lines)
        await wait_gone(app, pilot)
        assert not app.query('#intro')
    drive(check, intro=True)


def test_intro_static_without_animations(monkeypatch):
    from dispread.admin import intro
    monkeypatch.setattr(intro.Intro, 'STATIC_MIN_S', 0.1)

    async def check(app, pilot):
        await wait_gone(app, pilot)
        assert not app.query('#intro')
    drive(check, intro=True, animations='none')


def test_intro_skipped_in_too_small_terminal():
    async def check(app, pilot):
        await pilot.pause(0.3)
        assert not app.query('#intro')
        assert app.screen.has_class('too-small')
    drive(check, size=(40, 12), intro=True)


def test_log_lines_arriving_while_tab_hidden_use_full_width():
    """Regression: RichLog brach bei verborgenem Tab auf 20 Zeichen um (Meldungen schmal am Rand)."""
    async def check(app, pilot):
        await pilot.press('l')
        await pilot.pause(0.2)
        await pilot.press('1')
        await pilot.pause(0.2)
        app._add_logs([LogLine('23:00:01', 'info', 'Kurze Meldung bei verborgenem Tab')])
        await pilot.pause(0.2)
        await pilot.press('l')
        await pilot.pause(0.4)
        texts = [str(strip.text).rstrip() for strip in app.query_one('#log').lines]
        assert '23:00:01    Kurze Meldung bei verborgenem Tab' in texts
    drive(check)


def test_bridge_not_connected_is_never_green():
    from dispread.admin.ui import TONE

    async def check(app, pilot):
        await pilot.press('5')
        await pilot.pause(0.3)
        link = dict((row[0], row[1]) for row in app.view()._bridge_rows())['Verbindung']
        assert 'nicht verbunden' in link.plain
        assert TONE[probes.OK] not in str(link.spans[0].style)
    drive(check, state='idle')


def test_digit_and_info_keys_work_while_edit_input_only_navigates():
    async def check(app, pilot):
        await pilot.press('c')
        await pilot.pause(0.3)
        field = app.query_one('#cfg-port', Input)
        assert app.focused is field and not field.editing and not app.typing()
        await pilot.press('3')                      # Navigationszustand: Ziffer wechselt den Tab
        await pilot.pause(0.3)
        assert app.current == 'dienst'
        await pilot.press('c', 'enter')             # Bearbeiten: Ziffer wird getippt, kein Tabwechsel
        await pilot.pause(0.2)
        assert app.typing()
        await pilot.press('3')
        await pilot.pause(0.2)
        assert app.current == 'einstellungen'
        await pilot.press('escape')
    drive(check, instance=admin_fakes.INSTANCE)


def test_down_moves_between_focusable_elements_in_tab_body():
    async def check(app, pilot):
        await pilot.press('c')
        await pilot.pause(0.3)
        first = app.focused
        await pilot.press('down')
        await pilot.pause(0.2)
        assert app.focused is not first and app.focused is not None
        await pilot.press('up')
        await pilot.pause(0.2)
        assert app.focused is first
    drive(check, instance=admin_fakes.INSTANCE)


def test_log_lines_during_shutdown_are_dropped_silently():
    """raspi01 25.11.: Beim Beenden kamen Protokollzeilen, als die Tabs schon abgebaut waren
    (NoMatches im Hintergrundfaden, danach „Fatal Python error“). Jetzt still verworfen."""
    async def test(app, pilot):
        main = app.main_screen
        for view_id in ('dashboard', 'protokoll'):
            await main.query_one(f'#{view_id}').remove()
        app._add_logs([LogLine('23:59:59', 'info', 'kommt beim Beenden an')])   # wirft nicht
        app._stop_log()
        app._add_logs([LogLine('23:59:59', 'info', 'nach dem Stopp')])
        assert all(line.text != 'nach dem Stopp' for line in app.log_lines)
    drive(test)


def test_log_reader_thread_never_raises_on_shutdown(monkeypatch):
    async def test(app, pilot):
        def boom():
            raise LookupError('beliebiger Fehler beim Abbau')
        monkeypatch.setattr(app, '_read_journal', boom)
        app._log_reader()                         # endet still, ohne Ausgabe auf stderr
    drive(test)
