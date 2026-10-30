#!/usr/bin/env python3
"""Bounded, resumable, standard-library-only session archive and statistics.

SQLite transactions checkpoint each source block, including its parser tail and
numeric samples. Snapshots contain only immutable gzip blocks and JSON metadata;
no source paths, images, or application imports are needed by their consumers.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import stat
import statistics
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

MAX_BLOCK = 1024 * 1024
# A /proc walk per guarded step is expensive; the deadline stays unconditional.
GUARD_INTERVAL_S = 0.1
# Published generations keep: current plus one previous (preferably exposed).
# Der Dienst kann den Runner-State nicht lesen; mehrere freigegebene Vorstände
# halten den Rückfall, falls der Runner die neueste Generation ablehnt.
KEEP_PREVIOUS = 3
# Statistics rules of records.jsonl. 2: explorer acceptance rule (string status
# and finite capture_timestamp.value_ns), rate (n-1)/duration. Archived runs
# with older rules are re-evaluated once from their stored blocks.
STATS_RULES = 2
SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}\Z")
BASES = {"sensor_boottime", "replay_recorded", "v4l2_monotonic"}



def _reject_constant(name):
    """NaN/Infinity sind kein JSON; JSON.parse im Explorer lehnt sie ebenso ab."""
    raise ValueError("non-standard JSON constant " + name)

class Deferred(Exception):
    """The caller's time slice or idle permission ended."""


def workbench_idle(proc_root=Path("/proc")):
    """Fail closed on unreadable process status; match module and executable CLI."""
    try:
        for entry in proc_root.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                args = (entry / "cmdline").read_bytes().split(b"\0")
            except FileNotFoundError:
                if entry.exists():
                    return False
                continue  # process exited during enumeration
            except OSError:
                return False
            decoded = [a.decode("utf-8", "replace") for a in args if a]
            if "serve" not in decoded:
                continue
            if any(Path(a).name in {"dispread", "dispread.py"} for a in decoded):
                return False
        return True
    except OSError:
        return False


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _atomic(path, data):
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _store_block(path, data):
    """Write one immutable shared chunk: 0640 inode, private only by its directory.

    The block store directory stays 0700 (setgid inherited from the archive), so
    the runner cannot reach these inodes until a published generation links them.
    No chmod is needed at exposure time and no copy is made per generation.
    """
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o640)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _share_block(path):
    """Migrate an older private 0600 block to the shared 0640 mode in place."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(descriptor)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError("cached block is not a regular file")
        if stat.S_IMODE(st.st_mode) != 0o640:
            os.fchmod(descriptor, 0o640)
    finally:
        os.close(descriptor)


def _chunk_identity(st):
    # No ctime: os.link and chmod change it, but not the immutable content.
    # Size and mtime of the same inode still reveal an in-place rewrite.
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns]


def _safe_path(root, relative):
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ValueError("unsafe archive path")
    target = root
    for component in p.parts:
        target = target / component
        if target.is_symlink():
            raise ValueError("symlink refused")
    return target


_SNAPSHOT_CACHE = {}


def _checked_chunk(target, part, cache, check):
    identity = _chunk_identity(target.stat())
    if identity[2] != part["size"]:
        raise ValueError("chunk size mismatch")
    key = _dump(["chunk/2", *identity, part["sha256"]])
    if cache.execute("SELECT 1 FROM verified WHERE identity=?", (key,)).fetchone():
        return
    digest = hashlib.sha256()
    with target.open("rb") as stream:
        while True:
            check()
            block = stream.read(MAX_BLOCK)
            if not block:
                break
            digest.update(block)
    if _chunk_identity(target.stat()) != identity or digest.hexdigest() != part["sha256"]:
        raise ValueError("chunk hash mismatch")
    with cache:
        cache.execute("INSERT OR IGNORE INTO verified VALUES(?)", (key,))


def _validate_snapshot(directory, cache, check):
    check()
    data = _load(directory / "catalog.json")
    if not isinstance(data, dict) or data.get("schema") != "sessions/1" or not isinstance(data.get("runs"), list):
        raise ValueError("invalid catalog")
    for run in data["runs"]:
        check()
        if not isinstance(run, dict):
            raise ValueError("invalid catalog run")
        manifest = _load(_safe_path(directory, run["manifest"]))
        if not isinstance(manifest, dict) or manifest.get("schema") != "session-files/1":
            raise ValueError("invalid manifest")
        if manifest.get("id") != run["id"] or manifest.get("files") != run["files"]:
            raise ValueError("catalog and manifest disagree")
        for file in manifest["files"]:
            if not isinstance(file, dict) or not isinstance(file["parts"], list):
                raise ValueError("invalid file metadata")
            if sum(p["raw_size"] for p in file["parts"]) != file["size"]:
                raise ValueError("incomplete file parts")
            for part in file["parts"]:
                check()
                target = _safe_path(directory, part["path"])
                _checked_chunk(target, part, cache, check)
    return data


def _remember_snapshot(archive, directory):
    _SNAPSHOT_CACHE[str(archive.absolute())] = (_stat_identity((archive / "current").stat()), directory)


def _cached_snapshot(archive):
    try:
        identity, directory = _SNAPSHOT_CACHE[str(archive.absolute())]
        if _stat_identity((archive / "current").stat()) == identity:
            return directory
    except (OSError, KeyError):
        pass
    return None


def current_snapshot(archive, *, _check=None):
    """Verify manifests and compressed hashes, reusing unchanged inode proofs.

    An optional internal guard bounds verification during export. Busy export
    uses only the last in-process verified pointer and never starts bulk hashing.
    """
    archive = Path(archive)
    check = _check if _check is not None else lambda: None
    cache = None
    try:
        check()
        name = (archive / "current").read_text(encoding="ascii").strip()
        if not SAFE.fullmatch(name):
            _SNAPSHOT_CACHE.pop(str(archive.absolute()), None)
            return None
        pointed = _safe_path(archive, "snapshots/" + name)
        receipt = pointed / "published"
        candidates = [pointed] if receipt.is_file() and not receipt.is_symlink() else []
        published = [
            p
            for p in (archive / "snapshots").iterdir()
            if p.name != name
            and SAFE.fullmatch(p.name)
            and not p.is_symlink()
            and (p / "published").is_file()
            and not (p / "published").is_symlink()
        ]
        candidates.extend(sorted(published, key=lambda p: (p / "published").stat().st_mtime_ns, reverse=True))
        cache = sqlite3.connect(archive / "integrity.sqlite3")
        cache.execute("CREATE TABLE IF NOT EXISTS verified(identity TEXT PRIMARY KEY)")
        for directory in candidates:
            try:
                _validate_snapshot(directory, cache, check)
                # A fallback is returned without changing the publication pointer.
                _remember_snapshot(archive, directory)
                return directory
            except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
                continue
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        pass
    finally:
        if cache is not None:
            cache.close()
    _SNAPSHOT_CACHE.pop(str(archive.absolute()), None)
    return None


def _receiptless_current(archive):
    """A pointer-written/receipt-not-written crash may be rebuilt from source."""
    try:
        name = (archive / "current").read_text(encoding="ascii").strip()
        if not SAFE.fullmatch(name):
            return False
        directory = _safe_path(archive, "snapshots/" + name)
        receipt = directory / "published"
        return directory.is_dir() and not receipt.exists() and not receipt.is_symlink()
    except (OSError, ValueError):
        return False


def _open_source(path, flags=os.O_RDONLY):
    # Walk each directory through a descriptor: O_NOFOLLOW on only the final
    # filename would still follow an ancestor swapped for a symlink.
    parts = path.absolute().parts
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in parts[1:-1]:
            next_descriptor = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return os.open(parts[-1], flags | os.O_NOFOLLOW, dir_fd=descriptor)
    finally:
        os.close(descriptor)


def _identity(path):
    descriptor = _open_source(path, os.O_PATH)
    try:
        st = os.fstat(descriptor)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError("not a regular file or symlink refused: " + path.name)
        return _stat_identity(st)
    finally:
        os.close(descriptor)


def _finite(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def _median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def _mean(values):
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def _fresh_stats():
    return {
        "frames": 0,
        "invalid_lines": 0,
        "counts": {},
        "base": None,
        "time_ok": True,
        "first": None,
        "last": None,
        "versions": {},
        "tracking_seen": 0,
    }


def _rules_sample_key(sample_key):
    # rid has no ":" (SAFE names); keep "<rid>:<identity hash>" and tag the rules.
    return ":".join(sample_key.split(":")[:2]) + ":r" + str(STATS_RULES)


class Exporter:
    def __init__(self, source, archive, *, idle=None, block_size=MAX_BLOCK):
        self.source, self.archive = Path(source), Path(archive)
        self.idle = idle if idle is not None else workbench_idle
        if not 0 < block_size <= MAX_BLOCK:
            raise ValueError("block_size must be between 1 and 1048576")
        self.block_size = block_size
        self.deferred = False
        self.error = None
        self._guard_at = None

    def _check(self):
        # Deadline every call; the process scan at most every GUARD_INTERVAL_S,
        # shared with the SQLite progress handler. The first check of a run
        # always scans, so a busy Workbench still prevents any source access.
        now = time.monotonic()
        if now >= self.deadline:
            raise Deferred()
        if self._guard_at is None or now - self._guard_at >= GUARD_INTERVAL_S:
            self._guard_at = now
            if not self.idle():
                raise Deferred()

    def run(self, budget_s=45):
        self.deadline = time.monotonic() + max(0, budget_s)
        self.deferred, self.error = False, None
        self._guard_at = None
        self.validations = []
        old = _cached_snapshot(self.archive)
        try:
            self._check()  # no archive creation or source accesses while busy
        except Deferred:
            self.deferred = True
            return old
        self.archive.mkdir(parents=True, exist_ok=True)
        with (self.archive / "export.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                self.deferred = True
                return _cached_snapshot(self.archive)
            try:
                old = current_snapshot(self.archive, _check=self._check)
                if old is not None:
                    pointed_name = (self.archive / "current").read_text(encoding="ascii").strip()
                    if pointed_name != old.name:
                        # Repair under the export lock before any unchanged-run
                        # fast path can return the fallback to the exposure service.
                        self._check()
                        _atomic(self.archive / "current", old.name.encode("ascii") + b"\n")
                        _remember_snapshot(self.archive, old)
            except Deferred:
                self.deferred = True
                return old
            if old is None and (self.archive / "current").exists() and not _receiptless_current(self.archive):
                self.error = "no valid archived snapshot: integrity or metadata failure"
                return None
            db = sqlite3.connect(self.archive / "checkpoint.sqlite3")
            self.db = db
            db.execute("PRAGMA temp_store=FILE")
            db.execute("PRAGMA cache_size=-2048")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS files(key TEXT PRIMARY KEY, identity TEXT, state TEXT);
                CREATE TABLE IF NOT EXISTS samples(run TEXT, metric TEXT, value REAL);
                CREATE INDEX IF NOT EXISTS sample_sort ON samples(run, metric, value);
                CREATE TABLE IF NOT EXISTS archived(id TEXT PRIMARY KEY, run TEXT, signature TEXT);
                CREATE TABLE IF NOT EXISTS archived_samples(id TEXT PRIMARY KEY, sample_key TEXT);
                CREATE TEMP TABLE pending(id TEXT PRIMARY KEY, run TEXT, signature TEXT, sample_key TEXT);
                CREATE TABLE IF NOT EXISTS aggregates(key TEXT PRIMARY KEY, value TEXT);
            """)
            self.sql_deferred = False
            db.set_progress_handler(self._sql_progress, 1000)
            try:
                # Only runs from a previously verified publication may be
                # retained. Recover publication-before-DB-commit crashes here.
                self._restore_published(old)
                return self._run(old)
            except Deferred:
                self.deferred = True
                return old
            except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
                if self.sql_deferred:
                    self.deferred = True
                else:
                    self.error = str(exc)
                return old
            finally:
                db.set_progress_handler(None, 0)
                db.close()

    def _sql_progress(self):
        # SQLite invokes this every 1,000 VM instructions. Keep the deadline
        # unconditional, but avoid a full /proc walk on every few records.
        now = time.monotonic()
        last_guard = self._guard_at
        if now >= self.deadline:
            self.sql_deferred = True
            return 1
        if last_guard is None or now - last_guard >= GUARD_INTERVAL_S:
            self._guard_at = now
            if not self.idle():
                self.sql_deferred = True
                return 1
        return 0

    def _restore_published(self, old):
        accepted = _load(old / "catalog.json")["runs"] if old else []
        with self.db:
            existing = {row[0]: row[1] for row in self.db.execute("SELECT id, signature FROM archived")}
            self.db.execute("DELETE FROM archived")
            for run in accepted:
                rid = run["id"]
                self.db.execute("INSERT INTO archived VALUES(?,?,?)", (rid, _dump(run), existing.get(rid, "")))
                row = self.db.execute("SELECT sample_key FROM archived_samples WHERE id=?", (rid,)).fetchone()
                if row is None:
                    # A publication happened before promotion. Its checkpoint
                    # is sufficient to recover the immutable numeric namespace.
                    state = self._file_state(rid + "/records.jsonl")
                    self.db.execute("INSERT INTO archived_samples VALUES(?,?)", (rid, state["sample_key"]))
            self.db.execute("DELETE FROM archived_samples WHERE id NOT IN (SELECT id FROM archived)")

    def _promote(self):
        # Pointer publication has already succeeded; next invocation can recover
        # from its verified catalog even if this small promotion is interrupted.
        self.db.set_progress_handler(None, 0)
        with self.db:
            superseded = [
                row[0]
                for row in self.db.execute(
                    "SELECT a.sample_key FROM archived_samples a JOIN pending p ON a.id=p.id "
                    "WHERE a.sample_key != p.sample_key"
                )
            ]
            self.db.execute("INSERT OR REPLACE INTO archived SELECT id,run,signature FROM pending")
            self.db.execute("INSERT OR REPLACE INTO archived_samples SELECT id,sample_key FROM pending")
            # Samples of a run re-evaluated under newer rules are no longer referenced.
            self.db.executemany("DELETE FROM samples WHERE run=?", [(key,) for key in superseded])

    def _run(self, old):
        self._check()
        # A deleted or inaccessible source leaves the last good archive intact.
        if not self.source.exists():
            self.error = "source missing"
            return old
        if self.source.is_symlink() or not self.source.is_dir():
            raise ValueError("source must be a real directory")
        # Reject symlinks in ancestor components too.
        ancestor = self.source.absolute()
        while ancestor != ancestor.parent:
            if ancestor.is_symlink():
                raise ValueError("source ancestor symlink refused")
            ancestor = ancestor.parent
        errors = []
        for session in sorted(self.source.iterdir()):
            self._check()
            if session.is_symlink():
                errors.append("symlink refused: " + session.name)
                continue
            if not session.is_dir():
                continue
            if not SAFE.fullmatch(session.name):
                errors.append("unsafe session id")
                continue
            for run in sorted(session.iterdir()):
                self._check()
                if not run.name.startswith("run-"):
                    continue
                if run.is_symlink() or not SAFE.fullmatch(run.name):
                    errors.append("unsafe run id: " + session.name)
                    continue
                if not run.is_dir():
                    continue
                try:
                    self._import(run)
                except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
                    # One malformed run must not block every later export.
                    errors.append(session.name + "/" + run.name + ": " + (str(exc) or type(exc).__name__))
        self._check()
        self._validate_sources()
        runs = [
            _load_json(row[1])
            for row in self.db.execute(
                "SELECT id,run FROM archived WHERE id NOT IN (SELECT id FROM pending) "
                "UNION ALL SELECT id,run FROM pending ORDER BY id"
            )
        ]
        if old:
            previous = _load(old / "catalog.json")
            if previous["runs"] == runs and previous.get("errors") == sorted(set(errors)):
                return old
        groups = self._groups(runs)
        payload = {
            "schema": "sessions/1",
            "stats_version": "sessions-stats/1",
            "runs": runs,
            "groups": groups,
            "errors": sorted(set(errors)),
        }
        if old:
            previous = _load(old / "catalog.json")
            previous.pop("generated_at", None)
            if previous == payload:
                return old
        # Build a new immutable generation. All chunks already live in the
        # shared block store; hard links keep snapshots independent of future
        # source changes and cost no extra space per generation.
        stage = self.archive / ("stage-" + uuid.uuid4().hex)
        stage.mkdir()
        final = None
        published = False
        try:
            for run in runs:
                self._check()
                manifest = {"schema": "session-files/1", "id": run["id"], "files": run["files"]}
                out = stage / run["manifest"]
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(_dump(manifest), encoding="utf-8")
                for file in run["files"]:
                    for part in file["parts"]:
                        self._check()
                        destination = stage / part["path"]
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        if not destination.exists():
                            block = self.archive / "blocks" / (part["sha256"] + ".gz.bin")
                            _share_block(block)
                            os.link(block, destination)
            payload["generated_at"] = datetime.now(UTC).isoformat()
            (stage / "catalog.json").write_text(_dump(payload), encoding="utf-8")
            self._check()
            self._validate_sources()
            snapshots = self.archive / "snapshots"
            snapshots.mkdir(exist_ok=True)
            name = "generation-" + uuid.uuid4().hex
            final = snapshots / name
            os.replace(stage, final)
            # Verify every immutable payload before replacing the pointer.
            cache = sqlite3.connect(self.archive / "integrity.sqlite3")
            try:
                cache.execute("CREATE TABLE IF NOT EXISTS verified(identity TEXT PRIMARY KEY)")
                _validate_snapshot(final, cache, self._check)
            finally:
                cache.close()
            self._validate_sources()
            _atomic(self.archive / "current", name.encode("ascii") + b"\n")
            _atomic(final / "published", b"published\n")
            published = True
            _remember_snapshot(self.archive, final)
            self._promote()
            self._prune(final)
            return final
        finally:
            if stage.exists():
                shutil.rmtree(stage)
            if final is not None and not published:
                # Deferred or failed before the receipt was written: never leave
                # an orphaned generation behind. If the pointer already moved,
                # it stays: the receiptless-current recovery rebuilds from it.
                try:
                    pointed = (self.archive / "current").read_text(encoding="ascii").strip()
                except (OSError, UnicodeDecodeError):
                    pointed = final.name  # unklar: nichts löschen, _prune räumt später auf
                if pointed != final.name:
                    self._discard(final)

    def _discard(self, directory):
        """Atomically retire a generation, then delete it; leftovers are retried."""
        trash = self.archive / ("trash-" + uuid.uuid4().hex)
        try:
            os.replace(directory, trash)
        except OSError:
            return  # already gone or not movable; the next prune retries
        shutil.rmtree(trash, ignore_errors=True)

    def _prune(self, keep_current):
        """Delete generations neither current nor the kept previous one.

        Runs only after a successful publication and never turns it into a
        failure. The runner's own state file is not readable by this service,
        so one previous published generation is kept (preferably one already
        exposed to the runner) as its fallback.
        """
        try:
            for leftover in self.archive.iterdir():
                if leftover.name.startswith(("stage-", "trash-")) and not leftover.is_symlink() and leftover.is_dir():
                    self._check()
                    shutil.rmtree(leftover, ignore_errors=True)
            snapshots = self.archive / "snapshots"
            others = [
                p
                for p in snapshots.iterdir()
                if p.name != keep_current.name and SAFE.fullmatch(p.name) and not p.is_symlink() and p.is_dir()
            ]
            published = [p for p in others if (p / "published").is_file() and not (p / "published").is_symlink()]
            published.sort(key=lambda p: (p / "published").stat().st_mtime_ns, reverse=True)
            exposed = [p for p in published if stat.S_IMODE(p.stat().st_mode) & 0o050]
            keep = {p.name for p in (exposed or published)[:KEEP_PREVIOUS]}
            for directory in others:
                if directory.name in keep:
                    continue
                self._check()
                self._discard(directory)
        except (Deferred, OSError):
            pass  # remaining generations are pruned after the next publication

    def _validate_sources(self):
        for rid, paths, identities in self.validations:
            self._check()
            if any(_identity(path) != identities[name] for name, path in paths):
                raise ValueError("source mutated before publication: " + rid)

    def _paths(self, run):
        paths = [("records.jsonl", run / "records.jsonl"), ("session.json", run / "session.json")]
        for name in ("reference.jsonl", "marks.jsonl", "TESTLAUF.json"):
            path = run / name
            if path.is_symlink() or path.exists():
                paths.append((name, path))
        warnings = []
        for name in ("profile.json", "confirmation.json"):
            path = run.parent / name
            if path.is_symlink() or path.exists():
                paths.append((name, path))
            else:
                warnings.append("missing-" + name.split(".")[0])
        return paths, warnings

    def _import(self, directory):
        rid = directory.parent.name + "/" + directory.name
        paths, warnings = self._paths(directory)
        identities = {name: _identity(path) for name, path in paths}
        signature = _dump({"files": identities, "rules": STATS_RULES})
        previous = self.db.execute("SELECT signature FROM archived WHERE id=?", (rid,)).fetchone()
        if previous and previous[0] == signature:
            self.validations.append((rid, paths, identities))
            return  # no opening, rehashing or recomputing unchanged source files
        # Copy/hash session metadata through the same checkpointed block path.
        session_path = next(p for n, p in paths if n == "session.json")
        session_file = self._file(rid, "session.json", session_path, identities["session.json"])
        meta = self._metadata(session_file)
        if meta.get("schema") != "live-session/1":
            raise ValueError("unsupported session schema")
        if not meta.get("ended_at_utc"):
            return
        for field in ("gate", "camera", "summary"):
            if field in meta and not isinstance(meta[field], dict):
                raise ValueError("invalid nested metadata: " + field)
        if "reader_tolerance" not in meta:
            tolerance = "unknown"
        elif meta["reader_tolerance"] is None:
            # Explicit null is the producer's strict default, unlike absence.
            tolerance = 1.0
        else:
            raw_tolerance = meta["reader_tolerance"]
            if (
                not isinstance(raw_tolerance, dict)
                or not _finite(raw_tolerance.get("factor"))
                or raw_tolerance["factor"] <= 0
            ):
                raise ValueError("invalid reader tolerance factor")
            tolerance = float(raw_tolerance["factor"])
        if tolerance != "unknown" and tolerance != 1.0:
            warnings.append("unvalidated-reader-tolerance")
        files = [session_file]
        unreadable = False
        for name, path in paths:
            if name != "session.json":
                try:
                    files.append(self._file(rid, name, path, identities[name]))
                except PermissionError:
                    if name != "records.jsonl":
                        raise
                    unreadable = True
                    warnings.append("unreadable-records")
        self._check()
        if any(_identity(path) != identities[name] for name, path in paths):
            raise ValueError("source mutated during export")
        prior = self.db.execute("SELECT run FROM archived WHERE id=?", (rid,)).fetchone()
        if prior:
            archived = _load_json(prior[0])
            if archived["files"] != files:
                raise ValueError("archive ID conflict; existing content retained")
            if (archived.get("stats") or {}).get("rules") == STATS_RULES:
                with self.db:
                    self.db.execute("UPDATE archived SET signature=? WHERE id=?", (signature, rid))
                return
            # Same bytes, older statistics rules: recompute below; promotion
            # replaces the archived entry after the next publication.
        record_state = self._file_state(rid + "/records.jsonl")
        stat_state = record_state["stats"]
        sample_key = record_state["sample_key"]
        if unreadable:
            # A partial read is not a completed session observation set.
            stat_state = {
                "frames": 0,
                "invalid_lines": 0,
                "counts": {},
                "base": None,
                "time_ok": False,
                "first": None,
                "last": None,
                "versions": {},
                "tracking_seen": 0,
            }
            sample_key += ":unreadable"
        stats = self._stats(sample_key, stat_state, meta, warnings)
        gate = meta.get("gate") or {}
        camera = meta.get("camera") or {}
        config = {
            "device_id": meta.get("device_id", "unknown"),
            "unit": gate.get("expected_unit", meta.get("unit", "unknown")),
            "reader_family": gate.get("backend", "unknown"),
            "tolerance": tolerance,
            "confirm_frames": gate.get("confirm_frames", "unknown"),
            "camera": {k: camera.get(k, "unknown") for k in ("size", "fps", "fourcc")},
            "test_run": bool(meta.get("test_run")) or any(f["name"] == "TESTLAUF.json" for f in files),
        }
        gid = "group-" + hashlib.sha256(_dump(config).encode()).hexdigest()[:20]
        slug = "run-" + hashlib.sha256(rid.encode()).hexdigest()[:24]
        data = {
            "id": rid,
            "group": gid,
            "started_at_utc": meta.get("started_at_utc"),
            "ended_at_utc": meta["ended_at_utc"],
            "device_id": meta.get("device_id"),
            "unit": None if config["unit"] == "unknown" else config["unit"],
            "test_run": config["test_run"],
            "warnings": warnings,
            "config": config,
            "versions": stat_state["versions"],
            "manifest": "runs/" + slug + "/manifest.json",
            "files": files,
            "stats": stats,
        }
        with self.db:
            self.db.execute("INSERT INTO pending VALUES(?,?,?,?)", (rid, _dump(data), signature, sample_key))
        self.validations.append((rid, paths, identities))

    def _file_state(self, key):
        return _load_json(self.db.execute("SELECT state FROM files WHERE key=?", (key,)).fetchone()[0])

    def _file(self, rid, name, path, identity):
        key = rid + "/" + name
        row = self.db.execute("SELECT identity,state FROM files WHERE key=?", (key,)).fetchone()
        state = _load_json(row[1]) if row and _load_json(row[0]) == identity else None
        if state is not None and name == "records.jsonl" and state.get("rules") != STATS_RULES and not state["finished"]:
            state = None  # partial parse under older rules: restart, blocks deduplicate
        if state is None:
            sample_key = _rules_sample_key(rid + ":" + hashlib.sha256(_dump(identity).encode()).hexdigest())
            state = {
                "offset": 0,
                "parts": [],
                "tail": "",
                "discard": False,
                "finished": False,
                "rules": STATS_RULES,
                "sample_key": sample_key,
                "stats": _fresh_stats(),
            }
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO files VALUES(?,?,?)", (key, _dump(identity), _dump(state)))
                if name == "records.jsonl":
                    self.db.execute("DELETE FROM samples WHERE run=?", (sample_key,))
        if state["finished"] and name == "records.jsonl" and state.get("rules") != STATS_RULES:
            self._reparse(key, state)
        if state["finished"]:
            return {"name": name, "size": identity[2], "parts": state["parts"]}
        self._check()
        # O_NOFOLLOW closes the final-component symlink race. Identity checks
        # before/after reading also reject replacements and concurrent mutation.
        descriptor = _open_source(path)
        with os.fdopen(descriptor, "rb") as stream:
            if _stat_identity(os.fstat(stream.fileno())) != identity:
                raise ValueError("source replaced before read")
            stream.seek(state["offset"])
            while not state["finished"]:
                self._check()
                block = stream.read(self.block_size)
                final = state["offset"] + len(block) == identity[2]
                if not block and not final:
                    raise ValueError("source truncated")
                with self.db:
                    if block:
                        compressed = gzip.compress(block, mtime=0)
                        digest = hashlib.sha256(compressed).hexdigest()
                        blocks = self.archive / "blocks"
                        blocks.mkdir(exist_ok=True)
                        target = blocks / (digest + ".gz.bin")
                        if target.exists():
                            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                                raise ValueError("cached block hash conflict")
                        else:
                            _store_block(target, compressed)
                        state["parts"].append(
                            {
                                "path": "chunks/" + digest + ".gz.bin",
                                "size": len(compressed),
                                "sha256": digest,
                                "raw_size": len(block),
                                "raw_sha256": hashlib.sha256(block).hexdigest(),
                            }
                        )
                        state["offset"] += len(block)
                    if name == "records.jsonl":
                        self._parse(state["sample_key"], state, block, final)
                    state["finished"] = final
                    self.db.execute("UPDATE files SET state=? WHERE key=?", (_dump(state), key))
            if _stat_identity(os.fstat(stream.fileno())) != identity:
                raise ValueError("source mutated during read")
        return {"name": name, "size": identity[2], "parts": state["parts"]}

    def _reparse(self, key, state):
        """Re-evaluate finished records under STATS_RULES from the stored blocks.

        Only gzip decompression and parsing: no source access, no recompression.
        Checkpointed per block like the first pass; a new sample key keeps
        cached aggregates of the old rules from being reused.
        """
        redo = state.get("reparse")
        if redo is None:
            redo = {
                "index": 0,
                "tail": "",
                "discard": False,
                "sample_key": _rules_sample_key(state["sample_key"]),
                "stats": _fresh_stats(),
            }
            with self.db:
                self.db.execute("DELETE FROM samples WHERE run=?", (redo["sample_key"],))
                state["reparse"] = redo
                self.db.execute("UPDATE files SET state=? WHERE key=?", (_dump(state), key))
        parts = state["parts"]
        while True:
            self._check()
            index = redo["index"]
            final = index >= len(parts) - 1
            block = b""
            if parts:
                digest = parts[index]["sha256"]
                compressed = (self.archive / "blocks" / (digest + ".gz.bin")).read_bytes()
                if hashlib.sha256(compressed).hexdigest() != digest:
                    raise ValueError("cached block hash conflict")
                block = gzip.decompress(compressed)
            with self.db:
                self._parse(redo["sample_key"], redo, block, final)
                redo["index"] = index + 1
                if final:
                    state.update(
                        tail="", discard=False, stats=redo["stats"], sample_key=redo["sample_key"], rules=STATS_RULES
                    )
                    del state["reparse"]
                self.db.execute("UPDATE files SET state=? WHERE key=?", (_dump(state), key))
            if final:
                return

    def _metadata(self, file):
        if file["size"] > MAX_BLOCK:
            raise ValueError("session metadata exceeds 1 MiB")
        data = bytearray()
        for part in file["parts"]:
            self._check()
            data.extend(gzip.decompress((self.archive / "blocks" / (part["sha256"] + ".gz.bin")).read_bytes()))
        meta = json.loads(data)
        if not isinstance(meta, dict):
            raise ValueError("session metadata must be an object")
        return meta

    def _parse(self, rid, state, block, final):
        tail = base64.b64decode(state["tail"]) + block
        lines = tail.split(b"\n")
        tail = lines.pop()
        if final and tail:
            lines.append(tail)
            tail = b""
        for line in lines:
            if state["discard"]:
                state["discard"] = False
                continue
            if len(line) > MAX_BLOCK:
                state["stats"]["invalid_lines"] += 1
                continue
            self._record(rid, state["stats"], line)
        if len(tail) > MAX_BLOCK:
            if not state["discard"]:
                state["stats"]["invalid_lines"] += 1
            state["discard"] = True
            tail = b""
        state["tail"] = base64.b64encode(tail).decode("ascii")

    def _record(self, rid, stats, line):
        if not line.strip():
            return  # Leerzeilen ignoriert auch der Explorer
        try:
            record = json.loads(line, parse_constant=_reject_constant)
            if not isinstance(record, dict):
                raise ValueError("record is not an object")
        except (ValueError, UnicodeDecodeError, RecursionError):
            # RecursionError: deeply nested lines are invalid, not fatal.
            stats["invalid_lines"] += 1
            return
        # Same acceptance rule as the records explorer: a frame needs a string
        # status and a finite capture_timestamp.value_ns. Everything else is a
        # visible invalid line, so frame counts and shares agree in both views
        # and the status shares of the counted frames add up to 100 %.
        status = record.get("status")
        stamp = record.get("capture_timestamp")
        if not isinstance(status, str) or not isinstance(stamp, dict) or not _finite(stamp.get("value_ns")):
            stats["invalid_lines"] += 1
            return
        stats["frames"] += 1
        stats["counts"][status] = stats["counts"].get(status, 0) + 1
        reasons = record.get("reject_reasons")
        if (
            isinstance(reasons, list)
            and reasons
            and isinstance(reasons[0], str)
            and reasons[0].startswith("tracking_lost:")
        ):
            stats["tracking_seen"] += 1
        versions = record.get("component_versions")
        if isinstance(versions, dict):
            for key, value in versions.items():
                if isinstance(value, str):
                    seen = stats["versions"].setdefault(key, [])
                    if value not in seen:
                        seen.append(value)
        observations = []
        if status == "valid":
            observations.extend(
                (rid, metric, record[metric]) for metric in ("confidence", "value") if _finite(record.get(metric))
            )
        trace = record.get("trace")
        if record.get("schema_version") == 1 and isinstance(trace, dict):
            start, end = trace.get("t_dequeue_ns"), trace.get("t_record_built_ns")
            if _finite(start) and _finite(end) and end >= start:
                observations.append((rid, "processing_ms", (end - start) / 1e6))
        self.db.executemany("INSERT INTO samples VALUES(?,?,?)", observations)
        base, value = stamp.get("base"), stamp.get("value_ns")
        if base not in BASES:
            stats["time_ok"] = False
            return
        if stats["base"] is not None and stats["base"] != base:
            stats["time_ok"] = False
        stats["base"] = base
        if stats["first"] is None:
            stats["first"] = value
        if stats["last"] is not None and value < stats["last"]:
            stats["time_ok"] = False
        stats["last"] = value

    def _summary(self, ids, metric):
        cache_key = _dump([sorted(ids), metric])
        cached = self.db.execute("SELECT value FROM aggregates WHERE key=?", (cache_key,)).fetchone()
        if cached:
            return _load_json(cached[0])
        placeholders = ",".join("?" for _ in ids)
        condition = f"run IN ({placeholders}) AND metric=?"
        parameters = [*ids, metric]
        n, mean = self.db.execute(f"SELECT count(*),avg(value) FROM samples WHERE {condition}", parameters).fetchone()

        def quantile(p):
            if not n:
                return None
            index = (n - 1) * p
            lower = int(index)
            rows = self.db.execute(
                f"SELECT value FROM samples WHERE {condition} ORDER BY value LIMIT 2 OFFSET ?", [*parameters, lower]
            ).fetchall()
            a = rows[0][0]
            return a if len(rows) == 1 else a + (rows[1][0] - a) * (index - lower)

        result = {"n": n, "mean": mean, "median": quantile(0.5), "p95": quantile(0.95)}
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO aggregates VALUES(?,?)", (cache_key, _dump(result)))
        return result

    def _stats(self, rid, state, meta, warnings):
        n = state["frames"]
        duration = None
        if state["time_ok"] and state["first"] is not None and state["last"] > state["first"]:
            duration = (state["last"] - state["first"]) / 1e9
        summary = meta.get("summary") or {}
        if "frames_read" in summary and summary["frames_read"] != n:
            warnings.append("frame-count-mismatch")
        tracking = summary.get("tracking_lost")
        if not isinstance(tracking, int) or isinstance(tracking, bool) or tracking < 0:
            tracking = None
        elif tracking != state["tracking_seen"]:
            warnings.append("tracking-count-mismatch")
        if state["invalid_lines"]:
            warnings.append("invalid-record-lines")
        if not n:
            warnings.append("no-records")
        if not duration:
            warnings.append("capture-time-unavailable")
        return {
            "frames": n,
            "invalid_lines": state["invalid_lines"],
            "counts": state["counts"],
            **{m: self._summary([rid], m) for m in ("processing_ms", "confidence", "value")},
            "duration_s": duration,
            # n frames span n-1 intervals between first and last capture stamp.
            "rate_hz": (n - 1) / duration if duration else None,
            "tracking_lost": tracking,
            "rules": STATS_RULES,
        }

    def _groups(self, runs):
        groups = {}
        for run in runs:
            groups.setdefault(run["group"], []).append(run)
        output = []
        for gid, members in groups.items():
            self._check()
            statuses = sorted({k for r in members for k in r["stats"]["counts"]})
            total = sum(r["stats"]["frames"] for r in members)
            share_equal = {
                s: _mean(
                    [r["stats"]["counts"].get(s, 0) / r["stats"]["frames"] for r in members if r["stats"]["frames"]]
                )
                for s in statuses
            }
            share_weighted = (
                {s: sum(r["stats"]["counts"].get(s, 0) for r in members) / total for s in statuses} if total else {}
            )
            eligible = [r["stats"] for r in members if r["stats"]["duration_s"] is not None]
            tracked = [r["stats"] for r in members if r["stats"]["tracking_lost"] is not None and r["stats"]["frames"]]
            sample_keys = [
                (
                    self.db.execute("SELECT sample_key FROM pending WHERE id=?", (r["id"],)).fetchone()
                    or self.db.execute("SELECT sample_key FROM archived_samples WHERE id=?", (r["id"],)).fetchone()
                )[0]
                for r in members
            ]
            proc = self._summary(sample_keys, "processing_ms")
            confidence = self._summary(sample_keys, "confidence")
            equal = {
                "shares": share_equal,
                "processing_median_ms": _median([r["stats"]["processing_ms"]["median"] for r in members]),
                "processing_p95_ms": _median([r["stats"]["processing_ms"]["p95"] for r in members]),
                "confidence_median": _median([r["stats"]["confidence"]["median"] for r in members]),
                "rate_hz": _mean([r["stats"]["rate_hz"] for r in members]),
                "tracking_per_1000": _mean([s["tracking_lost"] * 1000 / s["frames"] for s in tracked]),
            }
            weighted = {
                "shares": share_weighted,
                "processing_median_ms": proc["median"],
                "processing_p95_ms": proc["p95"],
                "confidence_median": confidence["median"],
                "rate_hz": sum(s["frames"] - 1 for s in eligible) / sum(s["duration_s"] for s in eligible)
                if eligible
                else None,
                "tracking_per_1000": sum(s["tracking_lost"] for s in tracked) * 1000 / sum(s["frames"] for s in tracked)
                if tracked
                else None,
            }
            first = members[0]
            output.append(
                {
                    "id": gid,
                    "label": str(first["device_id"] or "unknown") + " / " + str(first["unit"] or "unknown"),
                    "config": first["config"],
                    "test_run": first["test_run"],
                    "run_equal": equal,
                    "frame_weighted": weighted,
                    "session_count": len(members),
                    "frames": total,
                }
            )
        return output


def _stat_identity(st):
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def _load_json(value):
    return json.loads(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--source", type=Path, required=True)
    export.add_argument("--archive", type=Path, required=True)
    export.add_argument("--budget", type=float, default=45)
    args = parser.parse_args(argv)
    exporter = Exporter(args.source, args.archive)
    snapshot = exporter.run(args.budget)
    print(_dump({"path": str(snapshot) if snapshot else None, "deferred": exporter.deferred, "error": exporter.error}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
