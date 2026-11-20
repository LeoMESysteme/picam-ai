"""Tab Speicher: Belegung des Datenträgers, Reserve und Aufteilung auf die picam-Orte."""

from __future__ import annotations

from rich.text import Text

from .. import probes
from ..ui import ACCENT, MUTED, TONE, Action, P, ascii_mode, bar
from ..widgets import ActionBar, SectionCard, TabBody, fact_badge, fields, header, help_line, shorten, value
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
    ABOUT = ('Läufe, Diagnoseaufnahmen und Programmversionen liegen auf der SD-Karte des Pi. Die Werkbank hält '
             'eine Reserve an freiem Platz: Sinkt er darunter, lehnt sie neue Läufe ab, damit nichts '
             'halb geschrieben wird.',
             'Aufräumen listet zuerst alte Läufe und was dabei frei würde, und fragt vor dem Löschen. '
             'Die Größen werden im Hintergrund alle 60 s neu gezählt.')
    INFO_FACTS = ('speicher',)

    def compose(self):
        with TabBody(classes='tab-body'):
            yield SectionCard(id='sp-disk')
            yield SectionCard(id='sp-groups')
        yield ActionBar()

    def actions(self) -> list[Action]:
        return [Action('a', 'Aufräumen …', lambda: self.app.run_cli(['aufraeumen'], 'picam aufraeumen'),
                       icon='storage')]

    def update_view(self) -> None:
        app = self.app
        fact = app.fact('speicher')
        level = fact.level if fact is not None else probes.UNKNOWN
        usage = app.storage
        disk, groups = self.query_one('#sp-disk', SectionCard), self.query_one('#sp-groups', SectionCard)
        width = self.card_width(disk)
        note = None
        if usage is not None and usage.get('total'):
            note = f"{gb(usage['total'])} gesamt · {usage.get('mount', '/')}"
        if level == probes.WARN:
            hint = help_line('Läufe könnten abgelehnt werden: wenig Platz.', 'i', 'Abhilfe')
        elif level == probes.FAIL:
            hint = help_line('Unter der Reserve: neue Läufe werden abgelehnt.', 'i', 'Abhilfe')
        else:
            hint = help_line('Unter der Reserve lehnt die Werkbank neue Läufe ab.')
        body = Text('wird ermittelt …', style=MUTED) if usage is None else self._disk(usage, level, width)
        disk.show(header('storage', 'Datenträger', fact_badge(fact), width, note=note), body, hint)
        body = Text('wird ermittelt …', style=MUTED) if usage is None else self._groups(usage, width)
        groups.show(header('file', 'Aufteilung', None, width), body,
                    help_line('Aufräumen löscht erst nach Vorschau und Rückfrage.'))
        self.sync_buttons()

    def _disk(self, usage: dict, level: str, width: int) -> Text:
        total, used, free = usage.get('total'), usage.get('used'), usage.get('free')
        if not total or used is None or free is None:
            return Text('Belegung unbekannt –', style=MUTED)
        bar_width = max(10, min(72, width))
        tight = level in (probes.WARN, probes.FAIL)
        tone = TONE[level] if tight else ACCENT
        text = Text()
        text.append_text(bar(used / total, bar_width, tone))
        reserve = reserve_bytes(self.app)
        if reserve:
            mark = '^' if ascii_mode() else '▲'
            position = min(bar_width - 1, max(0, round((1 - reserve / total) * bar_width)))
            label = f'Reserve {gb(reserve)} frei'
            if position + 2 + len(label) <= width:
                line = ' ' * position + mark + ' ' + label
            else:
                line = ' ' * max(0, position - len(label) - 1) + label + ' ' + mark
            text.append('\n' + line, style=MUTED)
        rows = [('belegt', value(gb(used), f'{used / total * 100:.0f} %')),
                ('frei', value(gb(free), tone=TONE[level] if tight else None, bold=tight))]
        if reserve:
            if free >= reserve:
                rows.append(('bis Reserve', value(gb(free - reserve))))
            else:
                rows.append(('unter Reserve', value(gb(reserve - free), tone=TONE[probes.FAIL], bold=True)))
        text.append('\n')
        text.append_text(fields(rows, width, label_w=14, columns=2 if width >= 60 else 1))
        return text

    def _groups(self, usage: dict, width: int) -> Text:
        total = usage.get('total') or 0
        rows = usage.get('groups') or []
        if not rows:
            return Text('–', style=MUTED)
        bar_width = 14 if width >= 76 else 8
        name_width = 19 if width >= 60 else 15
        size_width = 11
        path_width = width - (name_width + bar_width + size_width + 2)
        text = Text(no_wrap=True, overflow='ellipsis')
        for index, (name, path, size) in enumerate(rows):
            if index:
                text.append('\n')
            other = name == 'Sonstiges'
            text.append(name[:name_width - 1].ljust(name_width), style=MUTED)
            text.append_text(bar((size or 0) / total if total else 0, bar_width, MUTED if other else ACCENT))
            text.append(' ')
            text.append_text(value(gb(size).rjust(8)))
            if path_width >= 12:
                text.append(' ')
                if str(path).startswith('/'):
                    text.append_text(shorten(value(str(path), tone=P.text_soft), path_width))
                else:
                    text.append(str(path)[:path_width], style=MUTED)
        return text
