"""Konsistenz der CI-Workflows mit scripts/ci.py und docs/ci-failures.md.

Prueft: jeder Workflow ruft nur existierende ci.py-Stufen und -Gruppen auf, jeder in ci.py
referenzierte Katalog-Anker existiert, die neuen ci-*.yml haben concurrency, permissions
und je Job timeout-minutes. Die aelteren Workflows (docs, playwright, docs-maintenance)
sind bewusst nicht Teil der Pflichtpruefung.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
CI_WORKFLOWS = [p for p in WORKFLOWS if p.name.startswith("ci-")]
CI_CALL = re.compile(r"scripts/ci\.py\s+([^\s\"]+)(.*)")
CATALOG = ROOT / "docs" / "ci-failures.md"


def _load_ci():
    spec = importlib.util.spec_from_file_location("picam_ci_under_test", ROOT / "scripts" / "ci.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


ci = _load_ci()


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _run_blocks(doc: dict):
    for job in doc["jobs"].values():
        for step in job.get("steps", []):
            if "run" in step:
                yield step["run"]


def test_ci_workflows_vorhanden():
    names = {p.name for p in CI_WORKFLOWS}
    assert {"ci-fokussiert.yml", "ci-voll.yml", "ci-release.yml", "ci-nightly.yml"} <= names


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_yaml_parst(path):
    assert isinstance(_load(path).get("jobs"), dict)


@pytest.mark.parametrize("path", CI_WORKFLOWS, ids=lambda p: p.name)
def test_ruft_nur_existierende_stufen(path):
    calls = [m for block in _run_blocks(_load(path)) for m in CI_CALL.findall(block)]
    assert calls, f"{path.name} ruft scripts/ci.py nicht auf"
    for tier, rest in calls:
        assert tier in ci.TIERS, f"{path.name}: unbekannte Stufe {tier!r}"
        for opt in ("--only", "--skip"):
            m = re.search(opt + r"\s+([^\s\"]+)", rest)
            if m:
                unknown = set(m.group(1).split(",")) - set(ci.GROUPS)
                assert not unknown, f"{path.name}: unbekannte Gruppe(n) {sorted(unknown)}"


@pytest.mark.parametrize("path", CI_WORKFLOWS, ids=lambda p: p.name)
def test_concurrency_permissions_timeout(path):
    doc = _load(path)
    assert "concurrency" in doc and "group" in doc["concurrency"], f"{path.name}: concurrency fehlt"
    assert doc.get("permissions") == {"contents": "read"}, f"{path.name}: permissions nicht minimal"
    for name, job in doc["jobs"].items():
        assert "timeout-minutes" in job, f"{path.name}: Job {name} ohne timeout-minutes"


@pytest.mark.parametrize("path", CI_WORKFLOWS, ids=lambda p: p.name)
def test_artefakt_und_summary(path):
    for name, job in yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"].items():
        steps = job["steps"]
        assert any("ci-summary.py" in s.get("run", "") for s in steps), f"{path.name}/{name}: keine Zusammenfassung"
        uploads = [s for s in steps if "upload-artifact" in s.get("uses", "")]
        assert uploads, f"{path.name}/{name}: kein Artefakt-Upload"
        assert all("cancelled()" in str(s.get("if", "")) for s in uploads)


def test_katalog_anker_existieren():
    text = CATALOG.read_text(encoding="utf-8")
    anchors = set(re.findall(r"\{#([a-z0-9-]+)\}", text))
    referenced = {hint[2] for hint in ci.HINTS.values()}
    referenced |= set(re.findall(r"ci-failures\.md#([a-z0-9-]+)", (ROOT / "scripts" / "ci.py").read_text(encoding="utf-8")))
    assert referenced, "ci.py referenziert keine Anker"
    missing = sorted(referenced - anchors)
    assert not missing, f"Anker fehlen in docs/ci-failures.md: {missing}"
    required = {"ruff", "gitleaks", "bandit", "changelog", "pytest", "playwright", "release", "perf",
                "hardware", "werkzeug-fehlt"}
    assert required <= anchors


def test_schritte_erben_keine_git_hook_umgebung(monkeypatch):
    """Hooks setzen GIT_DIR; Tests mit temporaeren Repos duerfen es nicht erben (sonst Schreibzugriff aufs echte .git/config)."""
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.setenv(k, "/irgendwo")
    pytest_env = ci.step_env("pytest")
    assert not any(k.startswith("GIT_") and k in ci.GIT_ENV_ALL + ("GIT_INDEX_FILE",) for k in pytest_env)
    sec_env = ci.step_env("security")
    assert "GIT_DIR" not in sec_env and sec_env["GIT_INDEX_FILE"] == "/irgendwo"
