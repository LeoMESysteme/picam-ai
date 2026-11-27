#!/usr/bin/env python3
"""Schreibt die CI-Zusammenfassung (Markdown) fuer $GITHUB_STEP_SUMMARY.

Quellen: Log von scripts/ci.py (Schrittergebnisse, FEHLER-Bloecke mit Katalogverweis,
Reproduktionsbefehl), JUnit-XML in reports/ (rote Tests mit Kurztraceback),
reports/perf-summary.md (Perf-Gate). Nur Standardbibliothek. Gibt nichts Geheimes aus:
gitleaks laeuft in ci.py mit --redact, hier wird nur dessen Ausgabe weitergereicht.

Aufruf: ci-summary.py --title "T2 pytest" --stage t2 --repro "scripts/ci.py t2" --log reports/ci.log
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_FAILS = 15
MAX_TRACE_LINES = 12
MAX_TRACE_CHARS = 1800


def parse_log(path: Path) -> tuple[list[str], list[str], str]:
    """Liefert (Ergebniszeilen, FEHLER-Bloecke, Reproduktionsbefehl) aus dem ci.py-Log."""
    if not path or not path.is_file():
        return [], [], ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    results: list[str] = []
    blocks: list[str] = []
    repro = ""
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("=== Zusammenfassung ==="):
            i += 1
            while i < len(lines) and lines[i].strip():
                results.append(lines[i].rstrip())
                i += 1
            continue
        if ln.startswith("FEHLER "):
            blk = [ln]
            i += 1
            while i < len(lines) and lines[i].strip():
                blk.append(lines[i].rstrip())
                i += 1
            blocks.append("\n".join(blk))
            continue
        if ln.startswith("Zum lokalen Nachstellen:"):
            repro = ln.split(":", 1)[1].strip()
        i += 1
    return results, blocks, repro


def junit_failures(reports: Path) -> tuple[int, int, list[str]]:
    """(Tests gesamt, rote Tests, Detailtexte) ueber alle reports/junit-*.xml."""
    total = failed = 0
    details: list[str] = []
    for xml in sorted(reports.glob("junit-*.xml")):
        try:
            root = ET.parse(xml).getroot()
        except ET.ParseError:
            details.append(f"{xml.name}: nicht lesbar (Lauf abgebrochen?)")
            continue
        for tc in root.iter("testcase"):
            total += 1
            bad = tc.find("failure")
            if bad is None:
                bad = tc.find("error")
            if bad is None:
                continue
            failed += 1
            if len(details) >= MAX_FAILS:
                continue
            cls = (tc.get("classname") or "").replace(".", "/")
            node = f"{cls}.py::{tc.get('name')}" if cls else tc.get("name", "?")
            text = (bad.text or bad.get("message") or "").strip().splitlines()
            trace = "\n".join(text[-MAX_TRACE_LINES:])[-MAX_TRACE_CHARS:]
            details.append(f"{node}  ({xml.name})\n{trace}\n-> nachstellen: pytest {node} -x")
    return total, failed, details


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--title", required=True)
    ap.add_argument("--stage", required=True, help="t1|t2|t3|nightly")
    ap.add_argument("--repro", default="", help="Fallback fuer den Reproduktionsbefehl")
    ap.add_argument("--log", type=Path, help="Log von scripts/ci.py")
    ap.add_argument("--reports", type=Path, default=Path("reports"))
    args = ap.parse_args()

    results, blocks, repro = parse_log(args.log) if args.log else ([], [], "")
    repro = repro or args.repro
    total, failed, details = junit_failures(args.reports)
    bad_steps = [r for r in results if r.strip().startswith("FAIL")]
    verdict = "FEHLGESCHLAGEN" if (blocks or failed or bad_steps) else (
        "ok" if results else "kein Ergebnis (Lauf abgebrochen oder ci.py nicht gestartet)")

    out = [f"## {args.title}: {verdict}", "", f"Stufe: `{args.stage.upper()}`", ""]
    if repro:
        out += ["Lokal nachstellen:", "", "```bash", repro, "```", ""]
    if results:
        out += ["### Schritte", "", "```", *results, "```", ""]
    if total:
        out += ["### Tests (JUnit)", "", f"{total} Testfaelle, {failed} rot.", ""]
    if details:
        out += ["### Rote Tests", ""]
        out += [f"<details><summary>{d.splitlines()[0]}</summary>\n\n```\n" + "\n".join(d.splitlines()[1:]) + "\n```\n</details>\n" for d in details]
    if blocks:
        out += ["### Fehlerklassen mit Ursache und Fix", "", "```", *blocks, "```", "",
                "Katalog: docs/ci-failures.md", ""]
    perf = args.reports / "perf-summary.md"
    if perf.is_file():
        out += ["### Performance", "", perf.read_text(encoding="utf-8", errors="replace").strip(), ""]
    if args.reports.is_dir():
        files = sorted(p.name for p in args.reports.iterdir() if p.is_file())
        if files:
            out += ["### Artefakte (reports/)", "", *[f"- `{f}`" for f in files], ""]
    out += ["Weitere Artefakte (Playwright-Report, test-results, perf/results) hängen am Lauf als Download.", ""]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
