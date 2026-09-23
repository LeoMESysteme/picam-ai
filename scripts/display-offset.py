#!/usr/bin/env python3
"""Ende-zu-Ende-Versatz zwischen Telegramm und Anzeige, photometrisch.

Zweite Fassung (Task B in
docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md). Kein OCR:
gemessen wird nur, WANN sich das Glas aendert, nicht WAS dort steht.

GESCHICHTE DER ERSTEN FASSUNG - warum diese Fassung anders misst: Die erste
Fassung mass die mittlere Bild-zu-Bild-Differenz ueber den GANZEN
Anzeigeausschnitt und mittelte das ueber alle Ereignisse (Ensemble-Mittelung
mit Bootstrap-sigma). Auf allen vier echten Aufzeichnungen kam dabei "kein
Ausschlag ueber der Nullbaseline" heraus - das wurde zunaechst als Befund
berichtet. Eine Gegenpruefung an einem konkreten Ereignis in
`offset-norm-101440` (Schritt "schedule[3] factor=3.0") zeigte aber: die
Anzeige wechselt dort sichtbar UND schnell (innerhalb von ein bis zwei
Bildern je Kommando), aber die mittlere Differenz ueber den GESAMTEN
Ausschnitt bleibt winzig (Maximum 4.9 gegen einen Median von 0.66 ueber die
ganze Aufzeichnung) - weil nur ein kleiner Bruchteil der Pixel im Ausschnitt
(die geaenderten Ziffern) sich aendert und der Rest (Hintergrund, unveraen-
derte Ziffern, Einheit) das Signal verduennt. Das war also KEIN Befund
("kein Versatz messbar"), sondern ein Methodenfehler: die Mittelung ueber
alle Pixel loescht ein raeumlich konzentriertes Signal weg.

DIESE FASSUNG: Vorlagen-Projektion (template projection) statt globaler
Differenz. Fuer einen Uebergang A -> B:

1. Vorlage A = Mittelwert mehrerer Bilder tief im Plateau VOR dem
   Ereignis, Vorlage B = Mittelwert mehrerer Bilder tief im Plateau DANACH.
2. Jedes Bild f wird auf die Verbindungslinie A->B projiziert:

       p(f) = <f - A, B - A> / |B - A|^2

   p geht (rauschfrei) von 0 (reines A) nach 1 (reines B) - und zwar nur
   entlang der Pixel, die sich zwischen A und B tatsaechlich unterscheiden;
   unveraenderte Pixel tragen zu B-A nichts bei und verduennen das Signal
   nicht mehr.
3. Durchgangszeiten bei p=0.1 (Einstieg), p=0.5 (Mitte) und p=0.9 (Ende)
   liefern d_misch = t(0.9) - t(0.1) und delta = t(0.5) - t_telegramm.
4. Da t_telegramm nicht der wahre Uebergangszeitpunkt ist, werden die
   "tief im Plateau"-Fenster fuer A/B EINMAL nachjustiert: nach der ersten
   Schaetzung von delta wird die Grenze zwischen "noch A" und "schon B" auf
   den geschaetzten wahren Uebergang verschoben (mit Sicherheitsabstand
   `guard_s`), und Vorlagen + Projektion neu berechnet.
5. Ein Ereignis zaehlt nur als "measurable", wenn |B-A| deutlich ueber dem
   photometrischen Rauschen liegt (siehe `analyze_event_template`) UND ein
   Durchgang durch p=0.5 gefunden wurde. Sonst: nicht geraten, sondern als
   unmessbar ausgewiesen.

Populations-Kennzahlen (delta, sigma_delta, d_misch) sind jetzt direkt aus
den EINZELNEN Ereignis-Deltas gebildet (Mittelwert bzw. Streuung ueber die
qualifizierenden Ereignisse) - kein Bootstrap mehr noetig, weil jedes
Ereignis schon eine eigene delta-Schaetzung liefert (das war vorher nicht
der Fall: die alte Ensemble-Kurve war EIN gemitteltes Signal ueber alle
Ereignisse, kein Einzelereignis-delta).

Nullbaseline: dieselbe Projektionsmethode auf zufaellige Splitpunkte
INNERHALB langer, unveraenderter Telegramm-Plateaus angewandt (kein echter
Uebergang). Berichtet werden Durchfallquote (wie oft faellt der
|B-A|-Rauschtest zu Recht durch) und, falls doch "gemessen", die Streuung
der erfundenen Uebergangszeiten.

Zeitbasis: `frames.jsonl` traegt `capture_timestamp.value_ns` (int,
CLOCK_BOOTTIME, `sensor_boottime`), `serial.jsonl` traegt `t_boot` (float,
Sekunden, CLOCK_BOOTTIME) - dieselbe Domaene, siehe AGENTS.md "Zeitangaben
immer mit Zeitbasis".

Vorzeichenkonvention (unveraendert):

    delta = t_glas - t_telegramm

    delta > 0  -> das Telegramm kommt ZUERST an, das Glas folgt.
    delta < 0  -> das Glas zeigt den neuen Wert, BEVOR das Telegramm ankommt.

M wird **nur** aus einer als `detected` markierten Population nach der in
Festlegung 3 des Plans festgeschriebenen Formel gebildet - unveraendert:

    M = |delta| + d_misch + 3*sigma_delta + 40 ms
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2  # noqa: E402

from dispread.rectify import rectify  # noqa: E402
from dispread.workbench.vision import lcd_quad_in_region  # noqa: E402

CROP_SIZE = (400, 160)  # wie src/dispread/workbench/controller.py:CROP_SIZE
DEFAULT_HALF_WINDOW_S = 0.6
DEFAULT_MIN_TEMPLATE_FRAMES = 3
DEFAULT_MARGIN_START = 0.30
DEFAULT_NOISE_K = 3.0
DEFAULT_GUARD_S = 0.05
DEFAULT_N_ITERATIONS = 2
DEFAULT_MIN_QUALIFYING = 3
DEFAULT_NULL_PER_RUN = 3
DEFAULT_NULL_MAX_TOTAL = 60
#: Festlegung 3, docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md -
#: NICHT veraendern.
M_FIXED_EXTRA_S = 0.040


# ---------------------------------------------------------------------------
# Laden
# ---------------------------------------------------------------------------


def load_frames(session_dir: Path) -> list[dict[str, Any]]:
    """`frames.jsonl` laden. `capture_timestamp.value_ns` ist Nanosekunden
    (int), hier nach Sekunden (float) umgerechnet - CLOCK_BOOTTIME bleibt."""
    rows = []
    path = session_dir / "frames.jsonl"
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            ts = obj["capture_timestamp"]
            # `frames.jsonl` traegt nur den Dateinamen, das Bild liegt unter
            # <session_dir>/frames/ (sync-record.py: frames_dir = output_dir
            # / "frames"). Der gespeicherte Pfad ist relativ zu session_dir.
            rows.append(
                {
                    "file": f"frames/{obj['file']}",
                    "frame_sequence": obj.get("frame_sequence"),
                    "t": ts["value_ns"] / 1e9,
                    "timestamp_base": ts.get("base"),
                }
            )
    rows.sort(key=lambda r: r["t"])
    return rows


def load_serial(session_dir: Path) -> list[dict[str, Any]]:
    """`serial.jsonl` laden. `t_boot` ist bereits Sekunden (float),
    CLOCK_BOOTTIME - dieselbe Domaene wie `capture_timestamp`.

    Zukuenftige Aufzeichnungen koennen nicht-Telegramm-Zeilen mitschreiben.
    Eine Zeile gilt nur dann als Telegramm, wenn sie nicht explizit anders
    markiert ist."""
    rows = []
    path = session_dir / "serial.jsonl"
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            is_telegram = True
            if obj.get("is_command") is True or obj.get("non_telegram") is True:
                is_telegram = False
            kind = obj.get("kind") or obj.get("tag") or obj.get("type")
            if kind is not None and str(kind).lower() not in ("telegram", "value", "reading"):
                is_telegram = False
            rows.append({"t_boot": float(obj["t_boot"]), "text": obj["text"], "is_telegram": is_telegram})
    rows.sort(key=lambda r: r["t_boot"])
    return rows


def load_commands(session_dir: Path) -> list[dict[str, Any]]:
    """`commands.jsonl` laden, falls vorhanden (Norm-/Dpoint-Schreibzyklen,
    Task B)."""
    path = session_dir / "commands.jsonl"
    if not path.exists():
        return []
    rows = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Telegrammlaeufe (Plateaus) und Wechselereignisse
# ---------------------------------------------------------------------------


def build_runs(serial_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Telegrammzeilen zu Plateaus gleicher Zeichenkette zusammenfassen.
    Nicht-Telegramm-Zeilen werden uebersprungen."""
    runs: list[dict[str, Any]] = []
    for row in serial_rows:
        if not row["is_telegram"]:
            continue
        text = row["text"]
        if runs and runs[-1]["text"] == text:
            runs[-1]["t_end"] = row["t_boot"]
            runs[-1]["n_telegrams"] += 1
        else:
            runs.append({"text": text, "t_start": row["t_boot"], "t_end": row["t_boot"], "n_telegrams": 1})
    return runs


def classify_events(serial_rows: list[dict[str, Any]], session_end_t: float | None = None) -> list[dict[str, Any]]:
    """Wechselereignisse zwischen aufeinanderfolgenden Telegramm-Plateaus.

    "small" (genau eine abweichende Zeichenposition, z.B. Ruhezustand-
    Zappeln der letzten Nachkommastelle) vs. "large" (mehrere Positionen,
    z.B. Normierungswechsel oder ein von Hand gefahrener Stimulator).

    `isolated`: True, wenn das VORHERIGE Plateau mindestens zwei Telegramme
    trug (also mindestens ein ruhiges Intervall vor dem Wechsel lag) - eine
    Rampe (jedes Telegramm weicht vom vorigen ab) hat kein ruhiges
    Vorher-Fenster und wird per Default nicht zur delta-Schaetzung
    herangezogen (siehe `run()`).

    `run_a`/`run_b`: Zeitintervalle der Plateaus VOR und NACH dem Wechsel,
    fuer die Vorlagen-Projektion in `analyze_event_template`. `run_b`
    reicht bis zum naechsten Plateau-Wechsel bzw. bis `session_end_t`,
    wenn es das letzte Plateau ist - der Anzeigewert gilt schliesslich bis
    zum naechsten Telegrammwechsel, nicht nur bis zum letzten SAMPLE
    desselben Werts."""
    runs = build_runs(serial_rows)
    events = []
    for i in range(1, len(runs)):
        a, b = runs[i - 1], runs[i]
        n_diff = sum(1 for x, y in zip(a["text"], b["text"], strict=False) if x != y)
        n_diff += abs(len(a["text"]) - len(b["text"]))
        group = "small" if n_diff <= 1 else "large"
        run_b_end = runs[i + 1]["t_start"] if i + 1 < len(runs) else (session_end_t if session_end_t is not None else b["t_end"])
        events.append(
            {
                "t": b["t_start"],
                "text": b["text"],
                "prev_text": a["text"],
                "n_diff": n_diff,
                "group": group,
                "isolated": a["n_telegrams"] >= 2,
                "pre_run_length": a["n_telegrams"],
                "run_a": (a["t_start"], b["t_start"]),
                "run_b": (b["t_start"], run_b_end),
            }
        )
    return events


# ---------------------------------------------------------------------------
# Anzeigebereich lokalisieren (einmal je Sitzung, per Stichprobe verifiziert)
# ---------------------------------------------------------------------------


def locate_quad(
    session_dir: Path,
    frames: list[dict[str, Any]],
    hint_box: tuple[float, float, float, float],
    *,
    sample_frames: int = 5,
    saturation_threshold: int = 60,
    min_area_fraction: float = 0.25,
    stability_tol: float = 0.01,
) -> dict[str, Any]:
    """Quad auf einer Stichprobe von Bildern bestimmen. Kamera und Anzeige
    stehen in einer Aufzeichnungssitzung fest zueinander (Laboraufbau) -
    eine Verschiebung des Quads von Bild zu Bild waere ein Zeichen fuer
    Wackelkontakt, nicht fuer normalen Betrieb, und wird nicht still
    uebernommen: ist das Quad ueber die Stichprobe nicht stabil, bricht
    `run()` ab statt zu raten."""
    if not frames:
        raise ValueError("keine Bilder zum Lokalisieren des Anzeigebereichs")
    n = min(sample_frames, len(frames))
    indices = sorted(set(int(round(i)) for i in np.linspace(0, len(frames) - 1, n)))
    quads = []
    used_files = []
    for idx in indices:
        img = cv2.imread(str(session_dir / frames[idx]["file"]))
        if img is None:
            continue
        q = lcd_quad_in_region(
            img, hint_box, saturation_threshold=saturation_threshold, min_area_fraction=min_area_fraction
        )
        if q is not None:
            quads.append(q)
            used_files.append(frames[idx]["file"])
    if not quads:
        raise RuntimeError(
            "lcd_quad_in_region fand in keinem Stichprobenbild ein Quad - "
            "hint_box pruefen (kein geratenes Quad wird uebernommen)."
        )
    arr = np.array(quads, dtype=np.float64)
    spread = float(np.abs(arr - arr[0]).max())
    stable = spread < stability_tol
    quad_norm = tuple(tuple(pt) for pt in arr.mean(axis=0))
    return {
        "quad_norm": quad_norm,
        "stable": stable,
        "spread_norm": spread,
        "n_samples": len(quads),
        "sample_files": used_files,
    }


def quad_to_pixels(quad_norm, width: int, height: int) -> tuple[tuple[float, float], ...]:
    return tuple((float(x * width), float(y * height)) for x, y in quad_norm)


# ---------------------------------------------------------------------------
# Einzelbild lesen + entzerren, mit Cache
# ---------------------------------------------------------------------------


def _rectified_gray(session_dir: Path, file: str, quad_px, target_size=CROP_SIZE) -> np.ndarray | None:
    img = cv2.imread(str(session_dir / file))
    if img is None:
        return None
    crop = rectify(img, quad_px, target_size=target_size)
    gray = crop.image if crop.image.ndim == 2 else cv2.cvtColor(crop.image, cv2.COLOR_BGR2GRAY)
    return gray.astype(np.float32)


def _cached_gray(cache: dict, frames, session_dir: Path, quad_px, target_size, idx: int) -> np.ndarray | None:
    if idx not in cache:
        cache[idx] = _rectified_gray(session_dir, frames[idx]["file"], quad_px, target_size)
    return cache[idx]


# ---------------------------------------------------------------------------
# Verdeckungserkennung (photometrischer Ausreisser ohne Telegrammereignis)
# ---------------------------------------------------------------------------


def compute_crop_means(frames, session_dir: Path, quad_px, *, target_size=CROP_SIZE) -> np.ndarray:
    means = np.full(len(frames), np.nan, dtype=np.float64)
    for i, row in enumerate(frames):
        gray = _rectified_gray(session_dir, row["file"], quad_px, target_size)
        if gray is not None:
            means[i] = float(gray.mean())
    return means


def detect_occlusion_mask(means: np.ndarray, *, mad_k: float = 8.0) -> np.ndarray:
    """Bilder markieren, deren Anzeigebereich-Helligkeit ein Ausreisser zur
    restlichen Sitzung ist - typischerweise eine kurz vor die Kamera
    gehaltene Hand. Robuste Schwelle ueber den Median-Abstand (MAD); faellt
    MAD auf ~0 zurueck auf die Standardabweichung (rauschfreie synthetische
    Testdaten)."""
    mask = np.zeros(len(means), dtype=bool)
    finite = means[np.isfinite(means)]
    if finite.size < 8:
        mask[~np.isfinite(means)] = True
        return mask
    med = float(np.median(finite))
    mad = float(np.median(np.abs(finite - med)))
    robust_sigma = 1.4826 * mad if mad > 1e-9 else (float(np.std(finite)) or 1e-9)
    for i, m in enumerate(means):
        if not np.isfinite(m) or abs(m - med) > mad_k * robust_sigma:
            mask[i] = True
    return mask


# ---------------------------------------------------------------------------
# Vorlagen-Projektion - der Kern dieser Fassung
# ---------------------------------------------------------------------------


def deep_indices(
    frame_times: np.ndarray,
    lo: float,
    hi: float,
    min_frames: int,
    margin_start: float,
    excluded_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Bildindizes "tief im Plateau" [lo, hi): startet mit den mittleren
    `1 - 2*margin_start` des Intervalls und weitet bei Bedarf schrittweise
    bis zum ganzen Intervall, damit mindestens `min_frames` Bilder
    uebrigbleiben."""
    lo_i = int(np.searchsorted(frame_times, lo, side="left"))
    hi_i = int(np.searchsorted(frame_times, hi, side="left"))
    idxs = np.arange(lo_i, hi_i)
    if excluded_mask is not None and idxs.size:
        idxs = idxs[~excluded_mask[idxs]]
    if idxs.size == 0:
        return idxs
    span = hi - lo
    frac = margin_start
    while True:
        sub_lo, sub_hi = lo + frac * span, hi - frac * span
        sel = idxs[(frame_times[idxs] >= sub_lo) & (frame_times[idxs] < sub_hi)]
        if sel.size >= min_frames or frac <= 0:
            return sel
        frac = max(0.0, frac - 0.05)


def _crossing_time(times: np.ndarray, p: np.ndarray, level: float) -> float | None:
    """Erster (linear interpolierter) Zeitpunkt, an dem `p` den Wert
    `level` durchquert (steigend oder fallend)."""
    if times.size < 2:
        return None
    for i in range(len(p) - 1):
        p0, p1 = p[i], p[i + 1]
        if p1 == p0:
            continue
        if (p0 - level) * (p1 - level) <= 0:
            frac = (level - p0) / (p1 - p0)
            return float(times[i] + frac * (times[i + 1] - times[i]))
    return None


def analyze_event_template(
    frame_times: np.ndarray,
    frames: list[dict[str, Any]],
    session_dir: Path,
    quad_px,
    target_size,
    t_event: float,
    run_a: tuple[float, float],
    run_b: tuple[float, float],
    *,
    half_window_s: float = DEFAULT_HALF_WINDOW_S,
    min_template_frames: int = DEFAULT_MIN_TEMPLATE_FRAMES,
    margin_start: float = DEFAULT_MARGIN_START,
    noise_k: float = DEFAULT_NOISE_K,
    guard_s: float = DEFAULT_GUARD_S,
    n_iterations: int = DEFAULT_N_ITERATIONS,
    excluded_mask: np.ndarray | None = None,
    cache: dict | None = None,
) -> dict[str, Any]:
    """EIN Ereignis per Vorlagen-Projektion vermessen (Moduldoku). Baut
    Vorlage A aus `run_a`, Vorlage B aus `run_b`, iteriert die
    Plateaugrenzen einmal (`n_iterations`) nach der ersten delta-Schaetzung.

    `measurable=False` heisst: entweder zu wenige Templateframes, |B-A|
    nicht ausreichend ueber dem Rauschen, oder kein Durchgang durch p=0.5
    gefunden - in jedem Fall NICHT geraten, sondern klar als unmessbar
    ausgewiesen (`reason`)."""
    if cache is None:
        cache = {}
    lo_a, hi_a = run_a
    lo_b, hi_b = run_b
    result: dict[str, Any] = {"t_event": t_event, "measurable": False}
    for it in range(max(1, n_iterations)):
        idx_a = deep_indices(frame_times, lo_a, hi_a, min_template_frames, margin_start, excluded_mask)
        idx_b = deep_indices(frame_times, lo_b, hi_b, min_template_frames, margin_start, excluded_mask)
        if idx_a.size < min_template_frames or idx_b.size < min_template_frames:
            result.update(reason="zu wenige Templateframes", n_template_a=int(idx_a.size), n_template_b=int(idx_b.size))
            return result
        crops_a = [c for i in idx_a if (c := _cached_gray(cache, frames, session_dir, quad_px, target_size, i)) is not None]
        crops_b = [c for i in idx_b if (c := _cached_gray(cache, frames, session_dir, quad_px, target_size, i)) is not None]
        if len(crops_a) < min_template_frames or len(crops_b) < min_template_frames:
            result.update(reason="zu wenige lesbare Templateframes")
            return result

        a_img = np.mean(np.stack(crops_a), axis=0)
        b_img = np.mean(np.stack(crops_b), axis=0)
        diff_vec = (b_img - a_img).astype(np.float64)
        norm2 = float(np.sum(diff_vec * diff_vec))
        if norm2 <= 1e-9:
            result.update(reason="A und B ununterscheidbar (|B-A| ~ 0)")
            return result
        norm_ba = float(np.sqrt(norm2))
        residuals = [c - a_img for c in crops_a] + [c - b_img for c in crops_b]
        sigma_pixel = float(np.sqrt(np.mean(np.square(np.concatenate([r.ravel() for r in residuals])))))
        # p = <f-A, B-A>/|B-A|^2; fuer f = Vorlage + Rauschen n (Varianz
        # sigma^2 je Pixel) hat p Streuung sigma/|B-A| (Herleitung in
        # Moduldoku/Bericht) - das ist die Rauschbreite der p-Kurve SELBST,
        # nicht der Signaltest.
        std_p = sigma_pixel / norm_ba
        # Der Signaltest ("ist |B-A| ueber dem Rauschen") darf NICHT std_p
        # gegen einen festen Wert vergleichen: A und B sind selbst nur
        # Mittelwerte ueber n_a/n_b Bilder, ihr Unterschied hat also allein
        # durch Mittelungsrauschen eine erwartete Groesse - und die waechst
        # mit sqrt(Pixelzahl), weil |B-A| ueber ALLE (auch unveraenderte)
        # Pixel aufsummiert wird. Ohne diese Normierung faellt der Test bei
        # grossen Ausschnitten faelschlich fast immer "durch" (gemessen: ein
        # reiner Rauschausschnitt ohne jeden echten Unterschied wurde als
        # "signal_ok" durchgewunken). Erwartete Nullhypothese-Norm:
        #   E[|B-A|] ~ sigma_pixel * sqrt(n_pixel * (1/n_a + 1/n_b))
        # verlangt wird, dass die GEMESSENE Norm deutlich darueber liegt.
        n_pixel = float(a_img.size)
        expected_null_norm = sigma_pixel * float(np.sqrt(n_pixel * (1.0 / len(crops_a) + 1.0 / len(crops_b))))
        signal_ok = norm_ba > noise_k * max(expected_null_norm, 1e-9)

        lo_w = int(np.searchsorted(frame_times, t_event - half_window_s, side="left"))
        hi_w = int(np.searchsorted(frame_times, t_event + half_window_s, side="right"))
        p_times, p_vals = [], []
        for i in range(lo_w, hi_w):
            if excluded_mask is not None and excluded_mask[i]:
                continue
            g = _cached_gray(cache, frames, session_dir, quad_px, target_size, i)
            if g is None:
                continue
            p_vals.append(float(np.sum((g - a_img) * diff_vec)) / norm2)
            p_times.append(frame_times[i])
        p_times_arr = np.asarray(p_times)
        p_vals_arr = np.asarray(p_vals)

        onset = _crossing_time(p_times_arr, p_vals_arr, 0.1)
        mid = _crossing_time(p_times_arr, p_vals_arr, 0.5)
        end = _crossing_time(p_times_arr, p_vals_arr, 0.9)

        result = {
            "t_event": t_event,
            "signal_ok": signal_ok,
            "std_p": std_p,
            "sigma_pixel": sigma_pixel,
            "norm_ba": norm_ba,
            "expected_null_norm": expected_null_norm,
            "n_template_a": len(crops_a),
            "n_template_b": len(crops_b),
            "n_window_frames": int(p_vals_arr.size),
            "onset_s": (onset - t_event) if onset is not None else None,
            "mid_s": (mid - t_event) if mid is not None else None,
            "end_s": (end - t_event) if end is not None else None,
            "measurable": bool(signal_ok and mid is not None),
        }
        if not result["measurable"]:
            result["reason"] = "Signal nicht ausreichend ueber dem Rauschen" if not signal_ok else "kein Durchgang durch p=0.5"
            return result
        result["delta_s"] = result["mid_s"]
        result["d_misch_s"] = (
            (result["end_s"] - result["onset_s"])
            if (result["onset_s"] is not None and result["end_s"] is not None)
            else None
        )

        if it < n_iterations - 1:
            true_t = mid
            new_hi_a = true_t - guard_s
            new_lo_b = true_t + guard_s
            if lo_a < new_hi_a < hi_a:
                hi_a = new_hi_a
            if lo_b < new_lo_b < hi_b:
                lo_b = new_lo_b
    return result


def analyze_population_template(
    name: str,
    events: list[dict[str, Any]],
    frame_times: np.ndarray,
    frames: list[dict[str, Any]],
    session_dir: Path,
    quad_px,
    target_size,
    excluded_mask: np.ndarray | None,
    *,
    half_window_s: float,
    min_template_frames: int,
    margin_start: float,
    noise_k: float,
    guard_s: float,
    n_iterations: int,
) -> dict[str, Any]:
    per_event = []
    for e in events:
        res = analyze_event_template(
            frame_times,
            frames,
            session_dir,
            quad_px,
            target_size,
            e["t"],
            e["run_a"],
            e["run_b"],
            half_window_s=half_window_s,
            min_template_frames=min_template_frames,
            margin_start=margin_start,
            noise_k=noise_k,
            guard_s=guard_s,
            n_iterations=n_iterations,
            excluded_mask=excluded_mask,
        )
        res["group"] = e.get("group")
        per_event.append(res)

    qualifying = [r for r in per_event if r["measurable"]]
    n = len(qualifying)
    deltas = np.array([r["delta_s"] for r in qualifying], dtype=np.float64)
    d_misches = np.array([r["d_misch_s"] for r in qualifying if r["d_misch_s"] is not None], dtype=np.float64)
    return {
        "population": name,
        "n_events_total": len(events),
        "n_qualifying": n,
        "delta_s": float(np.mean(deltas)) if n else None,
        "sigma_delta_s": float(np.std(deltas, ddof=1)) if n >= 2 else None,
        "d_misch_s": float(np.mean(d_misches)) if d_misches.size else None,
        "per_event": per_event,
    }


def null_baseline_template(
    frame_times: np.ndarray,
    frames: list[dict[str, Any]],
    session_dir: Path,
    quad_px,
    target_size,
    excluded_mask: np.ndarray | None,
    runs: list[dict[str, Any]],
    *,
    half_window_s: float,
    min_template_frames: int,
    margin_start: float,
    noise_k: float,
    guard_s: float,
    rng: np.random.Generator,
    n_per_run: int = DEFAULT_NULL_PER_RUN,
    max_total: int = DEFAULT_NULL_MAX_TOTAL,
) -> dict[str, Any]:
    """Dieselbe Projektion auf zufaellige Splitpunkte INNERHALB eines
    unveraenderten Telegramm-Plateaus - es gibt dort keinen echten
    Uebergang. `pass_rate` sollte klein sein (der |B-A|-Rauschtest soll zu
    Recht meistens durchfallen); faellt er oft NICHT durch, ist die Methode
    auf dieser Aufzeichnung nicht spezifisch genug."""
    margin = half_window_s * 1.2
    long_runs = [r for r in runs if (r["t_end"] - r["t_start"]) - r.get("t_pad", 0.0) > 2 * margin]
    attempts = []
    for run in long_runs:
        if len(attempts) >= max_total:
            break
        lo, hi = run["t_start"], run["t_end"]
        if hi - lo <= 2 * margin:
            continue
        for _ in range(n_per_run):
            if len(attempts) >= max_total:
                break
            pseudo_t = float(rng.uniform(lo + margin, hi - margin))
            res = analyze_event_template(
                frame_times,
                frames,
                session_dir,
                quad_px,
                target_size,
                pseudo_t,
                (lo, pseudo_t),
                (pseudo_t, hi),
                half_window_s=half_window_s,
                min_template_frames=min_template_frames,
                margin_start=margin_start,
                noise_k=noise_k,
                guard_s=guard_s,
                n_iterations=1,
                excluded_mask=excluded_mask,
            )
            attempts.append(res)
    n_attempted = len(attempts)
    measurable = [r for r in attempts if r["measurable"]]
    spurious = [r["delta_s"] for r in measurable]
    return {
        "n_attempted": n_attempted,
        "n_measurable": len(measurable),
        "pass_rate": (len(measurable) / n_attempted) if n_attempted else None,
        "spurious_delta_spread_s": float(np.std(spurious)) if len(spurious) >= 2 else None,
    }


def population_detected(pop: dict[str, Any], null: dict[str, Any] | None, min_qualifying: int = DEFAULT_MIN_QUALIFYING) -> bool:
    if pop["n_qualifying"] < min_qualifying or pop["sigma_delta_s"] is None:
        return False
    if null is not None and null["pass_rate"] is not None and null["pass_rate"] >= 0.5:
        # Die Nullhypothese "kein echter Uebergang" haette (fast) genauso
        # oft ein "messbares" Signal geliefert - dann ist der Rauschtest
        # auf dieser Aufzeichnung nicht spezifisch genug, egal wie sauber
        # die echten Ereignisse aussehen.
        return False
    return True


def compute_M(delta_s: float, d_misch_s: float, sigma_delta_s: float, extra_s: float = M_FIXED_EXTRA_S) -> float:
    """Festlegung 3,
    docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md - fest
    vorgegebene Formel, wird hier nicht veraendert."""
    return abs(delta_s) + d_misch_s + 3 * sigma_delta_s + extra_s


# ---------------------------------------------------------------------------
# Norm-Kommandos (commands.jsonl) - zweistufig, informativ (keine M-Groesse)
# ---------------------------------------------------------------------------


def command_groups(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`commands.jsonl` nach `label` zu vollstaendigen Schreibzyklen
    gruppieren: `pause_transmission` -> `command`(s) -> `resume_transmission`.
    Nur Gruppen mit mindestens einem `set_norm`-Kommando UND einem
    `resume_transmission` zaehlen als Normierungswechsel."""
    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in commands:
        label = row.get("label")
        if label is None:
            continue
        if label not in groups:
            groups[label] = {"label": label}
            order.append(label)
        g = groups[label]
        event = row.get("event")
        t = row.get("t_boot")
        if event == "pause_transmission":
            g["t_pause"] = t
        elif event == "resume_transmission":
            g["t_resume"] = t
        elif event == "command":
            name = row.get("command_name")
            if name == "set_norm":
                g["t_set_norm"] = t
            elif name == "set_dpoint":
                g["t_set_dpoint"] = t
    result = []
    for label in order:
        g = groups[label]
        if "t_set_norm" in g and "t_resume" in g:
            result.append(g)
    return result


def analyze_norm_groups(
    norm_groups: list[dict[str, Any]],
    frame_times: np.ndarray,
    frames: list[dict[str, Any]],
    session_dir: Path,
    quad_px,
    target_size,
    excluded_mask: np.ndarray | None,
    *,
    half_window_s: float,
    min_template_frames: int,
    margin_start: float,
    noise_k: float,
    guard_s: float,
    session_end_t: float,
    pre_window_s: float = 1.0,
) -> dict[str, Any] | None:
    """Zweistufige Vorlagen-Projektion je Schreibzyklus: Stufe 1
    set_norm -> Zwischenzustand (neue Normierung, alter Dezimalpunkt),
    Stufe 2 set_dpoint -> Endzustand. Informativ - geht NICHT in M ein
    (siehe Moduldoku und Bericht): waehrend der Pause sendet das Geraet
    keine Telegramme, das erste Telegramm nach `resume` ist durch den
    Ablauf des Schreibzyklus bestimmt, nicht durch die Geraetetaktung."""
    if not norm_groups:
        return None
    stage1_events, stage2_events = [], []
    for i, g in enumerate(norm_groups):
        if "t_set_dpoint" not in g:
            continue
        next_pause = norm_groups[i + 1]["t_pause"] if i + 1 < len(norm_groups) and "t_pause" in norm_groups[i + 1] else session_end_t
        run_pre = (max(g["t_pause"] - pre_window_s, 0.0) if "t_pause" in g else g["t_set_norm"] - pre_window_s, g.get("t_pause", g["t_set_norm"]))
        run_mid = (g["t_set_norm"], g["t_set_dpoint"])
        run_post = (g["t_set_dpoint"], min(g["t_resume"] + pre_window_s, next_pause))
        stage1_events.append({"t": g["t_set_norm"], "run_a": run_pre, "run_b": run_mid})
        stage2_events.append({"t": g["t_set_dpoint"], "run_a": run_mid, "run_b": run_post})

    def _run(events, name):
        return analyze_population_template(
            name,
            events,
            frame_times,
            frames,
            session_dir,
            quad_px,
            target_size,
            excluded_mask,
            half_window_s=half_window_s,
            min_template_frames=min_template_frames,
            margin_start=margin_start,
            noise_k=noise_k,
            guard_s=guard_s,
            n_iterations=1,
        )

    return {
        "n_groups": len(norm_groups),
        "stage1_set_norm_to_mid": _run(stage1_events, "norm_stage1_set_norm"),
        "stage2_set_dpoint_to_mid": _run(stage2_events, "norm_stage2_set_dpoint"),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_hint_box(text: str) -> tuple[float, float, float, float]:
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("hint-box braucht genau vier Werte: x,y,w,h (normiert 0..1)")
    return tuple(parts)  # type: ignore[return-value]


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("session_dir", type=Path, help="Aufzeichnungsverzeichnis (frames.jsonl, serial.jsonl, frames/)")
    p.add_argument(
        "--hint-box",
        type=_parse_hint_box,
        required=True,
        help="Normierte Suchbox x,y,w,h (0..1) um den Anzeigebereich, fuer lcd_quad_in_region",
    )
    p.add_argument("--out", type=Path, default=None, help="Ausgabeverzeichnis (default: <session_dir>/offset-analyse)")
    p.add_argument("--half-window-s", type=float, default=DEFAULT_HALF_WINDOW_S)
    p.add_argument("--min-template-frames", type=int, default=DEFAULT_MIN_TEMPLATE_FRAMES)
    p.add_argument("--margin-start", type=float, default=DEFAULT_MARGIN_START)
    p.add_argument("--noise-k", type=float, default=DEFAULT_NOISE_K)
    p.add_argument("--guard-s", type=float, default=DEFAULT_GUARD_S)
    p.add_argument("--n-iterations", type=int, default=DEFAULT_N_ITERATIONS)
    p.add_argument("--min-qualifying", type=int, default=DEFAULT_MIN_QUALIFYING)
    p.add_argument("--sample-frames", type=int, default=5)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--occlusion-mad-k", type=float, default=8.0, help="Schwelle (Vielfaches der robusten Streuung) fuer die Verdeckungserkennung"
    )
    p.add_argument(
        "--isolated-only",
        dest="isolated_only",
        action="store_true",
        default=True,
        help="Nur Ereignisse mit ruhigem Vorher-Fenster fuer die delta-Schaetzung verwenden (Default: an)",
    )
    p.add_argument(
        "--no-isolated-only",
        dest="isolated_only",
        action="store_false",
        help="Auch Rampen-Ereignisse (kein ruhiges Vorher-Fenster) in die delta-Schaetzung aufnehmen",
    )
    return p


def run(args: argparse.Namespace) -> dict[str, Any]:
    session_dir: Path = args.session_dir
    out_dir: Path = args.out or (session_dir / "offset-analyse")
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = load_frames(session_dir)
    frame_times = np.array([r["t"] for r in frames], dtype=np.float64)
    session_end_t = float(frame_times[-1]) if frame_times.size else 0.0

    serial = load_serial(session_dir)
    commands = load_commands(session_dir)
    events = classify_events(serial, session_end_t=session_end_t)
    runs = build_runs(serial)
    n_telegram_lines = sum(1 for r in serial if r["is_telegram"])
    n_skipped_lines = len(serial) - n_telegram_lines

    loc = locate_quad(session_dir, frames, args.hint_box, sample_frames=args.sample_frames)
    if not loc["stable"]:
        raise RuntimeError(
            "Anzeigebereich ueber die Bildstichprobe nicht stabil "
            f"(Spanne {loc['spread_norm']:.4f} normiert) - kein Quad wird geraten. "
            "Pro-Bild-Lokalisierung ist in diesem Skript nicht implementiert; "
            "hint-box oder Aufzeichnung pruefen."
        )
    first_img = cv2.imread(str(session_dir / frames[0]["file"]))
    height, width = first_img.shape[:2]
    quad_px = quad_to_pixels(loc["quad_norm"], width, height)

    crop_means = compute_crop_means(frames, session_dir, quad_px)
    occluded_mask = detect_occlusion_mask(crop_means, mad_k=args.occlusion_mad_k)
    n_occluded = int(occluded_mask.sum())
    occluded_files = [frames[i]["file"] for i in np.where(occluded_mask)[0]]

    rng = np.random.default_rng(args.seed)
    populations = []
    for group in ("large", "small"):
        group_events_all = [e for e in events if e["group"] == group]
        used_events = [e for e in group_events_all if e["isolated"]] if args.isolated_only else group_events_all
        n_ramp_excluded = len(group_events_all) - len(used_events) if args.isolated_only else 0
        pop = analyze_population_template(
            group,
            used_events,
            frame_times,
            frames,
            session_dir,
            quad_px,
            CROP_SIZE,
            occluded_mask,
            half_window_s=args.half_window_s,
            min_template_frames=args.min_template_frames,
            margin_start=args.margin_start,
            noise_k=args.noise_k,
            guard_s=args.guard_s,
            n_iterations=args.n_iterations,
        )
        null = null_baseline_template(
            frame_times,
            frames,
            session_dir,
            quad_px,
            CROP_SIZE,
            occluded_mask,
            runs,
            half_window_s=args.half_window_s,
            min_template_frames=args.min_template_frames,
            margin_start=args.margin_start,
            noise_k=args.noise_k,
            guard_s=args.guard_s,
            rng=rng,
        )
        pop["null_baseline"] = null
        pop["n_events_ramp_excluded"] = n_ramp_excluded
        pop["detected"] = population_detected(pop, null, args.min_qualifying)
        pop["M_s"] = (
            compute_M(pop["delta_s"], pop["d_misch_s"], pop["sigma_delta_s"])
            if pop["detected"] and pop["d_misch_s"] is not None
            else None
        )
        populations.append(pop)

    agreement = None
    large = next(p for p in populations if p["population"] == "large")
    small = next(p for p in populations if p["population"] == "small")
    if large["detected"] and small["detected"]:
        agreement = abs(large["delta_s"] - small["delta_s"])

    norm_groups = command_groups(commands)
    norm_analysis = analyze_norm_groups(
        norm_groups,
        frame_times,
        frames,
        session_dir,
        quad_px,
        CROP_SIZE,
        occluded_mask,
        half_window_s=args.half_window_s,
        min_template_frames=args.min_template_frames,
        margin_start=args.margin_start,
        noise_k=args.noise_k,
        guard_s=args.guard_s,
        session_end_t=session_end_t,
    )

    result = {
        "session_dir": str(session_dir),
        "time_base": "CLOCK_BOOTTIME (frames: capture_timestamp.value_ns/1e9, serial: t_boot)",
        "sign_convention": "delta = t_glas - t_telegramm; delta>0: Telegramm zuerst, Glas folgt",
        "method": "template_projection",
        "n_frames": len(frames),
        "n_serial_lines": len(serial),
        "n_telegram_lines": n_telegram_lines,
        "n_non_telegram_lines_skipped": n_skipped_lines,
        "n_commands_jsonl_rows": len(commands),
        "occlusion": {"n_frames_occluded": n_occluded, "mad_k": args.occlusion_mad_k, "sample_files": occluded_files[:20]},
        "isolated_only": args.isolated_only,
        "quad": {
            "normalized": loc["quad_norm"],
            "stable": loc["stable"],
            "spread_norm": loc["spread_norm"],
            "n_samples": loc["n_samples"],
            "sample_files": loc["sample_files"],
        },
        "params": {
            "half_window_s": args.half_window_s,
            "min_template_frames": args.min_template_frames,
            "margin_start": args.margin_start,
            "noise_k": args.noise_k,
            "guard_s": args.guard_s,
            "n_iterations": args.n_iterations,
            "min_qualifying": args.min_qualifying,
            "seed": args.seed,
        },
        "populations": populations,
        "populations_agree_s": agreement,
        "norm_analysis": norm_analysis,
        "norm_analysis_note": (
            "delta je Stufe ist die photometrische Glasaenderung relativ zu set_norm bzw. "
            "set_dpoint - NICHT vergleichbar mit dem Telegramm-bezogenen delta der "
            "small/large-Populationen und geht nicht in M ein (Uebertragung war waehrend des "
            "Schreibzyklus pausiert)."
            if norm_analysis
            else None
        ),
    }

    out_json = out_dir / "offset-analyse.json"
    out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    result["_out_json"] = str(out_json)
    return result


def format_summary(result: dict[str, Any]) -> str:
    lines = [
        f"Sitzung: {result['session_dir']} (Methode: {result['method']})",
        f"Bilder: {result['n_frames']}, Telegramme: {result['n_telegram_lines']} "
        f"(uebersprungen als Nicht-Telegramm: {result['n_non_telegram_lines_skipped']})",
        f"Quad stabil ueber {result['quad']['n_samples']} Stichprobenbilder "
        f"(Spanne {result['quad']['spread_norm']:.4f}): {result['quad']['stable']}",
        f"Verdeckte Bilder ausgeschlossen: {result['occlusion']['n_frames_occluded']} "
        f"(Schwelle {result['occlusion']['mad_k']}x robuste Streuung)",
    ]
    for pop in result["populations"]:
        ramp_note = f" (+{pop['n_events_ramp_excluded']} Rampenereignisse ausgeschlossen)" if pop.get("n_events_ramp_excluded") else ""
        null = pop["null_baseline"]
        head = (
            f"[{pop['population']}] {pop['n_qualifying']}/{pop['n_events_total']} messbar{ramp_note}, "
            f"Null-Durchfallquote={None if null['pass_rate'] is None else f'{1 - null['pass_rate']:.0%}'}"
        )
        if pop["detected"]:
            lines.append(
                head + f" ERKANNT: delta={pop['delta_s']*1000:+.0f} ms, "
                f"sigma_delta={pop['sigma_delta_s']*1000:.0f} ms, "
                f"d_misch={'n/a' if pop['d_misch_s'] is None else f'{pop['d_misch_s']*1000:.0f} ms'}"
            )
            if pop["M_s"] is not None:
                lines.append(f"    -> M = {pop['M_s']*1000:.0f} ms")
        else:
            lines.append(head + " NICHT erkannt (zu wenige qualifizierende Ereignisse oder Nullbaseline nicht spezifisch genug).")
    if result["populations_agree_s"] is not None:
        lines.append(f"Populationen stimmen ueberein bis auf {result['populations_agree_s']*1000:.0f} ms.")
    if result.get("norm_analysis"):
        na = result["norm_analysis"]
        lines.append(f"\nNorm-Kommandos: {na['n_groups']} Schreibzyklen (informativ, nicht in M):")
        for key, label in (("stage1_set_norm_to_mid", "set_norm->Zwischenzustand"), ("stage2_set_dpoint_to_mid", "set_dpoint->Endzustand")):
            pop = na[key]
            if pop["n_qualifying"] == 0:
                lines.append(f"  [{label}] keine messbaren Ereignisse ({pop['n_events_total']} versucht).")
                continue
            lines.append(
                f"  [{label}] {pop['n_qualifying']}/{pop['n_events_total']} messbar: "
                f"delta={pop['delta_s']*1000:+.0f} ms, sigma={pop['sigma_delta_s']*1000 if pop['sigma_delta_s'] else float('nan'):.0f} ms"
            )
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = run(args)
    print(format_summary(result))
    print(f"\nJSON: {result['_out_json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
