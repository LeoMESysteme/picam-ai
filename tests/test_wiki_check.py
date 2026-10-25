"""Wiki-Wege werden vor dem Doku-Build in allen Quellen geprüft."""

from __future__ import annotations

import importlib.util
import json
import re
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


START = """<div class="wiki-stand" markdown="1">

* **Kamera:** Stand

</div>

<div class="wiki-wege" markdown="1">

### Einrichten und bedienen

Für Bediener.

### Konfigurieren und verstehen

Für Konfigurierende.

### Entwickeln und anbinden

Für Entwickler.

</div>
"""


def test_start_has_three_ways_in_order() -> None:
    assert wiki_check.check_start(START) == []
    reversed_ways = START.replace("### Einrichten und bedienen", "### Platzhalter")
    reversed_ways = reversed_ways.replace("### Entwickeln und anbinden", "### Einrichten und bedienen")
    reversed_ways = reversed_ways.replace("### Platzhalter", "### Entwickeln und anbinden")
    errors = wiki_check.check_start(reversed_ways)
    assert len(errors) == 1
    assert "Reihenfolge" in errors[0]


def test_start_missing_stand() -> None:
    text = START[START.index('<div class="wiki-wege"'):]
    assert wiki_check.check_start(text) == ["README.md: wiki-stand fehlt oder ist nicht geschlossen"]


def test_start_missing_wege() -> None:
    text = START[:START.index('<div class="wiki-wege"')]
    assert wiki_check.check_start(text) == ["README.md: wiki-wege fehlt oder ist nicht geschlossen"]


@pytest.mark.parametrize("heading", ["Einrichten und bedienen", "Konfigurieren und verstehen", "Entwickeln und anbinden"])
def test_start_requires_exactly_three_ways_inside_wrapper(heading: str) -> None:
    text = START.replace(f"### {heading}\n", "") + f"\n### {heading}\n"
    assert len(wiki_check.check_start(text)) == 1
    assert len(wiki_check.check_start(START.replace("</div>\n", "\n### Weiterer Weg\n\n</div>\n"))) == 1


@pytest.mark.parametrize("wrapper", ["wiki-stand", "wiki-wege"])
def test_start_requires_closed_wrapper(wrapper: str) -> None:
    opening = f'<div class="{wrapper}" markdown="1">'
    before, body = START.split(opening)
    text = before + opening + body.replace("</div>", "", 1)
    assert wiki_check.check_start(text) == [f"README.md: {wrapper} fehlt oder ist nicht geschlossen"]


def test_cli_checks_start(wiki_tree: Path) -> None:
    (wiki_tree / "README.md").write_text(START[START.index('<div class="wiki-wege"'):], encoding="utf-8")
    result = run_check(wiki_tree)
    assert result.returncode == 1
    assert result.stderr.strip() == "README.md: wiki-stand fehlt oder ist nicht geschlossen"


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
    (tmp_path / "README.md").write_text(START, encoding="utf-8")
    (tmp_path / "docs/anleitung").mkdir(parents=True)
    (tmp_path / "docs/anleitung/seite.md").write_text("---\nweg: entwickeln\n---\n# Titel\n", encoding="utf-8")
    write_kette_tree(tmp_path)
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
    with (wiki_tree / "README.md").open("a", encoding="utf-8") as handle:
        handle.write("\n" + START)
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
    with (wiki_tree / "README.md").open("a", encoding="utf-8") as handle:
        handle.write("\n" + START)
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


KETTE_IDS = ('frames', 'detect', 'track', 'rectify', 'ocr', 'validate', 'sink')
KETTE_TITLES = ('Bildquelle', 'Anzeige finden', 'Nachführen', 'Entzerren', 'Wert lesen', 'Freigabe', 'Ausgabe')


def write_kette_tree(root: Path) -> dict:
    data = {'schema': 'kette_v1', 'stufen': []}
    for stage_id, title in zip(KETTE_IDS, KETTE_TITLES, strict=True):
        stage = {
            'id': stage_id, 'titel': title, 'zustand': 'fertig',
            'zweck': 'Verarbeitet das Bild.', 'einstellung': 'Bestätigtes Profil.',
            'anbindung': f'src/dispread/{stage_id}.py',
            'api': f'api/{stage_id}.html', 'doku': 'docs/anleitung/seite.html',
        }
        data['stufen'].append(stage)
        for source in (stage['anbindung'], f'docs-site/api/{stage_id}.md'):
            path = root / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
    path = root / 'docs-site/assets/data/kette.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf-8')
    return data


def test_kette_valid(wiki_tree: Path) -> None:
    data = write_kette_tree(wiki_tree)
    (wiki_tree / 'src/dispread/frames.py').unlink()
    (wiki_tree / 'src/dispread/frames').mkdir()
    data['stufen'][0]['anbindung'] = 'src/dispread/frames'
    for index, state in enumerate(('fertig', 'gebaut', 'teilweise', 'außer Betrieb')):
        data['stufen'][index]['zustand'] = state
    assert wiki_check.check_kette(data, wiki_tree) == []


def test_kette_order(wiki_tree: Path) -> None:
    data = write_kette_tree(wiki_tree)
    data['stufen'].reverse()
    assert any('Reihenfolge' in error for error in wiki_check.check_kette(data, wiki_tree))


def test_kette_missing_module(wiki_tree: Path) -> None:
    data = write_kette_tree(wiki_tree)
    (wiki_tree / 'src/dispread/ocr.py').unlink()
    errors = wiki_check.check_kette(data, wiki_tree)
    assert len(errors) == 1
    assert 'src/dispread/ocr.py' in errors[0]


@pytest.mark.parametrize('field,value', [
    ('titel', ''), ('titel', 'Anderer Titel'), ('zweck', 'x' * 161),
    ('einstellung', None), ('zustand', 'abgenommen'),
    ('anbindung', 'scripts/wiki-check.py'), ('anbindung', 'src/dispread/../../README.md'),
    ('api', 'docs/anleitung/seite.html'), ('api', 'api/fehlt.html'),
    ('api', 'api/../frames.html'), ('api', 'api/frames.md'),
    ('doku', 'api/frames.html'), ('doku', 'docs/fehlt.html'),
    ('doku', 'docs/../README.html'),
])
def test_kette_rejects_invalid_fields(wiki_tree: Path, field: str, value: object) -> None:
    data = write_kette_tree(wiki_tree)
    data['stufen'][0][field] = value
    assert any(field in error for error in wiki_check.check_kette(data, wiki_tree))


@pytest.mark.parametrize('field', ['id', 'titel', 'zustand', 'zweck', 'einstellung', 'anbindung', 'api', 'doku'])
def test_kette_requires_fields(wiki_tree: Path, field: str) -> None:
    data = write_kette_tree(wiki_tree)
    del data['stufen'][0][field]
    assert any(field in error for error in wiki_check.check_kette(data, wiki_tree))


@pytest.mark.parametrize('data', [None, [], {}, {'schema': 'falsch', 'stufen': []},
                                  {'schema': 'kette_v1', 'stufen': None},
                                  {'schema': 'kette_v1', 'stufen': [None]}])
def test_kette_rejects_invalid_schema(wiki_tree: Path, data: object) -> None:
    assert wiki_check.check_kette(data, wiki_tree)


@pytest.mark.parametrize('content', [None, '{', '{"schema": "falsch", "stufen": []}'])
def test_cli_checks_kette(wiki_tree: Path, content: str | None) -> None:
    path = wiki_tree / 'docs-site/assets/data/kette.json'
    if content is None:
        path.unlink()
    else:
        path.write_text(content, encoding='utf-8')
    result = run_check(wiki_tree)
    assert result.returncode == 1
    assert 'kette.json' in result.stderr
    assert 'Traceback' not in result.stderr


def test_kette_repository_data() -> None:
    data = json.loads((ROOT / 'docs-site/assets/data/kette.json').read_text(encoding='utf-8'))
    assert wiki_check.check_kette(data, ROOT) == []
    assert [stage['zustand'] for stage in data['stufen']] == [
        'teilweise', 'fertig', 'fertig', 'fertig', 'fertig', 'fertig', 'teilweise',
    ]


def test_chart_overview_matches_reference_entries() -> None:
    text = (ROOT / 'docs/VALIDATION.md').read_text(encoding='utf-8')
    blocks = re.findall(r'<div class="wiki-chart"[^>]*>(.*?)</div>', text, re.S)
    assert len(blocks) == 2
    def rows(block: str) -> list[list[str]]:
        return [
            [cell.strip() for cell in line.strip().strip('|').split('|')]
            for line in block.splitlines() if line.startswith('|')
        ][2:]
    assert rows(blocks[0]) == [
        ['Streng 45 s', '715', '0/715', '27,2'],
        ['Toleranz ×1,8 5,6 min', '6630', '0/6630', '29,7'],
        ['Streng 12 min', '8979', '0/8979', '29,8'],
    ]
    anchors = ['referenzlauf', 'toleranzlauf', 'langlauf']
    for row, anchor in zip(rows(blocks[0]), anchors, strict=True):
        target = f'messpfad-live-{anchor}-2026-10-21'
        section = text.split('{ #' + target + ' }', 1)[1].split('\n## ', 1)[0]
        assert f'**0 von {row[1]}** entschiedenen VALID' in section
        assert f'| Gelesene Bilder/s | {row[3]}' in section
        assert f'](#{target})' in text[:text.index('## Leserlaufzeit 2026-10-13')]
    assert rows(blocks[1]) == [
        ['Ruhige Anzeige', '99,7', '0,3', '0'],
        ['Bilder im Wechsel', '74', '24', '2'],
    ]
    source = text.split('{ #messpfad-live-langlauf-2026-10-21 }', 1)[1]
    assert '| Ruhige Anzeige | 99,7 % VALID, 0,3 % TRANSITION, kein UNREADABLE |' in source
    assert '| Bilder im Wechsel | 74 % VALID, 24 % TRANSITION, 2 % UNREADABLE, 7 STALE |' in source


def test_chart_browser_free_logic() -> None:
    if shutil.which("node") is None:
        pytest.skip("Node.js ist nicht verfügbar")
    result = subprocess.run(
        ['node', '-e', r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const sandbox = { window: { wiki: { onPage() {}, hint: { register() {} } } } };
const source = fs.readFileSync('docs-site/assets/wiki-chart.js', 'utf8');
vm.runInNewContext(source.replace(/\}\)\(\);\s*$/, 'globalThis.parseNumber = parseNumber;})();'), sandbox);
assert.equal(sandbox.parseNumber('1.234,5 %'), 1234.5);
assert.equal(sandbox.parseNumber('1 234'), 1234);
for (const invalid of ['x', '—', '0/715', '1.2', '', 'Infinity', '-1']) {
  assert.equal(sandbox.parseNumber(invalid), null, invalid);
}
"""],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
