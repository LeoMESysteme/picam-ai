"""Begrenztes Fenster der Hauptursachen, bezogen auf verarbeitete Bilder."""

from collections import Counter, deque
from threading import Lock

from dispread.records import ValueStatus


class RejectionWindow:
    """Letzte 10 s Verarbeitungszeit, maximal 4096 Bilder (> 400 Bilder/s).

    Pro Bild zaehlt nur der erste (spezifischste) Grund. Der Nenner enthaelt
    auch VALID. Bei unrealistischer Ueberlast wird das Fenster als begrenzt
    markiert, statt einen vollstaendigen Zehnsekundenbefund zu behaupten.
    """

    def __init__(self) -> None:
        self._frames: deque[tuple[float, str | None]] = deque(maxlen=4096)
        self._lock = Lock()
        self._limited_at: float | None = None

    def _expire(self, now: float) -> None:
        while self._frames and self._frames[0][0] <= now - 10.0:
            self._frames.popleft()

    def observe(self, now: float, status: ValueStatus, reasons: tuple[str, ...]) -> None:
        with self._lock:
            self._expire(now)
            if len(self._frames) == self._frames.maxlen:
                self._limited_at = now
            reason = None if status is ValueStatus.VALID else next(iter(reasons), 'no_value')
            self._frames.append((now, reason))

    def snapshot(self, now: float) -> dict:
        with self._lock:
            self._expire(now)
            n = len(self._frames)
            counts = Counter(reason for _, reason in self._frames if reason is not None)
            return {
                'window_s': 10.0, 'frames': n,
                'limited': self._limited_at is not None and now - self._limited_at < 10.0,
                'causes': [{'reason': reason, 'count': count, 'fraction': count / n}
                           for reason, count in counts.most_common(5)],
            }
