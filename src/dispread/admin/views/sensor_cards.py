"""Bedienelemente des Tabs „Sensoren“: Kartenraster (CardGrid), Filterleiste (FilterBar).

Beide zeichnen selbst (wie ``widgets.ChipSelector``): ein Rich-Text je Bild, Klick und Tasten werden aus den
Zellen zurückgerechnet. Das Raster zeigt nur die sichtbaren Kartenzeilen (bei vielen Sensoren bleibt es
schnell) und wählt die Spaltenzahl nach der Breite: 80×24 ergibt zwei Spalten, 120×40 drei.

Kartenhöhe: groß (Rahmen und vier Zeilen), wenn das Raster hoch genug ist, sonst kompakt (zwei Zeilen);
so bleibt auch bei 24 Zeilen mehr als eine Kartenzeile sichtbar. „Aktiv“ ist ein schwerer Akzentrahmen mit
Marke, die Auswahl eine gefüllte Fläche – beides kann auf derselben Karte zusammenfallen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Static

from ..ui import MUTED, SOFT, TEXT, P, ascii_mode
from ..widgets import icon

MIN_CARD_WIDTH = 34
MAX_COLUMNS = 4
FULL_MIN_HEIGHT = 12     # ab dieser Rasterhöhe große Karten
GAP = 1


@dataclass
class Card:
    """Inhalt einer Karte; ``lines`` für die große, ``compact`` für die kompakte Darstellung."""

    key: str
    title: str
    marker: Text | None = None
    lines: list[Text] = field(default_factory=list)
    compact: Text | None = None
    active: bool = False


def fit_line(left: Text, right: Text | None, width: int, base: str) -> Text:
    """Eine Zeile aus linkem Text und rechter Marke auf genau ``width`` Zellen."""
    line = Text(no_wrap=True, style=base)
    right_w = right.cell_len + 1 if right is not None else 0
    cut = left.copy()
    cut.truncate(max(1, width - right_w), overflow='ellipsis')
    line.append_text(cut)
    gap = width - cut.cell_len - (right.cell_len if right is not None else 0)
    line.append(' ' * max(0, gap))
    if right is not None:
        line.append_text(right)
    line.truncate(width)
    return line


def _box(heavy: bool) -> tuple[str, str, str, str, str, str]:
    """(links oben, waagerecht, rechts oben, senkrecht, links unten, rechts unten)"""
    if ascii_mode():
        return ('#', '=', '#', '#', '#', '#') if heavy else ('+', '-', '+', '|', '+', '+')
    return ('┏', '━', '┓', '┃', '┗', '┛') if heavy else ('╭', '─', '╮', '│', '╰', '╯')


class CardGrid(Static):
    """Rasterliste von Karten: Pfeile wählen, Enter oder Klick öffnet, Rad und Bild↑/↓ rollen."""

    can_focus = True
    BINDINGS = [Binding('left', 'move(-1, 0)', show=False), Binding('right', 'move(1, 0)', show=False),
                Binding('up', 'move(0, -1)', show=False), Binding('down', 'move(0, 1)', show=False),
                Binding('home', 'jump(0)', show=False), Binding('end', 'jump(-1)', show=False),
                Binding('pageup', 'page(-1)', show=False), Binding('pagedown', 'page(1)', show=False),
                Binding('enter,space', 'open', show=False)]
    DEFAULT_CSS = '''
    CardGrid { height: 1fr; width: 1fr; max-width: 120; }
    CardGrid:focus { background-tint: 0%; }
    '''

    class Selected(Message):
        def __init__(self, grid: CardGrid, index: int):
            super().__init__()
            self.grid, self.index = grid, index

        @property
        def control(self) -> CardGrid:
            return self.grid

    class Opened(Selected):
        """Enter oder Klick auf eine Karte."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cards: list[Card] = []
        self.selected = 0
        self.empty: list[Text] = []
        self._top = 0   # erste sichtbare Kartenzeile
        self._geometry = (1, 34, 6, 6, 1)

    # ------------------------------------------------------------ Daten
    def set_cards(self, cards: list[Card], keep: str | None = None, empty: list[Text] | None = None) -> None:
        if keep is None and self.cards and self.selected < len(self.cards):
            keep = self.cards[self.selected].key
        self.cards = list(cards)
        self.empty = empty or []
        self.selected = next((i for i, c in enumerate(self.cards) if c.key == keep), 0)
        self._draw(follow=True)

    def current(self) -> Card | None:
        return self.cards[self.selected] if self.cards and self.selected < len(self.cards) else None

    # ------------------------------------------------------------ Geometrie
    def _layout(self) -> tuple[int, int, int, int, int]:
        """(Spalten, Kartenbreite, Kartenhöhe, Zeilenabstand, sichtbare Zeilen)"""
        width = self.content_size.width or self.size.width or 76
        height = self.content_size.height or self.size.height or 10
        scroll = 1 if self._rows_total(width) > self._visible_rows(height, 1) else 0
        usable = width - scroll
        columns = max(1, min(MAX_COLUMNS, (usable + GAP) // (MIN_CARD_WIDTH + GAP)))
        card_w = (usable - GAP * (columns - 1)) // columns
        full = height >= FULL_MIN_HEIGHT
        card_h, pitch = (6, 6) if full else (2, 3)
        return columns, card_w, card_h, pitch, max(1, (height + pitch - card_h) // pitch)

    def _visible_rows(self, height: int, _scroll: int) -> int:
        full = height >= FULL_MIN_HEIGHT
        card_h, pitch = (6, 6) if full else (2, 3)
        return max(1, (height + pitch - card_h) // pitch)

    def _rows_total(self, width: int) -> int:
        columns = max(1, min(MAX_COLUMNS, (width + GAP) // (MIN_CARD_WIDTH + GAP)))
        return -(-len(self.cards) // columns)

    # ------------------------------------------------------------ Zeichnen
    def _draw(self, follow: bool = False) -> None:
        columns, card_w, card_h, pitch, visible = self._geometry = self._layout()
        width = self.content_size.width or self.size.width or 76
        total_rows = -(-len(self.cards) // columns)
        row = self.selected // columns
        if follow:
            if row < self._top:
                self._top = row
            elif row >= self._top + visible:
                self._top = row - visible + 1
        self._top = max(0, min(self._top, max(0, total_rows - visible)))
        self.call_after_refresh(self._settle)
        if not self.cards:
            lines = [fit_line(line, None, width, '') for line in self.empty]
            self.update(Text('\n').join(lines) if lines else Text(''))
            return
        scrollbar = total_rows > visible
        lines: list[Text] = []
        canvas = f'{MUTED} on {P.canvas}'
        for r in range(self._top, min(total_rows, self._top + visible)):
            blocks = []
            for c in range(columns):
                index = r * columns + c
                blocks.append(self._card_lines(self.cards[index], card_w, card_h, index == self.selected)
                              if index < len(self.cards) else [Text(' ' * card_w, style=canvas)] * card_h)
            for y in range(card_h):
                line = Text(no_wrap=True, style=canvas)
                for c, block in enumerate(blocks):
                    if c:
                        line.append(' ' * GAP)
                    line.append_text(block[y])
                lines.append(line)
            if pitch > card_h and r < min(total_rows, self._top + visible) - 1:
                lines.extend(Text(' ' * (width - (1 if scrollbar else 0)), style=canvas)
                             for _ in range(pitch - card_h))
        if scrollbar:
            self._add_scrollbar(lines, total_rows, visible)
        self.update(Text('\n').join(lines))

    def _settle(self) -> None:
        """Nach dem Layout prüfen, ob die Maße beim Zeichnen schon stimmten (erstes Bild, Klassenwechsel)."""
        if self._layout() != self._geometry:
            self._draw(follow=True)

    def _add_scrollbar(self, lines: list[Text], total_rows: int, visible: int) -> None:
        height = len(lines)
        thumb = max(1, round(height * visible / total_rows))
        start = round((height - thumb) * self._top / max(1, total_rows - visible))
        track, bar = ('.', '#') if ascii_mode() else ('│', '█')
        for y, line in enumerate(lines):
            on = start <= y < start + thumb
            line.append(bar if on else track, style=f'{P.accent if on else P.line} on {P.canvas}')

    def _card_lines(self, card: Card, width: int, height: int, selected: bool) -> list[Text]:
        focused = self.has_focus
        if selected and focused:
            bg, fg = P.select_bg, P.select_fg
        elif selected:
            bg, fg = P.select_blur_bg, TEXT
        else:
            bg, fg = P.surface, TEXT
        base = f'{fg} on {bg}'
        title = Text(card.title, style=f'bold {fg}')
        if height == 2:   # kompakt: Leiste links, zwei Zeilen
            bar_style = f'{P.accent_strong if card.active else bg} on {bg}'
            mark = '|' if ascii_mode() else '▌'
            first = fit_line(title, card.marker, width - 2, base)
            second = fit_line(card.compact or Text(''), None, width - 2, f'{MUTED if not selected else SOFT} on {bg}')
            out = []
            for body in (first, second):
                line = Text(no_wrap=True, style=base)
                line.append(mark, style=bar_style)
                line.append(' ', style=base)
                line.append_text(body)
                out.append(line)
            return out
        heavy = card.active
        tl, hz, tr, vt, bl, br = _box(heavy)
        border = f'{P.accent_strong if heavy else P.accent if selected else P.line} on {bg}'
        inner = width - 4
        out = [Text(tl + hz * (width - 2) + tr, style=border, no_wrap=True)]
        rows = [fit_line(title, card.marker, inner, base)]
        for text in (card.lines + [Text('')] * 3)[:3]:
            rows.append(fit_line(text, None, inner, f'{MUTED if not selected else SOFT} on {bg}'))
        for body in rows:
            line = Text(no_wrap=True, style=base)
            line.append(vt + ' ', style=border)
            line.append_text(body)
            line.append(' ' + vt, style=border)
            out.append(line)
        out.append(Text(bl + hz * (width - 2) + br, style=border, no_wrap=True))
        return out

    # ------------------------------------------------------------ Ereignisse
    def on_focus(self) -> None:
        self._draw()

    def on_blur(self) -> None:
        self._draw()

    def on_resize(self) -> None:
        self._draw(follow=True)

    def _select(self, index: int, *, announce: bool = True) -> None:
        index = max(0, min(len(self.cards) - 1, index))
        if index == self.selected:
            return
        self.selected = index
        self._draw(follow=True)
        if announce:
            self.post_message(self.Selected(self, index))

    def action_move(self, dx: int, dy: int) -> None:
        if not self.cards:
            if dy:
                self._leave(dy)
            return
        columns = self._geometry[0]
        if dy:
            target = self.selected + dy * columns
            if target < 0 or target >= len(self.cards):
                if dy > 0 and self.selected // columns < (len(self.cards) - 1) // columns:
                    self._select(len(self.cards) - 1)   # letzte, kürzere Zeile
                else:
                    self._leave(dy)
                return
            self._select(target)
        elif dx:
            self._select(self.selected + dx)

    def _leave(self, step: int) -> None:
        mover = getattr(self.app, 'move_focus', None)
        if mover is not None:
            mover(step)

    def action_jump(self, where: int) -> None:
        self._select(0 if where == 0 else len(self.cards) - 1)

    def action_page(self, step: int) -> None:
        columns, _w, _h, _p, visible = self._geometry
        self._select(self.selected + step * columns * visible)

    def action_open(self) -> None:
        if self.cards:
            self.post_message(self.Opened(self, self.selected))

    def _scroll_rows(self, step: int) -> None:
        columns, _w, _h, _p, visible = self._geometry
        total_rows = -(-len(self.cards) // columns)
        self._top = max(0, min(self._top + step, max(0, total_rows - visible)))
        self._draw()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        event.stop()
        self._scroll_rows(1)

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        event.stop()
        self._scroll_rows(-1)

    def on_click(self, event: events.Click) -> None:
        columns, card_w, card_h, pitch, _visible = self._geometry
        row, inside = divmod(event.y, pitch)
        col, within = divmod(event.x, card_w + GAP)
        index = (self._top + row) * columns + col
        if inside >= card_h or within >= card_w or col >= columns or not 0 <= index < len(self.cards):
            return
        self.focus()
        self._select(index)
        self.post_message(self.Opened(self, index))


class FilterBar(Static):
    """Filtergruppen in einer Zeile (bei Platzmangel zwei): ← → wählt die Gruppe, Enter/Leertaste schaltet weiter.

    ``groups``: (Schlüssel, Beschriftung, [(Wert, Text), …]); der erste Wert jeder Gruppe ist „alle“.
    Eine gesetzte Gruppe trägt eine Marke, damit man sieht, dass gefiltert wird.
    """

    can_focus = True
    BINDINGS = [Binding('left', 'group(-1)', show=False), Binding('right', 'group(1)', show=False),
                Binding('enter,space', 'cycle(1)', show=False), Binding('backspace', 'cycle(-1)', show=False)]
    DEFAULT_CSS = '''
    FilterBar { height: auto; width: 1fr; max-width: 120; }
    FilterBar:focus { background-tint: 0%; }
    '''

    class Changed(Message):
        def __init__(self, bar: FilterBar):
            super().__init__()
            self.bar = bar

        @property
        def control(self) -> FilterBar:
            return self.bar

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.groups: list[tuple[str, str, list[tuple[str, str]]]] = []
        self.values: dict[str, str] = {}
        self.cursor = 0
        self._spans: list[tuple[int, int, int]] = []

    def set_groups(self, groups) -> None:
        self.groups = list(groups)
        for key, _label, options in self.groups:
            if self.values.get(key) not in {value for value, _ in options}:
                self.values[key] = options[0][0]
        self.cursor = min(self.cursor, max(0, len(self.groups) - 1))
        self._draw()

    def active(self) -> dict[str, str]:
        """Nur die gesetzten Filter (Wert ungleich „alle“)."""
        return {key: self.values[key] for key, _l, options in self.groups if self.values[key] != options[0][0]}

    def reset(self) -> None:
        for key, _label, options in self.groups:
            self.values[key] = options[0][0]
        self._draw()
        self.post_message(self.Changed(self))

    def _draw(self) -> None:
        width = self.content_size.width or self.size.width or 96
        text = Text(no_wrap=False)
        self._spans = []
        line, col = 0, 0
        for index, (key, label, options) in enumerate(self.groups):
            value = self.values.get(key, options[0][0])
            shown = next(name for val, name in options if val == value)
            on = value != options[0][0]
            chosen = self.has_focus and index == self.cursor
            if chosen:
                base = f'bold {P.select_fg} on {P.select_bg}'
            else:
                base = f'{P.accent_strong if on else SOFT} on {P.control}'
            chip = Text(style=base)
            chip.append(f' {label}: ')
            chip.append(shown, style=f'bold {base}')
            chip.append(f' {icon("on") if on else icon("filter")} ' if not chosen else f' {icon("select")} ')
            if col and col + 1 + chip.cell_len > width:
                text.append('\n')
                line, col = line + 1, 0
            elif col:
                text.append(' ')
                col += 1
            self._spans.append((line, col, col + chip.cell_len))
            text.append_text(chip)
            col += chip.cell_len
        self.update(text)

    def on_focus(self) -> None:
        self._draw()

    def on_blur(self) -> None:
        self._draw()

    def on_resize(self) -> None:
        self._draw()

    def action_group(self, step: int) -> None:
        if self.groups:
            self.cursor = (self.cursor + step) % len(self.groups)
            self._draw()

    def action_cycle(self, step: int) -> None:
        if not self.groups:
            return
        key, _label, options = self.groups[self.cursor]
        values = [value for value, _ in options]
        self.values[key] = values[(values.index(self.values[key]) + step) % len(values)]
        self._draw()
        self.post_message(self.Changed(self))

    def on_click(self, event: events.Click) -> None:
        for index, (line, start, end) in enumerate(self._spans):
            if event.y == line and start <= event.x < end:
                self.cursor = index
                self.focus()
                self.action_cycle(1)
                return
