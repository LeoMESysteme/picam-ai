"""Rohbildaufnahme fuer den Sammelmodus ohne Profilkalibrierung (Aufgabe 2).

Deckt die Controller-Anbindung ab: eigene Capture-Tokens, unveraendertes
Produktions-Profil/-ROI/-Layout/-Tracker/-Gate, kein Kamerazugriff ausserhalb
des bereits vorhandenen ``self.raw``.
"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from dispread.workbench.controller import Controller
from dispread.workbench.dataset_capture import CaptureError, CaptureRegistry
from dispread.workbench.datasets import DatasetError, DatasetStore, RevisionConflict


def _image(fill=100, width=200, height=100):
    return np.full((height, width, 3), fill, np.uint8)


def _make_device_and_group(c):
    device = c.command("dataset.device.create", {
        "name": "Pruefling 1",
        "model": "GSV-2ASD",
        "family": "gsv2asd",
        "technology": "LED",
        "split": "development",
        "identity_confirmed": True,
    })
    group = c.command("dataset.group.begin", {"device_id": device["id"], "change_note": "Situation 1"})
    return device, group


def _annotation(**overrides):
    annotation = {
        "bbox": [10, 10, 40, 20],
        "target_label": "oben, Spannung",
        "label_state": "readable",
        "expected_text": "-01.25",
        "conditions": ["frontal"],
    }
    annotation.update(overrides)
    return annotation


# -- Kapture-Ablehnungen ----------------------------------------------------


def test_capture_without_live_image_is_rejected(tmp_path):
    c = Controller(tmp_path)
    device, group = _make_device_and_group(c)
    with pytest.raises(ValueError):
        c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})


def test_capture_during_run_mode_is_rejected(tmp_path):
    c = Controller(tmp_path)
    c.publish(_image(), {"timebase": "synthetic"})
    device, group = _make_device_and_group(c)
    c.command("mode", {"value": "annotate"})
    c.mode = "run"  # unbestaetigtes Profil kann run ueber command() nicht erreichen; direkt setzen
    with pytest.raises(ValueError):
        c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})


def test_capture_with_unknown_device_or_group_is_rejected(tmp_path):
    c = Controller(tmp_path)
    c.publish(_image(), {"timebase": "synthetic"})
    device, group = _make_device_and_group(c)
    with pytest.raises(DatasetError):
        c.command("dataset.capture", {"device_id": "unbekannt", "group_id": group["group_id"]})
    with pytest.raises(DatasetError):
        c.command("dataset.capture", {"device_id": device["id"], "group_id": "unbekannt"})


def test_capture_allowed_without_confirmed_profile(tmp_path):
    c = Controller(tmp_path)
    c.publish(_image(), {"timebase": "synthetic"})
    assert c.config["confirmed"] is False
    device, group = _make_device_and_group(c)
    result = c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})
    assert "token" in result
    assert result["width"] == 200
    assert result["height"] == 100


def test_capture_over_open_limit_is_rejected(tmp_path):
    c = Controller(tmp_path)
    c.publish(_image(), {"timebase": "synthetic"})
    device, group = _make_device_and_group(c)
    c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})
    c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})
    with pytest.raises(CaptureError):
        c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})


# -- Eingefrorenes Bild bleibt unberuehrt von spaeterem publish() -----------


def test_capture_freezes_image_a_even_after_publishing_b(tmp_path):
    c = Controller(tmp_path)
    image_a = _image(fill=10)
    c.publish(image_a, {"timebase": "synthetic"})
    device, group = _make_device_and_group(c)
    captured = c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})

    image_b = _image(fill=250)
    c.publish(image_b, {"timebase": "synthetic"})

    sample = c.command(
        "dataset.save",
        {"token": captured["token"], **_annotation()},
    )
    saved = __import__("cv2").imread(
        str(tmp_path / "datasets" / "samples" / sample["id"] / "image.png")
    )
    assert (saved == 10).all()


def test_capture_and_save_do_not_touch_production_state(tmp_path):
    c = Controller(tmp_path)
    c.publish(_image(), {"timebase": "synthetic"})
    device, group = _make_device_and_group(c)
    config_before = c.config
    mode_before = c.mode
    tracker_before = c.tracker
    reading_before = c.reading

    captured = c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})
    c.command("dataset.save", {"token": captured["token"], **_annotation(expected_text="12.34")})

    assert c.config == config_before
    assert c.mode == mode_before
    assert c.tracker is tracker_before
    assert c.reading == reading_before


# -- Token-Ablauf, Geraetewechsel, konkurrierende Speicherversuche --------


def test_expired_token_cannot_be_saved():
    now = {"t": 0.0}
    registry = CaptureRegistry(now=lambda: now["t"])
    token = registry.begin(_image(), {"device_id": "d", "group_id": "g"})
    now["t"] += 601
    with pytest.raises(CaptureError):
        registry.get(token)


def test_double_save_with_different_label_is_a_conflict_not_a_silent_overwrite(tmp_path):
    c = Controller(tmp_path)
    c.publish(_image(), {"timebase": "synthetic"})
    device, group = _make_device_and_group(c)
    captured = c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})
    c.command("dataset.save", {"token": captured["token"], **_annotation(expected_text="12.34")})
    with pytest.raises(RevisionConflict):
        c.command("dataset.save", {"token": captured["token"], **_annotation(expected_text="99.99")})


def test_retry_save_with_same_label_is_idempotent(tmp_path):
    c = Controller(tmp_path)
    c.publish(_image(), {"timebase": "synthetic"})
    device, group = _make_device_and_group(c)
    captured = c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})
    first = c.command("dataset.save", {"token": captured["token"], **_annotation(expected_text="12.34")})
    second = c.command("dataset.save", {"token": captured["token"], **_annotation(expected_text="12.34")})
    assert first["id"] == second["id"]
    assert c.dataset_store.summary()["samples"] == 1


def test_saved_capture_no_longer_counts_against_open_limit(tmp_path):
    c = Controller(tmp_path)
    c.publish(_image(), {"timebase": "synthetic"})
    device, group = _make_device_and_group(c)
    captured = c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})
    c.command("dataset.save", {"token": captured["token"], **_annotation()})
    c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})
    c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})


# -- Sperrverhalten (Aufgabe 5: kein Blockieren des Kamerapfads) ----------


def test_blocked_save_does_not_block_status_or_publish(tmp_path, monkeypatch):
    c = Controller(tmp_path)
    c.publish(_image(), {"timebase": "synthetic"})
    device, group = _make_device_and_group(c)
    captured = c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})

    started = threading.Event()
    release = threading.Event()
    real_save_sample = DatasetStore.save_sample

    def slow_save_sample(self, capture, annotation):
        started.set()
        release.wait(timeout=5)
        return real_save_sample(self, capture, annotation)

    monkeypatch.setattr(DatasetStore, "save_sample", slow_save_sample)
    thread = threading.Thread(
        target=lambda: c.command("dataset.save", {"token": captured["token"], **_annotation()})
    )
    thread.start()
    assert started.wait(timeout=5)

    start = time.monotonic()
    c.command("status")
    c.publish(_image(fill=5), {"timebase": "synthetic"})
    elapsed = time.monotonic() - start
    assert elapsed < 1.0

    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_similarity_warning_roundtrips_through_command(tmp_path):
    c = Controller(tmp_path)
    device, group = _make_device_and_group(c)
    c.publish(_image(fill=0), {"timebase": "synthetic"})
    first_token = c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})["token"]
    c.command("dataset.save", {"token": first_token, **_annotation()})

    c.publish(_image(fill=3), {"timebase": "synthetic"})
    second_token = c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})["token"]
    with pytest.raises(DatasetError):
        c.command("dataset.save", {"token": second_token, **_annotation(expected_text="99.99")})

    confirmed = c.command(
        "dataset.save",
        {
            "token": second_token,
            **_annotation(expected_text="99.99"),
            "similarity_confirmed": True,
            "similarity_reason": "Bewusste Wiederholung mit leicht anderer Helligkeit",
        },
    )
    assert confirmed["similarity_warning"]["candidate"]


def test_discard_removes_the_draft(tmp_path):
    c = Controller(tmp_path)
    c.publish(_image(), {"timebase": "synthetic"})
    device, group = _make_device_and_group(c)
    captured = c.command("dataset.capture", {"device_id": device["id"], "group_id": group["group_id"]})
    c.command("dataset.discard", {"token": captured["token"]})
    with pytest.raises(CaptureError):
        c.command("dataset.save", {"token": captured["token"], **_annotation()})
