"""Python-Seite von tests/dataset_client.test.mjs: node in pytest einhängen.

Analog zu `test_workbench_client.py`. Die eigentliche Prüfung (reine
Geometrie, kein Server nötig) steht im node-Skript; hier wird sie nur unter
pytest gefahren und `node --check` ergänzt.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).with_name("dataset_client.test.mjs")
SCRIPT = Path(__file__).parents[1] / "src" / "dispread" / "workbench" / "static" / "dataset.js"


def test_dataset_boxtransform_regressionen():
    node = shutil.which("node")
    if node is None:  # pragma: no cover - Entwicklungsumgebung ohne node
        pytest.skip("node nicht verfuegbar")
    result = subprocess.run(
        [node, str(HARNESS)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=HARNESS.parent.parent,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_dataset_javascript_ist_syntaktisch_gueltig():
    node = shutil.which("node")
    if node is None:  # pragma: no cover
        pytest.skip("node nicht verfuegbar")
    result = subprocess.run([node, "--check", str(SCRIPT)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
