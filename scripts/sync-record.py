#!/usr/bin/env python3
"""Kamerabilder und den seriellen GSV-Strom derselben Sitzung gemeinsam
aufzeichnen - Task E aus
docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md.

Aufruf (ohne Hardware, vollstaendig testbar):

    ./.venv/bin/python scripts/sync-record.py --duration 30 \\
        --output var/diagnostics/lauf1

Aufruf mit echter Kamera + echtem Port (NICHT von hier aus ausgefuehrt -
siehe unten):

    ./.venv/bin/python scripts/sync-record.py --duration 60 --source camera \\
        --camera-settings var/calibration/streamcam-settings.json \\
        --port /dev/ttyUSB0 --baudrate 38400

Zweck: um den Ende-zu-Ende-Versatz zwischen dem seriellen Telegramm des
GSV-2AS und dem, was die Kamera auf dem LC-Display sieht, zu messen (Task B
desselben Plans), braucht es eine gemeinsame Aufzeichnung beider Stroeme mit
Zeitstempeln in DERSELBEN Zeitdomaene (CLOCK_BOOTTIME). Aufzeichnen und
Auswerten sind bewusst getrennt: dieses Skript zeichnet nur auf, labelt
nichts und legt keine Datensatzproben an. Dieselbe Aufzeichnung laesst sich
so spaeter mit einem anderen Schutzintervall (M) erneut auswerten, ohne neu
messen zu muessen.

Reiner Diagnosecode, kein Produktionspfad - Stil und Argumentbehandlung an
`dataset-benchmark.py` angelehnt.

**Nur lesen.** An den seriellen Port wird kein einziges Byte gesendet -
weder ein Handshake-Signal (kein RTS/CTS, DSR/DTR, XON/XOFF) noch ein
Kommando. `SerialSink` (`src/dispread/sink/serial_out.py`) ist die einzige
Stelle im Repo, die auf diesen Port schreiben darf, und das ist nicht dieses
Skript.

Kamera: Logitech StreamCam ueber `UvcSource` (seit 2026-09-25, IMX500 ausser
Betrieb, siehe docs/project_history.md). Frames tragen ihren Zeitstempel roh
in `TimeBaseKind.V4L2_MONOTONIC` (CLOCK_MONOTONIC-Domaene der uvcvideo-
Puffer) - die Umrechnung nach CLOCK_BOOTTIME laeuft ausschliesslich ueber
`dispread.records.to_boottime_ns` mit dem in `session.json` gemessenen
Versatz (`clock_offset_boottime_minus_monotonic_ns`, Median aus mehreren eng
geklammerten Messungen, siehe `measure_clock_offset_ns`), nie hier direkt.
Ein Zeitstempel ohne benannte Zeitbasis ist nach AGENTS.md keine verwertbare
Angabe.

Betriebshinweis (`--source camera`): Die Kamera kann nur EIN Prozess halten -
vor dem Start pruefen, ob ein `dispread serve` laeuft.

Robustheit:
  - Serielles Lesen laeuft in einem eigenen Thread, damit eine 66-ms-Bildauf-
    nahme kein Telegramm verschluckt.
  - Ctrl-C hinterlaesst vollstaendige, gueltige Dateien: beide JSONL-Dateien
    werden zeilenweise geflusht, und `session.json` wird auch im
    Abbruchfall geschrieben (mit `"aborted": true`).
  - Kommt ueber die ganze Dauer kein einziges Telegramm an, wird das am Ende
    laut gemeldet statt stillschweigend eine leere `serial.jsonl` zu
    hinterlassen.

## Erzeugen und Schreiben sind getrennte Threads (seit OQ-40-Nachtrag 2026-09-23)

Root-Cause-Messung vom 2026-09-23 (Aufzeichnung
`var/diagnostics/stall-105143` + ein unabhaengiger, I/O-loser Herzschlag-
prozess parallel): die Bildluecken (333/933/533/333 ms) UND der serielle
Burst fielen zeitlich mit Kernel-Dirty-Page-Writeback auf die SD-Karte
zusammen (bis 130 MB Writeback beobachtet). Der Herzschlagprozess selbst
zeigte KEINE Luecke - das System stand nicht still, nur die Dateischreiber
blockierten. Sowohl die Bildschleife (`cv2.imwrite`) als auch der serielle
Thread (`serial.jsonl`-Schreiben) blockierten im Dateisystemzugriff; der
serielle Thread rief dadurch `readline()` zu spaet auf und stempelte
laengst angekommene, gepufferte Zeilen zu spaet - das erzeugte den Burst.

Deshalb ist die Erzeugung (Kamera-`capture_request`/`synthetic`-Generator
bzw. `ser.readline()`) jetzt strikt von der Schreibseite (JPEG-Kodierung +
`frames.jsonl`, `serial.jsonl`) getrennt - je ein eigener Thread, verbunden
ueber `queue.Queue`:

  - `frame_queue` ist BEGRENZT (`--frame-queue-size`, Vorgabe 60 Bilder,
    bei 15 fps rund 4 s) - Bilder sind gross, ein unbegrenzter Puffer wuerde
    bei einem laengeren Schreibstau den Speicher aufbrauchen. Ist sie voll,
    wird das Bild verworfen und GEZAEHLT (`frames_dropped_queue_full` in
    `session.json`), nie still - dazu je ein `frames.jsonl`-Eintrag
    `{"dropped": true, "sensor_sequence": ..., "capture_timestamp": ...}`
    ueber eine eigene, unbegrenzte Meldungs-Warteschlange (Nutzdaten winzig).
    Die Aufnahmeseite blockiert dafuer NIE am `frame_queue.put(...)`.
  - `serial_queue` ist UNBEGRENZT wie die Drop-Meldungen - Telegrammzeilen
    sind winzig, ein Rueckstau kostet nur etwas RAM, nie eine verpasste
    Zeile.
  - Die Taktung (`--frame-rate`) bleibt im Erzeugerthread (regelt, wie
    schnell der naechste Frame angefordert wird), nicht im Schreiberthread -
    ein langsamer Schreiber darf die Aufnahmetaktung nie veraendern.
  - Bei Beendigung (Dauer erreicht, Ctrl-C, SIGTERM) werden beide
    Warteschlangen vollstaendig GELEERT, bevor `session.json` geschrieben
    wird - kein Bild/Telegramm, das schon in der Warteschlange steht, geht
    beim Abbruch verloren.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import queue
import signal
import sys
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2

from dispread.camera_settings import CameraSettings, load_camera_settings
from dispread.frames import open_source
from dispread.frames.uvc_source import UvcError, UvcSource

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUTPUT_ROOT = Path("var/diagnostics")
DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUDRATE = 38400
DEFAULT_SYNTHETIC_URI = "synthetic://seven-seg"
SERIAL_READ_TIMEOUT_S = 0.5
#: Grosszuegig bemessen: mit --norm-schedule laeuft im finally-Block des
#: Lesethreads noch die Rueckstellung (Strom anhalten, zwei Register
#: schreiben+pruefen, wieder anhalten, zwei Register lesen, Strom neu starten -
#: mehrere Sleeps von 0,15-0,8 s), bevor der Thread sich beendet.
JOIN_TIMEOUT_S = 20.0
#: Registerlesen + Schreibsequenz kann vor dem ersten Telegramm laufen
#: (--norm-schedule) - grosszuegiger bemessen als das reine Portoeffnen.
READY_TIMEOUT_S = 15.0
#: Bilder sind gross (im Gegensatz zu Telegrammzeilen) - ein unbegrenzter
#: Puffer wuerde bei einem laengeren Schreibstau den Speicher aufbrauchen.
#: 60 bei 15 fps sind rund 4 s Reserve, siehe Moduldocstring.
DEFAULT_FRAME_QUEUE_SIZE = 60
#: Wie lange der Schreiberthread beim Leeren wartet, bevor er nach dem
#: Ende-Signal (`_QUEUE_DONE`) der Erzeugerseite selbst aufgibt.
WRITER_DRAIN_JOIN_TIMEOUT_S = 30.0

#: Bewusst grosszuegig: ein einzelner `capture.read()`-Fehlschlag der
#: StreamCam darf keinen Abbruch ausloesen, siehe `UvcSource.frames()`
#: (`READ_FAIL_TIMEOUT_S`) - dieser Guard deckt nur das ERSTE Bild ab, das
#: `_camera_startup_guard` mit einer eigenen Zeitschranke abwartet.
STARTUP_TIMEOUT_S = 5.0

#: Exitcode, wenn der Kamerazweig ohne ein einziges Bild endet (Timeout beim
#: ersten Bild, ein `UvcError` beim Oeffnen oder frames_recorded == 0 am
#: Ende) - ungleich 0, damit ein Aufrufer (z.B. harvest.py) das nicht mit
#: einem erfolgreichen Lauf verwechselt.
EXIT_NO_FRAMES_ACQUIRED = 4

#: Anzahl Einzelmessungen fuer `measure_clock_offset_ns` (Median).
CLOCK_OFFSET_SAMPLES = 5

#: Sentinel: die Erzeugerseite (Kamera-/Serial-Thread) ist fertig, keine
#: weiteren Eintraege kommen mehr - der Schreiberthread leert die
#: Warteschlange bis hierher und beendet sich dann selbst. Eine eigene
#: Objektidentitaet statt z.B. `None`, damit sie sich nie mit einem echten
#: (leeren) Nutzlast-Eintrag verwechseln laesst.
_QUEUE_DONE = object()

DEFAULT_RESTORE_POINT = REPO_ROOT / "var/diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json"

#: Erlaubter Normierungsbereich des GSV-2AS, siehe CLAUDE.md ("Hardware-Fakten") -
#: 0,15...1 580 000. Nur zur Validierung von --norm-schedule, keine eigene Messung.
NORM_MIN, NORM_MAX = 0.15, 1_580_000.0


def _load_gsv_registers_module():
    """`scripts/gsv-registers.py` als Modul laden statt seine Byte-Kodierung
    neu zu schreiben (Registerkonstanten, Semikolon-Praefix-Pruefung,
    `read_register`). Reiner Funktions-/Konstantenimport - die Datei fuehrt
    beim Laden keinen I/O aus, nur unter `if __name__ == "__main__"`."""
    path = Path(__file__).resolve().with_name("gsv-registers.py")
    spec = importlib.util.spec_from_file_location("_dispread_gsv_registers", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_gsv_registers = _load_gsv_registers_module()

#: `set norm` (16) / `set dpoint` (17) aus der GSV-2-Anleitung, siehe
#: CLAUDE.md. `_gsv_registers` liefert nur die Lesebefehle; STOP/CLEAR/START
#: und LAST_ERR kommen von dort (identische Werte in norm_sweep.py).
SET_NORM_CMD = 0x10
SET_DPOINT_CMD = 0x11
LAST_ERR_CMD = _gsv_registers.READ_COMMANDS["last_error"][0]
OK_ERROR_CODE = 0xA0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Zeichnet Kamerabilder und den seriellen GSV-Strom parallel auf, "
            "mit Zeitstempeln in CLOCK_BOOTTIME - fuer die photometrische "
            "Versatzmessung (Task B). Labelt nichts."
        )
    )
    parser.add_argument("--duration", type=float, required=True, help="Aufzeichnungsdauer in Sekunden")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Zielverzeichnis; Vorgabe: var/diagnostics/<Zeitstempel> (ausserhalb des Repos zu waehlen)",
    )
    parser.add_argument("--source", choices=["synthetic", "camera"], default="synthetic")
    parser.add_argument(
        "--synthetic-uri",
        default=DEFAULT_SYNTHETIC_URI,
        help="URI fuer --source synthetic, siehe dispread.frames.open_source",
    )
    parser.add_argument(
        "--frame-rate",
        type=float,
        default=15.0,
        help=(
            "Zieltakt der Bildaufnahme in Hz (0 = so schnell wie moeglich). Nur "
            "--source synthetic wird davon tatsaechlich gebremst; bei --source "
            "camera laeuft die StreamCam mit dem Takt aus --camera-settings "
            "(settings.fps) - dieser Wert drosselt dort nur, wie viele der "
            "gelieferten Bilder geschrieben werden."
        ),
    )
    parser.add_argument("--port", default=DEFAULT_PORT, help="Serieller Port, nur gelesen")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--image-format", choices=["png", "jpg"], default="png")
    parser.add_argument(
        "--frame-queue-size",
        type=int,
        default=DEFAULT_FRAME_QUEUE_SIZE,
        help=(
            "Kapazitaet der Warteschlange zwischen Bildaufnahme und Schreiber "
            f"(JPEG-Kodierung + frames.jsonl); Vorgabe {DEFAULT_FRAME_QUEUE_SIZE} "
            "Bilder. Bei Ueberlauf wird das Bild verworfen und gezaehlt statt die "
            "Aufnahme zu blockieren, siehe Moduldocstring 'Erzeugen und Schreiben "
            "sind getrennte Threads'."
        ),
    )
    parser.add_argument(
        "--camera-settings",
        type=Path,
        default=None,
        help=(
            "Nur --source camera, dann Pflicht: Pfad zu einer JSON-Datei mit "
            "Top-Level-Schluessel 'camera' (Profil oder Ausgabe von "
            "harvest-setup focus), siehe dispread.camera_settings."
            "load_camera_settings. Legt fest, was UvcSource an der StreamCam "
            "einstellt (Aufloesung, FourCC, fps, Regler)."
        ),
    )
    parser.add_argument(
        "--camera-device",
        type=Path,
        default=None,
        help=(
            "Nur --source camera: '/dev/videoN' direkt vorgeben statt ueber die "
            "USB-ID (settings.usb_id) zu suchen (UvcSource.open())."
        ),
    )
    parser.add_argument(
        "--norm-schedule",
        default=None,
        help=(
            "Ablaufplan fuer den GSV-Normierungsfaktor, 'Faktor:Haltesekunden,...', "
            "z.B. '1.0:5,2.0:5,1.0:5'. Erzeugt waehrend der Aufzeichnung grosse "
            "Anzeigespruenge ueber Register 16 ('set norm')/17 ('set dpoint') - "
            "geschrieben INNERHALB der bereits offenen seriellen Sitzung dieses "
            "Skripts, siehe var/diagnostics/gsv-serial-2026-09-22/norm_sweep.py. "
            "Jeder Befehl inkl. Antwort landet in commands.jsonl. Ohne diese Option "
            "wird kein einziges Byte an den Port gesendet (Verhalten unveraendert)."
        ),
    )
    parser.add_argument(
        "--restore-point",
        type=Path,
        default=DEFAULT_RESTORE_POINT,
        help=(
            "Rueckstellpunkt-JSON (siehe scripts/gsv-registers.py --out), nur mit "
            f"--norm-schedule relevant. Vorgabe: {DEFAULT_RESTORE_POINT}"
        ),
    )
    parser.add_argument(
        "--ignore-restore-point-mismatch",
        action="store_true",
        help=(
            "Start trotz abweichendem Registerstand erzwingen (nur mit "
            "--norm-schedule). Ohne diese Option ist ein abweichender "
            "Ausgangszustand ein harter Abbruch vor jedem Schreibzugriff."
        ),
    )
    args = parser.parse_args(argv)
    if args.source == "camera" and args.camera_settings is None:
        parser.error("--camera-settings ist bei --source camera Pflicht")
    if args.frame_queue_size < 1:
        parser.error("--frame-queue-size muss mindestens 1 sein")
    if args.ignore_restore_point_mismatch and not args.norm_schedule:
        parser.error("--ignore-restore-point-mismatch ergibt nur mit --norm-schedule einen Sinn")
    if args.norm_schedule is not None:
        try:
            args.norm_schedule = _parse_norm_schedule(args.norm_schedule)
        except ValueError as exc:
            parser.error(str(exc))
    return args


def _parse_norm_schedule(raw: str) -> list[tuple[float, float]]:
    """'1.0:5,2.0:5,1.0:5' -> [(1.0, 5.0), (2.0, 5.0), (1.0, 5.0)]."""
    schedule: list[tuple[float, float]] = []
    for segment in raw.split(","):
        segment = segment.strip()
        if not segment:
            continue
        factor_str, sep, hold_str = segment.partition(":")
        if not sep:
            raise ValueError(f"--norm-schedule-Segment {segment!r} hat nicht die Form Faktor:Sekunden")
        try:
            factor = float(factor_str)
            hold_s = float(hold_str)
        except ValueError as exc:
            raise ValueError(f"--norm-schedule-Segment {segment!r} ist nicht numerisch: {exc}") from exc
        if not (NORM_MIN <= factor <= NORM_MAX):
            raise ValueError(
                f"--norm-schedule-Segment {segment!r}: Normierungsfaktor {factor} ausserhalb des "
                f"dokumentierten Bereichs {NORM_MIN}..{NORM_MAX} (CLAUDE.md)"
            )
        if hold_s <= 0:
            raise ValueError(f"--norm-schedule-Segment {segment!r}: Haltezeit muss > 0 Sekunden sein")
        schedule.append((factor, hold_s))
    if not schedule:
        raise ValueError("--norm-schedule ergab keine Eintraege")
    return schedule


def _encode_norm(norm: float) -> tuple[tuple[int, int, int], int]:
    """Portiert aus `norm_sweep.py::encode_norm` (Vorschrift aus der GSV-2-
    Anleitung, 'set norm', Befehl 16) - byteidentisch uebernommen, nicht neu
    hergeleitet."""
    dp = math.floor(math.log10(norm))
    scaled = norm / 10**dp
    if scaled > 1.6666 / 1.05:
        scaled /= 10
        dp += 1
    mant = round(scaled * 5250020)
    return (mant >> 16 & 0xFF, mant >> 8 & 0xFF, mant & 0xFF), dp + 1


def _send(ser, byte: int, sleep_s: float) -> None:
    """Ein einzelnes Kommandobyte schreiben, flushen, warten - wie die
    `ser.write(...); ser.flush(); time.sleep(...)`-Zeilen in norm_sweep.py,
    nur ohne die dort verwendeten Semikolon-Mehrfachanweisungen."""
    ser.write(bytes([byte]))
    ser.flush()
    time.sleep(sleep_s)


def _read_exact(ser, count: int, timeout_s: float = 1.0) -> bytes:
    """Wie `gsv-registers.py::_read_exact` / `norm_sweep.py::read_exact`."""
    deadline = time.monotonic() + timeout_s
    buf = b""
    while len(buf) < count and time.monotonic() < deadline:
        chunk = ser.read(count - len(buf))
        if chunk:
            buf += chunk
    return buf


# --- Norm-Schedule: Schreiben INNERHALB der bereits offenen seriellen Sitzung --
#
# Alle Funktionen hier bekommen das offene `serial.Serial`-Objekt des
# Lesethreads gereicht und werden auch nur von dort aufgerufen - es gibt nie
# eine zweite Verbindung zum Port, und nie einen zweiten Thread, der
# gleichzeitig liest/schreibt.


def _log_event(f_cmd, state: dict[str, Any], event: dict[str, Any]) -> None:
    event.setdefault("t_boot", time.clock_gettime(time.CLOCK_BOOTTIME))
    f_cmd.write(json.dumps(event, ensure_ascii=False) + "\n")
    f_cmd.flush()
    state["command_event_count"] = state.get("command_event_count", 0) + 1


def _read_norm_dpoint(ser, f_cmd, state, *, label: str) -> tuple[dict, dict]:
    """Liest die Register `norm` (0x1A) und `dpoint` (0x1C) ueber
    `gsv-registers.py::read_register` (prueft das Semikolon-Praefix). Beide
    Antworten sind keine Telegramme und werden nur hier geloggt, nie nach
    serial.jsonl geschrieben."""
    norm_cmd, norm_len = _gsv_registers.READ_COMMANDS["norm"]
    dpoint_cmd, dpoint_len = _gsv_registers.READ_COMMANDS["dpoint"]
    norm_entry = _gsv_registers.read_register(ser, "norm", norm_cmd, norm_len)
    _log_event(f_cmd, state, {"event": "register_read", "label": label, "register": "norm",
                               "response_tag": "non_telegram", **norm_entry})
    dpoint_entry = _gsv_registers.read_register(ser, "dpoint", dpoint_cmd, dpoint_len)
    _log_event(f_cmd, state, {"event": "register_read", "label": label, "register": "dpoint",
                               "response_tag": "non_telegram", **dpoint_entry})
    return norm_entry, dpoint_entry


def _pause_read_registers_resume(ser, f_cmd, state, *, label: str) -> tuple[dict, dict]:
    """Strom anhalten (STOP+CLEAR, wie `gsv-registers.py`), Register lesen,
    Strom wieder anwerfen (START). Pause- und Resume-Zeitpunkt werden je als
    eigenes Ereignis geloggt - das ist die einzige Stelle, an der der Strom
    fuer eine reine Lesekontrolle (Precheck, Rueckstellungspruefung)
    angehalten wird."""
    t_pause = time.clock_gettime(time.CLOCK_BOOTTIME)
    _send(ser, _gsv_registers.CMD_STOP, 0.3)
    _send(ser, _gsv_registers.CMD_CLEAR, 0.2)
    ser.reset_input_buffer()
    _log_event(f_cmd, state, {"event": "pause_transmission", "label": label, "t_boot": t_pause})

    norm_entry, dpoint_entry = _read_norm_dpoint(ser, f_cmd, state, label=label)

    _send(ser, _gsv_registers.CMD_START, 0.8)
    t_resume = time.clock_gettime(time.CLOCK_BOOTTIME)
    _log_event(f_cmd, state, {"event": "resume_transmission", "label": label, "t_boot": t_resume})
    return norm_entry, dpoint_entry


def _check_restore_point(ser, restore_point: dict, f_cmd, state, *, label: str) -> tuple[bool, dict]:
    norm_entry, dpoint_entry = _pause_read_registers_resume(ser, f_cmd, state, label=label)
    expected_norm = restore_point.get("register", {}).get("norm", {}).get("daten")
    expected_dpoint = restore_point.get("register", {}).get("dpoint", {}).get("daten")
    actual_norm = norm_entry.get("daten")
    actual_dpoint = dpoint_entry.get("daten")
    matches = actual_norm == expected_norm and actual_dpoint == expected_dpoint
    detail = {
        "matches_restore_point": matches,
        "expected_norm": expected_norm,
        "actual_norm": actual_norm,
        "expected_dpoint": expected_dpoint,
        "actual_dpoint": actual_dpoint,
    }
    return matches, detail


def _apply_norm_dpoint(ser, norm_bytes, dpoint_byte: int, f_cmd, state, *, label: str) -> bool:
    """Setzt Normierung + Dezimalpunkt. Reihenfolge byteidentisch zu
    `apply_cfg` in norm_sweep.py: Strom anhalten+leeren, `set norm` (0x10)
    schreiben, per `last error` (0x42) pruefen, `set dpoint` (0x11)
    schreiben, wieder pruefen, Strom neu starten. Jede Kommandoantwort ist
    keine Telegrammzeile - sie kommt aus einem direkten `ser.read()`, nie aus
    der `readline()`-Schleife, und wird deshalb nur nach commands.jsonl
    geschrieben, mit `response_tag: non_telegram`."""
    t_pause = time.clock_gettime(time.CLOCK_BOOTTIME)
    _send(ser, _gsv_registers.CMD_STOP, 0.25)
    _send(ser, _gsv_registers.CMD_CLEAR, 0.15)
    ser.reset_input_buffer()
    _log_event(f_cmd, state, {"event": "pause_transmission", "label": label, "t_boot": t_pause})

    ser.write(bytes([SET_NORM_CMD, *norm_bytes]))
    ser.flush()
    time.sleep(0.35)
    ser.reset_input_buffer()
    ser.write(bytes([LAST_ERR_CMD]))
    ser.flush()
    resp_norm = _read_exact(ser, 2)
    _log_event(f_cmd, state, {
        "event": "command", "label": label, "command_name": "set_norm",
        "command_bytes": [SET_NORM_CMD, *norm_bytes],
        "response_bytes": list(resp_norm), "response_tag": "non_telegram",
    })

    ser.write(bytes([SET_DPOINT_CMD, dpoint_byte]))
    ser.flush()
    time.sleep(0.35)
    ser.reset_input_buffer()
    ser.write(bytes([LAST_ERR_CMD]))
    ser.flush()
    resp_dpoint = _read_exact(ser, 2)
    _log_event(f_cmd, state, {
        "event": "command", "label": label, "command_name": "set_dpoint",
        "command_bytes": [SET_DPOINT_CMD, dpoint_byte],
        "response_bytes": list(resp_dpoint), "response_tag": "non_telegram",
    })

    _send(ser, _gsv_registers.CMD_START, 0.7)
    t_resume = time.clock_gettime(time.CLOCK_BOOTTIME)
    _log_event(f_cmd, state, {"event": "resume_transmission", "label": label, "t_boot": t_resume})

    ok_norm = len(resp_norm) == 2 and resp_norm[1] == OK_ERROR_CODE
    ok_dpoint = len(resp_dpoint) == 2 and resp_dpoint[1] == OK_ERROR_CODE
    return ok_norm and ok_dpoint


# --- Serieller Strom, eigener Thread, nur lesen -----------------------------


def _serial_worker(
    port: str,
    baudrate: int,
    serial_queue: queue.Queue[Any],
    stop_event: threading.Event,
    ready_event: threading.Event,
    state: dict[str, Any],
    *,
    commands_path: Path | None = None,
    norm_schedule: list[tuple[float, float]] | None = None,
    restore_point: dict | None = None,
    ignore_restore_point_mismatch: bool = False,
) -> None:
    """Liest zeilenweise, sendet nichts (ausser den bewusst dokumentierten
    `--norm-schedule`-Schreibbefehlen, siehe unten). Signalisiert
    `ready_event`, sobald der Port entweder offen ist oder das Oeffnen
    endgueltig fehlgeschlagen ist - der Aufrufer wartet darauf, bevor er die
    Bildaufnahme startet.

    Schreibt NIE selbst nach `serial.jsonl` - jede gelesene Zeile geht sofort
    auf `serial_queue` (Erzeuger/Schreiber-Trennung, siehe Moduldocstring).
    Ein eigener Schreiberthread (`_serial_writer_worker`) leert die
    Warteschlange; nur so bleibt `ser.readline()` frei von Dateisystem-
    Wartezeit, die frueher (OQ-40-Nachtrag 2026-09-23) genau hier den
    beobachteten Burst erzeugt hat. Legt auf JEDEM Ausstiegspfad genau einmal
    `_QUEUE_DONE` auf `serial_queue`, damit der Schreiberthread sich sicher
    beenden kann, auch wenn der Port nie geoeffnet werden konnte."""
    import serial

    ser = None
    f_cmd = None
    try:
        try:
            ser = serial.Serial(
                port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=SERIAL_READ_TIMEOUT_S,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
        except Exception as exc:  # noqa: BLE001 - an den Aufrufer weiterreichen
            state["open_error"] = f"{type(exc).__name__}: {exc}"
            ready_event.set()
            return

        state["open_error"] = None

        if norm_schedule is not None:
            assert commands_path is not None and restore_point is not None
            f_cmd = open(commands_path, "a", encoding="utf-8")

            # Precheck: Registerstand mit dem Rueckstellpunkt vergleichen, BEVOR
            # auch nur ein Schreibbefehl geschickt wird. Der Strom wird dafuer
            # kurz angehalten und danach sofort wieder gestartet (eigenes
            # pause/resume-Ereignispaar, Label "precheck").
            matches, precheck_detail = _check_restore_point(ser, restore_point, f_cmd, state, label="precheck")
            state["precheck"] = precheck_detail
            if not matches and not ignore_restore_point_mismatch:
                state["schedule_error"] = (
                    "Geraet steht nicht am Rueckstellpunkt "
                    f"(erwartet norm={precheck_detail['expected_norm']} dpoint={precheck_detail['expected_dpoint']}, "
                    f"gelesen norm={precheck_detail['actual_norm']} dpoint={precheck_detail['actual_dpoint']}). "
                    "Kein Schreibbefehl wurde gesendet. Mit --ignore-restore-point-mismatch uebersteuerbar."
                )
                ready_event.set()
                return
            if not matches and ignore_restore_point_mismatch:
                precheck_detail["ignored"] = True

        ready_event.set()
        count = 0
        max_queue_depth = 0
        schedule_index = 0
        next_switch_mono: float | None = None
        if norm_schedule:
            factor, hold_s = norm_schedule[0]
            norm_bytes, dpoint_byte = _encode_norm(factor)
            ok = _apply_norm_dpoint(ser, norm_bytes, dpoint_byte, f_cmd, state, label=f"schedule[0] factor={factor}")
            state.setdefault("schedule_steps", []).append(
                {"index": 0, "factor": factor, "hold_s": hold_s, "last_error_ok": ok}
            )
            next_switch_mono = time.monotonic() + hold_s
            schedule_index = 1

        while not stop_event.is_set():
            if (
                norm_schedule
                and schedule_index < len(norm_schedule)
                and next_switch_mono is not None
                and time.monotonic() >= next_switch_mono
            ):
                factor, hold_s = norm_schedule[schedule_index]
                norm_bytes, dpoint_byte = _encode_norm(factor)
                ok = _apply_norm_dpoint(
                    ser, norm_bytes, dpoint_byte, f_cmd, state,
                    label=f"schedule[{schedule_index}] factor={factor}",
                )
                state.setdefault("schedule_steps", []).append(
                    {"index": schedule_index, "factor": factor, "hold_s": hold_s, "last_error_ok": ok}
                )
                next_switch_mono = time.monotonic() + hold_s
                schedule_index += 1
                continue
            try:
                raw = ser.readline()
            except Exception as exc:  # noqa: BLE001
                state["read_error"] = f"{type(exc).__name__}: {exc}"
                break
            if not raw:
                # Lesetimeout, kein Byte angekommen - weiter warten.
                continue
            t_boot = time.clock_gettime(time.CLOCK_BOOTTIME)
            text = raw.decode("ascii", errors="replace").rstrip("\r\n")
            serial_queue.put({"t_boot": t_boot, "text": text})
            count += 1
            max_queue_depth = max(max_queue_depth, serial_queue.qsize())
        state["count"] = count
        state["max_serial_queue_depth"] = max_queue_depth
    finally:
        # `not state.get("schedule_error")`: bei abweichendem Rueckstellpunkt
        # (Precheck-Mismatch ohne --ignore-restore-point-mismatch) wurde
        # bewusst NIE ein Schreibbefehl gesendet ("Kein Schreibbefehl wurde
        # gesendet." in der Fehlermeldung) - dieser `finally`-Block wird
        # jetzt (anders als vor der Erzeuger/Schreiber-Trennung) auch beim
        # fruehen Rueckkehrpfad des Precheck-Mismatch durchlaufen, darf die
        # Rueckstellung dort aber NICHT ausloesen, sonst wuerde genau dort
        # doch noch ein Schreibbefehl rausgehen.
        if norm_schedule is not None and f_cmd is not None and ser is not None and not state.get("schedule_error"):
            try:
                restore_norm_bytes = restore_point["register"]["norm"]["daten"]
                restore_dpoint_byte = restore_point["register"]["dpoint"]["daten"][0]
                write_ok = _apply_norm_dpoint(
                    ser, restore_norm_bytes, restore_dpoint_byte, f_cmd, state, label="restore"
                )
                verify_matches, verify_detail = _check_restore_point(
                    ser, restore_point, f_cmd, state, label="restore_verify"
                )
                state["restore_verification"] = {"write_ok": write_ok, **verify_detail}
            except Exception as exc:  # noqa: BLE001 - Sitzung trotzdem sauber abschliessen
                state["restore_verification"] = {"error": f"{type(exc).__name__}: {exc}"}
        if f_cmd is not None:
            f_cmd.close()
        if ser is not None:
            try:
                ser.close()
            except Exception:  # noqa: BLE001 - Aufraeumen, kein neuer Fehler beim Beenden
                pass
        serial_queue.put(_QUEUE_DONE)


def _serial_writer_worker(
    serial_queue: queue.Queue[Any],
    out_path: Path,
    state: dict[str, Any],
) -> None:
    """Entkoppelter Schreiber fuer `serial.jsonl`. Leert `serial_queue`
    zeilenweise geflusht, bis das `_QUEUE_DONE`-Sentinel des Lesethreads
    kommt - danach ist die Warteschlange per Konstruktion leer (FIFO, das
    Sentinel ist immer der letzte Eintrag des Lesethreads), es geht also
    nichts verloren. `state["count"]` ist die massgebliche Zahl tatsaechlich
    geschriebener Telegrammzeilen (ersetzt das frueher im Lesethread selbst
    gefuehrte `count`)."""
    count = 0
    with open(out_path, "a", encoding="utf-8") as f:
        while True:
            item = serial_queue.get()
            if item is _QUEUE_DONE:
                break
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            f.flush()
            count += 1
    state["count"] = count


# --- Bildstrom ---------------------------------------------------------------


def measure_clock_offset_ns(samples: int = CLOCK_OFFSET_SAMPLES, clock=time.clock_gettime_ns) -> int:
    """Median aus `samples` Einzelmessungen des Versatzes CLOCK_BOOTTIME
    minus CLOCK_MONOTONIC - die einzige Groesse, die `to_boottime_ns`
    (dispread.records) braucht, um einen `v4l2_monotonic`-Zeitstempel der
    StreamCam nach CLOCK_BOOTTIME umzurechnen.

    Jede Einzelmessung ist eng geklammert (MONOTONIC vor und nach der
    BOOTTIME-Messung, Mittelwert der beiden als Bezugspunkt) - so faellt der
    durch die drei Aufrufe selbst eingebrachte Fehler klein aus. Der Median
    (statt des Mittelwerts) filtert einen einzelnen Ausreisser heraus (z.B.
    ein Scheduler-Aussetzer zwischen den drei Aufrufen)."""
    offsets: list[int] = []
    for _ in range(samples):
        m1 = clock(time.CLOCK_MONOTONIC)
        b = clock(time.CLOCK_BOOTTIME)
        m2 = clock(time.CLOCK_MONOTONIC)
        offsets.append(b - (m1 + m2) // 2)
    offsets.sort()
    return offsets[len(offsets) // 2]


def count_frame_gaps(timestamps_ns: list[int], fps: float) -> dict[str, Any]:
    """Zaehlt Luecken in einer aufsteigenden Liste von `value_ns`-
    Zeitstempeln: eine Luecke ist ein Abstand > 1,5 * (1e9 / fps) ns
    (Schwelle aus den globalen Vorgaben). Reine Funktion, kein I/O.

    Rueckgabe: `{"threshold_ns", "count", "max_gap_ns", "gaps": [{"after_value_ns",
    "gap_ns"}, ...]}` - `gaps` traegt je Luecke den Zeitstempel DAVOR, damit
    sie sich in `frames.jsonl` wiederfinden laesst."""
    threshold_ns = 1.5 * 1e9 / fps
    gaps: list[dict[str, int]] = []
    for prev, cur in zip(timestamps_ns, timestamps_ns[1:], strict=False):
        gap_ns = cur - prev
        if gap_ns > threshold_ns:
            gaps.append({"after_value_ns": prev, "gap_ns": gap_ns})
    return {
        "threshold_ns": threshold_ns,
        "count": len(gaps),
        "max_gap_ns": max((g["gap_ns"] for g in gaps), default=0),
        "gaps": gaps,
    }


def _synthetic_frames(uri: str):
    """`Frame`-Objekte aus `dispread.frames.open_source`, roh durchgereicht.

    Liefert ein drittes Element `sensor_sequence=None` - es gibt bei
    `synthetic://` keine Sensor-/libcamera-Sequenznummer, das Feld existiert
    trotzdem in jedem Eintrag, nur eben leer (siehe OQ-40-Nachtrag)."""
    source = open_source(uri)
    source.open()
    try:
        for frame in source.frames():
            yield frame.image, frame.capture_timestamp.to_dict(), None
    finally:
        source.close()


def _uvc_frames(settings: CameraSettings, device: str | None, state: dict[str, Any]):
    """Echte Kamera: Logitech StreamCam ueber `UvcSource`
    (src/dispread/frames/uvc_source.py). `UvcSource` ist am Modulanfang
    importiert (kein Hardwarebedarf beim reinen Import, das eigentliche
    `cv2` steckt lazy in `UvcSource.open()`) statt hier lokal - so kann ein
    Test `module.UvcSource` durch eine Fake-Klasse ersetzen.

    Liefert dasselbe Tripel wie `_synthetic_frames`, `sensor_sequence` immer
    `None` - die StreamCam hat keine Sensor-/libcamera-Sequenznummer wie das
    IMX500.

    `describe()` landet IMMER in `state["camera"]` - auch wenn `open()` mit
    `UvcError` scheitert (dann mit den bis dahin bekannten Feldern, z.B.
    `device=None`, wenn nicht einmal `find_uvc_device` durchlief) oder wenn
    kein einziges Bild ankam. Nur so kann `run()` das reale Kameraprofil
    dieser Sitzung dokumentieren, unabhaengig vom Ausgang."""
    source = UvcSource(settings, device=device)
    try:
        source.open()
        for frame in source.frames():
            yield frame.image, frame.capture_timestamp.to_dict(), None
    finally:
        source.close()
        state["camera"] = source.describe()


def _frame_generator(args: argparse.Namespace, state: dict[str, Any], camera_settings: CameraSettings | None = None,
                      camera_device: str | None = None):
    """Liefert Tripel `(image, timestamp_dict, sensor_sequence)` - siehe
    `_synthetic_frames`/`_uvc_frames`. `camera_settings`/`camera_device`
    werden nur im Kamerazweig gebraucht (dort von `run()` schon geladen,
    damit `settings.fps` auch fuer `count_frame_gaps` zur Verfuegung steht,
    ohne die Profildatei ein zweites Mal zu lesen)."""
    if args.source == "synthetic":
        state["camera"] = None
        yield from _synthetic_frames(args.synthetic_uri)
    else:
        assert camera_settings is not None
        yield from _uvc_frames(camera_settings, camera_device, state)


class _CameraStartupTimeout(Exception):
    """Kein Bild innerhalb von `STARTUP_TIMEOUT_S` nach Kamerastart (Bug 1)."""


def _no_frames_message(detail: str) -> str:
    """Einheitlicher Wortlaut fuer jeden Fall, in dem der Kamerazweig ohne
    Bild endet (Timeout, Ausnahme, oder frames_recorded == 0 am Ende)."""
    return f"Kamera liefert keine Bilder - Prozess NICHT hart beenden. {detail}"


def _camera_startup_guard(gen, timeout_s: float):
    """Wrapper-Generator: das ERSTE Element von `gen` wird mit einer
    Zeitschranke `timeout_s` geholt, alle weiteren unveraendert durchgereicht.

    Grund: eine haengende Kamera laesst `UvcSource.frames()`/`open()` unter
    Umstaenden lange haengen. Das darf nicht als stiller Leerlauf enden
    (Bug 1, Orchestrator 2026-09-23).

    Das erste `next(gen)` laeuft dafuer in einem eigenen Daemon-Thread. Bei
    Zeitueberschreitung wird dieser Thread NICHT abgebrochen - Python kann
    einen blockierten Aufruf nicht sicher unterbrechen. Der Thread stirbt mit
    dem Prozess (daemon=True); der reguläre Abbruchpfad (`close()` im
    `finally` von `_uvc_frames`) laeuft nur, wenn der blockierte Aufruf
    irgendwann doch noch zurueckkehrt oder wirft."""
    result: dict[str, Any] = {}
    done = threading.Event()

    def _fetch_first() -> None:
        try:
            result["item"] = next(gen)
        except StopIteration:
            result["stopped"] = True
        except Exception as exc:  # noqa: BLE001 - an den Aufrufer weiterreichen
            result["exception"] = exc
        finally:
            done.set()

    thread = threading.Thread(target=_fetch_first, daemon=True, name="camera-startup-guard")
    thread.start()
    if not done.wait(timeout=timeout_s):
        raise _CameraStartupTimeout(
            f"Kein Bild innerhalb von {timeout_s:.0f}s nach Kamerastart erhalten"
        )
    if "exception" in result:
        raise result["exception"]
    if not result.get("stopped"):
        yield result["item"]
    yield from gen


def _frame_acquisition_worker(
    args: argparse.Namespace,
    frame_queue: queue.Queue[Any],
    frame_drop_queue: queue.Queue[Any],
    stop_event: threading.Event,
    state: dict[str, Any],
    *,
    camera_settings: CameraSettings | None = None,
    camera_device: str | None = None,
) -> None:
    """Zieht Bilder aus `_frame_generator` und legt sie in `frame_queue` ab -
    kodiert und schreibt NICHTS (siehe Moduldocstring, Abschnitt "Erzeugen
    und Schreiben sind getrennte Threads"): genau die Dateisystemzugriffe,
    die dort frueher in dieser Schleife lagen, blockierten am 2026-09-23
    unter Kernel-Dirty-Page-Writeback (bis 130 MB) - ein I/O-loser
    Herzschlagprozess zeigte im selben Zeitraum KEINE Luecke.

    Die Taktung (`--frame-rate`) bleibt bewusst HIER, nicht im
    Schreiberthread: sie regelt, wie schnell dieser Thread den naechsten
    Generator-`next()` aufruft - fuer `synthetic://` ist das die einzige
    Bremse ueberhaupt (Erzeugung ist praktisch sofort), fuer `--source
    camera` taktet die Hardware selbst schon (`settings.fps`) und diese
    Sleep bleibt zusaetzlich wirksam, reines Verschieben der Zustaendigkeit,
    keine Verhaltensaenderung an der Taktung selbst.

    Ist `frame_queue` voll (Schreiber kommt nicht hinterher), wird das Bild
    NICHT geschrieben und NICHT still verworfen: es zaehlt in
    `state["frames_dropped_queue_full"]`, und eine kleine Meldung (ohne
    Bilddaten) geht auf die unbegrenzte `frame_drop_queue`, damit sie trotzdem
    als eigener `frames.jsonl`-Eintrag sichtbar wird. `frame_queue.put(...)`
    selbst blockiert dafuer NIE.

    `frame_gaps` (nur Kamerazweig): alle gelieferten `value_ns` werden
    gesammelt und am Ende ueber `count_frame_gaps(..., camera_settings.fps)`
    ausgewertet - Luecken sind hier am aussagekraeftigsten, weil sie die roh
    von der Kamera gelieferten Zeitstempel betreffen, nicht erst die
    Skript-eigene Taktung."""
    frame_period_s = 1.0 / args.frame_rate if args.frame_rate > 0 else 0.0
    start_mono = time.monotonic()
    next_due = start_mono
    max_loop_iteration_s = 0.0
    stall_iterations: list[dict[str, Any]] = []
    prev_loop_end_mono = start_mono
    prev_sensor_timestamp_ns: int | None = None
    max_frame_queue_depth = 0
    frames_acquired = 0
    frames_dropped = 0
    camera_value_ns: list[int] = []

    gen = _frame_generator(args, state, camera_settings, camera_device)
    if args.source == "camera":
        # Bug 1: nur der Kamerazweig kann haengen bleiben - synthetic:// ist
        # ein reiner Generator ohne Hardware-I/O.
        gen = _camera_startup_guard(gen, STARTUP_TIMEOUT_S)
    try:
        for image, timestamp_dict, sensor_sequence in gen:
            if stop_event.is_set():
                break
            now = time.monotonic()
            iter_duration_s = now - prev_loop_end_mono
            if iter_duration_s > max_loop_iteration_s:
                max_loop_iteration_s = iter_duration_s
            if frame_period_s > 0 and iter_duration_s > 3 * frame_period_s:
                stall_iterations.append({
                    "t_boot": time.clock_gettime(time.CLOCK_BOOTTIME),
                    "duration_s": iter_duration_s,
                })
            if now - start_mono >= args.duration:
                break
            frames_acquired += 1

            value_ns = timestamp_dict.get("value_ns")
            sensor_timestamp_interval_ns = None
            if prev_sensor_timestamp_ns is not None and value_ns is not None:
                sensor_timestamp_interval_ns = value_ns - prev_sensor_timestamp_ns
            if value_ns is not None:
                prev_sensor_timestamp_ns = value_ns
                if args.source == "camera":
                    camera_value_ns.append(value_ns)

            try:
                frame_queue.put_nowait({
                    "sensor_sequence": sensor_sequence,
                    "sensor_timestamp_interval_ns": sensor_timestamp_interval_ns,
                    "capture_timestamp": timestamp_dict,
                    "image": image,
                })
            except queue.Full:
                frames_dropped += 1
                frame_drop_queue.put({
                    "dropped": True,
                    "sensor_sequence": sensor_sequence,
                    "capture_timestamp": timestamp_dict,
                    "t_boot": time.clock_gettime(time.CLOCK_BOOTTIME),
                })
            max_frame_queue_depth = max(max_frame_queue_depth, frame_queue.qsize())

            if frame_period_s > 0:
                next_due += frame_period_s
                sleep_for = next_due - time.monotonic()
                if sleep_for > 0:
                    time.sleep(sleep_for)
            prev_loop_end_mono = time.monotonic()
    except _CameraStartupTimeout as exc:
        # Bug 1: laut ablehnen statt still 0 Bilder zu hinterlassen, inkl.
        # Hinweis, den Prozess NICHT hart zu beenden (siehe
        # _camera_startup_guard-Docstring).
        state["acquisition_error"] = _no_frames_message(f"{exc}.")
    except UvcError as exc:
        # StreamCam liess sich nicht wie im Profil verlangt einrichten
        # (`UvcSource.open()`, z.B. Aufloesung oder ein Regler-Ist-Wert
        # weicht ab) - dasselbe "keine Bilder"-Ergebnis wie der Startup-
        # Timeout, nur mit dem `UvcError`-Text als Detail. `UvcError` kann
        # nur aus `_uvc_frames` stammen, also immer im Kamerazweig - kein
        # `args.source`-Fallunterschied noetig.
        if frames_acquired == 0:
            state["acquisition_error"] = _no_frames_message(f"UvcError: {exc}")
        else:
            state["acquisition_error"] = f"UvcError: {exc}"
    except Exception as exc:  # noqa: BLE001 - Sitzung trotzdem sauber abschliessen
        if args.source == "camera" and frames_acquired == 0:
            # Jede Ausnahme im Kamerazweig OHNE EIN EINZIGES BILD ist derselbe
            # Befund wie der Startup-Timeout (Bug 1) - z.B. ein Lesefehler
            # ohne jedes Bild. Kam schon mindestens ein Bild an, ist es ein
            # anderer Fehler (die Kamera lief ja) - dafuer waere "keine
            # Bilder" falsch, siehe generischer Zweig unten.
            state["acquisition_error"] = _no_frames_message(f"{type(exc).__name__}: {exc}")
        else:
            state["acquisition_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        gen.close()
        state.setdefault("camera", None)
        state["frames_acquired"] = frames_acquired
        state["frames_dropped_queue_full"] = frames_dropped
        state["max_loop_iteration_s"] = max_loop_iteration_s
        state["stall_iterations"] = stall_iterations
        state["max_frame_queue_depth"] = max_frame_queue_depth
        state["frame_gaps"] = (
            count_frame_gaps(camera_value_ns, camera_settings.fps)
            if args.source == "camera" and camera_settings is not None
            else None
        )
        # Kameraausfall MITTEN in der Aufnahme (Review-Fund, Fix-Runde 1):
        # `UvcSource.frames()` wirft bei einem Lesefehler NICHT - sie setzt
        # `read_error` und beendet den Generator regulaer (siehe
        # `UvcSource.frames()`/READ_FAIL_TIMEOUT_S). Ohne Ausnahme durchlaeuft
        # die `for`-Schleife oben keinen `except`-Zweig, `acquisition_error`
        # bliebe also unbemerkt `None`, obwohl schon Bilder aufgezeichnet
        # wurden. Nur relevant, wenn schon mindestens ein Bild ankam (kam gar
        # keins an, greift stattdessen der no-frames-Pfad in `run()`, der
        # `frames_recorded == 0` prueft und Exit 4 ausloest) und noch kein
        # anderer Zweig oben schon einen Grund gesetzt hat.
        if (
            args.source == "camera"
            and frames_acquired > 0
            and state.get("acquisition_error") is None
            and state.get("camera") is not None
            and state["camera"].get("read_error")
        ):
            state["acquisition_error"] = (
                f"Kameraausfall waehrend der Aufnahme: {state['camera']['read_error']}"
            )
        frame_queue.put(_QUEUE_DONE)
        frame_drop_queue.put(_QUEUE_DONE)


def _frame_writer_worker(
    frame_queue: queue.Queue[Any],
    frame_drop_queue: queue.Queue[Any],
    frames_jsonl: Path,
    frames_dir: Path,
    ext: str,
    state: dict[str, Any],
) -> None:
    """Entkoppelter Schreiber: JPEG/PNG-Kodierung (`cv2.imwrite`) +
    `frames.jsonl` - siehe Moduldocstring. `frame_sequence` wird HIER
    vergeben (luecken-/abbruchfreie, aufsteigende Zaehlung der tatsaechlich
    geschriebenen Bilder, unveraendert gegenueber dem Verhalten vor dieser
    Aufteilung) - verworfene Bilder tragen keine `frame_sequence`, ihre
    `frames.jsonl`-Meldung traegt stattdessen `sensor_sequence`/
    `capture_timestamp` (das, was von ihnen bekannt ist).

    `cv2.imwrite` ist eine OpenCV-C++-Funktion; das Kodieren blockiert
    trotzdem bewusst NUR hier und nie den Aufnahmethread - unabhaengig
    davon, wie lange dabei der GIL gehalten wird, darf ein langsamer
    Schreibvorgang nie die naechste Bildaufnahme verzoegern. `cv2` ist am
    Modulanfang importiert (kein Hardwarebedarf, siehe dort) - kein
    zusaetzlicher lokaler Import noetig.

    Bildzaehler-Fix (Review Focus 2): `state["frames_recorded"]` wird nach
    JEDEM geschriebenen Bild aktualisiert, nicht erst am Ende der Schleife.
    Vorher stand dort nur der allerletzte Stand nach Schleifenende - haengt
    der Aufnahmethread (kommt also nie `_QUEUE_DONE` auf `frame_queue` an),
    lief diese Schleife nie zu Ende und `frames_recorded` blieb beim
    Default `0` stehen, obwohl der Schreiber laengst Bilder auf die Platte
    geschrieben hatte. `run()` liest `frames_recorded` nach dem (ggf. per
    Timeout beendeten) `frame_writer_thread.join(...)` - der laufend
    aktualisierte Stand ist deshalb auch dann ehrlich, wenn der Join-Timeout
    zuschlaegt. `writer_finished` markiert zusaetzlich, ob die Schleife
    tatsaechlich regulaer zu Ende kam (beide `_QUEUE_DONE`-Sentinel
    angekommen) oder ob der Thread beim Prozessende noch lief."""
    frames_written = 0
    frame_done = False
    drop_done = False
    with open(frames_jsonl, "a", encoding="utf-8") as f_frames:
        while not (frame_done and drop_done):
            try:
                item = frame_queue.get(timeout=0.1)
            except queue.Empty:
                item = None
            if item is not None:
                if item is _QUEUE_DONE:
                    frame_done = True
                else:
                    frames_written += 1
                    filename = f"frame_{frames_written:06d}.{ext}"
                    cv2.imwrite(str(frames_dir / filename), item["image"])
                    entry = {
                        "file": filename,
                        "frame_sequence": frames_written,
                        "sensor_sequence": item["sensor_sequence"],
                        "sensor_timestamp_interval_ns": item["sensor_timestamp_interval_ns"],
                        "capture_timestamp": item["capture_timestamp"],
                    }
                    f_frames.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    f_frames.flush()
                    state["frames_recorded"] = frames_written
            while True:
                try:
                    drop_item = frame_drop_queue.get_nowait()
                except queue.Empty:
                    break
                if drop_item is _QUEUE_DONE:
                    drop_done = True
                else:
                    f_frames.write(json.dumps(drop_item, ensure_ascii=False) + "\n")
                    f_frames.flush()
    state["frames_recorded"] = frames_written
    state["writer_finished"] = True


# --- Hauptablauf --------------------------------------------------------------


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"nicht serialisierbar: {type(value)!r}")


#: Vorher: SIGTERM hatte keinen Handler und beendete den Prozess sofort ohne
#: session.json - nur SIGINT (Ctrl-C, per Default-Handler eine
#: KeyboardInterrupt) lief durch den sauberen Abbruchpfad. SIGTERM wird hier
#: bewusst auf denselben Pfad umgelenkt statt einen eigenen zu bauen.
_SIGTERM_MARKER = "SIGTERM"


def _install_sigterm_handler() -> None:
    def _handle_sigterm(signum, frame):  # noqa: ARG001 - Signatur von signal.signal vorgegeben
        raise KeyboardInterrupt(_SIGTERM_MARKER)

    signal.signal(signal.SIGTERM, _handle_sigterm)


def run(args: argparse.Namespace) -> int:
    _install_sigterm_handler()

    # Kameraprofil VOR jedem Kamerazugriff laden - liest nur die JSON-Datei,
    # oeffnet weder Kamera noch Port. `--camera-settings` ist bei --source
    # camera bereits in parse_args als Pflicht erzwungen.
    camera_settings: CameraSettings | None = None
    camera_device: str | None = None
    if args.source == "camera":
        try:
            camera_settings = load_camera_settings(args.camera_settings)
        except (OSError, ValueError) as exc:
            print(f"Fehler: --camera-settings {args.camera_settings} konnte nicht geladen werden: {exc}", file=sys.stderr)
            return 1
        camera_device = str(args.camera_device) if args.camera_device is not None else None

    output_dir = args.output or (DEFAULT_OUTPUT_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S"))
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    serial_jsonl = output_dir / "serial.jsonl"
    frames_jsonl = output_dir / "frames.jsonl"
    session_json = output_dir / "session.json"

    commands_jsonl: Path | None = None
    restore_point: dict | None = None
    if args.norm_schedule is not None:
        if not args.restore_point.is_file():
            print(f"Fehler: Rueckstellpunkt-Datei nicht gefunden: {args.restore_point}", file=sys.stderr)
            return 1
        try:
            restore_point = json.loads(args.restore_point.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"Fehler: Rueckstellpunkt-Datei {args.restore_point} ist kein gueltiges JSON: {exc}", file=sys.stderr)
            return 1
        commands_jsonl = output_dir / "commands.jsonl"

    started_at_utc = datetime.now(UTC).isoformat()
    started_at_boottime_ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    # Versatz CLOCK_BOOTTIME-CLOCK_MONOTONIC direkt vor dem Start der
    # Aufnahme-Threads messen (siehe `measure_clock_offset_ns`) - noetig, um
    # spaeter `v4l2_monotonic`-Zeitstempel der StreamCam ueberhaupt nach
    # CLOCK_BOOTTIME umrechnen zu koennen (`dispread.records.to_boottime_ns`).
    # Wird IMMER gemessen, auch bei --source synthetic - die Umrechnung ist
    # zeitbasisabhaengig, nicht quellenabhaengig.
    clock_offset_start_ns = measure_clock_offset_ns()

    stop_event = threading.Event()
    ready_event = threading.Event()
    serial_state: dict[str, Any] = {"count": 0, "open_error": None}
    serial_writer_state: dict[str, Any] = {"count": 0}
    serial_queue: queue.Queue[Any] = queue.Queue()  # unbegrenzt, siehe Moduldocstring

    serial_thread = threading.Thread(
        target=_serial_worker,
        args=(args.port, args.baudrate, serial_queue, stop_event, ready_event, serial_state),
        kwargs={
            "commands_path": commands_jsonl,
            "norm_schedule": args.norm_schedule,
            "restore_point": restore_point,
            "ignore_restore_point_mismatch": args.ignore_restore_point_mismatch,
        },
        name="serial-reader",
        daemon=True,
    )
    serial_writer_thread = threading.Thread(
        target=_serial_writer_worker,
        args=(serial_queue, serial_jsonl, serial_writer_state),
        name="serial-writer",
        daemon=True,
    )
    # Schreiber zuerst starten: er soll sofort abholen koennen, sobald der
    # Lesethread die erste Zeile auf die Warteschlange legt.
    serial_writer_thread.start()
    serial_thread.start()

    if not ready_event.wait(timeout=READY_TIMEOUT_S):
        print(
            f"Fehler: serieller Lesethread meldete sich nicht innerhalb {READY_TIMEOUT_S}s",
            file=sys.stderr,
        )
        stop_event.set()
        serial_thread.join(timeout=JOIN_TIMEOUT_S)
        serial_writer_thread.join(timeout=WRITER_DRAIN_JOIN_TIMEOUT_S)
        return 1
    if serial_state["open_error"]:
        print(
            f"Fehler: serieller Port {args.port!r} konnte nicht geoeffnet werden: "
            f"{serial_state['open_error']}",
            file=sys.stderr,
        )
        stop_event.set()
        serial_thread.join(timeout=JOIN_TIMEOUT_S)
        serial_writer_thread.join(timeout=WRITER_DRAIN_JOIN_TIMEOUT_S)
        return 1
    if serial_state.get("schedule_error"):
        print(f"Fehler: {serial_state['schedule_error']}", file=sys.stderr)
        stop_event.set()
        serial_thread.join(timeout=JOIN_TIMEOUT_S)
        serial_writer_thread.join(timeout=WRITER_DRAIN_JOIN_TIMEOUT_S)
        return 1

    ext = "png" if args.image_format == "png" else "jpg"

    frame_acq_state: dict[str, Any] = {}
    frame_writer_state: dict[str, Any] = {}
    frame_queue: queue.Queue[Any] = queue.Queue(maxsize=args.frame_queue_size)  # begrenzt, siehe Moduldocstring
    frame_drop_queue: queue.Queue[Any] = queue.Queue()  # unbegrenzt, nur kleine Meldungen

    frame_acq_thread = threading.Thread(
        target=_frame_acquisition_worker,
        args=(args, frame_queue, frame_drop_queue, stop_event, frame_acq_state),
        kwargs={"camera_settings": camera_settings, "camera_device": camera_device},
        name="frame-acquisition",
        daemon=True,
    )
    frame_writer_thread = threading.Thread(
        target=_frame_writer_worker,
        args=(frame_queue, frame_drop_queue, frames_jsonl, frames_dir, ext, frame_writer_state),
        name="frame-writer",
        daemon=True,
    )
    frame_writer_thread.start()
    frame_acq_thread.start()

    aborted = False
    abort_reason: str | None = None
    start_mono = time.monotonic()

    try:
        # Die eigentliche Aufnahme laeuft komplett in den beiden Threads
        # oben - dieser Hauptthread wartet nur auf das Dauerende oder ein
        # Signal (SIGINT/SIGTERM landen hier als KeyboardInterrupt, siehe
        # `_install_sigterm_handler`, genau wie zuvor bei der blockierenden
        # Bildschleife).
        stop_event.wait(timeout=args.duration)
    except KeyboardInterrupt as exc:
        aborted = True
        if exc.args and exc.args[0] == _SIGTERM_MARKER:
            abort_reason = "SIGTERM"
            print("\nAbbruch (SIGTERM) - schreibe bereits aufgezeichnete Daten vollstaendig ab.", file=sys.stderr)
        else:
            abort_reason = "KeyboardInterrupt (Ctrl-C)"
            print("\nAbbruch (Ctrl-C) - schreibe bereits aufgezeichnete Daten vollstaendig ab.", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - Sitzung trotzdem sauber abschliessen
        aborted = True
        abort_reason = f"{type(exc).__name__}: {exc}"
        traceback.print_exc(file=sys.stderr)
    finally:
        elapsed_s = time.monotonic() - start_mono
        stop_event.set()

        # Reihenfolge ist Teil der Abbruchgarantie (siehe Moduldocstring):
        # erst die Erzeugerseiten fertig werden lassen - ihr jeweils letzter
        # Schritt ist `_QUEUE_DONE` auf die eigene Warteschlange zu legen -,
        # dann die Schreiberseiten, die bis zu diesem Sentinel vollstaendig
        # leeren. Erst danach ist bekannt, was wirklich geschrieben wurde.
        # JOIN_TIMEOUT_S ist grosszuegig bemessen (--norm-schedule laesst im
        # finally-Block des Lesethreads noch die Rueckstellung laufen; die
        # Kamera kann bis zu `wait=2.0` in `capture_request` haengen).
        frame_acq_thread.join(timeout=JOIN_TIMEOUT_S)
        frame_writer_thread.join(timeout=WRITER_DRAIN_JOIN_TIMEOUT_S)
        serial_thread.join(timeout=JOIN_TIMEOUT_S)
        serial_writer_thread.join(timeout=WRITER_DRAIN_JOIN_TIMEOUT_S)

        # Zweite Versatzmessung nach dem Join - die Differenz zu
        # `clock_offset_start_ns` zeigt einen Suspend waehrend der Aufnahme
        # an (SUSPEND_TOLERANCE_NS in dispread.records.to_boottime_ns).
        clock_offset_end_ns = measure_clock_offset_ns()

        frames_recorded = frame_writer_state.get("frames_recorded", 0)
        serial_lines_recorded = serial_writer_state.get("count", 0)

        acquisition_error = frame_acq_state.get("acquisition_error")
        if args.source == "camera" and frames_recorded == 0 and not acquisition_error:
            # Bug 1, zweiter Fall: der Kamerazweig lieferte zwar irgendwann
            # eine Antwort (kein Timeout, keine Ausnahme), aber am Ende steht
            # trotzdem 0 aufgezeichnete Bilder da - auch das ist ein Befund,
            # kein stiller Leerlauf.
            acquisition_error = _no_frames_message("Kamerazweig endete mit 0 aufgezeichneten Bildern.")

        session = {
            "started_at_utc": started_at_utc,
            "started_at_boottime_ns": started_at_boottime_ns,
            "duration_s": args.duration,
            "elapsed_s": elapsed_s,
            "args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
            "port": args.port,
            "baudrate": args.baudrate,
            "source": args.source,
            "frames_recorded": frames_recorded,
            "serial_lines_recorded": serial_lines_recorded,
            "aborted": aborted,
            "abort_reason": abort_reason,
            "norm_schedule": (
                [{"factor": f, "hold_s": h} for f, h in args.norm_schedule]
                if args.norm_schedule is not None
                else None
            ),
            # Immer True, sobald --norm-schedule gesetzt ist: jeder Schreib-
            # zugriff (Precheck, jeder Schedule-Schritt, die Rueckstellung)
            # haelt den Messwertstrom vorher an (STOP+CLEAR) und startet ihn
            # danach neu (START) - siehe commands.jsonl fuer die genauen
            # pause_transmission/resume_transmission-Zeitpunkte je Schritt.
            "transmission_paused_during_writes": args.norm_schedule is not None,
            "commands_jsonl_event_count": serial_state.get("command_event_count"),
            "precheck": serial_state.get("precheck"),
            "schedule_steps": serial_state.get("schedule_steps"),
            "restore_verification": serial_state.get("restore_verification"),
            # Stall-Diagnostik OQ-40-Nachtrag 2026-09-23 - jetzt im
            # Aufnahmethread gemessen, unbeeinflusst von der Schreibseite
            # (siehe Moduldocstring "Erzeugen und Schreiben sind getrennte
            # Threads"): ein langsamer Schreiber darf hier nie mehr
            # faelschlich als Stall auftauchen.
            "max_loop_iteration_s": frame_acq_state.get("max_loop_iteration_s", 0.0),
            "stall_iteration_count": len(frame_acq_state.get("stall_iterations", [])),
            "stall_iterations": frame_acq_state.get("stall_iterations", []),
            "frames_dropped_queue_full": frame_acq_state.get("frames_dropped_queue_full", 0),
            "max_frame_queue_depth": frame_acq_state.get("max_frame_queue_depth", 0),
            "max_serial_queue_depth": serial_state.get("max_serial_queue_depth", 0),
            "acquisition_error": acquisition_error,
            # Kamera: `UvcSource.describe()` (oder `None` bei --source
            # synthetic) - siehe `_uvc_frames`. Wird auch bei einem
            # `UvcError` beim Oeffnen oder 0 aufgezeichneten Bildern gesetzt.
            "camera": frame_acq_state.get("camera"),
            # Versatz CLOCK_BOOTTIME-CLOCK_MONOTONIC, IMMER gesetzt (auch bei
            # --source synthetic) - siehe `measure_clock_offset_ns` und
            # `dispread.records.to_boottime_ns`.
            "clock_offset_boottime_minus_monotonic_ns": {
                "start": clock_offset_start_ns,
                "end": clock_offset_end_ns,
            },
            # Luecken in den roh gelieferten Kamera-Zeitstempeln - nur im
            # Kamerazweig gesetzt, siehe `count_frame_gaps`.
            "frame_gaps": frame_acq_state.get("frame_gaps"),
            # Nur im Kamerazweig relevant: < 5000 Mbps heisst kein USB3, was
            # bei hoher Aufloesung/fps zum limitierenden Faktor werden kann.
            "usb_speed_warning": (
                (
                    f"USB-Verbindung der StreamCam laeuft mit "
                    f"{frame_acq_state['camera']['usb_speed_mbps']} Mbps (< 5000 = USB3)."
                )
                if frame_acq_state.get("camera") is not None
                and frame_acq_state["camera"].get("usb_speed_mbps") is not None
                and frame_acq_state["camera"]["usb_speed_mbps"] < 5000
                else None
            ),
            # Bildzaehler-Fix (Review Focus 2): ob der Schreiberthread
            # regulaer zu Ende kam (beide `_QUEUE_DONE`-Sentinel angekommen)
            # oder beim Prozessende noch lief (z.B. haengender
            # Aufnahmethread) - `frames_recorded` bleibt in beiden Faellen
            # ehrlich, siehe `_frame_writer_worker`.
            "frame_writer_finished": frame_writer_state.get("writer_finished", False),
        }
        session_json.write_text(json.dumps(session, indent=2, ensure_ascii=False, default=_json_default))

    if serial_state.get("read_error"):
        print(f"Warnung: serielles Lesen beendet mit Fehler: {serial_state['read_error']}", file=sys.stderr)
    if acquisition_error:
        print(f"FEHLER: Bildaufnahme: {acquisition_error}", file=sys.stderr)

    if serial_writer_state.get("count", 0) == 0:
        print(
            "WARNUNG: In der gesamten Aufzeichnung wurde kein einziges Telegramm "
            f"empfangen (Dauer={args.duration}s, Port={args.port!r}, Baudrate={args.baudrate}). "
            "serial.jsonl ist leer - das ist eine Meldung, kein stiller Erfolg.",
            file=sys.stderr,
        )
    if frame_acq_state.get("frames_dropped_queue_full", 0) > 0:
        print(
            f"WARNUNG: {frame_acq_state['frames_dropped_queue_full']} Bild(er) verworfen, weil die "
            f"Schreiber-Warteschlange voll war (--frame-queue-size {args.frame_queue_size}).",
            file=sys.stderr,
        )

    # Bug 1: Exit 4 (und das "FEHLER"-Wort statt "vollstaendig") ist speziell
    # der "keine Bilder"-Befund - ein Fehler NACH bereits aufgezeichneten
    # Bildern bleibt beim bisherigen Verhalten (Warnung, Exit 0), das ist ein
    # anderer Fall als der hier behandelte stille Leerlauf.
    no_frames_acquired = args.source == "camera" and frames_recorded == 0 and bool(acquisition_error)
    if aborted:
        status_word = "ABGEBROCHEN"
    elif no_frames_acquired:
        # Dieses Wort darf hier nie stehen, wenn keine Bilder angekommen
        # sind - "vollstaendig" hiesse stillschweigend erfolgreich.
        status_word = "FEHLER (keine Bilder, siehe acquisition_error)"
    else:
        status_word = "vollstaendig"
    print(
        f"Fertig: {frame_writer_state.get('frames_recorded', 0)} Bilder, "
        f"{serial_writer_state.get('count', 0)} Telegrammzeilen, "
        f"{status_word} -> {output_dir}"
    )
    if no_frames_acquired:
        return EXIT_NO_FRAMES_ACQUIRED
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
