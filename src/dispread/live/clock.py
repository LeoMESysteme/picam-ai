"""Zeitbasis der Live-Sitzung (Konzept.md §6, Spec 2026-10-12 §2).

StreamCam-Bilder tragen CLOCK_MONOTONIC (V4L2), serielle Telegramme
CLOCK_BOOTTIME. Verglichen wird nur ueber `records.to_boottime_ns` mit dem
hier gemessenen Versatz; `ClockLog` misst ihn bei Start, periodisch und am
Ende und liefert die Form, die `session.json` braucht.
Bei Werteplan-Freigaben prueft `checked_offset_bounds` den Versatz frisch,
damit Suspend auch zwischen den periodischen Auditproben auffaellt.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from dispread.records import SUSPEND_TOLERANCE_NS

#: Anzahl Einzelmessungen fuer `measure_clock_offset_ns` (Median).
CLOCK_OFFSET_SAMPLES = 5


def measure_clock_offset_ns(samples: int = CLOCK_OFFSET_SAMPLES, clock=time.clock_gettime_ns) -> int:
    """Median aus `samples` Einzelmessungen des Versatzes CLOCK_BOOTTIME
    minus CLOCK_MONOTONIC - die einzige Groesse, die `to_boottime_ns`
    (dispread.records) braucht, um einen `v4l2_monotonic`-Zeitstempel der
    StreamCam nach CLOCK_BOOTTIME umzurechnen.

    Jede Einzelmessung ist eng geklammert (MONOTONIC vor und nach der
    BOOTTIME-Messung, Mittelwert der beiden als Bezugspunkt) - so faellt der
    durch die drei Aufrufe selbst eingebrachte Fehler klein aus. Der Median
    (statt des Mittelwerts) filtert einen einzelnen Ausreisser heraus (z.B.
    ein Scheduler-Aussetzer zwischen den drei Aufrufen)."""
    offsets: list[int] = []
    for _ in range(samples):
        m1 = clock(time.CLOCK_MONOTONIC)
        b = clock(time.CLOCK_BOOTTIME)
        m2 = clock(time.CLOCK_MONOTONIC)
        offsets.append(b - (m1 + m2) // 2)
    offsets.sort()
    return offsets[len(offsets) // 2]


class ClockLog:
    def __init__(
        self,
        measure: Callable[[], int] = measure_clock_offset_ns,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._measure = measure
        self._monotonic_ns = monotonic_ns
        self.samples: list[tuple[int, int]] = []

    def sample(self) -> int:
        offset = int(self._measure())
        self.samples.append((int(self._monotonic_ns()), offset))
        return offset

    def checked_offset_bounds(self) -> dict[str, int]:
        """Frischer Versatz vor einer zeitabhaengigen Live-Freigabe.

        Die Endgrenze stammt immer von jetzt, damit ein Suspend seit der
        periodischen Probe nicht unbemerkt bleibt. Nur Versatzspruenge werden
        zusaetzlich ins Audit aufgenommen, keine Probenliste je Bild aufgebaut.
        `to_boottime_ns` entscheidet anhand beider Grenzen ueber die Umrechnung.
        """
        offset = int(self._measure())
        if not self.samples or abs(offset - self.samples[-1][1]) > SUSPEND_TOLERANCE_NS:
            self.samples.append((int(self._monotonic_ns()), offset))
        return {'start': self.samples[0][1], 'end': offset}

    @property
    def last_sample_monotonic_ns(self) -> int | None:
        return self.samples[-1][0] if self.samples else None

    def to_session(self, *, ended: bool) -> dict:
        if not self.samples:
            return {"start": None, "end": None, "samples": []}
        return {
            "start": self.samples[0][1],
            "end": self.samples[-1][1] if ended else None,
            "samples": [[t, offset] for t, offset in self.samples],
        }
