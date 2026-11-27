"""Eingabefeld mit Navigations- und Bearbeitungszustand (Einstellungen)."""

from test_admin_tui import ConfirmScreen, drive, text_of
from textual.color import Color
from textual.widgets import Button, Checkbox

from dispread.admin.edit_input import EditInput
from dispread.admin.instance import Instance


def settings(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('[workbench]\npam_user = "labor"\nhost = "192.168.1.9"\nport = 8080\nbridge_name = "aq"\n'
                      'bridge_endpoint = ["https://192.168.1.9:8080/bridge/v2"]\n')
    return Instance(kind='portable', unit=None, scope='user', config=str(config), host='192.168.1.9',
                    port=8080, pam_user='labor', bridge_name='aq')


async def open_tab(app, pilot):
    await pilot.press('c')
    await pilot.pause(0.3)
    return app.query_one('#cfg-port', EditInput), app.query_one('#cfg-bridge_name', EditInput)


def test_first_focus_is_port_in_navigation_state(tmp_path):
    async def check(app, pilot):
        port, _ = await open_tab(app, pilot)
        assert app.focused is port and not port.editing
        await pilot.press('1', 'x')
        assert port.value == '8080'
    drive(check, instance=settings(tmp_path))


def test_arrows_move_between_fields_checkbox_and_buttons(tmp_path):
    async def check(app, pilot):
        port, name = await open_tab(app, pilot)
        await pilot.press('down')
        assert app.focused is name
        await pilot.press('down')
        assert isinstance(app.focused, Checkbox)
        await pilot.press('down')
        assert app.focused.id == 'cfg-feature'
        await pilot.press('down')
        assert isinstance(app.focused, Button)
        await pilot.press('up', 'up', 'up', 'up')
        assert app.focused is port
        assert port.value == '8080' and name.value == 'aq'
    drive(check, instance=settings(tmp_path))


def test_checkbox_toggles_with_enter_and_space(tmp_path):
    async def check(app, pilot):
        await open_tab(app, pilot)
        await pilot.press('down', 'down')
        box = app.focused
        before = box.value
        await pilot.press('enter')
        assert box.value is (not before)
        await pilot.press('space')
        assert box.value is before
    drive(check, instance=settings(tmp_path))


def test_enter_edits_arrows_move_cursor_and_enter_submits(tmp_path):
    async def check(app, pilot):
        port, _ = await open_tab(app, pilot)
        await pilot.press('enter')
        assert port.editing
        await pilot.press('left', 'left', 'x', 'up', 'down')
        assert app.focused is port and port.value == '80x80'
        await pilot.press('end', 'ctrl+u', '8', '4', '4', '3')
        await pilot.press('enter')
        await pilot.pause(0.3)
        assert not port.editing
        assert isinstance(app.screen, ConfirmScreen)
    drive(check, instance=settings(tmp_path))


def test_escape_discards_and_second_escape_goes_to_dashboard(tmp_path):
    async def check(app, pilot):
        port, _ = await open_tab(app, pilot)
        await pilot.press('enter', 'end', '9')
        assert port.value == '80809'
        await pilot.press('escape')
        await pilot.pause(0.1)
        assert not port.editing and port.value == '8080'
        assert app.current == 'einstellungen' and app.focused is port
        await pilot.press('escape')
        await pilot.pause(0.2)
        assert app.current == 'dashboard'
    drive(check, instance=settings(tmp_path))


def test_mouse_click_starts_editing(tmp_path):
    async def check(app, pilot):
        _, name = await open_tab(app, pilot)
        await pilot.click('#cfg-bridge_name')
        await pilot.pause(0.1)
        assert name.editing and app.focused is name
        await pilot.press('z')
        assert sorted(name.value) == sorted('aqz')
    drive(check, instance=settings(tmp_path))


def test_edit_hint_shows_while_editing(tmp_path):
    async def check(app, pilot):
        await open_tab(app, pilot)
        await pilot.press('enter')
        await pilot.pause(0.1)
        assert 'Enter übernehmen' in text_of(app.query_one('#cfg-help'))
        await pilot.press('escape')
        await pilot.pause(0.1)
        assert 'Enter übernehmen' not in text_of(app.query_one('#cfg-help'))
    drive(check, instance=settings(tmp_path))


def _marked(app):
    """Felder, die sichtbar hervorgehoben sind: gefüllter Akzent (Navigieren) oder Feldfarbe des Fokus."""
    variables = app.get_css_variables()
    field = Color.parse(variables['picam-field'])
    return [w.id for w in app.query(EditInput) if w.styles.background != field and w.styles.background.a]


def _only_focused_marked(app):
    focused = app.focused
    marked = _marked(app)
    flagged = [w.id for w in app.query(EditInput) if w.has_focus]
    if isinstance(focused, EditInput):
        assert marked == [focused.id] and flagged == [focused.id], (marked, flagged)
    else:
        assert marked == [] and flagged == [], (marked, flagged)


def test_only_focused_element_is_highlighted_after_every_focus_change(tmp_path):
    async def check(app, pilot):
        port, name = await open_tab(app, pilot)
        _only_focused_marked(app)
        await pilot.press('down')  # Navigieren: ↓
        _only_focused_marked(app)
        await pilot.press('enter', 'down')  # Bearbeiten, ↓ bleibt im Feld
        assert app.focused is name and name.editing
        _only_focused_marked(app)
        await pilot.press('enter')  # übernehmen (Bestätigungsdialog) und zurück
        await pilot.pause(0.3)
        if isinstance(app.screen, ConfirmScreen):
            await pilot.press('escape')
            await pilot.pause(0.2)
        await pilot.press('enter', 'escape')  # Bearbeiten, Esc verwirft
        _only_focused_marked(app)
        await pilot.press('up')
        assert app.focused is port
        _only_focused_marked(app)
        await pilot.press('down', 'down')  # Kontrollkästchen
        assert isinstance(app.focused, Checkbox)
        _only_focused_marked(app)
        await pilot.press('down')  # Schalter „Experimentell“
        assert app.focused.id == 'cfg-feature'
        _only_focused_marked(app)
        await pilot.press('down')  # Knopf
        assert isinstance(app.focused, Button)
        _only_focused_marked(app)
        await pilot.click('#cfg-bridge_name')  # Mausklick: Bearbeiten
        await pilot.pause(0.1)
        _only_focused_marked(app)
        await pilot.click('#cfg-port')  # Mausklick auf anderes Feld
        await pilot.pause(0.1)
        assert name.has_focus is False
        _only_focused_marked(app)
        await pilot.press('escape')
        await pilot.press('d')  # Tab-Wechsel und zurück
        await pilot.pause(0.2)
        await pilot.press('c')
        await pilot.pause(0.3)
        _only_focused_marked(app)
    drive(check, instance=settings(tmp_path))
