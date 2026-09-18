"""Browserteil der Workbench: Vorschau und Bestaetigung duerfen nicht auseinanderlaufen.

`workbench.js` wird von `tests/workbench_client.test.mjs` im Auslieferungsstand
gefahren (node, minimaler DOM-Ersatz). Hier steht die Python-Seite davon: die
Rastergeometrien der Fixture kommen aus `grid_geometry()` - also aus derselben
Rechnung, die der Controller an den Browser schickt. Ein in JavaScript
nachgebautes Raster wuerde genau die Abweichung verstecken, um die es geht.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from dispread.layout import DisplayLayout
from dispread.ocr.autofit import AutofitResult
from dispread.workbench.controller import grid_geometry

HARNESS = Path(__file__).with_name("workbench_client.test.mjs")


def test_autofit_antwort_traegt_das_raster_des_vorschlags(tmp_path, monkeypatch):
    """Der Server rechnet das Vorschau-Raster, nicht der Browser.

    Nur so kann zwischen gezeichnetem und bestaetigtem Raster nichts
    auseinanderlaufen: beide stammen aus demselben `layout` (Review-Fund).
    """
    from test_workbench import ready_controller

    controller = ready_controller(tmp_path)
    frozen = controller.command("freeze")
    proposed = DisplayLayout(digits=5, decimals=1, has_sign=True, unit="V", digit_gap_ratio=0.65)

    def fake_fit(*_args, **_kwargs):
        return AutofitResult(
            matched=True,
            layout=proposed,
            ocr_box=(0.12, 0.14, 0.75, 0.72),
            separation=0.3,
            runner_up=0.1,
            flat_optimum=False,
            evaluated=42,
            reason=None,
        )

    monkeypatch.setattr("dispread.workbench.controller.fit_layout", fake_fit)

    result = controller.command(
        "layout.autofit",
        {"id": frozen["id"], "quad": frozen["quad"], "ocr_box": frozen["ocr_box"], "text": "1234,5"},
    )

    assert result["layout"] == proposed.to_dict()
    assert result["ocr_grid"] == grid_geometry(proposed.to_dict())
    # Gegenprobe: das uebernommene Raster ist ein anderes - die Vorschau muss
    # also wirklich das des Vorschlags sein.
    assert result["ocr_grid"] != grid_geometry(controller.config["layout"])


def test_browserclient_regressionen(tmp_path):
    """R1 (Vorschau == Bestaetigung) und R8a (Handaenderung sticht Vorschlag)."""
    node = shutil.which("node")
    if node is None:  # pragma: no cover - Entwicklungsumgebung ohne node
        pytest.skip("node nicht verfuegbar")

    committed = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V")
    proposed = DisplayLayout(
        digits=5, decimals=1, has_sign=True, unit="V", digit_gap_ratio=0.65, sign_cell_ratio=0.8
    )
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "committed": {
                    "layout": committed.to_dict(),
                    "ocr_grid": grid_geometry(committed.to_dict()),
                },
                "proposed": {
                    "layout": proposed.to_dict(),
                    "ocr_grid": grid_geometry(proposed.to_dict()),
                },
            }
        )
    )

    result = subprocess.run(
        [node, str(HARNESS), str(fixture)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=HARNESS.parent.parent,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_javascript_ist_syntaktisch_gueltig():
    """`node --check` wie in der Befehlsliste von CLAUDE.md - hier automatisiert."""
    node = shutil.which("node")
    if node is None:  # pragma: no cover
        pytest.skip("node nicht verfuegbar")
    script = Path(__file__).parents[1] / "src" / "dispread" / "workbench" / "static" / "workbench.js"
    result = subprocess.run([node, "--check", str(script)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
