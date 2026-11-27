"""Werkzeuge zur lokalen Einrichtung. Keine Schreibbefehle an Sensoren."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import math
import re
import shlex
import shutil
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from . import bundled_sensors, get_sensor, load_definition, local_root, registry_with_errors, templates
from .definitions import CHAR_NUMBER_FORMAT_RULE
from .formats import derive_display, required_characters
from .onboarding import OnboardingCancelled, RunDir

DEFAULT_BAUDS = '9600,19200,38400,57600,115200'
DEFAULT_TIMEOUT = 1800
_MAX_SNIFF_BYTES = 65536


def check_cancel(run: RunDir | None) -> None:
    if run is not None and run.cancelled():
        raise OnboardingCancelled('Onboarding abgebrochen')


def request_data(run: RunDir) -> dict:
    data = run.request()
    if not isinstance(data, dict) or type(data.get('v')) is not int or data['v'] != 1:
        raise ValueError('request.json braucht Version 1')
    for key in ('name', 'manufacturer', 'unit'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f'Angabe fehlt: {key}')
    if data.get('display_family') != 'hd44780_5x8':
        raise ValueError('P0 erwartet die Anzeigefamilie hd44780_5x8')
    connection = data.get('connection')
    if (not isinstance(connection, dict) or connection.get('kind') not in {'rs232', 'usb', 'none'}
            or (connection.get('port') is not None and not isinstance(connection['port'], str))):
        raise ValueError('Anschlussangaben ungueltig')
    return data


def ports() -> list[dict]:
    from serial.tools import list_ports

    return [{'port': item.device, 'description': item.description}
            for item in sorted(list_ports.comports(include_links=True))]



def _check_serial_ownership(port: str, instance) -> None:
    from dispread.admin.probes import socket_request
    from dispread.hardware_ports import same_port, uart_devices
    from dispread.workbench.cli import default_socket

    output = instance.output_port
    if not output.startswith('/'):
        output = uart_devices().get(output)
    if output and same_port(port, output):
        raise ValueError('Dieser Port ist als Werkbank-Ausgang reserviert')
    if same_port(port, instance.reference_port):
        path = instance.socket or default_socket()
        if Path(path).exists():
            status = socket_request(path, 'live.status')
            if status is None or status.get('state') in {'setup_running', 'running'}:
                raise ValueError('Werkbank verwendet möglicherweise den Referenzport. '
                                 'Einrichtung oder Lauf beenden und erneut versuchen.')

def sniff(port: str, bauds: str = DEFAULT_BAUDS, seconds: float = 3.0, *, run: RunDir | None = None, instance=None) -> list[dict]:
    import serial

    from dispread.gsv2as_cell_text import cell_text_from_telegram

    try:
        rates = list(dict.fromkeys(int(item) for item in bauds.split(',')))
    except ValueError as error:
        raise ValueError('Baudraten als kommagetrennte Ganzzahlen angeben') from error
    if not rates or len(rates) > 10 or any(not 1 <= rate <= 4_000_000 for rate in rates):
        raise ValueError('Erwartet 1 bis 10 gueltige Baudraten')
    if not math.isfinite(seconds) or not 0 < seconds <= 30:
        raise ValueError('Empfangsdauer muss groesser 0 und hoechstens 30 Sekunden sein')
    if instance is not None:
        _check_serial_ownership(port, instance)
    results = []
    for rate in rates:
        check_cancel(run)
        data = bytearray()
        with serial.Serial(port=None, baudrate=rate, timeout=min(seconds, 0.2), exclusive=True) as connection:
            # Bereits vor dem Oeffnen keine Leitungsaktivierung anfordern.
            connection.dtr = False
            connection.rts = False
            connection.port = port
            connection.open()
            end = time.monotonic() + seconds
            while time.monotonic() < end and len(data) < _MAX_SNIFF_BYTES:
                check_cancel(run)
                data.extend(connection.read(min(256, _MAX_SNIFF_BYTES - len(data))))
        lines = re.findall(rb'([^\r\n]*)[\r\n]+', data)
        matches = 0
        for line in lines:
            try:
                cell_text_from_telegram(line)
            except ValueError:
                continue
            matches += 1
        printable = sum(32 <= byte < 127 or byte in (9, 10, 13) for byte in data)
        results.append({'baud': rate, 'bytes': len(data), 'printable_fraction': printable / len(data) if data else 0,
                        'sample_lines': [line[:160].decode('ascii', 'replace') for line in lines[:5]],
                        'matches': {'gsv2as-161a': matches} if matches else {}})
    return results


def capture(run: RunDir, instance, source: str | None = None, *, confirmed: bool = False) -> dict:
    import cv2
    import numpy as np

    from dispread.admin.probes import socket_request
    from dispread.camera_settings import preview_settings
    from dispread.frames import open_source
    from dispread.workbench.cli import default_socket

    check_cancel(run)
    socket = instance.socket or default_socket()
    run.work_dir.mkdir(exist_ok=True)
    target = run.work_dir / 'capture.png'
    if confirmed:
        if source is not None:
            raise ValueError('Bestaetigtes Referenzbild kommt aus der Werkbank, bitte ohne --source aufrufen')
        snapshot = socket_request(socket, 'live.snapshot', args={'confirmed': True})
        if snapshot is None:
            raise ValueError('Kein bestätigtes Referenzbild erreichbar. Zuerst die Einrichtung in /live bestätigen.')
        image_bytes = base64.b64decode(snapshot['image'], validate=True)
        if hashlib.sha256(image_bytes).hexdigest() != snapshot['profile']['reference_frame']['sha256']:
            raise ValueError('Werkbank-Referenzbild passt nicht zum bestätigten Profil')
        check_cancel(run)
        target.write_bytes(image_bytes)
        _write_json(run.work_dir / 'profile.json', snapshot['profile'])
        _write_json(run.work_dir / 'capture.json', {'origin': 'werkbank_bestaetigt'})
        return {'path': str(target.resolve()), 'source': 'werkbank_bestaetigt'}

    image = None
    origin = 'quelle'
    if (source is None or source.startswith('v4l2://')) and Path(socket).exists():
        snapshot = socket_request(socket, 'live.snapshot')
        if snapshot is None:
            raise ValueError('Werkbank-Steuerung liefert kein Standbild. Dienst und Kamera in /live pruefen.')
        if snapshot.get('jpeg') is not None:
            image = cv2.imdecode(np.frombuffer(base64.b64decode(snapshot['jpeg'], validate=True), np.uint8),
                                 cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError('Standbild der Werkbank ist nicht lesbar')
            origin = 'werkbank'
        elif snapshot.get('camera_running') is not False:
            raise ValueError('Werkbank haelt die Kamera, liefert aber kein Bild. Vorschau in /live pruefen.')
    if image is None:
        if source is None:
            # Wie die Werkbank-Vorschau: nur Format, keine erfundenen Reglerwerte.
            from dispread.frames.uvc_source import UvcSource
            camera = UvcSource(preview_settings(), apply_controls=False)
        else:
            camera = open_source(source)
        try:
            camera.open()
            image = next(camera.frames()).image
        except StopIteration as error:
            raise ValueError('Bildquelle liefert kein Standbild') from error
        finally:
            camera.close()
    check_cancel(run)
    if not cv2.imwrite(str(target), image):
        raise OSError(f'Standbild konnte nicht gespeichert werden: {target}')
    _write_json(run.work_dir / 'capture.json', {'origin': origin})
    return {'path': str(target.resolve()), 'source': origin}


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _template_source(display):
    needed = required_characters(display)
    missing = needed
    for sensor in bundled_sensors():
        if sensor.display.family != display.family:
            continue
        absent = needed - templates(sensor).mean.keys()
        if not absent:
            return sensor
        if len(absent) < len(missing):
            missing = absent
    chars = ', '.join(repr(ch) for ch in sorted(missing))
    raise ValueError(f'Zeichen {chars} fehlen – Ernte/Training nötig (folgt)')


def propose(run: RunDir, instance, sensor_id: str, *, example=None, unit=None, sign_chars=None, digits=None,
            display_name=None, serial_port=None, serial_baud=None) -> dict:
    check_cancel(run)
    run.step('paket', 'running')
    try:
        data = request_data(run)
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,62}', sensor_id):
            raise ValueError(f'Ungueltige Sensor-id {sensor_id!r}')
        unit = data['unit'] if unit is None else unit
        example = data.get('example') if example is None else example
        display = derive_display(example, unit, sign_chars, digits)
        source = _template_source(display)
        if display.anchor is None:
            raise ValueError('Die Live-Rastersuche braucht in P0 ein festes + in Zelle 0. '
                             'Fuer diese Anzeige fehlt ein gepruefter Rasterstart.')
        if (serial_port is None) != (serial_baud is None) or (serial_baud is not None and serial_baud <= 0):
            raise ValueError('Serieller Befund braucht Port und positive Baudrate')
        root = local_root(instance)
        target = root / sensor_id
        existing, _ = registry_with_errors(instance=instance)
        if target.exists() or target.is_symlink() or any(
            sensor_id in (item.id, *item.aliases) for item in existing.values()
        ):
            raise ValueError(f'Sensor-id bereits vergeben: {sensor_id}')
        root.mkdir(parents=True, exist_ok=True)
        with (root / '.pakete.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if target.exists() or target.is_symlink():
                raise ValueError(f'Sensor-id bereits vergeben: {sensor_id}')
            with tempfile.TemporaryDirectory(dir=root, prefix='.paket-') as tmp:
                staged = Path(tmp) / sensor_id
                staged.mkdir(mode=0o755)
                _write_json(staged / 'sensor.json', {
                    'schema': 1, 'version': 1, 'id': sensor_id, 'device_id': sensor_id, 'status': 'provisional',
                    'display_name': data['name'] if display_name is None else display_name,
                    'manufacturer': data['manufacturer'], 'aliases': [],
                    'unit': unit, 'connection': data['connection']['kind'],
                    'templates': {'file': 'templates.json', 'sha256': source.templates.sha256},
                    'release_notice': 'Anzeigefamilie HD44780 5×8. Einheit durch Bediener zu bestätigen.',
                })
                _write_json(staged / 'display.json', asdict(display))
                shutil.copyfile(source.templates_path, staged / 'templates.json')
                sensor = load_definition(staged)
                templates(sensor)
                check_cancel(run)
                staged.rename(target)
        result = {'sensor_id': sensor_id, 'directory': str(target), 'status': sensor.status}
        run.log(f'Sensorpaket {sensor_id} erzeugt: {target}')
        run.step('paket', 'done', sensor_id)
        _write_json(run.work_dir / 'proposal.json', {
            **result, 'example': example, 'unit': unit, 'serial_port': serial_port, 'serial_baud': serial_baud,
        })
        return result
    except (ValueError, OSError, OnboardingCancelled) as error:
        run.step('paket', 'failed', str(error))
        raise


def _confirmed_profile(run: RunDir, instance, sensor):
    from dispread.session_profile import SessionProfile

    # Ein bereits bestaetigtes Quad gilt nur fuer dieselbe Aufnahme und dasselbe Geraet.
    capture = run.work_dir / 'capture.png'
    if not capture.is_file():
        return None
    paths = [run.work_dir / 'profile.json']
    if instance.live_data and Path(instance.live_data).is_dir():
        paths.extend(sorted(Path(instance.live_data).glob('live-*/profile.json'), reverse=True))
    digest = hashlib.sha256(capture.read_bytes()).hexdigest()
    for path in paths:
        if not path.is_file():
            continue
        try:
            profile = SessionProfile.load(path)
        except (OSError, ValueError, TypeError, KeyError):
            if path == paths[0]:
                raise
            continue
        if (profile.device_id == sensor.device_id and profile.confirmed_by and profile.resolution_ok
                and tuple(profile.target_size) == sensor.display.lattice.target_size
                and (profile.reference_frame or {}).get('sha256') == digest):
            return profile
    return None


def check(instance, sensor_id: str, run: RunDir | None = None) -> dict:
    check_cancel(run)
    if run is not None:
        run.step('pruefung', 'running')
    try:
        sensor = get_sensor(sensor_id, instance=instance)
        loaded = templates(sensor)
        if sensor.display.format.rule == CHAR_NUMBER_FORMAT_RULE:
            if missing := required_characters(sensor.display) - loaded.mean.keys():
                raise ValueError(f'Zeichen {sorted(missing)} fehlen – Ernte/Training nötig (folgt)')
            if sensor.display.anchor is None:
                raise ValueError('P0 braucht ein festes + in Zelle 0 fuer die Live-Rastersuche')
            if len(sensor.unit) != len(sensor.display.roles.unit):
                raise ValueError('Einheit passt nicht in die deklarierten Einheitszellen')
            if sensor.display.lattice != get_sensor().display.lattice:
                raise ValueError('P0 braucht das mitgelieferte Raster der HD44780-5x8-Familie')
        result = {'sensor_id': sensor.id, 'status': sensor.status, 'mode': 'static', 'ok': True}
        profile = _confirmed_profile(run, instance, sensor) if run is not None else None
        if profile is not None:
            import cv2

            from dispread.layout import CharLayout
            from dispread.ocr.dotmatrix import DotMatrixReader
            from dispread.rectify import rectify

            frame = cv2.imread(str(run.work_dir / 'capture.png'))
            if frame is None:
                raise ValueError('Standbild der Laufmappe ist nicht lesbar')
            crop = rectify(frame, profile.quad, target_size=sensor.display.lattice.target_size).image
            read = DotMatrixReader(loaded).read(crop, CharLayout.from_profile(profile, definition=sensor))
            result.update(mode='reading', ok=read.value is not None, value=read.value, raw_text=read.raw_text,
                          reason=read.diagnostics.get('reject_reason'))
        if run is not None:
            detail = ('Paket und Vorlagen geprüft. Kein zur Aufnahme passendes bestätigtes Quad.'
                      if profile is None else 'Standbild gelesen' if result['ok'] else str(result['reason']))
            run.step('pruefung', 'done' if result['ok'] else 'failed', detail)
        return result
    except (ValueError, OSError, RuntimeError) as error:
        if run is not None:
            run.step('pruefung', 'failed', str(error))
        raise


def activate(instance, sensor_id: str, accept_provisional: bool) -> dict:
    from dispread.admin import configedit
    from dispread.workbench.config import dev_sensor_config

    sensor = get_sensor(sensor_id, instance=instance)
    if sensor.status == 'draft':
        raise ValueError('Entwurf kann nicht als aktiver Sensor gesetzt werden')
    if sensor.status == 'provisional' and not accept_provisional:
        raise ValueError('Vorlaeufiges Paket: Aktivierung braucht --accept-provisional')
    check(instance, sensor_id)
    dev = instance.config is None and instance.kind == 'dev'
    if instance.config is None and not dev:
        raise ValueError('Keine Instanzkonfiguration gefunden. --config PFAD angeben.')
    path = dev_sensor_config(instance.data) if dev else Path(instance.config)
    try:
        if dev:
            path.parent.mkdir(parents=True, exist_ok=True)
        updated = configedit.propose_sensor(path, sensor.id, dev_data=instance.data if dev else None)
        configedit.apply(path, updated, create=dev)
    except PermissionError as error:
        command = f'picam --config {shlex.quote(str(path))} sensor activate --id {shlex.quote(sensor.id)}'
        if sensor.status == 'provisional':
            command += ' --accept-provisional'
        raise PermissionError(f'{path} ist nicht schreibbar. Ohne sudo eine schreibbare Benutzerinstanz '
                              f'mit --config wählen. Für diese Systeminstanz nutzt Einstellungen sudo; '
                              f'im Terminal: sudo {command}') from error
    restart = ('Neustart mit „picam restart“ erforderlich.' if instance.unit else
               'Neustart der Werkbank mit derselben Konfiguration erforderlich.')
    return {'sensor_id': sensor.id, 'status': sensor.status, 'config': str(path),
            'restart_required': True, 'message': f'Sensor {sensor.id} gespeichert. {restart}'}
