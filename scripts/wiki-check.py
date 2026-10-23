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


def check_glossary(md_text: str) -> list[str]:
    """Prüft Kurzdefinitionen, feste Metazeilen und eindeutige Begriffsnamen."""
    errors = []
    seen: set[str] = set()
    headers = list(re.finditer(r"^(#{2,3}) ([^\n]+)$", md_text, re.MULTILINE))
    meta_pattern = re.compile(
        r"^\*Weg:\* ([^·\n]+?)"
        r"(?: · \*Auch:\* (\S(?:[^·\n]*\S)?))? · \*Quelle:\* ([^·\n]+)$"
    )
    for index, header in enumerate(headers):
        if header[1] != "###":
            continue
        term = re.sub(r"\s*\{#[^}]+\}\s*$", "", header[2]).replace("`", "").strip()
        number = md_text.count("\n", 0, header.start()) + 1
        end = headers[index + 1].start() if index + 1 < len(headers) else len(md_text)
        paragraphs = list(re.finditer(r"\S[^\n]*(?:\n(?!\s*\n)[^\n]+)*", md_text[header.end():end]))
        prefix = f"glossar.md:{number}: {term}: "

        def paragraph_line(paragraph: re.Match[str]) -> int:
            return md_text.count("\n", 0, header.end() + paragraph.start()) + 1

        first = paragraphs[0] if paragraphs else None
        missing_short = first is None or first[0].startswith("*Weg:*")
        if missing_short:
            errors.append(prefix + "Kurzdefinition fehlt")
        else:
            short = re.sub(r"\s+", " ", first[0])
            if len(short) > 280:
                errors.append(f"glossar.md:{paragraph_line(first)}: {term}: Kurzdefinition > 280 Zeichen ({len(short)})")
        meta = first if missing_short else (paragraphs[1] if len(paragraphs) > 1 else None)
        match = meta_pattern.fullmatch(meta[0]) if meta else None
        aliases = []
        if not match:
            line = paragraph_line(meta) if meta else number
            errors.append(f"glossar.md:{line}: {term}: Metazeile fehlt / falsche Form")
        else:
            line = paragraph_line(meta)
            if match[1] not in ("Bedienen", "Konfigurieren", "Entwickeln"):
                errors.append(f"glossar.md:{line}: {term}: Weg unbekannt: {match[1]}")
            source = re.fullmatch(r"\[[^\]]+\]\(([^\s)]+)\)", match[3])
            target = source[1].split("#")[0] if source else ""
            if not target.endswith(".md") or "/src/" in target or re.match(r"\w+:", target):
                errors.append(f"glossar.md:{line}: {term}: Quelle ohne Link auf eine Wiki-Seite")
            aliases = [alias.strip() for alias in (match[2] or "").split(",") if alias.strip()]
        for name in [term, *aliases]:
            key = name.casefold()
            if key in seen:
                errors.append(prefix + f"Begriff oder Synonym doppelt: {name}")
            seen.add(key)
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
        if name == "docs/anleitung/glossar.md":
            errors.extend(check_glossary(text))
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
