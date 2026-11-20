#!/usr/bin/env python3
"""Sechs ME-Logo-Animationen, nur Python-Standardbibliothek (Linux/macOS).

Vom picam-Installer (Komponente me-fastfetch) nach
~/.local/share/me-fastfetch/ kopiert; Quelle: packaging/me-fastfetch/.
Start: python3 ~/.local/share/me-fastfetch/me-logo.py
Fastfetch mit einmaligem Glanzlauf: ~/.local/bin/me-fastfetch
Links/rechts oder oben/unten: wechseln; 1-6: Direktwahl; Leertaste: Pause;
+/-: Tempo; A: automatische Wechsel; R: Neustart; Q/Esc: Ende.

ASCII-Form aus der bereitgestellten me-logo.txt; deren $1/$2-Marker sind
keine sichtbaren Zeichen. Farbvorbild: mobile-logo.7a0ae658.svg (#00b5af).
Die Effekte sind dekorativ und stellen keine Messdaten dar.
"""

from __future__ import annotations

import argparse
import curses
import math
import os
import random
import re
import select
import shutil
import subprocess
import sys
import termios
import time
import unicodedata
from contextlib import contextmanager

LOGO = (
    "####  ####   ####   ##################",
    "####  ####   ####   ##################",
    "####  ####   ####   #####",
    "####  ####   ####   ##################",
    "####  ####   ####   ##################",
    "####         ####   #####",
    "####         ####   ##################",
    "####         ####   ##################",
)
WIDTH = max(map(len, LOGO))
HEIGHT = len(LOGO)
CAPTION = "M E - M e s s y s t e m e"
MODES = (
    ("Mess-Scan", "Ein Abtaststrahl zeichnet das Logo mit Leuchtspur."),
    ("Zusammenbau", "Die einzelnen Balken gleiten an ihren Platz."),
    ("Zug & Druck", "Das Logo dehnt und staucht sich zwischen Kraftpfeilen."),
    ("Signalwelle", "Eine laufende Welle bewegt die Zeichen."),
    ("Partikelflug", "Verstreute Zeichen finden sich zum Logo zusammen."),
    ("Glanzlauf", "Ein diagonaler Lichtreflex wandert ueber das Logo."),
)
DURATION = 8.0


def scramble_caption(text: str, phase: float) -> str:
    """Alle Zeichen rotieren parallel und rasten einzeln in gemischter Folge ein.

    Leerzeichen bleiben fest; die letzten 18 Prozent gehoeren dem fertigen
    Schriftzug. Die Phase ist an denselben Zyklus wie der Glanzlauf gebunden.
    """
    if phase >= 0.82:
        return text
    symbols = "|/-\\+*#%0123456789"
    order = list(range(sum(char != " " for char in text)))
    # Feste Mischung: Pause und Einzelbilder zeigen denselben Ablauf.
    random.Random(23).shuffle(order)
    settle_at = {index: 0.18 + 0.64 * rank / max(1, len(order) - 1)
                 for rank, index in enumerate(order)}
    tick = int(phase * 48)
    result = []
    index = 0
    for char in text:
        if char == " ":
            result.append(char)
        else:
            rotating = symbols.replace(char, "")
            result.append(char if phase >= settle_at[index] else rotating[(tick + index * 5) % len(rotating)])
            index += 1
    return "".join(result)


def smooth(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3 - 2 * value)


def dispersion(phase: float) -> float:
    """Anflug, erkennbare Ruhephase, Abflug; stetig an der Loop-Grenze."""
    return 1 - smooth(phase / 0.30) + smooth((phase - 0.72) / 0.28)


def render(mode: int, elapsed: float, width: int, height: int) -> list[list[tuple[str, int]]]:
    """Zeitbasierter ASCII-Frame; Intensitaeten 1 (dunkel) bis 4 (hell)."""
    cells = [[(" ", 0) for _ in range(width)] for _ in range(height)]

    def put(x: float, y: float, char: str, level: int) -> None:
        px, py = round(x), round(y)
        if 0 <= px < width and 0 <= py < height:
            if level >= cells[py][px][1]:
                cells[py][px] = (char, level)

    scale = max(1, min(3, (width - 12) // WIDTH, (height - 6) // HEIGHT))
    logo_w, logo_h = WIDTH * scale, HEIGHT * scale
    left, top = (width - logo_w) // 2, (height - logo_h) // 2
    phase = (elapsed % DURATION) / DURATION
    spread = dispersion(phase)
    scan = phase * (logo_w + 18) - 9
    pulse = math.sin(elapsed * 1.7)

    for y in range(logo_h):
        for x in range(logo_w):
            if LOGO[y // scale].ljust(WIDTH)[x // scale] != "#":
                continue
            px, py, char, level = float(x), float(y), "#", 2
            if mode == 0:
                distance = scan - x
                if abs(distance) < 1.5:
                    char, level = "@", 4
                elif 0 <= distance < 9:
                    char, level = "#", 3
                else:
                    char, level = ("#", 2) if distance >= 0 else (".", 1)
            elif mode == 1:
                # M: drei Balken; E: Ruecken und drei Querbalken.
                source_x, source_y = x // scale, y // scale
                if source_x < 4:
                    dx, dy = -width * 0.55, 0
                elif source_x < 10:
                    dx, dy = 0, -height * 0.6
                elif source_x < 17:
                    dx, dy = 0, height * 0.6
                elif source_x < 24:
                    dx, dy = width * 0.4, 0
                else:
                    dx, dy = width * 0.5, (source_y - 3.5) * 2
                px += dx * spread
                py += dy * spread
                level = 3 if spread > 0 else 2
            elif mode == 2:
                px = (x - (logo_w - 1) / 2) * (1 + 0.12 * pulse) + (logo_w - 1) / 2
                py = (y - (logo_h - 1) / 2) * (1 - 0.08 * pulse) + (logo_h - 1) / 2
                level = 3 if abs(pulse) > 0.75 else 2
            elif mode == 3:
                wave = x / logo_w * math.tau * 1.3 - elapsed * 2.5
                py += math.sin(wave) * 2.2
                level = 3 if math.cos(wave) > 0.65 else 2
                char = "@" if level == 3 else "#"
            elif mode == 4:
                # Deterministisch: Pause und Einzelbild bleiben reproduzierbar.
                seed = (x * 73856093 ^ y * 19349663) & 0xFFFF
                angle = seed / 65535 * math.tau
                radius = 5 + seed % max(6, width // 2)
                px += math.cos(angle) * radius * spread
                py += math.sin(angle) * radius * 0.45 * spread
                char, level = ("+", 3) if spread > 0.1 else ("#", 2)
            elif mode == 5:
                distance = abs(x + y * 1.8 - phase * (logo_w + logo_h * 1.8 + 20) + 10)
                if distance < 2:
                    char, level = "@", 4
                elif distance < 5:
                    char, level = "#", 3
            put(left + px, top + py, char, level)

    if mode == 0:
        for y in range(top - 1, top + logo_h + 1):
            put(left + scan, y, "|", 3)
    elif mode == 2:
        distance = logo_w / 2 * (1 + 0.12 * pulse) + 4
        for offset, char in ((-distance, "<" if pulse >= 0 else ">"),
                             (distance, ">" if pulse >= 0 else "<")):
            put(width / 2 + offset, height / 2, char, 4)
    return cells


def palette(no_color: bool) -> list[int]:
    fallback = [0, curses.A_DIM, curses.A_NORMAL, curses.A_BOLD, curses.A_BOLD]
    if no_color or not curses.has_colors():
        return fallback
    curses.start_color()
    background = curses.COLOR_BLACK
    try:
        curses.use_default_colors()
        background = -1
    except curses.error:
        pass
    # xterm-256: dunkles Petrol, ME-nahes Tuerkis, helles Tuerkis, Weiss.
    colors = (23, 37, 87, 231) if curses.COLORS >= 256 else (6, 6, 6, 7)
    attrs = [0]
    for index, color in enumerate(colors, 1):
        curses.init_pair(index, color, background)
        attrs.append(curses.color_pair(index) | (curses.A_BOLD if index >= 3 else 0))
    return attrs


def write(screen: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    rows, cols = screen.getmaxyx()
    if 0 <= y < rows and 0 <= x < cols - 1:
        try:
            screen.addnstr(y, x, text, cols - x - 1, attr)
        except curses.error:
            # Ein Resize kann zwischen getmaxyx und addnstr eintreffen.
            pass


def run(screen: curses.window, args: argparse.Namespace) -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    curses.set_escdelay(30)
    screen.keypad(True)
    screen.timeout(round(1000 / args.fps))
    attrs = palette(args.no_color or "NO_COLOR" in os.environ)
    mode, elapsed, speed = args.animation - 1, 0.0, 1.0
    paused, auto = False, args.auto
    previous = time.monotonic()

    while True:
        now = time.monotonic()
        if not paused:
            elapsed += (now - previous) * speed
        previous = now
        if auto and elapsed >= DURATION:
            mode = (mode + int(elapsed // DURATION)) % len(MODES)
            elapsed %= DURATION
        rows, cols = screen.getmaxyx()
        screen.erase()
        if rows < 20 or cols < 54:
            write(screen, 0, 0, "Bitte Terminal auf mindestens 54 x 20 vergroessern.")
            write(screen, 2, 0, "Q / Esc: Ende | Pfeiltasten: Wechsel")
        else:
            def center(y: int, text: str, attr: int = 0) -> None:
                write(screen, y, max(0, (screen.getmaxyx()[1] - len(text)) // 2), text, attr)

            center(1, "M E  /  A S C I I   S T U D I O", attrs[3])
            center(3, f"{mode + 1:02d} / {len(MODES):02d}   {MODES[mode][0]}", attrs[4])
            canvas_h = rows - 12
            canvas_w = min(cols - 4, 150)
            origin = (cols - canvas_w) // 2
            for y, row in enumerate(render(mode, elapsed, canvas_w, canvas_h)):
                # Gleichfarbige Laeufe statt einer Terminaloperation pro Zeichen.
                start = 0
                while start < len(row):
                    end = start + 1
                    while end < len(row) and row[end][1] == row[start][1]:
                        end += 1
                    write(screen, y + 5, origin + start,
                          "".join(char for char, _ in row[start:end]), attrs[row[start][1]])
                    start = end
            caption = scramble_caption(CAPTION, (elapsed % DURATION) / DURATION) if mode == 5 else CAPTION
            center(rows - 7, caption, attrs[3])
            center(rows - 5, MODES[mode][1], attrs[1])
            state = "PAUSE" if paused else "ANIMATION"
            center(rows - 4, f"{state}   |   Tempo {speed:.2g}x   |   Auto {'AN' if auto else 'AUS'}")
            center(rows - 2, "< > Wechsel  1-6 Wahl  SPACE Pause  Q Ende", attrs[3])
            center(rows - 1, "+/- Tempo   A Auto   R Neustart", attrs[1])
        screen.refresh()
        key = screen.getch()
        if key in (ord("q"), ord("Q"), 27):
            return
        if key in (curses.KEY_RIGHT, curses.KEY_DOWN, ord("n")):
            mode, elapsed = (mode + 1) % len(MODES), 0.0
        elif key in (curses.KEY_LEFT, curses.KEY_UP, ord("p")):
            mode, elapsed = (mode - 1) % len(MODES), 0.0
        elif ord("1") <= key <= ord("6"):
            mode, elapsed = key - ord("1"), 0.0
        elif key == ord(" "):
            paused = not paused
        elif key in (ord("+"), ord("=")):
            speed = min(4.0, speed * 1.25)
        elif key == ord("-"):
            speed = max(0.25, speed / 1.25)
        elif key in (ord("a"), ord("A")):
            auto = not auto
        elif key in (ord("r"), ord("R")):
            elapsed = 0.0
        # Die Wartezeit vor dem Tastendruck zaehlt nicht fuer die neue Szene.
        if key != -1:
            previous = time.monotonic()


@contextmanager
def animation_keyboard():
    """Tasten sofort erkennen, ohne sie dem anschliessenden Prompt wegzulesen."""
    fd = None
    original = None
    try:
        fd = os.open('/dev/tty', os.O_RDONLY | os.O_NOCTTY)
        original = termios.tcgetattr(fd)
        settings = original.copy()
        settings[6] = original[6].copy()
        settings[3] &= ~(termios.ICANON | termios.ECHO | termios.ECHONL)
        settings[6][termios.VMIN] = 1
        settings[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, settings)
    except (OSError, termios.error):
        if fd is not None:
            os.close(fd)
        fd = None
    try:
        yield fd
    finally:
        if fd is not None:
            try:
                # TCSANOW behaelt auch bereits getippte Zeichen im Eingabepuffer.
                termios.tcsetattr(fd, termios.TCSANOW, original)
            finally:
                os.close(fd)


def run_fastfetch(duration: float, no_color: bool) -> int:
    """Fastfetch einmal erfassen; nur dessen erkanntes ME-Logo kurz uebermalen.

    Keine Hintergrundausgabe: Der Prompt bekommt das Terminal erst nach dem
    letzten Frame zurueck; jede Eingabe beendet den Glanzlauf vorzeitig und
    bleibt fuer den Prompt erhalten. Fremde Logos, Pipes und kleine Terminals
    bleiben statisch. Die Fastfetch-Konfiguration bleibt die Quelle der Systemdaten.
    """
    binary = shutil.which("fastfetch")
    if binary is None:
        print("fastfetch wurde nicht gefunden.", file=sys.stderr)
        return 127
    no_color = no_color or "NO_COLOR" in os.environ
    ansi = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
    if no_color or not sys.stdout.isatty() or os.environ.get("TERM", "dumb") == "dumb":
        # --pipe entfernt keine vom Nutzer in Formatstrings eingebetteten ANSI-Farben.
        result = subprocess.run([binary, "--pipe", "true"], capture_output=True, text=True, check=False)
        sys.stdout.write(ansi.sub("", result.stdout))
        sys.stderr.write(result.stderr)
        return result.returncode

    result = subprocess.run(
        [binary, "--pipe", "false", "--disable-linewrap", "false", "--hide-cursor", "false"],
        capture_output=True, text=True, check=False,
    )
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.returncode:
        sys.stdout.write(result.stdout)
        return result.returncode
    lines = result.stdout.splitlines()
    plain = [ansi.sub("", line) for line in lines]
    size = shutil.get_terminal_size()
    location = None
    for start in range(len(plain) - HEIGHT + 1):
        left = len(plain[start]) - len(plain[start].lstrip(" "))
        if all(plain[start + y] == " " * left + row for y, row in enumerate(LOGO)):
            location = start, left
            break

    def columns(text: str) -> int:
        column = furthest = 0
        for part in re.split(r"(\x1b\[[0-?]*[ -/]*[@-~])", text):
            if part.startswith("\x1b["):
                if part.endswith("m"):
                    continue
                if part.endswith("G") and (not part[2:-1] or part[2:-1].isdigit()):
                    column = max(0, int(part[2:-1] or "1") - 1)
                else:
                    return size.columns  # Unbekannte Cursorbewegung: statisch bleiben.
            else:
                if any(ord(char) < 32 for char in part):
                    return size.columns
                column += sum(0 if unicodedata.combining(char) else
                              2 if unicodedata.east_asian_width(char) in ("W", "F") else 1 for char in part)
            furthest = max(furthest, column)
        return furthest

    # Kein Zeilenumbruch/Scrollen waehrend des Uebermalens. Unbekannte
    # Steuersequenzen (z.B. Bildlogos oder Hyperlinks) unveraendert ausgeben.
    fits = (len(lines) < size.lines and all(columns(line) < size.columns for line in lines)
            and all("\x1b" not in line for line in plain))
    if location is None or not fits or not result.stdout.endswith("\n"):
        sys.stdout.write(result.stdout)
        sys.stdout.flush()
        return 0

    start, left = location
    caption_row = start + HEIGHT
    has_caption = (caption_row < len(lines) and plain[caption_row].strip() == CAPTION
                   and CAPTION in lines[caption_row])
    initial_lines = lines.copy()
    if has_caption:
        initial_lines[caption_row] = lines[caption_row].replace(CAPTION, scramble_caption(CAPTION, 0), 1)
    colors = {2: "\x1b[38;2;0;181;175m", 3: "\x1b[1;38;2;119;231;219m", 4: "\x1b[1;97m"}
    reset = "\x1b[0m"
    anchor = f"\x1b8\x1b[{len(lines) - start}A"
    resized = False
    with animation_keyboard() as input_fd:
        sys.stdout.write("\n".join(initial_lines) + "\n")
        sys.stdout.flush()
        sys.stdout.write("\x1b7\x1b[?25l")
        try:
            began = time.monotonic()
            while True:
                if input_fd is not None and select.select([input_fd], [], [], 0)[0]:
                    break
                resized = shutil.get_terminal_size() != size
                if resized:
                    break
                phase = (time.monotonic() - began) / duration
                if phase >= 1:
                    break
                frame = render(5, phase * DURATION, WIDTH, HEIGHT)
                chunks = [anchor]
                for row in frame:
                    chunks.append(f"\r\x1b[{left + 1}G")
                    last_level = None
                    for char, level in row:
                        if level != last_level:
                            chunks.append(reset + colors.get(level, ""))
                            last_level = level
                        chunks.append(char)
                    chunks.append(reset + "\x1b[1B")
                if has_caption:
                    caption = lines[caption_row].replace(CAPTION, scramble_caption(CAPTION, phase), 1)
                    chunks.append("\r" + caption + reset)
                chunks.append("\x1b8")
                sys.stdout.write("".join(chunks))
                sys.stdout.flush()
                if input_fd is None:
                    time.sleep(1 / 30)
                elif select.select([input_fd], [], [], 1 / 30)[0]:
                    break
        finally:
            if not resized and shutil.get_terminal_size() == size:
                sys.stdout.write(anchor)
                for line in lines[start:start + HEIGHT + int(has_caption)]:
                    sys.stdout.write("\r" + line + reset + "\x1b[1B")
                sys.stdout.write("\x1b8")
            # Nach Resize keine veralteten Koordinaten mehr verwenden.
            sys.stdout.write(reset + "\x1b[?25h")
            sys.stdout.flush()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--animation", type=int, choices=range(1, 7), default=1, help="Startanimation (1-6)")
    parser.add_argument("--fps", type=int, choices=range(5, 61), default=30, metavar="5..60")
    parser.add_argument("--auto", action="store_true", help="Nach jedem 8-Sekunden-Zyklus wechseln")
    parser.add_argument("--no-color", action="store_true", help="Monochrome Darstellung")
    parser.add_argument("--snapshot", type=float, metavar="SEKUNDEN", help="Einzelbild ohne Terminalsteuerung ausgeben")
    parser.add_argument("--fastfetch", action="store_true", help="Fastfetch mit einmaligem Glanzlauf anzeigen")
    parser.add_argument("--duration", type=float, default=2.0, metavar="SEKUNDEN", help="Fastfetch-Glanzlauf: 0.1 bis 30 Sekunden (Vorgabe: 2)")
    args = parser.parse_args()
    if not math.isfinite(args.duration) or not 0.1 <= args.duration <= 30:
        parser.error("--duration muss zwischen 0.1 und 30 Sekunden liegen")
    if args.fastfetch:
        if args.snapshot is not None:
            parser.error("--fastfetch und --snapshot sind nicht kombinierbar")
        try:
            return run_fastfetch(args.duration, args.no_color)
        except KeyboardInterrupt:
            return 130
    if args.snapshot is not None:
        if not math.isfinite(args.snapshot) or args.snapshot < 0:
            parser.error("--snapshot muss eine endliche, nichtnegative Sekundenzahl sein")
        for row in render(args.animation - 1, args.snapshot, 80, 18):
            print("".join(char for char, _ in row).rstrip())
        caption = scramble_caption(CAPTION, (args.snapshot % DURATION) / DURATION) if args.animation == 6 else CAPTION
        print(caption.center(80))
        return 0
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("Bitte in einem interaktiven Terminal starten; fuer Textausgabe --snapshot 3 verwenden")
    try:
        curses.wrapper(run, args)
    except KeyboardInterrupt:
        return 0
    except curses.error as error:
        print(f"Terminal konnte nicht initialisiert werden: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
