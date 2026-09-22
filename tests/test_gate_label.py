"""`scripts/gate-label.py` (Task F aus
docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md).

Test-first: jeder Test hier muss scheitern, bevor `scripts/gate-label.py`
existiert/die Logik implementiert ist. Das Skript wertet eine Aufzeichnung
von `sync-record.py` OFFLINE aus - es oeffnet keine Bilddateien (die Gate-
Entscheidung braucht nur Zeitstempel), deshalb existieren die Bilddateien in
diesen Tests absichtlich NICHT.

Muster fuer den CLI-als-Subprozess-Teil aus `tests/test_dataset_benchmark.py`
und `tests/test_sync_record.py`.

Zeitbasis: `serial.jsonl`-Zeilen tragen `t_boot` in Sekunden (float,
CLOCK_BOOTTIME, wie von `sync-record.py` geschrieben); `frames.jsonl`-Zeilen
tragen `capture_timestamp.value_ns` in Nanosekunden derselben Domaene
(`Timestamp.to_dict()`). Diese Tests schreiben `capture_timestamp.value_ns`
direkt in Nanosekunden, um exakte Randfaelle bauen zu koennen.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "gate-label.py"

MS = 1_000_000  # Nanosekunden je Millisekunde


def _write_recording(
    tmp_path: Path,
    *,
    telegrams: list[tuple[int, str]],
    frames: list[tuple[str, int]],
    port: str = "/dev/ttyUSB0",
) -> Path:
    """Baut ein synthetisches Aufzeichnungsverzeichnis wie `sync-record.py`
    es hinterlaesst - ohne die Bilddateien selbst.

    `telegrams`: Liste (t_ns, text). `frames`: Liste (dateiname,
    capture_timestamp_ns).
    """
    recording = tmp_path / "lauf"
    recording.mkdir()
    with open(recording / "serial.jsonl", "w", encoding="utf-8") as f:
        for t_ns, text in telegrams:
            f.write(json.dumps({"t_boot": t_ns / 1e9, "text": text}) + "\n")
    with open(recording / "frames.jsonl", "w", encoding="utf-8") as f:
        for seq, (filename, t_ns) in enumerate(frames, start=1):
            entry = {
                "file": filename,
                "frame_sequence": seq,
                "capture_timestamp": {
                    "value_ns": t_ns,
                    "base": "sensor_boottime",
                    "semantics": "unknown",
                    "uncertainty_ns": None,
                },
            }
            f.write(json.dumps(entry) + "\n")
    (recording / "session.json").write_text(json.dumps({"port": port}))
    return recording


def _run_cli(recording: Path, output: Path, *, guard_margin_ms: float, max_gap_ms: float):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--recording",
            str(recording),
            "--guard-margin-ms",
            str(guard_margin_ms),
            "--max-gap-ms",
            str(max_gap_ms),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _labeled_by_file(proposal: dict) -> dict:
    return {entry["image_path"]: entry for entry in proposal["images"]}


def _image_path(recording: Path, filename: str) -> str:
    return str(recording / "frames" / filename)


# --- Test 1: Bild mitten in einem langen ruhigen Lauf ----------------------


def test_bild_mitten_im_ruhigen_lauf_wird_gelabelt(tmp_path):
    telegrams = [(i * 500 * MS, "+0.46776 mV/V") for i in range(20)]
    t_mid = telegrams[10][0]
    frames = [("frame_000001.png", t_mid)]
    recording = _write_recording(tmp_path, telegrams=telegrams, frames=frames)
    output = tmp_path / "proposal.json"

    result = _run_cli(recording, output, guard_margin_ms=100, max_gap_ms=1000)
    assert result.returncode == 0, result.stderr

    proposal = json.loads(output.read_text())
    by_file = _labeled_by_file(proposal)
    key = _image_path(recording, "frame_000001.png")
    assert key in by_file
    assert by_file[key]["telegram_text"] == "+0.46776 mV/V"
    assert by_file[key]["numeric_text"] == "+0.46776"


# --- Test 2: Falsifikationstest - Wertwechsel mitten im +-M-Fenster --------


def test_bild_im_wechselfenster_wird_abgelehnt(tmp_path):
    guard_margin_ms = 100
    t0 = 0
    t1 = 500 * MS  # naechstes, ABWEICHENDES Telegramm
    telegrams = [(t0, "+0.46776 mV/V"), (t1, "+0.50000 mV/V")]
    # Genau in der Mitte des Wechselfensters [t1 - M, t1 + M] um den Wechsel,
    # klar innerhalb des ausgeschlossenen Randbereichs um t1.
    t_change = t1  # exakt am Telegrammwechsel selbst
    frames = [("frame_000001.png", t_change)]
    recording = _write_recording(tmp_path, telegrams=telegrams, frames=frames)
    output = tmp_path / "proposal.json"

    result = _run_cli(recording, output, guard_margin_ms=guard_margin_ms, max_gap_ms=1000)
    assert result.returncode == 0, result.stderr

    proposal = json.loads(output.read_text())
    by_file = _labeled_by_file(proposal)
    key = _image_path(recording, "frame_000001.png")
    assert key not in by_file
    assert "Wertwechsel im Fenster: 1" in result.stdout


# --- Test 3/4: vor dem ersten bzw. nach dem letzten Telegramm --------------


def test_bild_vor_erstem_telegramm_wird_abgelehnt(tmp_path):
    telegrams = [(1000 * MS, "+0.46776 mV/V"), (1500 * MS, "+0.46776 mV/V")]
    frames = [("frame_000001.png", 500 * MS)]
    recording = _write_recording(tmp_path, telegrams=telegrams, frames=frames)
    output = tmp_path / "proposal.json"

    result = _run_cli(recording, output, guard_margin_ms=50, max_gap_ms=1000)
    assert result.returncode == 0, result.stderr

    proposal = json.loads(output.read_text())
    by_file = _labeled_by_file(proposal)
    key = _image_path(recording, "frame_000001.png")
    assert key not in by_file
    assert "erstem" in result.stdout or "letztem" in result.stdout


def test_bild_nach_letztem_telegramm_wird_abgelehnt(tmp_path):
    telegrams = [(1000 * MS, "+0.46776 mV/V"), (1500 * MS, "+0.46776 mV/V")]
    frames = [("frame_000001.png", 2000 * MS)]
    recording = _write_recording(tmp_path, telegrams=telegrams, frames=frames)
    output = tmp_path / "proposal.json"

    result = _run_cli(recording, output, guard_margin_ms=50, max_gap_ms=1000)
    assert result.returncode == 0, result.stderr

    proposal = json.loads(output.read_text())
    by_file = _labeled_by_file(proposal)
    key = _image_path(recording, "frame_000001.png")
    assert key not in by_file


# --- Test 5: Telegrammluecke - Teilung des Laufs ----------------------------


def test_luecke_im_lauf_teilt_ihn_bild_in_luecke_abgelehnt_sicherer_teil_gelabelt(tmp_path):
    guard_margin_ms = 50
    max_gap_ms = 800
    # Ein Lauf gleicher Zeichenkette ueber t=0..3000ms, aber mit einer
    # kuenstlichen Luecke von 0ms bis 2000ms (2000ms > max_gap_ms=800ms).
    telegrams = [
        (0, "+0.46776 mV/V"),
        (500 * MS, "+0.46776 mV/V"),
        (2000 * MS, "+0.46776 mV/V"),
        (2500 * MS, "+0.46776 mV/V"),
        # naechstes ABWEICHENDES Telegramm beendet den zweiten Teillauf
        (3000 * MS, "+0.50000 mV/V"),
    ]
    # In der Luecke (zwischen 500ms+M und 2000ms-M) -> abgelehnt (Luecke).
    t_in_gap = 1250 * MS
    # Im sicheren Teil VOR der Luecke (zwischen 0+M und 500ms-M) -> gelabelt.
    t_safe_before_gap = 250 * MS
    # Im sicheren Teil NACH der Luecke (zwischen 2000ms+M und 3000ms-M) -> gelabelt.
    t_safe_after_gap = 2250 * MS
    frames = [
        ("frame_gap.png", t_in_gap),
        ("frame_before.png", t_safe_before_gap),
        ("frame_after.png", t_safe_after_gap),
    ]
    recording = _write_recording(tmp_path, telegrams=telegrams, frames=frames)
    output = tmp_path / "proposal.json"

    result = _run_cli(recording, output, guard_margin_ms=guard_margin_ms, max_gap_ms=max_gap_ms)
    assert result.returncode == 0, result.stderr

    proposal = json.loads(output.read_text())
    by_file = _labeled_by_file(proposal)
    assert _image_path(recording, "frame_gap.png") not in by_file
    assert _image_path(recording, "frame_before.png") in by_file
    assert _image_path(recording, "frame_after.png") in by_file
    assert "Telegrammluecke: 1" in result.stdout


# --- Test 6: Randfall Fenstergrenze -----------------------------------------


def test_fenstergrenze_untere_geschlossen_obere_offen(tmp_path):
    guard_margin_ms = 100
    t0 = 0
    t1 = 1000 * MS
    telegrams = [(t0, "+0.46776 mV/V"), (t1, "+0.50000 mV/V")]
    lo = t0 + guard_margin_ms * MS  # t_i + M, MUSS gelabelt werden (geschlossen)
    hi = t1 - guard_margin_ms * MS  # t_{j+1} - M, MUSS abgelehnt werden (offen)
    frames = [("frame_lo.png", lo), ("frame_hi.png", hi)]
    recording = _write_recording(tmp_path, telegrams=telegrams, frames=frames)
    output = tmp_path / "proposal.json"

    result = _run_cli(recording, output, guard_margin_ms=guard_margin_ms, max_gap_ms=5000)
    assert result.returncode == 0, result.stderr

    proposal = json.loads(output.read_text())
    by_file = _labeled_by_file(proposal)
    assert _image_path(recording, "frame_lo.png") in by_file
    assert _image_path(recording, "frame_hi.png") not in by_file


# --- Test 7: groesseres Szenario, Anzahl von Hand gerechnet -----------------


def test_groesseres_szenario_erwartete_anzahl_von_hand_gerechnet(tmp_path):
    """Aufbau (alle Zeiten in ms, M=50, max_gap=300):

    Lauf 1 "A": Telegramme bei 0, 200, 400, 600, 800  (Abstand 200 <= 300,
        kein Split). Naechstes abweichendes Telegramm: bei 1000 ("B").
        Fenster: [0+50, 1000-50) = [50, 950).
    Lauf 2 "B": Telegramme bei 1000, 1200 (Abstand 200, kein Split). Danach
        eine Luecke: naechstes Telegramm bei 1900 (Abstand 700 > 300 ->
        Split). Teillauf 2a "B" (1000..1200): kein Folgetelegramm im selben
        Lauf mehr, also Tag "gap": Fenster [1000+50, 1200-50) = [1050, 1150).
        Teillauf 2b "B" (1900): letzter Teillauf von Lauf 2, und Lauf 2 hat
        ein nachfolgend ABWEICHENDES Telegramm bei 2200 ("C") -> Fenster
        [1900+50, 2200-50) = [1950, 2150).
    Lauf 3 "C": ein einziges Telegramm bei 2200, KEIN Folgetelegramm mehr
        (letzter Lauf des Stroms) -> Fall 3, Fenster [2200+50, 2200-50) =
        [2250, 2150) -> LEER (hi < lo), also niemals labelbar.

    Elf Bilder, eines je markantem Zeitpunkt:
      1. t=100   -> in [50,950)         -> "A" GELABELT
      2. t=500   -> in [50,950)         -> "A" GELABELT
      3. t=949   -> in [50,950)         -> "A" GELABELT
      4. t=950   -> Grenze, offen       -> ABGELEHNT (Wertwechsel)
      5. t=1000  -> vor [1050,1150), aber im Randbereich, der aus dem
                     Wertwechsel A->B stammt (derselbe Randbereich wie
                     Punkt 4, das vorangehende Fenster ist A) -> ABGELEHNT
                     (Wertwechsel)
      6. t=1100  -> in [1050,1150)      -> "B" GELABELT
      7. t=1150  -> Grenze, offen (2a)  -> ABGELEHNT (Luecke)
      8. t=1500  -> in der Luecke       -> ABGELEHNT (Luecke)
      9. t=2000  -> in [1950,2150)      -> "B" GELABELT
      10. t=2150 -> Grenze, offen (2b)  -> ABGELEHNT (Wertwechsel, da 2b endet
          mit Folgetelegramm C)
      11. t=2300 -> nach Lauf 3, dessen Fenster leer ist, aber t<=t_max(2200)?
          NEIN, 2300 > 2200 (letztes Telegramm ueberhaupt) -> ABGELEHNT
          (vor erstem/nach letztem Telegramm)

    Erwartete Anzahl gelabelter Bilder: 5 (Punkte 1, 2, 3, 6, 9).
    Erwartete Anzahl verschiedener Zeichenketten unter den gelabelten
    Bildern: 2 ("A", "B"; "C" ist nie labelbar).
    """
    guard_margin_ms = 50
    max_gap_ms = 300
    telegrams = [
        (0, "A"),
        (200 * MS, "A"),
        (400 * MS, "A"),
        (600 * MS, "A"),
        (800 * MS, "A"),
        (1000 * MS, "B"),
        (1200 * MS, "B"),
        (1900 * MS, "B"),
        (2200 * MS, "C"),
    ]
    frame_times = [100, 500, 949, 950, 1000, 1100, 1150, 1500, 2000, 2150, 2300]
    frames = [(f"frame_{i:02d}.png", t * MS) for i, t in enumerate(frame_times)]
    recording = _write_recording(tmp_path, telegrams=telegrams, frames=frames)
    output = tmp_path / "proposal.json"

    result = _run_cli(recording, output, guard_margin_ms=guard_margin_ms, max_gap_ms=max_gap_ms)
    assert result.returncode == 0, result.stderr

    proposal = json.loads(output.read_text())
    assert len(proposal["images"]) == 5
    strings = {entry["telegram_text"] for entry in proposal["images"]}
    assert strings == {"A", "B"}

    by_file = _labeled_by_file(proposal)
    expected_labeled = {"frame_00.png": "A", "frame_01.png": "A", "frame_02.png": "A",
                         "frame_05.png": "B", "frame_08.png": "B"}
    for filename, text in expected_labeled.items():
        key = _image_path(recording, filename)
        assert key in by_file, f"{filename} sollte gelabelt sein"
        assert by_file[key]["telegram_text"] == text

    expected_rejected = ["frame_03.png", "frame_04.png", "frame_06.png",
                          "frame_07.png", "frame_09.png", "frame_10.png"]
    for filename in expected_rejected:
        key = _image_path(recording, filename)
        assert key not in by_file, f"{filename} sollte ABGELEHNT sein"


# --- Luecke GENAU an einem Wertwechsel - der gefaehrlichste Fall ----------


def test_luecke_zwischen_zwei_verschiedenen_laeufen_wird_als_luecke_nicht_als_wertwechsel_behandelt(tmp_path):
    """Faellt ein Telegramm genau an einem Wertwechsel aus, sieht der Strom
    wie ein normaler A->B-Wechsel aus, obwohl dazwischen ein anderer, nie
    angekommener Wert gestanden haben kann. Der Abstand zwischen dem letzten
    A- und dem ersten B-Telegramm MUSS also ebenfalls gegen --max-gap-ms
    geprueft werden, nicht nur Abstaende INNERHALB eines Laufs."""
    guard_margin_ms = 50
    max_gap_ms = 300
    telegrams = [
        (0, "A"),
        (200 * MS, "A"),
        # Luecke von 1200ms > max_gap_ms=300ms genau zwischen A und B.
        (1400 * MS, "B"),
        (1600 * MS, "B"),
    ]
    # Mitten in der Luecke zwischen dem letzten A- und dem ersten B-Telegramm.
    t_in_gap = 800 * MS
    frames = [("frame_gap.png", t_in_gap)]
    recording = _write_recording(tmp_path, telegrams=telegrams, frames=frames)
    output = tmp_path / "proposal.json"

    result = _run_cli(recording, output, guard_margin_ms=guard_margin_ms, max_gap_ms=max_gap_ms)
    assert result.returncode == 0, result.stderr

    proposal = json.loads(output.read_text())
    by_file = _labeled_by_file(proposal)
    key = _image_path(recording, "frame_gap.png")
    assert key not in by_file, "ueber die Luecke hinweg darf NICHT als 'A' gelabelt werden"
    assert "Telegrammluecke: 1" in result.stdout
    assert "Wertwechsel im Fenster: 0" in result.stdout


# --- label_origin_detail traegt genau die von DatasetStore verlangten Felder


def test_label_origin_detail_traegt_die_pflichtfelder_von_datasetstore(tmp_path):
    telegrams = [(i * 500 * MS, "+0.46776 mV/V") for i in range(5)]
    t_mid = telegrams[2][0]
    frames = [("frame_000001.png", t_mid)]
    recording = _write_recording(tmp_path, telegrams=telegrams, frames=frames, port="/dev/ttyUSB3")
    output = tmp_path / "proposal.json"

    result = _run_cli(recording, output, guard_margin_ms=75, max_gap_ms=1000)
    assert result.returncode == 0, result.stderr

    proposal = json.loads(output.read_text())
    detail = proposal["images"][0]["label_origin_detail"]
    assert detail["source_port"] == "/dev/ttyUSB3"
    assert detail["guard_margin_ms"] == 75
    assert isinstance(detail["plateau_start_ns"], int)
    assert isinstance(detail["plateau_end_ns"], int)
    assert isinstance(detail["telegram_count"], int)
    assert detail["telegram_count"] == 5
