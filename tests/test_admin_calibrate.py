"""``picam kalibrieren`` (dispread.admin.calibrate) ohne Hardware und ohne echten Dienst.

Seriell: ``FakeGsv`` beantwortet Registerlesen/-schreiben wie der GSV-2AS
(Semikolon-Präfix 0x3B, ``last error`` 0xA0) und liefert Telegrammzeilen.
Aufnahme und Auswertung sind ersetzt (``Deps.record``/``Deps.analyse``); die
Kalibrierung selbst baut und prüft der echte Code
(``calibration_from_offset_reports``, ``load_calibration``). Dienst: ein
Aufzeichner statt systemctl. Es wird weder ``/dev/ttyUSB0`` noch die Kamera
geöffnet, und kein Dienst wird angefasst.
"""

from __future__ import annotations

import errno
import io
import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_display_offset import _write_session_profile

from dispread import gsv2as_serial
from dispread.admin import calibrate, cli, probes
from dispread.admin.instance import INSTALLED_UNIT, Instance
from dispread.timing_calibration import load_calibration

ORIGINAL_NORM = [80, 27, 228]
ORIGINAL_DPOINT = [1]
NOW = datetime(2026, 11, 20, 9, 30, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _no_serial_sleeps(monkeypatch):
    monkeypatch.setattr(gsv2as_serial, '_sleep', lambda _s: None)


class FakeGsv:
    """Zustand des Messverstärkers über alle Öffnungen hinweg."""

    def __init__(self, *, telegrams=True, stuck=False):
        self.norm = list(ORIGINAL_NORM)
        self.dpoint = list(ORIGINAL_DPOINT)
        self.telegrams = telegrams
        self.stuck = stuck        # Schreibbefehle wirken nicht (Rückstellung scheitert)
        self.opened = 0
        self.writes: list[bytes] = []

    def open(self, port, baudrate, timeout):
        self.opened += 1
        return FakeSerial(self)


class FakeSerial:
    def __init__(self, device: FakeGsv):
        self.device = device
        self.pending = b''
        self.closed = False

    def readline(self):
        return b'+0.60397 mV/V\r\n' if self.device.telegrams else b''

    def write(self, data: bytes):
        device = self.device
        device.writes.append(bytes(data))
        command = data[0]
        if command == 0x10 and not device.stuck:
            device.norm = list(data[1:4])
        elif command == 0x11 and not device.stuck:
            device.dpoint = [data[1]]
        elif command == 0x1A:
            self.pending = bytes([0x3B, *device.norm])
        elif command == 0x1C:
            self.pending = bytes([0x3B, *device.dpoint])
        elif command == 0x42:
            self.pending = bytes([0x3B, 0xA0])
        return len(data)

    def read(self, count):
        chunk, self.pending = self.pending[:count], self.pending[count:]
        return chunk

    def flush(self):
        pass

    def reset_input_buffer(self):
        pass

    def close(self):
        self.closed = True


def snapshot(state='idle', service=probes.OK, diagnose=False):
    def collect(instance, include_setup=False, **_):
        live = None if service in (probes.OFF, probes.FAIL) else {'state': state, 'diagnose_kopie': diagnose}
        facts = {'dienst': probes.Fact('dienst', 'Dienst', service, 'x')}
        return probes.Snapshot(instance, facts, live, time.time())
    return collect


def write_session(output: Path, *, restored=True, frames=900, lines=240, aborted=False, usb_id='046d:0893'):
    output.mkdir(parents=True, exist_ok=True)
    verification = {'write_ok': True, 'matches_restore_point': True} if restored else \
        {'write_ok': False, 'matches_restore_point': False}
    (output / 'session.json').write_text(json.dumps({
        'frames_recorded': frames, 'serial_lines_recorded': lines, 'aborted': aborted,
        'abort_reason': 'KeyboardInterrupt (Ctrl-C)' if aborted else None,
        'camera': {'usb_id': usb_id}, 'restore_verification': verification}))


def report(out_dir: Path, recording: Path, *, detected=True) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    populations = [
        {'population': 'large', 'detected': False, 'M_s': None, 'delta_s': None, 'n_qualifying': 1,
         'n_events_total': 20, 'null_baseline': {'pass_rate': 0.1}},
        {'population': 'small', 'detected': detected, 'M_s': 0.2716 if detected else None,
         'delta_s': 0.097 if detected else None, 'n_qualifying': 20 if detected else 2, 'n_events_total': 25,
         'null_baseline': {'pass_rate': 0.05 if detected else 0.6}},
    ]
    result = {'session_dir': str(recording), 'populations': populations, 'params': {'min_qualifying': 3}}
    path = out_dir / 'offset-analyse.json'
    path.write_text(json.dumps(result))
    return {**result, '_out_json': str(path)}


class Harness:
    def __init__(self, tmp_path: Path, *, collect=None, gsv=None, record=None, analyse=None, **overrides):
        self.tmp = tmp_path
        self.data = tmp_path / 'data'
        self.instance = Instance(kind='user', unit=INSTALLED_UNIT, scope='user',
                                 calibration=str(self.data / 'calibration' / 'timing-streamcam.json'),
                                 live_data=str(self.data / 'live'), root=str(tmp_path / 'releases' / '1.0'))
        (self.data / 'calibration').mkdir(parents=True)
        self.profile = self.data / 'live' / 'live-20261120T080000Z' / 'profile.json'
        self.profile.parent.mkdir(parents=True)
        _write_session_profile(self.profile, quad=[[0, 0], [59, 0], [59, 39], [0, 39]], camera_size=(1920, 1080))
        staging = tmp_path / 'shm'
        staging.mkdir()
        self.gsv = gsv or FakeGsv()
        self.services: list[list[str]] = []
        self.progress_calls = 0
        self.recorded_args = None
        self.out, self.err = io.StringIO(), io.StringIO()

        def default_record(args, progress):
            self.recorded_args = args
            progress(60.0, args.duration)
            progress(args.duration, args.duration)
            self.gsv.norm = [99, 99, 99]  # Normierungssprung wie im Faktorplan
            self.gsv.norm = list(ORIGINAL_NORM)  # Rückstellung im Lesethread
            write_session(Path(args.output))
            return 0

        self.deps = calibrate.Deps(
            collect=collect or snapshot(), usb_camera=lambda: {'speed_mbps': 5000, 'port': '2-1'},
            port_exists=lambda _port: True, open_serial=self.gsv.open, camera_holders=lambda: [],
            service_runner=self._service, recheck=lambda: None, wait_ready=lambda _instance: True,
            record=record or default_record,
            analyse=analyse or (lambda recording, profile, out_dir: report(out_dir, recording)),
            storage=lambda args, profile, folder: (None, 600 << 20), staging_root=staging,
            now=lambda: NOW, sleep=lambda _s: None, ask=lambda _prompt: 'j', isatty=lambda: True)
        for name, value in overrides.items():
            setattr(self.deps, name, value)
        self.console = calibrate.Console(cli.Style(self.out, color=False), out=self.out, err=self.err)

    def _service(self, command):
        self.services.append(command)
        return 0

    def run(self, **options) -> int:
        return calibrate.calibrate(self.instance, calibrate.Options(**options), self.console, self.deps)

    @property
    def target(self) -> Path:
        return Path(self.instance.calibration)

    @property
    def run_dir(self) -> Path:
        return self.target.parent / 'runs' / '20261120T093000Z'

    def actions(self) -> list[str]:
        return [command[-2] for command in self.services]

    @property
    def text(self) -> str:
        return self.out.getvalue() + self.err.getvalue()


# ------------------------------------------------------------------ Erfolg

def test_success_installs_validated_calibration_and_restarts_service(tmp_path):
    h = Harness(tmp_path)
    assert h.run(yes=True) == calibrate.EXIT_OK
    calibration = load_calibration(h.target)
    assert calibration.camera_usb_id == '046d:0893'
    assert calibration.guard_margin_ms == pytest.approx(271.6)
    assert calibration.display_offset_ms == pytest.approx(97.0)
    assert calibration.sources[0]['offset_json'].startswith(str(h.run_dir))
    assert len(calibration.sources[0]['sha256']) == 64
    assert h.actions() == ['stop', 'start']
    assert h.gsv.norm == ORIGINAL_NORM
    journal = json.loads((h.run_dir / 'lauf.json').read_text())
    assert journal['ergebnis'] == 'installiert' and journal['normierung_zurueckgestellt'] is True
    assert journal['dienst_neu_gestartet'] is True
    restore = json.loads((h.run_dir / 'rueckstellpunkt.json').read_text())
    assert restore['register']['norm']['daten'] == ORIGINAL_NORM
    assert restore['register']['dpoint']['daten'] == ORIGINAL_DPOINT
    args = h.recorded_args
    assert args.source == 'camera' and args.port == '/dev/ttyUSB0' and args.baudrate == 38400
    assert args.restore_point == h.run_dir / 'rueckstellpunkt.json'
    assert args.output == h.run_dir / 'aufnahme' and args.camera_settings == h.profile
    assert args.norm_schedule and all(0.15 <= factor <= 1_580_000 for factor, _ in args.norm_schedule)
    assert h.target.stat().st_mode & 0o777 == 0o644  # Ordner 0755 -> Datei lesbar wie der Ordner


def test_success_keeps_previous_file_and_drops_import_note(tmp_path):
    h = Harness(tmp_path)
    h.target.write_text('{"alt": true}')
    calibrate.import_note_path(h.target).write_text('{"quelle": "/x"}')
    assert h.run(yes=True) == calibrate.EXIT_OK
    assert json.loads((h.run_dir / 'vorherige-kalibrierung.json').read_text()) == {'alt': True}
    assert (h.run_dir / 'vorheriger-import.json').is_file()
    assert not calibrate.import_note_path(h.target).exists()


def test_service_not_running_is_neither_stopped_nor_started(tmp_path):
    h = Harness(tmp_path, collect=snapshot(service=probes.OFF))
    assert h.run(yes=True) == calibrate.EXIT_OK
    assert h.services == []


# ------------------------------------------------------------------ Nicht erkannt / ungültig

def test_not_detected_writes_nothing_and_explains(tmp_path):
    h = Harness(tmp_path, analyse=lambda recording, profile, out: report(out, recording, detected=False))
    assert h.run(yes=True) == calibrate.EXIT_FAIL
    assert not h.target.exists()
    assert 'Kein Versatz erkannt' in h.text and '2 von 25' in h.text and '60 %' in h.text
    assert '--dauer 180' in h.text
    assert json.loads((h.run_dir / 'lauf.json').read_text())['ergebnis'] == 'nicht erkannt'
    assert h.actions() == ['stop', 'start']


def test_wrong_camera_in_recording_writes_nothing(tmp_path):
    def record(args, progress):
        write_session(Path(args.output), usb_id='1234:5678')
        return 0

    h = Harness(tmp_path, record=record)
    h.target.write_text('{"alt": true}')
    assert h.run(yes=True) == calibrate.EXIT_FAIL
    assert json.loads(h.target.read_text()) == {'alt': True}
    assert 'Ergebnis ungültig' in h.text


def test_analysis_error_writes_nothing(tmp_path):
    def analyse(recording, profile, out):
        raise RuntimeError('Kamera-Bildgroesse passt nicht')

    h = Harness(tmp_path, analyse=analyse)
    assert h.run(yes=True) == calibrate.EXIT_FAIL
    assert not h.target.exists() and 'Kamera-Bildgroesse' in h.text


# ------------------------------------------------------------------ Fehlerpfade: Rückstellung und Dienst

def test_record_exception_restores_norm_and_restarts_service(tmp_path):
    h = Harness(tmp_path)

    def record(args, progress):
        h.gsv.norm = [11, 22, 33]  # Sprung geschrieben, dann Absturz ohne Rückstellung
        raise OSError('Platte voll')

    h.deps.record = record
    assert h.run(yes=True) == calibrate.EXIT_FAIL
    assert h.gsv.norm == ORIGINAL_NORM and h.gsv.dpoint == ORIGINAL_DPOINT
    assert h.actions() == ['stop', 'start']
    assert not h.target.exists()
    assert 'zweiter Versuch' in h.text and 'Platte voll' in h.text
    assert json.loads((h.run_dir / 'rueckstellung-nachgeholt.json').read_text())['ok'] is True


def test_ctrl_c_during_recording_restores_and_restarts(tmp_path):
    h = Harness(tmp_path)

    def record(args, progress):
        h.gsv.norm = [11, 22, 33]
        raise KeyboardInterrupt

    h.deps.record = record
    assert h.run(yes=True) == calibrate.EXIT_ABORT
    assert h.gsv.norm == ORIGINAL_NORM
    assert h.actions() == ['stop', 'start']
    assert json.loads((h.run_dir / 'lauf.json').read_text())['ergebnis'] == 'abgebrochen'


def test_worker_cancellation_restores_and_restarts_with_real_recorder(tmp_path, monkeypatch):
    import numpy as np
    import serial

    from dispread.calibration import record
    from dispread.records import Timestamp

    cancelled = threading.Event()
    recording = threading.Event()
    camera_closed = threading.Event()
    gsv = FakeGsv()
    connections = []

    class Serial(FakeSerial):
        def readline(self):
            time.sleep(0.01)
            return super().readline()

    def open_serial(*args, **kwargs):
        port = Serial(gsv)
        connections.append(port)
        return port

    class Camera:
        def __init__(self, settings, device=None):
            self.image = np.zeros((36, 64, 3), dtype=np.uint8)

        def open(self):
            pass

        def frames(self):
            while True:
                yield SimpleNamespace(image=self.image, capture_timestamp=Timestamp.now_monotonic())
                time.sleep(0.025)

        def close(self):
            camera_closed.set()

        def describe(self):
            return {'usb_id': '046d:0893'}

    class Progress(calibrate.Progress):
        def __call__(self, elapsed, total):
            recording.set()

    h = Harness(tmp_path, record=calibrate.run_record, open_serial=open_serial, cancelled=cancelled.is_set)
    h.console.progress = lambda tty: Progress(h.console, tty)
    monkeypatch.setattr(serial, 'Serial', open_serial)
    monkeypatch.setattr(record, 'UvcSource', Camera)
    monkeypatch.setattr(record, '_check_staging_capacity', lambda *_: None)
    resumed_with_cleanup = []

    def service(command):
        if 'start' in command:
            resumed_with_cleanup.append((gsv.norm == ORIGINAL_NORM, gsv.dpoint == ORIGINAL_DPOINT,
                                         camera_closed.is_set(), all(port.closed for port in connections)))
        return h._service(command)

    h.deps.service_runner = service
    codes = []
    worker = threading.Thread(target=lambda: codes.append(h.run(yes=True)), daemon=True)
    worker.start()
    try:
        assert recording.wait(10)
        assert gsv.norm != ORIGINAL_NORM
    finally:
        cancelled.set()
        worker.join(15)
    assert codes == [calibrate.EXIT_ABORT]
    assert h.actions() == ['stop', 'start']
    assert resumed_with_cleanup == [(True, True, True, True)]
    assert len(connections) == 3  # Telegrammprobe, Rückstellpunkt, Aufnahme mit eigener Rückstellung
    session = json.loads((h.run_dir / 'aufnahme' / 'session.json').read_text())
    assert session['aborted'] and session['abort_reason'] == 'konsole'
    assert session['restore_verification']['matches_restore_point']
    assert 'Fertig:' in h.out.getvalue()
    assert 'Abbruch (konsole)' in h.err.getvalue()
    result = h.console.last_result
    assert result == calibrate.Result('abgebrochen', calibrate.EXIT_ABORT, 'Abbruch in der Konsole', h.run_dir,
                                      norm_restored=True, service_restarted=True)
    assert json.loads((h.run_dir / 'lauf.json').read_text())['ergebnis'] == 'abgebrochen'
    assert not h.target.exists()


def test_worker_signal_contexts_are_noops(monkeypatch):
    from dispread.calibration import record

    calls = []
    monkeypatch.setattr(signal, 'signal', lambda *args: calls.append(args))

    def run():
        with calibrate.abort_on_signals(), calibrate.shielded(), record._SignalsHeld():
            record._install_sigterm_handler()

    worker = threading.Thread(target=run)
    worker.start()
    worker.join()
    assert not calls


def test_cancellation_while_waiting_for_camera_restarts_service(tmp_path):
    cancelled = threading.Event()
    h = Harness(tmp_path, camera_holders=lambda: ['4711 (python3)'],
                cancelled=cancelled.is_set, sleep=lambda _s: cancelled.set())
    assert h.run(yes=True) == calibrate.EXIT_ABORT
    assert h.actions() == ['stop', 'start']
    assert h.console.last_result.reason == 'Abbruch in der Konsole'
    assert h.gsv.opened == 1  # nur Telegrammprobe


def test_worker_cancellation_during_analysis_prevents_installation(tmp_path):
    cancelled = threading.Event()
    h = Harness(tmp_path, cancelled=cancelled.is_set)

    def analyse(recording, profile, out_dir):
        assert h.actions() == ['stop', 'start']
        assert 'nicht abbrechbar' in h.text
        cancelled.set()
        return report(out_dir, recording)

    h.deps.analyse = analyse
    codes = []
    worker = threading.Thread(target=lambda: codes.append(h.run(yes=True)))
    worker.start()
    worker.join(5)
    assert codes == [calibrate.EXIT_ABORT]
    assert h.console.last_result.outcome == 'abgebrochen'
    assert h.console.last_result.run_dir == h.run_dir
    assert not h.target.exists()


def test_aborted_session_counts_as_abort(tmp_path):
    def record(args, progress):
        write_session(Path(args.output), aborted=True)
        return 0

    h = Harness(tmp_path, record=record)
    assert h.run(yes=True) == calibrate.EXIT_ABORT
    assert not h.target.exists() and h.actions() == ['stop', 'start']


def test_failed_restore_is_loud_and_fails_even_with_calibration(tmp_path):
    h = Harness(tmp_path)

    def record(args, progress):
        write_session(Path(args.output), restored=False)
        h.gsv.norm, h.gsv.stuck = [11, 22, 33], True  # Gerät nimmt keine Schreibbefehle mehr an
        return 0

    h.deps.record = record
    assert h.run(yes=True) == calibrate.EXIT_FAIL
    assert h.gsv.norm == [11, 22, 33]
    assert 'NICHT zurückgestellt' in h.err.getvalue()
    assert 'picam kalibrieren --rueckstellen' in h.err.getvalue()
    assert h.actions() == ['stop', 'start']
    journal = json.loads((h.run_dir / 'lauf.json').read_text())
    assert journal['normierung_zurueckgestellt'] is False and journal['ergebnis'] == 'installiert'


def test_service_stop_failure_keeps_everything(tmp_path):
    h = Harness(tmp_path, service_runner=lambda command: 1)
    assert h.run(yes=True) == calibrate.EXIT_FAIL
    assert h.gsv.opened == 1  # nur die Telegrammprobe, kein Registerzugriff
    assert not h.target.exists()


def test_stop_reported_failed_but_service_down_is_started_again(tmp_path):
    states = iter([probes.OK])
    h = Harness(tmp_path)
    h.deps.collect = lambda instance, include_setup=False, **_: snapshot(service=next(states, probes.OFF))(instance)
    h.deps.service_runner = lambda command: (h.services.append(command) or (1 if 'stop' in command else 0))
    assert h.run(yes=True) == calibrate.EXIT_FAIL
    assert h.actions() == ['stop', 'start']


def test_camera_still_held_aborts_and_restarts(tmp_path, monkeypatch):
    monkeypatch.setattr(calibrate, 'CAMERA_FREE_TIMEOUT_S', -1.0)
    h = Harness(tmp_path, camera_holders=lambda: ['4711 (python3)'])
    assert h.run(yes=True) == calibrate.EXIT_FAIL
    assert 'noch belegt' in h.text and h.actions() == ['stop', 'start']
    assert all(write[0] not in (0x10, 0x11) for write in h.gsv.writes)


def test_restart_failure_is_reported(tmp_path):
    h = Harness(tmp_path, wait_ready=lambda _instance: False)
    assert h.run(yes=True) == calibrate.EXIT_OK  # Kalibrierung gültig, Dienst meldet sich nur nicht
    assert 'picam start' in h.err.getvalue()


# ------------------------------------------------------------------ Signale (SIGHUP/SIGTERM) und abgerissenes Terminal

def _service_state_collect(h: Harness):
    """Dienststatus folgt den ausgeführten stop/start-Befehlen."""
    def collect(instance, include_setup=False, **_):
        level = probes.OFF if h.actions() and h.actions()[-1] == 'stop' else probes.OK
        return snapshot(service=level)(instance)
    return collect


def _kill(number):
    os.kill(os.getpid(), number)
    time.sleep(0.05)  # Python prüft Signale zwischen Bytecodes


@pytest.mark.parametrize('number', [signal.SIGHUP, signal.SIGTERM])
@pytest.mark.parametrize('phase', ['dienst_stoppen', 'kamera_warten', 'rueckstellpunkt', 'aufnahme'])
def test_signal_in_any_phase_restores_and_restarts(tmp_path, phase, number):
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)}
    h = Harness(tmp_path)
    h.deps.collect = _service_state_collect(h)
    opened = h.gsv.open

    def service(command):
        h.services.append(command)
        if phase == 'dienst_stoppen' and 'stop' in command:
            _kill(number)  # Dienst ist gestoppt, Rückgabe erreicht den Aufrufer nicht mehr
        return 0

    def holders():
        if phase == 'kamera_warten':
            _kill(number)
        return []

    def open_serial(port, baudrate, timeout):
        if phase == 'rueckstellpunkt' and h.gsv.opened == 1:  # 1 = Telegrammprobe
            _kill(number)
        return opened(port, baudrate, timeout)

    def record(args, progress):
        h.gsv.norm = [11, 22, 33]  # Sprung geschrieben, dann Signal
        _kill(number)
        raise AssertionError('Signal kam nicht an')

    h.deps.service_runner, h.deps.camera_holders, h.deps.open_serial, h.deps.record = \
        service, holders, open_serial, record
    assert h.run(yes=True) == calibrate.EXIT_ABORT
    assert h.actions() == ['stop', 'start']
    assert h.gsv.norm == ORIGINAL_NORM and h.gsv.dpoint == ORIGINAL_DPOINT
    if phase == 'aufnahme':
        assert json.loads((h.run_dir / 'rueckstellung-nachgeholt.json').read_text())['ok'] is True
    else:
        assert all(write[0] not in (0x10, 0x11) for write in h.gsv.writes)  # nichts zu stellen
    journal = json.loads((h.run_dir / 'lauf.json').read_text())
    assert journal['ergebnis'] == 'abgebrochen'
    assert signal.Signals(number).name in journal['grund']
    assert not h.target.exists()
    assert {sig: signal.getsignal(sig) for sig in before} == before  # Handler zurückgestellt


class _HungUpStream(io.StringIO):
    """Terminal nach SIGHUP: jede Ausgabe scheitert mit EIO."""

    def __init__(self):
        super().__init__()
        self.broken = False

    def write(self, text):
        if self.broken:
            raise OSError(errno.EIO, 'Input/output error')
        return super().write(text)

    def flush(self):
        if self.broken:
            raise OSError(errno.EIO, 'Input/output error')


def test_hung_up_console_does_not_skip_restore_or_restart(tmp_path):
    h = Harness(tmp_path)
    out, err = _HungUpStream(), _HungUpStream()
    h.console = calibrate.Console(cli.Style(out, color=False), out=out, err=err)

    def record(args, progress):
        h.gsv.norm = [11, 22, 33]
        out.broken = err.broken = True
        raise KeyboardInterrupt('SIGHUP')

    h.deps.record = record
    assert h.run(yes=True) == calibrate.EXIT_ABORT
    assert h.gsv.norm == ORIGINAL_NORM
    assert h.actions() == ['stop', 'start']
    journal = json.loads((h.run_dir / 'lauf.json').read_text())
    assert journal['normierung_zurueckgestellt'] is True and journal['dienst_neu_gestartet'] is True
    assert 'SIGHUP' in journal['grund']


def test_cleanup_acts_before_any_output(tmp_path):
    h = Harness(tmp_path)
    events: list[str] = []

    class Spy(io.StringIO):
        def write(self, text):
            events.append('ausgabe')
            return super().write(text)

    out = Spy()
    h.console = calibrate.Console(cli.Style(out, color=False), out=out, err=out)
    opened = h.gsv.open

    def open_serial(port, baudrate, timeout):
        events.append('port')
        return opened(port, baudrate, timeout)

    def service(command):
        events.append(command[-2])
        return 0

    def record(args, progress):
        h.gsv.norm = [11, 22, 33]
        events.clear()
        raise KeyboardInterrupt

    h.deps.open_serial, h.deps.service_runner, h.deps.record = open_serial, service, record
    assert h.run(yes=True) == calibrate.EXIT_ABORT
    first_output = events.index('ausgabe')
    assert 'port' in events[:first_output] and 'start' in events[:first_output]
    assert h.gsv.norm == ORIGINAL_NORM
    text = out.getvalue()
    assert text.index('Abbruch (Strg+C)') < text.index('zweiter Versuch') < text.index('Dienst läuft')


def test_shielded_covers_sighup():
    with calibrate.shielded():
        assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN
        assert signal.getsignal(signal.SIGTERM) == signal.SIG_IGN
        assert signal.getsignal(signal.SIGINT) == signal.SIG_IGN


def test_open_serial_is_exclusive(monkeypatch):
    import serial

    seen = {}

    def fake(port, **kwargs):
        seen.update(kwargs, port=port)
        return object()

    monkeypatch.setattr(serial, 'Serial', fake)
    calibrate.open_serial('/dev/nichts', 38400, 0.5)
    assert seen['exclusive'] is True


def test_exclusive_open_refuses_second_opener():
    """pyserial ``exclusive=True`` (flock) wirkt auf einem Pseudo-Terminal:
    solange der Lesethread den Port hält, scheitert die Rückstellung beim
    Öffnen, statt Bytes einzustreuen."""
    import serial

    master, slave = os.openpty()
    try:
        first = serial.Serial(os.ttyname(slave), 38400, timeout=0.1, exclusive=True)
        try:
            with pytest.raises(serial.SerialException):
                serial.Serial(os.ttyname(slave), 38400, timeout=0.1, exclusive=True)
        finally:
            first.close()
    finally:
        os.close(master)
        os.close(slave)


# ------------------------------------------------------------------ Rückstellpunkt prüfen

@pytest.mark.parametrize('point, reason', [
    ({}, '„register“ fehlt'),
    ({'register': {'dpoint': {'daten': [1]}}}, 'register.norm.daten'),
    ({'register': {'norm': {'daten': [80, 27]}, 'dpoint': {'daten': [1]}}}, 'genau 3 Bytes'),
    ({'register': {'norm': {'daten': [80, 27, 228, 0]}, 'dpoint': {'daten': [1]}}}, 'genau 3 Bytes'),
    ({'register': {'norm': {'daten': [80, 27, 256]}, 'dpoint': {'daten': [1]}}}, '0…255'),
    ({'register': {'norm': {'daten': [80, -1, 228]}, 'dpoint': {'daten': [1]}}}, '0…255'),
    ({'register': {'norm': {'daten': [80, 27.0, 228]}, 'dpoint': {'daten': [1]}}}, '0…255'),
    ({'register': {'norm': {'daten': '80,27,228'}, 'dpoint': {'daten': [1]}}}, 'genau 3 Bytes'),
    ({'register': {'norm': {'daten': ORIGINAL_NORM}, 'dpoint': {'daten': [1, 2]}}}, 'genau 1 Byte'),
    ({'register': {'norm': {'daten': ORIGINAL_NORM}, 'dpoint': {'daten': [True]}}}, 'genau 1 Byte'),
    ({'register': {'norm': {'daten': ORIGINAL_NORM}, 'dpoint': {'daten': 1}}}, 'genau 1 Byte'),
])
def test_restore_from_file_refuses_invalid_point_without_sending(tmp_path, point, reason):
    h = Harness(tmp_path)
    path = tmp_path / 'rueckstellpunkt.json'
    path.write_text(json.dumps(point))
    assert calibrate.restore_from_file(path, calibrate.Options(yes=True), h.console, h.deps) == calibrate.EXIT_FAIL
    assert h.gsv.opened == 0 and h.gsv.writes == []
    assert 'kein gültiger Rückstellpunkt' in h.err.getvalue() and reason in h.err.getvalue()
    ok, detail = calibrate.restore_registers('/dev/x', 38400, point, tmp_path / 'log.jsonl', h.deps)
    assert ok is False and 'ungültig' in detail['error'] and h.gsv.opened == 0


def test_restore_point_problem_accepts_read_point_and_rejects_non_object():
    good = {'register': {'norm': {'daten': ORIGINAL_NORM}, 'dpoint': {'daten': ORIGINAL_DPOINT}}}
    assert calibrate.restore_point_problem(good) is None
    assert calibrate.restore_point_problem([1, 2, 3]) == 'kein JSON-Objekt'


# ------------------------------------------------------------------ Voraussetzungen

@pytest.mark.parametrize('change, reason', [
    ({'port_exists': lambda _p: False}, 'kein Adapter an /dev/ttyUSB0'),
    ({'usb_camera': lambda: None}, 'StreamCam 046d:0893 nicht gefunden'),
    ({'usb_camera': lambda: {'speed_mbps': 480}}, 'USB 2'),
    ({'collect': snapshot(state='running')}, 'gesperrt: Lauf aktiv'),
    ({'collect': snapshot(state='setup_running')}, 'Einrichtung läuft'),
    ({'collect': snapshot(diagnose=True)}, 'Diagnosekopie'),
    ({'storage': lambda a, p, f: ('nur 3 MiB frei', 1)}, 'nur 3 MiB frei'),
])
def test_preconditions_refuse_with_exit_3(tmp_path, change, reason):
    h = Harness(tmp_path, **change)
    assert h.run(yes=True) == calibrate.EXIT_BLOCKED
    assert reason in h.text
    assert h.services == [] and not (h.target.parent / 'runs').exists()


def test_precondition_no_telegrams(tmp_path):
    h = Harness(tmp_path, gsv=FakeGsv(telegrams=False))
    clock = iter(range(0, 1000))
    h.deps.monotonic = lambda: next(clock)
    assert h.run(yes=True) == calibrate.EXIT_BLOCKED
    assert 'keine GSV-Telegramme' in h.text
    assert h.gsv.writes == []  # Probe liest nur


def test_precondition_without_confirmed_setup(tmp_path):
    h = Harness(tmp_path)
    h.profile.unlink()
    assert h.run(yes=True) == calibrate.EXIT_BLOCKED
    assert 'keine bestätigte Einrichtung' in h.text


def test_precondition_unwritable_folder(tmp_path, monkeypatch):
    h = Harness(tmp_path)
    real_access = os.access
    monkeypatch.setattr(calibrate.os, 'access',
                        lambda path, mode: False if Path(path) == h.target.parent else real_access(path, mode))
    assert h.run(yes=True) == calibrate.EXIT_BLOCKED
    assert 'sudo picam kalibrieren' in h.text


def test_question_declined_changes_nothing(tmp_path):
    h = Harness(tmp_path, ask=lambda _prompt: 'n')
    assert h.run() == calibrate.EXIT_ABORT
    assert h.services == [] and not (h.target.parent / 'runs').exists()


def test_short_duration_refused(tmp_path):
    h = Harness(tmp_path)
    assert h.run(yes=True, duration_s=10) == calibrate.EXIT_BLOCKED


def test_console_hooks_receive_checks_plan_confirmation_and_step_keys(tmp_path):
    h = Harness(tmp_path)
    events = []

    class Reporter:
        def __call__(self, elapsed, total):
            events.append((elapsed, total))

        def finish(self):
            events.append('progress_finished')

    class Console(calibrate.Console):
        def checks(self, pre):
            assert pre.service_running and not pre.problems
            events.append('checks')

        def plan(self, title, lines):
            assert 'Werkbank' in title and any('Normierungssprünge' in line for line in lines)
            self.plan_lines = lines
            events.append('plan')

        def confirm(self, title, lines, expected, *, deps):
            assert title == 'Jetzt kalibrieren?' and lines == self.plan_lines and expected is None
            events.append('confirm')
            return True

        def step(self, text, *, key=None):
            events.append(key)

        def progress(self, tty):
            assert not tty
            events.append('progress')
            return Reporter()

    h.console = Console(h.console.style, out=h.out, err=h.err)
    h.deps.ask = lambda _prompt: pytest.fail('Terminalrückfrage trotz Console.confirm')
    assert h.run() == calibrate.EXIT_OK
    assert events == [
        'checks', 'plan', 'confirm', 'dienst_stop', 'kamera', 'rueckstellpunkt', 'aufnahme',
        'progress', (60.0, 180.0), (180.0, 180.0), 'progress_finished',
        'normierung', 'dienst_start', 'pruefen', 'auswertung', 'bauen',
    ]
    result = h.console.last_result
    assert result.outcome == 'installiert' and result.run_dir == h.run_dir
    assert result.norm_restored and result.service_restarted
    assert dict(result.metrics)['Versatz δ'] == '97,0 ms'
    assert dict(result.metrics)['Schutzabstand M'] == '271,6 ms'


@pytest.mark.parametrize('interactive', [True, False])
def test_system_service_sudo_only_uses_noninteractive_flag_when_requested(tmp_path, monkeypatch, interactive):
    h = Harness(tmp_path, service_interactive=interactive)
    h.instance = replace(h.instance, kind='system', scope='system')
    monkeypatch.setattr(calibrate.os, 'geteuid', lambda: 1000)
    assert calibrate.sudo_needed(h.instance, snapshot()(h.instance))
    assert not calibrate.sudo_needed(h.instance, snapshot(service=probes.OFF)(h.instance))
    assert not calibrate.sudo_needed(h.instance, snapshot(state='running')(h.instance))
    user_instance = replace(h.instance, kind='user', scope='user')
    assert not calibrate.sudo_needed(user_instance, snapshot()(user_instance))
    assert h.run(yes=True) == calibrate.EXIT_OK
    prefix = ['sudo'] if interactive else ['sudo', '-n']
    assert h.services == [[*prefix, 'systemctl', action, INSTALLED_UNIT] for action in ('stop', 'start')]
    assert ('sudo fragt' in h.text) == interactive


def test_sudo_cached_uses_noninteractive_probe(monkeypatch):
    calls = []
    monkeypatch.setattr(probes, 'run_command', lambda argv: (calls.append(argv) or 0, '', ''))
    assert calibrate.sudo_cached()
    assert calls == [['sudo', '-n', 'true']]


def test_sudo_validate_passes_password_only_over_stdin():
    password = 'sudu-Test $ ; ä'

    def run(argv, **kwargs):
        assert argv == ['sudo', '-S', '-p', '', '-v']
        assert kwargs.pop('input') == password + '\n'
        assert kwargs.pop('timeout') > 0
        assert kwargs == {'text': True, 'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL, 'check': False}
        return subprocess.CompletedProcess(argv, 0)

    assert calibrate.sudo_validate(password, run=run) == (True, '')

    def timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs['timeout'], output=password, stderr=password)

    ok, message = calibrate.sudo_validate(password, run=timeout)
    assert not ok and 'Zeitlimit' in message and password not in message


# ------------------------------------------------------------------ Prüfen und Importieren

def make_file(path: Path, camera='046d:0893') -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schema_version': 1, 'camera_usb_id': camera, 'guard_margin_ms': 325.9,
                                'display_offset_ms': 89.6, 'measured_at_utc': '2026-09-29T12:00:00+00:00',
                                'sources': []}))
    return path


def test_check_file_valid_invalid_and_other_camera(tmp_path):
    h = Harness(tmp_path)
    make_file(h.target)
    assert calibrate.check_file(h.instance, None, h.console) == calibrate.EXIT_OK
    assert '325,9 ms' in h.text and 'aktive Kalibrierung' in h.text
    broken = tmp_path / 'kaputt.json'
    broken.write_text('{"schema_version": 1}')
    assert calibrate.check_file(h.instance, broken, h.console) == calibrate.EXIT_FAIL
    other = make_file(tmp_path / 'fremd.json', camera='1234:5678')
    assert calibrate.check_file(h.instance, other, h.console) == calibrate.EXIT_FAIL
    assert '1234:5678' in h.text


def test_import_requires_typed_word_and_writes_note(tmp_path):
    h = Harness(tmp_path, ask=lambda _prompt: 'ja')
    source = make_file(tmp_path / 'anderer-pi' / 'timing-streamcam.json')
    assert calibrate.import_file(h.instance, source, h.console, h.deps) == calibrate.EXIT_ABORT
    assert not h.target.exists()
    assert 'nur für genau den Aufbau' in h.text
    h.deps.ask = lambda _prompt: 'importieren'
    h.target.write_text('{"alt": 1}')
    assert calibrate.import_file(h.instance, source, h.console, h.deps) == calibrate.EXIT_OK
    assert h.target.read_bytes() == source.read_bytes()
    note = json.loads(calibrate.import_note_path(h.target).read_text())
    assert note['quelle'] == str(source.resolve()) and note['sha256'] == calibrate.sha256_file(source)
    assert note['importiert_am_utc'] == NOW.isoformat()
    backups = list((h.target.parent / 'runs').glob('*-import/vorherige-kalibrierung.json'))
    assert backups and json.loads(backups[0].read_text()) == {'alt': 1}


def test_import_refuses_invalid_and_active_run(tmp_path):
    h = Harness(tmp_path, ask=lambda _prompt: 'importieren')
    broken = tmp_path / 'kaputt.json'
    broken.write_text('[]')
    assert calibrate.import_file(h.instance, broken, h.console, h.deps) == calibrate.EXIT_FAIL
    other = make_file(tmp_path / 'fremd.json', camera='1234:5678')
    assert calibrate.import_file(h.instance, other, h.console, h.deps) == calibrate.EXIT_FAIL
    h.deps.collect = snapshot(state='running')
    good = make_file(tmp_path / 'gut.json')
    assert calibrate.import_file(h.instance, good, h.console, h.deps) == calibrate.EXIT_BLOCKED
    assert not h.target.exists()


def test_import_without_terminal_needs_yes(tmp_path):
    h = Harness(tmp_path, isatty=lambda: False)
    source = make_file(tmp_path / 'gut.json')
    assert calibrate.import_file(h.instance, source, h.console, h.deps) == calibrate.EXIT_ABORT
    assert calibrate.import_file(h.instance, source, h.console, h.deps, yes=True) == calibrate.EXIT_OK


def test_worker_can_check_and_confirm_import(tmp_path):
    h = Harness(tmp_path)
    source = make_file(tmp_path / 'import.json')
    prompts = []

    class Console(calibrate.Console):
        def confirm(self, title, lines, expected, *, deps):
            prompts.append((title, lines, expected))
            return True

    console = Console(h.console.style, out=h.out, err=h.err)
    results = []

    def run():
        calibrate.check_file(h.instance, source, console)
        results.append(console.last_result)
        calibrate.import_file(h.instance, source, console, h.deps)
        results.append(console.last_result)

    worker = threading.Thread(target=run)
    worker.start()
    worker.join(5)
    assert [result.outcome for result in results] == ['gueltig', 'importiert']
    assert dict(results[0].metrics)['Datei'] == str(source)
    assert dict(results[1].metrics)['Datei'] == str(h.target)
    assert prompts == [('Kalibrierung importieren?', [calibrate.IMPORT_WARNING, f'Ziel: {h.target}'], 'importieren')]
    assert h.target.read_bytes() == source.read_bytes()


def test_restore_from_file(tmp_path):
    h = Harness(tmp_path)
    point = tmp_path / 'rueckstellpunkt.json'
    point.write_text(json.dumps({'register': {'norm': {'daten': ORIGINAL_NORM}, 'dpoint': {'daten': [1]}}}))
    h.gsv.norm = [5, 5, 5]
    options = calibrate.Options(yes=True)
    assert calibrate.restore_from_file(point, options, h.console, h.deps) == calibrate.EXIT_OK
    assert h.gsv.norm == ORIGINAL_NORM
    h.gsv.stuck, h.gsv.norm = True, [5, 5, 5]
    assert calibrate.restore_from_file(point, options, h.console, h.deps) == calibrate.EXIT_FAIL


# ------------------------------------------------------------------ fact_calibration

def test_fact_calibration_validates_file_and_camera(tmp_path):
    h = Harness(tmp_path)
    fact = probes.fact_calibration(h.instance)
    assert fact.level == probes.FAIL and fact.value == 'fehlt' and fact.command == 'picam kalibrieren'
    h.target.write_text('{"schema_version": 1}')
    fact = probes.fact_calibration(h.instance)
    assert fact.level == probes.FAIL and fact.value == 'ungültig' and 'fehlende Felder' in dict(fact.detail)['Fehler']
    make_file(h.target)
    fact = probes.fact_calibration(h.instance, now=lambda: datetime(2026, 10, 9, 12, tzinfo=UTC).timestamp())
    assert fact.level == probes.OK and fact.value == 'gültig'
    assert dict(fact.detail)['Schutzabstand M'] == '326 ms' and dict(fact.detail)['Alter'] == '10 Tage'
    fact = probes.fact_calibration(h.instance, camera_id='1234:5678')
    assert fact.level == probes.FAIL and fact.value == 'andere Kamera'
    calibrate.import_note_path(h.target).write_text('{}')
    assert 'Herkunft' in dict(probes.fact_calibration(h.instance).detail)


def test_collect_passes_live_camera_id(tmp_path):
    h = Harness(tmp_path)
    make_file(h.target, camera='1234:5678')
    live = {'state': 'idle', 'camera': {'source': {'usb_id': '1234:5678'}}}

    def run(command, timeout=5.0):
        return (0, 'ActiveState=active\n', '') if 'show' in command else (1, '', '')

    snap = probes.collect(h.instance, run=run, live_source=lambda: live, bridge_source=lambda: None)
    assert snap.facts['kalibrierung'].level == probes.OK


# ------------------------------------------------------------------ CLI

def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    h = Harness(tmp_path)
    monkeypatch.setattr(cli, 'discover', lambda _config=None: h.instance)
    assert cli.main(['kalibrieren', '--pruefen']) == calibrate.EXIT_FAIL
    make_file(h.target)
    assert cli.main(['kalibrieren', '--pruefen']) == calibrate.EXIT_OK
    assert cli.main(['kalibrieren', '--pruefen', str(tmp_path / 'fehlt.json')]) == calibrate.EXIT_FAIL
    assert cli.main(['kalibrieren', '--pruefen', 'a', '--import', 'b']) == cli.EXIT_USAGE
    calls = []
    monkeypatch.setattr(calibrate, 'calibrate', lambda instance, options, console: calls.append(options) or 3)
    assert cli.main(['kalibrieren', '--dauer', '180', '--yes']) == calibrate.EXIT_BLOCKED
    assert calls[0].duration_s == 180 and calls[0].yes and calls[0].port == '/dev/ttyUSB0'


def test_setup_calibration_step_offers_choices(tmp_path, monkeypatch, capsys):
    h = Harness(tmp_path)
    style = cli.Style(io.StringIO(), color=False)
    ran = []
    monkeypatch.setattr(calibrate, 'adapter_present', lambda port=None: True)
    answers = iter(['k'])
    assert cli.setup_calibration(h.instance, style, ask=lambda _p: next(answers),
                                 run=lambda argv: ran.append(argv) or 0, interactive=True) == 0
    assert ran[-1] == ['kalibrieren']
    answers = iter(['p', str(tmp_path / 'woanders.json')])
    cli.setup_calibration(h.instance, style, ask=lambda _p: next(answers), run=lambda argv: ran.append(argv) or 0,
                          interactive=True)
    assert ran[-1] == ['kalibrieren', '--import', str(tmp_path / 'woanders.json')]
    answers = iter(['p', ''])
    cli.setup_calibration(h.instance, style, ask=lambda _p: next(answers), run=lambda argv: ran.append(argv) or 0,
                          interactive=True)
    assert ran[-1] == ['kalibrieren', '--pruefen', h.instance.calibration]
    assert cli.setup_calibration(h.instance, style, ask=lambda _p: 's', run=lambda argv: ran.append(argv) or 0,
                                 interactive=True) == cli.EXIT_WARN
    monkeypatch.setattr(calibrate, 'adapter_present', lambda port=None: False)
    count = len(ran)
    cli.setup_calibration(h.instance, style, ask=lambda _p: 'k', run=lambda argv: ran.append(argv) or 0,
                          interactive=True)
    assert len(ran) == count  # ohne Adapter kein Messen
    assert 'Adapter stecken' in capsys.readouterr().out


def test_record_and_offset_scripts_are_thin_wrappers():
    root = Path(__file__).parents[1] / 'scripts'
    for name, module in (('sync-record.py', 'dispread.calibration import record'),
                         ('display-offset.py', 'dispread.calibration import offset'),
                         ('timing-calibration.py', 'dispread.calibration.build import')):
        text = (root / name).read_text()
        assert module in text and len(text.splitlines()) < 80, name


# ------------------------------------------------------------------ Konsole (Tab Kamera)

def sync(coroutine_function):
    import asyncio
    import functools

    @functools.wraps(coroutine_function)
    def wrapper(*args, **kwargs):
        asyncio.run(coroutine_function(*args, **kwargs))
    return wrapper


def _app(state='idle', **instance_changes):
    import dataclasses

    import admin_fakes

    instance = dataclasses.replace(admin_fakes.INSTANCE,
                                   calibration='/var/lib/picam/calibration/timing-streamcam.json',
                                   **instance_changes)
    return admin_fakes.make_app(state, instance=instance)


async def _kamera_actions(app, pilot):
    await pilot.pause(0.4)
    await pilot.press('4')
    await pilot.pause(0.4)
    return {action.key: action for action in app.view().actions()}


@sync
async def test_tui_calibration_actions_blocked_states(monkeypatch):
    monkeypatch.setattr(calibrate, 'adapter_present', lambda port=None: True)
    app = _app('run')
    async with app.run_test(size=(100, 30)) as pilot:
        actions = await _kamera_actions(app, pilot)
        assert 'Lauf aktiv' in actions['m'].blocked
        assert actions['p'].blocked == 'Lauf oder Einrichtung aktiv'
    app = _app('setup')
    async with app.run_test(size=(100, 30)) as pilot:
        assert 'Einrichtung läuft' in (await _kamera_actions(app, pilot))['m'].blocked
    app = _app('idle', kind='dev', root='/home/x/picam-ai')
    async with app.run_test(size=(100, 30)) as pilot:
        assert (await _kamera_actions(app, pilot))['m'].blocked == 'nur für eine installierte Werkbank mit Dienst'
    monkeypatch.setattr(calibrate, 'adapter_present', lambda port=None: False)
    app = _app('idle')
    async with app.run_test(size=(100, 30)) as pilot:
        actions = await _kamera_actions(app, pilot)
        assert actions['m'].blocked == 'kein USB-RS232-Adapter an /dev/ttyUSB0'
        assert actions['p'].blocked is None
        calls = []
        app.run_cli = lambda argv, title: calls.append(argv) or 0
        await pilot.press('m')
        await pilot.pause(0.3)
        assert calls == []


@sync
async def test_tui_calibrate_and_import_run_cli(monkeypatch):
    from dispread.admin.ui import AskScreen

    monkeypatch.setattr(calibrate, 'adapter_present', lambda port=None: True)
    app = _app('idle')
    async with app.run_test(size=(100, 30)) as pilot:
        actions = await _kamera_actions(app, pilot)
        assert actions['m'].blocked is None and actions['p'].blocked is None
        calls = []
        app.run_cli = lambda argv, title: calls.append(argv) or 0
        await pilot.press('m')
        await pilot.pause(0.4)
        assert calls == [['kalibrieren']]
        await pilot.press('p')
        await pilot.pause(0.4)
        assert isinstance(app.screen, AskScreen)
        await pilot.click('#ok')
        await pilot.pause(0.4)
        assert calls[-1] == ['kalibrieren', '--pruefen', '/var/lib/picam/calibration/timing-streamcam.json']
        await pilot.press('p')
        await pilot.pause(0.4)
        field = app.screen.query_one('#ask-input')
        field.value = '/home/labor/timing-anderer-pi.json'
        await pilot.click('#ok')
        await pilot.pause(0.4)
        assert calls[-1] == ['kalibrieren', '--import', '/home/labor/timing-anderer-pi.json']
