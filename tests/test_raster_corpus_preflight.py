"""The offline corpus evaluator must reject stale or incomplete resumed inputs."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs/quellen/raster-recherche-2026-11-13/korpus/evaluate.py"
CODE = ROOT / "src/dispread/dotlattice.py"


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def corpus(tmp_path):
    script = tmp_path / "evaluate.py"
    script.write_bytes(SCRIPT.read_bytes())
    image = tmp_path / "var/live/live-20261113T000000Z/setup/still.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"original image")
    label = image.parent / "cell-text.json"
    label.write_bytes(b"[]")
    rel = str(image.relative_to(tmp_path))
    manifest = {"path": rel, "sha256": digest(image.read_bytes()),
                "cell_text_sha256": digest(label.read_bytes())}
    (tmp_path / "manifest.jsonl").write_text(json.dumps(manifest) + "\n")
    row = {"path": rel, "sha256": manifest["sha256"], "hypothesis_sha256": digest(CODE.read_bytes())}
    (tmp_path / "trial-shard-0.jsonl").write_text(json.dumps(row) + "\n")
    return tmp_path, script, image, label, row


def run(corpus, *, shard="0", shards="1"):
    root, script, *_ = corpus
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"),
           "DISPREAD_DEV_DATA": str(root / "dev"), "RASTER_VARIANT": "trial",
           "RASTER_CODE_SHA256": digest(CODE.read_bytes()), "RASTER_SHARD": shard,
           "RASTER_SHARDS": shards}
    return subprocess.run([str(ROOT / ".venv/bin/python"), str(script)], cwd=root,
                          env=env, capture_output=True, text=True, timeout=30)


def test_missing_manifest_input_is_rejected(corpus):
    corpus[2].unlink()
    result = run(corpus)
    assert result.returncode != 0
    assert "manifest" in result.stderr.lower()


def test_extra_discovered_input_is_rejected(corpus):
    (corpus[2].parent / "still-versuch-1.png").write_bytes(b"extra")
    result = run(corpus)
    assert result.returncode != 0
    assert "manifest" in result.stderr.lower()


@pytest.mark.parametrize("index", [2, 3], ids=["image", "label"])
def test_changed_input_is_rejected_before_resume(corpus, index):
    corpus[index].write_bytes(b"changed")
    result = run(corpus)
    assert result.returncode != 0
    assert "manifest" in result.stderr.lower()


@pytest.mark.parametrize("bad_hash", ["other", None], ids=["wrong", "missing"])
def test_foreign_or_unlabeled_other_shard_is_rejected(corpus, bad_hash):
    row = {**corpus[4], "hypothesis_sha256": bad_hash}
    if bad_hash is None:
        del row["hypothesis_sha256"]
    (corpus[0] / "trial-shard-1.jsonl").write_text(json.dumps(row) + "\n")
    result = run(corpus)
    assert result.returncode != 0
    assert "hypothesis" in result.stderr.lower()


def test_unchanged_completed_input_can_resume(corpus):
    result = run(corpus)
    assert result.returncode == 0, result.stderr


def test_changed_input_is_rejected_even_on_another_shard(corpus):
    corpus[2].write_bytes(b"changed")
    result = run(corpus, shard="1", shards="2")
    assert result.returncode != 0
    assert "manifest" in result.stderr.lower()


def test_incomplete_own_shard_is_not_resumed(corpus):
    (corpus[0] / "trial-shard-0.jsonl").write_text('{"path":')
    result = run(corpus)
    assert result.returncode != 0
    assert "incomplete" in result.stderr.lower()
