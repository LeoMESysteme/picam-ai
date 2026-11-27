#!/usr/bin/env python3
"""Erzeugt sensors/index.json im Zweig sensor-katalog aus den Paketordnern.

Aufruf (aus dem master-Checkout, Katalogzweig woanders ausgecheckt):

    PYTHONPATH=src python3 scripts/sensor-catalog-index.py --sensors KATALOG/sensors

Jedes Paket wird mit dem Ladecode der Anwendung geprüft (Vorlagen-Prüfsumme eingeschlossen). `submitted` und
`checks` bleiben für unveränderte Versionen erhalten; `generated` ändert sich nur, wenn sich der Inhalt ändert,
damit ein erneuter Lauf keinen leeren Commit erzeugt. Pakete im Zustand draft kommen nicht in den Index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from dispread.sensors import load_definition, templates  # noqa: E402
from dispread.sensors.catalog import BUNDLE_FILES, preview_example, validate_index  # noqa: E402

_EXAMPLE = re.compile(r'^Beispiel:\s*\|(.{0,16})\|\s*$', re.MULTILINE)


def _example(directory: Path, definition) -> str:
    """Gespeichertes Beispiel aus der README, sonst Vorschau aus den Rollen der Anzeige."""
    readme = directory / 'README.md'
    if readme.is_file():
        match = _EXAMPLE.search(readme.read_text(encoding='utf-8'))
        if match:
            return match.group(1)
    return preview_example(definition)


def build_entries(sensors: Path, previous: dict, now: str) -> list[dict]:
    old = {item['id']: item for item in previous.get('sensors', ())}
    entries = []
    for directory in sorted(path for path in sensors.iterdir() if path.is_dir() and not path.name.startswith('.')):
        definition = load_definition(directory)
        templates(definition)
        if definition.status == 'draft':
            continue
        files = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                 for name in BUNDLE_FILES if (directory / name).is_file()}
        before = old.get(definition.id)
        same = before is not None and before['version'] == definition.version and before['files'] == files
        entries.append({
            'id': definition.id, 'version': definition.version, 'status': definition.status,
            'display_name': definition.display_name, 'manufacturer': definition.manufacturer,
            'aliases': list(definition.aliases), 'unit': definition.unit,
            'family': definition.display.family, 'polarity': definition.display.polarity,
            'connection': definition.connection,
            'example': _example(directory, definition), 'files': files,
            'submitted': before['submitted'] if same else now,
            'checks': before['checks'] if same else {'runs': 0},
        })
    return entries


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--sensors', type=Path, required=True, help='Ordner sensors/ des Katalogzweigs')
    args = parser.parse_args(argv)
    target = args.sensors / 'index.json'
    previous = {}
    if target.is_file():
        try:
            previous = validate_index(json.loads(target.read_text(encoding='utf-8')))
        except ValueError:
            previous = {}  # kaputter alter Index wird neu erzeugt
    now = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    entries = build_entries(args.sensors, previous, now)
    generated = previous['generated'] if previous.get('sensors') == entries else now
    index = validate_index({'schema': 1, 'generated': generated, 'sensors': entries})
    text = json.dumps(index, ensure_ascii=False, indent=2) + '\n'
    if not target.is_file() or target.read_text(encoding='utf-8') != text:
        target.write_text(text, encoding='utf-8')
    print(f'{len(entries)} Sensoren im Index')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
