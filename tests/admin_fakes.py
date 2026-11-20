"""Gemeinsame Beispieldaten für Tests und Bildschirmfotos der picam-Konsole.

``make_app(state=..., size=...)`` liefert eine ``PicamApp`` ohne echte Quellen.
Zustände: 'idle', 'run' (Lauf aktiv, Brücke über Netzwerk), 'setup'
(Einrichtung läuft), 'down' (Dienst ausgefallen).
"""

from __future__ import annotations

import time

from dispread.admin import probes
from dispread.admin.instance import Instance
from dispread.admin.service import LogLine

F = probes.Fact

INSTANCE = Instance(kind='system', unit='picam-werkbank.service', scope='system', config='/etc/picam/config.toml',
                    host='192.168.10.42', port=8080, socket='/run/picam/control.sock', pam_user='labor',
                    data='/var/lib/picam/workbench', live_data='/var/lib/picam/live',
                    bridge_directory='/var/lib/picam/workbench/bridge', bridge_name='Labor-Pi 2',
                    bridge_discovery=False, root='/opt/picam/releases/1.1.0')


def facts(state: str = 'idle') -> dict:
    d = {
        'dienst': F('dienst', 'Dienst', probes.OK, 'läuft', [('Unit', 'picam-werkbank.service'),
                    ('Art', 'Systemdienst'), ('Autostart', 'ja'), ('Seit', 'Do 2026-11-19 21:31:39 CET'),
                    ('PID', '1394956')]),
        'lauf': F('lauf', 'Lauf', probes.OK, 'kein Lauf', [('Zustand', 'kein Lauf')]),
        'kamera': F('kamera', 'Kamera', probes.OK, 'bereit', [('Gerät', '/dev/video0'), ('USB', '046d:0893'),
                    ('Anschluss', 'USB 3'), ('Format', '1920×1080 YUYV')]),
        'ausgabe': F('ausgabe', 'Ausgabe', probes.OFF, 'aus', [('Weg', 'aus')]),
        'bruecke': F('bruecke', 'Brücke', probes.WARN, 'nicht gekoppelt',
                     [('Pi-ID', '565e3468…'), ('Identität', 'vorhanden'), ('Name', 'Labor-Pi 2'), ('Kopplungen', '0'),
                      ('UART-Empfang', 'nicht vorbereitet')],
                     hint='Noch keine Windows-Brücke gekoppelt. In der Werkbank beim Laufstart „Brücke '
                          'einrichten…“ wählen: Profil laden, Code in die Windows-App eingeben.'),
        'zertifikat': F('zertifikat', 'Zertifikat', probes.OK, 'bis 11/2027',
                        [('Adresse', 'https://192.168.10.42:8080/live'), ('Gültig bis', '06.11.2027'),
                         ('Namen', '192.168.10.42'), ('Identität', 'urn:picam:pi:565e3468')]),
        'speicher': F('speicher', 'Speicher', probes.WARN, '2,5 GB frei',
                      [('Frei', '2,5 GB'), ('Reserve', '2,0 GB'), ('Laufdaten', '/var/lib/picam/live')],
                      hint='Wird knapp. Alte Läufe sichern und löschen (zeigt zuerst, was frei würde).',
                      command='picam aufraeumen'),
        'netzwerk': F('netzwerk', 'Netzwerk', probes.OK, 'eth0',
                      [('Werkbank-Adresse', '192.168.10.42'), ('eth0', '192.168.10.42')]),
        'vorlage': F('vorlage', 'Lesevorlage', probes.OK, 'geprüft',
                     [('Datei', '/opt/picam/current/src/dispread/data/templates-stufe2c-2026-09-30.json'),
                      ('SHA-256', 'stimmt')]),
        'kalibrierung': F('kalibrierung', 'Kalibrierung', probes.FAIL, 'fehlt',
                          [('Datei', '/var/lib/picam/calibration/timing-streamcam.json')],
                          hint=probes.CALIBRATION_HINT, command='picam kalibrieren'),
        'uart': F('uart', 'UART', probes.OK, 'aktiv', [('Gerät', '/dev/ttyAMA0 vorhanden'),
                  ('Boot', 'enable_uart=1'), ('Konsole', 'nicht auf UART')]),
        'konto': F('konto', 'Konto', probes.OK, 'labor', [('Konto', 'labor'), ('Gruppen', 'dialout, video')]),
        'uhr': F('uhr', 'Uhrzeit', probes.OK, 'synchron', [('NTP', 'synchronisiert')]),
        'version': F('version', 'Version', probes.OK, '1.1.0', [('Release', '1.1.0'), ('Commit', '9318ef6'),
                     ('Ort', '/opt/picam/releases/1.1.0'), ('Vorige', '1.0.0')]),
    }
    if state == 'run':
        d['lauf'] = F('lauf', 'Lauf', probes.OK, 'Lauf aktiv', [('Zustand', 'Lauf aktiv'),
                      ('Sitzung', 'live-20261120T091502Z'), ('Ausgabe', 'Netzwerk (Brücke)')])
        d['ausgabe'] = F('ausgabe', 'Ausgabe', probes.OK, 'Netzwerk (Brücke)', [('Weg', 'Netzwerk (Brücke)'),
                         ('Zustand', 'sending'), ('Brücke', 'verbunden')])
        d['bruecke'] = F('bruecke', 'Brücke', probes.OK, 'verbunden', [('Kopplungen', 'Netzwerk 1')])
        d['kalibrierung'] = F('kalibrierung', 'Kalibrierung', probes.OK, 'gültig', [])
    if state == 'setup':
        d['lauf'] = F('lauf', 'Lauf', probes.OK, 'Einrichtung läuft', [('Zustand', 'Einrichtung läuft')])
    if state == 'down':
        d['dienst'] = F('dienst', 'Dienst', probes.FAIL, 'ausgefallen', [('Unit', 'picam-werkbank.service'),
                        ('Ergebnis', 'exit-code')], hint='Protokoll ansehen, Ursache beheben, dann neu starten.',
                        command='picam logs')
        for key in ('lauf', 'ausgabe', 'bruecke'):
            d[key] = F(key, d[key].label, probes.OFF, '–', [('Grund', 'Dienst läuft nicht')])
        d['zertifikat'] = F('zertifikat', 'Zertifikat', probes.OFF, 'Dienst aus', [])
    return d


def live(state: str = 'idle') -> dict | None:
    if state == 'down':
        return None
    base = {'state': {'run': 'running', 'setup': 'setup_running'}.get(state, 'idle'), 'diagnose_kopie': False,
            'step': 'Lauf' if state == 'run' else ('Fokus' if state == 'setup' else None),
            'session_id': 'live-20261120T091502Z' if state != 'idle' else None,
            'storage': {'free_bytes': 2_500_000_000, 'reserve_bytes': 2_000_000_000, 'level': 'warn'},
            'system': {'cpu_percent': 31.0, 'cpu_window_s': 5.0},
            'camera': {'running': True, 'stalled': False, 'error': None, 'frames': 412_000, 'gaps': 3,
                       'source': {'device': '/dev/video0', 'usb_id': '046d:0893', 'speed_mbps': 5000,
                                  'size': [1920, 1080], 'fourcc': 'YUYV'},
                       'last_start': {'reason': 'serverstart', 'at_utc': '2026-11-19T20:32:03Z'}},
            'output': {'transport': 'off', 'state': 'off'}, 'run': None}
    if state == 'run':
        recent = []
        for index in range(240):
            status = 'v'
            if index in (37, 38, 120):
                status = 't'
            if index == 200:
                status = 'u'
            recent.append([index * 250, status, 0.4997])
        base['output'] = {'transport': 'tcp', 'state': 'sending', 'config': {'transport': 'tcp'}, 'error': None}
        base['run'] = {
            'latest': {'status': 'VALID', 'value': 0.4997, 'unit': 'mV/V', 'raw_text': ' 0.4997 mV/V',
                       'reject_reasons': [], 'frames_confirmed': 3, 'capture_timestamp': 0},
            'latest_age_s': 0.3,
            'counts': {'valid': 2841, 'transition': 37, 'unreadable': 4, 'stale': 0},
            'recent': recent, 'started_at_utc': '2026-11-20T09:15:02Z', 'elapsed_s': 724,
            'proc': {'fps': 29.8, 'latency_ms': 41.0, 'latency_now_ms': 59_000,
                     'latency_recent': [[i * 1000, 38 + (i % 7) * 2.5] for i in range(60)],
                     'skipped_recent': 0.02, 'cells': {'min_margin': 0.31, 'uncertain': 0}, 'age_s': 0.3},
        }
    return base


def collector(state: str = 'idle'):
    def collect(instance, include_setup=True, **_):
        return probes.Snapshot(instance, facts(state), live(state), time.time())
    return collect


def journal():
    rows = [('21:31:39', 'info', 'Werkbank: https://192.168.10.42:8080 | Anmeldung: labor'),
            ('21:32:03', 'info', 'Kamerastart (serverstart)'),
            ('21:32:03', 'info', 'Kamera: erstes Bild nach 0.60 s (serverstart)'),
            ('21:40:12', 'warnung', 'Brücke: Verbindung getrennt (Zeitüberschreitung)'),
            ('21:40:15', 'info', 'Brücke verbunden (Netzwerk, LABOR-PC-1)'),
            ('22:05:44', 'fehler', 'Live-Einrichtung: Rahmen verdeckt'),
            ('22:06:10', 'info', 'Einrichtung bestätigt')]
    return [LogLine(*row) for row in rows]


def metrics():
    return {'cpu_percent': 31.0, 'ram_percent': 34.0, 'ram_used': 2_870_000_000, 'ram_total': 8_450_000_000,
            'temperature_c': 51.2, 'load1': 1.3}


def storage(_instance=None):
    return {'total': 31_000_000_000, 'used': 28_500_000_000, 'free': 2_500_000_000, 'mount': '/',
            'groups': [('Läufe', '/var/lib/picam/live', 3_300_000_000),
                       ('Diagnose', '/var/lib/picam/live/*/run-*/diagnose', 2_400_000_000),
                       ('Werkbank-Daten', '/var/lib/picam/workbench', 450_000_000),
                       ('Brücke', '/var/lib/picam/workbench/bridge', 2_000_000),
                       ('Programmversionen', '/opt/picam/releases', 620_000_000),
                       ('Sonstiges', 'übriger Datenträger', 21_728_000_000)]}


def network():
    return {'hostname': 'raspi06', 'interfaces': [
        {'name': 'eth0', 'state': 'up', 'mac': '88:a2:9e:c8:c4:ef', 'addresses': ['192.168.10.42/24']},
        {'name': 'wlan0', 'state': 'down', 'mac': '88:a2:9e:c8:c4:f0', 'addresses': []},
        {'name': 'tailscale0', 'state': 'unknown', 'mac': None, 'addresses': ['100.122.154.35/32']}],
        'tailscale': {'state': 'Running', 'name': 'raspi06.tail4bdf43.ts.net', 'addresses': ['100.122.154.35']}}


class FakeSocket:
    """Zeichnet Steuerungsbefehle auf; Antwort je op einstellbar."""

    def __init__(self, replies: dict | None = None):
        self.calls: list[str] = []
        self.replies = replies or {}

    def __call__(self, path, op, timeout=5.0, args=None):
        self.calls.append(op)
        return self.replies.get(op, {'ok': True})


def make_app(state: str = 'idle', *, socket=None, popups: bool = False, **kwargs):
    from dispread.admin.tui import PicamApp

    return PicamApp(kwargs.pop('instance', INSTANCE), collect=collector(state), journal_source=journal,
                    auto_refresh=False, socket_request=socket or FakeSocket(), metrics_source=metrics,
                    storage_source=storage, network_source=lambda: network(), popups=popups, **kwargs)
