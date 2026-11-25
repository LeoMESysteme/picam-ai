"""``picam kalibrieren``: Timing-Kalibrierung bei der Inbetriebnahme.

Produktive Pis haben kein RS232. Der Versatz Telegramm -> Anzeige (δ) und der
Schutzabstand M (``timing-streamcam.json``) lassen sich aber nur mit den
GSV-Telegrammen messen. Deshalb wird einmal bei der Inbetriebnahme mit einem
vorübergehend gesteckten USB-RS232-Adapter (PL2303, ``/dev/ttyUSB0``, 38400 8N1)
gemessen, vollständig aus picam heraus:

1. Voraussetzungen prüfen (Adapter mit Telegrammen, StreamCam an USB 3,
   bestätigte Einrichtung, kein Lauf/keine Einrichtung/keine Diagnosekopie,
   Schreibrechte, Platz). Fehlt etwas: Exit 3 mit Grund, nichts geändert.
2. Plan zeigen und fragen (``--yes`` überspringt die Frage).
3. Werkbank-Dienst stoppen (gleiche Sperre wie ``picam stop``), warten, bis
   die Kamera frei ist.
4. Normierung und Dezimalpunkt des GSV lesen (Rückstellpunkt), dann
   aufnehmen (``dispread.calibration.record``) mit Normierungssprüngen über
   ``set norm``/``set dpoint``. Danach wird die Rückstellung geprüft und bei
   Bedarf ein zweites Mal geschrieben; scheitert sie, steht das laut da.
5. Dienst wieder starten (auf jedem Ausstiegspfad, auch bei Strg+C) und auf
   HTTPS warten.
6. Auswerten (``dispread.calibration.offset``), Kalibrierung in eine
   Zwischendatei bauen, mit ``load_calibration`` und der Kamera-USB-ID prüfen
   und erst dann atomar an den konfigurierten Ort legen. Ohne erkannte
   Population oder bei ungültigem Ergebnis wird dort NICHTS geschrieben.

Rohaufnahme, Bericht, Rückstellpunkt und Protokoll bleiben unter
``<Kalibrierordner>/runs/<Zeitstempel>/``. Nichts wird erfunden oder still von
einem anderen Pi übernommen: ``--import`` ist ein ausdrücklicher, bestätigter
Schritt mit Herkunftsnotiz. Ohne gültige Kalibrierung bleibt der Laufstart
gesperrt (``dispread.live.session.build_live_pipeline``).
"""

from __future__ import annotations

import contextlib
import getpass
import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from dispread.camera_settings import STREAMCAM_USB_ID
from dispread.gsv2as_serial import REFERENCE_BAUDRATE, REFERENCE_PORT
from dispread.timing_calibration import TimingCalibration, load_calibration

from . import probes
from .instance import Instance

EXIT_OK, EXIT_FAIL, EXIT_BLOCKED, EXIT_ABORT = 0, 1, 3, 130

#: Aufnahmedauer: Vorgabe und Untergrenze. Die belegten Kalibrieraufnahmen
#: `sc3-cal-*` (docs/VALIDATION.md, 2026-09-29) dauerten 168-180 s; die Vorgabe
#: folgt ihnen, damit die Auswertung genug Ereignisse findet (mind. 3 je
#: Population). Kürzer nur mit ``--dauer`` (Untergrenze unten).
DEFAULT_DURATION_S = 180.0
MIN_DURATION_S = 60.0
#: Haltezeit je Normierungsstufe, wie bei `sc3-cal-b` (7 s).
DEFAULT_HOLD_S = 7.0
#: Zuschlag je Schritt und fest wie bei der Ernte (`harvest.py`:
#: Dauer = Schritte * (Haltezeit + 2) + 10).
STEP_OVERHEAD_S = 2.0
FIXED_OVERHEAD_S = 10.0
#: Telegrammprobe vor dem Start: so viele Zeilen innerhalb so vieler Sekunden
#: (die erste Zeile kann angeschnitten sein).
TELEGRAM_PROBE_S = 6.0
TELEGRAM_MIN_LINES = 3
CAMERA_FREE_TIMEOUT_S = 30.0
CALIBRATION_FILE = 'timing-streamcam.json'
IMPORT_CONFIRM_WORD = 'importieren'
IMPORT_WARNING = ('Eine Timing-Kalibrierung gilt nur für genau den Aufbau, an dem sie gemessen wurde: dieselbe '
                  'Kamera mit denselben Einstellungen, derselbe Messverstärker und dieselbe Anzeige, dieselbe '
                  'Aufstellung. Eine woanders gemessene Datei ist hier nicht nachgemessen; δ und M können '
                  'abweichen. Nur übernehmen, wenn der Aufbau nachweislich gleich ist – sonst mit Adapter '
                  'neu kalibrieren (picam kalibrieren).')


class CalibrationError(RuntimeError):
    """Kalibrierung abgebrochen; der Grund steht in der Meldung."""


# ------------------------------------------------------------------ Hilfen

def adapter_present(port: str = REFERENCE_PORT) -> bool:
    """USB-RS232-Adapter gesteckt? Nur der Gerätepfad, ohne Öffnen."""
    return Path(port).exists()


def import_note_path(calibration: Path) -> Path:
    """Herkunftsnotiz einer importierten Kalibrierung (liegt daneben)."""
    calibration = Path(calibration)
    return calibration.with_name(calibration.stem + '.import.json')


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_file(path: Path, expected_camera: str = STREAMCAM_USB_ID) -> tuple[TimingCalibration | None, str | None]:
    """Kalibrierdatei laden und gegen die Kamera prüfen: (Kalibrierung, None) oder (…, Grund)."""
    try:
        calibration = load_calibration(Path(path))
    except ValueError as error:
        return None, str(error)
    if calibration.camera_usb_id != expected_camera:
        return calibration, (f'Kalibrierung gilt für Kamera {calibration.camera_usb_id}, '
                             f'angeschlossen/erwartet ist {expected_camera}')
    return calibration, None


def _local(stamp: str) -> str:
    try:
        return datetime.fromisoformat(str(stamp).replace('Z', '+00:00')).astimezone().strftime('%d.%m.%Y %H:%M')
    except ValueError:
        return str(stamp)


def describe(calibration: TimingCalibration, path: Path) -> list[tuple[str, str]]:
    rows = [('Datei', str(path)), ('Kamera', calibration.camera_usb_id),
            ('Versatz δ', f'{calibration.display_offset_ms:.1f} ms'.replace('.', ',')),
            ('Schutzabstand M', f'{calibration.guard_margin_ms:.1f} ms'.replace('.', ',')),
            ('Gemessen', _local(calibration.measured_at_utc)),
            ('Quellen', str(len(calibration.sources)))]
    try:
        rows.append(('SHA-256', sha256_file(path)[:16] + '…'))
    except OSError:
        pass
    note = import_note_path(path)
    if note.is_file():
        try:
            data = json.loads(note.read_text(encoding='utf-8'))
            rows.append(('Herkunft', f"importiert aus {data.get('quelle', '?')} "
                                     f"am {_local(data.get('importiert_am_utc', ''))}"))
        except (OSError, ValueError, AttributeError):
            rows.append(('Herkunft', 'importiert (Notiz unlesbar)'))
    return rows


def _existing_parent(path: Path) -> Path:
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _user() -> str:
    return os.environ.get('SUDO_USER') or getpass.getuser()


def _service_running(snapshot: probes.Snapshot) -> bool:
    fact = snapshot.facts.get('dienst')
    return fact is not None and fact.level in (probes.OK, probes.WARN)


def _service_up(instance: Instance, deps: Deps) -> bool:
    try:
        return _service_running(deps.collect(instance, include_setup=False))
    except Exception:  # noqa: BLE001 - unbekannt: lieber Start versuchen
        return False


def _adopt_owner(path: Path, reference: Path, recursive: bool = True) -> None:
    """Als root geschriebene Dateien dem Eigentümer des Datenordners geben."""
    if os.geteuid() != 0:
        return
    info = Path(reference).stat()
    targets = [Path(path)]
    if recursive and Path(path).is_dir():
        targets += list(Path(path).rglob('*'))
    for target in targets:
        with contextlib.suppress(OSError):
            os.chown(target, info.st_uid, info.st_gid, follow_symlinks=False)


def install_bytes(data: bytes, target: Path) -> None:
    """``data`` atomar nach ``target`` schreiben: Zwischendatei im Zielordner,
    fsync, ``os.replace``. Rechte wie der Ordner (0600 bei privatem Ordner),
    als root mit dessen Eigentümer."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    folder = target.parent.stat()
    mode = 0o644 if folder.st_mode & 0o077 else 0o600
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        if os.geteuid() == 0:
            os.chown(temporary, folder.st_uid, folder.st_gid)
        os.replace(temporary, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    with contextlib.suppress(OSError):
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def install_atomically(source: Path, target: Path) -> None:
    """Datei ``source`` atomar nach ``target`` kopieren (siehe ``install_bytes``)."""
    install_bytes(Path(source).read_bytes(), target)


#: Signale, die ``picam kalibrieren`` wie Strg+C behandelt: SIGTERM (Dienst-
#: oder Sitzungsende) und SIGHUP (SSH-Verbindung getrennt). Ohne Handler
#: beendeten sie den Prozess sofort – ohne Rückstellung der Normierung und
#: ohne Neustart der Werkbank.
ABORT_SIGNALS = {signal.SIGTERM: 'SIGTERM', signal.SIGHUP: 'SIGHUP'}
ABORT_TEXT = {'SIGTERM': 'Abbruch (SIGTERM)', 'SIGHUP': 'Abbruch (Verbindung getrennt, SIGHUP)',
              'konsole': 'Abbruch in der Konsole'}


class _ConsoleAbort(KeyboardInterrupt):
    """Kooperativer Abbruch über Deps.cancelled."""


def _check_cancelled(deps: Deps) -> None:
    if deps.cancelled():
        raise _ConsoleAbort('konsole')


def _raise_abort(signum, _frame) -> None:
    raise KeyboardInterrupt(ABORT_SIGNALS.get(signum, 'SIGTERM'))


@contextlib.contextmanager
def abort_on_signals():
    """SIGTERM und SIGHUP für die Dauer des Ablaufs in einen KeyboardInterrupt
    (Argument: Signalname) verwandeln, damit derselbe Aufräumpfad wie bei
    Strg+C läuft. Im Hauptthread gelten danach wieder die vorherigen Handler.
    In Worker-Threads bleibt die Signalbehandlung beim Hauptthread."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = {}
    try:
        for number in ABORT_SIGNALS:
            previous[number] = signal.signal(number, _raise_abort)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


@contextlib.contextmanager
def shielded():
    """Strg+C, SIGTERM und SIGHUP während des Aufräumens (Rückstellung,
    Dienststart) im Hauptthread ignorieren, damit es nicht halb abbricht."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = {}
    try:
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[number] = signal.signal(number, signal.SIG_IGN)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


# ------------------------------------------------------------------ Quellen (in Tests ersetzbar)

def open_serial(port: str, baudrate: int, timeout: float):
    """Port exklusiv öffnen (flock): hält ihn noch ein anderer Öffner mit
    ``exclusive`` – etwa der Lesethread der Aufnahme, der gerade zurückstellt –,
    scheitert das Öffnen, statt Bytes ineinanderlaufen zu lassen."""
    import serial

    return serial.Serial(port, baudrate=baudrate, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                         stopbits=serial.STOPBITS_ONE, timeout=timeout, xonxoff=False, rtscts=False, dsrdtr=False,
                         exclusive=True)


def camera_holders(proc: Path = Path('/proc')) -> list[str]:
    """Prozesse, die den Bildknoten der StreamCam offen haben (``pid (name)``)."""
    from dispread.frames.uvc_source import UvcError, find_uvc_device

    try:
        device = os.path.realpath(find_uvc_device(STREAMCAM_USB_ID))
    except UvcError as error:
        raise CalibrationError(f'StreamCam nicht gefunden: {error}') from error
    holders = []
    for entry in proc.glob('[0-9]*'):
        try:
            links = list((entry / 'fd').iterdir())
        except OSError:
            continue
        for link in links:
            try:
                if os.path.realpath(link) == device:
                    name = (entry / 'comm').read_text().strip()
                    holders.append(f'{entry.name} ({name})')
                    break
            except OSError:
                continue
    return holders


def record_args(argv: list[str]):
    from dispread.calibration import record

    return record.parse_args(argv)


def run_record(args, progress, *, out=None, err=None) -> int:
    from dispread.calibration import record

    return record.run(args, progress=progress, out=out, err=err)


def run_analysis(recording: Path, profile: Path, out_dir: Path) -> dict:
    """Offset-Analyse synchron im aufrufenden Thread ausführen.

    Die Analyse bietet keinen Abbruch-Callback. Ein Konsolenabbruch wird
    vor und nach diesem Aufruf berücksichtigt. Strg+C wirkt im Hauptthread.
    """
    from dispread.calibration import offset

    args = offset.build_arg_parser().parse_args([str(recording), '--profile', str(profile), '--out', str(out_dir)])
    return offset.run(args)


def storage_problem(args, profile: Path, data_folder: Path) -> tuple[str | None, int]:
    """(Grund oder None, geschätzte Bytes der Aufnahme)."""
    from dispread.calibration import record
    from dispread.camera_settings import load_camera_settings

    need = record._estimate_staging_need(args, load_camera_settings(profile))
    problem = record._check_staging_capacity(args.staging_root, need)
    if problem:
        return problem, need['files_bytes']
    free = shutil.disk_usage(_existing_parent(data_folder)).free
    if need['files_bytes'] > free:
        return (f'{data_folder}: geschätzt {need["files_bytes"] >> 20} MiB nötig, nur {free >> 20} MiB frei.',
                need['files_bytes'])
    return None, need['files_bytes']


@dataclass
class Deps:
    """Seiteneffekte von ``picam kalibrieren`` – in Tests ersetzt."""

    collect: Callable[..., probes.Snapshot] = probes.collect
    usb_camera: Callable[[], dict | None] = probes._usb_camera
    port_exists: Callable[[str], bool] = adapter_present
    open_serial: Callable[..., Any] = open_serial
    camera_holders: Callable[[], list[str]] = camera_holders
    service_runner: Callable[[list[str]], int] | None = None
    recheck: Callable[[], str | None] | None = None
    wait_ready: Callable[[Instance], bool] | None = None
    record_args: Callable[[list[str]], Any] = record_args
    record: Callable[[Any, Callable[[float, float], None]], int] = run_record
    analyse: Callable[[Path, Path, Path], dict] = run_analysis
    storage: Callable[[Any, Path, Path], tuple[str | None, int]] = storage_problem
    staging_root: Path | None = None
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    sleep: Callable[[float], None] = time.sleep
    monotonic: Callable[[], float] = time.monotonic
    ask: Callable[[str], str] = input
    isatty: Callable[[], bool] = lambda: sys.stdin.isatty()
    out: Any = None
    err: Any = None
    cancelled: Callable[[], bool] = lambda: False
    service_interactive: bool = True


@dataclass
class Options:
    duration_s: float = DEFAULT_DURATION_S
    hold_s: float = DEFAULT_HOLD_S
    port: str = REFERENCE_PORT
    baudrate: int = REFERENCE_BAUDRATE
    profile: Path | None = None
    seed: int | None = None
    yes: bool = False

    def for_instance(self, instance: Instance) -> Options:
        # The existing CLI passes the historical default even when --port
        # was omitted. Explicit non-default paths keep their override.
        if self.port in (None, REFERENCE_PORT):
            return replace(self, port=instance.reference_port)
        return self


@dataclass
class Check:
    label: str
    ok: bool
    text: str


@dataclass
class Preflight:
    checks: list[Check] = field(default_factory=list)
    snapshot: probes.Snapshot | None = None
    service_running: bool = False
    profile: Path | None = None
    profile_info: dict = field(default_factory=dict)
    record_argv: list[str] = field(default_factory=list)
    schedule: list[float] = field(default_factory=list)
    seed: int = 0
    estimate_bytes: int = 0

    @property
    def problems(self) -> list[Check]:
        return [check for check in self.checks if not check.ok]


@dataclass(frozen=True)
class Result:
    outcome: str
    exit_code: int
    reason: str | None = None
    run_dir: Path | None = None
    metrics: tuple[tuple[str, str], ...] = ()
    norm_restored: bool | None = None
    service_restarted: bool | None = None


class ProgressReporter(Protocol):
    def __call__(self, elapsed: float, total: float) -> None: ...

    def finish(self) -> None: ...


StepKey = Literal['dienst_stop', 'kamera', 'rueckstellpunkt', 'aufnahme', 'normierung',
                  'dienst_start', 'pruefen', 'auswertung', 'bauen']


class Console:
    """Fortschrittsausgabe mit den Zeichen von ``picam`` (Style aus cli)."""

    def __init__(self, style, out=None, err=None):
        self.style = style
        self.out = out or sys.stdout
        self.err = err or sys.stderr
        self.last_result: Result | None = None

    def write(self, data: str, stream=None) -> None:
        """Roh schreiben. Nach einem Verbindungsabbruch (SIGHUP: Terminal weg,
        EIO; Pipe zu: EPIPE) wirft eine Ausgabe nicht mehr – sonst bräche sie
        das Aufräumen (Rückstellung, Dienststart) ab."""
        stream = stream or self.out
        try:
            stream.write(data)
            stream.flush()
        except (OSError, ValueError):
            pass

    def line(self, text: str = '', stream=None) -> None:
        self.write(self.style.text(text) + '\n', stream)

    def mark(self, level: str, text: str, stream=None) -> None:
        self.line(f'{self.style.symbol(level)} {text}', stream)

    def step(self, text: str, *, key: StepKey | None = None) -> None:
        self.line()
        self.line(self.style.bold(text))

    def progress(self, tty: bool) -> ProgressReporter:
        return Progress(self, tty)

    def checks(self, pre: Preflight) -> None:
        width = max((len(check.label) for check in pre.checks), default=0)
        for check in pre.checks:
            self.mark(probes.OK if check.ok else probes.FAIL, f'{check.label:<{width}}  {check.text}')

    def plan(self, title: str, lines: list[str]) -> None:
        self.line()
        self.line(self.style.bold(title))
        for line in lines:
            self.line(line)

    def confirm(self, title: str, lines: list[str], expected: str | None, *, deps: Deps) -> bool:
        """``expected=None`` steht für Ja/Nein, sonst gilt das genaue Bestätigungswort."""
        prompt = f'\n{title} [j/N] ' if expected is None else f'Tippe „{expected}“ zum Übernehmen: '
        try:
            answer = deps.ask(prompt).strip()
        except EOFError:
            return False
        return answer.lower() in ('j', 'ja', 'y', 'yes') if expected is None else answer == expected

    def loud(self, lines: list[str]) -> None:
        bar = '!' * 72
        self.line(self.style.paint(bar, '31;1'), self.err)
        for text in lines:
            self.line(self.style.paint(text, '31;1'), self.err)
        self.line(self.style.paint(bar, '31;1'), self.err)


def _complete(console: Console, outcome: str, code: int, *, reason: str | None = None, **details) -> int:
    console.last_result = Result(outcome, code, reason=reason, **details)
    return code


class DeferredConsole(Console):
    """Merkt sich Ausgaben, statt sie zu schreiben; ``replay`` gibt sie
    danach in derselben Reihenfolge auf der echten Konsole aus. Im Aufräumen
    laufen Rückstellung und Dienststart so vor jeder Konsolenausgabe.
    ``mark`` und ``loud`` werden als solche aufgehoben und an der echten Konsole
    aufgerufen (eine Oberfläche zeigt einen Alarm anders als eine Zeile)."""

    def __init__(self, console: Console):
        super().__init__(console.style, console.out, console.err)
        self.target = console
        self.events: list[tuple] = []

    def line(self, text: str = '', stream=None) -> None:
        self.events.append(('line', stream is self.err, text))

    def mark(self, level: str, text: str, stream=None) -> None:
        self.events.append(('mark', stream is self.err, level, text))

    def loud(self, lines: list[str]) -> None:
        self.events.append(('loud', False, list(lines)))

    def replay(self) -> None:
        target = self.target
        for kind, to_err, *args in self.events:
            stream = target.err if to_err else None
            if kind == 'line':
                target.line(args[0], stream)
            elif kind == 'mark':
                target.mark(args[0], args[1], stream)
            else:
                target.loud(args[0])
        self.events.clear()


class Progress:
    """Balken mit verstrichener Zeit (Terminal) oder eine Zeile je 10 s."""

    WIDTH = 30

    def __init__(self, console: Console, tty: bool):
        self.console, self.tty, self.last = console, tty, -10.0

    def __call__(self, elapsed: float, total: float) -> None:
        out = self.console.out
        if self.tty:
            done = int(self.WIDTH * min(1.0, elapsed / total)) if total else self.WIDTH
            full, empty = ('#', '-') if self.console.style.ascii else ('█', '░')
            self.console.write(f'\r  Aufnahme [{full * done}{empty * (self.WIDTH - done)}] '
                               f'{elapsed:5.0f} / {total:.0f} s', out)
        elif elapsed - self.last >= 10 or elapsed >= total:
            self.last = elapsed
            self.console.line(f'  Aufnahme {elapsed:.0f} / {total:.0f} s')

    def finish(self) -> None:
        if self.tty:
            self.console.write('\n')


# ------------------------------------------------------------------ Profil

def find_profile(live_data: str | None) -> tuple[Path | None, dict, str | None]:
    """Neuestes bestätigtes Live-Profil mit StreamCam-Einstellungen."""
    from dispread.session_profile import SessionProfile, require_live_profile

    if not live_data:
        return None, {}, 'Ort der Laufdaten unbekannt'
    candidates = []
    for path in Path(live_data).glob('*/profile.json'):
        try:
            profile = SessionProfile.load(path)
            require_live_profile(profile)
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if profile.camera is None or profile.camera.usb_id != STREAMCAM_USB_ID or not profile.resolution_ok:
            continue
        candidates.append((profile.confirmed_at_utc, path.stat().st_mtime, path, profile))
    if not candidates:
        return None, {}, ('keine bestätigte Einrichtung gefunden – zuerst in der Werkbank einrichten '
                          '(Anzeige bestätigen); die Kalibrierung nutzt deren Anzeigebereich und Kamera-'
                          'einstellungen')
    _, _, path, profile = max(candidates, key=lambda item: (item[0], item[1]))
    return path, {'confirmed_at_utc': profile.confirmed_at_utc, 'fps': profile.camera.fps,
                  'usb_id': profile.camera.usb_id, 'size': list(profile.camera.size)}, None


def load_profile(path: Path) -> tuple[dict, str | None]:
    from dispread.session_profile import SessionProfile, require_live_profile

    try:
        profile = SessionProfile.load(path)
        require_live_profile(profile)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {}, f'Profil {path} unbrauchbar: {error}'
    if profile.camera is None or profile.camera.usb_id != STREAMCAM_USB_ID:
        return {}, f'Profil {path} hat keine StreamCam-Einstellungen ({STREAMCAM_USB_ID})'
    if not profile.resolution_ok:
        return {}, f'Profil {path} hat die Auflösungsprüfung nicht bestanden'
    return {'confirmed_at_utc': profile.confirmed_at_utc, 'fps': profile.camera.fps,
            'usb_id': profile.camera.usb_id, 'size': list(profile.camera.size)}, None


# ------------------------------------------------------------------ Seriell

def probe_telegrams(port: str, baudrate: int, deps: Deps) -> tuple[list[str], str | None]:
    """Nur lesen: kommen GSV-Telegramme an? Sendet kein Byte."""
    try:
        ser = deps.open_serial(port, baudrate, 0.5)
    except Exception as error:  # noqa: BLE001 - jeder Öffnungsfehler ist ein Grund
        return [], f'{port} lässt sich nicht öffnen: {error}'
    lines: list[str] = []
    try:
        deadline = deps.monotonic() + TELEGRAM_PROBE_S
        while deps.monotonic() < deadline and len(lines) < TELEGRAM_MIN_LINES:
            _check_cancelled(deps)
            raw = ser.readline()
            text = raw.decode('ascii', 'replace').strip() if raw else ''
            if text:
                lines.append(text)
    except Exception as error:  # noqa: BLE001
        return lines, f'Lesen von {port} fehlgeschlagen: {error}'
    finally:
        with contextlib.suppress(Exception):
            ser.close()
    if len(lines) < TELEGRAM_MIN_LINES:
        return lines, (f'keine GSV-Telegramme an {port} ({len(lines)} Zeilen in {TELEGRAM_PROBE_S:.0f} s, '
                       f'{baudrate} Baud) – Kabel zum RS232-Ausgang des Messverstärkers prüfen')
    return lines, None


def _byte_list(value: Any, count: int) -> bool:
    return (isinstance(value, list) and len(value) == count
            and all(isinstance(item, int) and not isinstance(item, bool) and 0 <= item <= 255 for item in value))


def restore_point_problem(restore_point: Any) -> str | None:
    """Rückstellpunkt prüfen, bevor ein Byte an den Messverstärker geht:
    ``register.norm.daten`` genau 3 Bytes, ``register.dpoint.daten`` genau
    1 Byte, alle ganzzahlig 0…255. Grund oder None."""
    if not isinstance(restore_point, dict):
        return 'kein JSON-Objekt'
    register = restore_point.get('register')
    if not isinstance(register, dict):
        return 'Schlüssel „register“ fehlt'
    for name, count in (('norm', 3), ('dpoint', 1)):
        entry = register.get(name)
        if not isinstance(entry, dict) or 'daten' not in entry:
            return f'„register.{name}.daten“ fehlt'
        if not _byte_list(entry['daten'], count):
            unit = 'Bytes' if count > 1 else 'Byte'
            return (f'„register.{name}.daten“ muss genau {count} {unit} (ganze Zahlen 0…255) enthalten, '
                    f'steht dort: {json.dumps(entry["daten"], ensure_ascii=False)}')
    return None


def read_restore_point(port: str, baudrate: int, log_path: Path, deps: Deps, now: datetime) -> dict:
    """Normierung und Dezimalpunkt lesen (Strom kurz anhalten, Register lesen,
    Strom neu starten) und als Rückstellpunkt zurückgeben."""
    from dispread.gsv2as_serial import _pause_read_registers_resume

    state: dict = {}
    try:
        ser = deps.open_serial(port, baudrate, 0.5)
    except Exception as error:  # noqa: BLE001
        raise CalibrationError(f'{port} lässt sich nicht öffnen: {error}') from error
    try:
        with open(log_path, 'a', encoding='utf-8') as log:
            norm, dpoint = _pause_read_registers_resume(ser, log, state, label='kalibrieren_vorher')
    finally:
        with contextlib.suppress(Exception):
            ser.close()
    for name, entry in (('norm', norm), ('dpoint', dpoint)):
        if 'daten' not in entry:
            raise CalibrationError(f'Register {name} nicht lesbar: {entry.get("fehler", "keine Antwort")}')
    point = {'gelesen_am_utc': now.isoformat(), 'port': port, 'baudrate': baudrate,
             'hinweis': 'Von picam kalibrieren vor der Aufnahme gelesen; Rückstellwerte für norm und dpoint.',
             'register': {'norm': norm, 'dpoint': dpoint}}
    problem = restore_point_problem(point)
    if problem:
        raise CalibrationError(f'Rückstellpunkt unbrauchbar gelesen: {problem}')
    return point


def restore_registers(port: str, baudrate: int, restore_point: dict, log_path: Path,
                      deps: Deps) -> tuple[bool, dict]:
    """Rückstellpunkt schreiben und durch erneutes Lesen prüfen."""
    from dispread.gsv2as_serial import _apply_norm_dpoint, _check_restore_point

    state: dict = {}
    problem = restore_point_problem(restore_point)
    if problem:
        return False, {'error': f'Rückstellpunkt ungültig: {problem}'}
    norm = restore_point['register']['norm']['daten']
    dpoint = restore_point['register']['dpoint']['daten'][0]
    try:
        ser = deps.open_serial(port, baudrate, 0.5)
    except Exception as error:  # noqa: BLE001
        return False, {'error': f'{port} lässt sich nicht öffnen: {error}'}
    try:
        with open(log_path, 'a', encoding='utf-8') as log:
            write_ok = _apply_norm_dpoint(ser, norm, dpoint, log, state, label='restore_nachholen')
            matches, detail = _check_restore_point(ser, restore_point, log, state, label='restore_nachholen_verify')
    except Exception as error:  # noqa: BLE001
        return False, {'error': f'{type(error).__name__}: {error}'}
    finally:
        with contextlib.suppress(Exception):
            ser.close()
    return bool(write_ok and matches), {'write_ok': write_ok, **detail}


# ------------------------------------------------------------------ Dienst

def sudo_needed(instance: Instance, snapshot: probes.Snapshot) -> bool:
    """Prüfen, ob der vorgesehene Dienststopp sudo braucht."""
    from . import service

    if instance.unit is None or not _service_running(snapshot):
        return False
    plan = service.plan('stop', instance, snapshot)
    return plan.blocker is None and any(cmd[:1] == ['sudo'] for cmd in plan.commands)


def sudo_cached() -> bool:
    """Kann sudo im aktuellen Sitzungskontext ``true`` ohne Passwort ausführen?"""
    code, _, _ = probes.run_command(['sudo', '-n', 'true'])
    return code == 0


def sudo_validate(password: str, *, run=None) -> tuple[bool, str]:
    """sudo-Authentifizierung per Standardeingabe für diese Sitzung auffrischen."""
    if any(char in password for char in ('\n', '\r', '\0')):
        return False, 'sudo erwartet ein einzeiliges Passwort.'
    run = run or subprocess.run
    try:
        done = run(['sudo', '-S', '-p', '', '-v'], input=password + '\n', text=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
    except subprocess.TimeoutExpired:
        return False, 'Zeitlimit bei der sudo-Authentifizierung erreicht.'
    except (OSError, subprocess.SubprocessError, ValueError):
        return False, 'sudo-Authentifizierung konnte nicht ausgeführt werden.'
    if done.returncode != 0:
        return False, f'sudo-Authentifizierung fehlgeschlagen (Exit {done.returncode}).'
    return True, ''


def stop_service(instance: Instance, snapshot: probes.Snapshot, deps: Deps, console: Console) -> tuple[bool, str]:
    from . import service

    plan = service.plan('stop', instance, snapshot)
    if plan.blocker:
        return False, f'Gesperrt: {plan.blocker}'
    for line in plan.shell(deps.service_interactive):
        console.line(console.style.dim(f'  $ {line}'))
    if deps.service_interactive and any(command[:1] == ['sudo'] for command in plan.commands):
        console.line('  sudo fragt gegebenenfalls nach dem Passwort.')
    return service.execute(plan, instance, interactive=deps.service_interactive, wait_ready=False,
                           run=deps.service_runner,
                           echo=lambda _line: None, recheck=deps.recheck)


def issue_start(instance: Instance, deps: Deps) -> tuple[bool, str, list[str]]:
    """Startbefehl ausführen, ohne Ausgabe: (ok, Meldung, Befehlszeilen).
    Im Aufräumen läuft das vor jeder Konsolenausgabe."""
    from . import service

    try:
        plan = service.plan('start', instance)
    except ValueError as error:
        return False, str(error), []
    try:
        ok, message = service.execute(plan, instance, interactive=deps.service_interactive, wait_ready=False,
                                      run=deps.service_runner, echo=lambda _line: None)
    except Exception as error:  # noqa: BLE001 - Start bleibt Pflicht, Fehler nur melden
        return False, f'{type(error).__name__}: {error}', plan.shell(deps.service_interactive)
    return ok, message, plan.shell(deps.service_interactive)


def start_service(instance: Instance, deps: Deps, console: Console,
                  issued: tuple[bool, str, list[str]] | None = None) -> tuple[bool, str]:
    """Dienst starten (oder den schon abgesetzten Start ``issued`` melden)
    und auf HTTPS warten."""
    from . import service

    ok, message, shell = issued if issued is not None else issue_start(instance, deps)
    for line in shell:
        console.line(console.style.dim(f'  $ {line}'))
    if not ok:
        return False, message
    console.line(f'  Warte bis zu {service.READY_TIMEOUT_S} s auf {instance.url or "HTTPS"} …')
    ready = (deps.wait_ready or service.wait_until_ready)(instance)
    if ready:
        return True, f'Dienst läuft, {instance.url or "HTTPS"} antwortet.'
    return False, f'Dienst gestartet, {instance.url or "HTTPS"} antwortet aber nicht – picam logs prüfen.'


# ------------------------------------------------------------------ Ablauf

def _calibration_target(instance: Instance) -> Path | None:
    return Path(instance.calibration) if instance.calibration else None


def _n_steps(duration_s: float, hold_s: float) -> int:
    return max(1, int((duration_s - FIXED_OVERHEAD_S) // (hold_s + STEP_OVERHEAD_S)))


def preflight(instance: Instance, options: Options, deps: Deps) -> Preflight:
    from dispread.calibration.schedule import (
        RECORD_FRAME_RATE,
        RECORD_STAGING_ROOT,
        build_schedule,
        format_num,
        plan_factors,
    )

    options = options.for_instance(instance)
    result = Preflight()
    add = result.checks.append
    _check_cancelled(deps)
    target = _calibration_target(instance)
    # Instanz
    if instance.kind == 'none' or target is None or not instance.live_data:
        add(Check('Instanz', False, instance.problem or 'keine Werkbank-Installation mit Kalibrierpfad gefunden'))
        return result
    add(Check('Instanz', True, f'{instance.label}, Kalibrierung {target}'))
    # Dienst und Lauf
    snapshot = deps.collect(instance, include_setup=False)
    result.snapshot = snapshot
    result.service_running = _service_running(snapshot)
    blocker = snapshot.stop_blocker
    if instance.unit is None and result.service_running:
        add(Check('Dienst', False, 'Werkbank läuft ohne Dienstmanager (portabel) – erst von Hand beenden'))
    elif blocker:
        add(Check('Dienst', False, f'gesperrt: {blocker}'))
    else:
        add(Check('Dienst', True, 'läuft, wird für die Aufnahme gestoppt' if result.service_running
                  else 'gestoppt'))
    # Schreibrechte
    _check_cancelled(deps)
    folder = _existing_parent(target.parent)
    if os.access(folder, os.W_OK | os.X_OK):
        add(Check('Ablage', True, str(target.parent / 'runs')))
    else:
        try:
            import pwd

            owner = pwd.getpwuid(folder.stat().st_uid).pw_name
        except (KeyError, OSError):
            owner = '?'
        add(Check('Ablage', False, f'keine Schreibrechte auf {folder} – als {owner} oder mit sudo ausführen '
                                   '(sudo picam kalibrieren)'))
    # Profil
    _check_cancelled(deps)
    if options.profile is not None:
        info, problem = load_profile(options.profile)
        profile = options.profile if problem is None else None
    else:
        profile, info, problem = find_profile(instance.live_data)
    if problem is None and info.get('fps', 0) < RECORD_FRAME_RATE:
        problem = f'Kamera-fps im Profil ({info.get("fps")}) unter der Aufnahmerate {RECORD_FRAME_RATE:g}'
    if problem:
        add(Check('Einrichtung', False, problem))
    else:
        result.profile, result.profile_info = profile, info
        add(Check('Einrichtung', True, f'{profile} (bestätigt {_local(info["confirmed_at_utc"])})'))
    # Kamera
    _check_cancelled(deps)
    camera = deps.usb_camera()
    if camera is None:
        add(Check('Kamera', False, f'StreamCam {STREAMCAM_USB_ID} nicht gefunden – an einen blauen USB-3-Port '
                                   'stecken'))
    elif camera.get('speed_mbps', 0) < 5000:
        add(Check('Kamera', False, f'StreamCam an USB 2 ({camera.get("speed_mbps")} Mbit/s) – an einen blauen '
                                   'USB-3-Port stecken'))
    else:
        add(Check('Kamera', True, f'StreamCam {STREAMCAM_USB_ID} an USB 3'))
    # Adapter und Telegramme
    _check_cancelled(deps)
    from dispread.hardware_ports import uart_devices, validate_port_pair

    output = instance.output_port
    if output.startswith('uart'):
        output = uart_devices().get(output, output)
    try:
        validate_port_pair(output, options.port)
    except ValueError as error:
        add(Check('RS232-Adapter', False, str(error)))
        return result
    if not deps.port_exists(options.port):
        add(Check('RS232-Adapter', False, f'kein Adapter an {options.port} – USB-RS232-Adapter stecken und mit '
                                          'dem RS232-Ausgang des Messverstärkers verbinden'))
    else:
        lines, problem = probe_telegrams(options.port, options.baudrate, deps)
        if problem:
            add(Check('RS232-Adapter', False, problem))
        else:
            add(Check('RS232-Adapter', True, f'{options.port}, {options.baudrate} Baud, Telegramm „{lines[-1]}“'))
    # Plan und Speicher (nur mit Profil)
    _check_cancelled(deps)
    if result.profile is not None:
        result.seed = options.seed if options.seed is not None else int(deps.now().timestamp())
        result.schedule = plan_factors(_n_steps(options.duration_s, options.hold_s), result.seed)
        staging = deps.staging_root or RECORD_STAGING_ROOT
        result.record_argv = [
            '--source', 'camera', '--frame-rate', format_num(RECORD_FRAME_RATE), '--image-format', 'jpg',
            '--norm-schedule', build_schedule(result.schedule, options.hold_s),
            '--duration', format_num(options.duration_s), '--staging-root', str(staging),
            '--port', options.port, '--baudrate', str(options.baudrate),
            '--camera-settings', str(result.profile)]
        try:
            args = deps.record_args([*result.record_argv, '--output', str(target.parent / 'runs' / 'x')])
            problem, result.estimate_bytes = deps.storage(args, result.profile, target.parent)
        except (OSError, ValueError, SystemExit) as error:
            problem = f'Aufnahme nicht planbar: {error}'
        add(Check('Speicher', problem is None, problem or f'etwa {result.estimate_bytes >> 20} MiB für die '
                                                          'Rohaufnahme'))
    return result


def print_checks(preflight_: Preflight, console: Console) -> None:
    console.checks(preflight_)


def print_plan(instance: Instance, options: Options, pre: Preflight, console: Console) -> list[str]:
    target = _calibration_target(instance)
    downtime = math.ceil((options.duration_s + 90) / 60)
    title = f'Plan (Werkbank etwa {downtime} min nicht erreichbar)' if pre.service_running else 'Plan'
    steps = []
    if pre.service_running:
        steps.append('Werkbank-Dienst stoppen (gibt die Kamera frei)')
    steps += [
        'Normierung und Dezimalpunkt des Messverstärkers lesen (Rückstellpunkt)',
        f'{options.duration_s:.0f} s aufnehmen: Kamera und Telegramme, {len(pre.schedule)} Normierungssprünge '
        f'über RS232 (set norm/set dpoint, je {options.hold_s:g} s)',
        'Normierung zurückstellen und durch Lesen prüfen',
    ]
    if pre.service_running:
        steps.append('Werkbank-Dienst wieder starten (auch bei Abbruch)')
    steps.append(f'Auswerten (Versatz δ, Schutzabstand M), prüfen und nach {target} übernehmen – '
                 'nur wenn das Ergebnis gültig ist')
    lines = [f'  {index}. {text}' for index, text in enumerate(steps, 1)]
    lines += [
        '',
        '  Während der Aufnahme Kamera und Anzeige nicht bewegen und nichts vor die Anzeige halten.',
        '  Die Anzeige springt zwischen stark skalierten Werten – das ist gewollt und wird danach zurückgestellt.',
        f'  Rohdaten bleiben unter {target.parent / "runs"} (etwa {pre.estimate_bytes >> 20} MiB).',
    ]
    if target.exists():
        lines.append('  Die vorhandene Kalibrierung wird nur bei gültigem Ergebnis ersetzt; eine Kopie bleibt in '
                     'der Ablage.')
    console.plan(title, lines)
    return lines


def explain_not_detected(result: dict, console: Console) -> None:
    console.mark(probes.FAIL, 'Kein Versatz erkannt – an der Kalibrierung wurde nichts geändert.', console.err)
    params = result.get('params') or {}
    needed = params.get('min_qualifying', 3)
    for population in result.get('populations', []):
        null = population.get('null_baseline') or {}
        rate = null.get('pass_rate')
        rate_text = '–' if rate is None else f'{rate * 100:.0f} %'
        console.line(f'  {population.get("population")}: {population.get("n_qualifying", 0)} von '
                     f'{population.get("n_events_total", 0)} Wechseln messbar (nötig: {needed}), '
                     f'Trefferquote der Nullprobe {rate_text} (muss unter 50 % liegen)', console.err)
    console.line('  Was helfen kann:', console.err)
    for text in ('länger aufnehmen (picam kalibrieren --dauer 180)',
                 'Sensor angeschlossen lassen, damit die letzte Stelle der Anzeige leicht schwankt',
                 'Kamera und Anzeige seit der Einrichtung bewegt? Dann in der Werkbank neu einrichten',
                 'Reflexe/Blendung prüfen, nichts vor die Anzeige halten'):
        console.line(f'  – {text}', console.err)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')


def ensure_norm_restored(run_dir: Path, restore_point: dict, options: Options, deps: Deps,
                         console: Console) -> bool:
    session = _read_json(run_dir / 'aufnahme' / 'session.json') or {}
    verification = session.get('restore_verification') or {}
    if verification.get('write_ok') and verification.get('matches_restore_point'):
        console.mark(probes.OK, 'Normierung zurückgestellt und durch Lesen bestätigt.')
        return True
    reason = verification.get('error') or ('nicht bestätigt' if verification else 'keine Rückstellung protokolliert')
    console.mark(probes.WARN, f'Rückstellung der Normierung: {reason} – zweiter Versuch …')
    ok, detail = restore_registers(options.port, options.baudrate, restore_point,
                                   run_dir / 'rueckstellung-nachgeholt.jsonl', deps)
    _write_json(run_dir / 'rueckstellung-nachgeholt.json', {'ok': ok, **detail})
    if ok:
        console.mark(probes.OK, 'Normierung im zweiten Versuch zurückgestellt und bestätigt.')
        return True
    norm = restore_point.get('register', {}).get('norm', {}).get('daten')
    dpoint = restore_point.get('register', {}).get('dpoint', {}).get('daten')
    console.loud([
        'ACHTUNG: Die Normierung des Messverstärkers ist NICHT zurückgestellt!',
        f'Grund: {detail.get("error") or "Lesekontrolle stimmt nicht"}',
        'Die Anzeige zeigt womöglich einen skalierten Wert. Vor jeder weiteren Messung zurückstellen:',
        f'  picam kalibrieren --rueckstellen {run_dir / "rueckstellpunkt.json"}',
        f'  (erwartet: norm {norm}, dpoint {dpoint}; Adapter muss gesteckt sein)',
    ])
    return False


def calibrate(instance: Instance, options: Options, console: Console, deps: Deps | None = None) -> int:
    """Messen und ``console.last_result`` setzen.

    Im Hauptthread nutzen SIGTERM und SIGHUP den Aufräumpfad von Strg+C.
    Worker fragen ``deps.cancelled`` kooperativ ab. Rückstellung und Dienststart
    laufen zu Ende. Die synchrone Auswertung läuft ebenfalls zu Ende, bevor
    ein währenddessen angeforderter Abbruch die Übernahme verhindert.
    """
    console.last_result = None
    options = options.for_instance(instance)
    with abort_on_signals():
        try:
            return _calibrate(instance, options, console, deps or Deps())
        except _ConsoleAbort:
            reason = ABORT_TEXT['konsole']
            console.mark(probes.FAIL, reason, console.err)
            return _complete(console, 'abgebrochen', EXIT_ABORT, reason=reason)


def _calibrate(instance: Instance, options: Options, console: Console, deps: Deps) -> int:
    def step(text: str, *, key: StepKey) -> None:
        _check_cancelled(deps)
        console.step(text, key=key)
        _check_cancelled(deps)

    _check_cancelled(deps)
    console.line(console.style.bold('Timing-Kalibrierung (Inbetriebnahme)'))
    if options.duration_s < MIN_DURATION_S:
        reason = f'--dauer mindestens {MIN_DURATION_S:.0f} s'
        console.mark(probes.FAIL, reason, console.err)
        return _complete(console, 'gesperrt', EXIT_BLOCKED, reason=reason)
    pre = preflight(instance, options, deps)
    _check_cancelled(deps)
    print_checks(pre, console)
    _check_cancelled(deps)
    if pre.problems:
        console.line()
        console.mark(probes.FAIL, 'Kalibrierung nicht möglich – nichts geändert.', console.err)
        reason = '\n'.join(f'{check.label}: {check.text}' for check in pre.problems)
        return _complete(console, 'gesperrt', EXIT_BLOCKED, reason=reason)
    plan_lines = print_plan(instance, options, pre, console)
    _check_cancelled(deps)
    if not options.yes:
        if not deps.isatty():
            reason = 'Keine Rückfrage möglich (kein Terminal); mit --yes bestätigen.'
            console.line(reason, console.err)
            return _complete(console, 'abgebrochen', EXIT_ABORT, reason=reason)
        confirmed = console.confirm('Jetzt kalibrieren?', plan_lines, None, deps=deps)
        _check_cancelled(deps)
        if not confirmed:
            reason = 'Abgebrochen, nichts geändert.'
            console.line(reason, console.err)
            return _complete(console, 'abgebrochen', EXIT_ABORT, reason=reason)

    target = _calibration_target(instance)
    assert target is not None and pre.profile is not None
    started = deps.now()
    run_dir = target.parent / 'runs' / started.strftime('%Y%m%dT%H%M%SZ')
    run_dir.mkdir(parents=True, exist_ok=False)
    journal: dict[str, Any] = {
        'schema': 'picam.kalibrierung/1', 'gestartet_utc': started.isoformat(),
        'benutzer': _user(), 'instanz': instance.label, 'ziel': str(target),
        'profil': {'pfad': str(pre.profile), 'sha256': sha256_file(pre.profile), **pre.profile_info},
        'port': options.port, 'baudrate': options.baudrate, 'dauer_s': options.duration_s,
        'halte_s': options.hold_s, 'seed': pre.seed, 'faktoren': pre.schedule, 'ergebnis': 'laeuft'}
    _write_json(run_dir / 'lauf.json', journal)
    restore_point: dict | None = None
    stop_attempted = stopped = recorded = aborted = False
    record_code: int | None = None
    norm_ok: bool | None = None
    service_ok: bool | None = None
    failure: str | None = None
    progress: ProgressReporter | None = None
    try:
        if pre.service_running:
            step('Werkbank-Dienst stoppen', key='dienst_stop')
            stop_attempted = True
            ok, message = stop_service(instance, pre.snapshot, deps, console)
            if not ok:
                raise CalibrationError(f'Dienst nicht gestoppt: {message}')
            stopped = True
            console.mark(probes.OK, message)
        step('Kamera freigeben', key='kamera')
        deadline = deps.monotonic() + CAMERA_FREE_TIMEOUT_S
        while holders := deps.camera_holders():
            _check_cancelled(deps)
            if deps.monotonic() > deadline:
                raise CalibrationError(f'Kamera nach {CAMERA_FREE_TIMEOUT_S:.0f} s noch belegt: {", ".join(holders)}')
            deps.sleep(0.5)
            _check_cancelled(deps)
        console.mark(probes.OK, 'Kamera frei.')
        step('Rückstellpunkt lesen', key='rueckstellpunkt')
        restore_point = read_restore_point(options.port, options.baudrate, run_dir / 'register-vorher.jsonl',
                                           deps, deps.now())
        _write_json(run_dir / 'rueckstellpunkt.json', restore_point)
        console.mark(probes.OK, f"norm {restore_point['register']['norm']['daten']}, "
                                f"dpoint {restore_point['register']['dpoint']['daten']} gesichert.")
        step(f'Aufnahme ({options.duration_s:.0f} s, {len(pre.schedule)} Normierungssprünge)', key='aufnahme')
        args = deps.record_args([*pre.record_argv, '--output', str(run_dir / 'aufnahme'),
                                 '--restore-point', str(run_dir / 'rueckstellpunkt.json')])
        progress = console.progress(deps.isatty() and getattr(console.out, 'isatty', lambda: False)())

        def on_progress(elapsed: float, total: float) -> None:
            _check_cancelled(deps)
            progress(elapsed, total)

        _check_cancelled(deps)
        recorded = True
        if deps.record is run_record:
            record_code = run_record(args, on_progress, out=console.out, err=console.err)
        else:
            record_code = deps.record(args, on_progress)
        _check_cancelled(deps)
    except KeyboardInterrupt as interrupt:
        aborted = True
        failure = ABORT_TEXT.get(interrupt.args[0] if interrupt.args else '', 'Abbruch (Strg+C)')
    except CalibrationError as error:
        failure = str(error)
    except Exception as error:  # noqa: BLE001 - Aufräumen bleibt Pflicht
        failure = f'{type(error).__name__}: {error}'
    finally:
        with shielded():
            # Erst handeln, dann reden: Rückstellung und Startbefehl laufen vor
            # jeder Konsolenausgabe (nach SIGHUP ist das Terminal weg; eine
            # Ausgabe wirft dann zwar nicht mehr, s. Console.write, darf aber
            # die beiden Pflichtschritte auch sonst nicht aufhalten).
            norm_report = DeferredConsole(console)
            if recorded and restore_point is not None:
                try:
                    norm_ok = ensure_norm_restored(run_dir, restore_point, options, deps, norm_report)
                except Exception as error:  # noqa: BLE001
                    norm_ok = False
                    norm_report.loud([f'ACHTUNG: Rückstellung der Normierung nicht prüfbar: {error}',
                                      f'Rückstellpunkt: {run_dir / "rueckstellpunkt.json"}'])
            if not stopped and stop_attempted and not _service_up(instance, deps):
                stopped = True  # Stopp lief trotz Fehler/Abbruch durch: trotzdem wieder starten
            issued = issue_start(instance, deps) if stopped else None
            # Jetzt berichten.
            if progress is not None:
                try:
                    progress.finish()
                except Exception as error:  # noqa: BLE001 - Ergebnis und Dienststatus trotzdem melden
                    failure = failure or f'{type(error).__name__}: {error}'
            if failure:
                console.mark(probes.FAIL, failure, console.err)
            if recorded and restore_point is not None:
                console.step('Normierung prüfen', key='normierung')
                norm_report.replay()
            if stopped:
                console.step('Werkbank-Dienst starten', key='dienst_start')
                try:
                    service_ok, message = start_service(instance, deps, console, issued)
                except Exception as error:  # noqa: BLE001 - Warten scheitert: nur melden
                    service_ok, message = False, f'{type(error).__name__}: {error}'
                if service_ok:
                    console.mark(probes.OK, message)
                else:
                    console.loud([f'Werkbank-Dienst nicht wieder gestartet: {message}',
                                  'Von Hand starten: picam start'])
            _adopt_owner(run_dir, target.parent)
            _adopt_owner(run_dir.parent, target.parent, recursive=False)
    journal.update({'aufnahme_exit': record_code, 'normierung_zurueckgestellt': norm_ok,
                    'dienst_neu_gestartet': service_ok if stopped else None})

    def finish(outcome: str, code: int, *, metrics: list[tuple[str, str]] | None = None, **extra) -> int:
        journal.update({'ergebnis': outcome, 'beendet_utc': deps.now().isoformat(), **extra})
        _write_json(run_dir / 'lauf.json', journal)
        _adopt_owner(run_dir, target.parent)
        reason = extra.get('grund')
        if norm_ok is False and code == EXIT_OK:
            code = EXIT_FAIL
            reason = 'Rückstellung der Normierung nicht bestätigt.'
        console.line()
        console.line(console.style.dim(f'Protokoll und Rohdaten: {run_dir}'))
        return _complete(console, outcome, code, reason=reason, run_dir=run_dir, metrics=tuple(metrics or ()),
                         norm_restored=norm_ok, service_restarted=service_ok if stopped else None)

    if failure or record_code is None:
        return finish('abgebrochen' if aborted else 'fehler', EXIT_ABORT if aborted else EXIT_FAIL,
                      grund=failure)
    try:
        step('Aufnahme prüfen', key='pruefen')
        session = _read_json(run_dir / 'aufnahme' / 'session.json') or {}
        if session.get('aborted'):
            reason = session.get('abort_reason')
            if reason == 'konsole':
                raise _ConsoleAbort(reason)
            console.mark(probes.FAIL, 'Aufnahme abgebrochen – an der Kalibrierung wurde nichts geändert.', console.err)
            return finish('abgebrochen', EXIT_ABORT, grund=reason)
        if record_code != 0:
            console.mark(probes.FAIL, f'Aufnahme fehlgeschlagen (Exit {record_code}): '
                                      f'{session.get("acquisition_error") or "siehe Meldungen oben"}', console.err)
            return finish('fehler', EXIT_FAIL, grund=f'Aufnahme Exit {record_code}')
        if not session.get('serial_lines_recorded') or not session.get('frames_recorded'):
            console.mark(probes.FAIL, f'Aufnahme unvollständig: {session.get("frames_recorded", 0)} Bilder, '
                                      f'{session.get("serial_lines_recorded", 0)} Telegramme.', console.err)
            return finish('fehler', EXIT_FAIL, grund='Aufnahme unvollständig')
        console.mark(probes.OK, f'{session["frames_recorded"]} Bilder, {session["serial_lines_recorded"]} Telegramme.')

        analysis_step = 'Auswertung (kann einige Minuten dauern)'
        if threading.current_thread() is not threading.main_thread():
            analysis_step = 'Auswertung (kann einige Minuten dauern und ist währenddessen nicht abbrechbar)'
        step(analysis_step, key='auswertung')
        try:
            result = deps.analyse(run_dir / 'aufnahme', pre.profile, run_dir / 'offset-analyse')
        except KeyboardInterrupt:
            console.mark(probes.FAIL, 'Auswertung abgebrochen – nichts geändert.', console.err)
            return finish('abgebrochen', EXIT_ABORT, grund='Auswertung abgebrochen')
        except Exception as error:  # noqa: BLE001 - jeder Auswertungsfehler: nichts übernehmen
            _check_cancelled(deps)
            console.mark(probes.FAIL, f'Auswertung fehlgeschlagen: {error} – nichts geändert.', console.err)
            return finish('fehler', EXIT_FAIL, grund=f'Auswertung: {error}')
        _check_cancelled(deps)
        detected = [p for p in result.get('populations', []) if p.get('detected') and p.get('M_s') is not None]
        for population in result.get('populations', []):
            if population.get('detected') and population.get('M_s') is not None:
                console.mark(probes.OK, f'{population["population"]}: {population["n_qualifying"]} Wechsel, '
                                        f'δ {population["delta_s"] * 1000:+.0f} ms, M {population["M_s"] * 1000:.0f} ms')
        if not detected:
            explain_not_detected(result, console)
            return finish('nicht erkannt', EXIT_FAIL, grund='Keine Population erkannt.', bericht=result.get('_out_json'))

        step('Kalibrierung bauen und prüfen', key='bauen')
        from dispread.calibration.build import build_calibration

        candidate = run_dir / CALIBRATION_FILE
        camera = pre.profile_info.get('usb_id', STREAMCAM_USB_ID)
        try:
            build_calibration([Path(result['_out_json'])], candidate, camera_usb_id=camera,
                              measured_at_utc=started.isoformat())
            calibration, problem = validate_file(candidate, camera)
            if problem:
                raise ValueError(problem)
        except (ValueError, OSError, KeyError) as error:
            console.mark(probes.FAIL, f'Ergebnis ungültig: {error} – nichts geändert.', console.err)
            return finish('ungueltig', EXIT_FAIL, grund=str(error))
        assert calibration is not None
        _check_cancelled(deps)
        metrics = describe(calibration, candidate)
        for label, text in metrics:
            console.line(f'  {label:<16} {text}')
        note = import_note_path(target)
        try:
            if target.exists():
                shutil.copy2(target, run_dir / 'vorherige-kalibrierung.json')
            _check_cancelled(deps)
            install_atomically(candidate, target)
        except OSError as error:
            console.mark(probes.FAIL, f'Übernehmen nach {target} fehlgeschlagen: {error}', console.err)
            return finish('fehler', EXIT_FAIL, grund=f'Übernehmen: {error}', metrics=metrics)
        if note.exists():
            with contextlib.suppress(OSError):
                shutil.move(str(note), run_dir / 'vorheriger-import.json')
        console.mark(probes.OK, f'Kalibrierung übernommen: {target}')
        return finish('installiert', EXIT_OK, metrics=metrics, kalibrierung=calibration.to_dict(),
                      sha256=sha256_file(target))
    except _ConsoleAbort:
        reason = ABORT_TEXT['konsole']
        console.mark(probes.FAIL, reason, console.err)
        return finish('abgebrochen', EXIT_ABORT, grund=reason)


# ------------------------------------------------------------------ Prüfen, Importieren, Rückstellen

def check_file(instance: Instance, path: Path | None, console: Console) -> int:
    """Datei prüfen und ``console.last_result`` setzen."""
    console.last_result = None
    target = _calibration_target(instance)
    path = Path(path) if path else target
    if path is None:
        reason = 'Kein Kalibrierpfad konfiguriert; Datei angeben.'
        console.mark(probes.FAIL, reason, console.err)
        return _complete(console, 'fehler', EXIT_FAIL, reason=reason)
    calibration, problem = validate_file(path)
    metrics = tuple(describe(calibration, path)) if calibration is not None else ()
    for label, text in metrics:
        console.line(f'  {label:<16} {text}')
    if problem:
        console.mark(probes.FAIL, f'Ungültig: {problem}', console.err)
        return _complete(console, 'ungueltig', EXIT_FAIL, reason=problem, metrics=metrics)
    active = target is not None and path.resolve() == target.resolve()
    console.mark(probes.OK, 'Gültig' + (' (aktive Kalibrierung).' if active else '.'))
    if not active and target is not None:
        console.line(f'  Übernehmen: picam kalibrieren --import {path}')
    return _complete(console, 'gueltig', EXIT_OK, metrics=metrics)


def import_file(instance: Instance, source: Path, console: Console, deps: Deps | None = None,
                yes: bool = False) -> int:
    """Datei nach Bestätigung importieren und ``console.last_result`` setzen."""
    console.last_result = None
    try:
        return _import_file(instance, source, console, deps or Deps(), yes)
    except _ConsoleAbort:
        reason = ABORT_TEXT['konsole']
        console.mark(probes.FAIL, reason, console.err)
        return _complete(console, 'abgebrochen', EXIT_ABORT, reason=reason)


def _import_file(instance: Instance, source: Path, console: Console, deps: Deps, yes: bool) -> int:
    _check_cancelled(deps)
    target = _calibration_target(instance)
    if target is None:
        reason = 'Kein Kalibrierpfad konfiguriert (keine installierte Werkbank).'
        console.mark(probes.FAIL, reason, console.err)
        return _complete(console, 'gesperrt', EXIT_BLOCKED, reason=reason)
    source = Path(source)
    calibration, problem = validate_file(source)
    metrics = tuple(describe(calibration, source)) if calibration is not None else ()
    for label, text in metrics:
        console.line(f'  {label:<16} {text}')
    _check_cancelled(deps)
    if problem:
        console.mark(probes.FAIL, f'Nicht importiert: {problem}', console.err)
        return _complete(console, 'ungueltig', EXIT_FAIL, reason=problem, metrics=metrics)
    assert calibration is not None
    if source.resolve() == target.resolve():
        console.mark(probes.OK, 'Das ist bereits die aktive Kalibrierung.')
        return _complete(console, 'bereits aktiv', EXIT_OK, metrics=metrics)
    snapshot = deps.collect(instance, include_setup=False)
    _check_cancelled(deps)
    if snapshot.run_active:
        reason = 'Lauf oder Einrichtung aktiv – erst in der Werkbank beenden.'
        console.mark(probes.FAIL, f'Gesperrt: {reason}', console.err)
        return _complete(console, 'gesperrt', EXIT_BLOCKED, reason=reason, metrics=metrics)
    console.line()
    console.mark(probes.WARN, IMPORT_WARNING)
    target_line = f'Ziel: {target}' + (' (vorhandene Datei wird ersetzt, Kopie bleibt)' if target.exists() else '')
    console.line(f'  {target_line}')
    if not yes:
        if not deps.isatty():
            reason = 'Keine Rückfrage möglich (kein Terminal); mit --yes bestätigen.'
            console.line(reason, console.err)
            return _complete(console, 'abgebrochen', EXIT_ABORT, reason=reason, metrics=metrics)
        confirmed = console.confirm('Kalibrierung importieren?', [IMPORT_WARNING, target_line],
                                    IMPORT_CONFIRM_WORD, deps=deps)
        _check_cancelled(deps)
        if not confirmed:
            reason = 'Nicht importiert.'
            console.line(reason, console.err)
            return _complete(console, 'abgebrochen', EXIT_ABORT, reason=reason, metrics=metrics)
    now = deps.now()
    digest = sha256_file(source)
    backup = None
    _check_cancelled(deps)
    if target.exists():
        backup = target.parent / 'runs' / (now.strftime('%Y%m%dT%H%M%SZ') + '-import')
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup / 'vorherige-kalibrierung.json')
        if import_note_path(target).exists():
            shutil.copy2(import_note_path(target), backup / 'vorheriger-import.json')
        _adopt_owner(backup, target.parent)
    note = {'schema': 'picam.kalibrierung-import/1', 'quelle': str(source.resolve()), 'sha256': digest,
            'importiert_am_utc': now.isoformat(), 'importiert_von': _user(),
            'kamera': calibration.camera_usb_id, 'gemessen_am_utc': calibration.measured_at_utc,
            'hinweis': IMPORT_WARNING}
    try:
        _check_cancelled(deps)
        install_atomically(source, target)
        install_bytes((json.dumps(note, indent=2, ensure_ascii=False) + '\n').encode('utf-8'),
                      import_note_path(target))
    except OSError as error:
        console.mark(probes.FAIL, f'Import fehlgeschlagen: {error}', console.err)
        return _complete(console, 'fehler', EXIT_FAIL, reason=str(error), run_dir=backup, metrics=metrics)
    console.mark(probes.OK, f'Importiert nach {target} (Herkunft: {import_note_path(target)}).')
    return _complete(console, 'importiert', EXIT_OK, run_dir=backup, metrics=tuple(describe(calibration, target)))


def restore_from_file(path: Path, options: Options, console: Console, deps: Deps | None = None) -> int:
    deps = deps or Deps()
    restore_point = _read_json(path)
    if restore_point is None:
        console.mark(probes.FAIL, f'{path} ist kein lesbarer Rückstellpunkt.', console.err)
        return EXIT_FAIL
    problem = restore_point_problem(restore_point)
    if problem:
        console.mark(probes.FAIL, f'{path} ist kein gültiger Rückstellpunkt: {problem} – nichts gesendet.',
                     console.err)
        return EXIT_FAIL
    saved_port = restore_point.get('port')
    if options.port in (None, REFERENCE_PORT) and saved_port is not None:
        from dispread.hardware_ports import GSV_UART_PORT, validate_port_pair
        from dispread.workbench.config import validate_serial_setting

        try:
            validate_serial_setting(saved_port, 'reference_port')
            validate_port_pair(GSV_UART_PORT, saved_port)
            if Path(saved_port).exists():
                validate_serial_setting(str(Path(saved_port).resolve()), 'reference_port')
        except (OSError, ValueError) as error:
            console.mark(probes.FAIL, f'Port im Rückstellpunkt ungültig: {error}', console.err)
            return EXIT_BLOCKED
        options = replace(options, port=saved_port)
    if options.port is None:
        options = replace(options, port=REFERENCE_PORT)
    if not deps.port_exists(options.port):
        console.mark(probes.FAIL, f'Kein Adapter an {options.port}.', console.err)
        return EXIT_BLOCKED
    norm = restore_point.get('register', {}).get('norm', {}).get('daten')
    dpoint = restore_point.get('register', {}).get('dpoint', {}).get('daten')
    console.line(f'Schreibt norm {norm} und dpoint {dpoint} an {options.port} und prüft durch Lesen.')
    if not options.yes:
        if not deps.isatty():
            console.line('Keine Rückfrage möglich (kein Terminal); mit --yes bestätigen.', console.err)
            return EXIT_ABORT
        try:
            answer = deps.ask('Zurückstellen? [j/N] ')
        except EOFError:
            answer = ''
        if answer.strip().lower() not in ('j', 'ja', 'y', 'yes'):
            return EXIT_ABORT
    log = Path(path).with_name('rueckstellung-von-hand.jsonl')
    try:
        ok, detail = restore_registers(options.port, options.baudrate, restore_point, log, deps)
    except OSError as error:
        ok, detail = False, {'error': str(error)}
    if ok:
        console.mark(probes.OK, 'Normierung zurückgestellt und bestätigt.')
        return EXIT_OK
    console.loud([f'Rückstellung fehlgeschlagen: {detail.get("error") or "Lesekontrolle stimmt nicht"}'])
    return EXIT_FAIL
