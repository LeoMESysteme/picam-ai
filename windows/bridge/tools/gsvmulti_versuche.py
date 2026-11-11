#!/usr/bin/env python3
"""GSVmulti-Versuche zu Lücken und Fehlwerten bei UserDefined (OQ-51), nur Testdaten.

Schreibt fest getaktete Testtelegramme auf einen COM-Port (z. B. COM7 des
com0com-Paars; GSVmulti hört auf COM8). Kein Pi, keine Brücke, keine Messwerte:
alle Werte sind erfunden und dienen nur dazu, das Aufnahmeverhalten von
GSVmulti zu beobachten. Der Platzhalter 0 im Lücken-Versuch ist nur hier
erlaubt, im Messpfad nie.

Jedes gesendete Telegramm wird als JSON-Zeile protokolliert (Tick, Sollzeit,
Istzeit, Telegramm), damit sich die GSVmulti-Aufnahme Zeile für Zeile
vergleichen lässt.

Aufruf (Windows, im Ordner windows\\bridge):
    py -3.13 -m pip install pyserial
    py -3.13 tools\\gsvmulti_versuche.py --port COM7 --versuch 1
    py -3.13 tools\\gsvmulti_versuche.py --versuch 3 --dry-run   (nur anzeigen)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass

RATE_HZ = 10.0
MARKER = ("1E+300", "1e300", "+1.0E+300", "99999999.0", "NaN", "+NaN", "Inf")


@dataclass(frozen=True)
class Tick:
    """Ein Sendeschritt: Telegrammtext ohne Präfix/Zeilenende, oder Pause."""

    text: str | None  # None = in diesem Tick nichts senden (Pause)
    note: str


def _wert(i: int) -> str:
    # Langsame Treppe 0.50000 .. 0.50999, gut im Plot erkennbar, nie 0.
    return f"{0.5 + (i % 1000) / 100000:.5f}"


def _vierkanal(wert: str, gueltig: int, seq: int, zeit: float) -> str:
    return f"{wert};{gueltig};{seq};{zeit:.6f}"


def versuch(nummer: int, clock=time.time) -> Iterator[Tick]:
    """Erzeugt die Ticks eines Versuchs; Zeitkanal = Uhrzeit beim Erzeugen."""
    seq = 0

    def gueltig(n, note):
        nonlocal seq
        for _ in range(n):
            seq += 1
            yield Tick(_vierkanal(_wert(seq), 1, seq, clock()), note)

    def ungueltig(n, note):
        nonlocal seq
        for _ in range(n):
            seq += 1
            yield Tick(_vierkanal("0", 0, seq, clock()), note)

    def pause(sekunden, note):
        for _ in range(round(sekunden * RATE_HZ)):
            yield Tick(None, note)

    if nummer == 1:  # Vierkanal-Frame wird angenommen
        yield from gueltig(600, "gueltig")
    elif nummer == 2:  # fester Takt erhält eine Lücke
        yield from gueltig(100, "gueltig")
        yield from ungueltig(50, "ungueltig")
        yield from gueltig(100, "gueltig")
    elif nummer == 3:  # Marker im Wertkanal (einkanalig)
        for marker in MARKER:
            for _ in range(50):
                yield Tick("0.5", "gueltig")
            for _ in range(50):
                yield Tick(marker, f"marker {marker}")
        for _ in range(50):
            yield Tick("0.5", "gueltig")
    elif nummer == 4:  # Start/Ende der Aufnahme per Schwelle auf Kanal 2
        yield from ungueltig(50, "vorlauf ungueltig")
        yield from gueltig(600, "gueltig")
        yield from ungueltig(50, "nachlauf ungueltig")
    elif nummer == 5:  # Pausen ohne Bytes
        yield from gueltig(100, "gueltig")
        for sekunden in (2, 4, 8, 30):
            yield from pause(sekunden, f"pause {sekunden} s")
            yield from gueltig(100, "gueltig")
    else:
        raise ValueError("Versuch 1 bis 5")


def senden(ticks, port, *, prefix="%", rate_hz=RATE_HZ, log=sys.stdout, monotonic=time.monotonic,
           sleep=time.sleep, wall=time.time):
    """Fester Takt ohne Aufholen: ein verspäteter Tick wird gesendet und als spät markiert."""
    periode = 1.0 / rate_hz
    start = monotonic()
    for i, tick in enumerate(ticks):
        soll = start + i * periode
        warten = soll - monotonic()
        if warten > 0:
            sleep(warten)
        ist = monotonic()
        eintrag = {"tick": i, "soll_s": round(soll - start, 4), "ist_s": round(ist - start, 4),
                   "spaet_ms": round(max(0.0, ist - soll) * 1000, 1), "uhrzeit": wall(), "note": tick.note}
        if tick.text is not None:
            telegramm = f"{prefix}{tick.text}\r\n".encode("ascii")
            if port is not None:
                geschrieben = port.write(telegramm)
                if geschrieben != len(telegramm):
                    raise OSError(f"unvollständig geschrieben: {geschrieben}/{len(telegramm)}")
            eintrag["telegramm"] = telegramm.decode("ascii").rstrip("\r\n")
        log.write(json.dumps(eintrag) + "\n")
        log.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--versuch", type=int, choices=range(1, 6), required=True)
    parser.add_argument("--port", help="z. B. COM7 (Brückenseite des com0com-Paars)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--log", default=None, help="JSONL-Protokoll (Standard: versuch-<n>-<zeit>.jsonl)")
    parser.add_argument("--dry-run", action="store_true", help="nichts senden, nur protokollieren (sofort, ohne Takt)")
    args = parser.parse_args(argv)
    if not args.dry_run and not args.port:
        parser.error("--port fehlt (oder --dry-run)")
    name = args.log or f"versuch-{args.versuch}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    with open(name, "w", encoding="utf-8") as log:
        if args.dry_run:
            senden(versuch(args.versuch), None, log=log, sleep=lambda s: None)
        else:
            import serial  # pyserial, nur für echtes Senden nötig

            with serial.Serial(args.port, args.baud, bytesize=8, parity="N", stopbits=1, write_timeout=1) as port:
                print(f"Versuch {args.versuch}: sende auf {args.port} mit {RATE_HZ:g} Hz, Protokoll {name}")
                senden(versuch(args.versuch), port, log=log)
    spaet = [json.loads(z) for z in open(name, encoding="utf-8")]
    gesendet = sum("telegramm" in e for e in spaet)
    max_spaet = max((e["spaet_ms"] for e in spaet), default=0)
    print(f"fertig: {gesendet} Telegramme, {len(spaet)} Ticks, größte Verspätung {max_spaet} ms, Protokoll {name}")


if __name__ == "__main__":
    main()
