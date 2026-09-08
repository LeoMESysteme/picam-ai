"""Geometrische Display-Vorschlaege; keine trainierte Erkennung."""

from dataclasses import dataclass

import cv2
import numpy as np


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


def draw_overlay(image, boxes):
    result = image.copy()
    for x, y, width, height in boxes:
        cv2.rectangle(result, (x, y), (x + width - 1, y + height - 1), (0, 255, 255), 2)
        cv2.putText(result, "Display-Kandidat", (x, max(18, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    if not boxes:
        cv2.putText(result, "Kein Display-Kandidat", (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    return result
