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


def _synthetic_annotation(
    directory,
    *,
    value,
    profile_name="synthetic",
    with_layout=True,
    with_ground_truth=True,
):
    """Workbench-Annotation (Schema 2) mit echtem Bild erzeugen, deterministisch.

    Spiegelbild zu `_synthetic_clip`, aber im Annotationsschema: `roi_quad`
    und `ocr_box` liegen auf der obersten Ebene (nicht unter `profile`), so
    wie `evaluate_annotation` es liest. `with_layout=False`/
    `with_ground_truth=False` bauen absichtlich eine nicht auswertbare
    Annotation - `with_layout=False` mit `ground_truth_text` trotzdem gesetzt
    spiegelt exakt die Form der realen Altannotation
    `0dd690423ad04ee28aa517f179e154c2` (Schema 1: `profile.layout` fehlt).
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

    directory.mkdir(parents=True, exist_ok=True)
    image_name = "image.png"
    assert cv2.imwrite(str(directory / image_name), image)

    # `profile` bleibt bei `with_layout=False` bewusst nicht leer - die reale
    # Schema-1-Altannotation `0dd690423ad04ee28...` hat ein voll besetztes
    # `profile` (Kamera-Settings, roi, ...), nur eben ohne `layout`-Schluessel.
    # Ein leeres `{}` wuerde den Guard `(profile or {}).get("layout")` nicht
    # trennscharf pruefen.
    profile = {"schema_version": 1, "version": 0, "role": "main"}
    if with_layout:
        profile["layout"] = layout.to_dict()

    annotation = {
        "schema_version": 2,
        "image": image_name,
        "roi_quad": roi_quad,
        "ocr_box": [0.0, 0.0, 1.0, 1.0],
        "profile": profile,
        "profile_name": profile_name,
    }
    if with_ground_truth:
        annotation["ground_truth_text"] = shown
    (directory / "annotation.json").write_text(json.dumps(annotation))
    return directory


def test_annotation_ohne_layout_wird_uebersprungen(tmp_path):
    """Altannotation nach Schema 1 (kein `profile.layout`) ist nicht auswertbar.

    Spiegelt die reale `var/workbench/annotations/0dd690423ad04ee28...`:
    `ground_truth_text` ist vorhanden, `profile.layout` fehlt. `None` ist das
    dokumentierte Signal dafuer, nicht ein Crash und nicht ein falsches
    Ergebnis (siehe Docstring von `evaluate_annotation`).
    """
    from dispread.benchmark import evaluate_annotation
    from dispread.ocr.sevenseg import SevenSegmentReader

    directory = _synthetic_annotation(
        tmp_path / "alt", value=12.34, with_layout=False, with_ground_truth=True
    )
    assert evaluate_annotation(directory, SevenSegmentReader()) is None


def test_annotation_ohne_sollwert_wird_uebersprungen(tmp_path):
    """Fehlender `ground_truth_text` ist ebenso nicht auswertbar wie fehlendes Layout."""
    from dispread.benchmark import evaluate_annotation
    from dispread.ocr.sevenseg import SevenSegmentReader

    directory = _synthetic_annotation(
        tmp_path / "kein_soll", value=12.34, with_layout=True, with_ground_truth=False
    )
    assert evaluate_annotation(directory, SevenSegmentReader()) is None


def test_annotation_vollstaendig_wird_korrekt_gelesen(tmp_path):
    """Eine vollstaendige Annotation (Layout, roi_quad, ocr_box, Sollwert) liest korrekt."""
    from dispread.benchmark import evaluate_annotation
    from dispread.ocr.sevenseg import SevenSegmentReader

    directory = _synthetic_annotation(
        tmp_path / "annotation", value=12.34, profile_name="geraet-x"
    )
    outcome = evaluate_annotation(directory, SevenSegmentReader())
    assert outcome is not None
    assert (outcome.correct, outcome.wrong, outcome.rejected) == (1, 0, 0)
    assert outcome.device_id == "geraet-x"
    assert outcome.source_id == f"annotation:{directory.name}"


def test_evaluate_set_ueberspringt_und_aggregiert(tmp_path):
    """`evaluate_set` dispatcht Clip/Annotation, summiert ueber beide und fuehrt die

    nicht auswertbare Altannotation unter `skipped`.

    Deckt genau die beiden Luecken ab, die der Reviewer benannt hat:
    Verzeichnis-Dispatch (`clip.json` -> `evaluate_clip`, `annotation.json`
    -> `evaluate_annotation`, sonst uebersprungen) *und* Aggregation ueber
    mehr als ein auswertbares Verzeichnis - eine Summe aus einem Term prueft
    keine Summe. Die dreigeteilte Metrik darf zudem nicht durch
    stillschweigend weggelassene Verzeichnisse verzerrt werden (AGENTS.md) -
    `skipped` muss die nicht auswertbare Altannotation namentlich auffuehren.
    """
    from dispread.benchmark import evaluate_set
    from dispread.ocr.sevenseg import SevenSegmentReader

    annotation = _synthetic_annotation(tmp_path / "ok", value=12.34)
    clip = _synthetic_clip(tmp_path / "clip", value=56.78, frames=5)
    not_evaluable = _synthetic_annotation(
        tmp_path / "alt", value=90.12, with_layout=False, with_ground_truth=True
    )

    report = evaluate_set([annotation, clip, not_evaluable], SevenSegmentReader())

    assert report["evaluated"] == 2
    assert report["skipped"] == [str(not_evaluable)]
    # 1 Frame aus der Annotation + 5 Frames aus dem Clip, alle korrekt -
    # nur ueber echte Addition zweier Outcomes erreichbar, nicht ueber ein
    # einzelnes durchgereichtes Ergebnis.
    assert (report["correct"], report["wrong"], report["rejected"]) == (6, 0, 0)
    assert len(report["outcomes"]) == 2
    source_ids = {outcome.source_id for outcome in report["outcomes"]}
    assert source_ids == {f"annotation:{annotation.name}", f"replay:{clip.name}"}
