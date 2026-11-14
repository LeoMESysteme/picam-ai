"""Schutzprobe einer Stilllegung als eigener Prozess (TB 2026-11-11, Review G4).

Aufruf nur durch ``session.ProbeProcess``: ``python -m dispread.live.region_probe``
liest ``(payload, base, target)`` als Pickle von stdin und schreibt
``('ok', Ergebnis)`` oder ``('error', Text)`` als Pickle nach stdout. Eigener
Interpreter: kein GIL-Wettbewerb mit dem Leserthread, Prioritaet nice 19, und
kein erneutes Importieren des Hauptmoduls der Werkbank. Beide Enden stammen
aus demselben Prozessbaum; es werden keine fremden Daten entpickelt.
"""

from __future__ import annotations

import os
import pickle
import sys


def run(payload: dict, base, target) -> dict:
    """Tracker aus dem Payload aufbauen und FrameTracker.bias_probe rechnen."""
    from dispread.live.frame_tracking import FrameTracker, FrameTrackingConfig, RegionProposal

    config = FrameTrackingConfig.from_dict(payload["config"])
    tracker = FrameTracker(payload["reference"], payload["quad"], RegionProposal.from_dict(payload["proposal"]),
                           config)
    return tracker.bias_probe(base, target)


def main() -> None:
    try:
        os.nice(19)
    except OSError:
        pass
    try:
        payload, base, target = pickle.loads(sys.stdin.buffer.read())
        outcome = ("ok", run(payload, base, target))
    except Exception as exc:  # noqa: BLE001 - Ergebnis ist dann "keine Stilllegung"
        outcome = ("error", f"{type(exc).__name__}: {exc}")
    sys.stdout.buffer.write(pickle.dumps(outcome))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
