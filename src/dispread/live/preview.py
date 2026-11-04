"""Geteilte JPEG-Vorschau; Kodierung laeuft getrennt von der Messung."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from dispread.frames import Frame


@dataclass(frozen=True)
class PreviewFrame:
    seq: int
    cap_ns: int
    jpeg: bytes
    hud: dict


class RateGovernor:
    """Messlast hat Vorrang; erst nach fuenf ruhigen Sekunden erholen."""

    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._encodes: deque[float] = deque(maxlen=10)
        self._last_trigger: float | None = None
        self._reason: Literal["messung", "kodierung"] | None = None

    def update(self, skipped_recent: float | None, encode_ms: float) -> None:
        self._encodes.append(encode_ms)
        now = self._clock()
        if skipped_recent is not None and skipped_recent > 0.10:
            self._reason = "messung"
            self._last_trigger = now
        elif sum(self._encodes) / len(self._encodes) > 25:
            self._reason = "kodierung"
            self._last_trigger = now
        elif self._last_trigger is not None and now - self._last_trigger >= 5:
            self._reason = None

    @property
    def interval_s(self) -> float:
        return 1 / 15 if self._reason is None else 1 / 5

    @property
    def reason(self) -> Literal["messung", "kodierung"] | None:
        return self._reason


class PreviewEncoder:
    """Nur das neueste JPEG halten, alle Betrachter teilen denselben Lock.

    Der Lock gehoert allein der Vorschau. CameraOwner.latest() gibt seinen
    eigenen Lock bereits vor der Kodierung frei. Das HUD wird auch bei
    gleicher Sequenz neu gelesen, damit alte Ablesungen als stale ankommen.
    """

    def __init__(
        self,
        latest: Callable[[], tuple[int, Frame] | None],
        hud_of: Callable[[], dict | None],
        *,
        width: int = 960,
        quality: int = 80,
        governor: RateGovernor,
    ) -> None:
        self._latest = latest
        self._hud_of = hud_of
        self._width = width
        self._quality = quality
        self._governor = governor
        self._lock = threading.Lock()
        self._seq: int | None = None
        self._jpeg: bytes | None = None

    def frame(self) -> PreviewFrame | None:
        import cv2

        with self._lock:
            latest = self._latest()
            if latest is None:
                return None
            seq, frame = latest
            encode_ms = None
            if seq != self._seq:
                started = time.perf_counter()
                image = frame.image
                height = round(image.shape[0] * self._width / image.shape[1])
                small = cv2.resize(image, (self._width, height))
                ok, encoded = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, self._quality])
                self._seq = seq
                self._jpeg = encoded.tobytes() if ok else None
                encode_ms = (time.perf_counter() - started) * 1000
            # Erst nach dem Kodieren lesen: eine inzwischen veraltete
            # Ablesung darf nicht mit ihrem vorherigen valid-Status reisen.
            info = deepcopy(self._hud_of() or {})
            if encode_ms is not None:
                self._governor.update(
                    (info.get("proc") or {}).get("skipped_recent"),
                    encode_ms,
                )
            if self._jpeg is None:
                return None
            cap_ns = frame.capture_timestamp.value_ns
            hud = {
                "seq": seq, "cap_ns": cap_ns, "w": frame.image.shape[1], "h": frame.image.shape[0],
                **{key: info.get(key) for key in ("rec", "track", "cells", "proc")},
                "preview": {"fps": 15 if self._governor.reason is None else 5,
                            "throttled": self._governor.reason},
            }
            return PreviewFrame(seq=seq, cap_ns=cap_ns, jpeg=self._jpeg, hud=hud)
