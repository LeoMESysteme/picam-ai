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
