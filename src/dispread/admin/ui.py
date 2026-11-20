"""Gemeinsame Bausteine der picam-Konsole: Farben, Zeichen, Dialoge, Darstellung.

Von ``tui`` (App) und ``views`` (Tabs) benutzt, damit die Tabs ohne
Kreisimport auskommen.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import Button, Input, RichLog, Static

from . import probes

SPINNER = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'

SYMBOL = {probes.OK: '✓', probes.WARN: '!', probes.FAIL: '✗', probes.OFF: '○', probes.UNKNOWN: '?'}
ASCII_SYMBOL = {probes.OK: '+', probes.WARN: '!', probes.FAIL: 'x', probes.OFF: '-', probes.UNKNOWN: '?'}
# ----------------------------------------------------------------- Farben
#: Jede Farbe der Konsole kommt aus genau einer aktiven ``Palette``. Rollen statt
#: Farbtöpfe: Flächen in Stufen (Grund < Abschnitt < hervorgehobener Abschnitt),
#: Bänder für Tab- und Statuszeile, Text in drei Stufen, eine Leitfarbe
#: (ME-Türkis) für Auswahl, Fokus und Tasten, dazu die Statustöne. Gewählt wird
#: beim Import über ``PICAM_THEME`` (schiefer | petrol | hell, auch a | b | c).


@dataclass(frozen=True)
class Palette:
    name: str
    label: str
    dark: bool
    # Flächen, von hinten nach vorn
    canvas: str          # Grund hinter allem
    surface: str         # Abschnitte (Karten) eines Tabs
    raised: str          # Abschnitt mit Fokus, Dialoge
    band: str            # Tab-, Status- und Tastenleiste
    line: str            # Trennlinien, leere Balken
    # Text
    text: str
    text_soft: str       # Nebentext, Abschnittsköpfe
    text_muted: str      # Beschriftungen, Einheiten, Hinweise
    # Leitfarbe
    accent: str          # Tasten, Adressen, Balken
    accent_strong: str   # aktiver Tab, Fokus
    on_accent: str       # Schrift auf accent_strong
    accent_deep: str     # Marke, Hauptknopf
    on_accent_deep: str
    secondary: str
    # Status (immer zusammen mit einem Zeichen, nie Farbe allein)
    ok: str
    warn: str
    fail: str
    off: str
    unknown: str
    # Getönte Hinweisflächen
    tint_ok: str
    tint_warn: str
    tint_fail: str
    tint_info: str
    tint_off: str        # Abzeichen „aus“/„unbekannt“
    inset: str           # eingelassenes Wertfeld (Live-Wert, Pfad, Zahl): dunkler als die Fläche
    # Bedienelemente
    control: str         # Knopf
    control_hover: str
    disabled_fg: str
    disabled_bg: str
    field: str           # Eingabefeld
    field_focus: str
    select_bg: str       # Listenauswahl
    select_fg: str
    select_blur_bg: str
    backdrop: str        # Schleier hinter Dialogen (mit Alpha)
    scrollbar: str
    scrollbar_hover: str
    # Besondere Darstellungen
    pin_5v: str
    pin_3v3: str
    lcd_off: str
    lcd_unread: str
    lcd_read: str
    lcd_beam: str
    lcd_beam_off: str
    logo_dim: str        # Logo noch nicht gezeichnet
    logo: str            # ME-Türkis
    logo_bright: str
    logo_flash: str

    def colors(self) -> dict[str, str]:
        """Alle Farbrollen als ``{rolle: hex}``."""
        return {k: v for k, v in self.__dict__.items() if k not in ('name', 'label', 'dark')}

    def variables(self) -> dict[str, str]:
        """CSS-Variablen ``$picam-<rolle>`` für Textual."""
        return {'picam-' + k.replace('_', '-'): v for k, v in self.colors().items()}


#: A „Schiefer“: mittleres Schiefergrau, weiche Stufen, Türkis als einzige Leitfarbe.
SCHIEFER = Palette(
    name='schiefer', label='Schiefer', dark=True,
    canvas='#2c343e', surface='#333c47', raised='#3c4753', band='#242b33', line='#4b5764',
    text='#dde3e9', text_soft='#c0c9d2', text_muted='#adb7c2',
    accent='#45c9be', accent_strong='#62d6cb', on_accent='#0e1b1c', accent_deep='#137a73', on_accent_deep='#f2fbfa',
    secondary='#8fb2e8',
    ok='#97d9ae', warn='#eec977', fail='#f69e94', off='#adb7c2', unknown='#c3b6f2',
    tint_ok='#32463d', tint_warn='#4a4230', tint_fail='#4d3639', tint_info='#2c4b4f',
    tint_off='#3a434e', inset='#21272f',
    control='#47525f', control_hover='#515d6b', disabled_fg='#939da8', disabled_bg='#39424d',
    field='#272e37', field_focus='#225050', select_bg='#225a57', select_fg='#f2fbfa', select_blur_bg='#3c4753',
    backdrop='#161c22b3', scrollbar='#4b5764', scrollbar_hover='#5b6876',
    pin_5v='#e8b86a', pin_3v3='#93acd0',
    lcd_off='#38424e', lcd_unread='#6b7683', lcd_read='#6cc6cc', lcd_beam='#b0e9ee', lcd_beam_off='#36575e',
    logo_dim='#1b4f4c', logo='#00b5af', logo_bright='#77e7db', logo_flash='#ffffff',
)

#: B „Petrol“: Grund ins ME-Petrol getönt, Nebentöne aus derselben Farbe, warmes
#: Bernstein als zweite Farbe für Warnungen.
PETROL = Palette(
    name='petrol', label='Petrol', dark=True,
    canvas='#19373a', surface='#1f4145', raised='#274d52', band='#112b2e', line='#386166',
    text='#e6f0ec', text_soft='#bfd5d0', text_muted='#a3c0bb',
    accent='#33cdc2', accent_strong='#5cdcd2', on_accent='#06201f', accent_deep='#00756f', on_accent_deep='#f2fbfa',
    secondary='#f2b45e',
    ok='#a3deac', warn='#f5b65f', fail='#ff9d8f', off='#a3c0bb', unknown='#cbbcf3',
    tint_ok='#23493d', tint_warn='#4b4128', tint_fail='#4c3438', tint_info='#1c5458',
    tint_off='#264b50', inset='#0f2628',
    control='#30595e', control_hover='#3a666b', disabled_fg='#86a5a1', disabled_bg='#244a4e',
    field='#132f32', field_focus='#11615b', select_bg='#0f6a64', select_fg='#f2fbfa', select_blur_bg='#2b5459',
    backdrop='#0a1a1cb3', scrollbar='#386166', scrollbar_hover='#4a7378',
    pin_5v='#f2b45e', pin_3v3='#93b8d8',
    lcd_off='#2a5054', lcd_unread='#6c8d8a', lcd_read='#5fd0c8', lcd_beam='#b5f0ec', lcd_beam_off='#2f6466',
    logo_dim='#15504d', logo='#00b5af', logo_bright='#77e7db', logo_flash='#ffffff',
)

#: C „Hell“: papierheller Grund, weiße Abschnitte, tiefes Türkis; für helle Laborräume.
HELL = Palette(
    name='hell', label='Hell', dark=False,
    canvas='#ecebe6', surface='#fbfaf7', raised='#e3f2ef', band='#dfe2de', line='#c9cfcc',
    text='#26343a', text_soft='#3e4d54', text_muted='#56636a',
    accent='#006c66', accent_strong='#00615c', on_accent='#ffffff', accent_deep='#00706a', on_accent_deep='#ffffff',
    secondary='#3c5f9e',
    ok='#276a40', warn='#865700', fail='#ad2c24', off='#56636a', unknown='#5d43a8',
    tint_ok='#e2f0e6', tint_warn='#f7ecd3', tint_fail='#f8e1dd', tint_info='#dcefec',
    tint_off='#e6e8e5', inset='#e2e1d9',
    control='#e1e5e3', control_hover='#d3d9d6', disabled_fg='#778186', disabled_bg='#eceeec',
    field='#e3e6e2', field_focus='#cbe8e3', select_bg='#c9e7e2', select_fg='#0f2a29', select_blur_bg='#e6e9e7',
    backdrop='#3a4a4a59', scrollbar='#c2c9c6', scrollbar_hover='#a9b3af',
    pin_5v='#9a5a00', pin_3v3='#3c5f9e',
    lcd_off='#d9dfdc', lcd_unread='#8a979c', lcd_read='#00807a', lcd_beam='#00b5af', lcd_beam_off='#b8dcd8',
    logo_dim='#cfe6e3', logo='#00a19b', logo_bright='#007a75', logo_flash='#0b5753',
)

PALETTES = {p.name: p for p in (SCHIEFER, PETROL, HELL)}
PALETTE_ALIASES = {'a': 'schiefer', 'b': 'petrol', 'c': 'hell'}
DEFAULT_PALETTE = 'schiefer'


def palette_from_env(value: str | None = None) -> Palette:
    """Palette aus ``PICAM_THEME`` (Name oder a/b/c); Unbekanntes fällt auf die Vorgabe zurück."""
    key = (os.environ.get('PICAM_THEME', '') if value is None else value).strip().lower()
    key = PALETTE_ALIASES.get(key, key)
    return PALETTES.get(key, PALETTES[DEFAULT_PALETTE])


P = palette_from_env()

#: Kurznamen der aktiven Palette (bestehender Code benutzt sie direkt).
BG = P.canvas
SURFACE = P.surface
PANEL = P.raised
LINE = P.line
TEXT = P.text
SOFT = P.text_soft
MUTED = P.text_muted
ACCENT = P.accent
ACCENT_DEEP = P.accent_deep
SECONDARY = P.secondary
#: Semantische Farben (Status: genau ein Zeichen + eine Farbe).
TONE = {probes.OK: P.ok, probes.WARN: P.warn, probes.FAIL: P.fail, probes.OFF: P.off, probes.UNKNOWN: P.unknown}
#: Getönte Flächen für Hinweise (Rand in Statusfarbe, Grund leicht eingefärbt).
TINT = {probes.OK: P.tint_ok, probes.WARN: P.tint_warn, probes.FAIL: P.tint_fail, 'info': P.tint_info}


def make_theme(p: Palette) -> Theme:
    return Theme(
        name='picam',
        primary=p.accent_strong,
        secondary=p.secondary,
        accent=p.accent,
        warning=p.warn,
        error=p.fail,
        success=p.ok,
        foreground=p.text,
        background=p.canvas,
        surface=p.surface,
        panel=p.raised,
        dark=p.dark,
        variables={
            **p.variables(),
            'text-muted': p.text_muted,
            'footer-key-foreground': p.accent,
            'footer-description-foreground': p.text_soft,
            'footer-background': p.band,
            'block-cursor-background': p.select_bg,
            'block-cursor-foreground': p.select_fg,
            'block-cursor-text-style': 'bold',
            'block-cursor-blurred-background': p.select_blur_bg,
            'block-cursor-blurred-foreground': p.text,
            'block-cursor-blurred-text-style': 'none',
            'scrollbar': p.scrollbar,
            'scrollbar-background': p.canvas,
            'scrollbar-background-hover': p.canvas,
            'scrollbar-background-active': p.canvas,
            'scrollbar-corner-color': p.canvas,
            'scrollbar-hover': p.scrollbar_hover,
            'scrollbar-active': p.accent,
            'input-cursor-background': p.accent_strong,
            'input-cursor-foreground': p.on_accent,
            'input-selection-background': p.select_bg,
        },
    )


THEME = make_theme(P)


def ascii_mode() -> bool:
    return bool(os.environ.get('PICAM_ASCII')) or 'UTF-8' not in (os.environ.get('LANG', '') +
                                                                   os.environ.get('LC_ALL', '') +
                                                                   os.environ.get('LC_CTYPE', '')).upper()


def symbol(level: str) -> str:
    return (ASCII_SYMBOL if ascii_mode() else SYMBOL)[level]


def fit(text: str, width: int) -> str:
    """Auf Zellbreite kürzen (Rich misst breite Zeichen korrekt)."""
    rendered = Text(text)
    if rendered.cell_len <= width:
        return text
    rendered.truncate(max(1, width), overflow='ellipsis')
    return rendered.plain


def fade_in(widget, start: float = 0.0, duration: float = 0.14) -> None:
    """Kurz einblenden; mit TEXTUAL_ANIMATIONS=none sofort sichtbar."""
    if widget.app.animation_level == 'none':
        return
    widget.styles.opacity = start
    widget.styles.animate('opacity', 1.0, duration=duration, easing='out_cubic')


# ----------------------------------------------------------------- Dialoge



@dataclass
class Confirmation:
    title: str
    lines: list[str]
    commands: list[str]
    action_label: str
    danger: bool = False
    blocker: str | None = None


class ConfirmScreen(ModalScreen[bool]):
    """Bestätigung mit sichtbarem Befehl. Fokus startet auf „Abbrechen“."""

    BINDINGS = [Binding('escape', 'cancel', 'Abbrechen', show=False),
                Binding('left,right', 'switch', show=False)]

    def __init__(self, confirmation: Confirmation):
        super().__init__()
        self.c = confirmation

    def compose(self) -> ComposeResult:
        with Vertical(id='dialog'):
            yield Static(Text(self.c.title, style='bold'), id='dialog-title')
            for line in self.c.lines:
                yield Static(Text(line), classes='dialog-line')
            if self.c.commands:
                yield Static(Text('\n'.join('$ ' + c for c in self.c.commands), style=MUTED), id='dialog-cmd')
            if self.c.blocker:
                yield Static(Text(f'{symbol(probes.WARN)} Gesperrt: {self.c.blocker}', style=TONE[probes.WARN]),
                             id='dialog-blocker')
            with Horizontal(id='dialog-buttons'):
                yield Button('Abbrechen', id='cancel')
                yield Button(self.c.action_label, id='ok', variant='error' if self.c.danger else 'primary',
                             disabled=self.c.blocker is not None)

    def on_mount(self) -> None:
        self.query_one('#cancel', Button).focus()
        fade_in(self.query_one('#dialog'))

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_switch(self) -> None:
        self.focus_next(Button)

    @on(Button.Pressed, '#cancel')
    def _cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, '#ok')
    def _ok(self) -> None:
        self.dismiss(True)


class AskScreen(ModalScreen[str | None]):
    """Eine Eingabe mit Erklärung; Enter übernimmt, Esc bricht ab."""

    BINDINGS = [Binding('escape', 'cancel', 'Abbrechen', show=False)]

    def __init__(self, title: str, lines: list[str], value: str = '', placeholder: str = ''):
        super().__init__()
        self.title_text, self.lines, self.value, self.placeholder = title, lines, value, placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id='dialog'):
            yield Static(Text(self.title_text, style='bold'), id='dialog-title')
            for line in self.lines:
                yield Static(Text(line), classes='dialog-line')
            yield Input(value=self.value, placeholder=self.placeholder, id='ask-input')
            with Horizontal(id='dialog-buttons'):
                yield Button('Abbrechen', id='cancel')
                yield Button('Weiter', id='ok', variant='primary')

    def on_mount(self) -> None:
        self.query_one('#ask-input', Input).focus()
        fade_in(self.query_one('#dialog'))

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted)
    @on(Button.Pressed, '#ok')
    def _ok(self) -> None:
        value = self.query_one('#ask-input', Input).value.strip()
        self.dismiss(value or None)

    @on(Button.Pressed, '#cancel')
    def _cancel(self) -> None:
        self.dismiss(None)




@dataclass
class Action:
    """Aktion eines Tabs: Taste, Beschriftung, Methode der App oder des Tabs, Sperrgrund."""

    key: str
    label: str
    run: object  # Aufrufbar ohne Argumente
    blocked: str | None = None  # Grund, warum gerade nicht möglich (dann ausgegraut)
    danger: bool = False
    icon: str = ''  # Name in ``widgets.ICONS`` (Knopf der Aktionsleiste: Taste, Zeichen, Verb)


@dataclass
class Choice:
    label: str
    value: str
    primary: bool = False
    danger: bool = False


class InfoScreen(ModalScreen[str | None]):
    """Erklärung oder Fehlermeldung mit Wahlmöglichkeiten. Fokus auf der ersten Wahl."""

    BINDINGS = [Binding('escape', 'close', show=False), Binding('left,right', 'switch', show=False)]

    def __init__(self, title: str, lines: list, choices: list[Choice] | None = None, tone: str | None = None):
        super().__init__()
        self.title_text, self.lines, self.tone = title, lines, tone
        self.choices = choices or [Choice('Schließen', 'close', primary=True)]

    def compose(self) -> ComposeResult:
        with Vertical(id='dialog', classes='info' + (f' {self.tone}' if self.tone else '')):
            yield Static(Text(self.title_text, style='bold'), id='dialog-title')
            for line in self.lines:
                yield Static(line if not isinstance(line, str) else Text(line), classes='dialog-line')
            with Horizontal(id='dialog-buttons'):
                for index, choice in enumerate(self.choices):
                    variant = 'error' if choice.danger else 'primary' if choice.primary else 'default'
                    yield Button(choice.label, id=f'choice-{index}', variant=variant)

    def on_mount(self) -> None:
        self.query_one('#choice-0', Button).focus()
        fade_in(self.query_one('#dialog'))

    def action_close(self) -> None:
        self.dismiss(None)

    def action_switch(self) -> None:
        self.focus_next(Button)

    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        index = int((event.button.id or 'choice-0').split('-')[1])
        value = self.choices[index].value
        self.dismiss(None if value == 'close' else value)


def bar(fraction: float, width: int, tone: str = None, ascii_only: bool | None = None) -> Text:
    """Waagerechter Balken mit Achtelschritten; ``fraction`` 0…1."""
    fraction = min(1.0, max(0.0, fraction))
    ascii_only = ascii_mode() if ascii_only is None else ascii_only
    text = Text()
    if ascii_only:
        filled = round(fraction * width)
        text.append('#' * filled, tone or ACCENT)
        text.append('.' * (width - filled), LINE)
        return text
    eighths = round(fraction * width * 8)
    full, part = divmod(eighths, 8)
    text.append('█' * full, tone or ACCENT)
    if part and full < width:
        text.append(' ▏▎▍▌▋▊▉'[part], tone or ACCENT)
        full += 1
    text.append('░' * (width - full), LINE)
    return text


def status_strip(recent: list, width: int, window_ms: int = 60_000) -> Text:
    """60-s-Band aus ``live.status.run.recent`` ([ms_offset, 'v'|'t'|'u'|'s', wert]).

    Jede Zelle fasst ihren Zeitabschnitt zusammen; der schlechteste Status
    gewinnt (unlesbar vor veraltet vor Übergang vor gültig). Leer = keine Daten.
    """
    rank = {'u': 3, 's': 2, 't': 1, 'v': 0}
    colour = {'v': TONE[probes.OK], 't': TONE[probes.WARN], 's': TONE[probes.UNKNOWN], 'u': TONE[probes.FAIL]}
    cells: list[str | None] = [None] * width
    for entry in recent or []:
        try:
            offset, status = int(entry[0]), str(entry[1])
        except (TypeError, ValueError, IndexError):
            continue
        index = min(width - 1, max(0, offset * width // max(1, window_ms)))
        if cells[index] is None or rank.get(status, 0) > rank.get(cells[index], 0):
            cells[index] = status
    text = Text()
    block = '#' if ascii_mode() else '▇'
    for status in cells:
        text.append(block if status else ('.' if ascii_mode() else '·'), colour.get(status, LINE))
    return text


def sparkline(values: list, width: int, tone: str | None = None) -> Text:
    """Kleiner Verlauf aus Zahlen (None = Lücke), rechts die neuesten."""
    ticks = '_.-=*#' if ascii_mode() else '▁▂▃▄▅▆▇█'
    data = list(values)[-width:]
    known = [v for v in data if v is not None]
    text = Text()
    if not known:
        return Text('–', MUTED)
    low, high = min(known), max(known)
    span = (high - low) or 1.0
    for value in data:
        if value is None:
            text.append(' ')
        else:
            text.append(ticks[min(len(ticks) - 1, int((value - low) / span * (len(ticks) - 1)))], tone or ACCENT)
    return text


class Canvas(Widget):
    """Feste Fläche für Einzelbilder (Startbild, Status-/Tastenzeile).

    ``show`` wandelt den Text einmal in fertige Zeilen (Strips) um und zeichnet
    nur diese Fläche neu, ohne Layout und ohne Textual-Umwandlung je Abruf.
    """

    DEFAULT_CSS = 'Canvas { width: auto; height: auto; }'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._content = Text()
        self._strips: list = []

    def show(self, content: Text) -> None:
        from rich.segment import Segment
        from textual.strip import Strip

        self._content = content
        lines = content.split('\n', allow_blank=True) if isinstance(content, Text) else [content]
        self._strips = [Strip(list(Segment.simplify(line.render(_CANVAS_CONSOLE)))) for line in lines]
        self.refresh()

    def render(self) -> Text:  # für Breite/Höhe ``auto`` und Bildschirmfotos
        return self._content

    def render_line(self, y: int):
        from textual.strip import Strip

        width = self.size.width
        base = self.rich_style
        strip = self._strips[y] if y < len(self._strips) else Strip([])
        return strip.crop_extend(0, width, base).apply_style(base)


def _canvas_console():
    import io

    from rich.console import Console

    return Console(file=io.StringIO(), width=1000, color_system='truecolor', force_terminal=True,
                   legacy_windows=False)


_CANVAS_CONSOLE = _canvas_console()


class ReflowLog(RichLog):
    """Protokollfeld, das seine Einträge bei jeder Breitenänderung neu umbricht.

    ``RichLog`` bricht eine Zeile beim Schreiben auf die aktuelle Breite um. Ist
    der Tab gerade verborgen (Breite 0), nimmt es die Mindestbreite von 20 Zeichen
    – die Meldungen standen dann schmal am linken Rand und brauchten mehrere
    Zeilen. Hier merkt sich das Feld die Einträge, schreibt nur bei bekannter Breite
    und baut beim Sichtbarwerden oder Größenwechsel alles neu auf.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._entries: list = []
        self._laid_out_width = 0
        self._dirty = False

    def add(self, renderable, scroll_end: bool | None = None) -> None:
        self._entries.append(renderable)
        if self.max_lines and len(self._entries) > self.max_lines:
            del self._entries[: len(self._entries) - self.max_lines]
        if self._laid_out_width and self._visible_now():
            self.write(renderable, scroll_end=scroll_end)
        else:
            self._dirty = True  # verborgen: erst beim Sichtbarwerden in voller Breite schreiben

    def _visible_now(self) -> bool:
        node = self
        while node is not None and hasattr(node, 'display'):
            if not node.display:
                return False
            node = node.parent
        return self.scrollable_content_region.width > 0

    def on_show(self) -> None:
        self.sync()

    def sync(self) -> None:
        """Nach dem Sichtbarwerden aufrufen (Tabwechsel): verpasste Einträge in voller Breite zeichnen."""
        def check() -> None:
            width = self.scrollable_content_region.width
            if width > 0 and (self._dirty or width != self._laid_out_width):
                self._laid_out_width = width
                self._rebuild()
        self.call_after_refresh(check)

    def replace(self, renderables: list) -> None:
        self._entries = list(renderables)[-(self.max_lines or len(renderables)):] if renderables else []
        self._rebuild()

    def reset(self) -> None:
        self._entries.clear()
        self.clear()

    def on_resize(self, event) -> None:
        width = self.scrollable_content_region.width
        if width > 0 and width != self._laid_out_width:
            self._laid_out_width = width
            self.call_after_refresh(self._rebuild)

    def _rebuild(self) -> None:
        self._dirty = False
        self.clear()
        if not self._laid_out_width:
            return
        for entry in self._entries:
            self.write(entry, scroll_end=False)
        if self.auto_scroll:
            self.scroll_end(animate=False)
