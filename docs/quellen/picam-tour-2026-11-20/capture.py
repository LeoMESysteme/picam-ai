"""Render picam TUI with fake data at sizes, export SVG."""
import asyncio, sys, time
from pathlib import Path
from dispread.admin import probes
from dispread.admin.instance import Instance
from dispread.admin.service import LogLine
from dispread.admin.tui import PicamApp

OUT = Path(sys.argv[1])
F = probes.Fact
def facts(state):
    d = {
     'dienst': F('dienst','Dienst',probes.OK,'läuft',[('Unit','picam-werkbank.service'),('Art','Systemdienst'),('Autostart','ja'),('Seit','Do 2026-11-19 21:31:39 CET'),('PID','1394956')]),
     'lauf': F('lauf','Lauf',probes.OK,'kein Lauf',[('Zustand','kein Lauf')]),
     'kamera': F('kamera','Kamera',probes.OK,'bereit',[('Gerät','/dev/video0'),('USB','046d:0893'),('Anschluss','USB 3'),('Format','1920×1080 YUYV')]),
     'ausgabe': F('ausgabe','Ausgabe',probes.OFF,'aus',[('Weg','aus')]),
     'bruecke': F('bruecke','Brücke',probes.WARN,'nicht gekoppelt',[('Pi-ID','565e3468…'),('Identität','vorhanden'),('Kopplungen','0')],hint='Noch keine Windows-Brücke gekoppelt. In der Werkbank beim Laufstart „Brücke einrichten…“ wählen: Profil laden, Code in die Windows-App eingeben.'),
     'zertifikat': F('zertifikat','Zertifikat',probes.OK,'bis 11/2027',[('Adresse','https://192.168.10.42:8080/live'),('Gültig bis','06.11.2027'),('Namen','192.168.10.42')]),
     'speicher': F('speicher','Speicher',probes.WARN,'2,5 GB frei',[('Frei','2,5 GB'),('Reserve','2,0 GB'),('Laufdaten','/var/lib/picam/live')],hint='Wird knapp. Alte Läufe sichern und löschen (zeigt zuerst, was frei würde).',command='picam aufraeumen'),
     'vorlage': F('vorlage','Lesevorlage',probes.OK,'geprüft',[('Datei','/opt/picam/current/src/dispread/data/templates-stufe2c-2026-09-30.json'),('SHA-256','stimmt')]),
     'kalibrierung': F('kalibrierung','Kalibrierung',probes.FAIL,'fehlt',[('Datei','/var/lib/picam/calibration/timing-streamcam.json')],hint='Ohne Timing-Kalibrierung startet kein Messlauf. Am Aufbau messen (scripts/timing-calibration.py im Entwicklungs-Checkout) und die Datei hier ablegen.'),
     'uart': F('uart','UART',probes.OK,'aktiv',[('Gerät','/dev/ttyAMA0 vorhanden')]),
     'konto': F('konto','Konto',probes.OK,'labor',[('Konto','labor'),('Gruppen','dialout, video')]),
     'uhr': F('uhr','Uhrzeit',probes.OK,'synchron',[('NTP','synchronisiert')]),
     'version': F('version','Version',probes.OK,'1.1.0',[('Release','1.1.0'),('Commit','9318ef6'),('Ort','/opt/picam/releases/1.1.0'),('Vorige','1.0.0')],hint='Update: picam update --source picam-<version>.tar.gz · Rückweg: picam update --rollback'),
    }
    if state == 'run':
        d['lauf'] = F('lauf','Lauf',probes.OK,'Lauf aktiv',[('Zustand','Lauf aktiv'),('Sitzung','20261120T091502Z'),('Ausgabe','Netzwerk (Brücke)')],hint='Dienstaktionen sind während des Laufs gesperrt.')
        d['ausgabe'] = F('ausgabe','Ausgabe',probes.OK,'Netzwerk (Brücke)',[('Weg','Netzwerk (Brücke)'),('Brücke','verbunden')])
        d['bruecke'] = F('bruecke','Brücke',probes.OK,'verbunden',[('Kopplungen','1')])
        d['kalibrierung'] = F('kalibrierung','Kalibrierung',probes.OK,'vorhanden',[])
    if state == 'down':
        d['dienst'] = F('dienst','Dienst',probes.FAIL,'ausgefallen',[('Unit','picam-werkbank.service'),('Ergebnis','exit-code')],hint='Protokoll ansehen, Ursache beheben, dann neu starten.',command='picam logs')
        for k in ('lauf','ausgabe'): d[k]=F(k,d[k].label,probes.OFF,'–',[('Grund','Dienst läuft nicht')])
        d['zertifikat']=F('zertifikat','Zertifikat',probes.OFF,'Dienst aus',[])
        d['bruecke']=F('bruecke','Brücke',probes.OFF,'–',[])
    return d

def collector(state):
    def collect(instance, include_setup=True, **kw):
        live = {'state': 'running' if state=='run' else 'idle', 'diagnose_kopie': False}
        return probes.Snapshot(instance, facts(state), None if state=='down' else live, time.time())
    return collect

INST = Instance(kind='system', unit='picam-werkbank.service', scope='system', config='/etc/picam/config.toml',
                host='192.168.10.42', port=8080, socket='/run/picam/control.sock', pam_user='labor',
                data='/var/lib/picam/workbench', live_data='/var/lib/picam/live', bridge_name='Labor-Pi 2',
                bridge_discovery=False, root='/opt/picam/releases/1.1.0')

def journal():
    rows = [('21:31:39','info','Werkbank: https://192.168.10.42:8080 | Anmeldung: labor'),('21:32:03','info','Kamerastart (serverstart)'),
            ('21:32:03','info','Kamera: erstes Bild nach 0.60 s (serverstart)'),('21:40:12','warnung','Brücke: Verbindung getrennt (Zeitüberschreitung)'),
            ('21:40:15','info','Brücke verbunden (Netzwerk, LABOR-PC-1)'),('22:05:44','fehler','Live-Einrichtung: Rahmen verdeckt'),('22:06:10','info','Einrichtung bestätigt')]
    return [LogLine(*r) for r in rows]

async def shoot(name, size, state='idle', keys=()):
    app = PicamApp(INST, collect=collector(state), journal_source=journal, auto_refresh=False)
    async with app.run_test(size=size) as pilot:
        await pilot.pause(0.3)
        for k in keys:
            await pilot.press(k)
            await pilot.pause(0.15)
        await pilot.pause(0.3)
        (OUT / f'{name}.svg').write_text(app.export_screenshot(title=f'picam {size[0]}x{size[1]}'))

async def main():
    which = sys.argv[2:] or None
    cases = [
        ('01-uebersicht-120x40', (120,40), 'idle', ()),
        ('02-uebersicht-80x24', (80,24), 'idle', ()),
        ('03-dienst-80x24', (80,24), 'idle', ('down',)),
        ('04-neustart-bestaetigen-80x24', (80,24), 'idle', ('r',)),
        ('05-lauf-aktiv-gesperrt-80x24', (80,24), 'run', ('down','down')),
        ('06-dienst-ausgefallen-80x24', (80,24), 'down', ()),
        ('07-kalibrierung-fehlt-80x24', (80,24), 'idle', ('down',)*9),
        ('08-version-update-80x24', (80,24), 'idle', ('down',)*13),
        ('09-update-dialog-80x24', (80,24), 'idle', ('down',)*13 + ('u',)),
        ('10-protokoll-80x24', (80,24), 'idle', ('l',)),
        ('11-konfiguration-80x24', (80,24), 'idle', ('c',)),
        ('12-hilfe-80x24', (80,24), 'idle', ('question_mark',)),
        ('13-schmal-liste-60x20', (60,20), 'idle', ()),
        ('14-schmal-bereich-60x20', (60,20), 'idle', ('down','down','enter')),
        ('15-zu-klein-40x12', (40,12), 'idle', ()),
    ]
    old_cases = [
        ('home-120x40', (120,40), 'idle', ()),
        ('home-80x24', (80,24), 'idle', ()),
        ('dienst-80x24', (80,24), 'idle', ('down',)),
        ('kalib-80x24', (80,24), 'idle', ('down',)*10),
        ('run-80x24', (80,24), 'run', ('down',)*2),
        ('down-80x24', (80,24), 'down', ()),
        ('log-80x24', (80,24), 'idle', ('l',)),
        ('config-80x24', (80,24), 'idle', ('c',)),
        ('confirm-80x24', (80,24), 'idle', ('r',)),
        ('help-80x24', (80,24), 'idle', ('question_mark',)),
        ('narrow-60x20', (60,20), 'idle', ()),
        ('narrow-open-60x20', (60,20), 'idle', ('down','down','down','down','down','down','enter')),
        ('small-40x12', (40,12), 'idle', ()),
    ]
    for name, size, state, keys in cases:
        if which and name not in which: continue
        await shoot(name, size, state, keys)
asyncio.run(main())
