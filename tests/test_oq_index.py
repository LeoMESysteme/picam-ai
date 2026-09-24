"""Die OQ-Uebersicht folgt den aktiven Aufgaben aus TODO.md."""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "oq-index.py"


def run_index(tmp_path: Path, questions: str, todo: str, *extra: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    questions_path = tmp_path / "open-questions.md"
    todo_path = tmp_path / "TODO.md"
    questions_path.write_text(questions, encoding="utf-8")
    todo_path.write_text(todo, encoding="utf-8")
    result = subprocess.run(
        [str(Path(__file__).parents[1] / ".venv/bin/python"), str(SCRIPT),
         "--path", str(questions_path), "--todo", str(todo_path), *extra],
        capture_output=True, text=True, check=False,
    )
    return result, questions_path


QUESTIONS = """# Offene Punkte

<!-- OQ-INDEX:START — erzeugt von scripts/oq-index.py, nicht von Hand bearbeiten -->
<!-- OQ-INDEX:END -->

## OQ-01 — Erste Frage
* **Status:** offen

## OQ-02 — Fertig
* **Status:** **BEANTWORTET 2026-09-22.** Antwort.

## OQ-03 — Teilantwort
* **Status:** teilweise geklärt (Rest offen)

## OQ-04 — Wird bearbeitet
* **Status:** in Arbeit
"""

TODO = """# TODO

## Aktueller Blocker — Beispiel
OQ-03 blockiert gerade.

## Die Aufgaben, in Reihenfolge
### 1. Erledigt
OQ-01 wurde in dieser Aufgabe erwähnt.

### 2. Nächster Schritt
Siehe OQ-04 und OQ-03.

### 3. Später
OQ-02 ist schon beantwortet.

## Landkarte
OQ-01 steht hier nur als Verweis.
"""


def test_focus_comes_from_active_todo_tasks(tmp_path: Path) -> None:
    result, path = run_index(tmp_path, QUESTIONS, TODO)
    assert result.returncode == 0, result.stderr
    output = path.read_text(encoding="utf-8")
    rows = [line for line in output.splitlines() if line.startswith("| [OQ-")]
    assert ["OQ-03", "OQ-04", "OQ-01", "OQ-02"] == [
        next(number for number in ("OQ-01", "OQ-02", "OQ-03", "OQ-04") if number in row)
        for row in rows
    ]
    assert output.count("Jetzt") == 2
    assert "| beantwortet |" in output
    assert '<span id="oq-03"></span>' in output
    assert "[OQ-03](#oq-03)" in output


def test_check_detects_stale_index_without_writing(tmp_path: Path) -> None:
    result, path = run_index(tmp_path, QUESTIONS, TODO, "--check")
    assert result.returncode == 1
    assert "veraltet" in result.stderr
    assert path.read_text(encoding="utf-8") == QUESTIONS


def test_unknown_status_fails_instead_of_guessing(tmp_path: Path) -> None:
    result, path = run_index(tmp_path, QUESTIONS.replace("in Arbeit", "irgendwie fertig"), TODO)
    assert result.returncode != 0
    assert "OQ-04" in result.stderr
    assert path.read_text(encoding="utf-8").count("OQ-INDEX:START") == 1


def test_status_prefix_is_not_enough_to_claim_open(tmp_path: Path) -> None:
    result, _ = run_index(tmp_path, QUESTIONS.replace("**Status:** offen", "**Status:** offenbar geklärt"), TODO)
    assert result.returncode != 0
    assert "OQ-01" in result.stderr


def test_missing_todo_sections_fail_instead_of_silently_losing_focus(tmp_path: Path) -> None:
    result, _ = run_index(tmp_path, QUESTIONS, "# TODO\n\n## Sonstiges\nOQ-03\n")
    assert result.returncode != 0
    assert "TODO" in result.stderr


def test_todo_reference_without_oq_entry_fails(tmp_path: Path) -> None:
    result, _ = run_index(tmp_path, QUESTIONS, TODO.replace("OQ-04 und OQ-03", "OQ-99 und OQ-03"))
    assert result.returncode != 0
    assert "OQ-99" in result.stderr


def test_active_heading_references_are_focus_even_without_body_repeat(tmp_path: Path) -> None:
    todo = """# TODO
## Aktueller Blocker — OQ-03
Hier steht nur die Maßnahme.
## Die Aufgaben, in Reihenfolge
### 1. OQ-04 bearbeiten
Noch offen.
### 2. Erledigt: OQ-01
Abgeschlossen.
"""
    result, path = run_index(tmp_path, QUESTIONS, todo)
    assert result.returncode == 0, result.stderr
    rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("| [OQ-")]
    assert rows[0].startswith("| [OQ-03](#oq-03) | Jetzt |")
    assert rows[1].startswith("| [OQ-04](#oq-04) | Jetzt |")
    assert "Jetzt" not in next(row for row in rows if "[OQ-01]" in row)


def test_real_oq_index_is_current() -> None:
    result = subprocess.run(
        [str(Path(__file__).parents[1] / ".venv/bin/python"), str(SCRIPT), "--check"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
