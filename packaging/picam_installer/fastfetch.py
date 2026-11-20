"""Optionale Komponente „me-fastfetch“: ME-Logo und Systemübersicht beim SSH-Login.

Richtet für das Bedienerkonto ein (nichts davon gehört root):

* ``~/.local/share/me-fastfetch/me-logo.py`` – einmaliger Glanzlauf, nur Standardbibliothek
* ``~/.local/bin/me-fastfetch`` – Startskript mit ``/usr/bin/python3``
* ``~/.config/fastfetch/config.jsonc`` und ``me-logo.txt``
* ein markierter Block in ``~/.bashrc``: nur interaktive SSH-Logins mit Terminal,
  ohne ``me-fastfetch`` einfach ``fastfetch``

Das Debian-Paket ``fastfetch`` gehört nur zu dieser Komponente und wird nur im
Systemmodus (root, ohne ``--root``) installiert. Abweichende vorhandene Dateien
werden vorher gesichert, nie still überschrieben; ein fremder fastfetch-Aufruf in
``~/.bashrc`` bleibt unangetastet. Ein Manifest hält fest, was der Installer
geschrieben hat: die Deinstallation entfernt nur unveränderte eigene Dateien und
den markierten Block. Läuft der Installer als root, schreibt er mit der
effektiven Kennung des Kontos (Symlinks im Home führen so nirgends hin, wo das
Konto nicht ohnehin schreiben darf). Standardbibliothek, Python >= 3.9.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

NAME = 'me-fastfetch'
PACKAGE = 'fastfetch'
SOURCE_DIR = 'packaging/me-fastfetch'
SHARE = '.local/share/me-fastfetch'
MANIFEST = SHARE + '/picam-manifest.json'
BASHRC = '.bashrc'
#: Quelldatei im Release → Ziel relativ zum Home, Dateirechte.
TARGETS = (
    ('me-logo.py', SHARE + '/me-logo.py', 0o644),
    ('me-fastfetch.in', '.local/bin/me-fastfetch', 0o755),
    ('config.jsonc', '.config/fastfetch/config.jsonc', 0o644),
    ('me-logo.txt', '.config/fastfetch/me-logo.txt', 0o644),
)
#: Ordner, die die Deinstallation entfernt, wenn sie danach leer sind (tiefste zuerst).
OWN_DIRS = (SHARE, '.config/fastfetch')
BEGIN = '# >>> me-fastfetch (picam-Installer) >>>'
END = '# <<< me-fastfetch (picam-Installer) <<<'
BLOCK = '\n'.join((
    BEGIN,
    '# Fastfetch mit einmaligem ME-Glanzlauf bei interaktiven SSH-Logins.',
    'if [ -n "$SSH_CONNECTION" ] && [[ $- == *i* ]] && [ -t 1 ] '
    '&& [ -z "${VSCODE_RESOLVING_ENVIRONMENT:-}" ] && command -v fastfetch >/dev/null 2>&1; then',
    '    if [ -x "$HOME/.local/bin/me-fastfetch" ] && [ -x /usr/bin/python3 ]; then',
    '        "$HOME/.local/bin/me-fastfetch"',
    '    else',
    '        fastfetch',
    '    fi',
    'fi',
    END,
)) + '\n'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sources(bundle_files=None):
    """Dateien der Komponente: aus dem geprüften Release, sonst neben dem Installer."""
    local = Path(__file__).resolve().parents[1] / 'me-fastfetch'
    found = {}
    for name, _, _ in TARGETS:
        key = f'{SOURCE_DIR}/{name}'
        if bundle_files and key in bundle_files:
            found[name] = bundle_files[key]
            continue
        try:
            found[name] = (local / name).read_bytes()
        except OSError as error:
            raise ValueError(f'{NAME}: {key} fehlt im Release') from error
    return found


def render(files, home: Path):
    """Zielpfad → Inhalt, Rechte. Das Startskript zeigt auf me-logo.py dieses Kontos."""
    script = shlex.quote(str(home / SHARE / 'me-logo.py')).encode()
    rendered = {}
    for name, relative, mode in TARGETS:
        data = files[name]
        if name.endswith('.in'):
            data = data.replace(b'@ME_LOGO@', script)
        rendered[home / relative] = (data, mode)
    return rendered


def package_installed(runner):
    try:
        result = runner(['dpkg-query', '-W', '-f=${Status}', PACKAGE], capture_output=True, text=True, timeout=10)
    except (OSError, ValueError):
        return shutil.which(PACKAGE) is not None
    return result.returncode == 0 and (result.stdout or '').strip() == 'install ok installed'


def check_home_path(home: Path, path: Path):
    """Kein Symlink zwischen Home und Ziel (das Ziel selbst eingeschlossen)."""
    if home.is_symlink() or not home.is_dir():
        raise ValueError(f'{NAME}: Home {home} ist kein echtes Verzeichnis')
    current = home
    for part in path.relative_to(home).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f'{NAME}: Symlink im Zielpfad {current}; nichts geändert')


def bashrc_state(text):
    """``fehlt`` | ``aktuell`` | ``veraltet`` (eigener Block) | ``fremd`` (anderer fastfetch-Aufruf)."""
    begin, end = text.find(BEGIN), text.find(END)
    if begin != -1 and end > begin and text.count(BEGIN) == 1 and text.count(END) == 1:
        current = text[begin:end + len(END)] + '\n'
        outside = text[:begin] + text[end + len(END):]
        if 'fastfetch' in outside:
            return 'fremd'
        return 'aktuell' if current == BLOCK else 'veraltet'
    if begin != -1 or end != -1 or 'fastfetch' in text:
        return 'fremd'
    return 'fehlt'


def _read_manifest(home: Path):
    path = home / MANIFEST
    if path.is_symlink() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        return None
    if not isinstance(data, dict) or data.get('component') != NAME or not isinstance(data.get('files'), dict):
        return None
    known = {str(home / relative) for _, relative, _ in TARGETS}
    data['files'] = {path: digest for path, digest in data['files'].items()
                     if path in known and isinstance(digest, str)}
    return data


def plan(home, files, *, package_present, can_install_package):
    """Schreibfreier Plan der Komponente (JSON-fähig)."""
    home = Path(home)
    manifest = _read_manifest(home) or {'files': {}}
    entries = []
    for path, (data, _) in render(files, home).items():
        check_home_path(home, path)
        if not path.exists():
            state = 'neu'
        elif not path.is_file():
            raise ValueError(f'{NAME}: {path} ist keine Datei; nichts geändert')
        elif sha256(path.read_bytes()) == sha256(data):
            state = 'gleich'
        elif manifest['files'].get(str(path)) == sha256(path.read_bytes()):
            state = 'erneuern'  # eigene, unveränderte ältere Fassung
        else:
            state = 'sichern'   # abweichend: erst sichern, dann ersetzen
        entries.append({'path': str(path), 'state': state})
    bashrc = home / BASHRC
    check_home_path(home, bashrc)
    if bashrc.exists() and not bashrc.is_file():
        raise ValueError(f'{NAME}: {bashrc} ist keine Datei; nichts geändert')
    text = bashrc.read_text(encoding='utf-8', errors='replace') if bashrc.is_file() else ''
    if package_present:
        package = 'vorhanden'
    else:
        package = 'installieren' if can_install_package else 'fehlt'
    notes = []
    state = bashrc_state(text)
    if state == 'fremd':
        notes.append(f'{bashrc} ruft fastfetch schon selbst auf; bleibt unverändert.')
    if package == 'fehlt':
        notes.append(f'Paket {PACKAGE} fehlt; später: sudo apt-get install {PACKAGE}')
    return {'component': NAME, 'home': str(home), 'files': entries,
            'bashrc': {'path': str(bashrc), 'state': state}, 'package': package, 'notes': notes,
            'applied': False}


@contextmanager
def as_user(uid, gid):
    """Als root mit der effektiven Kennung des Kontos arbeiten; sonst nichts tun."""
    if os.geteuid() != 0 or uid == 0:
        yield
        return
    groups, egid = os.getgroups(), os.getegid()
    os.setgroups([gid])
    os.setegid(gid)
    os.seteuid(uid)
    try:
        yield
    finally:
        os.seteuid(0)
        os.setegid(egid)
        os.setgroups(groups)


def _stamp():
    return time.strftime('%Y%m%d-%H%M%S')


def _write(path: Path, data: bytes, mode: int):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    temporary = path.with_name(f'.{path.name}.picam-neu')
    if temporary.is_symlink() or temporary.is_file():
        temporary.unlink()
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), mode)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _backup_name(path: Path, label='vor-picam'):
    candidate = path.with_name(f'{path.name}.{label}-{_stamp()}')
    index = 1
    while candidate.exists() or candidate.is_symlink():
        index += 1
        candidate = path.with_name(f'{path.name}.{label}-{_stamp()}-{index}')
    return candidate


def with_block(text):
    """``text`` mit genau einem aktuellen Block am Ende bzw. an der alten Stelle."""
    begin, end = text.find(BEGIN), text.find(END)
    if begin != -1 and end > begin:
        tail = text[end + len(END):]
        return text[:begin] + BLOCK + (tail[1:] if tail.startswith('\n') else tail)
    prefix = text if not text or text.endswith('\n') else text + '\n'
    return prefix + ('\n' if prefix else '') + BLOCK


def without_block(text):
    begin, end = text.find(BEGIN), text.find(END)
    if begin == -1 or end < begin:
        return text
    head, tail = text[:begin], text[end + len(END):]
    if tail.startswith('\n'):
        tail = tail[1:]
    if head.endswith('\n\n'):
        head = head[:-1]  # die Leerzeile, die with_block vorangestellt hat
    return head + tail


def _rewrite(path: Path, text: str, label):
    """Mit Sicherung neben der Datei ersetzen; Rechte bleiben erhalten."""
    mode = path.stat().st_mode & 0o7777 if path.exists() else 0o644
    backup = None
    if path.exists():
        backup = _backup_name(path, label)
        shutil.copy2(path, backup, follow_symlinks=False)
    _write(path, text.encode('utf-8'), mode)
    return backup


def apply(home, files, *, uid, gid, runner, step=lambda _text: None, install_package=False):
    """Komponente einrichten. Paket als root, Dateien mit der Kennung des Kontos."""
    home = Path(home)
    result = {'component': NAME, 'home': str(home), 'applied': False, 'backups': [], 'written': [],
              'package_installed': False}
    if install_package:
        step(f'{NAME}: Paket {PACKAGE} installieren (apt)')
        runner(['apt-get', 'install', '-y', '--', PACKAGE], check=True, capture_output=True, text=True, timeout=600)
        result['package_installed'] = True
    step(f'{NAME}: Dateien und Login-Begrüßung einrichten')
    with as_user(uid, gid):
        current = plan(home, files, package_present=True, can_install_package=False)
        manifest = _read_manifest(home) or {'component': NAME, 'schema': 1, 'files': {}, 'backups': []}
        manifest.setdefault('backups', [])
        states = {entry['path']: entry['state'] for entry in current['files']}
        for path, (data, mode) in render(files, home).items():
            state = states[str(path)]
            if state == 'gleich':
                if str(path) in manifest['files']:
                    manifest['files'][str(path)] = sha256(data)
                continue
            if state == 'sichern':
                backup = _backup_name(path)
                os.rename(path, backup)
                result['backups'].append(str(backup))
            _write(path, data, mode)
            manifest['files'][str(path)] = sha256(data)
            result['written'].append(str(path))
        bashrc = Path(current['bashrc']['path'])
        state = current['bashrc']['state']
        if state in ('fehlt', 'veraltet'):
            text = bashrc.read_text(encoding='utf-8') if bashrc.is_file() else ''
            backup = _rewrite(bashrc, with_block(text), 'vor-me-fastfetch')
            if backup:
                result['backups'].append(str(backup))
            result['written'].append(str(bashrc))
        manifest['bashrc'] = str(bashrc) if state != 'fremd' else manifest.get('bashrc')
        manifest['backups'] = sorted(set(manifest['backups']) | set(result['backups']))
        manifest['package_installed_by_picam'] = bool(manifest.get('package_installed_by_picam')
                                                       or result['package_installed'])
        _write(home / MANIFEST, (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode(), 0o644)
    result.update(applied=True, bashrc_state=state)
    return result


# ---------------------------------------------------------------- Deinstallation
def removal(home, *, remove_package=False):
    """Aktionen für ``uninstall``: nur unveränderte eigene Dateien und den markierten Block.

    Rückgabe ``None``, wenn die Komponente nicht vom Installer stammt (kein Manifest).
    """
    home = Path(home)
    manifest = _read_manifest(home)
    if manifest is None:
        return None
    actions, remove, keep, notes = [], [], [], []
    for path_text, digest in sorted(manifest['files'].items()):
        path = Path(path_text)
        check_home_path(home, path)
        if not path.exists():
            continue
        if path.is_file() and sha256(path.read_bytes()) == digest:
            actions.append({'kind': 'unlink', 'path': path_text, 'text': f'{NAME}: {path.name} entfernen'})
            remove.append(path_text)
        else:
            keep.append({'path': path_text, 'reason': 'seit der Installation geändert'})
    bashrc = home / BASHRC
    check_home_path(home, bashrc)
    if bashrc.is_file():
        text = bashrc.read_text(encoding='utf-8', errors='replace')
        if BEGIN in text and END in text:
            actions.append({'kind': 'bashrc_block', 'path': str(bashrc),
                            'text': f'{NAME}: markierten Block aus .bashrc entfernen (mit Sicherung)'})
    manifest_path = str(home / MANIFEST)
    actions.append({'kind': 'unlink', 'path': manifest_path, 'text': f'{NAME}: Manifest entfernen'})
    remove.append(manifest_path)
    for relative in OWN_DIRS:
        directory = str(home / relative)
        actions.append({'kind': 'rmdir_if_empty', 'path': directory, 'text': f'{NAME}: {relative} entfernen, falls leer'})
        remove.append(directory)
    for backup in manifest.get('backups') or []:
        if isinstance(backup, str) and Path(backup).exists():
            keep.append({'path': backup, 'reason': 'Sicherung aus der Installation'})
    if manifest.get('package_installed_by_picam'):
        if remove_package:
            actions.append({'kind': 'command', 'argv': ['apt-get', 'remove', '-y', '--', PACKAGE],
                            'text': f'{NAME}: Paket {PACKAGE} entfernen'})
        else:
            notes.append(f'Paket {PACKAGE} bleibt installiert (--remove-fastfetch-package entfernt es).')
    elif remove_package:
        notes.append(f'Paket {PACKAGE} stammt nicht vom Installer; bleibt.')
    return {'actions': actions, 'remove': remove, 'keep': keep, 'notes': notes, 'edit': [str(bashrc)],
            'needs_root': bool(remove_package and manifest.get('package_installed_by_picam'))}


def remove_block(path: Path):
    """Markierten Block entfernen; vorher Sicherung. Rückgabe: Sicherungspfad oder None."""
    if path.is_symlink():
        raise ValueError(f'{path} ist ein Symlink; nicht geändert')
    info = path.stat()
    with as_user(info.st_uid, info.st_gid):
        text = path.read_text(encoding='utf-8')
        changed = without_block(text)
        if changed == text:
            return None
        return _rewrite(path, changed, 'vor-me-fastfetch-entfernen')
