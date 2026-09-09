"""Validierte JSON-Profile und atomare Speicherung."""

from __future__ import annotations

import copy
import json
import math
import os
import re
import tempfile
from pathlib import Path

from dispread.layout import DisplayLayout

from .vision import DetectionConfig

DEFAULT = {
    "schema_version": 3,
    "version": 0,
    "camera": {"width": 960, "height": 720, "fps": 15.0, "controls": {"AeEnable": True, "Contrast": 1.0}},
    "roi": None,
    # Vier perspektivische Ecken, normiert auf das Kamerabild, in der
    # Reihenfolge oben-links, oben-rechts, unten-rechts, unten-links.
    # `roi` bleibt als achsparallele Huelle fuer Qualitaetsmetriken und die
    # Rueckwaertskompatibilitaet mit Profilversion 1 erhalten.
    "roi_quad": None,
    # Achsparalleler OCR-Ausschnitt innerhalb der perspektivisch entzerrten
    # ROI. Damit koennen Displayrahmen und tatsaechliches Ziffernraster
    # unabhaengig voneinander kalibriert werden.
    "ocr_box": [0.0, 0.0, 1.0, 1.0],
    "role": "main",
    "confirmed": False,
    "detection": vars(DetectionConfig()),
    # Zahlenformat der Anzeige. Kommt laut Konzept §4 aus dem bestaetigten
    # Profil und wird nicht geraten - der Leser tastet dagegen ab.
    "layout": DisplayLayout().to_dict(),
}
CONTROL_NAMES = {"AeEnable", "ExposureTime", "AnalogueGain", "Contrast"}
#: Erlaubte Spannen der Layout-Verhaeltnisse. Vorabdefaults, keine
#: validierten Grenzen.
LAYOUT_RATIOS = {
    "sign_cell_ratio": (0.2, 1.5),
    "thickness_ratio": (0.02, 0.45),
    "inset_ratio": (0.0, 0.35),
    # 1.0 erwies sich in der Bedienpruefung als zu eng: bei Anzeigen mit
    # deutlichem physischem Abstand zwischen den Stellen (bzw. einem grosszuegig
    # gezogenen OCR-Rahmen) reichte ein Zwischenraum bis zur Zellenbreite nicht.
    # Weiterhin ein Vorabdefault, keine an realen Geraeten validierte Grenze.
    "digit_gap_ratio": (0.0, 3.0),
}


def profile_name(name):
    if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
        raise ValueError("Profilname: nur Buchstaben, Ziffern, _ und -")
    return name


def finite(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def validate(data, capabilities=None):
    data = copy.deepcopy(data)
    # Profile v1 hatten nur eine achsparallele ROI. Beim Laden verlustfrei in
    # das neue Vierpunktformat ueberfuehren; beim naechsten Speichern wird v3
    # geschrieben.
    if data.get("schema_version") == 1 and set(data) == set(DEFAULT) - {"roi_quad", "ocr_box"}:
        data["roi_quad"] = quad_from_roi(data.get("roi"))
        data["ocr_box"] = copy.deepcopy(DEFAULT["ocr_box"])
        data["schema_version"] = 3
    if data.get("schema_version") == 2 and set(data) == set(DEFAULT) - {"ocr_box"}:
        data["ocr_box"] = copy.deepcopy(DEFAULT["ocr_box"])
        data["schema_version"] = 3
    # Innerhalb von Schema 3 kamen neue Layout-Felder hinzu (digit_gap_ratio).
    # Fehlende Felder in aelteren gespeicherten Profilen bekommen den
    # Default - das reproduziert exakt das bisherige lueckenlose Raster,
    # keine Vermutung ueber die tatsaechliche Anzeige.
    if isinstance(data.get("layout"), dict):
        for key, default in DEFAULT["layout"].items():
            data["layout"].setdefault(key, default)
    if set(data) != set(DEFAULT) or data["schema_version"] != 3:
        raise ValueError("Unbekanntes Profilschema oder unbekannte Felder")
    if type(data["version"]) is not int or data["version"] < 0:
        raise ValueError("Ungueltige Profilversion")
    cam = data["camera"]
    if set(cam) != {"width", "height", "fps", "controls"}:
        raise ValueError("Unbekannte Kamerafelder")
    for key in ("width", "height"):
        if type(cam[key]) is not int or not 64 <= cam[key] <= 4096:
            raise ValueError("Bildgroesse muss zwischen 64 und 4096 liegen")
    if not finite(cam["fps"]) or not 1 <= cam["fps"] <= 60:
        raise ValueError("Bildrate ausserhalb 1..60")
    controls = cam["controls"]
    if not isinstance(controls, dict) or not set(controls) <= CONTROL_NAMES:
        raise ValueError("Nicht unterstuetzter Kameraregler")
    for name, value in controls.items():
        if name == "AeEnable":
            if type(value) is not bool:
                raise ValueError("AeEnable muss true/false sein")
        elif not finite(value) or (value < 0 if name == "Contrast" else value <= 0):
            raise ValueError(f"Ungueltiger Wert fuer {name}")
        if name == "ExposureTime" and type(value) is not int:
            raise ValueError("ExposureTime ist eine ganze Zahl in Mikrosekunden")
        if capabilities is not None:
            if name not in capabilities:
                raise ValueError(f"Kamera unterstuetzt {name} nicht")
            low, high = capabilities[name][:2]
            if not low <= value <= high:
                raise ValueError(f"{name} ausserhalb {low}..{high}")
    if controls.get("AeEnable", True) and {"ExposureTime", "AnalogueGain"} & controls.keys():
        raise ValueError("Manuelle Belichtung erfordert AeEnable=false")
    if controls.get("AeEnable") is False and not {"ExposureTime", "AnalogueGain"} <= controls.keys():
        raise ValueError("Manuelle Belichtung braucht ExposureTime und AnalogueGain")
    roi = data["roi"]
    if roi is not None:
        if not isinstance(roi, list) or len(roi) != 4 or not all(finite(v) for v in roi):
            raise ValueError("ROI erwartet [x,y,w,h] normiert auf 0..1")
        x, y, width, height = roi
        if min(x, y) < 0 or min(width, height) <= 0 or x + width > 1.000001 or y + height > 1.000001:
            raise ValueError("ROI liegt ausserhalb des Bildes")
    if data["role"] not in ("main", "secondary") or type(data["confirmed"]) is not bool:
        raise ValueError("Ungueltige Anzeigenrolle/Bestaetigung")
    if data["confirmed"] and roi is None:
        raise ValueError("Keine ROI bestaetigt")
    quad = data["roi_quad"]
    if quad is None and roi is not None:
        quad = data["roi_quad"] = quad_from_roi(roi)
    if quad is not None:
        validate_quad(quad)
        bounds = roi_from_quad(quad)
        if roi is None or any(abs(a - b) > 1e-6 for a, b in zip(roi, bounds, strict=True)):
            data["roi"] = bounds
    if data["confirmed"] and quad is None:
        raise ValueError("Keine perspektivische ROI bestaetigt")
    validate_box(data["ocr_box"], "OCR-Rahmen")
    d = data["detection"]
    if set(d) != set(DEFAULT["detection"]) or not all(finite(v) for v in d.values()):
        raise ValueError("Ungueltige Erkennungsfilter")
    if not (
        0 < d["min_area"] < d["max_area"] <= 1
        and 1 <= d["min_aspect"] < d["max_aspect"]
        and 0 < d["min_rectangularity"] <= 1
    ):
        raise ValueError("Erkennungsfilter ausserhalb der Grenzen")
    validate_layout(data["layout"])
    return data


def quad_from_roi(roi):
    """Achsparallele normierte ROI in vier geordnete Ecken umwandeln."""
    if roi is None:
        return None
    x, y, width, height = roi
    return [[x, y], [x + width, y], [x + width, y + height], [x, y + height]]


def roi_from_quad(quad):
    """Kleinste achsparallele Huelle eines normierten Vierpunktausschnitts."""
    xs = [point[0] for point in quad]
    ys = [point[1] for point in quad]
    x, y = min(xs), min(ys)
    return [x, y, max(xs) - x, max(ys) - y]


def validate_box(box, label="ROI"):
    """Normiertes achsparalleles Rechteck innerhalb 0..1 pruefen."""
    if not isinstance(box, list) or len(box) != 4 or not all(finite(value) for value in box):
        raise ValueError(f"{label} erwartet [x,y,w,h] normiert auf 0..1")
    x, y, width, height = box
    if min(x, y) < 0 or min(width, height) <= 0 or x + width > 1.000001 or y + height > 1.000001:
        raise ValueError(f"{label} liegt ausserhalb des Bildes")


def validate_quad(quad):
    """Geordnetes, konvexes Vierpunktpolygon innerhalb des Bildes pruefen."""
    if (
        not isinstance(quad, list)
        or len(quad) != 4
        or any(not isinstance(point, list) or len(point) != 2 or not all(finite(v) for v in point) for point in quad)
    ):
        raise ValueError("ROI-Quad erwartet vier normierte [x,y]-Punkte")
    if any(not 0 <= value <= 1 for point in quad for value in point):
        raise ValueError("ROI-Quad liegt ausserhalb des Bildes")
    crosses = []
    for index in range(4):
        a, b, c = quad[index], quad[(index + 1) % 4], quad[(index + 2) % 4]
        crosses.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
    if min(abs(value) for value in crosses) < 1e-6 or not (all(value > 0 for value in crosses) or all(value < 0 for value in crosses)):
        raise ValueError("ROI-Quad muss konvex und im Uhrzeigersinn geordnet sein")


def validate_layout(layout):
    """Zahlenformat pruefen. Ein unmoegliches Raster darf nie in den Leser."""
    if not isinstance(layout, dict) or set(layout) != set(DEFAULT["layout"]):
        raise ValueError("Unbekannte Layoutfelder")
    if type(layout["digits"]) is not int or not 1 <= layout["digits"] <= 12:
        raise ValueError("Ziffernstellen muessen zwischen 1 und 12 liegen")
    decimals = layout["decimals"]
    if decimals is not None:
        if type(decimals) is not int or not 0 <= decimals <= 6:
            raise ValueError("Nachkommastellen: 0 bis 6 oder unbestimmt")
        # decimal_point_index() waere sonst negativ, das Format unmoeglich.
        if decimals >= layout["digits"]:
            raise ValueError("Nachkommastellen muessen kleiner als die Ziffernzahl sein")
    if type(layout["has_sign"]) is not bool:
        raise ValueError("Vorzeichenstelle muss true/false sein")
    unit = layout["unit"]
    if unit is not None and (not isinstance(unit, str) or not unit.strip() or len(unit) > 8 or not unit.isprintable()):
        raise ValueError("Einheit: bis zu 8 druckbare Zeichen oder keine")
    for name, (low, high) in LAYOUT_RATIOS.items():
        if not finite(layout[name]) or not low <= layout[name] <= high:
            raise ValueError(f"{name} ausserhalb {low}..{high}")


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".profile-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(data, output, indent=2, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
