"""`scripts/display-offset.py` - Ende-zu-Ende-Versatz Telegramm<->Anzeige,
photometrisch, per Vorlagen-Projektion (Task B aus
docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md).

Zweite Fassung: die erste (globale Bild-zu-Bild-Differenz, ensemble-
gemittelt) fand auf allen vier echten Aufzeichnungen "kein Signal" - eine
Gegenpruefung zeigte, dass das ein Methodenfehler war (Mittelung ueber den
ganzen Ausschnitt verduennt ein raeumlich kleines Signal weg), kein echter
Befund. Diese Fassung projiziert stattdessen jedes Bild auf die Verbindungs-
linie zweier Vorlagenbilder (Plateau davor/danach) - siehe Moduldocstring in
`scripts/display-offset.py`.

Das Skript hat einen Bindestrich im Namen und ist kein Package-Modul - wird
per `importlib` direkt geladen (wie `scripts/gate-label.py`, CLI-Teil per
Subprozess, siehe `tests/test_gate_label.py`).

Zeitbasis: `capture_timestamp.value_ns` ist Nanosekunden (int),
CLOCK_BOOTTIME; `serial.jsonl`s `t_boot` ist bereits Sekunden (float),
dieselbe Domaene.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

REPO_ROOT = Path(__file__).parents[1]
SCRIPT = REPO_ROOT / "scripts" / "display-offset.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("display_offset_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()


# ---------------------------------------------------------------------------
# Zeitbasis: ns (frames.jsonl) vs. s (serial.jsonl)
# ---------------------------------------------------------------------------


def test_load_frames_rechnet_nanosekunden_korrekt_in_sekunden_um(tmp_path):
    session = tmp_path / "session"
    (session / "frames").mkdir(parents=True)
    (session / "frames.jsonl").write_text(
        json.dumps(
            {
                "file": "frame_000001.jpg",
                "frame_sequence": 1,
                "capture_timestamp": {
                    "value_ns": 63749692983000,
                    "base": "sensor_boottime",
                    "semantics": "unknown",
                    "uncertainty_ns": None,
                },
            }
        )
        + "\n"
    )
    rows = mod.load_frames(session)
    assert len(rows) == 1
    assert rows[0]["t"] == pytest.approx(63749.692983000, abs=1e-9)
    assert rows[0]["file"] == "frames/frame_000001.jpg"


def test_load_serial_t_boot_bleibt_sekunden_und_markiert_nicht_telegramm_zeilen(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    (session / "serial.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"t_boot": 100.5, "text": "+0.60397 mV/V"}),
                json.dumps({"t_boot": 101.0, "text": "SET NORM 16", "kind": "command"}),
                json.dumps({"t_boot": 101.5, "text": "+0.60398 mV/V"}),
            ]
        )
    )
    rows = mod.load_serial(session)
    assert [r["t_boot"] for r in rows] == [100.5, 101.0, 101.5]
    assert [r["is_telegram"] for r in rows] == [True, False, True]


# ---------------------------------------------------------------------------
# Plateaus (`build_runs`) und Wechselereignisse (`classify_events`)
# ---------------------------------------------------------------------------


def _telegram_rows(pairs):
    return [{"t_boot": t, "text": text, "is_telegram": True} for t, text in pairs]


def test_build_runs_fasst_gleiche_telegramme_zu_plateaus_zusammen():
    rows = _telegram_rows([(0.0, "A"), (0.5, "A"), (1.0, "A"), (1.5, "B")])
    runs = mod.build_runs(rows)
    assert [(r["text"], r["n_telegrams"]) for r in runs] == [("A", 3), ("B", 1)]
    assert runs[0]["t_start"] == 0.0
    assert runs[0]["t_end"] == 1.0


def test_classify_events_trennt_small_und_large_und_ueberspringt_nicht_telegramm():
    rows = [
        {"t_boot": 0.0, "text": "+0.60397 mV/V", "is_telegram": True},
        {"t_boot": 0.5, "text": "+0.60397 mV/V", "is_telegram": True},
        {"t_boot": 1.0, "text": "SET NORM 16", "is_telegram": False},
        {"t_boot": 1.5, "text": "+0.60398 mV/V", "is_telegram": True},  # small (1 Zeichen)
        {"t_boot": 2.0, "text": "-1.71398 mV/V", "is_telegram": True},  # large (mehrere Zeichen)
    ]
    events = mod.classify_events(rows, session_end_t=3.0)
    assert [e["group"] for e in events] == ["small", "large"]
    assert events[0]["t"] == 1.5
    assert events[0]["run_a"] == (0.0, 1.5)
    assert events[0]["run_b"] == (1.5, 2.0)
    assert events[1]["run_b"] == (2.0, 3.0)  # letztes Plateau reicht bis session_end_t


def test_classify_events_isolated_erfordert_ruhiges_intervall_davor():
    ramp = _telegram_rows([(0.0, "+0.63390"), (0.4, "+0.63396"), (0.8, "+0.63397"), (1.2, "+0.63398")])
    events = mod.classify_events(ramp, session_end_t=1.6)
    assert len(events) == 3
    assert all(e["isolated"] is False for e in events)

    plateau_then_change = _telegram_rows([(0.0, "+0.60397"), (0.5, "+0.60397"), (1.0, "+0.60398")])
    events = mod.classify_events(plateau_then_change, session_end_t=1.5)
    assert len(events) == 1
    assert events[0]["isolated"] is True


# ---------------------------------------------------------------------------
# Vorlagen-Projektion: Bausteine ohne Bild-I/O
# ---------------------------------------------------------------------------


def test_deep_indices_nimmt_die_mitte_und_weitet_bei_bedarf():
    times = np.arange(0.0, 10.0, 0.1)  # 100 Bilder, 0.0 .. 9.9
    idx = mod.deep_indices(times, 0.0, 10.0, min_frames=3, margin_start=0.3)
    # mittlere 40% von [0,10) -> [3,7)
    assert times[idx[0]] >= 3.0 - 1e-9
    assert times[idx[-1]] < 7.0

    # zu kurzes Intervall fuer margin_start=0.3 mit min_frames=5 -> weitet sich
    idx_narrow = mod.deep_indices(times, 0.0, 0.35, min_frames=5, margin_start=0.3)
    assert idx_narrow.size >= 3  # 0.0..0.35 hat nur 4 Bilder (0.0,0.1,0.2,0.3)


def test_deep_indices_respektiert_ausschlussmaske():
    times = np.arange(0.0, 2.0, 0.1)
    excluded = np.zeros(times.size, dtype=bool)
    excluded[5:15] = True  # der ganze mittlere Bereich verdeckt
    idx = mod.deep_indices(times, 0.0, 2.0, min_frames=3, margin_start=0.0, excluded_mask=excluded)
    assert not any(excluded[i] for i in idx)


def test_crossing_time_interpoliert_linear():
    times = np.array([0.0, 1.0, 2.0])
    p = np.array([0.0, 1.0, 1.0])
    t = mod._crossing_time(times, p, 0.5)
    assert t == pytest.approx(0.5)
    assert mod._crossing_time(times, p, 5.0) is None


# ---------------------------------------------------------------------------
# `analyze_event_template`: langsamer, raeumlich kleiner Uebergang - der vom
# Auftraggeber verlangte Beweis, dass die Projektion (anders als eine
# globale Differenz ueber den ganzen Ausschnitt) ein kleines Signal in einer
# langsamen Flanke wiederfindet.
# ---------------------------------------------------------------------------


def _write_slow_small_area_transition(session_dir: Path, *, w, h, fps, n_frames, t_event, true_delta_s, ramp_duration_s,
                                       patch, a_val, b_val, noise_sigma, seed=0):
    frames_dir = session_dir / "frames"
    frames_dir.mkdir(parents=True)
    rng = np.random.default_rng(seed)
    dt = 1.0 / fps
    y0, y1, x0, x1 = patch
    ramp_start = t_event + true_delta_s - ramp_duration_s / 2
    frames = []
    for i in range(n_frames):
        t = i * dt
        frac = float(np.clip((t - ramp_start) / ramp_duration_s, 0.0, 1.0))
        img = np.full((h, w, 3), a_val, dtype=np.float64)
        img[y0:y1, x0:x1, :] = a_val + frac * (b_val - a_val)
        img += rng.normal(0.0, noise_sigma, size=img.shape)
        img = np.clip(img, 0, 255).astype(np.uint8)
        fname = f"frame_{i + 1:06d}.jpg"
        cv2.imwrite(str(frames_dir / fname), img)
        frames.append({"file": f"frames/{fname}", "t": t})
    return frames


def test_analyze_event_template_findet_delta_bei_langsamem_kleinflaechigem_uebergang(tmp_path):
    session_dir = tmp_path / "slow"
    w, h = 80, 50
    fps = 30.0
    n_frames = 120  # 4s
    t_event = 1.8
    true_delta_s = 0.07  # 70ms: Glas folgt dem Telegramm
    ramp_duration_s = 0.2  # "LCD-artiger" 200ms-Uebergang statt Sprung
    # Patch ist klein: 8x16 = 128 von 80*50=4000 Pixeln (~3.2%).
    patch = (5, 13, 5, 21)

    frames = _write_slow_small_area_transition(
        session_dir,
        w=w,
        h=h,
        fps=fps,
        n_frames=n_frames,
        t_event=t_event,
        true_delta_s=true_delta_s,
        ramp_duration_s=ramp_duration_s,
        patch=patch,
        a_val=100.0,
        b_val=170.0,
        noise_sigma=1.0,
    )
    frame_times = np.array([f["t"] for f in frames])
    quad_px = ((0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1))

    res = mod.analyze_event_template(
        frame_times,
        frames,
        session_dir,
        quad_px,
        (w, h),
        t_event,
        (0.2, t_event),
        (t_event, 3.6),
        half_window_s=0.5,
        min_template_frames=5,
        margin_start=0.3,
        noise_k=3.0,
        guard_s=0.02,
        n_iterations=2,
    )
    assert res["measurable"], res.get("reason")
    assert res["delta_s"] == pytest.approx(true_delta_s, abs=0.02)
    assert res["d_misch_s"] == pytest.approx(0.8 * ramp_duration_s, abs=0.03)


def test_analyze_event_template_lehnt_ab_wenn_signal_im_rauschen_untergeht(tmp_path):
    """Kein echter Uebergang (A==B, nur Rauschen) - muss als unmessbar
    ausgewiesen werden, nicht geraten."""
    session_dir = tmp_path / "flat"
    w, h = 40, 30
    fps = 20.0
    n_frames = 60
    frames_dir = session_dir / "frames"
    frames_dir.mkdir(parents=True)
    rng = np.random.default_rng(1)
    dt = 1.0 / fps
    frames = []
    for i in range(n_frames):
        img = np.full((h, w, 3), 100.0, dtype=np.float64)
        img += rng.normal(0.0, 1.0, size=img.shape)
        img = np.clip(img, 0, 255).astype(np.uint8)
        fname = f"frame_{i + 1:06d}.jpg"
        cv2.imwrite(str(frames_dir / fname), img)
        frames.append({"file": f"frames/{fname}", "t": i * dt})
    frame_times = np.array([f["t"] for f in frames])
    quad_px = ((0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1))
    res = mod.analyze_event_template(
        frame_times, frames, session_dir, quad_px, (w, h), 1.5, (0.2, 1.5), (1.5, 2.8),
        half_window_s=0.5, min_template_frames=5, margin_start=0.3, noise_k=3.0, guard_s=0.02, n_iterations=1,
    )
    assert res["measurable"] is False
    assert "reason" in res


def test_compute_m_folgt_der_festgelegten_formel():
    m = mod.compute_M(delta_s=-0.05, d_misch_s=0.08, sigma_delta_s=0.01)
    assert m == pytest.approx(0.05 + 0.08 + 3 * 0.01 + 0.040)


def test_population_detected_verlangt_mindestzahl_und_spezifische_nullbaseline():
    pop_ok = {"n_qualifying": 5, "sigma_delta_s": 0.01}
    assert mod.population_detected(pop_ok, {"pass_rate": 0.1}, min_qualifying=3) is True
    assert mod.population_detected(pop_ok, {"pass_rate": 0.8}, min_qualifying=3) is False
    pop_wenig = {"n_qualifying": 1, "sigma_delta_s": 0.01}
    assert mod.population_detected(pop_wenig, {"pass_rate": 0.0}, min_qualifying=3) is False


# ---------------------------------------------------------------------------
# commands.jsonl: Normierungswechsel-Zyklen (pause -> command(s) -> resume)
# ---------------------------------------------------------------------------


def test_command_groups_gruppiert_pause_command_resume_nach_label():
    commands = [
        {"event": "pause_transmission", "label": "a", "t_boot": 1.0},
        {"event": "command", "label": "a", "command_name": "set_norm", "t_boot": 1.5},
        {"event": "command", "label": "a", "command_name": "set_dpoint", "t_boot": 1.8},
        {"event": "resume_transmission", "label": "a", "t_boot": 2.0},
        {"event": "pause_transmission", "label": "precheck-nur-lesen", "t_boot": 5.0},
        {"event": "register_read", "label": "precheck-nur-lesen", "t_boot": 5.2},
        {"event": "resume_transmission", "label": "precheck-nur-lesen", "t_boot": 5.4},
    ]
    groups = mod.command_groups(commands)
    assert len(groups) == 1  # die reine Lesegruppe hat kein set_norm -> zaehlt nicht
    assert groups[0]["t_set_norm"] == 1.5
    assert groups[0]["t_set_dpoint"] == 1.8
    assert groups[0]["t_resume"] == 2.0


# ---------------------------------------------------------------------------
# Verdeckungserkennung (photometrischer Ausreisser ohne Telegrammereignis)
# ---------------------------------------------------------------------------


def test_detect_occlusion_mask_markiert_ausreisser():
    means = np.array([110.0] * 20 + [40.0, 38.0] + [110.5] * 20)
    mask = mod.detect_occlusion_mask(means, mad_k=8.0)
    assert mask[20] and mask[21]
    assert not mask[:20].any()
    assert not mask[22:].any()


# ---------------------------------------------------------------------------
# Ende-zu-Ende mit synthetischer Aufzeichnung (Plumbing: locate_quad ->
# classify_events -> analyze_population_template -> null_baseline_template)
# ---------------------------------------------------------------------------


def _write_synthetic_recording(session_dir, *, fps, n_frames, event_interval_s, n_events, start_offset_s,
                                true_delta_s, low, high, noise_sigma, image_size=(60, 40), seed=0):
    """Ganzflaechiger gruener Patch, der pro Ereignis zwischen `low`/`high`
    umschaltet (Sprung, nicht Rampe - die langsame Rampe ist bereits oben
    eigens getestet; hier geht es um die Verdrahtung: Quadsuche, Plateaus,
    Isolations-/Ramp-Filter, Populations- und Nullbaseline-Aggregation)."""
    frames_dir = session_dir / "frames"
    frames_dir.mkdir(parents=True)
    rng = np.random.default_rng(seed)
    dt = 1.0 / fps
    w, h = image_size

    event_times = [k * event_interval_s + start_offset_s for k in range(1, n_events + 1)]
    change_times = sorted(t + true_delta_s for t in event_times)

    def level(t):
        count = sum(1 for ct in change_times if ct <= t)
        return high if count % 2 == 1 else low

    frames_jsonl_lines = []
    for i in range(n_frames):
        t = i * dt
        lv = float(np.clip(level(t) + rng.normal(0.0, noise_sigma), 0, 255))
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:, :, 0] = 20
        img[:, :, 1] = int(round(lv))
        img[:, :, 2] = 40
        filename = f"frame_{i + 1:06d}.jpg"
        cv2.imwrite(str(frames_dir / filename), img)
        frames_jsonl_lines.append(
            json.dumps(
                {
                    "file": filename,
                    "frame_sequence": i + 1,
                    "capture_timestamp": {
                        "value_ns": int(round(t * 1e9)),
                        "base": "sensor_boottime",
                        "semantics": "unknown",
                        "uncertainty_ns": None,
                    },
                }
            )
        )
    (session_dir / "frames.jsonl").write_text("\n".join(frames_jsonl_lines) + "\n")

    base_values = [
        "+0.60397 mV/V",
        "+0.60398 mV/V",  # small
        "-1.60398 mV/V",  # large
        "-1.60399 mV/V",  # small
        "+2.71399 mV/V",  # large
        "+2.71398 mV/V",  # small
        "-3.82398 mV/V",  # large
        "-3.82399 mV/V",  # small
        "+4.93399 mV/V",  # large
    ]
    assert len(base_values) - 1 >= n_events
    serial_lines = []
    for k, t in enumerate([0.0] + event_times):
        text = base_values[k]
        serial_lines.append(json.dumps({"t_boot": t, "text": text}))
        if k < len(event_times):
            serial_lines.append(json.dumps({"t_boot": t + event_interval_s * 0.5, "text": text}))
    (session_dir / "serial.jsonl").write_text("\n".join(serial_lines) + "\n")
    (session_dir / "session.json").write_text(json.dumps({"frames_recorded": n_frames}))
    return event_times, change_times


FPS = 30.0
DT = 1.0 / FPS
TRUE_DELTA_S = 0.083
EVENT_INTERVAL_S = 12 * DT  # 0.4s
N_EVENTS = 8
N_FRAMES = 160
HALF_WINDOW_S = 0.15


@pytest.fixture(scope="module")
def synthetic_recording(tmp_path_factory):
    session_dir = tmp_path_factory.mktemp("display_offset_synth")
    event_times, change_times = _write_synthetic_recording(
        session_dir,
        fps=FPS,
        n_frames=N_FRAMES,
        event_interval_s=EVENT_INTERVAL_S,
        n_events=N_EVENTS,
        start_offset_s=6 * DT,
        true_delta_s=TRUE_DELTA_S,
        low=90,
        high=170,
        noise_sigma=1.5,
    )
    return session_dir, event_times, change_times


def test_locate_quad_findet_stabiles_quad_auf_synthetischer_aufzeichnung(synthetic_recording):
    session_dir, _e, _c = synthetic_recording
    frames = mod.load_frames(session_dir)
    loc = mod.locate_quad(session_dir, frames, hint_box=(0.05, 0.05, 0.9, 0.9), sample_frames=5)
    assert loc["stable"] is True
    assert loc["n_samples"] == 5


def test_locate_quad_bricht_ab_wenn_kein_quad_gefunden_wird(synthetic_recording):
    session_dir, _e, _c = synthetic_recording
    frames = mod.load_frames(session_dir)
    with pytest.raises(RuntimeError):
        mod.locate_quad(session_dir, frames, hint_box=(0.0, 0.0, 0.01, 0.01), sample_frames=3)


def test_populations_und_nullbaseline_end_to_end(synthetic_recording):
    session_dir, _e, _c = synthetic_recording
    frames = mod.load_frames(session_dir)
    frame_times = np.array([f["t"] for f in frames])
    serial = mod.load_serial(session_dir)
    events = mod.classify_events(serial, session_end_t=float(frame_times[-1]))
    runs = mod.build_runs(serial)

    loc = mod.locate_quad(session_dir, frames, hint_box=(0.05, 0.05, 0.9, 0.9), sample_frames=5)
    assert loc["stable"]
    first_img = cv2.imread(str(session_dir / frames[0]["file"]))
    h, w = first_img.shape[:2]
    quad_px = mod.quad_to_pixels(loc["quad_norm"], w, h)

    # Occlusion-Erkennung wird hier bewusst NICHT verwendet: diese
    # synthetische Aufzeichnung schaltet den GANZEN Ausschnitt (nicht nur
    # eine kleine Ziffernflaeche) mehrfach zwischen zwei etwa gleich
    # haeufigen, weit auseinanderliegenden Helligkeiten um - genau das
    # Muster, das der global-robuste MAD-Ausreissertest nicht von einer
    # kurzen Verdeckung unterscheiden kann (er ist fuer seltene, kurze
    # Anomalien vor stabiler Basislinie ausgelegt, nicht fuer haeufige,
    # etwa gleich verteilte Helligkeitswechsel). `detect_occlusion_mask`
    # ist eigens an einem klaren Ausreisser-Array getestet
    # (`test_detect_occlusion_mask_markiert_ausreisser`); auf den drei
    # echten Aufzeichnungen (Bericht) verhielt es sich plausibel.
    occluded = None

    rng = np.random.default_rng(0)
    results = {}
    for group in ("small", "large"):
        group_events = [e for e in events if e["group"] == group and e["isolated"]]
        assert len(group_events) >= 3, f"Testaufbau: zu wenige isolierte {group}-Ereignisse"
        pop = mod.analyze_population_template(
            group,
            group_events,
            frame_times,
            frames,
            session_dir,
            quad_px,
            (60, 40),
            occluded,
            half_window_s=HALF_WINDOW_S,
            min_template_frames=3,
            margin_start=0.3,
            noise_k=3.0,
            guard_s=0.01,
            n_iterations=2,
        )
        null = mod.null_baseline_template(
            frame_times,
            frames,
            session_dir,
            quad_px,
            (60, 40),
            occluded,
            runs,
            half_window_s=HALF_WINDOW_S,
            min_template_frames=3,
            margin_start=0.3,
            noise_k=3.0,
            guard_s=0.01,
            rng=rng,
        )
        pop["detected"] = mod.population_detected(pop, null, min_qualifying=3)
        results[group] = (pop, null)

    for group, (pop, null) in results.items():
        assert pop["n_qualifying"] >= 3, group
        assert pop["delta_s"] == pytest.approx(TRUE_DELTA_S, abs=DT * 2), group
        assert pop["sigma_delta_s"] is not None
        # Die Nullbaseline (Splitpunkte in unveraenderten Plateaus) soll den
        # |B-A|-Rauschtest ueberwiegend zu Recht nicht bestehen.
        assert null["pass_rate"] is None or null["pass_rate"] < 0.5, group


# ---------------------------------------------------------------------------
# CLI als Subprozess (Muster aus tests/test_gate_label.py)
# ---------------------------------------------------------------------------


def test_cli_laeuft_end_to_end_und_schreibt_json(synthetic_recording, tmp_path):
    session_dir, _e, _c = synthetic_recording
    out_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(session_dir),
            "--hint-box",
            "0.05,0.05,0.9,0.9",
            "--out",
            str(out_dir),
            "--half-window-s",
            str(HALF_WINDOW_S),
            "--guard-s",
            "0.01",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    out_json = out_dir / "offset-analyse.json"
    assert out_json.exists()
    payload = json.loads(out_json.read_text())
    assert payload["method"] == "template_projection"
    assert payload["sign_convention"].startswith("delta = t_glas - t_telegramm")
    assert {"small", "large"} == {p["population"] for p in payload["populations"]}
    assert payload["quad"]["stable"] is True
    assert "occlusion" in payload
    assert "Sitzung:" in result.stdout


def test_cli_ohne_hint_box_schlaegt_mit_klarer_fehlermeldung_fehl(synthetic_recording):
    session_dir, _e, _c = synthetic_recording
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(session_dir)], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30
    )
    assert result.returncode != 0
    assert "hint-box" in result.stderr or "hint_box" in result.stderr
