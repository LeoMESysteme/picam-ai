#!/usr/bin/env python3
"""Fakten der Projekt-Tour aus dem Code (docs/uebersicht/projekt-tour.md).

Die Szenen der Tour (`docs-site/assets/tour*.js`) und ihre Texte zeigen Werte
aus dem Code: Felder des ValueRecord, Voreinstellungen der Freigabe, Grenzen
des Trackers, den Zeichensatz des Lesers, Kamera- und Ernteparameter,
Testnamen. Damit eine Grafik nach einer Codeänderung nicht still den alten
Stand zeigt, liest dieses Skript die Werte statisch aus dem Quelltext (ast und
reguläre Ausdrücke, es importiert nichts und braucht nur die
Standardbibliothek) und schreibt sie nach
`docs-site/assets/data/tour-facts.json`. Die Szenen zeichnen mit diesen
Werten (`window.dispreadTour.fact(id, fallback)`).

    ./scripts/tour-facts.py --write   # Datei neu schreiben (nach Prüfung)
    ./scripts/tour-facts.py --check   # Code gegen die versionierte Datei

`--check` endet mit Exit 1, wenn sich ein Wert geändert hat, und nennt die
betroffenen Tour-Schritte (`used_by`, h3-IDs der Tour-Seite). Dann diese
Schritte ansehen: Text und Szene anpassen, falls nötig, und mit `--write`
übernehmen. `scripts/docs-site.sh` ruft `--check` vor jedem Build auf, der
Test `tests/test_tour_facts.py` ebenso.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs-site/assets/data/tour-facts.json"
TOUR_PAGE = ROOT / "docs/uebersicht/projekt-tour.md"
SCHEMA = "tour_facts_v1"


class FactError(RuntimeError):
    """Ein Fakt ist im Code nicht (mehr) an der erwarteten Stelle."""


# ---------------------------------------------------------------- Lesehilfen --

@cache
def _source(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise FactError(f"{rel} fehlt")
    return path.read_text(encoding="utf-8")


@cache
def _tree(rel: str) -> ast.Module:
    return ast.parse(_source(rel), filename=rel)


def _class(rel: str, name: str) -> ast.ClassDef:
    for node in ast.walk(_tree(rel)):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise FactError(f"{rel}: Klasse {name} fehlt")


def _function(rel: str, cls: str | None, name: str) -> ast.FunctionDef:
    body = _class(rel, cls).body if cls else _tree(rel).body
    for node in body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise FactError(f"{rel}: {cls + '.' if cls else ''}{name} fehlt")


def annotated_fields(rel: str, cls: str) -> list[str]:
    return [n.target.id for n in _class(rel, cls).body
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]


def field_default(rel: str, cls: str, field: str):
    for n in _class(rel, cls).body:
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == field:
            if n.value is None:
                break
            return ast.literal_eval(n.value)
    raise FactError(f"{rel}: {cls}.{field} ohne Vorgabewert")


def enum_members(rel: str, cls: str) -> dict[str, str]:
    out = {}
    for n in _class(rel, cls).body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            out[n.targets[0].id] = ast.literal_eval(n.value)
    if not out:
        raise FactError(f"{rel}: {cls} ohne Mitglieder")
    return out


def module_constant(rel: str, name: str):
    for n in _tree(rel).body:
        if isinstance(n, ast.Assign):
            targets, value = n.targets, n.value
        elif isinstance(n, ast.AnnAssign) and n.value is not None:
            targets, value = [n.target], n.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                # re.compile(r"...") -> Muster
                if isinstance(value, ast.Call) and getattr(value.func, "attr", "") == "compile":
                    return ast.literal_eval(value.args[0])
                return ast.literal_eval(value)
    raise FactError(f"{rel}: Konstante {name} fehlt")


def params(rel: str, cls: str, func: str) -> list[str]:
    fn = _function(rel, cls, func)
    return [a.arg for a in fn.args.args if a.arg != "self"]


def returns_constant(rel: str, cls: str, func: str):
    for node in ast.walk(_function(rel, cls, func)):
        if isinstance(node, ast.Return) and node.value is not None:
            return ast.literal_eval(node.value)
    raise FactError(f"{rel}: {cls}.{func} gibt keinen festen Wert zurück")


def always_raises(rel: str, cls: str, func: str) -> bool:
    fn = _function(rel, cls, func)
    return any(isinstance(n, ast.Raise) for n in fn.body)


def class_with_method(rel: str, method: str) -> str:
    for node in ast.walk(_tree(rel)):
        if isinstance(node, ast.ClassDef) and any(
            isinstance(n, ast.FunctionDef) and n.name == method for n in node.body
        ):
            return node.name
    raise FactError(f"{rel}: keine Klasse mit {method}")


def keyword_in_call(rel: str, first_arg: str, keyword: str):
    for node in ast.walk(_tree(rel)):
        if (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == first_arg):
            for kw in node.keywords:
                if kw.arg == keyword:
                    return ast.literal_eval(kw.value)
    raise FactError(f"{rel}: Aufruf mit {first_arg!r} und {keyword}= fehlt")


def dict_keys_assigned(rel: str, func: str, name: str) -> list[str]:
    keys: list[str] = []
    for node in ast.walk(_function(rel, None, func)):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == name and isinstance(node.value, ast.Dict):
                keys += [ast.literal_eval(k) for k in node.value.keys if k is not None]
            if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                    and target.value.id == name):
                keys.append(ast.literal_eval(target.slice))
    if not keys:
        raise FactError(f"{rel}: {func} baut kein {name}")
    return keys


def source_line(rel: str, pattern: str) -> str:
    for line in _source(rel).splitlines():
        if re.search(pattern, line):
            return line.strip()
    raise FactError(f"{rel}: keine Zeile passt zu {pattern!r}")


def shell_variable(rel: str, name: str) -> str:
    match = re.search(rf"^{name}=\"?([^\"\n]+)\"?$", _source(rel), re.M)
    if not match:
        raise FactError(f"{rel}: Variable {name} fehlt")
    return match.group(1)


def tests_present(names: list[str]) -> dict[str, str | None]:
    found: dict[str, str | None] = dict.fromkeys(names)
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        for name in names:
            if found[name] is None and re.search(rf"^def {name}\(", text, re.M):
                found[name] = str(path.relative_to(ROOT))
    return found


def abnahme(file_name: str) -> dict:
    data = json.loads((ROOT / "docs-site/assets/data/fortschritt.json").read_text(encoding="utf-8"))
    for entry in data.get("abnahmen", []):
        if entry.get("file") == file_name:
            groups = entry["groups"]
            total = {k: sum(g[k] for g in groups.values()) for k in ("richtig", "falsch", "abgelehnt")}
            return {
                "label": entry["label"],
                "bestanden": entry["bestanden"],
                "groups": groups,
                "gesamt": total,
                "templates_sha256_prefix": entry["templates_sha256"][:8],
            }
    raise FactError(f"fortschritt.json: Abnahme {file_name} fehlt")


# ------------------------------------------------------------------ Fakten --
# id: (Quelle für Menschen, Tour-Schritte, die den Wert zeigen, Leser)

RECORDS = "src/dispread/records.py"
VALIDATE = "src/dispread/validate.py"
DOTMATRIX = "src/dispread/ocr/dotmatrix.py"
FONT = "src/dispread/ocr/dotmatrix_font.py"
TEMPLATES = "src/dispread/ocr/dotmatrix_templates.py"

FACTS = {
    "record.fields": (
        f"{RECORDS}:ValueRecord (die neun Pflichtfelder aus Konzept §8)",
        ["erkennung-ausgabe"],
        lambda: annotated_fields(RECORDS, "ValueRecord")[:9],
    ),
    "record.status": (
        f"{RECORDS}:ValueStatus",
        ["erkennung-freigabe", "erkennung-veraltet", "erkennung-ausgabe", "regeln-altwert"],
        lambda: enum_members(RECORDS, "ValueStatus"),
    ),
    "record.suspend_tolerance_ns": (
        f"{RECORDS}:SUSPEND_TOLERANCE_NS",
        ["zeit-versatz"],
        lambda: module_constant(RECORDS, "SUSPEND_TOLERANCE_NS"),
    ),
    "gate.confirm_frames": (
        f"{VALIDATE}:GateConfig.confirm_frames",
        ["erkennung-freigabe", "regeln-spruenge"],
        lambda: field_default(VALIDATE, "GateConfig", "confirm_frames"),
    ),
    "gate.stale_after_ns": (
        f"{VALIDATE}:GateConfig.stale_after_ns",
        ["erkennung-veraltet", "regeln-altwert"],
        lambda: field_default(VALIDATE, "GateConfig", "stale_after_ns"),
    ),
    "gate.evaluate_params": (
        f"{VALIDATE}:ReleaseGate.evaluate",
        ["regeln-referenz", "erkennung-freigabe"],
        lambda: params(VALIDATE, "ReleaseGate", "evaluate"),
    ),
    "reader.read_params": (
        "src/dispread/ocr/__init__.py:ValueReader.read",
        ["regeln-referenz"],
        lambda: params("src/dispread/ocr/__init__.py", "ValueReader", "read"),
    ),
    "track.max_shift": (
        "src/dispread/track.py:TrackConfig.max_shift",
        ["erkennung-nachfuehrung"],
        lambda: field_default("src/dispread/track.py", "TrackConfig", "max_shift"),
    ),
    "track.max_rotation_deg": (
        "src/dispread/track.py:TrackConfig.max_rotation_deg",
        ["erkennung-nachfuehrung"],
        lambda: field_default("src/dispread/track.py", "TrackConfig", "max_rotation_deg"),
    ),
    "ocr.max_saturated": (
        f"{DOTMATRIX}:MAX_SATURATED",
        ["erkennung-format"],
        lambda: module_constant(DOTMATRIX, "MAX_SATURATED"),
    ),
    "ocr.number_pattern": (
        f"{DOTMATRIX}:_NUMBER (Formatregel gsv2as_v1, Zellen 1-7)",
        ["erkennung-raster", "erkennung-format"],
        lambda: module_constant(DOTMATRIX, "_NUMBER"),
    ),
    "ocr.classes": (
        f"{FONT}:CLASSES",
        ["erkennung-zelle", "training-vorlagen"],
        lambda: list(module_constant(FONT, "CLASSES")),
    ),
    "ocr.rom_a00": (
        f"{FONT}:ROM_A00",
        ["erkennung-zelle", "training-lernen"],
        lambda: {k: list(v) for k, v in module_constant(FONT, "ROM_A00").items()},
    ),
    "ocr.rom_tolerance_dots": (
        f"{TEMPLATES}:ROM_TOLERANCE_DOTS",
        ["training-lernen"],
        lambda: module_constant(TEMPLATES, "ROM_TOLERANCE_DOTS"),
    ),
    "ocr.thresholds": (
        f"{TEMPLATES}:compute_thresholds",
        ["training-lernen", "erkennung-zelle"],
        lambda: {
            "d_max": source_line(TEMPLATES, r"^\s*d_max = "),
            "margin_min": source_line(TEMPLATES, r"^\s*margin_min = "),
        },
    ),
    "ocr.confidence_calibrated": (
        "src/dispread/ocr/{dotmatrix,sevenseg,tesseract_cli}.py:declares_confidence_calibrated",
        ["regeln-konfidenz"],
        lambda: {
            rel.rsplit("/", 1)[1]: returns_constant(rel, class_with_method(rel, "declares_confidence_calibrated"),
                                                    "declares_confidence_calibrated")
            for rel in (DOTMATRIX, "src/dispread/ocr/sevenseg.py", "src/dispread/ocr/tesseract_cli.py")
        },
    ),
    "protocol.gsv_ascii_raises": (
        "src/dispread/sink/protocol/gsv_ascii.py:GsvAsciiFormatter.format",
        ["regeln-protokoll", "erkennung-ausgabe"],
        lambda: always_raises("src/dispread/sink/protocol/gsv_ascii.py", "GsvAsciiFormatter", "format"),
    ),
    "protocol.ascii_csv_provisional": (
        "src/dispread/sink/protocol/ascii_csv.py (provisional=)",
        ["regeln-protokoll"],
        lambda: "provisional=True" in _source("src/dispread/sink/protocol/ascii_csv.py"),
    ),
    "harvest.min_step_ratio": (
        "scripts/harvest.py:_MIN_STEP_RATIO",
        ["training-ernte"],
        lambda: module_constant("scripts/harvest.py", "_MIN_STEP_RATIO"),
    ),
    "harvest.hold_s": (
        "scripts/harvest.py:_DEFAULT_HOLD_S",
        ["training-ernte"],
        lambda: module_constant("scripts/harvest.py", "_DEFAULT_HOLD_S"),
    ),
    "setup.stability_s": (
        "scripts/harvest-setup.py assist --stability-s",
        ["bedienung-assistent"],
        lambda: keyword_in_call("scripts/harvest-setup.py", "--stability-s", "default"),
    ),
    "setup.serial": (
        "scripts/harvest-setup.py assist --serial-port/--baudrate",
        ["bedienung-assistent"],
        lambda: {
            "port": keyword_in_call("scripts/harvest-setup.py", "--serial-port", "default"),
            "baudrate": keyword_in_call("scripts/harvest-setup.py", "--baudrate", "default"),
        },
    ),
    "setup.checks": (
        "src/dispread/setup_checks.py:evaluate_setup (checks)",
        ["bedienung-assistent"],
        lambda: dict_keys_assigned("src/dispread/setup_checks.py", _setup_function(), "checks"),
    ),
    "camera.usb_id": (
        "scripts/camera-commissioning.sh:USB_ID",
        ["bedienung-inbetriebnahme"],
        lambda: shell_variable("scripts/camera-commissioning.sh", "USB_ID"),
    ),
    "camera.focus_absolute": (
        "scripts/camera-commissioning.sh:FOCUS_ABSOLUTE_TEST",
        ["bedienung-kamera", "bedienung-inbetriebnahme"],
        lambda: int(shell_variable("scripts/camera-commissioning.sh", "FOCUS_ABSOLUTE_TEST")),
    ),
    "tests.regeln": (
        "tests/ (Tests, die die Regeln erzwingen)",
        ["regeln-altwert", "regeln-referenz", "regeln-spruenge", "regeln-konfidenz"],
        lambda: tests_present([
            "test_stale_darf_keinen_zahlenwert_fuehren",
            "test_nach_verlust_wird_der_wert_veraltet_nicht_weitergefuehrt",
            "test_leser_bekommt_den_referenzwert_nicht_als_parameter",
            "test_referenzwert_kann_die_erkennung_nicht_beeinflussen",
            "test_echte_spruenge_werden_nicht_geglaettet",
            "test_mehrbildbestaetigung_meldet_ihre_zeitspanne",
            "test_declares_confidence_calibrated_ist_false",
        ]),
    ),
    "abnahme.stufe2c": (
        "docs-site/assets/data/fortschritt.json (Abnahme 3, aus den Abnahmedateien)",
        ["training-abnahme", "regeln-grenzen"],
        lambda: abnahme("abnahme-stufe2c-2026-09-30.json"),
    ),
}


def _setup_function() -> str:
    for node in _tree("src/dispread/setup_checks.py").body:
        if isinstance(node, ast.FunctionDef):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Assign) and isinstance(sub.targets[0], ast.Name)
                        and sub.targets[0].id == "checks" and isinstance(sub.value, ast.Dict)):
                    return node.name
    raise FactError("src/dispread/setup_checks.py: keine Funktion baut checks")


# ------------------------------------------------------------------- Ablauf --

def collect() -> dict:
    facts = {}
    for fact_id, (source, used_by, read) in FACTS.items():
        facts[fact_id] = {"value": read(), "source": source, "used_by": used_by}
    return {"schema": SCHEMA, "facts": facts}


def render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def tour_step_ids() -> set[str]:
    return set(re.findall(r"^###? .*\{#([a-z0-9-]+)\}", TOUR_PAGE.read_text(encoding="utf-8"), re.M))


def differences(current: dict, stored: dict) -> list[str]:
    out = []
    old, new = stored.get("facts", {}), current["facts"]
    for fact_id in sorted(set(old) | set(new)):
        if fact_id not in new:
            out.append(f"{fact_id}: nicht mehr erfasst (aus tour-facts.py entfernt)")
        elif fact_id not in old:
            out.append(f"{fact_id}: neu, noch nicht übernommen")
        elif old[fact_id] != new[fact_id]:
            steps = ", ".join(new[fact_id]["used_by"])
            if old[fact_id]["value"] != new[fact_id]["value"]:
                out.append(
                    f"{fact_id}: {json.dumps(old[fact_id]['value'], ensure_ascii=False)}"
                    f" -> {json.dumps(new[fact_id]['value'], ensure_ascii=False)}"
                    f"\n    Quelle: {new[fact_id]['source']}\n    Tour-Schritte prüfen: {steps}"
                )
            else:
                out.append(f"{fact_id}: Quelle oder Verwendung geändert")
    if stored.get("schema") != current["schema"]:
        out.append(f"schema: {stored.get('schema')} -> {current['schema']}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="tour-facts.json neu schreiben")
    mode.add_argument("--check", action="store_true", help="Code gegen tour-facts.json prüfen")
    args = parser.parse_args(argv)
    try:
        current = collect()
    except FactError as error:
        print(f"tour-facts: {error}. Die Tour zeigt diesen Wert; Fundstelle in "
              "scripts/tour-facts.py anpassen und betroffene Schritte prüfen.", file=sys.stderr)
        return 1
    unknown = {step for fact in current["facts"].values() for step in fact["used_by"]} - tour_step_ids()
    if unknown:
        print(f"tour-facts: unbekannte Tour-Schritte in used_by: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 1
    if args.write:
        OUT.write_text(render(current), encoding="utf-8")
        print(f"geschrieben: {OUT.relative_to(ROOT)} ({len(current['facts'])} Fakten)")
        return 0
    stored = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    diff = differences(current, stored)
    if diff:
        print("tour-facts: Der Code weicht von dem ab, was die Projekt-Tour zeigt:", file=sys.stderr)
        for line in diff:
            print(f"  - {line}", file=sys.stderr)
        print("Schritte in docs/uebersicht/projekt-tour.md und docs-site/assets/tour*.js "
              "prüfen, dann ./scripts/tour-facts.py --write.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
