"""`scripts/oq-index.py` - Uebersichtstabelle in docs/open-questions.md.

Der Test gegen die echte Datei ist der eigentliche Zweck: er faellt, sobald
ein OQ hinzukommt oder seinen Status wechselt, ohne dass die Tabelle neu
erzeugt wurde. Abhilfe steht in der Fehlermeldung.

Muster fuer das Laden des Skripts per importlib aus `tests/test_gate_label.py`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "oq-index.py"

_spec = importlib.util.spec_from_file_location("oq_index", SCRIPT)
oq_index = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oq_index)

SAMPLE = f"""# Offene Punkte

{oq_index.START}
{oq_index.END}

## OQ-01 — Welches Format?

* **Status:** offen · **Zuständig:** intern

## OQ-02 — Grenze a|b?

* **Status:** **teilweise geklärt 2026-09-23.** Punkt (a) ist entschieden.

## OQ-03 — Geklärt mit Datum

* **Status:** geklärt (2026-09-07) — durch die Inbetriebnahme.
* **Status:** offen (spätere Zeile zählt nicht)

## OQ-04 — Ohne Statuszeile
"""


def test_parse_entries_status_und_titel():
    assert oq_index.parse_entries(SAMPLE) == [
        ("OQ-01", "offen", "Welches Format?"),
        ("OQ-02", "teilweise geklärt 2026-09-23", "Grenze a|b?"),
        ("OQ-03", "geklärt", "Geklärt mit Datum"),
        ("OQ-04", "?", "Ohne Statuszeile"),
    ]


def test_update_text_ist_idempotent_und_escaped_pipes():
    once = oq_index.update_text(SAMPLE)
    assert "| OQ-02 | teilweise geklärt 2026-09-23 | Grenze a/b? |" in once
    assert oq_index.update_text(once) == once


def test_update_text_ohne_marker_wirft():
    with pytest.raises(ValueError):
        oq_index.update_text("## OQ-01 — x\n")


def test_tabelle_in_open_questions_ist_aktuell():
    text = oq_index.DEFAULT_PATH.read_text(encoding="utf-8")
    assert oq_index.update_text(text) == text, (
        "OQ-Tabelle in docs/open-questions.md ist veraltet: "
        "./.venv/bin/python scripts/oq-index.py ausfuehren"
    )
