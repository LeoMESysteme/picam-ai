"""Punktabtastung fuer den Dot-Matrix-Leser (Spec Abschnitt 2, Schritte 1-4).

Jede Zelle des bestaetigten `CharGrid` hat 5 x 8 Punktmitten. Abgetastet wird
ein gewichteter Mittelwert um jede Mitte (Gaussfilter, dann bilinear), nicht
ein einzelnes Pixel. Normiert wird je Bild: Hintergrund je Zelle (hellste
Punkte der Zelle), Punktpegel global gemessen, aber je Zelle multiplikativ
mit dem Hintergrund dieser Zelle skaliert (`ink_zelle = ink_global *
background_zelle / median(background)`) - so gleicht sich ein
Helligkeitsverlauf ueber das Glas aus, der wie eine ungleichmaessige
Hintergrundbeleuchtung multiplikativ wirkt, nicht additiv (in allen drei
Ernte-Aufstellungen war das rechte Drittel dunkler, VALIDATION.md
2026-09-24).

Seit `ink_per_cell_v1` (2026-09-29) ist auch die Punkttiefe nicht mehr
global: Die relative Tiefe `(Hintergrund - Punkt) / Hintergrund` wird je
Zelle gemessen und als Gerade ueber die Zellposition angepasst. Anlass:
In der Aufstellung `sc3` faellt die Punktschwaerze eines LCD mit dem
Blickwinkel ueber die Zeile ab (normierte An-Punkte 0,99 links bis 0,68
rechts, VALIDATION.md 2026-09-29). Das wirkt nicht multiplikativ mit dem
Hintergrund und wurde vom globalen Pegel nicht ausgeglichen.

Seit `bg_closing_v1` (2026-09-29) gibt es den Hintergrund zusaetzlich je
Punkt: eine Grauwert-Schliessung (erst Maximum-, dann Minimumfilter) des
geglaetteten Bildes mit einem Rechteck von +-1,5 Punktspalten und
+-1,5 Punktzeilen entfernt Punkte und Striche (hoechstens 2 Punkte breit)
und laesst Helligkeitsverlaeufe stehen, die groesser sind. Anlass: In der
Abnahme-Aufstellung `ab2` lief der weiche Rand einer Glasspiegelung durch
die Leerzelle 8; der Hintergrund je Zelle kam aus dem hellen Teil, der
dunkle Teil las sich als Punktmuster (bis 0,88, VALIDATION.md 2026-09-29).
Die relative Punkttiefe je Zelle (`ink_per_cell_v1`) bleibt, sie wird nur
mit dem Hintergrund des einzelnen Punkts statt der Zelle multipliziert.

Seit `bg_closing_shadow_v1` (2026-09-30) werden danach Punktschatten
abgezogen. Schraeg betrachtet wirft jeder An-Punkt einen versetzten
Schatten auf die Rueckschicht der LCD, und der Aus-Punkt daneben wird
dunkler (Abnahme 2: `ab4` 0,34 bei An-Nachbar links, `ab3` 0,22 oben und
links, VALIDATION.md 2026-09-30). Je Bild und ohne Labels wird der Anteil
je Nachbarrichtung geschaetzt (`shadow_coefficients`) und von den
Aus-Punkten abgezogen. An-Punkte und der globale Weg der
Leerzellenpruefung bleiben unveraendert.
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
#: Kennung der Normierung, steht in jeder Vorlagendatei (Vorlagen gelten nur
#: fuer die Normierung, mit der sie gelernt wurden).
NORMALIZATION = "bg_closing_shadow_v1"
#: Halbe Kantenlaenge des Rechtecks der Hintergrund-Schliessung, in
#: Punktspalten bzw. Punktzeilen. Groesser als ein 2 Punkte breiter Strich
#: (der Dezimalpunkt ist 2 x 2), kleiner als ein Spiegelungskeil ueber mehrere
#: Punkte.
_BG_CLOSING_HALF_COLS = 1.5
_BG_CLOSING_HALF_ROWS = 1.5
#: Punktschatten (`bg_closing_shadow_v1`): Ab diesem normierten Wert gilt ein
#: Punkt als an. Schatten liegen gemessen bei hoechstens 0,34 (`ab4`).
_SHADOW_ON_LEVEL = 0.5
#: Obergrenze je Schattenrichtung - ein Schatten dunkler als ein halber Punkt
#: waere von einem An-Punkt nicht mehr zu trennen.
_SHADOW_MAX_ALPHA = 0.5
#: Mindestzahl Aus-Punkte mit An-Nachbar je Richtung, sonst kein Abzug.
_SHADOW_MIN_SAMPLES = 10
#: Die 8 Nachbarrichtungen (dy, dx) in der 5x7-Zelle.
SHADOW_DIRECTIONS: tuple[tuple[int, int], ...] = tuple(
    (dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy, dx) != (0, 0)
)
#: Eine Zelle zaehlt fuer den Tiefenverlauf, wenn ihre eigene relative Tiefe
#: mindestens diesen Anteil der globalen erreicht UND mindestens
#: `MIN_CONTRAST` betraegt (Zellen mit Zeichen, keine Leerzellen - die
#: absolute Untergrenze verhindert, dass bei kleinem globalem Pegel reine
#: Rauschzellen mitzaehlen, Reviewbefund 2026-09-29).
_INKED_CELL_FRACTION = 0.5
#: Mindestzahl Zellen mit Zeichen fuer die Anpassung, sonst globaler Pegel.
_MIN_INKED_CELLS = 3
#: Rang des dunkelsten Punkts, der als Punktpegel der Zelle gilt (0 = der
#: dunkelste; 1 = der zweitdunkelste, robust gegen ein einzelnes Rauschpixel).
_CELL_INK_RANK = 1


def dot_centers(grid: CharGrid, cell: int, shift: tuple[int, int] = (0, 0)) -> np.ndarray:
    """Punktmitten einer Zelle im entzerrten Bild, Form (40, 2) als (x, y)."""
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
    #: Hintergrund je Punkt und Verschiebung, Form wie `raw`
    #: (`bg_closing_v1`); `None` heisst: Hintergrund je Zelle (`background`).
    background_dots: np.ndarray | None = None


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


def sample_image(gray: np.ndarray, grid: CharGrid, cells: range | tuple[int, ...]) -> SampledImage:
    """Tastet jede Zelle bei allen `SHIFTS` ab (Rohhelligkeiten, ungeglaettet)."""
    img = gray.astype(np.float32)
    col_w = grid.pitch / (grid.dot_columns + grid.gap_columns)
    smooth = cv2.GaussianBlur(img, (0, 0), max(0.5, _SIGMA_FRACTION * col_w))
    row_h = (grid.bottom - grid.top) / ROWS
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (2 * int(round(_BG_CLOSING_HALF_COLS * col_w)) + 1, 2 * int(round(_BG_CLOSING_HALF_ROWS * row_h)) + 1),
    )
    closed = cv2.erode(cv2.dilate(smooth, kernel), kernel)
    raw = np.empty((len(cells), len(SHIFTS), N_DOTS), dtype=np.float32)
    background_dots = np.empty_like(raw)
    for i, cell in enumerate(cells):
        for j, shift in enumerate(SHIFTS):
            centers = dot_centers(grid, cell, shift)
            raw[i, j] = _bilinear(smooth, centers)
            background_dots[i, j] = _bilinear(closed, centers)
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
    return SampledImage(
        raw, background.astype(np.float32), ink, float(max(contrast, 0.0)), saturated, background_dots
    )


def _relative_depth_per_cell(s: SampledImage) -> np.ndarray | None:
    """Relative Punkttiefe je Zelle, oder `None`, wenn weniger als
    `_MIN_INKED_CELLS` Zellen mit Zeichen vorliegen (dann gilt der globale
    Pegel fuer alle Zellen).

    Je Zelle: Tiefe = (Hintergrund - zweitdunkelster Punkt) / Hintergrund bei
    Verschiebung (0, 0). Zellen mit Zeichen (mindestens
    `_INKED_CELL_FRACTION` der globalen Tiefe und mindestens `MIN_CONTRAST`)
    bekommen die Tiefe einer Geraden ueber die Zellposition, angepasst nur an
    diesen Zellen und begrenzt auf [0,5 x kleinste, min(1, 1,5 x groesste)]
    gemessene Tiefe. Zellen ohne Zeichen behalten die globale Tiefe - keine
    Extrapolation auf Leerzellen, damit Rauschen dort nie zu einem
    Punktmuster verstaerkt wird (Reviewbefund 2026-09-29).
    """
    zero = SHIFTS.index((0, 0))
    bg = s.background.astype(np.float64)
    median_bg = float(np.median(bg))
    if median_bg <= 0:
        return None
    global_depth = (median_bg - s.ink) / median_bg
    if global_depth <= 0:
        return None
    dark = np.sort(s.raw[:, zero, :], axis=1)[:, _CELL_INK_RANK].astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        depth = np.where(bg > 0, (bg - dark) / bg, 0.0)
    idx = np.arange(len(bg), dtype=np.float64)
    inked = (depth >= _INKED_CELL_FRACTION * global_depth) & (depth >= MIN_CONTRAST)
    if int(inked.sum()) < _MIN_INKED_CELLS:
        return None
    slope, intercept = np.polyfit(idx[inked], depth[inked], 1)
    lo = 0.5 * float(depth[inked].min())
    hi = min(1.0, 1.5 * float(depth[inked].max()))
    fitted = np.clip(intercept + slope * idx, lo, hi)
    return np.where(inked, fitted, global_depth)


def _on_neighbors(on: np.ndarray) -> np.ndarray:
    """`on` Form (..., 40) als Bool. Ergebnis Form (..., 8, 40): Ist der
    Nachbar in Richtung `SHADOW_DIRECTIONS[k]` innerhalb der 5x7-Zelle an?
    Die leere Cursorzeile 8 zaehlt nicht mit."""
    grid = on.reshape(*on.shape[:-1], ROWS, COLS).copy()
    grid[..., 7:, :] = False
    out = np.zeros((*on.shape[:-1], len(SHADOW_DIRECTIONS), ROWS, COLS), dtype=bool)
    for k, (dy, dx) in enumerate(SHADOW_DIRECTIONS):
        ys = slice(max(0, -dy), ROWS - max(0, dy))
        xs = slice(max(0, -dx), COLS - max(0, dx))
        yn = slice(max(0, dy), ROWS - max(0, -dy))
        xn = slice(max(0, dx), COLS - max(0, -dx))
        out[..., k, ys, xs] = grid[..., yn, xn]
    out[..., 7:, :] = False
    return out.reshape(*on.shape[:-1], len(SHADOW_DIRECTIONS), N_DOTS)


def shadow_coefficients(norm_zero: np.ndarray) -> dict[tuple[int, int], float]:
    """Schattenanteil je Nachbarrichtung aus der unverschobenen Abtastung
    `norm_zero` (Form (Zellen, 40)), ohne Labels: lineare Regression ueber
    alle Aus-Punkte, Wert = c + sum(alpha_d * [Nachbar d an])."""
    on = norm_zero >= _SHADOW_ON_LEVEL
    nb = _on_neighbors(on)
    off = ~on
    off[:, 7 * COLS :] = False
    y = norm_zero[off].astype(np.float64)
    x = np.moveaxis(nb, -2, -1)[off].astype(np.float64)
    usable = [k for k in range(len(SHADOW_DIRECTIONS)) if x[:, k].sum() >= _SHADOW_MIN_SAMPLES]
    alphas = {d: 0.0 for d in SHADOW_DIRECTIONS}
    if not usable or y.size <= len(usable) + 1:
        return alphas
    design = np.column_stack([np.ones(len(y)), x[:, usable]])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    for k, a in zip(usable, coef[1:], strict=True):
        alphas[SHADOW_DIRECTIONS[k]] = float(np.clip(a, 0.0, _SHADOW_MAX_ALPHA))
    return alphas


def _remove_shadow(norm: np.ndarray) -> np.ndarray:
    """Zieht den geschaetzten Schatten von allen Aus-Punkten jeder
    Verschiebung ab (`bg_closing_shadow_v1`). An-Punkte bleiben."""
    zero = SHIFTS.index((0, 0))
    alphas = shadow_coefficients(norm[:, zero])
    weights = np.array([alphas[d] for d in SHADOW_DIRECTIONS], dtype=np.float32)
    if not weights.any():
        return norm
    on = norm >= _SHADOW_ON_LEVEL
    shade = np.einsum("...kn,k->...n", _on_neighbors(on).astype(np.float32), weights)
    return np.where(on, norm, np.clip(norm - shade, 0.0, 1.0)).astype(np.float32)


def normalized(s: SampledImage, ink: float | None = None, remove_shadow: bool = True) -> np.ndarray:
    """Rohhelligkeiten auf [0, 1] normiert, 1 = voll dunkel (Punkt an).

    Ohne `ink` (Vorgabe, `ink_per_cell_v1`): Die Punkttiefe jeder Zelle mit
    Zeichen kommt aus dem Tiefenverlauf ueber die Zeile
    (`_relative_depth_per_cell`), multipliziert mit dem Hintergrund der
    Zelle; Zellen ohne Zeichen behalten die globale Tiefe. Gibt es weniger
    als `_MIN_INKED_CELLS` Zellen mit Zeichen, gilt der globale Pegel wie mit
    `ink`.

    Mit `ink` (globaler Pegel): Der Tintenpegel wird je Zelle mit dem
    Verhaeltnis ihres Hintergrunds zum Median-Hintergrund skaliert. Das
    nutzt die Leerzellenpruefung (Final-Fix 3): Die Zellen 13-15 werden fuer
    sich abgetastet und bekommen den Pegel der Zellen 0-8. Ohne Ziffern in
    dieser Teilmenge waere ihr eigener Pegel ~= Hintergrund, `depth` liefe
    auf den Bodenwert 1e-3 und verstaerkte Rauschen zu einem Scheinmuster.
    """
    if s.background_dots is not None:
        bg = s.background_dots
    else:
        bg = np.broadcast_to(s.background[:, None, None], s.raw.shape)
    rel = None if ink is not None else _relative_depth_per_cell(s)
    if rel is not None:
        depth = bg * rel.astype(np.float32)[:, None, None]
    else:
        ink_level = s.ink if ink is None else ink
        median_bg = float(np.median(s.background))
        if median_bg > 0:
            depth = bg * (1.0 - ink_level / median_bg)
        else:
            depth = bg - ink_level
    depth = np.where(depth > 1e-3, depth, 1e-3)
    out = np.clip((bg - s.raw) / depth, 0.0, 1.0).astype(np.float32)
    if remove_shadow and ink is None:
        out = _remove_shadow(out)
    return out
