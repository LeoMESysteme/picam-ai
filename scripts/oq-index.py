#!/usr/bin/env python3
"""Erzeuge die OQ-Uebersicht aus den OQ-Eintraegen und der aktiven TODO-Reihenfolge."""

from __future__ import annotations

import argparse
import re
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).parents[1]
DEFAULT_PATH = ROOT / "docs/open-questions.md"
DEFAULT_TODO = ROOT / "TODO.md"
START = "<!-- OQ-INDEX:START — erzeugt von scripts/oq-index.py, nicht von Hand bearbeiten -->"
END = "<!-- OQ-INDEX:END -->"

_HEADING = re.compile(r"^## (OQ-\d+) — (.+?)(?: \{ #oq-\d+ \})?$", re.M)
_ALIAS = re.compile(r'(?m)^<span id="oq-\d+"></span>\n\n(?=## OQ-)')
_STATUS = re.compile(r"\*\*Status:\*\*\s*(.*)$")
_OQ = re.compile(r"\bOQ-\d+\b")


def status_label(raw: str, number: str) -> tuple[str, str]:
    """Gib (sichtbarer Status, Filterkategorie) ohne Datum zurueck."""
    value = raw.replace("*", "").strip().casefold()
    for prefix, label, category in (
        ("teilweise geklärt", "teilweise geklärt", "partial"),
        ("weitgehend geklärt", "weitgehend geklärt", "partial"),
        ("in arbeit", "in Arbeit", "progress"),
        ("beantwortet", "beantwortet", "resolved"),
        ("geklärt", "geklärt", "resolved"),
        ("verworfen", "verworfen", "discarded"),
        ("offen", "offen", "open"),
    ):
        if value == prefix or (value.startswith(prefix) and value[len(prefix)] in " (.,—-:;"):
            return label, category
    raise ValueError(f"{number}: unbekannter oder fehlender Status: {raw!r}")


def parse_entries(source: str) -> list[tuple[str, str, str, str]]:
    """Lies (Nummer, Titel, Statuslabel, Kategorie) aus OQ-Abschnitten."""
    entries: list[tuple[str, str, str, str]] = []
    headings = list(_HEADING.finditer(source))
    for index, heading in enumerate(headings):
        body = source[heading.end():headings[index + 1].start() if index + 1 < len(headings) else len(source)]
        status = next((_STATUS.search(line) for line in body.splitlines() if _STATUS.search(line)), None)
        label, category = status_label(status.group(1) if status else "", heading.group(1))
        entries.append((heading.group(1), heading.group(2), label, category))
    if not entries:
        raise ValueError("Keine OQ-Abschnitte gefunden")
    if len({number for number, *_ in entries}) != len(entries):
        raise ValueError("OQ-Nummern sind nicht eindeutig")
    return entries


def focus_from_todo(source: str) -> list[str]:
    """OQ im aktuellen Blocker und den unerledigten Aufgaben, in Textreihenfolge."""
    focus: list[str] = []
    section = ""
    active_task = True
    found_tasks = False
    for line in source.splitlines():
        if line.startswith("## "):
            heading = line[3:].casefold()
            section = "blocker" if heading.startswith("aktueller blocker") else (
                "tasks" if heading.startswith("die aufgaben, in reihenfolge") else ""
            )
            found_tasks |= section == "tasks"
            active_task = True
        elif line.startswith("### ") and section == "tasks":
            active_task = "erledigt" not in line.casefold()
        if section == "blocker" or (section == "tasks" and active_task):
            for number in _OQ.findall(line):
                if number not in focus:
                    focus.append(number)
    if not found_tasks:
        raise ValueError("TODO.md: Abschnitt 'Die Aufgaben, in Reihenfolge' fehlt")
    return focus


def render_block(entries: list[tuple[str, str, str, str]], focus: list[str]) -> str:
    by_number = {entry[0]: entry for entry in entries}
    missing = [number for number in focus if number not in by_number]
    if missing:
        raise ValueError(f"TODO.md verweist auf OQ ohne Eintrag: {', '.join(missing)}")
    active_focus = [number for number in focus if number in by_number and by_number[number][3] not in {"resolved", "discarded"}]
    remaining = [entry for entry in entries if entry[0] not in active_focus]
    remaining.sort(key=lambda entry: (entry[3] in {"resolved", "discarded"}, int(entry[0][3:])))
    ordered = [by_number[number] for number in active_focus] + remaining
    lines = [START, "", "| OQ | Fokus | Status | Titel |", "| --- | --- | --- | --- |"]
    for number, title, label, _category in ordered:
        safe_title = escape(title.replace("|", "/")).replace("[", "\\[").replace("]", "\\]")
        lines.append(f"| [{number}](#oq-{number[3:]}) | {'Jetzt' if number in active_focus else '—'} | {label} | {safe_title} |")
    lines.extend(["", END])
    return "\n".join(lines)


def update_text(source: str, todo: str) -> str:
    start = source.find(START)
    end = source.find(END)
    if start < 0 or end < start:
        raise ValueError("OQ-INDEX-Marker fehlen oder stehen in falscher Reihenfolge")
    body = source[end + len(END):]
    body = _ALIAS.sub("", body)
    body = _HEADING.sub(
        lambda match: f'<span id="oq-{match.group(1)[3:]}"></span>\n\n## {match.group(1)} — {match.group(2)}',
        body,
    )
    entries = parse_entries(body)
    block = render_block(entries, focus_from_todo(todo))
    return source[:start] + block + body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="nur pruefen, nicht schreiben")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--todo", type=Path, default=DEFAULT_TODO)
    args = parser.parse_args(argv)
    try:
        source = args.path.read_text(encoding="utf-8")
        updated = update_text(source, args.todo.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    if updated == source:
        return 0
    if args.check:
        print(f"{args.path}: OQ-Übersicht veraltet", file=sys.stderr)
        return 1
    args.path.write_text(updated, encoding="utf-8")
    print(f"{args.path}: OQ-Übersicht aktualisiert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
