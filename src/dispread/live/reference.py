"""Referenz-Audit neben dem Messpfad; beeinflusst keine Leserentscheidung."""

from __future__ import annotations

import json
import math
import queue
import threading
import time
from pathlib import Path

from dispread import gsv2as_serial as serial_io
from dispread.gsv2as_cell_text import cell_text_from_telegram
from dispread.gsv2as_serial import DEFAULT_RESTORE_POINT, NORM_MAX, NORM_MIN

JOIN_TIMEOUT_S = 20.0
RESTORE_ERROR = "Rückstellung nicht bestätigt – Gerät prüfen (gsv-registers.py)"


def parse_norm_schedule(value):
    """Seiten-/API-Eingabe pruefen, bevor ein Port geoeffnet wird."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = serial_io._parse_norm_schedule(value)
    try:
        result = [(float(factor), float(seconds)) for factor, seconds in value]
    except (TypeError, ValueError) as exc:
        raise ValueError("Werteplan braucht Faktor:Sekunden") from exc
    if not result or any(not (NORM_MIN <= f <= NORM_MAX)
                         or not math.isfinite(s) or s <= 0 for f, s in result):
        raise ValueError("Werteplan: Faktor 0.15..1580000 und endliche Haltezeit > 0 erforderlich")
    return result


class _ScheduledPort:
    """Ein Portbesitzer; nach Timeout keine weiteren Befehle zulassen."""

    def __init__(self, port, recorder):
        self._port = port
        self._recorder = recorder
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._port, name)

    def write(self, data):
        if self._closed:
            raise OSError('Referenzport geschlossen')
        self._recorder._enqueue('commands', {
            'event': 'serial_write', 'command_bytes': list(data),
            't_boottime_ns': self._recorder._clock(),
        })
        return self._port.write(data)

    def close(self):
        if not self._closed:
            self._closed = True
            self._port.close()


class _CommandLog:
    def __init__(self, recorder):
        self.recorder = recorder

    def write(self, text):
        entry = json.loads(text)
        entry['t_boottime_ns'] = self.recorder._clock()
        self.recorder._enqueue('commands', entry)

    def flush(self):
        pass


class ReferenceRecorder:
    def __init__(self, port_opener, out_path, *, clock=None, norm_schedule=None,
                 restore_point=None, monotonic=time.monotonic, startup_timeout_s=2.0,
                 queue_size=1024):
        self._opener = port_opener
        self._path = Path(out_path)
        self._clock = clock or (lambda: time.clock_gettime_ns(time.CLOCK_BOOTTIME))
        self._monotonic = monotonic
        self._schedule = parse_norm_schedule(norm_schedule)
        self._restore_point = restore_point
        self._startup_timeout = startup_timeout_s
        self._queue = queue.Queue(maxsize=queue_size)
        self._stop = threading.Event()
        self._done = threading.Event()
        self._ready = threading.Event()
        self._port = None
        self._latest = None
        self._reader = self._writer = None
        self._state = {'enabled': False, 'reason': 'noch nicht gestartet', 'path': self._path.name,
                       'lines': 0, 'parse_errors': 0, 'gaps': 0, 'dropped_oldest': 0,
                       'norm_schedule': self._schedule, 'restoring': False}
        self._stop_lock = threading.Lock()
        self._stop_deadline = None

    def status(self):
        return dict(self._state)

    def latest(self):
        return None if self._latest is None else dict(self._latest)

    def start(self):
        if self._reader is not None:
            raise RuntimeError('Referenz bereits gestartet')
        if self._schedule:
            if self._restore_point is None:
                self._restore_point = json.loads(DEFAULT_RESTORE_POINT.read_text(encoding='utf-8'))
            point = self._restore_point
            reg = point.get('register') if isinstance(point, dict) else None
            for name, length in [('norm', 3), ('dpoint', 1)]:
                entry = reg.get(name) if isinstance(reg, dict) else None
                data = entry.get('daten') if isinstance(entry, dict) else None
                if not isinstance(data, list) or len(data) != length or any(
                    type(b) is not int or not 0 <= b <= 255 for b in data
                ):
                    raise ValueError('Rueckstellpunkt ungueltig: ' + name)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._writer = threading.Thread(target=self._write, name='reference-writer', daemon=True)
        self._reader = threading.Thread(target=self._read, name='reference-reader', daemon=True)
        self._writer.start()
        self._reader.start()
        timeout = self._startup_timeout
        if not self._ready.wait(timeout):
            self._state.update(enabled=False, reason='keine Telegramme innerhalb von 2 s')
            self.stop()
        return self.status()

    def _enqueue(self, kind, entry):
        if self._done.is_set():
            return
        try:
            self._queue.put_nowait((kind, entry))
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._state['dropped_oldest'] += 1
            except queue.Empty:
                pass
            self._queue.put_nowait((kind, entry))

    def _write(self):
        try:
            with self._path.open('w', encoding='utf-8') as reference:
                commands = None
                try:
                    if self._schedule:
                        commands = self._path.with_name('commands.jsonl').open('w', encoding='utf-8')
                    while not self._done.is_set() or not self._queue.empty():
                        try:
                            kind, entry = self._queue.get(timeout=0.05)
                        except queue.Empty:
                            continue
                        target = commands if kind == 'commands' else reference
                        target.write(json.dumps(entry, ensure_ascii=False) + '\n')
                        target.flush()
                finally:
                    if commands is not None:
                        commands.close()
        except Exception as exc:  # noqa: BLE001 - Auditfehler sichtbar machen
            self._state['error'] = f'Referenzdatei: {exc}'
            self._stop.set()

    def _read(self):
        restore = False
        log = _CommandLog(self)
        command_state = {}
        try:
            self._port = port = self._opener()
            port.timeout = 0.1
            if self._stop.is_set():
                return
            discard = True
            fragment = b''
            last_t = None
            prepared = False
            schedule_aborted = False
            index, due = 0, self._monotonic()
            while not self._stop.is_set():
                if prepared and self._schedule and index < len(self._schedule) and self._monotonic() >= due:
                    factor, hold = self._schedule[index]
                    if self._stop.is_set():
                        break
                    ok = serial_io._apply_norm_dpoint(
                        port, *serial_io._encode_norm(factor), log, command_state, label=f'schedule[{index}] factor={factor}')
                    if not ok:
                        raise ValueError('Werteplan: last_error meldet Fehler')
                    index += 1
                    due = self._monotonic() + hold
                    discard, fragment = True, b''
                raw = port.readline()
                if not raw:
                    self._stop.wait(0.005)
                    continue
                if discard:
                    discard = not raw.endswith(b'\n')
                    continue
                fragment += raw
                if len(fragment) > 4096:
                    entry = {'t_boottime_ns': self._clock(),
                             'raw': fragment.decode('ascii', errors='replace').rstrip('\r\n'),
                             'cell_text': None, 'value': None, 'error': 'Telegramm laenger als 4096 Bytes'}
                    discard = not fragment.endswith(b'\n')
                    fragment = b''
                    self._state['parse_errors'] += 1
                    self._state['lines'] += 1
                    self._enqueue('reference', entry)
                    continue
                if not fragment.endswith(b'\n'):
                    continue
                t = self._clock()
                raw, fragment = fragment, b''
                try:
                    text = raw.decode('ascii').rstrip('\r\n')
                    cell_text = cell_text_from_telegram(text)
                    entry = {'t_boottime_ns': t, 'raw': text, 'cell_text': cell_text,
                             'value': float(text.split()[0])}
                except (ValueError, UnicodeError) as exc:
                    self._state['parse_errors'] += 1
                    entry = {'t_boottime_ns': t, 'raw': raw.decode('ascii', errors='replace').rstrip('\r\n'),
                             'cell_text': None, 'value': None, 'error': str(exc)}
                self._state['lines'] += 1
                self._enqueue('reference', entry)
                if entry.get('error'):
                    continue
                if last_t is not None and t - last_t > 1_000_000_000:
                    self._state['gaps'] += 1
                last_t = t
                self._latest = entry
                self._state.update(enabled=True, reason=None)
                self._ready.set()
                if self._schedule and not prepared and not schedule_aborted and not self._stop.is_set():
                    self._port = port = _ScheduledPort(port, self)
                    matches, detail = serial_io._check_restore_point(
                        port, self._restore_point, log, command_state, label='precheck')
                    self._state['precheck'] = detail
                    if not matches:
                        self._state['schedule_aborted'] = 'Geraet steht nicht am Rueckstellpunkt; kein set norm gesendet'
                        schedule_aborted = True
                    else:
                        restore = True
                        prepared = True
                    discard = True
        except Exception as exc:  # noqa: BLE001 - Lauf bleibt ohne Referenz benutzbar
            self._state.update(reason=f'Referenz nicht verfuegbar: {exc}')
            if self._state['enabled']:
                self._state['error'] = self._state['reason']
        finally:
            if restore:
                self._state['restoring'] = True
                try:
                    reg = self._restore_point['register']
                    ok = serial_io._apply_norm_dpoint(
                        self._port, reg['norm']['daten'], reg['dpoint']['daten'][0],
                        log, command_state, label='restore')
                    matches, detail = serial_io._check_restore_point(
                        self._port, self._restore_point, log, command_state, label='restore_verify')
                    self._state['restore_verification'] = {'write_ok': ok, **detail}
                    if not ok or not matches:
                        self._state['error'] = RESTORE_ERROR
                except Exception as exc:  # noqa: BLE001
                    self._state.update(error=RESTORE_ERROR, restore_verification={'error': str(exc)})
                self._state['restoring'] = False
            self._close_port()
            self._done.set()
            self._ready.set()

    def _close_port(self):
        if self._port is not None:
            try:
                self._port.close()
            except Exception:  # noqa: BLE001 - Abschluss auch bei Portfehler
                pass

    def request_stop(self):
        """Keine weiteren Planschritte; Rueckstellung erfolgt im Leserthread."""
        if self._stop_deadline is None:
            self._stop_deadline = time.monotonic() + (JOIN_TIMEOUT_S if self._schedule else 2.0)
        self._stop.set()

    def stop(self):
        with self._stop_lock:
            self.request_stop()
            deadline = self._stop_deadline
            if self._reader is not None:
                self._reader.join(max(0, deadline - time.monotonic()))
                if self._reader.is_alive():
                    self._state['error'] = RESTORE_ERROR if self._schedule else 'Referenzthread haengt'
                    self._state['restoring'] = False
                    self._close_port()
                    self._done.set()
            if self._writer is not None:
                self._writer.join(max(0, deadline - time.monotonic()))
                if self._writer.is_alive():
                    self._state.setdefault('error', 'Referenz-Schreibthread haengt')
            return self.status()
