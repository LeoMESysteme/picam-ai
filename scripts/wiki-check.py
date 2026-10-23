#!/usr/bin/env python3
"""Prüft die Weg-Angaben der Wiki-Quellen vor dem Doku-Build."""

from __future__ import annotations

import argparse
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEGE = ("bedienen", "konfigurieren", "entwickeln", "projekt")


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
        errors.extend(check_front_matter(path.read_text(encoding="utf-8"), path.relative_to(ROOT).as_posix()))
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
