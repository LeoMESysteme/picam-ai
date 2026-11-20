"""Startbild der picam-Konsole: Objektiv und Punktmatrix-LCD ohne Terminal."""

from dispread.admin import intro, tui


def test_lens_has_ring_glass_and_highlight_and_stays_in_bounds():
    lens = intro.Lens(30, 14)
    for t in (0.0, 1.3, 2.7, 5.1):
        chars, level, kind = lens.cells(t)
        assert chars.shape == (14, 30)
        kinds = set(kind.ravel())
        assert {1, 2} <= kinds
        assert level.max() < intro.LEVELS


def test_lens_moves_between_frames():
    lens = intro.Lens(30, 14)
    assert (lens.cells(0.0)[0] != lens.cells(0.8)[0]).any()


def test_lcd_sweep_lights_read_dots():
    total_lit = sum(row.count('#') for c in 'picam' for row in intro.LCD_FONT[c])
    before = intro.lcd_text('picam', 0.0)
    after = intro.lcd_text('picam', 1.0)
    read = lambda text: sum(1 for span in text.spans if str(span.style) == intro.LCD_READ)  # noqa: E731
    assert read(before) == 0
    assert read(after) == total_lit
    assert len(after.plain.splitlines()) == 7


def test_lcd_compact_and_ascii():
    compact = intro.lcd_text('picam', 0.5, compact=True)
    assert len(compact.plain.splitlines()) == 4
    assert len(compact.plain.splitlines()[0]) == intro.lcd_columns('picam')
    plain = intro.lcd_text('picam', 1.0, ascii_only=True).plain + intro.lcd_text('picam', 1.0, True, True).plain
    assert plain.isascii()


def test_intro_switches(monkeypatch):
    monkeypatch.delenv('PICAM_INTRO', raising=False)
    assert tui.intro_wanted()
    assert not tui.intro_wanted(False)
    monkeypatch.setenv('PICAM_INTRO', '0')
    assert not tui.intro_wanted()


def test_cli_accepts_no_intro(monkeypatch):
    from dispread.admin import cli
    from dispread.admin.instance import Instance

    seen = {}
    monkeypatch.setattr(cli, 'discover', lambda *_: Instance(kind='dev', unit='u', scope='user'))
    def run(instance, intro=True):
        seen['intro'] = intro
        return 0
    monkeypatch.setattr(tui, 'run', run)
    assert cli.main(['tui', '--no-intro']) == 0
    assert seen['intro'] is False
