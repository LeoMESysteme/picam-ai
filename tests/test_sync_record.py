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
