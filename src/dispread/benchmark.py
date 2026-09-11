"""Erkennungsqualitaet messen: korrekt / falsch / abgelehnt getrennt fuehren.

Eine einzelne Trefferquote verdeckt genau die Unterscheidung, auf die es
ankommt: eine Ablehnung kostet einen Messwert, eine falsche *Annahme*
verfaelscht eine Kalibrierung (AGENTS.md, Konzept.md §7). Dieser Benchmark
zaehlt deshalb dreigeteilt und schluesselt Fehler nach Klasse auf
(Vorzeichen, Stellenzahl, Ziffer).

Wichtig zur Deutung: die Metrik wird auf **Leserebene** gemessen, nicht auf
Gate-Ebene (`validate.py`). Die Freigabe kann gegenueber dem Leser nur
*zusaetzlich ablehnen*, nie *zusaetzlich annehmen* - sie verschaerft nur.
Die hier gemessene Rate falscher Annahmen ist damit die konservative
Obergrenze dessen, was am Ende beim Bediener ankommen koennte; die reale Rate
nach Gate ist hoechstens so hoch, in der Praxis niedriger.

Splitgrenze fuer Entwicklungs- und Testsatz ist immer die Geraeteinstanz, nie
der Frame und nicht der Clip - benachbarte Aufnahmen desselben Geraets sind
korreliert und wuerden ein Ergebnis zu optimistisch aussehen lassen
(ROADMAP, Konzept.md §9). `assert_disjoint_devices` erzwingt das als Test,
nicht nur als Doku-Regel.
"""

from __future__ import annotations

import glob
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from dispread.frames import open_source
from dispread.layout import DisplayLayout
from dispread.ocr import ReadResult, ValueReader
from dispread.rectify import rectify
from dispread.workbench.controller import CROP_SIZE, crop_box

__all__ = [
    "Outcome",
    "normalise",
    "classify",
    "read_frame",
    "evaluate_clip",
    "evaluate_annotation",
    "evaluate_set",
    "assert_disjoint_devices",
    "directories_from_glob",
]


@dataclass(frozen=True, slots=True)
class Outcome:
    """Ergebnis einer einzelnen Aufnahme (Clip oder Annotation), dreigeteilt."""

    source_id: str
    device_id: str
    expected: str
    correct: int
    wrong: int
    rejected: int
    #: Fehlerklasse -> Anzahl. Schluessel: sign, decimal, digit, count
    wrong_classes: dict[str, int]
    #: Ablehnungsgrund -> Anzahl, aus den Reader-Diagnosen
    reject_classes: dict[str, int]
    #: Bis zu fuenf Beispiele "soll -> ist" fuer die Fehleranalyse
    examples: tuple[str, ...]


def normalise(text: str) -> str:
    """Getippten oder gelesenen Wert auf vergleichbare Ziffernfolge bringen.

    Bediener tippen mit Komma ("28,80"), der Leser liefert einen Punkt. Der
    Dezimaltrenner selbst wird entfernt - seine *Position* prueft die
    Layoutstufe, nicht der Zeichenvergleich.
    """
    text = text.strip().replace(",", "").replace(".", "").replace(" ", "")
    return text


def classify(expected: str, got: str) -> str:
    """Fehlerklasse einer Abweichung. Konzept.md §7 verlangt getrennte Klassen."""
    if expected == got:
        return "correct"
    if expected.lstrip("-") == got.lstrip("-"):
        return "sign"
    if len(expected.lstrip("-")) != len(got.lstrip("-")):
        return "count"
    return "digit"


def read_frame(image: Any, profile: dict[str, Any], reader: ValueReader) -> ReadResult:
    """Ein Bild genau so lesen wie Controller._read() es im Betrieb tut."""
    layout = DisplayLayout.from_dict(profile["layout"])
    height, width = image.shape[:2]
    quad = tuple((float(x * width), float(y * height)) for x, y in profile["roi_quad"])
    crop = rectify(image, quad, target_size=CROP_SIZE)
    return reader.read(crop_box(crop.image, profile["ocr_box"]), layout)


def _tally(
    expected: str,
    read: ReadResult,
    examples: list[str],
    wrong_classes: dict[str, int],
    reject_classes: dict[str, int],
) -> str:
    """Ein Leseergebnis einsortieren; liefert 'correct', 'wrong' oder 'rejected'.

    Die gefaehrliche Spalte ist 'wrong': eine Ablehnung kostet einen Messwert,
    eine falsche Annahme verfaelscht eine Kalibrierung.
    """
    if read.value is None:
        for reason in _reject_reasons(read):
            reject_classes[reason] = reject_classes.get(reason, 0) + 1
        return "rejected"
    got = normalise(read.raw_text)
    klasse = classify(expected, got)
    if klasse == "correct":
        return "correct"
    wrong_classes[klasse] = wrong_classes.get(klasse, 0) + 1
    if len(examples) < 5:
        examples.append(f"{expected} -> {got}")
    return "wrong"


def _reject_reasons(read: ReadResult) -> list[str]:
    """Warum wurde abgelehnt? Aus den Diagnosen des Lesers, nicht geraten."""
    reasons = [f"state:{flag}" for flag in sorted(read.status_flags)]
    if int(read.diagnostics.get("unreadable_cells", 0)):
        reasons.append("unreadable_cells")
    if not read.sign_region_readable:
        reasons.append("sign_region_unreadable")
    if not read.decimal_point_detected:
        reasons.append("decimal_point_unknown")
    return reasons or ["no_value"]


def evaluate_clip(directory: Path, reader: ValueReader) -> Outcome:
    """Einen aufgezeichneten Clip (Task 1/2, `replay://`) dreigeteilt auswerten."""
    source = open_source(f"replay://{directory}")
    source.open()
    clip = source.describe()
    expected = normalise(clip["ground_truth_text"])
    profile = json.loads((directory / "clip.json").read_text())["profile"]
    counts = {"correct": 0, "wrong": 0, "rejected": 0}
    wrong_classes: dict[str, int] = {}
    reject_classes: dict[str, int] = {}
    examples: list[str] = []
    try:
        for frame in source.frames():
            read = read_frame(frame.image, profile, reader)
            counts[_tally(expected, read, examples, wrong_classes, reject_classes)] += 1
    finally:
        source.close()
    return Outcome(
        source_id=source.source_id,
        device_id=clip["device_id"],
        expected=expected,
        correct=counts["correct"],
        wrong=counts["wrong"],
        rejected=counts["rejected"],
        wrong_classes=wrong_classes,
        reject_classes=reject_classes,
        examples=tuple(examples),
    )


def evaluate_annotation(directory: Path, reader: ValueReader) -> Outcome | None:
    """Eine einzelne Workbench-Annotation (`var/workbench/annotations/<id>/`) auswerten.

    Liefert `None`, wenn das Verzeichnis nicht auswertbar ist - fehlender
    Sollwert oder fehlendes `profile.layout` (Altannotation nach Schema 1,
    im Datenbestand z.B. `0dd69042...`). `roi_quad`/`ocr_box` werden bewusst
    von der OBERSTEN Ebene der Annotation genommen, nicht aus `profile`: sie
    sind die fuer diese Aufnahme bestaetigte Geometrie, `profile` kann davon
    abweichen (z.B. bei einer spaeteren Profilaenderung).

    Es gibt in diesem Schema kein `device_id`-Feld (das ist ein Konzept der
    Clipaufnahme aus Task 2) - als Ersatz dient `profile_name`, damit
    mindestens Annahmen ueber "dieselbe Geraeteinstanz" grob pruefbar bleiben.
    """
    annotation = json.loads((directory / "annotation.json").read_text())
    ground_truth_text = annotation.get("ground_truth_text")
    layout_data = (annotation.get("profile") or {}).get("layout")
    if not ground_truth_text or not layout_data:
        return None

    expected = normalise(ground_truth_text)
    image_path = directory / annotation["image"]
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Annotationsbild nicht lesbar: {image_path}")

    profile = {
        "layout": layout_data,
        "roi_quad": annotation["roi_quad"],
        "ocr_box": annotation["ocr_box"],
    }
    counts = {"correct": 0, "wrong": 0, "rejected": 0}
    wrong_classes: dict[str, int] = {}
    reject_classes: dict[str, int] = {}
    examples: list[str] = []
    read = read_frame(image, profile, reader)
    counts[_tally(expected, read, examples, wrong_classes, reject_classes)] += 1
    return Outcome(
        source_id=f"annotation:{directory.name}",
        device_id=str(annotation.get("profile_name", "unknown")),
        expected=expected,
        correct=counts["correct"],
        wrong=counts["wrong"],
        rejected=counts["rejected"],
        wrong_classes=wrong_classes,
        reject_classes=reject_classes,
        examples=tuple(examples),
    )


def _evaluate_directory(directory: Path, reader: ValueReader) -> Outcome | None:
    """Clip oder Annotation erkennen und passend auswerten.

    Unterscheidung ueber die vorhandene Manifestdatei - `clip.json` fuer
    einen aufgezeichneten Clip (Task 1/2), `annotation.json` fuer eine
    Workbench-Annotation. Ein Verzeichnis mit keiner der beiden ist nicht
    auswertbar.
    """
    if (directory / "clip.json").exists():
        return evaluate_clip(directory, reader)
    if (directory / "annotation.json").exists():
        return evaluate_annotation(directory, reader)
    return None


def evaluate_set(directories: Sequence[Path], reader: ValueReader) -> dict[str, Any]:
    """Mehrere Clips/Annotationen zu einem Gesamtbericht zusammenfassen.

    Nicht auswertbare Verzeichnisse (siehe `evaluate_annotation`) werden
    uebersprungen und einzeln unter `skipped` aufgefuehrt - stillschweigendes
    Weglassen waere nach AGENTS.md nicht akzeptabel.
    """
    outcomes: list[Outcome] = []
    skipped: list[str] = []
    for directory in directories:
        outcome = _evaluate_directory(directory, reader)
        if outcome is None:
            skipped.append(str(directory))
        else:
            outcomes.append(outcome)

    correct = sum(o.correct for o in outcomes)
    wrong = sum(o.wrong for o in outcomes)
    rejected = sum(o.rejected for o in outcomes)
    wrong_classes: dict[str, int] = {}
    reject_classes: dict[str, int] = {}
    for outcome in outcomes:
        for klasse, count in outcome.wrong_classes.items():
            wrong_classes[klasse] = wrong_classes.get(klasse, 0) + count
        for reason, count in outcome.reject_classes.items():
            reject_classes[reason] = reject_classes.get(reason, 0) + count

    return {
        "evaluated": len(outcomes),
        "skipped": skipped,
        "correct": correct,
        "wrong": wrong,
        "rejected": rejected,
        "wrong_classes": wrong_classes,
        "reject_classes": reject_classes,
        "outcomes": outcomes,
    }


def _device_of(path: Path) -> str:
    """Geraeteinstanz eines Clip- oder Annotationsverzeichnisses ermitteln."""
    clip_manifest = path / "clip.json"
    if clip_manifest.exists():
        return str(json.loads(clip_manifest.read_text())["device_id"])
    annotation_manifest = path / "annotation.json"
    if annotation_manifest.exists():
        annotation = json.loads(annotation_manifest.read_text())
        return str(annotation.get("profile_name", "unknown"))
    raise ValueError(f"Weder clip.json noch annotation.json in {path}")


def assert_disjoint_devices(development: Sequence[Path], test: Sequence[Path]) -> None:
    """Splitgrenze ist die Geraeteinstanz, nie der Frame (ROADMAP, Konzept §9).

    Benachbarte Frames derselben Aufnahme in Entwicklung und Test wuerden das
    Ergebnis zu optimistisch aussehen lassen. Das hier ist der Test, der bei
    Verletzung fehlschlaegt - nicht nur eine Regel in der Doku.
    """
    left = {_device_of(path) for path in development}
    right = {_device_of(path) for path in test}
    shared = sorted(left & right)
    if shared:
        raise ValueError(
            "Dieselbe Geraeteinstanz steht in Entwicklungs- und Testsatz: " + ", ".join(shared)
        )


def directories_from_glob(pattern: str) -> list[Path]:
    """Hilfsfunktion fuer die CLI: Glob-Muster zu vorhandenen Verzeichnissen."""
    return [Path(p) for p in sorted(glob.glob(pattern)) if Path(p).is_dir()]
