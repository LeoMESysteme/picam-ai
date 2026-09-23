#!/usr/bin/env python3
r"""Automatischer Import einer `harvest.py`-Ernte in den `DatasetStore` - Task 5
aus docs/superpowers/plans/2026-09-23-ernte-phase1.md.

Nimmt eine Ernte (`--harvest DIR`, geschrieben von `scripts/harvest.py`:
`DIR/proposal.json` + `DIR/recording/`) und ein bestaetigtes Sitzungsprofil
(`--profile`, siehe `dispread.session_profile.SessionProfile`) entgegen,
waehlt je Plateau hoechstens `--per-plateau` Bilder gleichmaessig aus, prueft
Bildguete und Zellenkonsistenz ueber die ganze Sitzung, schneidet die
Zeichenzellen mit `CharGrid.cell_boxes()` aus dem entzerrten Bild und legt
Proben mit `label_origin="serial_ascii"` im `DatasetStore` an - **voll
automatisch** (Entscheidung 5 des Plans: an die Stelle der Durchsicht von
Hand treten automatische Plausibilitaetspruefungen und eine optionale
Stichprobenliste, `--audit`).

Legt KEINE Proben an, deren Sitzungsprofil ``resolution_ok=False`` traegt
(Exit 3) - Entscheidung 3 des Plans. Unlesbares oder Unplausibles wird
abgelehnt und der Grund gezaehlt, nie geraten (AGENTS.md).

## Regel 5: Zeichen -> Zelle (mit Bildbeleg)

Das GSV-2AS-Display hat 16 Zeichenzellen (HD44780, 16x1). Zwei entzerrte
Diagnosebilder zeigen die Abbildung eindeutig - Rasterlinien im 16-Zellen-
Raster ueber die entzerrten Ausschnitte gelegt (im Bericht dieser Aufgabe
verlinkt, Ablage unter dem Scratchpad-Verzeichnis der Sitzung):

  * `var/diagnostics/scalercrop-114805/frames/frame_000001.jpg`, Telegramm
    "+0.60972 mV/V" (kein unterdruecktes Fuehrungszeichen): das Raster zeigt
    "+" in Zelle 0, "0" in Zelle 1, "." in Zelle 2, ..., das letzte "V" in
    Zelle 12. Zellen 13-15 bleiben leer.
  * `var/diagnostics/offset-norm-101440/frames/frame_000206.jpg`, Telegramm
    "+01.2193 mV/V": das physische Display zeigt sichtbar "+ 1.2193 mV/V"
    - eine LEERE Zelle genau an Position 1 (dort, wo die von
    `telegram_to_display_text()` entfernte fuehrende Null im Rohtelegramm
    stand). "1" folgt in Zelle 2, ".", "2", "1", "9", "3" in Zellen 3-7,
    Leerzeichen in Zelle 8, "mV/V" in Zellen 9-12. Zellen 13-15 bleiben leer.

Befund: die 16 Zellen sind **linksbuendig ab Zelle 0** belegt, und zwar mit
dem ROHEN Telegrammtext (`telegram_text`, IMMER 13 Zeichen: Vorzeichen + 6
Ziffern + Punkt = 8-Zellen-Zahlenblock, siehe CLAUDE.md "der Zahlenblock
belegt immer genau 8 Zellen" + " mV/V" = 5 weitere Zeichen), NICHT mit
`label_text` (12 Zeichen, weil `telegram_to_display_text()` die unterdrueckte
fuehrende Null ENTFERNT statt sie als Leerzelle zu erhalten). Fuer die
Zelle-fuer-Zelle-Zuordnung (Zellenkonsistenzpruefung, Regel 4, und als
Sollwert fuer Phase 2) ist `telegram_text` mit einer an derselben Position
durch ein Leerzeichen ersetzten unterdrueckten Null
(`_cell_text_for_telegram`/`_padded_cell_text`, unten) die richtige
Grundlage - siehe deren Docstring fuer die exakte Regel. Das Ergebnis, auf
`n_cells` aufgefuellt, landet als `label_origin_detail["cell_text"]`.

`label_text` behaelt die Einheit " mV/V" (belegt, siehe beide Bilder oben) -
die Frage aus dem Auftrag ("behaelt label_text die Einheit?") ist damit
JA beantwortet. `label_text` landet unveraendert als
`label_origin_detail["display_text"]`.

## `expected_text` - Store-Konvention statt Store-Aenderung

`DatasetStore.normalize_label()` (`src/dispread/workbench/datasets.py`)
akzeptiert nur einen reinen Dezimalwert (`^-?(\d+\.\d+|\.\d+|\d+)$`) - kein
Vorzeichen '+', keine Einheit. Bestehende manuell gelabelte Proben folgen
genau dieser Form (z. B. `expected_text: "0.94801"`, siehe
`var/workbench/datasets/samples/663591e63681474eb1d89a420befa741/
sample.json`). `datasets.py` wird NICHT geaendert (Auftrag) - stattdessen
folgt `_expected_text_and_unit()` derselben Konvention: `expected_text` ist
der Zahlenteil von `label_text` mit entferntem '+' (ein '-' bleibt, auch
wenn an diesem Geraet unerreichbar, siehe CLAUDE.md/OQ-37), die Einheit
kommt separat in `label_origin_detail["unit_text"]`. Besteht der Zahlenteil
trotzdem nicht die Store-Pruefung, zaehlt das wie jeder andere `DatasetError`
als `store_abgelehnt`.

Diese Zuordnung ist an ZWEI verschiedenen Telegrammen/Bildern belegt (mit und
ohne unterdrueckte Null) und eindeutig, keine Mehrdeutigkeit im Sinne von
"import-harvest.py verweigert sich" - die Regel steht daher fest im Code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from dispread.rectify import rectify
from dispread.session_profile import SessionProfile
from dispread.workbench.datasets import DatasetError, DatasetStore

CELL_COMPARE_SIZE = (10, 16)  # (Breite, Hoehe) fuer den Zellenvergleich, Auftrag Regel 4
MAD_K = 6.0
MIN_CHAR_OCCURRENCES = 5

REASON_BILDGUETE = "bildguete"
REASON_ZELLEN_INKONSISTENT = "zellen_inkonsistent"
REASON_NICHT_PRUEFBAR = "nicht_pruefbar"
REASON_LAENGE = "laenge_passt_nicht"
REASON_STORE = "store_abgelehnt"
REASON_BILD_FEHLT = "bild_nicht_ladbar"

_ALL_REASONS = (
    REASON_BILDGUETE,
    REASON_ZELLEN_INKONSISTENT,
    REASON_NICHT_PRUEFBAR,
    REASON_LAENGE,
    REASON_STORE,
    REASON_BILD_FEHLT,
)

#: Nur informativ, taucht im Bericht auf - kein Ablehnungsgrund fuer sich.
COUNTER_ZEICHEN_ZU_SELTEN = "zeichen_zu_selten_fuer_pruefung"


def _cell_text_for_telegram(telegram_text: str) -> str:
    """Erwarteter Zellinhalt je Position 0..len-1 (siehe Modul-Docstring,
    Regel 5). Gleiche Regel wie `gate_label.telegram_to_display_text()`
    (Vorzeichen ueberspringen, genau eine fuehrende '0' vor einer weiteren
    Ziffer betroffen) - ABER die betroffene Null wird durch ein Leerzeichen
    ERSETZT statt entfernt, damit Position i weiterhin exakt Zelle i
    entspricht (belegt an zwei Bildern, s. o.). NICHT auf `n_cells` aufgefuellt
    - das macht `_padded_cell_text`."""
    if not telegram_text:
        return telegram_text
    if telegram_text[0] in "+-":
        sign, rest = telegram_text[0], telegram_text[1:]
    else:
        sign, rest = "", telegram_text
    if len(rest) >= 2 and rest[0] == "0" and rest[1].isdigit():
        rest = " " + rest[1:]
    return sign + rest


def _padded_cell_text(telegram_text: str, n_cells: int) -> str:
    """`_cell_text_for_telegram` rechtsseitig mit Leerzeichen auf `n_cells`
    aufgefuellt - das ist der Zellen-fuer-Zellen-Sollwert, wie ihn Phase 2
    (Zellen-Klassifikator) braucht, siehe `label_origin_detail["cell_text"]`."""
    return _cell_text_for_telegram(telegram_text).ljust(n_cells)


def _expected_text_and_unit(label_text: str) -> tuple[str, str]:
    """Zerlegt `label_text` (z. B. "+0.60972 mV/V") in den fuer
    `DatasetStore.normalize_label` gueltigen Zahlenteil und die Einheit.

    Bestehende Konvention im Store (siehe manuelle Proben, z. B.
    `var/workbench/datasets/samples/663591e63681474eb1d89a420befa741/
    sample.json`: `expected_text: "0.94801"`, kein Vorzeichen, keine
    Einheit): `expected_text` ist der reine Zahlenwert. Ein fuehrendes '+'
    wird entfernt (der Store kennt es nicht), ein '-' bleibt erhalten (auch
    wenn an diesem Geraet - Firmware 1.3.07 - nie erreichbar, siehe
    CLAUDE.md/OQ-37). Keine Neuformatierung sonst: die Ziffern zwischen
    Vorzeichen und Einheit werden unveraendert uebernommen. Die Einheit
    (alles nach dem ersten Leerzeichen) kommt separat in
    `label_origin_detail["unit_text"]`, damit sie nicht verloren geht.
    """
    signed, _, unit = label_text.partition(" ")
    numeric = signed[1:] if signed.startswith("+") else signed
    return numeric, unit


def _axis_aligned_bbox(quad: list[list[float]]) -> list[float]:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    x0, y0 = min(xs), min(ys)
    return [x0, y0, max(xs) - x0, max(ys) - y0]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Importiert eine harvest.py-Ernte (proposal.json + recording/) vollautomatisch "
            "in den DatasetStore - mit Plausibilitaetspruefungen statt Durchsicht von Hand "
            "(Ernte Phase 1, Entscheidung 5)."
        )
    )
    parser.add_argument("--harvest", type=Path, required=True, help="Ausgabeverzeichnis von harvest.py")
    parser.add_argument("--profile", type=Path, required=True, help="Sitzungsprofil (SessionProfile-JSON)")
    parser.add_argument("--dataset-root", type=Path, required=True, help="Wurzel des DatasetStore")
    parser.add_argument("--per-plateau", type=int, default=3, help="Hoechstens so viele Bilder je Plateau")
    parser.add_argument("--audit", type=int, default=0, help="Groesse der Stichprobenliste (audit.json)")
    parser.add_argument("--dry-run", action="store_true", help="Nichts im DatasetStore anlegen, nur zaehlen")
    return parser.parse_args(argv)


@dataclass
class _Candidate:
    image_path: Path
    telegram_text: str
    label_text: str
    label_normalization: str
    label_origin_detail: dict
    plateau_key: tuple[int, int]
    capture_timestamp: dict | None
    frame_sequence: int | None
    cell_text: str
    raw_image: np.ndarray | None = None
    rectified_gray: np.ndarray | None = None
    brightness: float | None = None
    sharpness: float | None = None


def _load_frames_map(recording_dir: Path) -> dict[str, dict]:
    frames_path = recording_dir / "frames.jsonl"
    out: dict[str, dict] = {}
    if not frames_path.is_file():
        return out
    for line in frames_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        out[str(obj["file"])] = obj
    return out


def _resolve_image_path(harvest_dir: Path, image_path: str) -> Path:
    name = Path(image_path).name
    candidate = harvest_dir / "recording" / "frames" / name
    if candidate.is_file():
        return candidate
    return Path(image_path)


def _select_per_plateau(images: list[dict], per_plateau: int) -> list[dict]:
    """Je Plateau hoechstens `per_plateau` Bilder, gleichmaessig ueber die
    (in Aufnahmereihenfolge vorliegende) Liste verteilt (Regel 2)."""
    groups: dict[tuple[int, int], list[dict]] = {}
    for entry in images:
        detail = entry["label_origin_detail"]
        key = (int(detail["plateau_start_ns"]), int(detail["plateau_end_ns"]))
        groups.setdefault(key, []).append(entry)

    selected: list[dict] = []
    for group in groups.values():
        n = len(group)
        if n <= per_plateau:
            selected.extend(group)
            continue
        idxs = sorted({round(i) for i in np.linspace(0, n - 1, per_plateau)})
        selected.extend(group[i] for i in idxs)
    return selected


def _robust_outlier(values: list[float], k: float = MAD_K) -> list[bool]:
    """`True` je Wert, der weiter als `k*MAD` vom Median entfernt liegt."""
    if not values:
        return []
    median = statistics.median(values)
    mad = statistics.median(abs(v - median) for v in values)
    if mad == 0:
        return [v != median for v in values]
    return [abs(v - median) > k * mad for v in values]


def _medoid(vectors: list[np.ndarray]) -> np.ndarray:
    if len(vectors) == 1:
        return vectors[0]
    stacked = np.stack(vectors)
    # paarweise euklidische Distanzen
    diffs = stacked[:, None, :] - stacked[None, :, :]
    dists = np.sqrt((diffs**2).sum(axis=2))
    totals = dists.sum(axis=1)
    return vectors[int(np.argmin(totals))]


def _normalized_cell(cell_img: np.ndarray) -> np.ndarray:
    """Zellenbild fuer den Vergleich vorbereiten: Mittel 0, Norm 1 (Auftrag
    Regel 4, woertlich) - NICHT Standardabweichung 1. Der Unterschied ist
    kein Stilpunkt: bei einer leeren (Hintergrund-)Zelle ist die
    Standardabweichung nur Bildrauschen, und eine Division dadurch
    verstaerkt genau dieses Rauschen auf volle Einheitsvarianz je Pixel -
    zwei leere Zellen wirken dann so unaehnlich wie echtes Rauschen
    (beobachtet: mittlere Distanz ~ sqrt(2*Pixelzahl), viel groesser als
    zwischen echten, unterschiedlichen Zeichen). Eine Division durch die
    L2-Norm des mittelwertfreien Vektors skaliert stattdessen den ganzen
    Vektor auf Einheitslaenge und bleibt bei einer leeren Zelle robust genug,
    dass Regel 4 nicht an Leerzellen scheitert."""
    gray = cell_img if cell_img.ndim == 2 else cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, CELL_COMPARE_SIZE, interpolation=cv2.INTER_AREA).astype(np.float64)
    centered = (resized - resized.mean()).ravel()
    norm = np.linalg.norm(centered)
    if norm == 0:
        return np.zeros(centered.size, dtype=np.float64)
    return centered / norm


def run(args: argparse.Namespace) -> int:
    harvest_dir: Path = args.harvest
    profile = SessionProfile.load(args.profile)
    if not profile.resolution_ok:
        print(
            f"Fehler: Sitzungsprofil {args.profile} hat resolution_ok=False - "
            "die Sitzung wurde beim Aufloesungs-Gate abgelehnt, kein Import.",
            file=sys.stderr,
        )
        return 3

    proposal_path = harvest_dir / "proposal.json"
    if not proposal_path.is_file():
        print(f"Fehler: {proposal_path} fehlt.", file=sys.stderr)
        return 1
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    images: list[dict] = proposal.get("images", [])

    frames_map = _load_frames_map(harvest_dir / "recording")

    selected_raw = _select_per_plateau(images, args.per_plateau)

    reject_counts: dict[str, int] = {r: 0 for r in _ALL_REASONS}
    counters = {COUNTER_ZEICHEN_ZU_SELTEN: 0}

    candidates: list[_Candidate] = []
    for entry in selected_raw:
        detail = entry["label_origin_detail"]
        key = (int(detail["plateau_start_ns"]), int(detail["plateau_end_ns"]))
        telegram_text = entry["telegram_text"]
        image_path = _resolve_image_path(harvest_dir, entry["image_path"])
        frame_meta = frames_map.get(image_path.name)
        cand = _Candidate(
            image_path=image_path,
            telegram_text=telegram_text,
            label_text=entry["label_text"],
            label_normalization=entry["label_normalization"],
            label_origin_detail=detail,
            plateau_key=key,
            capture_timestamp=frame_meta.get("capture_timestamp") if frame_meta else None,
            frame_sequence=frame_meta.get("frame_sequence") if frame_meta else None,
            cell_text=_padded_cell_text(telegram_text, profile.grid.n_cells),
        )
        raw = cv2.imread(str(image_path))
        if raw is None:
            reject_counts[REASON_BILD_FEHLT] += 1
            continue
        cand.raw_image = raw
        crop = rectify(raw, tuple(tuple(p) for p in profile.quad), target_size=profile.target_size)
        rect_img = crop.image
        gray = rect_img if rect_img.ndim == 2 else cv2.cvtColor(rect_img, cv2.COLOR_BGR2GRAY)
        cand.rectified_gray = gray
        cand.brightness = float(gray.mean())
        cand.sharpness = crop.sharpness
        candidates.append(cand)

    # -- Regel 3: Bildguete ------------------------------------------------
    brightness_outliers = _robust_outlier([c.brightness for c in candidates])
    sharpness_outliers = _robust_outlier([c.sharpness for c in candidates])
    survivors: list[_Candidate] = []
    for cand, bright_bad, sharp_bad in zip(candidates, brightness_outliers, sharpness_outliers, strict=True):
        if bright_bad or sharp_bad:
            reject_counts[REASON_BILDGUETE] += 1
            continue
        survivors.append(cand)

    # -- Regel 5 (Teil 1, gebraucht fuer Regel 4): Laenge gegen Rasterbelegung
    n_cells = profile.grid.n_cells
    length_ok: list[_Candidate] = []
    for cand in survivors:
        if len(_cell_text_for_telegram(cand.telegram_text)) > n_cells:
            reject_counts[REASON_LAENGE] += 1
            continue
        length_ok.append(cand)

    # -- Regel 4: Zellenkonsistenz ------------------------------------------
    boxes = profile.grid.cell_boxes()
    char_occurrences: dict[str, int] = {}
    for cand in length_ok:
        for ch in cand.cell_text:
            char_occurrences[ch] = char_occurrences.get(ch, 0) + 1

    checkable_chars = {ch for ch, n in char_occurrences.items() if n >= MIN_CHAR_OCCURRENCES}
    for ch, n in char_occurrences.items():
        if ch not in checkable_chars:
            counters[COUNTER_ZEICHEN_ZU_SELTEN] += n

    def _cell_image(cand: _Candidate, cell_idx: int) -> np.ndarray | None:
        if cell_idx >= len(boxes):
            return None
        x, y, w, h = boxes[cell_idx]
        gray = cand.rectified_gray
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(gray.shape[1], x + w), min(gray.shape[0], y + h)
        if x1 <= x0 or y1 <= y0:
            return None
        return gray[y0:y1, x0:x1]

    not_checkable: list[_Candidate] = []
    checkable: list[_Candidate] = []
    for cand in length_ok:
        if any(ch not in checkable_chars for ch in cand.cell_text):
            not_checkable.append(cand)
        else:
            checkable.append(cand)
    reject_counts[REASON_NICHT_PRUEFBAR] += len(not_checkable)

    # Zellenvektoren je Zeichen sammeln
    vectors_by_char: dict[str, list[np.ndarray]] = {ch: [] for ch in checkable_chars}
    cell_vectors: list[list[np.ndarray | None]] = []
    for cand in checkable:
        row: list[np.ndarray | None] = []
        for i, ch in enumerate(cand.cell_text):
            img = _cell_image(cand, i)
            vec = _normalized_cell(img) if img is not None and img.size else None
            row.append(vec)
            if vec is not None:
                vectors_by_char[ch].append(vec)
        cell_vectors.append(row)

    medoid_by_char = {ch: _medoid(vecs) for ch, vecs in vectors_by_char.items() if vecs}

    # Distanzen zum Medoid des eigenen Zeichens, gruppiert JE ZEICHEN (nicht
    # sitzungsweit gepoolt): "der Distanzen zum Medoid IHRES Zeichens" (Auftrag
    # Regel 4) wird hier woertlich als je-Zeichen-Verteilung gelesen. Das ist
    # nicht nur Wortlaut - ein sitzungsweit gepoolter Schwellwert scheitert an
    # Leerzellen (Leerzeichen zwischen Zahlenblock und Einheit, ungenutzte
    # Endzellen): eine leere Zelle hat kein Motiv, nur Bildrauschen, und nach
    # der Normierung (Mittel 0, Norm 1) zeigt reines Rauschen naturgemaess
    # groessere Abweichungen zwischen Aufnahmen als ein tatsaechliches
    # Zeichen mit hohem Kontrast - das ist keine Inkonsistenz, sondern die
    # erwartete Streuung leerer Zellen. Je Zeichen ein eigener
    # Median/MAD-Schwellwert haelt Leerzellen an ihrem eigenen, groesseren
    # Rauschmassstab, waehrend echte Ausreisser (falsches Zeichen im Bild)
    # innerhalb IHRER Zeichenklasse trotzdem auffallen.
    distances_by_char: dict[str, list[float]] = {ch: [] for ch in medoid_by_char}
    per_image_distances: list[list[tuple[str, float]]] = []
    for cand, row in zip(checkable, cell_vectors, strict=True):
        dists: list[tuple[str, float]] = []
        for ch, vec in zip(cand.cell_text, row, strict=True):
            if vec is None or ch not in medoid_by_char:
                continue
            d = float(np.linalg.norm(vec - medoid_by_char[ch]))
            dists.append((ch, d))
            distances_by_char[ch].append(d)
        per_image_distances.append(dists)

    threshold_by_char: dict[str, float] = {}
    for ch, dists in distances_by_char.items():
        if not dists:
            continue
        median = statistics.median(dists)
        mad = statistics.median(abs(d - median) for d in dists)
        threshold_by_char[ch] = median + MAD_K * mad

    consistent: list[_Candidate] = []
    for cand, dists in zip(checkable, per_image_distances, strict=True):
        if any(ch in threshold_by_char and d > threshold_by_char[ch] for ch, d in dists):
            reject_counts[REASON_ZELLEN_INKONSISTENT] += 1
            continue
        consistent.append(cand)

    # -- Regel 6: Anlegen -----------------------------------------------------
    created_ids: list[str] = []
    if not args.dry_run:
        store = DatasetStore(args.dataset_root)
        device_id = _resolve_or_create_device(store, profile.device_id, profile.session_id)
        note = f"Ernte-Sitzung {profile.session_id} (automatischer Import, Plan 2026-09-23-ernte-phase1)"
        group_id = _resolve_or_create_group(store, device_id, note)
        bbox = _axis_aligned_bbox(profile.quad)

        for cand in consistent:
            token = hashlib.sha256(f"{profile.session_id}:{cand.image_path}".encode()).hexdigest()
            capture = {
                "image": cand.raw_image,
                "capture_token": token,
                "device_id": device_id,
                "group_id": group_id,
                "source_id": f"harvest:{profile.session_id}",
                "frame_sequence": cand.frame_sequence,
                "capture_timestamp": cand.capture_timestamp,
                "source_revision": None,
                "synthetic": False,
                "stored_at_utc": _now_utc_iso(),
                "source": None,
                "license": None,
            }
            expected_text, unit_text = _expected_text_and_unit(cand.label_text)
            detail = dict(cand.label_origin_detail)
            detail.update(
                {
                    "session_id": profile.session_id,
                    "telegram_text": cand.telegram_text,
                    "label_normalization": cand.label_normalization,
                    "gap_thresholds_provisional": True,
                    "display_text": cand.label_text,
                    "cell_text": cand.cell_text,
                    "unit_text": unit_text,
                }
            )
            annotation = {
                "bbox": bbox,
                "label_state": "readable",
                "expected_text": expected_text,
                "conditions": [],
                "label_origin": "serial_ascii",
                "label_origin_detail": detail,
                "independence_confirmation": True,
            }
            try:
                sample = store.save_sample(capture, annotation)
            except DatasetError as error:
                message = str(error)
                if "Ähnlich zu vorhandener Probe" in message:
                    retry_annotation = dict(annotation)
                    retry_annotation["similarity_confirmed"] = True
                    retry_annotation["similarity_reason"] = (
                        f"automatische serielle Ernte: Plateau {cand.plateau_key[0]}-{cand.plateau_key[1]}, "
                        f"{args.per_plateau} Bilder je Plateau "
                        "(Plan 2026-09-23-ernte-phase1, Entscheidung 5)"
                    )
                    try:
                        sample = store.save_sample(capture, retry_annotation)
                    except DatasetError:
                        reject_counts[REASON_STORE] += 1
                        continue
                else:
                    reject_counts[REASON_STORE] += 1
                    continue
            created_ids.append(sample["id"])

    total = len(images)
    result = {
        "harvest": str(harvest_dir),
        "profile": str(args.profile),
        "dataset_root": str(args.dataset_root),
        "dry_run": bool(args.dry_run),
        "per_plateau": args.per_plateau,
        "frames_total": total,
        "selected": len(selected_raw),
        "imported": len(created_ids),
        "sample_ids": created_ids,
        "rejected_by_reason": reject_counts,
        "counters": counters,
        "gap_thresholds_provisional": True,
    }
    (harvest_dir / "import.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== import-harvest: Bericht ===")
    print(f"Ernte: {harvest_dir}")
    print(f"Bilder im Vorschlag: {total}  Ausgewaehlt (je Plateau <= {args.per_plateau}): {len(selected_raw)}")
    print(f"Importiert: {len(created_ids)}")
    print("Abgelehnt je Grund:")
    for reason in _ALL_REASONS:
        print(f"  {reason}: {reject_counts[reason]}")
    print(f"Zeichen zu selten fuer Pruefung (< {MIN_CHAR_OCCURRENCES} Vorkommen, nur Zaehlung): "
          f"{counters[COUNTER_ZEICHEN_ZU_SELTEN]}")
    print(f"\nErgebnisdatei geschrieben: {harvest_dir / 'import.json'}")

    if not args.dry_run and args.audit > 0:
        _write_audit(harvest_dir, profile, consistent, created_ids, args.audit)

    return 0


def _now_utc_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def _resolve_or_create_device(store: DatasetStore, external_device_id: str, session_id: str) -> str:
    """Sucht ein Geraet mit `name == external_device_id`, legt sonst eines an.

    `DatasetStore.create_device` vergibt IMMER eine neue zufaellige UUID und
    kennt kein "lege an, falls unbekannte externe ID" - das ist eine
    Einschraenkung des Stores (siehe Bericht dieser Aufgabe). Der Umweg hier
    (Suche ueber die oeffentliche `list_devices()`, Abgleich ueber das freie
    Textfeld `name`) kommt ohne Aenderung an `datasets.py` aus, ist aber
    ausdruecklich ein Workaround, kein Ersatz fuer eine echte
    Store-Erweiterung.
    """
    for device in store.list_devices():
        if device.get("name") == external_device_id:
            return device["id"]
    device = store.create_device(
        {
            "name": external_device_id,
            "model": None,
            "family": "gsv2as",
            "technology": "LCD",
            "split": "development",
            "identity_evidence": (
                f"Ernte-Sitzung {session_id}: externe Geraete-ID {external_device_id!r} aus dem vom "
                "Bediener bestaetigten Sitzungsprofil (harvest-setup.py confirm)."
            ),
            "identity_confirmed": True,
        }
    )
    return device["id"]


def _resolve_or_create_group(store: DatasetStore, device_id: str, note: str) -> str:
    """Sucht eine Gruppe mit passendem `change_note`, legt sonst eine an.

    Gleiche Einschraenkung wie `_resolve_or_create_device`: `begin_group`
    vergibt immer eine neue Gruppen-ID, es gibt keine "hole oder lege an"
    -Operation im Store. Die Suche laeuft ueber die von `get_device`
    oeffentlich gelieferten `groups`.
    """
    device = store.get_device(device_id)
    for group_id, group in device.get("groups", {}).items():
        if group.get("change_note") == note:
            return group_id
    created = store.begin_group(device_id, note)
    return created["group_id"]


def _write_audit(
    harvest_dir: Path,
    profile: SessionProfile,
    consistent: list[_Candidate],
    created_ids: list[str],
    audit_n: int,
) -> None:
    import random

    seed = int(hashlib.sha256(profile.session_id.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    pool = list(zip(consistent, created_ids, strict=False)) if len(consistent) == len(created_ids) else []
    rng.shuffle(pool)
    picked = pool[:audit_n]

    overlay_dir = harvest_dir / "audit_overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    boxes = profile.grid.cell_boxes()
    entries = []
    for cand, sample_id in picked:
        overlay = cand.rectified_gray
        overlay_bgr = cv2.cvtColor(overlay, cv2.COLOR_GRAY2BGR) if overlay.ndim == 2 else overlay.copy()
        for x, y, w, h in boxes:
            cv2.rectangle(overlay_bgr, (x, y), (x + w, y + h), (0, 0, 255), 1)
        overlay_path = overlay_dir / f"{sample_id}.png"
        cv2.imwrite(str(overlay_path), overlay_bgr)
        entries.append(
            {
                "sample_id": sample_id,
                "image_path": str(cand.image_path),
                "label_text": cand.label_text,
                "overlay_path": str(overlay_path),
            }
        )
    audit = {"session_id": profile.session_id, "requested": audit_n, "entries": entries}
    (harvest_dir / "audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Stichprobenliste geschrieben: {harvest_dir / 'audit.json'} ({len(entries)} Eintraege)")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
