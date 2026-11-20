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
from textual.widgets import Static

from .. import probes
from ..ui import ACCENT, MUTED, TONE, ascii_mode, bar, section, sparkline, status_strip, symbol
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


def latest_text(app, run: dict, long: bool = False) -> Text:
    """Letzter Messwert mit Status und Alter; ältere als ~5 s werden gedimmt und markiert."""
    latest = run.get('latest') or {}
    age = run_age(app, run)
    stale = age is None or age > STALE_AFTER_S
    word, level = STATUS_WORDS.get(str(latest.get('status')), ('–', probes.UNKNOWN))
    value = latest.get('value')
    text = Text()
    if value is None:
        text.append('–', style=MUTED)
    else:
        text.append(f'{value}', style=MUTED if stale else 'bold')
        if latest.get('unit'):
            text.append(f' {latest["unit"]}', style=MUTED)
    if latest:
        text.append(f'  {word}', style=TONE[level])
    text.append('  ')
    if age is None:
        text.append('Alter unbekannt', style=TONE[probes.WARN])
    elif stale:
        text.append(f'{symbol(probes.WARN)} {age_text(age)}' + (' – nicht mehr frisch' if long else ''),
                    style=TONE[probes.WARN])
    else:
        text.append(age_text(age), style=MUTED)
    return text


class LaufView(TabView):
    TAB_ID, TITLE, KEY = 'lauf', 'Lauf', '2'
    INFO_TITLE = 'Lauf'
    INFO = ('Nur zum Ansehen: Läufe und Einrichtung startet und beendet die Werkbank im Browser. Die Zahlen '
            'kommen aus dem Laufstatus der Werkbank (alle 5 s); Alter und Dauer laufen dazwischen weiter.',
            'Margin ist der Abstand der besten zur zweitbesten Ziffernvorlage, keine Fehlerwahrscheinlichkeit.')

    DEFAULT_CSS = """
    LaufView #lauf-cols { height: auto; layout: vertical; }
    LaufView .lauf-col { height: auto; width: 1fr; }
    LaufView.wide #lauf-cols { layout: horizontal; }
    LaufView.wide #lauf-a { padding: 0 2 0 0; }
    LaufView.wide #lauf-b { padding: 0 0 0 2; border-left: vkey #1b2129; }
    LaufView .lauf-col > Static { height: auto; width: 1fr; }
    LaufView .lauf-col > .section { margin: 1 0 0 0; }
    """

    def compose(self):
        yield Static(Text('Lauf', style='bold'), classes='title')
        with Vertical(id='lauf-cols'):
            with Vertical(id='lauf-a', classes='lauf-col'):
                yield section('Zustand')
                yield Static(id='run-state')
                yield section('Letzter Wert')
                yield Static(id='run-latest')
                yield section('Zählwerte')
                yield Static(id='run-counts')
            with Vertical(id='lauf-b', classes='lauf-col'):
                yield section('Letzte 60 s')
                yield Static(id='run-strip')
                yield section('Verarbeitung')
                yield Static(id='run-proc')
                yield section('System')
                yield Static(id='run-system')

    def on_mount(self) -> None:
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        if self.display and self.is_attached and self.app.current == self.TAB_ID:
            self.update_view()

    def on_resize(self, event: Resize) -> None:
        self.set_class(self.app.size.width >= WIDE, 'wide')
        self.call_after_refresh(self.update_view)

    # ------------------------------------------------------------ Breiten
    def _avail(self, widget_id: str, default: int = 40) -> int:
        width = self.query_one(widget_id).size.width
        return width if width > 0 else default

    # ------------------------------------------------------------ Inhalte
    def update_view(self) -> None:
        self.set_class(self.app.size.width >= WIDE, 'wide')
        app = self.app
        live, run = live_run(app)
        self._render_state(live, run)
        latest = self.query_one('#run-latest', Static)
        counts = self.query_one('#run-counts', Static)
        strip = self.query_one('#run-strip', Static)
        proc = self.query_one('#run-proc', Static)
        system = self.query_one('#run-system', Static)
        has_run = bool(live) and bool(run)
        if not has_run:
            note = Text('–', style=MUTED)
            for widget in (latest, counts, strip, proc):
                widget.update(note)
        else:
            latest.update(latest_text(app, run, long=True))
            counts.update(self._counts(run))
            strip.update(self._strip(run))
            proc.update(self._proc(run.get('proc') or {}))
        system.update(self._system(live))

    def _render_state(self, live: dict | None, run: dict) -> None:
        app = self.app
        out = self.query_one('#run-state', Static)
        if app.snapshot is None:
            out.update(Text('Laufstatus wird geprüft …', style=MUTED))
            return
        if live is None:
            text = Text()
            text.append(f'{symbol(probes.UNKNOWN)} Laufstatus unbekannt', style=TONE[probes.UNKNOWN])
            text.append('\nDie Steuerung der Werkbank ist nicht erreichbar.', style=MUTED)
            out.update(text)
            return
        state = live.get('state')
        word = probes.STATE_WORDS.get(state, str(state))
        rows = []
        head = Text()
        if state == 'running':
            head.append('● ' if not ascii_mode() else '* ', style=f'bold {ACCENT}')
            head.append(word, style='bold')
        elif state in ('setup_running', 'setup_ready', 'setup_failed'):
            level = probes.FAIL if state == 'setup_failed' else probes.OK
            head.append(('◐ ' if not ascii_mode() else '* ') if state == 'setup_running' else f'{symbol(level)} ',
                        style=f'bold {ACCENT if state == "setup_running" else TONE[level]}')
            head.append(word, style='bold')
        else:
            head.append(f'{symbol(probes.OFF)} ', style=MUTED)
            head.append('Kein Lauf' if state == 'idle' else word, style='bold')
        rows.append(head)
        if state == 'idle' and not run:
            note = Text()
            note.append('Läufe startet die Werkbank im Browser', style=MUTED)
            if app.instance.url:
                note.append(':\n')
                note.append(app.instance.url, style=ACCENT)
            else:
                note.append('.')
            rows.append(note)
        details = []
        if live.get('step'):
            details.append(('Schritt', str(live['step'])))
        if state in ('setup_running', 'setup_ready', 'setup_failed') and not live.get('step'):
            details.append(('Schritt', '–'))
        if live.get('session_id'):
            details.append(('Sitzung', str(live['session_id'])))
        if run:
            elapsed = run.get('elapsed_s')
            if elapsed is not None and state == 'running':
                elapsed = float(elapsed) + drift(app)
            details.append(('Dauer', fmt_duration(elapsed)))
            details.append(('Ausgabe', probes._transport_word((live.get('output') or {}).get('transport'))))
            if run.get('dir'):
                details.append(('Ordner', str(run['dir'])))
            if app.instance.live_data:
                details.append(('Ablage', str(app.instance.live_data)))
        text = Text()
        for index, row in enumerate(rows):
            if index:
                text.append('\n')
            text.append_text(row)
        pad = max((len(key) for key, _ in details), default=0) + 2
        for key, value in details:
            text.append('\n')
            text.append(key.ljust(pad), style=MUTED)
            text.append(value)
        out.update(text)

    def _counts(self, run: dict) -> Text:
        counts = run.get('counts') or {}
        total = sum(int(counts.get(key) or 0) for _, key, _ in STATUS_ROWS)
        width = self._avail('#run-counts')
        bar_width = 10 if width >= 44 else 0
        text = Text()
        for index, (name, key, level) in enumerate(STATUS_ROWS):
            n = int(counts.get(key) or 0)
            if index:
                text.append('\n')
            text.append(f'{name:<9}', style=MUTED)
            text.append(f'{fmt_int(n):>8}', style=TONE[level])
            share = n / total if total else None
            text.append(f'  {"–" if share is None else format(share * 100, ".1f").replace(".", ",")} %'.rjust(9),
                        style=MUTED)
            if bar_width and share is not None:
                text.append('  ')
                text.append_text(bar(share, bar_width, TONE[level]))
        text.append(f'\n{"gesamt":<9}', style=MUTED)
        text.append(f'{fmt_int(total):>8}')
        return text

    def _strip(self, run: dict) -> Text:
        width = max(20, min(60, self._avail('#run-strip') - 1))
        text = status_strip(run.get('recent') or [], width)
        text.append('\n')
        legend = Text(no_wrap=False)
        block = '#' if ascii_mode() else '▇'
        for name, _, level in STATUS_ROWS:
            legend.append(block, style=TONE[level])
            legend.append(f' {name}  ', style=MUTED)
        legend.append('\nlinks älter, rechts neuer', style=MUTED)
        text.append_text(legend)
        return text

    def _proc(self, proc: dict) -> Text:
        text = Text()
        if not proc:
            return Text('–', style=MUTED)
        width = self._avail('#run-proc')
        age = proc.get('age_s')
        age_stale = age is not None and float(age) + drift(self.app) > STALE_AFTER_S
        text.append(f'{"Bildrate":<13}', style=MUTED)
        text.append(fmt_num(proc.get('fps'), 1, 'Bilder/s'))
        text.append(f'\n{"Latenz":<13}', style=MUTED)
        text.append(fmt_num(proc.get('latency_ms'), 0, 'ms'), style=ACCENT)
        series = [v for _, v in (proc.get('latency_recent') or []) if v is not None]
        if series:
            text.append('  ')
            text.append_text(sparkline(series, max(8, min(40, width - 44))))
            text.append(f' min {min(series):.0f} / max {max(series):.0f} ms', style=MUTED)
        text.append(f'\n{"Übersprungen":<13}', style=MUTED)
        skipped = proc.get('skipped_recent')
        text.append('–' if skipped is None else fmt_num(skipped * 100, 0, '%'),
                    style=TONE[probes.WARN] if skipped is not None and skipped > 0.10 else '')
        cells = proc.get('cells') or {}
        text.append('\nMargin (Abstand beste/zweitbeste Vorlage)', style=MUTED)
        text.append('\n  kleinste ', style=MUTED)
        margin = cells.get('min_margin')
        text.append(fmt_num(margin, 2), style=TONE[probes.WARN] if margin is not None and margin < 0 else '')
        text.append('   unsichere Zellen ', style=MUTED)
        uncertain = cells.get('uncertain')
        text.append('–' if uncertain is None else str(uncertain),
                    style=TONE[probes.WARN] if uncertain else '')
        text.append('\nStand der Zahlen ', style=MUTED)
        if age is None:
            text.append('–')
        else:
            shown = float(age) + drift(self.app)
            text.append(age_text(shown), style=TONE[probes.WARN] if age_stale else MUTED)
            if age_stale:
                text.append(f' {symbol(probes.WARN)}', style=TONE[probes.WARN])
        return text

    def _system(self, live: dict | None) -> Text:
        metrics = self.app.metrics or {}
        cpu = metrics.get('cpu_percent')
        if cpu is None and live:
            cpu = (live.get('system') or {}).get('cpu_percent')
        ram = metrics.get('ram_percent')
        temp = metrics.get('temperature_c')
        text = Text()
        for index, (name, value, text_value, limit) in enumerate((
                ('CPU', cpu, fmt_num(cpu, 0, '%'), 85), ('RAM', ram, fmt_num(ram, 0, '%'), 85),
                ('Temperatur', temp, fmt_num(temp, 0, '°C'), 75))):
            if index:
                text.append('\n')
            text.append(f'{name:<10}', style=MUTED)
            text.append(f'{text_value:>7}', style=TONE[probes.WARN] if value is not None and value >= limit else '')
            if name != 'Temperatur' and value is not None:
                text.append('  ')
                text.append_text(bar(value / 100, 12, TONE[probes.WARN] if value >= limit else None))
        return text
