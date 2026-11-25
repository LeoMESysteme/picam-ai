"""Update-Bildschirm der Konsole (``UpdateScreen``) headless: Plan, Erfolg, Rückweg, Abbruch, sudo,
Neustart der Konsole. Der Ablauf ist ein Fake mit denselben Console-Hooks wie ``update.run_update``."""

from __future__ import annotations

import asyncio
import dataclasses
import threading
import time

import admin_fakes

from dispread.admin import update
from dispread.admin.ui import ConfirmScreen
from dispread.admin.views.update_screen import UpdateScreen

USER = dataclasses.replace(admin_fakes.INSTANCE, kind='user', scope='user')


def text_of(widget) -> str:
    from rich.console import Console

    content = getattr(widget, '_content', None) or getattr(widget, 'renderable', None) or widget.render()
    console = Console(width=200, record=True, file=open('/dev/null', 'w'))
    console.print(content)
    return console.export_text()


def screen_text(screen) -> str:
    return '\n'.join(text_of(screen.query_one(sel)) for sel in
                     ('#kal-title', '#kal-alarm', '#kal-plan', '#kal-ask-head', '#kal-ask-text', '#kal-ask-error',
                      '#kal-steps', '#kal-result'))


def log_text(screen) -> str:
    return '\n'.join(strip.text for strip in screen.query_one('#kal-log').lines)


async def until(pilot, predicate, limit_s=10.0):
    for _ in range(int(limit_s / 0.05)):
        if predicate():
            return
        await pilot.pause(0.05)
    raise AssertionError('Bedingung nicht eingetreten')


def drive(test, *, instance=USER, size=(100, 30), **kwargs):
    async def main():
        app = admin_fakes.make_app('idle', instance=instance)
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.3)
            screen = UpdateScreen(instance, **kwargs)
            app.push_screen(screen)
            await pilot.pause(0.2)
            await test(app, pilot, screen)
            screen.cancel_event.set()
    asyncio.run(main())


def fake_runner(outcome='ok', *, gate: threading.Event | None = None, calls=None, rollback=None, restart_command=None):
    """Wie ``update.run_update``: Rückfrage, Schritte, Ergebnis."""
    def run(instance, source, sha256, console, deps=None, *, release_id=None, yes=False):
        if calls is not None:
            calls.append((source, release_id))
        console.last_result = None
        progress = console.progress(False)
        if not console.confirm('Update installieren?', [f'Archiv: {source}'], None, deps=deps):
            result = update.Result('cancelled', reason='Update abgebrochen.', message='Update abgebrochen.')
            console.last_result = result
            console.mark('warn', result.message)
            return result
        keys = ['umschalten', 'dienst_neustart', 'bereit'] if release_id else \
            ['pruefen', 'entpacken', 'umgebung', 'selbsttest', 'umschalten', 'dienst_neustart', 'bereit']
        for index, key in enumerate(keys):
            console.step(update.STEPS[key], key=key)
            progress(index + (key == 'bereit'), len(keys))
            console.line(f'· {key}')
            if gate is not None and key == 'entpacken':
                while not gate.is_set():
                    if deps.cancelled():
                        result = update.Result('cancelled', old_version='1.0.0', new_version='1.1.0',
                                               reason='Update abgebrochen.', message='Update abgebrochen.')
                        console.last_result = result
                        console.mark('warn', result.message)
                        return result
                    time.sleep(0.02)
            if outcome == 'rollback' and key == 'dienst_neustart':
                console.step(update.STEPS['rueckweg'], key='rueckweg')
                result = update.Result('failed', old_version='1.0.0', new_version='1.1.0', rollback_triggered=True,
                                       rollback_ok=rollback, reason='Version 1.1.0 antwortet nicht.',
                                       message='Update auf 1.1.0 fehlgeschlagen, 1.0.0 läuft wieder.')
                console.last_result = result
                console.mark('warn', result.message)
                return result
        result = update.Result('ok', old_version='1.0.0', new_version='1.1.0',
                               message='Version 1.1.0 läuft, https://x antwortet.', restart_command=restart_command)
        console.last_result = result
        console.mark('ok', result.message)
        return result
    return run


def test_plan_then_success_shows_versions_and_steps(tmp_path):
    calls = []

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        text = screen_text(screen)
        assert 'PLAN' in text and '/tmp/picam-1.1.0.tar.gz' in text and 'Dienst wird neu gestartet' in text
        assert screen.query_one('#kal-ok').display and str(screen.query_one('#kal-ok').label) == 'Installieren'
        assert calls == [('/tmp/picam-1.1.0.tar.gz', None)]
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.finished)
        text = screen_text(screen)
        assert 'aktualisiert' in text and '1.0.0 → 1.1.0' in text and 'antwortet' in text
        assert 'Release entpacken' in text and all(s.state == 'fertig' for s in screen.steps)
    drive(check, source='/tmp/picam-1.1.0.tar.gz', runner=fake_runner(calls=calls))


def test_success_offers_console_restart_with_new_picam(tmp_path):
    new = tmp_path / 'picam'
    new.write_text('#!/bin/sh\n')

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
        assert app.screen.focused.id == 'cancel'        # Fokus nie auf der Aktion
        assert str(new) in str(app.screen.c.commands)
        await pilot.click('#ok')
        await pilot.pause(0.3)
        assert app.relaunch == [str(new), '--config', USER.config]
    drive(check, source='x', runner=fake_runner(restart_command=str(new)))


def test_decline_restart_keeps_console_running(tmp_path):
    new = tmp_path / 'picam'
    new.write_text('')

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
        await pilot.click('#cancel')
        await pilot.pause(0.3)
        assert app.relaunch is None and screen.finished
    drive(check, source='x', runner=fake_runner(restart_command=str(new)))


def test_automatic_rollback_is_shown_as_warning():
    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.finished)
        text = screen_text(screen)
        assert 'zurückgerollt' in text and '1.0.0 läuft wieder' in text and 'antwortet nicht' in text
        assert 'Vorige Version wiederherstellen' in text
        assert not isinstance(app.screen, ConfirmScreen)      # kein Neustart-Angebot
    drive(check, source='x', runner=fake_runner('rollback', rollback=True))


def test_rollback_without_answer_is_failure():
    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.finished)
        assert 'Rückweg ohne Antwort' in screen_text(screen) and 'antwortet nicht' in screen_text(screen)
    drive(check, source='x', runner=fake_runner('rollback', rollback=False))


def test_rollback_mode_switches_to_previous_version():
    calls = []

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        assert 'umgeschaltet' in screen_text(screen) and 'Zurückschalten' in str(screen.query_one('#kal-ok').label)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.finished)
        assert 'zurückgeschaltet' in screen_text(screen) and calls == [(None, '1.0.0')]
    drive(check, mode='rollback', release_id='1.0.0', runner=fake_runner(calls=calls))


def test_decline_confirmation_changes_nothing():
    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.press('escape')
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'cancelled' and 'abgebrochen' in screen_text(screen)
        assert 'unverändert' in screen_text(screen)
    drive(check, source='x', runner=fake_runner())


def test_cancel_during_run_asks_then_stops_at_checkpoint():
    gate = threading.Event()

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: any(s.key == 'entpacken' and s.state == 'läuft' for s in screen.steps))
        await pilot.press('escape')
        await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
        assert app.screen.focused.id == 'cancel'
        await pilot.click('#ok')
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'cancelled' and screen.cancel_requested
        gate.set()
    drive(check, source='x', runner=fake_runner(gate=gate))


def test_sudo_password_masked_validated_never_logged(monkeypatch):
    system = admin_fakes.INSTANCE
    seen = []
    monkeypatch.setattr(update, 'sudo_needed', lambda instance: True)
    monkeypatch.setattr(update, 'sudo_cached', lambda: False)
    monkeypatch.setattr(update, 'sudo_validate',
                        lambda password: seen.append(password) or (password == 'richtig', 'Passwort falsch.'))

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.pending is not None and screen.pending['entry'] == 'password')
        field = screen.query_one('#kal-input')
        assert field.password and 'sudo' in screen_text(screen)
        field.value = 'falsch'
        await pilot.press('enter')
        await until(pilot, lambda: screen.pending is not None and screen.pending['error'])
        assert 'Passwort falsch.' in screen_text(screen)
        field = screen.query_one('#kal-input')
        field.value = 'richtig'
        await pilot.press('enter')
        await until(pilot, lambda: screen.finished)
        assert seen == ['falsch', 'richtig']
        assert 'falsch' not in log_text(screen).replace('Passwort falsch.', '') and 'richtig' not in log_text(screen)
        assert screen.query_one('#kal-input').value == ''
    drive(check, instance=system, source='x', runner=fake_runner())


def test_real_run_update_with_fake_perform(monkeypatch):
    """Der echte ``run_update`` spricht mit den Hooks des Bildschirms (Schritte, Fortschritt, Ergebnis)."""
    def perform(instance, source, sha256, release_id, deps, echo, step=None):
        for key in ('pruefen', 'entpacken', 'umgebung', 'selbsttest', 'umschalten', 'dienst_neustart', 'bereit'):
            step(key)
        echo('fertig')
        return update.Result('ok', old_version='1.0.0', new_version='1.1.0', message='Version 1.1.0 läuft.')

    monkeypatch.setattr(update, '_perform', perform)
    monkeypatch.setattr(update, 'prefix_of', lambda instance: None)

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.finished)
        assert 'aktualisiert' in screen_text(screen) and 'fertig' in log_text(screen)
        assert screen.progress == (7.0, 7.0)
    drive(check, source='/tmp/a.tar.gz')


def test_usable_at_80x24():
    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        assert screen.query_one('#kal-buttons').region.bottom <= 24
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.finished)
        assert screen.query_one('#kal-buttons').region.bottom <= 24
    drive(check, size=(80, 24), source='/tmp/picam-1.1.0.tar.gz', runner=fake_runner())
