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
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "sync-record.py"


def _load_sync_record_module():
    """`sync-record.py` fuer In-Prozess-Tests laden (Bindestrich im Namen -
    kein normaler `import`), wie das Skript selbst es mit
    `gsv-registers.py` macht. Nur fuer den Kamera-Zweig gebraucht: der
    faengt den Import von `picamera2` lazy in der Funktion ab, was sich nur
    testen laesst, wenn `sys.modules["picamera2"]` VOR dem Aufruf gesetzt
    ist - als Subprozess ginge das nicht ohne eine echte Kamera."""
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


def test_scaler_crop_landet_in_session_json_als_angefordert_und_leer_ohne_kamera(tmp_path):
    """`--source synthetic` durchlaeuft nie `_camera_frames` - also traegt
    `session.json["scaler_crop_actual"]` hier immer `null`, waehrend
    `scaler_crop_requested` das geparste CLI-Argument widerspiegelt (Task 2,
    Interfaces: 'scaler_crop_actual ist der Wert aus den Metadaten des
    ersten Bildes ... oder null')."""
    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-scaler-crop"
    try:
        completed = _run_cli(
            duration=0.5,
            output=output_dir,
            port=os.ttyname(slave),
            extra_args=("--scaler-crop", "1000,800,1600,1200"),
        )
    finally:
        os.close(master)
        os.close(slave)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    session = json.loads((output_dir / "session.json").read_text())
    assert session["scaler_crop_requested"] == [1000, 800, 1600, 1200]
    assert session["scaler_crop_actual"] is None


def test_scaler_crop_ohne_argument_ist_null_in_session_json(tmp_path):
    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-ohne-scaler-crop"
    try:
        completed = _run_cli(duration=0.5, output=output_dir, port=os.ttyname(slave))
    finally:
        os.close(master)
        os.close(slave)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    session = json.loads((output_dir / "session.json").read_text())
    assert session["scaler_crop_requested"] is None
    assert session["scaler_crop_actual"] is None


def test_scaler_crop_falsche_anzahl_bricht_mit_klarer_meldung_ab(tmp_path):
    master, slave = os.openpty()
    try:
        completed = _run_cli(
            duration=0.5,
            output=tmp_path / "lauf-x",
            port=os.ttyname(slave),
            extra_args=("--scaler-crop", "1,2,3"),
        )
    finally:
        os.close(master)
        os.close(slave)

    assert completed.returncode != 0
    assert "--scaler-crop" in completed.stderr


@pytest.mark.parametrize("raw", ["1000,800,1600,0", "1000,-800,1600,1200", "0,0,1600,1200"])
def test_scaler_crop_negativ_oder_null_bricht_mit_klarer_meldung_ab(tmp_path, raw):
    master, slave = os.openpty()
    try:
        completed = _run_cli(
            duration=0.5,
            output=tmp_path / "lauf-y",
            port=os.ttyname(slave),
            extra_args=("--scaler-crop", raw),
        )
    finally:
        os.close(master)
        os.close(slave)

    assert completed.returncode != 0
    assert "--scaler-crop" in completed.stderr


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


# --- --source camera: Fake-Kamera, kein Hardwarebedarf ----------------------
#
# Kein Subprozess: der Kamera-Zweig faengt `from picamera2 import Picamera2`
# lazy in `_camera_frames` ab - das laesst sich nur ueber ein zuvor
# gesetztes `sys.modules["picamera2"]` testen, im selben Prozess.


class _FakeLibcameraRequest:
    """Steht fuer `CompletedRequest.request` (das zugrundeliegende
    `libcamera.Request`) - traegt in echt `.sequence`, siehe
    `/usr/lib/python3/dist-packages/picamera2/request.py:90` und
    `/usr/lib/python3/dist-packages/libcamera/__init__.py:4`."""

    def __init__(self, sequence: int) -> None:
        self.sequence = sequence


class _FakeCompletedRequest:
    def __init__(self, sequence: int, sensor_timestamp_ns: int, *, scaler_crop: tuple | None = None) -> None:
        self.request = _FakeLibcameraRequest(sequence)
        self._sensor_timestamp_ns = sensor_timestamp_ns
        self._scaler_crop = scaler_crop
        self.released = False

    def make_array(self, name: str):
        import numpy as np

        assert name == "main"
        return np.zeros((4, 4, 3), dtype=np.uint8)

    def get_metadata(self) -> dict:
        metadata = {"SensorTimestamp": self._sensor_timestamp_ns}
        if self._scaler_crop is not None:
            # Echtes picamera2 liefert hier ein 4er-Tupel (`Rectangle.to_tuple()`,
            # siehe /usr/lib/python3/dist-packages/picamera2/utils.py:6-13).
            metadata["ScalerCrop"] = self._scaler_crop
        return metadata

    def release(self) -> None:
        self.released = True


class _FakeCamera:
    """Fake fuer `picamera2.Picamera2`. `sensor_mode_size`/`sensor_array_size`
    (Bug 2) stehen in echt erst NACH `configure()` zur Verfuegung
    (`camera.camera_config["sensor"]["output_size"]`,
    `camera.camera_properties["PixelArraySize"]`, siehe `_camera_frames`-
    Docstring) - genauso hier: leer bis `configure()` laeuft, danach befuellt."""

    def __init__(
        self,
        requests: list[_FakeCompletedRequest],
        *,
        sensor_mode_size: tuple[int, int] | None = None,
        sensor_array_size: tuple[int, int] | None = None,
    ) -> None:
        self._requests = list(requests)
        self._sensor_mode_size = sensor_mode_size
        self._sensor_array_size = sensor_array_size
        self.started = False
        self.stopped = False
        self.configured_with = None
        self.camera_config: dict = {}
        self.camera_properties: dict = {}

    def create_video_configuration(self, **kwargs):
        return kwargs

    def configure(self, config) -> None:
        self.configured_with = config
        self.camera_config = {}
        if self._sensor_mode_size is not None:
            self.camera_config["sensor"] = {"output_size": self._sensor_mode_size}
        self.camera_properties = {}
        if self._sensor_array_size is not None:
            self.camera_properties["PixelArraySize"] = self._sensor_array_size

    def start(self, show_preview: bool = False) -> None:
        self.started = True

    def capture_request(self, wait: float = 2.0):
        if not self._requests:
            raise RuntimeError("Fake-Kamera: keine weiteren Requests")
        return self._requests.pop(0)

    def stop(self) -> None:
        self.stopped = True


def test_kamera_zweig_liest_sensor_sequence_aus_completed_request(monkeypatch):
    """OQ-40-Nachtrag: `frame_sequence` ist nur der Skriptzaehler und haette
    die gemessene 2,60s-Luecke nicht gezeigt. `_camera_frames` muss
    zusaetzlich `request.request.sequence` (die libcamera-Sequenznummer)
    liefern."""
    module = _load_sync_record_module()

    fake_requests = [
        _FakeCompletedRequest(sequence=100, sensor_timestamp_ns=1_000_000_000),
        _FakeCompletedRequest(sequence=101, sensor_timestamp_ns=1_066_000_000),
    ]
    fake_camera = _FakeCamera(fake_requests)
    fake_picamera2_module = types.SimpleNamespace(Picamera2=lambda: fake_camera)
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)

    gen = module._camera_frames((320, 240), 15.0)
    try:
        image1, ts1, seq1, _crop1, _mode1, _array1 = next(gen)
        image2, ts2, seq2, _crop2, _mode2, _array2 = next(gen)
    finally:
        gen.close()

    assert seq1 == 100
    assert seq2 == 101
    assert ts1["value_ns"] == 1_000_000_000
    assert ts2["value_ns"] == 1_066_000_000
    assert ts1["base"] == "sensor_boottime"
    # Sequenznummer/Metadaten muessen VOR dem Release gelesen worden sein.
    assert fake_requests[0].released is True
    assert fake_requests[1].released is True
    assert fake_camera.started is True
    assert fake_camera.stopped is True


def test_kamera_zweig_liefert_none_wenn_sequence_fehlt(monkeypatch):
    """Fehlt `.sequence` am zugrundeliegenden Request-Objekt (z.B. andere
    libcamera-Version), darf `_camera_frames` nicht abstuerzen, sondern muss
    `sensor_sequence=None` liefern - "null wenn nicht verfuegbar" aus dem
    Auftrag."""
    module = _load_sync_record_module()

    class _RequestOhneSequence:
        pass

    class _CompletedRequestOhneSequence(_FakeCompletedRequest):
        def __init__(self, sensor_timestamp_ns: int) -> None:
            self.request = _RequestOhneSequence()
            self._sensor_timestamp_ns = sensor_timestamp_ns
            self._scaler_crop = None
            self.released = False

    fake_camera = _FakeCamera([_CompletedRequestOhneSequence(sensor_timestamp_ns=42)])
    fake_picamera2_module = types.SimpleNamespace(Picamera2=lambda: fake_camera)
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)

    gen = module._camera_frames((320, 240), 15.0)
    try:
        _image, _ts, seq, _crop, _mode, _array = next(gen)
    finally:
        gen.close()

    assert seq is None


def test_camera_frames_setzt_scaler_crop_ueber_video_konfiguration(monkeypatch):
    """`--scaler-crop` muss ueber die `controls`-Dict von
    `create_video_configuration` gesetzt werden, nicht per `set_controls`
    nach dem Start: `configure_()` uebernimmt `camera_config['controls']`
    unveraendert in `self.controls`
    (/usr/lib/python3/dist-packages/picamera2/picamera2.py:1292), und
    `start_()` wendet das beim `camera.start(controls)` an
    (picamera2.py:1338) - so ist der Crop schon im allerersten Request
    aktiv, ein `set_controls` danach koennte erst ab dem zweiten Bild
    wirken."""
    module = _load_sync_record_module()

    fake_requests = [
        _FakeCompletedRequest(sequence=1, sensor_timestamp_ns=1, scaler_crop=(1000, 800, 1600, 1200)),
    ]
    fake_camera = _FakeCamera(fake_requests)
    fake_picamera2_module = types.SimpleNamespace(Picamera2=lambda: fake_camera)
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)

    gen = module._camera_frames((320, 240), 15.0, scaler_crop=(1000, 800, 1600, 1200))
    try:
        _image, _ts, _seq, scaler_crop_actual, _mode, _array = next(gen)
    finally:
        gen.close()

    assert fake_camera.configured_with["controls"]["ScalerCrop"] == (1000, 800, 1600, 1200)
    assert scaler_crop_actual == (1000, 800, 1600, 1200)


def test_camera_frames_ohne_scaler_crop_setzt_kein_control(monkeypatch):
    module = _load_sync_record_module()

    fake_requests = [_FakeCompletedRequest(sequence=1, sensor_timestamp_ns=1)]
    fake_camera = _FakeCamera(fake_requests)
    fake_picamera2_module = types.SimpleNamespace(Picamera2=lambda: fake_camera)
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)

    gen = module._camera_frames((320, 240), 15.0)
    try:
        _image, _ts, _seq, scaler_crop_actual, _mode, _array = next(gen)
    finally:
        gen.close()

    assert "ScalerCrop" not in fake_camera.configured_with["controls"]
    assert scaler_crop_actual is None


def test_camera_frames_liefert_sensor_mode_und_array_size_aus_configure(monkeypatch):
    """Bug 2: `sensor_mode_size` kommt aus `camera.camera_config['sensor']
    ['output_size']`, `sensor_array_size` aus
    `camera.camera_properties['PixelArraySize']` - beide erst NACH
    `camera.configure(...)` gueltig (siehe `_camera_frames`-Docstring)."""
    module = _load_sync_record_module()

    fake_requests = [_FakeCompletedRequest(sequence=1, sensor_timestamp_ns=1)]
    fake_camera = _FakeCamera(
        fake_requests, sensor_mode_size=(2028, 1520), sensor_array_size=(4056, 3040)
    )
    fake_picamera2_module = types.SimpleNamespace(Picamera2=lambda: fake_camera)
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)

    gen = module._camera_frames((960, 720), 15.0)
    try:
        _image, _ts, _seq, _crop, sensor_mode_size, sensor_array_size = next(gen)
    finally:
        gen.close()

    assert sensor_mode_size == (2028, 1520)
    assert sensor_array_size == (4056, 3040)


def test_camera_frames_ohne_sensor_infos_liefert_none(monkeypatch):
    """Fehlen die Angaben (andere picamera2-Version, alte Property nicht
    gesetzt), muss `_camera_frames` `None` liefern statt abzustuerzen -
    'null wenn nicht verfuegbar' wie bei sensor_sequence."""
    module = _load_sync_record_module()

    fake_requests = [_FakeCompletedRequest(sequence=1, sensor_timestamp_ns=1)]
    fake_camera = _FakeCamera(fake_requests)
    fake_picamera2_module = types.SimpleNamespace(Picamera2=lambda: fake_camera)
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)

    gen = module._camera_frames((320, 240), 15.0)
    try:
        _image, _ts, _seq, _crop, sensor_mode_size, sensor_array_size = next(gen)
    finally:
        gen.close()

    assert sensor_mode_size is None
    assert sensor_array_size is None


def test_kamera_lauf_schreibt_sensor_mode_und_array_size_in_session_json(monkeypatch, tmp_path):
    """Ende-zu-Ende ueber `module.run()`: beide Felder landen in
    session.json, gelesen vom ERSTEN Bild (analog scaler_crop_actual)."""
    module = _load_sync_record_module()

    fake_requests = [
        _FakeCompletedRequest(sequence=1, sensor_timestamp_ns=1_000_000_000),
        _FakeCompletedRequest(sequence=2, sensor_timestamp_ns=1_066_000_000),
    ]
    fake_camera = _FakeCamera(
        fake_requests, sensor_mode_size=(2028, 1520), sensor_array_size=(4056, 3040)
    )
    fake_picamera2_module = types.SimpleNamespace(Picamera2=lambda: fake_camera)
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)

    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-kamera-sensor-groessen"
    args = module.parse_args(
        [
            "--duration",
            "0.3",
            "--output",
            str(output_dir),
            "--source",
            "camera",
            "--camera-size",
            "320x240",
            "--frame-rate",
            "15",
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
            # Streamstart-Budget-Pruefung liest das ECHTE Kernel-Log des
            # Testrechners (Scope-Erweiterung) - fuer diesen Test irrelevant,
            # deshalb bewusst uebersteuert statt vom lokalen Log abzuhaengen.
            "--override-stream-budget",
        ]
    )
    try:
        returncode = module.run(args)
    finally:
        os.close(master)
        os.close(slave)

    assert returncode == 0
    session = json.loads((output_dir / "session.json").read_text())
    assert session["sensor_mode_size"] == [2028, 1520]
    assert session["sensor_array_size"] == [4056, 3040]


def test_synthetic_lauf_hat_sensor_mode_und_array_size_null(tmp_path):
    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-synthetic-sensor-groessen"
    try:
        completed = _run_cli(duration=0.3, output=output_dir, port=os.ttyname(slave))
    finally:
        os.close(master)
        os.close(slave)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    session = json.loads((output_dir / "session.json").read_text())
    assert session["sensor_mode_size"] is None
    assert session["sensor_array_size"] is None


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


# --- Bug 1 (Orchestrator 2026-09-23): haengender Kamerazweig darf nicht ----
# --- still mit Exit 0/"vollstaendig" und 0 Bildern enden --------------------


class _HangingCamera(_FakeCamera):
    """`capture_request` kehrt nie zurueck - wie am 2026-09-23 real beobachtet
    (Sensor durch OQ-22 blockiert, "stream on failed" im Kernel-Log, kein
    TimeoutError, keine Ausnahme). Simuliert nicht `wait=2.0` als
    picamera2-Timeout, weil genau das am echten Geraet ausblieb."""

    def capture_request(self, wait: float = 2.0):
        time.sleep(9999)


class _TimeoutRaisingCamera(_FakeCamera):
    """Alternative Auspraegung desselben Befunds: `capture_request` wirft
    stattdessen einen Timeout (z.B. eine andere picamera2-Version)."""

    def capture_request(self, wait: float = 2.0):
        raise TimeoutError("Fake-Kamera: kein Bild innerhalb der Frist")


def _run_camera_branch(module, monkeypatch, tmp_path, fake_camera_cls, *, extra_args=()):
    monkeypatch.setattr(module, "STARTUP_TIMEOUT_S", 0.2)
    fake_camera = fake_camera_cls([])
    fake_picamera2_module = types.SimpleNamespace(Picamera2=lambda: fake_camera)
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)

    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-kamera-haengt"
    args = module.parse_args(
        [
            "--duration",
            "1.0",
            "--output",
            str(output_dir),
            "--source",
            "camera",
            "--camera-size",
            "320x240",
            "--frame-rate",
            "15",
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
            # Streamstart-Budget-Pruefung liest das ECHTE Kernel-Log des
            # Testrechners (Scope-Erweiterung) - fuer diese Tests irrelevant.
            "--override-stream-budget",
            *extra_args,
        ]
    )
    try:
        returncode = module.run(args)
    finally:
        os.close(master)
        os.close(slave)
    return returncode, output_dir


def test_kamera_haengt_ohne_erstes_bild_wird_laut_gemeldet_und_bricht_ab(monkeypatch, tmp_path, capsys):
    module = _load_sync_record_module()
    returncode, output_dir = _run_camera_branch(module, monkeypatch, tmp_path, _HangingCamera)

    assert returncode == module.EXIT_NO_FRAMES_ACQUIRED
    assert returncode != 0

    session = json.loads((output_dir / "session.json").read_text())
    assert session["frames_recorded"] == 0
    # kein Ctrl-C/SIGTERM - der Abbruch ist ein Befund, kein Nutzerabbruch.
    assert session["aborted"] is False
    assert session["abort_reason"] is None
    assert session["acquisition_error"] is not None
    assert "OQ-22" in session["acquisition_error"]
    assert "blockiert" in session["acquisition_error"]

    captured = capsys.readouterr()
    assert "vollstaendig" not in captured.out
    assert "OQ-22" in captured.err


def test_kamera_wirft_timeout_error_wird_ebenso_laut_gemeldet(monkeypatch, tmp_path):
    """Zweite Auspraegung desselben Befunds: capture_request wirft statt zu
    haengen - auch das ist ein 'kein Bild bekommen'-Fall und muss denselben
    Weg (Exit != 0, OQ-22-Hinweis, kein 'vollstaendig') nehmen."""
    module = _load_sync_record_module()
    returncode, output_dir = _run_camera_branch(module, monkeypatch, tmp_path, _TimeoutRaisingCamera)

    assert returncode == module.EXIT_NO_FRAMES_ACQUIRED
    session = json.loads((output_dir / "session.json").read_text())
    assert session["frames_recorded"] == 0
    assert session["acquisition_error"] is not None
    assert "OQ-22" in session["acquisition_error"]


def test_kamera_haengt_aber_norm_schedule_rueckstellung_laeuft_trotzdem(monkeypatch, tmp_path):
    """Auch wenn die Bildaufnahme scheitert, muss die serielle Sitzung sauber
    zu Ende laufen: die Rueckstellung nach --norm-schedule darf nicht
    ausbleiben, nur weil die Kamera nie ein Bild lieferte. Das Skript darf
    die Kamera dafuer nicht hart abwuergen (Auftrag) - der haengende
    Kamera-Thread bleibt als Daemon zurueck, der serielle Pfad laeuft
    unabhaengig davon vollstaendig durch."""
    module = _load_sync_record_module()
    monkeypatch.setattr(module, "STARTUP_TIMEOUT_S", 0.2)

    fake_camera = _HangingCamera([])
    fake_picamera2_module = types.SimpleNamespace(Picamera2=lambda: fake_camera)
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)

    master, slave = os.openpty()
    device = _FakeGsvDevice(master)
    device.start()
    output_dir = tmp_path / "lauf-kamera-haengt-mit-rueckstellung"
    args = module.parse_args(
        [
            "--duration",
            "1.5",
            "--output",
            str(output_dir),
            "--source",
            "camera",
            "--camera-size",
            "320x240",
            "--frame-rate",
            "15",
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
            "--norm-schedule",
            "2.0:0.5",
            "--restore-point",
            str(RESTORE_POINT_PATH),
            "--override-stream-budget",
        ]
    )
    try:
        returncode = module.run(args)
    finally:
        device.stop()
        os.close(master)
        os.close(slave)

    assert returncode == module.EXIT_NO_FRAMES_ACQUIRED
    session = json.loads((output_dir / "session.json").read_text())
    assert session["frames_recorded"] == 0
    assert session["acquisition_error"] is not None
    # Die serielle Rueckstellung ist trotz gescheiterter Bildaufnahme gelaufen.
    assert session["precheck"]["matches_restore_point"] is True
    assert session["restore_verification"]["write_ok"] is True
    assert session["restore_verification"]["matches_restore_point"] is True
    assert device.norm_bytes == list(RESTORE_NORM_BYTES)
    assert device.dpoint == RESTORE_DPOINT


# --- Streamstart-Budget (Scope-Erweiterung, Orchestrator 2026-09-23) -------
#
# Root Cause der Blockade vom 2026-09-23: OQ-22 haelt fest, dass die
# IMX500/RP2040-Bruecke nach rund 20-25 Streamstarts je Boot unerreichbar
# wird. Reale Beobachtung: 20 erfolgreiche Starts, der 21. mit
# "imx500_power_on: failed to get led gpio" gefolgt von "stream on failed".
# count_stream_starts/has_stream_on_failed sind reine Funktionen (kein I/O),
# check_stream_budget kapselt die I/O-Helfer (journalctl/dmesg/Zaehlerdatei)
# hinter einer testbaren Entscheidungsfunktion.


def _journal_line(t_boot_s: float, message: str) -> str:
    return f"[{t_boot_s:14.6f}] {message}"


def test_count_stream_starts_single_line_per_start():
    """Normalfall: eine Log-Zeile je tatsaechlichem Streamstart."""
    module = _load_sync_record_module()
    text = "\n".join(
        _journal_line(t, "rp1-cfe 1f00128000.csi2: Using a link rate of 456000000 bps")
        for t in (10.0, 50.0, 200.0)
    )
    assert module.count_stream_starts(text) == 3


def test_count_stream_starts_groups_burst_within_one_second_as_one_start():
    """Der beobachtete Fehlschlag: 5 Zeilen innerhalb 1s gehoeren zu EINEM
    Streamstart-Versuch, nicht zu 5."""
    module = _load_sync_record_module()
    burst = "\n".join(
        _journal_line(1000.0 + 0.2 * i, "rp1-cfe: Using a link rate of 456000000 bps") for i in range(5)
    )
    text = (
        _journal_line(10.0, "rp1-cfe: Using a link rate of 456000000 bps")
        + "\n"
        + _journal_line(50.0, "rp1-cfe: Using a link rate of 456000000 bps")
        + "\n"
        + burst
    )
    assert module.count_stream_starts(text) == 3  # 10.0, 50.0, und der Burst als ein Start


def test_count_stream_starts_no_marker_is_zero():
    module = _load_sync_record_module()
    assert module.count_stream_starts("nichts Relevantes hier\nnoch eine Zeile\n") == 0


def test_count_stream_starts_unparsable_timestamps_counts_every_line():
    """Kein Zeitstempel erkennbar (unerwartetes Format) - sichere Richtung
    ist Ueberzaehlen, nie Unterzaehlen (das Budget waere sonst faelschlich
    'noch nicht erschoepft')."""
    module = _load_sync_record_module()
    text = "\n".join(["Using a link rate of foo"] * 4)
    assert module.count_stream_starts(text) == 4


def test_has_stream_on_failed_true_and_false():
    module = _load_sync_record_module()
    assert module.has_stream_on_failed("foo\nimx500_power_on: failed to get led gpio\nstream on failed\nbar")
    assert not module.has_stream_on_failed("alles gut, kein Problem hier")


def test_check_stream_budget_reads_from_journalctl_and_refuses_when_exhausted(monkeypatch):
    module = _load_sync_record_module()

    journal_text = "\n".join(
        _journal_line(10.0 * i, "rp1-cfe: Using a link rate of 456000000 bps") for i in range(20)
    )

    def _fake_run(cmd, **kwargs):
        assert cmd[0] == "journalctl"
        return types.SimpleNamespace(returncode=0, stdout=journal_text, stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    info = module.check_stream_budget(stream_budget=15, override=False)
    assert info["stream_budget_source"] == "journalctl"
    assert info["stream_starts_this_boot_before"] == 20
    assert info["stream_budget"] == 15
    assert info["refuse"] is True
    assert "OQ-22" in info["message"]
    assert "20/15" in info["message"]


def test_check_stream_budget_warns_near_budget_without_refusing(monkeypatch):
    module = _load_sync_record_module()
    journal_text = "\n".join(
        _journal_line(10.0 * i, "rp1-cfe: Using a link rate of 456000000 bps") for i in range(13)
    )

    def _fake_run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=0, stdout=journal_text, stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    info = module.check_stream_budget(stream_budget=15, override=False)
    assert info["stream_starts_this_boot_before"] == 13  # >= 15-3
    assert info["refuse"] is False
    assert info["warn"] is True
    assert "OQ-22" in info["warn_message"]


def test_check_stream_budget_below_warn_threshold_is_silent(monkeypatch):
    module = _load_sync_record_module()
    journal_text = "\n".join(
        _journal_line(10.0 * i, "rp1-cfe: Using a link rate of 456000000 bps") for i in range(5)
    )

    def _fake_run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=0, stdout=journal_text, stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    info = module.check_stream_budget(stream_budget=15, override=False)
    assert info["refuse"] is False
    assert info["warn"] is False


def test_check_stream_budget_refuses_on_existing_stream_on_failed(monkeypatch):
    module = _load_sync_record_module()
    journal_text = (
        _journal_line(1.0, "rp1-cfe: Using a link rate of 456000000 bps")
        + "\n"
        + _journal_line(2.0, "imx500_power_on: failed to get led gpio")
        + "\n"
        + _journal_line(2.1, "stream on failed")
    )

    def _fake_run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=0, stdout=journal_text, stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    # Weit unter dem Budget, aber "stream on failed" ist allein schon ein
    # Abbruchgrund (ein wiederholter Versuch gegen den blockierten Sensor
    # wuerde nur weitere Fehler erzeugen).
    info = module.check_stream_budget(stream_budget=15, override=False)
    assert info["stream_on_failed_seen_before_start"] is True
    assert info["refuse"] is True
    assert "stream on failed" in info["message"]
    assert "OQ-22" in info["message"]


def test_check_stream_budget_override_bypasses_both_refusal_reasons(monkeypatch):
    module = _load_sync_record_module()
    journal_text = _journal_line(1.0, "stream on failed") + "\n" + "\n".join(
        _journal_line(10.0 * i, "rp1-cfe: Using a link rate of 456000000 bps") for i in range(20)
    )

    def _fake_run(cmd, **kwargs):
        return types.SimpleNamespace(returncode=0, stdout=journal_text, stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    info = module.check_stream_budget(stream_budget=15, override=True)
    assert info["refuse"] is False


def test_check_stream_budget_falls_back_to_dmesg_when_journalctl_unavailable(monkeypatch):
    module = _load_sync_record_module()

    def _fake_run(cmd, **kwargs):
        if cmd[0] == "journalctl":
            raise FileNotFoundError("journalctl nicht installiert")
        assert cmd[0] == "dmesg"
        text = _journal_line(1.0, "rp1-cfe: Using a link rate of 456000000 bps")
        return types.SimpleNamespace(returncode=0, stdout=text, stderr="")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    info = module.check_stream_budget(stream_budget=15, override=False)
    assert info["stream_budget_source"] == "dmesg"
    assert info["stream_starts_this_boot_before"] == 1


def test_check_stream_budget_falls_back_to_counter_file_when_log_unavailable(monkeypatch, tmp_path):
    """Weder journalctl noch dmesg liefern etwas - Zaehlerdatei-Fallback,
    keyed ueber boot_id. Jeder Aufruf erhoeht den Stand um 1 und liefert den
    Stand VOR der Erhoehung."""
    module = _load_sync_record_module()

    def _fake_run(cmd, **kwargs):
        raise FileNotFoundError("weder journalctl noch dmesg verfuegbar")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    monkeypatch.setattr(module, "_read_boot_id", lambda: "test-boot-id-123")

    counter_path = tmp_path / "camera-stream-budget.json"

    info1 = module.check_stream_budget(stream_budget=15, override=False, counter_path=counter_path)
    assert info1["stream_budget_source"] == "unavailable"
    assert info1["stream_starts_this_boot_before"] == 0

    info2 = module.check_stream_budget(stream_budget=15, override=False, counter_path=counter_path)
    assert info2["stream_starts_this_boot_before"] == 1

    stored = json.loads(counter_path.read_text())
    assert stored == {"test-boot-id-123": 2}


def test_check_stream_budget_counter_fallback_without_boot_id_stays_zero(monkeypatch, tmp_path):
    module = _load_sync_record_module()

    def _fake_run(cmd, **kwargs):
        raise FileNotFoundError("kein Kernel-Log verfuegbar")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)
    monkeypatch.setattr(module, "_read_boot_id", lambda: None)

    counter_path = tmp_path / "camera-stream-budget.json"
    info = module.check_stream_budget(stream_budget=15, override=False, counter_path=counter_path)
    assert info["stream_starts_this_boot_before"] == 0
    assert not counter_path.exists()


def test_run_refuses_before_opening_camera_when_budget_exhausted(monkeypatch, tmp_path):
    """Ende-zu-Ende: `run()` bricht VOR jedem Kamerazugriff ab - die
    Fake-`Picamera2` darf nicht einmal instanziiert werden."""
    module = _load_sync_record_module()

    def _picamera2_not_allowed():
        raise AssertionError("Picamera2() haette hier NICHT aufgerufen werden duerfen")

    fake_picamera2_module = types.SimpleNamespace(Picamera2=_picamera2_not_allowed)
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)
    monkeypatch.setattr(
        module,
        "check_stream_budget",
        lambda **kwargs: {
            "stream_starts_this_boot_before": 20,
            "stream_budget": 15,
            "stream_budget_source": "journalctl",
            "stream_on_failed_seen_before_start": False,
            "refuse": True,
            "message": "FEHLER: Streamstart-Budget dieses Boots erschoepft (20/15), Reboot empfohlen, OQ-22.",
            "warn": False,
            "warn_message": None,
        },
    )

    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-budget-erschoepft"
    args = module.parse_args(
        [
            "--duration",
            "1.0",
            "--output",
            str(output_dir),
            "--source",
            "camera",
            "--camera-size",
            "320x240",
            "--frame-rate",
            "15",
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

    assert returncode == module.EXIT_STREAM_BUDGET_EXHAUSTED
    assert returncode == 5
    # Kein Aufnahmeverzeichnis, kein session.json - der Abbruch kam vor jedem
    # Seiteneffekt.
    assert not output_dir.exists()


def test_run_override_stream_budget_bypasses_refusal(monkeypatch, tmp_path):
    module = _load_sync_record_module()

    fake_requests = [_FakeCompletedRequest(sequence=1, sensor_timestamp_ns=1)]
    fake_camera = _FakeCamera(fake_requests)
    fake_picamera2_module = types.SimpleNamespace(Picamera2=lambda: fake_camera)
    monkeypatch.setitem(sys.modules, "picamera2", fake_picamera2_module)
    monkeypatch.setattr(
        module,
        "check_stream_budget",
        lambda **kwargs: {
            "stream_starts_this_boot_before": 20,
            "stream_budget": 15,
            "stream_budget_source": "journalctl",
            "stream_on_failed_seen_before_start": False,
            "refuse": False,  # override wurde schon in check_stream_budget beruecksichtigt
            "message": None,
            "warn": False,
            "warn_message": None,
        },
    )

    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-budget-uebersteuert"
    args = module.parse_args(
        [
            "--duration",
            "0.3",
            "--output",
            str(output_dir),
            "--source",
            "camera",
            "--camera-size",
            "320x240",
            "--frame-rate",
            "15",
            "--port",
            os.ttyname(slave),
            "--baudrate",
            "9600",
            "--override-stream-budget",
        ]
    )
    try:
        module.run(args)
    finally:
        os.close(master)
        os.close(slave)

    assert (output_dir / "session.json").is_file()
    session = json.loads((output_dir / "session.json").read_text())
    assert session["stream_starts_this_boot_before"] == 20
    assert session["stream_budget"] == 15
    assert session["stream_budget_source"] == "journalctl"


def test_synthetic_source_leaves_stream_budget_fields_null_in_session_json(tmp_path):
    """--source synthetic hat keine Kamera - die Streamstart-Budget-Felder
    bleiben `null`, das reale journalctl/dmesg des Testrechners darf hier
    keine Rolle spielen (dieser Lauf ist ein eigener Subprozess, siehe
    _run_cli - `run()` ruft `check_stream_budget` fuer diesen Zweig gar
    nicht erst auf, siehe `if args.source == "camera":` in `run()`)."""
    master, slave = os.openpty()
    output_dir = tmp_path / "lauf-synthetic-kein-budget"
    try:
        completed = _run_cli(duration=0.3, output=output_dir, port=os.ttyname(slave))
    finally:
        os.close(master)
        os.close(slave)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    session = json.loads((output_dir / "session.json").read_text())
    assert session["stream_starts_this_boot_before"] is None
    assert session["stream_budget"] is None
    assert session["stream_budget_source"] is None
