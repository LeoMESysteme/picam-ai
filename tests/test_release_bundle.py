"""Release archives contain verified product inputs, never runtime state."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

BUILDER_PATH = Path(__file__).parents[1] / "packaging" / "release.py"
SENSOR_DIR = "src/dispread/data/sensors/gsv2as-161a"
TEMPLATE_NAME = f"{SENSOR_DIR}/templates.json"
LEGACY_TEMPLATE = "src/dispread/data/templates-stufe2c-2026-09-30.json"
SHA256 = "6f20dec4f558e98be41203d0ab48eb4788d16e02c1350313a740c25cc03f693a"
sys.path.insert(0, str(BUILDER_PATH.parent))


from release import build_release  # noqa: E402


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    shutil.copytree(BUILDER_PATH.parents[1] / SENSOR_DIR, root / SENSOR_DIR, copy_function=shutil.copyfile)
    files = {
        "src/dispread/__init__.py": "",
        "src/dispread/live/__init__.py": "raise RuntimeError('kein Produktimport beim Bauen')\n",
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
    shutil.copyfile(BUILDER_PATH.parent / "picam_installer/archive.py", root / "packaging/picam_installer/archive.py")
    (root / "install.sh").chmod(0o755)
    git(root, "init", "--quiet")
    git(root, "add", ".")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "fixture")
    return root


def test_bundle_contains_verified_payload_manifest_and_executable(source, tmp_path):
    root = source
    output = tmp_path / "release.tar.gz"
    assert build_release(root, output, "1.2.3") == output
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
        assert archive.extractfile(files[TEMPLATE_NAME]).read() == (root / TEMPLATE_NAME).read_bytes()
        assert manifest["files"][TEMPLATE_NAME] == manifest["files"][LEGACY_TEMPLATE] == SHA256
        for name in ("sensor.json", "display.json", "README.md"):
            assert f"{SENSOR_DIR}/{name}" in files
        assert files["install.sh"].mode == 0o755
        assert "scripts/install.py" in files
        assert "packaging/picam_installer/__main__.py" in files
        assert {"packaging/picam_installer/tui.py", "packaging/picam_installer/fastfetch.py"} <= set(files)
        assert {f"packaging/me-fastfetch/{name}" for name in
                ("me-logo.py", "me-fastfetch.in", "config.jsonc", "me-logo.txt")} <= set(files)


def test_me_fastfetch_extras_are_not_bundled(source, tmp_path):
    root = source
    for name in ("packaging/me-fastfetch/me-logo.py.bak", "packaging/me-fastfetch/notes.md"):
        (root / name).write_text("private\n")
    output = build_release(root, tmp_path / "bundle.tar.gz", "release-1")
    with tarfile.open(output) as archive:
        names = set(archive.getnames())
    assert "picam/packaging/me-fastfetch/config.jsonc" in names
    assert not {"picam/packaging/me-fastfetch/me-logo.py.bak", "picam/packaging/me-fastfetch/notes.md"} & names


def test_reproducible_bytes_ignore_source_mtime(source, tmp_path):
    root = source
    first = build_release(root, tmp_path / "first.tar.gz", "release-1")
    import os
    for path in root.rglob("*"):
        if path.is_file():
            os.utime(path, (345678, 345678))
    second = build_release(root, tmp_path / "second.tar.gz", "release-1")
    assert first.read_bytes() == second.read_bytes()
    assert first.read_bytes()[4:8] == b"\0\0\0\0"


def test_bundle_uses_current_product_sources_and_excludes_private_files(source, tmp_path):
    root = source
    additions = {
        "src/dispread/new_module.py": b"NEW = True\n",
        "src/dispread/.env": b"SECRET=private",
        "src/dispread/secrets.json": b"private",
        "src/dispread/workbench/static/secrets.json": b"private",
        "src/dispread/workbench/static/credentials.json": b"private",
        "src/dispread/__pycache__/module.pyc": b"cache",
        "src/dispread/token.pem": b"private",
        "src/dispread/private.sqlite": b"private",
        f"{SENSOR_DIR}/unerwartet.py": b"kein Paketcode",
        "var/templates.json": b"runtime",
        ".venv/private.py": b"venv",
        "scripts/unrelated.py": b"private",
    }
    for name, content in additions.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (root / "src/dispread/__init__.py").write_text("CHANGED = True\n")
    output = build_release(root, tmp_path / "bundle.tar.gz", "release-1")
    with tarfile.open(output) as archive:
        names = set(archive.getnames())
        assert "picam/src/dispread/new_module.py" in names
        assert archive.extractfile("picam/src/dispread/__init__.py").read() == b"CHANGED = True\n"
        assert json.load(archive.extractfile("picam/release.json"))['dirty'] is True
        assert not {f"picam/{name}" for name in additions if name != "src/dispread/new_module.py"} & names


@pytest.mark.parametrize("release_id", ["", "../bad", "a/b", ".", "..", "-bad", "white space", "x\ny", "x" * 129])
def test_rejects_unsafe_release_id_without_artifact(source, tmp_path, release_id):
    root = source
    output = tmp_path / "release.tar.gz"
    with pytest.raises(ValueError, match="release"):
        build_release(root, output, release_id)
    assert not output.exists()


@pytest.mark.parametrize("problem", ["missing", "wrong", "symlink"])
def test_rejects_invalid_packaged_template_before_output(source, tmp_path, problem):
    root = source
    template = root / TEMPLATE_NAME
    if problem == "missing":
        template.unlink()
    elif problem == "wrong":
        template.write_text("wrong template")
    else:
        original = template.rename(tmp_path / "original.json")
        template.symlink_to(original)
    output = tmp_path / "release.tar.gz"
    with pytest.raises((ValueError, FileNotFoundError), match="[Tt]emplate|[Vv]orlage|[Ss]ymlink"):
        build_release(root, output, "release-1")
    assert not output.exists()


@pytest.mark.parametrize("missing", ["scripts/install.py", "install.sh", "packaging/picam_installer/engine.py", "VERSION",
                                     "packaging/me-fastfetch/me-logo.py", f"{SENSOR_DIR}/sensor.json",
                                     f"{SENSOR_DIR}/display.json"])
def test_rejects_incomplete_source_without_artifact(source, tmp_path, missing):
    root = source
    (root / missing).unlink()
    output = tmp_path / "release.tar.gz"
    with pytest.raises((ValueError, FileNotFoundError), match=missing):
        build_release(root, output, "release-1")
    assert not output.exists()


@pytest.mark.parametrize("kind", ["existing", "symlink", "inside_source"])
def test_rejects_output_that_could_overwrite_inputs(source, tmp_path, kind):
    root = source
    output = tmp_path / "release.tar.gz"
    if kind == "existing":
        output.write_bytes(b"preserve")
    elif kind == "symlink":
        output.symlink_to(tmp_path / "nonexistent")
    else:
        output = root / "release.tar.gz"
    with pytest.raises((ValueError, FileExistsError)):
        build_release(root, output, "release-1")
    if kind == "existing":
        assert output.read_bytes() == b"preserve"
    elif kind == "symlink":
        assert output.is_symlink()
    else:
        assert not output.exists()


@pytest.mark.parametrize("linked", ["src/dispread/new_module.py", "src/dispread/link", "packaging/picam_installer/engine.py"])
def test_rejects_symlink_input(source, tmp_path, linked):
    root = source
    target = root / linked
    if target.exists():
        target.unlink()
    target.symlink_to(root / TEMPLATE_NAME)
    output = tmp_path / "release.tar.gz"
    with pytest.raises(ValueError, match="[Ss]ymlink"):
        build_release(root, output, "release-1")
    assert not output.exists()


def test_ignored_source_and_legacy_template_are_not_used(source, tmp_path):
    root = source
    (root / ".gitignore").write_text("src/dispread/local_only.py\n")
    (root / "src/dispread/local_only.py").write_text("LOCAL_SECRET = True\n")
    embedded = root / LEGACY_TEMPLATE
    embedded.parent.mkdir(parents=True, exist_ok=True)
    embedded.write_text("unverified source copy")
    output = build_release(root, tmp_path / "bundle.tar.gz", "release-1")
    with tarfile.open(output) as archive:
        assert "picam/src/dispread/local_only.py" not in archive.getnames()
        assert archive.extractfile(f"picam/{LEGACY_TEMPLATE}").read() == (root / TEMPLATE_NAME).read_bytes()


@pytest.mark.parametrize("metadata", [{}, {"file": "templates.json", "sha256": "0" * 64},
                                      {"file": "andere.json", "sha256": SHA256}])
def test_bad_template_reference_is_rejected(source, tmp_path, metadata):
    root = source
    path = root / SENSOR_DIR / "sensor.json"
    sensor = json.loads(path.read_text())
    sensor["templates"] = metadata
    path.write_text(json.dumps(sensor))
    output = tmp_path / "bundle.tar.gz"
    with pytest.raises(ValueError, match="Vorlage"):
        build_release(root, output, "release-1")
    assert not output.exists()


def test_cli_requires_explicit_inputs_and_builds_without_product_import(source, tmp_path):
    root = source
    script = root / "scripts/build-release.py"
    shutil.copyfile(BUILDER_PATH.parents[1] / "scripts/build-release.py", script)
    shutil.copyfile(BUILDER_PATH, root / "packaging/release.py")
    incomplete = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert incomplete.returncode == 2
    assert "--output" in incomplete.stderr
    assert "--release-id" in incomplete.stderr
    output = tmp_path / "cli-release.tar.gz"
    built = subprocess.run(
        [sys.executable, str(script), "--output", str(output), "--release-id", "cli-1"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert built.returncode == 0, built.stderr
    obsolete = subprocess.run(
        [sys.executable, str(script), "--output", str(output), "--release-id", "cli-1", "--templates", str(root / TEMPLATE_NAME)],
        capture_output=True, text=True,
    )
    assert obsolete.returncode == 2
    assert "--templates" in obsolete.stderr
    with tarfile.open(output) as archive:
        assert json.load(archive.extractfile("picam/release.json"))["release_id"] == "cli-1"


def test_stable_bundle_sets_delivery_version_only(source, tmp_path):
    root = source
    (root / "VERSION").write_text('0.1.0.dev0\n')
    stable = build_release(root, tmp_path / 'stable.tar.gz', '1.1.0')
    dev = build_release(root, tmp_path / 'rc.tar.gz', 'rc-abcdef')
    for path, release_id, version in [(stable, '1.1.0', b'1.1.0\n'), (dev, 'rc-abcdef', b'0.1.0.dev0\n')]:
        with tarfile.open(path, 'r:gz') as bundle:
            assert bundle.extractfile('picam/VERSION').read() == version
            manifest = json.load(bundle.extractfile('picam/release.json'))
            assert manifest['release_id'] == release_id
            assert manifest['files']['VERSION'] == hashlib.sha256(version).hexdigest()
    assert (root / "VERSION").read_text() == '0.1.0.dev0\n'


@pytest.mark.parametrize('state', ['clean', 'dirty', 'wrong-tag'])
def test_publish_dry_run(source, tmp_path, monkeypatch, state):
    from dispread.release_source import REPOSITORY

    root = source
    actual = BUILDER_PATH.parents[1]
    script = root / 'scripts/publish-release.py'
    script.write_bytes((actual / 'scripts/publish-release.py').read_bytes())
    path = root / 'src/dispread/release_source.py'
    path.write_bytes((actual / 'src/dispread/release_source.py').read_bytes())
    (root / 'CHANGELOG.md').write_text('## 1.1.0 — 2026-11-25\n\nErster Release.\n')
    # Neither building nor publishing is allowed in this test.
    (root / 'scripts/build-release.py').write_text('raise SystemExit("build called")')
    gh = tmp_path / 'gh'
    gh.write_text('#!/bin/sh\ntouch "$(dirname "$0")/external-call"\nexit 1\n')
    gh.chmod(0o755)
    monkeypatch.setenv('PATH', f'{tmp_path}:/usr/bin:/bin')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'publisher')
    git(root, 'tag', 'v1.1.0', 'HEAD^' if state == 'wrong-tag' else 'HEAD')
    if state == 'dirty':
        (root / 'untracked').touch()
    result = subprocess.run([sys.executable, str(script), 'v1.1.0', '--dry-run'],
                            text=True, capture_output=True, check=False)
    assert not (tmp_path / 'external-call').exists()
    if state == 'clean':
        assert result.returncode == 0, result.stderr
        assert '--release-id 1.1.0' in result.stdout
        assert 'picam-1.1.0.tar.gz.sha256' in result.stdout
        assert 'gh release create v1.1.0' in result.stdout
        assert f'--repo {REPOSITORY}' in result.stdout
        assert '--verify-tag' in result.stdout
    else:
        assert result.returncode == 1
        assert ('Arbeitsbaum muss sauber sein' if state == 'dirty' else 'muss auf HEAD zeigen') in result.stderr
