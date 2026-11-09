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

from dispread.bridge.protocol import TEST_RELEASE
from dispread.records import TimeBaseKind, ValueRecord, ValueStatus
from dispread.sink.protocol.user_defined import UserDefinedFormatter

RELEASE_BLOCK = "DUT-Ausgabe gesperrt: Windows-Abnahme für Ungültig-/Altwertbehandlung fehlt"


class OutputState:
    """``release=TEST_RELEASE`` ist die vom Pi-Bediener je Lauf bestaetigte
    Testfreigabe echter Werte (Nutzerentscheidung 2026-11-09, keine Abnahme).
    Ohne sie bleibt jede echte Ausgabe gesperrt. Ungueltigkeit wird dann nur
    als Barriere quittiert (``omitted``), nie als COM-Schreibvorgang.
    """

    def __init__(self, out_dir: Path, *, demo=False, release=None, max_offer_age_ns=None,
                 clock=time.monotonic_ns):
        if release not in (None, TEST_RELEASE) or (demo and release is not None):
            raise ValueError("release marker must be the exact test release and never demo")
        if max_offer_age_ns is not None and (type(max_offer_age_ns) is not int or max_offer_age_ns <= 0):
            raise ValueError("invalid offer age limit")
        self.out_dir = Path(out_dir)
        self.demo = demo
        self.release = release
        self.max_offer_age_ns = max_offer_age_ns
        self._clock = clock
        self._published_ns = None
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

    @property
    def release_block(self):
        return None if self.demo or self.release is not None else RELEASE_BLOCK

    @property
    def offers_records(self):
        return self.demo or self.release is not None

    def _release_fields(self):
        return {"release_block": self.release_block, **({"release": self.release} if self.release else {})}

    def metadata(self):
        caps = asdict(UserDefinedFormatter().capabilities)
        caps["supported_invalid_policies"] = sorted(caps["supported_invalid_policies"])
        return {
            "run_id": self.run_id,
            "demo": self.demo,
            "release_block": self.release_block,
            "release": self.release,
            "formatter": caps,
        }

    def status(self):
        with self._lock:
            return {
                "state": self._state,
                "release_block": self.release_block,
                "release": self.release,
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
        self._event("start", demo=self.demo, release_block=self.release_block, release=self.release,
                    max_offer_age_ns=self.max_offer_age_ns)

    def publish(self, record: ValueRecord):
        if self.demo and record.capture_timestamp.base is not TimeBaseKind.SYNTHETIC:
            raise ValueError("Demo publisher accepts synthetic records only")
        with self._lock:
            if self._state == "audit_failed":
                raise OSError(self._error or "output audit failed")
            if self._stop.is_set():
                return
            if self.release is not None and record.capture_timestamp.base is not TimeBaseKind.V4L2_MONOTONIC:
                # Testfreigabe gilt nur fuer echte Kamerazeitbasis; Synthetik/Replay
                # wird nie als Wert angeboten (wie gesperrt, mit Audit-Grund).
                self._latest = None
                self._event("release_time_base_rejected", frame_sequence=record.frame_sequence,
                            time_base=record.capture_timestamp.base.value)
                return
            if record.status is not ValueStatus.VALID:
                # Ungueltigkeit traegt nur ihre Barriere; der zuvor juengste
                # gueltige Wert ist damit ueberholt und wird nie mehr angeboten.
                self._latest = None
                self._generation += 1
                self._barrier = (self._generation, record)
            else:
                self._latest = record
                self._published_ns = self._clock()

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
                outcome = message.get("outcome")
                if outcome not in ("written", "expired", "failed", "unconfirmed", "omitted"):
                    raise ValueError("invalid ACK outcome")
                if outcome == "omitted" and self.demo:
                    raise ValueError("demo invalidation must be written, not omitted")
                if self.release is not None and self._pending["barrier_id"] is not None and outcome == "written":
                    raise ValueError("test release writes VALID values only; invalidation is omitted")
                self._event("ack", **message)
                self._last_ack = {**expected, "outcome": outcome,
                                  "scope": "local omission, nothing written" if outcome == "omitted"
                                  else "COM driver only"}
                if (outcome in ("written", "omitted") and self._barrier
                        and message.get("barrier_id") == self._barrier[0]):
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
            if not self.offers_records:
                return {**reply, "type": "idle", "release_block": RELEASE_BLOCK}
            idle = {**reply, "type": "idle", **({"release_block": None, "release": self.release}
                                                 if self.release else {})}
            record = self._barrier[1] if self._barrier else self._latest
            if record is None or (self._barrier is None and record.frame_sequence <= self._attempted_sequence):
                return idle
            if (self._barrier is None and self.max_offer_age_ns is not None
                    and self._clock() - self._published_ns > self.max_offer_age_ns):
                # Kein historisches Nachsenden: ein liegengebliebener Wert verfaellt
                # (Pi-eigene Uhr, keine Aussage ueber das Messalter).
                self._attempted_sequence = record.frame_sequence
                self._event("stale_skipped", frame_sequence=record.frame_sequence,
                            max_offer_age_ns=self.max_offer_age_ns)
                return idle
            barrier_id = self._barrier[0] if self._barrier else None
            self._pending = {**reply, "frame_sequence": record.frame_sequence, "barrier_id": barrier_id}
            self._event("offered", **self._pending, status=record.status.value,
                        **({"release": self.release} if self.release else {}))
            return {
                **reply,
                "type": "record",
                "record": record.to_dict(),
                "frame_age_ns": None,
                "barrier_id": barrier_id,
                **({"release": self.release} if self.release else {}),
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
