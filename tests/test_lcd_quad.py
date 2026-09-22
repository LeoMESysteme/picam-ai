import cv2
import numpy as np

from dispread.workbench.vision import lcd_quad_in_region


def _blank_image(width=400, height=300):
    return np.full((height, width, 3), (60, 60, 60), dtype=np.uint8)


def _draw_tilted_saturated_rect(image, center, size, angle_deg, color):
    rect = ((center[0], center[1]), size, angle_deg)
    box = cv2.boxPoints(rect).astype(np.int32)
    cv2.fillConvexPoly(image, box, color)
    return box


def test_lcd_quad_finds_tilted_saturated_rectangle():
    image = _blank_image()
    # Kraeftig gesaettigtes Gruen wie eine hinterleuchtete LCD-Anzeige.
    box = _draw_tilted_saturated_rect(image, (200, 150), (180, 90), 12, (40, 220, 60))
    hint_box = (0.25, 0.25, 0.5, 0.5)

    quad = lcd_quad_in_region(image, hint_box)

    assert quad is not None
    assert len(quad) == 4
    height, width = image.shape[:2]
    quad_px = [(x * width, y * height) for x, y in quad]
    # Grobe Naehe zu den tatsaechlichen Rechteckecken - minAreaRect auf einer
    # geschlossenen Maske muss nicht pixelgenau treffen.
    for (px, py) in quad_px:
        distances = [np.hypot(px - bx, py - by) for bx, by in box]
        assert min(distances) < 25

    # tl/tr/br/bl-Reihenfolge: obere zwei Punkte muessen kleineres y haben
    # als die unteren zwei.
    ys = [y for _, y in quad_px]
    assert max(ys[0], ys[1]) < min(ys[2], ys[3]) + 5


def test_lcd_quad_returns_none_for_unsaturated_region():
    image = _blank_image()
    # Graue Flaeche ohne jede Saettigung - kein Backlit-LCD.
    cv2.rectangle(image, (150, 100), (330, 200), (180, 180, 180), -1)
    hint_box = (0.25, 0.25, 0.5, 0.5)

    quad = lcd_quad_in_region(image, hint_box)

    assert quad is None


def test_lcd_quad_returns_none_when_saturated_area_too_small():
    image = _blank_image()
    # Winziger gesaettigter Fleck weit unter min_area_fraction des Hinweises.
    cv2.rectangle(image, (195, 145), (210, 160), (40, 220, 60), -1)
    hint_box = (0.25, 0.25, 0.5, 0.5)

    quad = lcd_quad_in_region(image, hint_box)

    assert quad is None


def test_lcd_quad_coordinates_are_normalised():
    image = _blank_image()
    _draw_tilted_saturated_rect(image, (200, 150), (180, 90), 5, (30, 200, 200))
    hint_box = (0.25, 0.25, 0.5, 0.5)

    quad = lcd_quad_in_region(image, hint_box)

    assert quad is not None
    assert len(quad) == 4
    for x, y in quad:
        assert 0.0 <= x <= 1.0
        assert 0.0 <= y <= 1.0
