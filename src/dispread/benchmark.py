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
nicht nur als Doku-Regel - und verlangt dafuer eine ausdrueckliche
`device_id` je Aufnahme, statt ersatzweise den Profilnamen zu nehmen.
"""

from __future__ import annotations

import glob
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from dispread.frames import open_source, path_uri
from dispread.layout import DisplayLayout
from dispread.ocr import ReadResult, ValueReader
from dispread.rectify import rectify
from dispread.workbench.controller import CROP_SIZE, crop_box
from dispread.workbench.vision import fit_quad_in_region

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
    "DatasetSample",
    "load_dataset_samples",
    "sample_quad",
    "assert_disjoint_groups",
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
    """Getippten oder gelesenen Wert vergleichbar machen, OHNE die Dezimalstelle zu verlieren.

    Bediener tippen mit Komma ("28,80"), der Leser liefert einen Punkt - das
    ist reine Tippkonvention und wird vereinheitlicht. Die *Position* des
    Trenners ist dagegen Messinhalt: "28.80" und "288.0" sind verschiedene
    Werte um den Faktor zehn. Frueher entfernte diese Funktion den Trenner
    ganz, beide wurden zu "2880" und `classify` meldete "correct" - ein
    Stellenfehler war im Benchmark unsichtbar (Review-Fund). Konzept.md §7
    nennt den uebersehenen Dezimalpunkt ausdruecklich als eigenstaendigen
    kritischen Fehler.

    Vereinheitlicht werden nur Schreibweisen, die denselben Wert meinen:
    Komma/Punkt, Leerzeichen, der nachgestellte Punkt eines Ganzzahlformats
    ("1234." bei `layout.decimals == 0`, siehe `SevenSegmentReader.read`) und
    die fuehrende Null vor dem Trenner (".13" -> "0.13", entsteht bei
    `digits == decimals`).
    """
    text = text.strip().replace(",", ".").replace(" ", "")
    if text.startswith("+"):
        # Ein gesetztes Pluszeichen bedeutet dasselbe wie keines; ein
        # Minuszeichen bleibt selbstverstaendlich stehen.
        text = text[1:]
    if text.endswith("."):
        text = text[:-1]
    if text.startswith("."):
        text = "0" + text
    elif text.startswith("-."):
        text = "-0" + text[1:]
    return text


def _parts(text: str) -> tuple[str, str, int]:
    """(Vorzeichen, Ziffernfolge ohne Trenner, Anzahl Nachkommastellen).

    Zerlegt genau ein fuehrendes Vorzeichen - eine Kette wie "--12" ist
    mehrdeutige Eingabe und bleibt so als Abweichung sichtbar, statt still
    zurechtgebogen zu werden (AGENTS.md: ablehnen statt raten).
    """
    sign = "-" if text.startswith("-") else ""
    body = text[1:] if text[:1] in ("+", "-") else text
    whole, dot, fraction = body.partition(".")
    return sign, whole + fraction, len(fraction) if dot else 0


def classify(expected: str, got: str) -> str:
    """Fehlerklasse einer Abweichung. Konzept.md §7 verlangt getrennte Klassen.

    Reihenfolge der Pruefung ist bewusst: stimmen Ziffernfolge *und*
    Dezimalstelle, bleibt nur das Vorzeichen uebrig. Stimmt die Ziffernfolge,
    aber nicht die Dezimalstelle, ist es ein Stellenfehler ("decimal") - der
    gefaehrlichste stille Fall, weil die Ziffern selbst richtig aussehen.
    """
    if expected == got:
        return "correct"
    expected_sign, expected_digits, expected_decimals = _parts(expected)
    got_sign, got_digits, got_decimals = _parts(got)
    if expected_digits == got_digits and expected_decimals == got_decimals:
        return "sign" if expected_sign != got_sign else "digit"
    if expected_digits == got_digits:
        return "decimal"
    if len(expected_digits) != len(got_digits):
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
    """Einen aufgezeichneten Clip (Task 1/2, `replay://`) dreigeteilt auswerten.

    Die URI kommt aus `path_uri` und nicht aus einem f-String: ein relativer
    Pfad (`var/workbench/clips/abc`) landete sonst mit seinem ersten Segment
    in der URL-Autoritaet und wurde beim Oeffnen stillschweigend abgeschnitten
    (Review-Fund).
    """
    source = open_source(path_uri("replay", directory))
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

    `device_id` ist optional und wird, falls vorhanden, unveraendert
    uebernommen. Fehlt es, steht im Bericht `unbekannt` - ausdruecklich nur
    als Etikett fuer die Ausgabe. Fuer die Splitgrenze zaehlt es nicht:
    `_device_of`/`assert_disjoint_devices` verweigern die Bescheinigung eines
    disjunkten Splits, statt ersatzweise `profile_name` zu nehmen (der ist
    ein Profiletikett, kein Geraet - dasselbe Geraet kann nach einer
    Neukalibrierung unter zwei Namen liegen, Review-Fund).
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
        device_id=str(annotation.get("device_id") or "unbekannt"),
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
    """Geraeteinstanz eines Clip- oder Annotationsverzeichnisses ermitteln.

    Nur ein ausdrueckliches `device_id` gilt. Frueher diente bei Annotationen
    ersatzweise `profile_name` - das ist aber ein vom Bediener gewaehltes
    Profiletikett und keine Geraetekennung: dasselbe Geraet unter zwei
    Profilnamen sah wie zwei Geraete aus, und der Split galt faelschlich als
    disjunkt (Review-Fund). Ohne Kennung wird deshalb abgelehnt statt
    geraten (AGENTS.md).
    """
    clip_manifest = path / "clip.json"
    annotation_manifest = path / "annotation.json"
    if clip_manifest.exists():
        device = json.loads(clip_manifest.read_text()).get("device_id")
    elif annotation_manifest.exists():
        device = json.loads(annotation_manifest.read_text()).get("device_id")
    else:
        raise ValueError(f"Weder clip.json noch annotation.json in {path}")
    device = str(device or "").strip()
    if not device:
        raise ValueError(
            f"Keine Geraetekennung (device_id) in {path} - ein geraetedisjunkter "
            "Split laesst sich damit nicht bescheinigen. profile_name ist ein "
            "Profiletikett, keine Geraeteinstanz, und wird hier bewusst nicht "
            "ersatzweise verwendet."
        )
    return device


def assert_disjoint_devices(development: Sequence[Path], test: Sequence[Path]) -> None:
    """Splitgrenze ist die Geraeteinstanz, nie der Frame (ROADMAP, Konzept §9).

    Benachbarte Frames derselben Aufnahme in Entwicklung und Test wuerden das
    Ergebnis zu optimistisch aussehen lassen. Das hier ist der Test, der bei
    Verletzung fehlschlaegt - nicht nur eine Regel in der Doku.

    Ist die Geraeteinstanz eines Eingabeverzeichnisses nicht ausdruecklich
    bekannt, schlaegt das hier ebenfalls fehl (siehe `_device_of`): ein
    "vermutlich disjunkt" waere keine Bescheinigung.
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


# --- Datensatz-Benchmark (Sammelmodus-Proben) ------------------------------
#
# Ab hier: Proben aus `var/workbench/datasets/` (geführter Sammelmodus,
# `dispread.workbench.datasets.DatasetStore`), nicht Clips/Annotationen. Die
# Zahlengeometrie (`sample_quad`) und der Split-Schutz (`assert_disjoint_groups`)
# sind eigene Bausteine, weil eine Probe eine `bbox` in Pixelkoordinaten traegt,
# nicht bereits ein bestaetigtes `roi_quad`.


@dataclass(frozen=True, slots=True)
class DatasetSample:
    """Eine geladene Sammelmodus-Probe (`samples/<uuid>/{sample.json,image.png}`).

    `expected_text` ist `None` genau dann, wenn `label_state == "unreadable"` -
    eine unlesbare Probe hat per Exportvertrag keinen Sollwert und wird als
    benannte Einzelfalldiagnose weitergereicht (Konzept §7: Unlesbares
    ablehnen statt raten), nicht in eine Zaehlung gefaltet. `bbox` bleibt in
    Pixelkoordinaten, wie in `sample.json` gespeichert - `sample_quad`
    normiert sie erst bei Bedarf.
    """

    id: str
    device_id: str
    independence_group: str
    split: str
    label_state: str
    expected_text: str | None
    bbox: tuple[float, float, float, float]
    image_path: Path
    width: int
    height: int


#: Schluessel, die jede Probe unabhaengig vom Label-Zustand tragen muss.
_REQUIRED_SAMPLE_KEYS = (
    "id",
    "device_id",
    "independence_group",
    "split",
    "label_state",
    "bbox",
    "width",
    "height",
    "synthetic",
)


def load_dataset_samples(root: Path) -> tuple[list[DatasetSample], list[str]]:
    """`root/samples/<uuid>/sample.json` laden, wie es `DatasetStore` ablegt.

    Liest die Manifeste direkt (kein `DatasetStore` - dessen Instanzierung ist
    erst Task 3s Sache fuer `list_devices`/`_similarity_score`). Uebersprungen
    wird, "wie der Exportvertrag" es vormacht (`DatasetStore.export_dataset`):
    synthetische Proben (`synthetic: true`) und Proben mit
    `label_state in ("uncertain", "draft")` - deren Sollwert gilt nicht als
    belastbar genug fuer einen Benchmark. Jeder Uebersprung, jedes defekte
    Verzeichnis und jedes fehlende Pflichtfeld wird einzeln in `skipped`
    benannt (AGENTS.md: nie unmarkiert weglassen) statt eine Ausnahme zu
    werfen, die den ganzen Ladevorgang fuer eine einzelne kaputte Datei
    abbricht.

    `label_state == "unreadable"` ist dagegen KEIN Uebersprung: die Probe wird
    geladen (mit `expected_text=None`), damit ein Aufrufer sie als benannte
    Einzelfalldiagnose ausgeben kann, statt sie stillschweigend wegzulassen
    oder faelschlich in einen Nenner zu falten (Plan-Vorgabe, siehe
    Docstring von `DatasetSample`).
    """
    samples: list[DatasetSample] = []
    skipped: list[str] = []
    samples_root = root / "samples"
    if not samples_root.is_dir():
        return samples, skipped

    for sample_dir in sorted(p for p in samples_root.iterdir() if p.is_dir()):
        manifest_path = sample_dir / "sample.json"
        try:
            raw = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            skipped.append(f"{sample_dir}: sample.json nicht lesbar ({exc})")
            continue

        missing = [key for key in _REQUIRED_SAMPLE_KEYS if key not in raw]
        if missing:
            skipped.append(f"{sample_dir}: fehlende Felder {missing}")
            continue

        if raw["synthetic"] is True:
            skipped.append(f"{sample_dir}: synthetisch (nicht Teil der realen Auswertung)")
            continue

        label_state = raw["label_state"]
        if label_state in ("uncertain", "draft"):
            skipped.append(f"{sample_dir}: label_state={label_state} (kein belastbarer Sollwert)")
            continue

        expected_text: str | None
        if label_state == "readable":
            expected_text = raw.get("expected_text")
            if not expected_text:
                skipped.append(f"{sample_dir}: label_state=readable ohne expected_text")
                continue
        elif label_state == "unreadable":
            expected_text = None
        else:
            skipped.append(f"{sample_dir}: unbekannter label_state={label_state!r}")
            continue

        samples.append(
            DatasetSample(
                id=str(raw["id"]),
                device_id=str(raw["device_id"]),
                independence_group=str(raw["independence_group"]),
                split=str(raw["split"]),
                label_state=label_state,
                expected_text=expected_text,
                bbox=tuple(float(v) for v in raw["bbox"]),
                image_path=sample_dir / "image.png",
                width=int(raw["width"]),
                height=int(raw["height"]),
            )
        )
    return samples, skipped


def sample_quad(
    image: Any, bbox: tuple[float, float, float, float], *, deskew: bool
) -> tuple[tuple[float, float], ...] | None:
    """Pixel-`bbox` in das normierte Quad ueberfuehren, das `read_frame` erwartet.

    `deskew=False` (Arm 1): reine Normierung der achsparallelen Box auf ihre
    vier Eckpunkte - keine Suche, keine Rotation. `deskew=True` (Arm 2): erst
    normieren, dann `fit_quad_in_region` als perspektivischen Vorschlag
    innerhalb dieses Hinweisbereichs suchen lassen. Liefert `fit_quad_in_region`
    `None` (kein Kandidat besteht die Filter), gibt auch `sample_quad` `None`
    zurueck - **kein** stiller Rueckfall auf Arm 1. Der Plan verlangt den
    Vergleich beider Arme nur ueber Proben, bei denen beide ein Quad
    geliefert haben, plus eine getrennte Zahl der `None`-Faelle; ein Rueckfall
    wuerde die beiden Arme vermischen und den Vergleich uninterpretierbar
    machen.
    """
    height, width = image.shape[:2]
    x, y, w, h = bbox
    nx, ny, nw, nh = x / width, y / height, w / width, h / height
    if deskew:
        return fit_quad_in_region(image, (nx, ny, nw, nh))
    return (
        (nx, ny),
        (nx + nw, ny),
        (nx + nw, ny + nh),
        (nx, ny + nh),
    )


def assert_disjoint_groups(
    fitting: Sequence[DatasetSample], evaluation: Sequence[DatasetSample]
) -> None:
    """Unabhaengigkeitsgruppen-Analogon zu `assert_disjoint_devices`.

    Fuer Phase Bs "RND-Lab"-Faltungen (Raster auf dem Vertreter einer
    Situation fitten, gegen die Proben der anderen Situationen pruefen):
    dieselbe `independence_group` darf nicht gleichzeitig auf der
    Fitting-Seite und der Auswertungsseite einer Faltung stehen, sonst waere
    das Ergebnis der Faltung durch korrelierte Proben optimistisch verzerrt -
    exakt dieselbe Begruendung wie bei `assert_disjoint_devices`, nur auf
    Gruppen- statt Geraeteebene. Dies ist die Pruefprimitive, die Task 3 pro
    Faltung einmal aufruft - der Aufbau der Faltungen selbst gehoert Task 3.
    """
    left = {sample.independence_group for sample in fitting}
    right = {sample.independence_group for sample in evaluation}
    shared = sorted(left & right)
    if shared:
        raise ValueError(
            "Dieselbe Unabhaengigkeitsgruppe steht auf beiden Seiten einer Faltung: "
            + ", ".join(shared)
        )
