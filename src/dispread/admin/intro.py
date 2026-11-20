"""Startbild der picam-Konsole: ME-Logo und Punktmatrix-LCD.

Links zeichnet ein Messstrahl das ME-Logo (Form und Farben wie in
``me-fastfetch``), danach läuft in Abständen ein Glanzlicht darüber, und der
Schriftzug „M E - M e s s y s t e m e“ rastet Zeichen für Zeichen ein. Rechts
steht „picam“ als 5×7-Punktmatrix wie auf dem Displaytech 161A des GSV-2AS;
eine Lesezeile fährt über die Zellen, und die gelesenen Punkte leuchten auf.
Darunter stehen die echten ersten Prüfergebnisse.

Alles hier ist reine Darstellung: ``logo_cells`` und ``lcd_text`` sind ohne
Terminal testbar, ``Intro`` blendet sich über die Konsole und verschwindet von
selbst, sobald die erste Prüfung fertig ist (jede Taste überspringt).
"""

from __future__ import annotations

import random
import time

from rich.style import Style
from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from .ui import Canvas

#: HD44780-Zeichensatz (ROM A00), 5×7, nur die benötigten Zeichen.
LCD_FONT = {
    'p': ('.....', '.....', '####.', '#...#', '####.', '#....', '#....'),
    'i': ('..#..', '.....', '.##..', '..#..', '..#..', '..#..', '.###.'),
    'c': ('.....', '.....', '.###.', '#....', '#....', '#...#', '.###.'),
    'a': ('.....', '.....', '.###.', '....#', '.####', '#...#', '.####'),
    'm': ('.....', '.....', '##.#.', '#.#.#', '#.#.#', '#...#', '#...#'),
    ' ': ('.....',) * 7,
}

LCD_OFF = '#1d252e'
LCD_UNREAD = '#5b6570'
LCD_READ = '#6cb6c4'
LCD_BEAM = '#a9e3ee'

# ---------------------------------------------------------------- ME-Logo
#: Form aus ~/.config/fastfetch/me-logo.txt (ME-Messsysteme).
LOGO = (
    '####  ####   ####   ##################',
    '####  ####   ####   ##################',
    '####  ####   ####   #####',
    '####  ####   ####   ##################',
    '####  ####   ####   ##################',
    '####         ####   #####',
    '####         ####   ##################',
    '####         ####   ##################',
)
LOGO_W = max(map(len, LOGO))
LOGO_H = len(LOGO)
CAPTION = 'M E - M e s s y s t e m e'
#: Stufen 1 dunkles Petrol … 4 Weiß; 2 ist das ME-Türkis (#00b5af).
LOGO_STYLES = {
    1: Style(color='#0f4744'),
    2: Style(color='#00b5af'),
    3: Style(color='#77e7db', bold=True),
    4: Style(color='#ffffff', bold=True),
}
REVEAL_S = 1.1      # Messstrahl zeichnet das Logo
SHINE_S = 1.3       # Glanzlauf
SHINE_PERIOD = 3.4  # Abstand der Glanzläufe
CAPTION_S = 1.6     # Schriftzug rastet ein


def logo_cells(t: float, scale: int = 1, animated: bool = True) -> list[list[tuple[str, int]]]:
    """Zeichen und Helligkeitsstufe je Zelle (0 = leer) zum Zeitpunkt ``t``."""
    width, height = LOGO_W * scale, LOGO_H * scale
    cells = [[(' ', 0)] * width for _ in range(height)]
    scan = (t / REVEAL_S) * (width + 12) - 3 if animated else width + 99
    shine = None
    if animated and t > REVEAL_S + 0.4:
        phase = ((t - REVEAL_S - 0.4) % SHINE_PERIOD) / SHINE_S
        if phase < 1:
            shine = phase * (width + height * 1.8 + 20) - 10
    for y in range(height):
        row = LOGO[y // scale].ljust(LOGO_W)
        for x in range(width):
            if row[x // scale] != '#':
                if abs(scan - x) < 0.6 and scan < width + 1:
                    cells[y][x] = ('|', 3)
                continue
            distance = scan - x
            if distance < 0:
                cells[y][x] = ('.', 1)
            elif distance < 1.5:
                cells[y][x] = ('@', 4)
            elif distance < 9:
                cells[y][x] = ('#', 3)
            else:
                cells[y][x] = ('#', 2)
                if shine is not None:
                    gap = abs(x + y * 1.8 - shine)
                    if gap < 2:
                        cells[y][x] = ('@', 4)
                    elif gap < 5:
                        cells[y][x] = ('#', 3)
    return cells


def scramble_caption(text: str, phase: float) -> str:
    """Zeichen rotieren und rasten einzeln in fester, gemischter Folge ein."""
    if phase >= 0.82:
        return text
    symbols = '|/-\\+*#%0123456789'
    order = list(range(sum(char != ' ' for char in text)))
    random.Random(23).shuffle(order)
    settle = {index: 0.18 + 0.64 * rank / max(1, len(order) - 1) for rank, index in enumerate(order)}
    tick = int(phase * 48)
    result, index = [], 0
    for char in text:
        if char == ' ':
            result.append(char)
            continue
        rotating = symbols.replace(char, '')
        result.append(char if phase >= settle[index] else rotating[(tick + index * 5) % len(rotating)])
        index += 1
    return ''.join(result)


def logo_text(t: float, scale: int = 1, animated: bool = True, ascii_only: bool = False) -> Text:
    text = Text(no_wrap=True, overflow='crop')
    for row in logo_cells(t, scale, animated):
        run_chars: list[str] = []
        run_level = None
        for char, level in row:
            if level != run_level and run_chars:
                text.append(''.join(run_chars), LOGO_STYLES.get(run_level))
                run_chars = []
            run_level = level
            run_chars.append(char if level else ' ')
        if run_chars:
            text.append(''.join(run_chars), LOGO_STYLES.get(run_level))
        text.append('\n')
    caption = scramble_caption(CAPTION, t / CAPTION_S) if animated else CAPTION
    pad = max(0, (LOGO_W * scale - len(caption)) // 2)
    text.append('\n' + ' ' * pad)
    text.append(caption, LOGO_STYLES[3])
    return text


def logo_size(scale: int) -> tuple[int, int]:
    """Breite und Höhe des Logoblocks samt Schriftzug."""
    return LOGO_W * scale, LOGO_H * scale + 2


# ---------------------------------------------------------------- Punktmatrix
def lcd_columns(word: str) -> int:
    return len(word) * 6 - 1


def lcd_text(word: str, progress: float, compact: bool = False, ascii_only: bool = False) -> Text:
    """Punktmatrix des Worts; ``progress`` 0…1 ist die Lage der Lesezeile.

    Gelesene Punkte (links der Zeile) leuchten in der Akzentfarbe, ungelesene
    sind grau, unbeleuchtete Punkte bleiben schwach sichtbar wie auf dem LCD.
    ``compact`` setzt je zwei Punktzeilen in eine Textzeile (Halbblöcke).
    """
    total = lcd_columns(word)
    beam = progress * (total + 2) - 1
    grid: list[list[str]] = [[] for _ in range(7)]
    for index, char in enumerate(word):
        rows = LCD_FONT.get(char, LCD_FONT[' '])
        for r in range(7):
            if index:
                grid[r].append(' ')
            grid[r].extend(rows[r])

    def colour(col: int, lit: bool) -> str:
        if grid[0][col] == ' ' and not lit:  # Spalte zwischen zwei Zellen
            return ''
        if abs(col - beam) < 0.75:
            return LCD_BEAM if lit else '#2c4a52'
        if not lit:
            return LCD_OFF
        return LCD_READ if col < beam else LCD_UNREAD

    text = Text(no_wrap=True, overflow='crop')
    if compact:
        for pair in range(4):
            top_row, bottom_row = pair * 2, pair * 2 + 1
            for col in range(total):
                top_lit = grid[top_row][col] == '#'
                bottom_lit = bottom_row < 7 and grid[bottom_row][col] == '#'
                gap = grid[0][col] == ' '
                if gap:
                    text.append(' ')
                    continue
                if ascii_only:
                    text.append('#' if (top_lit or bottom_lit) else '.',
                                colour(col, top_lit or bottom_lit))
                    continue
                top_c = colour(col, top_lit)
                bottom_c = colour(col, bottom_lit) if bottom_row < 7 else None
                text.append('▀', Style(color=top_c, bgcolor=bottom_c))
            if pair < 3:
                text.append('\n')
        return text
    lit_char, off_char = ('o', '.') if ascii_only else ('●', '●')
    for r in range(7):
        for col in range(total):
            if grid[r][col] == ' ':
                text.append('  ')
                continue
            lit = grid[r][col] == '#'
            text.append(lit_char if lit else off_char, colour(col, lit))
            text.append(' ')
        if r < 6:
            text.append('\n')
    return text


SPINNER = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'


def logo_frame_key(t: float, animated: bool):
    """Gleicher Schlüssel = gleiches Bild; spart Neuzeichnen zwischen den Glanzläufen."""
    if not animated:
        return 'fest'
    if t < max(REVEAL_S, CAPTION_S) + 0.05:
        return round(t, 3)
    phase = ((t - REVEAL_S - 0.4) % SHINE_PERIOD) / SHINE_S
    return round(t, 3) if phase < 1 else 'fest'


class Intro(Vertical):
    """Startbild über der Konsole. Die App ruft ``ready`` mit der ersten Prüfung."""

    can_focus = True
    MIN_S, HOLD_S, MAX_S, STATIC_MIN_S = 2.4, 0.7, 6.0, 0.8
    FPS = 30
    SWEEP_START, SWEEP_S = 0.9, 1.2

    def __init__(self, label: str, version: str | None, ascii_only: bool, animate: bool, **kwargs):
        super().__init__(**kwargs)
        self.label, self.version = label, version
        self.ascii_only, self.animated = ascii_only, animate
        self._started = time.monotonic()
        self._lines: list[tuple[str, str, str, str]] = []  # (Symbol, Farbe, Name, Wert)
        self._ready_at: float | None = None
        self._scale = 0  # 0: kein Logo
        self._spaced = False
        self._size_key = None
        self._done = False
        self._timer = None
        self.on_done = None
        self._logo_key = None
        self._lcd_key = None
        self._checks_key = None

    def compose(self):
        with Horizontal(id='intro-row'):
            yield Canvas(id='intro-logo')
            with Vertical(id='intro-side'):
                yield Canvas(id='intro-lcd')
                yield Static(id='intro-tag')
                yield Canvas(id='intro-checks')
        yield Static(id='intro-hint')

    def on_mount(self) -> None:
        width, height = self.app.size
        if width < 48 or height < 14:  # zu klein: gleich zur Konsole (zeigt den Größenhinweis)
            self.call_after_refresh(self.finish)
            return
        self._layout()
        self._tick()
        self._timer = self.set_interval(1 / self.FPS if self.animated else 0.1, self._tick)

    def on_resize(self) -> None:
        self._layout()
        self._tick()

    def _layout(self) -> None:
        """Logo doppelt groß nur mit viel Platz; LCD gepunktet erst ab genug Breite."""
        width, height = self.size.width or self.app.size.width, self.size.height or self.app.size.height
        gap, compact_lcd, spaced_lcd, side_text = 5, 29, 58, 32
        if width >= 2 * LOGO_W + gap + spaced_lcd + 4 and height >= 30:
            scale, spaced = 2, True
        elif width >= LOGO_W + gap + spaced_lcd + 4 and height >= 22:
            scale, spaced = 1, True
        elif width >= LOGO_W + gap + max(compact_lcd, side_text) and height >= 16:
            scale, spaced = 1, False
        else:
            scale, spaced = 0, width >= spaced_lcd + 4 and height >= 22
        key = (scale, spaced)
        if key == self._size_key:
            return
        self._size_key = key
        self._scale, self._spaced = scale, spaced
        logo = self.query_one('#intro-logo', Canvas)
        logo.display = scale > 0
        side_height = (7 if spaced else 4) + 3 + 3
        logo_height = logo_size(scale)[1] if scale else side_height
        if scale:
            logo.styles.width, logo.styles.height = logo_size(scale)
            logo.styles.margin = (max(0, (side_height - logo_height) // 2), gap, 0, 0)
        self.query_one('#intro-side').styles.margin = (max(0, (logo_height - side_height) // 2), 0, 0, 0)
        lcd = self.query_one('#intro-lcd', Canvas)
        lcd.styles.width = lcd_columns('picam') * (2 if spaced else 1)
        lcd.styles.height = 7 if spaced else 4
        self._logo_key = self._lcd_key = None
        tag = Text('Werkbank-Verwaltung', style='#d6dae0')
        if self.version:
            tag.append(f'  ·  {self.version}', style='#7d8590')
        self.query_one('#intro-tag', Static).update(tag)
        self.query_one('#intro-hint', Static).update(Text('Taste: weiter', style='#4a525c'))

    def elapsed(self) -> float:
        return time.monotonic() - self._started

    def ready(self, lines: list[tuple[str, str, str, str]]) -> None:
        self._lines = lines
        if self._ready_at is None:
            self._ready_at = self.elapsed()

    def set_lines(self, lines: list[tuple[str, str, str, str]]) -> None:
        self._lines = lines

    def _tick(self) -> None:
        if self._done:
            return
        t = self.elapsed()
        if self._scale:
            key = logo_frame_key(t, self.animated)
            if key != self._logo_key:
                self._logo_key = key
                self.query_one('#intro-logo', Canvas).show(logo_text(t, self._scale, self.animated, self.ascii_only))
        progress = min(1.0, max(0.0, (t - self.SWEEP_START) / self.SWEEP_S)) if self.animated else 1.0
        lcd_key = round(progress * 60)
        if lcd_key != self._lcd_key:
            self._lcd_key = lcd_key
            self.query_one('#intro-lcd', Canvas).show(
                lcd_text('picam', progress, compact=not self._spaced, ascii_only=self.ascii_only))
        checks_key = (int(t * 12), tuple(self._lines), self.version)
        if checks_key != self._checks_key:
            if self._checks_key is not None and self._checks_key[2] != self.version:
                tag = Text('Werkbank-Verwaltung', style='#d6dae0')
                tag.append(f'  ·  {self.version}', style='#7d8590')
                self.query_one('#intro-tag', Static).update(tag)
            self._checks_key = checks_key
            self.query_one('#intro-checks', Canvas).show(self._checks_text(t))
        minimum = self.MIN_S if self.animated else self.STATIC_MIN_S
        if self._ready_at is not None and t >= max(minimum, self._ready_at + (self.HOLD_S if self.animated else 0)):
            self.finish()
        elif t >= self.MAX_S:
            self.finish()

    def _checks_text(self, t: float) -> Text:
        text = Text(no_wrap=True, overflow='ellipsis')
        spin = '*' if self.ascii_only else SPINNER[int(t * 12) % len(SPINNER)] if self.animated else '…'
        for index, (mark, colour, name, value) in enumerate(self._lines):
            if index:
                text.append('\n')
            if mark == 'spin':
                text.append(spin + ' ', '#6cb6c4')
            else:
                text.append(mark + ' ', colour)
            text.append(f'{name:<12}', '#9aa3ad')
            text.append(value, colour if mark != 'spin' else '#7d8590')
        return text

    def finish(self) -> None:
        if self._done:
            return
        self._done = True
        if self._timer is not None:
            self._timer.stop()
        if self.on_done is not None:
            self.on_done()

    def on_key(self, event) -> None:
        if event.key == 'ctrl+c':
            return
        event.stop()
        event.prevent_default()
        self.finish()

    def on_click(self, event) -> None:
        event.stop()
        self.finish()
