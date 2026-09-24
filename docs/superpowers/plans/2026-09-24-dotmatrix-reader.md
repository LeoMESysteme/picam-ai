# Dot-Matrix-Leser (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein `DotMatrixReader`, der die 16×1-Punktraster-Anzeige des GSV-2AS aus dem entzerrten Bild liest, im Zweifel ablehnt, und eine vorab festgelegte Entwicklungsmessung (Stufe 1) über die drei geernteten Aufstellungen.

**Architecture:** Punktmitten aus dem bestätigten `CharGrid` abtasten (40 Werte je Zelle), je Bild normieren, mit gelernten Vorlagen (Mittelwert + Streuung je Punkt) vergleichen, mit zwei Schwellen ablehnen, danach eine Formatregel über den ganzen Wert. Vorlagen und Schwellen entstehen offline aus dem Datensatz, werden mit Prüfsumme eingefroren und gegen den HD44780-Zeichensatz gegengeprüft.

**Tech Stack:** Python 3 (`./.venv` mit `--system-site-packages`), numpy, OpenCV (`cv2`), pytest, ruff. Keine neue Abhängigkeit.

**Spec:** `docs/superpowers/specs/2026-09-24-dotmatrix-reader-design.md`

## Global Constraints

- Arbeitsverzeichnis ist der Worktree `/home/me-systeme/picam-ai-ernte`, Branch `feat/task-b-versatz-normierung`. Nicht den Branch wechseln, nicht in `/home/me-systeme/picam-ai` arbeiten (dort arbeitet der Nutzer).
- Aufrufe: `PYTHONPATH=src /home/me-systeme/picam-ai/.venv/bin/python`, `PYTHONPATH=src /home/me-systeme/picam-ai/.venv/bin/pytest -q`, `/home/me-systeme/picam-ai/.venv/bin/ruff check src tests examples scripts`, jeweils aus dem Worktree. `var/` ist ein Symlink auf den Hauptordner — `var/workbench/datasets` **nur lesen**.
- Keine neue Abhängigkeit, kein ML-Framework.
- Der Leser bekommt nie den Referenzwert; er lernt im Betrieb nicht nach.
- `declares_confidence_calibrated` ist `False`.
- Unlesbares ablehnen, nie raten. Negative Werte werden nie ausgegeben (kein Beispiel, Firmware 1.3.07).
- Einheit kommt aus dem Profil (`mV/V`), wird nicht gelesen (OQ-17).
- Formatregel `gsv2as_v1`: Zelle 0 = `+`; Zellen 1–7 = genau 6 Ziffern und genau ein `.`, davor 0–2 Leerzellen (unterdrückte Nullen, OQ-41 `gsv2as_leading_zero_v2`), nie eine Leerzelle direkt vor `.` und nie eine Leerzelle nach der ersten Ziffer; Zelle 8 = Leerzelle. Zellen 9–15 (Einheit, Rest) werden in diesem Schritt nicht klassifiziert.
- Schwellenformel `thresholds_v1`: `D_max = 1.25 * p99.5(d_best richtiger Zuordnungen)`; `margin_min = max(0.2 * median(d_second - d_best richtiger Zuordnungen), 1.25 * max(d_second - d_best von Fehlzuordnungen))`, Fehlzuordnungen leer → zweiter Term 0.
- Kommentare, Meldungen, CHANGELOG deutsch, im Stil der umgebenden Datei.
- Jede Änderung unter `src/` oder `scripts/` braucht einen CHANGELOG-Eintrag im selben Commit (AGENTS.md). **Subagenten committen nicht** und bearbeiten weder `CHANGELOG.md` noch `docs/*.md` noch `TODO.md`; sie liefern den CHANGELOG-Text im Bericht, Commit und Doku übernimmt der Orchestrator.
- Subagenten öffnen weder Kamera noch seriellen Port.

## Review Focus

1. **Leere oder fast leere Anzeige** (Gerät aus, Hintergrundbeleuchtung aus, alle Zellen leer): Normierung darf nicht durch null teilen; erwartet wird Ablehnung `kontrast`, kein Wert. → Test in Task 2.
2. **Raster ragt nach Verschiebungssuche aus dem Bild** (Zelle am Rand, Shift ±1): Abtastung muss am Rand klemmen statt `IndexError`. → Test in Task 2.
3. **Graustufen- statt Farbbild** als Eingabe (`crop.ndim == 2`): muss genauso funktionieren. → Test in Task 4.
4. **`templates.json` von einer anderen Formelversion oder mit fehlender Klasse** (z. B. ohne `.`): Laden muss mit klarer Meldung scheitern. → Test in Task 3.
5. **Wert mit 2 unterdrückten Nullen** (`+  988.5`): muss als `988.5` freigegeben werden, 3 Leerzellen dagegen `format`. → Test in Task 4.

---

## Dateistruktur

| Datei | Verantwortung | Task |
| --- | --- | --- |
| `src/dispread/ocr/dotmatrix_font.py` (neu) | HD44780-A00-Bitmuster der 14 Zeichen als 5×8, `rom_vector(ch)` | 1 |
| `src/dispread/ocr/dotmatrix_sampling.py` (neu) | Punktmitten, Abtastung, Normierung, Verschiebungssuche | 2 |
| `src/dispread/ocr/dotmatrix_templates.py` (neu) | `Templates` (Laden/Speichern/Prüfsumme), Abstand, Klassifikation, Schwellenformel, ROM-Gegenprobe | 3 |
| `src/dispread/layout.py` (ändern) | `CharLayout` | 4 |
| `src/dispread/ocr/__init__.py` (ändern) | `ValueReader.read` akzeptiert `DisplayLayout \| CharLayout` | 4 |
| `src/dispread/ocr/dotmatrix.py` (neu) | `DotMatrixReader`, Formatregel `gsv2as_v1` | 4 |
| `src/dispread/validate.py` (ändern) | `default_gate_config(backend_id, **overrides)` | 5 |
| `scripts/import-harvest.py` (ändern) | Profil-Quad, -Raster, -Prüfsumme und Lauf-Kennung in `label_origin_detail` | 6 |
| `scripts/dotmatrix-dataset.py` (neu) | Proben laden, Profil je Probe auflösen, Zellvektoren erzeugen; Profil-Zuordnungsdatei schreiben | 6 |
| `scripts/dotmatrix-train.py` (neu) | Vorlagen + Schwellen aus gewählten Gruppen | 7 |
| `scripts/dotmatrix-eval.py` (neu) | Stufe 1: Leave-one-group-out, Bericht | 7 |
| `tests/test_dotmatrix_font.py`, `tests/test_dotmatrix_sampling.py`, `tests/test_dotmatrix_templates.py`, `tests/test_dotmatrix_reader.py`, `tests/test_gate_config.py`, `tests/test_dotmatrix_dataset.py`, `tests/test_dotmatrix_train_eval.py` (neu) | Tests | 1–7 |

Reihenfolge: 1 → 2 → 3 → 4, 5 parallel zu 2–4, 6 parallel zu 2–5, dann 7, dann Task 8 (Orchestrator: Stufe 1 laufen lassen, dokumentieren).

Gemeinsame Konstanten (in `dotmatrix_font.py`, von allen importiert):

```python
CLASSES: tuple[str, ...] = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "+", " ")
ROWS = 8
COLS = 5
N_DOTS = ROWS * COLS  # 40, Reihenfolge zeilenweise: index = r * COLS + c
```

---

### Task 1: HD44780-Zeichensatz

**Files:**
- Create: `src/dispread/ocr/dotmatrix_font.py`
- Test: `tests/test_dotmatrix_font.py`

**Interfaces:**
- Produces: `CLASSES`, `ROWS`, `COLS`, `N_DOTS`, `ROM_A00: dict[str, tuple[str, ...]]` (8 Zeilen à 5 Zeichen `"0"/"1"`, auch `"-"` und `"°"` für Tests), `rom_vector(ch: str) -> np.ndarray` (Form `(40,)`, `float32`, 1.0 = Punkt an).

- [ ] **Step 1: Failing test**

```python
# tests/test_dotmatrix_font.py
import numpy as np
import pytest

from dispread.ocr.dotmatrix_font import CLASSES, N_DOTS, ROM_A00, rom_vector


def test_every_class_and_minus_has_8x5_bitmap():
    for ch in (*CLASSES, "-", "°"):
        rows = ROM_A00[ch]
        assert len(rows) == 8
        assert all(len(r) == 5 and set(r) <= {"0", "1"} for r in rows)


def test_cursor_row_is_empty_for_all_classes():
    for ch in CLASSES:
        assert ROM_A00[ch][7] == "00000"


def test_rom_vector_shape_and_known_dots():
    v = rom_vector("1")
    assert v.shape == (N_DOTS,) and v.dtype == np.float32
    assert v[0 * 5 + 2] == 1.0  # oberste Zeile, Mitte
    assert rom_vector(" ").sum() == 0.0


def test_all_classes_pairwise_distinct():
    vecs = {ch: tuple(rom_vector(ch)) for ch in CLASSES}
    assert len(set(vecs.values())) == len(CLASSES)


def test_unknown_char_raises():
    with pytest.raises(KeyError):
        rom_vector("x")
```

- [ ] **Step 2:** `PYTHONPATH=src /home/me-systeme/picam-ai/.venv/bin/pytest -q tests/test_dotmatrix_font.py` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementieren**

```python
# src/dispread/ocr/dotmatrix_font.py
"""HD44780-Zeichensatz (ROM A00) fuer die Punktraster-Anzeige des GSV-2AS.

Nur die Zeichen, die der Dot-Matrix-Leser kennt, plus `-` und `°` fuer
Ablehnungstests. Quelle: HD44780U-Datenblatt, Zeichentabelle ROM Code A00,
5x8-Muster (7 Zeilen Zeichen, 8. Zeile Cursor). Der Modultyp (Displaytech
161A) legt nur die Geometrie fest, nicht die ROM-Variante (CLAUDE.md); bei
Ziffern stimmen die Varianten ueberein. Diese Tabelle dient als Gegenprobe
beim Lernen (Spec Abschnitt 2), nicht als Vorlage im Betrieb.
"""

from __future__ import annotations

import numpy as np

CLASSES: tuple[str, ...] = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "+", " ")
ROWS = 8
COLS = 5
N_DOTS = ROWS * COLS

ROM_A00: dict[str, tuple[str, ...]] = {
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110", "00000"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110", "00000"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111", "00000"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110", "00000"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010", "00000"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110", "00000"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110", "00000"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000", "00000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110", "00000"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000", "00000"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000", "00000"),
    "°": ("01100", "10010", "10010", "01100", "00000", "00000", "00000", "00000"),
}


def rom_vector(ch: str) -> np.ndarray:
    """40 Punktwerte (zeilenweise), 1.0 = Punkt an."""
    rows = ROM_A00[ch]
    return np.array([float(b) for row in rows for b in row], dtype=np.float32)
```

- [ ] **Step 4:** Test läuft grün, `ruff check src tests` sauber.
- [ ] **Step 5:** Bericht mit CHANGELOG-Vorschlag (kein Commit).

---

### Task 2: Abtastung, Normierung, Verschiebungssuche

**Files:**
- Create: `src/dispread/ocr/dotmatrix_sampling.py`
- Create (Test-Helfer): `tests/dotmatrix_helpers.py` mit `GRID` und `render` (unten im Test gezeigt; in die Helferdatei auslagern, der Test importiert sie mit `from dotmatrix_helpers import GRID, render` — `tests/` ist kein Paket, `conftest.py` legt das Verzeichnis auf `sys.path`)
- Test: `tests/test_dotmatrix_sampling.py`

**Interfaces:**
- Consumes: `CharGrid` (`dispread.charcells`), `ROWS`, `COLS`, `N_DOTS` (Task 1).
- Produces:
  - `SHIFTS: tuple[tuple[int, int], ...]` = alle `(dx, dy)` mit `dx, dy ∈ {-1, 0, 1}` (entzerrte Pixel; bei den gemessenen Aufstellungen entspricht 1 entzerrtes Pixel etwa 1 nativen Pixel).
  - `dot_centers(grid: CharGrid, cell: int, shift: tuple[int, int] = (0, 0)) -> np.ndarray` Form `(40, 2)` als `(x, y)`.
  - `@dataclass(frozen=True) class SampledImage: raw: np.ndarray` Form `(n_cells, 9, 40)` (Rohhelligkeiten je Zelle je Shift), `background: np.ndarray` Form `(n_cells,)`, `ink: float`, `contrast: float`, `saturated_fraction: float`.
  - `sample_image(gray: np.ndarray, grid: CharGrid, cells: range) -> SampledImage`.
  - `normalized(s: SampledImage) -> np.ndarray` Form `(n_cells, 9, 40)`, Werte in `[0, 1]`, 1 = voll dunkel.
  - `MIN_CONTRAST = 0.08` (unvalidierter Vorabwert, in Stufe 1 überprüft).

- [ ] **Step 1: Failing tests**

```python
# tests/test_dotmatrix_sampling.py
import numpy as np

from dispread.charcells import CharGrid
from dispread.ocr.dotmatrix_font import rom_vector
from dispread.ocr.dotmatrix_sampling import (
    MIN_CONTRAST, SHIFTS, dot_centers, normalized, sample_image,
)

GRID = CharGrid(n_cells=16, left=10.0, pitch=24.0, top=40.0, bottom=120.0)


def render(text: str, grid: CharGrid = GRID, size=(400, 160), bg=200, ink=60, blur=0.0):
    img = np.full((size[1], size[0]), bg, np.float32)
    for i, ch in enumerate(text):
        v = rom_vector(ch)
        for k, (x, y) in enumerate(dot_centers(grid, i)):
            if v[k]:
                r = 1.4
                ys, xs = np.ogrid[: size[1], : size[0]]
                img[(xs - x) ** 2 + (ys - y) ** 2 <= r * r] = ink
    if blur:
        import cv2
        img = cv2.GaussianBlur(img, (0, 0), blur)
    return img.astype(np.uint8)


def test_nine_shifts():
    assert len(SHIFTS) == 9 and (0, 0) in SHIFTS


def test_dot_centers_first_cell():
    c = dot_centers(GRID, 0)
    assert c.shape == (40, 2)
    assert np.allclose(c[0], (10 + 24 / 6 * 0.5, 40 + 80 / 8 * 0.5))


def test_normalized_matches_rom_at_zero_shift():
    img = render("+0.60972 ")
    s = sample_image(img, GRID, range(9))
    n = normalized(s)
    zero = SHIFTS.index((0, 0))
    assert n.shape == (9, 9, 40)
    for i, ch in enumerate("+0.60972 "):
        assert np.abs(n[i, zero] - rom_vector(ch)).max() < 0.35
    assert s.contrast > MIN_CONTRAST


def test_blank_display_has_low_contrast_and_no_nan():
    img = np.full((160, 400), 180, np.uint8)
    s = sample_image(img, GRID, range(9))
    assert s.contrast < MIN_CONTRAST
    assert np.isfinite(normalized(s)).all()


def test_shift_at_image_border_does_not_raise():
    grid = CharGrid(n_cells=16, left=0.0, pitch=25.0, top=0.0, bottom=160.0)
    img = render("+0.60972 ", grid=grid)
    s = sample_image(img, grid, range(9))
    assert s.raw.shape == (9, 9, 40)
```

- [ ] **Step 2:** Tests schlagen fehl (`ModuleNotFoundError`).

- [ ] **Step 3: Implementieren**

```python
# src/dispread/ocr/dotmatrix_sampling.py
"""Punktabtastung fuer den Dot-Matrix-Leser (Spec Abschnitt 2, Schritte 1-4).

Jede Zelle des bestaetigten `CharGrid` hat 5 x 8 Punktmitten. Abgetastet wird
ein gewichteter Mittelwert um jede Mitte (Gaussfilter, dann bilinear), nicht
ein einzelnes Pixel. Normiert wird je Bild: Hintergrund je Zelle (hellste
Punkte der Zelle), Punktpegel global - so gleicht sich ein Helligkeitsverlauf
ueber das Glas aus (in allen drei Ernte-Aufstellungen war das rechte Drittel
dunkler, VALIDATION.md 2026-09-24).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from dispread.charcells import CharGrid
from dispread.ocr.dotmatrix_font import COLS, N_DOTS, ROWS

SHIFTS: tuple[tuple[int, int], ...] = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
#: Vorabwert, nicht validiert - Stufe 1 prueft ihn (Spec Abschnitt 3).
MIN_CONTRAST = 0.08
#: Gaussbreite als Anteil der Punktspaltenbreite.
_SIGMA_FRACTION = 0.3
#: Anteil der hellsten Punkte einer Zelle, der als Hintergrund gilt.
_BACKGROUND_PERCENTILE = 80.0
_INK_PERCENTILE = 3.0


def dot_centers(grid: CharGrid, cell: int, shift: tuple[int, int] = (0, 0)) -> np.ndarray:
    col_w = grid.pitch / (grid.dot_columns + grid.gap_columns)
    row_h = (grid.bottom - grid.top) / ROWS
    x0 = grid.left + cell * grid.pitch + shift[0]
    y0 = grid.top + shift[1]
    pts = [(x0 + (c + 0.5) * col_w, y0 + (r + 0.5) * row_h) for r in range(ROWS) for c in range(COLS)]
    return np.asarray(pts, dtype=np.float32)


@dataclass(frozen=True)
class SampledImage:
    raw: np.ndarray
    background: np.ndarray
    ink: float
    contrast: float
    saturated_fraction: float


def _bilinear(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    h, w = img.shape
    x = np.clip(pts[:, 0], 0, w - 1.001)
    y = np.clip(pts[:, 1], 0, h - 1.001)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx = x - x0
    fy = y - y0
    a = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    b = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def sample_image(gray: np.ndarray, grid: CharGrid, cells: range) -> SampledImage:
    img = gray.astype(np.float32)
    col_w = grid.pitch / (grid.dot_columns + grid.gap_columns)
    smooth = cv2.GaussianBlur(img, (0, 0), max(0.5, _SIGMA_FRACTION * col_w))
    raw = np.empty((len(cells), len(SHIFTS), N_DOTS), dtype=np.float32)
    for i, cell in enumerate(cells):
        for j, shift in enumerate(SHIFTS):
            raw[i, j] = _bilinear(smooth, dot_centers(grid, cell, shift))
    zero = SHIFTS.index((0, 0))
    background = np.percentile(raw[:, zero, :], _BACKGROUND_PERCENTILE, axis=1)
    ink = float(np.percentile(raw[:, zero, :], _INK_PERCENTILE))
    ref = float(np.median(background))
    contrast = (ref - ink) / ref if ref > 0 else 0.0
    y0, y1 = int(max(0, grid.top)), int(min(img.shape[0], grid.bottom))
    x0 = int(max(0, grid.left))
    x1 = int(min(img.shape[1], grid.left + grid.n_cells * grid.pitch))
    region = gray[y0:y1, x0:x1]
    saturated = float((region >= 250).mean()) if region.size else 0.0
    return SampledImage(raw, background.astype(np.float32), ink, float(max(contrast, 0.0)), saturated)


def normalized(s: SampledImage) -> np.ndarray:
    depth = s.background[:, None, None] - s.ink
    depth = np.where(depth > 1e-3, depth, 1e-3)
    out = (s.background[:, None, None] - s.raw) / depth
    return np.clip(out, 0.0, 1.0).astype(np.float32)
```

- [ ] **Step 4:** Tests grün, ruff sauber.
- [ ] **Step 5:** Bericht mit CHANGELOG-Vorschlag.

---

### Task 3: Vorlagen, Klassifikation, Schwellen, ROM-Gegenprobe

**Files:**
- Create: `src/dispread/ocr/dotmatrix_templates.py`
- Test: `tests/test_dotmatrix_templates.py`

**Interfaces:**
- Consumes: `CLASSES`, `N_DOTS`, `rom_vector` (Task 1).
- Produces:
  - `FORMAT_VERSION = 1`, `THRESHOLD_FORMULA = "thresholds_v1"`, `SIGMA_FLOOR = 0.05`.
  - `@dataclass(frozen=True) class Templates: mean: dict[str, np.ndarray]` (je `(40,)`), `std: dict[str, np.ndarray]`, `d_max: float`, `margin_min: float`, `groups: tuple[str, ...]`, `counts: dict[str, int]`.
  - `distance(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> float` = `sqrt(mean(((x - mean) / max(std, SIGMA_FLOOR))**2))`.
  - `@dataclass(frozen=True) class CellDecision: text: str | None` (`None` = abgelehnt), `best: str`, `second: str`, `d_best: float`, `d_second: float`, `shift_index: int`, `reason: str | None` (`"zelle_unbekannt"` / `"zelle_mehrdeutig"` / `None`), `margin: float`.
  - `classify(vectors: np.ndarray, t: Templates) -> CellDecision` — `vectors` Form `(9, 40)` (alle Shifts einer Zelle); je Klasse der kleinste Abstand über alle Shifts; `margin = min(t.d_max - d_best, (d_second - d_best) - t.margin_min)`.
  - `fit_templates(samples: dict[str, list[np.ndarray]], groups: tuple[str, ...]) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]` — `samples[ch]` = Liste von `(9, 40)`; je Probe wird der Shift gewählt, der dem **ROM-Muster des gelabelten Zeichens** am nächsten liegt (euklidisch), dann Mittelwert und Streuung.
  - `rom_check(mean: dict[str, np.ndarray]) -> list[str]` — Zeichen, deren bei 0.5 binarisierte Vorlage vom ROM-Muster abweicht; leer = bestanden.
  - `compute_thresholds(samples, mean, std) -> tuple[float, float]` nach `thresholds_v1`.
  - `build_templates(samples, groups) -> Templates` — wirft `ValueError` mit Liste der Zeichen, wenn `rom_check` nicht leer ist oder eine Klasse fehlt.
  - `save_templates(t: Templates, path: Path) -> str` (gibt SHA-256 der Datei zurück), `load_templates(path: Path, expected_sha256: str | None = None) -> Templates` — wirft `ValueError` bei falscher `format_version`, falscher `threshold_formula`, fehlender Klasse oder abweichender Prüfsumme.

- [ ] **Step 1: Failing tests**

```python
# tests/test_dotmatrix_templates.py
import json

import numpy as np
import pytest

from dispread.ocr.dotmatrix_font import CLASSES, rom_vector
from dispread.ocr.dotmatrix_templates import (
    build_templates, classify, compute_thresholds, fit_templates, load_templates,
    rom_check, save_templates,
)

ZERO = 4  # SHIFTS.index((0, 0))


def noisy(ch, rng, n=20, noise=0.08):
    out = []
    for _ in range(n):
        v = np.tile(rom_vector(ch) * 0.9 + 0.05, (9, 1))
        v += rng.normal(0, 0.25, v.shape)  # falsche Shifts: verrauscht
        v[ZERO] = np.clip(rom_vector(ch) * 0.9 + 0.05 + rng.normal(0, noise, 40), 0, 1)
        out.append(v.astype(np.float32))
    return out


@pytest.fixture
def samples():
    rng = np.random.default_rng(1)
    return {ch: noisy(ch, rng) for ch in CLASSES}


def test_build_and_classify_roundtrip(samples):
    t = build_templates(samples, ("g1",))
    rng = np.random.default_rng(2)
    for ch in CLASSES:
        d = classify(noisy(ch, rng, n=1)[0], t)
        assert d.text == ch, (ch, d)


def test_random_pattern_is_rejected(samples):
    t = build_templates(samples, ("g1",))
    rng = np.random.default_rng(3)
    x = np.tile(rng.uniform(0, 1, 40).astype(np.float32), (9, 1))
    d = classify(x, t)
    assert d.text is None and d.reason == "zelle_unbekannt"


def test_blend_8_0_is_ambiguous(samples):
    t = build_templates(samples, ("g1",))
    x = np.tile(((rom_vector("8") + rom_vector("0")) / 2 * 0.9 + 0.05).astype(np.float32), (9, 1))
    d = classify(x, t)
    assert d.text is None and d.reason in ("zelle_mehrdeutig", "zelle_unbekannt")
    assert {d.best, d.second} == {"8", "0"} or d.reason == "zelle_unbekannt"


def test_rom_check_catches_mislabeled_class(samples):
    bad = dict(samples)
    bad["7"] = samples["1"]
    with pytest.raises(ValueError, match="7"):
        build_templates(bad, ("g1",))


def test_missing_class_raises(samples):
    s = dict(samples)
    del s["."]
    with pytest.raises(ValueError, match=r"\."):
        build_templates(s, ("g1",))


def test_thresholds_deterministic(samples):
    mean, std = fit_templates(samples, ("g1",))
    assert compute_thresholds(samples, mean, std) == compute_thresholds(samples, mean, std)


def test_save_load_checksum_and_version(tmp_path, samples):
    t = build_templates(samples, ("g1", "g2"))
    p = tmp_path / "templates.json"
    sha = save_templates(t, p)
    t2 = load_templates(p, expected_sha256=sha)
    assert t2.groups == ("g1", "g2") and t2.d_max == t.d_max
    with pytest.raises(ValueError, match="Pruefsumme"):
        load_templates(p, expected_sha256="0" * 64)
    data = json.loads(p.read_text())
    data["threshold_formula"] = "thresholds_v0"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="thresholds_v0"):
        load_templates(p)
    data["threshold_formula"] = "thresholds_v1"
    del data["mean"]["."]
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Klasse"):
        load_templates(p)


def test_rom_check_passes_on_rom():
    assert rom_check({ch: rom_vector(ch) for ch in CLASSES}) == []
```

- [ ] **Step 2:** Tests schlagen fehl.

- [ ] **Step 3: Implementieren**

```python
# src/dispread/ocr/dotmatrix_templates.py
"""Vorlagen, Zellentscheidung und Schwellen des Dot-Matrix-Lesers.

Spec Abschnitt 2 (Schritte 5-6) und Abschnitt 3 (Formel `thresholds_v1`).
Die Vorlagen entstehen offline und werden eingefroren; im Betrieb wird nichts
nachgelernt. `margin` ist ein Beleg, keine Fehlerwahrscheinlichkeit
(Konzept.md §7).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from dispread.ocr.dotmatrix_font import CLASSES, N_DOTS, rom_vector

FORMAT_VERSION = 1
THRESHOLD_FORMULA = "thresholds_v1"
SIGMA_FLOOR = 0.05


@dataclass(frozen=True)
class Templates:
    mean: dict[str, np.ndarray]
    std: dict[str, np.ndarray]
    d_max: float
    margin_min: float
    groups: tuple[str, ...]
    counts: dict[str, int]


@dataclass(frozen=True)
class CellDecision:
    text: str | None
    best: str
    second: str
    d_best: float
    d_second: float
    shift_index: int
    reason: str | None
    margin: float


def distance(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> float:
    return float(np.sqrt(np.mean(((x - mean) / np.maximum(std, SIGMA_FLOOR)) ** 2)))


def _best_per_class(vectors: np.ndarray, mean, std) -> dict[str, tuple[float, int]]:
    out = {}
    for ch in mean:
        ds = [distance(v, mean[ch], std[ch]) for v in vectors]
        j = int(np.argmin(ds))
        out[ch] = (ds[j], j)
    return out


def _decide(vectors, mean, std, d_max, margin_min) -> CellDecision:
    per = _best_per_class(vectors, mean, std)
    order = sorted(per, key=lambda c: per[c][0])
    best, second = order[0], order[1]
    d_best, j = per[best]
    d_second = per[second][0]
    gap = d_second - d_best
    margin = min(d_max - d_best, gap - margin_min)
    reason = None
    if d_best > d_max:
        reason = "zelle_unbekannt"
    elif gap < margin_min:
        reason = "zelle_mehrdeutig"
    return CellDecision(None if reason else best, best, second, d_best, d_second, j, reason, float(margin))


def classify(vectors: np.ndarray, t: Templates) -> CellDecision:
    return _decide(vectors, t.mean, t.std, t.d_max, t.margin_min)


def _require_classes(keys) -> None:
    missing = [c for c in CLASSES if c not in keys]
    if missing:
        raise ValueError(f"Klasse(n) ohne Daten: {missing!r}")


def fit_templates(samples: dict[str, list[np.ndarray]], groups: tuple[str, ...]):
    _require_classes([c for c in samples if samples[c]])
    mean, std = {}, {}
    for ch in CLASSES:
        rom = rom_vector(ch)
        chosen = [v[int(np.argmin(np.linalg.norm(v - rom, axis=1)))] for v in samples[ch]]
        arr = np.stack(chosen)
        mean[ch] = arr.mean(axis=0).astype(np.float32)
        std[ch] = arr.std(axis=0).astype(np.float32)
    return mean, std


def rom_check(mean: dict[str, np.ndarray]) -> list[str]:
    return [ch for ch in CLASSES if not np.array_equal(mean[ch] >= 0.5, rom_vector(ch) >= 0.5)]


def compute_thresholds(samples, mean, std) -> tuple[float, float]:
    correct_d, correct_gap, wrong_gap = [], [], []
    for ch in CLASSES:
        for v in samples[ch]:
            per = _best_per_class(v, mean, std)
            order = sorted(per, key=lambda c: per[c][0])
            gap = per[order[1]][0] - per[order[0]][0]
            if order[0] == ch:
                correct_d.append(per[ch][0])
                correct_gap.append(gap)
            else:
                wrong_gap.append(gap)
    d_max = 1.25 * float(np.percentile(correct_d, 99.5))
    margin_min = max(0.2 * float(np.median(correct_gap)), 1.25 * max(wrong_gap, default=0.0))
    return d_max, margin_min


def build_templates(samples, groups: tuple[str, ...]) -> Templates:
    mean, std = fit_templates(samples, groups)
    bad = rom_check(mean)
    if bad:
        raise ValueError(f"ROM-Gegenprobe gescheitert fuer {bad!r} - Labels oder Raster pruefen")
    d_max, margin_min = compute_thresholds(samples, mean, std)
    return Templates(mean, std, d_max, margin_min, tuple(groups), {c: len(samples[c]) for c in CLASSES})


def save_templates(t: Templates, path: Path) -> str:
    data = {
        "format_version": FORMAT_VERSION,
        "threshold_formula": THRESHOLD_FORMULA,
        "d_max": t.d_max,
        "margin_min": t.margin_min,
        "groups": list(t.groups),
        "counts": t.counts,
        "mean": {c: [float(x) for x in t.mean[c]] for c in CLASSES},
        "std": {c: [float(x) for x in t.std[c]] for c in CLASSES},
    }
    blob = json.dumps(data, indent=1, sort_keys=True).encode("utf-8")
    Path(path).write_bytes(blob)
    return hashlib.sha256(blob).hexdigest()


def load_templates(path: Path, expected_sha256: str | None = None) -> Templates:
    blob = Path(path).read_bytes()
    if expected_sha256 is not None and hashlib.sha256(blob).hexdigest() != expected_sha256:
        raise ValueError(f"Pruefsumme von {path} weicht ab")
    data = json.loads(blob)
    if data.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"format_version {data.get('format_version')!r} statt {FORMAT_VERSION}")
    if data.get("threshold_formula") != THRESHOLD_FORMULA:
        raise ValueError(f"threshold_formula {data.get('threshold_formula')!r} statt {THRESHOLD_FORMULA}")
    for key in ("mean", "std"):
        _require_classes(data[key])
        for c in CLASSES:
            if len(data[key][c]) != N_DOTS:
                raise ValueError(f"{key}[{c!r}] hat nicht {N_DOTS} Werte")
    return Templates(
        mean={c: np.asarray(data["mean"][c], np.float32) for c in CLASSES},
        std={c: np.asarray(data["std"][c], np.float32) for c in CLASSES},
        d_max=float(data["d_max"]),
        margin_min=float(data["margin_min"]),
        groups=tuple(data["groups"]),
        counts=dict(data["counts"]),
    )
```

- [ ] **Step 4:** Tests grün, ruff sauber. Kippt `test_blend_8_0_is_ambiguous` wegen der synthetischen Streuung, die Rauschstärke im Test **nicht** anpassen, sondern im Bericht melden.
- [ ] **Step 5:** Bericht mit CHANGELOG-Vorschlag.

---

### Task 4: `CharLayout`, `DotMatrixReader`, Formatregel

**Files:**
- Modify: `src/dispread/layout.py` (am Ende anfügen), `src/dispread/ocr/__init__.py:17,79`
- Create: `src/dispread/ocr/dotmatrix.py`
- Test: `tests/test_dotmatrix_reader.py`

**Interfaces:**
- Consumes: Tasks 1–3; `CharGrid`.
- Produces:
  - In `layout.py`: `@dataclass(frozen=True, slots=True) class CharLayout: grid: CharGrid; unit: str; format_id: str = "gsv2as_v1"; classified_cells: int = 9`. Import von `CharGrid` in `layout.py` nur unter `TYPE_CHECKING` plus `from __future__ import annotations`, falls ein Importzyklus auftritt (prüfen: `python -c "import dispread.ocr"`).
  - `ValueReader.read(self, crop: np.ndarray, layout: DisplayLayout | CharLayout) -> ReadResult`.
  - In `dotmatrix.py`: `BACKEND_ID = "dotmatrix"`, `BACKEND_VERSION = "1"`, `parse_gsv2as(cells: str) -> tuple[str, float] | None` (9 Zeichen → `(raw_text, value)` oder `None` bei Formatverletzung), `class DotMatrixReader(templates: Templates)` mit `read(crop, layout: CharLayout) -> ReadResult`, `backend_id`, `declares_confidence_calibrated = False`, Klassenmethode `from_file(path: Path, expected_sha256: str | None = None)`.
  - `ReadResult.diagnostics` enthält: `contrast` (float), `min_margin` (kleinster Zellen-`margin`, bei Ablehnung ≤ 0 möglich), `unreadable_cells` (int), `reject_reason` (`str | None`, einer von `zelle_unbekannt`, `zelle_mehrdeutig`, `kontrast`, `ueberbelichtet`, `format`, `vorzeichen`), `cells` (Liste von 9 Dicts `{"best", "second", "d_best", "d_second", "margin", "dots"}` mit `dots` = 40 gerundete Werte beim gewählten Shift), `templates_groups`.
  - `MAX_SATURATED = 0.02` (Anteil gesättigter Pixel im Rasterbereich; Vorabwert).
  - `decimal_point_index` folgt `DisplayLayout.decimal_point_index()` („nach welcher Ziffernstelle"): gezählt über die 6 Stellen von Zelle 1–7, Leerzellen zählen als Stelle (`"+  988.5"` → 4).

- [ ] **Step 1: Failing tests**

```python
# tests/test_dotmatrix_reader.py
import numpy as np
import pytest

from dispread.charcells import CharGrid
from dispread.layout import CharLayout
from dispread.ocr import ValueReader
from dispread.ocr.dotmatrix import DotMatrixReader, parse_gsv2as
from dispread.ocr.dotmatrix_font import CLASSES
from dispread.ocr.dotmatrix_sampling import normalized, sample_image
from dispread.ocr.dotmatrix_templates import build_templates
from dotmatrix_helpers import GRID, render

LAYOUT = CharLayout(grid=GRID, unit="mV/V")
TRAIN_TEXTS = ["+0.60972 ", "+ 1.2345 ", "+ 67.890 ", "+  988.5 ", "+ 3456.7 ", "+0.11111 "]


@pytest.fixture(scope="module")
def reader():
    rng = np.random.default_rng(7)
    samples = {c: [] for c in CLASSES}
    for text in TRAIN_TEXTS * 6:
        img = render(text, blur=rng.uniform(0.3, 1.0))
        img = np.clip(img + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
        n = normalized(sample_image(img, GRID, range(9)))
        for i, ch in enumerate(text):
            samples[ch].append(n[i])
    return DotMatrixReader(build_templates(samples, ("synthetisch",)))


@pytest.mark.parametrize("cells,expected", [
    ("+0.60972 ", ("+0.60972", 0.60972)),
    ("+ 909.09 ", ("+909.09", 909.09)),
    ("+  988.5 ", ("+988.5", 988.5)),
])
def test_parse_ok(cells, expected):
    assert parse_gsv2as(cells) == expected


@pytest.mark.parametrize("cells", [
    "+   88.5 ",   # drei Leerzellen
    "+0.6.972 ",   # zwei Punkte
    "+0 60972 ",   # Leerzelle mitten in der Zahl
    "+06097211",   # kein Punkt, Zelle 8 nicht leer
    "+ 12.34  ",   # nur 5 Ziffern
    " 0.60972 ",   # kein Vorzeichen
    "+ .12345 ",   # Leerzelle direkt vor dem Punkt
])
def test_parse_rejects(cells):
    assert parse_gsv2as(cells) is None


def test_is_value_reader(reader):
    assert isinstance(reader, ValueReader)
    assert reader.backend_id == "dotmatrix"
    assert reader.declares_confidence_calibrated is False


@pytest.mark.parametrize("text,value", [("+ 1.2345 ", 1.2345), ("+  988.5 ", 988.5)])
def test_reads_value(reader, text, value):
    r = reader.read(render(text), LAYOUT)
    assert r.value == value and r.unit_text == "mV/V"
    assert r.sign_region_readable and not r.sign_detected
    assert r.decimal_point_detected and r.diagnostics["reject_reason"] is None


def test_grayscale_and_color_same(reader):
    g = render("+ 67.890 ")
    c = np.dstack([g, g, g])
    assert reader.read(g, LAYOUT).value == reader.read(c, LAYOUT).value == 67.89


def test_minus_is_rejected(reader):
    r = reader.read(render("- 1.2345 "), LAYOUT)
    assert r.value is None and not r.sign_region_readable
    assert r.diagnostics["reject_reason"] in ("vorzeichen", "zelle_unbekannt")


def test_blank_display_rejected_as_contrast(reader):
    r = reader.read(np.full((160, 400), 190, np.uint8), LAYOUT)
    assert r.value is None and r.diagnostics["reject_reason"] == "kontrast"


def test_saturated_rejected(reader):
    img = render("+ 1.2345 ")
    img[40:120, 10:200] = 255
    r = reader.read(img, LAYOUT)
    assert r.value is None and r.diagnostics["reject_reason"] == "ueberbelichtet"


def test_unknown_glyph_rejected(reader):
    r = reader.read(render("+ 1.2°45 "), LAYOUT)
    assert r.value is None
    assert r.diagnostics["reject_reason"] in ("zelle_unbekannt", "zelle_mehrdeutig")
```

Der Test `render("+ 1.2°45 ")` funktioniert, weil `render` `rom_vector` nutzt und `ROM_A00` `°` kennt.

- [ ] **Step 2:** Tests schlagen fehl.

- [ ] **Step 3: Implementieren**

`src/dispread/layout.py` (anfügen):

```python
@dataclass(frozen=True, slots=True)
class CharLayout:
    """Bestaetigtes Profil einer Punktraster-Anzeige fuer `DotMatrixReader`.

    `grid` stammt aus dem vom Bediener bestaetigten `SessionProfile`
    (Ernte Phase 1, Entscheidung 2), `unit` aus dem Profil - gelesen wird sie
    nicht (OQ-17). `classified_cells` = Vorzeichen + Zahlenblock + Trennzelle.
    """

    grid: CharGrid
    unit: str
    format_id: str = "gsv2as_v1"
    classified_cells: int = 9
```

mit `from dispread.charcells import CharGrid` (oder unter `TYPE_CHECKING`, siehe Interfaces).

`src/dispread/ocr/__init__.py`: Import auf `from dispread.layout import CharLayout, DisplayLayout` erweitern, Signatur `def read(self, crop: np.ndarray, layout: DisplayLayout | CharLayout) -> ReadResult: ...`.

`src/dispread/ocr/dotmatrix.py`:

```python
"""Dot-Matrix-Leser fuer die GSV-2AS-Anzeige (Displaytech 161A, HD44780).

Spec: docs/superpowers/specs/2026-09-24-dotmatrix-reader-design.md. Liest
Zellen 0-8 gegen eingefrorene Vorlagen, lehnt im Zweifel ab und prueft den
ganzen Wert gegen die Formatregel `gsv2as_v1`. Negative Werte werden nie
ausgegeben: es gibt kein einziges Beispiel (Firmware 1.3.07), also kennt der
Leser nur `+`.
"""

from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np

from dispread.layout import CharLayout
from dispread.ocr import GlyphEvidence, ReadResult
from dispread.ocr.dotmatrix_sampling import MIN_CONTRAST, normalized, sample_image
from dispread.ocr.dotmatrix_templates import Templates, classify, load_templates

BACKEND_ID = "dotmatrix"
BACKEND_VERSION = "1"
MAX_SATURATED = 0.02

# Zellen 1-7: 0-2 Leerzellen, dann 6 Ziffern mit genau einem Punkt, die Ziffer
# vor dem Punkt ist nie leer (OQ-41, gsv2as_leading_zero_v2); Zelle 8 leer.
_NUMBER = re.compile(r"^( {0,2})(\d[\d.]*)$")


def parse_gsv2as(cells: str) -> tuple[str, float] | None:
    if len(cells) != 9 or cells[0] != "+" or cells[8] != " ":
        return None
    m = _NUMBER.match(cells[1:8])
    if m is None:
        return None
    body = m.group(2)
    if body.count(".") != 1 or body.startswith(".") or body.endswith("."):
        return None
    if sum(ch.isdigit() for ch in body) + len(m.group(1)) != 6:
        return None
    raw = "+" + body
    return raw, float(body)


class DotMatrixReader:
    def __init__(self, templates: Templates) -> None:
        self._t = templates

    @classmethod
    def from_file(cls, path: Path, expected_sha256: str | None = None) -> DotMatrixReader:
        return cls(load_templates(path, expected_sha256))

    @property
    def backend_id(self) -> str:
        return BACKEND_ID

    @property
    def declares_confidence_calibrated(self) -> bool:
        return False

    def read(self, crop: np.ndarray, layout: CharLayout) -> ReadResult:
        gray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        cells = range(layout.classified_cells)
        sampled = sample_image(gray, layout.grid, cells)
        diag: dict = {
            "contrast": sampled.contrast,
            "saturated_fraction": sampled.saturated_fraction,
            "templates_groups": list(self._t.groups),
            "format_id": layout.format_id,
        }
        if sampled.saturated_fraction > MAX_SATURATED:
            return self._reject("ueberbelichtet", diag, layout)
        if sampled.contrast < MIN_CONTRAST:
            return self._reject("kontrast", diag, layout)

        norm = normalized(sampled)
        decisions = [classify(norm[i], self._t) for i in range(len(cells))]
        diag["cells"] = [
            {
                "best": d.best, "second": d.second, "d_best": round(d.d_best, 4),
                "d_second": round(d.d_second, 4), "margin": round(d.margin, 4),
                "dots": [round(float(x), 3) for x in norm[i, d.shift_index]],
            }
            for i, d in enumerate(decisions)
        ]
        diag["min_margin"] = min(d.margin for d in decisions)
        diag["unreadable_cells"] = sum(d.text is None for d in decisions)
        glyphs = tuple(
            GlyphEvidence(
                text=d.text if d.text is not None else "?",
                confidence=0.0,
                segments=None,
                ambiguous_with=(d.second,) if d.reason == "zelle_mehrdeutig" else (),
                margin=d.margin,
            )
            for d in decisions
        )
        first_reject = next((d.reason for d in decisions if d.reason), None)
        sign_ok = decisions[0].text == "+"
        if not sign_ok:
            reason = first_reject if decisions[0].text is None else "vorzeichen"
            return self._reject(reason, diag, layout, glyphs, sign_readable=False)
        if first_reject:
            return self._reject(first_reject, diag, layout, glyphs)
        cells_text = "".join(d.text for d in decisions)
        parsed = parse_gsv2as(cells_text)
        if parsed is None:
            return self._reject("format", diag, layout, glyphs)
        raw, value = parsed
        diag["reject_reason"] = None
        return ReadResult(
            raw_text=raw, value=value, sign_detected=False, sign_region_readable=True,
            decimal_point_detected=True, decimal_point_index=cells_text[1:8].index(".") - 1,
            unit_text=layout.unit, status_flags=frozenset(), glyphs=glyphs,
            backend_id=BACKEND_ID, backend_version=BACKEND_VERSION, diagnostics=diag,
        )

    def _reject(self, reason, diag, layout, glyphs=(), sign_readable=True) -> ReadResult:
        diag["reject_reason"] = reason
        diag.setdefault("min_margin", 0.0)
        diag.setdefault("unreadable_cells", layout.classified_cells)
        return ReadResult(
            raw_text="", value=None, sign_detected=False, sign_region_readable=sign_readable,
            decimal_point_detected=False, decimal_point_index=None, unit_text=layout.unit,
            status_flags=frozenset({"glare"}) if reason == "ueberbelichtet" else frozenset(),
            glyphs=tuple(glyphs), backend_id=BACKEND_ID, backend_version=BACKEND_VERSION,
            diagnostics=diag,
        )
```

- [ ] **Step 4:** Tests grün; volle Suite grün (bestehende `sevenseg`/`tesseract_cli`-Tests unverändert); ruff sauber. `python -c "import dispread.ocr.dotmatrix"` ohne Importzyklus.
- [ ] **Step 5:** Bericht mit CHANGELOG-Vorschlag.

---

### Task 5: Freigabeschwellen je Leser

**Files:**
- Modify: `src/dispread/validate.py` (nach `GateConfig`)
- Test: `tests/test_gate_config.py`

**Interfaces:**
- Produces: `default_gate_config(backend_id: str, **overrides) -> GateConfig`. `"sevenseg"` und `"tesseract_cli"` → `GateConfig(**overrides)` (unverändert). `"dotmatrix"` → `GateConfig(min_margin=0.0, min_contrast=0.0, **overrides)`: der Leser wendet seine eingefrorenen, gemessenen Schwellen (`d_max`, `margin_min`, `MIN_CONTRAST`) bereits selbst an und lehnt dann ab; die Freigabe prüft zusätzlich `unreadable_cells`, Vorzeichen, Dezimalpunkt, Einheit, Zustände und Mehrbildbestätigung. Unbekannte `backend_id` → `ValueError`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_gate_config.py
import pytest

from dispread.validate import GateConfig, default_gate_config


def test_sevenseg_unchanged():
    assert default_gate_config("sevenseg") == GateConfig()
    assert default_gate_config("sevenseg", confirm_frames=3).confirm_frames == 3


def test_dotmatrix_relies_on_reader_thresholds():
    cfg = default_gate_config("dotmatrix", expected_unit="mV/V")
    assert cfg.min_margin == 0.0 and cfg.min_contrast == 0.0
    assert cfg.expected_unit == "mV/V"


def test_unknown_backend():
    with pytest.raises(ValueError):
        default_gate_config("foo")
```

- [ ] **Step 2:** Tests schlagen fehl.
- [ ] **Step 3: Implementieren**

```python
_READER_OWN_THRESHOLDS = frozenset({"dotmatrix"})
_KNOWN_BACKENDS = frozenset({"sevenseg", "tesseract_cli"}) | _READER_OWN_THRESHOLDS


def default_gate_config(backend_id: str, **overrides) -> GateConfig:
    """Freigabeschwellen je Leser.

    `min_margin`/`min_contrast` sind auf die 7-Segment-Kennzahlen geeicht. Der
    Dot-Matrix-Leser wendet seine eingefrorenen Schwellen (templates.json,
    Formel thresholds_v1) selbst an und lehnt ab - hier doppelt zu schwellen,
    wuerde eine zweite, ungemessene Grenze einfuehren.
    """
    if backend_id not in _KNOWN_BACKENDS:
        raise ValueError(f"unbekannter Leser {backend_id!r}")
    if backend_id in _READER_OWN_THRESHOLDS:
        overrides = {"min_margin": 0.0, "min_contrast": 0.0, **overrides}
    return GateConfig(**overrides)
```

- [ ] **Step 4:** Test grün, volle Suite grün, ruff sauber.
- [ ] **Step 5:** Bericht mit CHANGELOG-Vorschlag.

---

### Task 6: Nachverfolgbarkeit und Datensatz-Lader

**Files:**
- Modify: `scripts/import-harvest.py` (Block `detail.update({...})`, ca. Zeile 529–539; Parser um `--harvest-run-id` nicht nötig — die Lauf-Kennung ist `Path(args.harvest).name`)
- Create: `scripts/dotmatrix-dataset.py`
- Test: `tests/test_dotmatrix_dataset.py`, Ergänzung in `tests/test_import_harvest.py`

**Interfaces:**
- Consumes: `SessionProfile.load`, `rectify`, `sample_image`, `normalized`, `CLASSES`.
- Produces in `import-harvest.py`: `label_origin_detail` erhält zusätzlich `profile_sha256` (SHA-256 der Profildatei), `profile_quad` (JSON-String der 4 Ecken, auf 2 Nachkommastellen), `profile_grid` (JSON-String `CharGrid.to_dict()` plus `"target_size": [w, h]`), `harvest_run` (`Path(args.harvest).name`). Alle Strings ≤ 200 Zeichen (Datensatzregel), sonst `DatasetError`-Zählung wie bisher.
- Produces in `dotmatrix-dataset.py` (als Modul ladbar via `importlib`, wie andere Skripttests):
  - `@dataclass class CellSample: sample_id: str; group: str; plateau: tuple[int, int]; cell_text: str; vectors: np.ndarray` (Form `(9, 9, 40)`).
  - `load_cell_samples(dataset_root: Path, profile_map: dict[str, str]) -> list[CellSample]` — nur `label_origin == "serial_ascii"`, `label_state == "readable"`, Gerät `gsv-sensor-161a` (Name im `devices.json`); Profil aus `label_origin_detail` (`profile_quad`, `profile_grid`) oder, falls fehlend, aus `profile_map[session_id]` (Pfad einer `profile.json`); Gruppe = `label_origin_detail["session_id"]`; Bild = `samples/<id>/image.png`, `rectify(image, quad, target_size=...)`, dann `normalized(sample_image(gray, grid, range(9)))`. Proben ohne auflösbares Profil werden gezählt und übersprungen, nie geraten.
  - CLI `write-map --out var/diagnostics/dotmatrix-profile-map.json` schreibt `{"ernte1": "var/diagnostics/ernte1-profile/profile.json", "auf2": "...", "auf3": "..."}` samt SHA-256 je Profil (`{"session_id": {"path": ..., "sha256": ...}}`), `profile_map` liest dieses Format.

- [ ] **Step 1: Failing tests** — `tests/test_dotmatrix_dataset.py` baut in `tmp_path` einen Mini-Datensatz: `devices.json` mit einem Gerät `{"name": "gsv-sensor-161a", ...}`, zwei Proben (`samples/<id>/sample.json` + `image.png` aus `render("+0.60972 ")` aus `tests/dotmatrix_helpers.py`, eingebettet in ein 960×720-Bild an bekanntem Quad), eine mit `profile_quad`/`profile_grid` im Detail, eine nur mit `session_id` und Eintrag in `profile_map`, eine dritte ohne beides. Erwartet: 2 `CellSample`, `cell_text == "+0.60972 "`, `vectors.shape == (9, 9, 40)`, Zähler „ohne Profil" = 1. In `tests/test_import_harvest.py`: der bestehende End-zu-End-Test prüft zusätzlich, dass `profile_sha256`, `profile_quad`, `profile_grid`, `harvest_run` im gespeicherten `label_origin_detail` stehen und `json.loads(profile_grid)["pitch"]` dem Profil entspricht.
- [ ] **Step 2:** Tests schlagen fehl.
- [ ] **Step 3:** Implementieren wie in den Interfaces beschrieben. `cell_text` hat 16 Zeichen; verwendet werden `cell_text[:9]`.
- [ ] **Step 4:** Tests grün, volle Suite grün, ruff sauber.
- [ ] **Step 5:** Bericht mit CHANGELOG-Vorschlag.

---

### Task 7: Training und Entwicklungsmessung (Stufe 1)

**Files:**
- Create: `scripts/dotmatrix-train.py`, `scripts/dotmatrix-eval.py`
- Test: `tests/test_dotmatrix_train_eval.py`

**Interfaces:**
- Consumes: `load_cell_samples` (Task 6), `build_templates`, `save_templates` (Task 3), `classify` (Task 3), `parse_gsv2as` (Task 4).
- Produces:
  - `dotmatrix-train.py --dataset-root DIR --profile-map FILE --groups g1,g2 --out templates.json` → schreibt Vorlagen, gibt SHA-256, `d_max`, `margin_min`, Zählungen je Klasse und bei ROM-Abweichung die binarisierten gelernten Muster neben dem ROM-Muster aus (Exit 3, keine Datei).
  - Funktion `evaluate(samples: list[CellSample], t: Templates) -> dict` in `dotmatrix-eval.py`: je Probe alle 9 Zellen klassifizieren (Kontrast/Überbelichtung wie im Leser, über die gespeicherten Vektoren nicht prüfbar → **nur Zellentscheid und Format**, im Bericht so benannt), Ergebnis je Probe `richtig` / `falsch` / `abgelehnt:<grund>`; Summen, Verwechslungsmatrix je Zeichen (`dict[str, dict[str, int]]`), Zahl der Plateaus gesamt und je Ergebnis (ein Plateau gilt als `falsch`, sobald eine seiner Proben falsch freigegeben wurde).
  - `dotmatrix-eval.py loo --dataset-root DIR --profile-map FILE --out report.json`: für jede Gruppe G: `build_templates` auf allen anderen Gruppen, `evaluate` auf G; Bericht mit `groups`, je Durchgang `train_groups`, `test_group`, `d_max`, `margin_min`, `summary`, `confusion`, `plateaus`, dazu `label_origin_counts`, `"vorzeichen": "ungeprueft (nur +)"`, `"threshold_formula": "thresholds_v1"`, Git-Commit (`git rev-parse HEAD`).
  - Zusätzlich `dotmatrix-eval.py reader-check --dataset-root DIR --profile-map FILE --templates FILE --limit N`: liest N echte Proben über den kompletten `DotMatrixReader.read()` (mit Kontrast- und Sättigungsprüfung) und vergleicht mit `evaluate` — belegt, dass Leser und Messung dasselbe entscheiden.
- [ ] **Step 1: Failing tests** — mit einem synthetischen Datensatz aus den Helfern aus `tests/dotmatrix_helpers.py`, drei Gruppen: (a) `loo` erzeugt drei Durchgänge, und die Schwellen des Durchgangs mit Testgruppe G ändern sich nicht, wenn man die Proben von G verändert (Leckagetest: Proben von G durch Rauschen ersetzen, `d_max`/`margin_min` identisch); (b) eine absichtlich falsch gelabelte Probe in einer Trainingsgruppe (Label `7` auf einem `1`-Bild, 60 % der `7`-Proben) lässt `dotmatrix-train.py` mit Exit 3 enden; (c) eine Testprobe mit Label, das vom Bild abweicht, erscheint in `evaluate` als `falsch` und macht ihr Plateau `falsch`.
- [ ] **Step 2:** Tests schlagen fehl.
- [ ] **Step 3:** Implementieren.
- [ ] **Step 4:** Tests grün, volle Suite grün, ruff sauber.
- [ ] **Step 5:** Bericht mit CHANGELOG-Vorschlag.

---

### Task 8 (Orchestrator): Stufe 1 laufen lassen und dokumentieren

- [ ] `scripts/dotmatrix-dataset.py write-map --out var/diagnostics/dotmatrix-profile-map.json`.
- [ ] `scripts/dotmatrix-eval.py loo ... --out var/diagnostics/dotmatrix-stufe1/report.json`; `reader-check` mit Vorlagen aus allen drei Gruppen auf 30 Proben.
- [ ] Bei ROM-Abweichung: gelernte Muster gegen die Bilder prüfen, nicht die Tabelle anpassen, ohne einen Glasbeleg zu zeigen; Befund dem Nutzer vorlegen.
- [ ] Ergebnis dem Nutzer zeigen: je Durchgang richtig/falsch/abgelehnt, Plateaus, Verwechslungen. Nachbesserungen an Abtastung/Normierung nur mit Doku (Spec Abschnitt 3).
- [ ] Doku: VALIDATION (Stufe 1), lab_journal, CHANGELOG, Spec-Status, `docs/status.md`, `TODO.md`. Commit.
- [ ] Vorbereitung Stufe 2 mit dem Nutzer: Einfrieren (Commit, Prüfsumme) vor den neuen Aufstellungen.
