"""Bounded output/audit state shared by v1 transports and validated v2 adapters.

No sockets, serial devices or workers are opened here. Adapters must authorize
and bind v2 clients/leases before translating requests into handle_v1 fields.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from dispread.records import TimeBaseKind, ValueRecord, ValueStatus
from dispread.sink.protocol.user_defined import UserDefinedFormatter

RELEASE_BLOCK = "DUT-Ausgabe gesperrt: Windows-Abnahme für Ungültig-/Altwertbehandlung fehlt"


class OutputState:
    def __init__(self, out_dir: Path, *, demo=False):
        self.out_dir = Path(out_dir)
        self.demo = demo
        self.run_id = uuid.uuid4().hex
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._latest = None
        self._barrier = None
        self._generation = 0
        self._pending = None
        self._state = "waiting"
        self._error = None
        self._last_ack = None
        self._attempted_sequence = -1
        self._events = None

    def metadata(self):
        caps = asdict(UserDefinedFormatter().capabilities)
        caps["supported_invalid_policies"] = sorted(caps["supported_invalid_policies"])
        return {
            "run_id": self.run_id,
            "demo": self.demo,
            "release_block": None if self.demo else RELEASE_BLOCK,
            "formatter": caps,
        }

    def status(self):
        with self._lock:
            return {
                "state": self._state,
                "release_block": None if self.demo else RELEASE_BLOCK,
                "error": self._error,
                "last_ack": self._last_ack,
                "ack_scope": "COM driver write, not GSVmulti reception",
            }

    def _event(self, kind, **data):
        if self._events is not None:
            try:
                self._events.write(
                    json.dumps(
                        {
                            "event": kind,
                            "run_id": self.run_id,
                            "t_ns": time.monotonic_ns(),
                            "time_base": "host_monotonic",
                            **data,
                        },
                        allow_nan=False,
                    )
                    + "\n"
                )
                self._events.flush()
            except OSError as exc:
                self._state, self._error = "audit_failed", str(exc)
                self._stop.set()
                raise

    def start(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._events = (self.out_dir / "output.jsonl").open("a", encoding="utf-8")
        self._event("start", demo=self.demo, release_block=None if self.demo else RELEASE_BLOCK)

    def publish(self, record: ValueRecord):
        if self.demo and record.capture_timestamp.base is not TimeBaseKind.SYNTHETIC:
            raise ValueError("Demo publisher accepts synthetic records only")
        with self._lock:
            if self._state == "audit_failed":
                raise OSError(self._error or "output audit failed")
            if self._stop.is_set():
                return
            self._latest = record
            if record.status is not ValueStatus.VALID:
                self._generation += 1
                self._barrier = (self._generation, record)

    def handle_v1(self, message: dict):
        with self._lock:
            if (
                message.get("version") != 1
                or not isinstance(message.get("request_id"), str)
                or not message["request_id"]
            ):
                raise ValueError("invalid request")
            if message.get("type") == "ack":
                if self._pending is None:
                    raise ValueError("unsolicited ACK")
                expected = {
                    key: self._pending.get(key) for key in ("request_id", "run_id", "frame_sequence", "barrier_id")
                }
                if any(message.get(key) != value for key, value in expected.items()):
                    raise ValueError("ACK does not match pending transfer")
                if message.get("outcome") not in ("written", "expired", "failed", "unconfirmed"):
                    raise ValueError("invalid ACK outcome")
                self._event("ack", **message)
                self._last_ack = {**expected, "outcome": message["outcome"], "scope": "COM driver only"}
                if message["outcome"] == "written" and self._barrier and message.get("barrier_id") == self._barrier[0]:
                    self._barrier = None
                if self._pending["barrier_id"] is None:
                    self._attempted_sequence = self._pending["frame_sequence"]
                self._pending = None
                return None
            if message.get("type") != "poll" or self._pending is not None:
                raise ValueError("one outstanding poll allowed")
            reply = {"version": 1, "request_id": message["request_id"], "run_id": self.run_id, "demo": self.demo}
            if self._stop.is_set():
                return {**reply, "type": "ended"}
            if not self.demo:
                return {**reply, "type": "idle", "release_block": RELEASE_BLOCK}
            record = self._barrier[1] if self._barrier else self._latest
            if record is None or (self._barrier is None and record.frame_sequence <= self._attempted_sequence):
                return {**reply, "type": "idle"}
            barrier_id = self._barrier[0] if self._barrier else None
            self._pending = {**reply, "frame_sequence": record.frame_sequence, "barrier_id": barrier_id}
            self._event("offered", **self._pending, status=record.status.value)
            return {
                **reply,
                "type": "record",
                "record": record.to_dict(),
                "frame_age_ns": None,
                "barrier_id": barrier_id,
            }

    def settled(self, frame_sequence):
        """True once ``frame_sequence`` was offered and answered (any outcome)."""
        with self._lock:
            return self._pending is None and self._attempted_sequence >= frame_sequence

    def abandon_pending(self):
        """Record uncertainty; losing an ACK never proves non-delivery."""
        with self._lock:
            if self._pending is not None:
                self._event("unconfirmed", **self._pending)
                if self._pending["barrier_id"] is None:
                    self._attempted_sequence = self._pending["frame_sequence"]
                self._pending = None

    def stop(self):
        self._stop.set()
        with self._lock:
            if self._events:
                try:
                    self.abandon_pending()
                    self._event("stop")
                finally:
                    self._events.close()
                    self._events = None
            if self._state != "audit_failed":
                self._state = "stopped"
