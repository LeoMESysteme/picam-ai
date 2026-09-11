"""Pytest-Konfiguration.

`--mode` uebernommen von /opt/mehub/current/tests/conftest.py: mock laeuft
ohne Hardware, real zusaetzlich die als @hardware/@serial markierten Tests.
"""

from __future__ import annotations

import json

import cv2
import numpy as np
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--mode",
        action="store",
        default="mock",
        choices=("mock", "real"),
        help="mock = ohne Hardware (Default), real = mit Kamera und UART",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--mode") == "real":
        return
    skip = pytest.mark.skip(reason="braucht --mode=real (Hardware)")
    for item in items:
        if "hardware" in item.keywords or "serial" in item.keywords:
            item.add_marker(skip)


def _write_clip(directory, *, base="sensor_boottime", frames=2, label="28,80"):
    directory.mkdir(parents=True, exist_ok=True)
    entries = []
    for index in range(frames):
        name = f"frame_{index + 1:06d}.png"
        image = np.full((8, 12, 3), index * 10, np.uint8)
        assert cv2.imwrite(str(directory / name), image)
        entries.append(
            {
                "file": name,
                "frame_sequence": 100 + index,
                "capture_timestamp": {
                    "value_ns": 1_000 + index,
                    "base": base,
                    "semantics": "unknown",
                    "uncertainty_ns": None,
                },
                "metadata": {"ExposureTime": 5000},
            }
        )
    (directory / "clip.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "clip_id": directory.name,
                "device_id": "geraet-1",
                "ground_truth_text": label,
                "profile": {},
                "profile_name": "test",
                "calibrated_on_frame_sequence": None,
                "dropped_frames": 0,
                "created_at": "2026-09-11T00:00:00+00:00",
                "created_timebase": "UTC",
                "frames": entries,
            }
        )
    )
    return directory
