"""Displayausschnitt entzerren und Kontrast aufbereiten (Konzept.md §3, Schritt 3).

Die Entzerrung bekommt das Viereck der Anzeige und liefert einen achsparallelen
Ausschnitt in fester Zielgroesse. Feste Zielgroesse ist wichtig, weil der
7-Segment-Dekoder gegen das Profilraster abtastet - schwankende
Ausschnittgroessen wuerden die Abtastpunkte verschieben.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from dispread.detect import Quad


@dataclass(frozen=True, slots=True)
class DisplayCrop:
    """Entzerrter Ausschnitt samt Qualitaetsmassen."""

    image: np.ndarray
    source_quad: Quad
    #: Homographie als 9 Elemente - erlaubt die Rueckprojektion einzelner
    #: Segmente ins Originalbild, etwa fuer Diagnosebilder.
    homography: tuple[float, ...]
    #: Varianz des Laplace-Operators. Hoeher = schaerfer. Absolutwerte sind
    #: nur innerhalb eines Aufbaus vergleichbar.
    sharpness: float
    #: Anteil gesaettigter Bildpunkte (>= 250).
    saturated_fraction: float
    #: Anteil sehr dunkler Bildpunkte (<= 5).
    clipped_dark_fraction: float
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def exposure_ok(self) -> bool:
        """Grobe Belichtungspruefung. Die Schwellen sind Vorabdefaults."""
        return self.saturated_fraction < 0.02 and self.clipped_dark_fraction < 0.6


def _order_quad(quad: Quad) -> np.ndarray:
    """Eckpunkte nach oben-links, oben-rechts, unten-rechts, unten-links."""
    pts = np.array(quad, dtype=np.float32)
    by_sum = pts.sum(axis=1)
    by_diff = np.diff(pts, axis=1).ravel()
    return np.array(
        [
            pts[np.argmin(by_sum)],  # oben links
            pts[np.argmin(by_diff)],  # oben rechts
            pts[np.argmax(by_sum)],  # unten rechts
            pts[np.argmax(by_diff)],  # unten links
        ],
        dtype=np.float32,
    )


def enhance(gray: np.ndarray, *, clahe_clip: float = 2.0) -> np.ndarray:
    """Kontrast lokal anheben.

    CLAHE statt globaler Normierung, weil Reflexionen und ungleichmaessige
    Beleuchtung (Konzept.md §9) den Ausschnitt lokal unterschiedlich treffen.
    """
    clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8, 8))
    return clahe.apply(gray)


def rectify(
    image: np.ndarray,
    quad: Quad,
    *,
    target_size: tuple[int, int] = (400, 160),
    apply_enhance: bool = False,
) -> DisplayCrop:
    """Viereck auf einen achsparallelen Ausschnitt abbilden.

    `apply_enhance` ist standardmaessig aus: die Segmentauswertung schwellt
    ueber die gepoolten Segmentmessungen und braucht keine Kontrastspreizung.
    Eine Aufbereitung wuerde die gemessenen Helligkeiten veraendern und damit
    die Evidenz, die die Freigabe bewertet.
    """
    width, height = target_size
    src = _order_quad(quad)
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(image, matrix, (width, height), flags=cv2.INTER_LINEAR)

    gray = warped if warped.ndim == 2 else cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    if apply_enhance:
        gray = enhance(gray)
        warped = gray

    return DisplayCrop(
        image=warped,
        source_quad=quad,
        homography=tuple(float(v) for v in matrix.ravel()),
        sharpness=float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        saturated_fraction=float((gray >= 250).mean()),
        clipped_dark_fraction=float((gray <= 5).mean()),
        diagnostics={"target_size": [width, height], "enhanced": apply_enhance},
    )
