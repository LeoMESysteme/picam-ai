"""Tests für scripts/codebase-facts.py (Codebase-Übersicht aus Git und Quelltext).

Die Git-abhängigen Tests bauen ein kleines temporäres Repo; das echte Repo
wird nicht angefasst.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

SCHLUESSEL = {"meta", "cats", "snapshots", "perday", "commits", "lanes", "files", "functions",
              "hist", "graph", "mods", "modEdges", "heat", "health", "pipeline", "workflows",
              "systemd"}


@pytest.fixture(scope="module")
def cf():
    spec = importlib.util.spec_from_file_location("codebase_facts", ROOT / "scripts/codebase-facts.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str, when: str | None = None) -> None:
    env = dict(os.environ, GIT_AUTHOR_NAME="Tester", GIT_AUTHOR_EMAIL="t@example.org",
               GIT_COMMITTER_NAME="Tester", GIT_COMMITTER_EMAIL="t@example.org")
    if when:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


@pytest.fixture()
def repo(tmp_path):
    """Zwei Commits: einer vor, einer nach dem Ende der Sommerzeit (25.10.2026)."""
    r = tmp_path / "repo"
    (r / "src/dispread").mkdir(parents=True)
    (r / "tests").mkdir()
    (r / "docs").mkdir()
    _git(r.parent, "init", "-q", "-b", "master", str(r))
    (r / "src/dispread/a.py").write_text("def f(x):\n    if x:\n        return 1\n    return 2\n\n"
                                         "def unbenutzt_xyz():\n    return 0\n", encoding="utf-8")
    (r / "tests/test_a.py").write_text("from dispread.a import f\n\n\ndef test_f():\n    assert f(1)\n",
                                       encoding="utf-8")
    (r / "docs/x.md").write_text("# Titel\n\nText\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "eins", when="2026-10-24T23:30:00+02:00")
    (r / "src/dispread/b.py").write_text("from dispread import a\n\nVALUE = a.f(1)\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "zwei", when="2026-10-26T00:30:00+01:00")
    return r


def _cc(cf, code: str) -> int:
    func = next(n for n in ast.walk(ast.parse(textwrap.dedent(code))) if isinstance(n, ast.FunctionDef))
    return cf.complexity(func)


def test_mccabe_beispiele(cf):
    assert _cc(cf, "def f():\n    return 1\n") == 1
    assert _cc(cf, "def f(a):\n    if a:\n        return 1\n    elif a is None:\n        return 2\n    return 3\n") == 3
    assert _cc(cf, "def f(xs):\n    for x in xs:\n        if x and x > 1 or x < -1:\n            pass\n") == 5
    assert _cc(cf, "def f(a):\n    try:\n        pass\n    except ValueError:\n        pass\n"
                   "    except KeyError:\n        pass\n    return 1 if a else 2\n") == 4
    assert _cc(cf, "def f(xs):\n    return [x for x in xs if x if x > 1]\n") == 4


def test_verschachtelte_funktion_zaehlt_getrennt(cf):
    src = "def aussen(a):\n    def innen(b):\n        if b:\n            return 1\n        return 0\n    return innen\n"
    funcs = {f["n"]: f["cc"] for f in cf.analyse_python(src, "x.py", "core")}
    assert funcs == {"aussen": 1, "aussen.innen": 2}


def test_deutsches_zahlenformat(cf):
    assert cf.de(206538) == "206.538"
    assert cf.de(1234567) == "1.234.567"
    assert cf.de(11.76, 1) == "11,8"
    assert cf.de(0.5, 2) == "0,50"
    assert cf.de(0) == "0"


def test_berlin_zeit_vor_und_nach_sommerzeitende(cf):
    # 25.10.2026: Ende der Sommerzeit (MESZ -> MEZ)
    vor = cf.berlin(1792792800)    # 2026-10-23T22:00:00Z
    nach = cf.berlin(1793138400)   # 2026-10-27T22:00:00Z
    assert (vor.date().isoformat(), vor.hour, vor.utcoffset().total_seconds()) == ("2026-10-24", 0, 7200)
    assert (nach.date().isoformat(), nach.hour, nach.utcoffset().total_seconds()) == ("2026-10-27", 23, 3600)


def test_kategorien(cf):
    assert cf.categorize("src/dispread/records.py") == "core"
    assert cf.categorize("src/dispread/live/setup.py") == "workbench"
    assert cf.categorize("windows/bridge/src/x/app.py") == "bridge"
    assert cf.categorize("windows/bridge/README.md") == "docs"
    assert cf.categorize("tests/test_x.py") == "tests"
    assert cf.categorize("tests/fixtures/a.json") == "data"
    assert cf.categorize("src/dispread/workbench/static/vendor/fonts/a.woff2") == "vendor"
    assert cf.categorize("scripts/x.py") == "scripts"
    assert cf.categorize("pyproject.toml") == "infra"
    assert cf.categorize("docs/uebersicht/a.md") == "docs"


def test_schema_und_summen(cf, repo):
    data = cf.collect(repo, "master")
    assert SCHLUESSEL <= set(data)
    m = data["meta"]
    for cat in cf.LOC_CATS:
        assert m["loc"][cat] == sum(f["l"] for f in data["files"] if f["c"] == cat)
    assert m["locTotal"] == sum(m["loc"].values())
    assert m["files"] == len(data["files"]) == 4
    assert m["commits"] == 2 and m["focus"] == "master" and len(m["tip"]) == 7
    assert [c["label"] for c in data["cats"]][:3] == ["Kern", "Werkbank & Live", "Windows-Brücke"]
    assert sum(sum(row) for row in data["heat"]) == 2
    assert m["pyTests"] == 1
    assert data["modEdges"] == [["dispread.b", "dispread.a"]]
    assert data["health"]["dead"][0]["p"] == "src/dispread/a.py"
    assert data["health"]["dead"][0]["n"] == "unbenutzt_xyz()"
    assert set(data["health"]["method"]) >= {"dead", "orphans", "branches", "giants", "todo"}


def test_berlin_tage_im_repo(cf, repo):
    data = cf.collect(repo, "master")
    # 23:30 MESZ am 24.10. und 00:30 MEZ am 26.10. liegen auf Berlins Kalendertagen
    assert [d["d"] for d in data["perday"]] == ["2026-10-24", "2026-10-26"]
    assert data["heat"][5][23] == 1      # Samstag 23 Uhr
    assert data["heat"][0][0] == 1       # Montag 0 Uhr


def test_markdown_block_ersetzt_nur_zwischen_markern(cf, repo, tmp_path):
    data = cf.collect(repo, "master")
    md = cf.render_markdown(data)
    assert md.startswith(f"Stand: Commit `{data['meta']['tip']}` auf `master`, erzeugt am ")
    for anker in ("wachstum", "branches", "rhythmus", "struktur", "komplexitaet", "zustand", "maschine"):
        assert "{#" + anker + "}" in md
    assert 'class="wiki-chart" data-chart="bar"' in md
    seite = f"Kopf\n\n{cf.MARK_BEGIN}\nalt\n{cf.MARK_END}\n\nFuß\n"
    neu = cf.replace_block(seite, "NEU\n")
    assert neu == f"Kopf\n\n{cf.MARK_BEGIN}\nNEU\n{cf.MARK_END}\n\nFuß\n"
    with pytest.raises(ValueError):
        cf.replace_block("ohne Marker", "x")


def test_write_schreibt_beide_ausgaben(cf, repo, tmp_path):
    out_json, out_md = tmp_path / "o.json", tmp_path / "o.md"
    out_md.write_text(f"vorher\n{cf.MARK_BEGIN}\nalt\n{cf.MARK_END}\nnachher\n", encoding="utf-8")
    assert cf.main(["--root", str(repo), "--focus", "master", "--write",
                    "--out-json", str(out_json), "--out-md", str(out_md)]) == 0
    assert out_json.read_text(encoding="utf-8").startswith('{"meta":')
    text = out_md.read_text(encoding="utf-8")
    assert text.startswith("vorher\n") and text.endswith("nachher\n") and "alt\n" not in text
