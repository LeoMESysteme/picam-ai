"""`scripts/dotmatrix-dataset.py` (Task 6, Nachverfolgbarkeit und
Datensatz-Lader).

Baut einen Mini-`DatasetStore` von Hand (`devices.json` + `samples/<id>/
sample.json` + `image.png`) direkt in `tmp_path` - keine echte
Datensatzwurzel, kein Kamera-/Portzugriff (siehe AGENTS.md/Auftrag).

Muster fuer das Laden eines hyphenierten Skripts wie in
`tests/test_import_harvest.py`.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from dotmatrix_helpers import GRID, render

from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile

SCRIPT = Path(__file__).parents[1] / "scripts" / "dotmatrix-dataset.py"

_spec = importlib.util.spec_from_file_location("dotmatrix_dataset", SCRIPT)
dotmatrix_dataset = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = dotmatrix_dataset  # dataclasses braucht das Modul in sys.modules
_spec.loader.exec_module(dotmatrix_dataset)

DEVICE_ID = "dev-gsv-161a"
TARGET_SIZE = (400, 160)  # (Breite, Hoehe), passend zu GRID
TEXT = "+0.60972 "  # 9 Zeichen, genau CELL_COUNT
RAW_SIZE = (960, 720)  # (Breite, Hoehe) - volle Kameraframe-Groesse
OFFSET = (300, 300)  # (x, y) der eingebetteten Anzeige im Vollbild


def _quad() -> list[list[float]]:
    x0, y0 = OFFSET
    w, h = TARGET_SIZE
    return [[float(x0), float(y0)], [float(x0 + w), float(y0)], [float(x0 + w), float(y0 + h)], [float(x0), float(y0 + h)]]


def _full_frame() -> np.ndarray:
    """Ein 960x720-Vollbild (wie eine echte Kameraaufnahme) mit dem
    gerenderten Anzeigeninhalt an einer bekannten Stelle eingebettet."""
    gray = render(TEXT, grid=GRID, size=TARGET_SIZE)
    content = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    frame = np.full((RAW_SIZE[1], RAW_SIZE[0], 3), 200, dtype=np.uint8)
    x0, y0 = OFFSET
    w, h = TARGET_SIZE
    frame[y0 : y0 + h, x0 : x0 + w] = content
    return frame


def _write_devices(dataset_root: Path) -> None:
    devices = {
        "schema_version": 1,
        "devices": {
            DEVICE_ID: {
                "id": DEVICE_ID,
                "revision": 0,
                "identity_confirmed": True,
                "groups": {},
                "name": "gsv-sensor-161a",
                "model": None,
                "family": "gsv2as",
                "technology": "LCD",
                "split": "development",
                "identity_evidence": "Test",
            }
        },
    }
    dataset_root.mkdir(parents=True, exist_ok=True)
    (dataset_root / "devices.json").write_text(json.dumps(devices, ensure_ascii=False), encoding="utf-8")


def _write_sample(dataset_root: Path, sample_id: str, detail: dict) -> None:
    sample_dir = dataset_root / "samples" / sample_id
    sample_dir.mkdir(parents=True)
    cv2.imwrite(str(sample_dir / "image.png"), _full_frame())
    sample = {
        "schema_version": 2,
        "id": sample_id,
        "device_id": DEVICE_ID,
        "label_state": "readable",
        "expected_text": "0.60972",
        "label_origin": "serial_ascii",
        "label_origin_detail": detail,
    }
    (sample_dir / "sample.json").write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")


def _base_detail(session_id: str, plateau: tuple[int, int] = (1_000, 2_000)) -> dict:
    return {
        "session_id": session_id,
        "cell_text": TEXT.ljust(16),
        "plateau_start_ns": plateau[0],
        "plateau_end_ns": plateau[1],
    }


def _save_profile(tmp_path: Path) -> Path:
    profile = SessionProfile(
        schema_version=PROFILE_SCHEMA_VERSION,
        device_id="gsv-sensor-161a",
        session_id="sessB",
        quad=_quad(),
        target_size=TARGET_SIZE,
        grid=GRID,
        scaler_crop=None,
        min_source_dot_column_px=5.0,
        native_scale=1.0,
        min_native_dot_column_px=5.0,
        resolution_threshold_px=2.0,
        resolution_ok=True,
        confirmed_by="tester",
        confirmed_at_utc="2026-09-24T12:00:00+00:00",
    )
    path = tmp_path / "sessB-profile.json"
    profile.save(path)
    return path


def test_load_cell_samples_resolves_profile_from_detail_or_map_and_counts_missing(tmp_path):
    dataset_root = tmp_path / "dataset"
    _write_devices(dataset_root)

    # Probe A: Profil direkt in label_origin_detail (Task 6, neuer Import).
    detail_a = _base_detail("sessA")
    detail_a["profile_quad"] = json.dumps([[round(x, 2), round(y, 2)] for x, y in _quad()])
    grid_dict = GRID.to_dict()
    grid_dict["target_size"] = list(TARGET_SIZE)
    detail_a["profile_grid"] = json.dumps(grid_dict)
    _write_sample(dataset_root, "sample-a", detail_a)

    # Probe B: nur session_id, Profil kommt aus profile_map (Pruefsumme passt).
    detail_b = _base_detail("sessB")
    _write_sample(dataset_root, "sample-b", detail_b)
    profile_path = _save_profile(tmp_path)
    profile_map = {"sessB": {"path": str(profile_path), "sha256": dotmatrix_dataset._profile_sha256(profile_path)}}

    # Probe C: weder profile_quad/profile_grid im Detail noch ein Eintrag in
    # profile_map fuer ihre session_id - nicht aufloesbar.
    detail_c = _base_detail("sessC")
    _write_sample(dataset_root, "sample-c", detail_c)

    stats: dict[str, int] = {}
    samples = dotmatrix_dataset.load_cell_samples(dataset_root, profile_map, stats=stats)

    assert len(samples) == 2
    ids = {s.sample_id for s in samples}
    assert ids == {"sample-a", "sample-b"}
    for s in samples:
        assert s.cell_text == TEXT
        assert s.vectors.shape == (9, 9, 40)
        assert s.plateau == (1_000, 2_000)
    groups = {s.sample_id: s.group for s in samples}
    assert groups == {"sample-a": "sessA", "sample-b": "sessB"}

    assert stats["ohne_profil"] == 1


def test_load_cell_samples_ignores_wrong_device_and_state(tmp_path):
    dataset_root = tmp_path / "dataset"
    _write_devices(dataset_root)

    # Falsches Geraet.
    sample_dir = dataset_root / "samples" / "other-device"
    sample_dir.mkdir(parents=True)
    cv2.imwrite(str(sample_dir / "image.png"), _full_frame())
    detail = _base_detail("sessA")
    detail["profile_quad"] = json.dumps([[round(x, 2), round(y, 2)] for x, y in _quad()])
    grid_dict = GRID.to_dict()
    grid_dict["target_size"] = list(TARGET_SIZE)
    detail["profile_grid"] = json.dumps(grid_dict)
    sample = {
        "schema_version": 2,
        "id": "other-device",
        "device_id": "irgendein-anderes-geraet",
        "label_state": "readable",
        "label_origin": "serial_ascii",
        "label_origin_detail": detail,
    }
    (sample_dir / "sample.json").write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")

    # Nicht lesbar.
    detail_unreadable = dict(detail)
    _write_sample(dataset_root, "unreadable", detail_unreadable)
    unreadable_path = dataset_root / "samples" / "unreadable" / "sample.json"
    unreadable_sample = json.loads(unreadable_path.read_text(encoding="utf-8"))
    unreadable_sample["label_state"] = "unreadable"
    unreadable_path.write_text(json.dumps(unreadable_sample, ensure_ascii=False), encoding="utf-8")

    samples = dotmatrix_dataset.load_cell_samples(dataset_root, {})
    assert samples == []


def test_write_map_and_read_profile_map_roundtrip(tmp_path):
    profile_a = tmp_path / "a-profile.json"
    profile_b = tmp_path / "b-profile.json"
    profile_a.write_text("dummy-a", encoding="utf-8")
    profile_b.write_text("dummy-b", encoding="utf-8")

    original_paths = dict(dotmatrix_dataset.SESSION_PROFILE_PATHS)
    dotmatrix_dataset.SESSION_PROFILE_PATHS = {"ernte1": profile_a, "auf2": profile_b}
    try:
        out_path = tmp_path / "map.json"
        args = dotmatrix_dataset.parse_args(["write-map", "--out", str(out_path)])
        rc = args.func(args)
        assert rc == 0

        written = json.loads(out_path.read_text(encoding="utf-8"))
        assert set(written) == {"ernte1", "auf2"}
        assert written["ernte1"]["sha256"] == dotmatrix_dataset._profile_sha256(profile_a)

        profile_map = dotmatrix_dataset.read_profile_map(out_path)
        assert profile_map["ernte1"]["path"] == str(profile_a)
        assert profile_map["ernte1"]["sha256"] == dotmatrix_dataset._profile_sha256(profile_a)
        assert profile_map["auf2"]["path"] == str(profile_b)
        assert profile_map["auf2"]["sha256"] == dotmatrix_dataset._profile_sha256(profile_b)
    finally:
        dotmatrix_dataset.SESSION_PROFILE_PATHS = original_paths


def test_load_cell_samples_skips_sample_when_map_profile_was_reconfirmed(tmp_path):
    """Fix Runde 1 (Review-Befund): die `profile_map` traegt die `sha256`,
    die `write-map` beim Schreiben gemessen hat. Wird die Profildatei DANACH
    erneut bestaetigt (anderes Quad/Raster), darf die Probe NICHT mit dem
    neuen Profil entzerrt werden - sie wird uebersprungen und gezaehlt."""
    dataset_root = tmp_path / "dataset"
    _write_devices(dataset_root)

    detail = _base_detail("sessB")
    _write_sample(dataset_root, "sample-b", detail)

    profile_path = _save_profile(tmp_path)
    recorded_sha256 = dotmatrix_dataset._profile_sha256(profile_path)
    profile_map = {"sessB": {"path": str(profile_path), "sha256": recorded_sha256}}

    # Sitzung wurde nach write-map erneut bestaetigt - andere Profildatei am
    # selben Pfad (anderer Inhalt, damit auch der Hash anders ist).
    reconfirmed = SessionProfile(
        schema_version=PROFILE_SCHEMA_VERSION,
        device_id="gsv-sensor-161a",
        session_id="sessB",
        quad=[[0.0, 0.0], [399.0, 0.0], [399.0, 159.0], [0.0, 159.0]],
        target_size=TARGET_SIZE,
        grid=GRID,
        scaler_crop=None,
        min_source_dot_column_px=5.0,
        native_scale=1.0,
        min_native_dot_column_px=5.0,
        resolution_threshold_px=2.0,
        resolution_ok=True,
        confirmed_by="tester",
        confirmed_at_utc="2026-09-24T13:00:00+00:00",
    )
    reconfirmed.save(profile_path)
    assert dotmatrix_dataset._profile_sha256(profile_path) != recorded_sha256

    stats: dict[str, int] = {}
    samples = dotmatrix_dataset.load_cell_samples(dataset_root, profile_map, stats=stats)

    assert samples == []
    assert stats["profil_pruefsumme_abweichend"] == 1
    assert stats["ohne_profil"] == 0


def test_load_cell_samples_treats_map_entry_without_sha256_as_unresolved(tmp_path):
    dataset_root = tmp_path / "dataset"
    _write_devices(dataset_root)

    detail = _base_detail("sessB")
    _write_sample(dataset_root, "sample-b", detail)

    profile_path = _save_profile(tmp_path)
    profile_map = {"sessB": {"path": str(profile_path)}}  # keine sha256

    stats: dict[str, int] = {}
    samples = dotmatrix_dataset.load_cell_samples(dataset_root, profile_map, stats=stats)

    assert samples == []
    assert stats["ohne_profil"] == 1
    assert stats["profil_pruefsumme_abweichend"] == 0
