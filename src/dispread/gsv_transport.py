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
from dataclasses import asdict, dataclass
from pathlib import Path

from dispread.bridge.baud import UART_BAUD
from dispread.bridge.output_state import RELEASE_BLOCK as RELEASE_BLOCK
from dispread.bridge.output_state import OutputState
from dispread.hardware_ports import GSV_UART_PORT

MAX_MESSAGE_BYTES = 65536


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
    serial_port: str = GSV_UART_PORT
    baudrate: int = UART_BAUD
    tcp_host: str = "0.0.0.0"
    tcp_port: int = 5000
    max_frame_age_ms: int = 1000

    def __post_init__(self):
        if self.transport not in ("off", "uart", "tcp"):
            raise ValueError("Unbekannter Ausgabeweg")
        if self.serial_port != GSV_UART_PORT:
            raise ValueError(f"UART-Ausgang muss {GSV_UART_PORT} sein; Referenzport bleibt frei")
        if type(self.baudrate) is not int or self.baudrate != UART_BAUD:
            raise ValueError(f"Brücke benötigt {UART_BAUD} Baud")
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


class OutputPublisher(OutputState):
    """Compatibility v1 transport adapter over the shared bounded state."""

    def __init__(self, config: OutputConfig, out_dir: Path, *, demo=False):
        self.config = config
        super().__init__(out_dir, demo=demo)
        self._thread = None
        self._state = "off" if config.transport == "off" else "waiting"

    def metadata(self):
        return {**self.config.to_dict(), **super().metadata()}

    def status(self):
        return {"transport": self.config.transport, **super().status()}

    def start(self):
        if self.config.transport == "off":
            return
        super().start()
        self._thread = threading.Thread(target=self._worker, name="gsv-output", daemon=True)
        self._thread.start()

    def handle(self, message: dict):
        return self.handle_v1(message)

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
        super().stop()
