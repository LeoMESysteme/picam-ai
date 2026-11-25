import hashlib
import io
import json
import re
import shlex
import subprocess
import tarfile
from pathlib import Path

import pytest

from dispread import release_source

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / 'get-picam.sh'
FIXTURE = ROOT / 'tests/fixtures/github-release.json'
FILENAME = 'picam-1.1.0.tar.gz'


def test_bootstrap_syntax_and_source_configuration():
    subprocess.run(['bash', '-n', str(BOOTSTRAP)], check=True)
    text = BOOTSTRAP.read_text()
    for name, value in [('repository', release_source.REPOSITORY), ('api_base', release_source.API_BASE),
                        ('asset_pattern', release_source.ASSET_NAME)]:
        assert re.findall(rf"^{name}='([^']+)'$", text, re.MULTILINE) == [value]


def test_bootstrap_without_tty(tmp_path, monkeypatch):
    monkeypatch.setenv('PATH', str(tmp_path))
    process = subprocess.run(['/bin/bash', str(BOOTSTRAP)], stdin=subprocess.DEVNULL,
                             start_new_session=True, capture_output=True, text=True, timeout=5)
    assert process.returncode == 1
    assert 'Ein Terminal ist nötig' in process.stderr


@pytest.fixture
def fake_curl(tmp_path, monkeypatch):
    target = tmp_path / 'curl'
    target.write_text('''#!/bin/bash
set -eu
while [[ $# -gt 1 ]]; do
    if [[ $1 == --output ]]; then
        target=$2
        shift
    fi
    shift
done
printf '%s\\n' "$1" >> "$PICAM_TEST_FIXTURE/curl.log"
case $1 in
    https://api.github.com/repos/*/releases/latest|https://api.github.com/repos/*/releases/tags/v1.1.0)
        name=release.json ;;
    https://example.invalid/*) name=${1##*/} ;;
    *) exit 2 ;;
esac
if [[ ! -f $PICAM_TEST_FIXTURE/$name ]]; then
    printf 404
    exit 22
fi
cp "$PICAM_TEST_FIXTURE/$name" "$target"
printf 200
''')
    target.chmod(0o755)
    monkeypatch.setenv('PATH', f'{tmp_path}:/usr/bin:/bin')
    monkeypatch.setenv('PICAM_TEST_FIXTURE', str(tmp_path))
    (tmp_path / 'release.json').write_bytes(FIXTURE.read_bytes())
    return tmp_path


def make_archive(path, version):
    with tarfile.open(path, 'w:gz') as archive:
        for name, body, mode in [
            ('release.json', json.dumps({'release_id': version, 'dirty': False}), 0o644),
            ('VERSION', version + '\n', 0o644),
            ('install.sh', '''#!/bin/bash
set -eu
[[ -t 0 && "$1" == --guided && "$2" == --source && -f "$3" && "$4" == --sha256 ]]
actual=$(sha256sum < "$3")
[[ "${actual%% *}" == "$5" ]]
IFS= read -r reply
[[ "$reply" == Testeingabe ]]
printf 'Installer hat TTY und SHA-256\\n'
''', 0o755),
        ]:
            data = body.encode()
            info = tarfile.TarInfo(f'picam/{name}')
            info.size, info.mode = len(data), mode
            archive.addfile(info, io.BytesIO(data))


@pytest.mark.parametrize(('mode', 'expected'), [
    ('latest', 'Installer hat TTY und SHA-256'), ('pinned', 'Installer hat TTY und SHA-256'),
    ('missing', 'HTTP 404'), ('wrong', 'Archiv-Hash stimmt nicht'),
    ('wrong version', 'Archiv passt nicht zum veröffentlichten Release'),
])
def test_bootstrap_pipe_with_controlling_terminal(fake_curl, mode, expected):
    archive = fake_curl / FILENAME
    make_archive(archive, '1.1.1' if mode == 'wrong version' else '1.1.0')
    if mode != 'missing':
        digest = 'a' * 64 if mode == 'wrong' else hashlib.sha256(archive.read_bytes()).hexdigest()
        (fake_curl / (FILENAME + '.sha256')).write_text(f'{digest}  {FILENAME}\n')
    cmd = f'cat {shlex.quote(str(BOOTSTRAP))} | bash -s --'
    if mode == 'pinned':
        cmd += ' --version v1.1.0'
    result = subprocess.run(['script', '-qec', cmd, '/dev/null'], input='Testeingabe\n',
                            capture_output=True, text=True, timeout=15)
    assert expected in result.stdout, result.stdout + result.stderr
    assert result.returncode == (0 if mode in ('latest', 'pinned') else 1)
    endpoint = 'tags/v1.1.0' if mode == 'pinned' else 'latest'
    endpoint = f'{release_source.API_BASE}/repos/{release_source.REPOSITORY}/releases/{endpoint}'
    calls = (fake_curl / 'curl.log').read_text().splitlines()
    assert calls[0] == endpoint
    assert len(calls) == (2 if mode == 'missing' else 3)
