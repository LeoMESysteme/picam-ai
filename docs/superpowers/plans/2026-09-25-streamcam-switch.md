# Umstellung IMX500 → Logitech StreamCam — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ernten laufen mit der Logitech StreamCam (UVC) statt der IMX500; IMX500-Code ist entfernt/deaktiviert, der Zeitbezug ist sauber umgerechnet und eine StreamCam-Timing-Kalibrierung ist Pflicht vor jeder Ernte.

**Architecture:** Neue Bildquelle `UvcSource` (`v4l2://`, OpenCV-V4L2 + `v4l2-ctl`) mit rücklesbarer Kamerasteuerung aus einem `CameraSettings`-Block, der im Profil v3 gespeichert wird. Rohe V4L2-Zeitstempel (`v4l2_monotonic`) werden nur an einer Stelle (`to_boottime_ns`) mit einem in `session.json` gemessenen Versatz nach CLOCK_BOOTTIME umgerechnet. `harvest.py` liest M aus `var/calibration/timing-streamcam.json`.

**Tech Stack:** Python 3.13 (System-venv mit `--system-site-packages`), OpenCV (`cv2`, System), `v4l2-ctl` (v4l-utils, System), pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-09-25-streamcam-switch-design.md`

## Global Constraints

- Arbeitsverzeichnis: `/home/me-systeme/picam-ai-ernte` (Branch des Worktrees). Den Worktree `/home/me-systeme/picam-ai` **nie** anfassen (dort arbeitet der Nutzer).
- venv: `/home/me-systeme/picam-ai/.venv/bin/python` bzw. `/home/me-systeme/picam-ai/.venv/bin/pytest` (der Worktree hat kein eigenes `.venv`); Tests immer aus `/home/me-systeme/picam-ai-ernte` starten: `cd /home/me-systeme/picam-ai-ernte && /home/me-systeme/picam-ai/.venv/bin/pytest -q`.
- Keine neuen Abhängigkeiten (kein pip install). `cv2` nur lazy in Factories/Funktionen importieren, wo das Modul sonst ohne OpenCV importierbar sein muss (`frames/__init__.py`); `picamera2` wird nirgends mehr importiert.
- Subagenten committen **nicht** und ändern **nicht** CHANGELOG.md, docs/, TODO.md, CLAUDE.md, AGENTS.md, Konzept.md — das macht der Controller.
- Kamera-USB-ID: `046d:0893`. Kameramodell-Kennung: `logitech_streamcam`.
- Feste Controls: `focus_automatic_continuous=0`, `auto_exposure=1`, `white_balance_automatic=0`, `power_line_frequency=1`, `zoom_absolute=100`, `pan_absolute=0`, `tilt_absolute=0`. Aus Einstellungen: `focus_absolute`, `exposure_time_absolute`, `white_balance_temperature`, `gain`.
- Reihenfolge beim Setzen: erst `focus_automatic_continuous`, `auto_exposure`, `white_balance_automatic`, dann alle übrigen.
- Neue Zeitbasis: `TimeBaseKind.V4L2_MONOTONIC = "v4l2_monotonic"`.
- Suspend-Toleranz: `|offset_end − offset_start| > 1_000_000 ns` → Ablehnung.
- `frame_gaps`: Lücke = Zeitstempelabstand > 1,5 × (1e9 / Kamera-fps) ns.
- Profil: `PROFILE_SCHEMA_VERSION = 3`; `load` akzeptiert 2 und 3, weist alles andere ab.
- Timing-Datei: `var/calibration/timing-streamcam.json`, Felder `schema_version` (1), `camera_usb_id`, `guard_margin_ms`, `display_offset_ms`, `measured_at_utc`, `sources` (Liste `{offset_json, sha256}`).
- Kein Erfinden: Fehlt ein Wert (Zeitbasis, Versatz, Kalibrierung, Control), wird abgelehnt, nie ein Vorgabewert eingesetzt.
- Meldungstexte deutsch, ASCII-Umschrift in Code-Strings wie im Bestand (ae/oe/ue/ss) ist erlaubt.
- Nach jeder Aufgabe: `ruff check src tests scripts` sauber und volle Suite grün.

## Review Focus

1. **Alte IMX500-Sessions** (`base: "sensor_boottime"`, ohne Versatzfeld) müssen durch `gate-label`/`display-offset` exakt wie vorher laufen — Regressionstest in Task 1.
2. **Kamera wird während der Aufnahme abgezogen** (read liefert `False`): sauberer Abschluss, `frames_recorded` = tatsächlich geschriebene Bilder, auch wenn der Aufnahmethread nie `_QUEUE_DONE` liefert — Test in Task 3.
3. **`/dev/video8` heißt nach Neustart anders / zweiter Knoten `video9` ist Metadaten-Knoten**: Gerätesuche über sysfs nimmt nur `index == 0` mit passender USB-ID — Test in Task 2.
4. **Autofokus ist trotz Setzen noch aktiv** (Rücklesewert weicht ab): Abbruch mit Name/Soll/Ist, bevor ein Bild geliefert wird — Test in Task 2.
5. **Harvest mit altem v2-Profil oder ohne/mit fremder Timing-Datei**: Abbruch vor jedem Subprozess — Tests in Task 5.

---

### Task 1: Zeitbasis `v4l2_monotonic` und zentrale Umrechnung

**Files:**
- Modify: `src/dispread/records.py` (TimeBaseKind, neue Funktion `to_boottime_ns`)
- Modify: `scripts/gate-label.py:329-340` (`load_frames`), plus Aufrufer in `run()`
- Modify: `scripts/display-offset.py:116-140` (`load_frames`), plus Aufrufer in `run()`; `time_base`-Text im Ergebnis
- Test: `tests/test_records.py`, `tests/test_gate_label.py`, `tests/test_display_offset.py`, `tests/test_import_harvest.py`

**Interfaces:**
- Produces:
  - `TimeBaseKind.V4L2_MONOTONIC` (`"v4l2_monotonic"`), `carries_time_information` → `True`.
  - `SUSPEND_TOLERANCE_NS: int = 1_000_000` in `records.py`.
  - `to_boottime_ns(timestamp: dict, session: dict | None) -> int` in `records.py`. `timestamp` ist `Timestamp.to_dict()`-Form. `session` ist das geladene `session.json` (oder `None`, wenn keins existiert).
  - `gate-label.py::load_frames(path: Path, session: dict | None) -> list[tuple[str, int]]` (Zeit jetzt BOOTTIME-ns nach Umrechnung).
  - `display-offset.py::load_frames(session_dir: Path) -> list[dict]` liest `session.json` selbst (falls vorhanden) und rechnet um; `t` in BOOTTIME-Sekunden.

- [ ] **Step 1: Failing tests für `to_boottime_ns`** in `tests/test_records.py`:

```python
import pytest
from dispread.records import TimeBaseKind, to_boottime_ns


def _ts(value_ns, base):
    return {"value_ns": value_ns, "base": base, "semantics": "unknown", "uncertainty_ns": None}


def test_v4l2_monotonic_zaehlt_als_zeitbehaftet():
    assert TimeBaseKind("v4l2_monotonic") is TimeBaseKind.V4L2_MONOTONIC
    assert TimeBaseKind.V4L2_MONOTONIC.carries_time_information


def test_sensor_boottime_bleibt_unveraendert_auch_ohne_session():
    assert to_boottime_ns(_ts(123, "sensor_boottime"), None) == 123


def test_v4l2_monotonic_wird_mit_startversatz_umgerechnet():
    session = {"clock_offset_boottime_minus_monotonic_ns": {"start": 5_000, "end": 5_400}}
    assert to_boottime_ns(_ts(1_000_000, "v4l2_monotonic"), session) == 1_005_000


def test_v4l2_monotonic_ohne_versatz_wird_abgelehnt():
    with pytest.raises(ValueError, match="clock_offset"):
        to_boottime_ns(_ts(1, "v4l2_monotonic"), {})
    with pytest.raises(ValueError, match="clock_offset"):
        to_boottime_ns(_ts(1, "v4l2_monotonic"), None)


def test_suspend_zwischen_start_und_ende_wird_abgelehnt():
    session = {"clock_offset_boottime_minus_monotonic_ns": {"start": 0, "end": 1_000_001}}
    with pytest.raises(ValueError, match="Suspend"):
        to_boottime_ns(_ts(1, "v4l2_monotonic"), session)


@pytest.mark.parametrize("base", ["synthetic", "file_mtime", "replay_recorded", "quatsch"])
def test_andere_basen_werden_abgelehnt(base):
    with pytest.raises(ValueError, match="Zeitbasis"):
        to_boottime_ns(_ts(1, base), {"clock_offset_boottime_minus_monotonic_ns": {"start": 0, "end": 0}})
```

Zu `synthetic` (vom Controller geprüft): `SyntheticSource` stempelt `time.monotonic_ns()` mit `base: "synthetic"` — das trägt keine Zeitaussage und liegt nicht in BOOTTIME; die bestehenden Tests von `gate-label`/`display-offset`/`import-harvest` nutzen ausschließlich `sensor_boottime`. Also wird `synthetic` **abgelehnt** (wie im Test oben).

- [ ] **Step 2:** `cd /home/me-systeme/picam-ai-ernte && /home/me-systeme/picam-ai/.venv/bin/pytest tests/test_records.py -q` → FAIL (ImportError `to_boottime_ns`).

- [ ] **Step 3: Implementierung** in `records.py`:

```python
class TimeBaseKind(StrEnum):
    ...
    #: V4L2-Pufferzeitstempel der UVC-Kamera (uvcvideo, clock=CLOCK_MONOTONIC,
    #: gemessen 2026-09-25). Roh gespeichert; nach CLOCK_BOOTTIME nur ueber
    #: `to_boottime_ns` mit dem in session.json gemessenen Versatz.
    V4L2_MONOTONIC = "v4l2_monotonic"

    @property
    def carries_time_information(self) -> bool:
        return self in (
            TimeBaseKind.SENSOR_BOOTTIME,
            TimeBaseKind.REPLAY_RECORDED,
            TimeBaseKind.V4L2_MONOTONIC,
        )


#: Weichen die bei Start und Ende gemessenen Versaetze BOOTTIME-MONOTONIC
#: staerker ab, lag ein Suspend dazwischen - Umrechnung wird abgelehnt.
SUSPEND_TOLERANCE_NS = 1_000_000


def to_boottime_ns(timestamp: dict[str, Any], session: dict[str, Any] | None) -> int:
    """Aufnahmezeitstempel (Timestamp.to_dict()-Form) nach CLOCK_BOOTTIME.

    Einzige Umrechnungsstelle (Spec 2026-09-25, Abschnitt 2). Lehnt ab statt
    zu raten: fehlender Versatz, Suspend waehrend der Aufnahme oder eine
    Zeitbasis ohne BOOTTIME-Bezug -> ValueError.
    """
    base = timestamp.get("base")
    value_ns = int(timestamp["value_ns"])
    if base == TimeBaseKind.SENSOR_BOOTTIME.value:
        return value_ns
    if base == TimeBaseKind.V4L2_MONOTONIC.value:
        offsets = (session or {}).get("clock_offset_boottime_minus_monotonic_ns")
        if not offsets or offsets.get("start") is None or offsets.get("end") is None:
            raise ValueError(
                "v4l2_monotonic-Zeitstempel ohne clock_offset_boottime_minus_monotonic_ns "
                "in session.json - Umrechnung nach CLOCK_BOOTTIME nicht moeglich."
            )
        start, end = int(offsets["start"]), int(offsets["end"])
        if abs(end - start) > SUSPEND_TOLERANCE_NS:
            raise ValueError(
                f"BOOTTIME-MONOTONIC-Versatz aenderte sich waehrend der Aufnahme um "
                f"{end - start} ns (> {SUSPEND_TOLERANCE_NS}) - vermutlich Suspend, "
                "Zeitstempel werden nicht umgerechnet."
            )
        return value_ns + start
    raise ValueError(f"Zeitbasis {base!r} hat keinen CLOCK_BOOTTIME-Bezug - abgelehnt.")
```

- [ ] **Step 4:** Tests aus Step 1 → PASS.

- [ ] **Step 5: Failing tests für die Auswerter.**
  - `tests/test_gate_label.py`: Eine Aufzeichnung mit `frames.jsonl` in `v4l2_monotonic` und `session.json` mit Versatz `{start: S, end: S}` erzeugt **dieselben Labels** wie dieselbe Aufzeichnung mit `sensor_boottime` und um `S` verschobenen Werten. Nutze die vorhandenen Helfer des Testmoduls zum Bauen von Aufzeichnungen (erst lesen, dann erweitern). Zweiter Test: `v4l2_monotonic` ohne `session.json` bzw. ohne Versatz → Exit ≠ 0 und stderr enthält `clock_offset`.
  - `tests/test_display_offset.py`: `load_frames(session_dir)` mit `v4l2_monotonic`-Frames und Versatz liefert `t == (value_ns + S)/1e9`; ohne Versatz `ValueError`. Bestehende Tests mit `sensor_boottime` bleiben unverändert grün (Regression, Review Focus 1).
  - `tests/test_import_harvest.py`: Eine Aufzeichnung mit `v4l2_monotonic` wird importiert und `capture_timestamp` landet **unverändert (roh)** in der Probe. (`import-harvest.py` vergleicht keine Zeiten, es trägt nur durch — keine Umrechnung dort.)

- [ ] **Step 6:** Tests laufen lassen → FAIL.

- [ ] **Step 7: Implementierung.**
  - `gate-label.py`: `load_frames(path, session)` ruft pro Zeile `to_boottime_ns(obj["capture_timestamp"], session)`. `run()` lädt `session.json` der Aufzeichnung einmal (falls vorhanden, sonst `None`) und reicht es durch. `ValueError` → Meldung auf stderr, Exit 2 (Muster der vorhandenen Fehlerpfade in `run()` übernehmen). `sys.path`-Einfügen für `src` existiert dort bereits? Prüfen; sonst wie in `display-offset.py` ergänzen.
  - `display-offset.py`: `load_frames` lädt `session_dir / "session.json"` (falls vorhanden), rechnet mit `to_boottime_ns` um; `timestamp_base` bleibt als Rohbasis im Zeilen-Dict. `time_base`-Text im Ergebnis: `"CLOCK_BOOTTIME (frames: to_boottime_ns(capture_timestamp), serial: t_boot)"`. Docstrings, die „capture_timestamp ist CLOCK_BOOTTIME" behaupten, korrigieren.
- [ ] **Step 8:** Volle Suite + ruff → grün.
- [ ] **Step 9:** Bericht an den Controller (kein Commit).

---

### Task 2: `CameraSettings`, `UvcSource`, Registry ohne IMX500

**Files:**
- Create: `src/dispread/camera_settings.py`
- Create: `src/dispread/frames/uvc_source.py`
- Modify: `src/dispread/frames/__init__.py` (Registry, Docstring)
- Modify: `src/dispread/frames/types.py:30` (Docstring `InferenceResult`: „IMX500, außer Betrieb seit 2026-09-25")
- Test: `tests/test_camera_settings.py`, `tests/test_uvc_source.py`, `tests/test_frames_registry.py` (neu, falls es noch keinen Registry-Test gibt; sonst vorhandenen erweitern — `grep -rn "open_source\|known_schemes" tests` zuerst)

**Interfaces:**
- Produces (`src/dispread/camera_settings.py`):

```python
STREAMCAM_MODEL = "logitech_streamcam"
STREAMCAM_USB_ID = "046d:0893"
#: Vor allen anderen gesetzt (Automatiken aus), Reihenfolge fest.
MODE_CONTROLS: tuple[tuple[str, int], ...] = (
    ("focus_automatic_continuous", 0),
    ("auto_exposure", 1),
    ("white_balance_automatic", 0),
)
FIXED_CONTROLS: tuple[tuple[str, int], ...] = (
    ("power_line_frequency", 1),
    ("zoom_absolute", 100),
    ("pan_absolute", 0),
    ("tilt_absolute", 0),
)
SETTABLE_CONTROLS: tuple[str, ...] = (
    "focus_absolute", "exposure_time_absolute", "white_balance_temperature", "gain",
)

@dataclass(frozen=True, slots=True)
class CameraSettings:
    model: str
    usb_id: str
    size: tuple[int, int]
    fourcc: str
    fps: int
    controls: dict[str, int]          # genau SETTABLE_CONTROLS, alle Pflicht
    device: str | None = None         # nur Information

    def ordered_controls(self) -> list[tuple[str, int]]:
        """MODE_CONTROLS, dann FIXED_CONTROLS, dann SETTABLE_CONTROLS in dieser Reihenfolge."""
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> CameraSettings:
        """ValueError bei fehlendem Feld, fehlendem/zusaetzlichem Control, Nicht-int-Wert."""

def load_camera_settings(path: Path) -> CameraSettings:
    """Liest eine JSON-Datei mit Top-Level-Schluessel "camera" (Profil v3 oder
    Ausgabe von harvest-setup focus). ValueError, wenn "camera" fehlt."""
```

- Produces (`src/dispread/frames/uvc_source.py`):

```python
class UvcError(RuntimeError): ...

def find_uvc_device(usb_id: str, sysfs_root: Path = Path("/sys/class/video4linux")) -> str:
    """'/dev/videoN' des Knotens mit index==0 und passender idVendor:idProduct
    (sysfs: <root>/videoN/index, <root>/videoN/device/../idVendor|idProduct).
    UvcError, wenn keiner oder mehr als einer passt."""

def usb_speed_mbps(device: str, sysfs_root: Path = Path("/sys/class/video4linux")) -> int | None:
    """<root>/videoN/device/../speed als int (5000 = USB3), None wenn unlesbar."""

def v4l2_set_controls(device: str, controls: list[tuple[str, int]], run=subprocess.run) -> None:
    """Je Control ein Aufruf `v4l2-ctl -d DEV --set-ctrl=name=value`, in
    gegebener Reihenfolge. UvcError bei Exitcode != 0 (mit stderr)."""

def v4l2_get_controls(device: str, names: list[str], run=subprocess.run) -> dict[str, int]:
    """`v4l2-ctl -d DEV --get-ctrl=a,b,c`; parst Zeilen 'name: 42' bzw.
    'auto_exposure: 1 (Manual Mode)' -> erste ganze Zahl. UvcError bei
    fehlendem Namen oder Exitcode != 0."""

class UvcSource:
    """FrameSource fuer `v4l2://`. Capture und Controls injizierbar."""
    def __init__(self, settings: CameraSettings, *, device: str | None = None,
                 capture_factory=None, set_controls=v4l2_set_controls,
                 get_controls=v4l2_get_controls, sysfs_root: Path = Path("/sys/class/video4linux")): ...
    def open(self) -> None:
        """1. device = device or find_uvc_device(settings.usb_id)
        2. capture = capture_factory(device) (Default: cv2.VideoCapture(device, cv2.CAP_V4L2), lazy import)
        3. FOURCC, Breite, Hoehe, FPS setzen; Breite/Hoehe zuruecklesen -> UvcError bei Abweichung
        4. set_controls(device, settings.ordered_controls())
        5. get_controls(...) fuer alle Namen; jede Abweichung -> UvcError(f"{name}: soll {soll}, ist {ist}")
        Bei Fehler: capture freigeben, dann raise."""
    def close(self) -> None: ...
    def frames(self) -> Iterator[Frame]:
        """read(); False -> Ende des Iterators nach READ_FAIL_TIMEOUT_S=2.0 s
        ohne erfolgreiches Bild (dann self.read_error gesetzt). Zeitstempel:
        round(capture.get(cv2.CAP_PROP_POS_MSEC) * 1e6); <= 0 oder <= vorheriger
        -> Bild verwerfen, self.rejected_timestamps += 1. Frame mit
        Timestamp(value_ns, TimeBaseKind.V4L2_MONOTONIC, UNKNOWN, None),
        frame_sequence fortlaufend ab 1 (nur gelieferte Bilder)."""
    source_id -> f"v4l2:{device}"
    capabilities -> frozenset({Capability.LIVE, Capability.EXPOSURE_CONTROL})
    def describe(self) -> dict:
        """{"camera_model", "device", "usb_id", "usb_speed_mbps",
            "size", "fourcc", "fps", "controls_requested": dict(ordered_controls),
            "controls_readback": {...}, "rejected_timestamps", "read_error"}"""
```

Die Konstante für `CAP_PROP_POS_MSEC` wird im Capture-Default gebunden; Tests übergeben eine Attrappe mit `set(prop, v)`, `get(prop)`, `read()`, `release()`, `isOpened()`. Damit die Attrappe die Property-IDs nicht kennen muss, verwendet `UvcSource` intern die Namen über ein kleines Mapping `_PROPS = {"fourcc": cv2.CAP_PROP_FOURCC, ...}`, das erst in `open()` (lazy cv2) gebaut wird; die Attrappe darf die echten cv2-Konstanten importieren (`cv2` ist im Test-venv vorhanden).

- Produces (Registry): Schema `v4l2` → `_open_v4l2(uri)`. URI-Form `v4l2:///dev/video8?settings=/pfad/camera.json` **oder** `v4l2://?settings=/pfad/camera.json` (Gerät dann per USB-ID). `settings` ist Pflicht (`ValueError` ohne). `picamera2`/`imx500` sind **nicht** mehr in `_REGISTRY`; `open_source("picamera2://…")`/`("imx500://…")` wirft `ValueError` mit Text, der `"IMX500 ausser Betrieb seit 2026-09-25"` und `"docs/project_history.md"` enthält. `known_schemes()` enthält `v4l2`, nicht `picamera2`/`imx500`.

- [ ] **Step 1: Failing tests** `tests/test_camera_settings.py`:

```python
import json
import pytest
from dispread.camera_settings import CameraSettings, load_camera_settings

GOOD = {
    "model": "logitech_streamcam", "usb_id": "046d:0893", "size": [1920, 1080],
    "fourcc": "YUYV", "fps": 30,
    "controls": {"focus_absolute": 48, "exposure_time_absolute": 166,
                 "white_balance_temperature": 5261, "gain": 11},
}

def test_roundtrip():
    s = CameraSettings.from_dict(GOOD)
    assert CameraSettings.from_dict(s.to_dict()) == s
    assert s.size == (1920, 1080)

def test_reihenfolge_automatiken_zuerst():
    names = [n for n, _ in CameraSettings.from_dict(GOOD).ordered_controls()]
    assert names[:3] == ["focus_automatic_continuous", "auto_exposure", "white_balance_automatic"]
    assert names.index("focus_absolute") > names.index("focus_automatic_continuous")
    assert ("zoom_absolute", 100) in CameraSettings.from_dict(GOOD).ordered_controls()

@pytest.mark.parametrize("mutate", [
    lambda d: d["controls"].pop("gain"),
    lambda d: d["controls"].update(zoom_absolute=200),
    lambda d: d["controls"].update(gain="11"),
    lambda d: d.pop("usb_id"),
])
def test_ungueltig_wird_abgelehnt(mutate):
    d = json.loads(json.dumps(GOOD)); mutate(d)
    with pytest.raises(ValueError):
        CameraSettings.from_dict(d)

def test_load_braucht_camera_block(tmp_path):
    p = tmp_path / "x.json"; p.write_text(json.dumps({"camera": GOOD}))
    assert load_camera_settings(p).usb_id == "046d:0893"
    p.write_text(json.dumps(GOOD))
    with pytest.raises(ValueError, match="camera"):
        load_camera_settings(p)
```

- [ ] **Step 2: Failing tests** `tests/test_uvc_source.py` (Attrappen, kein echtes Gerät):

```python
import cv2
import numpy as np
import pytest
from dispread.camera_settings import CameraSettings
from dispread.frames.uvc_source import (UvcError, UvcSource, find_uvc_device,
                                        v4l2_get_controls)
from dispread.records import TimeBaseKind

SETTINGS = CameraSettings.from_dict({
    "model": "logitech_streamcam", "usb_id": "046d:0893", "size": [1920, 1080],
    "fourcc": "YUYV", "fps": 30,
    "controls": {"focus_absolute": 48, "exposure_time_absolute": 166,
                 "white_balance_temperature": 5261, "gain": 11}})


class FakeCapture:
    def __init__(self, stamps_ms, size=(1920, 1080)):
        self.props = {}; self.stamps = list(stamps_ms); self.size = size
        self.released = False; self.current = 0.0
    def isOpened(self): return True
    def set(self, prop, value): self.props[prop] = value; return True
    def get(self, prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH: return float(self.size[0])
        if prop == cv2.CAP_PROP_FRAME_HEIGHT: return float(self.size[1])
        if prop == cv2.CAP_PROP_POS_MSEC: return self.current
        return self.props.get(prop, 0.0)
    def read(self):
        if not self.stamps: return False, None
        self.current = self.stamps.pop(0)
        return True, np.zeros((self.size[1], self.size[0], 3), np.uint8)
    def release(self): self.released = True


def make_source(cap, readback=None, calls=None):
    calls = calls if calls is not None else []
    def set_controls(dev, controls): calls.extend(controls)
    def get_controls(dev, names):
        values = dict(SETTINGS.ordered_controls()); values.update(readback or {})
        return {n: values[n] for n in names}
    return UvcSource(SETTINGS, device="/dev/video8", capture_factory=lambda d: cap,
                     set_controls=set_controls, get_controls=get_controls), calls


def test_frames_tragen_v4l2_monotonic_und_rohwert():
    src, _ = make_source(FakeCapture([1000.0, 1033.3]))
    src.open()
    frames = list(src.frames())
    assert [f.capture_timestamp.base for f in frames] == [TimeBaseKind.V4L2_MONOTONIC] * 2
    assert frames[0].capture_timestamp.value_ns == 1_000_000_000
    assert [f.frame_sequence for f in frames] == [1, 2]


def test_automatiken_werden_zuerst_gesetzt():
    src, calls = make_source(FakeCapture([1.0]))
    src.open()
    assert [n for n, _ in calls[:3]] == ["focus_automatic_continuous", "auto_exposure", "white_balance_automatic"]


def test_ruecklese_abweichung_bricht_ab_und_gibt_frei():
    cap = FakeCapture([1.0])
    src, _ = make_source(cap, readback={"focus_absolute": 60})
    with pytest.raises(UvcError, match="focus_absolute.*48.*60"):
        src.open()
    assert cap.released


def test_falsche_groesse_bricht_ab():
    cap = FakeCapture([1.0], size=(1280, 720))
    src, _ = make_source(cap)
    with pytest.raises(UvcError, match="1280x720"):
        src.open()


def test_null_und_rueckwaerts_zeitstempel_werden_verworfen_und_gezaehlt():
    src, _ = make_source(FakeCapture([0.0, 10.0, 9.0, 11.0]))
    src.open()
    frames = list(src.frames())
    assert [f.capture_timestamp.value_ns for f in frames] == [10_000_000, 11_000_000]
    assert src.describe()["rejected_timestamps"] == 2


def test_find_uvc_device_nimmt_index0_mit_passender_usb_id(tmp_path):
    usb = tmp_path / "usb" / "2-1"; iface = usb / "2-1:1.0"; iface.mkdir(parents=True)
    (usb / "idVendor").write_text("046d\n"); (usb / "idProduct").write_text("0893\n")
    for name, idx in (("video8", "0"), ("video9", "1")):
        d = tmp_path / "v4l" / name; d.mkdir(parents=True)
        (d / "index").write_text(idx + "\n"); (d / "device").symlink_to(iface)
    assert find_uvc_device("046d:0893", sysfs_root=tmp_path / "v4l") == "/dev/video8"
    with pytest.raises(UvcError):
        find_uvc_device("1234:5678", sysfs_root=tmp_path / "v4l")


def test_get_controls_parst_menue_ausgabe():
    class R: returncode = 0; stdout = "auto_exposure: 1 (Manual Mode)\ngain: 11\n"; stderr = ""
    assert v4l2_get_controls("/dev/video8", ["auto_exposure", "gain"], run=lambda *a, **k: R()) == {"auto_exposure": 1, "gain": 11}
```

Zusätzlich (Review Focus 2, Quellseite): ein Test, dass `frames()` nach wiederholtem `read() == False` spätestens nach `READ_FAIL_TIMEOUT_S` endet und `describe()["read_error"]` gesetzt ist — `READ_FAIL_TIMEOUT_S` im Test per `monkeypatch.setattr(uvc_source, "READ_FAIL_TIMEOUT_S", 0.05)` verkürzen.

- [ ] **Step 3: Failing tests Registry** (`open_source("imx500://?rpk=x")` → `ValueError` mit „IMX500 ausser Betrieb seit 2026-09-25"; `known_schemes()` enthält `"v4l2"`, nicht `"picamera2"`; `open_source("v4l2:///dev/video8")` ohne `settings` → `ValueError` mit „settings").
- [ ] **Step 4:** Tests laufen → FAIL.
- [ ] **Step 5:** Implementierung nach den Interfaces. `frames/__init__.py`-Docstring: `v4l2://` als aktive Kamera, `picamera2://`/`imx500://` „außer Betrieb seit 2026-09-25 (StreamCam statt IMX500, docs/project_history.md)"; Satz „`picamera2` wird ausschliesslich in den Kameramodulen importiert" ersetzen durch „`cv2`-Kamerazugriff erst in der Factory (Lazy Import)". Prüfen, ob `picamera_source.py`/`imx500_source.py` existieren (bisher nicht) — nichts anlegen.
- [ ] **Step 6:** Volle Suite + ruff → grün. Tests, die `picamera2://` als bekanntes Schema erwarten, auf die neue Außer-Betrieb-Meldung umstellen (im Bericht auflisten).
- [ ] **Step 7:** Bericht (kein Commit).

---

### Task 3: `sync-record.py` auf die StreamCam umstellen

**Files:**
- Modify: `scripts/sync-record.py`
- Test: `tests/test_sync_record.py`

**Interfaces:**
- Consumes: `load_camera_settings(path) -> CameraSettings`, `UvcSource`, `UvcError` (Task 2); `TimeBaseKind.V4L2_MONOTONIC` (Task 1).
- Produces:
  - CLI: `--source {synthetic,camera}` bleibt; neu `--camera-settings PATH` (Pflicht bei `--source camera`, `parser.error` sonst); neu `--camera-device PATH` (optional, sonst USB-ID-Suche). **Entfernt:** `--camera-size`, `--allow-large-sensor-mode`, `--stream-budget`, `--override-stream-budget`, `--scaler-crop`. Entfernt: `check_stream_budget`, `count_stream_starts`, `has_stream_on_failed`, `_read_kernel_log`, `_read_boot_id`, `_consult_counter_fallback`, `DEFAULT_STREAM_BUDGET*`, `EXIT_STREAM_BUDGET_EXHAUSTED`, `_parse_scaler_crop`, `_check_camera_size`, `_camera_frames` (Picamera2). `EXIT_NO_FRAMES_ACQUIRED` bleibt.
  - `measure_clock_offset_ns(samples: int = 5, clock=time.clock_gettime_ns) -> int`: Median aus `samples` Messungen `boottime - monotonic`, jede Messung eng geklammert (`m1 = MONO; b = BOOT; m2 = MONO; b - (m1+m2)//2`).
  - `count_frame_gaps(timestamps_ns: list[int], fps: float) -> dict`: `{"threshold_ns", "count", "max_gap_ns", "gaps": [{"after_value_ns", "gap_ns"}, ...]}` mit Schwelle `1.5 * 1e9 / fps`.
  - Generator-Vertrag intern: `_frame_generator(args)` liefert Tripel `(image, timestamp_dict, sensor_sequence)`; der Synthetik-Zweig liefert `sensor_sequence=None` wie bisher.
  - `session.json` neu: `camera` (= `UvcSource.describe()` bzw. `None` bei synthetic), `clock_offset_boottime_minus_monotonic_ns: {"start": int, "end": int}` (immer, auch bei synthetic), `frame_gaps` (bei camera, sonst `None`), `usb_speed_warning` (String bei `usb_speed_mbps < 5000`, sonst `None`). **Entfernt:** `scaler_crop_requested`, `scaler_crop_actual`, `sensor_mode_size`, `sensor_array_size`, `stream_starts_this_boot_before`, `stream_budget`, `stream_budget_source`.

- [ ] **Step 1: Bestehende IMX500-Tests entfernen.** In `tests/test_sync_record.py` alle Tests zu Budget, ScalerCrop, Sensorgeometrie, 960×720-Sperre und dem Picamera2-Fake (`_camera_frames`, `sys.modules["picamera2"]`) löschen. Liste der gelöschten Testnamen in den Bericht.
- [ ] **Step 2: Failing tests** (In-Prozess über `_load_sync_record_module()`; Kamera über Monkeypatch: `module.UvcSource` durch eine Fake-Klasse ersetzen, die `open/close/frames/describe` hat und `Frame`s mit `v4l2_monotonic` liefert):
  - `test_camera_ohne_camera_settings_bricht_ab` (Subprozess, `--source camera` ohne `--camera-settings` → Exit 2, stderr enthält `--camera-settings`).
  - `test_measure_clock_offset_nimmt_median`: `clock` liefert eine Folge, sodass die 5 Einzelwerte `[10, 12, 1000, 11, 13]` ergeben → 12.
  - `test_count_frame_gaps`: Zeitstempel bei 30 fps mit einer Lücke von 100 ms → `count == 1`, `max_gap_ns == 100_000_000`.
  - `test_session_json_traegt_camera_versatz_und_gaps`: Kamerazweig mit Fake-Quelle und `--source synthetic`-freiem Seriell-Aufbau wie in den bestehenden In-Prozess-Tests (erst lesen, wie dort der serielle Teil per `os.openpty()` gebaut wird). Erwartet: `session["camera"]["camera_model"] == "logitech_streamcam"`, `session["clock_offset_boottime_minus_monotonic_ns"].keys() == {"start", "end"}`, `session["frame_gaps"]["count"] >= 0`, `frames.jsonl` trägt `capture_timestamp.base == "v4l2_monotonic"`, `sensor_sequence is None`.
  - `test_uvc_fehler_beim_oeffnen_ergibt_acquisition_error`: Fake-`open()` wirft `UvcError("focus_absolute: soll 48, ist 60")` → `session["acquisition_error"]` enthält den Text, Exit `EXIT_NO_FRAMES_ACQUIRED`.
  - `test_frames_recorded_stimmt_wenn_aufnahmethread_haengt` (Review Focus 2): Fake-Quelle liefert 5 Bilder und blockiert dann (wartet auf ein `threading.Event`, das der Test erst nach `run()` setzt); `--duration 1`, `JOIN_TIMEOUT_S` per Monkeypatch klein (z. B. 0.5). Erwartet: `session["frames_recorded"] == 5` (Anzahl geschriebener PNG-Dateien) statt 0.
  - `test_synthetic_traegt_versatz_und_keine_kamera`: `--source synthetic` → `session["camera"] is None`, Versatz vorhanden, keine entfernten Felder mehr (`"scaler_crop_actual" not in session`, `"stream_budget" not in session`).
- [ ] **Step 3:** Tests → FAIL.
- [ ] **Step 4: Implementierung.**
  - Kamerazweig: `_uvc_frames(settings, device)` erzeugt `UvcSource(settings, device=device)`, `open()`, iteriert `frames()` und liefert `(frame.image, frame.capture_timestamp.to_dict(), None)`; am Ende (`finally`) `close()` und `describe()` in `state["camera"]` ablegen (auch bei Fehler; bei `UvcError` in `open()` enthält `describe()` die bis dahin bekannten Felder). `_camera_startup_guard` bleibt für den Kamerazweig (Timeout bis zum ersten Bild).
  - `frame_gaps` im Aufnahmethread aus den gelieferten `value_ns` (Liste sammeln, am Ende `count_frame_gaps(values, settings.fps)`).
  - Versatz: `start` direkt vor dem Start der Threads, `end` nach dem Join; beide mit `measure_clock_offset_ns()`.
  - **Bildzähler-Fix:** `_frame_writer_worker` schreibt `state["frames_recorded"] = frames_written` nach **jedem** geschriebenen Bild (nicht nur am Ende); `run()` liest danach den Stand, auch wenn der Writer-Join per Timeout endet. Zusätzlich `state["writer_finished"] = True` am Ende des Writers und `session["frame_writer_finished"]` in `session.json`.
  - Modul-Docstring und Kommentare: IMX500-/Picamera2-/OQ-22-Passagen, die den entfernten Code erklären, entfernen; einen kurzen Absatz ergänzen: „Kamera: Logitech StreamCam über `UvcSource` (seit 2026-09-25, IMX500 außer Betrieb, siehe docs/project_history.md)". Zeitbasis-Absatz: Frames tragen `v4l2_monotonic` roh, Umrechnung über `to_boottime_ns` mit `clock_offset_boottime_minus_monotonic_ns`.
  - `--frame-rate`-Vorgabe bleibt; Help-Text: bei camera drosselt es die geschriebenen Bilder, Kamera läuft mit `settings.fps`.
- [ ] **Step 5:** Volle Suite + ruff → grün.
- [ ] **Step 6:** Bericht (kein Commit).

---

### Task 4: Profil v3 und `harvest-setup.py` (`focus`, `propose`, `confirm`)

**Files:**
- Modify: `src/dispread/session_profile.py`
- Create: `src/dispread/focus_sweep.py`
- Modify: `scripts/harvest-setup.py`
- Test: `tests/test_session_profile.py`, `tests/test_focus_sweep.py`, `tests/test_harvest_setup.py`

**Interfaces:**
- Consumes: `CameraSettings`, `load_camera_settings`, `STREAMCAM_MODEL`, `STREAMCAM_USB_ID` (Task 2); `UvcSource`, `find_uvc_device`, `v4l2_set_controls`, `v4l2_get_controls` (Task 2).
- Produces:
  - `PROFILE_SCHEMA_VERSION = 3`; `SUPPORTED_SCHEMA_VERSIONS = (2, 3)`; `SessionProfile.camera: CameraSettings | None` (neues letztes Feld, Default `None`). `to_dict` schreibt `"camera"` (bei v3 Pflicht, bei v2 fehlt es). `load`: Version nicht in `(2, 3)` → `ValueError`; v3 ohne `camera` → `ValueError("Feld 'camera' fehlt ...")`; v3 mit `scaler_crop is not None` oder `native_scale != 1.0` → `ValueError`.
  - `focus_sweep.py`:

```python
def sharpness(gray_roi: np.ndarray) -> float:
    """Varianz des Laplace-Bildes (cv2.Laplacian, CV_64F)."""

def sweep_focus(measure: Callable[[int], float], coarse: Sequence[int] = range(0, 256, 8),
                fine_radius: int = 8, fine_step: int = 2, lo: int = 0, hi: int = 255
                ) -> tuple[int, list[tuple[int, float]]]:
    """measure(focus) setzt den Fokus und liefert die Schaerfe. Grob ueber `coarse`,
    dann fein um das Grob-Maximum (+-fine_radius, Schritt fine_step, auf [lo, hi]
    begrenzt). Rueckgabe: (bester Fokus, alle Messungen in Messreihenfolge).
    Bei Gleichstand gewinnt der zuerst gemessene Wert."""
```

  - `harvest-setup.py focus --out DIR [--hint-box x,y,w,h] [--device DEV] [--settle-s 1.0]`: öffnet die Kamera direkt über `cv2.VideoCapture` (Größe 1920×1080, YUYV, 30 fps), setzt `focus_automatic_continuous=0`, fährt `sweep_focus` (je Fokuswert: setzen, `settle_s` warten, 3 Bilder verwerfen, 1 Bild messen im Hint-Box-ROI oder im mittleren Drittel), setzt dann `auto_exposure=3`, `white_balance_automatic=1`, wartet 3 s, liest `exposure_time_absolute`, `white_balance_temperature`, `gain` zurück, baut `CameraSettings` mit dem besten Fokus und diesen Werten, schreibt `DIR/camera-settings.json` (`{"camera": settings.to_dict(), "focus_sweep": [...], "created_at_utc": ...}`), öffnet dann `UvcSource(settings)` (setzt und prüft alles) und speichert ein Kontrollbild `DIR/control.png`. Hardware-Aufrufe über eine Funktion `_open_camera_io(device)` gekapselt, damit der Test sie per Monkeypatch ersetzen kann.
  - `propose`: `--session-json` und `--scaler-crop` **entfernt**; neu `--camera-settings PATH` (Pflicht). Vorschlag trägt `"camera": settings.to_dict()`, `native_scale = 1.0`, `min_native_dot_column_px = min_source_dot_column_px`, `"scaler_crop": None`. Prüfen, dass das `--frame`-Bild die Größe `settings.size` hat, sonst Exit 2.
  - `confirm`: `--assume-native-scale` **entfernt**; schreibt Profil v3 mit `camera` aus dem Vorschlag; Vorschlag ohne `camera` → Exit 2 mit „Vorschlag ohne Kameraeinstellungen (IMX500-Vorschlag?) - propose mit --camera-settings neu ausfuehren".
  - `_compute_native_scale` entfällt.

- [ ] **Step 1: Failing tests Profil** (`tests/test_session_profile.py`): v3 speichern/laden inkl. `camera`; v2-Datei (bestehende Testfixture) lädt weiter mit `camera is None`; v1 und v4 → `ValueError`; v3 ohne `camera` → `ValueError`; v3 mit `scaler_crop=[0,0,10,10]` → `ValueError`.
- [ ] **Step 2: Failing tests `focus_sweep`**:

```python
from dispread.focus_sweep import sweep_focus

def test_sweep_findet_maximum_grob_dann_fein():
    calls = []
    def measure(f):
        calls.append(f); return -abs(f - 50)
    best, measured = sweep_focus(measure)
    assert best == 50
    assert calls[:32] == list(range(0, 256, 8))
    assert all(42 <= f <= 58 for f in calls[32:])

def test_sweep_bleibt_im_bereich():
    best, measured = sweep_focus(lambda f: f)
    assert best == 255 or best == max(f for f, _ in measured)
    assert all(0 <= f <= 255 for f, _ in measured)
```

  `sharpness`: scharfes Schachbrett > weichgezeichnetes Schachbrett (`cv2.GaussianBlur`).
- [ ] **Step 3: Failing tests `harvest-setup.py`**: `propose --camera-settings` schreibt `camera`, `native_scale == 1.0`; `propose` mit Bild falscher Größe → Exit 2; `confirm` erzeugt v3-Profil mit `camera`; `confirm` mit altem Vorschlag ohne `camera` → Exit 2; `focus` mit gemonkeypatchtem `_open_camera_io` (Attrappe liefert Bilder, deren Schärfe bei Fokus 48 maximal ist) schreibt `camera-settings.json` mit `controls.focus_absolute == 48`. Bestehende Tests zu `--session-json`/`--assume-native-scale`/`_compute_native_scale` löschen (im Bericht auflisten). Der Spiegel-Regressionstest bleibt.
- [ ] **Step 4:** Tests → FAIL.
- [ ] **Step 5:** Implementierung. Docstrings: ScalerCrop/Binning-Erklärungen entfernen; Satz „Bildpixel = native Pixel (StreamCam, Zoom fest 100)". `import-harvest.py` liest Profile: prüfen, dass v3-Profile dort funktionieren (`profile_sha256`, `profile_grid`, `profile_quad`), Test ergänzen, der eine Aufzeichnung mit v3-Profil importiert.
- [ ] **Step 6:** Volle Suite + ruff → grün.
- [ ] **Step 7:** Bericht (kein Commit).

---

### Task 5: Timing-Kalibrierung und `harvest.py`

**Files:**
- Create: `src/dispread/timing_calibration.py`
- Create: `scripts/timing-calibration.py`
- Modify: `scripts/harvest.py`
- Test: `tests/test_timing_calibration.py`, `tests/test_harvest.py`

**Interfaces:**
- Consumes: `SessionProfile` v3 mit `camera` (Task 4); `sync-record.py --camera-settings` (Task 3).
- Produces:

```python
# src/dispread/timing_calibration.py
CALIBRATION_SCHEMA_VERSION = 1
DEFAULT_CALIBRATION_PATH = Path("var/calibration/timing-streamcam.json")  # relativ zum Repo-Root

@dataclass(frozen=True, slots=True)
class TimingCalibration:
    camera_usb_id: str
    guard_margin_ms: float
    display_offset_ms: float
    measured_at_utc: str
    sources: tuple[dict, ...]      # je {"offset_json": str, "sha256": str}
    schema_version: int = CALIBRATION_SCHEMA_VERSION
    def to_dict(self) -> dict: ...
    def save(self, path: Path) -> None: ...   # atomar (tmp + os.replace), legt Elternverzeichnis an

def load_calibration(path: Path) -> TimingCalibration:
    """ValueError bei fehlender Datei (FileNotFoundError umwandeln), falscher
    schema_version, fehlendem Feld, nicht-endlichem oder <= 0 guard_margin_ms."""

def calibration_from_offset_reports(reports: list[Path], camera_usb_id: str,
                                    measured_at_utc: str) -> TimingCalibration:
    """Liest offset-analyse.json-Dateien (display-offset.py). Nimmt alle
    Populationen mit detected=True und M_s != None; guard_margin_ms =
    1000 * max(M_s) (wie VALIDATION.md 2026-09-23: groesster Wert),
    display_offset_ms = 1000 * delta_s derselben Population. ValueError,
    wenn keine Population detected ist. sources mit sha256 je Datei."""
```

  - `scripts/timing-calibration.py REPORT [REPORT ...] --out PATH [--camera-usb-id 046d:0893]`: baut und speichert; gibt M und Quelle aus; Exit 2 bei `ValueError`.
  - `harvest.py`:
    - neu `--calibration PATH` (Vorgabe `<repo>/var/calibration/timing-streamcam.json`); `--guard-margin-ms` **entfällt**, `_DEFAULT_GUARD_MARGIN_MS` entfällt; `run(..., calibration_path: Path, min_gap_ms, max_gap_ms)` statt `guard_margin_ms`.
    - Reihenfolge der Prüfungen vor jedem Subprozess: Profil laden → `profile.camera is None` → `HarvestError("IMX500-Profil (schema_version 2), Kamera ausser Betrieb - neues Profil mit harvest-setup anlegen")`; `resolution_ok` wie bisher; Kalibrierung laden (`ValueError` → `HarvestError` mit Pfad); `calibration.camera_usb_id != profile.camera.usb_id` → `HarvestError`; `hold_s`-Prüfung mit `calibration.guard_margin_ms`.
    - `sync_cmd`: `--camera-settings <profile_path>` (Profil hat Top-Level `camera`); `--scaler-crop` entfällt.
    - `gate_cmd`: `--guard-margin-ms` aus der Kalibrierung.
    - `harvest.json`: `scaler_crop` entfällt; neu `camera` (Profil-Block), `calibration_path`, `calibration_sha256`, `guard_margin_ms` (aus Kalibrierung).

- [ ] **Step 1: Failing tests** `tests/test_timing_calibration.py`: Bericht mit zwei detected-Populationen (M_s 0.36 und 0.695) → `guard_margin_ms == 695.0`; keine detected → `ValueError`; Roundtrip save/load; `load_calibration` auf fehlende Datei → `ValueError`; `guard_margin_ms = 0` bzw. `NaN` → `ValueError`; CLI schreibt die Datei und Exit 0.
- [ ] **Step 2: Failing tests** `tests/test_harvest.py` (bestehende Tests lesen; sie ersetzen `subprocess.run` per Monkeypatch — Muster übernehmen): v2-Profil → `HarvestError` mit „IMX500-Profil", kein Subprozess gestartet; fehlende Kalibrierung → `HarvestError`, kein Subprozess; Kalibrierung mit fremder USB-ID → `HarvestError`; Erfolgsfall: `sync_cmd` enthält `--camera-settings <profil>` und kein `--scaler-crop`, `gate_cmd` enthält `--guard-margin-ms` mit dem Kalibrierwert, `harvest.json` enthält `calibration_sha256`. Bestehende Tests, die `guard_margin_ms=695` voraussetzen, auf die Kalibrierungsdatei umstellen.
- [ ] **Step 3:** Tests → FAIL.
- [ ] **Step 4:** Implementierung. Modul-Docstring `harvest.py`: M kommt aus der Kalibrierung, 695 ms war IMX500-spezifisch.
- [ ] **Step 5:** Volle Suite + ruff → grün.
- [ ] **Step 6:** Bericht (kein Commit).

---

### Task 6: Werkbank-Kamera deaktivieren, Inbetriebnahme-Skript, Hardwaretest

**Files:**
- Modify: `src/dispread/workbench/controller.py` (~Zeile 1600–1670, Picamera2-Pfad)
- Modify: `src/dispread/__init__.py:8`, `src/dispread/detect/__init__.py:4` (Docstrings: IMX500 außer Betrieb)
- Rewrite: `scripts/camera-commissioning.sh`
- Create: `tests/test_uvc_hardware.py` (`@pytest.mark.hardware`)
- Test: `tests/test_workbench.py`, `tests/test_camera_preview.py`

**Interfaces:**
- Consumes: `UvcSource`, `find_uvc_device`, `usb_speed_mbps`, `load_camera_settings` (Task 2).
- Produces:
  - Werkbank: Im Nicht-Simulationsmodus wird **kein** `picamera2` importiert. Der Kamerathread setzt einen Fehlerzustand mit dem Text `"Kamera der Werkbank ausser Betrieb (IMX500 abgeloest durch StreamCam, 2026-09-25) - StreamCam-Anbindung folgt; Simulationsmodus (--simulate) nutzen"` und liefert keine Bilder, ohne Ausnahme nach außen. Wo genau der Fehler sichtbar wird, richtet sich nach dem bestehenden Fehlerpfad des Kamerathreads (erst lesen: wie meldet der Controller heute „Kamera nicht verfügbar"? denselben Kanal nutzen).
  - `camera-commissioning.sh`: prüft der Reihe nach (je Zeile `OK`/`FEHLER`/`WARNUNG`), Exit 0 nur ohne FEHLER:
    1. `v4l2-ctl` vorhanden;
    2. Gerät mit USB-ID `046d:0893` und `index == 0` in `/sys/class/video4linux` (Knoten ausgeben);
    3. USB-Geschwindigkeit `speed == 5000` (sonst WARNUNG „USB2 - Kamera an einen blauen USB3-Port");
    4. Format YUYV 1920x1080 in `v4l2-ctl --list-formats-ext` vorhanden;
    5. `focus_automatic_continuous=0` und `focus_absolute=48` setzen und zurücklesen (danach unverändert lassen);
    6. ein Testbild über `/home/me-systeme/picam-ai/.venv/bin/python` bzw. `./.venv/bin/python`, falls vorhanden (`cv2.VideoCapture`, YUYV 1920x1080, ein `read()` muss `True` liefern), gespeichert nach `var/diagnostics/camera-commissioning/test.png`.
  - Hardwaretest `tests/test_uvc_hardware.py` (nur mit `--mode=real`, Marker `hardware` wie im Bestand; `conftest.py` lesen): `UvcSource` mit Einstellungen `focus_absolute=48`, Rest aus aktuellem `v4l2_get_controls`-Stand öffnen, 30 Bilder lesen, Zeitstempel streng monoton, `describe()["controls_readback"]` = angefordert.

- [ ] **Step 1: Failing tests Werkbank**: Im Nicht-Simulationsmodus wird `picamera2` nicht importiert (`sys.modules`-Wächter: `monkeypatch.setitem(sys.modules, "picamera2", None)` → ein Import würde `ImportError` werfen; der Controller darf trotzdem nicht abstürzen) und der Fehlerzustand enthält „ausser Betrieb". Bestehende Tests, die einen Picamera2-Fake in den Controller einschleusen, entfernen oder auf den Außer-Betrieb-Zustand umstellen (im Bericht auflisten).
- [ ] **Step 2:** Tests → FAIL.
- [ ] **Step 3:** Implementierung Werkbank und Docstrings.
- [ ] **Step 4:** `camera-commissioning.sh` neu schreiben; `bash -n scripts/camera-commissioning.sh` muss sauber sein. **Das Skript wird vom Subagenten NICHT gegen die echte Kamera ausgeführt** (der Controller macht das).
- [ ] **Step 5:** Hardwaretest schreiben; ohne `--mode=real` muss er übersprungen werden (volle Suite prüfen). **Nicht** mit `--mode=real` ausführen.
- [ ] **Step 6:** Restsuche: `grep -rn -i "picamera2\|imx500\|ScalerCrop\|scaler_crop\|stream_budget" src scripts tests` — jede verbleibende Fundstelle im Bericht begründen (erlaubt: historische Kommentare mit „außer Betrieb", `import-harvest.py`-Beispielpfade alter Aufzeichnungen, Lesen von v2-Profilen, Tests für die Außer-Betrieb-Meldung).
- [ ] **Step 7:** Volle Suite + ruff → grün.
- [ ] **Step 8:** Bericht (kein Commit).

---

### Nach Task 6 (Controller, nicht Subagenten)

1. `scripts/camera-commissioning.sh` und den Hardwaretest gegen die echte StreamCam laufen lassen.
2. Doku gemäß Spec Abschnitt 5 (project_history, Konzept-Abweichung, CLAUDE.md, OQ-22-Nachtrag, neue OQ, TODO, status, CHANGELOG, VALIDATION, ROADMAP, Memory) — CHANGELOG im selben Commit wie der Code.
3. Messsitzung mit dem Nutzer: `harvest-setup.py focus` → `sync-record.py --source camera --camera-settings … --norm-schedule …` → `display-offset.py` → `timing-calibration.py` → dann Ernten.
