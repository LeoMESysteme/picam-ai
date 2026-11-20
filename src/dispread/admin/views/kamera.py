"""Tab Kamera: Daten der Logitech StreamCam, Kalibrierung, Lesevorlage, Kameraaktionen."""

from __future__ import annotations

from datetime import datetime

from rich.text import Text
from textual.widgets import Static

from .. import probes
from ..ui import Action, Segment, fact_title, hint_block, kv_table
from .base import FactView, actions_segment

DASH = '–'
START_REASONS = {'serverstart': 'Serverstart', 'restart': 'Neustart', 'connect': 'Verbinden',
                 'manual': 'von Hand'}


def _count(value) -> str:
    return DASH if value is None else f'{int(value):,}'.replace(',', '.')


def _local_time(stamp) -> str:
    try:
        return datetime.fromisoformat(str(stamp).replace('Z', '+00:00')).astimezone().strftime('%d.%m.%Y %H:%M:%S')
    except ValueError:
        return str(stamp) if stamp else DASH


def _port(source: dict) -> str:
    speed = source.get('usb_speed_mbps') or source.get('speed_mbps')
    if not speed:
        return DASH
    return 'USB 3 (blau)' if speed >= 5000 else f'USB 2 ({speed} Mbit/s)'


class KameraView(FactView):
    TAB_ID, TITLE, KEY = 'kamera', 'Kamera', '4'
    FACTS = ('kalibrierung', 'vorlage')
    INFO_TITLE = 'Kamera'
    INFO = ('Die Logitech StreamCam (USB 3) filmt die Anzeige des Messverstärkers. Nur die Werkbank darf '
            'sie halten, solange sie läuft; ein zweites Programm bekommt „belegt“.',
            '1920×1080 gibt es nur an einem blauen USB-3-Anschluss; an USB 2 fällt die Kamera auf kleinere '
            'Größen zurück und die Werkbank bricht ab.',
            'Kamera verbinden öffnet sie, falls sie nicht läuft (z. B. nach dem Einstecken). Kamera neu '
            'starten schließt und öffnet sie neu; die Vorschau setzt kurz aus. Das ist während eines Laufs '
            'gesperrt.',
            '„Lücken“ zählt Bilder, die der Treiber ausgelassen hat. Die Timing-Kalibrierung und die '
            'Lesevorlage sind Voraussetzungen für einen Messlauf.')

    def compose(self):
        with Segment():
            yield Static(id='cam-state', classes='fact-title first')
            yield Static(id='cam-hint', classes='hint')
            yield Static(id='cam-specs')
        with Segment('Voraussetzungen für einen Lauf'):
            for key in self.FACTS:
                yield from self.fact_widgets(key)
        yield actions_segment()

    def update_view(self) -> None:
        super().update_view()
        app = self.app
        fact = app.fact('kamera')
        state, hint = self.query_one('#cam-state', Static), self.query_one('#cam-hint', Static)
        if fact is None:
            state.update(Text('Logitech StreamCam', style='bold'))
            hint.display = False
        else:
            title = fact_title(fact)
            title.stylize('bold', 0, len('Kamera'))
            state.update(title)
            block = hint_block(fact)
            hint.display = block is not None
            if block is not None:
                hint.update(block)
                hint.set_class(fact.level == probes.FAIL, 'fail')
                hint.set_class(fact.level not in (probes.FAIL, probes.WARN), 'info')
        live = app.snapshot.live if app.snapshot is not None else None
        camera = (live or {}).get('camera')
        camera = camera if isinstance(camera, dict) else {}
        source = camera.get('source') if isinstance(camera.get('source'), dict) else {}
        detail = dict(fact.detail) if fact is not None else {}
        size = source.get('size')
        size_text = f'{size[0]}×{size[1]} {source.get("fourcc", "")}'.strip() if size else detail.get('Format', DASH)
        last = camera.get('last_start') if isinstance(camera.get('last_start'), dict) else {}
        reason = START_REASONS.get(last.get('reason'), last.get('reason')) if last else None
        if camera:
            run = 'läuft' if camera.get('running') else 'nicht offen'
            run += ' · hängt' if camera.get('stalled') else ''
        else:
            run = DASH
        rows = [('Modell', 'Logitech StreamCam'),
                ('USB-ID', source.get('usb_id') or detail.get('USB') or DASH),
                ('Anschluss', _port(source) if source else detail.get('Anschluss', DASH)),
                ('Gerät', source.get('device') or detail.get('Gerät') or DASH),
                ('Format', size_text or DASH),
                ('Bilder', _count(camera.get('frames')) if camera else DASH),
                ('Lücken', _count(camera.get('gaps')) if camera else DASH),
                ('Zustand', run),
                ('Letzter Start', (f'{reason} · {_local_time(last.get("at_utc"))}' if last else DASH))]
        if camera.get('error'):
            rows.append(('Fehler', str(camera['error'])))
        self.query_one('#cam-specs', Static).update(kv_table(rows))

    def actions(self) -> list[Action]:
        app = self.app
        service = app.fact('dienst')
        down = None if service is not None and service.level in (probes.OK, probes.WARN) else 'Werkbank läuft nicht'
        return [Action('v', 'Kamera verbinden', app.camera_connect, blocked=down),
                Action('k', 'Kamera neu starten', app.camera_restart, blocked=down or app.blocker),
                *super().actions()]
