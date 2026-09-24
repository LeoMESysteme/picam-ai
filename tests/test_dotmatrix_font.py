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
