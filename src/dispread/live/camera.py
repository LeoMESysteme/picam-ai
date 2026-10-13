"""Einziger Halter der Kamera im Werkbank-Prozess.

Eine UVC-Kamera laesst nur einen Oeffner zu. Einrichtung, Vorschau, alte
Werkbank und Live-Sitzung bekommen ihre Bilder deshalb alle von hier: ein
Lesethread, das jeweils neueste Bild, Warten auf ein neueres Bild. Es wird
nichts gepuffert - wer langsamer ist, ueberspringt Bilder (Spec 2026-10-12
§2).
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from typing import Any

from dispread.frames import Frame, FrameSource


class CameraOwner:
    def __init__(
        self,
        source_factory: Callable[[], FrameSource],
        *,
        max_fps: float | None = None,
        gap_factor: float = 1.5,
    ) -> None:
        self._factory = source_factory
        self._max_fps = max_fps
        self._gap_factor = gap_factor
        self._cond = threading.Condition()
        self._lifecycle = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._source: FrameSource | None = None
        self._describe: dict[str, Any] = {}
        self._latest: tuple[int, Frame] | None = None
        self._sequence = 0
        self._frames = 0
        self._gaps = 0
        self._last_ts: int | None = None
        self._period_ns: float | None = None
        self._running = False
        self._error: str | None = None

    # -- Steuerung ---------------------------------------------------------
    def start(self) -> None:
        with self._lifecycle:
            with self._cond:
                if self._thread is not None and self._thread.is_alive():
                    if self._stop.is_set():
                        raise RuntimeError("Kamera-Lesethread noch nicht beendet")
                    return
            source = self._factory()
            try:
                source.open()
                describe = source.describe() if hasattr(source, "describe") else {}
                fps = describe.get("fps")
                stop = threading.Event()
                thread = threading.Thread(
                    target=self._run, args=(source, stop), name="camera-owner", daemon=True
                )
                with self._cond:
                    self._source, self._describe = source, dict(describe)
                    self._period_ns = 1e9 / float(fps) if fps else None
                    self._last_ts = None
                    self._running, self._error = True, None
                    self._stop, self._thread = stop, thread
                    thread.start()
            except Exception as exc:
                with contextlib.suppress(Exception):
                    source.close()
                with self._cond:
                    self._source, self._thread = None, None
                    self._running = False
                    self._error = str(exc)
                    self._stop.set()
                    self._cond.notify_all()
                raise

    def stop(self, timeout: float = 3.0) -> bool:
        """Leser stoppen; False bedeutet, dass er noch in der Quelle wartet."""
        with self._lifecycle:
            with self._cond:
                self._stop.set()
                thread = self._thread
                self._cond.notify_all()
            if thread is not None:
                thread.join(timeout)
                if thread.is_alive():
                    return False
            with self._cond:
                self._thread = None
                self._running = False
                self._cond.notify_all()
            return True

    def restart(self, source_factory: Callable[[], FrameSource] | None = None) -> None:
        with self._lifecycle:
            if not self.stop():
                raise RuntimeError("Kamera-Neustart abgelehnt: Lesethread noch nicht beendet")
            if source_factory is not None:
                self._factory = source_factory
            self.start()

    # -- Bilder ------------------------------------------------------------
    def latest(self) -> tuple[int, Frame] | None:
        with self._cond:
            return self._latest

    def wait_newer(self, after: int, timeout: float) -> tuple[int, Frame] | None:
        """Neuestes Bild mit Owner-Folgenummer > `after`, sonst None.

        Kehrt sofort mit None zurueck, wenn die Kamera nicht laeuft oder
        gestoppt wird und kein neueres Bild vorliegt."""
        with self._cond:
            stop = self._stop
            self._cond.wait_for(
                lambda: (self._latest is not None and self._latest[0] > after)
                or not self._running or stop.is_set(),
                timeout,
            )
            if self._latest is not None and self._latest[0] > after:
                return self._latest
            return None

    # -- Zustand -----------------------------------------------------------
    def status(self) -> dict[str, Any]:
        with self._cond:
            return {
                "running": self._running,
                "error": self._error,
                "frames": self._frames,
                "gaps": self._gaps,
                "source": dict(self._describe),
            }

    @property
    def source_id(self) -> str:
        source = self._source
        return source.source_id if source is not None else "camera-owner"

    def control_target(self) -> Any | None:
        """Die Quelle, wenn sie Regler setzen kann (UvcSource), sonst None."""
        source = self._source
        return source if source is not None and hasattr(source, "set_controls") else None

    # -- intern ------------------------------------------------------------
    def _run(self, source: FrameSource, stop: threading.Event) -> None:
        error: str | None = None
        try:
            for frame in source.frames():
                if stop.is_set():
                    break
                self._note(frame)
                if self._max_fps:
                    stop.wait(1.0 / self._max_fps)
            else:
                error = getattr(source, "read_error", None) or "Bildquelle beendet"
        except Exception as exc:  # noqa: BLE001 - wird als Kamerastatus gemeldet
            error = str(exc)
        finally:
            with contextlib.suppress(Exception):
                source.close()
            with self._cond:
                if self._thread is threading.current_thread():
                    self._running = False
                    if error and not stop.is_set():
                        self._error = error
                    self._cond.notify_all()

    def _note(self, frame: Frame) -> None:
        ts = frame.capture_timestamp.value_ns
        with self._cond:
            if self._last_ts is not None and self._period_ns:
                dt = ts - self._last_ts
                if dt > self._gap_factor * self._period_ns:
                    self._gaps += round(dt / self._period_ns) - 1
            self._last_ts = ts
            self._sequence += 1
            self._frames += 1
            self._latest = (self._sequence, frame)
            self._cond.notify_all()
