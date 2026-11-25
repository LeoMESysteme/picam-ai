"""Zertifikat erneuern in der Konsole (``ZertifikatErneuernScreen``): Brückenidentität und gewöhnliches Zertifikat."""

from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path
from types import SimpleNamespace

import admin_fakes
from test_admin_update_screen import log_text, text_of, until
from test_admin_update_screen import screen_text as base_text

from dispread.admin.views.zertifikat_screen import ZertifikatErneuernScreen
from dispread.workbench.cli import BridgeRenewalResult

USER = dataclasses.replace(admin_fakes.INSTANCE, kind='user', scope='user',
                           bridge_directory='/var/lib/picam/workbench/bridge')
OLD, NEW = 'a1' * 32, 'b2' * 32


def screen_text(screen):
    return base_text(screen) + '\n' + text_of(screen.query_one('#kal-checks'))


def renewal(**kwargs) -> BridgeRenewalResult:
    values = dict(pi_id='urn:picam:pi:565e3468', previous_certificate_sha256=OLD, certificate_sha256=NEW,
                  not_after_utc='2027-11-25T10:00:00Z', backup=Path('/var/lib/picam/workbench/bridge/backup/identity.json'),
                  certificate_export=Path('/var/lib/picam/workbench/tls/cert.pem'),
                  profile_url='https://192.168.10.42:8080/live/bridge/profile',
                  profile_export_command=('python', '-m', 'dispread.workbench.cli', 'bridge', 'export-profile',
                                          '--output', 'pi.dispread'))
    values.update(kwargs)
    return BridgeRenewalResult(**values)


def idle(instance, include_setup=False):
    return SimpleNamespace(stop_blocker=None)


class Backend:
    def __init__(self, *, renew=None, restart=(True, 'Dienst neu gestartet.')):
        self.calls = []
        self.renew_result = renew
        self.restart_result = restart

    def renew(self, instance, *, confirmed, collect=None):
        self.calls.append(('renew', confirmed))
        if isinstance(self.renew_result, Exception):
            raise self.renew_result
        return self.renew_result or renewal()

    def restart(self, instance):
        self.calls.append('restart')
        return self.restart_result


def drive(test, *, backend=None, mode='bridge', instance=USER, size=(100, 30), collect=None, **kwargs):
    backend = backend or Backend()
    kwargs.setdefault('directory', '/var/lib/picam/workbench/tls')

    async def main():
        app = admin_fakes.make_app('idle', instance=instance)
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.3)
            screen = ZertifikatErneuernScreen(instance, mode, renew=backend.renew, restart=backend.restart,
                                              collect=collect or idle, **kwargs)
            app.push_screen(screen)
            await pilot.pause(0.2)
            await test(app, pilot, screen, backend)
            screen.cancel_event.set()
    asyncio.run(main())


def test_bridge_plan_explains_consequences_and_asks_typed_word():
    async def check(app, pilot, screen, backend):
        await until(pilot, lambda: screen.pending is not None)
        text = screen_text(screen)
        for word in ('PLAN', 'Pi-ID', 'pi.dispread', 'neu koppeln', 'Browser', 'neu gestartet', 'gesperrt'):
            assert word in text, word
        assert screen.pending['expected'] == 'erneuern' and screen.focused.id == 'kal-input'
        assert backend.calls == []                       # nichts ohne Bestätigung
        await pilot.press('escape')
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'cancelled' and backend.calls == []
        assert 'nichts geändert' in screen_text(screen)
    drive(check)


def test_bridge_success_shows_fingerprints_backup_and_next_steps():
    async def check(app, pilot, screen, backend):
        await until(pilot, lambda: screen.pending is not None)
        screen.query_one('#kal-input').value = 'erneuern'
        await pilot.press('enter')
        await until(pilot, lambda: screen.finished)
        text = screen_text(screen)
        assert backend.calls == [('renew', True), 'restart']
        assert screen.result.outcome == 'ok'
        for word in ('erneuert', 'urn:picam:pi:565e3468', 'a1a1a1a1a1a1a1a1…a1a1a1a1', 'b2b2b2b2b2b2b2b2…b2b2b2b2',
                     '2027-11-25T10:00:00Z', 'identity.json', '/tls/cert.pem', 'neu gestartet', 'NÄCHSTE SCHRITTE',
                     'pi.dispread', '/live/bridge/profile', 'neu koppeln', 'neu vertrauen'):
            assert word in text, word
        assert 'Sicherung:' in log_text(screen)
    drive(check)


def test_wrong_typed_word_does_not_renew():
    async def check(app, pilot, screen, backend):
        await until(pilot, lambda: screen.pending is not None)
        screen.query_one('#kal-input').value = 'ja'
        await pilot.press('enter')
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'cancelled' and backend.calls == []
    drive(check)


def test_running_measurement_blocks_and_shows_reason():
    async def check(app, pilot, screen, backend):
        await until(pilot, lambda: screen.finished)
        text = screen_text(screen)
        assert screen.result.outcome == 'blocked' and backend.calls == []
        assert 'gesperrt' in text and 'nichts geändert' in text and 'Erneuerung gesperrt' in text
    drive(check, collect=lambda instance, include_setup=False: SimpleNamespace(stop_blocker='Lauf aktiv'))


def test_backend_refusal_is_a_failure_with_nothing_changed():
    async def check(app, pilot, screen, backend):
        await until(pilot, lambda: screen.pending is not None)
        screen.query_one('#kal-input').value = 'erneuern'
        await pilot.press('enter')
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'blocked' and 'Lauf gestartet' in screen_text(screen)
        assert 'restart' not in backend.calls
    drive(check, backend=Backend(renew=ValueError('Erneuerung gesperrt: Lauf gestartet')))


def test_permission_error_names_service_account_command():
    async def check(app, pilot, screen, backend):
        await until(pilot, lambda: screen.pending is not None)
        screen.query_one('#kal-input').value = 'erneuern'
        await pilot.press('enter')
        await until(pilot, lambda: screen.finished)
        text = screen_text(screen)
        assert screen.result.outcome == 'failed' and 'Dienstkonto' in text and 'bridge identity --renew' in text
    drive(check, backend=Backend(renew=PermissionError(13, 'verweigert', '/var/lib/picam/bridge')))


def test_restart_failure_is_partial_with_hint():
    async def check(app, pilot, screen, backend):
        await until(pilot, lambda: screen.pending is not None)
        screen.query_one('#kal-input').value = 'erneuern'
        await pilot.press('enter')
        await until(pilot, lambda: screen.finished)
        text = screen_text(screen)
        assert screen.result.outcome == 'partial' and 'NICHT neu gestartet' in text and 'picam restart' in text
        assert 'erst nach dem Neustart' in text
    drive(check, backend=Backend(restart=(False, 'antwortet nicht')))


def test_plain_certificate_uses_renew_tls_and_button_confirmation(tmp_path):
    cert = tmp_path / 'tls'
    cert.mkdir()
    calls = []

    def runner(argv):
        calls.append(argv)
        return 0, 'Zertifikat erneuert\n', ''

    async def check(app, pilot, screen, backend):
        await until(pilot, lambda: screen.pending is not None)
        assert screen.pending['expected'] is None and 'ZERTIFIKAT' in screen_text(screen)
        assert 'Windows-Brücken müssen neu koppeln' not in screen_text(screen)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.finished)
        assert calls and 'renew-tls' in calls[0] and str(cert) in calls[0] and 'sudo' not in calls[0]
        assert screen.result.outcome == 'ok' and backend.calls == ['restart']
        assert 'Zertifikat erneuert' in log_text(screen)
    drive(check, mode='tls', runner=runner, directory=cert)


def test_sudo_password_for_system_service_never_logged(monkeypatch):
    import os

    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    seen = []

    class Sudo:
        @staticmethod
        def sudo_cached():
            return False

        @staticmethod
        def sudo_validate(password):
            seen.append(password)
            return True, ''

    system = dataclasses.replace(admin_fakes.INSTANCE, bridge_directory='/x')

    async def check(app, pilot, screen, backend):
        await until(pilot, lambda: screen.pending is not None)
        screen.query_one('#kal-input').value = 'erneuern'
        await pilot.press('enter')
        await until(pilot, lambda: screen.pending is not None and screen.pending['entry'] == 'password')
        assert screen.query_one('#kal-input').password
        screen.query_one('#kal-input').value = 'geheim123'
        await pilot.press('enter')
        await until(pilot, lambda: screen.finished)
        assert seen == ['geheim123'] and 'geheim123' not in log_text(screen) + screen_text(screen)
    drive(check, instance=system, sudo=Sudo)


def test_80x24_usable():
    async def check(app, pilot, screen, backend):
        await until(pilot, lambda: screen.pending is not None)
        assert screen.query_one('#kal-buttons').region.bottom <= 24
        screen.query_one('#kal-input').value = 'erneuern'
        await pilot.press('enter')
        await until(pilot, lambda: screen.finished)
        assert screen.query_one('#kal-buttons').region.bottom <= 24
    drive(check, size=(80, 24))
