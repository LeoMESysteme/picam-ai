"""Die Projekt-Tour zeigt Werte aus dem Code (scripts/tour-facts.py).

Schlägt `test_tour_zeigt_den_aktuellen_code` fehl, hat sich ein Wert geändert,
den eine Szene oder ein Text der Tour zeigt. Die Meldung nennt die betroffenen
Schritte; nach der Prüfung `./scripts/tour-facts.py --write` ausführen.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def facts_module():
    spec = importlib.util.spec_from_file_location("tour_facts", ROOT / "scripts/tour-facts.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_tour_zeigt_den_aktuellen_code(facts_module):
    stored = json.loads(facts_module.OUT.read_text(encoding="utf-8"))
    diff = facts_module.differences(facts_module.collect(), stored)
    assert not diff, "\n".join(diff)


def test_jeder_fakt_nennt_vorhandene_tour_schritte(facts_module):
    steps = facts_module.tour_step_ids()
    for fact_id, (_source, used_by, _read) in facts_module.FACTS.items():
        assert used_by, fact_id
        assert set(used_by) <= steps, (fact_id, sorted(set(used_by) - steps))


def test_abweichung_nennt_die_betroffenen_schritte(facts_module):
    current = facts_module.collect()
    stored = json.loads(json.dumps(current))
    stored["facts"]["gate.stale_after_ns"]["value"] = 250_000_000
    diff = facts_module.differences(current, stored)
    assert len(diff) == 1
    assert "gate.stale_after_ns" in diff[0]
    assert "erkennung-veraltet" in diff[0]


def test_fehlende_fundstelle_wird_gemeldet_statt_geraten(facts_module):
    with pytest.raises(facts_module.FactError):
        facts_module.module_constant("src/dispread/records.py", "GIBT_ES_NICHT")


def test_alle_regel_tests_existieren(facts_module):
    present = facts_module.collect()["facts"]["tests.regeln"]["value"]
    assert all(present.values()), [name for name, path in present.items() if not path]
