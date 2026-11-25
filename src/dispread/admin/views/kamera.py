"""Tab Kamera: Daten der Logitech StreamCam, Kalibrierung, Lesevorlage, Kameraaktionen.

Je Abschnitt eine Karte (Kamera, Kalibrierung, Lesevorlage). Kalibrieren und
Prüfen/Importieren laufen im eigenen Bildschirm (``KalibrierenScreen``: Vorprüfung, Plan,
Schrittliste, Protokoll, Ergebnis), nicht mehr im pausierten Terminal; ``picam kalibrieren``
bleibt als Kommandozeile erhalten.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.text import Text

from .. import calibrate, probes
from ..ui import Action, AskScreen
from ..widgets import (
    ActionBar,
    SectionCard,
    TabBody,
    badge,
    detail_rows,
    fact_badge,
    fact_help,
    fields,
    header,
    help_line,
    value,
)
from .base import FactView, probes_label
from .kalibrieren_screen import KalibrierenScreen

DASH = '–'
MODEL = 'Logitech StreamCam'
START_REASONS = {'serverstart': 'Serverstart', 'restart': 'Neustart', 'connect': 'Verbinden',
                 'manual': 'von Hand'}
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
             'Lesevorlage sind Voraussetzungen für einen Messlauf.',
             'Kalibrieren misst den Versatz zwischen Telegramm und Anzeige einmal bei der Inbetriebnahme. Dafür '
             'muss ein USB-RS232-Adapter am RS232-Ausgang des Messverstärkers stecken; die Werkbank ist dabei einige '
             'Minuten aus und startet danach von selbst wieder. Datei prüfen/importieren übernimmt eine am '
             'gleichen Aufbau gemessene Datei nach ausdrücklicher Bestätigung.')
    INFO_FACTS = ('kamera', *FACTS)

    def compose(self):
        with TabBody(classes='tab-body'):
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
        if key == 'kamera' and (fact is None or not fact.hint):
            return help_line('Nur die Werkbank hält die Kamera, sonst „belegt“.', 'i', 'mehr')
        return fact_help(fact, PREREQUISITE)

    # ------------------------------------------------------------ Anzeige
    def update_view(self) -> None:
        card = self.query_one('#cam-card', SectionCard)
        width = self.card_width(card)
        fact, rows, _ = self._camera()
        columns = 2 if width >= 60 else 1
        card.show(header('camera', 'Kamera', fact_badge(fact), width, note=MODEL),
                  fields(rows, width, label_w=14, columns=columns), self._help('kamera', fact))
        for key in self.FACTS:
            card = self.query_one(f'#cam-{key}', SectionCard)
            fact = self.app.fact(key)
            card.show(header(GLYPHS[key], probes_label(key), fact_badge(fact), width),
                      fields(detail_rows(fact), width, label_w=14), self._help(key, fact))
        self.sync_buttons()

    def actions(self) -> list[Action]:
        app = self.app
        service = app.fact('dienst')
        down = None if service is not None and service.level in (probes.OK, probes.WARN) else 'Werkbank läuft nicht'
        return [Action('v', 'Kamera verbinden', app.camera_connect, blocked=down, icon='connect'),
                Action('k', 'Kamera neu starten', app.camera_restart, blocked=down or app.blocker, icon='restart'),
                Action('m', 'Kalibrieren …', self.calibrate, blocked=self.calibrate_blocker(), icon='clock'),
                Action('p', 'Datei prüfen/importieren …', self.check_or_import, blocked=self.import_blocker(),
                       icon='check')]

    # ------------------------------------------------------------ Kalibrierung
    def _service_up(self) -> bool:
        service = self.app.fact('dienst')
        return service is not None and service.level in (probes.OK, probes.WARN)

    def calibrate_blocker(self) -> str | None:
        app = self.app
        if not app.installed() or app.instance.unit is None or not app.instance.calibration:
            return 'nur für eine installierte Werkbank mit Dienst'
        if not calibrate.adapter_present(app.instance.reference_port):
            return f'kein USB-RS232-Adapter an {app.instance.reference_port}'
        if self._service_up():
            return app.blocker
        return None

    def import_blocker(self) -> str | None:
        app = self.app
        if not app.instance.calibration:
            return 'kein Kalibrierpfad (keine installierte Werkbank)'
        snapshot = app.snapshot
        if snapshot is not None and snapshot.run_active:
            return 'Lauf oder Einrichtung aktiv'
        return None

    def calibrate(self) -> None:
        if self.calibrate_blocker() is None:
            self.app.push_screen(KalibrierenScreen(self.app.instance, 'kalibrieren'))

    def check_or_import(self) -> None:
        if self.import_blocker() is None:
            self.app.run_worker(self._ask_file(), group='calibrate', exclusive=True)

    async def _ask_file(self) -> None:
        app = self.app
        current = app.instance.calibration or ''
        path = await app.push_screen_wait(AskScreen(
            'Kalibrierdatei prüfen/importieren',
            ['Die aktive Datei wird nur geprüft. Eine andere Datei wird geprüft, ihre Werte gezeigt und erst '
             'nach Eintippen von „importieren“ übernommen – nur für einen nachweislich gleichen Aufbau.',
             'Pfad der Datei:'],
            value=current, placeholder='/home/…/timing-streamcam.json'))
        if not path:
            return
        path = path.strip()
        same = bool(current) and Path(path).expanduser().resolve() == Path(current).resolve()
        app.push_screen(KalibrierenScreen(app.instance, 'pruefen' if same else 'import', path=path))
