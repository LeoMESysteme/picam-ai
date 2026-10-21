"""Begrenzte Rohbilddiagnose neben dem Messpfad, ohne eigene Kamera.

Ein Worker kodiert PNG (Stufe 1: verlustfrei, geringe CPU-Last) und schreibt.
Keine Niceness-Aenderung, keine Threads je Bild. Ein Abschluss-Thread wartet
nach Laufende auf den Worker und kopiert erst dann die ruhende Zwischenablage.
Trigger-Abstaende gelten in Host-Monotonzeit, nie als Aufnahmelatenz.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import threading
import time
from pathlib import Path

import cv2

# Verlustbeginn sofort, danach maximal einmal je Sekunde; Rueckkehr sofort.
LOSS_INTERVAL_S = 1.0
# Bei guter Nachfuehrung alle 30 s, erstmals 30 s nach Start.
PERIODIC_INTERVAL_S = 30.0
MAX_IMAGES = 300
MAX_BYTES = 600_000_000
SPACE_MARGIN_BYTES = 200_000_000
MEMORY_RESERVE_BYTES = 500_000_000
MEMORY_CHECK_INTERVAL_S = 1.0
MARK_INTERVAL_S = 2.0
QUEUE_SIZE = 8
PNG_COMPRESSION = 1


def read_mem_available(path=Path('/proc/meminfo')):
    """Verfuegbarer Hauptspeicher in Bytes; tmpfs-Freiraum reicht nicht (Swap)."""
    for line in Path(path).read_text().splitlines():
        fields = line.split()
        if fields and fields[0] == 'MemAvailable:':
            if len(fields) == 3 and fields[2] == 'kB' and int(fields[1]) >= 0:
                return int(fields[1]) * 1024
            break
    raise ValueError('MemAvailable in /proc/meminfo fehlt oder ist ungueltig')


def staging_leftovers(root, *, exclude=()):
    """Rettbare Ablagen nur melden, niemals automatisch entfernen."""
    result = []
    for path in sorted(Path(root).glob('dispread-diagnose-*')):
        if str(path) in exclude or path.is_symlink() or not path.is_dir():
            continue
        try:
            size = sum(p.stat().st_size for p in path.rglob('*') if not p.is_symlink() and p.is_file())
            result.append({'path': str(path), 'bytes': size})
        except OSError as exc:
            result.append({'path': str(path), 'bytes': None, 'error': str(exc)})
    return result


class DiagnosticRecorder:
    def __init__(self, out_dir, *, enabled=False, staging_root=Path('/dev/shm'),
                 monotonic=time.monotonic, memory_available=None):
        self.out_dir = Path(out_dir)
        self.staging = Path(staging_root) / f'dispread-diagnose-{self.out_dir.parent.name}-{self.out_dir.name}'
        self._requested = enabled
        self._monotonic = monotonic
        self._memory_available = memory_available or read_mem_available
        self._last_memory_check = 0.0
        self._memory_ok = True
        self._full = False
        self._last_mark = None
        self._lock = threading.Lock()
        # Ein zusaetzlicher Platz bleibt fuer das Stop-Sentinel reserviert.
        self._queue = queue.Queue(maxsize=QUEUE_SIZE + 1)
        self._stop = threading.Event()
        self._done = threading.Event()
        self._worker = self._finisher = None
        self._copying = False
        self._latest = None
        self._lost = False
        self._last_loss = 0.0
        self._last_good = 0.0
        self._pending_marks: list[int] = []
        self._state = dict(enabled=False, reason='vom Bediener deaktiviert', saved=0,
                           dropped_queue=0, dropped_limit=0, dropped_memory=0, dropped_mark_rate=0,
                           write_errors=0, first_error=None,
                           bytes=0, staging=None, copied=False)

    def status(self):
        with self._lock:
            return dict(self._state)

    @property
    def copying(self):
        with self._lock:
            return self._copying

    def start(self, *, profile_sha256, reference_sha256):
        self._hashes = dict(profile_sha256=profile_sha256, reference_frame_sha256=reference_sha256)
        if not self._requested:
            return
        try:
            self._last_good = self._monotonic()
            if shutil.disk_usage(self.staging.parent).free < MAX_BYTES + SPACE_MARGIN_BYTES:
                self._state['reason'] = 'Zu wenig freier Platz im RAM: 600 MB plus 200 MB Reserve erforderlich'
                return
            if self._memory_available() < MAX_BYTES + MEMORY_RESERVE_BYTES:
                self._state['reason'] = 'Zu wenig MemAvailable: 600 MB plus 500 MB Hauptspeicherreserve erforderlich'
                return
            self._last_memory_check = self._monotonic()
            self.staging.mkdir()  # Bestehende Diagnose niemals ueberschreiben.
            self._state.update(enabled=True, reason=None, staging=str(self.staging))
            self._worker = threading.Thread(target=self._write, name='diagnose-writer', daemon=True)
            self._worker.start()
        except Exception as exc:  # noqa: BLE001 - Diagnose darf Laufstart nicht verhindern
            self._error(exc)
            self._state.update(enabled=False, reason=f'Diagnose nicht verfuegbar: {exc}')

    def _error(self, exc):
        with self._lock:
            self._state['write_errors'] += 1
            if self._state['first_error'] is None:
                self._state['first_error'] = f'{type(exc).__name__}: {exc}'

    def observe(self, frame, record, track, *, owner_sequence, mode):
        if not self._state['enabled'] or self._stop.is_set():
            return
        try:
            now = self._monotonic()
            lost = any(r.startswith('tracking_lost:') for r in record.reject_reasons)
            metadata = {
                **self._hashes, 'frame_sequence': frame.frame_sequence, 'owner_sequence': owner_sequence,
                'camera_sequence': frame.raw_metadata.get('sequence'),
                'capture_timestamp': frame.capture_timestamp.to_dict(),
                'tracking': {'mode': mode, **{key: getattr(track, key, None)
                    for key in ('reason', 'score', 'shift', 'rotation_deg', 'quad')}},
                'status': record.status.value, 'reject_reasons': list(record.reject_reasons),
            }
            with self._lock:
                self._latest = (frame.image, metadata)
                pending, self._pending_marks = self._pending_marks, []
            if lost:
                if not self._lost or now - self._last_loss >= LOSS_INTERVAL_S:
                    self._enqueue('tracking_loss')
                    self._last_loss = now
            elif self._lost:
                self._enqueue('tracking_recovered')
                self._last_good = now
            elif now - self._last_good >= PERIODIC_INTERVAL_S:
                self._enqueue('periodic')
                self._last_good = now
            self._lost = lost
            # Vor dem ersten Bild gemeldete Marken beziehen sich auf dieses Bild.
            for mark in pending:
                self._enqueue('operator_mark', mark=mark)
        except Exception as exc:  # noqa: BLE001 - keinerlei Rueckwirkung auf Records
            self._error(exc)

    def mark(self, number):
        with self._lock:
            if not self._state['enabled'] or self._stop.is_set():
                return
            now = self._monotonic()
            if self._last_mark is not None and now - self._last_mark < MARK_INTERVAL_S:
                self._state['dropped_mark_rate'] += 1
                return
            self._last_mark = now
            if self._latest is None:
                if len(self._pending_marks) < QUEUE_SIZE:
                    self._pending_marks.append(number)
                else:
                    self._state['dropped_queue'] += 1
                return
        self._enqueue('operator_mark', mark=number)

    def _enqueue(self, trigger, **extra):
        try:
            with self._lock:
                if self._stop.is_set():
                    return
                if self._state['saved'] >= MAX_IMAGES or self._full:
                    self._state['dropped_limit'] += 1
                    return
                now = self._monotonic()
                if now - self._last_memory_check >= MEMORY_CHECK_INTERVAL_S:
                    self._last_memory_check = now
                    # Bei Lesefehlern ebenfalls keine neuen Bilder annehmen.
                    self._memory_ok = False
                    self._memory_ok = self._memory_available() >= MEMORY_RESERVE_BYTES
                if not self._memory_ok:
                    self._state['dropped_memory'] += 1
                    return
                if self._queue.qsize() >= QUEUE_SIZE:
                    self._state['dropped_queue'] += 1
                    return
                image, metadata = self._latest
            # Snapshot, falls ein injizierter Bildlieferant seinen Puffer wiederverwendet.
            snapshot = image.copy()
            with self._lock:
                if self._stop.is_set():
                    return
                if self._queue.qsize() >= QUEUE_SIZE:
                    self._state['dropped_queue'] += 1
                    return
                self._queue.put_nowait((snapshot, {**metadata, 'trigger': trigger, **extra}))
        except queue.Full:
            with self._lock:
                self._state['dropped_queue'] += 1
        except Exception as exc:  # noqa: BLE001
            self._error(exc)

    def _write(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            image, metadata = item
            try:
                self._save(image, metadata)
            except Exception as exc:  # noqa: BLE001 - Fehler zaehlen und weiterarbeiten
                self._error(exc)

    def _save(self, image, metadata):
        state = self.status()
        if state['saved'] >= MAX_IMAGES or self._full:
            with self._lock:
                self._state['dropped_limit'] += 1
            return
        ok, encoded = cv2.imencode('.png', image, [cv2.IMWRITE_PNG_COMPRESSION, PNG_COMPRESSION])
        if not ok:
            raise OSError('PNG-Kodierung fehlgeschlagen')
        path = self.staging / f"{state['saved'] + 1:04d}.png"
        line = (json.dumps({**metadata, 'image': path.name}, ensure_ascii=False) + '\n').encode('utf-8')
        size = encoded.nbytes + len(line)
        if state['bytes'] + size > MAX_BYTES:
            with self._lock:
                self._full = True
                self._state['dropped_limit'] += 1
            return
        index = self.staging / 'images.jsonl'
        previous = index.stat().st_size if index.exists() else 0
        try:
            path.write_bytes(encoded.tobytes())
            with index.open('ab') as stream:
                stream.write(line)
        except Exception:
            path.unlink(missing_ok=True)
            if index.exists():
                with index.open('r+b') as stream:
                    stream.truncate(previous)
            raise
        with self._lock:
            self._state['saved'] += 1
            self._state['bytes'] += size

    def stop(self, on_done=None):
        """Sofort zurueckkehren; weder Kodierung noch Kopieren im Stop-Pfad."""
        with self._lock:
            if self._stop.is_set():
                return
            self._stop.set()
            self._latest = None
            # Marken ohne ein einziges verarbeitetes Bild bleiben als Text erhalten.
            self._state['dropped_queue'] += len(self._pending_marks)
            self._pending_marks.clear()
        if self._worker is None:
            self._done.set()
            return
        with self._lock:
            self._copying = True
        self._queue.put_nowait(None)
        self._finisher = threading.Thread(target=self._finish, args=(on_done,), name='diagnose-copy', daemon=True)
        try:
            self._finisher.start()
        except Exception as exc:  # noqa: BLE001 - auch Threadmangel darf Stop nicht abbrechen
            self._error(exc)
            with self._lock:
                self._copying = False
            self._done.set()

    def _finish(self, on_done):
        try:
            self._worker.join()
            target = self.out_dir / 'diagnose'
            target.mkdir(parents=True)
            for source in self.staging.iterdir():
                dest = target / source.name
                shutil.copyfile(source, dest)
                with dest.open('rb') as stream:
                    os.fsync(stream.fileno())
                if source.stat().st_size != dest.stat().st_size:
                    raise OSError(f'Diagnosekopie unvollstaendig: {dest}')
            fd = os.open(target, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            shutil.rmtree(self.staging)
            with self._lock:
                self._state['copied'] = True
        except Exception as exc:  # noqa: BLE001 - Zwischenablage fuer Rettung behalten
            self._error(exc)
        finally:
            try:
                if on_done is not None:
                    on_done()
            except Exception as exc:  # noqa: BLE001 - Status zeigt auch Metadatenfehler
                self._error(exc)
            finally:
                with self._lock:
                    self._copying = False
                self._done.set()

    def wait(self, timeout=None):
        """Fuer Dienstende/Abschlussbeobachter, nie im Pipeline-Stop."""
        return self._done.wait(timeout)
