import pytest

from dispread.charcells import CharGrid, source_dot_column_px


def test_cell_boxes_regular():
    g = CharGrid(n_cells=4, left=10.0, pitch=20.0, top=5.0, bottom=45.0)
    assert g.cell_boxes() == [(10, 5, 20, 40), (30, 5, 20, 40), (50, 5, 20, 40), (70, 5, 20, 40)]


def test_validate_rejects_overflow():
    g = CharGrid(n_cells=16, left=0.0, pitch=30.0, top=0.0, bottom=10.0)
    with pytest.raises(ValueError):
        g.validate(width=400, height=160)  # 16*30 = 480 > 400


def test_roundtrip_dict():
    g = CharGrid(n_cells=16, left=3.5, pitch=24.0, top=10.0, bottom=150.0)
    assert CharGrid.from_dict(g.to_dict()) == g


def test_source_dot_column_px_frontal_identity_scale():
    # Quad = achsparalleles Rechteck 400x160 im Quellbild, Ziel 400x160: Massstab 1
    quad = [[0, 0], [400, 0], [400, 160], [0, 160]]
    g = CharGrid(n_cells=16, left=0.0, pitch=24.0, top=0.0, bottom=160.0)
    assert source_dot_column_px(g, quad, (400, 160)) == pytest.approx(4.0, rel=1e-3)


def test_source_dot_column_px_oblique_takes_minimum():
    # rechte Seite im Quellbild halb so hoch/weit -> ferne Zellen schmaler
    quad = [[0, 0], [300, 40], [300, 120], [0, 160]]
    g = CharGrid(n_cells=16, left=0.0, pitch=25.0, top=0.0, bottom=160.0)
    frontal = source_dot_column_px(g, [[0, 0], [300, 0], [300, 160], [0, 160]], (400, 160))
    assert source_dot_column_px(g, quad, (400, 160)) < frontal
