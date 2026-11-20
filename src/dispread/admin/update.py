"""``picam update``: neue Version daneben vorbereiten, umschalten, neu starten.

Ablauf: Laufsperre prüfen → neue Version unter ``releases/<id>`` vorbereiten
(Dateien, eigene venv, Selbsttest) → Laufsperre erneut prüfen → ``current``
umschalten → Dienst neu starten → auf HTTPS warten. Antwortet die neue
Version nicht, schaltet picam auf die vorige zurück und startet sie neu.
Daten, Konfiguration, Identität und Kalibrierung bleiben unberührt.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

from . import probes, service
from .instance import Instance


class UpdateError(ValueError):
    pass


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


def sudo_command(argv: list[str]) -> list[str]:
    return ['sudo', sys.executable, '-m', 'dispread.admin.cli', *argv]


def _restart_and_wait(instance: Instance, echo) -> bool:
    command = probes.systemctl(instance) + ['restart', instance.unit]
    echo('$ ' + ' '.join(command))
    if subprocess.call(command) != 0:
        return False
    echo(f'Warte auf {instance.url} …')
    return service.wait_until_ready(instance)


def switch(instance: Instance, release_id: str, echo=print, collect=probes.collect) -> tuple[bool, str]:
    """Auf eine vorbereitete Version umschalten und neu starten; bei Fehlschlag zurück."""
    update = installer_module(instance, 'update')
    prefix = prefix_of(instance)
    blocker = collect(instance, include_setup=False).stop_blocker
    if blocker:
        return False, f'Umschalten gesperrt: {blocker}. Später: picam update --activate {release_id}'
    result = update.activate(prefix, release_id)
    echo(f'Aktiv: {result["current"]} (vorher {result["previous"]})')
    if _restart_and_wait(instance, echo):
        return True, f'Version {release_id} läuft, {instance.url} antwortet.'
    echo(f'Version {release_id} antwortet nicht – zurück auf {result["previous"]}.')
    update.activate(prefix, result['previous'])
    if _restart_and_wait(instance, echo):
        return False, (f'Update auf {release_id} fehlgeschlagen, {result["previous"]} läuft wieder. '
                       'Protokoll: picam logs')
    return False, 'Update fehlgeschlagen und Rückweg antwortet nicht. Protokoll: picam logs'


def install_update(instance: Instance, source: str, sha256: str | None, echo=print,
                   collect=probes.collect) -> tuple[bool, str]:
    update = installer_module(instance, 'update')
    prefix = prefix_of(instance)
    blocker = collect(instance, include_setup=False).stop_blocker
    if blocker:
        return False, f'Update gesperrt: {blocker}'
    prepared = update.prepare(prefix, source, sha256, progress=lambda text: echo('· ' + text))
    echo(f'Vorbereitet: {prepared["release_id"]} in {prepared["path"]}')
    return switch(instance, prepared['release_id'], echo=echo, collect=collect)


def versions(instance: Instance) -> dict:
    update = installer_module(instance, 'update')
    return update.releases(prefix_of(instance))
