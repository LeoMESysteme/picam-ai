"""Unveränderlicher, direkt auswertbarer Export (Aufgabe 6).

Prüft `DatasetStore.export()` gegen den echten Experiment-Loader aus
`codex/automatic-seven-segment` (6a18bdf), ohne dessen Code zu duplizieren -
`scripts/check-dataset-export.py` startet dafür einen separaten Prozess mit
dem *eigenen* venv jenes Worktrees. Fehlt dieser Worktree (z. B. auf einer
anderen Maschine), werden die Loader-Integrationstests übersprungen statt
stillschweigend zu bestehen - ein fehlender Experimentstand ist kein
Bestehen, nur kein hier lauffähiger Test.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import pytest

from dispread.workbench.datasets import DatasetStore

SCRIPT = Path(__file__).parents[1] / "scripts" / "check-dataset-export.py"
EXPERIMENT_ROOT = Path("/home/me-systeme/picam-ai-auto-seven-segment")
REAL_IMAGE = EXPERIMENT_ROOT / "experiments" / "automatic_seven_segment" / "data" / "scale.jpg"

pytestmark = pytest.mark.skipif(not REAL_IMAGE.is_file(), reason="Experiment-Worktree mit Realbild nicht vorhanden")


def _real_manifest_entry():
    manifest = json.loads(
        (EXPERIMENT_ROOT / "experiments" / "automatic_seven_segment" / "manifest.json").read_text()
    )
    return next(sample for sample in manifest["samples"] if sample["id"] == "scale")


def _device_payload(**overrides):
    payload = {
        "name": "Küchenwaage",
        "model": "Silvercrest",
        "family": "scale",
        "technology": "LCD",
        "split": "development",
        "identity_confirmed": True,
        "identity_evidence": "Wikimedia Commons: lizenziertes Originalfoto, siehe source/license",
    }
    payload.update(overrides)
    return payload


def _capture_with_real_image(device_id, group_id, entry, token="real-1"):
    image = cv2.imread(str(REAL_IMAGE))
    assert image is not None
    return {
        "image": image,
        "capture_token": token,
        "device_id": device_id,
        "group_id": group_id,
        "source_id": "folder",
        "frame_sequence": 1,
        "capture_timestamp": {"value_ns": 0, "base": "file_mtime"},
        "source_revision": 1,
        "synthetic": False,
        "stored_at_utc": "2026-09-18T12:00:00+00:00",
        "source": entry["source"],
        "license": entry["license"],
    }


def _annotation_from_real_entry(entry):
    return {
        "bbox": entry["bbox"],
        "target_label": entry.get("family"),
        "label_state": "readable",
        "expected_text": entry["expected_text"],
        "conditions": entry["conditions"],
    }


def _build_real_export(tmp_path):
    entry = _real_manifest_entry()
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Originalfoto, unverändert übernommen")
    store.save_sample(_capture_with_real_image(device["id"], group["group_id"], entry), _annotation_from_real_entry(entry))
    return store.export()


def test_real_export_is_accepted_by_the_actual_experiment_loader(tmp_path):
    result = _build_real_export(tmp_path)
    manifest_path = result["path"] / "manifest.json"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(manifest_path), "--experiment-root", str(EXPERIMENT_ROOT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "bestanden" in completed.stdout


def test_modified_image_file_is_rejected(tmp_path):
    result = _build_real_export(tmp_path)
    manifest_path = result["path"] / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    image_path = result["path"] / manifest["samples"][0]["path"]
    original = image_path.read_bytes()
    image_path.write_bytes(original[:-1] + bytes([original[-1] ^ 0xFF]))

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(manifest_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 1
    assert "Bildhash" in completed.stderr


def test_local_check_without_experiment_root_reports_unchecked_not_a_pass(tmp_path):
    result = _build_real_export(tmp_path)
    manifest_path = result["path"] / "manifest.json"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(manifest_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0
    assert "NICHT GEPRÜFT" in completed.stdout


def test_export_survives_being_moved_to_another_directory_and_cwd(tmp_path):
    result = _build_real_export(tmp_path)
    moved = tmp_path / "moved-elsewhere"
    shutil.move(str(result["path"]), str(moved))
    other_cwd = tmp_path / "somewhere-else"
    other_cwd.mkdir()

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(moved / "manifest.json"), "--experiment-root", str(EXPERIMENT_ROOT)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=other_cwd,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_later_label_correction_does_not_change_an_existing_export(tmp_path):
    entry = _real_manifest_entry()
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Originalfoto")
    store.save_sample(_capture_with_real_image(device["id"], group["group_id"], entry), _annotation_from_real_entry(entry))
    first_export = store.export()
    first_manifest = json.loads((first_export["path"] / "manifest.json").read_text())

    # Eine spaetere "Korrektur" ist hier ein neuer, unabhaengig gespeicherter
    # Sample-Datensatz (ein bereits veroeffentlichtes Sample-Verzeichnis ist
    # unveraenderlich) - der alte Export darf davon nichts mitbekommen.
    other_group = store.begin_group(device["id"], "Korrigierte Ablesung, neue Aufnahme")
    corrected = dict(_annotation_from_real_entry(entry))
    corrected["expected_text"] = "99.9"
    store.save_sample(
        _capture_with_real_image(device["id"], other_group["group_id"], entry, token="real-2"), corrected
    )

    unchanged_manifest = json.loads((first_export["path"] / "manifest.json").read_text())
    assert unchanged_manifest == first_manifest
