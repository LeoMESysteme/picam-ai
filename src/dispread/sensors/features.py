"""Optionale, experimentelle Funktionen: KI-Sensoreinrichtung und Sensor-Marktplatz.

Der Schalter liegt in der Instanzkonfiguration unter `[features] sensor_assistant = true|false`
(Vorgabe aus). Dev-Instanzen ohne Konfigurationsdatei nutzen dieselbe Datei wie `live.sensor`
(`sensor-config.toml`). Die Sensorauswahl und der Messpfad mit dem mitgelieferten Paket
haengen nicht von diesem Schalter ab.
"""

from __future__ import annotations

from pathlib import Path

HINT = 'KI-Sensoreinrichtung und Marktplatz sind aus – in den Einstellungen aktivieren (Experimentell).'


class FeatureDisabled(ValueError):
    """Eine Funktion hinter dem Schalter wurde aufgerufen, waehrend er aus ist."""


def _path(instance) -> tuple[Path | None, bool]:
    """(Konfigurationsdatei, ist-Dev-Datei ohne eigene Konfiguration)."""
    from dispread.workbench.config import dev_sensor_config

    config = getattr(instance, 'config', None)
    if config:
        return Path(config), False
    if getattr(instance, 'kind', None) == 'dev' and getattr(instance, 'data', None):
        return dev_sensor_config(instance.data), True
    return None, False


def enabled(instance) -> bool:
    """Ist der Schalter an? Liest die Datei frisch; unlesbar oder fehlend heisst aus."""
    from dispread.workbench.config import load_features

    path, _ = _path(instance)
    if path is not None and path.is_file():
        try:
            return load_features(path)['sensor_assistant']
        except (OSError, ValueError):
            return False
    return getattr(instance, 'sensor_assistant', False) is True


def require(instance) -> None:
    if not enabled(instance):
        raise FeatureDisabled(HINT)


def set_enabled(instance, value: bool) -> dict:
    """Schalter setzen. Rueckgabe: sensor_assistant, config, changed, restart_required, message."""
    from dispread.admin import configedit

    if type(value) is not bool:
        raise ValueError('Schalter braucht true oder false')
    path, dev = _path(instance)
    if path is None:
        raise ValueError('Keine Instanzkonfiguration gefunden. --config PFAD angeben.')
    if dev:
        path.parent.mkdir(parents=True, exist_ok=True)
    before = enabled(instance)
    try:
        updated = configedit.propose_features(path, value, dev_data=instance.data if dev else None)
        if not path.exists() or path.read_text(encoding='utf-8') != updated:
            configedit.apply(path, updated, create=dev)
    except PermissionError as error:
        state = 'on' if value else 'off'
        raise PermissionError(f'{path} ist nicht schreibbar. Für eine Systeminstanz im Terminal: '
                              f'sudo picam --config {path} sensor features {state}') from error
    if hasattr(instance, 'sensor_assistant'):
        instance.sensor_assistant = value
    word = 'aktiviert' if value else 'deaktiviert'
    # Konsole und CLI lesen den Schalter bei jedem Aufruf neu; kein Dienst haelt ihn im Speicher.
    return {'sensor_assistant': value, 'config': str(path), 'changed': before != value,
            'restart_required': False,
            'message': f'KI-Sensoreinrichtung und Marktplatz {word}.'}
