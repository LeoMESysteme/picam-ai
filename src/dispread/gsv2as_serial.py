"""Belegte GSV-2AS-Kodierung und serielle Ablaeufe, ohne eigene Portoeffnung."""

import json
import math
import time
from pathlib import Path
from typing import Any

_sleep = time.sleep
DEFAULT_RESTORE_POINT = Path("var/diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json")

SEMICOLON = 0x3B

CMD_STOP = 0x23
CMD_START = 0x24
CMD_CLEAR = 0x25

#: Name -> (Befehlsbyte, Anzahl DATEN-Bytes laut Anleitung)
READ_COMMANDS: dict[str, tuple[int, int]] = {
    "norm": (0x1A, 3),
    "unit": (0x1B, 1),
    "dpoint": (0x1C, 1),
    "mode": (0x27, 1),
    "digits": (0x3E, 1),
    "range": (0x33, 1),
    "firmware": (0x2B, 2),
    "options": (0x36, 3),
    "bridge_type": (0x31, 1),
    "device_type": (0x45, 1),
    "last_error": (0x42, 1),
}


NORM_MIN, NORM_MAX = 0.15, 1_580_000.0
SET_NORM_CMD = 0x10
SET_DPOINT_CMD = 0x11
LAST_ERR_CMD = READ_COMMANDS["last_error"][0]
OK_ERROR_CODE = 0xA0


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
    _sleep(sleep_s)


def _read_exact(ser, count: int, timeout_s: float = 1.0) -> bytes:
    """Wie `gsv-registers.py::_read_exact` / `norm_sweep.py::read_exact`."""
    deadline = time.monotonic() + timeout_s
    buf = b""
    while len(buf) < count and time.monotonic() < deadline:
        chunk = ser.read(count - len(buf))
        if chunk:
            buf += chunk
    return buf


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
    norm_cmd, norm_len = READ_COMMANDS["norm"]
    dpoint_cmd, dpoint_len = READ_COMMANDS["dpoint"]
    norm_entry = read_register(ser, "norm", norm_cmd, norm_len)
    _log_event(f_cmd, state, {"event": "register_read", "label": label, "register": "norm",
                               "response_tag": "non_telegram", **norm_entry})
    dpoint_entry = read_register(ser, "dpoint", dpoint_cmd, dpoint_len)
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
    _send(ser, CMD_STOP, 0.3)
    _send(ser, CMD_CLEAR, 0.2)
    ser.reset_input_buffer()
    _log_event(f_cmd, state, {"event": "pause_transmission", "label": label, "t_boot": t_pause})

    norm_entry, dpoint_entry = _read_norm_dpoint(ser, f_cmd, state, label=label)

    _send(ser, CMD_START, 0.8)
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
    _send(ser, CMD_STOP, 0.25)
    _send(ser, CMD_CLEAR, 0.15)
    ser.reset_input_buffer()
    _log_event(f_cmd, state, {"event": "pause_transmission", "label": label, "t_boot": t_pause})

    ser.write(bytes([SET_NORM_CMD, *norm_bytes]))
    ser.flush()
    _sleep(0.35)
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
    _sleep(0.35)
    ser.reset_input_buffer()
    ser.write(bytes([LAST_ERR_CMD]))
    ser.flush()
    resp_dpoint = _read_exact(ser, 2)
    _log_event(f_cmd, state, {
        "event": "command", "label": label, "command_name": "set_dpoint",
        "command_bytes": [SET_DPOINT_CMD, dpoint_byte],
        "response_bytes": list(resp_dpoint), "response_tag": "non_telegram",
    })

    _send(ser, CMD_START, 0.7)
    t_resume = time.clock_gettime(time.CLOCK_BOOTTIME)
    _log_event(f_cmd, state, {"event": "resume_transmission", "label": label, "t_boot": t_resume})

    ok_norm = len(resp_norm) == 2 and resp_norm[1] == OK_ERROR_CODE
    ok_dpoint = len(resp_dpoint) == 2 and resp_dpoint[1] == OK_ERROR_CODE
    return ok_norm and ok_dpoint


def read_register(ser, name: str, command: int, data_len: int) -> dict:
    ser.reset_input_buffer()
    ser.write(bytes([command]))
    ser.flush()
    raw = _read_exact(ser, 1 + data_len)
    entry: dict = {"command": command, "expected_data_bytes": data_len, "rohantwort": list(raw)}
    if len(raw) != 1 + data_len:
        entry["fehler"] = f"nur {len(raw)} von {1 + data_len} Bytes erhalten"
        return entry
    if raw[0] != SEMICOLON:
        entry["fehler"] = f"erwartetes Semikolon-Praefix 0x3B fehlt, erstes Byte war 0x{raw[0]:02X}"
        return entry
    entry["daten"] = list(raw[1:])
    return entry

