#!/usr/bin/env python3
r"""Entwicklungsmessung (Stufe 1) und Leser-Gegenprobe des Dot-Matrix-Lesers
(Task 7, docs/superpowers/specs/2026-09-24-dotmatrix-reader-design.md
Abschnitt 3).

`evaluate()` klassifiziert je Probe alle 9 Zellen des Zahlenblocks
(`gsv2as_v1`) gegen eingefrorene Vorlagen und vergleicht mit dem gelabelten
Text. Da nur die gespeicherten Punktvektoren vorliegen, nicht das Bild,
werden Kontrast- und Saettigungspruefung hier **nicht** wiederholt (das
macht `DotMatrixReader.read` - siehe `reader-check`) - bewertet werden nur
Zellentscheid und Formatregel.

`loo` (leave-one-group-out) ist die ehrliche Entwicklungsmessung: je
zurueckgehaltener Gruppe werden Vorlagen und Schwellen **ausschliesslich**
aus den uebrigen Gruppen gebaut (nie aus der Testgruppe, auch nicht
indirekt) und gegen die Testgruppe bewertet. Scheitert dabei die
ROM-Gegenprobe (siehe `dotmatrix-train.py`), wird kein Bericht geschrieben.
`--exclude-groups` (mit Pflicht-`--exclude-reason`) wirft Gruppen VOR jedem
Training/jeder Messung raus - fuer Aufbauten mit erwiesenermassen falsch
sitzendem Profil (z. B. Kamera zwischen Bestaetigung und Ernte verschoben).
Ausgeschlossene Gruppen erscheinen in keinem Durchgang und werden im
Bericht unter `excluded_groups` mit ihrem Grund aufgefuehrt.

`reader-check` belegt, dass der volle Leser (`DotMatrixReader.read`, mit
Kontrast-/Saettigungspruefung) und diese Messung (`evaluate`, ohne beide)
auf denselben echten Proben dieselbe Entscheidung treffen - abgesehen von
Ablehnungen, die nur der Leser sehen kann (`kontrast`, `ueberbelichtet`)
oder die er feiner benennt (`vorzeichen` statt `format` - beides verletzt
dieselbe Formatregel, siehe `_normalize_reason`).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from dispread.layout import CharLayout
from dispread.ocr.dotmatrix import DotMatrixReader, parse_gsv2as
from dispread.ocr.dotmatrix_sampling import normalized, sample_image
from dispread.ocr.dotmatrix_templates import (
    ROM_CHECK,
    THRESHOLD_FORMULA,
    Templates,
    classify,
    load_templates,
    rom_deviations,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

#: Einheit des GSV-2AS, aus dem Profil, nicht gelesen (OQ-17,
#: global-constraints.md). In diesem Schritt gibt es kein Feld dafuer im
#: `SessionProfile` - fest fuer dieses Geraet, wie in `tests/test_dotmatrix_reader.py`.
UNIT = "mV/V"


def _load_module(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_dataset_module():
    return _load_module("dotmatrix_dataset", "dotmatrix-dataset.py")


def _load_train_module():
    return _load_module("dotmatrix_train", "dotmatrix-train.py")


def _git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def evaluate(samples, t: Templates) -> dict:
    """Je Probe: alle 9 Zellen klassifizieren, mit dem gelabelten Text
    vergleichen. Ergebnis je Probe `"richtig"`, `"falsch"` oder
    `"abgelehnt:<grund>"`. `<grund>` ist entweder ein Ablehnungsgrund einer
    Zelle (`zelle_unbekannt`/`zelle_mehrdeutig`, die erste in Zellreihenfolge)
    oder `format`, wenn alle Zellen entschieden wurden, der Text aber die
    Formatregel `gsv2as_v1` verletzt (das schliesst ein falsches oder
    fehlendes Vorzeichen in Zelle 0 ein - Vorzeichen ist Teil der Formatregel,
    kein eigener Grund).

    Rueckgabe: `summary` (Zaehlung je Ergebnis-String), `confusion`
    (`dict[wahr][erkannt] -> Anzahl`, nur ueber entschiedene Zellen, nicht
    ueber abgelehnte) und `plateaus` (`gesamt`/`richtig`/`falsch`/`abgelehnt`
    - ein Plateau ist `falsch`, sobald eine seiner Proben `falsch` war,
    sonst `richtig`, wenn mindestens eine Probe `richtig` war, sonst
    `abgelehnt`).
    """
    summary: dict[str, int] = {}
    confusion: dict[str, dict[str, int]] = {}
    plateau_outcomes: dict[tuple[str, tuple[int, int]], list[str]] = {}

    for s in samples:
        true_text = s.cell_text[:9]
        decisions = [classify(s.vectors[i], t) for i in range(9)]
        for i, d in enumerate(decisions):
            if d.text is not None:
                row = confusion.setdefault(true_text[i], {})
                row[d.text] = row.get(d.text, 0) + 1

        reject = next((d.reason for d in decisions if d.reason), None)
        if reject:
            outcome = f"abgelehnt:{reject}"
        else:
            predicted = "".join(d.text for d in decisions)
            if parse_gsv2as(predicted) is None:
                outcome = "abgelehnt:format"
            elif predicted == true_text:
                outcome = "richtig"
            else:
                outcome = "falsch"

        summary[outcome] = summary.get(outcome, 0) + 1
        key = (s.group, s.plateau)
        plateau_outcomes.setdefault(key, []).append(outcome)

    plateaus = {"gesamt": len(plateau_outcomes), "richtig": 0, "falsch": 0, "abgelehnt": 0}
    for outcomes in plateau_outcomes.values():
        if any(o == "falsch" for o in outcomes):
            plateaus["falsch"] += 1
        elif any(o == "richtig" for o in outcomes):
            plateaus["richtig"] += 1
        else:
            plateaus["abgelehnt"] += 1

    return {"summary": summary, "confusion": confusion, "plateaus": plateaus}


def _cmd_loo(args: argparse.Namespace) -> int:
    dataset = _load_dataset_module()
    train_mod = _load_train_module()

    exclude_groups = [g.strip() for g in (args.exclude_groups or "").split(",") if g.strip()]
    if exclude_groups and not args.exclude_reason:
        print("--exclude-reason ist Pflicht, wenn --exclude-groups gesetzt ist.", file=sys.stderr)
        return 2

    profile_map = dataset.read_profile_map(args.profile_map)
    stats: dict[str, int] = {}
    all_samples = dataset.load_cell_samples(args.dataset_root, profile_map, stats=stats)
    all_samples = [s for s in all_samples if s.group not in exclude_groups]
    groups = sorted({s.group for s in all_samples})

    herkunft: dict[str, int] = {}
    for s in all_samples:
        herkunft[s.label_origin] = herkunft.get(s.label_origin, 0) + 1

    durchgaenge = []
    for held_out in groups:
        train_samples = [s for s in all_samples if s.group != held_out]
        test_samples = [s for s in all_samples if s.group == held_out]
        train_groups = tuple(sorted({s.group for s in train_samples}))

        samples_by_char = train_mod.build_samples_by_char(train_samples, stats=stats)
        result = train_mod.train(samples_by_char, train_groups)
        if isinstance(result, list):  # ROM-Gegenprobe gescheitert, Muster bereits ausgegeben
            print(f"Durchgang mit Testgruppe {held_out!r}: kein Bericht geschrieben.", file=sys.stderr)
            return 3

        ev = evaluate(test_samples, result)
        devs = {ch: n for ch, n in rom_deviations(result.mean).items() if n >= 1}
        durchgaenge.append(
            {
                "train_groups": list(train_groups),
                "test_group": held_out,
                "d_max": result.d_max,
                "margin_min": result.margin_min,
                "rom_check": ROM_CHECK,
                "rom_deviations": devs,
                **ev,
            }
        )

    report = {
        "groups": groups,
        "durchgaenge": durchgaenge,
        "excluded_groups": [{"group": g, "reason": args.exclude_reason} for g in sorted(exclude_groups)],
        "lade_zaehler": stats,
        "herkunft": herkunft,
        "hinweis": (
            "Zellen 13-15 (Rest) nur im reader-check geprueft: evaluate() hat nur "
            "die gespeicherten 9-Zellen-Vektoren, keine Zellen 13-15 (Final-Fix 3)."
        ),
        "vorzeichen": "ungeprueft (nur +)",
        "threshold_formula": THRESHOLD_FORMULA,
        "git_commit": _git_commit(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=False, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Bericht geschrieben: {args.out}")
    return 0


#: Ablehnungsgruende, die nur der volle Leser sehen kann (Bild, nicht
#: Vektoren) - eine Abweichung von `evaluate()` hierueber ist erwartet, kein
#: Uneinigkeits-Befund.
_IMAGE_ONLY_REASONS = ("kontrast", "ueberbelichtet")


def _normalize_reason(reason: str | None) -> str | None:
    """`evaluate()` kennt kein eigenes `vorzeichen` - eine falsche oder
    fehlende Vorzeichenzelle verletzt die Formatregel `gsv2as_v1` (Zelle 0 =
    `+`) und wird dort als `format` gezaehlt. Fuer den Vergleich in
    `reader-check` wird die Leser-Ausgabe auf denselben Namen normiert."""
    return "format" if reason == "vorzeichen" else reason


def _reader_outcome(result, true_text: str) -> tuple[str, str | None]:
    """Ergebnis-String wie `evaluate()` liefert, aus einem `ReadResult` -
    plus dem rohen (nicht normierten) Ablehnungsgrund fuer die
    Bild-only-Erkennung."""
    reason = result.diagnostics.get("reject_reason")
    if reason is not None:
        return f"abgelehnt:{_normalize_reason(reason)}", reason
    predicted = "".join(g.text for g in result.glyphs)
    return ("richtig" if predicted == true_text else "falsch"), None


def _cmd_reader_check(args: argparse.Namespace) -> int:
    dataset = _load_dataset_module()
    profile_map = dataset.read_profile_map(args.profile_map)
    templates = load_templates(args.templates, args.templates_sha256)
    reader = DotMatrixReader(templates)

    stats: dict[str, int] = {}
    records = dataset.load_resolved_records(args.dataset_root, profile_map, stats=stats, limit=args.limit)

    einig = 0
    erwartete_abweichung = 0
    uneinig = []
    for rec in records:
        layout = CharLayout(grid=rec.grid, unit=UNIT)
        result = reader.read(rec.crop_gray, layout)
        reader_outcome, raw_reason = _reader_outcome(result, rec.cell_text)

        vectors = normalized(sample_image(rec.crop_gray, rec.grid, range(9)))
        cell_sample = dataset.CellSample(rec.sample_id, rec.group, rec.plateau, rec.cell_text, vectors)
        ev = evaluate([cell_sample], templates)
        messung_outcome = next(iter(ev["summary"]))

        if reader_outcome == messung_outcome:
            einig += 1
        elif raw_reason in _IMAGE_ONLY_REASONS:
            erwartete_abweichung += 1
        else:
            uneinig.append({"sample_id": rec.sample_id, "leser": reader_outcome, "messung": messung_outcome})

    out = {
        "n": len(records),
        "einig": einig,
        "erwartete_abweichung_bild": erwartete_abweichung,
        "uneinig": uneinig,
        "datensatz_zaehler": stats,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if not uneinig else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Entwicklungsmessung und Leser-Gegenprobe des Dot-Matrix-Lesers.")
    sub = parser.add_subparsers(dest="command", required=True)

    loo = sub.add_parser("loo", help="Leave-one-group-out Entwicklungsmessung (Stufe 1).")
    loo.add_argument("--dataset-root", type=Path, required=True)
    loo.add_argument("--profile-map", type=Path, required=True)
    loo.add_argument("--out", type=Path, required=True)
    loo.add_argument(
        "--exclude-groups",
        default="",
        help="Kommagetrennte Gruppen, die vor jedem Training/jeder Messung verworfen werden "
        "(z. B. ein Aufbau mit erwiesenermassen falsch sitzendem Profil). Erscheinen in keinem "
        "Durchgang, weder als train_groups noch als test_group. Braucht --exclude-reason.",
    )
    loo.add_argument(
        "--exclude-reason", default=None, help="Begruendung fuer --exclude-groups, steht im Bericht (Pflicht, wenn gesetzt)."
    )
    loo.set_defaults(func=_cmd_loo)

    reader_check = sub.add_parser("reader-check", help="Volle Leser-Ausgabe gegen evaluate() vergleichen.")
    reader_check.add_argument("--dataset-root", type=Path, required=True)
    reader_check.add_argument("--profile-map", type=Path, required=True)
    reader_check.add_argument("--templates", type=Path, required=True)
    reader_check.add_argument(
        "--templates-sha256", required=True, help="Erwartete Pruefsumme von --templates (Pflicht, fail-open schliessen)"
    )
    reader_check.add_argument("--limit", type=int, default=20)
    reader_check.set_defaults(func=_cmd_reader_check)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
