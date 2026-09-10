"""Geometrische Display-Vorschlaege; keine trainierte Erkennung."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from dispread.layout import DisplayLayout
from dispread.rectify import _order_quad


@dataclass(frozen=True)
class DetectionConfig:
    min_area: float = 0.005
    max_area: float = 0.60
    min_aspect: float = 1.5
    max_aspect: float = 8.0
    min_rectangularity: float = 0.65


def box_iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    intersection = max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0, min(ay + ah, by + bh) - max(ay, by))
    return intersection / (aw * ah + bw * bh - intersection)


def find_display_candidates(image, config=DetectionConfig()):
    """Geometrische Vorschlaege; Rechteckigkeit ist keine Wahrscheinlichkeit.

    Kandidaten nach Rechteckigkeit, dann Flaeche sortieren. Die achsparallelen
    Boxen liegen im Koordinatensystem des Eingabebildes.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = image.shape[0] * image.shape[1]
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        (_, _), (width, height), _ = cv2.minAreaRect(contour)
        if min(width, height) <= 0:
            continue
        aspect = max(width, height) / min(width, height)
        rectangularity = area / (width * height)
        if (
            config.min_area <= area / image_area <= config.max_area
            and config.min_aspect <= aspect <= config.max_aspect
            and rectangularity >= config.min_rectangularity
        ):
            candidates.append((rectangularity, area, cv2.boundingRect(contour)))
    boxes = []
    for _, _, box in sorted(candidates, reverse=True):
        if all(box_iou(box, other) <= 0.5 for other in boxes):
            boxes.append(box)
        if len(boxes) == 5:
            break
    return boxes


def _aspect_ok(aspect, config, layout):
    """Seitenverhaeltnis gegen die feste Spanne pruefen, mit Profil zusaetzlich
    gegen das aus `DisplayLayout.n_cells` erwartete Verhaeltnis."""
    if config.min_aspect <= aspect <= config.max_aspect:
        return True
    if layout is not None:
        expected = layout.n_cells
        return 0.6 * expected <= aspect <= 1.6 * expected
    return False


#: Ein Kandidat muss diesen Anteil des Hinweisbereichs (nicht des aufgeweiteten
#: Suchfensters) ueberdecken, um ueberhaupt in Frage zu kommen. Verhindert,
#: dass ein anderes, zufaellig rechteckigeres Objekt im aufgeweiteten Fenster
#: gewinnt - beobachtet an einer echten Aufnahme mit Monitoren neben dem
#: Pruefling: eine grosszuegig bestaetigte ROI weitet das Suchfenster so weit
#: auf, dass benachbarte Bildschirme hineinragen. Vorabdefault, an den zwei
#: realen Annotationen (dort ueberdeckt der richtige Kandidat >0.9) und einer
#: synthetischen Ablenker-Szene geprueft, nicht an einer breiten Gerätevielfalt
#: validiert.
MIN_HINT_OVERLAP = 0.2


def fit_quad_in_region(image, hint_box, config=DetectionConfig(), layout: DisplayLayout | None = None):
    """Perspektivisches `roi_quad` innerhalb eines groben Bedienerhinweises vorschlagen.

    `hint_box` ist die normierte achsparallele Box `[x,y,w,h]` (Rohbild) - die
    bereits bestaetigte `roi` als Vergleichshinweis (`Controller.publish`,
    gedrosselte Suche nach Bestaetigung). Ein grober Hinweis ist zuverlaessiger
    als eine Vollbildsuche ohne jeden
    Hinweis (mehrere aehnlich rechteckige Objekte am Pruefstand sind sonst
    nicht unterscheidbar). Die Suche bleibt auf einen um ~25% aufgeweiteten
    Ausschnitt beschraenkt, aber ein Kandidat muss zusaetzlich den
    ungepolsterten Hinweisbereich selbst zu einem Mindestanteil ueberdecken
    (`MIN_HINT_OVERLAP`) - sonst gewinnt bei einem grosszuegigen Hinweis leicht
    ein unbeteiligtes Objekt im aufgeweiteten Fenster (Bedienerbefund: andere
    Bildschirme im Bild wurden vorgeschlagen).

    Gibt ein geordnetes, normiertes Vierpunktquad (oben-links, oben-rechts,
    unten-rechts, unten-links) in vollen Bildkoordinaten zurueck, oder `None`
    wenn kein Kandidat die Filter besteht - ein Fehlschlag ist inert, nie eine
    schlechte Automatik-Uebernahme (`manual_roi` bleibt Primaerpfad, das hier
    ist nur ein Vorschlag, den der Bediener weiter bestaetigen muss).
    """
    height, width = image.shape[:2]
    hint_x, hint_y, hint_w, hint_h = hint_box
    pad_x, pad_y = hint_w * 0.25, hint_h * 0.25
    x0 = max(0.0, hint_x - pad_x)
    y0 = max(0.0, hint_y - pad_y)
    x1 = min(1.0, hint_x + hint_w + pad_x)
    y1 = min(1.0, hint_y + hint_h + pad_y)
    left, top = int(round(x0 * width)), int(round(y0 * height))
    right, bottom = int(round(x1 * width)), int(round(y1 * height))
    if right - left < 4 or bottom - top < 4:
        return None

    region = image[top:bottom, left:right]
    region_area = region.shape[0] * region.shape[1]
    # Hinweisbereich im lokalen Pixelkoordinatensystem des Ausschnitts -
    # fuer den Ueberdeckungstest gegen jeden Kandidaten.
    hint_local = (hint_x * width - left, hint_y * height - top, hint_w * width, hint_h * height)
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    for contour in contours:
        area = cv2.contourArea(contour)
        rect = cv2.minAreaRect(contour)
        (_, _), (rect_w, rect_h), _ = rect
        if min(rect_w, rect_h) <= 0:
            continue
        aspect = max(rect_w, rect_h) / min(rect_w, rect_h)
        rectangularity = area / (rect_w * rect_h)
        if not (
            config.min_area <= area / region_area <= config.max_area
            and _aspect_ok(aspect, config, layout)
            and rectangularity >= config.min_rectangularity
            and box_iou(cv2.boundingRect(contour), hint_local) >= MIN_HINT_OVERLAP
        ):
            continue
        score = (rectangularity, area)
        if best is None or score > best[0]:
            best = (score, cv2.boxPoints(rect))
    if best is None:
        return None

    ordered = _order_quad(best[1])
    return tuple((float((left + x) / width), float((top + y) / height)) for x, y in ordered)


def _threshold_variants(gray):
    """Otsu-Schwelle in beide Polaritaeten; welche gemeint ist, entscheidet
    die spaetere Blobstruktur - kein neuer Bedienregler in dieser Stufe."""
    _, bright_on_dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return bright_on_dark, cv2.bitwise_not(bright_on_dark)


def _digit_blobs(mask, min_height, max_height, close_kernel_y, close_kernel_x):
    # Kernel proportional zur erwarteten Ziffernhoehe: bei beruehrenden Stellen
    # (digit_gap_ratio=0, dem Default) oder nur schmal getrennten Segmenten
    # zerfaellt eine Ziffer sonst in Ober-/Unterhaelfte statt zu einem Blob zu
    # verschmelzen - das zerstreut ihre vertikale Mitte unnoetig.
    # numpy-Achsreihenfolge ist (Zeilen, Spalten) = (vertikal, horizontal) -
    # np.ones((close_kernel_y, close_kernel_x), ...) ist deshalb absichtlich
    # NICHT vertauscht: close_kernel_y bestimmt die vertikale, close_kernel_x
    # die horizontale Schliess-Reichweite.
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((close_kernel_y, close_kernel_x), np.uint8))
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    return [tuple(stats[label][:4]) for label in range(1, count) if min_height <= stats[label][3] <= max_height]


def _cluster_by_vertical_center(blobs, height, gap_fraction=0.08):
    """Blobs anhand ihrer vertikalen Mitte zu Zeilen gruppieren.

    Sortiert und an Luecken > `gap_fraction` der Crophoehe getrennt, statt
    gegen einen laufenden Mittelwert zu vergleichen - sonst kann ein einzelner
    Ausreisser (Glanzfleck, Nebenanzeige) sich ueber eine Kette benachbarter
    Abstaende in die falsche Zeile hineinziehen.
    """
    ordered = sorted(blobs, key=lambda box: (box[1] + box[3] / 2) / height)
    clusters, current, previous_center = [], [], None
    for box in ordered:
        center = (box[1] + box[3] / 2) / height
        if previous_center is not None and center - previous_center > gap_fraction:
            clusters.append(current)
            current = []
        current.append(box)
        previous_center = center
    if current:
        clusters.append(current)
    return clusters


def _rank_clusters(blobs, height):
    """Zeilen-Cluster (mindestens 2 Blobs) absteigend nach Gesamt-Blobflaeche.

    Gemeinsame Rangfolge fuer `fit_ocr_box` (nimmt nur Platz 1) und
    `fit_ocr_box_candidates` (geht die ganze Liste durch)."""
    clusters = [c for c in _cluster_by_vertical_center(blobs, height) if len(c) >= 2]
    return sorted(clusters, key=lambda boxes: sum(w * h for _, _, w, h in boxes), reverse=True)


def _best_blobs(gray, close_kernel_y, close_kernel_x, min_height, max_height):
    best = None
    for mask in _threshold_variants(gray):
        blobs = _digit_blobs(mask, min_height, max_height, close_kernel_y, close_kernel_x)
        if len(blobs) >= 2 and (best is None or len(blobs) > len(best)):
            best = blobs
    return best


#: Schliess-Kernel fuer die Ziffernblob-Erkennung, Basisformel proportional zur
#: Crophoehe (unveraendert seit der ersten Fassung).
OCR_CLOSE_HEIGHT_RATIO = 0.08

#: Zusaetzliche, an der erwarteten Zellenbreite gemessene vertikale
#: Schliess-Reichweite - behebt eine bekannte Grenze bei sehr schmalen
#: Layouts (wenige, breite Ziffernzellen): eine "1" zeichnet nur die rechten
#: Segmente b/c; ihr Zwischenraum (dort waere Segment g) skaliert mit der
#: Segmentdicke und damit mit der Zellenbreite, nicht mit der Crophoehe - bei
#: einem breiten Layout kann der bisherige, nur hoehenbasierte Kernel diesen
#: Zwischenraum nicht mehr schliessen und die "1" zerfaellt in zwei kleine
#: Blobs statt eines. Empirisch bestimmt (Sweep 0,0-0,30 gegen vier
#: synthetische Layout-/Wertkombinationen, ein rekonstruiertes 3-stelliges
#: Layout ohne Nachkommastelle und alle realen Annotationen unter
#: `var/workbench/annotations/`; siehe docs/VALIDATION.md): der Fehler
#: verschwindet ab 0,14, ab 0,25 beginnt eine der vier Vergleichsformen leicht
#: zu regressieren. 0,15 liegt sicher dazwischen.
#: **Bewusst NICHT auf `close_kernel_x` angewandt** - eine Version, die
#: stattdessen die horizontale Kernelausdehnung mit der Zellenbreite skaliert,
#: wurde gemessen und verworfen: sie verschmilzt ab dem gleichen Bereich
#: benachbarte Ziffernzellen im selben Blob (weniger, aber breitere Blobs je
#: Zeile) und regressiert dadurch mehrere reale Annotationen vollstaendig auf
#: `None` statt sie zu verbessern - das eigentliche Problem ist ein
#: vertikaler Zwischenraum innerhalb einer Ziffer, keine horizontale Luecke
#: zwischen Ziffern.
OCR_CLOSE_WIDTH_RATIO = 0.15


def _ocr_close_kernel(height, width, layout: DisplayLayout | None = None):
    """Anisotroper Schliess-Kernel (Zeilen, Spalten) fuer die Blob-Erkennung.

    Ohne Layout bitidentisch zur bisherigen quadratischen Formel
    (`close_kernel_x == close_kernel_y`, beide nur aus der Crophoehe). Mit
    Layout wird nur `close_kernel_y` (vertikale Reichweite) zusaetzlich an
    die erwartete Zellenbreite gekoppelt - Begruendung siehe
    `OCR_CLOSE_WIDTH_RATIO`.
    """
    close_kernel_x = max(3, round(height * OCR_CLOSE_HEIGHT_RATIO))
    close_kernel_y = close_kernel_x
    if layout is not None and layout.n_cells > 0:
        cell_width = width / layout.n_cells
        close_kernel_y = max(close_kernel_y, round(cell_width * OCR_CLOSE_WIDTH_RATIO))
    return close_kernel_y, close_kernel_x


def _box_from_cluster(blobs, width, height, layout: DisplayLayout | None = None):
    """Vereinigungsbox eines Zeilen-Clusters mit Rand-/Flaechen-/
    Seitenverhaeltnis-Pruefung. `None`, wenn dieses Cluster fuer sich allein
    die Filter nicht besteht - blockiert nicht die uebrigen Kandidaten."""
    xs0 = min(x for x, _, _, _ in blobs)
    ys0 = min(y for _, y, _, _ in blobs)
    xs1 = max(x + w for x, _, w, _ in blobs)
    ys1 = max(y + h for _, y, _, h in blobs)
    margin_x, margin_y = width * 0.015, height * 0.015
    x0 = max(0.0, xs0 - margin_x)
    y0 = max(0.0, ys0 - margin_y)
    x1 = min(float(width), xs1 + margin_x)
    y1 = min(float(height), ys1 + margin_y)
    box_w, box_h = x1 - x0, y1 - y0
    if box_h <= 0:
        return None
    area_fraction = (box_w * box_h) / (width * height)
    if not 0.05 <= area_fraction <= 0.90:
        return None
    if layout is not None:
        expected_aspect = layout.n_cells
        actual_aspect = box_w / box_h
        if not 0.4 * expected_aspect <= actual_aspect <= 2.5 * expected_aspect:
            return None
    return (float(x0 / width), float(y0 / height), float(box_w / width), float(box_h / height))


def fit_ocr_box_candidates(rectified_crop, layout: DisplayLayout | None = None, max_candidates=5):
    """Alle plausiblen `ocr_box`-Kandidaten (Vorzeichen+Ziffern) im entzerrten
    Ausschnitt, absteigend nach Gesamt-Blobflaeche, dedupliziert
    (`box_iou <= 0.5`, wie `find_display_candidates`).

    Behebt OQ-25: bei zwei uebereinanderliegenden Anzeigen im selben ROI
    (Haupt-/Nebenanzeige, Konzept.md §7) bilden beide Zeilen eigene, die
    Filter bestehende Cluster - `fit_ocr_box` (Singular) waehlt davon
    weiterhin nur die flaechengroessere und kann damit die falsche treffen;
    hier bekommt der Bediener beide zur Auswahl, statt dass die Automatik
    still die falsche uebernimmt. Nie `None` - hoechstens eine leere Liste.
    """
    gray = rectified_crop if rectified_crop.ndim == 2 else cv2.cvtColor(rectified_crop, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    min_height, max_height = height * 0.15, height * 0.95
    close_kernel_y, close_kernel_x = _ocr_close_kernel(height, width, layout)

    best_blobs = _best_blobs(gray, close_kernel_y, close_kernel_x, min_height, max_height)
    if best_blobs is None:
        return []

    candidates = []
    for cluster in _rank_clusters(best_blobs, height):
        box = _box_from_cluster(cluster, width, height, layout)
        if box is None:
            continue
        if all(box_iou(box, other) <= 0.5 for other in candidates):
            candidates.append(box)
        if len(candidates) == max_candidates:
            break
    return candidates


def fit_ocr_box(rectified_crop, layout: DisplayLayout | None = None):
    """`ocr_box`-Vorschlag (Vorzeichen+Ziffern) im entzerrten Ausschnitt -
    nur die eine wahrscheinlichste Zeile. Fuer alle plausiblen Zeilen siehe
    `fit_ocr_box_candidates`.

    Arbeitet auf dem bereits ueber `dispread.rectify.rectify` entzerrten Crop.
    Filtert Blobs nach Hoehe (Staub/Dezimalpunkt/Einheitentext zu klein,
    Gehaeusekante zu gross), clustert die verbleibenden nach vertikaler Mitte
    und behaelt das flaechengroesste Cluster - das schliesst Einheitentext und
    Blende aus, ohne sie explizit zu kennen. `None` bei zu wenig Evidenz oder
    degenerierter Flaeche; ein Fehlschlag ist inert, nie eine schlechte
    Automatik-Uebernahme.

    Der Schliess-Kernel ist anisotrop (`_ocr_close_kernel`): bei sehr schmalen
    Layouts (wenige, breite Ziffernzellen) skaliert die Segmentdicke - und
    damit der Zwischenraum innerhalb einer Ziffer, etwa zwischen den beiden
    Segmenten einer "1" - mit der Zellenbreite, nicht mit der Crophoehe. Ohne
    diese Kopplung (`OCR_CLOSE_WIDTH_RATIO`) zerfaellt eine solche Ziffer in
    zwei kleine Blobs statt eines, siehe docs/VALIDATION.md fuer den Sweep.

    Bewusst KEIN `fit_ocr_box_candidates(..., max_candidates=1)[0]`: das wuerde
    bei einem fuer sich scheiternden flaechengroessten Cluster still zum
    naechst-schwaecheren durchreichen und damit die in VALIDATION.md/OQ-25
    gemessene Sicherheitseigenschaft brechen ("mit enger vorgeschlagener
    roi_quad liefert fit_ocr_box `None` statt eines falschen Vorschlags").
    Nimmt deshalb strukturell nur Rang 1, ohne Fallback - bitidentisch zum
    bisherigen Verhalten, nur auf den gemeinsamen Hilfsfunktionen aufgebaut.
    """
    gray = rectified_crop if rectified_crop.ndim == 2 else cv2.cvtColor(rectified_crop, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    min_height, max_height = height * 0.15, height * 0.95
    close_kernel_y, close_kernel_x = _ocr_close_kernel(height, width, layout)

    best_blobs = _best_blobs(gray, close_kernel_y, close_kernel_x, min_height, max_height)
    if best_blobs is None:
        return None
    ranked = _rank_clusters(best_blobs, height)
    if not ranked:
        return None
    return _box_from_cluster(ranked[0], width, height, layout)


def draw_overlay(image, boxes):
    result = image.copy()
    for x, y, width, height in boxes:
        cv2.rectangle(result, (x, y), (x + width - 1, y + height - 1), (0, 255, 255), 2)
        cv2.putText(result, "Display-Kandidat", (x, max(18, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    if not boxes:
        cv2.putText(result, "Kein Display-Kandidat", (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    return result
