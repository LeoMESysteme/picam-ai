"""Wiki-Wege werden vor dem Doku-Build in allen Quellen geprüft."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/wiki-check.py"
spec = importlib.util.spec_from_file_location("wiki_check", SCRIPT)
wiki_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wiki_check)


@pytest.mark.parametrize("weg", ["bedienen", "konfigurieren", "entwickeln", "projekt"])
def test_front_matter_weg_valid(weg: str) -> None:
    assert wiki_check.check_front_matter(f"---\nweg: {weg}\n---\n# Titel\n", "seite.md") == []


def test_front_matter_weg_unknown() -> None:
    assert wiki_check.check_front_matter("---\nweg: kunde\n---\n# Titel\n", "docs/seite.md") == [
        'docs/seite.md: weg "kunde" unbekannt (erlaubt: bedienen, konfigurieren, entwickeln, projekt)'
    ]


def test_no_front_matter_ok() -> None:
    assert wiki_check.check_front_matter("# Titel\n\n---\nweg: kunde\n---\n", "seite.md") == []


def test_only_front_matter_weg_is_checked() -> None:
    text = "---\ntitle: Beispiel\n---\n\nweg: kunde\n"
    assert wiki_check.check_front_matter(text, "seite.md") == []


def test_unclosed_block_is_not_front_matter() -> None:
    assert wiki_check.check_front_matter("---\nweg: kunde\n# Titel\n", "seite.md") == []


@pytest.fixture
def wiki_tree(tmp_path: Path) -> Path:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(SCRIPT, scripts / SCRIPT.name)
    shutil.copy2(ROOT / "scripts/docs-site.sh", scripts / "docs-site.sh")
    for name in ("README.md", "Konzept.md", "CHANGELOG.md", "AGENTS.md", "CLAUDE.md", "TODO.md", "PLANNED_FEATURES.md"):
        (tmp_path / name).write_text("# Titel\n", encoding="utf-8")
    (tmp_path / "docs/anleitung").mkdir(parents=True)
    (tmp_path / "docs/anleitung/seite.md").write_text("---\nweg: entwickeln\n---\n# Titel\n", encoding="utf-8")
    return tmp_path


def run_check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "scripts/wiki-check.py"), "--check"],
        cwd=root / "docs", capture_output=True, text=True, check=False,
    )


def test_cli_valid_is_silent(wiki_tree: Path) -> None:
    result = run_check(wiki_tree)
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""


def test_cli_reports_all_errors_in_docs_readme_and_root_docs(wiki_tree: Path) -> None:
    paths = [
        "docs/anleitung/seite.md", "README.md", "Konzept.md", "CHANGELOG.md",
        "AGENTS.md", "CLAUDE.md", "TODO.md", "PLANNED_FEATURES.md",
    ]
    for path in paths:
        (wiki_tree / path).write_text("---\nweg: kunde\n---\n# Titel\n", encoding="utf-8")
    (wiki_tree / "docs/kein-markdown.txt").write_text("---\nweg: kunde\n---\n", encoding="utf-8")

    result = run_check(wiki_tree)

    assert result.returncode == 1
    assert result.stdout == ""
    assert sorted(result.stderr.splitlines()) == sorted(
        f'{path}: weg "kunde" unbekannt (erlaubt: bedienen, konfigurieren, entwickeln, projekt)'
        for path in paths
    )
