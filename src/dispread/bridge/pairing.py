"""Owner-local SQLite credentials: hashed, transport-scoped and revocable."""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path

from dispread.bridge.identity import _private_fd, private_directory

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_TOKEN = re.compile(r"(?:[A-Za-z0-9_-]{43}|[0-9a-f]{64})\Z")


class PairingError(ValueError):
    """Credential refused; exception never contains credential material."""


def _client(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("invalid client ID")


def _transport(value):
    if value not in ("network", "uart"):
        raise ValueError("invalid pairing transport")


def _digest(value):
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise PairingError("invalid credential")
    return hashlib.sha256(value.encode("ascii")).hexdigest()


class PairingStore:
    """Each directory belongs to one provisioned Pi; tokens never authorize a run.

    Offers use monotonic time and the kernel boot ID, so wall clock correction
    cannot extend them and reboot expires them. Clients persist until revoked.
    Failed redemption is limited to five attempts per client per minute and
    twenty across all clients, so rotating client IDs cannot bypass it.
    """

    def __init__(self, directory: Path, clock=time.monotonic):
        self.directory = private_directory(Path(directory))
        self.clock = clock
        self.boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        self.path = self.directory / "pairing.sqlite3"
        os.close(_private_fd(self.path, os.O_CREAT | os.O_RDWR))
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS offers (
                    hash TEXT PRIMARY KEY, transport TEXT NOT NULL, client_id TEXT,
                    expires REAL NOT NULL, boot_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS clients (
                    hash TEXT PRIMARY KEY, client_id TEXT NOT NULL, transport TEXT NOT NULL,
                    UNIQUE(client_id, transport));
                CREATE TABLE IF NOT EXISTS failures (
                    client_id TEXT NOT NULL, at REAL NOT NULL, boot_id TEXT NOT NULL);
            """)

    @contextlib.contextmanager
    def _connect(self):
        # Rollback journal inherits database mode 0600; never use WAL with secrets.
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_offer(self, transport: str, client_id: str | None = None) -> str:
        _transport(transport)
        if client_id is not None:
            _client(client_id)
        offer = secrets.token_urlsafe(32)
        now = self.clock()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM offers WHERE boot_id != ? OR expires <= ?", (self.boot_id, now))
            if db.execute("SELECT count(*) FROM offers").fetchone()[0] >= 128:
                raise PairingError("too many pending pairing offers")
            db.execute("INSERT INTO offers VALUES (?, ?, ?, ?, ?)", (_digest(offer), transport, client_id, now + 300, self.boot_id))
            db.commit()
        return offer

    def redeem_offer(self, offer: str, client_id: str, transport: str) -> str:
        _client(client_id)
        _transport(transport)
        try:
            digest = _digest(offer)
        except PairingError:
            digest = ""  # Malformed attempts count against the same limiter.
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Lock acquisition can wait; expiry/rate decisions need the time
            # at the atomic redemption decision, never a pre-wait snapshot.
            now = self.clock()
            db.execute("DELETE FROM failures WHERE boot_id != ? OR at <= ?", (self.boot_id, now - 60))
            if (
                db.execute("SELECT count(*) FROM failures WHERE client_id = ?", (client_id,)).fetchone()[0] >= 5
                or db.execute("SELECT count(*) FROM failures").fetchone()[0] >= 20
            ):
                raise PairingError("pairing rate limit reached")
            row = db.execute("SELECT transport, client_id, expires, boot_id FROM offers WHERE hash = ?", (digest,)).fetchone()
            if row is None or row[0] != transport or row[1] not in (None, client_id) or now >= row[2] or row[3] != self.boot_id:
                db.execute("INSERT INTO failures VALUES (?, ?, ?)", (client_id, now, self.boot_id))
                db.commit()
                raise PairingError("pairing offer refused or expired")
            token = secrets.token_urlsafe(32)
            db.execute("DELETE FROM offers WHERE hash = ?", (digest,))
            db.execute("DELETE FROM clients WHERE client_id = ? AND transport = ?", (client_id, transport))
            db.execute("INSERT INTO clients VALUES (?, ?, ?)", (_digest(token), client_id, transport))
            db.commit()
        return token

    def authorize(self, token: str, transport: str) -> str:
        _transport(transport)
        digest = _digest(token)
        with self._connect() as db:
            row = db.execute("SELECT client_id FROM clients WHERE hash = ? AND transport = ?", (digest, transport)).fetchone()
        if row is None:
            raise PairingError("client credential refused")
        return row[0]

    def revoke(self, client_id: str) -> None:
        _client(client_id)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM clients WHERE client_id = ?", (client_id,))
            db.execute("DELETE FROM offers WHERE client_id = ?", (client_id,))
            db.commit()
