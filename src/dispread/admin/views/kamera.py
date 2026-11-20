"""Tab Kamera: Daten der Logitech StreamCam, Kalibrierung, Lesevorlage, Kameraaktionen.

Zwei Anordnungen (``PICAM_LAYOUT``): A „Karten + Abzeichen“ – je Abschnitt eine
Karte; B „Kacheln + Details“ – Kacheln Kamera, Kalibrierung, Lesevorlage, darunter
die Einzelheiten der gewählten Kachel.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath

from rich.text import Text
from textual import on

from .. import probes
from ..ui import Action
from ..widgets import (
    ActionBar,
    DetailPanel,
    SectionCard,
    TabBody,
    TileRow,
    badge,
    clip,
    fact_badge,
    fields,
    first_sentence,
    header,
    help_line,
    layout_mode,
    tile_text,
    value,
)
from .base import FactView, probes_label

DASH = '–'
MODEL = 'Logitech StreamCam'
START_REASONS = {'serverstart': 'Serverstart', 'restart': 'Neustart', 'connect': 'Verbinden',
                 'manual': 'von Hand'}
#: Detailwerte, die eine Aussage sind (Abzeichen statt Wertfeld).
DETAIL_STATES = {'stimmt': probes.OK, 'vorhanden': probes.OK, 'fehlt': probes.FAIL, 'weicht ab': probes.FAIL}
#: Zeichen je Abschnitt
GLYPHS = {'kamera': 'camera', 'kalibrierung': 'clock', 'vorlage': 'template'}
PREREQUISITE = 'Voraussetzung für einen Messlauf.'


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


def detail_rows(fact: probes.Fact | None) -> list:
    """Einzelheiten eines Befunds: Pfade breit, Aussagen als Abzeichen, sonst Wertfeld."""
    rows = []
    for key, raw in (fact.detail if fact is not None else []):
        text = str(raw)
        if text in DETAIL_STATES:
            rows.append((key, badge(DETAIL_STATES[text], text)))
        else:
            rows.append((key, value(text), text.startswith('/')))
    return rows


class KameraView(FactView):
    TAB_ID, TITLE, KEY = 'kamera', 'Kamera', '4'
    FACTS = ('kalibrierung', 'vorlage')
    OWN_BAR = True
    INFO_TITLE = 'Kamera'
    ABOUT = ('Die Logitech StreamCam (USB 3) filmt die Anzeige des Messverstärkers. Nur die Werkbank darf '
             'sie halten, solange sie läuft; ein zweites Programm bekommt „belegt“.',
             '1920×1080 gibt es nur an einem blauen USB-3-Anschluss; an USB 2 fällt die Kamera auf kleinere '
             'Größen zurück und die Werkbank bricht ab.',
             'Kamera verbinden öffnet sie, falls sie nicht läuft (z. B. nach dem Einstecken). Kamera neu '
             'starten schließt und öffnet sie neu; die Vorschau setzt kurz aus. Das ist während eines Laufs '
             'gesperrt.',
             '„Lücken“ zählt Bilder, die der Treiber ausgelassen hat. Die Timing-Kalibrierung und die '
             'Lesevorlage sind Voraussetzungen für einen Messlauf.')
    SCOPED_CSS = False
    DEFAULT_CSS = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode = layout_mode()
        self.tile_sel = 0

    @property
    def INFO(self) -> tuple[str, ...]:  # noqa: N802 - Schnittstelle der App (view.INFO)
        """Erklärung plus die vollständigen Hinweise der Befunde (auf dem Tab steht nur der erste Satz)."""
        hints = []
        for key in ('kamera', *self.FACTS):
            fact = self.app.fact(key) if self.is_mounted else None
            if fact is not None and fact.hint:
                hints.append(f'{fact.label}: {fact.hint}')
        return (*self.ABOUT, *hints)

    def compose(self):
        with TabBody(classes='tab-body'):
            if self.mode == 'b':
                yield TileRow(3, id='cam-tiles')
                yield DetailPanel(id='cam-detail')
            else:
                yield SectionCard(id='cam-card')
                yield SectionCard(id='cam-kalibrierung')
                yield SectionCard(id='cam-vorlage')
        yield ActionBar()

    # ------------------------------------------------------------ Daten
    def _camera(self) -> tuple[probes.Fact | None, list, Text | None]:
        """Befund, Zeilen (Beschriftung, Wert[, breit]) und Zustandsabzeichen der Kamera."""
        app = self.app
        fact = app.fact('kamera')
        live = app.snapshot.live if app.snapshot is not None else None
        camera = (live or {}).get('camera')
        camera = camera if isinstance(camera, dict) else {}
        source = camera.get('source') if isinstance(camera.get('source'), dict) else {}
        detail = dict(fact.detail) if fact is not None else {}
        size = source.get('size')
        size_text = f'{size[0]}×{size[1]} {source.get("fourcc", "")}'.strip() if size else detail.get('Format')
        last = camera.get('last_start') if isinstance(camera.get('last_start'), dict) else {}
        reason = START_REASONS.get(last.get('reason'), last.get('reason')) if last else None
        if not camera:
            state = value(None)
        elif camera.get('stalled'):
            state = badge(probes.WARN, 'hängt')
        elif camera.get('running'):
            state = badge(probes.OK, 'läuft', 'on')
        else:
            state = badge(probes.OFF, 'nicht offen')
        rows = [('Zustand', state),
                ('Anschluss', value(_port(source) if source else detail.get('Anschluss'))),
                ('Gerät', value(source.get('device') or detail.get('Gerät'))),
                ('USB-ID', value(source.get('usb_id') or detail.get('USB'))),
                ('Format', value(size_text)),
                ('Bilder', value(_count(camera.get('frames')) if camera else None)),
                ('Lücken', value(_count(camera.get('gaps')) if camera else None)),
                ('Letzter Start', value(f'{reason} · {_local_time(last.get("at_utc"))}' if last else None), True)]
        if camera.get('error'):
            rows.append(('Fehler', badge(probes.FAIL, str(camera['error'])), True))
        return fact, rows, state

    def _help(self, key: str, fact: probes.Fact | None) -> Text:
        if fact is not None and fact.hint:
            return help_line(first_sentence(fact.hint), 'i', 'Abhilfe')
        if key == 'kamera':
            return help_line('Nur die Werkbank hält die Kamera, sonst „belegt“.', 'i', 'mehr')
        return help_line(PREREQUISITE)

    # ------------------------------------------------------------ Anzeige
    def update_view(self) -> None:
        if self.mode == 'b':
            self._update_b()
        else:
            self._update_a()
        self.sync_buttons()

    def _update_a(self) -> None:
        card = self.query_one('#cam-card', SectionCard)
        width = card.inner_width(max(40, self.size.width - 6))
        fact, rows, _ = self._camera()
        columns = 2 if width >= 60 else 1
        card.show(header('camera', 'Kamera', fact_badge(fact), width, note=MODEL),
                  fields(rows, width, label_w=14, columns=columns), self._help('kamera', fact))
        for key in self.FACTS:
            card = self.query_one(f'#cam-{key}', SectionCard)
            fact = self.app.fact(key)
            card.show(header(GLYPHS[key], probes_label(key), fact_badge(fact), width),
                      fields(detail_rows(fact), width, label_w=14), self._help(key, fact))

    def _update_b(self) -> None:
        row = self.query_one('#cam-tiles', TileRow)
        inner = row.arrange(row.size.width or max(40, self.size.width - 4))
        cam_fact, cam_rows, _ = self._camera()
        keys = ('kamera', *self.FACTS)
        for index, key in enumerate(keys):
            fact = cam_fact if key == 'kamera' else self.app.fact(key)
            if key == 'kamera':
                live = self.app.snapshot.live if self.app.snapshot is not None else None
                frames = ((live or {}).get('camera') or {}).get('frames')
                kennzahl = value(_count(frames) if frames is not None else None, 'Bilder')
            else:
                path = dict(fact.detail).get('Datei') if fact is not None else None
                kennzahl = value(PurePosixPath(path).name if path else None)
            row.set_tile(index, tile_text(GLYPHS[key], probes_label(key), fact_badge(fact), kennzahl, inner))
        key = keys[self.tile_sel]
        detail = self.query_one('#cam-detail', DetailPanel)
        width = detail.inner_width(max(40, self.size.width - 8))
        if key == 'kamera':
            body = fields([('Modell', value(MODEL)), *cam_rows], width, label_w=14,
                          columns=2 if width >= 60 else 1)
            fact = cam_fact
        else:
            fact = self.app.fact(key)
            body = fields(detail_rows(fact), width, label_w=14)
        text = Text()
        text.append_text(body)
        text.append('\n')
        text.append_text(clip(self._help(key, fact), width))
        detail.update(text)

    @on(TileRow.Selected, '#cam-tiles')
    def _tile_selected(self, event: TileRow.Selected) -> None:
        self.tile_sel = event.index
        self.update_view()

    def actions(self) -> list[Action]:
        app = self.app
        service = app.fact('dienst')
        down = None if service is not None and service.level in (probes.OK, probes.WARN) else 'Werkbank läuft nicht'
        return [Action('v', 'Kamera verbinden', app.camera_connect, blocked=down, icon='connect'),
                Action('k', 'Kamera neu starten', app.camera_restart, blocked=down or app.blocker, icon='restart'),
                *super().actions()]
