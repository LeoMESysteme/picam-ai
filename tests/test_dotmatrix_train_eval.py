"""`scripts/dotmatrix-train.py` und `scripts/dotmatrix-eval.py` (Task 7,
Training und Entwicklungsmessung Stufe 1,
docs/superpowers/specs/2026-09-24-dotmatrix-reader-design.md Abschnitt 3).

Baut einen kleinen synthetischen Mini-Datensatz analog zu
`tests/test_dotmatrix_dataset.py` (mehrere Gruppen/Sitzungen als
Verzeichnisse unter `tmp_path`), damit `loo` echte Durchgaenge erzeugt -
ohne Kamera, ohne echte Ernte-Daten (AGENTS.md, `var/workbench/datasets`
nur lesen). Deckt die drei in der Aufgabe verlangten Verhaltensweisen ab:

(a) Leckagetest: die Schwellen des Durchgangs mit Testgruppe G aendern sich
    nicht, wenn man NUR die Proben von G veraendert.
(b) Eine absichtlich falsch gelabelte Trainingsprobe (Label '7' auf einem
    '1'-Bild, 60 % der '7'-Proben) laesst `dotmatrix-train.py` mit Exit 3
    enden, ohne `templates.json` zu schreiben.
(c) Eine Testprobe mit vom Bild abweichendem Label erscheint in `evaluate()`
    als `falsch` und macht ihr Plateau `falsch`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from dotmatrix_helpers import GRID, render

from dispread.ocr.dotmatrix_font import CLASSES
from dispread.ocr.dotmatrix_sampling import normalized, sample_image
from dispread.ocr.dotmatrix_templates import build_templates
from dispread.session_profile import SessionProfile

_SCRIPTS = Path(__file__).parents[1] / "scripts"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dataset_mod = _load("dotmatrix_dataset", "dotmatrix-dataset.py")
train_mod = _load("dotmatrix_train", "dotmatrix-train.py")
eval_mod = _load("dotmatrix_eval", "dotmatrix-eval.py")

DEVICE_ID = "dev-gsv-161a"
TARGET_SIZE = (400, 160)
RAW_SIZE = (960, 720)
OFFSET = (300, 300)

#: Deckt alle 13 Klassen ab (0-9, '.', '+', ' '), wie
#: tests/test_dotmatrix_reader.py TRAIN_TEXTS. "+0.60972 ", "+ 67.890 " und
#: "+ 3456.7 " enthalten je genau eine '7'-Zelle (fuer Test b).
TEXTS = ["+0.60972 ", "+ 1.2345 ", "+ 67.890 ", "+  988.5 ", "+ 3456.7 ", "+0.11111 "]


def _quad() -> list[list[float]]:
    x0, y0 = OFFSET
    w, h = TARGET_SIZE
    return [
        [float(x0), float(y0)],
        [float(x0 + w), float(y0)],
        [float(x0 + w), float(y0 + h)],
        [float(x0), float(y0 + h)],
    ]


def _full_frame(text: str, rng: np.random.Generator) -> np.ndarray:
    gray = render(text, grid=GRID, size=TARGET_SIZE, blur=float(rng.uniform(0.2, 0.7)))
    gray = np.clip(gray.astype(np.float32) + rng.normal(0, 3.0, gray.shape), 0, 255).astype(np.uint8)
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


def _write_sample(
    dataset_root: Path,
    sample_id: str,
    session_id: str,
    render_text: str,
    label_text: str,
    plateau: tuple[int, int],
    rng: np.random.Generator,
) -> None:
    sample_dir = dataset_root / "samples" / sample_id
    sample_dir.mkdir(parents=True)
    cv2.imwrite(str(sample_dir / "image.png"), _full_frame(render_text, rng))
    detail = {
        "session_id": session_id,
        "cell_text": label_text.ljust(16),
        "plateau_start_ns": plateau[0],
        "plateau_end_ns": plateau[1],
    }
    sample = {
        "schema_version": 2,
        "id": sample_id,
        "device_id": DEVICE_ID,
        "label_state": "readable",
        "label_origin": "serial_ascii",
        "label_origin_detail": detail,
    }
    (sample_dir / "sample.json").write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")


def _save_profile(tmp_path: Path, session_id: str) -> Path:
    profile = SessionProfile(
        schema_version=2,
        device_id="gsv-sensor-161a",
        session_id=session_id,
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
    path = tmp_path / f"{session_id}-profile.json"
    profile.save(path)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_profile_map(tmp_path: Path, sessions: list[str]) -> Path:
    out = {}
    for session_id in sessions:
        path = _save_profile(tmp_path, session_id)
        out[session_id] = {"path": str(path), "sha256": dataset_mod._profile_sha256(path)}
    map_path = tmp_path / "profile-map.json"
    map_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return map_path


def _build_three_group_dataset(tmp_path: Path, seed: int = 0) -> tuple[Path, Path]:
    """Drei Gruppen (g1, g2, g3), je 2 Wiederholungen von `TEXTS` (deckt alle
    13 Klassen ab, jede Gruppe fuer sich)."""
    rng = np.random.default_rng(seed)
    dataset_root = tmp_path / "dataset"
    _write_devices(dataset_root)
    for group in ("g1", "g2", "g3"):
        i = 0
        for _rep in range(2):
            for text in TEXTS:
                sample_id = f"{group}-{i:03d}"
                plateau = (i * 1_000_000, i * 1_000_000 + 500_000)
                _write_sample(dataset_root, sample_id, group, text, text, plateau, rng)
                i += 1
    map_path = _write_profile_map(tmp_path, ["g1", "g2", "g3"])
    return dataset_root, map_path


# --- (a) Leckagetest -------------------------------------------------------


def test_loo_thresholds_of_held_out_group_do_not_change_when_its_own_samples_change(tmp_path):
    dataset_root, map_path = _build_three_group_dataset(tmp_path)

    out1 = tmp_path / "report1.json"
    rc = eval_mod.main(
        ["loo", "--dataset-root", str(dataset_root), "--profile-map", str(map_path), "--out", str(out1)]
    )
    assert rc == 0
    report1 = json.loads(out1.read_text(encoding="utf-8"))
    assert set(report1["groups"]) == {"g1", "g2", "g3"}
    assert len(report1["durchgaenge"]) == 3
    by_group1 = {d["test_group"]: d for d in report1["durchgaenge"]}

    # Nur die Bilder der Gruppe g1 mit starkem Rauschen ueberschreiben - ihre
    # eigenen Proben, nicht die der anderen Gruppen. Das Label bleibt stehen
    # (sonst waeren die Proben nicht mehr klassenzuordenbar); das Rauschen
    # ist deutlich, aber kein reines Zufallsbild - reines Zufallsrauschen
    # macht die Zeichen in den Durchgaengen, die g1 als TRAINING nutzen
    # (g2, g3), so unkenntlich, dass dort die ROM-Gegenprobe faelschlich
    # anschlaegt (mit dem Datensatz selbst nichts zu tun, nur ein zu
    # extremer Test-Reiz) - hier soll nur g1 als TESTGRUPPE unveraendert
    # bleiben, waehrend die anderen Durchgaenge sich sichtbar aendern.
    rng = np.random.default_rng(99)
    for sample_dir in sorted((dataset_root / "samples").iterdir()):
        sample = json.loads((sample_dir / "sample.json").read_text(encoding="utf-8"))
        if sample["label_origin_detail"]["session_id"] != "g1":
            continue
        original = cv2.imread(str(sample_dir / "image.png"))
        noisy = np.clip(original.astype(np.float32) + rng.normal(0, 25.0, original.shape), 0, 255).astype(np.uint8)
        cv2.imwrite(str(sample_dir / "image.png"), noisy)

    out2 = tmp_path / "report2.json"
    rc = eval_mod.main(
        ["loo", "--dataset-root", str(dataset_root), "--profile-map", str(map_path), "--out", str(out2)]
    )
    assert rc == 0
    report2 = json.loads(out2.read_text(encoding="utf-8"))
    by_group2 = {d["test_group"]: d for d in report2["durchgaenge"]}

    # Testgruppe g1: Training sieht g1 nie - Schwellen unveraendert.
    assert by_group1["g1"]["d_max"] == by_group2["g1"]["d_max"]
    assert by_group1["g1"]["margin_min"] == by_group2["g1"]["margin_min"]

    # Gegenprobe: g1 steckt im Training der anderen Durchgaenge - dort
    # AENDERN sich die Schwellen durch das Rauschen (sonst waere der obige
    # Vergleich bedeutungslos, weil nichts sich je aendert).
    changed = any(
        by_group1[g]["d_max"] != by_group2[g]["d_max"] or by_group1[g]["margin_min"] != by_group2[g]["margin_min"]
        for g in ("g2", "g3")
    )
    assert changed


# --- (b) Falsch gelabelte Trainingsprobe -> Exit 3 -------------------------


def test_train_exits_3_and_writes_nothing_on_mislabeled_training_data(tmp_path):
    rng = np.random.default_rng(5)
    dataset_root = tmp_path / "dataset"
    _write_devices(dataset_root)

    seven_sample_ids: list[str] = []
    i = 0
    for _rep in range(5):
        for text in TEXTS:
            sample_id = f"g1-{i:03d}"
            plateau = (i * 1_000_000, i * 1_000_000 + 500_000)
            _write_sample(dataset_root, sample_id, "g1", text, text, plateau, rng)
            if "7" in text:
                seven_sample_ids.append(sample_id)
            i += 1

    # 60 % der '7'-Proben: Bild zeigt '1' statt '7', Label bleibt '7'.
    n_bad = int(round(len(seven_sample_ids) * 0.6))
    assert n_bad >= 1
    for sample_id in seven_sample_ids[:n_bad]:
        sample_path = dataset_root / "samples" / sample_id / "sample.json"
        sample = json.loads(sample_path.read_text(encoding="utf-8"))
        label_text = sample["label_origin_detail"]["cell_text"][:9]
        pos = label_text.index("7")
        bad_render_text = label_text[:pos] + "1" + label_text[pos + 1 :]
        cv2.imwrite(str(dataset_root / "samples" / sample_id / "image.png"), _full_frame(bad_render_text, rng))

    map_path = _write_profile_map(tmp_path, ["g1"])
    out_path = tmp_path / "templates.json"
    rc = train_mod.main(
        [
            "--dataset-root", str(dataset_root),
            "--profile-map", str(map_path),
            "--groups", "g1",
            "--out", str(out_path),
        ]
    )

    assert rc == 3
    assert not out_path.exists()


def test_train_writes_templates_on_clean_training_data(tmp_path):
    """Gegenprobe zu Test b: derselbe Aufbau ohne Mislabeling schreibt
    normal Vorlagen (Exit 0) - stellt sicher, dass Exit 3 oben tatsaechlich
    am Mislabeling liegt, nicht am Datensatzaufbau."""
    rng = np.random.default_rng(6)
    dataset_root = tmp_path / "dataset"
    _write_devices(dataset_root)
    i = 0
    for _rep in range(5):
        for text in TEXTS:
            sample_id = f"g1-{i:03d}"
            plateau = (i * 1_000_000, i * 1_000_000 + 500_000)
            _write_sample(dataset_root, sample_id, "g1", text, text, plateau, rng)
            i += 1

    map_path = _write_profile_map(tmp_path, ["g1"])
    out_path = tmp_path / "templates.json"
    rc = train_mod.main(
        [
            "--dataset-root", str(dataset_root),
            "--profile-map", str(map_path),
            "--groups", "g1",
            "--out", str(out_path),
        ]
    )

    assert rc == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["threshold_formula"] == "thresholds_v1"


# --- (c) Falsch gelabelte Testprobe -> "falsch", Plateau "falsch" ----------


def _templates_from_texts(rng: np.random.Generator):
    samples = {c: [] for c in CLASSES}
    for text in TEXTS * 3:
        img = render(text, blur=float(rng.uniform(0.3, 0.8)))
        img = np.clip(img.astype(np.float32) + rng.normal(0, 3, img.shape), 0, 255).astype(np.uint8)
        n = normalized(sample_image(img, GRID, range(9)))
        for i, ch in enumerate(text):
            samples[ch].append(n[i])
    return build_templates(samples, ("synthetisch",))


def _cell_sample(sample_id, group, plateau, render_text, label_text):
    img = render(render_text)
    n = normalized(sample_image(img, GRID, range(9)))
    return dataset_mod.CellSample(sample_id, group, plateau, label_text, n)


def test_evaluate_marks_mislabeled_test_sample_falsch_and_its_plateau_falsch():
    rng = np.random.default_rng(11)
    t = _templates_from_texts(rng)

    plateau = (1_000, 5_000)
    correct = _cell_sample("s1", "test", plateau, "+0.60972 ", "+0.60972 ")
    mislabeled = _cell_sample("s2", "test", plateau, "+0.60972 ", "+1.60972 ")  # Bild zeigt '0', Label '1'

    result = eval_mod.evaluate([correct, mislabeled], t)

    assert result["summary"].get("richtig") == 1
    assert result["summary"].get("falsch") == 1
    assert result["plateaus"] == {"gesamt": 1, "richtig": 0, "falsch": 1, "abgelehnt": 0}


def test_evaluate_all_correct_plateau_is_richtig():
    rng = np.random.default_rng(12)
    t = _templates_from_texts(rng)
    plateau = (2_000, 6_000)
    a = _cell_sample("s3", "test", plateau, "+ 1.2345 ", "+ 1.2345 ")
    b = _cell_sample("s4", "test", plateau, "+ 1.2345 ", "+ 1.2345 ")

    result = eval_mod.evaluate([a, b], t)

    assert result["summary"] == {"richtig": 2}
    assert result["plateaus"] == {"gesamt": 1, "richtig": 1, "falsch": 0, "abgelehnt": 0}
    # Verwechslungsmatrix: jede entschiedene Zelle steht auf der Diagonale.
    for true_ch, row in result["confusion"].items():
        assert set(row) == {true_ch}


def test_evaluate_unknown_pattern_is_abgelehnt():
    rng = np.random.default_rng(13)
    t = _templates_from_texts(rng)
    plateau = (3_000, 7_000)
    garbage_vectors = np.tile(np.random.default_rng(14).uniform(0, 1, 40).astype(np.float32), (9, 9, 1))
    s = dataset_mod.CellSample("s5", "test", plateau, "+ 1.2345 ", garbage_vectors)

    result = eval_mod.evaluate([s], t)

    assert list(result["summary"]) == ["abgelehnt:zelle_unbekannt"]
    assert result["plateaus"] == {"gesamt": 1, "richtig": 0, "falsch": 0, "abgelehnt": 1}


def test_build_samples_by_char_skips_short_cell_text_instead_of_indexerror():
    """Final-Fix 5: eine Probe mit `cell_text` kuerzer als 9 Zeichen wird
    gezaehlt und uebersprungen statt mit IndexError abzubrechen."""
    good = _cell_sample("s1", "g1", (0, 1), "+0.60972 ", "+0.60972 ")
    short = dataset_mod.CellSample("s2", "g1", (0, 1), "+0.6097", good.vectors[:7])

    stats: dict[str, int] = {}
    samples_by_char = train_mod.build_samples_by_char([good, short], stats=stats)

    assert stats["zelltext_zu_kurz"] == 1
    assert sum(len(v) for v in samples_by_char.values()) == 9  # nur "good" eingesortiert


# --- Zusaetzliche Absicherung: loo-Berichtsstruktur, reader-check ----------


def test_loo_report_has_required_fields(tmp_path):
    dataset_root, map_path = _build_three_group_dataset(tmp_path)
    out = tmp_path / "report.json"
    rc = eval_mod.main(["loo", "--dataset-root", str(dataset_root), "--profile-map", str(map_path), "--out", str(out)])
    assert rc == 0
    report = json.loads(out.read_text(encoding="utf-8"))

    assert report["vorzeichen"] == "ungeprueft (nur +)"
    assert report["threshold_formula"] == "thresholds_v1"
    assert len(report["git_commit"]) == 40
    assert report["lade_zaehler"]["geladen"] == 36
    # Final-Fix 5: `herkunft` zaehlt `label_origin` ueber die geladenen
    # Proben - hier laedt der Loader ausschliesslich `serial_ascii` (der
    # Filter in `_iter_resolved_records` laesst nichts anderes durch).
    assert report["herkunft"] == {"serial_ascii": 36}
    for durchgang in report["durchgaenge"]:
        for key in ("train_groups", "test_group", "d_max", "margin_min", "summary", "confusion", "plateaus"):
            assert key in durchgang
        assert durchgang["test_group"] not in durchgang["train_groups"]


def test_reader_check_agrees_with_evaluate_on_synthetic_dataset(tmp_path):
    dataset_root, map_path = _build_three_group_dataset(tmp_path)
    templates_path = tmp_path / "templates.json"
    rc = train_mod.main(
        [
            "--dataset-root", str(dataset_root),
            "--profile-map", str(map_path),
            "--groups", "g1,g2,g3",
            "--out", str(templates_path),
        ]
    )
    assert rc == 0

    rc = eval_mod.main(
        [
            "reader-check",
            "--dataset-root", str(dataset_root),
            "--profile-map", str(map_path),
            "--templates", str(templates_path),
            "--templates-sha256", _sha256(templates_path),
            "--limit", "10",
        ]
    )
    assert rc == 0


def test_reader_check_reports_genuine_disagreement(tmp_path, monkeypatch, capsys):
    """Fix Runde 1 (Review-Befund): `reader-check` war nur auf einem
    Datensatz getestet, auf dem Leser und Messung immer einig sind - das
    beweist nicht, dass eine echte Uneinigkeit erkannt und gemeldet wird.
    Der Leser wird hier fuer GENAU eine erfolgreich gelesene Probe auf einen
    Ablehnungsgrund gezwungen, den `evaluate()` fuer dieselbe Probe NICHT
    liefert (`zelle_unbekannt` ist kein Bild-only-Grund wie `kontrast`/
    `ueberbelichtet` - siehe `_IMAGE_ONLY_REASONS`), damit eine echte
    Uneinigkeit entsteht."""
    from dispread.ocr.dotmatrix import DotMatrixReader

    dataset_root, map_path = _build_three_group_dataset(tmp_path)
    templates_path = tmp_path / "templates.json"
    rc = train_mod.main(
        [
            "--dataset-root", str(dataset_root),
            "--profile-map", str(map_path),
            "--groups", "g1,g2,g3",
            "--out", str(templates_path),
        ]
    )
    assert rc == 0
    capsys.readouterr()  # Ausgabe des Trainings verwerfen, nur reader-check auswerten

    original_read = DotMatrixReader.read
    state = {"forced_sample": None}

    def forcing_read(self, crop, layout):
        result = original_read(self, crop, layout)
        if state["forced_sample"] is None and result.diagnostics.get("reject_reason") is None:
            # Genau die erste bislang erfolgreich gelesene Probe kapern -
            # ein Grund, den evaluate() fuer dieselbe Probe nicht kennt.
            state["forced_sample"] = True
            diag = dict(result.diagnostics)
            diag["reject_reason"] = "zelle_unbekannt"
            return dataclasses.replace(result, value=None, raw_text="", diagnostics=diag)
        return result

    monkeypatch.setattr(DotMatrixReader, "read", forcing_read)

    rc = eval_mod.main(
        [
            "reader-check",
            "--dataset-root", str(dataset_root),
            "--profile-map", str(map_path),
            "--templates", str(templates_path),
            "--templates-sha256", _sha256(templates_path),
            "--limit", "10",
        ]
    )

    assert state["forced_sample"] is True  # sonst waere der Test bedeutungslos
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert len(out["uneinig"]) == 1
    entry = out["uneinig"][0]
    assert entry["leser"] == "abgelehnt:zelle_unbekannt"
    assert entry["messung"] != "abgelehnt:zelle_unbekannt"


def test_reader_check_normalizes_vorzeichen_to_format_as_agreement(tmp_path):
    """Fix Runde 1: die `vorzeichen`->`format`-Normierung (`_normalize_reason`)
    war unbeuebt - eine Probe mit falscher Vorzeichenzelle (Bild zeigt '8'
    statt '+') laesst den Leser mit eigenem Grund `vorzeichen` ablehnen,
    `evaluate()` (kennt kein `vorzeichen`) mit `format`. Beides verweigert
    denselben Wert und muss als Einigkeit zaehlen, nicht als `uneinig`."""
    dataset_root, map_path = _build_three_group_dataset(tmp_path)
    templates_path = tmp_path / "templates.json"
    rc = train_mod.main(
        [
            "--dataset-root", str(dataset_root),
            "--profile-map", str(map_path),
            "--groups", "g1,g2,g3",
            "--out", str(templates_path),
        ]
    )
    assert rc == 0

    # Eigener Mini-Datensatz mit einer einzigen Probe: Vorzeichenzelle zeigt
    # '8' statt '+' (aus dem Leser-Code bekannt: eine konfident falsch
    # erkannte Vorzeichenzelle -> Grund "vorzeichen", nicht "zelle_unbekannt").
    sign_root = tmp_path / "sign_dataset"
    _write_devices(sign_root)
    rng = np.random.default_rng(42)
    _write_sample(sign_root, "wrong-sign-0", "signtest", "80.60972 ", "80.60972 ", (1_000, 2_000), rng)
    sign_profiles = tmp_path / "sign_profiles"
    sign_profiles.mkdir()
    sign_map = _write_profile_map(sign_profiles, ["signtest"])

    from dispread.layout import CharLayout
    from dispread.ocr.dotmatrix import DotMatrixReader
    from dispread.ocr.dotmatrix_templates import load_templates

    templates = load_templates(templates_path)
    records = dataset_mod.load_resolved_records(sign_root, dataset_mod.read_profile_map(sign_map))
    assert len(records) == 1
    result = DotMatrixReader(templates).read(records[0].crop_gray, CharLayout(grid=records[0].grid, unit="mV/V"))
    assert result.diagnostics["reject_reason"] == "vorzeichen"  # Testannahme absichern

    rc = eval_mod.main(
        [
            "reader-check",
            "--dataset-root", str(sign_root),
            "--profile-map", str(sign_map),
            "--templates", str(templates_path),
            "--templates-sha256", _sha256(templates_path),
            "--limit", "5",
        ]
    )

    assert rc == 0  # als Einigkeit gezaehlt, nicht "uneinig"


# --- Fix Runde 1 (Controller): --exclude-groups ----------------------------


def test_loo_exclude_groups_drops_group_from_every_fold_and_lists_it_with_reason(tmp_path):
    dataset_root, map_path = _build_three_group_dataset(tmp_path)
    out = tmp_path / "report.json"

    rc = eval_mod.main(
        [
            "loo",
            "--dataset-root", str(dataset_root),
            "--profile-map", str(map_path),
            "--out", str(out),
            "--exclude-groups", "g3",
            "--exclude-reason", "Kamera zwischen Bestaetigung und Ernte verschoben (Test)",
        ]
    )
    assert rc == 0
    report = json.loads(out.read_text(encoding="utf-8"))

    assert "g3" not in report["groups"]
    assert set(report["groups"]) == {"g1", "g2"}
    assert report["excluded_groups"] == [
        {"group": "g3", "reason": "Kamera zwischen Bestaetigung und Ernte verschoben (Test)"}
    ]
    assert len(report["durchgaenge"]) == 2
    for durchgang in report["durchgaenge"]:
        assert "g3" not in durchgang["train_groups"]
        assert durchgang["test_group"] != "g3"
    # 24 statt 36 geladene Proben: g3s 12 Proben wurden zwar geladen (die
    # Datensatz-Zaehler zaehlen das Laden, nicht die Verwendung), aber vor
    # Training/Messung verworfen - siehe oben, kein g3 in irgendeinem
    # Durchgang.
    assert report["lade_zaehler"]["geladen"] == 36


def test_loo_exclude_groups_requires_reason(tmp_path):
    dataset_root, map_path = _build_three_group_dataset(tmp_path)
    out = tmp_path / "report.json"

    rc = eval_mod.main(
        [
            "loo",
            "--dataset-root", str(dataset_root),
            "--profile-map", str(map_path),
            "--out", str(out),
            "--exclude-groups", "g3",
        ]
    )

    assert rc == 2
    assert not out.exists()
