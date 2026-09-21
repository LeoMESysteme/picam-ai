#!/usr/bin/env python3
"""Sammelmodus-Proben gegen den 7-Segment-Leser messen. Schreibt nichts in die Doku.

Aufruf:
    ./.venv/bin/python scripts/dataset-benchmark.py --samples var/workbench/datasets --split development

Liest reale Proben aus dem geführten Sammelmodus (`dispread.workbench.datasets`,
nicht die älteren Annotationen/Clips - dafür ist `ocr-benchmark.py` da) und
druckt zwei getrennte Berichte je Gerät:

  Phase A (Passbarkeit/Diagnose) - AUSDRÜCKLICH KEIN ERKENNUNGSWERT. Grobe
  Rahmenvorsuche + `fit_layout` auf jeder lesbaren Probe einzeln, ohne
  eingefrorene Verhältnisse. Beantwortet OQ-23: passt das feste relative
  Segment-Abtastraster überhaupt zur realen Schrift? Wenn nichts passt (heute
  der erwartete Regelfall laut Vorab-Messung im Plan), wird stattdessen die
  Segmentdiagnose einiger Beispiele gedruckt - welches Segment falsch
  abgetastet wird.

  Phase B (Übertragung) - die eigentliche Erkennungszahl. Leave-one-group-out
  je Gerät: Glyphenverhältnisse auf dem `selected`-Vertreter EINER Situation
  fitten, auf die lesbaren Proben aller ANDEREN Situationen anwenden. Ein
  Gerät mit nur einer Situation (aktuell BK Precision) kann das nicht - das
  wird als benannte Datenlücke gemeldet, nicht stillschweigend übersprungen.

Beide Geometriearme (achsparallel/entzerrt) werden getrennt berichtet, nie
gemischt - `--deskew both|off|on` wählt, welche laufen.

Bekannte, bewusste Lücken dieses Laufs (siehe
docs/PLAN_2026-09-21-dataset-benchmark.md):
  - Keine Aufschlüsselung nach Bedingung (reflection/angled/...).
  - Der Ähnlichkeitsgrad je Faltung wird nicht extra gemessen - nur das
    bereits gespeicherte `similarity_warning` je Probe wird durchgereicht.
  - `has_sign` kommt NICHT von einem Gerätefeld (existiert nicht im
    aktuellen Schema von `dispread.workbench.datasets`), sondern wird aus
    dem Vorzeichen aller LESBAREN Proben eines Geräts aggregiert - nie aus
    der einzelnen Zielprobe einer Auswertung (siehe `benchmark.target_layout`).

Die Leser-Polarität (`dark_on_bright` für LCD, sonst `bright_on_dark`) kommt
dagegen SEHR WOHL aus einem Gerätefeld (`technology` in `devices.json`,
direkt gelesen, siehe `_device_polarities`) - eine falsche Polarität lässt
JEDE Probe scheitern, unabhängig von der Geometrie, weil `fit_layout` sie
nicht mitsucht (2026-09-21, GSV-Sensor-Fund).

Die Fehlerklasse "decimal" ist in dieser Messanordnung strukturell
unerreichbar (der Dezimalpunkt kommt aus dem eingefrorenen Layout, nicht aus
einer Messung, siehe OQ-17) - "0 Dezimalfehler" ist daher kein Befund.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2

from dispread.benchmark import (
    DatasetSample,
    Outcome,
    aggregate,
    assert_disjoint_groups,
    evaluate_dataset_sample,
    fit_dataset_sample,
    load_dataset_samples,
    sample_quad,
    segment_report,
    target_layout,
)
from dispread.layout import DisplayLayout
from dispread.ocr.autofit import parse_expected
from dispread.ocr.sevenseg import SevenSegmentReader
from dispread.rectify import rectify
from dispread.workbench.controller import CROP_SIZE
from dispread.workbench.vision import fit_ocr_box

GEOMETRIES = {"axis_aligned": False, "deskewed": True}

_FROZEN_RATIO_KEYS = ("digit_gap_ratio", "sign_cell_ratio", "thickness_ratio", "inset_ratio")

#: Geraete-`technology` (`dispread.workbench.datasets.TECHNOLOGIES`) -> Leser-Polaritaet.
#: LCD zeigt dunkle Segmente auf hellem Grund, alles andere (LED/VFD/other)
#: den DisplayLayout-Default. `fit_layout` sucht Polaritaet nicht mit (kein
#: Eintrag in `autofit._CANDIDATES`) - eine falsche Polaritaet laesst JEDE
#: Probe scheitern, unabhaengig von der Geometrie (2026-09-21, GSV-Sensor-Fund).
_TECHNOLOGY_POLARITY = {"LCD": "dark_on_bright"}
_DEFAULT_POLARITY = "bright_on_dark"


def _device_polarities(root: Path) -> dict[str, str]:
    """`device_id -> Polaritaet`, aus `root/devices.json` direkt gelesen.

    Keine `DatasetStore`-Instanz (siehe Task-1-Docstring in `benchmark.py`,
    dieselbe Begruendung: reiner Lesezugriff auf eine bereits geschriebene
    Datei, kein Grund fuer die volle Store-Maschinerie). Fehlt die Datei oder
    ein Geraet darin, bekommt es den Default - eine fehlende Zuordnung ist
    kein Grund, den ganzen Lauf abzubrechen, aber sie wird nicht erraten:
    unbekannte Technologie-Werte fallen auf den LED/VFD-Default, nicht auf LCD.
    """
    devices_path = root / "devices.json"
    if not devices_path.is_file():
        return {}
    try:
        registry = json.loads(devices_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        device_id: _TECHNOLOGY_POLARITY.get(device.get("technology"), _DEFAULT_POLARITY)
        for device_id, device in registry.get("devices", {}).items()
    }


def _device_has_sign(samples: list[DatasetSample]) -> bool:
    """`has_sign` fuer ein Geraet aus ALLEN lesbaren Proben aggregiert.

    Kein Geraetefeld dafuer im aktuellen Schema von `DatasetStore` (Abweichung
    vom Plan, siehe Modul-Docstring). Aggregiert ueber den gesamten Bestand
    des Geraets, nicht aus der einzelnen Probe einer laufenden Auswertung -
    das ist der Unterschied zwischen "vom Geraet" und "vom Zieltext dieser
    Messung" (Konzept.md §7: Vorzeichen ist eine eigene kritische Klasse).
    """
    return any(
        s.expected_text is not None and s.expected_text.strip().startswith("-")
        for s in samples
        if s.label_state == "readable"
    )


def _geometries(arg: str) -> list[str]:
    if arg == "both":
        return ["axis_aligned", "deskewed"]
    if arg == "off":
        return ["axis_aligned"]
    return ["deskewed"]


def _load_image(sample: DatasetSample) -> Any:
    image = cv2.imread(str(sample.image_path))
    if image is None:
        raise FileNotFoundError(f"Probenbild nicht lesbar: {sample.image_path}")
    return image


def _print_phase_a(
    device_id: str,
    geometry: str,
    fits: list[tuple[DatasetSample, Any]],
    *,
    diagnose: int,
    reader: SevenSegmentReader,
    polarity: str,
) -> None:
    matched = [f for _s, f in fits if f.matched]
    no_quad = [f for _s, f in fits if f.quad is None]
    print(f"  -- Phase A ({geometry}), ausdruecklich KEIN Erkennungswert --")
    print(f"     Proben: {len(fits)}  gefittet: {len(matched)}  kein Quad: {len(no_quad)}")
    if matched:
        for key in _FROZEN_RATIO_KEYS:
            values = sorted(getattr(f.layout, key) for f in matched)
            print(f"     {key}: {values}")
        flat = sum(1 for f in matched if f.flat_optimum)
        print(f"     flat_optimum: {flat}/{len(matched)}")
    unmatched = [(s, f) for s, f in fits if not f.matched and f.quad is not None]
    if unmatched and diagnose > 0:
        print(f"     Segmentdiagnose (bis zu {diagnose} Beispiele, unbestaetigter Rahmen, Polaritaet={polarity}):")
        for sample, fit in unmatched[:diagnose]:
            _print_segment_diagnosis(sample, fit, reader, polarity)


def _print_segment_diagnosis(sample: DatasetSample, fit, reader: SevenSegmentReader, polarity: str) -> None:
    assert sample.expected_text is not None
    try:
        image = _load_image(sample)
        height, width = image.shape[:2]
        pixel_quad = tuple((x * width, y * height) for x, y in fit.quad)
        crop = rectify(image, pixel_quad, target_size=CROP_SIZE).image
        _digits_str, minus, digits, decimals = parse_expected(sample.expected_text)
        layout_hint = DisplayLayout(digits=digits, decimals=decimals, has_sign=minus, polarity=polarity)
        box = fit_ocr_box(crop, layout_hint) or (0.0, 0.0, 1.0, 1.0)
        report = segment_report(crop, layout_hint, box, sample.expected_text, reader=reader)
    except Exception as exc:  # Diagnose ist best-effort, darf den Lauf nicht abbrechen.
        print(f"       {sample.id}: Segmentdiagnose nicht moeglich ({exc})")
        return
    print(f"       {sample.id} (soll={sample.expected_text}, unbestaetigter Rahmen {box}):")
    for entry in report:
        print(
            f"         Stelle {entry['index']}: erwartet {entry['expected_digit']}="
            f"{','.join(entry['expected_segments'])}  gemessen={entry['got_text']}"
            f" segmente={entry['got_segments']}"
            f" werte={ {k: round(v, 2) for k, v in entry['values'].items()} }"
        )


def _reject_outcome(source_id: str, device_id: str, expected: str, reason: str) -> Outcome:
    return Outcome(
        source_id=source_id,
        device_id=device_id,
        expected=expected,
        correct=0,
        wrong=0,
        rejected=1,
        wrong_classes={},
        reject_classes={reason: 1},
        examples=(),
    )


def _run_fold(
    device_id: str,
    held_out_group: str,
    representative: DatasetSample,
    evaluation: list[DatasetSample],
    *,
    has_sign: bool,
    deskew: bool,
    reader: SevenSegmentReader,
    polarity: str,
) -> None:
    geometry = "deskewed" if deskew else "axis_aligned"
    print(f"  -- Phase B, Situation '{held_out_group}' ausgelassen ({geometry}) --")
    print(f"     Nenner (lesbare Proben anderer Situationen): {len(evaluation)}")

    assert_disjoint_groups([representative], evaluation)

    rep_image = _load_image(representative)
    rep_fit = fit_dataset_sample(
        rep_image, representative, has_sign=has_sign, deskew=deskew, reader=reader, polarity=polarity
    )
    if not rep_fit.matched:
        print(
            "     kein Raster gefunden, keine Uebertragung moeglich "
            f"(Vertreter {representative.id} passte in {rep_fit.evaluated} Leseversuchen nicht: {rep_fit.reason})"
        )
        return

    frozen_ratios = {key: getattr(rep_fit.layout, key) for key in _FROZEN_RATIO_KEYS}
    outcomes: list[Outcome] = []
    for sample in evaluation:
        expected = sample.expected_text or ""
        target = target_layout(has_sign, sample, frozen_ratios, polarity=polarity)
        image = _load_image(sample)
        quad = sample_quad(image, sample.bbox, deskew=deskew)
        if quad is None:
            outcomes.append(_reject_outcome(f"sample:{sample.id}", device_id, expected, "kein_quad"))
            continue
        height, width = image.shape[:2]
        pixel_quad = tuple((x * width, y * height) for x, y in quad)
        crop = rectify(image, pixel_quad, target_size=CROP_SIZE).image
        box = fit_ocr_box(crop, target)
        if box is None:
            outcomes.append(_reject_outcome(f"sample:{sample.id}", device_id, expected, "kein_ocr_box"))
            continue

        outcome = evaluate_dataset_sample(image, sample, target, box, reader, deskew=deskew)
        outcomes.append(outcome or _reject_outcome(f"sample:{sample.id}", device_id, expected, "kein_quad"))

    report = aggregate(outcomes)
    total = report["evaluated"] or 1
    print(
        f"     korrekt={report['correct']} ({100 * report['correct'] / total:.0f}%)  "
        f"falsch angenommen={report['wrong']} ({100 * report['wrong'] / total:.0f}%)  "
        f"abgelehnt={report['rejected']} ({100 * report['rejected'] / total:.0f}%)"
    )
    if report["wrong_classes"]:
        print(f"     Fehlerklassen: {dict(sorted(report['wrong_classes'].items()))}")
    if report["reject_classes"]:
        print(f"     Ablehnungsgruende: {dict(sorted(report['reject_classes'].items()))}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--samples", type=Path, default=Path("var/workbench/datasets"))
    parser.add_argument("--split", choices=("development", "heldout", "all"), default="development")
    parser.add_argument("--deskew", choices=("both", "off", "on"), default="both")
    parser.add_argument("--device", help="Nur dieses Geraet (device_id) auswerten")
    parser.add_argument("--diagnose", type=int, default=3, help="Segmentdiagnose-Beispiele je Geometrie/Geraet")
    args = parser.parse_args()

    all_samples, skipped = load_dataset_samples(args.samples)
    print(f"geladen: {len(all_samples)}  uebersprungen: {len(skipped)}")
    for entry in skipped:
        print(f"  uebersprungen: {entry}")
    if not all_samples:
        print("FEHLER: keine auswertbaren Proben gefunden", file=sys.stderr)
        return 1

    print(
        "Hinweis: 'decimal' ist in dieser Messanordnung strukturell unerreichbar "
        "(der Dezimalpunkt kommt aus dem eingefrorenen Layout, nicht aus einer Messung, OQ-17)."
    )

    if args.split != "all":
        scoped = [s for s in all_samples if s.split == args.split]
        if not scoped:
            print(f"LUECKE: kein Gerät hat Proben mit split={args.split!r}")
        all_samples = scoped

    by_device: dict[str, list[DatasetSample]] = defaultdict(list)
    for sample in all_samples:
        by_device[sample.device_id].append(sample)

    polarities = _device_polarities(args.samples)
    devices = [args.device] if args.device else sorted(by_device)
    reader = SevenSegmentReader()
    geometries = _geometries(args.deskew)

    exit_code = 0
    for device_id in devices:
        samples = by_device.get(device_id, [])
        if not samples:
            print(f"LUECKE: Geraet {device_id!r} hat keine Proben in split={args.split!r}")
            continue
        print(f"\n=== Geraet {device_id} ===")

        unreadable = [s for s in samples if s.label_state == "unreadable"]
        readable = [s for s in samples if s.label_state == "readable"]
        for sample in unreadable:
            print(f"  Einzelfalldiagnose (unlesbar, n=1, keine Quote): {sample.id}")

        if not readable:
            print("  LUECKE: keine lesbaren Proben")
            continue

        has_sign = _device_has_sign(readable)
        polarity = polarities.get(device_id, _DEFAULT_POLARITY)
        print(f"  has_sign (aus allen lesbaren Proben aggregiert): {has_sign}")
        print(f"  Polaritaet (aus Geraete-technology, LCD=dark_on_bright): {polarity}")

        for geometry in geometries:
            deskew = GEOMETRIES[geometry]
            fits = [
                (
                    sample,
                    fit_dataset_sample(
                        _load_image(sample),
                        sample,
                        has_sign=has_sign,
                        deskew=deskew,
                        reader=reader,
                        polarity=polarity,
                    ),
                )
                for sample in readable
            ]
            _print_phase_a(device_id, geometry, fits, diagnose=args.diagnose, reader=reader, polarity=polarity)

            groups = sorted({s.independence_group for s in readable})
            if len(groups) < 2:
                print(f"  -- Phase B ({geometry}) --")
                print(f"     LUECKE: nur {len(groups)} Situation(en) - Uebertragung ueber Situationen unmoeglich")
                continue

            for held_out in groups:
                candidates = [s for s in readable if s.independence_group == held_out and s.selected]
                if len(candidates) != 1:
                    print(
                        f"FEHLER: Situation {held_out!r} von Geraet {device_id} hat "
                        f"{len(candidates)} als 'selected' markierte Proben (erwartet genau 1) - "
                        "diese Faltung wird uebersprungen, kein Ersatzvertreter erraten",
                        file=sys.stderr,
                    )
                    exit_code = 1
                    continue
                representative = candidates[0]
                evaluation = [s for s in readable if s.independence_group != held_out]
                _run_fold(
                    device_id,
                    held_out,
                    representative,
                    evaluation,
                    has_sign=has_sign,
                    deskew=deskew,
                    reader=reader,
                    polarity=polarity,
                )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
