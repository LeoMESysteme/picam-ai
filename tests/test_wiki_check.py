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


SETTING = """<div class="wiki-setting" markdown="1">

| Einstellung | `Beispiel` |
| --- | --- |
| Wozu | Beschreibung |
| Im Hintergrund | Beschreibung |
| Standard | Beschreibung |
| Ändern? | **Nur wenn** erforderlich. |
| Quelle | [Quelle](quelle.md) |

</div>
"""

SEAM = """<div class="wiki-seam" markdown="1">

| Trennstelle | `Beispiel` |
| --- | --- |
| Vertrag | Beschreibung |
| Darf geändert werden | Beschreibung |
| Bleibt unverändert | Beschreibung |
| Tests | [Tests](tests.md) |

```python
beispiel = "| keine Tabellenzeile |"
```

</div>
"""


@pytest.mark.parametrize("row", ["Wozu", "Im Hintergrund", "Standard", "Ändern?", "Quelle"])
def test_setting_rows_complete(row: str) -> None:
    text = "\n".join(line for line in SETTING.splitlines() if not line.startswith(f"| {row} |"))
    assert wiki_check.check_patterns("# Titel\n\n" + text, "docs/seite.md") == [
        f'docs/seite.md:3: wiki-setting fehlt Zeile "{row}"'
    ]


@pytest.mark.parametrize("verdict", ["Vielleicht", "**Vielleicht**", "Nein", "Nur wenn", "Ja", "Text **Nein**"])
def test_setting_verdict_word(verdict: str) -> None:
    text = SETTING.replace("**Nur wenn** erforderlich.", verdict)
    assert wiki_check.check_patterns(text, "docs/seite.md") == [
        'docs/seite.md:8: wiki-setting Zeile "Ändern?" muss mit **Nein**, **Nur wenn** oder **Ja** beginnen'
    ]


@pytest.mark.parametrize("verdict", ["Nein", "Nur wenn", "Ja"])
def test_setting_valid(verdict: str) -> None:
    text = SETTING.replace("**Nur wenn**", f"**{verdict}**")
    assert wiki_check.check_patterns(text, "docs/seite.md") == []


@pytest.mark.parametrize("row", ["Vertrag", "Darf geändert werden", "Bleibt unverändert", "Tests"])
def test_seam_rows_complete(row: str) -> None:
    text = "\n".join(line for line in SEAM.splitlines() if not line.startswith(f"| {row} |"))
    assert wiki_check.check_patterns(text, "docs/seite.md") == [
        f'docs/seite.md:1: wiki-seam fehlt Zeile "{row}"'
    ]


def test_seam_valid_with_optional_code_block() -> None:
    assert wiki_check.check_patterns(SEAM, "docs/seite.md") == []


@pytest.mark.parametrize("text,header", [(SETTING, "Einstellung"), (SEAM, "Trennstelle")], ids=["setting", "seam"])
def test_pattern_header_required(text: str, header: str) -> None:
    errors = wiki_check.check_patterns(text.replace(f"| {header} |", "| Titel |"), "seite.md")
    assert len(errors) == 1
    assert header in errors[0]


@pytest.mark.parametrize(
    "text,first,second", [(SETTING, "Wozu", "Standard"), (SEAM, "Vertrag", "Tests")], ids=["setting", "seam"]
)
def test_pattern_rows_in_fixed_order(text: str, first: str, second: str) -> None:
    text = text.replace(f"| {first} |", "| Platzhalter |").replace(f"| {second} |", f"| {first} |")
    text = text.replace("| Platzhalter |", f"| {second} |")
    errors = wiki_check.check_patterns(text, "seite.md")
    assert len(errors) == 1
    assert "Reihenfolge" in errors[0]


@pytest.mark.parametrize(
    "text,expected",
    [
        (SETTING, "seite.md:3: wiki-setting Tabelle muss zweispaltig sein"),
        (SEAM, "seite.md:3: wiki-seam Tabelle muss zweispaltig sein"),
    ],
    ids=["setting", "seam"],
)
def test_pattern_table_must_have_two_columns(text: str, expected: str) -> None:
    errors = wiki_check.check_patterns(text.replace("`Beispiel` |", "`Beispiel` | Zusatz |"), "seite.md")
    assert errors == [expected]


def test_pattern_escaped_pipe_in_cell_is_not_a_column() -> None:
    text = SETTING.replace("| Wozu | Beschreibung |", r"| Wozu | Links \| rechts |")
    assert wiki_check.check_patterns(text, "seite.md") == []


def test_patterns_do_not_consume_next_block() -> None:
    text = SETTING.replace("| Quelle | [Quelle](quelle.md) |\n", "") + "\n" + SETTING
    assert wiki_check.check_patterns(text, "seite.md") == ['seite.md:1: wiki-setting fehlt Zeile "Quelle"']


def test_patterns_ignore_fenced_examples_and_unrelated_tables() -> None:
    text = '```html\n<div class="wiki-setting" markdown="1">\n\n| Wozu | Beispiel |\n\n</div>\n```\n'
    text += '\n| Ändern? | Vielleicht |\n'
    assert wiki_check.check_patterns(text, "seite.md") == []


@pytest.mark.parametrize("text,kind", [(SETTING, "wiki-setting"), (SEAM, "wiki-seam")])
@pytest.mark.parametrize("following", ["", SETTING, '<div class="fremd">\nFremder Inhalt\n</div>\n'])
def test_pattern_missing_closing_div(text: str, kind: str, following: str) -> None:
    text = "# Titel\n\n" + text.replace("</div>\n", "") + "\n" + following
    assert wiki_check.check_patterns(text, "docs/seite.md") == [
        f"docs/seite.md:3: {kind} ohne schließendes </div>"
    ]


@pytest.mark.parametrize("kind", ["wiki-setting", "wiki-seam"])
@pytest.mark.parametrize("ticks", ["`", "``"])
def test_pattern_opener_in_inline_code_ignored(kind: str, ticks: str) -> None:
    text = f'Die Hülle {ticks}<div class="{kind}" markdown="1">{ticks} ist ein Beispiel.\n\n</div>\n'
    assert wiki_check.check_patterns(text, "seite.md") == []


@pytest.mark.parametrize("text", [SETTING, SEAM], ids=["setting", "seam"])
def test_pattern_indented_opener_valid(text: str) -> None:
    assert wiki_check.check_patterns("  " + text, "seite.md") == []


@pytest.mark.parametrize("closed", [True, False])
def test_pattern_closing_div_in_table_is_not_block_end(closed: bool) -> None:
    text = SETTING.replace("| Wozu | Beschreibung |", "| Wozu | Literal `</div>` |")
    if not closed:
        text = text.removesuffix("</div>\n")
    expected = [] if closed else ["seite.md:1: wiki-setting ohne schließendes </div>"]
    assert wiki_check.check_patterns(text, "seite.md") == expected


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


def test_cli_checks_patterns_in_same_sources_as_front_matter(wiki_tree: Path) -> None:
    paths = [
        "docs/anleitung/seite.md", "README.md", "Konzept.md", "CHANGELOG.md",
        "AGENTS.md", "CLAUDE.md", "TODO.md", "PLANNED_FEATURES.md",
    ]
    text = SETTING.replace("| Quelle | [Quelle](quelle.md) |\n", "")
    for path in paths:
        (wiki_tree / path).write_text(text, encoding="utf-8")
    (wiki_tree / "docs/kein-markdown.txt").write_text(text, encoding="utf-8")

    result = run_check(wiki_tree)

    assert result.returncode == 1
    assert result.stdout == ""
    assert sorted(result.stderr.splitlines()) == sorted(
        f'{path}:1: wiki-setting fehlt Zeile "Quelle"' for path in paths
    )


GLOSSARY = """# Glossar

## Bildverarbeitung

### ROI {#roi}

Der bestätigte Anzeigebereich.

*Weg:* Bedienen · *Auch:* Region of Interest, Anzeigebereich · *Quelle:* [Konzept](../../Konzept.md)
"""


def test_glossary_valid() -> None:
    assert wiki_check.check_glossary(GLOSSARY) == []


def test_glossary_meta_required() -> None:
    text = GLOSSARY.split("*Weg:*")[0]
    assert wiki_check.check_glossary(text) == ["glossar.md:5: ROI: Metazeile fehlt / falsche Form"]


@pytest.mark.parametrize("weg", ["Projekt", "bedienen", "Unbekannt"])
def test_glossary_weg_values(weg: str) -> None:
    assert wiki_check.check_glossary(GLOSSARY.replace("Bedienen", weg)) == [
        f'glossar.md:9: ROI: Weg unbekannt: {weg}'
    ]


@pytest.mark.parametrize("source", ["Konzept", "[Konzept]()", "[Konzept](../../src/gate.py)"])
def test_glossary_source_link(source: str) -> None:
    errors = wiki_check.check_glossary(GLOSSARY.replace("[Konzept](../../Konzept.md)", source))
    assert len(errors) == 1
    assert "Quelle ohne Link auf eine Wiki-Seite" in errors[0]


@pytest.mark.parametrize("length", [280, 281])
def test_glossary_short_length(length: int) -> None:
    errors = wiki_check.check_glossary(GLOSSARY.replace("Der bestätigte Anzeigebereich.", "x" * length))
    assert errors == ([] if length == 280 else ["glossar.md:7: ROI: Kurzdefinition > 280 Zeichen (281)"])


def test_glossary_short_missing() -> None:
    assert wiki_check.check_glossary(GLOSSARY.replace("Der bestätigte Anzeigebereich.\n\n", "")) == [
        "glossar.md:5: ROI: Kurzdefinition fehlt"
    ]


@pytest.mark.parametrize("other", ["roi", "region of interest", "Anzeigebereich"])
def test_glossary_duplicate_alias(other: str) -> None:
    text = GLOSSARY + f"\n### `{other}`\n\nEin weiterer Begriff.\n\n*Weg:* Entwickeln · *Quelle:* [API](../../api/vertraege.md)\n"
    errors = wiki_check.check_glossary(text)
    assert len(errors) == 1
    assert f"Begriff oder Synonym doppelt: {other}" in errors[0]


@pytest.mark.parametrize("meta", [
    "*Quelle:* [Konzept](../../Konzept.md) · *Weg:* Bedienen",
    "*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md) · *Auch:* Bereich",
    "*Weg:* Bedienen · *Auch:* · *Quelle:* [Konzept](../../Konzept.md)",
])
def test_glossary_meta_fixed_form(meta: str) -> None:
    text = GLOSSARY[:GLOSSARY.index("*Weg:*")] + meta
    assert wiki_check.check_glossary(text) == ["glossar.md:9: ROI: Metazeile fehlt / falsche Form"]


def test_cli_checks_glossary(wiki_tree: Path) -> None:
    (wiki_tree / "docs/anleitung/glossar.md").write_text(GLOSSARY.split("*Weg:*")[0], encoding="utf-8")
    result = run_check(wiki_tree)
    assert result.returncode == 1
    assert result.stderr.strip() == "glossar.md:5: ROI: Metazeile fehlt / falsche Form"
