"""N1 contracts; fake fixtures establish no Windows or dependency approval."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BRIDGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BRIDGE / "src"))


@pytest.mark.parametrize('spec_name', ['bridge.spec', 'bridge-app.spec'])
def test_packaged_session_data_include_both_pinned_originals(spec_name):
    import ast

    tree = ast.parse((BRIDGE / 'packaging' / spec_name).read_text())
    analysis = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Analysis')
    data_node = next(keyword.value for keyword in analysis.keywords if keyword.arg == 'datas')
    data = eval(compile(ast.Expression(data_node), spec_name, 'eval'), {'bridge_root': BRIDGE})
    packaged = {Path(source).name: (Path(source).read_bytes(), destination) for source, destination in data}
    originals = {
        'Session-COM8.ucf': 'bruecke-testlauf-2026-11-06/Session-COM8.ucf',
        'versuch2b-session-hidden.ucf': 'gsvmulti-versuche-2026-11-11/versuch2b-session-hidden.ucf',
    }
    for filename, source in originals.items():
        assert filename in packaged
        assert packaged[filename] == ((BRIDGE.parents[1] / 'docs/quellen' / source).read_bytes(),
                                      'dispread_bridge_app/templates')


def support():
    spec = importlib.util.spec_from_file_location("bridge_build_support", BRIDGE / "packaging/build_support.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_light_bridge_import_has_no_camera_dependencies(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.chdir(tmp_path)
    source_root = BRIDGE.parents[1] / "src"
    code = (
        f"import sys; sys.path.insert(0, {str(source_root)!r}); "
        "import dispread.gsv_bridge,json; "
        "print(json.dumps({'modules': sorted(sys.modules), 'bridge_file': dispread.gsv_bridge.__file__}))"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert Path(report["bridge_file"]).is_relative_to(source_root)
    roots = {name.split(".")[0] for name in report["modules"]}
    assert not ({"cv2", "numpy", "PAM", "pam", "picamera2", "libcamera"} & roots)


def test_probe_reports_missing_runtime(capsys, monkeypatch):
    from dispread_bridge_app import probe_main

    real_import = probe_main.importlib.import_module

    def missing_qt(name):
        if name.startswith("PySide6"):
            raise ImportError("Qt not installed")
        return real_import(name)

    monkeypatch.setattr(probe_main.importlib, "import_module", missing_qt)
    assert probe_main.main(["--self-test"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["bridge_import_ok"] is True
    assert report["system_python_used"] is True
    assert report["qt_platform"] is None
    assert report["ok"] is False
    assert any("Qt not installed" in error for error in report["errors"])


def test_build_rejects_unverified_download(tmp_path):
    mod = support()
    (tmp_path / "requirements-build.lock").write_text("PyInstaller==1.0 --hash=sha256:" + "1" * 64)
    with pytest.raises(mod.BuildError, match="verification"):
        mod.validate_inputs(tmp_path, tmp_path / "absent-verification.json")


@pytest.mark.parametrize("line", [
    "PySide6", "PySide6>=1", "PySide6==1", "--index-url https://untrusted.invalid",
    "-r other.lock", "PySide6 @ https://example.invalid/a.whl", "PySide6==1 --hash=md5:1234",
    "PySide6==1 --hash=sha256:" + "1" * 64 + " --trusted-host bad.invalid",
])
def test_lock_rejects_floating_unhashed_and_remote_options(line):
    mod = support()
    with pytest.raises(mod.BuildError, match="lock"):
        mod.parse_lock(line)


def test_hash_pinned_lock_accepts_continuations():
    mod = support()
    assert mod.parse_lock("# fixture only\nPySide6==1.2 \\\n    --hash=sha256:" + "a" * 64)["pyside6"]["version"] == "1.2"


def test_build_reports_missing_runtime(tmp_path):
    mod = support()
    (tmp_path / "dispread-bridge-probe.exe").write_bytes(b"fixture")
    with pytest.raises(mod.BuildError, match="Python runtime"):
        mod.validate_bundle(tmp_path, "3.13.5")


def test_build_reports_missing_qt_windows_plugin(tmp_path):
    mod = support()
    (tmp_path / "dispread-bridge-probe.exe").write_bytes(b"fixture")
    (tmp_path / "python313.dll").write_bytes(b"fixture")
    with pytest.raises(mod.BuildError, match="qwindows"):
        mod.validate_bundle(tmp_path, "3.13.5")


def test_self_test_report_rejects_system_python_and_wrong_qt():
    mod = support()
    report = {"ok": True, "runtime_version": "3.13.5", "qt_platform": "offscreen",
              "bridge_import_ok": True, "system_python_used": True, "errors": []}
    with pytest.raises(mod.BuildError, match="frozen"):
        mod.validate_probe_report(report)


def test_probe_environment_removes_python_and_external_qt():
    env = support().probe_environment({"SystemRoot": r"C:\Windows", "PATH": r"C:\Python37",
        "PYTHONHOME": "bad", "PYTHONPATH": "bad", "QT_PLUGIN_PATH": "bad", "QT_QPA_PLATFORM": "offscreen"})
    assert "Python37" not in env["PATH"]
    assert not ({"PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM"} & env.keys())


def test_hash_manifest_detects_changed_and_added_files(tmp_path):
    mod = support()
    (tmp_path / "file.dll").write_bytes(b"before")
    files = mod.hash_tree(tmp_path)
    (tmp_path / "file.dll").write_bytes(b"after")
    with pytest.raises(mod.BuildError, match="hash"):
        mod.verify_tree(tmp_path, files)
    (tmp_path / "file.dll").write_bytes(b"before")
    (tmp_path / "injected.dll").write_bytes(b"extra")
    with pytest.raises(mod.BuildError, match="hash"):
        mod.verify_tree(tmp_path, files)


def test_failed_promotion_preserves_last_good_package(tmp_path):
    mod = support()
    stage, released = tmp_path / "stage", tmp_path / "released"
    stage.mkdir()
    released.mkdir()
    (released / "old.exe").write_bytes(b"good")
    with pytest.raises(mod.BuildError):
        mod.promote(stage, released)
    assert (released / "old.exe").read_bytes() == b"good"
    assert stage.exists()


def test_promotion_rejects_modified_manifest_files(tmp_path):
    mod = support()
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "file.dll").write_bytes(b"before")
    manifest = {"files": mod.hash_tree(stage)}
    (stage / "build-manifest.json").write_text(json.dumps(manifest))
    (stage / "file.dll").write_bytes(b"tampered")
    with pytest.raises(mod.BuildError, match="hash"):
        mod.promote(stage, tmp_path / "released")
    assert stage.exists()
    assert not (tmp_path / "released").exists()


def verified_fixture(tmp_path):
    """Synthetic contract fixtures; never actual verified dependencies/evidence."""
    mod = support()
    runtime = "".join(f"{name}==1.2.3 --hash=sha256:{'a' * 64}\n" for name in ("PySide6", "pyserial"))
    build = runtime + "".join(f"{name}==1.2.3 --hash=sha256:{'b' * 64}\n"
                              for name in ("PyInstaller", "pytest", "pip", "setuptools"))
    bridge = tmp_path / "windows/bridge"
    bridge.mkdir(parents=True)
    (bridge / "requirements-runtime.lock").write_text(runtime)
    (bridge / "requirements-build.lock").write_text(build)
    (tmp_path / "fixture-only.txt").write_text("synthetic evidence fixture; not a Windows result")
    record = {"schema_version": 1, "status": "windows_probe_verified", "target": "windows11-x64",
              "verified_by": "unit-test fixture", "python_version": sys.version.split()[0],
              "locks": {name: mod.sha256(bridge / name) for name in mod.LOCK_NAMES},
              "evidence": [{"path": "fixture-only.txt", "sha256": mod.sha256(tmp_path / "fixture-only.txt")}]}
    verification = tmp_path / "verification.json"
    verification.write_text(json.dumps(record))
    return mod, bridge, verification, record


def valid_report():
    return {"ok": True, "runtime_version": sys.version.split()[0], "frozen": True,
            "qt_platform": "windows", "qt_plugin_bundled": True, "bridge_import_ok": True,
            "system_python_used": False, "provisional": True, "time_claim": False,
            "errors": [], "loaded_modules": ["dispread.gsv_bridge", "PySide6.QtWidgets", "serial"]}


def test_verified_inputs_require_exact_locks_and_original_evidence(tmp_path):
    mod, bridge, verification, record = verified_fixture(tmp_path)
    assert mod.validate_inputs(bridge, verification) == record
    (bridge / "requirements-runtime.lock").write_text("changed")
    with pytest.raises(mod.BuildError, match="lock hash"):
        mod.validate_inputs(bridge, verification)


def test_missing_windows_evidence_blocks_build(tmp_path):
    mod, bridge, verification, _ = verified_fixture(tmp_path)
    (tmp_path / "fixture-only.txt").unlink()
    with pytest.raises(mod.BuildError, match="evidence"):
        mod.validate_inputs(bridge, verification)


@pytest.mark.parametrize("field,value", [("status", "candidate"), ("target", "linux"),
                                         ("python_version", "3.7.0"), ("verified_by", "")])
def test_wrong_approval_never_allows_build(tmp_path, field, value):
    mod, bridge, verification, record = verified_fixture(tmp_path)
    record[field] = value
    verification.write_text(json.dumps(record))
    with pytest.raises(mod.BuildError, match="verification"):
        mod.validate_inputs(bridge, verification)


def test_valid_probe_report_accepts_only_bundled_runtime():
    mod = support()
    report = valid_report()
    mod.validate_probe_report(report)
    report["loaded_modules"].append("numpy.core")
    with pytest.raises(mod.BuildError, match="forbidden"):
        mod.validate_probe_report(report)


def test_probe_subprocess_uses_scrubbed_environment(tmp_path, monkeypatch):
    mod = support()
    executable = tmp_path / mod.EXE_NAME
    executable.write_bytes(b"not a real executable")
    seen = {}

    def run(argv, **kwargs):
        seen.update(kwargs)
        assert argv == [str(executable), "--self-test"]
        return subprocess.CompletedProcess(argv, 0, json.dumps(valid_report()), "")

    monkeypatch.setattr(mod.subprocess, "run", run)
    monkeypatch.setattr(mod.sys, "platform", "win32")
    monkeypatch.setattr(mod.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setenv("PATH", r"C:\Python37")
    assert mod.run_frozen_probe(executable)["system_python_used"] is False
    assert "Python37" not in seen["env"]["PATH"]
    assert seen["timeout"] == 45
    assert seen["creationflags"] == 0x08000000


def test_source_snapshot_detects_concurrent_changes(tmp_path):
    mod, bridge, _, _ = verified_fixture(tmp_path)
    source = tmp_path / "src/dispread"
    source.mkdir(parents=True)
    code = source / "gsv_bridge.py"
    code.write_text("# before")
    snapshot = mod.source_snapshot(tmp_path, bridge, "a" * 40)
    code.write_text("# changed during package analysis")
    with pytest.raises(mod.BuildError, match="source"):
        mod.verify_source_snapshot(snapshot, tmp_path, bridge, "a" * 40)


def test_installed_versions_must_match_reviewed_lock(tmp_path, monkeypatch):
    mod, bridge, verification, _ = verified_fixture(tmp_path)
    monkeypatch.setattr(mod.importlib.metadata, "version", lambda name: "999.0")
    with pytest.raises(mod.BuildError, match="installed"):
        mod.validate_installed(bridge, verification)


def test_successful_finalize_hashes_proof_and_atomically_publishes(tmp_path, monkeypatch):
    mod, bridge, verification, _ = verified_fixture(tmp_path)
    stage = tmp_path / ".partial"
    stage.mkdir()
    for name in (mod.EXE_NAME, f"python{sys.version_info.major}{sys.version_info.minor}.dll", "qwindows.dll"):
        (stage / name).write_bytes(b"synthetic fixture")
    snapshot_file = tmp_path / "source-snapshot.json"
    snapshot_file.write_text(json.dumps(mod.source_snapshot(tmp_path, bridge, "a" * 40)))
    monkeypatch.setattr(mod, "run_frozen_probe", lambda path: valid_report())
    monkeypatch.setattr(mod.importlib.metadata, "version", lambda name: "1.2.3")
    destination = tmp_path / "internal-package"
    mod.finalize(stage, destination, bridge, verification, tmp_path, "a" * 40, snapshot_file)
    assert not stage.exists()
    manifest = json.loads((destination / "build-manifest.json").read_text())
    assert manifest["source_commit"] == "a" * 40
    assert manifest["release_signed"] is False
    assert manifest["provisional"] is True
    assert manifest["time_claim"] is False
    assert "build-evidence/verification-record.json" in manifest["files"]
    assert manifest["verification_sha256"] == mod.sha256(destination / "build-evidence/verification-record.json")
    mod.verify_tree(destination, manifest["files"])


@pytest.mark.parametrize("changed_input", ["evidence", "verification", "build_lock", "runtime_lock"])
def test_finalize_rejects_approval_inputs_changed_during_probe(tmp_path, monkeypatch, changed_input):
    mod, bridge, verification, _ = verified_fixture(tmp_path)
    stage = tmp_path / ".partial"
    stage.mkdir()
    for name in (mod.EXE_NAME, f"python{sys.version_info.major}{sys.version_info.minor}.dll", "qwindows.dll"):
        (stage / name).write_bytes(b"synthetic fixture")
    snapshot_file = tmp_path / "source-snapshot.json"
    snapshot_file.write_text(json.dumps(mod.source_snapshot(tmp_path, bridge, "a" * 40)))
    changed_path = {
        "evidence": tmp_path / "fixture-only.txt", "verification": verification,
        "build_lock": bridge / "requirements-build.lock", "runtime_lock": bridge / "requirements-runtime.lock",
    }[changed_input]

    def probe(path):
        changed_path.write_bytes(changed_path.read_bytes() + b"\nchanged while probe was running")
        return valid_report()

    monkeypatch.setattr(mod, "run_frozen_probe", probe)
    monkeypatch.setattr(mod.importlib.metadata, "version", lambda name: "1.2.3")
    destination = tmp_path / "new-package"
    last_good = tmp_path / "last-good"
    last_good.mkdir()
    (last_good / "keep.exe").write_bytes(b"previous good package")
    with pytest.raises(mod.BuildError, match="verification|evidence|lock|source"):
        mod.finalize(stage, destination, bridge, verification, tmp_path, "a" * 40, snapshot_file)
    assert stage.exists()
    assert not destination.exists()
    assert (last_good / "keep.exe").read_bytes() == b"previous good package"


@pytest.mark.parametrize("copied_name", ["requirements-build.lock", "requirements-runtime.lock", "0-fixture-only.txt"])
def test_finalize_rejects_staged_copies_unlinked_from_approval(tmp_path, monkeypatch, copied_name):
    mod, bridge, verification, _ = verified_fixture(tmp_path)
    stage = tmp_path / ".partial"
    stage.mkdir()
    for name in (mod.EXE_NAME, f"python{sys.version_info.major}{sys.version_info.minor}.dll", "qwindows.dll"):
        (stage / name).write_bytes(b"synthetic fixture")
    snapshot_file = tmp_path / "source-snapshot.json"
    snapshot_file.write_text(json.dumps(mod.source_snapshot(tmp_path, bridge, "a" * 40)))
    monkeypatch.setattr(mod, "run_frozen_probe", lambda path: valid_report())
    monkeypatch.setattr(mod.importlib.metadata, "version", lambda name: "1.2.3")
    copyfile = mod.shutil.copyfile

    def corrupt_copy(original, copied):
        result = copyfile(original, copied)
        if copied.name == copied_name:
            copied.write_bytes(b"different bytes in staged copy")
        return result

    monkeypatch.setattr(mod.shutil, "copyfile", corrupt_copy)
    with pytest.raises(mod.BuildError, match="evidence|lock"):
        mod.finalize(stage, tmp_path / "new-package", bridge, verification, tmp_path, "a" * 40, snapshot_file)
    assert stage.exists()
    assert not (tmp_path / "new-package").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="needs a real Windows 11 x64 frozen artifact")
def test_frozen_probe_without_system_python():
    artifact = os.environ.get("DISPREAD_FROZEN_PROBE")
    assert artifact, "N1 RED: set DISPREAD_FROZEN_PROBE to an actual packaged probe EXE"
    executable = Path(artifact)
    assert executable.is_file(), "N1 RED: frozen artifact is missing"
    report = support().run_frozen_probe(executable)
    assert report["bridge_import_ok"] is True
    assert report["system_python_used"] is False
