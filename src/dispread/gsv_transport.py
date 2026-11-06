"""Bounded, versioned Pi/Windows bridge transport. Real DUT output is locked.

The bridge protocol is ours, not a native GSV device protocol. ACK means
COM-driver submission, never GSVmulti receipt. Local monotonic event marks
are explicitly labelled; the ValueRecord remains unmodified.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from dispread.records import TimeBaseKind, ValueRecord, ValueStatus
from dispread.sink.protocol.user_defined import UserDefinedFormatter

MAX_MESSAGE_BYTES = 65536
RELEASE_BLOCK = "DUT-Ausgabe gesperrt: Windows-Abnahme für Ungültig-/Altwertbehandlung fehlt"


def encode_message(message: dict) -> bytes:
    result = (json.dumps(message, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(result) > MAX_MESSAGE_BYTES:
        raise ValueError("bridge message too large")
    return result


class JsonLineReader:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[dict]:
        result = []
        for chunk in data.splitlines(keepends=True):
            self.buffer.extend(chunk)
            if len(self.buffer) > MAX_MESSAGE_BYTES:
                raise ValueError("bridge message too large")
            if self.buffer.endswith(b"\n"):
                raw = bytes(self.buffer)
                self.buffer.clear()

                def reject_constant(value):
                    raise ValueError(f"non-finite JSON constant: {value}")

                obj = json.loads(raw, parse_constant=reject_constant)
                if not isinstance(obj, dict) or obj.get("version") != 1:
                    raise ValueError("invalid bridge version or message")
                result.append(obj)
        return result


@dataclass(frozen=True)
class OutputConfig:
    transport: str = "off"
    serial_port: str = "/dev/ttyAMA0"
    baudrate: int = 115200
    tcp_host: str = "0.0.0.0"
    tcp_port: int = 5000
    max_frame_age_ms: int = 1000

    def __post_init__(self):
        if self.transport not in ("off", "uart", "tcp"):
            raise ValueError("Unbekannter Ausgabeweg")
        if self.serial_port != "/dev/ttyAMA0":
            raise ValueError("UART-Ausgang muss /dev/ttyAMA0 sein; Referenzport bleibt frei")
        if type(self.baudrate) is not int or self.baudrate != 115200:
            raise ValueError("Prototyp benötigt 115200 Baud")
        if type(self.tcp_port) is not int or not 1 <= self.tcp_port <= 65535:
            raise ValueError("Ungültiger TCP-Port")
        if not isinstance(self.tcp_host, str) or not self.tcp_host:
            raise ValueError("Ungültige Bind-Adresse")
        if type(self.max_frame_age_ms) is not int or not 1 <= self.max_frame_age_ms <= 1000:
            raise ValueError("Frischegrenze muss 1–1000 ms sein")

    @classmethod
    def from_dict(cls, raw):
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise ValueError("Ausgabekonfiguration muss ein Objekt sein")
        try:
            return cls(**raw)
        except TypeError as exc:
            raise ValueError("Unbekannte Ausgabefelder") from exc

    def to_dict(self):
        return asdict(self)


class OutputPublisher:
    def __init__(self, config: OutputConfig, out_dir: Path, *, demo=False):
        self.config = config
        self.out_dir = Path(out_dir)
        self.demo = demo
        self.run_id = uuid.uuid4().hex
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._latest = None
        self._barrier = None
        self._generation = 0
        self._pending = None
        self._state = "off" if config.transport == "off" else "waiting"
        self._error = None
        self._last_ack = None
        self._attempted_sequence = -1
        self._events = None

    def metadata(self):
        caps = asdict(UserDefinedFormatter().capabilities)
        caps["supported_invalid_policies"] = sorted(caps["supported_invalid_policies"])
        return {
            **self.config.to_dict(),
            "run_id": self.run_id,
            "demo": self.demo,
            "release_block": None if self.demo else RELEASE_BLOCK,
            "formatter": caps,
        }

    def status(self):
        with self._lock:
            return {
                "transport": self.config.transport,
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
        if self.config.transport == "off":
            return
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._events = (self.out_dir / "output.jsonl").open("a", encoding="utf-8")
        self._event("start", demo=self.demo, release_block=None if self.demo else RELEASE_BLOCK)
        self._thread = threading.Thread(target=self._worker, name="gsv-output", daemon=True)
        self._thread.start()

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

    def handle(self, message: dict):
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

    def abandon_pending(self):
        """Record uncertainty; losing an ACK never proves non-delivery."""
        with self._lock:
            if self._pending is not None:
                self._event("unconfirmed", **self._pending)
                if self._pending["barrier_id"] is None:
                    self._attempted_sequence = self._pending["frame_sequence"]
                self._pending = None

    def _serve(self, stream, *, tcp):
        decoder = JsonLineReader()
        last_request = time.monotonic()
        with self._lock:
            self.abandon_pending()
            self._state, self._error = "bridge_connected", None
            self._event("connected")
        while not self._stop.is_set():
            try:
                data = stream.recv(4096) if tcp else stream.read(max(1, min(stream.in_waiting, 4096)))
            except TimeoutError:
                data = None
            if tcp and data == b"":
                raise ConnectionError("bridge disconnected")
            if data:
                last_request = time.monotonic()
                for message in decoder.feed(data):
                    reply = self.handle(message)
                    if reply is not None:
                        payload = encode_message(reply)
                        if tcp:
                            stream.sendall(payload)
                        elif stream.write(payload) != len(payload):
                            raise OSError("partial UART write")
            if time.monotonic() - last_request > 2:
                raise TimeoutError("bridge heartbeat missing")

    def _worker(self):
        delay = 1
        while not self._stop.is_set():
            try:
                if self.config.transport == "tcp":
                    with socket.socket() as listener:
                        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        listener.bind((self.config.tcp_host, self.config.tcp_port))
                        listener.listen(1)
                        listener.settimeout(0.2)
                        while not self._stop.is_set():
                            try:
                                connection, _ = listener.accept()
                            except TimeoutError:
                                continue
                            with connection:
                                connection.settimeout(0.2)
                                self._serve(connection, tcp=True)
                else:
                    import serial

                    with serial.Serial(
                        self.config.serial_port,
                        self.config.baudrate,
                        timeout=0.1,
                        write_timeout=0.2,
                        xonxoff=False,
                        rtscts=False,
                        dsrdtr=False,
                    ) as stream:
                        self._serve(stream, tcp=False)
                delay = 1
            except Exception as exc:
                with self._lock:
                    if self._state != "audit_failed":
                        self._state, self._error = "disconnected", f"{type(exc).__name__}: {exc}"
                    try:
                        self.abandon_pending()
                        self._event("disconnected", error=self._error)
                    except OSError:
                        self._state = "audit_failed"
                        self._stop.set()
                self._stop.wait(delay)
                delay = min(8, delay * 2)
        with self._lock:
            if self._state != "audit_failed":
                self._state = "stopped"

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        with self._lock:
            if self._events:
                try:
                    self.abandon_pending()
                    self._event("stop")
                finally:
                    self._events.close()
                    self._events = None
