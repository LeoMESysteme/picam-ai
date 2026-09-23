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

Fuer die Bild-Zeitstempelfelder ist `Controller._capture`
(`src/dispread/workbench/controller.py`) der verbindliche Bezug: dieselben
Feldnamen, dieselbe Behandlung (`timestamp_semantics: "unknown"`,
`uncertainty_ns: None`, `TimeBaseKind.SENSOR_BOOTTIME`, `SensorTimestamp`
unveraendert). Ein Zeitstempel ohne benannte Zeitbasis ist nach AGENTS.md
keine verwertbare Angabe.

Betriebshinweis (`--source camera`): Die Kamera kann nur EIN Prozess halten.
Vor dem Start pruefen, ob ein `dispread serve` laeuft, und die
RP2040-Wedge-/Sperrgefahr aus OQ-22 (docs/open-questions.md) im Blick
behalten - dieser Zweig wird bewusst nicht von der Entwicklungsumgebung aus
ausgefuehrt, nur geschrieben und per `--source synthetic` getestet.

Robustheit:
  - Serielles Lesen laeuft in einem eigenen Thread, damit eine 66-ms-Bildauf-
    nahme kein Telegramm verschluckt.
  - Ctrl-C hinterlaesst vollstaendige, gueltige Dateien: beide JSONL-Dateien
    werden zeilenweise geflusht, und `session.json` wird auch im
    Abbruchfall geschrieben (mit `"aborted": true`).
  - Kommt ueber die ganze Dauer kein einziges Telegramm an, wird das am Ende
    laut gemeldet statt stillschweigend eine leere `serial.jsonl` zu
    hinterlassen.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import signal
import sys
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2

from dispread.frames import open_source
from dispread.records import TimeBaseKind, Timestamp, TimestampSemantics

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

REPO_ROOT = Path(__file__).resolve().parents[1]
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
        help="Zieltakt der Bildaufnahme in Hz (0 = so schnell wie moeglich)",
    )
    parser.add_argument("--port", default=DEFAULT_PORT, help="Serieller Port, nur gelesen")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--image-format", choices=["png", "jpg"], default="png")
    parser.add_argument(
        "--camera-size",
        # 960x720 ist NICHT beliebig gewaehlt, sondern die in OQ-22
        # festgehaltene Betriebsgroesse. Jede dort protokollierte Sitzung mit
        # einem grossen Sensormodus (2028x1520, 4056x3040) war die letzte des
        # Boots - danach setzt der Sensor keinen Stream mehr auf und nur ein
        # Reboot hilft. Am 2026-09-22 mit der Vorgabe 2028x1520 erneut
        # ausgeloest. 960x720 hebt das Problem nicht auf, verzoegert es aber
        # nachweislich; mehr Ziffernhoehe kommt ueber ScalerCrop, nicht ueber
        # den Sensormodus.
        default="960x720",
        help="Nur --source camera: Aufloesung BxH. Vorgabe 960x720 - "
             "groessere Sensormodi blockieren den Sensor bis zum Reboot (OQ-22)",
    )
    parser.add_argument(
        "--allow-large-sensor-mode",
        action="store_true",
        help="Sperre gegen grosse Sensormodi aufheben. Nur bewusst setzen - "
             "siehe OQ-22, Folge ist im Zweifel ein Reboot des Labor-Pi",
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
    _check_camera_size(parser, args)
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


#: Ab dieser Pixelzahl gilt ein Modus als "gross" im Sinne von OQ-22.
#: 960x720 = 691 200 liegt darunter, 2028x1520 = 3 082 560 darueber.
LARGE_SENSOR_MODE_PIXELS = 1_000_000


def _check_camera_size(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Grosse Sensormodi abweisen, solange OQ-22 offen ist.

    Das ist bewusst ein harter Abbruch und keine Warnung: die Folge eines
    grossen Modus ist ein Sensor, der bis zum Reboot keinen Stream mehr
    aufsetzt. Auf einem Laborrechner ist das teuer genug, um es nicht von
    einer uebersehenen Zeile auf stderr abhaengen zu lassen. Am 2026-09-22
    genau so passiert.
    """
    if args.source != "camera" or args.allow_large_sensor_mode:
        return
    width, _, height = args.camera_size.partition("x")
    try:
        pixels = int(width) * int(height)
    except ValueError:
        parser.error(f"--camera-size muss die Form BxH haben, nicht {args.camera_size!r}")
    if pixels > LARGE_SENSOR_MODE_PIXELS:
        parser.error(
            f"--camera-size {args.camera_size} ist ein grosser Sensormodus. Laut OQ-22 "
            "(docs/open-questions.md) war jede protokollierte Sitzung mit einem solchen "
            "Modus die letzte des Boots - danach setzt der Sensor keinen Stream mehr auf "
            "und nur ein Reboot hilft. Nimm 960x720 (mehr Ziffernhoehe ueber ScalerCrop) "
            "oder setze --allow-large-sensor-mode, wenn du das bewusst in Kauf nimmst."
        )


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
    out_path: Path,
    stop_event: threading.Event,
    ready_event: threading.Event,
    state: dict[str, Any],
    *,
    commands_path: Path | None = None,
    norm_schedule: list[tuple[float, float]] | None = None,
    restore_point: dict | None = None,
    ignore_restore_point_mismatch: bool = False,
) -> None:
    """Liest zeilenweise, sendet nichts. Signalisiert `ready_event`, sobald
    der Port entweder offen ist oder das Oeffnen endgueltig fehlgeschlagen
    ist - der Aufrufer wartet darauf, bevor er die Bildaufnahme startet."""
    import serial

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

    f_cmd = None
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
            f_cmd.close()
            try:
                ser.close()
            except Exception:  # noqa: BLE001
                pass
            ready_event.set()
            return
        if not matches and ignore_restore_point_mismatch:
            precheck_detail["ignored"] = True

    ready_event.set()
    count = 0
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

    try:
        with open(out_path, "a", encoding="utf-8") as f:
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
                f.write(json.dumps({"t_boot": t_boot, "text": text}, ensure_ascii=False) + "\n")
                f.flush()
                count += 1
    finally:
        if norm_schedule is not None and f_cmd is not None:
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
            finally:
                f_cmd.close()
        try:
            ser.close()
        except Exception:  # noqa: BLE001 - Aufraeumen, kein neuer Fehler beim Beenden
            pass
        state["count"] = count


# --- Bildstrom ---------------------------------------------------------------


def _synthetic_frames(uri: str):
    """`Frame`-Objekte aus `dispread.frames.open_source`, roh durchgereicht."""
    source = open_source(uri)
    source.open()
    try:
        for frame in source.frames():
            yield frame.image, frame.capture_timestamp.to_dict()
    finally:
        source.close()


def _camera_frames(size: tuple[int, int], fps: float):
    """Echte Kamera - lazy Import, siehe CLAUDE.md.

    Feldbehandlung ist `Controller._capture` nachgebildet (controller.py
    ~Zeile 1515), **und die Konfiguration ebenfalls** (~Zeile 1638). Das ist
    kein Schoenheitsdetail:

    Die erste Fassung nahm `create_still_configuration`. Am echten IMX500
    liefert das ueber zwei Minuten **kein einziges Bild** - der Standbildpfad
    ist auf Einzelaufnahmen ausgelegt, nicht auf einen Dauerlauf, und der
    Sensor laeuft bei voller Aufloesung mit 10 fps. Gemessen am 2026-09-22:
    serieller Strom lief, `frames.jsonl` blieb leer.

    `create_video_configuration` ist der im Repo erprobte Streaming-Pfad; mit
    ihm sind die 88 Bestandsproben aufgenommen worden. `format="RGB888"` und
    die gesetzte `FrameRate` gehoeren dazu - ohne das Format liefert
    `make_array("main")` eine andere Kanalanordnung als der Rest der Kette
    erwartet. `queue=False` verhindert, dass ein gepuffertes altes Bild
    ausgeliefert wird; fuer eine Zeitversatzmessung waere genau das fatal.
    """
    from picamera2 import Picamera2

    camera = Picamera2()
    try:
        config = camera.create_video_configuration(
            main={"size": size, "format": "RGB888"},
            controls={"FrameRate": fps} if fps > 0 else {},
            queue=False,
        )
        camera.configure(config)
        camera.start(show_preview=False)
        while True:
            request = camera.capture_request(wait=2.0)
            try:
                image = request.make_array("main").copy()
                raw_metadata = request.get_metadata()
            finally:
                request.release()
            # Nur JSON-faehige echte Metadaten; SensorTimestamp unveraendert -
            # deckungsgleich mit Controller._capture.
            metadata = {k: v for k, v in raw_metadata.items() if isinstance(v, (str, bool, int, float))}
            timestamp = Timestamp(
                value_ns=int(metadata.get("SensorTimestamp", 0)),
                base=TimeBaseKind.SENSOR_BOOTTIME,
                semantics=TimestampSemantics.UNKNOWN,
                uncertainty_ns=None,
            )
            yield image, timestamp.to_dict()
    finally:
        camera.stop()


def _frame_generator(args: argparse.Namespace):
    if args.source == "synthetic":
        yield from _synthetic_frames(args.synthetic_uri)
    else:
        w, _, h = args.camera_size.partition("x")
        yield from _camera_frames((int(w), int(h)), args.frame_rate)


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

    stop_event = threading.Event()
    ready_event = threading.Event()
    serial_state: dict[str, Any] = {"count": 0, "open_error": None}

    serial_thread = threading.Thread(
        target=_serial_worker,
        args=(args.port, args.baudrate, serial_jsonl, stop_event, ready_event, serial_state),
        kwargs={
            "commands_path": commands_jsonl,
            "norm_schedule": args.norm_schedule,
            "restore_point": restore_point,
            "ignore_restore_point_mismatch": args.ignore_restore_point_mismatch,
        },
        name="serial-reader",
        daemon=True,
    )
    serial_thread.start()

    if not ready_event.wait(timeout=READY_TIMEOUT_S):
        print(
            f"Fehler: serieller Lesethread meldete sich nicht innerhalb {READY_TIMEOUT_S}s",
            file=sys.stderr,
        )
        stop_event.set()
        return 1
    if serial_state["open_error"]:
        print(
            f"Fehler: serieller Port {args.port!r} konnte nicht geoeffnet werden: "
            f"{serial_state['open_error']}",
            file=sys.stderr,
        )
        stop_event.set()
        serial_thread.join(timeout=JOIN_TIMEOUT_S)
        return 1
    if serial_state.get("schedule_error"):
        print(f"Fehler: {serial_state['schedule_error']}", file=sys.stderr)
        stop_event.set()
        serial_thread.join(timeout=JOIN_TIMEOUT_S)
        return 1

    frame_period_s = 1.0 / args.frame_rate if args.frame_rate > 0 else 0.0
    ext = "png" if args.image_format == "png" else "jpg"

    frames_recorded = 0
    aborted = False
    abort_reason: str | None = None
    start_mono = time.monotonic()
    next_due = start_mono

    try:
        with open(frames_jsonl, "a", encoding="utf-8") as f_frames:
            for image, timestamp_dict in _frame_generator(args):
                now = time.monotonic()
                if now - start_mono >= args.duration:
                    break
                frames_recorded += 1
                filename = f"frame_{frames_recorded:06d}.{ext}"
                cv2.imwrite(str(frames_dir / filename), image)
                entry = {
                    "file": filename,
                    "frame_sequence": frames_recorded,
                    "capture_timestamp": timestamp_dict,
                }
                f_frames.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f_frames.flush()

                if frame_period_s > 0:
                    next_due += frame_period_s
                    sleep_for = next_due - time.monotonic()
                    if sleep_for > 0:
                        time.sleep(sleep_for)
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
        # Bei --norm-schedule laeuft hier noch die Rueckstellung im
        # finally-Block des Lesethreads (siehe _serial_worker) - deshalb
        # JOIN_TIMEOUT_S grosszuegig bemessen, nicht das kurze Portoeffnen.
        serial_thread.join(timeout=JOIN_TIMEOUT_S)

        serial_lines_recorded = serial_state.get("count", 0)
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
        }
        session_json.write_text(json.dumps(session, indent=2, ensure_ascii=False, default=_json_default))

    if serial_state.get("read_error"):
        print(f"Warnung: serielles Lesen beendet mit Fehler: {serial_state['read_error']}", file=sys.stderr)

    if serial_state.get("count", 0) == 0:
        print(
            "WARNUNG: In der gesamten Aufzeichnung wurde kein einziges Telegramm "
            f"empfangen (Dauer={args.duration}s, Port={args.port!r}, Baudrate={args.baudrate}). "
            "serial.jsonl ist leer - das ist eine Meldung, kein stiller Erfolg.",
            file=sys.stderr,
        )

    print(
        f"Fertig: {frames_recorded} Bilder, {serial_state.get('count', 0)} Telegrammzeilen, "
        f"{'ABGEBROCHEN' if aborted else 'vollstaendig'} -> {output_dir}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
