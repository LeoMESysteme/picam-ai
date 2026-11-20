"""Tab Speicher: Belegung des Datenträgers, Reserve und Aufteilung auf die picam-Orte."""

from __future__ import annotations

from rich.text import Text
from textual.containers import Horizontal
from textual.widgets import Static

from .. import probes
from ..ui import ACCENT, MUTED, TONE, Action, ascii_mode, bar, fit, section, symbol
from .base import FactView


def gb(value: float | None) -> str:
    """Größe mit deutschem Dezimalkomma; unbekannt wird „–“."""
    if value is None:
        return '–'
    if value < 1e8:
        return f'{value / 1e6:.0f} MB'
    return f'{value / 1e9:.1f} GB'.replace('.', ',')


def reserve_bytes(app) -> int | None:
    live = app.snapshot.live if app.snapshot is not None else None
    storage = (live or {}).get('storage')
    if isinstance(storage, dict) and storage.get('reserve_bytes') is not None:
        return storage['reserve_bytes']
    try:
        from dispread.live.storage import STORAGE_RESERVE_BYTES
    except Exception:  # noqa: BLE001 - nur Anzeige
        return None
    return STORAGE_RESERVE_BYTES


class SpeicherView(FactView):
    TAB_ID, TITLE, KEY = 'speicher', 'Speicher', '7'
    FACTS = ('speicher',)
    INFO_TITLE = 'Speicher'
    INFO = ('Läufe, Diagnoseaufnahmen und Programmversionen liegen auf der SD-Karte des Pi. Die Werkbank hält '
            'eine Reserve an freiem Platz: Sinkt er darunter, lehnt sie neue Läufe ab, damit nichts '
            'halb geschrieben wird.',
            'Aufräumen listet zuerst alte Läufe und was dabei frei würde, und fragt vor dem Löschen. '
            'Die Größen werden im Hintergrund alle 60 s neu gezählt.')

    DEFAULT_CSS = """
    SpeicherView #sp-warn { margin: 1 0 0 0; }
    SpeicherView #sp-disk, SpeicherView #sp-groups { margin: 0; }
    """

    def compose(self):
        yield Static(Text(self.TITLE, style='bold'), classes='title')
        yield Static(id='sp-warn', classes='hint')
        yield section('Datenträger')
        yield Static(id='sp-disk')
        yield section('Aufteilung')
        yield Static(id='sp-groups')
        yield Static(id='sp-note', classes='note')
        yield Horizontal(id='buttons', classes='buttons')

    def on_resize(self) -> None:
        if self.is_mounted:
            self.update_view()

    def actions(self) -> list[Action]:
        return [Action('a', 'Aufräumen …', lambda: self.app.run_cli(['aufraeumen'], 'picam aufraeumen'))]

    def _width(self) -> int:
        return max(40, (self.size.width or 80) - 2)

    def update_view(self) -> None:
        app = self.app
        fact = app.fact('speicher')
        level = fact.level if fact is not None else probes.UNKNOWN
        warn = self.query_one('#sp-warn', Static)
        warn.display = level in (probes.WARN, probes.FAIL)
        if warn.display:
            text = Text()
            text.append(f'{symbol(level)} ', style=TONE[level])
            text.append('Läufe könnten abgelehnt werden' if level == probes.WARN
                        else 'Unter der Reserve: neue Läufe werden abgelehnt', style='bold')
            text.append('\n' + (fact.hint or ''))
            warn.update(text)
            warn.set_class(level == probes.FAIL, 'fail')
        usage = app.storage
        disk, groups = self.query_one('#sp-disk', Static), self.query_one('#sp-groups', Static)
        if usage is None:
            disk.update(Text('wird ermittelt …', style=MUTED))
            groups.update(Text('wird ermittelt …', style=MUTED))
        else:
            disk.update(self._disk(usage, level))
            groups.update(self._groups(usage))
        self.query_one('#sp-note', Static).update(
            Text('Aufräumen löscht erst nach Vorschau und Rückfrage.', style=MUTED))
        self.sync_buttons()

    def _disk(self, usage: dict, level: str) -> Text:
        total, used, free = usage.get('total'), usage.get('used'), usage.get('free')
        text = Text()
        if not total or used is None or free is None:
            text.append('Belegung unbekannt –', style=MUTED)
            return text
        width = self._width()
        bar_width = max(10, min(60, width))
        tone = TONE[level] if level in (probes.WARN, probes.FAIL) else ACCENT
        text.append(f"{usage.get('mount', '/')}   {gb(total)} gesamt\n", style=MUTED)
        text.append_text(bar(used / total, bar_width, tone))
        text.append(f'\nbelegt {gb(used)} ({used / total * 100:.0f} %)  ·  frei ', style='')
        text.append(gb(free), style=TONE[level] if level in (probes.WARN, probes.FAIL) else '')
        reserve = reserve_bytes(self.app)
        if reserve:
            mark = '^' if ascii_mode() else '▲'
            position = min(bar_width - 1, max(0, round((1 - reserve / total) * bar_width)))
            label = f'Reserve {gb(reserve)} frei'
            if position + 2 + len(label) <= bar_width + 10:
                line = ' ' * position + mark + ' ' + label
            else:
                line = ' ' * max(0, position - len(label) - 1) + label + ' ' + mark
            text.append('\n' + line, style=MUTED)
            if free >= reserve:
                text.append(f'\nNoch {gb(free - reserve)} bis zur Reserve. Darunter lehnt die Werkbank '
                            'neue Läufe ab.')
            else:
                text.append(f'\n{gb(reserve - free)} unter der Reserve: neue Läufe werden abgelehnt.',
                            style=TONE[probes.FAIL])
        return text

    def _groups(self, usage: dict) -> Text:
        total = usage.get('total') or 0
        width = self._width()
        bar_width = 14 if width >= 76 else 8
        rows = usage.get('groups') or []
        if not rows:
            return Text('–', style=MUTED)
        name_width = 19
        path_width = width - (name_width + bar_width + 12)
        text = Text(no_wrap=True, overflow='ellipsis')
        for index, (name, path, size) in enumerate(rows):
            if index:
                text.append('\n')
            text.append(name.ljust(name_width), style='bold' if name != 'Sonstiges' else MUTED)
            tone = MUTED if name == 'Sonstiges' else ACCENT
            text.append_text(bar((size or 0) / total if total else 0, bar_width, tone))
            text.append(' ' + gb(size).rjust(9) + ' ')
            if path_width >= 12:
                text.append(fit(str(path), path_width), style=MUTED)
        return text
