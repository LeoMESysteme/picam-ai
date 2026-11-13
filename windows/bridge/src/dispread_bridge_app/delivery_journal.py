"""Durable COM submission evidence; never a claim of GSVmulti receipt.

Run evidence is deliberately never pruned. Only the separate detail store has
bounded retention. Pending intents are unknown after interruption and cannot
be reclaimed automatically.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from dispread.bridge.types import BridgeEvent
from dispread.gsv_bridge import DeliveryAlreadyAttempted, DeliveryBlockedError
from dispread.records import TimeBaseKind


class JournalError(RuntimeError):
    """No safe durable claim can be made."""


@dataclass(frozen=True)
class TickAttempt:
    """Eine COM-Zeile des Vierkanal-Takts: Pi-Takt (``tick``) oder Windows-Auffuellung (``fill``)."""

    attempt_id: str
    pi_id: str
    run_id: str
    seq: int
    kind: str
    valid: bool
    payload_digest: str
    outcome: str


TICK_KINDS = ('tick', 'fill')


@dataclass(frozen=True)
class Attempt:
    attempt_id: str
    pi_id: str
    run_id: str
    frame_sequence: int
    barrier_id: int | None
    payload_digest: str
    outcome: str


class DeliveryJournal:
    """SQLite FULL synchronous commits precede and follow each COM call.

    Absent barriers normalize to -1 so SQLite's NULL uniqueness exception cannot
    permit concurrent numeric claims. BEGIN IMMEDIATE also serializes the
    Pi-wide invalidation check and the insertion across separate processes.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._owned_attempts = set()
        self._clock_domain = uuid.uuid4().hex
        self._db = sqlite3.connect(self.path, timeout=5, check_same_thread=False)
        try:
            self._db.execute('PRAGMA journal_mode=DELETE')
            self._db.execute('PRAGMA synchronous=FULL')
            self._db.execute('''CREATE TABLE IF NOT EXISTS attempts (
                attempt_id TEXT PRIMARY KEY, pi_id TEXT NOT NULL, run_id TEXT NOT NULL,
                frame_sequence INTEGER NOT NULL, barrier_key INTEGER NOT NULL,
                payload_digest TEXT NOT NULL, outcome TEXT NOT NULL,
                created_ns INTEGER NOT NULL, finished_ns INTEGER,
                time_base TEXT NOT NULL, clock_domain TEXT NOT NULL,
                UNIQUE(pi_id, run_id, frame_sequence, barrier_key))''')
            # B2 (2026-11-11): eine Zeile je COM-Schreibvorgang des Vierkanal-Takts.
            # Auffuellungen haben eine eigene Art: ein nicht geschriebener Pi-Takt
            # (expired) wird spaeter als Fehlwertzeile derselben Nummer aufgefuellt.
            # Geschrieben wird je Nummer hoechstens einmal (nur oberhalb der
            # hoechsten geschriebenen Nummer, BridgeSession).
            self._db.execute('''CREATE TABLE IF NOT EXISTS ticks (
                attempt_id TEXT PRIMARY KEY, pi_id TEXT NOT NULL, run_id TEXT NOT NULL,
                seq INTEGER NOT NULL, kind TEXT NOT NULL, valid INTEGER NOT NULL,
                payload_digest TEXT NOT NULL, outcome TEXT NOT NULL,
                created_ns INTEGER NOT NULL, finished_ns INTEGER,
                time_base TEXT NOT NULL, clock_domain TEXT NOT NULL,
                UNIQUE(pi_id, run_id, seq, kind))''')
            self._db.execute('''CREATE TABLE IF NOT EXISTS tick_gaps (
                pi_id TEXT NOT NULL, run_id TEXT NOT NULL, seq INTEGER NOT NULL,
                missing INTEGER NOT NULL, created_ns INTEGER NOT NULL,
                time_base TEXT NOT NULL, clock_domain TEXT NOT NULL,
                UNIQUE(pi_id, run_id, seq))''')
            self._db.commit()
        except BaseException:
            self._db.close()
            raise

    @staticmethod
    def _identity(pi_id, run_id, frame_sequence, barrier_id, payload):
        if (not isinstance(pi_id, str) or not pi_id or len(pi_id) > 256
                or not isinstance(run_id, str) or not run_id or len(run_id) > 256
                or type(frame_sequence) is not int or not 0 <= frame_sequence < 2**63
                or (barrier_id is not None and
                    (type(barrier_id) is not int or not 0 < barrier_id < 2**63))
                or not isinstance(payload, bytes) or not payload or len(payload) > 4096):
            raise JournalError('invalid delivery identity/payload')
        return (pi_id, run_id, frame_sequence, -1 if barrier_id is None else barrier_id,
                hashlib.sha256(payload).hexdigest())

    def _existing(self, identity):
        row = self._db.execute('''SELECT payload_digest, outcome FROM attempts
            WHERE pi_id=? AND run_id=? AND frame_sequence=? AND barrier_key=?''',
                               identity[:4]).fetchone()
        if row and row[0] != identity[4]:
            raise JournalError('delivery identity bound to different payload')
        return None if row is None else row[1]

    def _blocked(self, pi_id):
        return self._db.execute('''SELECT 1 FROM attempts WHERE pi_id=? AND barrier_key>0
            AND outcome IN ('pending', 'unknown') LIMIT 1''', (pi_id,)).fetchone() is not None

    def has_unresolved_invalidation(self, pi_id) -> bool:
        with self._lock:
            return self._blocked(pi_id)

    def begin_attempt(self, pi_id, run_id, frame_sequence, barrier_id, payload: bytes) -> str:
        identity = self._identity(pi_id, run_id, frame_sequence, barrier_id, payload)
        with self._lock:
            try:
                self._db.execute('BEGIN IMMEDIATE')
                outcome = self._existing(identity)
                if self._blocked(pi_id):
                    raise DeliveryBlockedError('unknown invalidation blocks this Pi')
                if outcome is not None:
                    raise DeliveryAlreadyAttempted(outcome)
                attempt_id = uuid.uuid4().hex
                self._db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?,NULL,?,?)',
                                 (attempt_id, *identity, 'pending', time.monotonic_ns(),
                                  TimeBaseKind.HOST_MONOTONIC.value, self._clock_domain))
                self._db.commit()
                self._owned_attempts.add(attempt_id)
                return attempt_id
            except BaseException:
                self._db.rollback()
                raise

    @staticmethod
    def _tick_identity(pi_id, run_id, seq, kind, valid, payload):
        if (not isinstance(pi_id, str) or not pi_id or len(pi_id) > 256
                or not isinstance(run_id, str) or not run_id or len(run_id) > 256
                or type(seq) is not int or not 0 < seq < 2**63 or kind not in TICK_KINDS
                or type(valid) is not bool or (kind == 'fill' and valid)
                or not isinstance(payload, bytes) or not payload or len(payload) > 4096):
            raise JournalError('invalid tick identity/payload')
        return pi_id, run_id, seq, kind, int(valid), hashlib.sha256(payload).hexdigest()

    def _tick_blocked(self, pi_id):
        return self._db.execute('''SELECT 1 FROM ticks WHERE pi_id=?
            AND outcome IN ('pending', 'unknown') LIMIT 1''', (pi_id,)).fetchone() is not None

    def has_unresolved_tick(self, pi_id) -> bool:
        with self._lock:
            return self._tick_blocked(pi_id)

    def begin_tick(self, pi_id, run_id, seq, kind, valid, payload: bytes) -> str:
        """Dauerhafte Absicht vor genau einer COM-Zeile; offene Zeilen sperren den Pi."""
        identity = self._tick_identity(pi_id, run_id, seq, kind, valid, payload)
        with self._lock:
            try:
                self._db.execute('BEGIN IMMEDIATE')
                row = self._db.execute('''SELECT payload_digest, outcome FROM ticks
                    WHERE pi_id=? AND run_id=? AND seq=? AND kind=?''', identity[:4]).fetchone()
                if self._blocked(pi_id) or self._tick_blocked(pi_id):
                    if row is not None:
                        raise DeliveryAlreadyAttempted(row[1])
                    raise DeliveryBlockedError('unknown delivery blocks this Pi')
                if row is not None:
                    raise DeliveryAlreadyAttempted(row[1])
                attempt_id = uuid.uuid4().hex
                self._db.execute('INSERT INTO ticks VALUES (?,?,?,?,?,?,?,?,?,NULL,?,?)',
                                 (attempt_id, *identity, 'pending', time.monotonic_ns(),
                                  TimeBaseKind.HOST_MONOTONIC.value, self._clock_domain))
                self._db.commit()
                self._owned_attempts.add(attempt_id)
                return attempt_id
            except BaseException:
                self._db.rollback()
                raise

    def finish_tick(self, attempt_id, outcome: str):
        if outcome not in ('written', 'unknown', 'not_written'):
            raise JournalError('invalid delivery outcome')
        with self._lock:
            try:
                self._db.execute('BEGIN IMMEDIATE')
                row = self._db.execute('SELECT outcome FROM ticks WHERE attempt_id=?', (attempt_id,)).fetchone()
                if row is None:
                    raise JournalError('unknown attempt')
                if row[0] != 'pending':
                    raise JournalError('terminal outcome cannot be changed')
                if attempt_id not in self._owned_attempts:
                    raise JournalError('attempt has no live claim; orphan remains unknown')
                self._db.execute('UPDATE ticks SET outcome=?,finished_ns=? WHERE attempt_id=?',
                                 (outcome, time.monotonic_ns(), attempt_id))
                self._db.commit()
                self._owned_attempts.discard(attempt_id)
            except BaseException:
                self._db.rollback()
                raise

    def last_tick_written(self, pi_id, run_id) -> int:
        """Hoechste geschriebene Taktnummer (Pi-Takt oder Auffuellung), sonst 0."""
        with self._lock:
            row = self._db.execute("""SELECT MAX(seq) FROM ticks WHERE pi_id=? AND run_id=?
                AND outcome='written'""", (pi_id, run_id)).fetchone()
        return row[0] or 0

    def tick_outcome(self, pi_id, run_id, seq):
        with self._lock:
            row = self._db.execute("""SELECT outcome FROM ticks WHERE pi_id=? AND run_id=? AND seq=?
                AND kind='tick'""", (pi_id, run_id, seq)).fetchone()
        return None if row is None else row[0]

    def record_tick_gap(self, pi_id, run_id, seq, missing):
        """Nicht aufgefuellte Luecke (> Fenster): Ausgabe gestoert, Zeilenzahl weicht ab."""
        with self._lock:
            try:
                self._db.execute('BEGIN IMMEDIATE')
                self._db.execute('INSERT OR IGNORE INTO tick_gaps VALUES (?,?,?,?,?,?,?)',
                                 (pi_id, run_id, seq, missing, time.monotonic_ns(),
                                  TimeBaseKind.HOST_MONOTONIC.value, self._clock_domain))
                self._db.commit()
            except BaseException:
                self._db.rollback()
                raise

    def tick_gaps(self, pi_id, run_id):
        with self._lock:
            rows = self._db.execute('''SELECT seq, missing FROM tick_gaps WHERE pi_id=? AND run_id=?
                ORDER BY seq''', (pi_id, run_id)).fetchall()
        return tuple(tuple(row) for row in rows)

    def tick_attempts(self) -> tuple[TickAttempt, ...]:
        with self._lock:
            rows = self._db.execute('''SELECT attempt_id,pi_id,run_id,seq,kind,valid,payload_digest,outcome
                FROM ticks ORDER BY rowid''').fetchall()
        return tuple(TickAttempt(*row[:5], bool(row[5]), *row[6:]) for row in rows)

    def unresolved_ticks(self) -> tuple[TickAttempt, ...]:
        return tuple(row for row in self.tick_attempts() if row.outcome in ('pending', 'unknown'))

    def finish_attempt(self, attempt_id, outcome: str):
        if outcome not in ('written', 'unknown', 'not_written'):
            raise JournalError('invalid delivery outcome')
        with self._lock:
            try:
                self._db.execute('BEGIN IMMEDIATE')
                row = self._db.execute('SELECT outcome FROM attempts WHERE attempt_id=?',
                                       (attempt_id,)).fetchone()
                if row is None:
                    raise JournalError('unknown attempt')
                if row[0] != 'pending':
                    raise JournalError('terminal outcome cannot be changed')
                if attempt_id not in self._owned_attempts:
                    raise JournalError('attempt has no live claim; orphan remains unknown')
                self._db.execute('UPDATE attempts SET outcome=?,finished_ns=? WHERE attempt_id=?',
                                 (outcome, time.monotonic_ns(), attempt_id))
                self._db.commit()
                self._owned_attempts.discard(attempt_id)
            except BaseException:
                self._db.rollback()
                raise

    def receipt(self, pi_id, run_id, frame_sequence, barrier_id, payload: bytes):
        identity = self._identity(pi_id, run_id, frame_sequence, barrier_id, payload)
        with self._lock:
            return self._existing(identity)

    def should_emit(self, pi_id, run_id, frame_sequence, barrier_id, payload: bytes) -> bool:
        """Advisory only: begin_attempt is the atomic authorization to write."""
        identity = self._identity(pi_id, run_id, frame_sequence, barrier_id, payload)
        with self._lock:
            return self._existing(identity) is None and not self._blocked(pi_id)

    def attempts(self) -> tuple[Attempt, ...]:
        with self._lock:
            rows = self._db.execute('''SELECT attempt_id,pi_id,run_id,frame_sequence,
                barrier_key,payload_digest,outcome FROM attempts ORDER BY rowid''').fetchall()
        return tuple(Attempt(*row[:4], None if row[4] == -1 else row[4], *row[5:]) for row in rows)

    def unresolved(self) -> tuple[Attempt, ...]:
        return tuple(row for row in self.attempts() if row.outcome in ('pending', 'unknown'))

    def close(self):
        with self._lock:
            self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# Diagnostics accept only structured fields, never arbitrary exception/request
# strings. Unknown field names are removed rather than risking credential leaks.
_PUBLIC_FIELDS = frozenset({'type', 'outcome', 'state', 'completion_stage', 'provisional',
                            'time_base', 't_ns', 'bytes', 'error_code', 'nested',
                            'kind', 'code', 'detail', 'demo_only', 'output_ready',
                            'gsv_receipt_confirmed', 'count', 'release', 'ts'})


_PUBLIC_VALUES = frozenset({
    'started', 'stopped', 'connected', 'idle', 'ended', 'exchange', 'written',
    'unknown', 'pending', 'not_written', 'expired', 'failed', 'audit_failed',
    'connection_failed', 'blocked', 'unknown_invalidation', 'unknown_delivery',
    'recovering', 'connection_unavailable',
    'com_driver_write', 'host_monotonic', 'synthetic',
    'written_summary', 'diagnostics', 'dropped',
    'omitted', 'test_unaccepted', 'test_release',
    'tick_disturbed', 'tick_gap_unfilled',
    # Ereignisarten und Fehlercodes aus dem eigenen Code (feste Bezeichner, keine
    # Transportdaten). 13.11.2026: ohne sie war die Ursache eines UART-Abbruchs im
    # Export nicht erkennbar („[redacted]/[redacted]“).
    'connection', 'activity', 'heartbeat', 'peer_output_changed', 'connecting', 'authenticated',
    'backoff', 'disconnected', 'network', 'uart',
    'adapter_driver_unavailable', 'adapter_required', 'adapter_unavailable', 'authentication_refused',
    'cancelled', 'connection_lost', 'demo_rejected', 'demo_unconfirmed', 'invalid_legacy_request',
    'lease_unavailable', 'network_unavailable', 'no_pending_poll', 'not_connected', 'pairing_refused',
    'pairing_required', 'peer_invalid', 'redirect_refused', 'run_changed', 'run_conflict',
    'selection_required', 'stale_ack', 'transport_unsupported', 'transport_write_uncertain',
    'uart_peer_unavailable',
})


def _redacted(value):
    if isinstance(value, BridgeEvent):
        value = asdict(value)
    if isinstance(value, dict):
        return {key: _redacted(item) for key, item in value.items()
                if key in _PUBLIC_FIELDS}
    if isinstance(value, (list, tuple)):
        return [_redacted(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    # Public strings are machine identifiers, not transport data or errors.
    if isinstance(value, str) and value in _PUBLIC_VALUES:
        return value
    return '[redacted]'


class DiagnosticStore:
    """Separate rotating detail files; audit.sqlite and run evidence are untouched."""

    def __init__(self, path, *, max_bytes=64 * 1024 * 1024, max_age_s=7 * 86400,
                 clock=time.time):
        if not 0 < max_bytes <= 64 * 1024 * 1024 or not 0 < max_age_s <= 7 * 86400:
            raise ValueError('diagnostic retention must be at most 64 MiB / 7 days')
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.max_bytes, self.max_age_s, self.clock = max_bytes, max_age_s, clock
        self._lock = threading.RLock()
        self._active = None
        self.prune()

    def _files(self):
        return sorted(self.path.glob('detail-*.jsonl'), key=lambda p: p.stat().st_mtime)

    def prune(self, reserve=0, *, reserve_file=False):
        with self._lock:
            files = self._files()
            total = sum(path.stat().st_size for path in files)
            cutoff = self.clock() - self.max_age_s
            count = len(files)
            for path in files:
                stat = path.stat()
                if (stat.st_mtime < cutoff or total + reserve > self.max_bytes
                        or (reserve_file and count >= 128)):
                    path.unlink()
                    total -= stat.st_size
                    count -= 1

    def append(self, event):
        record = _redacted(event)
        if isinstance(record, dict):
            record['ts'] = round(self.clock(), 3)    # Unix-Sekunden je Zeile; ohne Zeit kein Ablauf
        payload = (json.dumps(record, allow_nan=False) + '\n').encode('utf-8')
        if len(payload) > self.max_bytes:
            raise JournalError('diagnostic event exceeds retention budget')
        with self._lock:
            self.prune(len(payload))
            path = self._active
            if (path is None or not path.exists()
                    or path.stat().st_size + len(payload) > min(1024 * 1024, self.max_bytes)):
                self.prune(len(payload), reserve_file=True)
                path = self.path / f'detail-{uuid.uuid4().hex}.jsonl'
                self._active = path
            old_size = path.stat().st_size if path.exists() else 0
            # mtime represents the FIRST event in a segment. Appending cannot
            # keep old details alive beyond seven days; rotation can remove
            # younger details alongside old ones, never extend their lifetime.
            created = path.stat().st_mtime if path.exists() else self.clock()
            try:
                with path.open('ab') as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.utime(path, (created, created))
            except BaseException:
                # Preserve prior detail bytes when a partial append fails.
                try:
                    if old_size:
                        with path.open('r+b') as stream:
                            stream.truncate(old_size)
                    else:
                        path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise

    def usage(self):
        with self._lock:
            self.prune()
            return dict(bytes=sum(path.stat().st_size for path in self._files()),
                        max_bytes=self.max_bytes, max_age_s=self.max_age_s)

    def export(self):
        with self._lock:
            self.prune()
            events = []
            for path in self._files():
                for line in path.read_text('utf-8').splitlines():
                    events.append(json.dumps(_redacted(json.loads(line))))
            return '\n'.join(events)
