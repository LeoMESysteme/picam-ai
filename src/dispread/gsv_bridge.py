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

from dispread.bridge.protocol import TEST_RELEASE, TICK_WINDOW
from dispread.gsv_transport import JsonLineReader, encode_message
from dispread.live.tick import Tick, nominal_unix_ns, validate_rate
from dispread.records import InvalidValuePolicy, TimeBaseKind, Timestamp, ValueRecord, ValueStatus
from dispread.sink.protocol.user_defined import UserDefinedFormatter
from dispread.sink.protocol.userdefined import UserDefinedFormatter as DirectFormatter
from dispread.sink.protocol.userdefined_4ch import TickFormatter, checked_value_text


class BridgeError(RuntimeError):
    """A transport attempt failed; its bytes must not be blindly retried."""


class _AdmissionExpired(BridgeError):
    """No COM attempt was admitted before the host request deadline."""


class _TickWriteFailed(BridgeError):
    """A tick line reached the driver call and failed; it stays ``unknown``."""


class BridgeAuditError(BridgeError):
    """Durable evidence failed; COM output must stop."""


class DeliveryBlockedError(BridgeError):
    """Unknown invalidation prevents further output for this Pi."""


class DeliveryUncertainError(BridgeError):
    """An earlier submission must never be automatically repeated."""


class DeliveryAlreadyAttempted(RuntimeError):
    """Atomic journal claim found a previous intent; only written may re-ACK."""

    def __init__(self, outcome):
        self.outcome = outcome
        super().__init__(f"duplicate attempt: {outcome}")


class BridgeSession:
    """One request at a time, with an independently logged COM write receipt."""

    def __init__(self, *, log=None, max_frame_age_ms=1000, timeout_s=1.0, clock=time.monotonic_ns,
                 journal=None, pi_id=None, before_write=None, admit_write=None, release_gate=None):
        """``release_gate(link, run_id)`` (R1) bestaetigt die Pi-Testfreigabe der
        aktuellen Verbindung; ohne ihn bleiben echte Werte gesperrt."""
        if max_frame_age_ms <= 0 or timeout_s <= 0:
            raise ValueError("positive age/timeout required")
        if journal is not None and (not isinstance(pi_id, str) or not pi_id):
            raise ValueError("durable delivery requires a validated Pi identity")
        self.journal, self.pi_id, self.before_write = journal, pi_id, before_write
        self.admit_write = admit_write
        self.log = log
        self.max_age_ns = int(max_frame_age_ms * 1_000_000)
        self.timeout_ns = int(timeout_s * 1_000_000_000)
        self.clock = clock
        self.formatter = UserDefinedFormatter(invalid_policy=InvalidValuePolicy.SEND_NAN, demo=True)
        # Testfreigabe: dieselben Bytes wie UART direkt (P4-3), Ungueltiges entfaellt.
        self.release_gate = release_gate
        self.release_formatter = DirectFormatter(prefix="%")
        self.tick_formatter = TickFormatter()
        self._last_written = None
        self._tick_lock = threading.Lock()
        self._tick_stats = self._empty_tick_stats(None)

    @staticmethod
    def _empty_tick_stats(run_id):
        return dict(run_id=run_id, ticks_written=0, ticks_invalid=0, ticks_filled=0, tick_disturbed=False)

    def tick_stats(self):
        """Taktzeilen des laufenden bzw. letzten Laufs; nur lokale COM-Annahme."""
        with self._tick_lock:
            return dict(self._tick_stats)

    def _count_tick(self, run_id, **increments):
        with self._tick_lock:
            if self._tick_stats["run_id"] != run_id:
                self._tick_stats = self._empty_tick_stats(run_id)
            for key, value in increments.items():
                if key == "tick_disturbed":
                    self._tick_stats[key] = self._tick_stats[key] or value
                else:
                    self._tick_stats[key] += value

    def _event(self, *, formatter=None, **event):
        if self.log is not None:
            event.update(t_ns=self.clock(), time_base="host_monotonic", provisional=True,
                         format_id=(formatter or self.formatter).capabilities.format_id,
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
        if kind == "tick":
            return self._exchange_tick(link, com, reply, request_id, started)
        if kind != "record":
            raise BridgeError("unknown reply type")
        released = reply.get("demo") is not True
        if released and (reply.get("demo") is not False or reply.get("release") != TEST_RELEASE
                         or self.release_gate is None or not self.release_gate(link, reply.get("run_id"))):
            raise BridgeError("DUT-Ausgabe gesperrt: GSVmulti-Abnahme fehlt, keine Pi-Testfreigabe")
        formatter = self.release_formatter if released else self.formatter
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
            if not released and record.capture_timestamp.base is not TimeBaseKind.SYNTHETIC:
                raise ValueError("only synthetic demo captures are allowed")
            if age is not None:
                # Keine Altersbehauptung ueber ungepaarte Pi-/Windows-Uhren.
                raise ValueError("frame age claims are not supported")
            if self.journal is not None:
                if record.status is ValueStatus.VALID and barrier is not None:
                    raise ValueError("valid record must not carry barrier")
                if record.status is not ValueStatus.VALID and (barrier is None or barrier <= 0):
                    raise ValueError("invalid record requires positive barrier")
            payload = formatter.format(record)
            if payload is None and not released:
                raise ValueError("invalid state must not be silently omitted")
        except (KeyError, TypeError, ValueError, AssertionError) as exc:
            raise BridgeError(f"invalid record: {exc}") from exc
        ack = {"version": 1, "type": "ack", "request_id": request_id, "run_id": run_id,
               "frame_sequence": record.frame_sequence, "barrier_id": barrier}
        if payload is None:
            # Testfreigabe: nur VALID an COM. Ungueltigkeit (Barriere) und nicht
            # formatierbare Werte werden quittiert, ohne ein Byte zu schreiben;
            # GSVmulti zeigt dann den letzten Wert unmarkiert weiter.
            link.send(dict(ack, outcome="omitted"))
            self._event(**ack, outcome="omitted", status=record.status.value, formatter=formatter)
            return "omitted"
        # Budget includes request, processing and COM submission; it cannot bound
        # the receiver's own buffers or prove the physical DUT measurement age.
        remaining = min(self.timeout_ns - (self.clock() - started),
                        self.max_age_ns - age - (self.clock() - started) if age is not None else self.timeout_ns)
        if remaining <= 0 and self.journal is None:
            link.send(dict(ack, outcome="expired"))
            self._event(**ack, outcome="expired")
            return "expired"
        key = (run_id, record.frame_sequence, barrier)
        if self.journal is None and key == self._last_written:
            link.send(dict(ack, outcome="written"))
            self._event(**ack, outcome="duplicate_ack", completion_stage="com_driver_write")
            return "written"
        attempt_id = None
        if self.journal is not None:
            try:
                attempt_id = self.journal.begin_attempt(
                    self.pi_id, run_id, record.frame_sequence, barrier, payload)
            except DeliveryAlreadyAttempted as exc:
                if exc.outcome == "written":
                    link.send(dict(ack, outcome="written"))
                    self._event(**ack, outcome="duplicate_ack", completion_stage="com_driver_write")
                    return "written"
                state = "unknown" if exc.outcome in ("pending", "unknown") else exc.outcome
                raise DeliveryUncertainError(f"{state} prior delivery; automatic retry blocked") from exc
            except DeliveryBlockedError:
                raise
            except Exception as exc:
                raise BridgeAuditError("audit_failed before COM; output stopped") from exc
            # Durable intent can block on fsync/locks. Recheck the host request
            # budget afterwards; synthetic capture timestamps imply no latency.
            elapsed = self.clock() - started
            remaining = min(self.timeout_ns - elapsed,
                            self.max_age_ns - age - elapsed if age is not None else self.timeout_ns)
            if remaining <= 0:
                self._finish_attempt(attempt_id, "not_written")
                link.send(dict(ack, outcome="expired"))
                self._event(**ack, outcome="expired")
                return "expired"
        if self.before_write is not None:
            try:
                self.before_write()
            except Exception:
                if attempt_id is not None:
                    self._finish_attempt(attempt_id, "not_written")
                raise
        if self.journal is not None:
            # Connection generation checks can also wait. No pre-write work
            # may extend the host request's deadline.
            elapsed = self.clock() - started
            remaining = min(self.timeout_ns - elapsed,
                            self.max_age_ns - age - elapsed if age is not None else self.timeout_ns)
            if remaining <= 0:
                self._finish_attempt(attempt_id, "not_written")
                link.send(dict(ack, outcome="expired"))
                self._event(**ack, outcome="expired")
                return "expired"
        admitted = False

        def claim():
            # Called synchronously under the connection's generation lock and
            # worker's cancellation lock. No disk, driver or network operation
            # belongs here. Lock waits and timeout setup consume the budget.
            nonlocal admitted
            if admitted:
                raise BridgeError("COM attempt already admitted")
            elapsed = self.clock() - started
            budget = min(self.timeout_ns - elapsed,
                         self.max_age_ns - age - elapsed if age is not None else self.timeout_ns)
            if budget <= 0:
                raise _AdmissionExpired("host request expired before COM admission")
            admitted = True

        try:
            # Driver configuration can block. It MUST finish before the atomic
            # generation/stop/deadline claim; it is not itself a byte submission.
            com.write_timeout = remaining / 1_000_000_000
            if self.admit_write is not None:
                self.admit_write(link, claim)
                if not admitted:
                    raise BridgeError("COM admission callback did not claim attempt")
            elif self.journal is not None:
                claim()
            else:
                admitted = True  # preserve the legacy v1 default call sequence
            # No manager/worker admission lock is held across a driver call.
            # An already admitted attempt may become unknown after revocation.
            written = com.write(payload)
            if written != len(payload):
                raise OSError(f"partial COM write: {written}/{len(payload)}")
            elapsed = self.clock() - started
            if elapsed >= self.timeout_ns or (age is not None and age + elapsed > self.max_age_ns):
                raise TimeoutError("COM write exceeded remaining freshness budget")
        except _AdmissionExpired:
            if attempt_id is not None:
                self._finish_attempt(attempt_id, "not_written")
            link.send(dict(ack, outcome="expired"))
            self._event(**ack, outcome="expired")
            return "expired"
        except Exception as exc:
            if attempt_id is not None:
                self._finish_attempt(attempt_id, "unknown" if admitted else "not_written")
            self._event(**ack, outcome="failed", attempted_bytes_hex=payload.hex() if admitted else None,
                        error=str(exc))
            if admitted:
                try:
                    com.reset_output_buffer()
                except Exception:
                    pass
            link.send(dict(ack, outcome="failed"))
            raise BridgeError(f"COM: {exc}") from exc
        if attempt_id is not None:
            self._finish_attempt(attempt_id, "written")
        self._last_written = key
        self._event(**ack, outcome="written", wire_bytes_hex=payload.hex(),
                    completion_stage="com_driver_write", formatter=formatter)
        try:
            link.send(dict(ack, outcome="written"))
        except Exception:
            self._event(**ack, outcome="unconfirmed", completion_stage="com_driver_write")
            raise
        return "written"

    @staticmethod
    def _parse_tick(reply):
        """Takt streng pruefen; der Pi hat ihn schon validiert, Windows vertraut nicht."""
        seq, valid, text = reply.get("seq"), reply.get("valid"), reply.get("value_text")
        frame, time_ns, origin = reply.get("frame_sequence"), reply.get("time_unix_ns"), reply.get("origin_unix_ns")
        rate = reply.get("rate_hz")
        if (type(seq) is not int or not 0 < seq < 2**63 or type(valid) is not bool
                or type(time_ns) is not int or time_ns < 0 or type(origin) is not int or origin < 0):
            raise ValueError("invalid tick fields")
        validate_rate(rate)
        if valid:
            if not isinstance(text, str) or checked_value_text(text) != text or type(frame) is not int or frame < 0:
                raise ValueError("invalid valid tick")
        elif text is not None or frame is not None:
            raise ValueError("invalid tick carries value")
        return Tick(seq, valid, text, time_ns, frame), origin, rate

    def _exchange_tick(self, link, com, reply, request_id, started):
        """Ein Pi-Takt: fehlende Takte zuerst als Fehlwertzeilen, dann der Takt.

        Jede Zeile wird vor dem COM-Schreiben dauerhaft beabsichtigt. Geschrieben
        wird nur oberhalb der hoechsten geschriebenen Taktnummer; kein Wert wird
        nachgereicht oder wiederholt. Luecken ueber ``TICK_WINDOW`` bleiben stehen
        und melden die Ausgabe als gestoert (Spec F2).
        """
        run_id = reply.get("run_id")
        if not isinstance(run_id, str) or not run_id or len(run_id) > 256:
            raise BridgeError("invalid run metadata")
        if reply.get("release") != TEST_RELEASE or self.release_gate is None or not self.release_gate(link, run_id):
            raise BridgeError("DUT-Ausgabe gesperrt: GSVmulti-Abnahme fehlt, keine Pi-Testfreigabe")
        if self.journal is None or self.pi_id is None:
            raise BridgeError("tick output requires the durable delivery journal")
        try:
            tick, origin, rate = self._parse_tick(reply)
            payload = self.tick_formatter.format_tick(tick)
        except (TypeError, ValueError) as exc:
            raise BridgeError(f"invalid tick: {exc}") from exc
        ack = {"version": 1, "type": "tick_ack", "request_id": request_id, "run_id": run_id, "seq": tick.seq}
        self._count_tick(run_id)
        try:
            existing = self.journal.tick_outcome(self.pi_id, run_id, tick.seq)
            last = self.journal.last_tick_written(self.pi_id, run_id)
        except Exception as exc:
            raise BridgeAuditError("audit_failed reading tick journal") from exc
        if existing == "written":
            link.send(dict(ack, outcome="written", filled=0))
            return "written"
        if existing in ("pending", "unknown"):
            raise DeliveryUncertainError("unknown prior tick delivery; automatic retry blocked")
        if existing is not None or tick.seq <= last:
            raise BridgeError("tick out of order; never written twice")
        missing = tick.seq - last - 1
        lines = []
        if missing > TICK_WINDOW:
            try:
                self.journal.record_tick_gap(self.pi_id, run_id, tick.seq, missing)
            except Exception as exc:
                raise BridgeAuditError("audit_failed recording tick gap") from exc
            self._count_tick(run_id, tick_disturbed=True)
            self._event(outcome="tick_gap_unfilled", run_id=run_id, seq=tick.seq, missing=missing,
                        formatter=self.tick_formatter)
        else:
            for seq in range(last + 1, tick.seq):
                fill = Tick(seq, False, None, nominal_unix_ns(origin, rate, seq), None)
                lines.append(("fill", fill, self.tick_formatter.format_tick(fill)))
        lines.append(("tick", tick, payload))
        filled = 0
        for kind, line, data in lines:
            try:
                outcome = self._write_tick_line(link, com, run_id, kind, line, data, started)
            except _TickWriteFailed as exc:
                self._event(**ack, outcome="failed", filled=filled, failed_seq=line.seq, error=str(exc),
                            formatter=self.tick_formatter)
                link.send(dict(ack, outcome="failed", filled=filled))
                raise
            if outcome != "written":
                link.send(dict(ack, outcome="expired", filled=filled))
                self._event(**ack, outcome="expired", filled=filled, formatter=self.tick_formatter)
                return "expired"
            if kind == "fill":
                filled += 1
                self._count_tick(run_id, ticks_filled=1)
            else:
                self._count_tick(run_id, ticks_written=1, ticks_invalid=int(not line.valid))
        self._event(**ack, outcome="written", filled=filled, wire_bytes_hex=payload.hex(),
                    completion_stage="com_driver_write", formatter=self.tick_formatter)
        try:
            link.send(dict(ack, outcome="written", filled=filled))
        except Exception:
            self._event(**ack, outcome="unconfirmed", completion_stage="com_driver_write",
                        formatter=self.tick_formatter)
            raise
        return "written"

    def _write_tick_line(self, link, com, run_id, kind, line, payload, started):
        """Eine Zeile: Absicht, Zulassung im Budget, COM, Ergebnis. ``not_written`` bei Ablauf."""
        try:
            attempt_id = self.journal.begin_tick(self.pi_id, run_id, line.seq, kind, line.valid, payload)
        except (DeliveryBlockedError, DeliveryAlreadyAttempted) as exc:
            raise DeliveryUncertainError("unknown prior delivery; automatic retry blocked") from exc
        except Exception as exc:
            raise BridgeAuditError("audit_failed before COM; output stopped") from exc
        admitted = False

        def claim():
            nonlocal admitted
            if admitted:
                raise BridgeError("COM attempt already admitted")
            if self.timeout_ns - (self.clock() - started) <= 0:
                raise _AdmissionExpired("host request expired before COM admission")
            admitted = True

        try:
            remaining = self.timeout_ns - (self.clock() - started)
            if remaining <= 0:
                raise _AdmissionExpired("host request expired before COM admission")
            com.write_timeout = remaining / 1_000_000_000
            if self.admit_write is not None:
                self.admit_write(link, claim)
                if not admitted:
                    raise BridgeError("COM admission callback did not claim attempt")
            else:
                claim()
            written = com.write(payload)
            if written != len(payload):
                raise OSError(f"partial COM write: {written}/{len(payload)}")
        except _AdmissionExpired:
            self._finish_tick(attempt_id, "not_written")
            return "expired"
        except Exception as exc:
            self._finish_tick(attempt_id, "unknown" if admitted else "not_written")
            if admitted:
                try:
                    com.reset_output_buffer()
                except Exception:
                    pass
            raise _TickWriteFailed(f"COM: {exc}") from exc
        self._finish_tick(attempt_id, "written")
        return "written"

    def _finish_tick(self, attempt_id, outcome):
        try:
            self.journal.finish_tick(attempt_id, outcome)
        except Exception as exc:
            raise BridgeAuditError("audit_failed; tick delivery unknown; output stopped") from exc

    def _finish_attempt(self, attempt_id, outcome):
        try:
            self.journal.finish_attempt(attempt_id, outcome)
        except Exception as exc:
            # The committed pending intent remains conservative evidence when
            # the final disk write fails. Never send a written ACK here.
            raise BridgeAuditError("audit_failed; delivery unknown; output stopped") from exc


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
