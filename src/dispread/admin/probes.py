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

from .instance import Instance

OK, WARN, FAIL, OFF, UNKNOWN = 'ok', 'warn', 'fail', 'off', 'unknown'
LEVEL_ORDER = {FAIL: 0, WARN: 1, UNKNOWN: 2, OFF: 3, OK: 4}
#: Sichere Zustände für Dienststopp, wie scripts/werkbank-dienst.sh.
STOP_SAFE_STATES = frozenset({'idle', 'setup_ready', 'setup_failed', 'confirmed', 'stopped'})
CAMERA_USB_ID = '046d:0893'
UART_DEVICE = Path('/dev/ttyAMA0')
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
        return asyncio.run(ask())
    except (TimeoutError, OSError, ValueError, ImportError, RuntimeError):
        return None
    except Exception:  # aiohttp.ClientError u. a.: Quelle gilt als nicht erreichbar
        return None


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
            'bridge_uart': 'UART über Brücke', 'network': 'Netzwerk'}.get(transport, str(transport))


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
    pairing = identity.parent / 'pairing'
    try:
        pairs = len([p for p in pairing.iterdir() if p.suffix == '.json'])
    except OSError:
        pairs = 0
    detail.append(('Kopplungen', str(pairs)))
    if bridge is None:
        level = OFF if service.level in (OFF, FAIL) else UNKNOWN
        return Fact('bruecke', 'Brücke', level, '–' if level == OFF else 'unbekannt', detail)
    if bridge.get('pi_id'):
        detail.insert(0, ('Pi-ID', str(bridge['pi_id'])[:8] + '…'))
    detail.append(('UART-Empfang', {'unprepared': 'nicht vorbereitet', 'prepared': 'vorbereitet',
                                    'ready': 'bereit'}.get(bridge.get('uart_state'), str(bridge.get('uart_state')))))
    if bridge.get('connected'):
        return Fact('bruecke', 'Brücke', OK, 'verbunden', detail)
    if pairs == 0:
        return Fact('bruecke', 'Brücke', WARN, 'nicht gekoppelt', detail,
                    hint='Noch keine Windows-Brücke gekoppelt. In der Werkbank beim Laufstart '
                         '„Brücke einrichten…“ wählen: Profil laden, Code in die Windows-App eingeben.')
    return Fact('bruecke', 'Brücke', OK, 'wartet', detail)


def fact_storage(instance: Instance, live: dict | None) -> Fact:
    storage = (live or {}).get('storage')
    target = instance.live_data or instance.data
    if isinstance(storage, dict) and storage.get('free_bytes') is not None:
        free, reserve = storage['free_bytes'], storage.get('reserve_bytes') or 0
    elif target:
        from dispread.live.service import STORAGE_RESERVE_BYTES

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
    from dispread.live import DEFAULT_TEMPLATES_SHA256

    if not instance.templates:
        return Fact('vorlage', 'Lesevorlage', UNKNOWN, 'unbekannt')
    path = Path(instance.templates)
    if not path.is_file():
        return Fact('vorlage', 'Lesevorlage', FAIL, 'fehlt', [('Datei', str(path))],
                    hint='Die eingefrorene Vorlage gehört zum Release; neu installieren.')
    if _sha256(path) != DEFAULT_TEMPLATES_SHA256:
        return Fact('vorlage', 'Lesevorlage', FAIL, 'verändert', [('Datei', str(path))],
                    hint='Prüfsumme stimmt nicht. Vorlage aus dem Release wiederherstellen.')
    return Fact('vorlage', 'Lesevorlage', OK, 'geprüft', [('Datei', str(path)), ('SHA-256', 'stimmt')])


def fact_calibration(instance: Instance, now=time.time) -> Fact:
    if not instance.calibration:
        return Fact('kalibrierung', 'Kalibrierung', UNKNOWN, 'unbekannt')
    path = Path(instance.calibration)
    if not path.is_file():
        tool = Path(instance.root or '.') / 'scripts' / 'timing-calibration.py'
        return Fact('kalibrierung', 'Kalibrierung', FAIL, 'fehlt', [('Datei', str(path))],
                    hint=('Ohne Timing-Kalibrierung startet kein Messlauf. Am Aufbau messen '
                          '(scripts/timing-calibration.py im Entwicklungs-Checkout) und die Datei hier ablegen.'),
                    command=shlex.join([sys.executable, str(tool)]) if tool.is_file() else None)
    age_days = int((now() - path.stat().st_mtime) // 86400)
    return Fact('kalibrierung', 'Kalibrierung', OK, 'vorhanden',
                [('Datei', str(path)), ('Stand', datetime.fromtimestamp(path.stat().st_mtime)
                                        .strftime('%d.%m.%Y')), ('Alter', f'{age_days} Tage')])


def _boot_text(paths) -> tuple[Path | None, str]:
    for path in paths:
        try:
            return path, path.read_text()
        except OSError:
            continue
    return None, ''


def fact_uart(device: Path = UART_DEVICE, configs=BOOT_CONFIGS, cmdlines=BOOT_CMDLINES) -> Fact:
    config_path, config = _boot_text(configs)
    _, cmdline = _boot_text(cmdlines)
    enabled = any(line.split('#', 1)[0].strip().replace(' ', '') in ('dtparam=uart0=on', 'dtparam=uart0')
                  for line in config.splitlines())
    console = 'console=ttyAMA0' in cmdline or 'console=serial0' in cmdline.replace('ttyAMA10', '')
    detail = [('Gerät', f"{device} {'vorhanden' if device.exists() else 'fehlt'}"),
              ('Bootdatei', f"dtparam=uart0=on {'gesetzt' if enabled else 'fehlt'}"
               + (f' ({config_path})' if config_path else ''))]
    if console:
        detail.append(('Konsole', 'serielle Konsole auf dem Datenport'))
    if not device.exists() or not enabled:
        return Fact('uart', 'UART', WARN, 'nicht aktiv', detail,
                    hint='Nur für UART-Ausgabe nötig. dtparam=uart0=on in config.txt ergänzen, dann neu booten.',
                    command="echo 'dtparam=uart0=on' | sudo tee -a /boot/firmware/config.txt")
    if console:
        return Fact('uart', 'UART', WARN, 'Konsole belegt', detail,
                    hint='Serielle Konsole abschalten (raspi-config → Interface → Serial: Login-Shell nein).')
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
                        hint='Update: picam update --source picam-<version>.tar.gz · Rückweg: picam update --rollback')
        except (OSError, ValueError):
            pass
    if root is not None and (root / '.git').exists():
        code, out, _ = run(['git', '-C', str(root), 'describe', '--tags', '--always', '--dirty'])
        if code == 0 and out.strip():
            text = out.strip()
            detail = [('Stand', text), ('Ort', str(root))]
            return Fact('version', 'Version', OK, text.split('-g')[0] if '-g' in text else text, detail)
    from importlib import metadata

    try:
        return Fact('version', 'Version', OK, metadata.version('dispread'))
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
SETUP = ('vorlage', 'kalibrierung', 'uart', 'konto', 'linger', 'uhr', 'version')


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
        facts['vorlage'] = fact_templates(instance)
        facts['kalibrierung'] = fact_calibration(instance)
        facts['uart'] = fact_uart()
        facts['konto'] = fact_groups(instance)
        linger = fact_linger(instance, run)
        if linger is not None:
            facts['linger'] = linger
        facts['uhr'] = fact_clock(run)
        facts['version'] = fact_version(instance, run)
    return Snapshot(instance, facts, live, time.time())
