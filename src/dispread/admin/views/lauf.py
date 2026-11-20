"""Lauf: lesende Metrik-Ansicht des laufenden Messlaufs (zweites Metrik-Dashboard).

Nur Anzeige: Läufe startet und beendet die Werkbank im Browser. Alle Zahlen
stammen aus dem Laufstatus (``snapshot.live``); Alter und Dauer werden um die
seit der Abfrage vergangene Zeit weitergerechnet, damit nichts älter
aussieht als es ist (und Veraltetes nie unmarkiert bleibt).
"""

from __future__ import annotations

import time

from rich.text import Text
from textual.containers import Vertical
from textual.events import Resize

from .. import probes
from ..ui import MUTED, TONE, ascii_mode, bar, sparkline, status_strip
from ..widgets import SectionCard, badge, fields, header, help_line, join, value
from .base import TabView

WIDE = 120          # ab dieser Breite zwei Spalten
STALE_AFTER_S = 5.0  # älter als das gilt der letzte Wert als nicht mehr frisch

STATUS_ROWS = (('gültig', 'valid', probes.OK), ('Übergang', 'transition', probes.WARN),
               ('unlesbar', 'unreadable', probes.FAIL), ('veraltet', 'stale', probes.UNKNOWN))
STATUS_WORDS = {'VALID': ('gültig', probes.OK), 'TRANSITION': ('Übergang', probes.WARN),
                'UNREADABLE': ('unlesbar', probes.FAIL), 'STALE': ('veraltet', probes.UNKNOWN)}


# ------------------------------------------------------------ Formate (auch vom Dashboard benutzt)
def fmt_int(value) -> str:
    try:
        return f'{int(value):,}'.replace(',', '.')
    except (TypeError, ValueError):
        return '–'


def fmt_duration(seconds) -> str:
    """mm:ss, ab einer Stunde h:mm:ss; unbekannt = „–“."""
    try:
        seconds = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        return '–'
    hours, rest = divmod(seconds, 3600)
    return f'{hours}:{rest // 60:02d}:{rest % 60:02d}' if hours else f'{rest // 60:02d}:{rest % 60:02d}'


def fmt_num(value, digits: int = 0, unit: str = '') -> str:
    if value is None:
        return '–'
    try:
        return f'{float(value):.{digits}f}'.replace('.', ',') + (f' {unit}' if unit else '')
    except (TypeError, ValueError):
        return '–'


def drift(app) -> float:
    """Sekunden seit der letzten Abfrage (0, wenn unbekannt)."""
    snap = app.snapshot
    if snap is None:
        return 0.0
    return max(0.0, time.time() - snap.collected_at)


def live_run(app) -> tuple[dict | None, dict]:
    snap = app.snapshot
    live = snap.live if snap is not None else None
    return live, ((live or {}).get('run') or {})


def run_age(app, run: dict) -> float | None:
    age = run.get('latest_age_s')
    try:
        return None if age is None else float(age) + drift(app)
    except (TypeError, ValueError):
        return None


def age_text(age: float | None) -> str:
    if age is None:
        return '–'
    if age < 120:
        return f'vor {age:.0f} s'
    return f'vor {fmt_duration(age)} min'


def latest_body(app, run: dict) -> Text:
    """Letzter Messwert (eingelassen) und Alter; älter als ~5 s gedimmt und als Abzeichen markiert."""
    latest = run.get('latest') or {}
    age = run_age(app, run)
    stale = age is None or age > STALE_AFTER_S
    text = Text(no_wrap=True)
    text.append_text(value(latest.get('value'), latest.get('unit'), tone=MUTED if stale else None, bold=not stale))
    text.append('  ')
    if age is None:
        text.append_text(badge(probes.WARN, 'Alter unbekannt'))
    elif stale:
        text.append_text(badge(probes.WARN, f'{age_text(age)} – nicht mehr frisch'))
    else:
        text.append(age_text(age), style=MUTED)
    return text


def _warn_tone(flag: bool) -> str | None:
    return TONE[probes.WARN] if flag else None


class LaufView(TabView):
    TAB_ID, TITLE, KEY = 'lauf', 'Lauf', '2'
    INFO_TITLE = 'Lauf'
    ABOUT = ('Nur zum Ansehen: Läufe und Einrichtung startet und beendet die Werkbank im Browser. Die Zahlen '
             'kommen aus dem Laufstatus der Werkbank (alle 5 s); Alter und Dauer laufen dazwischen weiter.',
             'Margin ist der Abstand der besten zur zweitbesten Ziffernvorlage, keine Fehlerwahrscheinlichkeit.')

    DEFAULT_CSS = """
    LaufView #lauf-cols { height: auto; layout: vertical; max-width: 160; }
    LaufView .lauf-col { height: auto; width: 1fr; }
    LaufView.wide #lauf-cols { layout: horizontal; }
    LaufView.wide #lauf-a { padding: 0 1 0 0; }
    LaufView.wide #lauf-b { padding: 0 0 0 1; }
    """

    def compose(self):
        with Vertical(id='lauf-cols'):
            with Vertical(id='lauf-a', classes='lauf-col'):
                yield SectionCard(id='run-state')
                yield SectionCard(id='run-latest')
                yield SectionCard(id='run-counts')
            with Vertical(id='lauf-b', classes='lauf-col'):
                yield SectionCard(id='run-strip')
                yield SectionCard(id='run-proc')
                yield SectionCard(id='run-system')

    def on_mount(self) -> None:
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        if self.display and self.is_attached and self.app.current == self.TAB_ID:
            self.update_view()

    def on_resize(self, event: Resize) -> None:
        self.set_class(self.app.size.width >= WIDE, 'wide')
        self.call_after_refresh(self.update_view)

    def _card(self, widget_id: str) -> tuple[SectionCard, int]:
        card = self.query_one(widget_id, SectionCard)
        wide = self.app.size.width >= WIDE
        return card, self.card_width(card, margin=6 if not wide else (self.size.width or 120) // 2 + 4)

    # ------------------------------------------------------------ Inhalte
    def update_view(self) -> None:
        self.set_class(self.app.size.width >= WIDE, 'wide')
        app = self.app
        live, run = live_run(app)
        self._render_state(live, run)
        has_run = bool(live) and bool(run)
        # Ohne Lauf nur Zustand und System: leere Karten wären nur Rauschen
        for widget_id in ('#run-latest', '#run-counts', '#run-strip', '#run-proc'):
            self.query_one(widget_id).display = has_run
        self._render_latest(run if has_run else None)
        card, width = self._card('#run-counts')
        card.show(header('storage', 'Zählwerte', None, width),
                  self._counts(run, width) if has_run else value(None))
        card, width = self._card('#run-strip')
        card.show(header('clock', 'Letzte 60 s', None, width),
                  self._strip(run, width) if has_run else value(None),
                  help_line('Links älter, rechts neuer.') if has_run else None)
        card, width = self._card('#run-proc')
        proc = (run.get('proc') or {}) if has_run else {}
        card.show(header('camera', 'Verarbeitung', self._proc_age(proc), width),
                  self._proc(proc, width) if proc else value(None),
                  help_line('Margin (Abstand beste/zweitbeste Vorlage).', 'i', 'mehr')
                  if proc else None)
        card, width = self._card('#run-system')
        card.show(header('system', 'System', None, width), self._system(live, width))

    def _render_state(self, live: dict | None, run: dict) -> None:
        app = self.app
        card, width = self._card('#run-state')
        if app.snapshot is None:
            card.show(header('run', 'Lauf', badge('busy', 'Laufstatus wird geprüft', 'busy'), width))
            return
        if live is None:
            card.show(header('run', 'Lauf', badge(probes.UNKNOWN, 'Laufstatus unbekannt'), width), None,
                      help_line('Die Steuerung der Werkbank ist nicht erreichbar.'))
            return
        state = live.get('state')
        word = probes.STATE_WORDS.get(state, str(state))
        if state == 'running':
            badge_text = badge(probes.OK, word, 'on')
        elif state == 'setup_running':
            badge_text = badge('busy', word, 'busy')
        elif state in ('setup_ready', 'setup_failed'):
            badge_text = badge(probes.FAIL if state == 'setup_failed' else probes.OK, word)
        else:
            badge_text = badge(probes.OFF, 'kein Lauf' if state == 'idle' else word)
        rows: list = []
        if live.get('step') or state in ('setup_running', 'setup_ready', 'setup_failed'):
            rows.append(('Schritt', value(live.get('step'))))
        if live.get('session_id'):
            rows.append(('Sitzung', value(str(live['session_id']))))
        if run:
            elapsed = run.get('elapsed_s')
            if elapsed is not None and state == 'running':
                elapsed = float(elapsed) + drift(app)
            rows.append(('Dauer', value(fmt_duration(elapsed))))
            rows.append(('Ausgabe', value(probes._transport_word((live.get('output') or {}).get('transport')))))
            if run.get('dir'):
                rows.append(('Ordner', value(str(run['dir'])), True))
            if app.instance.live_data:
                rows.append(('Ablage', value(str(app.instance.live_data)), True))
        if state == 'idle' and not run:
            rows.append(('Werkbank', value(app.instance.url), True))
            hint = help_line('Läufe startet die Werkbank im Browser.')
        else:
            hint = help_line('Nur ansehen; gesteuert wird im Browser.', 'i', 'mehr')
        card.show(header('run', 'Lauf', badge_text, width),
                  fields(rows, width, label_w=10, columns=2 if width >= 56 else 1), hint)

    def _render_latest(self, run: dict | None) -> None:
        card, width = self._card('#run-latest')
        latest = (run or {}).get('latest') or {}
        right = None
        if latest:
            word, level = STATUS_WORDS.get(str(latest.get('status')), ('–', probes.UNKNOWN))
            right = badge(level, word)
        card.show(header('values', 'Letzter Wert', right, width),
                  latest_body(self.app, run) if run else value(None))

    def _counts(self, run: dict, width: int) -> Text:
        counts = run.get('counts') or {}
        total = sum(int(counts.get(key) or 0) for _, key, _ in STATUS_ROWS)
        bar_width = max(0, min(24, width - 38))
        text = Text(no_wrap=True)
        for index, (name, key, level) in enumerate(STATUS_ROWS):
            n = int(counts.get(key) or 0)
            if index:
                text.append('\n')
            text.append(f'{name:<10}', style=MUTED)
            text.append_text(value(f'{fmt_int(n):>7}', tone=TONE[level]))
            share = n / total if total else None
            text.append(f'{"–" if share is None else format(share * 100, ".1f").replace(".", ",")} %'.rjust(9),
                        style=MUTED)
            if bar_width >= 6 and share is not None:
                text.append('  ')
                text.append_text(bar(share, bar_width, TONE[level]))
        text.append(f'\n{"gesamt":<10}', style=MUTED)
        text.append_text(value(f'{fmt_int(total):>7}', bold=True))
        return text

    def _strip(self, run: dict, width: int) -> Text:
        text = status_strip(run.get('recent') or [], max(20, min(60, width)))
        text.append('\n')
        block = '#' if ascii_mode() else '▇'
        for name, _, level in STATUS_ROWS:
            text.append(block, style=TONE[level])
            text.append(f' {name}  ', style=MUTED)
        return text

    def _proc_age(self, proc: dict) -> Text | None:
        age = proc.get('age_s')
        if age is None:
            return None
        shown = float(age) + drift(self.app)
        if shown > STALE_AFTER_S:
            return badge(probes.WARN, f'Stand {age_text(shown)}')
        return None

    def _proc(self, proc: dict, width: int) -> Text:
        age = proc.get('age_s')
        latency = value(fmt_num(proc.get('latency_ms'), 0) if proc.get('latency_ms') is not None else None, 'ms')
        series = [v for _, v in (proc.get('latency_recent') or []) if v is not None]
        if series:
            spark = max(8, min(30, width - 40))
            latency = join(latency, '  ', sparkline(series, spark),
                           f' {min(series):.0f}–{max(series):.0f} ms' if width >= 60 else '')
        skipped = proc.get('skipped_recent')
        cells = proc.get('cells') or {}
        margin = cells.get('min_margin')
        uncertain = cells.get('uncertain')
        if age is None:
            stand = value(None)
        else:
            shown = float(age) + drift(self.app)
            stand = (badge(probes.WARN, age_text(shown)) if shown > STALE_AFTER_S
                     else Text(age_text(shown), style=MUTED))
        rows = [('Bildrate', value(fmt_num(proc.get('fps'), 1) if proc.get('fps') is not None else None,
                                   'Bilder/s')),
                ('Latenz', latency, True),
                ('Übersprungen', value(None if skipped is None else fmt_num(skipped * 100, 0), '%',
                                       tone=_warn_tone(skipped is not None and skipped > 0.10))),
                ('Margin min.', value(None if margin is None else fmt_num(margin, 2),
                                      tone=_warn_tone(margin is not None and margin < 0))),
                ('Unsicher', value(None if uncertain is None else str(uncertain), 'Zellen' if uncertain is not None
                                   else None, tone=_warn_tone(bool(uncertain)))),
                ('Stand', stand)]
        return fields(rows, width, label_w=14, columns=2 if width >= 64 else 1)

    def _system(self, live: dict | None, width: int) -> Text:
        metrics = self.app.metrics or {}
        cpu = metrics.get('cpu_percent')
        if cpu is None and live:
            cpu = (live.get('system') or {}).get('cpu_percent')
        ram = metrics.get('ram_percent')
        temp = metrics.get('temperature_c')
        bar_width = max(0, min(24, width - 26))
        text = Text(no_wrap=True)
        for index, (name, number, unit, limit) in enumerate((
                ('CPU', cpu, '%', 85), ('RAM', ram, '%', 85), ('Temperatur', temp, '°C', 75))):
            if index:
                text.append('\n')
            hot = number is not None and number >= limit
            text.append(f'{name:<12}', style=MUTED)
            field = value(None if number is None else f'{fmt_num(number, 0):>3}', unit, tone=_warn_tone(hot))
            text.append_text(field)
            if unit == '%' and number is not None and bar_width >= 6:
                text.append(' ' * max(1, 10 - field.cell_len))
                text.append_text(bar(number / 100, bar_width, TONE[probes.WARN] if hot else None))
        return text
