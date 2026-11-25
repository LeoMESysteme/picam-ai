"""Prepare, switch and verify an installed release, with a fallback on restart failure."""

from __future__ import annotations

import argparse
import errno
import fcntl
import importlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path

from . import probes, service
from .calibrate import sudo_cached as sudo_cached
from .calibrate import sudo_validate as sudo_validate
from .instance import Instance

RELEASE_SOURCE: str | None = None  # OQ-49
STEPS = {
    'pruefen': 'Releasearchiv prüfen',
    'entpacken': 'Release entpacken',
    'umgebung': 'Python-Umgebung vorbereiten',
    'selbsttest': 'Selbsttest ausführen',
    'umschalten': 'Aktive Version umschalten',
    'dienst_neustart': 'Dienst neu starten und HTTPS prüfen',
    'bereit': 'Neue Version bereit',
    'rueckweg': 'Vorige Version wiederherstellen',
}


class UpdateError(ValueError):
    pass


class _Cancelled(UpdateError):
    pass


class _Blocked(UpdateError):
    pass


@dataclass
class Deps:
    collect: Callable[..., probes.Snapshot] = probes.collect
    restart: Callable[[Instance, Callable[[str], None]], bool] | None = None
    cancelled: Callable[[], bool] = lambda: False
    ask: Callable[[str], str] = input


@dataclass
class Result:
    outcome: str = 'failed'
    old_version: str | None = None
    new_version: str | None = None
    rollback_triggered: bool = False
    rollback_ok: bool | None = None
    reason: str | None = None
    message: str = ''
    restart_command: str | None = None

    @property
    def exit_code(self) -> int:
        return {'ok': 0, 'failed': 1, 'blocked': 3, 'cancelled': 130}[self.outcome]


def resolve_source(source: str | None) -> str:
    if source is None:
        if not RELEASE_SOURCE:
            raise UpdateError('Bezugsquelle noch nicht festgelegt – mit --source angeben')
        source = RELEASE_SOURCE
    return source


def prefix_of(instance: Instance) -> Path:
    if instance.kind not in ('system', 'user') or not instance.root:
        raise UpdateError('Update nur für eine installierte Werkbank (System- oder Benutzerdienst). '
                          'Im Entwicklungsbetrieb: git pull und picam restart.')
    release = Path(instance.root)
    if release.parent.name != 'releases':
        raise UpdateError(f'{release} liegt nicht in einem releases/-Verzeichnis')
    return release.parent.parent


def installer_module(instance: Instance, name: str):
    """Installer-Modul aus der aktiven Version (packaging/picam_installer)."""
    packaging = Path(instance.root or '') / 'packaging'
    if str(packaging) not in sys.path:
        sys.path.insert(0, str(packaging))
    return importlib.import_module(f'picam_installer.{name}')


def needs_root(instance: Instance) -> bool:
    return instance.scope == 'system' and os.geteuid() != 0


sudo_needed = needs_root


def sudo_command(argv: list[str]) -> list[str]:
    return ['sudo', sys.executable, '-m', 'dispread.admin.cli', *argv]


@contextmanager
def _update_lock(prefix: Path):
    # Kein zusätzliches Lockfile, das nach der Deinstallation zurückbleibt.
    fd = os.open(prefix, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in (errno.EAGAIN, errno.EACCES):
                raise _Blocked('Update gesperrt: Ein anderes Update läuft bereits.') from error
            raise
        yield
    finally:
        os.close(fd)


def _restart_and_wait(instance: Instance, echo, *, output=None) -> bool:
    command = probes.systemctl(instance) + ['restart', instance.unit]
    echo('$ ' + ' '.join(command))
    if subprocess.call(command, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                       timeout=service.COMMAND_TIMEOUT_S) != 0:
        return False
    echo(f'Warte auf {instance.url} …')
    return service.wait_until_ready(instance)


def _check_cancelled(deps):
    if deps.cancelled():
        raise _Cancelled('Update abgebrochen.')


def _check_blocker(instance, deps, *, target=None):
    blocker = deps.collect(instance, include_setup=False).stop_blocker
    if blocker:
        if target:
            raise _Blocked(f'Umschalten gesperrt: {blocker}. Später: picam update --activate {target}')
        raise _Blocked(f'Update gesperrt: {blocker}')


def _notify(callback, *args):
    # Nach dem Umschalten hat der Wiederanlauf Vorrang vor der Anzeige,
    # auch wenn etwa die Textual-App oder die Ausgabepipe geschlossen wurde.
    with suppress(Exception, KeyboardInterrupt):
        callback(*args)


def _switch(instance, prefix, installer, result, deps, echo, step):
    release_id = result.new_version
    step('umschalten')
    _check_blocker(instance, deps, target=release_id)
    _check_cancelled(deps)
    active = installer.activate(prefix, release_id)
    result.old_version = previous = active['previous']
    restart = deps.restart or _restart_and_wait
    log = partial(_notify, echo)
    try:
        log(f'Aktiv: {active["current"]} (vorher {previous})')
        _notify(step, 'dienst_neustart')
        if restart(instance, log):
            result.outcome = 'ok'
            result.message = f'Version {release_id} läuft, {instance.url} antwortet.'
            result.restart_command = str(prefix / 'current/.venv/bin/picam')
        else:
            result.reason = f'Version {release_id} antwortet nicht.'
    except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        result.reason = str(error) or 'Neustart unterbrochen.'
    if result.outcome == 'ok':
        _notify(step, 'bereit')
        return

    result.rollback_triggered = True
    _notify(step, 'rueckweg')
    log(f'{result.reason} Zurück auf {previous}.')
    try:
        installer.activate(prefix, previous)
        result.rollback_ok = restart(instance, log)
    except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        result.rollback_ok = False
        result.reason += f' Rückweg fehlgeschlagen: {error}'
    if result.rollback_ok:
        result.message = f'Update auf {release_id} fehlgeschlagen, {previous} läuft wieder. Protokoll: picam logs'
    else:
        result.message = 'Update fehlgeschlagen und Rückweg antwortet nicht. Protokoll: picam logs'


def _perform(instance, source, sha256, release_id, deps, echo, step=None) -> Result:
    result = Result(new_version=release_id)

    def phase(key):
        if key in ('pruefen', 'entpacken', 'umgebung', 'selbsttest', 'umschalten'):
            _check_cancelled(deps)
        if step is not None:
            step(key)

    try:
        prefix = prefix_of(instance)
        installer = installer_module(instance, 'update')
        with _update_lock(prefix):
            result.old_version = installer.releases(prefix)['current']
            if release_id is None:
                _check_cancelled(deps)
                _check_blocker(instance, deps)
                prepared = installer.prepare(prefix, source, sha256, progress=lambda text: echo('· ' + text),
                                             **({'step': phase} if step is not None else {}))
                result.new_version = prepared['release_id']
                echo(f'Vorbereitet: {result.new_version} in {prepared["path"]}')
            _switch(instance, prefix, installer, result, deps, echo, phase)
    except (_Blocked, _Cancelled) as error:
        result.outcome = 'blocked' if isinstance(error, _Blocked) else 'cancelled'
        result.reason = result.message = str(error)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        result.reason = result.message = str(error)
    return result


def switch(instance: Instance, release_id: str, echo=print, collect=probes.collect) -> tuple[bool, str]:
    """Terminal-Aufruf für eine bereits vorbereitete Version."""
    result = _perform(instance, None, None, release_id, Deps(collect=collect), echo)
    return result.outcome == 'ok', result.message


def install_update(instance: Instance, source: str, sha256: str | None, echo=print,
                   collect=probes.collect) -> tuple[bool, str]:
    """Terminal-Aufruf mit derselben Umschalt- und Rückweglogik."""
    result = _perform(instance, source, sha256, None, Deps(collect=collect), echo)
    return result.outcome == 'ok', result.message


def run_update(instance: Instance, source: str | None, sha256: str | None, console, deps: Deps | None = None,
               *, release_id: str | None = None, yes: bool = False) -> Result:
    """Worker-Einstieg. Console-Hooks laufen im aufrufenden Thread.

    Vor dem Aufruf bei Bedarf sudo freigeben. Abbruch ist kooperativ bis zum
    Umschalten. Danach laufen Neustart und gegebenenfalls Rückweg zu Ende.
    """
    deps = deps or Deps()
    console.last_result = None
    progress = console.progress(False)
    phases = (('umschalten', 'dienst_neustart', 'bereit') if release_id is not None
              else tuple(key for key in STEPS if key != 'rueckweg'))

    def step(key):
        console.step(STEPS[key], key=key)
        if key in phases:
            index = phases.index(key)
            progress(index + (key == 'bereit'), len(phases))

    try:
        if release_id is None:
            source = resolve_source(source)
        prefix_of(instance)
        _check_cancelled(deps)
        title = f'Auf Version {release_id} umschalten?' if release_id is not None else 'Update installieren?'
        lines = ([f'Archiv: {source}'] if release_id is None else []) + ['Der Werkbankdienst wird neu gestartet.']
        if not yes and not console.confirm(title, lines, None, deps=deps):
            raise _Cancelled('Update abgebrochen.')
        _check_cancelled(deps)
        if needs_root(instance):
            result = _privileged(instance, source, sha256, release_id, deps, console.line, step)
        else:
            result = _perform(instance, source, sha256, release_id, deps, console.line, step)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        result = Result('cancelled' if isinstance(error, _Cancelled) else 'failed',
                        new_version=release_id, reason=str(error), message=str(error))
    finally:
        _notify(progress.finish)
    console.last_result = result
    if result.rollback_ok is False:
        _notify(console.loud, [result.message, result.reason or ''])
    else:
        level = {'ok': probes.OK, 'failed': probes.FAIL, 'blocked': probes.WARN, 'cancelled': probes.WARN}
        _notify(console.mark, level[result.outcome], result.message)
    return result


def _privileged(instance, source, sha256, release_id, deps, echo, step):
    options = {'config': instance.config, 'activate': release_id, 'sha256': sha256}
    if release_id is None and source is not None:
        options['source'] = os.path.abspath(source) if '://' not in source else source
    argv = [f'--{key}={value}' for key, value in options.items() if value is not None]
    python = Path(sys.executable)
    command = ['sudo', '-n', str(python.parent.resolve() / python.name), '-I', '-m', 'dispread.admin.update', *argv]
    result = None
    with tempfile.TemporaryFile(mode='w+t') as errors:
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                              text=True, encoding='utf-8', bufsize=1) as process:
            for line in process.stdout:
                event = json.loads(line)
                if 'step' in event:
                    step(event['step'])
                elif 'line' in event:
                    echo(event['line'])
                elif 'checkpoint' in event:
                    process.stdin.write('cancel\n' if deps.cancelled() else 'continue\n')
                    process.stdin.flush()
                elif 'result' in event:
                    result = Result(**event['result'])
            code = process.wait()
        if result is None or code != result.exit_code:
            errors.seek(0)
            detail = errors.read().strip()
            raise UpdateError(f'Update über sudo nicht abgeschlossen (Exit {code}). {detail}'.rstrip())
    return result


def _worker_main():
    """Interner sudo-Einstieg. Handshake erlaubt kooperativen Abbruch über die Pipe."""
    from .instance import discover

    parser = argparse.ArgumentParser()
    parser.add_argument('--config')
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--source')
    target.add_argument('--activate')
    parser.add_argument('--sha256')
    args = parser.parse_args()

    def send(**event):
        # Ein geschlossener Ausgabekanal darf nach dem Umschalten den Rückweg nicht verhindern.
        try:
            print(json.dumps(event), flush=True)
        except OSError:
            pass

    def cancelled():
        send(checkpoint=True)
        return sys.stdin.readline() != 'continue\n'

    # systemctl-Ausgaben gehören nicht in den strukturierten Ereignisstrom.
    deps = Deps(cancelled=cancelled, restart=partial(_restart_and_wait, output=sys.stderr))
    result = _perform(discover(args.config), args.source, args.sha256, args.activate, deps,
                      lambda text: send(line=text), lambda key: send(step=key))
    send(result=asdict(result))
    return result.exit_code


def versions(instance: Instance) -> dict:
    update = installer_module(instance, 'update')
    return update.releases(prefix_of(instance))


if __name__ == '__main__':
    raise SystemExit(_worker_main())
