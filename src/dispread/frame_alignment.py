"""Ausrichtungspruefung Ernte <-> Profilbild (StreamCam-Umstieg, Task 10).

Die StreamCam kann zwischen/waehrend Aufnahmen mechanisch verschoben werden
(Tisch/Halterung). `estimate_quad_shift` schaetzt, wie weit sich ein Bild
gegenueber dem beim `harvest-setup.py confirm` bestaetigten Profilbild
verschoben hat, und bildet die vier Profil-Quad-Ecken unter dieser Schaetzung
ab (Translation, Rotation, gleichfoermiger Massstab).

## Methode: ORB + `cv2.estimateAffinePartial2D` (RANSAC), nicht ECC

`dispread.track.QuadTracker` registriert bereits gegen eine Referenz - aber
mit `cv2.findTransformECC` (Gradientenabstieg, Startwert Identitaet), gebaut
fuer KLEINE Nachregistrierungen (dessen `TrackConfig.max_shift` ist ein
Toleranzband von Bruchteilen der Arbeitsbreite). Reale Messungen dieser
Aufgabe zeigen etwas anderes: `var/diagnostics/sc2-run` gegen
`sc2-still/frame_000014.png` liefert Eckverschiebungen von rund 6-11 Pixeln
mit einem Vorzeichensprung mitten im Lauf (Kamera wurde angestossen),
`var/diagnostics/sc1-run` gegen `sc1-focus/control.png` sogar rund 100-110
Pixel PLUS einen Massstabsfaktor von rund 0.98 (rund 2 % kleiner). Ein
Gradientenverfahren ohne Bildpyramide divergiert bei Startfehlern dieser
Groessenordnung typischerweise. ORB-Merkmale plus RANSAC brauchen dagegen
keinen Startwert und sind gegen grosse, abrupte Verschiebungen robust - beide
realen Faelle oben wurden im Bericht dieser Aufgabe genau damit nachgemessen.
`cv2.estimateAffinePartial2D` schaetzt Translation, Rotation und
GLEICHFOERMIGEN Massstab (4 Freiheitsgrade), das ist die im Auftrag
verlangte "Translation + Massstab".

## Ausschnitt mit Rand statt Vollbild

Gesucht wird nicht im ganzen Bild, sondern in einem Ausschnitt um das
Profil-Quad mit Rand `margin = max(quad_breite, quad_hoehe)` auf jeder Seite
(auf die Bildgrenzen beschnitten). Das haelt die Merkmalssuche lokal auf die
Messflaeche bezogen (eine Verschiebung, die nur ausserhalb dieses Bereichs
sichtbar waere, ist fuer DIESE Pruefung ohnehin nicht die interessante
Groesse), ist aber grosszuegig genug, um auch die groessere gemessene
sc1-Verschiebung (rund 100 Pixel Eckversatz bei rund 394 Pixel Quadbreite)
noch mit ueberlappendem statischen Bildinhalt abzudecken - siehe Bericht
dieser Aufgabe fuer die Messung, die diese Wahl belegt.

## Unpruefbarkeit - lieber ablehnen als raten (AGENTS.md)

Drei unabhaengige Stellen koennen eine Schaetzung verwerfen statt sie zu
liefern:

* zu wenige ORB-Deskriptoren ueberhaupt (strukturloser Ausschnitt),
* nach dem Lowe-Ratio-Test (0.75) weniger als `MIN_GOOD_MATCHES` gute
  Paarungen,
* nach RANSAC weniger als `MIN_INLIERS` Inlier ODER ein Inlier-Anteil unter
  `MIN_INLIER_RATIO`.

Die Schwellen sind an den realen sc1/sc2-Aufnahmen kalibriert (dort liegen
Inlier-Anteile deutlich ueber 50 % bei 40-90 guten Matches, siehe Bericht) -
ein einzelnes verrauschtes/strukturloses Bild soll zuverlaessig durchfallen,
ohne echte Labor-Aufnahmen unnoetig abzulehnen.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

#: ORB-Merkmale je Ausschnitt (Referenz und aktuelles Bild).
N_ORB_FEATURES = 2000

#: Lowe-Ratio-Test (Standardwert aus Lowes SIFT-Arbeit, hier fuer ORB-
#: Deskriptoren uebernommen - dasselbe Kriterium, "eindeutig genug").
LOWE_RATIO = 0.75

#: Weniger gute Matches als das gelten als unpruefbar, siehe Moduldocstring.
MIN_GOOD_MATCHES = 8

#: Nach RANSAC: weniger Inlier als das gelten als unpruefbar. Hoeher als
#: `MIN_GOOD_MATCHES`, weil erst nach RANSAC klar ist, wie viele der guten
#: Matches geometrisch konsistent sind.
MIN_INLIERS = 15

#: Nach RANSAC: ein kleinerer Inlier-Anteil als das gilt als unpruefbar. Auf
#: den realen sc1-Aufnahmen (`var/diagnostics/sc1-run` gegen
#: `sc1-focus/control.png`, Bericht dieser Aufgabe) liegt der Anteil trotz
#: klar korrekter Schaetzung (190+ Inlier, konsistente Translation/Massstab)
#: nur bei rund 0.36 - die Szene enthaelt sich wiederholende Strukturen
#: (Kalibrierraster im Hintergrund), die viele *falsche* Lowe-Ratio-Matches
#: erzeugen, ohne die Schaetzung selbst unsicherer zu machen. Ein hoeherer
#: Schwellwert (z. B. 0.5) wuerde diese echten, gut vermessenen Aufnahmen
#: verwerfen. 0.3 laesst sie durch, lehnt aber die tatsaechlich unsichere
#: sc1-Aufnahme (Frame 953, Uebergang mitten in der Bewegung, Anteil 0.26)
#: weiterhin ab.
MIN_INLIER_RATIO = 0.3

#: Schwelle fuer `cv2.estimateAffinePartial2D` (RANSAC-Reprojektionsfehler
#: in Pixeln des Ausschnitts).
RANSAC_REPROJ_THRESHOLD_PX = 3.0


@dataclass(frozen=True, slots=True)
class AlignmentEstimate:
    """Ergebnis einer Ausrichtungsschaetzung.

    `reliable=False` heisst: keine Zahl, sondern eine Ablehnung
    (`reason` erklaert warum) - kein Rateversuch (AGENTS.md). Bei
    `reliable=True` ist `max_corner_shift_px` die groesste der vier
    Eckverschiebungen und `moved_quad` das transformierte Profil-Quad in
    Quellbildkoordinaten des AKTUELLEN Bilds.
    """

    reliable: bool
    reason: str | None
    max_corner_shift_px: float | None
    moved_quad: list[list[float]] | None


def _quad_bbox(quad) -> tuple[float, float, float, float]:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return min(xs), min(ys), max(xs), max(ys)


def _crop_region(image_shape: tuple[int, ...], quad) -> tuple[int, int, int, int]:
    """Ausschnittsgrenzen `(x0, y0, x1, y1)`, siehe Moduldocstring."""
    height, width = image_shape[:2]
    x0, y0, x1, y1 = _quad_bbox(quad)
    margin = max(x1 - x0, y1 - y0)
    cx0 = max(0, int(x0 - margin))
    cy0 = max(0, int(y0 - margin))
    cx1 = min(width, int(x1 + margin))
    cy1 = min(height, int(y1 + margin))
    return cx0, cy0, cx1, cy1


def _to_gray(image: np.ndarray) -> np.ndarray:
    return image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def estimate_quad_shift(reference_image: np.ndarray, current_image: np.ndarray, quad) -> AlignmentEstimate:
    """Schaetzt die Verschiebung von `reference_image` nach `current_image`
    in einem Ausschnitt um `quad` (Quellbildpixel, wie `SessionProfile.quad`)
    und bildet die vier Quad-Ecken damit ab.

    `reference_image`/`current_image` muessen dieselbe Groesse haben wie das
    Bild, gegen das `quad` gemessen wurde (Vertrag wie bei `rectify()`).
    """
    cx0, cy0, cx1, cy1 = _crop_region(reference_image.shape, quad)
    ref_crop = _to_gray(reference_image)[cy0:cy1, cx0:cx1]
    cur_crop = _to_gray(current_image)[cy0:cy1, cx0:cx1]

    orb = cv2.ORB_create(N_ORB_FEATURES)
    kp_ref, des_ref = orb.detectAndCompute(ref_crop, None)
    kp_cur, des_cur = orb.detectAndCompute(cur_crop, None)
    if des_ref is None or des_cur is None or len(kp_ref) < 2 or len(kp_cur) < 2:
        return AlignmentEstimate(False, "zu wenige Bildmerkmale im Ausschnitt (ORB)", None, None)

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    knn_matches = matcher.knnMatch(des_ref, des_cur, k=2)
    good = [m for pair in knn_matches if len(pair) == 2 for m, n in [pair] if m.distance < LOWE_RATIO * n.distance]
    if len(good) < MIN_GOOD_MATCHES:
        return AlignmentEstimate(
            False,
            f"zu wenige gute Deskriptor-Matches ({len(good)} < {MIN_GOOD_MATCHES})",
            None,
            None,
        )

    src_pts = np.float32([kp_ref[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp_cur[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    transform, inlier_mask = cv2.estimateAffinePartial2D(
        src_pts, dst_pts, method=cv2.RANSAC, ransacReprojThreshold=RANSAC_REPROJ_THRESHOLD_PX
    )
    if transform is None:
        return AlignmentEstimate(False, "RANSAC fand keine Affintransformation", None, None)

    n_inliers = int(inlier_mask.sum()) if inlier_mask is not None else 0
    inlier_ratio = n_inliers / len(good)
    if n_inliers < MIN_INLIERS or inlier_ratio < MIN_INLIER_RATIO:
        return AlignmentEstimate(
            False,
            f"zu wenige Inlier ({n_inliers}/{len(good)}, Anteil {inlier_ratio:.2f})",
            None,
            None,
        )

    quad_rel = np.float32([[x - cx0, y - cy0] for x, y in quad]).reshape(-1, 1, 2)
    moved_rel = cv2.transform(quad_rel, transform).reshape(-1, 2)
    orig_rel = np.float32([[x - cx0, y - cy0] for x, y in quad])
    shifts = np.hypot(moved_rel[:, 0] - orig_rel[:, 0], moved_rel[:, 1] - orig_rel[:, 1])
    moved_quad = [[float(x + cx0), float(y + cy0)] for x, y in moved_rel]
    return AlignmentEstimate(True, None, float(shifts.max()), moved_quad)
