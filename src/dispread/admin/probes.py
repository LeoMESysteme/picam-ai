"""Status- und Diagnosequellen für picam.

Jede Prüfung liefert ein :class:`Fact`: Stufe, ein kurzes Wort für die
Übersicht, Detailzeilen und gegebenenfalls Abhilfe. Prüfungen lesen nur; sie
starten weder Kamera noch Lauf und ändern nichts. Fehlt eine Quelle, ist die
Stufe ``unknown`` — ein früherer Erfolg wird nicht weitergeführt.

Keine Messwerte, Bildzahlen oder Raten: die gehören in die Werkbank.
"""

from __future__ import annotations

import asyncio
import grp
import hashlib
import os
import pwd
import re
import shlex
import shutil
import socket
import ssl
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from dispread.camera_settings import STREAMCAM_USB_ID
from dispread.hardware_ports import GSV_UART_PORT, same_port, uart_devices

from .instance import Instance

OK, WARN, FAIL, OFF, UNKNOWN = 'ok', 'warn', 'fail', 'off', 'unknown'
LEVEL_ORDER = {FAIL: 0, WARN: 1, UNKNOWN: 2, OFF: 3, OK: 4}
#: Sichere Zustände für Dienststopp, wie scripts/werkbank-dienst.sh.
STOP_SAFE_STATES = frozenset({'idle', 'setup_ready', 'setup_failed', 'confirmed', 'stopped'})
CAMERA_USB_ID = STREAMCAM_USB_ID
UART_DEVICE = Path(GSV_UART_PORT)
BOOT_CONFIGS = (Path('/boot/firmware/config.txt'), Path('/boot/config.txt'))
BOOT_CMDLINES = (Path('/boot/firmware/cmdline.txt'), Path('/boot/cmdline.txt'))
TLS_WARN_DAYS = 30
STATE_WORDS = {
    'idle': 'kein Lauf', 'setup_running': 'Einrichtung läuft', 'setup_ready': 'Einrichtung bereit',
    'setup_failed': 'Einrichtung fehlgeschlagen', 'confirmed': 'eingerichtet', 'running': 'Lauf aktiv',
    'stopped': 'Lauf beendet',
}


@dataclass
class Fact:
    key: str
    label: str
    level: str
    value: str
    detail: list[tuple[str, str]] = field(default_factory=list)
    hint: str | None = None
    command: str | None = None

    def to_json(self) -> dict:
        data = asdict(self)
        data['detail'] = [list(row) for row in self.detail]
        return data


@dataclass
class Snapshot:
    instance: Instance
    facts: dict[str, Fact]
    live: dict | None
    collected_at: float

    def worst(self) -> str:
        levels = [fact.level for fact in self.facts.values()]
        return min(levels, key=LEVEL_ORDER.__getitem__) if levels else UNKNOWN

    @property
    def run_active(self) -> bool:
        return bool(self.live) and self.live.get('state') not in STOP_SAFE_STATES

    @property
    def stop_blocker(self) -> str | None:
        """Grund, warum Stoppen/Neustarten einen Lauf abbrechen würde (oder unbekannt ist)."""
        service = self.facts.get('dienst')
        if service is None or service.level in (OFF, FAIL):
            return None
        if self.live is None:
            return 'Laufstatus unbekannt (Steuerung nicht erreichbar)'
        state = self.live.get('state')
        if state not in STOP_SAFE_STATES:
            return f'{STATE_WORDS.get(state, state)} – erst in der Werkbank beenden'
        if self.live.get('diagnose_kopie'):
            return 'Diagnosekopie läuft noch – kurz warten'
        return None

    def to_json(self) -> dict:
        return {'schema': 'picam.status/1', 'instance': self.instance.to_json(),
                'collected_at_utc': datetime.fromtimestamp(self.collected_at, UTC).isoformat(),
                'overall': self.worst(), 'facts': [fact.to_json() for fact in self.facts.values()]}


def run_command(command, timeout=5.0):
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return done.returncode, done.stdout, done.stderr
    except (OSError, subprocess.TimeoutExpired) as error:
        return 127, '', str(error)


def systemctl(instance: Instance) -> list[str]:
    return ['systemctl'] + (['--user'] if instance.scope == 'user' else [])


def _gb(value: float) -> str:
    return f'{value / 1e9:.1f} GB'.replace('.', ',')


def _since(timestamp_text: str) -> str:
    return timestamp_text.split(' ', 1)[1] if ' ' in timestamp_text else timestamp_text


# --------------------------------------------------------------------- Quellen

def socket_request(path: str | None, op: str, timeout: float = 3.0, args: dict | None = None):
    """Lokale Steuerung der Werkbank; None, wenn nicht erreichbar."""
    if not path or not Path(path).exists():
        return None
    from dispread.workbench.cli import request

    async def ask():
        return await asyncio.wait_for(request(op, args, socket_path=path), timeout)
    try:
        return _run_coroutine(ask, timeout + 2.0)
    except (TimeoutError, OSError, ValueError, ImportError, RuntimeError):
        return None
    except Exception:  # aiohttp.ClientError u. a.: Quelle gilt als nicht erreichbar
        return None


def _run_coroutine(factory, wait_s: float):
    """``asyncio.run`` auch dann, wenn in diesem Thread schon eine Schleife läuft.

    Die Konsole (Textual) ruft die Laufprüfung vor einer sudo-Aktion im eigenen
    Event-Loop auf; ``asyncio.run`` lehnt das ab. Dann läuft die Abfrage in einem
    eigenen Thread mit eigener Schleife (raspi01, 20.11.: Stoppen scheiterte so
    stillschweigend an „Laufstatus unbekannt“).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    import threading

    outcome: dict = {}

    def worker() -> None:
        try:
            outcome['value'] = asyncio.run(factory())
        except BaseException as error:  # noqa: BLE001 - an den Aufrufer weiterreichen
            outcome['error'] = error

    thread = threading.Thread(target=worker, name='picam-socket', daemon=True)
    thread.start()
    thread.join(wait_s)
    if thread.is_alive():
        raise TimeoutError('Steuerung antwortet nicht')
    if 'error' in outcome:
        raise outcome['error']
    return outcome.get('value')


def peer_certificate(host: str, port: int, timeout: float = 3.0):
    """Zertifikat, das Browser und Brücke tatsächlich bekommen (ohne Vertrauensprüfung)."""
    from cryptography import x509

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as raw:
        with context.wrap_socket(raw, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    if der is None:
        raise ValueError('kein Zertifikat erhalten')
    return x509.load_der_x509_certificate(der)


# --------------------------------------------------------------------- Fakten

def fact_service(instance: Instance, run=run_command, ping=None) -> Fact:
    if instance.unit is None:
        if instance.kind != 'portable' or instance.problem:
            return Fact('dienst', 'Dienst', UNKNOWN, 'kein Dienst',
                        detail=[('Art', instance.label)], hint=instance.problem)
        # Portabel: kein Dienstmanager; läuft, wenn die lokale Steuerung antwortet.
        answer = (ping or (lambda: socket_request(instance.socket, 'live.status', timeout=2)))()
        detail = [('Art', 'portabel (ohne Dienstmanager)'), ('Steuerung', instance.socket or '–')]
        if answer is not None:
            return Fact('dienst', 'Dienst', OK, 'läuft', detail)
        start = shlex.join([sys.executable, '-m', 'dispread.workbench.cli', 'serve', '--config', str(instance.config)])
        return Fact('dienst', 'Dienst', OFF, 'gestoppt', detail, hint='Portabel installiert: von Hand starten.',
                    command=start)
    code, out, err = run(systemctl(instance) + ['show', instance.unit, '-p', 'ActiveState', '-p', 'SubState',
                                                '-p', 'ActiveEnterTimestamp', '-p', 'MainPID',
                                                '-p', 'LoadState', '-p', 'UnitFileState', '-p', 'Result'])
    if code != 0:
        return Fact('dienst', 'Dienst', UNKNOWN, 'unbekannt', detail=[('Fehler', err.strip() or str(code))])
    props = dict(line.split('=', 1) for line in out.splitlines() if '=' in line)
    state = props.get('ActiveState', 'unknown')
    detail = [('Unit', instance.unit + (' (Benutzer)' if instance.scope == 'user' else '')),
              ('Art', instance.label)]
    if props.get('UnitFileState'):
        detail.append(('Autostart', {'enabled': 'ja', 'disabled': 'nein', 'static': 'statisch',
                                     'transient': 'nein (systemd-run)'}
                       .get(props['UnitFileState'], props['UnitFileState'])))
    if state == 'active':
        detail += [('Seit', _since(props.get('ActiveEnterTimestamp', ''))), ('PID', props.get('MainPID', '?'))]
        return Fact('dienst', 'Dienst', OK, 'läuft', detail)
    if state in ('activating', 'reloading', 'deactivating'):
        return Fact('dienst', 'Dienst', WARN, {'activating': 'startet', 'deactivating': 'stoppt'}
                    .get(state, state), detail)
    if state == 'failed':
        return Fact('dienst', 'Dienst', FAIL, 'ausgefallen', detail + [('Ergebnis', props.get('Result', '?'))],
                    hint='Protokoll ansehen, Ursache beheben, dann neu starten.', command='picam logs')
    return Fact('dienst', 'Dienst', OFF, 'gestoppt', detail, hint='Dienst starten.', command='picam start')


def fact_https(instance: Instance, service: Fact) -> tuple[Fact, object | None]:
    if not instance.host or not instance.port:
        return Fact('zertifikat', 'Zertifikat', UNKNOWN, 'Adresse fehlt'), None
    if service.level in (OFF, FAIL):
        return Fact('zertifikat', 'Zertifikat', OFF, 'Dienst aus', [('Adresse', instance.url or '')]), None
    try:
        cert = peer_certificate(instance.host, instance.port)
    except (OSError, ssl.SSLError, ValueError) as error:
        return Fact('zertifikat', 'Zertifikat', FAIL, 'keine Antwort',
                    [('Adresse', instance.url or ''), ('Fehler', str(error))],
                    hint='Werkbank antwortet nicht über HTTPS. Protokoll prüfen.', command='picam logs'), None
    from cryptography import x509

    left = cert.not_valid_after_utc - datetime.now(UTC)
    try:
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        san = [str(n.value) for n in names if isinstance(n, (x509.DNSName, x509.IPAddress))]
        uris = [str(n.value) for n in names if isinstance(n, x509.UniformResourceIdentifier)]
    except x509.ExtensionNotFound:
        san = []
    detail = [('Adresse', instance.url or ''), ('Gültig bis', cert.not_valid_after_utc.strftime('%d.%m.%Y')),
              ('Namen', ', '.join(san) or '–')]
    if uris:
        detail.append(('Identität', ', '.join(uris)))
    if left.days < 0:
        return Fact('zertifikat', 'Zertifikat', FAIL, 'abgelaufen', detail,
                    hint='Neues Zertifikat erzeugen und Windows-Vertrauen erneuern.'), cert
    if instance.host not in san:
        return Fact('zertifikat', 'Zertifikat', WARN, 'Name fehlt', detail,
                    hint=(f'{instance.host} steht nicht im Zertifikat: Browser warnen bei dieser Adresse. '
                          'Die Brücke prüft die Pi-Identität und ist nicht betroffen.')), cert
    if left.days < TLS_WARN_DAYS:
        return Fact('zertifikat', 'Zertifikat', WARN, f'noch {left.days} Tage', detail,
                    hint='Zertifikat bald erneuern.'), cert
    return Fact('zertifikat', 'Zertifikat', OK, f'bis {cert.not_valid_after_utc:%m/%Y}', detail), cert


def fact_run(live: dict | None, service: Fact) -> Fact:
    if service.level in (OFF, FAIL):
        return Fact('lauf', 'Lauf', OFF, '–', [('Grund', 'Dienst läuft nicht')])
    if live is None:
        return Fact('lauf', 'Lauf', UNKNOWN, 'unbekannt', [('Grund', 'Steuerung nicht erreichbar')],
                    hint='Lokale Steuerung antwortet nicht. Dienst gerade gestartet? Sonst Protokoll prüfen.')
    state = live.get('state') or 'unknown'
    word = STATE_WORDS.get(state, state)
    detail = [('Zustand', word)]
    if live.get('session_id'):
        detail.append(('Sitzung', str(live['session_id'])))
    if live.get('step'):
        detail.append(('Schritt', str(live['step'])))
    output = live.get('output') or {}
    if state == 'running':
        detail.append(('Ausgabe', _transport_word(output.get('transport'))))
        if live.get('test_run'):
            detail.append(('Modus', 'Testlauf'))
    if live.get('diagnose_kopie'):
        detail.append(('Diagnosekopie', 'läuft'))
    if live.get('error'):
        return Fact('lauf', 'Lauf', FAIL, word, detail + [('Fehler', str(live['error']))],
                    hint='Meldung in der Werkbank ansehen.')
    if state == 'setup_failed':
        return Fact('lauf', 'Lauf', WARN, word, detail, hint='In der Werkbank neu einrichten.')
    if state == 'running':
        return Fact('lauf', 'Lauf', OK, word, detail,
                    hint='Dienstaktionen sind während des Laufs gesperrt.')
    return Fact('lauf', 'Lauf', OK, word, detail)


def _transport_word(transport) -> str:
    return {'off': 'aus', None: 'aus', 'serial': 'UART direkt', 'bridge_network': 'Netzwerk (Brücke)',
            'bridge_uart': 'UART über Brücke', 'network': 'Netzwerk',
            # Laufausgabe (live/output.py): off | serial | uart | tcp
            'uart': 'UART über Brücke', 'tcp': 'Netzwerk (Brücke)'}.get(transport, str(transport))


def _usb_camera(sys_root: Path = Path('/sys/bus/usb/devices')) -> dict | None:
    vendor, product = CAMERA_USB_ID.split(':')
    try:
        entries = list(sys_root.iterdir())
    except OSError:
        return None
    for entry in entries:
        try:
            if (entry / 'idVendor').read_text().strip() == vendor and \
                    (entry / 'idProduct').read_text().strip() == product:
                return {'speed_mbps': int((entry / 'speed').read_text().strip() or 0), 'port': entry.name}
        except (OSError, ValueError):
            continue
    return None


def fact_camera(live: dict | None, service: Fact, usb=_usb_camera) -> Fact:
    camera = (live or {}).get('camera')
    if (live or {}).get('simulate') and service.level == OK:
        return Fact('kamera', 'Kamera', OFF, 'Simulation', [('Quelle', 'synthetische Bilder (--simulate)')],
                    hint='Die Werkbank läuft ohne Kamera; keine Messläufe mit echten Werten.')
    if isinstance(camera, dict) and service.level == OK:
        source = camera.get('source') or {}
        detail = [('Gerät', str(source.get('device', '–'))), ('USB', str(source.get('usb_id', '–')))]
        speed = source.get('usb_speed_mbps')
        if speed:
            detail.append(('Anschluss', 'USB 3' if speed >= 5000 else f'USB 2 ({speed} Mbit/s)'))
        size = source.get('size')
        if size:
            detail.append(('Format', f"{size[0]}×{size[1]} {source.get('fourcc', '')}".strip()))
        if camera.get('error'):
            return Fact('kamera', 'Kamera', FAIL, 'Fehler', detail + [('Fehler', str(camera['error']))],
                        hint='Kamera abziehen, an blauen USB-3-Port stecken, Dienst neu starten.')
        if camera.get('stalled'):
            return Fact('kamera', 'Kamera', FAIL, 'hängt', detail,
                        hint='Kamera liefert keine Bilder. Kabel prüfen, Dienst neu starten.')
        if not camera.get('running'):
            return Fact('kamera', 'Kamera', WARN, 'nicht offen', detail)
        if speed and speed < 5000:
            return Fact('kamera', 'Kamera', WARN, 'USB 2', detail,
                        hint='An einen blauen USB-3-Port stecken; an USB 2 fehlt 1920×1080.')
        return Fact('kamera', 'Kamera', OK, 'bereit', detail)
    found = usb()
    if found is None:
        return Fact('kamera', 'Kamera', FAIL, 'nicht gefunden', [('Gesucht', f'StreamCam {CAMERA_USB_ID}')],
                    hint='StreamCam an einen blauen USB-3-Port stecken.')
    detail = [('USB', CAMERA_USB_ID), ('Anschluss', 'USB 3' if found['speed_mbps'] >= 5000
                                       else f"USB 2 ({found['speed_mbps']} Mbit/s)")]
    if found['speed_mbps'] < 5000:
        return Fact('kamera', 'Kamera', WARN, 'USB 2', detail, hint='An einen blauen USB-3-Port stecken.')
    return Fact('kamera', 'Kamera', OK, 'angeschlossen', detail)


def fact_output(live: dict | None, bridge: dict | None, service: Fact) -> Fact:
    if service.level in (OFF, FAIL):
        return Fact('ausgabe', 'Ausgabe', OFF, '–', [('Grund', 'Dienst läuft nicht')])
    if live is None:
        return Fact('ausgabe', 'Ausgabe', UNKNOWN, 'unbekannt')
    output = live.get('output') or {}
    transport = output.get('transport')
    detail = [('Weg', _transport_word(transport)), ('Zustand', str(output.get('state', '–')))]
    if bridge is not None:
        detail.append(('Brücke', 'verbunden' if bridge.get('connected') else 'nicht verbunden'))
        if bridge.get('transport'):
            detail.append(('Brückenweg', _transport_word(bridge['transport'])))
    if transport in (None, 'off'):
        return Fact('ausgabe', 'Ausgabe', OFF, 'aus', detail)
    if output.get('error'):
        return Fact('ausgabe', 'Ausgabe', FAIL, 'Fehler', detail + [('Fehler', str(output['error']))])
    return Fact('ausgabe', 'Ausgabe', OK, _transport_word(transport), detail)


def pairing_counts(database: Path) -> dict | None:
    """Gekoppelte Windows-Apps je Weg, nur lesend; None, wenn nicht lesbar."""
    import sqlite3

    if not database.is_file():
        return {}
    try:
        connection = sqlite3.connect(f'file:{database}?mode=ro', uri=True, timeout=2)
        try:
            rows = connection.execute('SELECT transport, COUNT(*) FROM clients GROUP BY transport').fetchall()
        finally:
            connection.close()
    except sqlite3.Error:
        return None
    return {str(transport): int(count) for transport, count in rows}


def fact_bridge(instance: Instance, bridge: dict | None, service: Fact) -> Fact:
    identity = Path(instance.bridge_directory) / 'identity.json' if instance.bridge_directory else None
    detail = []
    if identity is not None:
        detail.append(('Identität', 'vorhanden' if identity.is_file() else 'fehlt'))
    if instance.bridge_name:
        detail.append(('Name', instance.bridge_name))
    if identity is None:
        return Fact('bruecke', 'Brücke', OFF, 'ohne Brücke', [('Grund', 'keine Brückenidentität konfiguriert')])
    if not identity.is_file():
        return Fact('bruecke', 'Brücke', FAIL, 'keine Identität', detail,
                    hint='Identität anlegen.', command='dispread bridge identity --provision')
    counts = pairing_counts(identity.parent / 'pairing' / 'pairing.sqlite3')
    pairs = sum(counts.values()) if counts is not None else None
    if counts is None:
        detail.append(('Kopplungen', 'nicht lesbar'))
    else:
        words = {'network': 'Netzwerk', 'uart': 'UART'}
        detail.append(('Kopplungen', ', '.join(f'{words.get(k, k)} {n}' for k, n in sorted(counts.items()))
                       or 'keine'))
    if bridge is None:
        level = OFF if service.level in (OFF, FAIL) else UNKNOWN
        return Fact('bruecke', 'Brücke', level, '–' if level == OFF else 'unbekannt', detail)
    if bridge.get('pi_id'):
        detail.insert(0, ('Pi-ID', str(bridge['pi_id'])[:8] + '…'))
    detail.append(('UART-Empfang', {'unprepared': 'nicht vorbereitet', 'prepared': 'vorbereitet',
                                    'ready': 'bereit'}.get(bridge.get('uart_state'), str(bridge.get('uart_state')))))
    if bridge.get('connected'):
        return Fact('bruecke', 'Brücke', OK, 'verbunden', detail)
    if pairs == 0:  # None (nicht lesbar) behauptet keine fehlende Kopplung
        return Fact('bruecke', 'Brücke', WARN, 'nicht gekoppelt', detail,
                    hint='Noch keine Windows-Brücke gekoppelt. In der Werkbank beim Laufstart '
                         '„Brücke einrichten…“ wählen: Profil laden, Code in die Windows-App eingeben.')
    return Fact('bruecke', 'Brücke', OK, 'gekoppelt', detail + [('Verbindung', 'gerade keine')])


def fact_storage(instance: Instance, live: dict | None) -> Fact:
    storage = (live or {}).get('storage')
    target = instance.live_data or instance.data
    if isinstance(storage, dict) and storage.get('free_bytes') is not None:
        free, reserve = storage['free_bytes'], storage.get('reserve_bytes') or 0
    elif target:
        from dispread.live.storage import STORAGE_RESERVE_BYTES

        path = Path(target)
        while not path.exists() and path != path.parent:
            path = path.parent
        try:
            free, reserve = shutil.disk_usage(path).free, STORAGE_RESERVE_BYTES
        except OSError:
            return Fact('speicher', 'Speicher', UNKNOWN, 'unbekannt')
    else:
        return Fact('speicher', 'Speicher', UNKNOWN, 'unbekannt')
    detail = [('Frei', _gb(free)), ('Reserve', _gb(reserve))]
    if target:
        detail.append(('Laufdaten', target))
    if free < reserve:
        return Fact('speicher', 'Speicher', FAIL, f'{_gb(free)} frei', detail,
                    hint='Unter der Reserve: neue Läufe werden abgelehnt. Alte Läufe sichern und löschen '
                         '(zeigt zuerst, was frei würde).',
                    command='picam aufraeumen')
    if free < 2 * reserve:
        return Fact('speicher', 'Speicher', WARN, f'{_gb(free)} frei', detail,
                    hint='Wird knapp. Alte Läufe sichern und löschen (zeigt zuerst, was frei würde).',
                    command='picam aufraeumen')
    return Fact('speicher', 'Speicher', OK, f'{_gb(free)} frei', detail)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 16), b''):
            digest.update(block)
    return digest.hexdigest()


def fact_templates(instance: Instance) -> Fact:
    from dispread.live import resolve_templates_path
    from dispread.sensors import get_sensor

    if instance.kind == 'none' or (instance.problem and instance.config):
        return Fact('vorlage', 'Lesevorlage', UNKNOWN, 'unbekannt')
    try:
        definition = get_sensor(instance.sensor)
        configured = Path(instance.templates) if instance.templates else None
        path = resolve_templates_path(definition, configured)
    except (OSError, ValueError) as exc:
        return Fact('vorlage', 'Lesevorlage', FAIL, str(exc))
    if not path.is_file():
        return Fact('vorlage', 'Lesevorlage', FAIL, 'fehlt', [('Datei', str(path))],
                    hint='Die eingefrorene Vorlage gehört zum Release; neu installieren.')
    if _sha256(path) != definition.templates.sha256:
        return Fact('vorlage', 'Lesevorlage', FAIL, 'verändert', [('Datei', str(path))],
                    hint='Prüfsumme stimmt nicht. Vorlage aus dem Release wiederherstellen.')
    details = [('Datei', str(path)), ('SHA-256', 'stimmt')]
    if configured is not None and configured != path:
        details.append(('Paketvorlage verwendet', f'Alte Vorlagendatei {configured} fehlt'))
    return Fact('vorlage', 'Lesevorlage', OK, 'geprüft', details)


CALIBRATION_HINT = ('Ohne gültige Timing-Kalibrierung startet kein Messlauf. Einmalig mit gestecktem '
                    'USB-RS232-Adapter am Messverstärker messen (picam kalibrieren) oder eine am gleichen '
                    'Aufbau gemessene Datei prüfen und importieren (picam kalibrieren --import DATEI).')


def _live_camera_id(live: dict | None) -> str | None:
    camera = (live or {}).get('camera')
    source = camera.get('source') if isinstance(camera, dict) else None
    usb_id = source.get('usb_id') if isinstance(source, dict) else None
    return usb_id if isinstance(usb_id, str) and usb_id else None


def fact_calibration(instance: Instance, now=time.time, camera_id: str | None = None) -> Fact:
    """Kalibrierdatei laden und prüfen (wie der Laufstart) und gegen die Kamera
    abgleichen: ``camera_id`` aus dem Kamerastatus der Werkbank, sonst die
    unterstützte StreamCam."""
    from dispread.timing_calibration import load_calibration

    from .calibrate import import_note_path

    if not instance.calibration:
        return Fact('kalibrierung', 'Kalibrierung', UNKNOWN, 'unbekannt')
    path = Path(instance.calibration)
    if not path.is_file():
        return Fact('kalibrierung', 'Kalibrierung', FAIL, 'fehlt', [('Datei', str(path))],
                    hint=CALIBRATION_HINT, command='picam kalibrieren')
    try:
        calibration = load_calibration(path)
    except ValueError as error:
        return Fact('kalibrierung', 'Kalibrierung', FAIL, 'ungültig', [('Datei', str(path)), ('Fehler', str(error))],
                    hint='Die Datei ist unbrauchbar; der Laufstart bleibt gesperrt. ' + CALIBRATION_HINT,
                    command='picam kalibrieren')
    expected = camera_id or CAMERA_USB_ID
    detail = [('Datei', str(path)), ('Kamera', calibration.camera_usb_id),
              ('Versatz δ', f'{calibration.display_offset_ms:.0f} ms'),
              ('Schutzabstand M', f'{calibration.guard_margin_ms:.0f} ms')]
    try:
        measured = datetime.fromisoformat(calibration.measured_at_utc.replace('Z', '+00:00'))
        detail.append(('Gemessen', measured.astimezone().strftime('%d.%m.%Y')))
        age_days = int((now() - measured.timestamp()) // 86400)
        detail.append(('Alter', f'{age_days} Tage'))
    except ValueError:
        detail.append(('Gemessen', calibration.measured_at_utc))
    note = import_note_path(path)
    if note.is_file():
        detail.append(('Herkunft', 'importiert, siehe ' + str(note)))
    if calibration.camera_usb_id != expected:
        return Fact('kalibrierung', 'Kalibrierung', FAIL, 'andere Kamera',
                    detail + [('Erwartet', expected)],
                    hint=(f'Die Kalibrierung gilt für Kamera {calibration.camera_usb_id}, angeschlossen ist '
                          f'{expected}. Der Laufstart bleibt gesperrt. Mit dieser Kamera neu kalibrieren.'),
                    command='picam kalibrieren')
    return Fact('kalibrierung', 'Kalibrierung', OK, 'gültig', detail)


def _boot_text(paths) -> tuple[Path | None, str]:
    for path in paths:
        try:
            return path, path.read_text()
        except OSError:
            continue
    return None, ''


def fact_uart(device: Path = UART_DEVICE, configs=BOOT_CONFIGS, cmdlines=BOOT_CMDLINES, *,
              output_port: str | None = None) -> Fact:
    from .uart_ports import CHECK_AFTER_REBOOT, UARTS, read_boot_config

    configured = output_port or str(device)
    mapped = uart_devices() if output_port is not None else {}
    if configured.startswith('uart'):
        uart = configured
        device = Path(mapped[uart]) if uart in mapped else None
    elif output_port is not None:
        device = Path(configured)
        uart = next((key for key, port in mapped.items() if same_port(port, configured)), None)
    else:
        uart = 'uart0'
    if uart is None and configured == GSV_UART_PORT:
        uart = 'uart0'
    config_path = next((path for path in configs if path.exists()), None)
    _, cmdline = _boot_text(cmdlines)
    try:
        boot = read_boot_config(config_path) if config_path else None
    except (OSError, ValueError) as error:
        return Fact('uart', 'UART', WARN, 'Bootkonfiguration nicht lesbar', [('Fehler', str(error))])
    enabled = bool(boot and uart in boot.enabled_uarts)
    detail = [('Ausgang', configured),
              ('Gerät', str(device) if device and device.exists() else 'fehlt')]
    if config_path:
        detail.append(('Bootdatei', str(config_path)))
    consoles = re.findall(r'(?:^|\s)console=([^,\s]+)', cmdline)
    if device and any(same_port(str(device), '/dev/' + console) or console == device.name
                      for console in consoles):
        return Fact('uart', 'UART', WARN, 'Konsole belegt', detail,
                    hint='Serielle Konsole abschalten (raspi-config → Interface → Serial: Login-Shell nein).')
    if not device or not device.exists() or (uart and not enabled):
        function = next((item for item in UARTS if item.uart == uart), None)
        hint = (f'{function.overlay_line} in config.txt aktivieren und Pi neu starten.'
                if function and not enabled else CHECK_AFTER_REBOOT)
        return Fact('uart', 'UART', WARN, 'nicht aktiv', detail, hint=hint)
    return Fact('uart', 'UART', OK, 'aktiv', detail)


def fact_groups(instance: Instance) -> Fact:
    user = instance.pam_user or os.environ.get('USER') or ''
    try:
        entry = pwd.getpwnam(user)
    except KeyError:
        return Fact('konto', 'Konto', FAIL, 'fehlt', [('Konto', user or '–')],
                    hint='Das Dienstkonto existiert nicht.')
    members = {g.gr_name for g in grp.getgrall() if user in g.gr_mem}
    try:
        members.add(grp.getgrgid(entry.pw_gid).gr_name)
    except KeyError:
        pass
    missing = [name for name in ('video', 'dialout') if name not in members]
    detail = [('Konto', user), ('Gruppen', ', '.join(sorted(members & {'video', 'dialout'})) or '–')]
    if missing:
        return Fact('konto', 'Konto', WARN, 'Gruppe fehlt', detail,
                    hint=f"{user} fehlt in {', '.join(missing)} (Kamera/UART). Danach neu anmelden.",
                    command=shlex.join(['sudo', 'usermod', '-aG', ','.join(missing), user]))
    return Fact('konto', 'Konto', OK, user, detail)


def fact_version(instance: Instance, run=run_command) -> Fact:
    root = Path(instance.root) if instance.root else None
    detail = []
    if root is not None and (root / 'release.json').is_file():
        import json

        try:
            manifest = json.loads((root / 'release.json').read_text())
            detail = [('Release', str(manifest.get('release_id', '?'))),
                      ('Commit', str(manifest.get('commit', '?'))[:10]), ('Ort', str(root))]
            previous = root.parent.parent / 'previous'
            if previous.is_symlink() and previous.resolve().is_dir():
                detail.append(('Vorige', previous.resolve().name))
            return Fact('version', 'Version', OK, str(manifest.get('release_id', '?')), detail,
                        hint='Update: picam update · Rückweg: picam update --rollback')
        except (OSError, ValueError):
            pass
    if root is not None and (root / 'VERSION').is_file():
        try:
            return Fact('version', 'Version', OK, (root / 'VERSION').read_text().strip())
        except OSError:
            pass
    if root is not None and (root / '.git').exists():
        code, out, _ = run(['git', '-C', str(root), 'describe', '--tags', '--always', '--dirty'])
        if code == 0 and out.strip():
            text = out.strip()
            detail = [('Stand', text), ('Ort', str(root))]
            return Fact('version', 'Version', OK, text.split('-g')[0] if '-g' in text else text, detail)
    from importlib import metadata

    try:
        return Fact('version', 'Version', OK, metadata.version('picam-number-ingestion'))
    except metadata.PackageNotFoundError:
        return Fact('version', 'Version', UNKNOWN, 'unbekannt')


def fact_linger(instance: Instance, run=run_command) -> Fact | None:
    if instance.scope != 'user' or instance.kind == 'portable':
        return None
    user = os.environ.get('USER') or ''
    code, out, _ = run(['loginctl', 'show-user', user, '--property=Linger', '--value'])
    if code == 0 and out.strip() == 'yes':
        return Fact('linger', 'Nach Abmeldung', OK, 'läuft weiter', [('Linger', 'ja')])
    return Fact('linger', 'Nach Abmeldung', WARN, 'stoppt', [('Linger', 'nein')],
                hint='Benutzerdienst endet beim Abmelden und startet nach dem Booten nicht.',
                command=shlex.join(['sudo', 'loginctl', 'enable-linger', user]))


def local_addresses(run=run_command) -> list[tuple[str, str]]:
    import json

    code, out, _ = run(['ip', '-j', 'addr', 'show'])
    if code != 0:
        return []
    found = []
    try:
        for link in json.loads(out or '[]'):
            for info in link.get('addr_info', []):
                if info.get('local'):
                    found.append((str(info['local']), str(link.get('ifname', ''))))
    except (ValueError, AttributeError):
        return []
    return found


def fact_network(instance: Instance, run=run_command) -> Fact:
    host = instance.host
    if not host:
        return Fact('netzwerk', 'Netzwerk', UNKNOWN, 'Adresse fehlt')
    addresses = local_addresses(run)
    detail = [('Werkbank-Adresse', host)] + [(name or '?', address) for address, name in addresses
                                             if name != 'lo']
    if not addresses:
        return Fact('netzwerk', 'Netzwerk', UNKNOWN, 'unbekannt', detail)
    names = {socket.gethostname(), socket.gethostname() + '.local'}
    if host in {address for address, _ in addresses} or host in names:
        interface = next((name for address, name in addresses if address == host), 'Name')
        return Fact('netzwerk', 'Netzwerk', OK, interface, detail)
    return Fact('netzwerk', 'Netzwerk', FAIL, 'Adresse fehlt', detail,
                hint=(f'{host} liegt auf keiner Schnittstelle dieses Pi (neue DHCP-Adresse? anderes Netz?). '
                      'Browser und Brücke erreichen die Werkbank so nicht. Feste Adresse einrichten '
                      'oder neu installieren.'))


def fact_clock(run=run_command) -> Fact:
    code, out, _ = run(['timedatectl', 'show', '-p', 'NTPSynchronized', '--value'])
    if code != 0:
        return Fact('uhr', 'Uhrzeit', UNKNOWN, 'unbekannt')
    if out.strip() == 'yes':
        return Fact('uhr', 'Uhrzeit', OK, 'synchron', [('NTP', 'synchronisiert')])
    return Fact('uhr', 'Uhrzeit', WARN, 'nicht synchron', [('NTP', 'nicht synchronisiert')],
                hint='Zeitstempel der Läufe könnten falsch sein. Netzwerk/NTP prüfen.')


# --------------------------------------------------------------------- Sammeln

#: Reihenfolge der Übersicht: zuerst Betrieb, dann Einrichtung.
OVERVIEW = ('dienst', 'lauf', 'kamera', 'ausgabe', 'bruecke', 'zertifikat', 'speicher')
SETUP = ('netzwerk', 'vorlage', 'kalibrierung', 'uart', 'konto', 'linger', 'uhr', 'version')


def collect(instance: Instance, run=run_command, live_source=None, bridge_source=None,
            include_setup: bool = True) -> Snapshot:
    """Alle Fakten lesen. ``*_source`` ersetzen die Socketabfrage in Tests."""
    service = fact_service(instance, run)
    up = service.level in (OK, WARN)
    live = (live_source() if live_source else socket_request(instance.socket, 'live.status')) if up else None
    bridge = None
    if up and instance.bridge_directory:
        bridge = bridge_source() if bridge_source else socket_request(instance.socket, 'bridge.status')
    facts = {'dienst': service}
    facts['lauf'] = fact_run(live, service)
    facts['kamera'] = fact_camera(live, service)
    facts['ausgabe'] = fact_output(live, bridge, service)
    facts['bruecke'] = fact_bridge(instance, bridge, service)
    facts['zertifikat'], _ = fact_https(instance, service)
    facts['speicher'] = fact_storage(instance, live)
    if include_setup:
        facts['netzwerk'] = fact_network(instance, run)
        facts['vorlage'] = fact_templates(instance)
        facts['kalibrierung'] = fact_calibration(instance, camera_id=_live_camera_id(live))
        facts['uart'] = fact_uart(output_port=instance.output_port)
        facts['konto'] = fact_groups(instance)
        linger = fact_linger(instance, run)
        if linger is not None:
            facts['linger'] = linger
        facts['uhr'] = fact_clock(run)
        facts['version'] = fact_version(instance, run)
    return Snapshot(instance, facts, live, time.time())


# ------------------------------------------------------------------ Systemwerte
# Lokal und billig gelesen; unbekannt bleibt None (Anzeige „–“), nichts wird geschätzt.

_CPU_LAST: tuple[int, int] | None = None


def _cpu_times(proc: Path) -> tuple[int, int] | None:
    try:
        fields = (proc / 'stat').read_text().splitlines()[0].split()[1:]
        values = [int(v) for v in fields]
    except (OSError, ValueError, IndexError):
        return None
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return sum(values), idle


def system_metrics(proc: Path = Path('/proc'), sys_root: Path = Path('/sys')) -> dict:
    """CPU-Last seit dem letzten Aufruf (%), RAM belegt (%/Bytes), SoC-Temperatur (°C)."""
    global _CPU_LAST
    result: dict = {'cpu_percent': None, 'ram_percent': None, 'ram_used': None, 'ram_total': None,
                    'temperature_c': None, 'load1': None}
    times = _cpu_times(proc)
    if times is not None and _CPU_LAST is not None:
        total, idle = times[0] - _CPU_LAST[0], times[1] - _CPU_LAST[1]
        if total > 0:
            result['cpu_percent'] = round(100.0 * (total - idle) / total, 1)
    _CPU_LAST = times
    try:
        info = {}
        for line in (proc / 'meminfo').read_text().splitlines():
            key, _, rest = line.partition(':')
            info[key] = int(rest.split()[0]) * 1024
        total, available = info['MemTotal'], info.get('MemAvailable', info.get('MemFree', 0))
        result.update(ram_total=total, ram_used=total - available,
                      ram_percent=round(100.0 * (total - available) / total, 1) if total else None)
    except (OSError, ValueError, KeyError, IndexError):
        pass
    try:
        result['temperature_c'] = round(int((sys_root / 'class/thermal/thermal_zone0/temp').read_text()) / 1000, 1)
    except (OSError, ValueError):
        pass
    try:
        result['load1'] = float((proc / 'loadavg').read_text().split()[0])
    except (OSError, ValueError, IndexError):
        pass
    return result


def _du(path: Path, run=run_command, timeout: float = 20.0) -> int | None:
    if not path.exists():
        return None
    code, out, _ = run(['du', '-sb', '--one-file-system', str(path)], timeout=timeout)
    if code not in (0, 1) or not out.strip():  # 1: einzelne Dateien nicht lesbar, Summe trotzdem da
        return None
    try:
        return int(out.split()[0])
    except ValueError:
        return None


def storage_usage(instance: Instance, run=run_command) -> dict:
    """Belegung des Datenträgers und Größe der picam-Orte (langsam: im Hintergrund aufrufen).

    ``groups`` ist eine Liste (Name, Pfad, Bytes|None); „Läufe“ ohne die
    Diagnoseordner, die einzeln gezählt werden. Der Rest des Datenträgers
    erscheint als „Sonstiges“.
    """
    target = Path(instance.live_data or instance.data or '/')
    probe = target
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        disk = shutil.disk_usage(probe)
    except OSError:
        return {'total': None, 'used': None, 'free': None, 'groups': [], 'mount': str(probe)}
    groups: list[tuple[str, str, int | None]] = []
    live = Path(instance.live_data) if instance.live_data else None
    if live is not None:
        size = _du(live, run)
        diagnose = 0
        if live.is_dir():
            for folder in live.glob('live-*/run-*/diagnose'):
                diagnose += _du(folder, run) or 0
        groups.append(('Läufe', str(live), None if size is None else max(0, size - diagnose)))
        groups.append(('Diagnose', str(live / '*/run-*/diagnose'), diagnose))
    if instance.data:
        data = Path(instance.data)
        size = _du(data, run)
        bridge = _du(Path(instance.bridge_directory), run) if instance.bridge_directory else None
        inside = bridge if instance.bridge_directory and str(instance.bridge_directory).startswith(str(data)) else 0
        groups.append(('Werkbank-Daten', str(data), None if size is None else max(0, size - (inside or 0))))
        if instance.bridge_directory:
            groups.append(('Brücke', str(instance.bridge_directory), bridge))
    if instance.root and Path(instance.root).parent.name == 'releases':
        releases = Path(instance.root).parent
        groups.append(('Programmversionen', str(releases), _du(releases, run)))
    known = sum(size or 0 for _, _, size in groups)
    groups.append(('Sonstiges', 'übriger Datenträger', max(0, disk.used - known)))
    return {'total': disk.total, 'used': disk.used, 'free': disk.free, 'groups': groups, 'mount': str(probe)}


def network_info(run=run_command) -> dict:
    """Hostname, Schnittstellen mit Adressen und Zustand, Tailscale falls installiert."""
    import json

    info: dict = {'hostname': socket.gethostname(), 'interfaces': [], 'tailscale': None}
    code, out, _ = run(['ip', '-j', 'addr', 'show'])
    if code == 0:
        try:
            for link in json.loads(out or '[]'):
                name = str(link.get('ifname', ''))
                if name == 'lo':
                    continue
                addresses = [f"{a.get('local')}/{a.get('prefixlen')}" for a in link.get('addr_info', [])
                             if a.get('local')]
                info['interfaces'].append({'name': name, 'state': str(link.get('operstate', '?')).lower(),
                                           'mac': link.get('address'), 'addresses': addresses})
        except (ValueError, AttributeError):
            pass
    if shutil.which('tailscale'):
        code, out, err = run(['tailscale', 'status', '--json'], timeout=4.0)
        if code == 0:
            try:
                data = json.loads(out or '{}')
                own = data.get('Self') or {}
                info['tailscale'] = {'state': data.get('BackendState'), 'name': own.get('DNSName', '').rstrip('.'),
                                     'addresses': list(own.get('TailscaleIPs') or [])}
            except ValueError:
                info['tailscale'] = {'state': 'unbekannt', 'name': '', 'addresses': []}
        else:
            info['tailscale'] = {'state': (err or 'nicht erreichbar').strip()[:80], 'name': '', 'addresses': []}
    return info
