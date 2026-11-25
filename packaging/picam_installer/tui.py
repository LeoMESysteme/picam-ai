"""Terminal-Bausteine des geführten Installers: Ausgabe, Menüs, Spinner, Logo.

Nur Standardbibliothek (``termios`` für Tasten), keine Produktimporte.

* ``Out`` schreibt Statuszeilen, Abschnittsbänder, Karten (abgestufter Hintergrund)
  und Abzeichen (OK/WARNUNG/FEHLER/AUS) in der Formsprache der picam-Konsole
  (Palette „Schiefer“, Truecolor; ``PICAM_COLORS=256|16`` oder ``TERM=linux``
  rechnen herunter). Farbe nur im Terminal und ohne ``NO_COLOR``, ASCII-Zeichen
  ohne UTF-8 oder mit ``NO_COLOR``; ohne Terminal einfache Zeilen. Nie benutzt
  werden ✔ ⚙ ⏸ ⏹ ℹ (verrutschen im Windows-Terminal über SSH).
* ``Menus`` fragt mit Pfeiltasten (↑/↓, j/k), Enter, Leertaste, Ziffern und
  Esc/q. Nur wenn stdin und stdout ein Terminal sind und ``TERM`` nicht
  ``dumb`` ist; sonst nimmt ``guided`` die bisherige Texteingabe.
* ``Progress`` zeigt laufende Schritte mit Spinner und Laufzeit, fertige mit
  ✓/✗ und einen Gesamtbalken. Ohne Terminal (Pipe, Datei) einfache Zeilen,
  nie Steuerzeichen; nichts wartet künstlich.
* ``play_intro`` zeigt das ME-Logo höchstens 1,4 s (jede Taste überspringt).

Der Tastenmodus wird auf jedem Ausgang zurückgesetzt, auch bei Strg+C und
SIGTERM, und der Cursor wieder eingeblendet.
"""
from __future__ import annotations

import os
import random
import select
import shutil
import signal
import sys
import textwrap
import threading
import time
from contextlib import contextmanager

try:  # POSIX; ohne termios gibt es nur die Texteingabe
    import termios
except ImportError:  # pragma: no cover
    termios = None

# ME-Türkis wie in me-fastfetch und der picam-Konsole (#00b5af).
TEAL = '38;2;0;181;175'
TEAL_DIM = '38;2;27;79;76'
TEAL_BRIGHT = '1;38;2;119;231;219'
FLASH = '1;97'
#: Palette „Schiefer“ der Konsole (dispread.admin.ui), als Hex für Truecolor/256/16.
PALETTE = {
    'canvas': '#2c343e', 'surface': '#333c47', 'raised': '#3c4753', 'band': '#242b33', 'line': '#4b5764',
    'text': '#dde3e9', 'soft': '#c0c9d2', 'muted': '#adb7c2',
    'accent': '#45c9be', 'accent_strong': '#62d6cb', 'on_accent': '#0e1b1c', 'accent_deep': '#137a73',
    'ok': '#97d9ae', 'warn': '#eec977', 'fail': '#f69e94', 'off': '#adb7c2',
    'tint_ok': '#32463d', 'tint_warn': '#4a4230', 'tint_fail': '#4d3639', 'tint_off': '#3a434e',
    'tint_info': '#2c4b4f', 'inset': '#21272f', 'select_bg': '#225a57', 'select_fg': '#f2fbfa',
}
BADGES = {'ok': ('OK', 'ok', 'tint_ok'), 'warn': ('WARNUNG', 'warn', 'tint_warn'),
          'fail': ('FEHLER', 'fail', 'tint_fail'), 'off': ('AUS', 'off', 'tint_off')}
CODES = {'ok': '32', 'warn': '33', 'fail': '31', 'step': TEAL, 'ask': TEAL, 'set': TEAL}

UTF8 = {'ok': '✓', 'warn': '▲', 'fail': '✗', 'step': '›', 'ask': '?', 'set': '›', 'pointer': '▸',
        'on': '●', 'off': '○', 'arrow': '→', 'spin': '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏', 'full': '█',
        'eighths': ' ▏▎▍▌▋▊▉', 'track': '─', 'keys': '↑↓', 'dot': '·',
        'idle': '○', 'card': '◆', 'edge': '▌', 'help': '›'}
ASCII = {'ok': '+', 'warn': '!', 'fail': 'x', 'step': '-', 'ask': '?', 'set': '>', 'pointer': '>',
         'on': '[x]', 'off': '[ ]', 'arrow': '->', 'spin': '|/-\\', 'full': '#',
         'eighths': None, 'track': '.', 'keys': 'Pfeile', 'dot': '-',
         'idle': '-', 'card': '#', 'edge': '|', 'help': '>'}

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
CAPTION = 'M E - M e s s y s t e m e'
INTRO_S = 1.4


def _isatty(stream):
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


class Caps:
    """Was das Terminal kann: ``live`` (Steuerzeichen), ``interactive`` (Tasten), Farbe, UTF-8."""

    def __init__(self, stream, stdin=None, env=None):
        env = os.environ if env is None else env
        dumb = env.get('TERM', '') == 'dumb'
        no_color = bool(env.get('NO_COLOR'))
        self.live = _isatty(stream) and not dumb
        self.interactive = self.live and stdin is not None and _isatty(stdin) and termios is not None
        self.color = self.live and not no_color
        self.depth = color_depth(env)
        encoding = (getattr(stream, 'encoding', None) or '').lower().replace('-', '')
        locale = ''.join(env.get(name, '') for name in ('LC_ALL', 'LC_CTYPE', 'LANG')).upper().replace('-', '')
        self.utf8 = not no_color and ('utf8' in encoding or 'UTF8' in locale)


def color_depth(env):
    """``'true'`` (Vorgabe wie in der Konsole, auch ohne COLORTERM über SSH), ``'256'`` oder ``'16'``."""
    wanted = (env.get('PICAM_COLORS') or '').strip().lower()
    if wanted in ('16', '8'):
        return '16'
    if wanted == '256':
        return '256'
    if wanted in ('truecolor', '24bit', 'true', '16m'):
        return 'true'
    return '16' if env.get('TERM') == 'linux' else 'true'


def hex_rgb(color):
    color = color.lstrip('#')
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _index256(r, g, b):
    if abs(r - g) < 8 and abs(g - b) < 8:  # Grautreppe
        gray = round((r - 8) / 10) if r > 8 else 0
        if 0 <= gray <= 23:
            return 232 + gray
    return 16 + 36 * round(r / 51) + 6 * round(g / 51) + round(b / 51)


def _index16(r, g, b):
    return (r > 127) | ((g > 127) << 1) | ((b > 127) << 2), max(r, g, b) > 200


def color_code(kind, rgb, depth):
    """SGR-Teil für Vorder-(``fg``) oder Hintergrund (``bg``); mit 16 Farben gibt es keinen Hintergrund."""
    base = 38 if kind == 'fg' else 48
    if depth == 'true':
        return f'{base};2;{rgb[0]};{rgb[1]};{rgb[2]}'
    if depth == '256':
        return f'{base};5;{_index256(*rgb)}'
    if kind == 'bg':
        return ''
    index, bright = _index16(*rgb)
    return str((90 if bright else 30) + index)


def downgrade(code, depth):
    """Truecolor-Teile einer SGR-Folge (``38;2;r;g;b``) auf die Farbtiefe des Terminals umrechnen."""
    if depth == 'true' or ';2;' not in code:
        return code
    parts, out, index = code.split(';'), [], 0
    while index < len(parts):
        if parts[index] in ('38', '48') and parts[index + 1:index + 2] == ['2'] and index + 4 < len(parts):
            rgb = tuple(int(v) for v in parts[index + 2:index + 5])
            piece = color_code('fg' if parts[index] == '38' else 'bg', rgb, depth)
            if piece:
                out.append(piece)
            index += 5
        else:
            out.append(parts[index])
            index += 1
    return ';'.join(out)


def visible(text):
    """Länge ohne ANSI-Steuerfolgen."""
    length, escape = 0, False
    for char in text:
        if escape:
            escape = not ('@' <= char <= '~' and char != '[')
        elif char == '\x1b':
            escape = True
        else:
            length += 1
    return length


def duration(seconds):
    if seconds < 60:
        return f'{seconds:.1f} s'
    return f'{int(seconds // 60)}:{int(seconds % 60):02d} min'


class Out:
    """Zeilen mit Statuszeichen; Farbe nur im Terminal und ohne NO_COLOR."""

    def __init__(self, stream=None, color=None, stdin=None, env=None):
        self.stream = stream or sys.stdout
        self.caps = Caps(self.stream, stdin if stdin is not None else sys.stdin, env)
        self.color = self.caps.color if color is None else bool(color)
        self.sym = UTF8 if self.caps.utf8 else ASCII
        self.depth = self.caps.depth
        self.lock = threading.RLock()

    @property
    def live(self):
        return self.caps.live

    def paint(self, text, code):
        if not (self.color and code):
            return text
        return f'\033[{downgrade(code, self.depth)}m{text}\033[0m'

    def style(self, text, fg=None, bg=None, bold=False, dim=False, italic=False):
        """Text mit Palettenfarben (Namen aus ``PALETTE``); ohne Farbe unverändert."""
        if not self.color or not text:
            return text
        codes = (['1'] if bold else []) + (['2'] if dim else []) + (['3'] if italic else [])
        if fg:
            codes.append(color_code('fg', hex_rgb(PALETTE[fg]), self.depth))
        if bg:
            codes.append(color_code('bg', hex_rgb(PALETTE[bg]), self.depth))
        codes = [c for c in codes if c]
        return f'\033[{";".join(codes)}m{text}\033[0m' if codes else text

    def badge(self, kind, pad=False):
        """Zustand als Abzeichen: Zeichen + Wort auf getönter Fläche (ohne Farbe ``[OK]``)."""
        word, tone, tint = BADGES[kind]
        if not self.color:
            return f'[{word}]'
        mark = self.sym['idle' if kind == 'off' else kind]
        return self.style(f' {mark} {word.ljust(7) if pad else word} ', fg=tone, bg=tint)

    def columns(self):
        return max(40, shutil.get_terminal_size((80, 24)).columns)

    def card_width(self):
        return max(36, min(100, self.columns() - 4))

    def write(self, text):
        with self.lock:
            self.stream.write(text)
            self.stream.flush()

    def line(self, text=''):
        self.write(text + '\n')

    def title(self, text):
        self.line()
        self.line(self.paint(text, '1'))

    def rule(self, text):
        """Abschnittsband (Konsolen-Kopf: Zeichen + TITEL auf dunklem Band); ohne Terminal eine Titelzeile."""
        if not self.live:
            return self.title(text)
        width = self.card_width()
        band = f' {self.sym["card"]} {text.upper()}'
        self.line()
        if not self.color:
            self.line(self.paint(f'{self.sym["track"] * 2} {text} ', '1')
                      + self.sym['track'] * max(0, width - len(text) - 4))
            return
        head = self.style(f' {self.sym["card"]} ', fg='accent', bg='band') + self.style(
            text.upper(), fg='soft', bg='band', bold=True)
        self.line('  ' + head + self.style(' ' * max(0, width - visible(band) - 1), bg='band'))

    def status(self, kind, label, text):
        if self.live and self.color and kind in BADGES:
            return self.line(f'  {self.badge(kind, True)} {label:<15} {text}')
        self.line(f'  {self.paint(self.sym[kind], CODES[kind])} {label:<16} {text}')

    def card(self, title, rows=(), badge=None, hint=None):
        """Karte der Konsole: Kopf (Zeichen, TITEL, Abzeichen rechts), Zeilen, eine Hilfezeile.

        ``rows``: (Beschriftung, Text[, Stufe]); ``Stufe`` ok|warn|fail|off setzt ein Abzeichen vor
        den Text. Im Terminal mit abgestuftem Hintergrund und Randstreifen, sonst Titel und
        Statuszeilen wie bisher.
        """
        rows = [tuple(row) + (None,) * (3 - len(row)) for row in rows]
        if not self.live:
            self.rule(title)
            for label, text, kind in rows:
                if kind:
                    self.status(kind, label, text)
                else:
                    self.line(f'  {label:<16} {text}'.rstrip())
            if hint:
                self.line('  ' + self.dim(hint))
            return
        width = self.card_width()
        inner = width - 2  # Randstreifen + Leerzeichen
        sym = self.sym
        edge = self.style(sym['edge'], fg='accent', bg='surface') + self.style(' ', bg='surface')

        def line(parts, plain):
            pad = max(0, inner - plain)
            self.line('  ' + edge + ''.join(parts) + self.style(' ' * pad, bg='surface'))

        self.line()
        head = f'{sym["card"]} {title.upper()}'
        right = self.badge(badge) if badge else ''
        gap = max(1, inner - len(head) - (visible(right) if right else 0) - 1)
        parts = [self.style(f'{sym["card"]} ', fg='accent', bg='surface'),
                 self.style(title.upper(), fg='soft', bg='surface', bold=True)]
        if right:
            parts += [self.style(' ' * gap, bg='surface'), right]
        line(parts, len(head) + (gap + visible(right) if right else 0))
        label_w = min(18, max([len(label) for label, _, _ in rows] + [8]) + 1)
        lead = 12 if any(kind for _, _, kind in rows) else 0  # Breite eines Abzeichens samt Lücke
        for label, text, kind in rows:
            mark = (self.badge(kind, True) + self.style(' ', bg='surface') if kind
                    else self.style(' ' * lead, bg='surface'))
            room = max(12, inner - label_w - lead - 1)
            pieces = textwrap.wrap(str(text), room, break_long_words=True, break_on_hyphens=False) or ['']
            for number, piece in enumerate(pieces):
                head = self.style(label.ljust(label_w)[:label_w] if not number else ' ' * label_w,
                                  fg='muted', bg='surface')
                lead_part = mark if not number else self.style(' ' * lead, bg='surface')
                line([head, lead_part, self.style(piece, fg='text', bg='surface')], label_w + lead + len(piece))
        if hint:
            text = f'{sym["help"]} {hint}'
            if len(text) > inner - 1:
                text = text[:inner - 4] + '...'
            line([self.style(text, fg='muted', bg='surface', italic=True)], len(text))

    def step(self, text):
        self.line(f'  {self.paint(self.sym["step"], TEAL)} {text}')

    def dim(self, text):
        return self.paint(text, '2')

    def task(self, label, quiet=False):
        """Ein einzelner langer Schritt: Spinner mit Laufzeit, danach verschwindet die Zeile."""
        return Progress(self, None, keep=False, label=label, quiet=quiet)

    def progress(self, total):
        """Schrittliste mit ✓/✗, Spinner und Gesamtbalken."""
        return Progress(self, total)


class LiveBlock:
    """Mehrzeiliger Bereich ab der aktuellen Zeile, an Ort und Stelle neu gezeichnet."""

    def __init__(self, out):
        self.out, self.lines = out, 0

    def _home(self):
        return '\r' + (f'\033[{self.lines - 1}A' if self.lines > 1 else '') + '\033[J'

    def draw(self, lines):
        columns = max(20, shutil.get_terminal_size((80, 24)).columns) - 1
        fitted = [fit(line, columns) for line in lines]
        self.out.write(self._home() + '\n'.join(fitted))
        self.lines = len(fitted)

    def clear(self):
        if self.lines:
            self.out.write(self._home())
            self.lines = 0


def fit(line, columns):
    """Sichtbaren Text auf ``columns`` kürzen, Steuerfolgen behalten."""
    if visible(line) <= columns:
        return line
    result, count, escape = [], 0, False
    for char in line:
        if escape:
            result.append(char)
            escape = not ('@' <= char <= '~' and char != '[')
            continue
        if char == '\x1b':
            escape = True
            result.append(char)
            continue
        if count >= columns:
            continue
        result.append(char)
        count += 1
    return ''.join(result) + '\033[0m'


# ---------------------------------------------------------------- Tasten
def _terminate(signum, _frame):
    raise SystemExit(128 + signum)


@contextmanager
def keys(out):
    """Tasten einzeln lesen (ohne Echo), Cursor aus; alles wird sicher zurückgesetzt."""
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    settings = termios.tcgetattr(fd)
    settings[3] &= ~(termios.ICANON | termios.ECHO)
    settings[6][termios.VMIN] = 1
    settings[6][termios.VTIME] = 0
    previous = {}
    if threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGTERM, signal.SIGHUP):
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, _terminate)
    try:
        termios.tcsetattr(fd, termios.TCSANOW, settings)
        out.write('\033[?25l')
        yield fd
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSANOW, original)
        finally:
            out.write('\033[?25h')
            for signum, handler in previous.items():
                signal.signal(signum, handler if handler is not None else signal.SIG_DFL)


SEQUENCES = {b'[A': 'up', b'OA': 'up', b'[B': 'down', b'OB': 'down', b'[C': 'right', b'OC': 'right',
             b'[D': 'left', b'OD': 'left', b'[H': 'home', b'OH': 'home', b'[F': 'end', b'OF': 'end',
             b'[1~': 'home', b'[4~': 'end', b'[Z': 'up'}


def read_key(fd):
    """Eine Taste: ``up``/``down``/``left``/``right``/``enter``/``space``/``esc``/``tab`` oder das Zeichen."""
    first = os.read(fd, 1)
    if not first or first in (b'\x03', b'\x04'):
        raise KeyboardInterrupt
    if first == b'\x1b':
        sequence = b''
        while len(sequence) < 8 and select.select([fd], [], [], 0.04 if not sequence else 0.01)[0]:
            sequence += os.read(fd, 1)
            if len(sequence) >= 2 and (sequence[-1:].isalpha() or sequence[-1:] == b'~'):
                break
        return SEQUENCES.get(sequence, 'esc' if not sequence else 'unknown')
    if first in (b'\r', b'\n'):
        return 'enter'
    if first == b' ':
        return 'space'
    if first == b'\t':
        return 'tab'
    if first[0] >= 0xc0:  # UTF-8-Folgebytes mitlesen
        need = 1 if first[0] < 0xe0 else 2 if first[0] < 0xf0 else 3
        first += os.read(fd, need)
    return first.decode('utf-8', 'replace')


# ---------------------------------------------------------------- Menüs
def split_option(text):
    label, sep, detail = text.partition(' – ')
    return (label, detail) if sep else (text, '')


class Menus:
    """Interaktive Auswahl im Terminal. Esc/q bricht ab (``KeyboardInterrupt``)."""

    menus = True

    def __init__(self, out, read=read_key, keymode=None, input_=None):
        # read/keymode/input_ nur für Tests: Tasten ohne echtes Terminal einspielen.
        self.out, self.read = out, read
        self.keymode = keymode or keys
        self.input_ = input_ or input

    # -- Bausteine
    def _question(self, label):
        return f'  {self.out.paint(self.out.sym["ask"], TEAL)} {self.out.paint(label, "1")}'

    def _hint(self, *parts):
        return '    ' + self.out.dim(f' {self.out.sym["dot"]} '.join(parts))

    def _selected(self, text):
        """Gewählte Zeile wie in der Konsole: Auswahlfläche (Teal) über die Kartenbreite."""
        room = max(len(text) + 2, min(self.out.card_width(), 72))
        return '    ' + self.out.style((' ' + text).ljust(room), fg='select_fg', bg='select_bg', bold=True)

    def answered(self, label, text):
        self.out.line(f'  {self.out.paint(self.out.sym["set"], TEAL)} {label:<16} {self.out.paint(text, "1")}')

    def _loop(self, render, handle):
        block = LiveBlock(self.out)
        with self.keymode(self.out) as fd:
            try:
                while True:
                    block.draw(render())
                    done, value = handle(self.read(fd))
                    if done:
                        return value
            finally:
                block.clear()

    # -- Auswahl
    def choose(self, label, options, default=1):
        """``options``: Liste (wert, text); ``text`` darf „Name – Erläuterung“ sein."""
        rows = [split_option(text) for _, text in options]
        width = max(len(name) for name, _ in rows)
        state = {'index': max(0, min(len(options) - 1, default - 1))}
        sym = self.out.sym
        numbered = len(options) <= 9

        def render():
            lines = [self._question(label)]
            for index, (name, detail) in enumerate(rows):
                number = f'{index + 1} ' if numbered else ''
                current = index == state['index']
                if current and self.out.color:
                    lines.append(self._selected(f'{sym["pointer"]} {number}{name:<{width}}  {detail}'))
                    continue
                pointer = self.out.paint(sym['pointer'], TEAL) if current else ' '
                title = self.out.paint(f'{number}{name:<{width}}', TEAL_BRIGHT if current else '')
                lines.append(f'    {pointer} {title}  {self.out.dim(detail)}'.rstrip())
            shortcut = [f'1–{len(options)} direkt'] if numbered else []
            lines.append(self._hint(f'{sym["keys"]} wählen', 'Enter bestätigen', *shortcut, 'Esc abbrechen'))
            return lines

        def handle(key):
            if key in ('up', 'k', 'left'):
                state['index'] = (state['index'] - 1) % len(options)
            elif key in ('down', 'j', 'right', 'tab'):
                state['index'] = (state['index'] + 1) % len(options)
            elif key == 'home':
                state['index'] = 0
            elif key == 'end':
                state['index'] = len(options) - 1
            elif key == 'enter':
                return True, state['index']
            elif key in ('esc', 'q', 'Q'):
                raise KeyboardInterrupt
            elif numbered and key.isdigit() and 1 <= int(key) <= len(options):
                return True, int(key) - 1
            return False, None

        index = self._loop(render, handle)
        self.answered(label, rows[index][0].strip())
        return options[index][0]

    def multi(self, label, items):
        """``items``: (schlüssel, name, erläuterung, an). Rückgabe: Menge der gewählten Schlüssel."""
        chosen = {key for key, _, _, on in items if on}
        state = {'index': 0}
        sym = self.out.sym
        width = max(len(name) for _, name, _, _ in items)

        def render():
            lines = [self._question(label)]
            for index, (key, name, detail, _) in enumerate(items):
                current = index == state['index']
                if current and self.out.color:
                    box = sym['on'] if key in chosen else sym['off']
                    lines.append(self._selected(f'{sym["pointer"]} {box} {name:<{width}}  {detail}'))
                    continue
                pointer = self.out.paint(sym['pointer'], TEAL) if current else ' '
                mark = self.out.paint(sym['on'], TEAL) if key in chosen else self.out.dim(sym['off'])
                title = self.out.paint(f'{name:<{width}}', TEAL_BRIGHT if current else '')
                lines.append(f'    {pointer} {mark} {title}  {self.out.dim(detail)}'.rstrip())
            lines.append(self._hint(f'{sym["keys"]} wählen', 'Leertaste an/aus', 'Enter übernehmen',
                                    'Esc abbrechen'))
            return lines

        def handle(key):
            if key in ('up', 'k'):
                state['index'] = (state['index'] - 1) % len(items)
            elif key in ('down', 'j', 'tab'):
                state['index'] = (state['index'] + 1) % len(items)
            elif key in ('space', 'x') or (key.isdigit() and 1 <= int(key) <= len(items)):
                if key.isdigit():
                    state['index'] = int(key) - 1
                chosen.symmetric_difference_update({items[state['index']][0]})
            elif key == 'enter':
                return True, None
            elif key in ('esc', 'q', 'Q'):
                raise KeyboardInterrupt
            return False, None

        self._loop(render, handle)
        names = [name for key, name, _, _ in items if key in chosen]
        self.answered(label, ', '.join(names) if names else 'keine')
        return chosen

    def confirm(self, question, default=False):
        """Ja/Nein nebeneinander; j/y = Ja, n = Nein, Esc/q = Nein."""
        state = {'yes': bool(default)}
        sym = self.out.sym

        def option(text, active):
            if active:
                return self.out.paint(f'{sym["pointer"]} {text}', TEAL_BRIGHT)
            return self.out.dim(f'  {text}')

        def render():
            return [f'{self._question(question)}   {option("Ja", state["yes"])}   {option("Nein", not state["yes"])}',
                    self._hint(f'{sym["keys"]} wechseln', 'Enter bestätigen', 'j/n direkt', 'Esc = Nein')]

        def handle(key):
            if key in ('up', 'down', 'left', 'right', 'tab', 'h', 'l', 'k'):
                state['yes'] = not state['yes']
            elif key == 'enter':
                return True, state['yes']
            elif key in ('j', 'J', 'y', 'Y'):
                return True, True
            elif key in ('n', 'N', 'esc', 'q', 'Q'):
                return True, False
            return False, None

        answer = self._loop(render, handle)
        self.answered(question, 'Ja' if answer else 'Nein')
        return answer

    def text(self, label, default=None, validate=None):
        """Freitext mit Vorgabe; Fehler stehen direkt unter der Zeile, dann neue Eingabe."""
        try:
            import readline  # noqa: F401 -- Zeilenbearbeitung für input()
            wrap = ('\001', '\002')
        except ImportError:  # pragma: no cover
            wrap = ('', '')
        sym = self.out.sym

        def guarded(text, code):
            if not self.out.color or not code:
                return text
            return f'{wrap[0]}\033[{code}m{wrap[1]}{text}{wrap[0]}\033[0m{wrap[1]}'

        hint = f' (Enter = {default})' if default not in (None, '') else ''
        prompt = f'  {guarded(sym["ask"], TEAL)} {guarded(label, "1")}{guarded(hint, "2")} {guarded(sym["set"], TEAL)} '
        plain = visible(prompt.replace('\001', '').replace('\002', ''))
        error_lines = 0
        while True:
            try:
                raw = self.input_(prompt)
            except EOFError:
                raise KeyboardInterrupt from None
            value = raw.strip() or (default or '')
            error = None if value else 'Bitte einen Wert eingeben.'
            if error is None and validate is not None:
                error = validate(value)
            columns = max(20, shutil.get_terminal_size((80, 24)).columns)
            rows = (plain + len(raw)) // columns + 1 + error_lines
            self.out.write(f'\033[{rows}A\r\033[J')
            if error is None:
                self.answered(label, value)
                return value
            self.out.line(f'    {self.out.paint(sym["fail"], "31")} {error}')
            error_lines = 1


# ---------------------------------------------------------------- Fortschritt
class Progress:
    """Schritte mit Spinner und Laufzeit; fertige Zeilen bleiben mit ✓/✗ stehen.

    Ohne Terminal schreibt ``step`` nur ``› Text`` (wie bisher) und nichts animiert.
    ``total=None``: einzelner Schritt ohne Balken; ``keep=False`` löscht dessen
    Zeile am Ende (der Aufrufer meldet das Ergebnis selbst).
    """

    FRAME_S = 0.08

    def __init__(self, out, total, keep=True, label=None, quiet=False):
        self.out, self.total, self.keep, self.quiet = out, total, keep, quiet
        self.live = out.live
        self.block = LiveBlock(out) if self.live else None
        self.current, self.started, self.began = None, None, time.monotonic()
        self.done = 0
        self.first_label = label
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        if self.live:
            self.out.write('\033[?25l')
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        if self.first_label:
            self.step(self.first_label)
        return self

    def __exit__(self, kind, error, _trace):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        with self.out.lock:
            if self.current is not None:
                self._finish('fail' if kind else 'ok')
            if self.live:
                if self.total and not kind:
                    self.done = max(self.done, self.total)
                    self.block.draw([self._bar_line()])
                    self.out.write('\n')
                    self.block.lines = 0
                else:
                    self.block.clear()
                self.out.write('\033[?25h')
        return False

    def step(self, text):
        with self.out.lock:
            if self.current is not None:
                self._finish('ok')
            self.current, self.started = text, time.monotonic()
            if not self.live:
                if not self.quiet:
                    self.out.step(text)
                return
            self._draw()

    def _finish(self, kind):
        text, elapsed = self.current, time.monotonic() - self.started
        self.current = None
        self.done += 1
        if not self.live:
            return
        self.block.clear()
        if self.keep or kind == 'fail':
            mark = self.out.paint(self.out.sym[kind], CODES[kind])
            self.out.write(f'  {mark} {text}  {self.out.dim(duration(elapsed))}\n')

    def _bar_line(self):
        total = max(self.total or 1, self.done)
        fraction = min(1.0, self.done / total)
        width, sym = 28, self.out.sym
        filled = fraction * width
        full = int(filled)
        if sym['eighths'] and full < width:
            part = sym['eighths'][int((filled - full) * 8)]
            bar = sym['full'] * full + (part.strip() and part)
        else:
            bar = sym['full'] * full
        rest = width - visible(bar)
        counter = f'{min(self.done, total)}/{total}'
        return (f'    {self.out.paint(bar, TEAL)}{self.out.paint(sym["track"] * rest, TEAL_DIM)}  '
                f'{counter} {self.out.dim(sym["dot"] + " " + duration(time.monotonic() - self.began))}')

    def _draw(self):
        if self.current is None:
            self.block.clear()
            return
        frames = self.out.sym['spin']
        frame = frames[int((time.monotonic() - self.began) / self.FRAME_S) % len(frames)]
        lines = [f'  {self.out.paint(frame, TEAL)} {self.current}  '
                 f'{self.out.dim(duration(time.monotonic() - self.started))}']
        if self.total:
            lines.append(self._bar_line())
        self.block.draw(lines)

    def _spin(self):
        while not self._stop.wait(self.FRAME_S):
            with self.out.lock:
                if not self._stop.is_set():
                    self._draw()


# ---------------------------------------------------------------- ME-Logo
def scramble(text, phase):
    """Zeichen rotieren und rasten einzeln in fester, gemischter Folge ein (wie me-fastfetch)."""
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


def logo_cells(progress):
    """Zeichen und Stufe (0 leer, 1 ungezeichnet … 4 Blitz); ``None`` = fertiges Logo.

    Erste Hälfte Mess-Scan (ein Strahl zeichnet das Logo), danach ein Glanzlauf.
    """
    if progress is None:
        return [[('#', 2) if char == '#' else (' ', 0) for char in row.ljust(LOGO_W)] for row in LOGO]
    scan = min(1.0, progress / 0.55) * (LOGO_W + 12) - 3
    shine = None
    if progress > 0.55:
        shine = (progress - 0.55) / 0.45 * (LOGO_W + len(LOGO) * 1.8 + 20) - 10
    cells = []
    for y, row in enumerate(LOGO):
        line = []
        for x, char in enumerate(row.ljust(LOGO_W)):
            distance = scan - x
            if char != '#':
                line.append(('|', 3) if abs(distance) < 0.6 and scan < LOGO_W + 1 else (' ', 0))
            elif distance < 0:
                line.append(('.', 1))
            elif distance < 1.5:
                line.append(('@', 4))
            elif distance < 9:
                line.append(('#', 3))
            elif shine is not None and abs(x + y * 1.8 - shine) < 2:
                line.append(('@', 4))
            elif shine is not None and abs(x + y * 1.8 - shine) < 5:
                line.append(('#', 3))
            else:
                line.append(('#', 2))
        cells.append(line)
    return cells


def logo_lines(out, progress, subtitle):
    styles = {1: TEAL_DIM, 2: TEAL, 3: TEAL_BRIGHT, 4: FLASH}
    lines = []
    for row in logo_cells(progress):
        parts, level, run = [], None, ''
        for char, current in row:
            if current != level and run:
                parts.append(out.paint(run, styles.get(level)))
                run = ''
            level = current
            run += char
        if run:
            parts.append(out.paint(run.rstrip() if level == 0 else run, styles.get(level)))
        lines.append('  ' + ''.join(parts).rstrip())
    caption = scramble(CAPTION, progress / 0.9) if progress is not None else CAPTION
    pad = ' ' * (2 + (LOGO_W - len(CAPTION)) // 2)
    lines += ['', pad + out.paint(caption, TEAL_BRIGHT), pad + out.dim(subtitle.center(len(CAPTION)))]
    return lines


def intro_allowed(out, env=None):
    env = os.environ if env is None else env
    size = shutil.get_terminal_size((0, 0))
    return (out.caps.interactive and out.color and env.get('PICAM_INTRO', '1') != '0'
            and not env.get('NO_COLOR') and size.columns >= LOGO_W + 6 and size.lines >= 16)


def play_intro(out, subtitle='Werkbank installieren', env=None, seconds=INTRO_S):
    """ME-Logo mit Mess-Scan und Glanzlauf; jede Taste überspringt. Rückgabe: gezeigt?"""
    if not intro_allowed(out, env):
        return False
    block = LiveBlock(out)
    out.line()
    with keys(out) as fd:
        began = time.monotonic()
        while True:
            progress = (time.monotonic() - began) / seconds
            if progress >= 1:
                break
            block.draw(logo_lines(out, progress, subtitle))
            if select.select([fd], [], [], 1 / 30)[0]:
                os.read(fd, 1024)  # Taste verbrauchen, nicht an die erste Frage weiterreichen
                break
        block.draw(logo_lines(out, None, subtitle))
        out.write('\n')
    return True
