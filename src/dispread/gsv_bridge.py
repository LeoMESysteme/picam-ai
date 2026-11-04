"""Windows companion for provisional UserDefined transport experiments.

Only synthetic demo records may reach COM until the receiver's invalid/stale
semantics have been demonstrated. A COM write receipt is NOT a GSVmulti ACK.
This module deliberately imports no camera, numpy or OpenCV packages.
"""
from __future__ import annotations

import argparse
import json
import math
import socket
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from dispread.gsv_transport import JsonLineReader, encode_message
from dispread.records import InvalidValuePolicy, TimeBaseKind, Timestamp, ValueRecord, ValueStatus
from dispread.sink.protocol.user_defined import UserDefinedFormatter


class BridgeError(RuntimeError):
    """A transport attempt failed; its bytes must not be blindly retried."""


class BridgeSession:
    """One request at a time, with an independently logged COM write receipt."""

    def __init__(self, *, log=None, max_frame_age_ms=1000, timeout_s=1.0, clock=time.monotonic_ns):
        if max_frame_age_ms <= 0 or timeout_s <= 0:
            raise ValueError("positive age/timeout required")
        self.log = log
        self.max_age_ns = int(max_frame_age_ms * 1_000_000)
        self.timeout_ns = int(timeout_s * 1_000_000_000)
        self.clock = clock
        self.formatter = UserDefinedFormatter(invalid_policy=InvalidValuePolicy.SEND_NAN, demo=True)
        self._last_written = None

    def _event(self, **event):
        if self.log is not None:
            event.update(t_ns=self.clock(), time_base="host_monotonic", provisional=True,
                         format_id=self.formatter.capabilities.format_id,
                         carries_capture_timestamp=False, timestamp_resolution_ns=None)
            self.log.write(json.dumps(event, allow_nan=False) + "\n")
            self.log.flush()

    def exchange(self, link, com):
        request_id = uuid.uuid4().hex
        started = self.clock()
        link.send({"version": 1, "type": "poll", "request_id": request_id})
        reply = link.receive()
        if (not isinstance(reply, dict) or type(reply.get("version")) is not int or reply["version"] != 1
                or reply.get("request_id") != request_id):
            raise BridgeError("invalid version/request_id")
        kind = reply.get("type")
        if kind in ("idle", "ended"):
            self._event(outcome=kind, run_id=reply.get("run_id"), release_block=reply.get("release_block"))
            return kind
        if kind != "record":
            raise BridgeError("unknown reply type")
        if reply.get("demo") is not True:
            raise BridgeError("DUT-Ausgabe gesperrt: GSVmulti-Abnahme fehlt")
        run_id = reply.get("run_id")
        barrier = reply.get("barrier_id")
        age = reply.get("frame_age_ns")
        if (not isinstance(run_id, str) or not run_id or len(run_id) > 256
                or (barrier is not None and (type(barrier) is not int or barrier < 0))
                or (age is not None and (type(age) is not int or age < 0))):
            raise BridgeError("invalid run/barrier/age metadata")
        try:
            record = ValueRecord.from_dict(reply["record"])
            if type(record.frame_sequence) is not int or record.frame_sequence < 0:
                raise ValueError("invalid frame sequence")
            if record.capture_timestamp.base is not TimeBaseKind.SYNTHETIC:
                raise ValueError("only synthetic demo captures are allowed")
            if age is not None:
                raise ValueError("synthetic frame has no measured age")
            if age is None and record.capture_timestamp.base is not TimeBaseKind.SYNTHETIC:
                raise ValueError("missing measured age")
            payload = self.formatter.format(record)
            if payload is None:
                raise ValueError("invalid state must not be silently omitted")
        except (KeyError, TypeError, ValueError, AssertionError) as exc:
            raise BridgeError(f"invalid record: {exc}") from exc
        ack = {"version": 1, "type": "ack", "request_id": request_id, "run_id": run_id,
               "frame_sequence": record.frame_sequence, "barrier_id": barrier}
        # Budget includes request, processing and COM submission; it cannot bound
        # the receiver's own buffers or prove the physical DUT measurement age.
        remaining = min(self.timeout_ns - (self.clock() - started),
                        self.max_age_ns - age - (self.clock() - started) if age is not None else self.timeout_ns)
        if remaining <= 0:
            link.send(dict(ack, outcome="expired"))
            self._event(**ack, outcome="expired")
            return "expired"
        key = (run_id, record.frame_sequence, barrier)
        if key == self._last_written:
            link.send(dict(ack, outcome="written"))
            self._event(**ack, outcome="duplicate_ack", completion_stage="com_driver_write")
            return "written"
        try:
            com.write_timeout = remaining / 1_000_000_000
            written = com.write(payload)
            if written != len(payload):
                raise OSError(f"partial COM write: {written}/{len(payload)}")
            elapsed = self.clock() - started
            if elapsed >= self.timeout_ns or (age is not None and age + elapsed > self.max_age_ns):
                raise TimeoutError("COM write exceeded remaining freshness budget")
        except Exception as exc:
            self._event(**ack, outcome="failed", attempted_bytes_hex=payload.hex(), error=str(exc))
            try:
                com.reset_output_buffer()
            except Exception:
                pass
            link.send(dict(ack, outcome="failed"))
            raise BridgeError(f"COM: {exc}") from exc
        self._last_written = key
        self._event(**ack, outcome="written", wire_bytes_hex=payload.hex(),
                    completion_stage="com_driver_write")
        try:
            link.send(dict(ack, outcome="written"))
        except Exception:
            self._event(**ack, outcome="unconfirmed", completion_stage="com_driver_write")
            raise
        return "written"


class _Link:
    def __init__(self, connection, *, serial=False, timeout_s=1.0):
        self.connection, self.serial = connection, serial
        self.decoder = JsonLineReader()
        self.pending = deque()
        self.timeout_s = timeout_s

    def send(self, message):
        payload = encode_message(message)
        if self.serial:
            if self.connection.write(payload) != len(payload):
                raise BridgeError("partial UART write")
        else:
            self.connection.sendall(payload)

    def receive(self):
        deadline = time.monotonic() + self.timeout_s
        while not self.pending:
            if time.monotonic() >= deadline:
                raise TimeoutError("Pi reply timeout")
            data = (self.connection.read(max(1, min(self.connection.in_waiting, 4096)))
                    if self.serial else self.connection.recv(4096))
            if not data:
                if not self.serial:
                    raise ConnectionError("Pi connection closed")
                continue
            self.pending.extend(self.decoder.feed(data))
        return self.pending.popleft()


def demo_records(count=600):
    """Finite, unique synthetic values; no sensor-time or accuracy claim."""
    if type(count) is not int or not 1 <= count <= 100000:
        raise ValueError("demo count must be 1..100000")
    for index in range(count):
        raw = f"{(index - count // 2) / 1000:+08.3f}"
        yield ValueRecord(index, Timestamp(index, TimeBaseKind.SYNTHETIC), float(raw), "mV/V",
                          ValueStatus.VALID, 1.0, "demo/userdefined", None, None, raw_text=raw)


def send_demo(com, *, count=600, rate_hz=10.0, stop=None, wait=None, log=None,
              completion_stage="com_driver_write"):
    """Submit a finite demo directly to a COM port (or a binary stdout)."""
    if not math.isfinite(rate_hz) or not 0 < rate_hz <= 100:
        raise ValueError("demo rate must be >0 and <=100 Hz")
    stop = stop or threading.Event()
    wait = wait or stop.wait
    formatter = UserDefinedFormatter()
    for record in demo_records(count):
        if stop.is_set():
            break
        payload = formatter.format(record)
        if com.write(payload) != len(payload):
            raise BridgeError("partial COM demo write")
        if log is not None:
            log.write(json.dumps({"demo": True, "provisional": True, "format_id": formatter.capabilities.format_id,
                                  "capture_time_base": "synthetic", "frame_sequence": record.frame_sequence,
                                  "wire_bytes_hex": payload.hex(), "completion_stage": completion_stage,
                                  "t_ns": time.monotonic_ns(), "time_base": "host_monotonic"}) + "\n")
            log.flush()
        if wait(1 / rate_hz):
            break


def _serial(port, baudrate, *, timeout=0.1):
    import serial
    return serial.Serial(port, baudrate=baudrate, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                         stopbits=serial.STOPBITS_ONE, timeout=timeout, write_timeout=1,
                         xonxoff=False, rtscts=False, dsrdtr=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vorläufige Windows-COM-Brücke; echte DUT-Ausgabe bis Abnahme gesperrt.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tcp-host", help="Pi-Adresse (Brücke verbindet als TCP-Client)")
    source.add_argument("--uart-port", help="Physischer USB-TTL-COM-Port am Windows-PC")
    source.add_argument("--demo", action="store_true", help="Endliche synthetische Demowerte ohne Pi senden")
    parser.add_argument("--tcp-port", type=int, default=5000)
    parser.add_argument("--com-port", help="Brückenseite des virtuellen COM-Portpaars")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--stdout", action="store_true", help="Nur --demo: Telegramme nach stdout statt COM")
    parser.add_argument("--count", type=int, default=600)
    parser.add_argument("--rate-hz", type=float, default=10)
    parser.add_argument("--max-frame-age-ms", type=int, default=1000)
    parser.add_argument("--log", type=Path, default=Path("bridge.jsonl"))
    args = parser.parse_args(argv)
    if args.stdout and not args.demo:
        parser.error("--stdout ist nur für --demo verfügbar")
    if not args.stdout and not args.com_port:
        parser.error("--com-port fehlt")
    if args.uart_port and args.uart_port.casefold() == args.com_port.casefold():
        parser.error("Eingang und Ausgang müssen unterschiedliche COM-Ports sein")
    if not (0 < args.tcp_port < 65536 and args.baudrate > 0 and args.max_frame_age_ms > 0
            and 0 < args.rate_hz <= 100 and math.isfinite(args.rate_hz) and 1 <= args.count <= 100000):
        parser.error("ungültige Port-, Raten-, Alters- oder Demoanzahl-Einstellung")
    stop = threading.Event()
    with args.log.open("a", encoding="utf-8") as log:
        if args.demo:
            output = sys.stdout.buffer if args.stdout else _serial(args.com_port, args.baudrate)
            try:
                send_demo(output, count=args.count, rate_hz=args.rate_hz, stop=stop, log=log,
                          completion_stage="stdout_write" if args.stdout else "com_driver_write")
            finally:
                if not args.stdout:
                    output.close()
            return 0
        session = BridgeSession(log=log, max_frame_age_ms=args.max_frame_age_ms)
        delay = 1
        try:
            while not stop.is_set():
                com = connection = None
                try:
                    try:
                        com = _serial(args.com_port, args.baudrate)
                    except Exception as exc:
                        raise BridgeError(f"COM open: {exc}") from exc
                    connection = (_serial(args.uart_port, args.baudrate) if args.uart_port else
                                  socket.create_connection((args.tcp_host, args.tcp_port), timeout=1))
                    link = _Link(connection, serial=bool(args.uart_port))
                    while not stop.is_set():
                        outcome = session.exchange(link, com)
                        delay = 1
                        if outcome == "ended":
                            break
                        stop.wait(1 / args.rate_hz)
                except (OSError, ValueError, BridgeError, KeyError) as exc:
                    session._event(outcome="connection_error", error=f"{type(exc).__name__}: {exc}")
                    print(f"Verbindungswarnung: {exc}; neuer Versuch in {delay}s", file=sys.stderr)
                finally:
                    if connection is not None:
                        connection.close()
                    if com is not None:
                        com.close()
                stop.wait(delay)
                delay = min(delay * 2, 8)
        except KeyboardInterrupt:
            stop.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
