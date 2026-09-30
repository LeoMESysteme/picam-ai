"""Tests für scripts/docs-progress-data.py (Daten der Fortschrittsgrafik)."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "docs-progress-data.py"
spec = importlib.util.spec_from_file_location("docs_progress_data", SCRIPT)
progress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(progress)

GEN = "2026-09-29T00:00:00+00:00"


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


def _run(var: Path, name: str, *, session_id=None, harvest=True, session=True,
         imported=None, rejected=None, recorded=100, dropped=10, staging=False,
         started="2026-09-29T10:00:00+00:00") -> None:
    d = var / "diagnostics" / f"{name}-run"
    (d / "recording").mkdir(parents=True, exist_ok=True)
    if harvest:
        _write(d / "harvest.json", {
            "session_id": session_id or name,
            "summary": {"frames_total": recorded, "labeled": 50,
                        "distinct_label_texts": 7, "rejected_by_reason": {"x": 1}},
        })
    if session:
        s = {"started_at_utc": started, "frames_recorded": recorded,
             "frames_dropped_queue_full": dropped, "frame_gaps": {"count": 0}}
        if staging:
            s["staging"] = {"root": "/dev/shm"}
        _write(d / "recording" / "session.json", s)
    if imported is not None:
        _write(d / "import.json", {"imported": imported,
                                   "rejected_by_reason": rejected or {"a": 0}})


def _loo_report(groups: dict) -> dict:
    return {
        "git_commit": "0123456789abcdef",
        "groups": sorted(groups),
        "training_eligibility": {"groups": {g: {"eligible": g != "auf3"} for g in groups}},
        "lade_zaehler": {"geladen": 1},
        "durchgaenge": [
            {"test_group": g, "summary": s, "d_max": 2.5, "margin_min": 0.8,
             "plateaus": {"gesamt": 3, "richtig": 2, "falsch": 0, "abgelehnt": 1}}
            for g, s in groups.items()
        ],
    }


def _store(var: Path, counts: dict, *, extra: bool = True) -> None:
    root = var / "workbench" / "datasets"
    _write(root / "devices.json", {"devices": {
        "dev-gsv": {"name": "gsv-sensor-161a"}, "dev-led": {"name": "RND-Lab"}}})
    n = 0

    def sample(group, origin="serial_ascii", state="readable", device="dev-gsv", name=None):
        nonlocal n
        n += 1
        _write(root / "samples" / (name or f"s{n:04d}") / "sample.json", {
            "label_origin": origin, "label_state": state, "device_id": device,
            "label_origin_detail": {"session_id": group}})

    for group, k in counts.items():
        for _ in range(k):
            sample(group)
    if extra:  # darf alles nicht gezählt werden
        sample("sc6", device="dev-led")
        sample("sc6", origin="manual")
        sample("sc6", state="unreadable")
        sample("sc6", name=".sample-tmp")
        _write(root / "samples" / "kaputt" / "sample.json", '{"label_origin": ')


@pytest.fixture
def var(tmp_path: Path) -> Path:
    v = tmp_path / "var"
    _run(v, "sc6", imported=88, rejected={"zellen_inkonsistent": 1, "bildguete": 0},
         recorded=2468, dropped=1269, started="2026-09-29T11:25:13+00:00")
    _run(v, "sc6b", session_id="sc6", imported=131, rejected={"zellen_inkonsistent": 10},
         recorded=3737, dropped=0, staging=True, started="2026-09-29T12:23:20+00:00")
    _run(v, "sc1", imported=45, started="2026-09-28T09:00:00+00:00")
    _run(v, "ab3", imported=None, started="2026-09-29T13:55:00+00:00")
    _run(v, "ernte1", harvest=False, session=False)
    _write(v / "diagnostics" / "ernte1-profile" / "profile.json", {"session_id": "ernte1"})
    _write(v / "diagnostics" / "dotmatrix-profile-map.json",
           {"sc6": {"path": "x"}, "ernte1": {"path": "y"}})
    _write(v / "diagnostics" / "dotmatrix-loo-2026-09-29e.json", _loo_report({
        "sc6": {"richtig": 80, "abgelehnt:zelle_unbekannt": 5, "abgelehnt:zelle_mehrdeutig": 3},
        "auf3": {"richtig": 61, "falsch": 1},
    }))
    _write(v / "dotmatrix" / "abnahme-stufe2-2026-09-29.json", {
        "templates_sha256": "abc", "normalization": "ink_per_cell_v1",
        "gruppen": {"ab1": {"proben": {"gesamt": 99, "richtig": 99, "falsch": 0, "abgelehnt": 0}}},
        "gesamt": {"abgelehnt_anteil": 0.456}, "bestanden": False,
    })
    _store(v, {"sc6": 219, "ernte1": 152, "ab3": 40, "sc1": 3})
    return v


def test_schema_and_values(var: Path):
    data = progress.build(var, GEN)
    assert set(data) == {"schema", "generated_at", "harvests", "dataset", "loo_runs", "abnahmen"}
    assert data["schema"] == "fortschritt_v1" and data["generated_at"] == GEN

    harvest_keys = {"run", "setup", "group", "role", "started_at_utc", "frames_recorded",
                    "frames_dropped", "drop_fraction", "labeled", "distinct_values",
                    "staging_ram", "imported", "import_rejected"}
    runs = {h["run"]: h for h in data["harvests"]}
    assert all(set(h) == harvest_keys for h in data["harvests"])
    sc6 = runs["sc6-run"]
    assert (sc6["frames_recorded"], sc6["frames_dropped"]) == (2468, 1269)
    assert sc6["drop_fraction"] == round(1269 / 3737, 4)
    assert sc6["staging_ram"] is False and sc6["import_rejected"] == 1
    assert (sc6["labeled"], sc6["distinct_values"], sc6["role"]) == (50, 7, "training")
    sc6b = runs["sc6b-run"]
    assert (sc6b["setup"], sc6b["group"], sc6b["staging_ram"]) == ("sc6b", "sc6", True)
    assert sc6b["drop_fraction"] == 0.0
    assert runs["sc1-run"]["role"] == "verworfen"

    groups = {g["group"]: g for g in data["dataset"]["groups"]}
    assert all(set(g) == {"group", "role", "samples", "in_profile_map"} for g in groups.values())
    assert groups["sc6"] == {"group": "sc6", "role": "training", "samples": 219,
                             "in_profile_map": True}
    assert groups["sc1"]["samples"] == 0 and groups["sc1"]["role"] == "verworfen"
    assert groups["ernte1"]["samples"] == 152  # aus dem Store, ohne import.json
    # ab3: harvest.json ohne import.json -> Import offen, Store-Stand unsicher
    assert groups["ab3"]["samples"] is None and groups["ab3"]["in_profile_map"] is False
    assert data["dataset"]["total_samples"] == 219 + 152

    (loo,) = data["loo_runs"]
    assert set(loo) == {"file", "label", "normalization", "raster", "code_commit", "order", "groups"}
    assert (loo["label"], loo["normalization"], loo["raster"], loo["code_commit"], loo["order"]) == (
        "loo (e)", "ink_per_cell_v1", "alt", "0123456", 5)
    assert loo["groups"]["sc6"] == {
        "richtig": 80, "abgelehnt": 8, "falsch": 0, "plateaus_richtig": 2,
        "plateaus_abgelehnt": 1, "plateaus_falsch": 0, "d_max": 2.5, "training_eligible": True}
    assert loo["groups"]["auf3"]["falsch"] == 1
    assert loo["groups"]["auf3"]["training_eligible"] is False

    (ab,) = data["abnahmen"]
    assert ab == {"file": "abnahme-stufe2-2026-09-29.json",
                  "label": "Abnahme 1 (ink_per_cell_v1)", "templates_sha256": "abc",
                  "groups": {"ab1": {"richtig": 99, "abgelehnt": 0, "falsch": 0}},
                  "abgelehnt_anteil": 0.456, "bestanden": False}


def test_missing_files_become_null(var: Path):
    runs = {h["run"]: h for h in progress.build(var, GEN)["harvests"]}
    e1 = runs["ernte1-run"]
    assert e1["group"] == "ernte1"  # aus dem Profil
    for key in ("started_at_utc", "frames_recorded", "frames_dropped", "drop_fraction",
                "labeled", "distinct_values", "staging_ram", "imported", "import_rejected"):
        assert e1[key] is None, key
    assert runs["ab3-run"]["imported"] is None and runs["ab3-run"]["import_rejected"] is None


def test_incomplete_and_truncated_files(var: Path):
    d = var / "diagnostics" / "sc6b-run"
    _write(d / "import.json", '{"imported": 13')  # halb geschrieben
    _write(d / "recording" / "session.json", {"started_at_utc": "2026-09-29T12:00:00+00:00"})
    _write(d / "harvest.json", {"session_id": "sc6"})  # ohne summary
    data = progress.build(var, GEN)
    h = {h["run"]: h for h in data["harvests"]}["sc6b-run"]
    assert h["imported"] is None and h["frames_recorded"] is None and h["drop_fraction"] is None
    assert h["labeled"] is None and h["staging_ram"] is False and h["group"] == "sc6"
    groups = {g["group"]: g for g in data["dataset"]["groups"]}
    assert groups["sc6"]["samples"] is None  # import.json unlesbar -> Import offen


def test_import_finished_counts_store(var: Path):
    _write(var / "diagnostics" / "ab3-run" / "import.json", {"imported": 40})
    groups = {g["group"]: g for g in progress.build(var, GEN)["dataset"]["groups"]}
    assert groups["ab3"]["samples"] == 40


def test_missing_store_gives_null(var: Path):
    import shutil
    shutil.rmtree(var / "workbench")
    data = progress.build(var, GEN)
    groups = {g["group"]: g for g in data["dataset"]["groups"]}
    assert groups["sc6"]["samples"] is None and groups["ernte1"]["samples"] is None
    assert groups["sc1"]["samples"] == 0  # verworfen bleibt 0
    assert data["dataset"]["total_samples"] == 0


def test_empty_var_tree(tmp_path: Path):
    data = progress.build(tmp_path / "var", GEN)
    assert data["harvests"] == [] and data["loo_runs"] == [] and data["abnahmen"] == []
    assert data["dataset"] == {"groups": [], "total_samples": 0}


def test_output_is_deterministic(var: Path, tmp_path: Path):
    out1, out2 = tmp_path / "a" / "f.json", tmp_path / "b" / "f.json"
    for out in (out1, out2):
        assert progress.main(["--var-root", str(var), "--out", str(out),
                              "--generated-at", GEN]) == 0
    text = out1.read_text(encoding="utf-8")
    assert text == out2.read_text(encoding="utf-8")
    assert text == progress.dumps(json.loads(text))


def test_refuses_output_under_var(var: Path):
    with pytest.raises(SystemExit):
        progress.main(["--var-root", str(var), "--out", str(var / "x.json")])


def test_loo_normalization_from_report_and_short_label_for_unknown_file(tmp_path):
    """Neue loo-Berichte tragen `normalization` selbst (seit 2026-09-30);
    unbekannte Dateien bekommen den Namen ohne `dotmatrix-loo-`."""
    diag = tmp_path / "diagnostics"
    diag.mkdir()
    (diag / "dotmatrix-loo-2026-10-01-neu.json").write_text(json.dumps(
        {"durchgaenge": [], "normalization": "bg_closing_v1", "git_commit": "f" * 40}))
    (run,) = progress.collect_loo(diag)
    assert (run["label"], run["normalization"], run["raster"]) == ("2026-10-01-neu", "bg_closing_v1", None)


def test_unknown_acceptance_file_gets_next_number(tmp_path):
    dm = tmp_path / "dotmatrix"
    dm.mkdir()
    (dm / "abnahme-stufe3-2026-10-02.json").write_text(json.dumps({"normalization": "x", "gruppen": {}}))
    (entry,) = progress.collect_abnahmen(dm)
    assert entry["label"] == f"Abnahme {len(progress.ABNAHME_LABELS) + 1} (x)"
