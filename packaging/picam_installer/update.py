"""Update und Rückweg einer installierten Werkbank (System- oder Benutzermodus).

Eine neue Version wird neben der laufenden unter ``<prefix>/releases/<id>``
vorbereitet (Dateien, eigene venv, Selbsttest). Erst ``activate`` schaltet
``current`` atomar um und merkt sich die vorige Version in ``previous``.
Daten, Konfiguration, Identität und Kalibrierung bleiben unberührt.
Dienststopp/-start und die Laufsperre steuert ``picam update``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .archive import load_source
from .engine import no_symlinks, prepare_release
from .platform import probe_system


def releases(prefix: Path) -> dict:
    """Aktive, vorige und vorhandene Versionen."""
    prefix = Path(prefix)
    current = prefix / 'current'
    previous = prefix / 'previous'
    return {
        'current': current.resolve().name if current.is_symlink() else None,
        'previous': previous.resolve().name if previous.is_symlink() and previous.resolve().is_dir() else None,
        'installed': sorted(p.name for p in (prefix / 'releases').iterdir() if p.is_dir())
        if (prefix / 'releases').is_dir() else [],
    }


def check_prefix(prefix: Path) -> Path:
    prefix = Path(prefix)
    if not prefix.is_absolute():
        raise ValueError('Installationsort muss absolut sein')
    no_symlinks(prefix)
    if not (prefix / 'current').is_symlink() or not (prefix / 'releases').is_dir():
        raise ValueError(f'{prefix} ist keine picam-Installation (current/releases fehlt)')
    target = (prefix / 'current').resolve()
    if target.parent != (prefix / 'releases').resolve():
        raise ValueError('current zeigt nicht in releases/; keine automatische Umschaltung')
    return prefix


def plan_update(prefix, source, sha256=None, *, stable_version=None):
    prefix = check_prefix(prefix)
    bundle = load_source(source, sha256)
    if stable_version is not None and (
        bundle.release_id != stable_version or bundle.manifest.get('dirty') is not False
        or bundle.files['VERSION'].strip() != stable_version.encode('ascii')
    ):
        raise ValueError(f'Archiv passt nicht zum veröffentlichten Release {stable_version}.')
    state = releases(prefix)
    if bundle.release_id == state['current']:
        raise ValueError(f'Version {bundle.release_id} ist bereits aktiv')
    target = prefix / 'releases' / bundle.release_id
    if target.exists():
        raise ValueError(f'{target} besteht bereits (frühere Installation?); '
                         f'zum Umschalten: picam update --activate {bundle.release_id}')
    return bundle, target, state


def prepare(prefix, source, sha256=None, python='/usr/bin/python3', runner=subprocess.run,
            progress=lambda _text: None, *, step=None, stable_version=None):
    """Neue Version vorbereiten, nicht aktivieren. Bei Fehler bleibt nichts zurück."""
    os.umask(0o022)  # Programmdateien für das Dienstkonto lesbar, auch bei geerbtem umask 077
    if step is not None:
        step('pruefen')
    bundle, target, state = plan_update(prefix, source, sha256, stable_version=stable_version)
    info = probe_system(python, runner=runner)
    if info.missing_modules:
        raise ValueError('Python-Systemmodule fehlen: ' + ', '.join(info.missing_modules))
    try:
        prepare_release(bundle, target, info, runner, progress, **({'phase': step} if step is not None else {}))
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return {'release_id': bundle.release_id, 'path': str(target), 'from': state['current']}


def _swap_link(link: Path, target: Path) -> None:
    temporary = link.with_name(link.name + '.neu')
    if temporary.is_symlink() or temporary.exists():
        temporary.unlink()
    temporary.symlink_to(target)
    try:
        os.replace(temporary, link)
    finally:
        temporary.unlink(missing_ok=True)


def _release_dir(prefix: Path, release_id: str) -> Path:
    if (not isinstance(release_id, str) or not release_id or release_id != Path(release_id).name
            or release_id in ('.', '..') or '/' in release_id or '\x00' in release_id):
        raise ValueError(f'Ungültiger Versionsname: {release_id!r}')
    target = prefix / 'releases' / release_id
    if target.is_symlink() or target.resolve().parent != (prefix / 'releases').resolve():
        raise ValueError(f'Version {release_id} liegt nicht direkt in releases/')
    return target


def activate(prefix, release_id) -> dict:
    """``current`` atomar auf ``release_id`` umschalten, vorige Version als ``previous`` merken."""
    prefix = check_prefix(prefix)
    target = _release_dir(prefix, release_id)
    if not (target / 'release.json').is_file() or not (target / '.venv/bin/python').exists():
        raise ValueError(f'Version {release_id} ist nicht vollständig vorbereitet')
    old = (prefix / 'current').resolve()
    if old == target.resolve():
        raise ValueError(f'Version {release_id} ist bereits aktiv')
    previous = prefix / 'previous'
    if previous.exists() and not previous.is_symlink():
        raise ValueError(f'{previous} ist kein Versionsverweis')
    previous_target = previous.readlink() if previous.is_symlink() else None
    _swap_link(previous, old)
    try:
        _swap_link(prefix / 'current', target)
    except OSError as error:
        try:
            if previous_target is None:
                previous.unlink()
            else:
                _swap_link(previous, previous_target)
        except OSError as restore_error:
            raise ValueError(
                f'Umschalten fehlgeschlagen: {error}. Vorigen Versionsverweis prüfen: {restore_error}'
            ) from restore_error
        raise
    return {'current': release_id, 'previous': old.name}


def remove(prefix, release_id) -> None:
    """Nicht aktive, nicht vorige Version löschen (Aufräumen)."""
    prefix = check_prefix(prefix)
    state = releases(prefix)
    if release_id in (state['current'], state['previous']):
        raise ValueError('Aktive oder vorige Version wird nicht gelöscht')
    target = _release_dir(prefix, release_id)
    if not target.is_dir():
        raise ValueError(f'Version {release_id} nicht gefunden')
    shutil.rmtree(target)
