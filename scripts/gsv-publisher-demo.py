#!/usr/bin/env python3
"""Finite synthetic Pi source for the shared TCP/UART Windows bridge."""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

from dispread.gsv_bridge import demo_records
from dispread.gsv_transport import OutputConfig, OutputPublisher
from dispread.hardware_ports import GSV_UART_PORT
from dispread.sink.jsonl import JsonlSink


def main(argv=None):
    parser = argparse.ArgumentParser(description="Synthetischer Pi-Demostrom; keine DUT-Messung und keine Zeitaussage.")
    parser.add_argument("--transport", choices=("tcp", "uart"), required=True)
    parser.add_argument("--tcp-host", default="0.0.0.0", help="Lokale Pi-Bind-Adresse")
    parser.add_argument("--tcp-port", type=int, default=5000)
    parser.add_argument("--serial-port", default=GSV_UART_PORT)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, default=600)
    parser.add_argument("--rate-hz", type=float, default=10)
    parser.add_argument("--connect-timeout", type=float, default=30)
    args = parser.parse_args(argv)
    if not (1 <= args.count <= 100000 and math.isfinite(args.rate_hz) and 0 < args.rate_hz <= 100
            and math.isfinite(args.connect_timeout) and 0 < args.connect_timeout <= 300):
        parser.error("ungültige Anzahl/Rate/Verbindungsfrist")
    try:
        config = OutputConfig(transport=args.transport, serial_port=args.serial_port,
                              tcp_host=args.tcp_host, tcp_port=args.tcp_port)
    except ValueError as exc:
        parser.error(str(exc))
    # Exclusive directory: never overwrite an earlier experiment's evidence.
    args.out_dir.mkdir(parents=True, exist_ok=False)
    publisher = OutputPublisher(config, args.out_dir, demo=True)
    audit = JsonlSink(args.out_dir / "records.jsonl", max_bytes=0)
    meta = {"demo": True, "provisional": True, "time_claim": False,
            "output": publisher.metadata(), "count_requested": args.count,
            "completed": 0, "end_reason": "starting"}

    def save():
        (args.out_dir / "session.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    result = 1
    try:
        save()
        audit.open()
        publisher.start()
        deadline = time.monotonic() + args.connect_timeout
        while publisher.status()["state"] != "bridge_connected":
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Brücke nicht verbunden: {publisher.status()}")
            time.sleep(.02)
        meta["end_reason"] = "running"
        save()
        for record in demo_records(args.count):
            emitted = time.monotonic()
            receipt = audit.emit(record)
            if receipt.t_complete_ns is None or audit.health().errors:
                raise OSError("Demo-Audit konnte nicht geschrieben werden")
            publisher.publish(record)
            deadline = time.monotonic() + args.connect_timeout
            while True:
                ack = publisher.status()["last_ack"]
                if ack is not None and ack["frame_sequence"] == record.frame_sequence:
                    if ack["outcome"] != "written":
                        raise OSError(f"Demowert nicht weitergegeben: {ack}")
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError("COM-Schreibbestätigung fehlt; kein Weiterzählen")
                time.sleep(.01)
            meta["completed"] += 1
            time.sleep(max(0, 1 / args.rate_hz - (time.monotonic() - emitted)))
        meta["end_reason"] = "completed"
        result = 0
    except KeyboardInterrupt:
        meta["end_reason"] = "interrupted"
        result = 130
    except (OSError, ValueError) as exc:
        meta["end_reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        cleanup_errors = []
        try:
            publisher.stop()
        except OSError as exc:
            cleanup_errors.append(f"publisher.stop: {exc}")
        finally:
            try:
                audit.close()
            except OSError as exc:
                cleanup_errors.append(f"audit.close: {exc}")
            finally:
                meta["output_status"] = publisher.status()
                if cleanup_errors:
                    meta["cleanup_errors"] = cleanup_errors
                    if result == 0:
                        meta["end_reason"] = "cleanup_failed"
                    result = result or 1
                try:
                    save()
                except OSError as exc:
                    print(f"Abschlussbericht nicht gespeichert: {exc}", file=sys.stderr)
                    result = result or 1
    print(json.dumps({"demo": True, "completed": meta["completed"], "end_reason": meta["end_reason"]}))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
