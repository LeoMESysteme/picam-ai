#!/usr/bin/env python3
"""Uebersichtstabelle der offenen Punkte in docs/open-questions.md erzeugen.

Die Datei ist mit >100 KB zu gross, um sie zum Sitzungsbeginn ganz zu lesen.
Oben steht deshalb eine Tabelle (Nummer, Status, Titel) zwischen den Markern
`<!-- OQ-INDEX:START -->` und `<!-- OQ-INDEX:END -->`; einzelne Eintraege
oeffnet man gezielt per `grep -n '^## OQ-22' docs/open-questions.md`.

Die Tabelle wird aus den `## OQ-nn — Titel`-Ueberschriften und der jeweils
ersten `**Status:**`-Zeile erzeugt, nie von Hand gepflegt - sonst laeuft sie
auseinander. `tests/test_oq_index.py` schlaegt fehl, wenn sie veraltet ist.

Aufruf:

    ./.venv/bin/python scripts/oq-index.py          # Tabelle neu schreiben
    ./.venv/bin/python scripts/oq-index.py --check  # Exit 1, wenn veraltet
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_PATH = Path(__file__).parents[1] / "docs" / "open-questions.md"

START = "<!-- OQ-INDEX:START — erzeugt von scripts/oq-index.py, nicht von Hand bearbeiten -->"
END = "<!-- OQ-INDEX:END -->"

_HEADING_RE = re.compile(r"^## (OQ-\d+) — (.+?)\s*$")
_STATUS_RE = re.compile(r"\*\*Status:\*\*\s*(.*)$")
# Der Status ist das erste Satzglied: alles vor " · ", " — ", " (", "," oder
# einem Satzpunkt. Datumsangaben bleiben erhalten ("2026-09-22" hat keinen
# Punkt), Begruendungen fallen weg - die stehen im Eintrag selbst.
_STATUS_CUT_RE = re.compile(r" · | — | \(|,|\.(?:\s|$)")


def parse_entries(text: str) -> list[tuple[str, str, str]]:
    """(Nummer, Status, Titel) je OQ-Abschnitt, in Dateireihenfolge."""
    entries: list[tuple[str, str, str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            current = [heading.group(1), "", heading.group(2)]
            entries.append(current)  # type: ignore[arg-type]
            continue
        if current is not None and not current[1]:
            status = _STATUS_RE.search(line)
            if status:
                raw = status.group(1).replace("*", "").strip()
                current[1] = _STATUS_CUT_RE.split(raw, maxsplit=1)[0].strip() or "?"
    return [(n, s or "?", t) for n, s, t in entries]


def render_block(entries: list[tuple[str, str, str]]) -> str:
    rows = [
        START,
        "",
        "| OQ | Status | Titel |",
        "| --- | --- | --- |",
    ]
    for number, status, title in entries:
        rows.append(f"| {number} | {status} | {title.replace('|', '/')} |")
    rows += ["", END]
    return "\n".join(rows)


def update_text(text: str) -> str:
    """Text mit neu erzeugter Tabelle. Wirft, wenn die Marker fehlen."""
    start = text.find(START)
    end = text.find(END)
    if start < 0 or end < start:
        raise ValueError(f"Marker fehlen: {START!r} … {END!r}")
    block = render_block(parse_entries(text[end:]))
    return text[:start] + block + text[end + len(END):]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OQ-Uebersichtstabelle erzeugen oder pruefen.")
    parser.add_argument("--check", action="store_true", help="nur pruefen, Exit 1 wenn veraltet")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)

    text = args.path.read_text(encoding="utf-8")
    updated = update_text(text)
    if updated == text:
        return 0
    if args.check:
        print(f"{args.path}: OQ-Tabelle veraltet - scripts/oq-index.py ausfuehren", file=sys.stderr)
        return 1
    args.path.write_text(updated, encoding="utf-8")
    print(f"{args.path}: OQ-Tabelle aktualisiert ({len(parse_entries(updated))} Eintraege)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
