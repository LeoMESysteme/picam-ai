"""Deinstallationsvorschau der Konsole (``UninstallScreen``) und der Übergang ins Terminal."""

from __future__ import annotations

import asyncio
import dataclasses
import sys
from pathlib import Path

import admin_fakes
import pytest

from dispread.admin import tui, uninstall
from dispread.admin.views.uninstall_screen import UninstallScreen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packaging'))

from picam_installer import uninstall as installer  # noqa: E402
from test_installer_uninstall import layout  # noqa: E402


def text_of(widget) -> str:
    from rich.console import Console

    content = getattr(widget, '_content', None) or getattr(widget, 'renderable', None) or widget.render()
    console = Console(width=200, record=True, file=open('/dev/null', 'w'))
    console.print(content)
    return console.export_text()


def screen_text(screen) -> str:
    return '\n'.join(text_of(screen.query_one(sel)) for sel in ('#un-title', '#un-remove', '#un-keep', '#un-notes'))


@pytest.fixture
def paths(tmp_path, monkeypatch):
    found = layout(tmp_path / 'img')
    monkeypatch.setattr(uninstall, 'plan_uninstall', lambda instance, **kw: installer.plan_uninstall(**found, **kw))
    monkeypatch.setattr(uninstall, 'describe', lambda instance, plan: installer.describe(plan))
    return found


def instance_with_script(tmp_path):
    root = tmp_path / 'opt/releases/1.1.0'
    root.mkdir(parents=True)
    (root / 'install.sh').write_text('#!/bin/sh\n')
    return dataclasses.replace(admin_fakes.INSTANCE, root=str(root), data=str(tmp_path / 'var/workbench'))


def drive(test, instance=admin_fakes.INSTANCE, size=(100, 30)):
    async def main():
        app = admin_fakes.make_app('idle', instance=instance)
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.3)
            await test(app, pilot)
        return app
    return asyncio.run(main())


def test_preview_lists_remove_and_keep_with_paths(paths):
    async def check(app, pilot):
        screen = UninstallScreen(app.instance)
        app.push_screen(screen)
        await pilot.pause(0.3)
        text = screen_text(screen)
        for word in ('WIRD ENTFERNT', 'Dienst', 'Programmversionen', 'Befehl picam', 'BLEIBT ERHALTEN', 'Daten',
                     'Einstellungen', str(paths['data']), str(paths['config'].parent), 'sudo', '--purge-data',
                     'deinstallieren'):
            assert word in text, word
        assert screen.focused.id == 'un-cancel'          # Fokus nie auf der gefährlichen Aktion
        assert screen.query_one('#un-ok').variant == 'error' and not screen.query_one('#un-ok').disabled
    drive(check)


def test_cancel_keeps_console_open_and_changes_nothing(paths):
    results = []

    async def check(app, pilot):
        app.push_screen(UninstallScreen(app.instance), callback=results.append)
        await pilot.pause(0.3)
        await pilot.press('escape')
        await pilot.pause(0.3)
        assert results == [False] and not app._exit and app.terminal_job is None
        app.push_screen(UninstallScreen(app.instance), callback=results.append)
        await pilot.pause(0.3)
        await pilot.click('#un-cancel')
        await pilot.pause(0.3)
        assert results == [False, False] and app.terminal_job is None
    drive(check)


def test_plan_error_blocks_confirmation(monkeypatch):
    def broken(instance, **kw):
        raise ValueError('Datenpfad /x passt nicht zum Layout des Installers.')

    monkeypatch.setattr(uninstall, 'plan_uninstall', broken)

    async def check(app, pilot):
        screen = UninstallScreen(app.instance)
        app.push_screen(screen)
        await pilot.pause(0.3)
        text = screen_text(screen)
        assert 'nicht möglich' in text.lower() and 'passt nicht zum Layout' in text
        assert screen.query_one('#un-ok').disabled
    drive(check)


def test_confirm_exits_console_with_terminal_job(paths, tmp_path, monkeypatch):
    instance = instance_with_script(tmp_path)
    monkeypatch.setattr(uninstall, 'installer_argv', lambda inst, **kw: ['--uninstall', '--mode', 'system'])
    monkeypatch.setattr('os.geteuid', lambda: 0)
    seen = {}

    async def check(app, pilot):
        app.start_uninstall()
        for _ in range(60):
            if isinstance(app.screen, UninstallScreen):
                break
            await pilot.pause(0.05)
        assert isinstance(app.screen, UninstallScreen)
        await pilot.pause(0.2)
        await pilot.click('#un-ok')
        await pilot.pause(0.5)
        seen['app'] = app

    app = drive(check, instance=instance)
    assert app._exit and app.return_code == 0
    command = app.terminal_job
    assert command == [str(Path(instance.root) / 'install.sh'), '--uninstall', '--mode', 'system', '--guided']


def test_run_hands_terminal_job_to_subprocess(monkeypatch):
    """Nach dem Ende der Konsole (nicht in suspend) läuft das Terminal-Kommando; vorher kein Aufruf."""
    calls = []

    class FakeApp:
        def __init__(self, *args, **kwargs):
            self.terminal_job = ['sudo', '/x/install.sh', '--uninstall', '--guided']
            self.relaunch = None
            self.instance = admin_fakes.INSTANCE

        def run(self):
            calls.append('app.run')
            return 0

    monkeypatch.setattr(tui, 'PicamApp', FakeApp)
    monkeypatch.setattr(tui.subprocess, 'call', lambda command: calls.append(command) or 130)
    assert tui.run(admin_fakes.INSTANCE, intro=False, onboarding=None) == 130
    assert calls == ['app.run', ['sudo', '/x/install.sh', '--uninstall', '--guided']]


def test_run_relaunches_with_new_picam_via_execv(monkeypatch):
    execs = []

    class FakeApp:
        def __init__(self, *args, **kwargs):
            self.terminal_job = None
            self.relaunch = ['/opt/picam/current/.venv/bin/picam', '--config', '/etc/picam/config.toml']
            self.instance = admin_fakes.INSTANCE

        def run(self):
            return 0

    monkeypatch.setattr(tui, 'PicamApp', FakeApp)
    monkeypatch.setattr(tui.os, 'execv', lambda path, argv: execs.append((path, argv)))
    tui.run(admin_fakes.INSTANCE, intro=False, onboarding=None)
    assert execs == [('/opt/picam/current/.venv/bin/picam',
                      ['/opt/picam/current/.venv/bin/picam', '--config', '/etc/picam/config.toml'])]


def test_80x24_buttons_visible(paths):
    async def check(app, pilot):
        screen = UninstallScreen(app.instance)
        app.push_screen(screen)
        await pilot.pause(0.4)
        assert screen.query_one('#un-buttons').region.bottom <= 24
    drive(check, size=(80, 24))
