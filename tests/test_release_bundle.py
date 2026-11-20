"""Release archives contain verified product inputs, never runtime state."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

BUILDER_PATH = Path(__file__).parents[1] / "packaging" / "release.py"
TEMPLATE_NAME = "src/dispread/data/templates-stufe2c-2026-09-30.json"


def build_release(*args):
    assert BUILDER_PATH.is_file(), "release builder is missing"
    spec = importlib.util.spec_from_file_location("picam_release_builder", BUILDER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_release(*args)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    template = tmp_path / "templates.json"
    template.write_bytes(b'{"templates":[]}\n')
    files = {
        "src/dispread/__init__.py": "",
        "src/dispread/live/__init__.py": (
            "raise RuntimeError('never import the product while building')\n"
            f'DEFAULT_TEMPLATES_SHA256 = "{hashlib.sha256(template.read_bytes()).hexdigest()}"\n'
        ),
        "src/dispread/workbench/static/app.js": "console.log('product');\n",
        "pyproject.toml": '[project]\nname = "test-product"\n',
        "VERSION": "1.2.3\n",
        "packaging/apt-packages.txt": "python3-numpy\n",
        "scripts/install.py": "print('installer')\n",
        "install.sh": "#!/bin/sh\nexec python3 scripts/install.py\n",
    }
    for name in ("__init__", "platform", "archive", "engine", "guided", "tui", "fastfetch", "update", "uninstall",
                 "__main__"):
        files[f"packaging/picam_installer/{name}.py"] = "# installer\n"
    for name in ("me-logo.py", "me-fastfetch.in", "config.jsonc", "me-logo.txt"):
        files[f"packaging/me-fastfetch/{name}"] = f"# {name}\n"
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (root / "install.sh").chmod(0o755)
    git(root, "init", "--quiet")
    git(root, "add", ".")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "fixture")
    return root, template


def test_bundle_contains_verified_payload_manifest_and_executable(source, tmp_path):
    root, template = source
    output = tmp_path / "release.tar.gz"
    assert build_release(root, output, template, "1.2.3") == output
    with tarfile.open(output, "r:gz") as archive:
        files = {m.name.removeprefix("picam/"): m for m in archive if m.isfile()}
        assert all(m.name == "picam" or m.name.startswith("picam/") for m in archive)
        manifest = json.load(archive.extractfile(files.pop("release.json")))
        assert manifest["schema"] == 1
        assert manifest["release_id"] == "1.2.3"
        assert manifest["commit"] == git(root, "rev-parse", "HEAD")
        assert manifest["dirty"] is False
        assert set(manifest["files"]) == set(files)
        for name, member in files.items():
            assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == manifest["files"][name]
        assert archive.extractfile(files[TEMPLATE_NAME]).read() == template.read_bytes()
        assert files["install.sh"].mode == 0o755
        assert "scripts/install.py" in files
        assert "packaging/picam_installer/__main__.py" in files
        assert {"packaging/picam_installer/tui.py", "packaging/picam_installer/fastfetch.py"} <= set(files)
        assert {f"packaging/me-fastfetch/{name}" for name in
                ("me-logo.py", "me-fastfetch.in", "config.jsonc", "me-logo.txt")} <= set(files)


def test_me_fastfetch_extras_are_not_bundled(source, tmp_path):
    root, template = source
    for name in ("packaging/me-fastfetch/me-logo.py.bak", "packaging/me-fastfetch/notes.md"):
        (root / name).write_text("private\n")
    output = build_release(root, tmp_path / "bundle.tar.gz", template, "release-1")
    with tarfile.open(output) as archive:
        names = set(archive.getnames())
    assert "picam/packaging/me-fastfetch/config.jsonc" in names
    assert not {"picam/packaging/me-fastfetch/me-logo.py.bak", "picam/packaging/me-fastfetch/notes.md"} & names


def test_reproducible_bytes_ignore_source_mtime(source, tmp_path):
    root, template = source
    first = build_release(root, tmp_path / "first.tar.gz", template, "release-1")
    import os
    for path in root.rglob("*"):
        if path.is_file():
            os.utime(path, (345678, 345678))
    second = build_release(root, tmp_path / "second.tar.gz", template, "release-1")
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes()[4:8] == b"\0\0\0\0"


def test_bundle_uses_current_product_sources_and_excludes_private_files(source, tmp_path):
    root, template = source
    additions = {
        "src/dispread/new_module.py": b"NEW = True\n",
        "src/dispread/.env": b"SECRET=private",
        "src/dispread/secrets.json": b"private",
        "src/dispread/workbench/static/secrets.json": b"private",
        "src/dispread/workbench/static/credentials.json": b"private",
        "src/dispread/__pycache__/module.pyc": b"cache",
        "src/dispread/token.pem": b"private",
        "src/dispread/private.sqlite": b"private",
        "var/templates.json": b"runtime",
        ".venv/private.py": b"venv",
        "scripts/unrelated.py": b"private",
    }
    for name, content in additions.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (root / "src/dispread/__init__.py").write_text("CHANGED = True\n")
    output = build_release(root, tmp_path / "bundle.tar.gz", template, "release-1")
    with tarfile.open(output) as archive:
        names = set(archive.getnames())
        assert "picam/src/dispread/new_module.py" in names
        assert archive.extractfile("picam/src/dispread/__init__.py").read() == b"CHANGED = True\n"
        assert json.load(archive.extractfile("picam/release.json"))['dirty'] is True
        assert not {f"picam/{name}" for name in additions if name != "src/dispread/new_module.py"} & names


@pytest.mark.parametrize("release_id", ["", "../bad", "a/b", ".", "..", "-bad", "white space", "x\ny", "x" * 129])
def test_rejects_unsafe_release_id_without_artifact(source, tmp_path, release_id):
    root, template = source
    output = tmp_path / "release.tar.gz"
    with pytest.raises(ValueError, match="release"):
        build_release(root, output, template, release_id)
    assert not output.exists()


@pytest.mark.parametrize("problem", ["missing", "wrong", "symlink"])
def test_rejects_invalid_external_template_before_output(source, tmp_path, problem):
    root, template = source
    if problem == "missing":
        template.unlink()
    elif problem == "wrong":
        template.write_text("wrong template")
    else:
        original = template.rename(tmp_path / "original.json")
        template.symlink_to(original)
    output = tmp_path / "release.tar.gz"
    with pytest.raises((ValueError, FileNotFoundError), match="[Tt]emplate|[Vv]orlage|[Ss]ymlink"):
        build_release(root, output, template, "release-1")
    assert not output.exists()


@pytest.mark.parametrize("missing", ["scripts/install.py", "install.sh", "packaging/picam_installer/engine.py", "VERSION",
                                     "packaging/me-fastfetch/me-logo.py"])
def test_rejects_incomplete_source_without_artifact(source, tmp_path, missing):
    root, template = source
    (root / missing).unlink()
    output = tmp_path / "release.tar.gz"
    with pytest.raises((ValueError, FileNotFoundError), match=missing):
        build_release(root, output, template, "release-1")
    assert not output.exists()


@pytest.mark.parametrize("kind", ["existing", "symlink", "inside_source"])
def test_rejects_output_that_could_overwrite_inputs(source, tmp_path, kind):
    root, template = source
    output = tmp_path / "release.tar.gz"
    if kind == "existing":
        output.write_bytes(b"preserve")
    elif kind == "symlink":
        output.symlink_to(tmp_path / "nonexistent")
    else:
        output = root / "release.tar.gz"
    with pytest.raises((ValueError, FileExistsError)):
        build_release(root, output, template, "release-1")
    if kind == "existing":
        assert output.read_bytes() == b"preserve"
    elif kind == "symlink":
        assert output.is_symlink()
    else:
        assert not output.exists()


@pytest.mark.parametrize("linked", ["src/dispread/new_module.py", "src/dispread/link", "packaging/picam_installer/engine.py"])
def test_rejects_symlink_input(source, tmp_path, linked):
    root, template = source
    target = root / linked
    if target.exists():
        target.unlink()
    target.symlink_to(template)
    output = tmp_path / "release.tar.gz"
    with pytest.raises(ValueError, match="[Ss]ymlink"):
        build_release(root, output, template, "release-1")
    assert not output.exists()


def test_ignored_source_and_embedded_template_are_not_used(source, tmp_path):
    root, template = source
    (root / ".gitignore").write_text("src/dispread/local_only.py\n")
    (root / "src/dispread/local_only.py").write_text("LOCAL_SECRET = True\n")
    embedded = root / TEMPLATE_NAME
    embedded.parent.mkdir(parents=True)
    embedded.write_text("unverified source copy")
    output = build_release(root, tmp_path / "bundle.tar.gz", template, "release-1")
    with tarfile.open(output) as archive:
        assert "picam/src/dispread/local_only.py" not in archive.getnames()
        assert archive.extractfile(f"picam/{TEMPLATE_NAME}").read() == template.read_bytes()


@pytest.mark.parametrize("hash_source", ["", 'DEFAULT_TEMPLATES_SHA256 = "invalid"\n', 'DEFAULT_TEMPLATES_SHA256 = dangerous()\n'])
def test_missing_or_nonliteral_template_hash_is_rejected(source, tmp_path, hash_source):
    root, template = source
    (root / "src/dispread/live/__init__.py").write_text(hash_source)
    output = tmp_path / "bundle.tar.gz"
    with pytest.raises(ValueError):
        build_release(root, output, template, "release-1")
    assert not output.exists()


def test_cli_requires_explicit_inputs_and_builds_without_product_import(source, tmp_path):
    import shutil
    import sys

    root, template = source
    script = root / "scripts/build-release.py"
    shutil.copyfile(BUILDER_PATH.parents[1] / "scripts/build-release.py", script)
    shutil.copyfile(BUILDER_PATH, root / "packaging/release.py")
    incomplete = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert incomplete.returncode == 2
    assert "--templates" in incomplete.stderr
    assert "--output" in incomplete.stderr
    assert "--release-id" in incomplete.stderr
    output = tmp_path / "cli-release.tar.gz"
    built = subprocess.run(
        [sys.executable, str(script), "--output", str(output), "--templates", str(template), "--release-id", "cli-1"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert built.returncode == 0, built.stderr
    with tarfile.open(output) as archive:
        assert json.load(archive.extractfile("picam/release.json"))["release_id"] == "cli-1"
