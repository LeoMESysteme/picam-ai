"""Verhaltenstests für den geführten Datensatz-Sammelmodus (Aufgabe 1).

Diese Tests kennen keine Kamera und keinen ``Controller`` - ``DatasetStore``
bekommt ein bereits eingefrorenes Rohbild (hier ein kleines synthetisches
NumPy-Array) und eingefrorene Metadaten uebergeben, genau wie es der
spaetere Capture-Pfad (Aufgabe 2) tun wird.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from dispread.workbench.datasets import (
    DatasetError,
    DatasetStore,
    RevisionConflict,
    WriteFailure,
    normalize_label,
    validate_bbox,
)


def _image(width=100, height=80):
    return np.zeros((height, width, 3), dtype=np.uint8)


def _filled_image(value, width=100, height=80):
    return np.full((height, width, 3), value, dtype=np.uint8)


def _device_payload(**overrides):
    payload = {
        "name": "Pruefling 1",
        "model": "GSV-2ASD",
        "family": "gsv2asd",
        "technology": "LED",
        "split": "development",
        "identity_confirmed": True,
        "identity_evidence": "Laborsicht: Typenschild und Gehäuse mit dem Bediener abgeglichen",
    }
    payload.update(overrides)
    return payload


def _capture(device_id, group_id, token="tok-1", **overrides):
    capture = {
        "image": _image(),
        "capture_token": token,
        "device_id": device_id,
        "group_id": group_id,
        "source_id": "picamera2",
        "frame_sequence": 42,
        "capture_timestamp": {"value_ns": 123, "base": "sensor_boottime"},
        "source_revision": 3,
        "synthetic": False,
        "stored_at_utc": "2026-09-18T10:00:00+00:00",
        "source": None,
        "license": None,
    }
    capture.update(overrides)
    return capture


def _serial_ascii_detail(**overrides):
    detail = {
        "source_port": "/dev/ttyUSB0",
        "guard_margin_ms": 150,
        "plateau_start_ns": 1_000_000_000,
        "plateau_end_ns": 1_200_000_000,
        "telegram_count": 3,
    }
    detail.update(overrides)
    return detail


def _annotation(**overrides):
    annotation = {
        "bbox": [10, 10, 40, 20],
        "target_label": "oben, Spannung",
        "label_state": "readable",
        "expected_text": "-01.25",
        "conditions": ["frontal"],
        "label_origin": "manual",
    }
    annotation.update(overrides)
    return annotation


# -- normalize_label -----------------------------------------------------


@pytest.mark.parametrize(
    "raw,want",
    [("-01,25", "-01.25"), (".000", ".000"), ("-.125", "-.125"), ("28,80", "28.80"), ("5", "5")],
)
def test_label_preserves_decimal_and_leading_zeroes(raw, want):
    assert normalize_label(raw) == want


@pytest.mark.parametrize("raw", ["--12", "+-12", "1.2.3", "NaN", "12 V", "", "x" * 65])
def test_invalid_label_is_rejected(raw):
    with pytest.raises(DatasetError):
        normalize_label(raw)


# -- validate_bbox ---------------------------------------------------------


def test_bbox_within_bounds_is_accepted():
    assert validate_bbox([1, 2, 3, 4], width=100, height=80) == [1.0, 2.0, 3.0, 4.0]


@pytest.mark.parametrize(
    "bbox",
    [
        [0, 0, 0, 10],  # keine Flaeche
        [-1, 0, 10, 10],  # negativer Ursprung
        [95, 0, 10, 10],  # ragt ueber die Breite hinaus
        [0, 75, 10, 10],  # ragt ueber die Hoehe hinaus
        [0, 0, 10],  # falsche Laenge
        [0, 0, float("nan"), 10],
    ],
)
def test_invalid_bbox_is_rejected_not_clamped(bbox):
    with pytest.raises(DatasetError):
        validate_bbox(bbox, width=100, height=80)


# -- Geraete ---------------------------------------------------------------


def test_create_device_requires_identity_confirmation(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    with pytest.raises(DatasetError):
        store.create_device(_device_payload(identity_confirmed=False))


def test_create_device_rejects_unknown_technology(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    with pytest.raises(DatasetError):
        store.create_device(_device_payload(technology="plasma"))


def test_create_device_assigns_uuid_and_revision(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    assert len(device["id"]) == 32
    assert device["revision"] == 0
    assert device["split"] == "development"


def test_list_devices_is_sorted_by_name_and_includes_groups(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    store.create_device(_device_payload(name="Zebra"))
    beta = store.create_device(_device_payload(name="Beta"))
    store.begin_group(beta["id"], "erste Situation")

    listed = store.list_devices()

    assert [d["name"] for d in listed] == ["Beta", "Zebra"]
    assert len(listed[0]["groups"]) == 1


def test_update_device_requires_matching_revision(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    with pytest.raises(RevisionConflict):
        store.update_device(device["id"], revision=99, changes={"name": "Neuer Name"})
    updated = store.update_device(device["id"], revision=0, changes={"name": "Neuer Name"})
    assert updated["name"] == "Neuer Name"
    assert updated["revision"] == 1


def test_split_is_locked_after_first_sample(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload(split="development"))
    group = store.begin_group(device["id"], "erste Situation")
    store.save_sample(_capture(device["id"], group["group_id"]), _annotation())
    with pytest.raises(DatasetError):
        store.update_device(device["id"], revision=0, changes={"split": "heldout"})


def test_begin_group_requires_known_device(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    with pytest.raises(DatasetError):
        store.begin_group("does-not-exist", "Notiz")


def test_begin_group_requires_change_note(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    with pytest.raises(DatasetError):
        store.begin_group(device["id"], "")


# -- Samples: Pflichtfelder und Boxgrenzen --------------------------------


def test_save_sample_happy_path(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    sample = store.save_sample(_capture(device["id"], group["group_id"]), _annotation())
    assert sample["device_id"] == device["id"]
    assert sample["independence_group"] == group["group_id"]
    assert sample["expected_text"] == "-01.25"
    assert sample["label_state"] == "readable"
    image_path = tmp_path / "datasets" / "samples" / sample["id"] / "image.png"
    assert image_path.exists()
    sample_json = tmp_path / "datasets" / "samples" / sample["id"] / "sample.json"
    assert json.loads(sample_json.read_text())["sha256"] == sample["sha256"]


def test_unreadable_sample_has_no_expected_text(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    sample = store.save_sample(
        _capture(device["id"], group["group_id"]),
        _annotation(label_state="unreadable", expected_text=None),
    )
    assert sample["expected_text"] is None


def test_readable_sample_requires_expected_text(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    with pytest.raises(DatasetError):
        store.save_sample(
            _capture(device["id"], group["group_id"]),
            _annotation(label_state="readable", expected_text=None),
        )


def test_uncertain_sample_rejects_expected_text(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    with pytest.raises(DatasetError):
        store.save_sample(
            _capture(device["id"], group["group_id"]),
            _annotation(label_state="uncertain", expected_text="1.0"),
        )


def test_save_sample_rejects_bbox_outside_image_without_clamping(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    with pytest.raises(DatasetError):
        store.save_sample(
            _capture(device["id"], group["group_id"]),
            _annotation(bbox=[90, 0, 50, 10]),
        )


def test_save_sample_rejects_unknown_group_for_device(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device_a = store.create_device(_device_payload(name="A"))
    device_b = store.create_device(_device_payload(name="B"))
    group_a = store.begin_group(device_a["id"], "Situation 1")
    with pytest.raises(DatasetError):
        store.save_sample(_capture(device_b["id"], group_a["group_id"]), _annotation())


# -- label_origin (OQ-38 Punkt 6, Herkunftsmerkmal) -----------------------


def test_save_sample_without_label_origin_is_rejected(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    annotation = _annotation()
    del annotation["label_origin"]
    with pytest.raises(DatasetError):
        store.save_sample(_capture(device["id"], group["group_id"]), annotation)


def test_save_sample_with_explicit_none_label_origin_is_rejected(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    with pytest.raises(DatasetError):
        store.save_sample(_capture(device["id"], group["group_id"]), _annotation(label_origin=None))


def test_manual_label_origin_with_detail_is_rejected(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    with pytest.raises(DatasetError):
        store.save_sample(
            _capture(device["id"], group["group_id"]),
            _annotation(label_origin="manual", label_origin_detail=_serial_ascii_detail()),
        )


def test_serial_ascii_label_origin_without_detail_is_rejected(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    with pytest.raises(DatasetError):
        store.save_sample(
            _capture(device["id"], group["group_id"]),
            _annotation(label_origin="serial_ascii", label_origin_detail=None),
        )


@pytest.mark.parametrize(
    "missing_key", ["source_port", "guard_margin_ms", "plateau_start_ns", "plateau_end_ns", "telegram_count"]
)
def test_serial_ascii_label_origin_with_incomplete_detail_is_rejected(tmp_path, missing_key):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    detail = _serial_ascii_detail()
    del detail[missing_key]
    with pytest.raises(DatasetError):
        store.save_sample(
            _capture(device["id"], group["group_id"]),
            _annotation(label_origin="serial_ascii", label_origin_detail=detail),
        )


def test_valid_serial_ascii_sample_is_saved_and_reads_back_unchanged(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    detail = _serial_ascii_detail()
    sample = store.save_sample(
        _capture(device["id"], group["group_id"]),
        _annotation(label_origin="serial_ascii", label_origin_detail=detail),
    )
    assert sample["label_origin"] == "serial_ascii"
    assert sample["label_origin_detail"] == detail

    sample_json = tmp_path / "datasets" / "samples" / sample["id"] / "sample.json"
    reloaded = json.loads(sample_json.read_text())
    assert reloaded["label_origin"] == "serial_ascii"
    assert reloaded["label_origin_detail"] == detail


def test_idempotent_retry_with_same_label_origin_returns_same_sample(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    detail = _serial_ascii_detail()
    capture = _capture(device["id"], group["group_id"])
    annotation = _annotation(label_origin="serial_ascii", label_origin_detail=detail)
    first = store.save_sample(capture, annotation)
    second = store.save_sample(capture, annotation)
    assert first["id"] == second["id"]
    samples_dir = tmp_path / "datasets" / "samples"
    assert len(list(samples_dir.iterdir())) == 1


def test_retry_with_same_token_but_different_label_origin_is_a_conflict(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    capture = _capture(device["id"], group["group_id"])
    store.save_sample(
        capture,
        _annotation(label_origin="serial_ascii", label_origin_detail=_serial_ascii_detail()),
    )
    with pytest.raises(RevisionConflict):
        store.save_sample(capture, _annotation(label_origin="manual", label_origin_detail=None))


# -- Idempotenz und Revisionskonflikte ------------------------------------


def test_repeated_save_with_same_token_and_label_is_idempotent(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    capture = _capture(device["id"], group["group_id"])
    first = store.save_sample(capture, _annotation())
    second = store.save_sample(capture, _annotation())
    assert first["id"] == second["id"]
    samples_dir = tmp_path / "datasets" / "samples"
    assert len(list(samples_dir.iterdir())) == 1


def test_repeated_save_with_same_token_and_different_label_is_a_conflict(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    capture = _capture(device["id"], group["group_id"])
    store.save_sample(capture, _annotation(expected_text="-01.25"))
    with pytest.raises(RevisionConflict):
        store.save_sample(capture, _annotation(expected_text="-09.99"))


def test_identical_image_bytes_are_flagged_as_duplicate(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    first = store.save_sample(_capture(device["id"], group["group_id"], token="tok-a"), _annotation())
    second = store.save_sample(_capture(device["id"], group["group_id"], token="tok-b"), _annotation())
    assert second["duplicate_of"] == first["id"]
    assert first["duplicate_of"] is None


# -- Schreibfehler ----------------------------------------------------------


def test_failed_image_write_leaves_no_finished_sample(tmp_path, monkeypatch):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")

    monkeypatch.setattr("dispread.workbench.datasets.cv2.imwrite", lambda *a, **k: False)
    with pytest.raises(WriteFailure):
        store.save_sample(_capture(device["id"], group["group_id"]), _annotation())

    assert store.summary()["samples"] == 0
    samples_dir = tmp_path / "datasets" / "samples"
    assert not samples_dir.exists() or not any(samples_dir.iterdir())


def test_successful_retry_after_write_failure_creates_exactly_one_sample(tmp_path, monkeypatch):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    capture = _capture(device["id"], group["group_id"])

    calls = {"n": 0}
    real_imwrite = __import__("cv2").imwrite

    def flaky(path, image):
        calls["n"] += 1
        if calls["n"] == 1:
            return False
        return real_imwrite(path, image)

    monkeypatch.setattr("dispread.workbench.datasets.cv2.imwrite", flaky)
    with pytest.raises(WriteFailure):
        store.save_sample(capture, _annotation())
    store.save_sample(capture, _annotation())

    assert store.summary()["samples"] == 1


def test_failed_metadata_write_leaves_no_finished_sample(tmp_path, monkeypatch):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")

    original_open = open

    def broken_open(path, mode="r", *args, **kwargs):
        if str(path).endswith("sample.json") and "w" in mode:
            raise OSError("Platte voll (simuliert)")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", broken_open)
    with pytest.raises(WriteFailure):
        store.save_sample(_capture(device["id"], group["group_id"]), _annotation())

    monkeypatch.undo()
    assert store.summary()["samples"] == 0


# -- Neustart / Neuladen ---------------------------------------------------


def test_registry_and_samples_survive_reload(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    sample = store.save_sample(_capture(device["id"], group["group_id"]), _annotation())

    reloaded = DatasetStore(tmp_path / "datasets")
    assert reloaded.get_device(device["id"])["name"] == device["name"]
    summary = reloaded.summary()
    assert summary["devices"] == 1
    assert summary["samples"] == 1
    assert summary["readable"] == 1
    resaved = reloaded.save_sample(_capture(device["id"], group["group_id"]), _annotation())
    assert resaved["id"] == sample["id"]


# -- select_sample -----------------------------------------------------------


def test_select_sample_requires_matching_revision(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    sample = store.save_sample(_capture(device["id"], group["group_id"]), _annotation())
    with pytest.raises(RevisionConflict):
        store.select_sample(sample["id"], revision=5)
    selected = store.select_sample(sample["id"], revision=0)
    assert selected["selected"] is True


def test_selecting_a_repeat_moves_the_representative(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    first = store.save_sample(_capture(device["id"], group["group_id"], token="tok-1"), _annotation())
    second = store.save_sample(_capture(device["id"], group["group_id"], token="tok-2"), _annotation())
    store.select_sample(first["id"], revision=0)
    store.select_sample(second["id"], revision=0)

    reloaded_first = json.loads((tmp_path / "datasets" / "samples" / first["id"] / "sample.json").read_text())
    reloaded_second = json.loads((tmp_path / "datasets" / "samples" / second["id"] / "sample.json").read_text())
    assert reloaded_first["selected"] is False
    assert reloaded_second["selected"] is True


# -- relabel_sample -----------------------------------------------------------


def test_relabel_sample_corrects_a_typo_and_records_history(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    sample = store.save_sample(_capture(device["id"], group["group_id"]), _annotation())

    corrected = store.relabel_sample(
        sample["id"], revision=sample["metadata_revision"], expected_text="0.94801", reason="Tippfehler, visuell nachgeprueft"
    )

    assert corrected["expected_text"] == "0.94801"
    assert corrected["metadata_revision"] == sample["metadata_revision"] + 1
    assert len(corrected["label_history"]) == 1
    entry = corrected["label_history"][0]
    assert entry["previous_expected_text"] == sample["expected_text"]
    assert entry["reason"] == "Tippfehler, visuell nachgeprueft"
    assert "changed_at_utc" in entry

    reloaded = json.loads((tmp_path / "datasets" / "samples" / sample["id"] / "sample.json").read_text())
    assert reloaded["expected_text"] == "0.94801"
    assert reloaded["label_history"][0]["previous_expected_text"] == sample["expected_text"]


def test_relabel_sample_on_serial_ascii_sample_flips_origin_to_manual(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    detail = _serial_ascii_detail()
    sample = store.save_sample(
        _capture(device["id"], group["group_id"]),
        _annotation(label_origin="serial_ascii", label_origin_detail=detail),
    )
    assert sample["label_origin"] == "serial_ascii"

    corrected = store.relabel_sample(
        sample["id"], revision=sample["metadata_revision"], expected_text="0.94801", reason="Tippfehler, visuell nachgeprueft"
    )

    assert corrected["label_origin"] == "manual"
    assert corrected["label_origin_detail"] is None
    assert corrected["label_history"][-1]["previous_label_origin"] == "serial_ascii"
    assert corrected["label_history"][-1]["previous_label_origin_detail"] == detail

    reloaded = json.loads((tmp_path / "datasets" / "samples" / sample["id"] / "sample.json").read_text())
    assert reloaded["label_origin"] == "manual"
    assert reloaded["label_origin_detail"] is None


def test_relabel_sample_requires_matching_revision(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    sample = store.save_sample(_capture(device["id"], group["group_id"]), _annotation())

    with pytest.raises(RevisionConflict):
        store.relabel_sample(sample["id"], revision=5, expected_text="0.94801", reason="Tippfehler")


def test_relabel_sample_rejects_unknown_sample(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    with pytest.raises(DatasetError):
        store.relabel_sample("0" * 32, revision=0, expected_text="0.94801", reason="Tippfehler")


def test_relabel_sample_rejects_unreadable_samples(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    sample = store.save_sample(
        _capture(device["id"], group["group_id"]),
        _annotation(label_state="unreadable", expected_text=None),
    )
    with pytest.raises(DatasetError):
        store.relabel_sample(sample["id"], revision=sample["metadata_revision"], expected_text="0.94801", reason="Tippfehler")


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_relabel_sample_rejects_missing_or_blank_reason(tmp_path, reason):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    sample = store.save_sample(_capture(device["id"], group["group_id"]), _annotation())
    with pytest.raises(DatasetError):
        store.relabel_sample(sample["id"], revision=sample["metadata_revision"], expected_text="0.94801", reason=reason)


def test_relabel_sample_rejects_a_no_op_change(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    sample = store.save_sample(_capture(device["id"], group["group_id"]), _annotation())
    with pytest.raises(DatasetError):
        store.relabel_sample(
            sample["id"], revision=sample["metadata_revision"], expected_text=sample["expected_text"], reason="Tippfehler"
        )


def test_relabel_sample_leaves_image_and_hash_untouched(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    sample = store.save_sample(_capture(device["id"], group["group_id"]), _annotation())
    image_path = tmp_path / "datasets" / "samples" / sample["id"] / "image.png"
    image_bytes_before = image_path.read_bytes()

    corrected = store.relabel_sample(
        sample["id"], revision=sample["metadata_revision"], expected_text="0.94801", reason="Tippfehler"
    )

    assert corrected["sha256"] == sample["sha256"]
    assert image_path.read_bytes() == image_bytes_before


# -- Export (Grundverhalten; Loaderintegration siehe Aufgabe 6) -----------


def test_export_excludes_uncertain_and_draft_samples(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    store.save_sample(
        _capture(device["id"], group["group_id"]),
        _annotation(label_state="uncertain", expected_text=None),
    )
    result = store.export()
    manifest = json.loads((result["path"] / "manifest.json").read_text())
    selection = json.loads((result["path"] / "selection.json").read_text())
    assert manifest["samples"] == []
    assert any(x["reason"].startswith("label_state=") for x in selection["excluded"])


def test_export_includes_single_readable_sample_and_matches_hash(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    sample = store.save_sample(_capture(device["id"], group["group_id"]), _annotation())
    result = store.export()
    manifest = json.loads((result["path"] / "manifest.json").read_text())
    assert manifest["schema_version"] == 1
    assert len(manifest["samples"]) == 1
    entry = manifest["samples"][0]
    assert entry["id"] == sample["id"]
    assert entry["sha256"] == sample["sha256"]
    assert entry["expected_text"] == "-01.25"
    image_bytes = (result["path"] / entry["path"]).read_bytes()
    import hashlib

    assert hashlib.sha256(image_bytes).hexdigest() == entry["sha256"]


def test_export_requires_explicit_selection_for_repeated_group(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    store.save_sample(_capture(device["id"], group["group_id"], token="tok-1"), _annotation())
    store.save_sample(_capture(device["id"], group["group_id"], token="tok-2"), _annotation(bbox=[5, 5, 40, 20]))
    result = store.export()
    manifest = json.loads((result["path"] / "manifest.json").read_text())
    assert manifest["samples"] == []


# -- Aufgabe 5: Gruppen, Ähnlichkeitswarnung, Fortschritt ------------------


def test_ten_repeats_of_one_situation_count_as_one_independence_group(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    for i in range(10):
        store.save_sample(
            _capture(device["id"], group["group_id"], token=f"tok-{i}"),
            _annotation(bbox=[10, 10, 40, 20 + i]),
        )
    assert store.summary()["independence_groups"] == 1
    assert store.summary()["samples"] == 10


def test_changing_the_selection_does_not_change_the_independence_count(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    first = store.save_sample(_capture(device["id"], group["group_id"], token="tok-1"), _annotation())
    second = store.save_sample(_capture(device["id"], group["group_id"], token="tok-2"), _annotation(bbox=[5, 5, 40, 20]))
    before = store.summary()["independence_groups"]
    store.select_sample(first["id"], revision=0)
    store.select_sample(second["id"], revision=0)
    assert store.summary()["independence_groups"] == before


def test_similar_but_not_identical_image_requires_confirmation_and_reason(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    store.save_sample(
        _capture(device["id"], group["group_id"], token="tok-1", image=_filled_image(0)), _annotation()
    )
    with pytest.raises(DatasetError):
        store.save_sample(
            _capture(device["id"], group["group_id"], token="tok-2", image=_filled_image(3)), _annotation()
        )
    # Ohne Begruendung ebenfalls abgelehnt, auch mit similarity_confirmed=True.
    with pytest.raises(DatasetError):
        store.save_sample(
            _capture(device["id"], group["group_id"], token="tok-2", image=_filled_image(3)),
            _annotation(similarity_confirmed=True),
        )
    confirmed = store.save_sample(
        _capture(device["id"], group["group_id"], token="tok-2", image=_filled_image(3)),
        _annotation(similarity_confirmed=True, similarity_reason="Bewusste Wiederholung, leicht unterschiedliche Belichtung"),
    )
    assert confirmed["similarity_warning"]["candidate"]
    assert confirmed["similarity_confirmation_reason"]


def test_clearly_different_images_need_no_similarity_confirmation(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    store.save_sample(
        _capture(device["id"], group["group_id"], token="tok-1", image=_filled_image(0)), _annotation()
    )
    sample = store.save_sample(
        _capture(device["id"], group["group_id"], token="tok-2", image=_filled_image(200)), _annotation()
    )
    assert sample["similarity_warning"] is None


def test_similarity_check_is_scoped_to_the_same_independence_group(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group_a = store.begin_group(device["id"], "Situation 1")
    group_b = store.begin_group(device["id"], "Situation 2")
    store.save_sample(
        _capture(device["id"], group_a["group_id"], token="tok-1", image=_filled_image(0)), _annotation()
    )
    # Selbe fast-identische Aufnahme, aber in einer ANDEREN Situation - keine
    # Warnung, denn Aehnlichkeit ist nur innerhalb einer Situation relevant.
    sample = store.save_sample(
        _capture(device["id"], group_b["group_id"], token="tok-2", image=_filled_image(3)), _annotation()
    )
    assert sample["similarity_warning"] is None


def test_synthetic_samples_do_not_inflate_real_readable_counters(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    store.save_sample(
        _capture(device["id"], group["group_id"], token="tok-real"), _annotation(expected_text="-01.25")
    )
    store.save_sample(
        _capture(device["id"], group["group_id"], token="tok-synthetic", synthetic=True, image=_filled_image(50)),
        _annotation(expected_text="99.99"),
    )
    summary = store.summary()
    assert summary["samples"] == 2
    assert summary["readable"] == 1


def test_device_count_depends_only_on_uuids_not_on_sample_or_label_count(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device_a = store.create_device(_device_payload(name="A"))
    device_b = store.create_device(_device_payload(name="B"))
    group_a = store.begin_group(device_a["id"], "Situation 1")
    for i in range(5):
        store.save_sample(
            _capture(device_a["id"], group_a["group_id"], token=f"tok-{i}"),
            _annotation(bbox=[10, 10, 40, 20 + i]),
        )
    assert store.summary()["devices"] == 2
    del device_b


def test_export_deduplicates_identical_image_across_different_groups(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group_a = store.begin_group(device["id"], "Situation 1")
    group_b = store.begin_group(device["id"], "Situation 2")
    # Beide Proben sind mit demselben Standardbild eindeutig eigenstaendige
    # Situationen (verschiedene group_id) - der externe Loader lehnt ein
    # doppeltes Bildhash ueber den GESAMTEN Export hinweg trotzdem ab, deshalb
    # muss der Export selbst nur die erste Probe aufnehmen.
    store.save_sample(_capture(device["id"], group_a["group_id"], token="tok-1"), _annotation())
    store.save_sample(_capture(device["id"], group_b["group_id"], token="tok-2"), _annotation())
    result = store.export()
    manifest = json.loads((result["path"] / "manifest.json").read_text())
    selection = json.loads((result["path"] / "selection.json").read_text())
    assert len(manifest["samples"]) == 1
    assert any("duplicate_image_hash_of" in x["reason"] for x in selection["excluded"])


def test_missing_conditions_are_reported_as_a_gap_not_fabricated_coverage(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    store.save_sample(
        _capture(device["id"], group["group_id"], token="tok-1"), _annotation(conditions=["frontal"])
    )
    missing = store.summary()["missing_conditions"]
    assert "frontal" not in missing["overall"]
    assert "negative" in missing["overall"]
    assert "negative" in missing["by_device"][device["id"]]
    assert "frontal" not in missing["by_device"][device["id"]]


# -- Nachschliff nach Advisor-Review: synthetisch/Temp-Verzeichnisse/Beleg --


def test_synthetic_sample_is_excluded_from_export_like_uncertain(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    store.save_sample(
        _capture(device["id"], group["group_id"], token="tok-1", synthetic=True), _annotation()
    )
    result = store.export()
    manifest = json.loads((result["path"] / "manifest.json").read_text())
    selection = json.loads((result["path"] / "selection.json").read_text())
    assert manifest["samples"] == []
    assert any(x["reason"] == "synthetic" for x in selection["excluded"])


def test_incomplete_temp_sample_directory_does_not_count_after_restart(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload())
    group = store.begin_group(device["id"], "Situation 1")
    store.save_sample(_capture(device["id"], group["group_id"], token="tok-1"), _annotation())

    # Simuliert einen Absturz zwischen sample.json-Schreiben und dem
    # abschliessenden rename() in _save_sample_locked: ein Verzeichnis mit
    # Inhalt, aber ohne UUID-Namen.
    leftover = tmp_path / "datasets" / "samples" / ".sample-crashed"
    leftover.mkdir()
    (leftover / "sample.json").write_text("{}")
    (leftover / "image.png").write_bytes(b"not a real png")

    reloaded = DatasetStore(tmp_path / "datasets")
    summary = reloaded.summary()
    assert summary["samples"] == 1
    assert summary["incomplete_temp_dirs"] == 1

    # Ein liegen gebliebenes Temp-Verzeichnis darf auch nicht als
    # Gruppenvertreter im Export landen.
    result = reloaded.export()
    manifest = json.loads((result["path"] / "manifest.json").read_text())
    assert len(manifest["samples"]) == 1
    assert manifest["samples"][0]["id"] != ".sample-crashed"


def test_device_creation_requires_identity_evidence(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    with pytest.raises(DatasetError):
        store.create_device(_device_payload(identity_evidence=None))
    with pytest.raises(DatasetError):
        store.create_device(_device_payload(identity_evidence=""))


def test_identity_evidence_is_carried_through_to_the_export_manifest(tmp_path):
    store = DatasetStore(tmp_path / "datasets")
    device = store.create_device(_device_payload(identity_evidence="Seriennummer am Typenschild fotografiert"))
    group = store.begin_group(device["id"], "Situation 1")
    store.save_sample(_capture(device["id"], group["group_id"], token="tok-1"), _annotation())
    result = store.export()
    manifest = json.loads((result["path"] / "manifest.json").read_text())
    assert manifest["samples"][0]["identity_evidence"] == "Seriennummer am Typenschild fotografiert"
