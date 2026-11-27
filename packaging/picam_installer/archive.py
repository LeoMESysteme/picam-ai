"""Bounded archive inspection before any destination is created."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

MAX_BYTES = 128 * 1024 * 1024
SENSOR_DIR = 'src/dispread/data/sensors/gsv2as-161a'
SENSOR = f'{SENSOR_DIR}/sensor.json'
DISPLAY = f'{SENSOR_DIR}/display.json'
TEMPLATE = f'{SENSOR_DIR}/templates.json'
LEGACY_TEMPLATE = 'src/dispread/data/templates-stufe2c-2026-09-30.json'
TEMPLATE_SHA256 = '6f20dec4f558e98be41203d0ab48eb4788d16e02c1350313a740c25cc03f693a'
REQUIRED = {'pyproject.toml', 'VERSION', 'packaging/apt-packages.txt', 'scripts/install.py',
            'install.sh', 'packaging/picam_installer/__main__.py', 'src/dispread/__init__.py', SENSOR, DISPLAY, TEMPLATE}


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Doppelter JSON-Schluessel')
        result[key] = value
    return result


def check_template(sensor_data, template_data):
    """Prueft den Paketverweis und die unabhaengig festgelegte Stufe-2c-Pruefsumme."""
    try:
        reference = json.loads(sensor_data, object_pairs_hook=unique_json)['templates']
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Vorlagenverweis in sensor.json fehlt oder ist ungueltig') from error
    if reference != {'file': 'templates.json', 'sha256': TEMPLATE_SHA256}:
        raise ValueError('Vorlagenverweis in sensor.json passt nicht zur freigegebenen Vorlage')
    if hashlib.sha256(template_data).hexdigest() != TEMPLATE_SHA256:
        raise ValueError('Vorlagen-Hash stimmt nicht mit der freigegebenen Vorlage ueberein')


@dataclass(frozen=True)
class Bundle:
    release_id: str
    manifest: dict
    files: dict
    sha256: str


def valid_relative(name):
    return (isinstance(name, str) and name and not name.startswith('/') and '\\' not in name
            and all(p not in ('', '.', '..') for p in name.split('/'))
            and str(PurePosixPath(name)) == name)


def read_bundle(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('Releasearchiv ist zu gross')
    files, seen, total = {}, set(), 0
    try:
        # Bound the complete tar stream, including PAX/GNU headers consumed by
        # tarfile internally before it yields a member. Only tar and gzip tar.
        if raw.startswith(b'\x1f\x8b'):
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
                expanded = compressed.read(MAX_BYTES + 1)
        else:
            expanded = raw
        if len(expanded) > MAX_BYTES:
            raise ValueError('Entpacktes Archiv einschliesslich Metadaten ist zu gross')
        with tarfile.open(fileobj=io.BytesIO(expanded), mode='r:') as archive:
            for member in archive:
                name = member.name.rstrip('/') if member.isdir() else member.name
                if not valid_relative(name) or name.split('/')[0] != 'picam' or name in seen:
                    raise ValueError('Unsicherer oder doppelter Archivpfad')
                seen.add(name)
                if len(seen) > 10000:
                    raise ValueError('Zu viele Archiveintraege')
                if member.isdir():
                    continue
                if not member.isfile() or '/' not in name:
                    raise ValueError('Archiv darf nur Dateien und Verzeichnisse enthalten, keine Links')
                total += member.size
                if member.size < 0 or total > MAX_BYTES:
                    raise ValueError('Entpackte Lieferung ist zu gross')
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError('Archivdatei nicht lesbar')
                files[name[len('picam/'):]] = stream.read(member.size + 1)
    except (tarfile.TarError, EOFError, OSError) as error:
        raise ValueError(f'Ungueltiges Releasearchiv: {error}') from error
    try:
        manifest = json.loads(files.pop('release.json'), object_pairs_hook=unique_json)
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('release.json fehlt oder ist ungueltig') from error
    if not isinstance(manifest, dict) or type(manifest.get('schema')) is not int or manifest['schema'] != 1:
        raise ValueError('Unbekanntes Releaseformat')
    release_id = manifest.get('release_id')
    if not isinstance(release_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', release_id):
        raise ValueError('Ungueltige Release-ID')
    hashes = manifest.get('files')
    if not isinstance(hashes, dict) or set(hashes) != set(files) or not REQUIRED <= set(files):
        raise ValueError('Release-Inhalt unvollstaendig oder nicht im Manifest')
    for name, digest in hashes.items():
        if not valid_relative(name) or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Ungueltige Manifestdatei')
        if hashlib.sha256(files[name]).hexdigest() != digest:
            raise ValueError(f'Hash stimmt nicht: {name}')
    check_template(files[SENSOR], files[TEMPLATE])
    if LEGACY_TEMPLATE in files and files[LEGACY_TEMPLATE] != files[TEMPLATE]:
        raise ValueError('Vorlage fuer bestehende Installationen weicht vom Sensorpaket ab')
    # A file cannot also be another file's parent, even when its hash is valid.
    for name in files:
        if any(str(parent) in files for parent in PurePosixPath(name).parents if str(parent) != '.'):
            raise ValueError('Widerspruechliche Archivpfade')
    return Bundle(release_id, manifest, files, hashlib.sha256(raw).hexdigest())


class HttpsRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_url(value):
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Download braucht eine HTTPS-Adresse ohne Zugangsdaten oder Fragment')


def load_source(source, expected_sha256=None):
    if expected_sha256 is not None and not re.fullmatch('[0-9a-fA-F]{64}', expected_sha256):
        raise ValueError('--sha256 braucht genau 64 Hex-Zeichen')
    if '://' in source:
        check_url(source)
        if expected_sha256 is None:
            raise ValueError('HTTPS-Download braucht einen separat bezogenen --sha256')
        with urllib.request.build_opener(HttpsRedirects()).open(source, timeout=30) as response:
            raw = response.read(MAX_BYTES + 1)
    else:
        path = Path(source)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ValueError('Quelle muss ein regulaeres Releasearchiv sein (hoechstens 128 MiB)')
        with path.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Releasearchiv ist zu gross')
    if expected_sha256 and hashlib.sha256(raw).hexdigest() != expected_sha256.lower():
        raise ValueError('Archiv-Hash stimmt nicht')
    return read_bundle(raw)
