#!/usr/bin/env python3
"""Testauswahl nach Aenderung: geaenderte Dateien -> betroffene pytest-Dateien.

Ablauf (siehe scripts/ci.py, Stufe T1):
  1. geaenderte Dateien bestimmen (git diff gegen Basis + uncommittet + neu,
     --staged, --files-from oder Dateien als Argumente),
  2. pro Datei Tests ableiten: Namenskonvention + scripts/test-map.toml,
  3. auf "voll" (T2) eskalieren bei Kernpfaden, > 25 Dateien, > 3 Bereichen
     oder einer Quelldatei ohne Zuordnung (sicher statt still unvollstaendig).

Ausgabe: lesbar mit Begruendung je Entscheidung; --print-tests liefert nur die
Testdateien (eine je Zeile), --json maschinenlesbar. Exit-Code ist immer 0,
ausser bei Aufrufsfehlern.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_FILE = ROOT / "scripts" / "test-map.toml"
SRC_PREFIX = "src/dispread/"

#: Eskalation auf "voll" bei Aenderung dieser Pfade (fnmatch, '*' ueberschreitet '/').
CORE_PATTERNS: tuple[str, ...] = (
    "src/dispread/pipeline.py",
    "src/dispread/rectify*",
    "src/dispread/ocr/*",
    "src/dispread/validate.py",
    "src/dispread/records.py",
    "src/dispread/live/*",
    "pyproject.toml",
    "tests/conftest.py",
    "packaging/*",
    "scripts/ci*",
    "scripts/test-select.py",
    "scripts/test-map.toml",
)
MAX_FILES = 25
MAX_AREAS = 3
#: Dateiendungen/Pfade ohne pytest-Bezug (nur Hinweis, keine Auswahl).
NO_TEST_SUFFIXES = (".md", ".txt", ".rst", ".png", ".jpg", ".svg", ".zip")


@dataclass
class Decision:
    """Ergebnis der Auswahl: none = nichts zu testen, focused = Liste, full = T2."""

    level: str = "none"
    tests: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def load_map(path: Path = MAP_FILE) -> dict:
    """Liest die Mapping-Datei; fehlende Datei = leeres Mapping."""
    if not path.is_file():
        return {"full": {}, "map": {}}
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    data.setdefault("full", {})
    data.setdefault("map", {})
    return data


def match_any(path: str, patterns) -> str | None:
    """Erstes passendes fnmatch-Muster oder None."""
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return pat
    return None


def expand_tests(globs, root: Path = ROOT) -> list[str]:
    """Globs relativ zum Repo -> vorhandene Dateien (sortiert, ohne Duplikate)."""
    found: set[str] = set()
    for g in globs:
        found.update(p.relative_to(root).as_posix() for p in root.glob(g) if p.is_file())
    return sorted(found)


def convention_globs(path: str) -> list[str]:
    """Namenskonvention: Quelle -> Testdatei-Globs (ohne Pruefung auf Existenz)."""
    p = Path(path)
    if path.startswith(SRC_PREFIX) and p.suffix == ".py":
        parts = p.relative_to(SRC_PREFIX).parts
        stem = p.stem
        if len(parts) == 1:
            if stem == "__init__":
                return []
            return [f"tests/test_{stem}*.py"]
        pkg = parts[0]
        if stem == "__init__":
            return [f"tests/test_{pkg}*.py"]
        return [f"tests/test_{pkg}_{stem}*.py", f"tests/test_{stem}*.py"]
    if path.startswith("scripts/") and p.suffix in {".py", ".sh"}:
        return [f"tests/test_{p.stem.replace('-', '_')}*.py"]
    return []


def area_of(path: str) -> str | None:
    """Bereich fuer die Zaehlung 'Top-Level-Pakete'; Tests und Doku zaehlen nicht."""
    if path.startswith(("tests/", "docs/")) or path.endswith(NO_TEST_SUFFIXES):
        return None
    if path.startswith(SRC_PREFIX):
        rest = path[len(SRC_PREFIX):]
        return rest.split("/", 1)[0] if "/" in rest else "dispread-kern"
    return path.split("/", 1)[0]


def is_source(path: str) -> bool:
    """Quellen unter src/dispread brauchen eine Zuordnung (Konsistenztest)."""
    return path.startswith(SRC_PREFIX) and "/__pycache__/" not in path


def select(files, mapping: dict | None = None, root: Path = ROOT, max_files: int = MAX_FILES,
           max_areas: int = MAX_AREAS) -> Decision:
    """Kernfunktion. Reine Funktion ueber Dateiliste + Mapping (testbar)."""
    mapping = load_map() if mapping is None else mapping
    files = sorted({f.strip().removeprefix("./") for f in files if f.strip()})
    dec = Decision()
    if not files:
        dec.notes.append("keine geaenderten Dateien")
        return dec

    def full(reason: str) -> Decision:
        dec.level = "full"
        dec.tests = []
        dec.reasons.append(f"voll, weil {reason}")
        return dec

    core = [(f, m) for f in files if (m := match_any(f, CORE_PATTERNS))]
    if core:
        f, m = core[0]
        more = f" (+{len(core) - 1} weitere Kernpfade)" if len(core) > 1 else ""
        return full(f"Kernpfad beruehrt: {f} (Muster {m}){more}")
    if len(files) > max_files:
        return full(f"{len(files)} Dateien geaendert (Grenze {max_files})")
    areas = sorted({a for f in files if (a := area_of(f))})
    if len(areas) > max_areas:
        return full(f"{len(areas)} Bereiche betroffen (Grenze {max_areas}): {', '.join(areas)}")

    full_patterns = mapping.get("full", {})
    map_entries = mapping.get("map", {})
    tests: set[str] = set()
    for f in files:
        if f.startswith("tests/"):
            name = Path(f).name
            if f.startswith("tests/test_") and f.endswith(".py"):
                if (root / f).is_file():
                    tests.add(f)
                    dec.reasons.append(f"{f}: Testdatei selbst geaendert")
                else:
                    dec.notes.append(f"{f}: Testdatei geloescht, nichts auszufuehren")
                continue
            if f.startswith("tests/fixtures/") or (name.endswith(".py") and "/" not in f[len("tests/"):]):
                return full(f"gemeinsame Testhilfe/Fixture geaendert: {f}")
            dec.notes.append(f"{f}: kein pytest-Bezug (Node/Playwright-Test), nicht Teil der Auswahl")
            continue
        explicit = match_any(f, full_patterns)
        if explicit:
            return full(f"{f} ist als 'voll' markiert ({full_patterns[explicit]})")
        globs: list[str] = []
        origin = []
        mapped = match_any(f, map_entries)
        if mapped:
            globs += list(map_entries[mapped])
            origin.append(f"Mapping {mapped}")
        conv = convention_globs(f)
        if conv:
            hits = expand_tests(conv, root)
            if hits:
                globs += conv
                origin.append("Namenskonvention")
        hits = expand_tests(globs, root)
        if hits:
            tests.update(hits)
            dec.reasons.append(f"{f}: {len(hits)} Testdatei(en) via {' + '.join(origin)}")
            continue
        if is_source(f) and f.endswith(".py"):
            return full(f"Quelldatei ohne Test-Zuordnung: {f} (Mapping in scripts/test-map.toml ergaenzen)")
        if f.startswith(SRC_PREFIX):
            return full(f"Datei unter src/dispread ohne Test-Zuordnung: {f}")
        dec.notes.append(f"{f}: keine zugeordneten Tests (kein Quellcode), ignoriert")
    dec.tests = sorted(tests)
    dec.level = "focused" if tests else "none"
    if not tests:
        dec.reasons.append("keine Quellaenderung mit Testbezug")
    return dec


def _git(*args: str, root: Path = ROOT) -> str:
    res = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else ""


def default_base(root: Path = ROOT) -> str:
    """Basis-Ref: Upstream, sonst origin/master|main, sonst master|main, sonst HEAD."""
    cands = ["@{upstream}", "origin/master", "origin/main", "master", "main"]
    for ref in cands:
        if _git("rev-parse", "--verify", "--quiet", ref, root=root).strip():
            return ref
    return "HEAD"


def changed_files(base: str | None = None, staged: bool = False, root: Path = ROOT) -> list[str]:
    """Geaenderte Dateien: staged oder (Merge-Base..Arbeitsbaum + neue Dateien)."""
    if staged:
        out = _git("diff", "--cached", "--name-only", "--diff-filter=ACMRD", root=root)
        return sorted(set(out.split("\n")) - {""})
    base = base or default_base(root)
    mb = _git("merge-base", "HEAD", base, root=root).strip() or base
    out = _git("diff", "--name-only", "--diff-filter=ACMRD", mb, root=root)
    out += "\n" + _git("ls-files", "--others", "--exclude-standard", root=root)
    return sorted(set(out.split("\n")) - {""})


def read_file_list(path: str) -> list[str]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]


def format_decision(dec: Decision, n_files: int) -> str:
    head = {"none": "keine Tests noetig", "focused": f"fokussiert: {len(dec.tests)} Testdatei(en)",
            "full": "VOLL (T2)"}[dec.level]
    lines = [f"Testauswahl: {head} ({n_files} geaenderte Datei(en))"]
    lines += [f"  - {r}" for r in dec.reasons]
    lines += [f"  . {n}" for n in dec.notes]
    if dec.level == "focused":
        lines += [f"    {t}" for t in dec.tests]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="Dateien explizit angeben (statt git)")
    ap.add_argument("--base", help="Basis-Ref (Default: Upstream/origin/master)")
    ap.add_argument("--staged", action="store_true", help="nur gestagte Dateien")
    ap.add_argument("--files-from", metavar="DATEI", help="Dateiliste aus Datei ('-' = stdin)")
    ap.add_argument("--map", type=Path, default=MAP_FILE, help="Mapping-Datei")
    ap.add_argument("--print-tests", action="store_true", help="nur Testdateien ausgeben ('FULL' bei voll)")
    ap.add_argument("--json", action="store_true", help="JSON ausgeben")
    args = ap.parse_args(argv)
    if args.files:
        files = args.files
    elif args.files_from:
        files = read_file_list(args.files_from)
    else:
        files = changed_files(args.base, args.staged)
    dec = select(files, load_map(args.map))
    if args.json:
        print(json.dumps({"level": dec.level, "tests": dec.tests, "reasons": dec.reasons,
                          "notes": dec.notes, "files": files}, indent=2, ensure_ascii=False))
    elif args.print_tests:
        print("FULL" if dec.level == "full" else "\n".join(dec.tests))
    else:
        print(format_decision(dec, len(files)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
