"""Aufgezeichnete Clips zurueckspielen.

Ein Clip ist die kleinste Einheit belastbarer Validierung: der Bediener stellt
am Geraet einen Wert ein, tippt ihn *einmal* ein und nimmt ein paar Sekunden
auf. Jeder Frame traegt damit dasselbe Label, ohne Einzelbildannotation.

Der Sollwert steht in `raw_metadata["ground_truth"]` - wie bei
`SyntheticSource`. Die Pipeline sieht ihn nie; nur der Benchmark liest ihn.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import cv2

from dispread.frames.types import Capability, Frame
from dispread.records import TimeBaseKind, Timestamp, TimestampSemantics

CLIP_SCHEMA_VERSION = 1


class ReplaySource:
    """Bildquelle aus einem aufgezeichneten Clipverzeichnis."""

    def __init__(self, session_dir: str) -> None:
        self.directory = Path(session_dir)
        self.clip: dict[str, Any] = {}

    # -- FrameSource ------------------------------------------------------
    def open(self) -> None:
        manifest = self.directory / "clip.json"
        if not manifest.exists():
            raise FileNotFoundError(f"Kein clip.json in {self.directory}")
        clip = json.loads(manifest.read_text())
        if clip.get("schema_version") != CLIP_SCHEMA_VERSION:
            raise ValueError(
                f"Clipschema {clip.get('schema_version')!r} unbekannt, erwartet {CLIP_SCHEMA_VERSION}"
            )
        self.clip = clip

    def close(self) -> None:
        self.clip = {}

    @property
    def source_id(self) -> str:
        return f"replay:{self.directory.name}"

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.SEEK})

    def describe(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "clip_id": self.clip.get("clip_id"),
            "device_id": self.clip.get("device_id"),
            "ground_truth_text": self.clip.get("ground_truth_text"),
            "frame_count": len(self.clip.get("frames", ())),
            "dropped_frames": self.clip.get("dropped_frames", 0),
            "profile_name": self.clip.get("profile_name"),
            "calibrated_on_frame_sequence": self.clip.get("calibrated_on_frame_sequence"),
        }

    def frames(self) -> Iterator[Frame]:
        if not self.clip:
            raise RuntimeError("ReplaySource.open() fehlt")
        ground_truth = {"text": self.clip.get("ground_truth_text")}
        for entry in self.clip["frames"]:
            path = self.directory / entry["file"]
            image = cv2.imread(str(path))
            if image is None:
                raise FileNotFoundError(f"Clipbild nicht lesbar: {path}")
            yield Frame(
                frame_sequence=int(entry["frame_sequence"]),
                image=image,
                capture_timestamp=_replayed(entry["capture_timestamp"]),
                source_id=self.source_id,
                raw_metadata={
                    **entry.get("metadata", {}),
                    "ground_truth": ground_truth,
                    "device_id": self.clip.get("device_id"),
                    "clip_id": self.clip.get("clip_id"),
                },
            )


def _replayed(raw: dict[str, Any]) -> Timestamp:
    """Aufgezeichneten Zeitstempel ehrlich zurueckgeben.

    Trug er eine Zeitaussage, wird er REPLAY_RECORDED - der Enum-Wert existiert
    genau dafuer. Trug er keine (SYNTHETIC, FILE_MTIME), bleibt er, was er war:
    ein Replay darf aus einer synthetischen Aufnahme keine Zeitaussage machen.
    """
    base = TimeBaseKind(raw["base"])
    if base.carries_time_information:
        base = TimeBaseKind.REPLAY_RECORDED
    return Timestamp(
        value_ns=int(raw["value_ns"]),
        base=base,
        semantics=TimestampSemantics(raw.get("semantics", "unknown")),
        uncertainty_ns=raw.get("uncertainty_ns"),
    )
