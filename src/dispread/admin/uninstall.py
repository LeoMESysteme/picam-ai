"""Schreibfreie Deinstallationsvorschau für eine installierte Instanz."""

from pathlib import Path

from .instance import Instance
from .update import installer_module


def installer_argv(instance: Instance, *, purge_data: bool = False, remove_fastfetch_package: bool = False,
                   unit_dir: Path | None = None, link: Path | None = None) -> list[str]:
    """Argumente für ``install.sh --uninstall`` (Plan und Ausführung) zur aktuellen Installation."""
    if instance.kind not in ('system', 'user', 'portable') or not instance.root:
        raise ValueError('Deinstallation nur für eine installierte Werkbank.')
    release = Path(instance.root)
    if release.parent.name != 'releases':
        raise ValueError(f'{release} liegt nicht in einem releases/-Verzeichnis')
    if instance.problem:
        raise ValueError(instance.problem)
    if instance.data and Path(instance.data).name != 'workbench':
        raise ValueError(f'Datenpfad {instance.data} passt nicht zum Layout des Installers.')
    data = Path(instance.data).parent if instance.data else None
    runtime = Path(instance.socket).parent if instance.kind == 'portable' and instance.socket else None
    argv = ['--uninstall', '--mode', instance.kind, '--prefix', str(release.parent.parent)]
    for key, value in (('data', data), ('config', instance.config), ('runtime', runtime),
                       ('unit-dir', unit_dir), ('link', link)):
        if value is not None:
            argv.extend([f'--{key}', str(value)])
    if purge_data:
        argv.append('--purge-data')
    if remove_fastfetch_package:
        argv.append('--remove-fastfetch-package')
    return argv


def plan_uninstall(instance: Instance, *, purge_data: bool = False,
                   remove_fastfetch_package: bool = False, unit_dir: Path | None = None,
                   link: Path | None = None) -> dict:
    """Derselbe Plan wie bei `install.sh --uninstall --json`, für die aktuelle Installation."""
    argv = installer_argv(instance, purge_data=purge_data, remove_fastfetch_package=remove_fastfetch_package,
                          unit_dir=unit_dir, link=link)
    installer = installer_module(instance, 'uninstall')
    return installer.plan_from_args(installer.parser().parse_args(argv))


def describe(instance: Instance, plan: dict) -> dict:
    """Anzeigezeilen des Plans (``remove``, ``keep``, ``notes``, ``needs_root``, ``service``)."""
    return installer_module(instance, 'uninstall').describe(plan)
