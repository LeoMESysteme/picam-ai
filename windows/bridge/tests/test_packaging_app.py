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


def test_onefile_spec_branch_bundles_data_without_collect():
    portable = SPEC.split("if portable:", 1)[1].split("else:", 1)[0]
    assert "EXE(" in portable and "a.binaries, a.datas" in portable
    assert "COLLECT(" not in portable and "exclude_binaries" not in portable
    for name in ("Session-COM8.ucf", "vorlage-4kanal-mvv.ucf", "THIRD_PARTY_NOTICES.md"):
        assert name in SPEC
    assert '"--", "--portable"' in PS1


def test_inno_search_order_and_release_preflight():
    probes = ('${env:ProgramFiles(x86)}', '$env:ProgramFiles', '$env:LOCALAPPDATA')
    assert [PS1.index(probe) for probe in probes] == sorted(PS1.index(probe) for probe in probes)
    assert PS1.count("Inno Setup 6/ISCC.exe") == 3
    preflight = PS1.index('if (-not $Inno)')
    assert PS1.index('if ($Release) { throw', preflight) < PS1.index('"-m", "PyInstaller"')
    assert 'winget install JRSoftware.InnoSetup' in PS1


def test_build_self_tests_both_exes_before_publishing():
    assert PS1.index('Test-BuiltExe $PortableExe') < PS1.index('Invoke-Checked $Inno')
    assert PS1.index('Test-BuiltExe $OnedirExe') < PS1.index('Invoke-Checked $Inno')
    assert '"$PackageName-portable.exe"' in PS1
    assert "GSVmulti-Bruecke-Setup-$Version$Suffix.exe" in PS1
    assert "-SHA256SUMS.txt" in PS1 and "Get-FileHash" in PS1
    assert "CreateFromDirectory" not in PS1


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


def test_setup_updates_in_place_and_offers_shortcut_and_launch():
    assert "AppId={{B3C2A3E1-5D0F-4C57-9E3A-6F1B2A7C4D18}" in ISS
    assert "CloseApplications=force" in ISS and "RestartApplications=no" in ISS
    assert "[Tasks]" in ISS and "Flags: unchecked" in ISS
    assert "{userdesktop}" in ISS and "Tasks: desktopicon" in ISS
    assert "{userprograms}" in ISS
    run = ISS.split("[Run]\n", 1)[1].split("\n[", 1)[0]
    assert re.search(r'^Filename: "\{app\}\\GSVmulti-Bruecke.exe"; .*Flags: postinstall nowait skipifsilent$', run, re.M)
    assert re.search(r'^Source: .*THIRD_PARTY_NOTICES.md"; DestDir: "\{app\}"', ISS, re.M)
    assert "PySide6" in (BRIDGE / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")


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


def test_release_build_path_is_clean_and_distinct():
    assert "[switch]$Release" in PS1 and "dist-release" in PS1 and 'channel = "$Channel"' in PS1
    assert "nicht eingecheckte" in PS1 and "$Dirty" in PS1          # Release verweigert bei geaendertem Arbeitsbaum
    assert '$Suffix = if ($Release) { "" }' in PS1                   # Release-Name ohne Commit/-test
    rel = (BRIDGE / "build-release.cmd").read_bytes()
    assert b"\r\n" in rel and b"\n" not in rel.replace(b"\r\n", b"")
    assert b"BUILD_RELEASE=1" in rel and b"build-test.cmd" in rel
    iss = (BRIDGE / "packaging" / "setup-app.iss").read_text(encoding="utf-8")
    assert "#ifdef Release" in iss and "VersionInfoVersion={#AppVersion}.0" in iss
    assert "interner Test" in iss                                    # Testbuild bleibt unveraendert
    assert (BRIDGE / "pyproject.toml").read_text(encoding="utf-8").count('version = "1.1.0"') == 1


def test_double_click_starter_bypasses_policy_only_for_this_run():
    raw = (BRIDGE / "build-test.cmd").read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")   # reine CRLF-Zeilen, sonst zerbricht cmd.exe goto
    text = raw.decode("ascii")
    assert '-ExecutionPolicy Bypass -File "%SCRIPT%"' in text and 'build-test.ps1"' in text
    assert "Set-ExecutionPolicy" not in text                         # keine dauerhafte Systemänderung
    assert "py -3.13" in text and "pause" in text
    attrs = (BRIDGE / ".gitattributes").read_text(encoding="utf-8")
    assert re.search(r"^\*\.cmd -text$", attrs, re.M)


def test_download_archive_carries_the_commit_for_release_builds():
    """ZIP vom Server (git archive) hat kein .git: der Commit kommt per export-subst in die Datei."""
    import shutil
    import subprocess
    import tarfile
    from io import BytesIO

    raw = (BRIDGE / "packaging/source-commit.txt").read_text(encoding="utf-8")
    assert raw.strip() == "$Format:%H$"                       # im Arbeitsbaum nur der Platzhalter
    assert "packaging/source-commit.txt export-subst" in (BRIDGE / ".gitattributes").read_text(encoding="utf-8")
    assert "source-commit.txt" in PS1 and "'^[0-9a-f]{40}$'" in PS1
    git = shutil.which("git")
    repo = BRIDGE.parents[1]
    if git is None or subprocess.run([git, "-C", str(repo), "rev-parse", "HEAD"], capture_output=True).returncode:
        pytest.skip("kein Git-Arbeitsbaum")
    head = subprocess.run([git, "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    listed = subprocess.run([git, "-C", str(repo), "ls-tree", "HEAD", "windows/bridge/packaging/source-commit.txt"],
                            capture_output=True, text=True).stdout
    if not listed:
        pytest.skip("Datei noch nicht committet")
    out = subprocess.run([git, "-C", str(repo), "archive", "--format=tar", "HEAD",
                          "windows/bridge/packaging/source-commit.txt"], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=BytesIO(out)) as tar:
        member = tar.extractfile("windows/bridge/packaging/source-commit.txt")
        assert member is not None and member.read().decode().strip() == head
