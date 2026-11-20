"""Bildsprache der picam-Konsole: Zeichen, Wertfelder, Abzeichen, Abschnitte, Kacheln, Aktionsleiste.

Eine feste Grammatik, damit man auf einen Blick sieht, was was ist:

========================  =====================================================
Art                       Form
========================  =====================================================
Abschnitt                 Zeichen + kurzer TITEL in Versalien, einmal je Abschnitt
Beschriftung              gedämpft, feste Spalte, nie fett
Live-Wert                 eingelassenes Feld (Rolle ``inset``), heller Text;
                          Einheit gedämpft; Pfade, IDs, Zahlen immer eingelassen;
                          unbekannt „–“
Zustand / Aussage         Abzeichen: Zeichen + Wort auf getönter Fläche
Hilfe                     eine kursive, gedämpfte Zeile mit „›“ (Rest hinter i)
Aktion                    Knopf mit Tastenfeld, Zeichen und Verb
========================  =====================================================

Nie Farbe allein: jedes Abzeichen trägt Zeichen und Wort. Alle Zeichen stehen in
``ICONS`` mit ASCII-Ersatz (``ascii_mode()``). Benutzt werden nur Zeichen, die im
Labor-Terminal (Windows-Konsole über SSH) einspaltig und sauber erscheinen.

Zwei Anordnungen zum Vergleich (``PICAM_LAYOUT``): ``a`` „Karten + Abzeichen“
(jeder Abschnitt eine Karte, Kopf links, Abzeichen rechts) und ``b`` „Kacheln +
Details“ (oben Kacheln mit Zustand und Kennzahl, darunter schlichte Zeilen).
"""

from __future__ import annotations

import os

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Static

from . import probes
from .ui import MUTED, SOFT, TEXT, TONE, Action, P, ascii_mode

DASH = '–'

# ----------------------------------------------------------------- Anordnung
LAYOUTS = ('a', 'b')


def layout_mode() -> str:
    """``PICAM_LAYOUT``: ``a`` (Karten + Abzeichen, Vorgabe) oder ``b`` (Kacheln + Details)."""
    value = os.environ.get('PICAM_LAYOUT', 'a').strip().lower()
    return value if value in LAYOUTS else 'a'


# ----------------------------------------------------------------- Zeichen
#: Name → (Unicode, ASCII). Nur Zeichen, die im Labor-Terminal einspaltig erscheinen;
#: nicht benutzen: ✔ ⚙ ⏸ ⏹ ℹ (zu breit) und Emoji-Darstellungen.
ICONS: dict[str, tuple[str, str]] = {
    # Zustände (immer mit Wort)
    'ok': ('✓', '+'), 'fail': ('✗', 'x'), 'warn': ('▲', '!'), 'off': ('○', '-'), 'unknown': ('?', '?'),
    'on': ('●', '*'), 'busy': ('◐', '~'),
    # Bereiche
    'dashboard': ('⌂', '#'), 'service': ('⏻', 'o'), 'run': ('●', '*'), 'camera': ('◉', 'o'),
    'output': ('⇅', '>'), 'bridge': ('⇄', '='), 'network': ('≋', '~'), 'uart': ('⌁', '-'),
    'cert': ('⚿', 'k'), 'storage': ('▤', '#'), 'clock': ('◷', '@'), 'file': ('⌸', '/'),
    'template': ('⧉', '/'), 'log': ('☰', '='), 'system': ('◆', '+'), 'version': ('⎘', 'v'),
    'setup': ('✎', '*'), 'info': ('ⓘ', 'i'),
    # Handlungen
    'start': ('⏵', '>'), 'stop': ('■', '#'), 'restart': ('↻', '*'), 'connect': ('▸', '>'),
    'open': ('→', '>'), 'fix': ('✎', '*'), 'power': ('⏻', 'o'),
    # Satzzeichen der Bildsprache
    'help': ('›', '>'), 'select': ('▸', '>'), 'sub': ('└', '`'),
}

LEVEL_ICON = {probes.OK: 'ok', probes.WARN: 'warn', probes.FAIL: 'fail', probes.OFF: 'off',
              probes.UNKNOWN: 'unknown'}


def icon(name: str) -> str:
    unicode, plain = ICONS[name]
    return plain if ascii_mode() else unicode


# ----------------------------------------------------------------- Abzeichen
BADGE_BG = {probes.OK: P.tint_ok, probes.WARN: P.tint_warn, probes.FAIL: P.tint_fail,
            probes.OFF: P.tint_off, probes.UNKNOWN: P.tint_off, 'busy': P.tint_info}
BADGE_FG = {**TONE, 'busy': P.accent_strong}


def badge(level: str, word: str, glyph: str | None = None) -> Text:
    """Zustand als Abzeichen: Zeichen + Wort auf getönter Fläche (nie Farbe allein)."""
    mark = icon(glyph or LEVEL_ICON.get(level, 'unknown'))
    text = Text(no_wrap=True, overflow='ellipsis')
    text.append(f' {mark} {word} ', style=f'{BADGE_FG.get(level, MUTED)} on {BADGE_BG.get(level, P.tint_off)}')
    return text


def fact_badge(fact: probes.Fact | None, glyph: str | None = None) -> Text:
    if fact is None:
        return badge(probes.UNKNOWN, 'wird geprüft', 'busy')
    return badge(fact.level, str(fact.value), glyph)


# ----------------------------------------------------------------- Wertfelder
def value(content, unit: str | None = None, *, tone: str | None = None, bold: bool = False) -> Text:
    """Eingelassenes Wertfeld. Unbekannt (None, '') wird ein gedämpftes „–“."""
    bg = f' on {P.inset}'
    text = Text(no_wrap=True)
    if content is None or content == '' or content == DASH:
        text.append(f' {DASH} ', style=f'{MUTED}{bg}')
        return text
    style = f'{"bold " if bold else ""}{tone or TEXT}{bg}'
    text.append(f' {content}', style=style)
    if unit:
        text.append(f' {unit}', style=f'{MUTED}{bg}')
    text.append(' ', style=bg)
    return text


def shorten(text: Text, width: int) -> Text:
    """Auf Zellbreite kürzen, Mitte weglassen (Pfadanfang und Dateiname bleiben)."""
    if text.cell_len <= width or width < 6:
        return text
    keep = width - 1
    head = keep // 3
    tail = keep - head
    out = text[:head]
    out.append('…', style=f'{MUTED} on {P.inset}')
    out.append_text(text[len(text) - tail:])
    return out


def help_line(content: str, key: str | None = None, key_label: str | None = None) -> Text:
    """Eine kursive Hilfezeile „› …“; optional ein Tastenhinweis (z. B. i für mehr)."""
    text = Text(no_wrap=True, overflow='ellipsis')
    text.append(f'{icon("help")} {content}', style=f'italic {MUTED}')
    if key:
        text.append('  ')
        text.append_text(key_chip(key))
        text.append(f' {key_label}', style=f'italic {MUTED}')
    return text


def clip(text: Text, width: int) -> Text:
    """Eine Zeile auf Zellbreite kürzen (Hilfezeilen und Köpfe umbrechen nie)."""
    if width > 0 and text.cell_len > width:
        text = text.copy()
        text.truncate(width, overflow='ellipsis')
    return text


def key_chip(key: str, dim: bool = False) -> Text:
    style = f'{P.disabled_fg} on {P.band}' if dim else f'bold {P.accent} on {P.band}'
    return Text(f' {key} ', style=style)


def first_sentence(hint: str | None) -> str | None:
    if not hint:
        return None
    for end in ('. ', ': '):
        if end in hint:
            return hint.split(end, 1)[0] + ('.' if end == '. ' else '')
    return hint


# ----------------------------------------------------------------- Zeilen und Köpfe
def header(glyph: str, title: str, right: Text | None = None, width: int = 80, note: str | None = None) -> Text:
    """Abschnittskopf: Zeichen + TITEL links, Abzeichen rechts; ``note`` gedämpft nach dem Titel."""
    text = Text(no_wrap=True, overflow='ellipsis')
    text.append(f'{icon(glyph)} ', style=P.accent)
    text.append(title.upper(), style=f'bold {SOFT}')
    if note:
        text.append(f'  {note}', style=MUTED)
    if right is not None:
        gap = width - text.cell_len - right.cell_len
        if gap < 2:
            text.truncate(max(4, width - right.cell_len - 2), overflow='ellipsis')
            gap = width - text.cell_len - right.cell_len
        text.append(' ' * max(1, gap))
        text.append_text(right)
    return text


def fields(rows, width: int, label_w: int = 13, columns: int = 1, gap: int = 3) -> Text:
    """Beschriftung → Wert, als Text (damit Tests den Inhalt lesen können).

    ``rows``: (Beschriftung, Text | str | None[, breit]). ``columns=2`` legt kurze
    Werte paarweise nebeneinander; breite (Pfade) bekommen eine eigene Zeile.
    Zu lange Werte werden in der Mitte gekürzt.
    """
    items = []
    for row in rows:
        label, content = row[0], row[1]
        wide = len(row) > 2 and row[2]
        items.append((label, content if isinstance(content, Text) else value(content), wide))
    col_w = (width - gap) // 2
    lines: list[list[tuple[str, Text, int]]] = []
    index = 0
    while index < len(items):
        label, content, wide = items[index]
        if columns == 2 and index + 1 < len(items):
            nlabel, ncontent, nwide = items[index + 1]
            fits = (not wide and not nwide and label_w + content.cell_len <= col_w
                    and label_w + ncontent.cell_len <= col_w)
            if fits:
                lines.append([(label, content, col_w), (nlabel, ncontent, col_w)])
                index += 2
                continue
        lines.append([(label, content, width)])
        index += 1
    out = Text()
    for number, line in enumerate(lines):
        if number:
            out.append('\n')
        for position, (label, content, room) in enumerate(line):
            if position:
                out.append(' ' * gap)
            cell = Text(label.ljust(label_w - 1)[: label_w - 1] + ' ', style=MUTED)
            content = shorten(content, max(6, room - label_w))
            cell.append_text(content)
            if position == 0 and len(line) > 1:
                cell.append(' ' * max(0, room - cell.cell_len))
            out.append_text(cell)
    return out


# ----------------------------------------------------------------- Abschnitte (Richtung A)
class SectionCard(Static):
    """Karte der Richtung A: Kopf (Zeichen, TITEL, Abzeichen rechts), Zeilen, eine Hilfezeile.

    Inhalt über ``show(head, body, help)`` – fertige Rich-Texte; die Karte ordnet sie an.
    """

    DEFAULT_CSS = '''
    SectionCard { height: auto; width: 1fr; max-width: 120; margin: 1 0 0 0; padding: 0 1;
                  background: $picam-surface; }
    '''

    def inner_width(self, fallback: int = 90) -> int:
        width = self.content_size.width or self.size.width
        return width if width > 0 else fallback

    def show(self, head: Text, body: Text | None = None, hint: Text | None = None) -> None:
        width = self.inner_width()
        text = Text()
        text.append_text(clip(head, width))
        if body is not None and body.plain:
            text.append('\n')
            text.append_text(body)
        if hint is not None and hint.plain:
            text.append('\n')
            text.append_text(clip(hint, width))
        self.update(text)


# ----------------------------------------------------------------- Kacheln (Richtung B)
def tile_text(glyph: str, title: str, state: Text, key: Text | None, width: int) -> Text:
    """Drei Zeilen: Zeichen + TITEL, Abzeichen, Kennzahl (eingelassen)."""
    text = Text(no_wrap=True, overflow='ellipsis')
    text.append(f'{icon(glyph)} ', style=P.accent)
    text.append(title.upper(), style=f'bold {SOFT}')
    text.truncate(width, overflow='ellipsis')
    text.append('\n')
    state = state.copy()
    state.truncate(width, overflow='ellipsis')
    text.append_text(state)
    text.append('\n')
    if key is not None:
        text.append_text(shorten(key, width))
    return text


class Tile(Static):
    """Eine Kachel; ``TileRow`` setzt Inhalt und Auswahl."""

    def on_click(self, event: events.Click) -> None:
        row = self.parent
        if isinstance(row, TileRow):
            event.stop()
            row.focus()
            row.select(row.tiles().index(self), activate=True)


class TileRow(Grid):
    """Reihe von Kacheln; ein Fokuspunkt für alle (← → wählen, Enter löst aus).

    Unter ``min_tile`` Zellen je Kachel bricht die Reihe in zwei Spalten um.
    """

    can_focus = True
    BINDINGS = [Binding('left', 'step(-1)', show=False), Binding('right', 'step(1)', show=False),
                Binding('enter', 'activate', show=False)]
    DEFAULT_CSS = '''
    TileRow { height: auto; width: 1fr; max-width: 120; grid-gutter: 1 1; grid-rows: auto; margin: 1 0 0 0; }
    TileRow Tile { height: auto; padding: 0 1; background: $picam-surface; border-left: wide $picam-surface; }
    TileRow Tile.-sel { background: $picam-raised; border-left: wide $picam-accent; }
    TileRow:focus Tile.-sel { border-left: wide $picam-accent-strong; }
    TileRow:focus { background-tint: 0%; }
    TileRow Tile:hover { background: $picam-raised; }
    '''

    class Selected(Message):
        def __init__(self, row: TileRow, index: int, activate: bool):
            super().__init__()
            self.row, self.index, self.activate = row, index, activate

        @property
        def control(self) -> TileRow:
            return self.row

    def __init__(self, count: int, *, min_tile: int = 20, selectable: bool = True, **kwargs):
        super().__init__(*[Tile(id=f'{kwargs.get("id", "tiles")}-{i}') for i in range(count)], **kwargs)
        self.count, self.min_tile, self.selectable = count, min_tile, selectable
        self.selected = 0

    def tiles(self) -> list[Tile]:
        return list(self.query(Tile))

    def arrange(self, width: int) -> int:
        """Spalten nach Breite; gibt die Innenbreite einer Kachel zurück."""
        width = width or 100
        columns = self.count
        while columns > 1 and (width - (columns - 1)) // columns < self.min_tile:
            columns = (columns + 1) // 2 if columns > 2 else 1
        self.styles.grid_size_columns = columns
        return max(8, (width - (columns - 1)) // columns - 3)

    def set_tile(self, index: int, content: Text) -> None:
        tile = self.tiles()[index]
        tile.update(content)
        tile.set_class(self.selectable and index == self.selected, '-sel')

    def select(self, index: int, activate: bool = False) -> None:
        self.selected = index % self.count
        for number, tile in enumerate(self.tiles()):
            tile.set_class(self.selectable and number == self.selected, '-sel')
        self.post_message(self.Selected(self, self.selected, activate))

    def action_step(self, step: int) -> None:
        self.select(self.selected + step)

    def action_activate(self) -> None:
        self.select(self.selected, activate=True)


class TabBody(VerticalScroll):
    """Scrollender Inhalt eines Tabs mit eigener Aktionsleiste; selbst nicht fokussierbar (Pfeile bleiben bei der App)."""

    can_focus = False


class CardBox(Vertical):
    """Karte der Richtung A als Behälter (wenn ein Kopf bedienbar ist, z. B. eine Auswahlleiste)."""

    DEFAULT_CSS = '''
    CardBox { height: auto; width: 1fr; max-width: 120; margin: 1 0 0 0; padding: 0 1; background: $picam-surface; }
    CardBox > Static { height: auto; width: 1fr; }
    '''


class DetailPanel(Static):
    """Einzelheiten der gewählten Kachel (Richtung B): schlichte Zeilen, Randlinie wie die Auswahl."""

    DEFAULT_CSS = '''
    DetailPanel { height: auto; width: 1fr; max-width: 120; margin: 1 0 0 0; padding: 0 1;
                  border-left: wide $picam-accent; }
    '''

    def inner_width(self, fallback: int = 90) -> int:
        width = self.content_size.width or self.size.width
        return width if width > 0 else fallback


# ----------------------------------------------------------------- Auswahlleiste (Richtung A)
class ChipSelector(Static):
    """Waagerechte Auswahl („Segmente“) mit einem Fokuspunkt: ← → oder Klick wählen.

    ``items``: (Zeichen, Beschriftung, Marke) – die Marke (z. B. „●“) steht hinter
    der Beschriftung und zeigt etwas anderes als die Auswahl (z. B. den Weg im Lauf).
    """

    can_focus = True
    BINDINGS = [Binding('left', 'step(-1)', show=False), Binding('right', 'step(1)', show=False)]
    DEFAULT_CSS = '''
    ChipSelector { height: auto; width: 1fr; }
    ChipSelector:focus { background-tint: 0%; }
    '''

    class Selected(Message):
        def __init__(self, selector: ChipSelector, index: int):
            super().__init__()
            self.selector, self.index = selector, index

        @property
        def control(self) -> ChipSelector:
            return self.selector

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.items: list[tuple[str, str, Text | None]] = []
        self.selected = 0
        self._spans: list[tuple[int, int, int]] = []  # (zeile, von, bis)

    def set_items(self, items, selected: int) -> None:
        self.items, self.selected = list(items), selected
        self._draw()

    def _draw(self) -> None:
        width = self.content_size.width or self.size.width or 96
        text = Text()
        self._spans = []
        line, col = 0, 0
        for index, (glyph, label, mark) in enumerate(self.items):
            chosen = index == self.selected
            chip = Text()
            if chosen:
                base = f'bold {P.select_fg} on {P.select_bg}'
                chip.append(f' {icon("select")} ' if self.has_focus else '   ', style=base)
                chip.append(f'{icon(glyph)} {label}', style=base + (' underline' if self.has_focus else ''))
            else:
                base = f'{SOFT} on {P.control}'
                chip.append('   ', style=base)
                chip.append(f'{icon(glyph)} {label}', style=base)
            if mark is not None:
                chip.append(' ', style=base)
                chip.append_text(mark)
            chip.append(' ', style=base)
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

    def on_click(self, event: events.Click) -> None:
        for index, (line, start, end) in enumerate(self._spans):
            if event.y == line and start <= event.x < end:
                self.choose(index)
                return

    def choose(self, index: int) -> None:
        self.selected = index % max(1, len(self.items))
        self._draw()
        self.post_message(self.Selected(self, self.selected))

    def action_step(self, step: int) -> None:
        self.choose(self.selected + step)


# ----------------------------------------------------------------- Aktionsleiste
def action_label(action: Action) -> Text:
    """Knopfbeschriftung: Tastenfeld, Zeichen, Verb."""
    dim = action.blocked is not None
    text = Text()
    text.append_text(key_chip(action.key, dim))
    text.append(' ')
    if action.icon:
        text.append(f'{icon(action.icon)} ')
    text.append(action.label)
    return text


class ActionBar(Horizontal):
    """Leiste am unteren Rand des Tabs mit den Aktionsknöpfen (id ``buttons``).

    Passen die Knöpfe nicht in eine Zeile, stehen sie im Raster zu zweit.
    """

    DEFAULT_CSS = '''
    ActionBar { height: auto; width: 1fr; max-width: 120; padding: 0; margin: 1 0 0 0; }
    ActionBar.-grid { layout: grid; grid-size: 2; grid-gutter: 0 1; grid-rows: 1; }
    '''

    def __init__(self, **kwargs):
        kwargs.setdefault('id', 'buttons')
        super().__init__(classes='buttons actionbar', **kwargs)

    def fit(self, width: int) -> None:
        buttons = [b for b in self.query('Button') if b.display]
        need = sum(_label_len(b) + 3 for b in buttons)
        self.set_class(width > 0 and need > width, '-grid')


def _label_len(button) -> int:
    label = button.label
    return label.cell_len if isinstance(label, Text) else len(str(label))
