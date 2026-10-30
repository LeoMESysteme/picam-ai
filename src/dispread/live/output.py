"""Opt-in-UserDefined-Ausgang: ein offener Auftrag, kein Nachliefern.

Der Bildpfad reserviert nur einen Platz. Solange der Sender beschaeftigt
ist, werden neue Frames verworfen und belegt. Begonnene Telegramme werden
mit begrenzter Frist vervollstaendigt. Kein flush und kein Wiederverbinden. sent bezeichnet lokale Annahme, keinen Empfang.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, replace
from pathlib import Path

from dispread.records import InvalidValuePolicy, TxReceipt, ValueRecord
from dispread.sink.protocol.userdefined import UserDefinedFormatter
from dispread.sink.serial_out import SerialSink

# ME v2.6 S. 118–121, docs/GSVMULTI_PROTOCOL.md.
BAUDRATES = (2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)
REFERENCE_USB_ID = ('067b', '2303')  # docs/HARDWARE_PROFILE.md: PL2303 des GSV-2AS.
SYSFS_ROOT = Path('/sys')
# Konservativ die ganze 16-Zellen-Anzeige (live/setup.py N_CELLS), inkl. Vorzeichen/Punkt.
MAX_DISPLAY_TEXT_LENGTH = 16
MAX_TELEGRAM_BYTES = MAX_DISPLAY_TEXT_LENGTH + 1 + 2  # Praefix + CRLF.
FRAME_INTERVAL_NS = 33_000_000
MIN_LIVE_BAUDRATE = 9600  # 19 * 10 / 9600 = 19,79 ms; 4800 schon 39,58 ms.
WRITE_TIMEOUT_S = 1.0


def same_port(left: str, right: str) -> bool:
    return Path(left).resolve() == Path(right).resolve()


def is_reference_adapter(port: str, *, sysfs_root: Path | None = None) -> bool:
    """USB-Eltern anhand VID/PID pruefen, unabhaengig von ttyUSB-Steckreihenfolge."""
    root = SYSFS_ROOT if sysfs_root is None else Path(sysfs_root)
    root = root.resolve()
    device = (root / 'class/tty' / Path(port).resolve().name / 'device').resolve()
    for node in (device, *device.parents):
        if not node.is_relative_to(root):
            break
        try:
            vendor = (node / 'idVendor').read_text(encoding='ascii').strip().lower()
            product = (node / 'idProduct').read_text(encoding='ascii').strip().lower()
        except FileNotFoundError:
            continue
        return (vendor, product) == REFERENCE_USB_ID
    return False


def validate_output(value, *, reference_port: str | None = None, sysfs_root: Path | None = None) -> dict | None:
    """Vor Portzugriff pruefen; aktive Referenz und Debug bleiben gesperrt."""
    if value is None:
        return None
    try:
        if not isinstance(value, dict) or set(value) - {'port', 'baudrate', 'prefix', 'allow_reference_adapter'}:
            raise ValueError('Objekt mit Port, Baudrate und Präfix erforderlich')
        port = value.get('port')
        if not isinstance(port, str) or not port.strip() or '\x00' in port:
            raise ValueError('Port muss angegeben sein')
        allow = value.get('allow_reference_adapter', False)
        if type(allow) is not bool:
            raise ValueError('allow_reference_adapter muss bool sein')
        if same_port(port, '/dev/serial0'):
            raise ValueError('Debugport ist reserviert')
        if not allow and (same_port(port, '/dev/ttyUSB0') or is_reference_adapter(port, sysfs_root=sysfs_root)):
            raise ValueError('Referenzadapter 067b:2303 (PL2303) ist reserviert; allow_reference_adapter erforderlich')
        if reference_port and same_port(port, reference_port):
            raise ValueError('Port ist bereits fuer Referenz/Werteplan belegt')
        baudrate = value.get('baudrate', 115200)
        if type(baudrate) is not int or baudrate not in BAUDRATES:
            raise ValueError(f'Baudrate muss eine von {BAUDRATES} sein')
        if baudrate < MIN_LIVE_BAUDRATE or MAX_TELEGRAM_BYTES * 10 * 1_000_000_000 >= baudrate * FRAME_INTERVAL_NS:
            raise ValueError(f'Baudrate mindestens {MIN_LIVE_BAUDRATE}: {MAX_TELEGRAM_BYTES} Byte bei 8N1 unter 33 ms')
        prefix = value.get('prefix', '%')
        if not isinstance(prefix, str):
            raise ValueError('Präfix muss ein Zeichen sein')
        UserDefinedFormatter(prefix=prefix)
        return {'port': port, 'baudrate': baudrate, 'prefix': prefix, 'allow_reference_adapter': allow}
    except (ValueError, OSError, RuntimeError) as exc:
        raise ValueError(f'Ausgabe: {exc}') from exc


class LiveOutput:
    def __init__(self, options: dict, path: Path):
        self._options = validate_output(options)
        self._sink = SerialSink(self._options['port'], UserDefinedFormatter(prefix=self._options['prefix']),
                                baudrate=self._options['baudrate'], timeout=0, write_timeout=WRITE_TIMEOUT_S)
        self._path = path
        self._stream = None
        self._thread = None
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._pending = None
        self._busy = False
        self._closing = False
        self._failed = False
        self.failed_event = threading.Event()
        self._sequence = 0
        self._counts = dict(sent=0, omitted=0, dropped=0, errors=0)
        self._first_error = None

    def start(self, *, reference_port: str | None = None) -> None:
        validate_output(self._options, reference_port=reference_port)
        try:
            self._sink.open()  # Fehler vor dem ersten Leseschritt klar ablehnen.
            self._stream = self._path.open('x', encoding='utf-8')
            thread = threading.Thread(target=self._run, name='live-output', daemon=True)
            thread.start()
            self._thread = thread
        except Exception:
            self._sink.close()
            if self._stream is not None:
                self._stream.close()
            raise

    def status(self) -> dict:
        with self._lock:
            caps = asdict(self._sink.formatter.capabilities)
            caps['supported_invalid_policies'] = sorted(p.value for p in caps['supported_invalid_policies'])
            return {**self._options, 'capabilities': caps, **self._counts,
                    'first_error': self._first_error, 'enabled': not self._failed and not self._closing}

    def _error(self, message: str) -> None:
        self._counts['errors'] += 1
        self._first_error = self._first_error or message
        self._failed = True
        self.failed_event.set()

    def _receipt(self, record: ValueRecord, sequence: int, enqueue: int, **kwargs) -> TxReceipt:
        return TxReceipt(frame_sequence=record.frame_sequence, tx_sequence=sequence,
                         format_id=self._sink.formatter.capabilities.format_id,
                         t_enqueue_ns=enqueue, invalid_policy=InvalidValuePolicy.OMIT_RECORD, **kwargs)

    def submit(self, record: ValueRecord) -> None:
        # Nur Formatpruefung im Bildpfad; kein Zugriff auf den seriellen Treiber.
        payload = self._sink.formatter.format(record)
        enqueue = time.monotonic_ns()
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
            if payload is None:
                self._record(self._receipt(record, sequence, enqueue, wire_bytes=None,
                                           t_complete_ns=time.monotonic_ns(), omitted=True))
            elif self._busy or self._failed or self._closing:
                reason = 'output_failed' if self._failed else 'output_stopped' if self._closing else 'output_busy'
                self._record(self._receipt(record, sequence, enqueue, wire_bytes=payload,
                                           t_complete_ns=None, omitted=True, dropped=True, drop_reason=reason,
                                           bytes_written=0))
            elif len(payload) > MAX_TELEGRAM_BYTES:
                self._record(self._receipt(record, sequence, enqueue, wire_bytes=payload,
                                           t_complete_ns=None, error='Telegramm überschreitet Live-Längengrenze',
                                           bytes_written=0))
            else:
                self._busy = True
                self._pending = (record, sequence, enqueue, payload)
                self._wake.set()

    def _record(self, receipt: TxReceipt, *, count_error: bool = True) -> None:
        """Unter Lock; die Belegdatei wird nie waehrend eines Serial-Writes gesperrt."""
        if receipt.error and count_error:
            self._error(receipt.error)
        self._counts['omitted'] += int(receipt.omitted)
        self._counts['dropped'] += int(receipt.dropped)
        self._counts['sent'] += int(not receipt.omitted and receipt.t_complete_ns is not None)
        try:
            data = asdict(receipt)
            data['wire_bytes'] = None if receipt.wire_bytes is None else receipt.wire_bytes.hex()
            data['invalid_policy'] = receipt.invalid_policy.value
            data.update(time_base='host_monotonic', uncertainty_ns=None,
                        provisional=self._sink.formatter.capabilities.provisional)
            self._stream.write(json.dumps(data, ensure_ascii=False) + '\n')
            self._stream.flush()
        except Exception as exc:
            # Auch ValueError (z. B. geschlossene Datei) darf den Leser nicht beenden.
            self._error(f'Tx-Audit: {type(exc).__name__}: {exc}')

    def _run(self) -> None:
        pending = None
        receipt = None
        try:
            while True:
                self._wake.wait()
                with self._lock:
                    pending, self._pending = self._pending, None
                    self._wake.clear()
                    if pending is None:
                        if self._closing:
                            return
                        continue
                    record, sequence, enqueue, payload = pending
                    if self._closing:
                        self._record(self._receipt(record, sequence, enqueue, wire_bytes=payload,
                                                   t_complete_ns=None, omitted=True, dropped=True,
                                                   drop_reason='output_stopped', bytes_written=0))
                        return
                receipt = replace(self._sink.emit(record), tx_sequence=sequence, t_enqueue_ns=enqueue)
                with self._lock:
                    self._busy = False
                    self._record(receipt)
                pending = receipt = None
        except BaseException as exc:
            # Auch unerwartete Formatter-/Audit-/Threadfehler duerfen keinen toten,
            # scheinbar aktiven Ausgang hinterlassen. Niemals erneut formatieren.
            with self._lock:
                message = f'{type(exc).__name__}: {exc}'
                self._error(message)
                self._busy = False
                if pending is not None:
                    record, sequence, enqueue, payload = pending
                    failure = self._receipt(record, sequence, enqueue, wire_bytes=payload,
                                            t_complete_ns=None, error=message,
                                            bytes_written=None if receipt is None else receipt.bytes_written)
                    try:
                        # Fehler ist bereits gezaehlt; nur den bestmoeglichen Beleg schreiben.
                        self._record(failure, count_error=False)
                    except BaseException:
                        pass  # Status bleibt auch bei ausgefallenem Audit sichtbar.
        finally:
            with self._lock:
                self._busy = False

    def stop(self) -> None:
        with self._lock:
            self._closing = True
            self._wake.set()
        if self._thread is not None:
            self._thread.join()
        try:
            self._sink.close()
        except Exception as exc:
            with self._lock:
                self._error(f'Ausgabe schliessen: {exc}')
        if self._stream is not None:
            try:
                self._stream.close()
            except OSError as exc:
                with self._lock:
                    self._error(f'Tx-Audit schliessen: {exc}')
