"""Lokale Aufnahmen pro Test aufloesen, ohne beim Import Module zu skippen."""

import sys
from pathlib import Path

import pytest

# Wie bei direkt gestarteten Skripten auch fuer importlib-Aufrufe auffindbar.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from _devdata import input_path, recording_glob  # noqa: E402, F401


def local_recording(relative: str | Path, *, required: bool = True) -> Path:
    """Altes var/-Schema; required=False nur fuer Collection/skipif."""
    path = input_path(relative)
    if required and not path.exists():
        pytest.skip(f"lokale Aufnahme fehlt: {relative} (DISPREAD_DEV_DATA setzen)")
    return path
