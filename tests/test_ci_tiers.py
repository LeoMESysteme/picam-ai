"""Konsistenz der Teststufen: Mapping scripts/test-map.toml und Eskalationsregeln.

Prueft, dass jede Quelle unter src/dispread einer Testauswahl zugeordnet ist
(Namenskonvention, Mapping, explizit 'voll' oder Kernpfad), dass kein
Mapping-Eintrag ins Leere zeigt, und die Eskalationsregeln von
scripts/test-select.py mit synthetischen Dateilisten.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses braucht das Modul in sys.modules
    spec.loader.exec_module(mod)
    return mod


ts = _load("picam_test_select_under_test", "test-select.py")
MAPPING = ts.load_map()


def _sources() -> list[str]:
    return sorted(
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "src" / "dispread").rglob("*.py")
        if "__pycache__" not in p.parts
    )


@pytest.mark.parametrize("source", _sources())
def test_jede_quelle_ist_zugeordnet(source):
    if ts.match_any(source, ts.CORE_PATTERNS) or ts.match_any(source, MAPPING["full"]):
        return
    mapped = ts.match_any(source, MAPPING["map"])
    globs = list(MAPPING["map"][mapped]) if mapped else []
    globs += ts.convention_globs(source)
    assert ts.expand_tests(globs), (
        f"{source} hat keine Testzuordnung: Test nach Konvention benennen oder in "
        "scripts/test-map.toml unter [map] bzw. [full] eintragen"
    )


def test_mapping_hat_keine_verwaisten_eintraege():
    problems = []
    for pattern, globs in MAPPING["map"].items():
        if not _fn_matches(pattern):
            problems.append(f"Quellmuster ohne Datei: {pattern}")
        for g in globs:
            if not ts.expand_tests([g]):
                problems.append(f"{pattern}: Test-Glob ohne Treffer: {g}")
    for pattern in MAPPING["full"]:
        if not _fn_matches(pattern):
            problems.append(f"[full]-Muster ohne Datei: {pattern}")
    assert not problems, "\n".join(problems)


def _fn_matches(pattern: str) -> bool:
    """fnmatch-Muster gegen alle versionierbaren Dateien (ohne Cache/venv)."""
    skip = {"__pycache__", ".git", ".venv", ".venv-tools", ".venv-docs", "node_modules", ".worktrees", "site", "var",
            "test-results"}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip]
        rel_dir = Path(dirpath).relative_to(ROOT)
        for name in filenames:
            if ts.match_any((rel_dir / name).as_posix(), [pattern]):
                return True
    return False


# --- Eskalationsregeln mit synthetischen Dateilisten -------------------------


def _sel(files, mapping=None):
    return ts.select(files, MAPPING if mapping is None else mapping)


@pytest.mark.parametrize(
    "core",
    [
        "src/dispread/pipeline.py",
        "src/dispread/rectify.py",
        "src/dispread/ocr/sevenseg.py",
        "src/dispread/validate.py",
        "src/dispread/records.py",
        "src/dispread/live/tick.py",
        "pyproject.toml",
        "tests/conftest.py",
        "packaging/release.py",
        "scripts/ci.py",
    ],
)
def test_kernpfad_eskaliert_auf_voll(core):
    dec = _sel([core])
    assert dec.level == "full"
    assert dec.reasons[0].startswith("voll, weil Kernpfad")


def test_kleine_aenderung_waehlt_nur_zugehoerige_tests():
    dec = _sel(["src/dispread/bridge/hub.py"])
    assert dec.level == "focused"
    assert dec.tests == ["tests/test_bridge_hub.py"]


def test_geaenderte_testdatei_laeuft_selbst():
    dec = _sel(["tests/test_jsonl_sink.py"])
    assert dec.level == "focused" and dec.tests == ["tests/test_jsonl_sink.py"]


def test_mehr_als_25_dateien_eskaliert():
    files = [f"docs/seite{i}.txt" for i in range(26)]
    dec = _sel(files)
    assert dec.level == "full" and "26 Dateien" in dec.reasons[0]


def test_genau_25_dateien_eskaliert_nicht():
    assert _sel([f"docs/seite{i}.txt" for i in range(25)]).level == "none"


def test_mehr_als_3_bereiche_eskaliert():
    dec = _sel(
        [
            "src/dispread/bridge/hub.py",
            "src/dispread/sink/jsonl.py",
            "src/dispread/frames/replay_source.py",
            "src/dispread/admin/tui.py",
        ]
    )
    assert dec.level == "full" and "4 Bereiche" in dec.reasons[0]


def test_drei_bereiche_bleiben_fokussiert():
    dec = _sel(["src/dispread/bridge/hub.py", "src/dispread/sink/jsonl.py", "src/dispread/frames/replay_source.py"])
    assert dec.level == "focused"


def test_quelle_ohne_mapping_faellt_auf_voll_zurueck():
    dec = _sel(["src/dispread/gibt_es_nicht.py"])
    assert dec.level == "full" and "ohne Test-Zuordnung" in dec.reasons[0]


def test_explizit_als_voll_markierte_quelle():
    dec = _sel(["src/dispread/paths.py"])
    assert dec.level == "full" and "'voll' markiert" in dec.reasons[0]


def test_mapping_ergaenzt_konvention():
    mapping = {"full": {}, "map": {"src/dispread/gibt_es_nicht.py": ["tests/test_jsonl_sink.py"]}}
    dec = _sel(["src/dispread/gibt_es_nicht.py"], mapping)
    assert dec.level == "focused" and dec.tests == ["tests/test_jsonl_sink.py"]


def test_nur_doku_braucht_keine_tests():
    dec = _sel(["docs/status.md", "README.md"])
    assert dec.level == "none" and dec.tests == []


def test_gemeinsame_testhilfe_eskaliert():
    assert _sel(["tests/devdata_helpers.py"]).level == "full"
    assert _sel(["tests/fixtures/cell_text_cases.json"]).level == "full"


def test_leere_liste():
    assert _sel([]).level == "none"


def test_konvention_scripts():
    assert ts.convention_globs("scripts/oq-index.py") == ["tests/test_oq_index*.py"]
    assert ts.convention_globs("src/dispread/live/tick.py") == ["tests/test_live_tick*.py", "tests/test_tick*.py"]
