"""Vorschau teilt Kodierungen und gibt der Messung Vorrang."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import cv2
import numpy as np
import pytest

from dispread.frames import Frame
from dispread.records import TimeBaseKind, Timestamp


def camera_frame(seq=7):
    return Frame(frame_sequence=99, image=np.zeros((108, 192, 3), np.uint8),
                 capture_timestamp=Timestamp(value_ns=123456 + seq, base=TimeBaseKind.SYNTHETIC),
                 source_id="vorschau-test")


def frame_info():
    return {
        "rec": {"seq": 6, "status": "valid", "text": "+0.62427", "unit": "mV/V",
                "reasons": [], "age_s": 0.04},
        "track": {"quad": [[20, 20], [180, 20], [180, 80], [20, 80]], "score": 0.93,
                  "shift_px": 0.4, "rotation_deg": 0.0, "reason": None, "correcting": False,
                  "regions": [{"c": [28, 29], "s": 15, "peak": 0.92, "ok": True}]},
        "cells": [{"i": i, "best": "7", "margin": 0.41, "uncertain": False} for i in range(9)],
        "proc": {"fps": 14.8, "latency_ms": None, "skipped_recent": 0.02},
    }


def test_encoder_encodes_each_sequence_once(monkeypatch):
    from types import SimpleNamespace

    from dispread.live.preview import PreviewEncoder, RateGovernor

    calls = []
    encode = cv2.imencode

    def spy(*args):
        calls.append(args[2])
        return encode(*args)

    monkeypatch.setattr(cv2, "imencode", spy)
    image = camera_frame()
    latest = [7, image]
    now = [0.0]
    monkeypatch.setattr("dispread.live.preview.time", SimpleNamespace(
        monotonic=lambda: now[0], perf_counter=lambda: 0.0))
    encoder = PreviewEncoder(lambda: tuple(latest), frame_info, governor=RateGovernor(lambda: 0.0))
    first, second = encoder.frame(), encoder.frame()
    assert first.jpeg == second.jpeg and first.seq == second.seq == 7
    assert calls == [[cv2.IMWRITE_JPEG_QUALITY, 80]]
    latest[0] = 8
    # Die naechste Sequenz kommt nach dem gemeinsamen Vorschauintervall.
    now[0] = 1 / 15
    assert encoder.frame().seq == 8
    assert len(calls) == 2
    assert not image.image.any()
    assert cv2.imdecode(np.frombuffer(first.jpeg, np.uint8), cv2.IMREAD_COLOR).shape == (540, 960, 3)


@pytest.mark.parametrize("skips, interval", [(0.0, 1 / 15), (0.2, 0.2)])
def test_encoder_caches_changing_sequences_for_shared_interval(monkeypatch, skips, interval):
    from types import SimpleNamespace

    from dispread.live import preview

    now = [0.0]
    monkeypatch.setattr(preview, "time", SimpleNamespace(monotonic=lambda: now[0], perf_counter=lambda: 0.0))
    latest = [7, camera_frame(7)]
    info = frame_info()
    info["proc"]["skipped_recent"] = skips
    encoder = preview.PreviewEncoder(lambda: tuple(latest), lambda: info,
                                     governor=preview.RateGovernor(lambda: now[0]))
    first = encoder.frame()
    latest[:] = [8, camera_frame(8)]
    now[0] = interval - 0.001
    info["rec"]["status"] = "stale"
    cached = encoder.frame()
    assert (cached.seq, cached.cap_ns, cached.jpeg) == (first.seq, first.cap_ns, first.jpeg)
    assert cached.hud["seq"] == 7 and cached.hud["cap_ns"] == first.cap_ns
    assert cached.hud["rec"]["status"] == "stale"
    now[0] = interval
    assert encoder.frame().seq == 8


def test_encoder_keeps_target_rate_with_slow_encoding(monkeypatch):
    from types import SimpleNamespace

    from dispread.live import preview

    now = [0.0]
    starts = []
    encode = cv2.imencode

    def slow(*args):
        starts.append(now[0])
        now[0] += 0.015
        return encode(*args)

    monkeypatch.setattr(preview, 'time', SimpleNamespace(
        monotonic=lambda: now[0], perf_counter=lambda: now[0]))
    monkeypatch.setattr(cv2, 'imencode', slow)
    encoder = preview.PreviewEncoder(lambda: (len(starts), camera_frame()), frame_info,
                                     governor=preview.RateGovernor(lambda: now[0]))
    # Zwei Betrachter fragen versetzt alle 5 ms nach dem neuesten Bild.
    while now[0] < 1:
        encoder.frame()
        now[0] += 0.005
    assert len(starts) == 15
    assert all(1 / 15 <= b - a <= 1 / 15 + 0.005 for a, b in zip(starts, starts[1:], strict=False))


def test_encoder_concurrent_calls_share_encoding(monkeypatch):
    from dispread.live.preview import PreviewEncoder, RateGovernor

    calls = []
    encode = cv2.imencode

    def spy(*args):
        calls.append(1)
        return encode(*args)

    monkeypatch.setattr(cv2, "imencode", spy)
    encoder = PreviewEncoder(lambda: (7, camera_frame()), frame_info, governor=RateGovernor(lambda: 0.0))
    with ThreadPoolExecutor(max_workers=4) as pool:
        frames = list(pool.map(lambda _: encoder.frame(), range(8)))
    assert all(f.seq == 7 and f.jpeg.startswith(b"\xff\xd8") for f in frames)
    assert len(calls) == 1


def test_encoder_missing_or_failed_image_is_unavailable(monkeypatch):
    from dispread.live.preview import PreviewEncoder, RateGovernor

    latest = [None]
    encoder = PreviewEncoder(lambda: latest[0], lambda: None, governor=RateGovernor(lambda: 0.0))
    assert encoder.frame() is None
    latest[0] = (7, camera_frame())
    calls = []

    def fail(*args):
        calls.append(1)
        return False, None

    monkeypatch.setattr(cv2, "imencode", fail)
    assert encoder.frame() is None
    assert encoder.frame() is None
    assert len(calls) == 1


def test_encoder_refreshes_hud_without_mutating_session_snapshot(monkeypatch):
    from types import SimpleNamespace

    from dispread.live.preview import PreviewEncoder, RateGovernor

    monkeypatch.setattr("dispread.live.preview.time", SimpleNamespace(monotonic=lambda: 0.0, perf_counter=lambda: 0.0))
    info = frame_info()
    original = deepcopy(info)
    encoder = PreviewEncoder(lambda: (7, camera_frame()), lambda: info, governor=RateGovernor(lambda: 0.0))
    first = encoder.frame()
    assert set(first.hud) == {"seq", "cap_ns", "w", "h", "rec", "track", "cells", "proc", "preview"}
    assert (first.hud["w"], first.hud["h"], first.cap_ns) == (192, 108, 123463)
    assert first.hud["rec"]["seq"] == 6
    assert first.hud["preview"] == {"fps": 15, "throttled": None}
    first.hud["track"]["quad"][0][0] = -1
    assert info == original
    info["rec"]["status"] = "stale"
    info["rec"]["age_s"] = 0.6
    second = encoder.frame()
    assert second.jpeg == first.jpeg
    assert second.hud["rec"]["status"] == "stale" and second.hud["rec"]["age_s"] == 0.6


def test_encoder_reads_fresh_hud_after_encoding(monkeypatch):
    from dispread.live.preview import PreviewEncoder, RateGovernor

    now = [0.0]
    encode = cv2.imencode

    def slow(*args):
        now[0] = 0.6
        return encode(*args)

    def hud():
        info = frame_info()
        info["rec"]["age_s"] = now[0]
        info["rec"]["status"] = "stale" if now[0] > 0.5 else "valid"
        return info

    monkeypatch.setattr(cv2, "imencode", slow)
    encoder = PreviewEncoder(lambda: (7, camera_frame()), hud, governor=RateGovernor(lambda: now[0]))
    assert encoder.frame().hud["rec"]["status"] == "stale"


def test_rate_governor_throttles_on_skips_and_recovers_after_5s():
    from dispread.live.preview import RateGovernor

    now = [0.0]
    governor = RateGovernor(lambda: now[0])
    governor.update(0.10, 25.0)
    assert governor.interval_s == pytest.approx(1 / 15) and governor.reason is None
    governor.update(0.2, 1.0)
    assert governor.interval_s == 0.2 and governor.reason == "messung"
    now[0] = 4.9
    governor.update(0.0, 1.0)
    assert governor.interval_s == 0.2
    now[0] = 5.1
    governor.update(None, 1.0)
    assert governor.interval_s == pytest.approx(1 / 15) and governor.reason is None


def test_rate_governor_throttles_on_slow_encode():
    from dispread.live.preview import RateGovernor

    now = [0.0]
    governor = RateGovernor(lambda: now[0])
    for _ in range(10):
        governor.update(None, 26.0)
    assert governor.interval_s == 0.2 and governor.reason == "kodierung"
    # Eine schnelle Kodierung ersetzt nur eine Probe im Zehnerfenster.
    governor.update(None, 24.0)
    now[0] = 6.0
    governor.update(None, 24.0)
    assert governor.interval_s == 0.2
    for _ in range(10):
        governor.update(None, 1.0)
    now[0] = 10.9
    governor.update(None, 1.0)
    assert governor.interval_s == 0.2
    now[0] = 11.1
    governor.update(None, 1.0)
    assert governor.interval_s == pytest.approx(1 / 15)


def test_service_preview_shares_jpeg_and_only_shows_active_run(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from dispread.live.service import LiveService

    calls = []
    encode = cv2.imencode

    def spy(*args):
        calls.append(1)
        return encode(*args)

    monkeypatch.setattr(cv2, "imencode", spy)
    service = LiveService(SimpleNamespace(latest=lambda: (7, camera_frame())), tmp_path,
                          diagnostic_staging_root=tmp_path / "staging")
    service._session = SimpleNamespace(frame_info=frame_info)
    idle = service.preview_frame()
    assert idle.hud["rec"] is None and idle.hud["track"] is None and idle.hud["cells"] is None
    service._state = "running"
    active = service.preview_frame()
    assert active.hud["rec"]["seq"] == 6
    assert service.preview_jpeg() == active.jpeg == idle.jpeg
    assert len(calls) == 1
    service._state = "stopped"
    assert service.preview_frame().hud["track"] is None
