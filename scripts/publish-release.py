#!/usr/bin/env python3
"""Build locally and publish both Pi release assets to the configured mirror."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'src'))
from dispread import release_source  # noqa: E402


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()


def check_checkout(tag):
    head = git('rev-parse', 'HEAD')
    try:
        tagged_commit = git('rev-parse', '--verify', '--quiet', f'refs/tags/{tag}^{{commit}}')
    except subprocess.CalledProcessError as error:
        raise ValueError(f'Lokaler Tag {tag} fehlt oder zeigt auf keinen Commit.') from error
    if tagged_commit != head:
        raise ValueError(f'Tag {tag} muss auf HEAD zeigen.')
    if git('status', '--porcelain', '--untracked-files=normal'):
        raise ValueError('Der Arbeitsbaum muss sauber sein.')
    return head


def notes_for(version, notes_file):
    if notes_file is not None:
        notes = notes_file.read_text()
    else:
        changelog = (ROOT / 'CHANGELOG.md').read_text()
        heading = re.search(rf'^## v?{re.escape(version)}(?=\s|$)[^\n]*\n', changelog, re.MULTILINE)
        if heading is None:
            raise ValueError(f'CHANGELOG-Abschnitt für {version} fehlt. --notes-file angeben.')
        notes = re.split(r'^## ', changelog[heading.end():], maxsplit=1, flags=re.MULTILINE)[0]
    if not notes.strip():
        raise ValueError('Release-Notes sind leer.')
    return notes.strip() + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag', help='Versionstag vX.Y.Z auf HEAD')
    parser.add_argument('--templates', required=True, type=Path, help='Pfad zur freigegebenen lokalen Lesevorlage')
    parser.add_argument('--notes-file', type=Path, help='Release-Notes, sonst der Versionsabschnitt im CHANGELOG')
    parser.add_argument('--dry-run', action='store_true', help='Voraussetzungen prüfen und Befehle anzeigen')
    args = parser.parse_args()
    tag = args.tag
    version = tag[1:]
    if not tag.startswith('v') or release_source.stable_version(version) is None:
        parser.error('Tag muss vX.Y.Z sein.')
    try:
        commit = check_checkout(tag)
        notes = notes_for(version, args.notes_file)
        if not args.templates.is_file():
            raise ValueError(f'Lesevorlage fehlt: {args.templates}')
        filename = release_source.ASSET_NAME.format(version=version)

        def commands(directory):
            archive = directory / filename
            checksum = directory / (filename + '.sha256')
            build = [sys.executable, str(ROOT / 'scripts/build-release.py'), '--output', str(archive),
                     '--templates', str(args.templates.absolute()), '--release-id', version]
            upload = ['gh', 'release', 'create', tag, str(archive), str(checksum),
                      '--repo', release_source.REPOSITORY, '--verify-tag',
                      '--title', f'picam {version}', '--notes-file', str(directory / 'release-notes.md')]
            return archive, checksum, build, upload

        if args.dry_run:
            archive, checksum, build, upload = commands(Path('/tmp/picam-publish-DRY-RUN'))
            print(shlex.join(build))
            print(f'SHA-256 für {archive.name} → {checksum.name}')
            print(shlex.join(upload))
            return 0

        with tempfile.TemporaryDirectory(prefix='picam-publish-', dir='/tmp') as temp:
            directory = Path(temp)
            archive, checksum, build, upload = commands(directory)
            subprocess.run(build, check=True)
            with tarfile.open(archive, 'r:gz') as bundle:
                manifest = json.load(bundle.extractfile('picam/release.json'))
                archive_version = bundle.extractfile('picam/VERSION').read().decode('ascii').strip()
            if (manifest['dirty'] is not False or manifest['commit'] != commit
                    or manifest['release_id'] != version or archive_version != version
                    or check_checkout(tag) != commit):
                raise ValueError('Archiv und Arbeitsbaum passen nicht zum getaggten Release.')
            with archive.open('rb') as stream:
                sha256 = hashlib.file_digest(stream, 'sha256').hexdigest()
            checksum.write_text(f'{sha256}  {filename}\n', encoding='ascii')
            (directory / 'release-notes.md').write_text(notes, encoding='utf-8')
            subprocess.run(upload, check=True)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f'picam: Veröffentlichung fehlgeschlagen: {error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
