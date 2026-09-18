"""Benchmark: die gefaehrliche Zahl ist die falsche Annahme, nicht die Ablehnung."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import pytest
from conftest import _write_clip

from dispread.benchmark import assert_disjoint_devices, classify, normalise


def _clip(path, *, device="geraet-1"):
    return _write_clip(path, device_id=device)


def _synthetic_clip(directory, *, value, frames=5, ground_truth_override=None, device_id="synthetic-1"):
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
                "device_id": device_id,
                "ground_truth_text": ground_truth_override or shown,
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


def test_normalise_akzeptiert_komma_und_punkt_behaelt_aber_die_stelle():
    """Bediener tippen '28,80'; der Leser liefert '28.80' - derselbe Wert.

    Die *Position* des Trenners ist dagegen Messinhalt und darf nicht
    wegnormiert werden: frueher wurden '28.80' und '288.0' beide zu '2880'
    und ein Zehnerfehler galt als korrekt (Review-Fund).
    """
    assert normalise("28,80") == normalise("28.80") == "28.80"
    assert normalise("-000.13") == "-000.13"
    assert normalise("28.80") != normalise("288.0")
    # Schreibweisen, die denselben Wert meinen, werden weiter vereinheitlicht:
    # das Ganzzahlformat des Lesers ("1234." bei decimals=0) und die fehlende
    # fuehrende Null (".1234" bei digits==decimals).
    assert normalise("1234.") == normalise("1234") == "1234"
    assert normalise(".1234") == normalise("0,1234") == "0.1234"
    assert normalise("+28,80") == "28.80"


@pytest.mark.parametrize(
    ("expected", "got", "klasse"),
    [
        ("-1234", "1234", "sign"),
        ("1234", "-1234", "sign"),
        ("1234", "1235", "digit"),
        ("1234", "123", "count"),
        ("1234", "1234", "correct"),
        ("28,80", "28.80", "correct"),
        # Stellenfehler: dieselben Ziffern, andere Dezimalstelle - Faktor zehn.
        ("28.80", "288.0", "decimal"),
        ("28.80", "2.880", "decimal"),
        ("-28.80", "-2.880", "decimal"),
    ],
)
def test_fehlerklassen_werden_getrennt_gefuehrt(expected, got, klasse):
    """Konzept.md §7 nennt fehlendes Minuszeichen und uebersehenen Dezimalpunkt
    als eigenstaendige kritische Fehler - beide brauchen eine eigene Klasse."""
    assert classify(normalise(expected), normalise(got)) == klasse


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
    ground_truth_override=None,
    device_id=None,
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
        annotation["ground_truth_text"] = ground_truth_override or shown
    if device_id is not None:
        annotation["device_id"] = device_id
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
        tmp_path / "annotation", value=12.34, profile_name="profil-x", device_id="geraet-x"
    )
    outcome = evaluate_annotation(directory, SevenSegmentReader())
    assert outcome is not None
    assert (outcome.correct, outcome.wrong, outcome.rejected) == (1, 0, 0)
    # Geraetekennung, nicht Profilname - der ist nur ein Etikett.
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


# --- Stellenfehler im echten Auswertepfad ----------------------------------


def test_komma_und_punkt_bleiben_derselbe_wert(tmp_path):
    """Tippkonvention (Komma) gegen Leserausgabe (Punkt) - kein Fehler."""
    from dispread.benchmark import evaluate_annotation
    from dispread.ocr.sevenseg import SevenSegmentReader

    directory = _synthetic_annotation(
        tmp_path / "komma", value=28.80, ground_truth_override="28,80"
    )
    outcome = evaluate_annotation(directory, SevenSegmentReader())
    assert outcome is not None
    assert (outcome.correct, outcome.wrong, outcome.rejected) == (1, 0, 0)
    assert outcome.wrong_classes == {}


@pytest.mark.parametrize("typed", ["288,0", "2,880"])
def test_verschobene_dezimalstelle_gilt_als_falsch_angenommen(tmp_path, typed):
    """Ein Zehnerfehler ist ein Messfehler, kein Treffer.

    Die Anzeige zeigt 28,80; der Sollwert nennt dieselbe Ziffernfolge an
    anderer Dezimalstelle. Vor dem Fix entfernte `normalise` den Trenner ganz
    ('2880' == '2880') und `classify` meldete "correct" - der Benchmark war
    fuer genau den Fehler blind, den Konzept.md §7 als kritisch fuehrt.
    """
    from dispread.benchmark import evaluate_annotation
    from dispread.ocr.sevenseg import SevenSegmentReader

    directory = _synthetic_annotation(
        tmp_path / typed.replace(",", "_"), value=28.80, ground_truth_override=typed
    )
    outcome = evaluate_annotation(directory, SevenSegmentReader())
    assert outcome is not None
    assert (outcome.correct, outcome.wrong, outcome.rejected) == (0, 1, 0)
    assert outcome.wrong_classes == {"decimal": 1}


def test_clip_mit_verschobener_dezimalstelle_wird_als_falsch_gezaehlt(tmp_path):
    """Derselbe Fall ueber den Clippfad - inklusive Summierung in evaluate_set."""
    from dispread.benchmark import evaluate_clip, evaluate_set
    from dispread.ocr.sevenseg import SevenSegmentReader

    clip = _synthetic_clip(tmp_path / "shift", value=12.34, frames=3, ground_truth_override="123,4")
    outcome = evaluate_clip(clip, SevenSegmentReader())
    assert (outcome.correct, outcome.wrong, outcome.rejected) == (0, 3, 0)
    assert outcome.wrong_classes == {"decimal": 3}

    report = evaluate_set([clip], SevenSegmentReader())
    assert report["wrong"] == 3
    assert report["wrong_classes"] == {"decimal": 3}


# --- Relative und kodierte Clippfade ---------------------------------------


def test_relativer_clippfad_wird_ausgewertet(tmp_path, monkeypatch):
    """`replay://var/...` verlor frueher sein erstes Pfadsegment an die
    URL-Autoritaet (netloc) - der dokumentierte CLI-Aufruf mit relativem
    Glob las damit ein anderes, nicht existierendes Verzeichnis."""
    from dispread.benchmark import directories_from_glob, evaluate_clip, evaluate_set
    from dispread.ocr.sevenseg import SevenSegmentReader

    _synthetic_clip(tmp_path / "var" / "clips" / "abc", value=12.34, frames=2)
    monkeypatch.chdir(tmp_path)

    relative = Path("var/clips/abc")
    outcome = evaluate_clip(relative, SevenSegmentReader())
    assert (outcome.correct, outcome.wrong, outcome.rejected) == (2, 0, 0)

    # Derselbe Weg wie scripts/ocr-benchmark.py: Glob -> evaluate_set.
    directories = directories_from_glob("var/clips/*")
    assert directories == [relative]
    assert evaluate_set(directories, SevenSegmentReader())["correct"] == 2


def test_absoluter_clippfad_und_pfad_mit_leerzeichen(tmp_path):
    """Der absolute Pfad muss weiter funktionieren, ein Leerzeichen ebenfalls."""
    from dispread.benchmark import evaluate_clip
    from dispread.ocr.sevenseg import SevenSegmentReader

    absolute = _synthetic_clip(tmp_path / "clip abs", value=12.34, frames=2)
    outcome = evaluate_clip(absolute, SevenSegmentReader())
    assert (outcome.correct, outcome.wrong, outcome.rejected) == (2, 0, 0)


def test_path_uri_baut_absolute_kodierte_uri():
    """Die Bauvorschrift selbst - damit andere Aufrufer nicht wieder
    `f"replay://{pfad}"` schreiben."""
    from urllib.parse import urlparse

    from dispread.frames import path_uri

    uri = path_uri("replay", "var/clips/mit leerzeichen")
    assert "%20" in uri
    parsed = urlparse(uri)
    assert parsed.netloc == ""  # nichts landet in der Autoritaet
    assert parsed.path.endswith("/var/clips/mit%20leerzeichen")


# --- Geraeteidentitaet statt Profilname ------------------------------------


def _annotation_manifest(directory, *, profile_name="profil", device_id=None):
    """Nur das Manifest - `_device_of` liest nichts anderes."""
    directory.mkdir(parents=True, exist_ok=True)
    data = {"schema_version": 2, "profile_name": profile_name}
    if device_id is not None:
        data["device_id"] = device_id
    (directory / "annotation.json").write_text(json.dumps(data))
    return directory


def test_dasselbe_geraet_unter_zwei_profilnamen_faellt_durch(tmp_path):
    """Ein Profilname ist ein Etikett, keine Geraeteinstanz: dasselbe Geraet
    nach einer Neukalibrierung unter zweitem Namen galt frueher als zwei
    Geraete - der Split sah faelschlich disjunkt aus (Review-Fund)."""
    development = _annotation_manifest(
        tmp_path / "a", profile_name="gsv-2asd", device_id="geraet-1"
    )
    test = _annotation_manifest(
        tmp_path / "b", profile_name="gsv-2asd-neu", device_id="geraet-1"
    )
    with pytest.raises(ValueError, match="geraet-1"):
        assert_disjoint_devices([development], [test])


def test_unbekannte_geraeteidentitaet_wird_nicht_bescheinigt(tmp_path):
    """Eine Annotation ohne `device_id` und ein Clip desselben Geraets: die
    Identitaeten sind nicht vergleichbar. Dann wird abgelehnt statt geraten -
    ein stiller Rueckfall auf `profile_name` haette hier "disjunkt" gemeldet."""
    annotation = _annotation_manifest(tmp_path / "a", profile_name="geraet-1")
    clip = _clip(tmp_path / "b", device="geraet-1")
    with pytest.raises(ValueError, match="device_id"):
        assert_disjoint_devices([annotation], [clip])


def test_zwei_verschiedene_geraete_bleiben_zulaessig(tmp_path):
    """Die Verschaerfung darf den gueltigen Fall nicht treffen."""
    development = _annotation_manifest(tmp_path / "a", device_id="geraet-1")
    test = _clip(tmp_path / "b", device="geraet-2")
    assert_disjoint_devices([development], [test])  # wirft nicht


def test_annotation_ohne_device_id_meldet_unbekannt(tmp_path):
    """Im Bericht steht `unbekannt` - ein Etikett fuer die Ausgabe, keine
    Bescheinigung (die verweigert `assert_disjoint_devices`)."""
    from dispread.benchmark import evaluate_annotation
    from dispread.ocr.sevenseg import SevenSegmentReader

    directory = _synthetic_annotation(tmp_path / "ohne", value=12.34, profile_name="geraet-x")
    outcome = evaluate_annotation(directory, SevenSegmentReader())
    assert outcome is not None
    assert outcome.device_id == "unbekannt"
