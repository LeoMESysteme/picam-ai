"""Einrichtungsassistent der Konsole (``OnboardingScreen``) headless: Schrittfolge, Kalibrierbildschirm
oder Sperrgrund, Marke, erneuter Aufruf. Beispieldaten aus ``admin_fakes``."""

from __future__ import annotations

import asyncio
import dataclasses

import admin_fakes
import pytest

from dispread.admin import calibrate
from dispread.admin.views import onboarding_screen as ob
from dispread.admin.views.onboarding_screen import OnboardingScreen

KEEP = {}


def plain(widget) -> str:
    from rich.console import Console

    content = getattr(widget, '_content', None) or getattr(widget, 'renderable', None) or widget.render()
    console = Console(width=200, record=True, file=open('/dev/null', 'w'))
    console.print(content)
    return console.export_text()


def page_text(screen) -> str:
    return '\n'.join(plain(w) for w in screen.query('#ob-title, #ob-chips, #ob-hint, SectionCard') if w.display)


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'cfg'))
    data = tmp_path / 'data'
    (data / 'tls').mkdir(parents=True)
    return data


def instance(data):
    return dataclasses.replace(admin_fakes.INSTANCE, data=str(data), calibration='/var/lib/picam/calibration/timing-streamcam.json')


def drive(test, *, data, state='idle', size=(100, 30), start=0, **kwargs):
    async def main():
        app = admin_fakes.make_app(state, instance=instance(data), **kwargs)
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.3)
            screen = OnboardingScreen(app.instance, start=start)
            app.push_screen(screen)
            await pilot.pause(0.3)
            await test(app, pilot, screen)
    asyncio.run(main())


def test_steps_in_order_with_progress_and_finish_sets_marker(home):
    async def test(app, pilot, screen):
        text = page_text(screen)
        assert 'Schritt 1 von 3: Konto & Adresse' in text and 'https://192.168.10.42:8080/live' in text
        assert 'Benutzer labor mit dem Linux-Passwort dieses Kontos' in text
        assert 'ZERTIFIKAT IM BROWSER VERTRAUEN' in text
        await pilot.click('#ob-next')
        await pilot.pause(0.3)
        text = page_text(screen)
        assert 'Schritt 2 von 3: Kamera & Fokus' in text and '/dev/video0' in text and '1920×1080' in text
        assert 'https://192.168.10.42:8080/live' in text and 'Bild und Fokus in der Werkbank unter /live' in text
        await pilot.click('#ob-next')
        await pilot.pause(0.3)
        text = page_text(screen)
        assert 'Schritt 3 von 3: Timing-Kalibrierung' in text and 'USB-RS232-Adapter' in text
        assert str(screen.query_one('#ob-next').label) == 'Fertig – zur Übersicht'
        assert not ob.is_done(app.instance)
        await pilot.click('#ob-next')
        await pilot.pause(0.3)
        assert app.screen is not screen and ob.is_done(app.instance)
    drive(test, data=home)


def test_back_and_skip_mark_states(home):
    async def test(app, pilot, screen):
        assert screen.query_one('#ob-back').disabled
        assert screen.state('konto') == ob.OPEN          # Dienst aus: Schritt offen
        await pilot.click('#ob-skip')
        await pilot.pause(0.2)
        assert screen.page == 1 and screen.state('konto') == ob.SKIPPED
        assert 'übersprungen' in plain(screen.query_one('#ob-chips'))
        await pilot.click('#ob-back')
        await pilot.pause(0.2)
        assert screen.page == 0
        await pilot.click('#ob-skip')
        await pilot.click('#ob-skip')
        await pilot.click('#ob-skip')   # letzter Schritt: Überspringen schließt den Assistenten
        await pilot.pause(0.3)
        assert app.screen is not screen and ob.is_done(app.instance)
        saved = ob.json.loads(next(p for p in ob.marker_paths(app.instance) if p.is_file()).read_text())
        assert saved['schritte']['konto'] == ob.SKIPPED
    drive(test, data=home, state='down')


def test_calibration_opens_screen_when_possible(home, monkeypatch):
    monkeypatch.setattr(calibrate, 'adapter_present', lambda: True)

    async def test(app, pilot, screen):
        app.view('kamera').calibrate_blocker = lambda: None
        opened = []
        app.view('kamera').calibrate = lambda: opened.append(True)
        act = screen.query_one('#ob-act')
        assert not act.disabled and 'Kalibrieren' in str(act.label)
        await pilot.click('#ob-act')
        await pilot.pause(0.2)
        assert opened == [True]
    drive(test, data=home, start=2)


def test_calibration_blocker_is_shown_and_action_disabled(home, monkeypatch):
    monkeypatch.setattr(calibrate, 'adapter_present', lambda: False)

    async def test(app, pilot, screen):
        act = screen.query_one('#ob-act')
        assert act.disabled
        text = page_text(screen)
        assert 'kein USB-RS232-Adapter' in text and 'nicht erkannt' in text
        assert 'kein USB-RS232-Adapter' in plain(screen.query_one('#ob-hint'))
    drive(test, data=home, start=2)


def test_calibration_valid_needs_no_action(home):
    async def test(app, pilot, screen):
        assert screen.state('kalibrierung') == ob.DONE
        assert screen.query_one('#ob-act').disabled and 'Gültig: nichts zu tun' in page_text(screen)
        assert not screen.query_one('#ob-skip').display
    drive(test, data=home, state='run', start=2)


def test_camera_reconnect_is_the_tab_action(home):
    async def test(app, pilot, screen):
        calls = []
        app.camera_connect = lambda: calls.append(1)
        await pilot.click('#ob-act')
        await pilot.pause(0.2)
        assert calls == [1]
    drive(test, data=home, start=1)


def test_escape_closes_and_counts_as_done(home):
    async def test(app, pilot, screen):
        await pilot.press('escape')
        await pilot.pause(0.3)
        assert app.screen is not screen and ob.is_done(app.instance)
    drive(test, data=home)


def test_marker_roundtrip_and_fallback_location(home, tmp_path):
    inst = instance(home)
    assert ob.should_start(inst) and not ob.is_done(inst)
    path = ob.write_marker(inst, {'konto': ob.DONE})
    assert path == home / ob.MARKER and ob.is_done(inst) and not ob.should_start(inst)
    # Datenordner nicht schreibbar: Marke landet in der Benutzerkonfiguration
    blocked = dataclasses.replace(inst, data=str(tmp_path / 'datei'))
    (tmp_path / 'datei').write_text('x')
    fallback = ob.write_marker(blocked, {})
    assert fallback is not None and fallback.parent == tmp_path / 'cfg' / 'picam'
    # ohne config.toml (Entwicklungsbetrieb) nie automatisch
    assert not ob.should_start(dataclasses.replace(inst, config=None))


def test_fingerprint_of_pem(tmp_path):
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, 'test')])
    now = datetime.datetime.now(datetime.UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    path = tmp_path / 'cert.pem'
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    expected = cert.fingerprint(hashes.SHA256()).hex().upper()
    assert ob.fingerprint(path).replace(':', '') == expected
    assert ob.fingerprint(tmp_path / 'fehlt.pem') is None and ob.fingerprint(None) is None


def test_auto_start_forced_and_settings_action(home):
    async def main():
        inst = instance(home)
        app = admin_fakes.make_app('idle', instance=inst, onboarding='auto')
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.8)
            assert isinstance(app.screen, OnboardingScreen)
            await pilot.press('escape')
            await pilot.pause(0.3)
        app = admin_fakes.make_app('idle', instance=inst, onboarding='auto')
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.8)
            assert not isinstance(app.screen, OnboardingScreen)   # Marke gesetzt
            app.open_onboarding()
            await pilot.pause(0.3)
            assert isinstance(app.screen, OnboardingScreen)
        app = admin_fakes.make_app('idle', instance=inst, onboarding='force')
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.8)
            assert isinstance(app.screen, OnboardingScreen)
    asyncio.run(main())


def test_cli_switch():
    from dispread.admin import cli

    assert cli.parser().parse_args(['--onboarding']).onboarding is True
    assert not hasattr(cli.parser().parse_args([]), 'onboarding')


def test_small_terminal_80x24_is_usable(home):
    async def test(app, pilot, screen):
        for _ in range(3):
            for button in screen.query('#ob-buttons Button'):
                if button.display:
                    assert button.region.height == 1 and button.region.right <= 80, button.id
            assert screen.query_one('#ob-chips').region.right <= 80
            await pilot.click('#ob-next')
            await pilot.pause(0.3)
    drive(test, data=home, size=(80, 24))
