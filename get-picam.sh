#!/usr/bin/env bash
# Standalone entry point. Keep these settings in sync with src/dispread/release_source.py.
repository='LeoMESysteme/picam-ai'
api_base='https://api.github.com'
asset_pattern='picam-{version}.tar.gz'

main() {
    set -eu
    local tag='' version_pattern='(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
    if [[ $# == 2 && $1 == --version && $2 =~ ^v${version_pattern}$ && ${#2} -le 129 ]]; then
        tag=$2
    elif [[ $# != 0 ]]; then
        fail 'Aufruf: bash get-picam.sh [--version vX.Y.Z]'
    fi
    if ! { exec 3</dev/tty; } 2>/dev/null; then
        fail 'Ein Terminal ist nötig. Ohne TTY das Releasearchiv mit install.sh und ausdrücklichen Angaben verwenden.'
    fi

    umask 077
    work=$(mktemp -d)
    trap 'rm -rf -- "$work"' EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP

    local endpoint=latest
    if [[ -n $tag ]]; then
        endpoint=tags/$tag
    fi
    printf 'picam · Suche Release …\n'
    fetch "$api_base/repos/$repository/releases/$endpoint" "$work/release-api.json" 1048576 15
    python3 - "$work" "$tag" "$version_pattern" "$asset_pattern" <<'PYTHON'
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

work, requested, pattern, asset_pattern = sys.argv[1:]
work = Path(work)
try:
    data = json.loads((work / 'release-api.json').read_bytes())
    if not isinstance(data, dict) or data.get('draft') is not False or data.get('prerelease') is not False:
        raise ValueError('Kein veröffentlichter stabiler Release.')
    tag = data.get('tag_name')
    if not isinstance(tag, str) or len(tag) > 129 or not re.fullmatch('v' + pattern, tag):
        raise ValueError('Release braucht einen Tag vX.Y.Z.')
    if requested and tag != requested:
        raise ValueError('Antwort passt nicht zum angeforderten Tag.')
    name = asset_pattern.format(version=tag[1:])
    lines = [name, tag[1:]]
    assets = data.get('assets')
    if not isinstance(assets, list):
        raise ValueError('Dateiliste fehlt in der GitHub-Release-Antwort.')
    for filename in (name, name + '.sha256'):
        urls = [asset.get('browser_download_url') for asset in assets
                if isinstance(asset, dict) and asset.get('name') == filename]
        if len(urls) != 1 or not isinstance(urls[0], str):
            raise ValueError(f'Release-Datei fehlt oder ist nicht eindeutig: {filename}')
        url = urls[0]
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or '#' in url or any(ord(c) <= 32 for c in url)):
            raise ValueError('Release-Datei braucht eine HTTPS-Adresse ohne Zugangsdaten oder Fragment.')
        lines.append(url)
    (work / 'assets').write_text('\n'.join(lines) + '\n', encoding='utf-8')
except (OSError, ValueError) as error:
    sys.exit(f'picam: {error}')
PYTHON
    local name version archive_url checksum_url digest actual
    {
        IFS= read -r name
        IFS= read -r version
        IFS= read -r archive_url
        IFS= read -r checksum_url
    } < "$work/assets"
    fetch "$checksum_url" "$work/$name.sha256" 512 15
    digest=$(python3 - "$work/$name.sha256" "$name" <<'PYTHON'
import re
import sys
from pathlib import Path

raw = Path(sys.argv[1]).read_bytes()
name = re.escape(sys.argv[2].encode('ascii'))
match = re.fullmatch(rb'([a-fA-F0-9]{64}) [ *]' + name + rb'\n?', raw)
if match is None:
    sys.exit('picam: Ungültige SHA-256-Datei.')
print(match[1].decode('ascii').lower())
PYTHON
    )

    printf 'picam · Lade Version %s …\n' "$version"
    fetch "$archive_url" "$work/$name" 134217728 120
    actual=$(sha256sum < "$work/$name")
    [[ ${actual%% *} == "$digest" ]] || fail 'Archiv-Hash stimmt nicht.'

    # Validate the bounded tar stream before running code from the archive.
    python3 - "$work" "$name" "$version" <<'PYTHON'
import gzip
import io
import json
import sys
import tarfile
from pathlib import Path

work, name, version = sys.argv[1:]
work = Path(work)
limit = 128 * 1024 * 1024
try:
    with gzip.open(work / name, 'rb') as archive:
        expanded = archive.read(limit + 1)
    if len(expanded) > limit:
        raise ValueError('Entpacktes Releasearchiv ist zu groß.')
    with tarfile.open(fileobj=io.BytesIO(expanded), mode='r:') as archive:
        seen = set()
        for entry in archive:
            parts = entry.name.split('/')
            if (parts[0] != 'picam' or any(part in ('', '.', '..') for part in parts)
                    or entry.name in seen or len(seen) >= 10000
                    or not (entry.isdir() or (entry.isfile() and len(parts) > 1))):
                raise ValueError('Unsichere Einträge im Releasearchiv.')
            seen.add(entry.name)
        manifest = json.load(archive.extractfile('picam/release.json'))
        if (not isinstance(manifest, dict) or manifest.get('release_id') != version
                or manifest.get('dirty') is not False
                or archive.extractfile('picam/VERSION').read().strip() != version.encode('ascii')):
            raise ValueError(f'Archiv passt nicht zum veröffentlichten Release {version}.')
        if not archive.getmember('picam/install.sh').isfile():
            raise ValueError('install.sh fehlt im Releasearchiv.')
except (OSError, EOFError, TypeError, ValueError, KeyError, tarfile.TarError) as error:
    sys.exit(f'picam: {error}')
PYTHON
    tar --no-same-owner --no-same-permissions -xzf "$work/$name" -C "$work"
    # Nur der Temp-Ordner ist privat (mktemp -d: 0700). Der Installer legt Programmdateien
    # fuer das Dienstkonto an und darf das strenge umask nicht erben (raspi01 25.11.).
    umask 022
    "$work/picam/install.sh" --guided --source "$work/$name" --sha256 "$digest" <&3
}

fail() {
    printf 'picam: %s\n' "$*" >&2
    exit 1
}

fetch() {
    local url=$1 target=$2 limit=$3 timeout=$4 code
    if ! code=$(curl -q -fsSL --proto '=https' --proto-redir '=https' --max-redirs 4 \
        --globoff --connect-timeout 5 --max-time "$timeout" --max-filesize "$limit" \
        --output "$target" --write-out '%{http_code}' -- "$url"); then
        case $code in
            403|429) fail "GitHub verweigert den Download (HTTP $code, möglicherweise Ratenlimit). Später erneut versuchen." ;;
            404) fail 'GitHub-Release oder Release-Datei nicht gefunden (HTTP 404).' ;;
            *) fail "Release-Download fehlgeschlagen: $url" ;;
        esac
    fi
    [[ $(wc -c < "$target") -le $limit ]] || fail 'Release-Download überschreitet das Größenlimit.'
}

main "$@"
