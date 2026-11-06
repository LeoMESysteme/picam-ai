"""Statische Prüfung des internen Testbuild-Wegs. Baut nichts, belegt nichts unter Windows."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

BRIDGE = Path(__file__).resolve().parents[1]
PS1 = (BRIDGE / "build-test.ps1").read_text(encoding="utf-8")
SPEC = (BRIDGE / "packaging/bridge-app.spec").read_text(encoding="utf-8")
ISS = (BRIDGE / "packaging/setup-app.iss").read_text(encoding="utf-8")


def test_spec_references_existing_files_and_is_windowed():
    assert (BRIDGE / "packaging/app_launcher.py").is_file()
    assert "packaging/app_launcher.py" in SPEC
    assert "console=False" in SPEC
    assert 'name="GSVmulti-Bruecke"' in SPEC
    for hidden in ("PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "serial.tools.list_ports",
                   "cryptography", "aiohttp", "zeroconf", "collect_submodules(\"dispread.bridge\")"):
        assert hidden in SPEC


def test_spec_excludes_heavy_modules():
    excludes = re.search(r"excludes=\[(.*?)\]", SPEC, re.S).group(1)
    for name in ("cv2", "numpy", "dispread.workbench"):
        assert f'"{name}"' in excludes


def test_launcher_freezes_first_and_intercepts_self_test_before_gui():
    text = (BRIDGE / "packaging/app_launcher.py").read_text(encoding="utf-8")
    assert text.index("freeze_support()") < text.index("--self-test") < text.index("dispread_bridge_app.main")


def test_build_script_is_explicit_windows_only_and_isolated():
    assert "PIP_CONFIG_FILE" in PS1 and '"NUL"' in PS1
    assert 'Windows_NT' in PS1 and "22000" in PS1
    assert "--only-binary=:all:" in PS1 and "--isolated" in PS1
    assert ".build-test" in PS1 and "dist-test" in PS1
    assert "bridge-app.spec" in PS1 and "--self-test-out" in PS1
    # Keine Interpretersuche im PATH.
    low = PS1.lower()
    for forbidden in ("get-command", "where.exe", "py.exe", "py -3", "$env:path", "which "):
        assert forbidden not in low
    assert re.search(r"\[Parameter\(Mandatory = \$true\)\]\[string\]\$Python", PS1)


def test_build_script_does_not_touch_qualified_path():
    code = "\n".join(line for line in PS1.splitlines() if not line.lstrip().startswith("#"))
    assert "build_support" not in code and "bridge.spec" not in code.replace("bridge-app.spec", "")


def test_build_script_marks_itself_unqualified():
    assert "unqualifiziert" in PS1.lower() and "unsigniert" in PS1.lower()


def test_setup_is_per_user_without_admin_and_keeps_user_data():
    assert re.search(r"^PrivilegesRequired=lowest\s*$", ISS, re.M)
    assert "PrivilegesRequired=admin" not in ISS
    assert "{localappdata}\\Programs\\GSVmulti-Bruecke" in ISS
    assert not re.search(r"^\[UninstallDelete\]", ISS, re.M)
    assert not re.search(r"^[^;\n]*dispread-bridge", ISS, re.M)
    assert "Root: HKCU" in ISS and "HKLM" not in ISS
    assert ".dispread" in ISS
    assert not re.search(r"^\[Run\]", ISS, re.M)


def test_build_info_is_ignored_but_not_tracked():
    gitignore = (BRIDGE.parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "/windows/bridge/src/dispread_bridge_app/build_info.py" in gitignore


def test_selftest_reports_json_and_flags_non_frozen(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from dispread_bridge_app import selftest

    out = tmp_path / "r.json"
    code = selftest.main(["--self-test-out", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["frozen"] is False
    assert code == 1 and report["ok"] is False and "nicht eingefroren" in report["errors"]
    assert report["imports"]["dispread_bridge_app.ui.window"] is True
    assert report["forbidden_loaded"] == []


def test_selftest_ok_when_not_requiring_frozen(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from dispread_bridge_app import selftest

    report = selftest.run_self_test(require_frozen=False)
    assert report["errors"] == [] and report["ok"] is True
