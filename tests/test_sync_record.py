"""`scripts/sync-record.py`, `--source synthetic` als Subprozess (Task E aus
docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md).

Muster aus tests/test_dataset_benchmark.py (CLI als eigener Prozess) fuer den
Bildteil, und aus tests/test_gate_und_referenz.py (`os.openpty()`) fuer den
seriellen Teil - KEIN echter serieller Port wird geoeffnet, kein Byte an ein
echtes Geraet gesendet. `/dev/ttyUSB0` bleibt fuer die laufende Messung eines
anderen Prozesses unberuehrt.
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from dispread.frames.types import Frame
from dispread.records import TimeBaseKind, Timestamp, TimestampSemantics

SCRIPT = Path(__file__).parents[1] / "scripts" / "sync-record.py"


def _load_sync_record_module():
    """`sync-record.py` fuer In-Prozess-Tests laden (Bindestrich im Namen -
    kein normaler `import`), wie das Skript selbst es mit
    `gsv-registers.py` macht. Fuer den Kamera-Zweig gebraucht: `module.UvcSource`
    laesst sich per Monkeypatch durch eine Fake-Klasse ersetzen (`UvcSource`
    ist am Modulanfang importiert) - als Subprozess ginge das nicht ohne
    eine echte Kamera."""
    spec = importlib.util.spec_from_file_location("_sync_record_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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


def test_frames_jsonl_hat_sensor_sequence_und_intervall_felder(tmp_path):
    """End-zu-Ende ueber `--source synthetic`: `sensor_sequence` ist bei
    synthetischen Bildern immer `null` (nicht anwendbar), aber das Feld
    existiert, und `sensor_timestamp_interval_ns` ist beim ersten Bild
    `null` und danach die Differenz aufeinanderfolgender `value_ns`."""
    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-felder"
    try:
        completed = _run_cli(duration=0.5, output=output_dir, port=os.ttyname(slave))
    finally:
        os.close(master)
        os.close(slave)

    assert completed.returncode == 0, completed.stdout + completed.stderr

    lines = [json.loads(line) for line in (output_dir / "frames.jsonl").read_text().splitlines()]
    assert len(lines) > 1
    assert lines[0]["sensor_sequence"] is None
    assert lines[0]["sensor_timestamp_interval_ns"] is None
    prev_value_ns = lines[0]["capture_timestamp"]["value_ns"]
    for entry in lines[1:]:
        assert entry["sensor_sequence"] is None
        value_ns = entry["capture_timestamp"]["value_ns"]
        assert entry["sensor_timestamp_interval_ns"] == value_ns - prev_value_ns
        prev_value_ns = value_ns

    session = json.loads((output_dir / "session.json").read_text())
    for field in ("max_loop_iteration_s", "stall_iteration_count", "stall_iterations"):
        assert field in session, field
    assert session["max_loop_iteration_s"] >= 0.0
    assert session["stall_iteration_count"] == len(session["stall_iterations"])


# --- Erzeuger/Schreiber-Trennung: ein langsamer Schreiber darf die ---------
# --- aufgezeichneten Zeitstempel nicht verfaelschen (Scope-Erweiterung, ----
# --- Orchestrator 2026-09-23, Root-Cause siehe Moduldocstring) -------------


def test_serieller_schreiber_verzoegerung_beeinflusst_leseintervalle_nicht(monkeypatch, tmp_path):
    """Ein 1s-Stau beim ERSTEN Schreiben nach serial.jsonl (simuliert das
    gemessene Dirty-Page-Writeback) darf die aufgezeichneten `t_boot`-Werte
    nicht verzerren - sie werden beim LESEN gestempelt (`_serial_worker`),
    nicht beim Schreiben (`_serial_writer_worker`), verbunden nur ueber die
    Warteschlange. Vorher (ungetrennt) haette ein solcher Stau exakt den
    beobachteten Burst erzeugt (Intervalle 2384, 0, 0, 0, 283ms statt
    533ms, siehe docs/open-questions.md OQ-40-Nachtrag)."""
    module = _load_sync_record_module()

    real_dumps = module.json.dumps
    call_count = {"n": 0}

    class _SlowJson:
        @staticmethod
        def dumps(obj, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                time.sleep(1.0)
            return real_dumps(obj, **kwargs)

    monkeypatch.setattr(module, "json", _SlowJson())

    master, slave = os.openpty()
    stop_feed = threading.Event()
    interval_s = 0.1
    feeder = threading.Thread(
        target=_feed_pty,
        args=(master, [b"+1.00000 mV/V\r\n"]),
        kwargs={"interval_s": interval_s, "stop_after": stop_feed},
        daemon=True,
    )
    feeder.start()

    serial_queue = module.queue.Queue()
    stop_event = threading.Event()
    ready_event = threading.Event()
    serial_state: dict = {"count": 0, "open_error": None}
    serial_writer_state: dict = {"count": 0}
    out_path = tmp_path / "serial.jsonl"

    reader = threading.Thread(
        target=module._serial_worker,
        args=(os.ttyname(slave), 9600, serial_queue, stop_event, ready_event, serial_state),
        daemon=True,
    )
    writer = threading.Thread(
        target=module._serial_writer_worker,
        args=(serial_queue, out_path, serial_writer_state),
        daemon=True,
    )
    try:
        writer.start()
        reader.start()
        assert ready_event.wait(timeout=5.0)
        # Genug Telegramme trotz der 1s-Schreibverzoegerung beim ersten Schreiben.
        time.sleep(1.5)
        stop_event.set()
        reader.join(timeout=5.0)
        writer.join(timeout=5.0)
    finally:
        stop_feed.set()
        feeder.join(timeout=2.0)
        os.close(master)
        os.close(slave)

    lines = [json.loads(line) for line in out_path.read_text().splitlines()]
    assert len(lines) >= 5, "zu wenige Telegramme aufgezeichnet - Test aussagelos"
    t_boots = [entry["t_boot"] for entry in lines]
    intervals = [b - a for a, b in zip(t_boots, t_boots[1:], strict=False)]
    # Nominale Taktung 0.1s - trotz der 1s-Schreibverzoegerung darf kein
    # Intervall in die Naehe von 1s kommen (das waere der alte Burst-Fehler).
    assert max(intervals) < 0.3, intervals


def test_volle_frame_queue_verwirft_und_zaehlt_statt_zu_blockieren(monkeypatch, tmp_path):
    """`--frame-queue-size` klein + durchgehend langsamer Schreiber: die
    Warteschlange laeuft ueber. Verworfene Bilder muessen GEZAEHLT
    (`frames_dropped_queue_full`) und als eigener `frames.jsonl`-Eintrag
    (`dropped: true`) sichtbar werden - nie still verschwinden, nie die
    Aufnahme blockieren (Auftrag, Punkt 4)."""
    module = _load_sync_record_module()

    real_imwrite = module.cv2.imwrite

    class _SlowCv2:
        @staticmethod
        def imwrite(path, image):
            time.sleep(0.2)
            return real_imwrite(path, image)

    monkeypatch.setattr(module, "cv2", _SlowCv2())

    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-volle-queue"
    args = module.parse_args(
        [
            "--duration",
            "1.0",
            "--output",
            str(output_dir),
            "--source",
            "synthetic",
            "--synthetic-uri",
            "synthetic://seven-seg?digits=4&decimals=2&count=200",
            "--frame-rate",
            "100",
            "--frame-queue-size",
            "2",
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
        ]
    )
    try:
        returncode = module.run(args)
    finally:
        os.close(master)
        os.close(slave)

    assert returncode == 0

    lines = [json.loads(line) for line in (output_dir / "frames.jsonl").read_text().splitlines()]
    dropped = [entry for entry in lines if entry.get("dropped")]
    written = [entry for entry in lines if not entry.get("dropped")]
    assert dropped, "bei --frame-queue-size 2 und 100fps gegen einen 0.2s-Schreiber muss verworfen werden"
    for entry in dropped:
        assert set(entry) == {"dropped", "sensor_sequence", "capture_timestamp", "t_boot"}
        assert entry["dropped"] is True

    session = json.loads((output_dir / "session.json").read_text())
    assert session["frames_dropped_queue_full"] == len(dropped)
    assert session["frames_dropped_queue_full"] > 0
    assert session["frames_recorded"] == len(written)
    assert session["max_frame_queue_depth"] <= 2


def test_bild_schreiber_verzoegerung_beeinflusst_aufnahmeintervalle_nicht(monkeypatch, tmp_path):
    """Wie oben, fuer die Bildseite: ein 1s-Stau beim ERSTEN `cv2.imwrite`
    darf weder die aufgezeichneten Bildintervalle noch die
    Stall-Diagnostik (`max_loop_iteration_s`/`stall_iteration_count`)
    verfaelschen - Aufnahme (`_frame_acquisition_worker`) und Schreiben
    (`_frame_writer_worker`) sind ueber `frame_queue` entkoppelt."""
    module = _load_sync_record_module()

    real_imwrite = module.cv2.imwrite
    call_count = {"n": 0}

    class _SlowCv2:
        @staticmethod
        def imwrite(path, image):
            call_count["n"] += 1
            if call_count["n"] == 1:
                time.sleep(1.0)
            return real_imwrite(path, image)

    monkeypatch.setattr(module, "cv2", _SlowCv2())

    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-langsamer-schreiber"
    args = module.parse_args(
        [
            "--duration",
            "1.5",
            "--output",
            str(output_dir),
            "--source",
            "synthetic",
            "--synthetic-uri",
            "synthetic://seven-seg?digits=4&decimals=2&count=200",
            "--frame-rate",
            "20",
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
        ]
    )
    try:
        returncode = module.run(args)
    finally:
        os.close(master)
        os.close(slave)

    assert returncode == 0

    lines = [json.loads(line) for line in (output_dir / "frames.jsonl").read_text().splitlines()]
    assert len(lines) >= 10, "zu wenige Bilder aufgezeichnet - Test aussagelos"
    intervals_ns = [
        entry["sensor_timestamp_interval_ns"] for entry in lines if entry["sensor_timestamp_interval_ns"] is not None
    ]
    assert intervals_ns
    # Nominale Taktung 50ms (20 fps) - trotz der 1s-Schreibverzoegerung darf
    # kein aufgezeichnetes Intervall in die Naehe von 1s kommen.
    assert max(intervals_ns) < 300_000_000, intervals_ns

    session = json.loads((output_dir / "session.json").read_text())
    # Die Stall-Diagnostik wird im Aufnahmethread gemessen (entkoppelt von
    # der Schreibseite) - der 1s-Schreibstau darf dort NICHT auftauchen.
    assert session["stall_iteration_count"] == 0, session["stall_iterations"]
    assert session["max_loop_iteration_s"] < 0.3
    assert session["frames_dropped_queue_full"] == 0


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




# --- --source camera: Fake `UvcSource`, kein Hardwarebedarf (StreamCam) -----
#
# Ersetzt den frueheren Picamera2-Fake (IMX500 ausser Betrieb seit
# 2026-09-25, siehe docs/project_history.md). `module.UvcSource` wird per
# Monkeypatch durch `_FakeUvcSource` ersetzt - kein echtes `/dev/video*`,
# kein `v4l2-ctl`.


def _camera_settings_payload(**overrides) -> dict:
    camera = {
        "model": "logitech_streamcam",
        "usb_id": "046d:0893",
        "size": [640, 480],
        "fourcc": "MJPG",
        "fps": 30,
        "controls": {
            "focus_absolute": 0,
            "exposure_time_absolute": 156,
            "white_balance_temperature": 4600,
            "gain": 32,
        },
    }
    camera.update(overrides)
    return {"camera": camera}


def _write_camera_settings(path: Path, **overrides) -> Path:
    path.write_text(json.dumps(_camera_settings_payload(**overrides)), encoding="utf-8")
    return path


class _FakeUvcSource:
    """Fake fuer `UvcSource` (Interfaces: `open()`/`close()`/`frames()`/
    `describe()`, Attribute `read_error`/`rejected_timestamps`). Liefert
    `frame_count` `Frame`s mit aufsteigendem `v4l2_monotonic`-Zeitstempel im
    festen Abstand `interval_ns`; `sensor_sequence` gibt es bei der
    StreamCam nicht, das bildet `_uvc_frames` selbst als `None` ab (nicht
    Teil dieses Fakes).

    `open_error`: wird in `open()` geworfen (z.B. ein `UvcError`), bevor
    `self.device` gesetzt wird - wie am echten `UvcSource` bei einem
    abweichenden Regler-Ist-Wert.

    `hang_event`: wenn gesetzt, blockiert `frames()` NACH dem letzten Bild
    auf `hang_event.wait()` - simuliert einen haengenden Aufnahmethread
    (Review Focus 2), ohne echte Hardware.

    `read_error_after`: wenn gesetzt, endet `frames()` NACH dem letzten Bild
    regulaer (kein `raise`) und setzt vorher `self.read_error` auf diesen
    Text - genau der Vertrag des echten `UvcSource.frames()` bei einem
    Kameraausfall mitten in der Aufnahme (`READ_FAIL_TIMEOUT_S` ohne
    erfolgreiches Bild, siehe `src/dispread/frames/uvc_source.py`): der
    Generator endet normal, wirft NICHT (Review-Fund Fix-Runde 1)."""

    def __init__(
        self,
        settings,
        *,
        device=None,
        frame_count: int = 5,
        interval_ns: int = 33_000_000,
        open_error: Exception | None = None,
        hang_event: threading.Event | None = None,
        read_error_after: str | None = None,
    ) -> None:
        self.settings = settings
        self._device_arg = device
        self.device: str | None = None
        self._frame_count = frame_count
        self._interval_ns = interval_ns
        self._open_error = open_error
        self._hang_event = hang_event
        self._read_error_after = read_error_after
        self.read_error: str | None = None
        self.rejected_timestamps = 0
        self._sequence = 0

    def open(self) -> None:
        if self._open_error is not None:
            raise self._open_error
        self.device = self._device_arg or "/dev/video0"

    def close(self) -> None:
        pass

    def frames(self):
        value_ns = 0
        for _ in range(self._frame_count):
            value_ns += self._interval_ns
            self._sequence += 1
            yield Frame(
                frame_sequence=self._sequence,
                image=np.zeros((4, 4, 3), dtype=np.uint8),
                capture_timestamp=Timestamp(
                    value_ns=value_ns,
                    base=TimeBaseKind.V4L2_MONOTONIC,
                    semantics=TimestampSemantics.UNKNOWN,
                    uncertainty_ns=None,
                ),
                source_id=f"v4l2:{self.device}",
            )
        if self._read_error_after is not None:
            self.read_error = self._read_error_after
            return
        if self._hang_event is not None:
            self._hang_event.wait()

    def describe(self) -> dict:
        return {
            "camera_model": self.settings.model,
            "device": self.device,
            "usb_id": self.settings.usb_id,
            "usb_speed_mbps": 5000,
            "size": list(self.settings.size),
            "fourcc": self.settings.fourcc,
            "fps": self.settings.fps,
            "controls_requested": dict(self.settings.ordered_controls()),
            "controls_readback": dict(self.settings.controls),
            "rejected_timestamps": self.rejected_timestamps,
            "read_error": self.read_error,
        }


def test_camera_ohne_camera_settings_bricht_ab(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--duration",
            "1.0",
            "--output",
            str(tmp_path / "lauf-ohne-settings"),
            "--source",
            "camera",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 2
    assert "--camera-settings" in completed.stderr


def test_measure_clock_offset_nimmt_median():
    """`clock` liefert je Einzelmessung `(m1, b, m2)` - mit `m1=m2=0` ist
    `b - (m1+m2)//2 == b`, die 5 Einzelwerte sind also direkt `[10, 12, 1000,
    11, 13]`. Median davon (sortiert `[10, 11, 12, 13, 1000]`) ist 12."""
    module = _load_sync_record_module()
    values = [10, 12, 1000, 11, 13]
    calls = []
    for v in values:
        calls.extend([0, v, 0])
    calls_iter = iter(calls)

    def _fake_clock(_clock_id):
        return next(calls_iter)

    result = module.measure_clock_offset_ns(samples=5, clock=_fake_clock)
    assert result == 12


def test_count_frame_gaps():
    """30 fps -> Schwelle 1,5 * 1e9/30 = 50ms. Eine eingestreute Luecke von
    100ms muss als genau eine Luecke zaehlen, mit `max_gap_ns == 100ms`."""
    module = _load_sync_record_module()
    interval_ns = round(1e9 / 30)
    timestamps = [0]
    for _ in range(5):
        timestamps.append(timestamps[-1] + interval_ns)
    timestamps.append(timestamps[-1] + 100_000_000)
    for _ in range(5):
        timestamps.append(timestamps[-1] + interval_ns)

    result = module.count_frame_gaps(timestamps, 30.0)
    assert result["count"] == 1
    assert result["max_gap_ns"] == 100_000_000
    assert result["threshold_ns"] == 1.5 * 1e9 / 30


def test_session_json_traegt_camera_versatz_und_gaps(monkeypatch, tmp_path):
    module = _load_sync_record_module()
    monkeypatch.setattr(
        module,
        "UvcSource",
        lambda settings, *, device=None: _FakeUvcSource(
            settings, device=device, frame_count=8, interval_ns=33_000_000
        ),
    )

    settings_path = _write_camera_settings(tmp_path / "camera-settings.json")
    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-kamera-versatz"
    args = module.parse_args(
        [
            "--duration",
            "1.0",
            "--output",
            str(output_dir),
            "--source",
            "camera",
            "--camera-settings",
            str(settings_path),
            "--frame-rate",
            "30",
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
        ]
    )
    try:
        returncode = module.run(args)
    finally:
        os.close(master)
        os.close(slave)

    assert returncode == 0
    session = json.loads((output_dir / "session.json").read_text())
    assert session["camera"]["camera_model"] == "logitech_streamcam"
    assert set(session["clock_offset_boottime_minus_monotonic_ns"]) == {"start", "end"}
    assert session["frame_gaps"]["count"] >= 0

    lines = [json.loads(line) for line in (output_dir / "frames.jsonl").read_text().splitlines()]
    assert lines
    for entry in lines:
        assert entry["capture_timestamp"]["base"] == "v4l2_monotonic"
        assert entry["sensor_sequence"] is None


def test_uvc_fehler_beim_oeffnen_ergibt_acquisition_error(monkeypatch, tmp_path):
    module = _load_sync_record_module()
    error = module.UvcError("focus_absolute: soll 48, ist 60")
    monkeypatch.setattr(
        module,
        "UvcSource",
        lambda settings, *, device=None: _FakeUvcSource(settings, device=device, open_error=error),
    )
    monkeypatch.setattr(module, "STARTUP_TIMEOUT_S", 1.0)

    settings_path = _write_camera_settings(tmp_path / "camera-settings.json")
    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-uvc-fehler"
    args = module.parse_args(
        [
            "--duration",
            "1.0",
            "--output",
            str(output_dir),
            "--source",
            "camera",
            "--camera-settings",
            str(settings_path),
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
        ]
    )
    try:
        returncode = module.run(args)
    finally:
        os.close(master)
        os.close(slave)

    assert returncode == module.EXIT_NO_FRAMES_ACQUIRED
    session = json.loads((output_dir / "session.json").read_text())
    assert "focus_absolute: soll 48, ist 60" in session["acquisition_error"]


def test_frames_recorded_stimmt_wenn_aufnahmethread_haengt(monkeypatch, tmp_path):
    """Review Focus 2 / Bildzaehler-Fix: haengt der Aufnahmethread NACH
    bereits gelieferten Bildern (kommt also nie `_QUEUE_DONE` an), muss
    `session["frames_recorded"]` trotzdem die Anzahl der tatsaechlich
    geschriebenen Bilder zeigen, nicht 0 - der Schreiberthread aktualisiert
    `state["frames_recorded"]` nach JEDEM Bild, nicht erst am Ende."""
    module = _load_sync_record_module()
    hang_event = threading.Event()
    monkeypatch.setattr(
        module,
        "UvcSource",
        lambda settings, *, device=None: _FakeUvcSource(
            settings, device=device, frame_count=5, interval_ns=10_000_000, hang_event=hang_event
        ),
    )
    monkeypatch.setattr(module, "JOIN_TIMEOUT_S", 0.5)
    monkeypatch.setattr(module, "WRITER_DRAIN_JOIN_TIMEOUT_S", 0.5)

    settings_path = _write_camera_settings(tmp_path / "camera-settings.json")
    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-haengender-aufnahmethread"
    args = module.parse_args(
        [
            "--duration",
            "1",
            "--output",
            str(output_dir),
            "--source",
            "camera",
            "--camera-settings",
            str(settings_path),
            "--frame-rate",
            "0",
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
        ]
    )
    try:
        module.run(args)
    finally:
        # Aufraeumen: der gefakte Aufnahmethread haengt in `frames()` auf
        # `hang_event.wait()` - erst jetzt (nach der Kernaussage des Tests)
        # freigeben, damit kein Thread ueber das Testende hinaus haengt.
        hang_event.set()
        os.close(master)
        os.close(slave)

    session = json.loads((output_dir / "session.json").read_text())
    assert session["frames_recorded"] == 5
    assert len(list((output_dir / "frames").iterdir())) == 5


def test_kameraausfall_mitten_in_der_aufnahme_setzt_acquisition_error(monkeypatch, tmp_path):
    """Review-Fund (Fix-Runde 1): `UvcSource.frames()` wirft bei einem
    Lesefehler NICHT - sie setzt `read_error` und beendet den Generator
    regulaer (`READ_FAIL_TIMEOUT_S` ohne Bild). Kamen vorher schon Bilder an,
    darf das nicht als stiller Erfolg durchgehen: `acquisition_error` muss
    den `read_error`-Text tragen, `frames_recorded` bleibt korrekt (die schon
    gelieferten Bilder), und der Lauf bleibt Exit 0 (ein Fehler NACH bereits
    aufgezeichneten Bildern ist eine Warnung, kein `EXIT_NO_FRAMES_ACQUIRED`
    - das bleibt dem reinen 0-Bilder-Befund vorbehalten)."""
    module = _load_sync_record_module()
    monkeypatch.setattr(
        module,
        "UvcSource",
        lambda settings, *, device=None: _FakeUvcSource(
            settings,
            device=device,
            frame_count=3,
            interval_ns=10_000_000,
            read_error_after="kein Bild innerhalb von READ_FAIL_TIMEOUT_S=2.0s",
        ),
    )

    settings_path = _write_camera_settings(tmp_path / "camera-settings.json")
    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-kameraausfall-mittendrin"
    args = module.parse_args(
        [
            "--duration",
            "1.0",
            "--output",
            str(output_dir),
            "--source",
            "camera",
            "--camera-settings",
            str(settings_path),
            "--frame-rate",
            "0",
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
        ]
    )
    try:
        returncode = module.run(args)
    finally:
        os.close(master)
        os.close(slave)

    assert returncode == 0
    session = json.loads((output_dir / "session.json").read_text())
    assert session["frames_recorded"] == 3
    assert session["acquisition_error"] is not None
    assert "kein Bild innerhalb von READ_FAIL_TIMEOUT_S=2.0s" in session["acquisition_error"]
    assert session["camera"]["read_error"] == "kein Bild innerhalb von READ_FAIL_TIMEOUT_S=2.0s"


def test_synthetic_traegt_versatz_und_keine_kamera(tmp_path):
    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-synthetic-versatz"
    try:
        completed = _run_cli(duration=0.3, output=output_dir, port=os.ttyname(slave))
    finally:
        os.close(master)
        os.close(slave)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    session = json.loads((output_dir / "session.json").read_text())
    assert session["camera"] is None
    assert set(session["clock_offset_boottime_minus_monotonic_ns"]) == {"start", "end"}
    assert "scaler_crop_actual" not in session
    assert "stream_budget" not in session
