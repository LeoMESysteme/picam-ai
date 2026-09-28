"""Hardwaretest der Logitech StreamCam (USB/UVC, 046d:0893).

Nur mit `--mode=real` (Marker `hardware`, siehe tests/conftest.py) - braucht
die angeschlossene StreamCam und ein installiertes `v4l2-ctl`. Ohne
`--mode=real` wird diese Datei uebersprungen, siehe
test_skipped_without_mode_real weiter unten.

Absichtlich real, kein Fake: dieser Test ist die Gegenprobe zu allen
gemockten UvcSource-Tests (tests/test_uvc_source.py) - er prueft, dass die
echte Kamera unter echtem `v4l2-ctl` das liefert, was der Vertrag verlangt:
strikt monotone Zeitstempel und eine Ruecklesung, die exakt der Anforderung
entspricht.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from dispread.camera_settings import (
    SETTABLE_CONTROLS,
    STREAMCAM_MODEL,
    STREAMCAM_USB_ID,
    CameraSettings,
)
from dispread.frames.uvc_source import UvcSource, find_uvc_device, v4l2_get_controls

FRAME_COUNT = 30


@pytest.mark.hardware
def test_streamcam_liefert_monotone_zeitstempel_und_controls_readback():
    device = find_uvc_device(STREAMCAM_USB_ID)

    # Fokus fest auf den Kommissionierungswert (Schritt 5 von
    # camera-commissioning.sh); alle uebrigen Regler bleiben, wie sie gerade
    # am Geraet stehen - kein Erfinden von Vorgabewerten.
    current = v4l2_get_controls(device, [n for n in SETTABLE_CONTROLS if n != "focus_absolute"])
    controls = dict(current, focus_absolute=48)

    settings = CameraSettings(
        model=STREAMCAM_MODEL,
        usb_id=STREAMCAM_USB_ID,
        size=(1920, 1080),
        fourcc="YUYV",
        fps=30,
        controls=controls,
    )

    source = UvcSource(settings, device=device)
    source.open()
    try:
        timestamps = []
        for frame in source.frames():
            timestamps.append(frame.capture_timestamp.value_ns)
            if len(timestamps) >= FRAME_COUNT:
                break

        assert len(timestamps) == FRAME_COUNT
        assert all(b > a for a, b in pairwise(timestamps)), "Zeitstempel nicht streng monoton"

        described = source.describe()
        # I-2 final-review.md: controls_readback deckt jetzt ALLE gesetzten
        # Regler ab (Automatiken + feste Werte + die vier aus `controls`),
        # nicht mehr nur die vier SETTABLE_CONTROLS - Vergleich deshalb gegen
        # `settings.ordered_controls()`, nicht gegen `controls` allein.
        assert described["controls_readback"] == dict(settings.ordered_controls())
    finally:
        source.close()
