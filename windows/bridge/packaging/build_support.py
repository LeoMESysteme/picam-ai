"""Fail-closed, dependency-free checks shared by Windows builds and Linux tests.

Verification records are locally reviewed inputs, NOT signature verification or
permission to publish. Release signing/hosting and genuine VM evidence stay open.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

EXE_NAME = "dispread-bridge-probe.exe"
LOCK_NAMES = ("requirements-build.lock", "requirements-runtime.lock")
MANIFEST_NAME = "build-manifest.json"


class BuildError(RuntimeError):
    """Build inputs, runtime or staged artifact do not meet the contract."""


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def parse_json(data: bytes, label: str) -> dict:
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise BuildError(f"{label}: {exc}") from exc
    if not isinstance(value, dict):
        raise BuildError(f"{label} must be an object")
    return value


def read_json(path: Path, label: str) -> dict:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise BuildError(f"{label}: {exc}") from exc
    return parse_json(data, label)


def parse_lock(text: str) -> dict:
    """Only flattened exact pins with SHA-256; no URLs/options/includes/code."""
    requirements = {}
    text = text.replace("\\\r\n", " ").replace("\\\n", " ")
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(
            r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)"
            r"((?:\s+--hash=sha256:[a-fA-F0-9]{64})+)", line,
        )
        if not match:
            raise BuildError("lock requires exact versions and SHA-256 hashes, no other options")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        if name in requirements:
            raise BuildError(f"duplicate lock requirement: {name}")
        requirements[name] = {"version": match[2], "hashes": sorted(re.findall(r"sha256:([a-fA-F0-9]{64})", match[3]))}
    if not requirements:
        raise BuildError("lock is empty/unverified")
    return requirements


def validate_environment() -> None:
    if (sys.platform != "win32" or platform.machine().upper() not in {"AMD64", "X86_64"}
            or struct.calcsize("P") != 8 or sys.getwindowsversion().build < 22000):
        raise BuildError("build requires Windows 11 x64 (no ARM64 or cross-build)")
    if sys.version_info < (3, 13):  # noqa: UP036 -- explicit build-interpreter preflight
        raise BuildError("build requires an explicit Python >=3.13 x64 interpreter")


def validate_inputs(bridge_root: Path, verification_path: Path, *, verification_bytes: bytes | None = None) -> dict:
    # A caller that retains an immutable byte snapshot validates that exact
    # record, instead of reopening a file that may change while a probe runs.
    record = (read_json(verification_path, "verification record missing/invalid") if verification_bytes is None
              else parse_json(verification_bytes, "verification record missing/invalid"))
    if (record.get("schema_version") != 1 or record.get("status") != "windows_probe_verified"
            or record.get("target") != "windows11-x64" or not record.get("verified_by")
            or record.get("python_version") != platform.python_version()):
        raise BuildError("verification record does not approve this target/Python runtime")
    approved_locks = record.get("locks")
    if not isinstance(approved_locks, dict):
        raise BuildError("verification record has no approved locks")
    locks = {}
    for name in LOCK_NAMES:
        path = bridge_root / name
        if not path.is_file() or approved_locks.get(name) != sha256(path):
            raise BuildError(f"verification lock hash mismatch or missing: {name}")
        locks[name] = parse_lock(path.read_text(encoding="utf-8"))
    build, runtime = (locks[name] for name in LOCK_NAMES)
    if not {"pyside6", "pyserial"} <= runtime.keys() or not {"pyinstaller", "pytest"} <= build.keys():
        raise BuildError("lock missing required runtime/build dependencies")
    if any(build.get(name) != value for name, value in runtime.items()):
        raise BuildError("runtime lock must be an identical subset of the build lock")
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise BuildError("verification record has no Windows evidence")
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise BuildError("verification evidence entry invalid")
        path = verification_path.parent / item["path"]
        if not path.is_file() or item.get("sha256") != sha256(path):
            raise BuildError("verification evidence missing or hash mismatch")
    return record


def validate_installed(bridge_root: Path, verification: Path, *, verification_bytes: bytes | None = None) -> dict:
    validate_inputs(bridge_root, verification, verification_bytes=verification_bytes)
    locked = parse_lock((bridge_root / LOCK_NAMES[0]).read_text(encoding="utf-8"))
    installed = {}
    for name, requirement in locked.items():
        try:
            installed[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise BuildError(f"installed dependency missing: {name}") from exc
        if installed[name] != requirement["version"]:
            raise BuildError(f"installed dependency differs from reviewed lock: {name}")
    return installed


def probe_environment(environ: dict | None = None) -> dict:
    env = dict(os.environ if environ is None else environ)
    env = {key: value for key, value in env.items()
           if not key.upper().startswith(("PYTHON", "QT_", "PYSIDE")) and key.upper() != "PATH"}
    root = next((value for key, value in env.items() if key.upper() == "SYSTEMROOT"), r"C:\Windows")
    env["PATH"] = root + r"\System32;" + root
    return env


def validate_probe_report(report: dict) -> None:
    if (report.get("ok") is not True or report.get("frozen") is not True
            or report.get("system_python_used") is not False or report.get("bridge_import_ok") is not True
            or report.get("qt_platform") != "windows" or report.get("qt_plugin_bundled") is not True
            or report.get("provisional") is not True or report.get("time_claim") is not False
            or report.get("errors") != []):
        raise BuildError("frozen runtime/bridge/Qt self-test failed")
    version = report.get("runtime_version", "")
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (3, 13, 0):
        raise BuildError("frozen Python runtime >=3.13 required")
    modules = report.get("loaded_modules")
    if (not isinstance(modules, list) or not all(isinstance(name, str) for name in modules)
            or {"cv2", "numpy", "PAM", "pam", "picamera2", "libcamera"}
            & {name.split(".")[0] for name in modules}):
        raise BuildError("frozen report has forbidden/missing module inventory")


def run_frozen_probe(executable: Path) -> dict:
    if not executable.is_file():
        raise BuildError(f"frozen probe missing: {executable}")
    try:
        result = subprocess.run([str(executable.resolve()), "--self-test"], cwd=executable.parent,
                                env=probe_environment(), capture_output=True, text=True,
                                encoding="utf-8", timeout=45, check=False,
                                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BuildError(f"frozen probe did not run: {exc}") from exc
    if result.returncode:
        raise BuildError(f"frozen probe exit {result.returncode}: {result.stderr[:2000]} {result.stdout[:2000]}")
    try:
        report = json.loads(result.stdout)
    except ValueError as exc:
        raise BuildError("frozen probe did not return one JSON object") from exc
    if not isinstance(report, dict):
        raise BuildError("frozen probe report must be an object")
    validate_probe_report(report)
    return report


def validate_bundle(stage: Path, runtime_version: str) -> None:
    if not (stage / EXE_NAME).is_file():
        raise BuildError("frozen probe executable missing")
    version = runtime_version.split(".")
    runtime_name = f"python{version[0]}{version[1]}.dll"
    if not list(stage.rglob(runtime_name)):
        raise BuildError(f"Python runtime missing: {runtime_name}")
    if not list(stage.rglob("qwindows.dll")):
        raise BuildError("Qt platform plugin missing: qwindows.dll")


def hash_tree(root: Path) -> dict:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise BuildError("artifact hash inventory cannot contain symlinks")
        if path.is_file() and path.relative_to(root).as_posix() != MANIFEST_NAME:
            files[path.relative_to(root).as_posix()] = sha256(path)
    if not files:
        raise BuildError("artifact hash inventory is empty")
    return files


def verify_tree(root: Path, files: dict) -> None:
    if hash_tree(root) != files:
        raise BuildError("artifact hash inventory mismatch")


def promote(stage: Path, destination: Path) -> None:
    if destination.exists():
        raise BuildError("destination already exists; previous package preserved")
    manifest = read_json(stage / MANIFEST_NAME, "build manifest")
    verify_tree(stage, manifest.get("files"))
    if stage.parent.resolve() != destination.parent.resolve():
        raise BuildError("stage and destination must share a parent for atomic rename")
    stage.rename(destination)


def source_snapshot(source_root: Path, bridge_root: Path, source_commit: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{40,64}", source_commit):
        raise BuildError("source commit must be a full Git object ID")
    source_files = {}
    for base in (source_root / "src/dispread", bridge_root):
        for path in sorted(base.rglob("*")):
            if (path.is_file() and path.suffix in {".py", ".spec", ".ps1", ".toml", ".in", ".lock"}
                    and not any(part.startswith(".") or part in {"__pycache__", "dist", "build"}
                                for part in path.relative_to(base).parts)):
                if path.is_symlink():
                    raise BuildError("source snapshot cannot contain symlinks")
                source_files[path.relative_to(source_root).as_posix()] = sha256(path)
    if not source_files:
        raise BuildError("source snapshot is empty")
    return {"source_commit": source_commit, "source_hashes": source_files}


def verify_source_snapshot(snapshot: dict, source_root: Path, bridge_root: Path, source_commit: str) -> None:
    if snapshot != source_snapshot(source_root, bridge_root, source_commit):
        raise BuildError("source changed during build; discard partial artifact and rebuild")


def validate_staged_evidence(files: dict, record: dict, verification_hash: str) -> None:
    """Bind the exact inventory used for promotion to the validated approval."""
    expected = {"build-evidence/verification-record.json": verification_hash}
    expected.update({f"build-evidence/{name}": record["locks"][name] for name in LOCK_NAMES})
    expected.update({f"build-evidence/{index}-{Path(item['path']).name}": item["sha256"]
                     for index, item in enumerate(record["evidence"])})
    for name, approved_hash in expected.items():
        if files.get(name) != approved_hash:
            raise BuildError(f"staged verification/evidence/lock hash differs from approval: {name}")


def finalize(stage: Path, destination: Path, bridge_root: Path, verification: Path,
             source_root: Path, source_commit: str, snapshot_file: Path) -> None:
    verification_bytes = verification.read_bytes()
    verification_hash = hashlib.sha256(verification_bytes).hexdigest()
    record = validate_inputs(bridge_root, verification, verification_bytes=verification_bytes)
    installed = validate_installed(bridge_root, verification, verification_bytes=verification_bytes)
    snapshot = read_json(snapshot_file, "source snapshot")
    verify_source_snapshot(snapshot, source_root, bridge_root, source_commit)
    validate_bundle(stage, platform.python_version())
    probe = run_frozen_probe(stage / EXE_NAME)
    if probe["runtime_version"] != platform.python_version():
        raise BuildError("bundled runtime differs from approved build Python")
    if sha256(verification) != verification_hash:
        raise BuildError("verification record changed during probe; discard staged package")
    evidence_dir = stage / "build-evidence"
    evidence_dir.mkdir()
    (evidence_dir / "verification-record.json").write_bytes(verification_bytes)
    for name in LOCK_NAMES:
        shutil.copyfile(bridge_root / name, evidence_dir / name)
    for index, item in enumerate(record["evidence"]):
        original = verification.parent / item["path"]
        shutil.copyfile(original, evidence_dir / f"{index}-{original.name}")
    (stage / "probe-report.json").write_text(json.dumps(probe, indent=2) + "\n", encoding="utf-8")
    files = hash_tree(stage)
    validate_staged_evidence(files, record, verification_hash)
    manifest = {
        "schema_version": 1, **snapshot,
        "target": "windows11-x64", "runtime_version": platform.python_version(),
        "versions": installed,
        "verification_sha256": files["build-evidence/verification-record.json"], "approved_locks": record["locks"],
        "provisional": True, "time_claim": False, "release_signed": False,
        "files": files,
    }
    verify_source_snapshot(snapshot, source_root, bridge_root, source_commit)
    (stage / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    promote(stage, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "snapshot", "installed", "finalize"])
    parser.add_argument("--bridge-root", type=Path, required=True)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args(argv)
    try:
        validate_environment()
        validate_inputs(args.bridge_root, args.verification)
        if args.command == "installed":
            validate_installed(args.bridge_root, args.verification)
        if args.command == "snapshot":
            if not all((args.snapshot, args.source_root, args.source_commit)):
                raise BuildError("snapshot requires snapshot, source-root and source-commit")
            snapshot = source_snapshot(args.source_root, args.bridge_root, args.source_commit)
            args.snapshot.write_text(json.dumps(snapshot, sort_keys=True) + "\n", encoding="utf-8")
        if args.command == "finalize":
            if not all((args.stage, args.destination, args.source_root, args.source_commit, args.snapshot)):
                raise BuildError("finalize requires stage, destination, source-root, source-commit and snapshot")
            finalize(args.stage, args.destination, args.bridge_root, args.verification,
                     args.source_root, args.source_commit, args.snapshot)
    except (BuildError, OSError, importlib.metadata.PackageNotFoundError) as exc:
        print(f"BUILD BLOCKED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
