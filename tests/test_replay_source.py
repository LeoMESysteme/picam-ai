"""replay:// — aufgezeichnete Clips zuruecklesen, ohne Zeitaussagen zu erfinden."""

from __future__ import annotations

import pytest
from conftest import _write_clip

from dispread.frames import open_source
from dispread.records import TimeBaseKind  # noqa: F401


def test_clip_wird_mit_label_und_sequenz_zurueckgelesen(tmp_path):
    clip = _write_clip(tmp_path / "clip-a")
    source = open_source(f"replay://{clip}")
    source.open()
    try:
        frames = list(source.frames())
    finally:
        source.close()
    assert [f.frame_sequence for f in frames] == [100, 101]
    assert frames[0].raw_metadata["ground_truth"]["text"] == "28,80"
    assert frames[0].raw_metadata["device_id"] == "geraet-1"
    assert frames[0].image.shape == (8, 12, 3)


def test_aufgezeichneter_sensorzeitstempel_wird_als_replay_gefuehrt(tmp_path):
    """REPLAY_RECORDED traegt die Zeitaussage der Aufnahme, nicht die des Abspielens."""
    clip = _write_clip(tmp_path / "clip-b", base="sensor_boottime")
    source = open_source(f"replay://{clip}")
    source.open()
    frame = next(iter(source.frames()))
    source.close()
    assert frame.timebase is TimeBaseKind.REPLAY_RECORDED
    assert frame.is_time_bearing
    assert frame.capture_timestamp.value_ns == 1_000


def test_synthetische_aufnahme_wird_durch_replay_nicht_zeittragend(tmp_path):
    """Ein Replay darf aus SYNTHETIC keine Zeitaussage machen (AGENTS.md)."""
    clip = _write_clip(tmp_path / "clip-c", base="synthetic")
    source = open_source(f"replay://{clip}")
    source.open()
    frame = next(iter(source.frames()))
    source.close()
    assert frame.timebase is TimeBaseKind.SYNTHETIC
    assert not frame.is_time_bearing


def test_fehlende_clipdatei_wird_klar_gemeldet(tmp_path):
    (tmp_path / "leer").mkdir()
    source = open_source(f"replay://{tmp_path / 'leer'}")
    with pytest.raises(FileNotFoundError, match="clip.json"):
        source.open()


def test_unbekannte_schemaversion_wird_abgelehnt(tmp_path):
    import json

    clip = _write_clip(tmp_path / "clip-d")
    data = json.loads((clip / "clip.json").read_text())
    data["schema_version"] = 99
    (clip / "clip.json").write_text(json.dumps(data))
    source = open_source(f"replay://{clip}")
    with pytest.raises(ValueError, match="Clipschema"):
        source.open()
