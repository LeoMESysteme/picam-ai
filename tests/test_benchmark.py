"""Benchmark: die gefaehrliche Zahl ist die falsche Annahme, nicht die Ablehnung."""

from __future__ import annotations

import json

import cv2
import pytest
from conftest import _write_clip

from dispread.benchmark import assert_disjoint_devices, classify, normalise


def _clip(path, *, device="geraet-1"):
    return _write_clip(path, device_id=device)


def _synthetic_clip(directory, *, value, frames=5):
    """Realen Clip mit vollstaendigem Profil erzeugen, deterministisch.

    `render_display` liefert den Ziffernbereich als Pixel-Box innerhalb des
    gerenderten Bilds - genau das, was ein Bediener nach Konzept.md §4 als
    ROI bestaetigen wuerde. `roi_quad` wird daraus als normiertes Viereck
    abgeleitet (Reihenfolge egal, `rectify._order_quad` sortiert selbst).
    Der `ocr_box` ist der volle rektifizierte Ausschnitt, weil der
    Ziffernbereich hier bereits der komplette Leserinput ist.
    """
    from dispread.frames.synthetic_source import render_display
    from dispread.layout import DisplayLayout

    layout = DisplayLayout(digits=4, decimals=2, has_sign=False, unit=None)
    size = (480, 200)
    image, shown, (x, y, w, h) = render_display(value, layout, size=size)
    width, height = size
    roi_quad = [
        [x / width, y / height],
        [(x + w) / width, y / height],
        [(x + w) / width, (y + h) / height],
        [x / width, (y + h) / height],
    ]
    profile = {
        "layout": layout.to_dict(),
        "roi_quad": roi_quad,
        "ocr_box": [0.0, 0.0, 1.0, 1.0],
    }

    directory.mkdir(parents=True, exist_ok=True)
    entries = []
    for index in range(frames):
        name = f"frame_{index + 1:06d}.png"
        assert cv2.imwrite(str(directory / name), image)
        entries.append(
            {
                "file": name,
                "frame_sequence": 100 + index,
                "capture_timestamp": {
                    "value_ns": 1_000 + index,
                    "base": "synthetic",
                    "semantics": "unknown",
                    "uncertainty_ns": None,
                },
                "metadata": {},
            }
        )
    (directory / "clip.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "clip_id": directory.name,
                "device_id": "synthetic-1",
                "ground_truth_text": shown,
                "profile": profile,
                "profile_name": "synthetic",
                "calibrated_on_frame_sequence": None,
                "dropped_frames": 0,
                "created_at": "2026-09-11T00:00:00+00:00",
                "created_timebase": "SYNTHETIC",
                "frames": entries,
            }
        )
    )
    return directory


def test_normalise_akzeptiert_komma_und_punkt():
    """Bediener tippen '28,80'; der Leser liefert '28.80'."""
    assert normalise("28,80") == normalise("28.80") == "2880"
    assert normalise("-000.13") == "-00013"


@pytest.mark.parametrize(
    ("expected", "got", "klasse"),
    [
        ("-1234", "1234", "sign"),
        ("1234", "-1234", "sign"),
        ("1234", "1235", "digit"),
        ("1234", "123", "count"),
        ("1234", "1234", "correct"),
    ],
)
def test_fehlerklassen_werden_getrennt_gefuehrt(expected, got, klasse):
    """Konzept.md §7 nennt fehlendes Minuszeichen als eigenstaendigen Fehler."""
    assert classify(expected, got) == klasse


def test_gruppensplit_wird_erzwungen(tmp_path):
    """Splitgrenze ist die Geraeteinstanz, nie der Frame (ROADMAP)."""
    development = _clip(tmp_path / "a", device="geraet-1")
    test = _clip(tmp_path / "b", device="geraet-1")
    with pytest.raises(ValueError, match="geraet-1"):
        assert_disjoint_devices([development], [test])

    other = _clip(tmp_path / "c", device="geraet-2")
    assert_disjoint_devices([development], [other])  # wirft nicht


def test_synthetischer_clip_wird_vollstaendig_korrekt_gelesen(tmp_path):
    from dispread.benchmark import evaluate_clip
    from dispread.ocr.sevenseg import SevenSegmentReader

    clip = _synthetic_clip(tmp_path / "syn", value=12.34, frames=5)
    outcome = evaluate_clip(clip, SevenSegmentReader())
    assert (outcome.correct, outcome.wrong, outcome.rejected) == (5, 0, 0)
