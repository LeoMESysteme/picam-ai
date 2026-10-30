#!/usr/bin/env python3
"""Endlicher UserDefined-Demostrom für die offene Windows-Abnahme (P4-2).

Keine Kamera, keine Messfreigabe. Nur der Sendeversuch hat CLOCK_BOOTTIME;
die ValueRecords sind SYNTHETIC und tragen keine Aufnahmezeitaussage.
Vollstaendige Telegramme mit Schreibfrist; kein Aufholburst.
sent bedeutet Annahme durch den lokalen Treiber, keinen GSVmulti-Empfang.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from time import sleep
from typing import TextIO

import serial

from dispread.records import TimeBaseKind, Timestamp, ValueRecord, ValueStatus
from dispread.sink.protocol.userdefined import UserDefinedFormatter
from dispread.sink.serial_out import SerialWriteError, write_complete

BAUDRATES = (2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)
# Grenzen des Demo-Profils aus dem Beispiel-ZIP, keine behaupteten GSVmulti-Grenzen.
PROFILES = {
    "constant": ("+12.345",),
    "staircase": ("0", "1", "2", "3", "4", "5", "4", "3", "2", "1"),
    "boundaries": ("-99999.999", "-12.345", "-0.001", "-0.000", "0", "+0.000", "+0.001", "+99999.999"),
}
PROTECTED_PORTS = ("/dev/ttyUSB0", "/dev/serial0")


def boottime_ns() -> int:
    return time.clock_gettime_ns(time.CLOCK_BOOTTIME)


def positive_rate(raw: str) -> float:
    value = float(raw)
    if not math.isfinite(value) or value <= 0 or not math.isfinite(1e9 / value) or 1e9 / value < 1:
        raise argparse.ArgumentTypeError("Rate muss endlich, positiv und als Nanosekundenintervall darstellbar sein")
    return value


def positive_count(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("Anzahl muss positiv sein")
    return value


def protected_port(port: str) -> bool:
    """Auch symlink-/by-id-Aliasse der beiden reservierten Ports sperren."""
    path = Path(port)
    return any(path == Path(name) or path.resolve() == Path(name).resolve() for name in PROTECTED_PORTS)


WRITE_TIMEOUT_S = 1.0


def send_frame(transport, payload: bytes) -> tuple[str | None, int]:
    """Bei Stau nur das neue Telegramm auslassen; begonnene Bytes erhalten."""
    if transport.out_waiting:
        return 'output_backlog', 0
    return None, write_complete(transport, payload, WRITE_TIMEOUT_S)


def run_demo(transport, output: TextIO, formatter: UserDefinedFormatter, *,
             profile: str, rate: float, count: int, baudrate: int) -> int:
    interval_ns = math.ceil(1e9 / rate)
    next_send_ns = boottime_ns()
    for sequence in range(1, count + 1):
        while (remaining_ns := next_send_ns - boottime_ns()) > 0:
            sleep(remaining_ns / 1e9)
        text = PROFILES[profile][(sequence - 1) % len(PROFILES[profile])]
        record = ValueRecord(
            frame_sequence=sequence, capture_timestamp=Timestamp(sequence, TimeBaseKind.SYNTHETIC),
            value=float(text), unit=None, status=ValueStatus.VALID, confidence=1.0,
            profile_id=f"demo/{profile}", trigger_sequence=None, result_timestamp=None, raw_text=text,
        )
        payload = formatter.format(record)
        if payload is None:
            raise RuntimeError("Demo-Profil vom Formatter abgelehnt")
        t_send = boottime_ns()
        entry = {
            "sequence": sequence, "t_send_boottime_ns": t_send, "send_time_base": "CLOCK_BOOTTIME",
            "bytes_hex": payload.hex(), "value_text": text, "demo": True,
            "capture_time_base": record.capture_timestamp.base.value,
            "capture_timestamp": record.capture_timestamp.to_dict(),
            "format_id": formatter.capabilities.format_id, "provisional": formatter.capabilities.provisional,
            "profile": profile, "prefix": formatter.prefix, "baudrate": baudrate, "rate_hz": rate,
            "status": "dry_run" if transport is None else "sent", "bytes_written": 0,
        }
        fatal_error = None
        if transport is not None:
            try:
                reason, written = send_frame(transport, payload)
                entry["bytes_written"] = written
                if reason:
                    entry.update(status="dropped", drop_reason=reason)
            except (serial.SerialException, OSError) as exc:
                # Portausfall wird einmal belegt und beendet den Lauf, kein Wiederverbinden.
                fatal_error = f"{type(exc).__name__}: {exc}"
                entry.update(status="dropped", drop_reason="serial_error", error=fatal_error,
                             bytes_written=exc.bytes_written if isinstance(exc, SerialWriteError) else None)
        output.write(json.dumps(entry, ensure_ascii=True) + "\n")
        output.flush()
        if fatal_error:
            print(fatal_error, file=sys.stderr)
            return 1
        # Frist immer ab jetzt: Schreib-/Auditstau erzeugt keinen Aufholburst.
        next_send_ns = boottime_ns() + interval_ns
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Ausgangsport, kein Standard")
    parser.add_argument("--allow-port", action="store_true", help="Reservierten Referenz-/Debugport ausdrücklich erlauben")
    parser.add_argument("--profile", choices=PROFILES, default="constant")
    parser.add_argument("--rate", type=positive_rate, default=10.0, help="Demo-Frames/s (Standard: 10)")
    parser.add_argument("--count", type=positive_count, default=600)
    parser.add_argument("--baud", type=int, choices=BAUDRATES, default=115200)
    parser.add_argument("--prefix", default="%")
    parser.add_argument("--output", "--jsonl", default="-", help="JSONL-Datei; Standard - = stdout")
    parser.add_argument("--dry-run", action="store_true", help="Nur JSONL erzeugen, keinen Port öffnen")
    args = parser.parse_args(argv)
    try:
        formatter = UserDefinedFormatter(prefix=args.prefix)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.dry_run and not args.port:
        parser.error("--port ist ohne --dry-run erforderlich")
    if args.port and protected_port(args.port) and not args.allow_port:
        parser.error("Referenz-/Debugport gesperrt; nur ausdrücklich mit --allow-port")
    try:
        with ExitStack() as stack:
            output = sys.stdout if args.output == "-" else stack.enter_context(open(args.output, "x", encoding="utf-8"))
            transport = None
            if not args.dry_run:
                transport = serial.Serial(
                    args.port, baudrate=args.baud, bytesize=8, parity="N", stopbits=1,
                    timeout=0, write_timeout=WRITE_TIMEOUT_S, xonxoff=False, rtscts=False, dsrdtr=False,
                )
                stack.callback(transport.close)
            return run_demo(transport, output, formatter, profile=args.profile, rate=args.rate,
                            count=args.count, baudrate=args.baud)
    except (OSError, serial.SerialException) as exc:
        print(f"Demo-Sender: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
