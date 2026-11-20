"""Dashboard: links Logo, Lauf und Knöpfe, rechts die Statusliste der Bereiche."""

from __future__ import annotations

import time

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.widgets import OptionList, RichLog, Static
from textual.widgets.option_list import Option

from .. import probes
from ..intro import SHINE_PERIOD, SHINE_S, logo_text
from ..ui import ACCENT, MUTED, SOFT, TONE, Action, Segment, ascii_mode, section_text, status_strip, symbol
from .base import TabView, actions_segment
from .lauf import drift, fmt_duration, fmt_int, latest_text

SHINE_EVERY_S = 20.0
TAIL_LINES = 400


SPLIT = 76          # darunter: gestapelt, Liste zuerst
LOGO_MIN_LEFT = 40  # Logo (38 Spalten) nur, wenn die linke Spalte so breit ist
LOGO_MIN_HEIGHT = 30


class RunCard(Static):
    """Laufkarte; Klick oder Enter öffnet den Tab Lauf."""

    can_focus = True
    BINDINGS = [Binding('enter', 'open', show=False)]
    DEFAULT_CSS = '''
    RunCard { border-left: wide $picam-line; transition: background 150ms out_cubic; }
    RunCard.running { border-left: wide $picam-accent; }
    RunCard:hover { background: $picam-raised; }
    RunCard:focus { background: $picam-raised; border-left: wide $picam-accent-strong; }
    '''

    def on_click(self) -> None:
        self.action_open()

    def action_open(self) -> None:
        self.app.open_tab('lauf')


class DashboardView(TabView):
    TAB_ID, TITLE, KEY = 'dashboard', 'Dashboard', '1'
    INFO_TITLE = 'Dashboard'
    INFO = ('Links der Lauf (nur lesend; Läufe startet und beendet die Werkbank im Browser) und die '
            'häufigsten Aktionen, rechts alle Bereiche mit ihrem Zustand. Enter oder Klick öffnet einen '
            'Bereich als Tab.',)

    ROWS = (('dienst', 'Werkbank', 'dienst'), ('lauf', 'Lauf', 'lauf'), ('ausgabe', '└ Ausgabe', 'ausgabe'),
            ('kamera', 'Kamera', 'kamera'), ('bruecke', 'Brücke', 'ausgabe'),
            ('zertifikat', 'Zertifikat', 'zertifikat'), ('speicher', 'Speicher', 'speicher'),
            ('#cpu', 'CPU', 'dienst'), ('#ram', 'RAM', 'dienst'), ('#temp', 'Temperatur', 'dienst'),
            ('version', 'Version', 'dienst'), ('#setup', 'Einrichtung', None))

    def compose(self):
        with Horizontal(id='dash'):
            with Vertical(id='dash-left'):
                yield Static(id='dash-logo')
                yield Static(id='dash-warn', classes='hint')
                yield RunCard(id='dash-run')
                yield actions_segment()
                with Segment(id='dash-tail'):
                    yield Static(id='tail-head', classes='section')
                    yield RichLog(id='tail-log', max_lines=TAIL_LINES, wrap=True, markup=False, auto_scroll=True,
                                  min_width=20)
            with Vertical(id='dash-right'):
                with Segment('Bereiche', id='dash-areas'):
                    yield OptionList(id='dash-list')

    def on_mount(self) -> None:
        bar = self.query_one('#buttons', Horizontal)
        for action in self.actions():
            bar.mount(self.action_button(action))
        self._shine_from = None
        self._shine_timer = None
        self._render_logo()
        self._layout()
        if self.app.animation_level != 'none':
            self.set_interval(SHINE_EVERY_S, self._start_shine)
        head = section_text('Letzte Meldungen', styled=False)
        head.append('   l', style=f'bold {ACCENT}')
        head.append(' ganzes Protokoll', style=MUTED)
        self.query_one('#tail-head', Static).update(head)

    # ------------------------------------------------------------ Layout
    def on_resize(self, event: Resize) -> None:
        self._layout()
        self.call_after_refresh(self.update_view)

    def _layout(self) -> None:
        """Breitenabhängiges Layout aus der App-Größe (deterministisch, ohne Messen)."""
        width, height = self.app.size
        stacked = width < SPLIT
        right_w = 34 if width <= 100 else 42
        left = self.query_one('#dash-left')
        right = self.query_one('#dash-right')
        dash = self.query_one('#dash')
        self._list_width = right_w - 3 if not stacked else max(20, width - 8)
        right.styles.width = '1fr' if stacked else right_w
        if stacked:
            left.styles.padding = (1, 0, 0, 0)
            if dash.children and dash.children[0] is left:
                dash.move_child(right, before=left)
        else:
            left.styles.padding = (1, 2, 0, 0)
            if dash.children and dash.children[0] is right:
                dash.move_child(left, before=right)
        left_w = (width - 5) if stacked else (width - 5 - right_w - 3 - 2)
        self._left_w = left_w
        self._logo_ok = left_w >= LOGO_MIN_LEFT and height >= LOGO_MIN_HEIGHT and not stacked
        self.query_one('#dash-logo').display = self._logo_ok
        bar = self.query_one('#buttons')
        buttons = list(bar.query('Button'))
        if left_w < 46:
            mode = 'col'
        elif left_w < 86:
            mode = 'grid'
        else:
            mode = 'row'
        bar.styles.layout = {'col': 'vertical', 'grid': 'grid', 'row': 'horizontal'}[mode]
        if mode == 'grid':
            bar.styles.grid_size_columns = 2
            bar.styles.grid_gutter_vertical = 0
            bar.styles.grid_gutter_horizontal = 1
            bar.styles.grid_rows = '1'
        bar.styles.margin = (1, 0, 0, 0)
        for button in buttons:
            button.styles.width = 'auto' if mode == 'row' else '1fr'
            button.styles.margin = (0, 2, 0, 0) if mode == 'row' else (0, 0, 0, 0)
        # Meldung: Hinweistext nur, wenn Platz ist
        self._tall = height >= LOGO_MIN_HEIGHT

    # ------------------------------------------------------------ Logo
    def _render_logo(self, t: float | None = None) -> None:
        if t is None:  # Ruhe: fertig gezeichnetes Logo ohne Glanz
            self.query_one('#dash-logo', Static).update(logo_text(0, animated=False))
        else:
            self.query_one('#dash-logo', Static).update(logo_text(t))

    def _start_shine(self) -> None:
        if self._shine_timer is not None or not self.display or not getattr(self, '_logo_ok', False):
            return
        self._shine_from = time.monotonic()
        self._shine_timer = self.set_interval(1 / 15, self._shine_tick)

    def _shine_tick(self) -> None:
        from ..intro import REVEAL_S
        elapsed = time.monotonic() - self._shine_from
        if elapsed > SHINE_S:
            self._shine_timer.stop()
            self._shine_timer = None
            self._render_logo()
            return
        # Zeitpunkt im ersten Glanzlauf nach dem Zeichnen; Schriftzug bleibt fest
        self._render_logo(REVEAL_S + 0.4 + elapsed + 0 * SHINE_PERIOD + 10.0 * 0)

    # ------------------------------------------------------------ Inhalte
    def update_view(self) -> None:
        self._layout()
        self._render_list()
        self._render_run()
        self._render_warn()
        self.sync_buttons()

    def _row(self, key: str, label: str) -> Text:
        app = self.app
        width = max(20, getattr(self, '_list_width', 31) - 3)
        value, level = '–', None
        metrics = app.metrics or {}
        if key == '#cpu':
            cpu = metrics.get('cpu_percent')
            value = '–' if cpu is None else f'{cpu:.0f} %'
            level = probes.OK if cpu is None or cpu < 85 else probes.WARN
        elif key == '#ram':
            ram = metrics.get('ram_percent')
            value = '–' if ram is None else f'{ram:.0f} %'
            level = probes.OK if ram is None or ram < 85 else probes.WARN
        elif key == '#temp':
            temp = metrics.get('temperature_c')
            value = '–' if temp is None else f'{temp:.0f} °C'
            level = probes.OK if temp is None or temp < 75 else probes.WARN
        elif key == '#setup':
            setup = [f for k, f in app.setup_facts().items() if f.level in (probes.WARN, probes.FAIL)]
            if not app.setup_facts():
                value, level = 'wird geprüft', None
            elif setup:
                level = min((f.level for f in setup), key=probes.LEVEL_ORDER.__getitem__)
                value = f'{len(setup)} offen'
            else:
                value, level = 'vollständig', probes.OK
        else:
            fact = app.fact(key)
            if fact is not None:
                value, level = fact.value, fact.level
        text = Text()
        if label.startswith('└'):
            text.append('  ' + label, style=MUTED)
        else:
            mark = symbol(level) if level else ' '
            text.append(f'{mark} ', style=TONE.get(level, MUTED))
            text.append(label)
        quiet = level in (None, probes.OK, probes.OFF)
        right = Text(value, style=MUTED if quiet else TONE[level])
        room = width - text.cell_len - 1
        if right.cell_len > room:
            right.truncate(max(1, room), overflow='ellipsis')
        text.append(' ' * max(1, width - text.cell_len - right.cell_len))
        text.append_text(right)
        return text

    def _render_list(self) -> None:
        listing = self.query_one('#dash-list', OptionList)
        if listing.option_count != len(self.ROWS):
            listing.clear_options()
            listing.add_options([Option(self._row(key, label), id=key) for key, label, _ in self.ROWS])
            return
        for key, label, _ in self.ROWS:
            listing.replace_option_prompt(key, self._row(key, label))

    @on(OptionList.OptionSelected, '#dash-list')
    def _open(self, event: OptionList.OptionSelected) -> None:
        target = dict((key, tab) for key, _, tab in self.ROWS).get(event.option.id)
        if event.option.id == '#setup':
            target = self.app.first_setup_tab()
        if target:
            self.app.open_tab(target)

    def _render_run(self) -> None:
        app = self.app
        snap = app.snapshot
        card = self.query_one('#dash-run', RunCard)
        text = Text()
        running = False
        if snap is None:
            text.append('Laufstatus wird geprüft …', style=MUTED)
        elif snap.live is None:
            text.append(f'{symbol(probes.UNKNOWN)} Laufstatus unbekannt', style=TONE[probes.UNKNOWN])
            text.append('\nSteuerung der Werkbank nicht erreichbar.', style=MUTED)
        else:
            live = snap.live
            state = live.get('state')
            word = probes.STATE_WORDS.get(state, str(state))
            run = live.get('run') or {}
            if state == 'running':
                running = True
                output = (live.get('output') or {}).get('transport')
                elapsed = run.get('elapsed_s')
                if elapsed is not None:
                    elapsed = float(elapsed) + drift(app)
                text.append('* ' if ascii_mode() else '● ', style=f'bold {ACCENT}')
                text.append('Lauf aktiv', style='bold')
                step = str(live.get('step') or '')
                parts = [step if step != 'Lauf' else '', fmt_duration(elapsed)]
                if self._left_w >= 56:
                    parts.append(f'Ausgabe {probes._transport_word(output)}')
                text.append('  ·  ' + '  ·  '.join(p for p in parts if p and p != '–'), style=MUTED)
                counts = run.get('counts') or {}
                segments = [(name, counts.get(key), level) for name, key, level in (
                    ('gültig', 'valid', probes.OK), ('Übergang', 'transition', probes.WARN),
                    ('unlesbar', 'unreadable', probes.FAIL), ('veraltet', 'stale', probes.UNKNOWN))]
                inner = max(20, self._left_w - 3)
                per_line = 4 if inner >= 56 else 2
                for index, (name, value, level) in enumerate(segments):
                    text.append('\n' if index % per_line == 0 else '   ')
                    text.append(f'{name} ', style=MUTED)
                    text.append(fmt_int(value), style=TONE[level])
                text.append('\n')
                text.append_text(status_strip(run.get('recent') or [], max(20, min(60, inner))))
                text.append('\n')
                text.append_text(latest_text(app, run))
                text.append('\n2', style=f'bold {ACCENT}')
                text.append(' oder Enter: Laufdetails', style=MUTED)
            elif state in ('setup_running', 'setup_ready', 'setup_failed'):
                level = probes.FAIL if state == 'setup_failed' else probes.OK
                busy = state == 'setup_running'
                mark = ('* ' if ascii_mode() else '◐ ') if busy else f'{symbol(level)} '
                text.append(mark, style=f'bold {ACCENT}' if busy else TONE[level])
                text.append(f'Einrichtung: {word}', style='bold')
                if live.get('step'):
                    text.append(f'  ·  {live["step"]}', style=MUTED)
                text.append('\nLäufe und Einrichtung steuert die Werkbank im Browser.', style=MUTED)
            else:
                text.append(f'{symbol(probes.OFF)} ', style=MUTED)
                text.append('Kein Lauf', style='bold')
                if state != 'idle':
                    text.append(f'  ·  {word}', style=MUTED)
                if app.instance.url:
                    text.append('\nLäufe startet die Werkbank: ', style=MUTED)
                    text.append(app.instance.url, style=ACCENT)
        card.set_class(running, 'running')
        card.update(text)

    def _render_warn(self) -> None:
        warn = self.query_one('#dash-warn', Static)
        problems = [f for f in self.app.problems() if f.key not in ('lauf',)]
        if not problems:
            warn.display = False
            return
        worst = problems[0]
        text = Text()
        text.append(f'{symbol(worst.level)} {worst.label}: {worst.value}', style=f'bold {TONE[worst.level]}')
        if len(problems) > 1:
            text.append(f'   +{len(problems) - 1} weitere', style=MUTED)
        if worst.hint and getattr(self, '_tall', True):
            text.append('\n' + worst.hint, style=SOFT)
        warn.update(text)
        warn.display = True
        warn.set_class(worst.level == probes.FAIL, 'fail')

    def actions(self) -> list[Action]:
        app = self.app
        service = app.fact('dienst')
        running = service is not None and service.level in (probes.OK, probes.WARN)
        no_unit = 'kein Dienst eingerichtet (portabel)' if app.instance.unit is None else None
        unchecked = 'Laufstatus noch nicht geprüft' if app.snapshot is None else None
        blocked = no_unit or unchecked or (app.blocker if running else None)
        actions = [
            Action('s', 'Werkbank stoppen' if running else 'Werkbank starten',
                   lambda: app.service_action('stop' if running else 'start'), blocked=blocked, danger=running),
            Action('r', 'Neu starten', lambda: app.service_action('restart'), blocked=blocked),
            Action('k', 'Kamera neu starten', app.camera_restart,
                   blocked=('Werkbank läuft nicht' if not running else app.blocker)),
        ]
        if app.instance.bridge_directory:
            actions.append(Action('b', 'Brücke: UART-Empfang', app.bridge_prepare,
                                  blocked=None if running else 'Werkbank läuft nicht'))
        return actions

    def add_log(self, row) -> None:
        self.query_one('#tail-log', RichLog).write(row, scroll_end=True)

    def clear_log(self) -> None:
        self.query_one('#tail-log', RichLog).clear()
