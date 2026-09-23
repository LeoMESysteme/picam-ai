"""`scripts/sync-record.py`, `--source synthetic` als Subprozess (Task E aus
docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md).

Muster aus tests/test_dataset_benchmark.py (CLI als eigener Prozess) fuer den
Bildteil, und aus tests/test_gate_und_referenz.py (`os.openpty()`) fuer den
seriellen Teil - KEIN echter serieller Port wird geoeffnet, kein Byte an ein
echtes Geraet gesendet. `/dev/ttyUSB0` bleibt fuer die laufende Messung eines
anderen Prozesses unberuehrt.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "sync-record.py"


def _feed_pty(master_fd: int, lines: list[bytes], *, interval_s: float, stop_after: threading.Event) -> None:
    """Schreibt `lines` zyklisch auf die Masterseite des Pseudo-Terminals,
    bis `stop_after` gesetzt wird - simuliert das GSV-Telegramm."""
    i = 0
    while not stop_after.is_set():
        os.write(master_fd, lines[i % len(lines)])
        i += 1
        time.sleep(interval_s)


def _run_cli(*, duration, output, port, baudrate=9600, extra_args=()):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--duration",
            str(duration),
            "--output",
            str(output),
            "--source",
            "synthetic",
            "--synthetic-uri",
            "synthetic://seven-seg?digits=4&decimals=2&count=200",
            "--frame-rate",
            "20",
            "--port",
            port,
            "--baudrate",
            str(baudrate),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_synthetischer_lauf_schreibt_vollstaendige_und_gueltige_sitzung(tmp_path):
    master, slave = os.openpty()
    stop_feed = threading.Event()
    feeder = threading.Thread(
        target=_feed_pty,
        args=(master, [b"+0.46776 mV/V\r\n", b"+0.46781 mV/V\r\n"]),
        kwargs={"interval_s": 0.05, "stop_after": stop_feed},
        daemon=True,
    )
    feeder.start()
    output_dir = tmp_path / "lauf1"
    try:
        completed = _run_cli(duration=1.0, output=output_dir, port=os.ttyname(slave))
    finally:
        stop_feed.set()
        feeder.join(timeout=2.0)
        os.close(master)
        os.close(slave)

    assert completed.returncode == 0, completed.stdout + completed.stderr

    assert (output_dir / "serial.jsonl").is_file()
    assert (output_dir / "frames.jsonl").is_file()
    assert (output_dir / "frames").is_dir()
    assert (output_dir / "session.json").is_file()

    frame_files = sorted((output_dir / "frames").iterdir())
    frame_lines = (output_dir / "frames.jsonl").read_text().splitlines()
    assert len(frame_files) > 0
    assert len(frame_lines) == len(frame_files)

    for line in frame_lines:
        entry = json.loads(line)
        assert (output_dir / "frames" / entry["file"]).is_file()
        ts = entry["capture_timestamp"]
        assert set(ts) == {"value_ns", "base", "semantics", "uncertainty_ns"}
        assert ts["base"] == "synthetic"

    serial_lines = (output_dir / "serial.jsonl").read_text().splitlines()
    assert len(serial_lines) > 0
    for line in serial_lines:
        entry = json.loads(line)
        assert set(entry) == {"t_boot", "text"}
        assert isinstance(entry["t_boot"], float)
        assert "mV/V" in entry["text"]

    session = json.loads((output_dir / "session.json").read_text())
    for field in (
        "started_at_utc",
        "started_at_boottime_ns",
        "duration_s",
        "elapsed_s",
        "args",
        "port",
        "baudrate",
        "source",
        "frames_recorded",
        "serial_lines_recorded",
        "aborted",
        "abort_reason",
    ):
        assert field in session, field
    assert session["aborted"] is False
    assert session["abort_reason"] is None
    assert session["frames_recorded"] == len(frame_files)
    assert session["serial_lines_recorded"] == len(serial_lines)
    assert session["source"] == "synthetic"


def test_keine_telegramme_wird_am_ende_deutlich_gemeldet(tmp_path):
    """Schutzklausel aus dem Auftrag: kommt ueber die Dauer kein einziges
    Telegramm, muss das gemeldet werden statt stillschweigend eine leere
    serial.jsonl zu hinterlassen."""
    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-leer"
    try:
        completed = _run_cli(duration=0.6, output=output_dir, port=os.ttyname(slave))
    finally:
        os.close(master)
        os.close(slave)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "kein einziges Telegramm" in completed.stderr

    session = json.loads((output_dir / "session.json").read_text())
    assert session["serial_lines_recorded"] == 0
    assert (output_dir / "serial.jsonl").is_file()
    assert (output_dir / "serial.jsonl").read_text() == ""


def test_ctrl_c_hinterlaesst_vollstaendige_gueltige_sitzung(tmp_path):
    """Ctrl-C (SIGINT) waehrend der Aufzeichnung: beide JSONL-Dateien bleiben
    gueltig, session.json wird trotzdem geschrieben und markiert den
    Abbruch."""
    master, slave = os.openpty()
    stop_feed = threading.Event()
    feeder = threading.Thread(
        target=_feed_pty,
        args=(master, [b"+0.46776 mV/V\r\n"]),
        kwargs={"interval_s": 0.05, "stop_after": stop_feed},
        daemon=True,
    )
    feeder.start()
    output_dir = tmp_path / "lauf-abbruch"

    proc = subprocess.Popen(
        [
            sys.executable,
            str(SCRIPT),
            "--duration",
            "30",
            "--output",
            str(output_dir),
            "--source",
            "synthetic",
            "--synthetic-uri",
            "synthetic://seven-seg?digits=4&decimals=2",
            "--frame-rate",
            "20",
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        # Warten, bis der Import (cv2/numpy) fertig ist und die erste Zeile
        # geschrieben wurde - SIGINT waehrend des Imports selbst ist eine
        # Racebedingung des Tests, kein Skriptfehler.
        deadline = time.monotonic() + 15.0
        frames_jsonl = output_dir / "frames.jsonl"
        while time.monotonic() < deadline:
            if frames_jsonl.is_file() and frames_jsonl.stat().st_size > 0:
                break
            time.sleep(0.05)
        else:
            pytest.fail("frames.jsonl blieb leer - Skript kam nicht zum Laufen")
        proc.send_signal(signal.SIGINT)
        stdout, stderr = proc.communicate(timeout=10)
    finally:
        stop_feed.set()
        feeder.join(timeout=2.0)
        os.close(master)
        os.close(slave)

    assert proc.returncode == 0, stdout + stderr

    session = json.loads((output_dir / "session.json").read_text())
    assert session["aborted"] is True
    assert session["abort_reason"] is not None

    # Beide JSONL-Dateien muessen bis zum letzten geschriebenen Byte gueltig
    # sein (zeilenweise geflusht) - jede Zeile ist fuer sich gueltiges JSON.
    for name in ("frames.jsonl", "serial.jsonl"):
        for line in (output_dir / name).read_text().splitlines():
            json.loads(line)


@pytest.mark.parametrize("bad_port", ["/dev/nonexistent-tty-fuer-diesen-test"])
def test_nicht_oeffenbarer_port_bricht_sofort_klar_ab(tmp_path, bad_port):
    output_dir = tmp_path / "lauf-fehler"
    completed = _run_cli(duration=1.0, output=output_dir, port=bad_port)
    assert completed.returncode == 1
    assert "konnte nicht geoeffnet werden" in completed.stderr


def test_sigterm_hinterlaesst_vollstaendige_gueltige_sitzung(tmp_path):
    """Bisher: SIGTERM toetete den Prozess ohne session.json, nur SIGINT lief
    durch den sauberen Abbruchpfad. SIGTERM muss jetzt denselben Pfad nehmen."""
    master, slave = os.openpty()
    stop_feed = threading.Event()
    feeder = threading.Thread(
        target=_feed_pty,
        args=(master, [b"+0.46776 mV/V\r\n"]),
        kwargs={"interval_s": 0.05, "stop_after": stop_feed},
        daemon=True,
    )
    feeder.start()
    output_dir = tmp_path / "lauf-sigterm"

    proc = subprocess.Popen(
        [
            sys.executable,
            str(SCRIPT),
            "--duration",
            "30",
            "--output",
            str(output_dir),
            "--source",
            "synthetic",
            "--synthetic-uri",
            "synthetic://seven-seg?digits=4&decimals=2",
            "--frame-rate",
            "20",
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 15.0
        frames_jsonl = output_dir / "frames.jsonl"
        while time.monotonic() < deadline:
            if frames_jsonl.is_file() and frames_jsonl.stat().st_size > 0:
                break
            time.sleep(0.05)
        else:
            pytest.fail("frames.jsonl blieb leer - Skript kam nicht zum Laufen")
        proc.send_signal(signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=10)
    finally:
        stop_feed.set()
        feeder.join(timeout=2.0)
        os.close(master)
        os.close(slave)

    assert proc.returncode == 0, stdout + stderr

    session = json.loads((output_dir / "session.json").read_text())
    assert session["aborted"] is True
    assert session["abort_reason"] == "SIGTERM"

    for name in ("frames.jsonl", "serial.jsonl"):
        for line in (output_dir / name).read_text().splitlines():
            json.loads(line)


# --- --norm-schedule: Schreiben INNERHALB der bereits offenen Sitzung -------

RESTORE_POINT_PATH = Path(__file__).parents[1] / "var/diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json"
RESTORE_NORM_BYTES = (80, 27, 228)  # entspricht norm=1.0, siehe RESTORE_POINT_PATH
RESTORE_DPOINT = 1


class _FakeGsvDevice:
    """Simulierter GSV-2AS auf der Masterseite eines `os.openpty()` - beant-
    wortet exakt die Befehle, die `_apply_norm_dpoint`/`_check_restore_point`
    in scripts/sync-record.py senden (siehe norm_sweep.py/gsv-registers.py):
    STOP/START/CLEAR, `set norm`(0x10)/`set dpoint`(0x11) mit `last error`
    (0x42)-Quittung, sowie die Leseregister `norm`(0x1A)/`dpoint`(0x1C) mit
    Semikolon-Praefix. Sendet Telegrammzeilen, solange der Strom laeuft."""

    def __init__(self, master_fd, *, norm_bytes=RESTORE_NORM_BYTES, dpoint=RESTORE_DPOINT):
        self.master_fd = master_fd
        self.norm_bytes = list(norm_bytes)
        self.dpoint = dpoint
        self.streaming = True
        self._stop = threading.Event()
        self._reader = threading.Thread(target=self._command_loop, daemon=True)
        self._writer = threading.Thread(target=self._telegram_loop, daemon=True)

    def start(self):
        self._reader.start()
        self._writer.start()

    def stop(self):
        self._stop.set()
        self._reader.join(timeout=2.0)
        self._writer.join(timeout=2.0)

    def _read_n(self, n):
        buf = b""
        while len(buf) < n and not self._stop.is_set():
            try:
                chunk = os.read(self.master_fd, n - len(buf))
            except OSError:
                return buf
            buf += chunk
        return buf

    def _command_loop(self):
        while not self._stop.is_set():
            cmd = self._read_n(1)
            if not cmd:
                continue
            byte = cmd[0]
            if byte == 0x23:  # STOP
                self.streaming = False
            elif byte == 0x24:  # START
                self.streaming = True
            elif byte == 0x25:  # CLEAR
                pass
            elif byte == 0x10:  # SET_NORM
                data = self._read_n(3)
                if len(data) == 3:
                    self.norm_bytes = list(data)
            elif byte == 0x11:  # SET_DPOINT
                data = self._read_n(1)
                if len(data) == 1:
                    self.dpoint = data[0]
            elif byte == 0x42:  # LAST_ERR
                self._write(bytes([0x3B, 0xA0]))
            elif byte == 0x1A:  # Register lesen: norm
                self._write(bytes([0x3B, *self.norm_bytes]))
            elif byte == 0x1C:  # Register lesen: dpoint
                self._write(bytes([0x3B, self.dpoint]))
            # andere Registerbefehle kommen in diesen Tests nicht vor.

    def _write(self, data: bytes) -> None:
        try:
            os.write(self.master_fd, data)
        except OSError:
            pass

    def _telegram_loop(self):
        i = 0
        while not self._stop.is_set():
            if self.streaming:
                self._write(f"+{1.0 + (i % 5) * 0.001:.5f} mV/V\r\n".encode("ascii"))
                i += 1
            time.sleep(0.03)


def test_norm_schedule_schreibt_commands_jsonl_und_stellt_zurueck(tmp_path):
    """Gluecklicher Fall: Geraet steht am Rueckstellpunkt, --norm-schedule
    laeuft, commands.jsonl bekommt Pause/Resume + Kommando/Antwort-Zeilen,
    und am Ende steht das (simulierte) Geraet wieder am Rueckstellpunkt."""
    master, slave = os.openpty()
    device = _FakeGsvDevice(master)
    device.start()
    output_dir = tmp_path / "lauf-schedule"
    try:
        completed = _run_cli(
            duration=2.0,
            output=output_dir,
            port=os.ttyname(slave),
            extra_args=[
                "--norm-schedule",
                "2.0:0.5,1.0:0.5",
                "--restore-point",
                str(RESTORE_POINT_PATH),
            ],
        )
    finally:
        device.stop()
        os.close(master)
        os.close(slave)

    assert completed.returncode == 0, completed.stdout + completed.stderr

    commands_jsonl = output_dir / "commands.jsonl"
    assert commands_jsonl.is_file()
    events = [json.loads(line) for line in commands_jsonl.read_text().splitlines()]
    assert events, "commands.jsonl ist leer"

    event_names = {e["event"] for e in events}
    assert {"pause_transmission", "resume_transmission", "command", "register_read"} <= event_names
    for event in events:
        assert isinstance(event["t_boot"], float)
    command_events = [e for e in events if e["event"] == "command"]
    assert command_events, "keine Kommando-Ereignisse geloggt"
    for event in command_events:
        assert event["response_tag"] == "non_telegram"
        assert "response_bytes" in event

    # Keine Kommandoantwort-Bytes duerfen als Telegramm gelandet sein.
    serial_lines = (output_dir / "serial.jsonl").read_text().splitlines()
    for line in serial_lines:
        entry = json.loads(line)
        assert "mV/V" in entry["text"]

    session = json.loads((output_dir / "session.json").read_text())
    assert session["transmission_paused_during_writes"] is True
    assert session["precheck"]["matches_restore_point"] is True
    assert session["restore_verification"]["write_ok"] is True
    assert session["restore_verification"]["matches_restore_point"] is True
    assert session["norm_schedule"] == [
        {"factor": 2.0, "hold_s": 0.5},
        {"factor": 1.0, "hold_s": 0.5},
    ]

    # Simuliertes Geraet steht am Ende wirklich wieder am Rueckstellpunkt.
    assert device.norm_bytes == list(RESTORE_NORM_BYTES)
    assert device.dpoint == RESTORE_DPOINT


def test_norm_schedule_lehnt_abweichenden_registerstand_ab(tmp_path):
    master, slave = os.openpty()
    device = _FakeGsvDevice(master, dpoint=RESTORE_DPOINT + 1)
    device.start()
    output_dir = tmp_path / "lauf-mismatch"
    try:
        completed = _run_cli(
            duration=1.0,
            output=output_dir,
            port=os.ttyname(slave),
            extra_args=[
                "--norm-schedule",
                "2.0:5",
                "--restore-point",
                str(RESTORE_POINT_PATH),
            ],
        )
    finally:
        device.stop()
        os.close(master)
        os.close(slave)

    assert completed.returncode == 1
    assert "Rueckstellpunkt" in completed.stderr
    assert not (output_dir / "commands.jsonl").is_file() or (
        # Falls angelegt: kein Schreibbefehl darf drinstehen.
        all(
            json.loads(line)["event"] != "command"
            for line in (output_dir / "commands.jsonl").read_text().splitlines()
        )
    )
    # Kein Schreibbefehl - das simulierte Geraet blieb unveraendert.
    assert device.dpoint == RESTORE_DPOINT + 1


def test_norm_schedule_mismatch_mit_override_laeuft_trotzdem(tmp_path):
    master, slave = os.openpty()
    device = _FakeGsvDevice(master, dpoint=RESTORE_DPOINT + 1)
    device.start()
    output_dir = tmp_path / "lauf-override"
    try:
        completed = _run_cli(
            duration=1.5,
            output=output_dir,
            port=os.ttyname(slave),
            extra_args=[
                "--norm-schedule",
                "2.0:0.5",
                "--restore-point",
                str(RESTORE_POINT_PATH),
                "--ignore-restore-point-mismatch",
            ],
        )
    finally:
        device.stop()
        os.close(master)
        os.close(slave)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    session = json.loads((output_dir / "session.json").read_text())
    assert session["precheck"]["matches_restore_point"] is False
    # Am Ende trotzdem zurueckgestellt.
    assert session["restore_verification"]["matches_restore_point"] is True
    assert device.norm_bytes == list(RESTORE_NORM_BYTES)
    assert device.dpoint == RESTORE_DPOINT


def test_ohne_norm_schedule_bleibt_verhalten_unveraendert(tmp_path):
    """Ohne --norm-schedule darf kein einziges Byte an den Port gehen und
    commands.jsonl darf nicht entstehen (Vorgabe 4 aus dem Auftrag)."""
    master, slave = os.openpty()
    stop_feed = threading.Event()
    feeder = threading.Thread(
        target=_feed_pty,
        args=(master, [b"+0.46776 mV/V\r\n"]),
        kwargs={"interval_s": 0.05, "stop_after": stop_feed},
        daemon=True,
    )
    feeder.start()
    output_dir = tmp_path / "lauf-ohne-schedule"
    try:
        completed = _run_cli(duration=1.0, output=output_dir, port=os.ttyname(slave))
    finally:
        stop_feed.set()
        feeder.join(timeout=2.0)
        os.close(master)
        os.close(slave)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert not (output_dir / "commands.jsonl").exists()
    session = json.loads((output_dir / "session.json").read_text())
    assert session["norm_schedule"] is None
    assert session["transmission_paused_during_writes"] is False
    assert session["precheck"] is None
    assert session["restore_verification"] is None
