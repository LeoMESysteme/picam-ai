import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from dispread import release_source as source

FIXTURE = Path(__file__).parent / 'fixtures' / 'github-release.json'


@pytest.mark.parametrize(('candidate', 'installed', 'expected'), [
    ('1.10.0', '1.9.99', 1), ('1.0.0', '1.0.0', 0), ('1.0.0', '2.0.0', -1),
    ('0.0.1', 'rc-abcd123', 1), ('0.0.1', '0.1.0.dev0', 1), ('1.1.0', '0.1.0-installer1', 1),
])
def test_compare_versions(candidate, installed, expected):
    assert source.compare_versions(candidate, installed) == expected


@pytest.mark.parametrize('version', ['1.2', '1.2.3rc1', '01.2.3', '1.2.3+local'])
def test_unstable_candidate(version):
    with pytest.raises(ValueError, match='stabile'):
        source.compare_versions(version, '1.0.0')


def test_latest_endpoint(monkeypatch):
    def fetch(url, limit):
        assert url == f'{source.API_BASE}/repos/{source.REPOSITORY}/releases/latest'
        assert limit == 1024 * 1024
        return FIXTURE.read_bytes()

    monkeypatch.setattr(source, '_fetch', fetch)
    release = source.latest_release()
    assert release.version == '1.1.0'
    assert release.filename == 'picam-1.1.0.tar.gz'


@pytest.mark.parametrize('change', [
    {'draft': True}, {'prerelease': True}, {'tag_name': 'v1.1.0-rc.1'}, {'assets': []},
])
def test_rejects_unusable_latest_response(change):
    payload = json.loads(FIXTURE.read_bytes()) | change
    with pytest.raises(ValueError):
        source.parse_latest(json.dumps(payload).encode())


@pytest.mark.parametrize('kind', ['missing', 'wrong', 'malformed', 'good'])
def test_archive_checksum(tmp_path, monkeypatch, kind):
    release = source.parse_latest(FIXTURE.read_bytes())
    archive = b'example archive'
    expected = hashlib.sha256(archive).hexdigest()
    checksum = f'{expected if kind != "wrong" else "a" * 64}  {release.filename}\n'.encode()

    def fetch(url, limit):
        assert (url, limit) == (release.checksum_url, 512)
        if kind == 'missing':
            raise ValueError('HTTP 404')
        return checksum + (b'unexpected' if kind == 'malformed' else b'')

    def download(url, path, limit, timeout):
        assert kind in ('good', 'wrong')
        assert (url, limit, timeout) == (release.archive_url, source.MAX_ARCHIVE, 120)
        path.write_bytes(archive)

    monkeypatch.setattr(source, '_fetch', fetch)
    monkeypatch.setattr(source, '_download', download)
    if kind == 'good':
        path, digest = release.download(tmp_path)
        assert (path.read_bytes(), digest) == (archive, expected)
    else:
        with pytest.raises(ValueError, match={'missing': '404', 'wrong': 'Hash', 'malformed': 'SHA-256'}[kind]):
            release.download(tmp_path)


@pytest.mark.parametrize(('exit_code', 'status', 'message'), [
    (22, '403:0', 'Ratenlimit'), (22, '429:', 'Ratenlimit'), (6, '000:', 'fehlgeschlagen'),
    (63, '200:', 'Größenlimit'), (0, '200:', 'Größenlimit'),
])
def test_download_limits_and_errors(tmp_path, monkeypatch, exit_code, status, message):
    def run(command, *, capture_output, text, timeout):
        assert command[command.index('--proto-redir') + 1] == '=https'
        assert command[command.index('--proto') + 1] == '=https'
        assert command[command.index('--max-filesize') + 1] == '4'
        assert timeout == 16
        Path(command[command.index('--output') + 1]).write_bytes(b'12345')
        return SimpleNamespace(returncode=exit_code, stdout=status, stderr='curl error')

    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(ValueError, match=message):
        source._download('https://example.invalid/asset', tmp_path / 'asset', 4, 15)
    with pytest.raises(ValueError, match='HTTPS'):
        source._download('http://example.invalid/asset', tmp_path / 'asset', 4, 15)
