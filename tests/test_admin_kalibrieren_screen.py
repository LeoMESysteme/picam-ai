"""Kalibrierbildschirm der Konsole (``KalibrierenScreen``) headless: Vorprüfung, Bestätigung, Lauf,
Abbruch, Alarm, sudo-Passwort, Import. Ablauf, Seriell und Aufnahme sind die Fakes aus
``test_admin_calibrate`` (kein Adapter, keine Kamera, kein echter Dienst)."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import admin_fakes
from test_admin_calibrate import ORIGINAL_NORM, Harness, make_file, report, write_session

from dispread.admin import calibrate
from dispread.admin.ui import ConfirmScreen
from dispread.admin.views.kalibrieren_screen import KalibrierenScreen


def text_of(widget) -> str:
    from rich.console import Console

    content = getattr(widget, '_content', None) or getattr(widget, 'renderable', None) or widget.render()
    console = Console(width=200, record=True, file=open('/dev/null', 'w'))
    console.print(content)
    return console.export_text()


def screen_text(screen) -> str:
    return '\n'.join(text_of(screen.query_one(sel)) for sel in
                     ('#kal-title', '#kal-alarm', '#kal-checks', '#kal-plan', '#kal-ask-head', '#kal-ask-text',
                      '#kal-ask-error', '#kal-steps', '#kal-result'))


def log_text(screen) -> str:
    return '\n'.join(strip.text for strip in screen.query_one('#kal-log').lines)


async def until(pilot, predicate, limit_s=10.0):
    for _ in range(int(limit_s / 0.05)):
        if predicate():
            return
        await pilot.pause(0.05)
    raise AssertionError('Bedingung nicht eingetreten')


def drive(h, test, *, mode='kalibrieren', path=None, size=(100, 30)):
    async def main():
        app = admin_fakes.make_app('idle', instance=h.instance)
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.3)
            screen = KalibrierenScreen(h.instance, mode, path=path, deps=h.deps)
            app.push_screen(screen)
            await pilot.pause(0.2)
            await test(app, pilot, screen)
            screen.cancel_event.set()
    asyncio.run(main())


def gated_record(h, gate: threading.Event, *, total=180.0):
    """Aufnahme, die einen Teil meldet und dann wartet; bricht ab, sobald progress() wirft."""
    def record(args, progress):
        h.recorded_args = args
        progress(60.0, total)
        while not gate.is_set():
            progress(60.0, total)  # wirft bei Abbruch (Konsole), wie die echte Aufnahme
            time.sleep(0.02)
        progress(total, total)
        write_session(Path(args.output))
        return 0
    return record


# ------------------------------------------------------------ Vorprüfung

def test_failed_preflight_shows_problem_and_starts_nothing(tmp_path):
    h = Harness(tmp_path, port_exists=lambda _port: False)

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.finished)
        text = screen_text(screen)
        assert 'Problem' in text and 'nicht möglich' in text and 'Nichts geändert' in text
        assert screen.result.outcome == 'gesperrt'
        assert screen.pending is None and not screen.query_one('#kal-ok').display
        assert str(screen.query_one('#kal-cancel').label) == 'Schließen'
        assert h.services == [] and h.gsv.opened == 0 and not h.target.exists()
        await pilot.press('escape')
        await pilot.pause(0.2)
        assert not isinstance(app.screen, KalibrierenScreen)
    drive(h, check)


def test_precheck_ok_then_decline_starts_nothing(tmp_path):
    h = Harness(tmp_path)

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        text = screen_text(screen)
        assert 'bestanden' in text and 'PLAN' in text and 'Werkbank-Dienst wird gestoppt' in text
        assert 'Normierung des Messverstärkers wird verändert' in text
        assert screen.query_one('#kal-ok').display
        await pilot.press('escape')
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'abgebrochen' and 'nichts geändert' in screen.result.reason
        assert h.services == [] and h.gsv.opened <= 1 and not (h.target.parent / 'runs').exists()
    drive(h, check)


# ------------------------------------------------------------ Durchlauf

def test_full_run_shows_steps_progress_and_result(tmp_path):
    gate = threading.Event()
    h = Harness(tmp_path)
    h.deps.record = gated_record(h, gate)

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.progress is not None)
        await pilot.pause(0.4)
        states = {step.key: step.state for step in screen.steps}
        assert states['dienst_stop'] == 'fertig' and states['aufnahme'] == 'läuft'
        assert states['auswertung'] == 'wartet'
        steps = text_of(screen.query_one('#kal-steps'))
        assert ' 60 / 180 s' in steps and 'Werkbank-Dienst stoppen' in steps and 'wartet' in steps
        assert not screen.query_one('#kal-plan').display
        assert str(screen.query_one('#kal-cancel').label) == 'Abbruch anfordern'
        gate.set()
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'installiert' and h.target.exists()
        assert {step.state for step in screen.steps} == {'fertig'}
        text = screen_text(screen)
        assert '180 / 180 s' in text and 'installiert' in text
        assert 'zurückgestellt' in text and 'wieder gestartet' in text and 'Laufordner' in text
        assert 'δ' in text or 'Schutzabstand' in text  # Kennzahlen aus describe()
        assert h.actions() == ['stop', 'start']
        assert 'Kalibrierung übernommen' in log_text(screen)
        await pilot.press('escape')
        await pilot.pause(0.2)
        assert not isinstance(app.screen, KalibrierenScreen)
    drive(h, check)


def test_raw_recording_output_goes_to_the_log_not_the_terminal(tmp_path, capfd, monkeypatch):
    h = Harness(tmp_path)

    def record(args, progress, *, out=None, err=None):
        out.write('Rohmeldung der Aufnahme\nhalbe Zeile')
        out.write(' fertig\n')
        write_session(Path(args.output))
        return 0
    monkeypatch.setattr(calibrate, 'run_record', record)  # wie die echte Aufnahme mit out/err aufgerufen
    h.deps.record = record

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.finished)
        await pilot.pause(0.2)
        log = log_text(screen)
        assert 'Rohmeldung der Aufnahme' in log and 'halbe Zeile fertig' in log
    drive(h, check)
    captured = capfd.readouterr()
    assert 'Rohmeldung' not in captured.out + captured.err


# ------------------------------------------------------------ Abbruch

def test_cancel_during_recording_restores_and_closes_only_after_worker(tmp_path):
    gate = threading.Event()
    h = Harness(tmp_path)
    inner = gated_record(h, gate)

    def record(args, progress):
        h.gsv.norm = [99, 99, 99]  # Sprung läuft: Rückstellung muss nachgeholt werden
        return inner(args, progress)
    h.deps.record = record

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.progress is not None)
        await pilot.press('escape')
        await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
        await pilot.click('#ok')
        await until(pilot, lambda: screen.cancel_requested)
        # Abbruch angefordert: Esc/q/Ctrl+C schließen nichts, solange der Worker läuft
        if not screen.finished:
            await pilot.press('escape')  # schließt nichts
            assert isinstance(app.screen, KalibrierenScreen)
        await until(pilot, lambda: screen.finished)
        assert isinstance(app.screen, KalibrierenScreen)
        result = screen.result
        assert result.outcome == 'abgebrochen' and result.norm_restored is True
        assert result.service_restarted is True and h.gsv.norm == ORIGINAL_NORM
        assert not h.target.exists()
        text = screen_text(screen)
        assert 'abgebrochen' in text and 'zurückgestellt' in text and 'wieder gestartet' in text
        states = {step.key: step.state for step in screen.steps}
        assert states['aufnahme'] == 'abgebrochen' and states['auswertung'] == 'übersprungen'
        assert states['dienst_start'] == 'fertig'
        assert h.actions() == ['stop', 'start']
        await pilot.press('escape')
        await pilot.pause(0.2)
        assert not isinstance(app.screen, KalibrierenScreen)
    drive(h, check)


def test_quit_during_run_requests_cancel_instead_of_exiting(tmp_path):
    gate = threading.Event()
    h = Harness(tmp_path)
    h.deps.record = gated_record(h, gate)

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.progress is not None)
        app.action_quit_app()
        await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
        await pilot.press('escape')   # Rückfrage verneint: es läuft weiter
        await pilot.pause(0.2)
        assert not screen.cancel_requested and not screen.cancel_event.is_set()
        gate.set()
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'installiert'
    drive(h, check)


def test_cancel_during_analysis_only_blocks_the_takeover(tmp_path):
    release = threading.Event()
    entered = threading.Event()
    h = Harness(tmp_path)

    def analyse(recording, profile, out_dir):
        entered.set()
        release.wait(10)
        return report(out_dir, recording)
    h.deps.analyse = analyse

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: entered.is_set())
        await pilot.pause(0.4)
        steps = text_of(screen.query_one('#kal-steps'))
        assert 'nicht abbrechbar' in steps
        await pilot.press('escape')
        await until(pilot, lambda: isinstance(app.screen, ConfirmScreen))
        await pilot.click('#ok')
        await until(pilot, lambda: screen.cancel_requested)
        assert 'läuft zu Ende' in text_of(screen.query_one('#kal-steps'))
        release.set()
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'abgebrochen' and not h.target.exists()
        assert screen.result.service_restarted is True
    drive(h, check)


# ------------------------------------------------------------ Alarm

def test_loud_alarm_is_a_red_card_on_top(tmp_path):
    h = Harness(tmp_path)

    def record(args, progress):
        write_session(Path(args.output), restored=False)
        h.gsv.norm, h.gsv.stuck = [11, 22, 33], True  # Rückstellung scheitert
        return 0
    h.deps.record = record

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        assert not screen.query_one('#kal-alarm').display
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.finished)
        alarm = screen.query_one('#kal-alarm')
        assert alarm.display and 'NICHT zurückgestellt' in text_of(alarm)
        assert 'picam kalibrieren --rueckstellen' in text_of(alarm)
        assert screen.result.norm_restored is False
        assert 'NICHT zurückgestellt' in text_of(screen.query_one('#kal-result'))
        states = {step.key: step.state for step in screen.steps}
        assert states['normierung'] == 'fehlgeschlagen'
    drive(h, check)


# ------------------------------------------------------------ sudo

def test_sudo_password_is_asked_masked_validated_and_never_logged(tmp_path, monkeypatch):
    h = Harness(tmp_path)
    seen = []
    monkeypatch.setattr(calibrate, 'sudo_needed', lambda instance, snapshot: True)
    monkeypatch.setattr(calibrate, 'sudo_cached', lambda: False)

    def validate(password, **_):
        seen.append(password)
        return (password == 'richtig', 'sudo-Authentifizierung fehlgeschlagen (Exit 1).')
    monkeypatch.setattr(calibrate, 'sudo_validate', validate)

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.pending is not None and screen.pending['entry'] == 'password')
        field = screen.query_one('#kal-input')
        assert field.password and field.display
        assert 'Linux-Konto' in screen_text(screen)
        field.value = 'falsch-geheim'
        await pilot.press('enter')
        await until(pilot, lambda: screen.pending is not None and screen.pending['error'])
        assert 'fehlgeschlagen' in text_of(screen.query_one('#kal-ask-error'))
        assert screen.query_one('#kal-input').value == ''          # nicht im Widget behalten
        assert screen.phase != 'running'
        screen.query_one('#kal-input').value = 'richtig'
        await pilot.press('enter')
        await until(pilot, lambda: screen.finished)
        assert seen == ['falsch-geheim', 'richtig'] and screen.result.outcome == 'installiert'
        everything = screen_text(screen) + log_text(screen) + h.text
        assert 'falsch-geheim' not in everything and 'richtig' not in everything
        assert screen.query_one('#kal-input').value == ''
        assert not any('falsch-geheim' in str(v) or v == 'richtig' for v in vars(screen).values()
                       if isinstance(v, (str, list, tuple)))
    drive(h, check)


def test_sudo_cancel_changes_nothing(tmp_path, monkeypatch):
    h = Harness(tmp_path)
    monkeypatch.setattr(calibrate, 'sudo_needed', lambda instance, snapshot: True)
    monkeypatch.setattr(calibrate, 'sudo_cached', lambda: False)
    monkeypatch.setattr(calibrate, 'sudo_validate', lambda password, **_: (_ for _ in ()).throw(AssertionError))

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.pending is not None and screen.pending['entry'] == 'password')
        await pilot.press('escape')
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'abgebrochen' and h.services == [] and not h.target.exists()
    drive(h, check)


# ------------------------------------------------------------ Prüfen und Importieren

def test_import_with_wrong_word_is_not_applied(tmp_path):
    h = Harness(tmp_path)
    source = make_file(tmp_path / 'anderer-pi' / 'timing-streamcam.json')

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        assert screen.pending['expected'] == 'importieren'
        assert 'nur für genau den Aufbau' in text_of(screen.query_one('#kal-ask-text'))
        assert not screen.query_one('#kal-steps').display
        field = screen.query_one('#kal-input')
        field.value = 'ja'
        await pilot.press('enter')
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'abgebrochen' and not h.target.exists()
        assert not calibrate.import_note_path(h.target).exists()
        assert 'abgebrochen' in screen_text(screen)
    drive(h, check, mode='import', path=source)


def test_import_with_right_word_is_applied(tmp_path):
    h = Harness(tmp_path)
    source = make_file(tmp_path / 'anderer-pi' / 'timing-streamcam.json')

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        screen.query_one('#kal-input').value = 'importieren'
        await pilot.press('enter')
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'importiert'
        assert h.target.read_bytes() == source.read_bytes()
        assert calibrate.import_note_path(h.target).exists()
        assert 'importiert' in screen_text(screen)
    drive(h, check, mode='import', path=source)


def test_check_file_shows_metrics_without_confirmation(tmp_path):
    h = Harness(tmp_path)
    make_file(h.target)

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.finished)
        assert screen.result.outcome == 'gueltig' and screen.pending is None
        text = screen_text(screen)
        assert 'gültig' in text and '325,9 ms' in text
        assert not screen.query_one('#kal-steps').display
    drive(h, check, mode='pruefen', path=h.target)


# ------------------------------------------------------------ Größen

def test_usable_at_80x24(tmp_path):
    gate = threading.Event()
    h = Harness(tmp_path)
    h.deps.record = gated_record(h, gate)

    async def check(app, pilot, screen):
        await until(pilot, lambda: screen.pending is not None)
        assert screen.query_one('#kal-ok').region.height == 1
        assert screen.query_one('#kal-ok').region.bottom <= 24
        await pilot.click('#kal-ok')
        await until(pilot, lambda: screen.progress is not None)
        await pilot.pause(0.3)
        assert screen.query_one('#kal-log').region.height >= 3
        assert screen.query_one('#kal-cancel').region.bottom <= 24
        gate.set()
        await until(pilot, lambda: screen.finished)
        assert screen.query_one('#kal-cancel').region.bottom <= 24
    drive(h, check, size=(80, 24))

