"""Startbild der picam-Konsole: Kameraobjektiv und Punktmatrix-LCD.

Links dreht sich ein schattiertes Objektiv (Fassung als Torus, gewölbtes
Glas mit Glanzlicht), rechts steht der Name als 5×7-Punktmatrix wie auf dem
Displaytech 161A des GSV-2AS. Eine Lesezeile fährt über die Zellen, und die
gelesenen Punkte leuchten auf. Darunter stehen die echten Prüfschritte.

Alles hier ist reine Darstellung: ``lens_cells`` und ``lcd_text`` sind ohne
Terminal testbar, ``Intro`` blendet sich über die Konsole und verschwindet von
selbst, sobald die erste Prüfung fertig ist (jede Taste überspringt).
"""

from __future__ import annotations

import math
import time

import numpy as np
from rich.style import Style
from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

#: HD44780-Zeichensatz (ROM A00), 5×7, nur die benötigten Zeichen.
LCD_FONT = {
    'p': ('.....', '.....', '####.', '#...#', '####.', '#....', '#....'),
    'i': ('..#..', '.....', '.##..', '..#..', '..#..', '..#..', '.###.'),
    'c': ('.....', '.....', '.###.', '#....', '#....', '#...#', '.###.'),
    'a': ('.....', '.....', '.###.', '....#', '.####', '#...#', '.####'),
    'm': ('.....', '.....', '##.#.', '#.#.#', '#.#.#', '#...#', '#...#'),
    ' ': ('.....',) * 7,
}

RING_RAMP = '.,-~:;=!*#$@'
GLASS_RAMP = '.:-=+*#%@'

# Farben (zum Theme der Konsole passend)
_RING_DARK, _RING_LIGHT = (0x24, 0x2c, 0x36), (0xc9, 0xd4, 0xe0)
_GLASS_DARK, _GLASS_LIGHT = (0x10, 0x2a, 0x30), (0x6c, 0xb6, 0xc4)
_SPECULAR = (0xf2, 0xfb, 0xff)
LCD_OFF = '#1d252e'
LCD_UNREAD = '#5b6570'
LCD_READ = '#6cb6c4'
LCD_BEAM = '#a9e3ee'
LEVELS = 10


def _mix(a, b, f: float) -> str:
    f = min(1.0, max(0.0, f))
    return '#' + ''.join(f'{round(x + (y - x) * f):02x}' for x, y in zip(a, b, strict=True))


_RING_STYLES = [Style(color=_mix(_RING_DARK, _RING_LIGHT, i / (LEVELS - 1))) for i in range(LEVELS)]
_GLASS_STYLES = [Style(color=_mix(_GLASS_DARK, _GLASS_LIGHT, i / (LEVELS - 1))) for i in range(LEVELS)]
_SPEC_STYLE = Style(color=_mix(_GLASS_LIGHT, _SPECULAR, 0.85), bold=True)


class Lens:
    """Punktwolke eines Objektivs; ``cells`` projiziert sie für einen Zeitpunkt."""

    R_RING, R_TUBE, R_GLASS = 2.0, 0.42, 1.62
    DISTANCE = 6.0

    def __init__(self, width: int, height: int):
        self.width, self.height = width, height
        density = max(1.0, width / 26)
        theta = np.linspace(0, 2 * np.pi, int(40 * density), endpoint=False)
        phi = np.linspace(0, 2 * np.pi, int(150 * density), endpoint=False)
        t, p = (a.ravel() for a in np.meshgrid(theta, phi))
        ring = np.stack([(self.R_RING + self.R_TUBE * np.cos(t)) * np.cos(p),
                         (self.R_RING + self.R_TUBE * np.cos(t)) * np.sin(p),
                         self.R_TUBE * np.sin(t)], axis=1)
        ring_n = np.stack([np.cos(t) * np.cos(p), np.cos(t) * np.sin(p), np.sin(t)], axis=1)
        radius = np.sqrt(np.linspace(0.0, 1.0, int(22 * density))) * self.R_GLASS
        angle = np.linspace(0, 2 * np.pi, int(110 * density), endpoint=False)
        r, a = (v.ravel() for v in np.meshgrid(radius, angle))
        dome = 0.35 * (1 - (r / self.R_GLASS) ** 2)  # gewölbtes Glas
        glass = np.stack([r * np.cos(a), r * np.sin(a), -dome], axis=1)
        glass_n = np.stack([r * np.cos(a) * 0.45, r * np.sin(a) * 0.45, -np.ones_like(r) * self.R_GLASS], axis=1)
        glass_n /= np.linalg.norm(glass_n, axis=1, keepdims=True)
        self.points = np.concatenate([ring, glass])
        self.normals = np.concatenate([ring_n, glass_n])
        self.is_glass = np.concatenate([np.zeros(len(ring), bool), np.ones(len(glass), bool)])
        light = np.array([-0.55, 0.65, -0.75])
        self.light = light / np.linalg.norm(light)
        half = self.light + np.array([0.0, 0.0, -1.0])
        self.half = half / np.linalg.norm(half)

    @staticmethod
    def angles(t: float) -> tuple[float, float]:
        """Ruhiges Umschauen: Neigen und Schwenken, das Glas bleibt meist sichtbar."""
        return 0.22 + 0.22 * math.sin(t * 0.83), 0.55 * math.sin(t * 0.61)

    def cells(self, t: float):
        """(Zeichen, Stufe, Art) je Zelle; Art 0 leer, 1 Fassung, 2 Glas, 3 Glanzlicht."""
        tilt, pan = self.angles(t)
        ct, st, cp, sp = math.cos(tilt), math.sin(tilt), math.cos(pan), math.sin(pan)
        rot = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]]) @ np.array([[1, 0, 0], [0, ct, -st], [0, st, ct]])
        pts = self.points @ rot.T
        nrm = self.normals @ rot.T
        z = pts[:, 2] + self.DISTANCE
        ooz = 1.0 / z
        scale = self.height * self.DISTANCE * 0.42 / (self.R_RING + self.R_TUBE)
        xs = np.floor(self.width / 2 + 2.0 * scale * ooz * pts[:, 0]).astype(int)
        ys = np.floor(self.height / 2 - scale * ooz * pts[:, 1]).astype(int)
        inside = (xs >= 0) & (xs < self.width) & (ys >= 0) & (ys < self.height)
        index = (ys * self.width + xs)[inside]
        depth = ooz[inside]
        order = np.argsort(-depth, kind='stable')
        cell_ids, first = np.unique(index[order], return_index=True)
        pick = np.flatnonzero(inside)[order[first]]
        glass = self.is_glass[pick]
        n = nrm[pick]
        # Glas von hinten gesehen: Normale zum Betrachter (−z) drehen
        flip = np.where(glass & (n[:, 2] > 0), -1.0, 1.0)[:, None]
        n = n * flip
        diffuse = np.clip(n @ self.light, 0, 1)
        spec = np.clip(n @ self.half, 0, 1) ** 28
        chars = np.full(self.width * self.height, ' ', dtype='<U1')
        level = np.zeros(self.width * self.height, dtype=int)
        kind = np.zeros(self.width * self.height, dtype=int)
        ring_light = 0.10 + 0.75 * diffuse + 0.35 * spec
        glass_light = 0.04 + 0.30 * diffuse ** 2 + 0.9 * spec
        light = np.where(glass, glass_light, ring_light)
        ramp_ring = np.array(list(RING_RAMP))
        ramp_glass = np.array(list(GLASS_RAMP))
        ri = np.clip((light * len(RING_RAMP)).astype(int), 0, len(RING_RAMP) - 1)
        gi = np.clip((light * len(GLASS_RAMP)).astype(int), 0, len(GLASS_RAMP) - 1)
        chars[cell_ids] = np.where(glass, ramp_glass[gi], ramp_ring[ri])
        level[cell_ids] = np.clip((light * LEVELS).astype(int), 0, LEVELS - 1)
        kind[cell_ids] = np.where(glass, np.where(spec > 0.55, 3, 2), 1)
        shape = (self.height, self.width)
        return chars.reshape(shape), level.reshape(shape), kind.reshape(shape)


def lens_text(lens: Lens, t: float) -> Text:
    chars, level, kind = lens.cells(t)
    text = Text(no_wrap=True, overflow='crop')
    for row in range(lens.height):
        for col in range(lens.width):
            k = kind[row, col]
            if k == 0:
                text.append(' ')
            elif k == 1:
                text.append(chars[row, col], _RING_STYLES[level[row, col]])
            elif k == 2:
                text.append(chars[row, col], _GLASS_STYLES[level[row, col]])
            else:
                text.append('@' if chars[row, col] == ' ' else chars[row, col], _SPEC_STYLE)
        if row < lens.height - 1:
            text.append('\n')
    return text


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


class Intro(Vertical):
    """Startbild über der Konsole. Die App ruft ``ready`` mit der ersten Prüfung."""

    can_focus = True
    MIN_S, HOLD_S, MAX_S, STATIC_MIN_S = 2.0, 0.7, 6.0, 0.8
    FPS = 20
    SWEEP_START, SWEEP_S = 0.25, 1.3

    def __init__(self, label: str, version: str | None, ascii_only: bool, animate: bool, **kwargs):
        super().__init__(**kwargs)
        self.label, self.version = label, version
        self.ascii_only, self.animated = ascii_only, animate
        self._started = time.monotonic()
        self._lines: list[tuple[str, str, str, str]] = []  # (Symbol, Farbe, Name, Wert)
        self._ready_at: float | None = None
        self._lens: Lens | None = None
        self._size_key = None
        self._done = False
        self._timer = None
        self.on_done = None

    def compose(self):
        with Horizontal(id='intro-row'):
            yield Static(id='intro-lens')
            with Vertical(id='intro-side'):
                yield Static(id='intro-lcd')
                yield Static(id='intro-tag')
                yield Static(id='intro-checks')
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

    # Größe: Objektiv nach Höhe, LCD gepunktet erst ab genug Breite
    def _layout(self) -> None:
        width, height = self.size.width or self.app.size.width, self.size.height or self.app.size.height
        lens_h = 0
        if height >= 16 and width >= 64:
            lens_h = min(20, max(9, (height - 6) // 2 + 2))
        spaced = width >= lens_h * 2 + 2 + 6 + 58 and height >= 22
        if not spaced and lens_h and width < lens_h * 2 + 2 + 6 + 30:
            lens_h = max(9, (width - 38) // 2 - 1) if width >= 58 else 0
        self._spaced = spaced
        key = (lens_h, spaced)
        if key != self._size_key:
            self._size_key = key
            self._lens = Lens(lens_h * 2 + 2, lens_h) if lens_h else None
            lens_widget = self.query_one('#intro-lens', Static)
            lens_widget.display = self._lens is not None
            if self._lens is not None:
                lens_widget.styles.width = self._lens.width
                lens_widget.styles.height = self._lens.height
            side_height = (7 if spaced else 4) + 1 + 1 + 1 + 3
            top = max(0, (self._lens.height - side_height) // 2) if self._lens is not None else 0
            self.query_one('#intro-side').styles.margin = (top, 0, 0, 0)

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
        frame_t = t if self.animated else 0.6
        if self._lens is not None:
            self.query_one('#intro-lens', Static).update(lens_text(self._lens, frame_t + 1.1))
        if self.animated:
            progress = min(1.0, max(0.0, (t - self.SWEEP_START) / self.SWEEP_S))
        else:
            progress = 1.0
        self.query_one('#intro-lcd', Static).update(
            lcd_text('picam', progress, compact=not self._spaced, ascii_only=self.ascii_only))
        tag = Text('Werkbank-Verwaltung', style='#d6dae0')
        if self.version:
            tag.append(f'  ·  {self.version}', style='#7d8590')
        self.query_one('#intro-tag', Static).update(tag)
        self.query_one('#intro-checks', Static).update(self._checks_text(t))
        hint = Text('Taste: weiter', style='#4a525c')
        self.query_one('#intro-hint', Static).update(hint)
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
