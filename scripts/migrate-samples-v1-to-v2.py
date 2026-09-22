#!/usr/bin/env python3
"""Datensatzproben von ``schema_version`` 1 auf 2 heben (Feld ``label_origin``).

Hintergrund: Version 2 fuehrt das Herkunftsmerkmal ``label_origin`` als
Pflichtfeld ein (OQ-38 Punkt 6), damit von Hand und automatisch gelabelte
Proben unterscheidbar bleiben. ``DatasetStore`` lehnt seither jede Probe mit
``schema_version == 1`` hart ab, statt stillschweigend eine Herkunft zu
unterstellen.

Was diese Migration eintraegt, ist keine Annahme: **alle** Bestandsproben
entstanden, bevor es ueberhaupt einen automatischen Labelpfad gab. Sie sind
ausnahmslos von Hand gelabelt, also ``label_origin="manual"`` mit
``label_origin_detail=None``.

Das Skript aendert echte Messdaten unter ``var/``. Deshalb:

* **Vorgabe ist ein Trockenlauf.** Geschrieben wird nur mit ``--apply``.
* Vor der ersten Schreiboperation wird jede betroffene Datei in ein
  Sicherungsverzeichnis kopiert; ohne vollstaendige Sicherung wird nichts
  geschrieben.
* Geschrieben wird atomar (Temporaerdatei + ``os.replace``), damit ein
  Abbruch keine halbe Datei hinterlaesst.
* Proben, die bereits auf Version 2 stehen, werden uebersprungen, nicht
  erneut angefasst. Der Lauf ist damit wiederholbar.

Aufruf:

    ./.venv/bin/python scripts/migrate-samples-v1-to-v2.py            # Trockenlauf
    ./.venv/bin/python scripts/migrate-samples-v1-to-v2.py --apply    # schreibt
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

FROM_VERSION = 1
TO_VERSION = 2


def find_samples(root: Path) -> list[Path]:
    return sorted((root / "samples").glob("*/sample.json"))


def classify(paths: list[Path]) -> tuple[list[Path], list[Path], list[tuple[Path, str]]]:
    """In migrierbar, schon aktuell und unklar aufteilen."""
    todo: list[Path] = []
    current: list[Path] = []
    problems: list[tuple[Path, str]] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append((path, f"nicht lesbar: {exc}"))
            continue
        version = data.get("schema_version")
        if version == TO_VERSION:
            current.append(path)
        elif version == FROM_VERSION:
            if "label_origin" in data:
                # Version 1 kennt das Feld nicht. Steht es trotzdem drin, ist
                # die Datei von Hand bearbeitet worden - dann raten wir nicht.
                problems.append((path, "schema_version 1, aber label_origin bereits vorhanden"))
            else:
                todo.append(path)
        else:
            problems.append((path, f"unerwartete schema_version {version!r}"))
    return todo, current, problems


def migrate(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = TO_VERSION
    data["label_origin"] = "manual"
    data["label_origin_detail"] = None
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path("var/workbench/datasets"))
    parser.add_argument("--apply", action="store_true", help="tatsaechlich schreiben (sonst nur Trockenlauf)")
    parser.add_argument("--backup-dir", type=Path, default=None)
    args = parser.parse_args()

    if not args.root.is_dir():
        print(f"Kein Datensatzverzeichnis unter {args.root}", file=sys.stderr)
        return 2

    paths = find_samples(args.root)
    todo, current, problems = classify(paths)

    print(f"Proben gesamt:        {len(paths)}")
    print(f"  bereits Version {TO_VERSION}:  {len(current)}")
    print(f"  zu migrieren:       {len(todo)}")
    print(f"  unklar:             {len(problems)}")
    for path, why in problems:
        print(f"    {path}: {why}")

    if problems:
        print("\nAbbruch: unklare Proben. Es wird nichts geschrieben, solange auch nur")
        print("eine Datei nicht eindeutig zuzuordnen ist - Raten ist hier der Fehler,")
        print("den dieses Projekt nicht haben will.", file=sys.stderr)
        return 1

    if not todo:
        print("\nNichts zu tun.")
        return 0

    if not args.apply:
        print("\nTrockenlauf. Mit --apply werden diese Proben auf")
        print(f'  schema_version={TO_VERSION}, label_origin="manual", label_origin_detail=None')
        print("gehoben. Vorher wird jede Datei gesichert.")
        return 0

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = args.backup_dir or Path(f"var/backup-samples-schema1-{stamp}")
    backup.mkdir(parents=True, exist_ok=False)
    for path in todo:
        target = backup / path.parent.name
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target / path.name)
    copied = len(list(backup.glob("*/sample.json")))
    if copied != len(todo):
        print(f"Sicherung unvollstaendig ({copied} von {len(todo)}) - es wird nichts geschrieben.", file=sys.stderr)
        return 1
    print(f"\nSicherung: {backup} ({copied} Dateien)")

    for path in todo:
        migrate(path)
    print(f"Migriert: {len(todo)} Proben auf schema_version={TO_VERSION}.")
    print(f"Rueckweg: Dateien aus {backup} zurueckkopieren.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
