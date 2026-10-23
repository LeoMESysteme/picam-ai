#!/usr/bin/env python3
"""Prüft Weg-Angaben und Seitenmuster der Wiki-Quellen vor dem Doku-Build."""

from __future__ import annotations

import argparse
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEGE = ("bedienen", "konfigurieren", "entwickeln", "projekt")
PATTERNS = {
    "wiki-setting": ("Einstellung", ("Wozu", "Im Hintergrund", "Standard", "Ändern?", "Quelle")),
    "wiki-seam": ("Trennstelle", ("Vertrag", "Darf geändert werden", "Bleibt unverändert", "Tests")),
}


def check_front_matter(md_text: str, path: str) -> list[str]:
    """Meldet unbekannte Wege im einfachen Front-Matter-Block am Dateianfang."""
    lines = md_text.splitlines()
    if not lines or lines[0] != "---":
        return []
    try:
        end = lines.index("---", 1)
    except ValueError:
        return []

    errors = []
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator and key.strip() == "weg":
            value = value.strip()
            if value not in WEGE:
                errors.append(f'{path}: weg "{value}" unbekannt (erlaubt: {", ".join(WEGE)})')
    return errors


def check_patterns(md_text: str, path: str) -> list[str]:
    """Prüft die erste Tabelle jeder Musterhülle; Codebeispiele bleiben außen vor."""
    lines = md_text.splitlines()
    fence = None
    for index, line in enumerate(lines):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence is not None:
            lines[index] = ""
            if re.fullmatch(rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}\s*", line):
                fence = None
        elif marker:
            fence = marker[1]
            lines[index] = ""

    text = "\n".join(lines)
    errors = []
    for block in re.finditer(r'^[ \t]*<div class="(wiki-setting|wiki-seam)"[^>]*>', text, re.MULTILINE):
        kind = block[1]
        header, required = PATTERNS[kind]
        start = text.count("\n", 0, block.start()) + 1
        prefix = f"{path}:{start}: {kind}"
        body = text[block.end():]
        next_div = re.search(r"^[ \t]*<div\b", body, re.MULTILINE)
        if next_div:
            body = body[:next_div.start()]
        table = []
        body_start = text.count("\n", 0, block.end()) + 1
        table_end = 0
        for offset, line in enumerate(body.splitlines(keepends=True)):
            if line.strip().startswith("|"):
                cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
                table.append((body_start + offset, cells))
            elif table or "</div>" in line:
                break
            table_end += len(line)

        if "</div>" not in body[table_end:]:
            errors.append(f"{prefix} ohne schließendes </div>")

        if not table or table[0][1][0] != header:
            errors.append(f'{prefix} Kopfzeile muss mit "{header}" beginnen')
        rows = table[2:]
        names = [cells[0] for _, cells in rows]
        for name in required:
            if name not in names:
                errors.append(f'{prefix} fehlt Zeile "{name}"')
        if all(name in names for name in required) and names != list(required):
            errors.append(f'{prefix} Zeilen müssen in der Reihenfolge {", ".join(required)} stehen')
        for number, cells in table:
            if len(cells) != 2:
                errors.append(f"{path}:{number}: {kind} Tabelle muss zweispaltig sein")
            if kind == "wiki-setting" and cells[0] == "Ändern?":
                if len(cells) < 2 or not re.match(r"^\*\*(Nein|Nur wenn|Ja)\*\*", cells[1]):
                    errors.append(
                        f'{path}:{number}: {kind} Zeile "Ändern?" muss mit '
                        "**Nein**, **Nur wenn** oder **Ja** beginnen"
                    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True, help="Wiki-Quellen prüfen, ohne sie zu ändern")
    parser.parse_args()

    build_script = (ROOT / "scripts/docs-site.sh").read_text(encoding="utf-8")
    root_docs = re.search(r"^ROOT_DOCS=\(([^)]*)\)", build_script, re.MULTILINE)
    if root_docs is None:
        print("scripts/docs-site.sh: ROOT_DOCS fehlt", file=sys.stderr)
        return 1
    paths = sorted((ROOT / "docs").rglob("*.md"))
    paths += [ROOT / name for name in dict.fromkeys(["README.md", *shlex.split(root_docs[1])])]
    errors = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(ROOT).as_posix()
        errors.extend(check_front_matter(text, name))
        errors.extend(check_patterns(text, name))
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
