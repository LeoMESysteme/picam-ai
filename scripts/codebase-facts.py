#!/usr/bin/env python3
"""Codebase-Übersicht aus Git und Quelltext (docs/uebersicht/codebase.md).

Die Seite „Codebase im Überblick“ zeigt, wie der Code gewachsen ist, wie die
Branches verlaufen, wann gearbeitet wird, woraus er besteht, wo er schwer zu
prüfen ist und was aufgeräumt werden kann. Statt eines eingefrorenen
Schnappschusses erzeugt dieses Skript die Daten bei Bedarf neu. Es liest nur
getrackte Dateien (`git ls-files`-Stand des Fokus-Branches) und die
Git-Historie; es importiert nichts aus dem Projekt und braucht nur die
Standardbibliothek und die `git`-Befehlszeile.

    ./scripts/codebase-facts.py                    # nur Zusammenfassung
    ./scripts/codebase-facts.py --write            # beide Ausgaben schreiben
    ./scripts/codebase-facts.py --focus feat/integration --write
    ./scripts/codebase-facts.py --root /pfad/zum/worktree --out-json x.json

Zwei Ausgaben:

* `docs-site/assets/data/codebase.json` (Schema des Objekts `window.REPO` der
  interaktiven Bühne) mit `meta.generated`, `meta.focus`, `meta.tip`;
* ein Markdown-Block in `docs/uebersicht/codebase.md` zwischen
  `<!-- CODEBASE-FACTS:BEGIN -->` und `<!-- CODEBASE-FACTS:END -->`.

Es gibt absichtlich kein `--check`: die Daten ändern sich mit jedem Commit.

Messregeln
----------

Zeilen
    Textzeilen je Datei (Zeilenumbrüche, plus eine unvollständige letzte
    Zeile). Binärdateien (NUL-Byte in den ersten 8000 Bytes) zählen 0. Die
    Kategorien `data` und `vendor` zählen Dateien, aber keine Zeilen in
    `meta.loc`.

Komplexität (McCabe, nur Python, per `ast`)
    Eine Funktion (auch Methode oder verschachtelte Funktion) beginnt bei 1.
    Dazu zählt je 1: `if` (auch `elif`, das ist ein verschachteltes `if`),
    `for`, `async for`, `while`, `except`-Zweig, Bedingungsausdruck
    (`a if b else c`), jeder zusätzliche Operand einer `and`/`or`-Kette,
    jede Klausel einer Comprehension (`for`) und jede ihrer `if`-Bedingungen,
    jeder `case` eines `match`. `with`, `try`, `else`, `finally`, `assert`
    zählen nicht. Verschachtelte Funktionen und Klassen zählen als eigene
    Einträge und nicht in der umschließenden Funktion; Lambdas zählen mit.
    JavaScript wird nicht gemessen (kein Parser in der Standardbibliothek),
    dort stehen `cc`/`cs`/`fn` auf 0.

Importkanten
    Python-Module unter `src/` und `windows/bridge/src/` (Kern, Werkbank,
    Brücke). Aufgelöst werden `import a.b` und `from a.b import c` (auch
    relativ), soweit das Ziel ein Modul des Projekts ist.

Zeitzone
    Tage, Wochentage und Stunden in `Europe/Berlin` (`zoneinfo`), mit der
    Sommerzeit des jeweiligen Datums.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = "docs-site/assets/data/codebase.json"
OUT_MD = "docs/uebersicht/codebase.md"
KETTE = "docs-site/assets/data/kette.json"
MARK_BEGIN = "<!-- CODEBASE-FACTS:BEGIN -->"
MARK_END = "<!-- CODEBASE-FACTS:END -->"

TZ = ZoneInfo("Europe/Berlin")
STILL_TAGE = 14          # ab so vielen Tagen ohne Commit gilt ein offener Branch als still
GIANT_LINES = 800        # „Riese“: Quelldatei mit mehr Zeilen
BIGDOC_KB = 200          # große Markdown-Dateien (nur Hinweis in den Daten)
CODE_EXT = {".py", ".js", ".mjs", ".ts", ".css"}
CODE_CATS = ("core", "workbench", "bridge", "scripts")
CATS = [
    ("core", "Kern"),
    ("workbench", "Werkbank & Live"),
    ("bridge", "Windows-Brücke"),
    ("scripts", "Skripte"),
    ("tests", "Tests"),
    ("docs", "Doku"),
    ("infra", "Infrastruktur"),
]
CAT_LABEL = dict(CATS)
LOC_CATS = [c for c, _ in CATS]
HIST_BUCKETS = [(1, 5), (6, 10), (11, 20), (21, 40), (41, 999)]
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

# Ausgabetyp je Stufe der Kette. kette.json hat kein Feld dafür; die Namen
# werden deshalb nur übernommen, wenn die Klasse im Quelltext existiert.
STUFE_AUS = {
    "frames": "Frame",
    "detect": "DisplayCandidate",
    "track": "TrackResult",
    "rectify": "DisplayCrop",
    "ocr": "ReadResult",
    "validate": "GateDecision",
    "sink": "TxReceipt",
}
# Umfeld der Kette: Pfade (unter dem Wurzelverzeichnis) und feste Kurzrolle.
UMFELD = [
    ("pipeline.py + records.py", ["src/dispread/pipeline.py", "src/dispread/records.py"],
     "verdrahtet die Stufen und baut den ValueRecord"),
    ("live/", ["src/dispread/live/"], "Livepfad: Einrichtung, Sitzung, Nachführung, Audit-Log"),
    ("workbench/", ["src/dispread/workbench/"], "Webwerkbank, CLI und TUI auf dem Pi"),
    ("bridge/", ["src/dispread/bridge/"], "Protokoll zwischen Pi und Windows-Brücke"),
    ("windows/bridge", ["windows/bridge/"], "Windows-Programm, das GSVmulti speist"),
]

MARKER_RE = re.compile(r"\b(?:" + "TO" + "DO|FIX" + "ME|XX" + "X)\\b")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

METHODE = {
    "dead": ("Top-Level-Funktionen und -Klassen (per ast, ohne Decorator, ohne test_*, main "
             "und dunder) in Kern, Werkbank, Brücke und Skripten, deren Name im gesamten "
             "getrackten Repo-Text nur an der Definition vorkommt."),
    "orphans": ("Dateien direkt unter scripts/, deren Dateiname (bei Python-Modulen auch der "
                "Modulname) in keiner anderen getrackten Textdatei vorkommt."),
    "branches": (f"Lokale und Remote-Refs außer Haupt- und Fokus-Branch. still: Commits, die nicht "
                 f"im Fokus-Branch sind, und seit mindestens {STILL_TAGE} Tagen kein neuer Commit "
                 f"(gemessen am Commit-Datum der Fokus-Spitze); offen: dasselbe, aber jünger; "
                 f"gemergt: Ref liegt vollständig im Fokus-Branch."),
    "giants": f"Quelldateien (py, js, mjs, ts, css) in Kern, Werkbank, Brücke und Skripten mit mehr als {GIANT_LINES} Zeilen.",
    "bigDocs": f"Markdown-Dateien ab {BIGDOC_KB} kB.",
    "todo": "Vorkommen der Marker TODO, FIXME und XXX in den Quelldateien dieser vier Bereiche.",
    "complexity": ("McCabe per ast, nur Python: 1 + if/elif, for, while, except, Bedingungsausdruck, "
                   "Operanden von and/or, Comprehension-Klauseln und -Bedingungen, match-Fälle."),
}


# ------------------------------------------------------------------ Git-Zugriff --

class GitError(RuntimeError):
    """Ein Git-Befehl ist fehlgeschlagen."""


def git(root: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=off", *args],
                          capture_output=True)
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout.decode("utf-8", "replace")


def git_bytes(root: Path, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def read_blobs(root: Path, shas: list[str]) -> dict[str, bytes]:
    """Inhalt mehrerer Blobs über einen `cat-file --batch`-Prozess lesen."""
    out: dict[str, bytes] = {}
    if not shas:
        return out
    proc = subprocess.Popen(["git", "-C", str(root), "cat-file", "--batch"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert proc.stdin is not None and proc.stdout is not None
    for i in range(0, len(shas), 200):
        chunk = shas[i:i + 200]
        proc.stdin.write(("\n".join(chunk) + "\n").encode())
        proc.stdin.flush()
        for sha in chunk:
            header = proc.stdout.readline().split()
            if len(header) < 3 or header[1] != b"blob":
                out[sha] = b""
                continue
            size = int(header[2])
            data = proc.stdout.read(size)
            proc.stdout.read(1)
            out[sha] = data
    proc.stdin.close()
    proc.wait()
    return out


def count_lines(data: bytes) -> int | None:
    """Textzeilen; `None` bei Binärdaten."""
    if b"\0" in data[:8000]:
        return None
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


# ----------------------------------------------------------------------- Zeit --

def berlin(ts: int | float) -> datetime:
    return datetime.fromtimestamp(ts, TZ)


def day_start(d: datetime) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=TZ).timestamp())


def day_end(d: datetime) -> int:
    nxt = datetime(d.year, d.month, d.day, tzinfo=TZ) + timedelta(days=1)
    # Auf Wanduhr-Basis: Mitternacht des Folgetags in Berlin minus 1 s
    nxt = datetime(nxt.year, nxt.month, nxt.day, tzinfo=TZ)
    return int(nxt.timestamp()) - 1


# ------------------------------------------------------------- Kategorien --

DATA_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".zip", ".tdms", ".tdms_index",
            ".sha256", ".ucf", ".jsonl"}
JSON_DATA_DIRS = ("tests/fixtures/", "docs/quellen/", "docs/superpowers/specs/")


def categorize(path: str) -> str:
    """Kategorie eines Pfads (die Regeln der Bühne, siehe Modul-Docstring)."""
    name = path.rsplit("/", 1)[-1]
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if "/vendor/" in "/" + path or name == "package-lock.json":
        return "vendor"
    if ext in DATA_EXT:
        return "data"
    if ext == ".json" and (path.startswith(JSON_DATA_DIRS) or "/templates/" in path):
        return "data"
    if path.startswith(("tests/", "windows/bridge/tests/")) or (
            "/" not in path and name.startswith("test_")):
        return "tests"
    if path.startswith("src/dispread/"):
        sub = path.split("/")[2]
        return "workbench" if sub in ("live", "workbench") else "core"
    if path.startswith("windows/bridge/"):
        return "docs" if ext == ".md" else "bridge"
    if path.startswith(("scripts/", "examples/")):
        return "scripts"
    if path.startswith(".claude/skills/"):
        return "docs"
    if path.startswith((".claude/", ".codex/", ".github/", ".agents/", "systemd/")):
        return "infra"
    if path.startswith(("docs/", "docs-site/", "docs-overrides/", "cloudflare/")):
        return "docs"
    if "/" not in path:
        if ext == ".md":
            return "docs"
        if ext == ".py":
            return "scripts"
        return "infra"
    return "docs"


# ------------------------------------------------------------- Komplexität --

def complexity(func: ast.AST) -> int:
    """McCabe-Komplexität einer Funktion (Zählung im Modul-Docstring)."""
    total = 1
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
                             ast.IfExp, ast.comprehension, ast.match_case)):
            total += 1
        if isinstance(node, ast.comprehension):
            total += len(node.ifs)
        elif isinstance(node, ast.BoolOp):
            total += len(node.values) - 1
        stack.extend(ast.iter_child_nodes(node))
    return total


def iter_functions(tree: ast.AST):
    """(qualifizierter Name, Knoten) aller Funktionen, Methoden und inneren Funktionen."""
    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                yield name, child
                yield from walk(child, name + ".")
            elif isinstance(child, ast.ClassDef):
                yield from walk(child, prefix + child.name + ".")
            else:
                yield from walk(child, prefix)
    yield from walk(tree, "")


def analyse_python(source: str, path: str, cat: str) -> list[dict]:
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError):
        return []
    return [{"p": path, "n": name, "cc": complexity(node),
             "l": (node.end_lineno or node.lineno) - node.lineno + 1,
             "ln": node.lineno, "c": cat}
            for name, node in iter_functions(tree)]


# ---------------------------------------------------------------- Module --

def module_id(path: str) -> str | None:
    """Modulname eines Python-Pfads unter src/ oder windows/bridge/src/."""
    for prefix in ("src/", "windows/bridge/src/"):
        if path.startswith(prefix) and path.endswith(".py"):
            parts = path[len(prefix):-3].split("/")
            if parts[-1] == "__init__":
                parts.pop()
            return ".".join(parts) if parts else None
    return None


def module_group(path: str, mid: str) -> str:
    if path.startswith("windows/bridge/src/"):
        return "bridge-app/ui" if ".ui." in mid + "." and mid.split(".")[1:2] == ["ui"] else "bridge-app"
    parts = mid.split(".")
    if len(parts) == 1:
        return "dispread"
    return parts[1] if parts[1] in ("live", "workbench", "bridge", "ocr", "frames", "sink", "detect") else "kern"


def import_edges(modules: dict[str, str], sources: dict[str, str]) -> set[tuple[str, str]]:
    """Importkanten zwischen Projektmodulen. `modules`: Modulname -> Pfad."""
    edges: set[tuple[str, str]] = set()
    names = set(modules)
    for mid, path in modules.items():
        try:
            tree = ast.parse(sources[path])
        except (SyntaxError, ValueError):
            continue
        is_pkg = path.endswith("__init__.py")
        parts = mid.split(".")
        for node in ast.walk(tree):
            found: list[str] = []
            if isinstance(node, ast.Import):
                for alias in node.names:
                    found.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base_parts = parts if is_pkg else parts[:-1]
                    cut = len(base_parts) - (node.level - 1)
                    if cut < 0:
                        continue
                    base = ".".join(base_parts[:cut] + ([node.module] if node.module else []))
                else:
                    base = node.module or ""
                if not base:
                    continue
                for alias in node.names:
                    found.append(f"{base}.{alias.name}" if f"{base}.{alias.name}" in names else base)
            for target in found:
                while target and target not in names:
                    target = target.rpartition(".")[0]
                if target and target != mid:
                    edges.add((mid, target))
    return edges


# -------------------------------------------------------------- Sammlung --

def current_branch(root: Path) -> str:
    out = git(root, "symbolic-ref", "--short", "-q", "HEAD", check=False).strip()
    return out or "HEAD"


def list_refs(root: Path) -> dict[str, dict]:
    """Refs nach Kurzname: Spitze, Remote-Flag. Lokal und Remote zu einem Namen vereint."""
    out = git(root, "for-each-ref", "--format=%(refname)\x1f%(objectname)\x1f%(authordate:unix)",
              "refs/heads", "refs/remotes")
    refs: dict[str, dict] = {}
    for line in out.splitlines():
        ref, sha, ts = line.split("\x1f")
        if ref.endswith("/HEAD"):
            continue
        if ref.startswith("refs/heads/"):
            name, remote = ref[len("refs/heads/"):], False
        else:
            name, remote = ref[len("refs/remotes/"):].split("/", 1)[1], True
        cur = refs.get(name)
        if cur is None:
            refs[name] = {"tip": sha, "t": int(ts), "remote": remote, "local": not remote}
        else:
            cur["remote"] = cur["remote"] or remote
            cur["local"] = cur["local"] or not remote
            if int(ts) > cur["t"]:
                cur["tip"], cur["t"] = sha, int(ts)
    return refs


def author_kind(name: str, email: str) -> str:
    low = f"{name} {email}".lower()
    if "codex" in low:
        return "c"
    if "bot" in low:
        return "b"
    return "h"


def read_history(root: Path, tips: list[str]) -> list[dict]:
    """Alle Commits ab den Spitzen mit Numstat (Merges ohne Änderungen)."""
    fmt = "\x1e%H\x1f%P\x1f%at\x1f%an\x1f%ae\x1f%s"
    raw = git(root, "log", *tips, "--no-renames", "--numstat", f"--format={fmt}")
    commits: list[dict] = []
    for block in raw.split("\x1e")[1:]:
        head, _, stat = block.partition("\n")
        h, parents, t, an, ae, subject = head.split("\x1f", 5)
        files = []
        for line in stat.splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3:
                a = int(parts[0]) if parts[0].isdigit() else 0
                x = int(parts[1]) if parts[1].isdigit() else 0
                files.append((parts[2], a, x))
        commits.append({"hash": h, "parents": parents.split(), "t": int(t),
                        "w": author_kind(an, ae), "s": subject, "files": files})
    return commits


def commit_category(files: list[tuple[str, int, int]]) -> str:
    weight: Counter = Counter()
    for path, a, x in files:
        cat = categorize(path)
        if cat in LOC_CATS:
            weight[cat] += a + x
    if not weight:
        return ""
    best = max(weight.values())
    for cat in LOC_CATS:
        if weight[cat] == best:
            return cat
    return ""


def merge_name(subject: str) -> str | None:
    for pattern in (r"^Merge (?:remote-tracking )?branch '([^']+)'",
                    r"^Merge pull request #?\d+ from \S+?/(\S+)",
                    r"^Merge ([a-z][\w./-]*):"):
        m = re.match(pattern, subject)
        if m and m.group(1) not in ("master", "main") and not m.group(1).startswith("origin/"):
            return m.group(1)
    return None


def build_lanes(commits: list[dict], by_hash: dict[str, dict], trunk_tip: str, focus_tip: str,
                trunk: str, focus: str, refs: dict[str, dict], still_ref_t: int) -> list[dict]:
    """Spuren (Linien) für den Verlauf; setzt `lane` an jedem Commit."""
    lane_of: dict[str, int] = {}
    lanes: list[dict] = []

    def claim(tip: str, name: str, kind: str) -> int | None:
        chain = []
        cur = tip
        while cur in by_hash and cur not in lane_of:
            chain.append(cur)
            parents = by_hash[cur]["parents"]
            cur = parents[0] if parents else ""
        if not chain:
            return None
        idx = len(lanes)
        for h in chain:
            lane_of[h] = idx
        oldest = by_hash[chain[-1]]
        fork = oldest["parents"][0] if oldest["parents"] else None
        lanes.append({"name": name, "kind": kind, "chain": chain, "fork": fork})
        return idx

    claim(trunk_tip, trunk, "trunk")
    if focus_tip != trunk_tip and focus_tip not in lane_of:
        claim(focus_tip, focus, "focus")
    named = sorted(((n, r) for n, r in refs.items() if n not in (trunk, focus)),
                   key=lambda kv: (-kv[1]["t"], kv[0]))
    for name, ref in named:
        claim(ref["tip"], name, "branch")
    for c in sorted(commits, key=lambda c: -c["t"]):
        for p in c["parents"][1:]:
            if p in by_hash and p not in lane_of:
                claim(p, merge_name(c["s"]) or f"(Merge {c['hash'][:7]})", "branch")
    for c in sorted(commits, key=lambda c: -c["t"]):
        if c["hash"] not in lane_of:
            claim(c["hash"], f"(abgezweigt {c['hash'][:7]})", "branch")

    # Merge-Beziehungen: erster Merge, der die Spitze der Spur als Nebenelternteil trägt
    merged_by: dict[str, dict] = {}
    for c in sorted(commits, key=lambda c: c["t"]):
        for p in c["parents"][1:]:
            merged_by.setdefault(p, c)
    for lane in lanes:
        chain = lane["chain"]
        times = [by_hash[h]["t"] for h in chain]
        lane["n"], lane["t0"], lane["t1"] = len(chain), min(times), max(times)
        fork = lane["fork"]
        lane["frm"] = lane_of.get(fork) if fork else None
        lane["tFork"] = by_hash[fork]["t"] if fork in by_hash else lane["t0"]
        merge = merged_by.get(chain[0])
        if lane["kind"] in ("trunk", "focus") or merge is None or lane_of.get(merge["hash"]) == lanes.index(lane):
            lane["into"], lane["tMerge"] = None, None
        else:
            lane["into"], lane["tMerge"] = lane_of[merge["hash"]], merge["t"]
        if lane["kind"] == "trunk":
            lane["state"] = "trunk"
        elif lane["kind"] == "focus":
            lane["state"] = "focus"
        elif lane["into"] is not None:
            lane["state"] = "merged"
            if lane["into"] == 0:
                lane["kind"] = "merged"
        else:
            idle = (still_ref_t - lane["t1"]) / 86400
            lane["state"] = "stale" if idle >= STILL_TAGE else "open"

    # Reihenfolge: Haupt-, Fokus-Spur, dann nach jüngster Aktivität; Zeilen packen
    order = [0] + ([1] if len(lanes) > 1 and lanes[1]["kind"] == "focus" else [])
    rest = sorted((i for i in range(len(lanes)) if i not in order),
                  key=lambda i: (-lanes[i]["t1"], lanes[i]["name"]))
    order += rest
    remap = {old: new for new, old in enumerate(order)}
    new_lanes = []
    rows: list[list[tuple[int, int]]] = []
    for old in order:
        lane = lanes[old]
        lo = min(lane["tFork"], lane["t0"])
        hi = max(lane["t1"], lane["tMerge"] or lane["t1"])
        if lane["kind"] == "trunk":
            row = 0
        elif lane["kind"] == "focus":
            row = 1
        else:
            row = 2
            while any(lo <= b and a <= hi for a, b in (rows[row] if row < len(rows) else [])):
                row += 1
        while len(rows) <= row:
            rows.append([])
        rows[row].append((lo, hi))
        new_lanes.append({
            "name": lane["name"], "kind": lane["kind"], "state": lane["state"], "n": lane["n"],
            "row": row, "t0": lane["t0"], "t1": lane["t1"], "tFork": lane["tFork"],
            "tMerge": lane["tMerge"],
            "frm": remap[lane["frm"]] if lane["frm"] is not None else None,
            "into": remap[lane["into"]] if lane["into"] is not None else None,
        })
    for h, old in lane_of.items():
        by_hash[h]["lane"] = remap[old]
    return new_lanes


def collect(root: Path | str = ROOT, focus: str | None = None) -> dict:
    """Alle Daten der Übersicht (Schema von `window.REPO`)."""
    root = Path(root)
    focus = focus or current_branch(root)
    focus_tip = git(root, "rev-parse", "--verify", f"{focus}^{{commit}}").strip()
    refs = list_refs(root)
    trunk = next((n for n in ("master", "main") if n in refs), focus)
    trunk_tip = refs[trunk]["tip"] if trunk in refs else focus_tip
    tips = sorted({focus_tip, trunk_tip, *(r["tip"] for r in refs.values())})
    commits = read_history(root, tips)
    by_hash = {c["hash"]: c for c in commits}
    focus_set = set(git(root, "rev-list", focus_tip).split())
    trunk_set = set(git(root, "rev-list", trunk_tip).split())
    tip_t = by_hash[focus_tip]["t"]

    # ---- Dateien am Stand des Fokus
    entries = []
    for entry in git_bytes(root, "ls-tree", "-r", "-z", "-l", focus_tip).split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.decode("utf-8", "replace").partition("\t")
        mode, kind, sha, size = meta.split()
        if kind == "blob":
            entries.append((path, sha, int(size)))
    contents = read_blobs(root, sorted({sha for _, sha, _ in entries}))
    sources: dict[str, str] = {}
    texts: dict[str, str] = {}
    line_cache: dict[str, int | None] = {}
    files: list[dict] = []
    functions: list[dict] = []
    for path, sha, size in sorted(entries):
        data = contents.get(sha, b"")
        lines = line_cache.get(sha) if sha in line_cache else count_lines(data)
        line_cache[sha] = lines
        cat = categorize(path)
        if lines is not None and size < 3_000_000:
            texts[path] = data.decode("utf-8", "ignore")
        cc = cs = fn = 0
        if path.endswith(".py") and lines is not None and cat not in ("data", "vendor"):
            sources[path] = texts[path]
            funcs = analyse_python(texts[path], path, cat)
            functions.extend(funcs)
            fn = len(funcs)
            cc = max((f["cc"] for f in funcs), default=0)
            cs = sum(f["cc"] for f in funcs)
        files.append({"p": path, "c": cat, "l": lines or 0, "b": size, "n": 0, "t": 0, "t0": 0,
                      "ch": 0, "cc": cc, "cs": cs, "fn": fn, "mi": None})
    by_path = {f["p"]: f for f in files}

    # ---- Dateihistorie und Commit-Kennzahlen
    for c in sorted(commits, key=lambda c: c["t"]):
        counted = [(p, a, x) for p, a, x in c["files"] if categorize(p) not in ("data", "vendor")]
        c["a"] = sum(a for _, a, _ in counted)
        c["x"] = sum(x for _, _, x in counted)
        c["cat"] = commit_category(c["files"])
        if c["hash"] not in focus_set:
            continue
        for path, a, x in c["files"]:
            f = by_path.get(path)
            if f is None:
                continue
            f["n"] += 1
            f["ch"] += a + x
            f["t"] = max(f["t"], c["t"])
            f["t0"] = c["t"] if not f["t0"] else min(f["t0"], c["t"])

    # ---- Meta
    loc = {c: sum(f["l"] for f in files if f["c"] == c) for c in LOC_CATS}
    files_by = Counter(f["c"] for f in files)
    first = min(c["t"] for c in commits)
    last = max(c["t"] for c in commits)
    d0, d1 = berlin(first).date(), berlin(last).date()
    non_test = [f for f in functions if f["c"] != "tests"]
    test_fn = [f for f in functions if f["c"] == "tests"]
    py_tests = sum(1 for f in test_fn if f["n"].rsplit(".", 1)[-1].startswith("test_"))
    e2e = 0
    for path, text in texts.items():
        if categorize(path) == "tests" and path.endswith((".spec.ts", ".spec.js", ".spec.mjs")):
            e2e += len(re.findall(r"(?m)^\s*(?:test|it)(?:\.(?:only|skip|fixme|fail))?\s*\(", text))
    remote = git(root, "remote", "get-url", "origin", check=False).strip()
    repo_name = re.sub(r"\.git$", "", remote.rstrip("/").rsplit("/", 1)[-1]) if remote else root.name
    meta = {
        "repo": repo_name, "focus": focus, "trunk": trunk, "tip": focus_tip[:7],
        "generated": datetime.now(TZ).isoformat(timespec="seconds"),
        "first": first, "last": last, "days": (d1 - d0).days + 1,
        "activeDays": len({berlin(c["t"]).date() for c in commits}),
        "commits": len(commits), "commitsFocus": len(focus_set), "commitsMaster": len(trunk_set),
        "who": {},
        "files": len(files), "loc": loc, "filesBy": dict(sorted(files_by.items())),
        "locTotal": sum(loc.values()),
        "fnTotal": len(non_test), "fnTests": len(test_fn), "pyTests": py_tests, "e2eTests": e2e,
        "branches": len(refs), "merges": sum(1 for c in commits if len(c["parents"]) > 1),
        "over10": sum(1 for f in non_test if f["cc"] > 10),
        "over40": sum(1 for f in non_test if f["cc"] > 40),
    }
    who = Counter(c["w"] for c in commits)
    meta["who"] = {"human": who["h"], "bot": who["b"], "codex": who["c"]}
    meta["tip"] = focus_tip[:7]

    # ---- Spuren und Commits
    lanes = build_lanes(commits, by_hash, trunk_tip, focus_tip, trunk, focus, refs, tip_t)
    out_commits = []
    for c in sorted(commits, key=lambda c: (-c["t"], c["hash"])):
        out_commits.append({
            "h": c["hash"][:7], "p": [p[:7] for p in c["parents"]], "t": c["t"], "w": c["w"],
            "s": c["s"], "a": c["a"], "x": c["x"], "f": len(c["files"]), "l": c.get("lane", 0),
            "F": 1 if c["hash"] in focus_set else 0, "c": c["cat"]})

    # ---- Tage und Rhythmus
    per_day: dict = {}
    heat = [[0] * 24 for _ in range(7)]
    for c in commits:
        b = berlin(c["t"])
        d = per_day.setdefault(b.date(), {"d": b.date().isoformat(), "t": day_start(b), "n": 0,
                                          "a": 0, "x": 0, "m": 0})
        d["n"] += 1
        d["a"] += c["a"]
        d["x"] += c["x"]
        d["m"] += 1 if len(c["parents"]) > 1 else 0
        heat[b.weekday()][b.hour] += 1
    perday = [per_day[k] for k in sorted(per_day)]

    # ---- Schnappschüsse (Zeilen je Kategorie am Ende jedes Tages auf dem Fokus-Pfad)
    snapshots = snapshot_series(root, focus_tip, focus_set, by_hash, line_cache)

    # ---- Funktionen, Histogramm
    functions_out = sorted((f for f in non_test if f["cc"] >= 10),
                           key=lambda f: (-f["cc"], f["p"], f["ln"]))
    hist = []
    for lo, hi in HIST_BUCKETS:
        hist.append({"lo": lo, "hi": hi,
                     "n": sum(1 for f in non_test if lo <= f["cc"] <= hi),
                     "tests": sum(1 for f in test_fn if lo <= f["cc"] <= hi)})

    # ---- Module und Graph
    modules = {}
    for path in sources:
        mid = module_id(path)
        if mid and by_path[path]["c"] in ("core", "workbench", "bridge"):
            modules[mid] = path
    edges = import_edges(modules, sources)
    inbound: Counter = Counter(b for _, b in edges)
    mods = [{"id": mid, "l": by_path[p]["l"], "g": module_group(p, mid), "cs": by_path[p]["cs"],
             "inb": inbound[mid]} for mid, p in sorted(modules.items())]
    group_of = {m["id"]: m["g"] for m in mods}
    group_loc: Counter = Counter()
    for m in mods:
        group_loc[m["g"]] += m["l"]
    group_edges: Counter = Counter()
    for a, b in edges:
        if group_of[a] != group_of[b]:
            group_edges[(group_of[a], group_of[b])] += 1
    graph = {
        "nodes": [{"id": g, "loc": n} for g, n in sorted(group_loc.items(), key=lambda kv: (-kv[1], kv[0]))],
        "edges": [{"a": a, "b": b, "w": w}
                  for (a, b), w in sorted(group_edges.items(), key=lambda kv: (-kv[1], kv[0]))],
    }

    # ---- Zustand
    health = build_health(root, files, by_path, texts, sources, refs, focus, trunk, focus_tip,
                          trunk_tip, focus_set, tip_t)

    return {
        "meta": meta,
        "cats": [{"id": c, "label": label} for c, label in CATS],
        "snapshots": snapshots,
        "perday": perday,
        "commits": out_commits,
        "lanes": lanes,
        "files": files,
        "functions": functions_out,
        "hist": hist,
        "graph": graph,
        "mods": mods,
        "modEdges": sorted([a, b] for a, b in edges),
        "heat": heat,
        "health": health,
        "pipeline": build_pipeline(root, files, functions),
        "workflows": read_workflows(root, focus_tip),
        "systemd": read_systemd(root, focus_tip),
    }


def snapshot_series(root: Path, focus_tip: str, focus_set: set[str], by_hash: dict[str, dict],
                    line_cache: dict[str, int | None]) -> list[dict]:
    """Zeilen je Kategorie am Ende jedes Tages mit Commits auf dem Fokus-Pfad."""
    chain = git(root, "rev-list", "--first-parent", focus_tip).split()
    days = sorted({berlin(by_hash[h]["t"]).date() for h in chain})
    picks = []
    for d in days:
        end = day_end(datetime(d.year, d.month, d.day, tzinfo=TZ))
        pick = next((h for h in chain if by_hash[h]["t"] <= end), None)
        if pick:
            picks.append((d, end, pick))
    trees = {}
    needed: set[str] = set()
    for _, _, h in picks:
        listing = []
        for entry in git_bytes(root, "ls-tree", "-r", "-z", h).split(b"\0"):
            if not entry:
                continue
            meta, _, path = entry.decode("utf-8", "replace").partition("\t")
            mode, kind, sha = meta.split()
            if kind != "blob":
                continue
            cat = categorize(path)
            listing.append((cat, sha))
            if cat in LOC_CATS and sha not in line_cache:
                needed.add(sha)
        trees[h] = listing
    for sha, data in read_blobs(root, sorted(needed)).items():
        line_cache[sha] = count_lines(data)
    out = []
    for i, (d, end, h) in enumerate(picks):
        loc = {c: 0 for c in LOC_CATS}
        for cat, sha in trees[h]:
            if cat in loc:
                loc[cat] += line_cache.get(sha) or 0
        t = by_hash[h]["t"] if i == len(picks) - 1 else end
        out.append({"d": d.isoformat(), "t": t, "loc": loc, "f": len(trees[h])})
    return out


def build_health(root, files, by_path, texts, sources, refs, focus, trunk, focus_tip, trunk_tip,
                 focus_set, tip_t) -> dict:
    age = lambda t: max(0, round((tip_t - t) / 86400))  # noqa: E731

    # Ungenutzte Definitionen
    tokens: Counter = Counter()
    for text in texts.values():
        tokens.update(IDENT_RE.findall(text))
    dead = []
    for path, src in sources.items():
        if by_path[path]["c"] not in CODE_CATS:
            continue
        try:
            tree = ast.parse(src)
        except (SyntaxError, ValueError):
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            name = node.name
            if node.decorator_list or name.startswith(("test", "__")) or name == "main":
                continue
            if tokens[name] <= 1:
                dead.append({"p": path, "n": name + ("" if isinstance(node, ast.ClassDef) else "()"),
                             "l": (node.end_lineno or node.lineno) - node.lineno + 1,
                             "why": "Name kommt im getrackten Repo-Text nur an der Definition vor",
                             "age": age(by_path[path]["t"])})
    dead.sort(key=lambda d: (-d["l"], d["p"], d["n"]))

    # Verwaiste Skripte
    orphans = []
    for f in files:
        p = f["p"]
        if not p.startswith("scripts/") or "/" in p[len("scripts/"):] or p not in texts:
            continue
        base = p.rsplit("/", 1)[-1]
        stem = base.rsplit(".", 1)[0]
        pats = [re.compile(re.escape(base))]
        if base.endswith(".py") and stem.isidentifier():
            pats.append(re.compile(r"\b" + re.escape(stem) + r"\b"))
        if not any(pat.search(t) for q, t in texts.items() if q != p for pat in pats):
            orphans.append({"p": p, "l": f["l"], "age": age(f["t"]),
                            "why": "kein anderer getrackter Text nennt den Dateinamen"})
    orphans.sort(key=lambda o: (-o["age"], o["p"]))

    # Branches
    branches = []
    for name, ref in refs.items():
        if name in (trunk, focus):
            continue
        tip = ref["tip"]
        ahead = int(git(root, "rev-list", "--count", f"{focus_tip}..{tip}").strip())
        own = int(git(root, "rev-list", "--count", f"{trunk_tip}..{tip}").strip())
        behind = int(git(root, "rev-list", "--count", f"{tip}..{trunk_tip}").strip())
        idle = age(ref["t"])
        state = "merged" if ahead == 0 else ("stale" if idle >= STILL_TAGE else "open")
        why = ("vollständig im Fokus" if state == "merged"
               else f"{ahead} Commits nicht im Fokus, {behind} hinter {trunk}")
        branches.append({"name": name, "age": idle, "ahead": ahead, "own": own, "behind": behind,
                         "t": ref["t"], "remote": ref["remote"], "state": state, "why": why})
    rank = {"stale": 0, "open": 1, "merged": 2}
    branches.sort(key=lambda b: (rank[b["state"]], -b["age"] if b["state"] != "open" else b["age"],
                                 b["name"]))

    giants = sorted(({"p": f["p"], "l": f["l"], "c": f["c"], "cc": f["cc"]} for f in files
                     if f["c"] in CODE_CATS and f["l"] > GIANT_LINES
                     and "." + f["p"].rsplit(".", 1)[-1] in CODE_EXT),
                    key=lambda g: (-g["l"], g["p"]))
    big_docs = sorted(({"p": f["p"], "kb": round(f["b"] / 1000), "l": f["l"]} for f in files
                       if f["p"].endswith(".md") and f["b"] >= BIGDOC_KB * 1000),
                      key=lambda g: (-g["kb"], g["p"]))
    todo = sum(len(MARKER_RE.findall(texts[f["p"]])) for f in files
               if f["c"] in CODE_CATS and f["p"] in texts
               and "." + f["p"].rsplit(".", 1)[-1] in CODE_EXT)
    return {"dead": dead, "orphans": orphans, "branches": branches, "giants": giants,
            "bigDocs": big_docs, "todo": todo, "method": METHODE,
            "giantLines": GIANT_LINES, "stillDays": STILL_TAGE}


def build_pipeline(root: Path, files: list[dict], functions: list[dict]) -> dict:
    """Stufen der Kette aus kette.json (einzige Quelle der Stufenliste)."""
    kette = json.loads((root / KETTE).read_text(encoding="utf-8")) if (root / KETTE).exists() else {"stufen": []}
    classes = class_names(root, files)
    stages = []
    for s in kette["stufen"]:
        paths = [p.removeprefix("src/dispread/") for p in s["anbindung"].split(",")]
        prefixes = ["src/dispread/" + p.strip() for p in paths]
        mine = [f for f in files if f["c"] in ("core", "workbench", "bridge") and any(f["p"].startswith(p) for p in prefixes)]
        funcs = [fn for fn in functions if any(fn["p"].startswith(p) for p in prefixes)]
        stage = {"id": s["id"], "name": s["titel"], "de": s["titel"],
                 "loc": sum(f["l"] for f in mine), "cc": max((fn["cc"] for fn in funcs), default=0),
                 "paths": [p.strip() for p in paths]}
        out = STUFE_AUS.get(s["id"])
        if out and out in classes:
            stage["out"] = out
        stages.append(stage)
    around = []
    for name, prefixes, role in UMFELD:
        loc = sum(f["l"] for f in files if f["c"] in ("core", "workbench", "bridge")
                  and any(f["p"].startswith(p) for p in prefixes))
        around.append({"name": name, "role": role, "loc": loc})
    return {"stages": stages, "around": around}


def class_names(root: Path, files: list[dict]) -> set[str]:
    names: set[str] = set()
    for f in files:
        if f["p"].startswith("src/dispread/") and f["p"].endswith(".py"):
            try:
                tree = ast.parse((root / f["p"]).read_text(encoding="utf-8")) \
                    if (root / f["p"]).exists() else None
            except (SyntaxError, ValueError, OSError):
                continue
            if tree:
                names.update(n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
    return names


# ------------------------------------------------- Workflows und systemd --

def tree_file(root: Path, rev: str, path: str) -> str | None:
    proc = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{path}"], capture_output=True)
    return proc.stdout.decode("utf-8", "replace") if proc.returncode == 0 else None


def tree_listing(root: Path, rev: str, directory: str) -> list[str]:
    out = git(root, "ls-tree", "--name-only", rev, directory.rstrip("/") + "/", check=False)
    return sorted(out.split())


def trigger_text(block: list[str]) -> str:
    """Auslöser aus dem `on:`-Block eines Workflows (zeilenweise, ohne YAML-Parser)."""
    parts: list[str] = []
    current = None
    for line in block:
        m = re.match(r"^  (\w+):\s*(.*)$", line)
        if m:
            current = m.group(1)
            label = {"push": "Push", "pull_request": "Pull Request", "schedule": "Zeitplan",
                     "workflow_dispatch": "manuell"}.get(current, current)
            parts.append(label)
        elif current in ("push", "pull_request") and (br := re.match(r"^    branches:\s*\[(.*?)\]", line)):
            parts[-1] += f" auf {br.group(1).replace(' ', '')}"
        elif current == "schedule":
            cron = re.search(r"cron:\s*['\"]?([^'\"]+?)['\"]?\s*$", line)
            if cron:
                parts[-1] += f" ({cron.group(1)})"
            tz = re.search(r"timezone:\s*(\S+)", line)
            if tz:
                parts[-1] = parts[-1][:-1] + f", {tz.group(1)})"
    return ", ".join(parts)


def read_workflows(root: Path, rev: str) -> list[dict]:
    out = []
    for path in tree_listing(root, rev, ".github/workflows"):
        if not path.endswith((".yml", ".yaml")):
            continue
        text = tree_file(root, rev, path) or ""
        lines = text.splitlines()
        name = next((m.group(1).strip() for ln in lines if (m := re.match(r"^name:\s*(.+)$", ln))),
                    path.rsplit("/", 1)[-1])
        block: list[str] = []
        inside = False
        for ln in lines:
            if re.match(r"^on:\s*$", ln):
                inside = True
                continue
            if inside:
                if ln and not ln.startswith(" "):
                    break
                block.append(ln)
        runner = next((m.group(1) for ln in lines if (m := re.match(r"^\s+runs-on:\s*(\S+)", ln))), "")
        steps = []
        for ln in lines:
            m = re.match(r"^\s+- name:\s*(.+)$", ln)
            if m:
                steps.append(m.group(1).strip().strip("'\""))
        out.append({"name": name, "file": path.rsplit("/", 1)[-1], "trigger": trigger_text(block),
                    "runner": runner, "steps": steps})
    return out


def read_systemd(root: Path, rev: str) -> list[dict]:
    out = []
    for path in tree_listing(root, rev, "systemd"):
        text = tree_file(root, rev, path) or ""
        m = re.search(r"(?m)^Description=(.+)$", text)
        out.append({"unit": path.rsplit("/", 1)[-1], "role": m.group(1).strip() if m else ""})
    return out


# ------------------------------------------------------------ Markdown --

def de(n: float, dec: int = 0) -> str:
    """Zahl im deutschen Format: Tausenderpunkt, Dezimalkomma."""
    s = f"{abs(n):,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return ("-" if n < 0 and float(s.replace(".", "").replace(",", ".")) != 0 else "") + s


def de_date(ts: int) -> str:
    return berlin(ts).strftime("%d.%m.%Y")


def cell(text: str) -> str:
    return str(text).replace("|", "\\|")


def table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def chart(title: str, unit: str, header: list[str], rows: list[list]) -> str:
    return (f'<div class="wiki-chart" data-chart="bar" data-title="{title}" data-unit="{unit}" '
            f'markdown="1">\n\n{table(header, rows)}\n\n</div>')


def week_series(snapshots: list[dict]) -> list[tuple[str, int]]:
    """(Beschriftung, Zeilen am Wochenende) je Kalenderwoche, fehlende Wochen mit Vorwert."""
    if not snapshots:
        return []
    by_week: dict[tuple[int, int], int] = {}
    monday: dict[tuple[int, int], datetime] = {}
    for s in snapshots:
        d = datetime.fromisoformat(s["d"])
        iso = d.isocalendar()
        key = (iso.year, iso.week)
        by_week[key] = sum(s["loc"].values())
        monday[key] = d - timedelta(days=d.weekday())
    first = min(monday.values())
    last = max(monday.values())
    out = []
    cur = first
    value = 0
    while cur <= last:
        iso = cur.isocalendar()
        key = (iso.year, iso.week)
        value = by_week.get(key, value)
        out.append((f"KW {iso.week} (ab {cur.strftime('%d.%m.')})", value))
        cur += timedelta(days=7)
    return out


def render_markdown(repo: dict) -> str:
    m = repo["meta"]
    gen = datetime.fromisoformat(m["generated"])
    lines = [f"Stand: Commit `{m['tip']}` auf `{m['focus']}`, erzeugt am {gen.strftime('%d.%m.%Y')}.", ""]
    code = sum(m["loc"][c] for c in CODE_CATS)

    # Wachstum
    snaps = repo["snapshots"]
    first_loc = sum(snaps[0]["loc"].values()) if snaps else 0
    lines += ["## Wachstum {#wachstum}", "",
              f"Der Bestand wuchs von {de(first_loc)} Zeilen am {datetime.fromisoformat(snaps[0]['d']).strftime('%d.%m.%Y')} "
              f"auf {de(m['locTotal'])} Zeilen in {de(m['files'])} Dateien; davon sind {de(code)} Code "
              f"(Kern, Werkbank, Brücke, Skripte), {de(m['loc']['tests'])} Tests und {de(m['loc']['docs'])} Doku. "
              f"Daten- und Fremddateien zählen nicht mit.", ""] if snaps else [
              "## Wachstum {#wachstum}", "", "Keine Schnappschüsse ermittelbar.", ""]
    if snaps:
        lines += [chart("Zeilen am Ende jeder Kalenderwoche", "Zeilen", ["Woche", "Zeilen"],
                        [[lab, de(v)] for lab, v in week_series(snaps)]), ""]

    # Branches
    br = repo["health"]["branches"]
    cnt = Counter(b["state"] for b in br)
    lines += ["## Branches {#branches}", "",
              f"Neben `{m['trunk']}` und dem Fokus `{m['focus']}` gibt es {de(len(br))} Refs: "
              f"{de(cnt['stale'])} still, {de(cnt['open'])} offen und {de(cnt['merged'])} gemergt. "
              f"Insgesamt enthält die Historie {de(m['commits'])} Commits und {de(m['merges'])} Merges.", ""]
    names = {"stale": "still", "open": "offen", "merged": "gemergt"}
    lines += [table(["Branch", "Zustand", "Commits (nicht im Fokus)", "letzter Commit"],
                    [[f"`{b['name']}`", names[b["state"]], de(b["ahead"]), de_date(b["t"])] for b in br]), ""]

    # Rhythmus
    per_wd = [sum(row) for row in repo["heat"]]
    total = sum(per_wd)
    peak_wd = max(range(7), key=lambda i: per_wd[i])
    hours = [sum(repo["heat"][d][h] for d in range(7)) for h in range(24)]
    peak_h = max(range(24), key=lambda h: hours[h])
    lines += ["## Rhythmus {#rhythmus}", "",
              f"{WOCHENTAGE[peak_wd]} ist mit {de(per_wd[peak_wd])} von {de(total)} Commits "
              f"({de(per_wd[peak_wd] / total * 100 if total else 0)} %) der stärkste Tag, "
              f"die Spitzenstunde liegt bei {peak_h:02d} Uhr ({de(hours[peak_h])} Commits). "
              f"An {de(m['activeDays'])} von {de(m['days'])} Tagen gab es Commits (Zeiten in Berlin).", ""]
    lines += [chart("Commits je Wochentag", "Commits", ["Wochentag", "Commits", "Anteil"],
                    [[WOCHENTAGE[i], de(per_wd[i]), de(per_wd[i] / total * 100 if total else 0) + " %"]
                     for i in range(7)]), ""]

    # Struktur
    by_cat = defaultdict(list)
    for f in repo["files"]:
        by_cat[f["c"]].append(f)
    rows = []
    for c, label in CATS:
        fs = by_cat[c]
        big = max(fs, key=lambda f: f["l"], default=None)
        rows.append([label, de(m["loc"][c]), de(len(fs)),
                     f"`{big['p']}` ({de(big['l'])})" if big else "–"])
    biggest = max(CATS, key=lambda cl: m["loc"][cl[0]])
    lines += ["## Struktur {#struktur}", "",
              f"Die {de(m['files'])} Dateien verteilen sich auf sieben Bereiche; "
              f"am größten ist „{biggest[1]}“ mit {de(m['loc'][biggest[0]])} Zeilen. "
              f"Auf Tests kommen {de(m['loc']['tests'] / code if code else 0, 2)} Zeilen je Codezeile.", ""]
    lines += [chart("Zeilen je Bereich", "Zeilen", ["Bereich", "Zeilen", "Dateien", "größte Datei (Zeilen)"], rows), ""]

    # Komplexität
    top = repo["functions"][:12]
    share = m["over10"] / m["fnTotal"] * 100 if m["fnTotal"] else 0
    lines += ["## Komplexität {#komplexitaet}", "",
              f"Von {de(m['fnTotal'])} Python-Funktionen außerhalb der Tests haben {de(m['over10'])} "
              f"({de(share, 1)} %) eine Komplexität über 10 und {de(m['over40'])} über 40. "
              f"Die komplexeste ist {top[0]['n']} mit {de(top[0]['cc'])}." if top else
              "Keine Funktionen ermittelbar.", ""]
    if top:
        lines += [chart("Die zwölf komplexesten Funktionen", "Komplexität",
                        ["Funktion", "Komplexität", "Ort", "Zeilen"],
                        [[f["n"], de(f["cc"]), f"`{f['p']}:{f['ln']}`", de(f["l"])] for f in top]), ""]

    # Zustand
    h = repo["health"]
    dead_lines = sum(d["l"] for d in h["dead"])
    lines += ["## Zustand {#zustand}", "",
              f"Die Suche findet {de(len(h['dead']))} ungenutzte Definitionen ({de(dead_lines)} Zeilen), "
              f"{de(len(h['orphans']))} verwaiste Skripte, {de(cnt['stale'])} stille Branches und "
              f"{de(len(h['giants']))} Quelldateien über {de(GIANT_LINES)} Zeilen. Das sind Hinweise zum "
              f"Aufräumen, keine geprüften Fehler.", ""]
    lines += [table(["Befund", "Anzahl", "Methode"], [
        ["Ungenutzte Definitionen", de(len(h["dead"])), h["method"]["dead"]],
        ["Verwaiste Skripte", de(len(h["orphans"])), h["method"]["orphans"]],
        ["Stille Branches", de(cnt["stale"]), h["method"]["branches"]],
        ["Gemergte Refs", de(cnt["merged"]), h["method"]["branches"]],
        [f"Riesen (> {de(GIANT_LINES)} Zeilen)", de(len(h["giants"])), h["method"]["giants"]],
        ["TODO-Marker", de(h["todo"]), h["method"]["todo"]],
    ]), ""]

    # Maschine
    st = repo["pipeline"]["stages"]
    lines += ["## Maschine {#maschine}", "",
              f"Die Kette hat {de(len(st))} Stufen mit zusammen {de(sum(s['loc'] for s in st))} Zeilen; "
              f"die Stufen stammen aus `kette.json`. {de(len(repo['workflows']))} Workflows und "
              f"{de(len(repo['systemd']))} Systemd-Units halten den Betrieb auf dem Pi.", ""]
    lines += [chart("Stufen der Kette", "Zeilen", ["Stufe", "Zeilen", "übergibt", "höchste Komplexität"],
                    [[s["name"], de(s["loc"]), s.get("out", "–"), de(s["cc"])] for s in st]), ""]
    lines += [table(["Name", "Auslöser", "Datei", "Schritte"],
                    [[w["name"], w["trigger"], f"`{w['file']}`", de(len(w["steps"]))]
                     for w in repo["workflows"]]), ""]
    if repo["systemd"]:
        lines += [table(["Unit", "Aufgabe"], [[f"`{u['unit']}`", u["role"]] for u in repo["systemd"]]), ""]
    return "\n".join(lines).rstrip() + "\n"


def replace_block(text: str, block: str) -> str:
    """Nur den Text zwischen den Markern ersetzen."""
    i, j = text.find(MARK_BEGIN), text.find(MARK_END)
    if i < 0 or j < 0 or j < i:
        raise ValueError(f"Marker {MARK_BEGIN} / {MARK_END} fehlen")
    return text[:i + len(MARK_BEGIN)] + "\n" + block.rstrip("\n") + "\n" + text[j:]


# ----------------------------------------------------------------- Aufruf --

def summary(repo: dict) -> str:
    m = repo["meta"]
    return "\n".join([
        f"Fokus {m['focus']} @ {m['tip']}: {m['commits']} Commits ({m['commitsFocus']} im Fokus, "
        f"{m['commitsMaster']} auf {m['trunk']}), {m['files']} Dateien, {m['locTotal']} Zeilen",
        f"  loc {m['loc']}",
        f"  Funktionen {m['fnTotal']} (über 10: {m['over10']}, über 40: {m['over40']}), "
        f"Tests py {m['pyTests']} / e2e {m['e2eTests']}",
        f"  Branches {m['branches']}, Merges {m['merges']}, aktive Tage {m['activeDays']}/{m['days']}",
        f"  Zustand: dead {len(repo['health']['dead'])}, orphans {len(repo['health']['orphans'])}, "
        f"branches {len(repo['health']['branches'])}, giants {len(repo['health']['giants'])}, "
        f"todo {repo['health']['todo']}",
    ])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="codebase.json und Markdown-Block schreiben")
    ap.add_argument("--focus", help="Fokus-Branch (Vorgabe: aktueller Branch, sonst HEAD)")
    ap.add_argument("--root", type=Path, default=ROOT, help="Repo-Wurzel (Vorgabe: relativ zum Skript)")
    ap.add_argument("--out-json", type=Path, help="Zielpfad der JSON-Datei")
    ap.add_argument("--out-md", type=Path, help="Zielpfad der Markdown-Seite")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    repo = collect(root, args.focus)
    print(summary(repo))
    if not args.write:
        return 0
    out_json = args.out_json or root / OUT_JSON
    out_md = args.out_md or root / OUT_MD
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(repo, separators=(",", ":"), ensure_ascii=False, sort_keys=False) + "\n",
                        encoding="utf-8")
    text = out_md.read_text(encoding="utf-8")
    out_md.write_text(replace_block(text, render_markdown(repo)), encoding="utf-8")
    print(f"geschrieben: {out_json}, {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
