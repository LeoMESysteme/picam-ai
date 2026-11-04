"""Kurzer Laufverlauf in Zeiteimern, ohne Glaettung freigegebener Werte."""

from collections import deque
from math import floor
from threading import Lock

_STATUS = {'valid': 'v', 'transition': 't', 'unreadable': 'u', 'stale': 's'}
_RANK = {'v': 0, 't': 1, 'u': 2, 's': 3}


class RecentStrip:
    def __init__(self, window_s: float = 60.0, bucket_ms: int = 250) -> None:
        if window_s <= 0 or bucket_ms <= 0:
            raise ValueError('Fenster und Eimer muessen positiv sein')
        self._window_ms = window_s * 1000
        self._bucket_ms = bucket_ms
        self._buckets: deque[list] = deque()
        self._lock = Lock()

    def _expire(self, now_s: float) -> None:
        while self._buckets and self._buckets[0][0] <= now_s * 1000 - self._window_ms:
            self._buckets.popleft()

    def observe(self, now_s: float, status: str, value: float | None) -> None:
        code = _STATUS[status]
        bucket = floor(now_s * 1000 / self._bucket_ms) * self._bucket_ms
        with self._lock:
            self._expire(now_s)
            if not self._buckets or self._buckets[-1][0] != bucket:
                self._buckets.append([bucket, code, value if code == 'v' else None])
                return
            last = self._buckets[-1]
            if _RANK[code] > _RANK[last[1]]:
                last[1] = code
            if code == 'v':
                last[2] = value

    def to_list(self, now_s: float) -> list[list]:
        with self._lock:
            self._expire(now_s)
            if not self._buckets:
                return []
            origin = self._buckets[0][0]
            return [[bucket - origin, status, value] for bucket, status, value in self._buckets]
