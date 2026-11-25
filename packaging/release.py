"""Build a reproducible, explicit delivery without importing the product."""
from __future__ import annotations

import ast
import gzip
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path

TEMPLATE_PATH = "src/dispread/data/templates-stufe2c-2026-09-30.json"
INSTALLER_MODULES = ("__init__", "platform", "archive", "engine", "guided", "tui", "fastfetch", "update", "uninstall",
                     "__main__")
# Optionale Komponente me-fastfetch: der Installer kopiert sie ins Home des Bedienerkontos.
FASTFETCH_FILES = ("me-logo.py", "me-fastfetch.in", "config.jsonc", "me-logo.txt")
REQUIRED_FILES = (
    "pyproject.toml",
    "VERSION",
    "packaging/apt-packages.txt",
    "scripts/install.py",
    "install.sh",
    *(f"packaging/picam_installer/{name}.py" for name in INSTALLER_MODULES),
    *(f"packaging/me-fastfetch/{name}" for name in FASTFETCH_FILES),
    "src/dispread/__init__.py",
    "src/dispread/live/__init__.py",
)
STATIC_SUFFIXES = {".html", ".js", ".css", ".json", ".jpg", ".jpeg", ".png", ".svg", ".woff2", ".ico"}


def _no_symlink(path: Path) -> None:
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise ValueError(f"Symlink input is not allowed: {candidate}")


def _read_regular(path: Path) -> tuple[bytes, int]:
    _no_symlink(path)
    # O_NOFOLLOW also closes the final-component link race between check and open.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"Input is not a regular file: {path}")
        return stream.read(), 0o755 if info.st_mode & 0o111 else 0o644


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE).decode()
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"Source must be a Git worktree: {root}") from exc


def _product_path(name: str) -> bool:
    path = Path(name)
    if any(part.startswith(".") or part == "__pycache__" for part in path.parts):
        return False
    private_names = {"secret", "secrets", "credential", "credentials", "private", "token", "tokens"}
    if any(Path(part).stem.lower() in private_names for part in path.parts):
        return False
    if name.startswith("packaging/picam_installer/"):
        return path.suffix == ".py"
    if name.startswith("packaging/me-fastfetch/"):
        return path.name in FASTFETCH_FILES
    if not name.startswith("src/dispread/") or name == TEMPLATE_PATH:
        return False
    if path.suffix == ".py":
        return True
    if name.startswith("src/dispread/workbench/static/"):
        return path.suffix in STATIC_SUFFIXES or path.name == "LICENSE.noto"
    return name == "src/dispread/workbench/PRODUCT.md"


def _template_hash(live_source: bytes) -> str:
    values = []
    for node in ast.parse(live_source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "DEFAULT_TEMPLATES_SHA256" for target in node.targets
        ):
            values.append(ast.literal_eval(node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "DEFAULT_TEMPLATES_SHA256":
                values.append(ast.literal_eval(node.value))
    if len(values) != 1 or not isinstance(values[0], str) or not re.fullmatch(r"[0-9a-f]{64}", values[0]):
        raise ValueError("Product template SHA256 constant is missing or invalid")
    return values[0]


def _tar_entry(name: str, mode: int, size: int = 0, *, directory: bool = False) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.mode = mode
    info.size = size
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    if directory:
        info.type = tarfile.DIRTYPE
    return info


def build_release(root: Path, output: Path, templates: Path, release_id: str) -> Path:
    """Snapshot allowlisted worktree files into a new tar.gz outside the source.

    ``commit`` identifies HEAD; ``dirty`` explicitly records deviations and new
    files. The archive hashes describe the delivered bytes even for a dirty tree.
    Existing outputs, including dangling links, are never replaced.
    """
    if not isinstance(release_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", release_id):
        raise ValueError("Invalid release ID: use 1–128 ASCII letters, digits, dot, dash or underscore")
    root, output, templates = Path(root).absolute(), Path(output).absolute(), Path(templates).absolute()
    _no_symlink(root)
    _no_symlink(output)
    if output.exists():
        raise FileExistsError(f"Release output already exists: {output}")
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Release output must be outside the source worktree")
    if not output.parent.is_dir():
        raise ValueError(f"Release output directory does not exist: {output.parent}")

    contents: dict[str, tuple[bytes, int]] = {}
    for name in REQUIRED_FILES:
        contents[name] = _read_regular(root / name)
    try:
        template_data, _ = _read_regular(templates)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Template file is missing: {templates}") from exc
    if hashlib.sha256(template_data).hexdigest() != _template_hash(contents["src/dispread/live/__init__.py"][0]):
        raise ValueError("Template SHA256 does not match the frozen product template")

    commit = _git(root, "rev-parse", "HEAD").strip()
    dirty = bool(_git(root, "status", "--porcelain", "--untracked-files=normal"))
    candidates = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "src", "packaging/picam_installer", "packaging/me-fastfetch").split("\0")
    # Reject links anywhere in candidate trees, including links whose suffix
    # would otherwise exclude them. Never traverse directory symlinks.
    for folder in (root / "src", root / "packaging/picam_installer", root / "packaging/me-fastfetch"):
        _no_symlink(folder)
        for parent, directories, filenames in os.walk(folder, followlinks=False):
            for name in (*directories, *filenames):
                if (Path(parent) / name).is_symlink():
                    raise ValueError(f"Symlink input is not allowed: {Path(parent) / name}")
    for name in sorted(set(candidates)):
        if _product_path(name) and name not in contents:
            contents[name] = _read_regular(root / name)
    contents[TEMPLATE_PATH] = (template_data, 0o644)
    if re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", release_id):
        contents["VERSION"] = ((release_id + "\n").encode("ascii"), contents["VERSION"][1])
    manifest = {
        "schema": 1,
        "release_id": release_id,
        "commit": commit,
        "dirty": dirty,
        "files": {name: hashlib.sha256(data).hexdigest() for name, (data, _) in sorted(contents.items())},
    }
    contents["release.json"] = ((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(), 0o644)
    directories = {"picam"}
    for name in contents:
        directories.update(str(parent) for parent in (Path("picam") / name).parents if str(parent) != ".")

    # Stage in the output directory, then publish atomically with an exclusive
    # hard link: a concurrent builder cannot clobber an existing output.
    descriptor, temporary_name = tempfile.mkstemp(prefix=".picam-release-", dir=output.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                with tarfile.open(mode="w", fileobj=compressed, format=tarfile.PAX_FORMAT) as archive:
                    for name in sorted(directories):
                        archive.addfile(_tar_entry(name, 0o755, directory=True))
                    for name, (data, mode) in sorted(contents.items()):
                        archive.addfile(_tar_entry(f"picam/{name}", mode, len(data)), io.BytesIO(data))
            raw.flush()
            os.fsync(raw.fileno())
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output
