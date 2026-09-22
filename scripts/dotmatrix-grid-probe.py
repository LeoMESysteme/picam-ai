#!/usr/bin/env python3
"""Diagnose-Messung fuer OQ-Dotmatrix: laesst sich das 16-Zellen-Raster der
Displaytech-161A-Anzeige (GSV-Sensor) pro Bild zuverlaessig verankern?

Aufruf:
    ./.venv/bin/python scripts/dotmatrix-grid-probe.py

Reiner Messcode - trifft KEINE Aussage, ob der dotmatrix-Ansatz taugt. Das
entscheidet ein Mensch anhand der gedruckten Zahlen (siehe
docs/superpowers/plans/2026-09-22-dotmatrix-backend.md).

Arbeitet ausschliesslich auf den 11 Proben des GSV-Sensors
(device_id 87564e345aa047338f954c045bc9df02) unter
var/workbench/datasets/samples/*/. Schreibt nichts in `var/` und nichts in
den Produktionscode - nur eine Kontaktabzugs-PNG in ein Scratch-Verzeichnis
fuer die manuelle Sichtpruefung.

Zweite Fassung: die erste Fassung fittete `left` UND `pitch` gemeinsam ueber
denselben Score, was auf einen Pitch nahe der HALBEN wahren Zellbreite
konvergierte (16 Zellen passen dann komplett in die dichte Textregion - der
Score kennt die wahre Zellzahl nicht, nur "Mitte dunkel, Rand hell", und das
erfuellt auch ein zu enges Raster). Diese Fassung bestimmt den Pitch
unabhaengig per Autokorrelation (ein einziges, unsupervised Signal ueber die
ganze Anzeige) und sucht danach nur noch die Phase (1 freier Parameter) -
siehe `find_pitch_autocorr` und `fit_phase`.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dispread.workbench.vision import lcd_quad_in_region  # noqa: E402

DEVICE_ID = "87564e345aa047338f954c045bc9df02"
SAMPLES_ROOT = Path("var/workbench/datasets/samples")

#: Feste Warp-Zielgroesse - willkuerlich aber fest, damit Pixelwerte
#: (Pitch, Crop) zwischen Proben vergleichbar sind.
WARP_SIZE = (640, 128)  # (Breite, Hoehe)

N_CELLS = 16

#: Vorab festgelegter Crop (Praeregistrierung, siehe Auftrag): vertikal auf
#: den Zeichenkoerper, horizontal den Glasrand weg.
VERTICAL_CROP = (0.12, 0.88)  # Anteil der Warp-Hoehe
HORIZONTAL_TRIM_PX = 14  # je Seite, absolut auf 640px Warpbreite

#: Adaptive Schwelle statt globalem Otsu - der Helligkeitsgradient der
#: Anzeige macht bei Otsu das rechte Drittel zu einem soliden dunklen Blob
#: (gemessen, siehe Auftragstext). 51/15 sind vorregistrierte Werte.
ADAPTIVE_BLOCK_SIZE = 51
ADAPTIVE_C = 15

#: Pitch-Suchbereich fuer die Autokorrelation, in Pixeln auf dem beschnittenen
#: Bild (~612px breit, nahe an den 640px Warpbreite, auf die sich die
#: Referenzmessung ~35px bezieht).
PITCH_LAG_MIN = 25
PITCH_LAG_MAX = 55
#: Ein Autokorrelationspeak zaehlt nur, wenn er mindestens diesen Anteil des
#: globalen Peaks (Lag 0, die Varianzsumme) erreicht - sonst ist es Rauschen.
PITCH_PROMINENCE_FRACTION = 0.25

#: Sechs Kombinationen aus Zellaufloesung (Zeilen, Spalten) und
#: Binarisierungsschwelle - der komplette vorregistrierte Parametergrid.
CELL_SHAPES = [(7, 5), (10, 8)]  # (Zeilen, Spalten), "5x7" bzw. "8x10"
CELL_THRESHOLDS = [0.15, 0.25, 0.35]

CELL_LABELS_TEMPLATE = [
    "sign", "digit0", ".", "digit1", "digit2", "digit3", "digit4", "digit5",
    "blank", "m", "V", "/", "V2", "blank", "blank", "blank",
]


def load_gsv_samples(root: Path) -> list[dict]:
    """Alle 11 GSV-Proben laden, sample.json + Bildpfad je Eintrag."""
    samples = []
    for folder in sorted(root.iterdir()):
        sample_path = folder / "sample.json"
        if not sample_path.is_file():
            continue
        data = json.loads(sample_path.read_text())
        if data.get("device_id") != DEVICE_ID:
            continue
        image_path = folder / "image.png"
        if not image_path.is_file():
            continue
        data["_folder"] = folder
        data["_image_path"] = image_path
        samples.append(data)
    return samples


def rectify_to_warp(image: np.ndarray, bbox_px: list[float]) -> np.ndarray | None:
    """bbox (Pixel) -> normiertes hint_box -> lcd_quad_in_region -> Warp fester Groesse."""
    height, width = image.shape[:2]
    x, y, w, h = bbox_px
    hint_box = (x / width, y / height, w / width, h / height)
    quad = lcd_quad_in_region(image, hint_box)
    if quad is None:
        return None
    src = np.array([(px * width, py * height) for px, py in quad], dtype=np.float32)
    warp_w, warp_h = WARP_SIZE
    dst = np.array([[0, 0], [warp_w - 1, 0], [warp_w - 1, warp_h - 1], [0, warp_h - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(image, matrix, WARP_SIZE)


def crop_warp(warp: np.ndarray) -> np.ndarray:
    """Vertikal auf den Zeichenkoerper, horizontal den Glasrand weg (Praeregistrierung)."""
    height, width = warp.shape[:2]
    top = int(round(VERTICAL_CROP[0] * height))
    bottom = int(round(VERTICAL_CROP[1] * height))
    left = HORIZONTAL_TRIM_PX
    right = width - HORIZONTAL_TRIM_PX
    return warp[top:bottom, left:right]


def ink_image(cropped: np.ndarray) -> np.ndarray:
    """Adaptive Schwelle statt globalem Otsu (Gradient-Problem), als float
    0/1-Bild mit Tinte=1.0. `cv2.THRESH_BINARY` liefert per Definition 255 in
    HELLEN Regionen (ueber Lokalmittel-C) - Tinte ist dunkel, also invertieren."""
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
        ADAPTIVE_BLOCK_SIZE, ADAPTIVE_C,
    )
    return (binary == 0).astype(np.float32)  # Tinte (dunkel) -> 1.0


def find_pitch_autocorr(ink: np.ndarray, lag_min: int = PITCH_LAG_MIN, lag_max: int = PITCH_LAG_MAX) -> int:
    """Pitch unsupervised aus der Spalten-Tintenprofil-Autokorrelation.

    Harmonik-Falle: ein periodisches Signal mit wahrer Periode T erzeugt in
    der Autokorrelation auch bei 2T, 3T, ... Peaks (oft sogar hoehere, wenn
    sich Randeffekte konstruktiv ueberlagern). Diese Harmonik-Sorge ist
    bereits durch den Bereichsschnitt [PITCH_LAG_MIN, PITCH_LAG_MAX] entschaerft:
    der Suchbereich ist so gewaehlt, dass 2T/3T-Vielfache der plausiblen
    Zellbreite ausserhalb liegen und gar nicht erst in die Auswahl geraten.
    Innerhalb des Bereichs ist der STAERKSTE lokale Peak zu waehlen, nicht der
    kleinste Lag mit Peak ueber Schwelle - letzteres zieht die Wahl
    systematisch an den Bereichsboden, auch wenn ein deutlich staerkerer Peak
    weiter rechts liegt (gemessen an der Referenzprobe: Lag 25 mit 0.328 vs.
    das eigentliche Pitch-Signal bei Lag 36 mit 0.396).
    """
    profile = ink.mean(axis=0)
    profile = profile - profile.mean()
    n = len(profile)
    full = np.correlate(profile, profile, mode="full")
    positive_lags = full[n - 1:]  # Lag 0 .. n-1
    global_peak = positive_lags[0]
    threshold = PITCH_PROMINENCE_FRACTION * global_peak

    hi = min(lag_max, len(positive_lags) - 2)
    best_lag, best_value = None, -np.inf
    for lag in range(lag_min, hi + 1):
        if (
            positive_lags[lag] > positive_lags[lag - 1]
            and positive_lags[lag] > positive_lags[lag + 1]
            and positive_lags[lag] > threshold
        ):
            if positive_lags[lag] > best_value:
                best_lag, best_value = lag, positive_lags[lag]
    if best_lag is not None:
        return best_lag
    # Fallback ohne strikte Lokalmaximum-Bedingung: globales Maximum im Fenster.
    window = positive_lags[lag_min: hi + 1]
    return lag_min + int(np.argmax(window))


def fit_phase(ink: np.ndarray, pitch: float, n_cells: int = N_CELLS) -> tuple[float, float]:
    """Nur noch die Phase (1 freier Parameter) suchen - Pitch ist fix."""
    profile = ink.mean(axis=0)
    width = len(profile)

    def sample_at(x: float) -> float:
        xi = int(round(x))
        xi = min(max(xi, 0), width - 1)
        return profile[xi]

    best_offset, best_score = 0.0, -1e9
    for offset in np.arange(0.0, pitch, 0.5):
        centre_vals = [sample_at(offset + (i + 0.5) * pitch) for i in range(n_cells)]
        boundary_vals = [sample_at(offset + i * pitch) for i in range(n_cells + 1)]
        score = float(np.mean(centre_vals) - np.mean(boundary_vals))
        if score > best_score:
            best_score = score
            best_offset = offset
    return best_offset, best_score


def extract_cells(ink: np.ndarray, offset: float, pitch: float, shape: tuple[int, int], threshold: float,
                   n_cells: int = N_CELLS) -> list[np.ndarray]:
    """Je Zelle einen Bool-Ausschnitt liefern: Rohzelle (float 0/1) mit
    INTER_AREA auf `shape` herunterskalieren (das mittelt die Tintendichte,
    statt sie durch grobes Resampling zu verlieren) und erst danach bei
    `threshold` binarisieren."""
    width = ink.shape[1]
    rows, cols = shape
    cells = []
    for i in range(n_cells):
        x0 = int(round(offset + i * pitch))
        x1 = int(round(offset + (i + 1) * pitch))
        x0 = min(max(x0, 0), width - 1)
        x1 = min(max(x1, x0 + 1), width)
        cell = ink[:, x0:x1]
        resized = cv2.resize(cell, (cols, rows), interpolation=cv2.INTER_AREA)
        cells.append(resized > threshold)
    return cells


def labels_for_sample(expected_text: str) -> list[str]:
    """16 Zell-Labels gemaess fixem Displayformat, Ziffern aus expected_text."""
    digits = expected_text.replace(".", "")
    if len(digits) != 6:
        raise ValueError(f"expected_text {expected_text!r} liefert nicht 6 Ziffern")
    labels = list(CELL_LABELS_TEMPLATE)
    digit_iter = iter(digits)
    for idx, label in enumerate(labels):
        if label.startswith("digit"):
            labels[idx] = next(digit_iter)
    labels[12] = "V"  # V2 -> V (zweites V in "mV/V")
    return labels


def hamming(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.count_nonzero(a != b))


def mean_pairwise_hamming(vectors: list[np.ndarray]) -> float:
    if len(vectors) < 2:
        return float("nan")
    dists = [hamming(a, b) for a, b in itertools.combinations(vectors, 2)]
    return float(np.mean(dists))


def nearest_class_fraction(all_cells: list[tuple[str, np.ndarray]]) -> tuple[float, dict[str, tuple[int, int]]]:
    """Anteil Zellen, deren naechster Klassenmittelwert die EIGENE Klasse ist.
    space/empty sind hier bereits zu 'blank' zusammengefasst (CELL_LABELS_TEMPLATE)."""
    flat_by_label: dict[str, list[np.ndarray]] = defaultdict(list)
    for label, pattern in all_cells:
        flat_by_label[label].append(pattern.flatten())
    mean_by_label = {label: (np.mean(np.stack(v), axis=0) > 0.5) for label, v in flat_by_label.items()}

    correct_by_label: dict[str, int] = defaultdict(int)
    total_by_label: dict[str, int] = defaultdict(int)
    for label, pattern in all_cells:
        vector = pattern.flatten()
        best_label, best_dist = None, None
        for cand_label, mean_vec in mean_by_label.items():
            dist = hamming(vector, mean_vec)
            if best_dist is None or dist < best_dist:
                best_dist, best_label = dist, cand_label
        total_by_label[label] += 1
        if best_label == label:
            correct_by_label[label] += 1

    total_correct = sum(correct_by_label.values())
    total_all = sum(total_by_label.values())
    fraction = total_correct / total_all if total_all else float("nan")
    breakdown = {label: (correct_by_label[label], total_by_label[label]) for label in total_by_label}
    return fraction, breakdown


def build_contact_sheet(cells_by_label: dict[str, list[np.ndarray]], out_path: Path) -> None:
    """Alle extrahierten Zellbitmaps der Median-Kombination, nach Label gruppiert, als PNG."""
    rows, cols = next(iter(cells_by_label.values()))[0].shape
    scale = 8
    pad = 4
    label_w = 60
    max_instances = max(len(v) for v in cells_by_label.values())
    tile_w = cols * scale
    tile_h = rows * scale
    sheet_w = label_w + max_instances * (tile_w + pad) + pad
    sheet_h = len(cells_by_label) * (tile_h + pad) + pad
    sheet = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)
    for row_idx, label in enumerate(sorted(cells_by_label)):
        y0 = pad + row_idx * (tile_h + pad)
        cv2.putText(sheet, label, (2, y0 + tile_h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        for col_idx, pattern in enumerate(cells_by_label[label]):
            x0 = label_w + pad + col_idx * (tile_w + pad)
            tile = (~pattern * 255).astype(np.uint8)
            tile_bgr = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
            tile_big = cv2.resize(tile_bgr, (tile_w, tile_h), interpolation=cv2.INTER_NEAREST)
            sheet[y0: y0 + tile_h, x0: x0 + tile_w] = tile_big
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), sheet)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--samples", type=Path, default=SAMPLES_ROOT)
    parser.add_argument(
        "--contact-sheet",
        type=Path,
        default=Path("/home/me-systeme/.claude/jobs/fddd9a96/tmp/probe2-cells.png"),
    )
    args = parser.parse_args()

    samples = load_gsv_samples(args.samples)
    print(f"GSV-Proben geladen: {len(samples)}")
    if not samples:
        print("FEHLER: keine GSV-Proben gefunden", file=sys.stderr)
        return 1

    fit_rows = []  # (sample_id8, expected_text, pitch, offset, labels, ink)
    failures = []

    for data in samples:
        sample_id = data["id"]
        expected_text = data["expected_text"]
        image = cv2.imread(str(data["_image_path"]))
        if image is None:
            failures.append((sample_id, "Bild nicht lesbar"))
            continue
        warp = rectify_to_warp(image, data["bbox"])
        if warp is None:
            failures.append((sample_id, "lcd_quad_in_region liefert None"))
            continue
        cropped = crop_warp(warp)
        ink = ink_image(cropped)
        pitch = find_pitch_autocorr(ink)
        offset, _phase_score = fit_phase(ink, pitch)
        try:
            labels = labels_for_sample(expected_text)
        except ValueError as exc:
            failures.append((sample_id, str(exc)))
            continue
        fit_rows.append((sample_id[:8], expected_text, pitch, offset, ink.shape[1], labels, ink))

    if failures:
        print(f"\nFehlgeschlagen: {len(failures)}")
        for sample_id, reason in failures:
            print(f"  {sample_id[:8]}: {reason}")

    # --- A: Raster-Fit-Tabelle (Pitch aus Autokorrelation, Phase fix danach) --
    print("\n=== A. Raster-Fit je Probe (Autokorrelations-Pitch) ===")
    print(f"{'sample':10} {'expected':10} {'pitch_px':>9} {'offset_px':>10} {'16*pitch/crop_w':>16}")
    for sample_id, expected_text, pitch, offset, crop_w, _labels, _ink in fit_rows:
        span_frac = N_CELLS * pitch / crop_w
        print(f"{sample_id:10} {expected_text:10} {pitch:9.1f} {offset:10.1f} {span_frac:16.4f}")

    # --- B/C: sechs Parameterkombinationen -------------------------------------
    print("\n=== B. Nearest-Class-Anteil je Parameterkombination ===")
    combo_results = {}  # (shape, threshold) -> (fraction, breakdown, cells_by_label)
    for shape, threshold in itertools.product(CELL_SHAPES, CELL_THRESHOLDS):
        all_cells: list[tuple[str, np.ndarray]] = []
        cells_by_label: dict[str, list[np.ndarray]] = defaultdict(list)
        for _sid, _exp, pitch, offset, _crop_w, labels, ink in fit_rows:
            cells = extract_cells(ink, offset, pitch, shape, threshold)
            for label, pattern in zip(labels, cells, strict=True):
                all_cells.append((label, pattern))
                cells_by_label[label].append(pattern)
        fraction, breakdown = nearest_class_fraction(all_cells)
        combo_results[(shape, threshold)] = (fraction, breakdown, cells_by_label)
        rows, cols = shape
        print(f"  {cols}x{rows} @ threshold={threshold:.2f}: {fraction * 100:5.1f}%")

    # --- C: Median ---------------------------------------------------------
    fractions = [v[0] for v in combo_results.values()]
    median_fraction = float(np.median(fractions))
    print(f"\n=== C. Median ueber alle sechs Kombinationen: {median_fraction * 100:.1f}% ===")

    # Median-Kombination: die mit dem zur Median-Statistik naechstgelegenen
    # Wert (bei 6 Werten liegt der Median i.A. zwischen zwei Rangwerten -
    # naechstgelegen macht D trotzdem an EINER konkreten Kombination fest).
    median_combo = min(combo_results, key=lambda k: abs(combo_results[k][0] - median_fraction))
    median_fraction_exact, median_breakdown, median_cells_by_label = combo_results[median_combo]
    shape, threshold = median_combo
    rows, cols = shape
    print(f"Median-Kombination: {cols}x{rows} @ threshold={threshold:.2f} (Anteil={median_fraction_exact * 100:.1f}%)")

    # --- D: Aufschluesselung der Median-Kombination -------------------------
    print("\n=== D. Median-Kombination: Aufschluesselung je Label ===")
    for label in sorted(median_breakdown):
        c, t = median_breakdown[label]
        print(f"  {label:8} n={t:3}  correct={c:3}  {100 * c / t:5.1f}%")

    flat_by_label = {label: [p.flatten() for p in patterns] for label, patterns in median_cells_by_label.items()}
    within_scores = {label: mean_pairwise_hamming(v) for label, v in flat_by_label.items() if len(v) >= 2}
    overall_within = float(np.mean(list(within_scores.values()))) if within_scores else float("nan")

    between_dists = []
    labels_sorted = sorted(flat_by_label)
    for i, label_a in enumerate(labels_sorted):
        for label_b in labels_sorted[i + 1:]:
            for va in flat_by_label[label_a]:
                for vb in flat_by_label[label_b]:
                    between_dists.append(hamming(va, vb))
    overall_between = float(np.mean(between_dists)) if between_dists else float("nan")
    ratio = overall_between / overall_within if overall_within else float("nan")
    print(f"\nwithin-class Mittel:  {overall_within:.3f}")
    print(f"between-class Mittel: {overall_between:.3f}")
    print(f"Verhaeltnis between/within: {ratio:.3f}")

    # --- Kontaktabzug (Median-Kombination) -----------------------------------
    build_contact_sheet(median_cells_by_label, args.contact_sheet)
    print(f"\nKontaktabzug (Median-Kombination) geschrieben nach: {args.contact_sheet}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
