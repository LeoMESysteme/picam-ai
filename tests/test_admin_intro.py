"""Startbild der picam-Konsole: Objektiv und Punktmatrix-LCD ohne Terminal."""

from dispread.admin import intro, tui


def test_logo_is_drawn_by_scan_then_complete():
    shape = sum(row.count('#') for row in intro.LOGO)
    def levels(t, animated=True):
        return [level for row in intro.logo_cells(t, animated=animated) for _, level in row if level]
    early = levels(0.05)
    assert early.count(1) > shape * 0.8  # noch ungelesen: dunkle Punkte
    done = levels(intro.REVEAL_S + 0.2)
    assert len(done) == shape and 1 not in done
    assert levels(0.0, animated=False).count(2) == shape


def test_logo_scales_and_caption_settles():
    cells = intro.logo_cells(5.0, scale=2)
    assert len(cells) == 2 * intro.LOGO_H and len(cells[0]) == 2 * intro.LOGO_W
    assert intro.scramble_caption(intro.CAPTION, 0.1) != intro.CAPTION
    assert intro.scramble_caption(intro.CAPTION, 0.9) == intro.CAPTION
    text = intro.logo_text(3.0, ascii_only=True).plain
    assert text.isascii() and intro.CAPTION in text


def test_logo_shine_passes_over_logo():
    seen = set()
    for step in range(40):
        t = intro.REVEAL_S + 0.4 + step * intro.SHINE_S / 40
        seen |= {level for row in intro.logo_cells(t) for _, level in row}
    assert 4 in seen


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
