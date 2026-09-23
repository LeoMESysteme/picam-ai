#!/usr/bin/env python3
"""Prüft einen Datensatz-Export (`dataset.export`) lokal, optional gegen den
echten Experiment-Loader aus Branch `codex/automatic-seven-segment` (6a18bdf).

Ohne --experiment-root: nur Schema-/Pfad-/Hashprüfung dieses Skripts. Die
externe Kompatibilität wird ausdrücklich als NICHT GEPRÜFT gemeldet - ein
fehlender Experimentstand ist kein Bestehen.

Mit --experiment-root: startet dessen eigene `.venv/bin/python` in einem
separaten Prozess (argumentgetrennter `subprocess.run`, kein Shell-String).
Dieser Prozess importiert ausschließlich `load_manifest`, keine Modelle/den
Runner - reiner lokaler Prüf-/Kompatibilitätsbefehl, kein Trainingslauf.

Aufruf:
    ./.venv/bin/python scripts/check-dataset-export.py --manifest PFAD
    ./.venv/bin/python scripts/check-dataset-export.py --manifest PFAD \
        --experiment-root /pfad/zum/experiment-worktree
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:[.][0-9]+)?|[.][0-9]+)\Z")

#: Vom lokalen Check akzeptierte manifest.json-Schemaversionen. Version 1
#: (vor label_origin) bleibt zugelassen: dieses Skript prueft nur Struktur/
#: Pfade/Hashes, nichts hier liest label_origin, und bereits vorhandene
#: Alt-Exporte unter var/ muessen weiter lokal pruefbar bleiben (Konzept:
#: alte Lesepfade nicht kaputtmachen). Version 2 (2026-09-23) fuegt je Probe
#: label_origin/label_origin_detail hinzu - siehe
#: dispread.workbench.datasets.EXPORT_SCHEMA_VERSION. Der externe
#: Experiment-Loader (codex/automatic-seven-segment, siehe check_external)
#: akzeptiert bisher NUR Version 1 - ein Export mit Version 2 besteht die
#: lokale Pruefung hier, aber (noch) nicht check_external.
_ACCEPTED_SCHEMA_VERSIONS = (1, 2)

_LOADER_PROBE = (
    "import sys, json\n"
    "sys.path.insert(0, sys.argv[2])\n"
    "from dispread.experimental.evaluation import load_manifest\n"
    "from pathlib import Path\n"
    "try:\n"
    "    load_manifest(Path(sys.argv[1]))\n"
    "except Exception as error:\n"
    "    print('FEHLER: ' + str(error))\n"
    "    sys.exit(1)\n"
    "print('OK')\n"
)


def _normalise(text: str) -> str:
    return text.strip().replace(",", ".")


def check_local(manifest_path: Path) -> list[str]:
    """Schema/Pfade/Hashes ohne den externen Loader prüfen.

    Liefert eine Liste gefundener Probleme; leer heißt bestanden. Bewusst
    keine Kopie der Loader-Logik selbst - nur genug, um einen kaputten Export
    zu erkennen, bevor überhaupt ein zweiter Prozess gestartet wird.
    """
    problems: list[str] = []
    manifest_path = manifest_path.resolve()
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        return [f"Manifest nicht lesbar: {error}"]
    if manifest.get("schema_version") not in _ACCEPTED_SCHEMA_VERSIONS:
        problems.append(
            f"schema_version {manifest.get('schema_version')!r} nicht unterstuetzt "
            f"(akzeptiert: {_ACCEPTED_SCHEMA_VERSIONS})"
        )
    ids: set[str] = set()
    for sample in manifest.get("samples", []):
        sample_id = sample.get("id")
        if sample_id in ids:
            problems.append(f"doppelte id: {sample_id}")
        ids.add(sample_id)
        path = sample.get("path")
        if not isinstance(path, str) or path.startswith("/") or ".." in Path(path).parts:
            problems.append(f"unzulässiger Pfad: {path!r}")
            continue
        resolved = (manifest_path.parent / path).resolve()
        if not resolved.is_relative_to(manifest_path.parent):
            problems.append(f"Pfad verlässt das Exportverzeichnis: {path!r}")
            continue
        if not resolved.is_file():
            problems.append(f"Bilddatei fehlt: {path!r}")
            continue
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if digest != sample.get("sha256"):
            problems.append(f"Bildhash weicht ab: {sample_id}")
        text = sample.get("expected_text")
        if text is not None and not _NUMBER.fullmatch(_normalise(text)):
            problems.append(f"ungültiger Zahlentext: {sample_id}")
        box = sample.get("bbox")
        if (
            not isinstance(box, list)
            or len(box) != 4
            or not all(isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v) for v in box)
            or min(box[:2]) < 0
            or min(box[2:]) <= 0
        ):
            problems.append(f"ungültige Zielbox: {sample_id}")
    return problems


def check_external(manifest_path: Path, experiment_root: Path) -> list[str]:
    python = experiment_root / ".venv" / "bin" / "python"
    if not python.is_file():
        return [f"kein venv-Interpreter unter {python}"]
    experiment_src = experiment_root / "src"
    result = subprocess.run(
        [str(python), "-c", _LOADER_PROBE, str(manifest_path), str(experiment_src)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        return [result.stdout.strip() or result.stderr.strip() or "externer Loader lehnte den Export ab"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", required=True, type=Path, help="Pfad zu manifest.json eines Exports")
    parser.add_argument(
        "--experiment-root",
        type=Path,
        default=None,
        help="Worktree von codex/automatic-seven-segment (6a18bdf) für die echte Loaderprüfung",
    )
    args = parser.parse_args(argv)

    problems = check_local(args.manifest)
    if problems:
        for problem in problems:
            print(f"FEHLER: {problem}", file=sys.stderr)
        return 1
    print("Lokale Prüfung (Schema/Pfade/Hashes): bestanden")

    if args.experiment_root is None:
        print("Externe Kompatibilität mit dem Experiment-Loader: NICHT GEPRÜFT (kein --experiment-root)")
        return 0

    if not args.experiment_root.is_dir():
        print(f"FEHLER: --experiment-root existiert nicht: {args.experiment_root}", file=sys.stderr)
        return 1

    external_problems = check_external(args.manifest, args.experiment_root)
    if external_problems:
        for problem in external_problems:
            print(f"FEHLER (externer Loader): {problem}", file=sys.stderr)
        return 1
    print("Externe Kompatibilität mit dem Experiment-Loader: bestanden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
