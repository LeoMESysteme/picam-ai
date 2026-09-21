"""Dataset-Benchmark, Task 1: Laden, Geometrie, die Pflichtpruefung.

Pflichtpruefung (Konzept/Plan): derselbe Lauf gegen eine `render_display`-Probe
muss "correct" liefern - schlaegt sie fehl, liegt der Fehler im Skript, nicht
in den Realbildern. Fuer Task 1 heisst das konkret: eine `render_display`-Probe,
durch `sample_quad` exakt so geschnitten wie eine echte Probe-`bbox` es waere,
muss durch das bestehende `read_frame`/`classify`/`normalise` als "correct"
durchgehen - das beweist, dass die neue Geometrie genau das erzeugt, was
`read_frame` erwartet.
"""

from __future__ import annotations

import json

import cv2
import pytest

from dispread.benchmark import (
    DatasetSample,
    assert_disjoint_groups,
    classify,
    load_dataset_samples,
    normalise,
    sample_quad,
)
from dispread.frames.synthetic_source import render_display
from dispread.layout import DisplayLayout
from dispread.ocr.sevenseg import SevenSegmentReader


def _layout():
    return DisplayLayout(digits=4, decimals=2, has_sign=False, unit=None)


# --- Die Pflichtpruefung: render_display -> sample_quad -> read_frame ------


def test_synthetische_probe_deskew_false_liest_korrekt():
    from dispread.benchmark import read_frame

    layout = _layout()
    image, shown, bbox = render_display(12.34, layout, size=(480, 200))

    quad = sample_quad(image, bbox, deskew=False)
    assert quad is not None
    profile = {
        "layout": layout.to_dict(),
        "roi_quad": quad,
        "ocr_box": [0.0, 0.0, 1.0, 1.0],
    }
    read = read_frame(image, profile, SevenSegmentReader())
    assert read.value is not None
    assert classify(normalise(shown), normalise(read.raw_text)) == "correct"


def test_synthetische_probe_deskew_true_liest_korrekt():
    """Arm 2 (`fit_quad_in_region`) muss auf einem sauberen synthetischen Bild
    ebenfalls sauber runden - das ist der Vergleichsarm, den der Plan gegen
    Arm 1 stellt.

    `render_display` selbst zeichnet keinen Gehaeuserand - das Panel fuellt
    das ganze Bild in einer Farbe, ohne Kontur (anders als eine echte
    Aufnahme mit sichtbarem Displaygehaeuse). `fit_quad_in_region` braucht
    aber eine Kontur, um ueberhaupt etwas vorzuschlagen (siehe
    `tests/test_workbench.py::test_fit_quad_in_region_finds_a_panel_within_the_hint`
    fuer dasselbe Muster: gezeichnetes Panel gegen einen kontrastierenden
    Hintergrund). Deshalb wird das gerenderte Panel hier auf einen groesseren,
    andersfarbigen Bedienoberflaechenhintergrund montiert - der Bedienerhinweis
    (`bbox`) ist dann das ganze Panel, nicht nur die Ziffernregion, und
    `ocr_box` zeigt als Bruchteil des Panels auf die Ziffernregion, die
    `render_display` zurueckgegeben hat.
    """
    from dispread.benchmark import read_frame

    layout = _layout()
    panel_w, panel_h = 480, 200
    panel, shown, (bx, by, bw, bh) = render_display(56.78, layout, size=(panel_w, panel_h))

    import numpy as np

    margin = 60
    canvas = np.full((panel_h + 2 * margin, panel_w + 2 * margin, 3), 150, np.uint8)
    canvas[margin : margin + panel_h, margin : margin + panel_w] = panel
    bbox = (margin, margin, panel_w, panel_h)

    quad = sample_quad(canvas, bbox, deskew=True)
    assert quad is not None
    ocr_box = (bx / panel_w, by / panel_h, bw / panel_w, bh / panel_h)
    profile = {
        "layout": layout.to_dict(),
        "roi_quad": quad,
        "ocr_box": ocr_box,
    }
    read = read_frame(canvas, profile, SevenSegmentReader())
    assert read.value is not None
    assert classify(normalise(shown), normalise(read.raw_text)) == "correct"


# --- sample_quad: kein stiller Ruecfall bei deskew=True -------------------


def test_sample_quad_deskew_true_liefert_none_statt_fallback():
    """Ein degenerierter Hinweisbereich (nahe Null Breite) besteht keinen
    Filter in `fit_quad_in_region` (Mindestflaeche `min_area`) - `sample_quad`
    muss dann `None` zurueckgeben, nicht leise auf Arm 1 zurueckfallen."""
    layout = _layout()
    image, _shown, _bbox = render_display(12.34, layout, size=(480, 200))

    degenerate_bbox = (10.0, 10.0, 0.5, 0.5)  # 0.5x0.5 Pixel: weit unter min_area
    quad = sample_quad(image, degenerate_bbox, deskew=True)
    assert quad is None


def test_sample_quad_deskew_false_gibt_vier_normierte_eckpunkte():
    height, width = 200, 480
    image, _shown, bbox = render_display(1.23, _layout(), size=(width, height))
    quad = sample_quad(image, bbox, deskew=False)
    assert quad is not None
    assert len(quad) == 4
    x, y, w, h = bbox
    expected = {
        (x / width, y / height),
        ((x + w) / width, y / height),
        ((x + w) / width, (y + h) / height),
        (x / width, (y + h) / height),
    }
    got_flat = [coord for point in sorted(quad) for coord in point]
    expected_flat = [coord for point in sorted(expected) for coord in point]
    assert got_flat == pytest.approx(expected_flat)
    for px, py in quad:
        assert 0.0 <= px <= 1.0
        assert 0.0 <= py <= 1.0


# --- load_dataset_samples ---------------------------------------------------


def _write_sample(root, sample_id, *, overrides=None):
    sample_dir = root / "samples" / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": sample_id,
        "device_id": "geraet-1",
        "independence_group": "gruppe-1",
        "split": "development",
        "label_state": "readable",
        "expected_text": "12.34",
        "bbox": [10.0, 20.0, 100.0, 50.0],
        "width": 480,
        "height": 200,
        "synthetic": False,
    }
    if overrides:
        data.update(overrides)
    (sample_dir / "sample.json").write_text(json.dumps(data))
    return sample_dir


def _write_valid_image(sample_dir):
    import numpy as np

    image = np.zeros((200, 480, 3), dtype=np.uint8)
    cv2.imwrite(str(sample_dir / "image.png"), image)


def test_load_dataset_samples_ueberspringt_synthetisch_und_defekt_und_laedt_rest(tmp_path):
    root = tmp_path / "datasets"

    ok = _write_sample(root, "ok-1")
    _write_valid_image(ok)

    synthetic_dir = _write_sample(root, "synth-1", overrides={"synthetic": True})
    _write_valid_image(synthetic_dir)

    broken_dir = root / "samples" / "broken-1"
    broken_dir.mkdir(parents=True)
    (broken_dir / "sample.json").write_text("{not valid json")

    missing_field_dir = root / "samples" / "missing-1"
    missing_field_dir.mkdir(parents=True)
    (missing_field_dir / "sample.json").write_text(json.dumps({"id": "missing-1"}))

    samples, skipped = load_dataset_samples(root)

    assert [s.id for s in samples] == ["ok-1"]
    assert isinstance(samples[0], DatasetSample)
    assert samples[0].expected_text == "12.34"
    assert samples[0].bbox == (10.0, 20.0, 100.0, 50.0)
    assert samples[0].independence_group == "gruppe-1"

    assert len(skipped) == 3
    assert any("synth-1" in entry for entry in skipped)
    assert any("broken-1" in entry for entry in skipped)
    assert any("missing-1" in entry for entry in skipped)


def test_load_dataset_samples_unreadable_wird_geladen_nicht_uebersprungen(tmp_path):
    """Die eine `unreadable`-Probe soll NICHT in die Zaehlung fallen, aber auch
    nicht stillschweigend fehlen - sie wird geladen, mit `expected_text=None`,
    damit ein Aufrufer sie als benannte Einzelfalldiagnose ausgeben kann."""
    root = tmp_path / "datasets"
    sample_dir = _write_sample(
        root,
        "unreadable-1",
        overrides={"label_state": "unreadable", "expected_text": None},
    )
    _write_valid_image(sample_dir)

    samples, skipped = load_dataset_samples(root)

    assert skipped == []
    assert len(samples) == 1
    assert samples[0].label_state == "unreadable"
    assert samples[0].expected_text is None


def test_load_dataset_samples_uncertain_wird_uebersprungen(tmp_path):
    root = tmp_path / "datasets"
    sample_dir = _write_sample(root, "uncertain-1", overrides={"label_state": "uncertain"})
    _write_valid_image(sample_dir)

    samples, skipped = load_dataset_samples(root)

    assert samples == []
    assert len(skipped) == 1
    assert "uncertain-1" in skipped[0]


def test_load_dataset_samples_leerer_root_liefert_leere_listen(tmp_path):
    samples, skipped = load_dataset_samples(tmp_path / "nichts")
    assert samples == []
    assert skipped == []


# --- assert_disjoint_groups --------------------------------------------------


def _sample(id_, group, expected="1.00"):
    return DatasetSample(
        id=id_,
        device_id="geraet-1",
        independence_group=group,
        split="development",
        label_state="readable",
        expected_text=expected,
        bbox=(0.0, 0.0, 10.0, 10.0),
        image_path=None,  # type: ignore[arg-type]
        width=100,
        height=100,
    )


def test_assert_disjoint_groups_wirft_bei_geteilter_gruppe():
    fitting = [_sample("a", "gruppe-1")]
    evaluation = [_sample("b", "gruppe-1")]
    with pytest.raises(ValueError, match="gruppe-1"):
        assert_disjoint_groups(fitting, evaluation)


def test_assert_disjoint_groups_wirft_nicht_bei_disjunkten_gruppen():
    fitting = [_sample("a", "gruppe-1")]
    evaluation = [_sample("b", "gruppe-2")]
    assert_disjoint_groups(fitting, evaluation)  # wirft nicht
