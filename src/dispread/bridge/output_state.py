"""Bounded output/audit state shared by v1 transports and validated v2 adapters.

No sockets, serial devices or workers are opened here. Adapters must authorize
and bind v2 clients/leases before translating requests into handle_v1 fields.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict
from pathlib import Path

from dispread.bridge.protocol import TEST_RELEASE, TICK_WINDOW
from dispread.records import TimeBaseKind, ValueRecord, ValueStatus
from dispread.sink.protocol.user_defined import UserDefinedFormatter
from dispread.sink.protocol.userdefined_4ch import TickFormatter

RELEASE_BLOCK = "DUT-Ausgabe gesperrt: Windows-Abnahme für Ungültig-/Altwertbehandlung fehlt"
#: Bounded wait at run end so that already generated ticks can still be fetched.
TICK_DRAIN_TIMEOUT_S = 1.0


class OutputState:
    """``release=TEST_RELEASE`` ist die vom Pi-Bediener je Lauf bestaetigte
    Testfreigabe echter Werte (Nutzerentscheidung 2026-11-09, keine Abnahme).
    Ohne sie bleibt jede echte Ausgabe gesperrt. Ungueltigkeit wird dann nur
    als Barriere quittiert (``omitted``), nie als COM-Schreibvorgang.
    """

    def __init__(self, out_dir: Path, *, demo=False, release=None, max_offer_age_ns=None,
                 clock=time.monotonic_ns, tick_rate_hz=None, tick_max_frame_age_ns=None,
                 timebase=None, tick_thread=True):
        """``tick_rate_hz`` (B2, 2026-11-11) schaltet auf den Vierkanal-Takt: Der Pi
        erzeugt mit demselben ``Ticker`` wie bei UART direkt je Takt genau einen
        Datensatz, auditiert ihn und haelt hoechstens ``TICK_WINDOW`` Takte zum
        Angebot vor. Ohne Testfreigabe entsteht kein einziger Takt.
        """
        if release not in (None, TEST_RELEASE) or (demo and release is not None):
            raise ValueError("release marker must be the exact test release and never demo")
        if tick_rate_hz is not None:
            from dispread.live.tick import validate_rate

            if demo:
                raise ValueError("demo never uses the tick output")
            validate_rate(tick_rate_hz)
            if tick_max_frame_age_ns is None:
                tick_max_frame_age_ns = 1_000_000_000
            if type(tick_max_frame_age_ns) is not int or tick_max_frame_age_ns <= 0:
                raise ValueError("invalid tick frame age limit")
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
        self.tick_rate_hz = tick_rate_hz
        self._tick_max_age_ns = tick_max_frame_age_ns
        self._timebase = timebase
        self._tick_thread_enabled = tick_thread
        self._ticker = None
        self._tick_queue = deque()
        self._tick_counts = dict(offered=0, acknowledged=0, unconfirmed=0, lost=0)
        self._tick_stop = threading.Event()
        self._tick_thread = None
        self.drain_timeout_s = TICK_DRAIN_TIMEOUT_S
        #: Testnaht fuer Zeitraffer: Wartezeiten des Taktthreads werden geteilt.
        self._time_scale = 1

    @property
    def release_block(self):
        return None if self.demo or self.release is not None else RELEASE_BLOCK

    @property
    def offers_records(self):
        return self.demo or self.release is not None

    @property
    def tick_mode(self):
        return self.tick_rate_hz is not None

    def _release_fields(self):
        return {"release_block": self.release_block, **({"release": self.release} if self.release else {})}

    def metadata(self):
        formatter = TickFormatter() if self.tick_mode else UserDefinedFormatter()
        caps = asdict(formatter.capabilities)
        caps["supported_invalid_policies"] = sorted(
            getattr(policy, "value", policy) for policy in caps["supported_invalid_policies"])
        return {
            "run_id": self.run_id,
            "demo": self.demo,
            "release_block": self.release_block,
            "release": self.release,
            "formatter": caps,
            **({"format": "4ch", "rate_hz": self.tick_rate_hz, "tick": self.tick_status()}
               if self.tick_mode else {}),
        }

    def tick_status(self):
        """B1-Taktfelder plus Bruecke: angeboten, quittiert, unbestaetigt, verloren, wartend.

        ``acknowledged`` belegt nur die COM-Annahme auf Windows (``written``),
        nie den Empfang durch GSVmulti. ``lost``: erzeugt, aber nie geschrieben
        (aelter als das Fenster, ``expired`` oder bei Laufende noch wartend).
        """
        from dispread.live.tick import tick_status

        with self._lock:
            return {**tick_status(self.tick_rate_hz, self._ticker, self._timebase),
                    **self._tick_counts, "queued": len(self._tick_queue), "window": TICK_WINDOW,
                    "ack_scope": "COM driver write, not GSVmulti reception"}

    def status(self):
        with self._lock:
            return {
                "state": self._state,
                "release_block": self.release_block,
                "release": self.release,
                "error": self._error,
                "last_ack": self._last_ack,
                "ack_scope": "COM driver write, not GSVmulti reception",
                **({"tick": self.tick_status()} if self.tick_mode else {}),
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

    def start(self, *, clock_log=None):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._events = (self.out_dir / "output.jsonl").open("a", encoding="utf-8")
        self._event("start", demo=self.demo, release_block=self.release_block, release=self.release,
                    max_offer_age_ns=self.max_offer_age_ns,
                    **({"format": "4ch", "rate_hz": self.tick_rate_hz,
                        "max_frame_age_ns": self._tick_max_age_ns} if self.tick_mode else {}))
        if self.tick_mode and self.release is not None:
            from dispread.live.clock import ClockLog
            from dispread.live.tick import Ticker, TickTimebase

            with self._lock:
                self._timebase = self._timebase or TickTimebase(clock_log or ClockLog())
                self._ticker = Ticker(self.tick_rate_hz, self._clock, self._tick_max_age_ns,
                                      timebase=self._timebase)
                self._event("tick_start", origin_unix_ns=self._ticker.origin_unix_ns,
                            start_monotonic_ns=self._ticker.start_ns, timebase=self._timebase.status())
            if self._tick_thread_enabled:
                self._tick_thread = threading.Thread(target=self._tick_loop, name="bridge-ticker", daemon=True)
                self._tick_thread.start()

    def step_ticks(self):
        """Faelligen Takt erzeugen, auditieren und erst danach zum Angebot stellen.

        Gleiche Taktentscheidung wie UART direkt (``Ticker.due``); kein Aufholen.
        Takte, die mehr als ``TICK_WINDOW`` hinter dem juengsten liegen, gelten als
        verloren; Windows fuellt die Luecke mit Fehlwertzeilen.
        """
        with self._lock:
            if (self._ticker is None or self._tick_stop.is_set() or self._stop.is_set()
                    or self._state == "audit_failed"):
                return None
            tick = self._ticker.due(self._clock())
            if tick is None:
                return None
            # Audit vor Angebot: ohne Beleg wird der Takt nie angeboten.
            self._event("tick", seq=tick.seq, valid=tick.valid, value_text=tick.value_text,
                        frame_sequence=tick.frame_sequence, time_unix_ns=tick.time_unix_ns,
                        tick_time_base="unix_realtime_from_monotonic")
            self._tick_queue.append(tick)
            dropped = []
            while self._tick_queue and self._tick_queue[0].seq <= tick.seq - TICK_WINDOW:
                dropped.append(self._tick_queue.popleft().seq)
            if dropped:
                self._tick_lost(dropped, reason="window")
            return tick

    def _tick_lost(self, seqs, *, reason):
        self._tick_counts["lost"] += len(seqs)
        self._event("tick_lost", count=len(seqs), first_seq=seqs[0], last_seq=seqs[-1], reason=reason)

    def _tick_loop(self):
        try:
            while not self._tick_stop.is_set():
                self.step_ticks()
                with self._lock:
                    if self._ticker is None or self._state == "audit_failed":
                        return
                    delay = (self._ticker.next_deadline_ns - self._clock()) / 1e9
                self._tick_stop.wait(min(max(0.0, delay) / self._time_scale, 0.2))
        except Exception as exc:  # noqa: BLE001 - kein stiller Taktausfall
            self._tick_stop.set()
            with self._lock:
                if self._state != "audit_failed":
                    self._state, self._error = "tick_failed", f"{type(exc).__name__}: {exc}"

    def _tick_reply(self, reply):
        tick = self._tick_queue.popleft()
        self._pending = {**reply, "seq": tick.seq, "kind": "tick"}
        self._tick_counts["offered"] += 1
        self._event("tick_offered", request_id=reply["request_id"], seq=tick.seq, release=self.release)
        return {**reply, "type": "tick", "seq": tick.seq, "valid": tick.valid, "value_text": tick.value_text,
                "frame_sequence": tick.frame_sequence, "time_unix_ns": tick.time_unix_ns,
                "origin_unix_ns": self._ticker.origin_unix_ns, "rate_hz": self.tick_rate_hz,
                "release": self.release}

    def _tick_ack(self, message):
        pending = self._pending
        if pending is None or pending.get("kind") != "tick":
            raise ValueError("unsolicited tick ACK")
        if any(message.get(key) != pending[key] for key in ("request_id", "run_id", "seq")):
            raise ValueError("tick ACK does not match pending tick")
        outcome = message.get("outcome")
        filled = message.get("filled")
        if outcome not in ("written", "expired", "failed", "unconfirmed") or type(filled) is not int \
                or not 0 <= filled <= TICK_WINDOW:
            raise ValueError("invalid tick ACK")
        self._event("tick_ack", request_id=pending["request_id"], seq=pending["seq"], outcome=outcome,
                    filled=filled)
        key = {"written": "acknowledged", "expired": "lost"}.get(outcome, "unconfirmed")
        self._tick_counts[key] += 1
        self._last_ack = {"request_id": pending["request_id"], "run_id": pending["run_id"], "seq": pending["seq"],
                          "outcome": outcome, "filled": filled, "scope": "COM driver only"}
        self._pending = None

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
                if self._ticker is not None:
                    self._ticker.on_record(None)  # naechster Takt traegt den Fehlwert
                self._event("release_time_base_rejected", frame_sequence=record.frame_sequence,
                            time_base=record.capture_timestamp.base.value)
                return
            if self.tick_mode:
                # Taktbetrieb: nur der Ticker entscheidet, ohne Taktfreigabe nichts.
                if self._ticker is not None:
                    self._ticker.on_record(record)
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
            if message.get("type") == "tick_ack":
                return self._tick_ack(message)
            if message.get("type") == "ack":
                if self._pending is None or self._pending.get("kind") == "tick":
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
            if self.tick_mode:
                return self._tick_reply(reply) if self._tick_queue else idle
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
                if self._pending.get("kind") == "tick":
                    # Ein angebotener Takt wird nie erneut angeboten.
                    self._tick_counts["unconfirmed"] += 1
                    self._event("unconfirmed", request_id=self._pending["request_id"],
                                run_id=self._pending["run_id"], seq=self._pending["seq"])
                    self._pending = None
                    return
                self._event("unconfirmed", **self._pending)
                if self._pending["barrier_id"] is None:
                    self._attempted_sequence = self._pending["frame_sequence"]
                self._pending = None

    def _stop_ticks(self):
        """Keine neuen Takte; bereits erzeugte begrenzt abholen lassen (Laufende)."""
        if self._tick_stop.is_set():
            return
        self._tick_stop.set()
        thread = self._tick_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        with self._lock:
            ticker = self._ticker
        if ticker is None:
            return
        deadline = time.monotonic() + self.drain_timeout_s
        while time.monotonic() < deadline and not self._stop.is_set():
            with self._lock:
                if not self._tick_queue and self._pending is None:
                    break
            self._stop.wait(.01)
        with self._lock:
            if self._timebase is not None:
                self._timebase.observe()
            if self._tick_queue:
                self._tick_lost([tick.seq for tick in self._tick_queue], reason="run_end")
                self._tick_queue.clear()

    def stop(self):
        if self.tick_mode:
            try:
                self._stop_ticks()
            except OSError:
                pass  # audit_failed ist bereits gesetzt; Abschluss geht weiter
        self._stop.set()
        with self._lock:
            if self._events:
                try:
                    self.abandon_pending()
                    if self.tick_mode:
                        self._event("tick_end", **self.tick_status())
                    self._event("stop")
                finally:
                    self._events.close()
                    self._events = None
            if self._state != "audit_failed":
                self._state = "stopped"
