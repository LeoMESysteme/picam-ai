"""Bildquelle `v4l2://` - Logitech StreamCam (USB/UVC, 046d:0893).

Ersetzt die IMX500-/Picamera2-Anbindung (ausser Betrieb seit 2026-09-25,
siehe docs/project_history.md). `cv2` wird ausschliesslich hier und erst in
`UvcSource.open()` importiert (lazy), damit `dispread.frames` weiterhin ohne
OpenCV importierbar bleibt. `v4l2-ctl` wird nie direkt aufgerufen, sondern
immer ueber die injizierbaren `run`-Parameter - das ist die Voraussetzung
dafuer, dass diese Quelle ohne angeschlossene Kamera getestet werden kann.
"""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from dispread.camera_settings import SETTABLE_CONTROLS, CameraSettings
from dispread.frames.types import Capability, Frame
from dispread.records import TimeBaseKind, Timestamp, TimestampSemantics

#: Solange darf `capture.read()` erfolglos bleiben, bevor `frames()` endet.
READ_FAIL_TIMEOUT_S = 2.0

#: Kurze Pause zwischen zwei erfolglosen `read()`-Versuchen - vermeidet reines
#: Busy-Waiting waehrend der Kulanzfrist.
_READ_RETRY_DELAY_S = 0.01

_NUMBER_RE = re.compile(r"-?\d+")


class UvcError(RuntimeError):
    """Die StreamCam liess sich nicht wie im Profil verlangt einrichten."""


def find_uvc_device(usb_id: str, sysfs_root: Path = Path("/sys/class/video4linux")) -> str:
    """'/dev/videoN' des Knotens mit index==0 und passender idVendor:idProduct
    (sysfs: <root>/videoN/index, <root>/videoN/device/../idVendor|idProduct).
    UvcError, wenn keiner oder mehr als einer passt."""
    vendor, _, product = usb_id.partition(":")
    matches: list[str] = []
    if sysfs_root.is_dir():
        for entry in sorted(sysfs_root.iterdir()):
            index_file = entry / "index"
            if not index_file.exists():
                continue
            try:
                index = int(index_file.read_text().strip())
            except ValueError:
                continue
            if index != 0:
                continue
            device_link = entry / "device"
            try:
                iface = device_link.resolve(strict=True)
            except OSError:
                continue
            usb_dir = iface.parent
            try:
                found_vendor = (usb_dir / "idVendor").read_text().strip()
                found_product = (usb_dir / "idProduct").read_text().strip()
            except OSError:
                continue
            if found_vendor == vendor and found_product == product:
                matches.append(f"/dev/{entry.name}")
    if len(matches) != 1:
        raise UvcError(
            f"USB-ID {usb_id}: {len(matches)} passende Video-Knoten unter {sysfs_root} "
            "gefunden (erwartet genau 1)"
        )
    return matches[0]


def usb_speed_mbps(device: str, sysfs_root: Path = Path("/sys/class/video4linux")) -> int | None:
    """<root>/videoN/device/../speed als int (5000 = USB3), None wenn unlesbar."""
    entry = sysfs_root / Path(device).name
    try:
        iface = (entry / "device").resolve(strict=True)
        return int((iface.parent / "speed").read_text().strip())
    except (OSError, ValueError):
        return None


def v4l2_set_controls(
    device: str, controls: list[tuple[str, int]], run: Any = subprocess.run
) -> None:
    """Je Control ein Aufruf `v4l2-ctl -d DEV --set-ctrl=name=value`, in
    gegebener Reihenfolge. UvcError bei Exitcode != 0 (mit stderr)."""
    for name, value in controls:
        result = run(
            ["v4l2-ctl", "-d", device, f"--set-ctrl={name}={value}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise UvcError(
                f"v4l2-ctl --set-ctrl={name}={value} an {device} fehlgeschlagen: "
                f"{result.stderr.strip()}"
            )


def v4l2_get_controls(
    device: str, names: list[str], run: Any = subprocess.run
) -> dict[str, int]:
    """`v4l2-ctl -d DEV --get-ctrl=a,b,c`; parst Zeilen 'name: 42' bzw.
    'auto_exposure: 1 (Manual Mode)' -> erste ganze Zahl. UvcError bei
    fehlendem Namen oder Exitcode != 0."""
    result = run(
        ["v4l2-ctl", "-d", device, f"--get-ctrl={','.join(names)}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise UvcError(
            f"v4l2-ctl --get-ctrl an {device} fehlgeschlagen: {result.stderr.strip()}"
        )
    values: dict[str, int] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        name, _, rest = line.partition(":")
        name = name.strip()
        match = _NUMBER_RE.search(rest)
        if match is not None:
            values[name] = int(match.group())
    missing = [n for n in names if n not in values]
    if missing:
        raise UvcError(
            f"v4l2-ctl --get-ctrl an {device}: fehlende Werte fuer {', '.join(missing)}"
        )
    return {n: values[n] for n in names}


class UvcSource:
    """FrameSource fuer `v4l2://`. Capture und Controls injizierbar."""

    def __init__(
        self,
        settings: CameraSettings,
        *,
        device: str | None = None,
        capture_factory: Any = None,
        set_controls: Any = v4l2_set_controls,
        get_controls: Any = v4l2_get_controls,
        sysfs_root: Path = Path("/sys/class/video4linux"),
    ) -> None:
        self.settings = settings
        self._device_arg = device
        self.device: str | None = None
        self._capture_factory = capture_factory
        self._set_controls = set_controls
        self._get_controls = get_controls
        self._sysfs_root = sysfs_root
        self._capture: Any = None
        self._props: dict[str, int] = {}
        self.rejected_timestamps = 0
        self.read_error: str | None = None
        self._last_timestamp_ns: int | None = None
        self._sequence = 0
        self._controls_readback: dict[str, int] = {}

    def open(self) -> None:
        """1. device = device or find_uvc_device(settings.usb_id)
        2. capture = capture_factory(device) (Default: cv2.VideoCapture(device, cv2.CAP_V4L2), lazy import)
        3. FOURCC, Breite, Hoehe, FPS setzen; Breite/Hoehe zuruecklesen -> UvcError bei Abweichung
        4. set_controls(device, settings.ordered_controls())
        5. get_controls(...) fuer alle Namen; jede Abweichung -> UvcError(f"{name}: soll {soll}, ist {ist}")
        Bei Fehler: capture freigeben, dann raise."""
        import cv2

        self._props = {
            "fourcc": cv2.CAP_PROP_FOURCC,
            "width": cv2.CAP_PROP_FRAME_WIDTH,
            "height": cv2.CAP_PROP_FRAME_HEIGHT,
            "fps": cv2.CAP_PROP_FPS,
            "pos_msec": cv2.CAP_PROP_POS_MSEC,
        }

        self.device = self._device_arg or find_uvc_device(
            self.settings.usb_id, sysfs_root=self._sysfs_root
        )
        factory = self._capture_factory or (
            lambda d: cv2.VideoCapture(d, cv2.CAP_V4L2)
        )
        capture = factory(self.device)
        self._capture = capture
        try:
            fourcc_code = cv2.VideoWriter_fourcc(*self.settings.fourcc)
            capture.set(self._props["fourcc"], fourcc_code)
            width, height = self.settings.size
            capture.set(self._props["width"], width)
            capture.set(self._props["height"], height)
            capture.set(self._props["fps"], self.settings.fps)

            actual_width = int(capture.get(self._props["width"]))
            actual_height = int(capture.get(self._props["height"]))
            if (actual_width, actual_height) != (width, height):
                raise UvcError(
                    f"Aufloesung: soll {width}x{height}, ist {actual_width}x{actual_height}"
                )

            self._set_controls(self.device, self.settings.ordered_controls())

            names = list(SETTABLE_CONTROLS)
            readback = self._get_controls(self.device, names)
            self._controls_readback = dict(readback)
            for name in names:
                soll = self.settings.controls[name]
                ist = readback.get(name)
                if ist != soll:
                    raise UvcError(f"{name}: soll {soll}, ist {ist}")
        except Exception:
            capture.release()
            self._capture = None
            raise

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def frames(self) -> Iterator[Frame]:
        """read(); False -> Ende des Iterators nach READ_FAIL_TIMEOUT_S=2.0 s
        ohne erfolgreiches Bild (dann self.read_error gesetzt). Zeitstempel:
        round(capture.get(cv2.CAP_PROP_POS_MSEC) * 1e6); <= 0 oder <= vorheriger
        -> Bild verwerfen, self.rejected_timestamps += 1. Frame mit
        Timestamp(value_ns, TimeBaseKind.V4L2_MONOTONIC, UNKNOWN, None),
        frame_sequence fortlaufend ab 1 (nur gelieferte Bilder)."""
        capture = self._capture
        fail_deadline: float | None = None
        while True:
            ok, image = capture.read()
            if not ok:
                now = time.monotonic()
                if fail_deadline is None:
                    fail_deadline = now + READ_FAIL_TIMEOUT_S
                if now >= fail_deadline:
                    self.read_error = (
                        f"kein Bild innerhalb von READ_FAIL_TIMEOUT_S={READ_FAIL_TIMEOUT_S}s"
                    )
                    return
                time.sleep(_READ_RETRY_DELAY_S)
                continue
            fail_deadline = None

            pos_msec = capture.get(self._props["pos_msec"])
            value_ns = round(pos_msec * 1e6)
            if value_ns <= 0 or (
                self._last_timestamp_ns is not None and value_ns <= self._last_timestamp_ns
            ):
                self.rejected_timestamps += 1
                continue
            self._last_timestamp_ns = value_ns
            self._sequence += 1
            yield Frame(
                frame_sequence=self._sequence,
                image=image,
                capture_timestamp=Timestamp(
                    value_ns=value_ns,
                    base=TimeBaseKind.V4L2_MONOTONIC,
                    semantics=TimestampSemantics.UNKNOWN,
                    uncertainty_ns=None,
                ),
                source_id=self.source_id,
            )

    @property
    def source_id(self) -> str:
        return f"v4l2:{self.device}"

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.LIVE, Capability.EXPOSURE_CONTROL})

    def describe(self) -> dict[str, Any]:
        """{"camera_model", "device", "usb_id", "usb_speed_mbps",
        "size", "fourcc", "fps", "controls_requested": dict(ordered_controls),
        "controls_readback": {...}, "rejected_timestamps", "read_error"}"""
        return {
            "camera_model": self.settings.model,
            "device": self.device,
            "usb_id": self.settings.usb_id,
            "usb_speed_mbps": (
                usb_speed_mbps(self.device, sysfs_root=self._sysfs_root)
                if self.device is not None
                else None
            ),
            "size": self.settings.size,
            "fourcc": self.settings.fourcc,
            "fps": self.settings.fps,
            "controls_requested": dict(self.settings.ordered_controls()),
            "controls_readback": dict(self._controls_readback),
            "rejected_timestamps": self.rejected_timestamps,
            "read_error": self.read_error,
        }
