#!/usr/bin/env python3
"""Registerstand eines GSV-2 auslesen und als Rueckstellpunkt sichern.

Zweck: **bevor** irgendetwas am Geraet veraendert wird, den Ist-Zustand
festhalten. Das Skript sendet ausschliesslich Lesebefehle plus die beiden
Befehle, die den Messwertstrom anhalten und wieder starten - **keinen
einzigen Schreibbefehl auf ein Konfigurationsregister**.

Zwei Fallstricke aus der Anleitung sind hier eingebaut, weil sie in der
vorigen Sitzung von Hand fast zu einer Fehlkonfiguration gefuehrt haben:

1. **Das Semikolon-Praefix.** Registerwerte kommen als ``; <HByte> [...]``.
   Die Spalte "Laenge der Befehlsantwort" der Anleitung zaehlt nur die
   Datenbytes. Wer ein Byte liest, haelt ``0x3B`` fuer den Registerwert.
   Dieses Skript liest ``1 + n`` Bytes und **prueft** das Praefix.
2. **``start transmission`` gehoert in dieselbe offene Sitzung.** Wird der
   Port vorher geschlossen, bleibt der Strom still. Der Neustart passiert
   hier im ``finally``-Block und wird anschliessend **verifiziert**, indem
   auf tatsaechlich eintreffende Daten gewartet wird.

Aufruf::

    ./.venv/bin/python scripts/gsv-registers.py --out var/diagnostics/gsv-register-<stamp>.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from dispread.gsv2as_serial import (
    CMD_CLEAR,
    CMD_START,
    CMD_STOP,
    READ_COMMANDS,
    SEMICOLON,
    _read_exact,
    read_register,
)

__all__ = ["READ_COMMANDS", "SEMICOLON", "_read_exact", "read_register"]

#: Einheitencodes, soweit in der Anleitung tabelliert (Auszug).
UNIT_NAMES = {0: "mV/V", 1: "kg", 2: "g", 3: "N", 31: "Pa", 32: "hPa", 33: "MPa", 34: "N/mm2"}


def decode_norm(raw: list[int], dpoint: int | None) -> dict:
    """Normierungsfaktor aus den drei Rohbytes zurueckrechnen.

    Umkehrung der Vorschrift aus der Anleitung (set norm, Befehl 16): der
    gewuenschte Wert wird durch ``10**dp`` geteilt, mit 5250020 multipliziert
    und als 3 Bytes uebertragen; ``dpoint`` ist ``dp + 1``.

    **Abgeleitet, nicht gemessen.** Die Rueckrechnung gilt erst als
    bestaetigt, wenn sie gegen die tatsaechliche Anzeige geprueft wurde.
    """
    value = (raw[0] << 16) | (raw[1] << 8) | raw[2]
    negative = bool(value & 0x800000)
    mantissa = value & 0x7FFFFF
    out: dict = {"raw_bytes": raw, "raw_int": value, "negative_bit": negative, "mantissa": mantissa}
    scaled = mantissa / 5250020
    out["mantissa_scaled"] = scaled
    if dpoint is not None:
        norm = scaled * (10 ** (dpoint - 1))
        out["norm_abgeleitet"] = -norm if negative else norm
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", default="/dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=38400)
    parser.add_argument("--out", type=Path, required=True, help="Zieldatei fuer den Rueckstellpunkt (JSON)")
    args = parser.parse_args()

    import serial

    result: dict = {
        "gelesen_am_utc": datetime.now(UTC).isoformat(),
        "port": args.port,
        "baudrate": args.baudrate,
        "hinweis": "Nur Lesebefehle. Keine Konfiguration veraendert.",
        "register": {},
    }

    ser = serial.Serial(
        args.port, args.baudrate, bytesize=8, parity="N", stopbits=1,
        timeout=0.2, rtscts=False, dsrdtr=False, xonxoff=False,
    )
    try:
        # Strom anhalten, damit Messwerte nicht in die Registerantworten laufen.
        ser.write(bytes([CMD_STOP]))
        ser.flush()
        time.sleep(0.3)
        ser.write(bytes([CMD_CLEAR]))
        ser.flush()
        time.sleep(0.2)
        ser.reset_input_buffer()

        for name, (command, data_len) in READ_COMMANDS.items():
            result["register"][name] = read_register(ser, name, command, data_len)
            time.sleep(0.08)

        # Abgeleitete Groessen - ausdruecklich als abgeleitet gekennzeichnet.
        reg = result["register"]
        dpoint = reg.get("dpoint", {}).get("daten", [None])[0]
        if "daten" in reg.get("norm", {}):
            result["norm_rueckgerechnet"] = decode_norm(reg["norm"]["daten"], dpoint)
        if "daten" in reg.get("unit", {}):
            code = reg["unit"]["daten"][0]
            result["einheit_abgeleitet"] = UNIT_NAMES.get(code, f"unbekannter Code {code}")
        if "daten" in reg.get("firmware", {}):
            fw = reg["firmware"]["daten"]
            result["firmware_abgeleitet"] = f"{fw[0]}.{fw[1]}"
    finally:
        # Immer wieder anwerfen, und zwar in DIESER Sitzung.
        ser.write(bytes([CMD_START]))
        ser.flush()
        time.sleep(0.8)
        wieder_da = _read_exact(ser, 8, timeout_s=3.0)
        result["strom_nach_neustart"] = {
            "bytes_erhalten": len(wieder_da),
            "auszug": wieder_da.decode("ascii", "replace"),
            "laeuft_wieder": len(wieder_da) > 0,
        }
        ser.close()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["strom_nach_neustart"]["laeuft_wieder"]:
        print("\nWARNUNG: nach 'start transmission' kamen keine Daten. "
              "Der Messwertstrom steht moeglicherweise still.", file=sys.stderr)
        return 1
    print(f"\nRueckstellpunkt gesichert: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
