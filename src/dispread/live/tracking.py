"""Bestaetigtes Quad als DisplayLocator aus Rahmenbereichen oder altem ECC.

Registriert jedes Bild gegen das Referenzbild der Bestaetigung (nie gegen das
Vorbild, siehe dispread.track). Verletzt die Nachfuehrung ihre Grenzen, gibt
es keinen Kandidaten: der Wert wird UNREADABLE, der letzte laeuft nicht
weiter (Konzept.md §4).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from dispread.detect import DisplayCandidate
from dispread.frames import Frame
from dispread.live.frame_tracking import FrameTracker, FrameTrackingConfig, RegionProposal
from dispread.track import QuadTracker, TrackConfig, TrackResult

LOCATOR_ID = "tracked_confirmed_quad"


class TrackedQuadLocator:
    def __init__(
        self, reference_image: np.ndarray, quad: Sequence[Sequence[float]], *, config: TrackConfig = TrackConfig()
    ) -> None:
        self._tracker = QuadTracker(reference_image, quad, config=config)
        self.last_reason: str | None = None
        self.last_track: TrackResult | None = None

    @property
    def locator_id(self) -> str:
        return LOCATOR_ID

    def locate(self, frame: Frame) -> tuple[DisplayCandidate, ...]:
        result = self._tracker.update(frame.image)
        self.last_track = result
        if result.quad is None:
            self.last_reason = f"tracking_lost:{result.reason}"
            return ()
        self.last_reason = None
        return (DisplayCandidate(quad=result.quad, score=result.score, locator_id=LOCATOR_ID, role_hint="main"),)


class ConfirmedRegionLocator:
    """Nur die bestaetigten Rahmenfenster gegen das feste Referenzbild pruefen."""

    locator_id = "rahmenbereiche_confirmed_quad"

    def __init__(self, reference_image: np.ndarray, quad: Sequence[Sequence[float]], live_tracking: dict) -> None:
        config = FrameTrackingConfig.from_dict(live_tracking["config"])
        proposal = RegionProposal.from_dict(live_tracking["proposal"])
        if not proposal.ok:
            raise ValueError("Rahmenvorschlag ungeeignet")
        self._tracker = FrameTracker(reference_image, quad, proposal, config)
        self.last_reason: str | None = None
        self.last_track: TrackResult | None = None

    def locate(self, frame: Frame) -> tuple[DisplayCandidate, ...]:
        result = self._tracker.update(frame.image)
        self.last_track = result
        if result.quad is None:
            self.last_reason = f"tracking_lost:{result.reason}"
            return ()
        self.last_reason = None
        return (DisplayCandidate(quad=result.quad, score=result.score, locator_id=self.locator_id, role_hint="main"),)
