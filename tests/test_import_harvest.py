"""`scripts/import-harvest.py` (Ernte Phase 1, Task 5).

Baut eine kleine synthetische Ernte (Sitzungsprofil + proposal.json +
recording/) direkt in `tmp_path` und prueft den Import gegen einen frischen
`DatasetStore`, ebenfalls in `tmp_path`. Kein Kamera-/Portzugriff, keine
echten Datensatzwurzeln (siehe AGENTS.md/Auftrag dieser Aufgabe).

Das Zellenraster ist bewusst klein (5 Zellen) und das Quad deckungsgleich mit
`target_size` (Massstab 1, keine Verzerrung) - das haelt die synthetischen
Bilder einfach, ohne die zu pruefende Logik (Auswahl, Bildguete,
Zellenkonsistenz, Store-Anlage) zu beruehren.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np

from dispread.charcells import CharGrid
from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile
from dispread.workbench.datasets import DatasetStore

SCRIPT = Path(__file__).parents[1] / "scripts" / "import-harvest.py"

_spec = importlib.util.spec_from_file_location("import_harvest", SCRIPT)
import_harvest = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = import_harvest
_spec.loader.exec_module(import_harvest)

TARGET_SIZE = (100, 40)  # (Breite, Hoehe), 5 Zellen a 20px
N_CELLS = 5


def _grid() -> CharGrid:
    return CharGrid(n_cells=N_CELLS, left=0.0, pitch=20.0, top=0.0, bottom=40.0)


def _quad() -> list[list[float]]:
    w, h = TARGET_SIZE
    return [[0.0, 0.0], [float(w), 0.0], [float(w), float(h)], [0.0, float(h)]]


def _render(
    chars: str,
    *,
    base: int = 235,
    noise: np.random.Generator | None = None,
    grid: CharGrid | None = None,
    size: tuple[int, int] | None = None,
) -> np.ndarray:
    """Zeichnet `chars` (eines je Zelle) mit `cv2.putText` in ein Graubild
    passend zu `grid`/`size` (Vorgabe: `_grid()`/`TARGET_SIZE`). Deterministisch
    bis auf optionales Rauschen (fuer realistische, aber noch konsistente
    Bildguete-Werte)."""
    grid = grid or _grid()
    w, h = size or TARGET_SIZE
    canvas = np.full((h, w), base, dtype=np.uint8)
    for box, ch in zip(grid.cell_boxes(), chars, strict=False):
        if ch == " ":
            continue
        x, y, cw, ch_h = box
        cv2.putText(canvas, ch, (x + 2, y + ch_h - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 1, cv2.LINE_8)
    if noise is not None:
        canvas = np.clip(canvas.astype(np.float64) + noise.normal(0, 2.0, size=canvas.shape), 0, 255).astype(
            np.uint8
        )
    return cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)


def _profile(tmp_path: Path, *, resolution_ok: bool = True) -> Path:
    profile = SessionProfile(
        schema_version=PROFILE_SCHEMA_VERSION,
        device_id="gsv2as-test",
        session_id="sess-1",
        quad=_quad(),
        target_size=TARGET_SIZE,
        grid=_grid(),
        scaler_crop=None,
        min_source_dot_column_px=5.0,
        native_scale=1.0,
        min_native_dot_column_px=5.0,
        resolution_threshold_px=2.0,
        resolution_ok=resolution_ok,
        confirmed_by="tester",
        confirmed_at_utc="2026-09-23T12:00:00+00:00",
    )
    path = tmp_path / "profile.json"
    profile.save(path)
    return path


def _detail(plateau_start: int, plateau_end: int) -> dict:
    return {
        "source_port": "/dev/ttyUSB0",
        "guard_margin_ms": 695.0,
        "plateau_start_ns": plateau_start,
        "plateau_end_ns": plateau_end,
        "telegram_count": 3,
    }


def _build_harvest(
    tmp_path: Path,
    *,
    plateaus: list[tuple[str, int, list[str | None]]],
) -> Path:
    """Baut `harvest/recording/frames/*.jpg`, `recording/frames.jsonl` und
    `harvest/proposal.json`.

    `plateaus` ist eine Liste `(telegram_text, n_images, [glyphs_override, ...])`
    - `glyphs_override[i]` ersetzt die tatsaechlich GEZEICHNETEN Zeichen des
    i-ten Bildes dieses Plateaus (Standard: `telegram_text` selbst), um
    absichtlich fehlerhafte oder qualitativ schlechte Bilder zu bauen.
    """
    harvest_dir = tmp_path / "harvest"
    frames_dir = harvest_dir / "recording" / "frames"
    frames_dir.mkdir(parents=True)

    rng = np.random.default_rng(42)
    frames_jsonl = []
    images = []
    seq = 0
    t_ns = 1_000_000_000
    for telegram_text, n_images, overrides in plateaus:
        plateau_start = t_ns
        plateau_end = t_ns + (n_images - 1) * 500_000_000 + 2000
        for i in range(n_images):
            seq += 1
            fname = f"frame_{seq:06d}.jpg"
            glyphs = overrides[i] if overrides and overrides[i] is not None else telegram_text
            if glyphs == "__black__":
                img = np.zeros((TARGET_SIZE[1], TARGET_SIZE[0], 3), dtype=np.uint8)
            else:
                # Realistische Streuung der Hintergrundhelligkeit zwischen
                # Bildern (Beleuchtung/Belichtung schwankt real) - ohne das
                # waere der Sitzungsmedian der Helligkeit so eng, dass jede
                # winzige, durch ein einzelnes Zeichen verursachte
                # Verschiebung faelschlich als Bildguete-Ausreisser gilt statt
                # von der Zellenkonsistenzpruefung (Regel 4) erfasst zu
                # werden - siehe test_zellen_inkonsistent_rejects_mislabeled_cell.
                base = int(rng.integers(228, 243))
                img = _render(glyphs, base=base, noise=rng)
            cv2.imwrite(str(frames_dir / fname), img)
            frames_jsonl.append(
                {
                    "file": fname,
                    "frame_sequence": seq,
                    "capture_timestamp": {
                        "value_ns": t_ns,
                        "base": "sensor_boottime",
                        "semantics": "unknown",
                        "uncertainty_ns": None,
                    },
                }
            )
            # `plateau_start_ns`/`plateau_end_ns` sind je Plateau KONSTANT
            # (Zeitstempel des ersten/letzten Telegramms des Plateaus, siehe
            # gate-label.py) - nicht je Bild verschieden, sonst waere jedes
            # Bild sein eigenes Ein-Bild-"Plateau" und die Auswahlregel
            # (Regel 2, `_select_per_plateau`) liefe leer.
            images.append(
                {
                    "image_path": str(frames_dir / fname),
                    "telegram_text": telegram_text,
                    "label_text": telegram_text,
                    "label_normalization": "gsv2as_leading_zero_v1",
                    "numeric_text": telegram_text,
                    "label_origin_detail": _detail(plateau_start, plateau_end),
                }
            )
            t_ns += 500_000_000
        t_ns += 5_000_000_000  # deutlicher Abstand zum naechsten Plateau

    (harvest_dir / "recording" / "frames.jsonl").write_text(
        "\n".join(json.dumps(f) for f in frames_jsonl) + "\n", encoding="utf-8"
    )
    (harvest_dir / "proposal.json").write_text(
        json.dumps({"images": images}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return harvest_dir


# --- Rule 5: Zeichen -> Zelle (siehe Modul-Docstring von import-harvest.py) ---


def test_cell_text_for_telegram_no_suppression():
    # "+0.60972 mV/V" - keine unterdrueckte Null (Wert < 1), siehe
    # var/diagnostics/scalercrop-114805/frames/frame_000001.jpg
    assert import_harvest._cell_text_for_telegram("+0.60972 mV/V") == "+0.60972 mV/V"


def test_cell_text_for_telegram_suppressed_zero_becomes_blank_cell():
    # "+01.2193 mV/V" -> Glas zeigt "+ 1.2193 mV/V" (Leerzelle an Position 1),
    # siehe var/diagnostics/offset-norm-101440/frames/frame_000206.jpg
    assert import_harvest._cell_text_for_telegram("+01.2193 mV/V") == "+ 1.2193 mV/V"


def test_padded_cell_text_fills_to_n_cells():
    assert import_harvest._padded_cell_text("+01.2193 mV/V", 16) == "+ 1.2193 mV/V   "


def test_expected_text_and_unit_strips_sign_and_unit():
    # Store-Konvention (Orchestrator-Entscheidung): expected_text ist der
    # reine Zahlenwert wie bei manuell gelabelten Proben, siehe
    # var/workbench/datasets/samples/663591e63681474eb1d89a420befa741/sample.json
    assert import_harvest._expected_text_and_unit("+0.60972 mV/V") == ("0.60972", "mV/V")
    assert import_harvest._expected_text_and_unit("+1.2193 mV/V") == ("1.2193", "mV/V")


def test_expected_text_and_unit_keeps_minus_sign():
    # '-' bleibt erhalten (auch wenn an diesem Geraet unerreichbar, OQ-37) -
    # nur '+' wird entfernt, weil normalize_label es nicht kennt.
    assert import_harvest._expected_text_and_unit("-0.60972 mV/V") == ("-0.60972", "mV/V")


# --- Auswahl (Regel 2) ---------------------------------------------------


def test_select_per_plateau_caps_count():
    images = [
        {"label_origin_detail": {"plateau_start_ns": 0, "plateau_end_ns": 100, "telegram_count": 1}}
        for _ in range(10)
    ]
    selected = import_harvest._select_per_plateau(images, per_plateau=3)
    assert len(selected) == 3


# --- Gesamtlauf ------------------------------------------------------------


def test_resolution_not_ok_aborts_before_store_access(tmp_path):
    profile_path = _profile(tmp_path, resolution_ok=False)
    harvest_dir = _build_harvest(tmp_path, plateaus=[("1.234", 1, None)])
    dataset_root = tmp_path / "dataset"
    args = import_harvest.parse_args(
        ["--harvest", str(harvest_dir), "--profile", str(profile_path), "--dataset-root", str(dataset_root)]
    )
    rc = import_harvest.run(args)
    assert rc == 3
    assert not dataset_root.exists()


def test_dry_run_creates_nothing(tmp_path):
    profile_path = _profile(tmp_path)
    harvest_dir = _build_harvest(tmp_path, plateaus=[("1.234", 3, None)] * 3)
    dataset_root = tmp_path / "dataset"
    args = import_harvest.parse_args(
        [
            "--harvest",
            str(harvest_dir),
            "--profile",
            str(profile_path),
            "--dataset-root",
            str(dataset_root),
            "--dry-run",
        ]
    )
    rc = import_harvest.run(args)
    assert rc == 0
    assert not dataset_root.exists()
    result = json.loads((harvest_dir / "import.json").read_text())
    assert result["dry_run"] is True
    assert result["imported"] == 0
    assert result["sample_ids"] == []


def test_successful_import_creates_samples_in_one_group(tmp_path):
    profile_path = _profile(tmp_path)
    # 3 Plateaus a 4 Bilder, alle mit demselben gueltigen Telegramm "1.234"
    # (5 Zeichen = 5 Zellen) - genug Vorkommen je Zeichen (>=5) fuer die
    # Zellenkonsistenzpruefung.
    harvest_dir = _build_harvest(tmp_path, plateaus=[("1.234", 4, None)] * 3)
    dataset_root = tmp_path / "dataset"
    args = import_harvest.parse_args(
        ["--harvest", str(harvest_dir), "--profile", str(profile_path), "--dataset-root", str(dataset_root)]
    )
    rc = import_harvest.run(args)
    assert rc == 0

    result = json.loads((harvest_dir / "import.json").read_text())
    assert result["imported"] > 0, result
    assert result["imported"] == len(result["sample_ids"])

    store = DatasetStore(dataset_root)
    devices = store.list_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device["name"] == "gsv2as-test"
    assert len(device["groups"]) == 1

    group_ids = set()
    for sample_id in result["sample_ids"]:
        sample = json.loads((dataset_root / "samples" / sample_id / "sample.json").read_text())
        assert sample["label_origin"] == "serial_ascii"
        for key in ("source_port", "guard_margin_ms", "plateau_start_ns", "plateau_end_ns", "telegram_count"):
            assert key in sample["label_origin_detail"], key
        assert sample["label_origin_detail"]["session_id"] == "sess-1"
        assert sample["label_origin_detail"]["telegram_text"] == "1.234"
        assert sample["label_origin_detail"]["gap_thresholds_provisional"] is True
        assert sample["expected_text"] == "1.234"
        group_ids.add(sample["independence_group"])
    assert len(group_ids) == 1


def test_bildguete_rejects_black_image(tmp_path):
    profile_path = _profile(tmp_path)
    # 3 normal belichtete Plateaus + ein Plateau mit einem komplett
    # schwarzen Bild - deutlicher Ausreisser gegen den Sitzungsmedian.
    harvest_dir = _build_harvest(
        tmp_path,
        plateaus=[("1.234", 4, None)] * 3 + [("1.234", 1, ["__black__"])],
    )
    dataset_root = tmp_path / "dataset"
    args = import_harvest.parse_args(
        ["--harvest", str(harvest_dir), "--profile", str(profile_path), "--dataset-root", str(dataset_root)]
    )
    rc = import_harvest.run(args)
    assert rc == 0
    result = json.loads((harvest_dir / "import.json").read_text())
    assert result["rejected_by_reason"]["bildguete"] >= 1


def test_zellen_inkonsistent_rejects_mislabeled_cell(tmp_path):
    profile_path = _profile(tmp_path)
    # Viele konsistente "1.234"-Bilder etablieren den Medoid je Zeichen;
    # ein Bild behauptet Label "1.234", zeigt in der letzten Zelle aber "5"
    # statt "4" (siehe Auftrag: Label "7"/Zelle "1"-Beispiel, hier mit den
    # tatsaechlich verwendeten Zeichen; "5" gewaehlt, weil es die
    # Bildguete-Kennzahlen der Sitzung kaum veraendert - die Abweichung soll
    # gezielt die Zellenkonsistenzpruefung treffen, nicht schon Regel 3).
    harvest_dir = _build_harvest(
        tmp_path,
        plateaus=[("1.234", 4, None)] * 3 + [("1.234", 1, ["1.235"])],
    )
    dataset_root = tmp_path / "dataset"
    args = import_harvest.parse_args(
        ["--harvest", str(harvest_dir), "--profile", str(profile_path), "--dataset-root", str(dataset_root)]
    )
    rc = import_harvest.run(args)
    assert rc == 0
    result = json.loads((harvest_dir / "import.json").read_text())
    assert result["rejected_by_reason"]["zellen_inkonsistent"] >= 1


def test_store_error_is_counted_not_swallowed(tmp_path):
    """Ein Label, das die Store-eigene `normalize_label`-Syntax nicht
    erfuellt (hier: Buchstaben statt eines reinen Dezimalwerts), wird als
    DatasetError gezaehlt statt eine Probe anzulegen - siehe Bericht dieser
    Aufgabe zur Store-Einschraenkung bei Vorzeichen/Einheit."""
    profile_path = _profile(tmp_path)
    harvest_dir = _build_harvest(tmp_path, plateaus=[("A.BCD", 4, None)] * 3)
    dataset_root = tmp_path / "dataset"
    args = import_harvest.parse_args(
        ["--harvest", str(harvest_dir), "--profile", str(profile_path), "--dataset-root", str(dataset_root)]
    )
    rc = import_harvest.run(args)
    assert rc == 0
    result = json.loads((harvest_dir / "import.json").read_text())
    assert result["imported"] == 0
    assert result["rejected_by_reason"]["store_abgelehnt"] > 0


def test_realistic_label_imported_with_numeric_expected_text_and_cell_text(tmp_path):
    """End-to-end mit einem realistischen 16-Zellen-Raster und Telegramm
    "+01.2193 mV/V" (Rohtelegramm MIT der unterdrueckten fuehrenden Null,
    siehe Modul-Docstring von import-harvest.py). `gate-label.py` haette
    daraus `label_text = "+1.2193 mV/V"` gemacht (Null entfernt) - das wird
    hier direkt vorgegeben, um den Importer isoliert zu pruefen.

    Erwartet (Orchestrator-Entscheidung zur Store-Konvention):
    `expected_text == "1.2193"` (kein '+', keine Einheit) und
    `label_origin_detail["cell_text"] == "+ 1.2193 mV/V   "` (16 Zeichen,
    Leerzelle an Position 1 fuer die unterdrueckte Null, 3 Leerzeichen
    rechts aufgefuellt)."""
    n_cells = 16
    grid = CharGrid(n_cells=n_cells, left=0.0, pitch=20.0, top=0.0, bottom=40.0)
    size = (n_cells * 20, 40)
    # Das Rohbild ist ein paar Pixel groesser als `size` und das Quad liegt
    # NICHT bis auf den letzten Pixel am Bildrand (Rand `MARGIN`) - sonst
    # tastet `rectify()`s inverse Homographie (`dst` bis `width-1`) an der
    # rechten/unteren Kante ausserhalb des Quellbilds ab und erzeugt dort
    # einen kuenstlichen dunklen Rand. Ein echtes, vom Bediener bestaetigtes
    # Quad liegt in der Praxis ohnehin nie pixelgenau auf dem Sensorrand.
    margin = 4
    raw_size = (size[0] + 2 * margin, size[1] + 2 * margin)
    quad = [
        [float(margin), float(margin)],
        [float(margin + size[0]), float(margin)],
        [float(margin + size[0]), float(margin + size[1])],
        [float(margin), float(margin + size[1])],
    ]

    profile = SessionProfile(
        schema_version=PROFILE_SCHEMA_VERSION,
        device_id="gsv2as-test-16",
        session_id="sess-16",
        quad=quad,
        target_size=size,
        grid=grid,
        scaler_crop=None,
        min_source_dot_column_px=5.0,
        native_scale=1.0,
        min_native_dot_column_px=5.0,
        resolution_threshold_px=2.0,
        resolution_ok=True,
        confirmed_by="tester",
        confirmed_at_utc="2026-09-23T12:00:00+00:00",
    )
    profile_path = tmp_path / "profile.json"
    profile.save(profile_path)

    telegram_text = "+01.2193 mV/V"  # roh, MIT unterdrueckter Null
    label_text = "+1.2193 mV/V"  # von gate-label.telegram_to_display_text()
    cell_glyphs = import_harvest._cell_text_for_telegram(telegram_text)  # "+ 1.2193 mV/V"

    harvest_dir = tmp_path / "harvest"
    frames_dir = harvest_dir / "recording" / "frames"
    frames_dir.mkdir(parents=True)
    rng = np.random.default_rng(7)

    frames_jsonl, images = [], []
    t_ns = 1_000_000_000
    # Zwei Plateaus a 3 Bilder (Standard --per-plateau=3, alle bleiben
    # erhalten) = 6 Vorkommen je Zeichen, ueber dem Mindestwert (5) fuer die
    # Zellenkonsistenzpruefung (Regel 4).
    for plateau in range(2):
        plateau_start = t_ns
        plateau_end = t_ns + 2 * 500_000_000 + 2000
        for i in range(3):
            seq = plateau * 3 + i + 1
            fname = f"frame_{seq:06d}.jpg"
            base = int(rng.integers(228, 243))
            content = _render(cell_glyphs, base=base, noise=rng, grid=grid, size=size)
            raw = np.full((raw_size[1], raw_size[0], 3), base, dtype=np.uint8)
            raw[margin : margin + size[1], margin : margin + size[0]] = content
            cv2.imwrite(str(frames_dir / fname), raw)
            frames_jsonl.append(
                {
                    "file": fname,
                    "frame_sequence": seq,
                    "capture_timestamp": {
                        "value_ns": t_ns,
                        "base": "sensor_boottime",
                        "semantics": "unknown",
                        "uncertainty_ns": None,
                    },
                }
            )
            images.append(
                {
                    "image_path": str(frames_dir / fname),
                    "telegram_text": telegram_text,
                    "label_text": label_text,
                    "label_normalization": "gsv2as_leading_zero_v1",
                    "numeric_text": "+01.2193",
                    "label_origin_detail": _detail(plateau_start, plateau_end),
                }
            )
            t_ns += 500_000_000
        t_ns += 5_000_000_000

    (harvest_dir / "recording" / "frames.jsonl").write_text(
        "\n".join(json.dumps(f) for f in frames_jsonl) + "\n", encoding="utf-8"
    )
    (harvest_dir / "proposal.json").write_text(
        json.dumps({"images": images}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    dataset_root = tmp_path / "dataset"
    args = import_harvest.parse_args(
        ["--harvest", str(harvest_dir), "--profile", str(profile_path), "--dataset-root", str(dataset_root)]
    )
    rc = import_harvest.run(args)
    assert rc == 0
    result = json.loads((harvest_dir / "import.json").read_text())
    assert result["imported"] > 0, result

    sample_id = result["sample_ids"][0]
    sample = json.loads((dataset_root / "samples" / sample_id / "sample.json").read_text())
    assert sample["expected_text"] == "1.2193"
    detail = sample["label_origin_detail"]
    assert detail["display_text"] == "+1.2193 mV/V"
    assert detail["telegram_text"] == "+01.2193 mV/V"
    assert detail["unit_text"] == "mV/V"
    assert detail["cell_text"] == "+ 1.2193 mV/V   "
