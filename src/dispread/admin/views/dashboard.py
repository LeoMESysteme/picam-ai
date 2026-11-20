"""Dashboard: Lauf, Hinweis, Bereiche, letzte Meldungen; unten die Aktionsleiste.

Zwei Anordnungen (``PICAM_LAYOUT``):

- A „Karten + Abzeichen“: links Logo, Hinweis und Laufkarte, rechts die Karte
  „Bereiche“ (Zeichen, Name, Abzeichen bzw. Wertfeld), darunter die Meldungen.
- B „Kacheln + Details“: oben fünf Kacheln (Werkbank, Lauf, Kamera, Ausgabe,
  Speicher; Enter oder Klick öffnet den Tab), darunter links die Laufzeilen,
  rechts die übrigen Bereiche als schlichte Zeilen.
"""

from __future__ import annotations

import time

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from .. import probes
from ..intro import SHINE_PERIOD, SHINE_S, logo_text
from ..ui import MUTED, Action, P, ReflowLog, status_strip
from ..widgets import (
    ActionBar,
    TabBody,
    TileRow,
    badge,
    clip,
    fact_badge,
    fields,
    header,
    help_line,
    icon,
    key_chip,
    layout_mode,
    tile_text,
    value,
)
from .base import TabView
from .lauf import STALE_AFTER_S, STATUS_WORDS, age_text, drift, fmt_duration, fmt_int, run_age

SHINE_EVERY_S = 20.0
TAIL_LINES = 400


SPLIT = 76          # darunter: gestapelt, Liste zuerst
LOGO_MIN_LEFT = 40  # Logo (38 Spalten) nur, wenn die linke Spalte so breit ist
LOGO_MIN_HEIGHT = 30

#: Zeichen je Bereich (Liste und Kacheln)
GLYPHS = {'dienst': 'service', 'lauf': 'run', 'ausgabe': 'output', 'kamera': 'camera', 'bruecke': 'bridge',
          'zertifikat': 'cert', 'speicher': 'storage', '#cpu': 'system', '#ram': 'system', '#temp': 'system',
          'version': 'version', '#setup': 'setup'}
#: Kacheln der Richtung B: (Befund, Titel, Tab)
TILES = (('dienst', 'Werkbank', 'dienst'), ('lauf', 'Lauf', 'lauf'), ('kamera', 'Kamera', 'kamera'),
         ('ausgabe', 'Ausgabe', 'ausgabe'), ('speicher', 'Speicher', 'speicher'))


class RunCard(Static):
    """Laufkarte; Klick oder Enter öffnet den Tab Lauf."""

    can_focus = True
    BINDINGS = [Binding('enter', 'open', show=False)]
    DEFAULT_CSS = '''
    RunCard { padding: 0 1; background: $picam-surface; transition: background 150ms out_cubic; }
    RunCard.plain { background: $picam-canvas; border-left: wide $picam-line; }
    RunCard.plain.running { border-left: wide $picam-accent; }
    RunCard:hover { background: $picam-raised; }
    RunCard:focus { background: $picam-raised; }
    RunCard.plain:focus { border-left: wide $picam-accent-strong; }
    '''

    def on_click(self) -> None:
        self.action_open()

    def action_open(self) -> None:
        self.app.open_tab('lauf')


class DashboardView(TabView):
    TAB_ID, TITLE, KEY = 'dashboard', 'Dashboard', '1'
    OWN_BAR = True
    INFO_TITLE = 'Dashboard'
    INFO = ('Der Lauf ist nur zum Ansehen (Läufe startet und beendet die Werkbank im Browser); 2 oder Enter '
            'öffnet die Laufdetails. Daneben alle Bereiche mit ihrem Zustand; Enter oder Klick öffnet einen '
            'Bereich als Tab. Unten die häufigsten Aktionen.',)

    ROWS = (('dienst', 'Werkbank', 'dienst'), ('lauf', 'Lauf', 'lauf'), ('ausgabe', 'Ausgabe', 'ausgabe'),
            ('kamera', 'Kamera', 'kamera'), ('bruecke', 'Brücke', 'ausgabe'),
            ('zertifikat', 'Zertifikat', 'zertifikat'), ('speicher', 'Speicher', 'speicher'),
            ('#cpu', 'CPU', 'dienst'), ('#ram', 'RAM', 'dienst'), ('#temp', 'Temperatur', 'dienst'),
            ('version', 'Version', 'dienst'), ('#setup', 'Einrichtung', None))
    SUB_ROWS = ('ausgabe',)  # gehört zum Lauf: eingerückt

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode = layout_mode()

    def rows(self) -> tuple:
        """Zeilen der Bereichsliste; in B stehen die Kachelbereiche nicht noch einmal in der Liste."""
        if self.mode != 'b':
            return self.ROWS
        tiles = {key for key, _, _ in TILES}
        return tuple(row for row in self.ROWS if row[0] not in tiles)

    def compose(self):
        with TabBody(classes='tab-body'):
            if self.mode == 'b':
                yield TileRow(len(TILES), id='dash-tiles', min_tile=14, classes='nav')
            with Horizontal(id='dash'):
                with Vertical(id='dash-left'):
                    yield Static(id='dash-logo')
                    yield Static(id='dash-warn')
                    yield RunCard(id='dash-run', classes='plain' if self.mode == 'b' else '')
                    with Vertical(id='dash-tail'):
                        yield Static(id='tail-head')
                        yield ReflowLog(id='tail-log', max_lines=TAIL_LINES, wrap=True, markup=False,
                                      auto_scroll=True, min_width=20)
                with Vertical(id='dash-right'):
                    with Vertical(id='dash-areas', classes='plain' if self.mode == 'b' else ''):
                        yield Static(id='areas-head')
                        yield OptionList(id='dash-list')
        yield ActionBar()

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
            left.styles.padding = (0, 2, 0, 0)
            if dash.children and dash.children[0] is right:
                dash.move_child(left, before=right)
        left_w = (width - 5) if stacked else (width - 5 - right_w - 3 - 2)
        self._left_w = left_w
        self._logo_ok = (self.mode != 'b' and left_w >= LOGO_MIN_LEFT and height >= LOGO_MIN_HEIGHT
                         and not stacked)
        self.query_one('#dash-logo').display = self._logo_ok
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
        for log in self.query('#tail-log'):
            log.sync()
        self._layout()
        if self.mode == 'b':
            self._render_tiles()
        self._render_list()
        self._render_run()
        self._render_warn()
        self._render_heads()
        self.sync_buttons()

    def _render_heads(self) -> None:
        width = max(20, getattr(self, '_list_width', 31))
        self.query_one('#areas-head', Static).update(header('dashboard', 'Bereiche', width=width))
        head = header('log', 'Letzte Meldungen')
        head.append('   ')
        head.append_text(key_chip('l'))
        head.append(' ganzes Protokoll', style=MUTED)
        self.query_one('#tail-head', Static).update(head)

    def _area(self, key: str) -> tuple[Text, str | None]:
        """Rechte Seite einer Bereichszeile: Abzeichen (Zustand) oder Wertfeld (Zahl)."""
        app = self.app
        metrics = app.metrics or {}
        metric = {'#cpu': ('cpu_percent', '%', 85), '#ram': ('ram_percent', '%', 85),
                  '#temp': ('temperature_c', '°C', 75)}.get(key)
        if metric is not None:
            number = metrics.get(metric[0])
            if number is None:
                return value(None), None
            if number >= metric[2]:
                return badge(probes.WARN, f'{number:.0f} {metric[1]}'), probes.WARN
            return value(f'{number:.0f}', metric[1]), probes.OK
        if key == '#setup':
            setup = [f for f in app.setup_facts().values() if f.level in (probes.WARN, probes.FAIL)]
            if not app.setup_facts():
                return badge(probes.UNKNOWN, 'wird geprüft', 'busy'), None
            if setup:
                level = min((f.level for f in setup), key=probes.LEVEL_ORDER.__getitem__)
                return badge(level, f'{len(setup)} offen'), level
            return badge(probes.OK, 'vollständig'), probes.OK
        fact = app.fact(key)
        if fact is None:
            return value(None), None
        return fact_badge(fact), fact.level

    def _row(self, key: str, label: str) -> Text:
        width = max(20, getattr(self, '_list_width', 31) - 2)
        right, _ = self._area(key)
        text = Text(no_wrap=True)
        if key in self.SUB_ROWS and self.mode != 'b':
            text.append(f' {icon("sub")} ', style=P.line)
        text.append(f'{icon(GLYPHS.get(key, "system"))} ', style=MUTED)
        text.append(label)
        room = width - text.cell_len - 1
        if right.cell_len > room:
            right = right.copy()
            right.truncate(max(4, room), overflow='ellipsis')
        text.append(' ' * max(1, width - text.cell_len - right.cell_len))
        text.append_text(right)
        return text

    def _render_list(self) -> None:
        listing = self.query_one('#dash-list', OptionList)
        rows = self.rows()
        if listing.option_count != len(rows):
            listing.clear_options()
            listing.add_options([Option(self._row(key, label), id=key) for key, label, _ in rows])
            return
        for key, label, _ in rows:
            listing.replace_option_prompt(key, self._row(key, label))

    @on(OptionList.OptionSelected, '#dash-list')
    def _open(self, event: OptionList.OptionSelected) -> None:
        target = dict((key, tab) for key, _, tab in self.ROWS).get(event.option.id)
        if event.option.id == '#setup':
            target = self.app.first_setup_tab()
        if target:
            self.app.open_tab(target)

    # ------------------------------------------------------------ Kacheln (B)
    def _render_tiles(self) -> None:
        app = self.app
        row = self.query_one('#dash-tiles', TileRow)
        inner = row.arrange(row.size.width or max(40, self.app.size.width - 6))
        live = app.snapshot.live if app.snapshot is not None else None
        run = (live or {}).get('run') or {}
        for index, (key, title, _) in enumerate(TILES):
            if key == 'dienst':
                kennzahl = value(f'{app.instance.host}:{app.instance.port}' if app.instance.host else None)
            elif key == 'lauf':
                elapsed = run.get('elapsed_s')
                kennzahl = value(fmt_duration(float(elapsed) + drift(app)) if elapsed is not None else None)
            elif key == 'kamera':
                frames = ((live or {}).get('camera') or {}).get('frames')
                kennzahl = value(fmt_int(frames) if frames is not None else None, 'Bilder')
            elif key == 'ausgabe':
                kennzahl = value(((live or {}).get('output') or {}).get('state') if live else None)
            else:
                reserve = dict(app.fact('speicher').detail).get('Reserve') if app.fact('speicher') else None
                kennzahl = value(reserve, 'Reserve' if reserve else None)
            row.set_tile(index, tile_text(GLYPHS[key], title, fact_badge(app.fact(key)), kennzahl, inner))

    @on(TileRow.Selected, '#dash-tiles')
    def _tile_open(self, event: TileRow.Selected) -> None:
        if event.activate:
            self.app.open_tab(TILES[event.index][2])

    # ------------------------------------------------------------ Lauf
    def _latest(self, run: dict) -> Text:
        """Letzter Wert (eingelassen), Status als Abzeichen, Alter; älter als ~5 s markiert."""
        app = self.app
        latest = run.get('latest') or {}
        age = run_age(app, run)
        stale = age is None or age > STALE_AFTER_S
        text = Text()
        val = latest.get('value')
        text.append_text(value(val, latest.get('unit'), tone=MUTED if stale else None, bold=not stale))
        if latest:
            word, level = STATUS_WORDS.get(str(latest.get('status')), ('–', probes.UNKNOWN))
            text.append(' ')
            text.append_text(badge(level, word))
        text.append('  ')
        if age is None:
            text.append_text(badge(probes.WARN, 'Alter unbekannt'))
        elif stale:
            text.append_text(badge(probes.WARN, age_text(age)))
        else:
            text.append(age_text(age), style=MUTED)
        return text

    def _counts(self, run: dict, width: int) -> Text:
        counts = run.get('counts') or {}
        items = [(name, counts.get(key), level) for name, key, level in (
            ('gültig', 'valid', probes.OK), ('Übergang', 'transition', probes.WARN),
            ('unlesbar', 'unreadable', probes.FAIL), ('veraltet', 'stale', probes.UNKNOWN))]
        per_line = 4 if width >= 64 else 2
        text = Text()
        for index, (name, number, level) in enumerate(items):
            if index:
                text.append('\n' if index % per_line == 0 else '  ')
            text.append(f'{icon({probes.OK: "ok", probes.WARN: "warn", probes.FAIL: "fail"}.get(level, "unknown"))} ',
                        style=P.ok if level == probes.OK else (P.warn if level == probes.WARN else
                                                                 P.fail if level == probes.FAIL else P.unknown))
            text.append(f'{name} ', style=MUTED)
            text.append_text(value(fmt_int(number)))
        return text

    def _render_run(self) -> None:
        app = self.app
        snap = app.snapshot
        card = self.query_one('#dash-run', RunCard)
        width = card.content_size.width or max(30, self._left_w - (4 if self.mode == 'b' else 2))
        running = False
        rows: list = []
        hint: Text | None = None
        extra: list[Text] = []
        if snap is None:
            state = badge(probes.UNKNOWN, 'Laufstatus wird geprüft', 'busy')
        elif snap.live is None:
            state = badge(probes.UNKNOWN, 'Laufstatus unbekannt')
            hint = help_line('Steuerung der Werkbank nicht erreichbar.')
        else:
            live = snap.live
            status = live.get('state')
            word = probes.STATE_WORDS.get(status, str(status))
            run = live.get('run') or {}
            if status == 'running':
                running = True
                state = badge(probes.OK, 'Lauf aktiv', 'on')
                elapsed = run.get('elapsed_s')
                if elapsed is not None:
                    elapsed = float(elapsed) + drift(app)
                output = (live.get('output') or {}).get('transport')
                step = str(live.get('step') or '')
                rows = [('Dauer', value(fmt_duration(elapsed))),
                        ('Ausgabe', value(probes._transport_word(output)))]
                if step and step != 'Lauf':
                    rows.insert(1, ('Schritt', value(step)))
                extra = [self._counts(run, width - 2),
                         Text('Letzte 60 s  ', style=MUTED) + status_strip(run.get('recent') or [],
                                                                        max(20, min(60, width - 15))),
                         Text('Letzter Wert ' if width >= 48 else 'Wert ', style=MUTED) + self._latest(run)]
                hint = help_line('Laufdetails:', '2', 'oder Enter')
            elif status in ('setup_running', 'setup_ready', 'setup_failed'):
                level = probes.FAIL if status == 'setup_failed' else probes.OK
                busy = status == 'setup_running'
                state = badge('busy' if busy else level, f'Einrichtung: {word}', 'busy' if busy else None)
                if live.get('step'):
                    rows = [('Schritt', value(live['step']))]
                hint = help_line('Läufe und Einrichtung steuert die Werkbank im Browser.')
            else:
                state = badge(probes.OFF, 'kein Lauf' if status == 'idle' else f'kein Lauf · {word}')
                if app.instance.url:
                    rows = [('Werkbank', value(app.instance.url))]
                hint = help_line('Läufe startet die Werkbank im Browser.')
        text = Text()
        # B: Zustand steht schon auf der Kachel „Lauf“
        text.append_text(clip(header('run', 'Lauf', None if self.mode == 'b' and snap is not None else state,
                                     width), width))
        if rows:
            text.append('\n')
            text.append_text(fields(rows, width, label_w=13, columns=2))
        for line in extra:
            text.append('\n')
            text.append_text(line)
        if hint is not None:
            text.append('\n')
            text.append_text(clip(hint, width))
        card.set_class(running, 'running')
        card.update(text)

    def _render_warn(self) -> None:
        warn = self.query_one('#dash-warn', Static)
        # in B stehen die Kachelbereiche schon mit Abzeichen oben
        hidden = {'lauf'} | ({key for key, _, _ in TILES} if self.mode == 'b' else set())
        problems = [f for f in self.app.problems() if f.key not in hidden]
        if not problems:
            warn.display = False
            return
        worst = problems[0]
        width = max(30, self._left_w - 2)
        text = Text()
        text.append_text(badge(worst.level, f'{worst.label}: {worst.value}'))
        if len(problems) > 1:
            text.append(f'  +{len(problems) - 1} weitere', style=MUTED)
        if worst.hint and getattr(self, '_tall', True):
            text.append('\n')
            text.append_text(clip(help_line(worst.hint), width))
        warn.update(text)
        warn.display = True

    def actions(self) -> list[Action]:
        app = self.app
        service = app.fact('dienst')
        running = service is not None and service.level in (probes.OK, probes.WARN)
        no_unit = 'kein Dienst eingerichtet (portabel)' if app.instance.unit is None else None
        unchecked = 'Laufstatus noch nicht geprüft' if app.snapshot is None else None
        blocked = no_unit or unchecked or (app.blocker if running else None)
        actions = [
            Action('s', 'Werkbank stoppen' if running else 'Werkbank starten',
                   lambda: app.service_action('stop' if running else 'start'), blocked=blocked, danger=running,
                   icon='stop' if running else 'start'),
            Action('r', 'Neu starten', lambda: app.service_action('restart'), blocked=blocked, icon='restart'),
            Action('k', 'Kamera neu starten', app.camera_restart,
                   blocked=('Werkbank läuft nicht' if not running else app.blocker), icon='restart'),
        ]
        if app.instance.bridge_directory:
            actions.append(Action('b', 'Brücke: UART-Empfang', app.bridge_prepare, icon='bridge',
                                  blocked=None if running else 'Werkbank läuft nicht'))
        return actions

    def add_log(self, row) -> None:
        self.query_one('#tail-log', ReflowLog).add(row, scroll_end=True)

    def clear_log(self) -> None:
        self.query_one('#tail-log', ReflowLog).reset()
