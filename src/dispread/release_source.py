"""The public stable release channel used by picam update and the publisher."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

# Keep the standalone bootstrap's configuration in sync when moving the mirror.
REPOSITORY = 'LeoMESysteme/picam-ai'
API_BASE = 'https://api.github.com'
ASSET_NAME = 'picam-{version}.tar.gz'
STABLE_VERSION = r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)'
MAX_ARCHIVE = 128 * 1024 * 1024


def stable_version(value: str) -> tuple[int, ...] | None:
    if len(value) <= 128 and re.fullmatch(STABLE_VERSION, value):
        return tuple(map(int, value.split('.')))
    return None


def compare_versions(candidate: str, installed: str) -> int:
    new = stable_version(candidate)
    if new is None:
        raise ValueError(f'Keine stabile Release-Version: {candidate}')
    old = stable_version(installed)
    if old is not None:
        return (new > old) - (new < old)
    # Legacy local builds had arbitrary IDs, including rc-<commit>.
    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', installed):
        return 1
    raise ValueError('Installierte Version ist unbekannt. Update mit --source angeben.')


def installed_version(root: Path) -> str:
    try:
        manifest = json.loads((root / 'release.json').read_text())
    except FileNotFoundError:
        return (root / 'VERSION').read_text().strip()
    if isinstance(manifest, dict) and isinstance(manifest.get('release_id'), str):
        return manifest['release_id']
    raise ValueError('Installierte Versionsangabe in release.json ist ungültig.')


def _check_https(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or (
        parsed.password is not None or '#' in url or any(ord(c) <= 32 for c in url)
    ):
        raise ValueError('Release-Downloads brauchen HTTPS-Adressen ohne Zugangsdaten oder Fragment.')
    return url


def _download(url: str, path: Path, limit: int, timeout: int) -> None:
    _check_https(url)
    command = [
        'curl', '-q', '-fsSL', '--proto', '=https', '--proto-redir', '=https', '--max-redirs', '4',
        '--globoff', '--connect-timeout', '5', '--max-time', str(timeout), '--max-filesize', str(limit),
        '--output', str(path), '--write-out', '%{http_code}:%header{x-ratelimit-remaining}', '--', url,
    ]
    try:
        response = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 1)
    except subprocess.TimeoutExpired as error:
        raise ValueError('Zeitlimit beim Release-Download überschritten.') from error
    except OSError as error:
        raise ValueError(f'Release-Download konnte curl nicht starten: {error}') from error
    if response.returncode:
        status, _, remaining = response.stdout.partition(':')
        if status == '429' or (status == '403' and remaining.strip() == '0'):
            raise ValueError('GitHub-Ratenlimit erreicht. Später erneut versuchen oder --source angeben.')
        if status == '404':
            raise ValueError('GitHub-Release oder Release-Datei nicht gefunden (HTTP 404).')
        if response.returncode == 63:
            raise ValueError(f'Release-Download überschreitet das Größenlimit ({limit} Bytes).')
        raise ValueError(f'Release-Download fehlgeschlagen: {response.stderr.strip() or "Netzfehler"}')
    if path.stat().st_size > limit:
        raise ValueError(f'Release-Download überschreitet das Größenlimit ({limit} Bytes).')


def _fetch(url: str, limit: int) -> bytes:
    with tempfile.TemporaryDirectory(prefix='picam-release-') as directory:
        path = Path(directory) / 'download'
        _download(url, path, limit, 15)
        return path.read_bytes()


@dataclass(frozen=True)
class LatestRelease:
    version: str
    archive_url: str
    checksum_url: str

    @property
    def filename(self):
        return ASSET_NAME.format(version=self.version)

    def download(self, directory: Path) -> tuple[Path, str]:
        expected = parse_checksum(_fetch(self.checksum_url, 512), self.filename)
        path = directory / self.filename
        _download(self.archive_url, path, MAX_ARCHIVE, 120)
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError('Archiv-Hash stimmt nicht.')
        return path, expected


def parse_checksum(raw: bytes, filename: str) -> str:
    match = re.fullmatch(rb'([a-fA-F0-9]{64}) [ *]' + re.escape(filename.encode('ascii')) + rb'\n?', raw)
    if match is None:
        raise ValueError(f'Ungültige SHA-256-Datei für {filename}.')
    return match[1].decode('ascii').lower()


def parse_latest(raw: bytes) -> LatestRelease:
    try:
        data = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Ungültige Antwort der GitHub-Release-API.') from error
    if not isinstance(data, dict) or data.get('draft') is not False or data.get('prerelease') is not False:
        raise ValueError('GitHub meldet keinen veröffentlichten stabilen Release.')
    tag = data.get('tag_name')
    if not isinstance(tag, str) or not tag.startswith('v') or stable_version(tag[1:]) is None:
        raise ValueError('GitHub-Release braucht einen Tag vX.Y.Z.')
    filename = ASSET_NAME.format(version=tag[1:])
    assets = data.get('assets')
    if not isinstance(assets, list):
        raise ValueError('Dateiliste fehlt in der GitHub-Release-Antwort.')

    def asset_url(name):
        urls = [asset.get('browser_download_url') for asset in assets
                if isinstance(asset, dict) and asset.get('name') == name]
        if len(urls) != 1 or not isinstance(urls[0], str):
            raise ValueError(f'Release-Datei fehlt oder ist nicht eindeutig: {name}')
        return _check_https(urls[0])

    return LatestRelease(tag[1:], asset_url(filename), asset_url(filename + '.sha256'))


def latest_release() -> LatestRelease:
    return parse_latest(_fetch(f'{API_BASE}/repos/{REPOSITORY}/releases/latest', 1024 * 1024))
