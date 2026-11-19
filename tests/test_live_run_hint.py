"""Angepasste Lesetoleranz als gleichwertige Wahl (Leonhard, 2026-11-18).

Ist die angepasste Toleranz moeglich, sperrt das Gegenlesen den Lauf nicht mehr;
ein Lauf mit Standardtoleranz bleibt erlaubt und bekommt einen Hinweis. Echte
Sperren (Widerspruch zur Referenz, Toleranz unmoeglich) bleiben.
"""
import pytest

from dispread.live.service import run_block_reason, run_hint_reason


def _proposal(status, *, possible=None, factor=1.54, contradictions=(), read=0):
    metrics = {"frames": 2, "read_count": read, "rejection_reasons": {} if status == "OK" else {"zelle_unbekannt": 2},
               "contradictions": list(contradictions)}
    if possible is not None:
        metrics["tolerance"] = {"possible": possible, "factor": factor if possible else None}
    return {"setup_checks": {"checks": {"gegenlesen": {"status": status, "metrics": metrics}}}}


def test_ok_reader_check_neither_blocks_nor_hints():
    proposal = _proposal("OK", read=2)
    assert run_block_reason(proposal) is None
    assert run_hint_reason(proposal) is None


def test_possible_tolerance_turns_block_into_hint():
    proposal = _proposal("WARNUNG", possible=True)
    assert run_block_reason(proposal) is None
    hint = run_hint_reason(proposal)
    assert hint is not None
    assert "0 von 2" in hint and "×1.54" in hint and "unlesbare" in hint


@pytest.mark.parametrize("proposal", [
    _proposal("WARNUNG", possible=False),
    _proposal("WARNUNG"),
    _proposal("FEHLER", possible=True,
              contradictions=[{"cell": 3, "read": "5", "reference": "6"}]),
    {"setup_checks": {"checks": {}}},
])
def test_real_blocks_stay_and_carry_no_hint(proposal):
    block = run_block_reason(proposal)
    assert block is not None and block.startswith("Lauf gesperrt")
    assert run_hint_reason(proposal) is None
