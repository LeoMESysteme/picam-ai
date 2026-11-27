"""Datenpakete fuer Sensoren laden und anhand ihrer Kennung finden."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from dataclasses import fields
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING

from .definitions import (
    CHAR_NUMBER_FORMAT_RULE,
    GSV2AS_FORMAT_RULE,
    AnchorDefinition,
    DisplayDefinition,
    FormatDefinition,
    LatticeDefinition,
    RolesDefinition,
    SensorDefinition,
    TemplateRef,
)

if TYPE_CHECKING:
    from dispread.ocr.dotmatrix_templates import Templates

DEFAULT_SENSOR_ID = "gsv2as-161a"
_PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "data" / "sensors"


def _unique_keys(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f"Doppelter Schluessel {key!r}")
        data[key] = value
    return data


CONNECTIONS = ("rs232", "usb", "none", "unknown")


def _object(data, model, name, *, derived=(), optional=()):
    if not isinstance(data, dict):
        raise ValueError(f"{name} muss ein Objekt sein")
    keys = {field.name for field in fields(model)}.difference(derived)
    if unknown := data.keys() - keys:
        raise ValueError(f"{name}: unbekannte Schluessel {sorted(unknown)}")
    if missing := keys - data.keys() - set(optional):
        raise ValueError(f"{name}: Pflichtfelder fehlen {sorted(missing)}")
    return data


def _read(path, model, *, derived=(), optional=()):
    if path.is_symlink():
        raise ValueError(f"Symlink als Paketdatei unzulaessig: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path} nicht als JSON lesbar: {exc}") from exc
    _object(data, model, path.name, derived=derived, optional=optional)
    if type(data["schema"]) is not int or data["schema"] != 1:
        raise ValueError(f"{path.name}: schema {data['schema']!r} wird nicht unterstuetzt")
    return data


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} muss eine nichtleere Zeichenkette sein")
    return value


def _integer(value, name):
    if type(value) is not int:
        raise ValueError(f"{name} muss eine Ganzzahl sein")
    return value


def _positive(value, name):
    if _integer(value, name) < 1:
        raise ValueError(f"{name} muss positiv sein")
    return value


def _number(value, name):
    if type(value) in (float, int):
        try:
            if math.isfinite(value):
                return float(value)
        except OverflowError:
            pass
    raise ValueError(f"{name} muss eine endliche Zahl sein")


def _sequence(value, name, check):
    if not isinstance(value, list):
        raise ValueError(f"{name} muss eine Liste sein")
    return tuple(check(item, name) for item in value)


def _supported(value, name, choices):
    if _text(value, name) not in choices:
        raise ValueError(f"{name} {value!r} wird in P0 noch nicht unterstuetzt")
    return value


def _lattice(data):
    data = _object(data, LatticeDefinition, "lattice")
    size = _sequence(data["target_size"], "target_size", _positive)
    if len(size) != 2:
        raise ValueError("target_size braucht Breite und Hoehe")
    lattice = LatticeDefinition(**{key: _number(data[key], key) for key in ("left", "pitch", "top", "bottom")},
                                target_size=size)
    if lattice.pitch <= 0 or lattice.bottom <= lattice.top:
        raise ValueError("lattice braucht positiven Zellabstand und Hoehe")
    return lattice


def _roles(data, cells):
    data = _object(data, RolesDefinition, "roles")
    roles = RolesDefinition(**{key: _sequence(value, key, _integer) for key, value in data.items()})
    used = set()
    for key in data:
        for cell in getattr(roles, key):
            if not 0 <= cell < cells:
                raise ValueError(f"Zelle {cell} der Rolle {key} liegt ausserhalb des Displays")
            if cell in used:
                raise ValueError(f"Zelle {cell} ist in den Rollen mehrfach belegt")
            used.add(cell)
    classified = sorted(roles.sign + roles.number + roles.separator)
    if classified != list(range(len(classified))):
        raise ValueError("Klassifizierte Zellen muessen ab 0 zusammenhaengen")
    return roles


def _display(path):
    data = _read(path, DisplayDefinition)
    cells = _positive(data["cells"], "cells")
    roles = _roles(data["roles"], cells)
    fmt = _object(data["format"], FormatDefinition, "format", optional=("decimal", "min_digits"))
    lattice = _lattice(data["lattice"])
    rule = _supported(fmt["rule"], "format.rule", {GSV2AS_FORMAT_RULE, CHAR_NUMBER_FORMAT_RULE})
    anchor = None
    if data["anchor"] is not None or rule == GSV2AS_FORMAT_RULE:
        raw_anchor = _object(data["anchor"], AnchorDefinition, "anchor")
        cell = _integer(raw_anchor["cell"], "anchor.cell")
        if cell not in roles.sign:
            raise ValueError("anchor.cell muss eine Vorzeichenzelle sein")
        anchor = AnchorDefinition(_supported(raw_anchor["char"], "anchor.char", {"+"}), cell)
    format_definition = FormatDefinition(
        rule, _positive(fmt["digits"], "digits"), _sequence(fmt["sign_chars"], "sign_chars", _text),
        _text(fmt["leading_zero_rule"], "leading_zero_rule"),
        _supported(fmt.get("decimal", "point"), "format.decimal",
                   {"point"} if rule == GSV2AS_FORMAT_RULE else {"point", "none"}),
        _positive(fmt["min_digits"], "min_digits") if fmt.get("min_digits") is not None else None,
    )
    if anchor is not None and anchor.char not in format_definition.sign_chars:
        raise ValueError("anchor.char muss in format.sign_chars enthalten sein")
    if format_definition.digits > len(roles.number):
        raise ValueError("format.digits ist groesser als der Zahlenblock")
    if rule == CHAR_NUMBER_FORMAT_RULE:
        _validate_generic_display(data, roles, format_definition, anchor)
    if lattice.target_size[0] != cells * lattice.pitch:
        raise ValueError("lattice.target_size: Breite muss cells * pitch entsprechen")
    return DisplayDefinition(
        schema=data["schema"], family=_supported(data["family"], "family", {"hd44780_5x8"}),
        polarity=_supported(data["polarity"], "polarity", {"dark_on_light"}),
        cells=cells, rows=_positive(data["rows"], "rows"), lattice=lattice, roles=roles,
        anchor=anchor, format=format_definition,
    )



def _validate_generic_display(data, roles, fmt, anchor):
    if data["cells"] != 16 or data["rows"] != 1:
        raise ValueError("char_number_v1 braucht 16 Zellen in einer Zeile")
    if roles.sign + roles.number + roles.separator + roles.unit + roles.blank != tuple(range(16)):
        raise ValueError("Zellrollen muessen alle Zellen in Anzeigereihenfolge abdecken")
    if not roles.separator or not roles.unit:
        raise ValueError("Trennzellen und Einheit fehlen")
    if (bool(roles.sign) != bool(fmt.sign_chars) or set(fmt.sign_chars) - {"+", "-"}
            or len(set(fmt.sign_chars)) != len(fmt.sign_chars)):
        raise ValueError("Vorzeichenzellen und sign_chars passen nicht zusammen")
    if anchor is not None and (roles.sign != (0,) or fmt.sign_chars != ("+",)):
        raise ValueError("Plus-Anker braucht ein festes + in Zelle 0")
    if fmt.leading_zero_rule != "leading_spaces":
        raise ValueError("char_number_v1 erwartet leading_spaces")
    minimum = fmt.digits if fmt.min_digits is None else fmt.min_digits
    if not 1 <= minimum <= fmt.digits:
        raise ValueError("min_digits muss zwischen 1 und digits liegen")
    if fmt.decimal == "point" and (minimum < 2 or fmt.digits + 1 > len(roles.number)):
        raise ValueError("Zahlenblock braucht Platz fuer Ziffern und Dezimalpunkt")

def load_definition(directory: Path | str) -> SensorDefinition:
    """Liest die beiden Beschreibungen. Die Vorlagen werden bei Bedarf geladen."""
    directory = Path(directory).absolute()
    data = _read(directory / "sensor.json", SensorDefinition, derived=("display", "directory"),
                 optional=("connection",))
    sensor_id = _text(data["id"], "id")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", sensor_id):
        raise ValueError(f"Ungueltige Sensor-id {sensor_id!r}")
    if sensor_id != directory.name:
        raise ValueError(f"Sensor-id {sensor_id!r} passt nicht zum Verzeichnis {directory.name!r}")
    ref = _object(data["templates"], TemplateRef, "templates")
    filename = _text(ref["file"], "templates.file")
    if (filename == "." or ".." in filename or "/" in filename or "\\" in filename
            or "\x00" in filename or PureWindowsPath(filename).drive):
        raise ValueError("templates.file muss ein einfacher Dateiname im Paketverzeichnis sein")
    if (directory / filename).is_symlink():
        raise ValueError(f"Symlink als Vorlagendatei unzulaessig: {filename}")
    digest = _text(ref["sha256"], "templates.sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("templates.sha256 braucht 64 kleine Hexzeichen")
    return SensorDefinition(
        id=sensor_id, schema=data["schema"], version=_positive(data["version"], "version"),
        status=_supported(data["status"], "status", {"verified", "provisional", "draft"}),
        aliases=_sequence(data["aliases"], "aliases", _text), templates=TemplateRef(filename, digest),
        display=_display(directory / "display.json"), directory=directory,
        connection=_supported(data.get("connection", "unknown"), "connection", set(CONNECTIONS)),
        **{key: _text(data[key], key) for key in
           ("display_name", "manufacturer", "device_id", "unit", "release_notice")},
    )


def templates(definition: SensorDefinition) -> Templates:
    """Laedt die Zeichenvorlagen mit der im Paket angegebenen Pruefsumme."""
    from dispread.ocr.dotmatrix_templates import load_templates

    return load_templates(definition.templates_path, definition.templates.sha256)



def local_root(instance=None) -> Path:
    """Paketordner neben Werkbank- und Live-Daten derselben Instanz."""
    if isinstance(instance, dict):
        if instance.get("sensor_root") is not None:
            return Path(instance["sensor_root"]).resolve()
        data = instance.get("data")
        live_data = instance.get("live_data")
    else:
        data = getattr(instance, "data", None)
        live_data = getattr(instance, "live_data", None)
    if data or live_data:
        # Die üblichen Werkbank-/Live-Unterordner teilen einen Datenstamm.
        # Ein eigenständiges --data-Verzeichnis ist selbst der Datenstamm.
        anchor = Path(data or live_data).resolve()
        standard = "workbench" if data else "live"
        if anchor.name == standard:
            return anchor.parent / "sensors"
        return anchor / "sensors"
    if getattr(instance, "kind", None) == "system" or Path("/etc/picam/config.toml").is_file():
        return Path("/var/lib/picam/sensors")
    checkout = Path(__file__).resolve().parents[3]
    if (checkout / "pyproject.toml").is_file():
        return (checkout / "var").resolve() / "sensors"
    return Path("/var/lib/picam/sensors")


def bundled_sensors() -> Iterable[SensorDefinition]:
    """Mitgelieferte Vorlagengeber in stabiler Reihenfolge."""
    for directory in sorted(_PACKAGE_ROOT.iterdir()):
        if (directory / "sensor.json").is_file():
            yield load_definition(directory)

def registry_with_errors(
    extra_roots: Iterable[Path | str] = (), *, instance=None,
) -> tuple[dict[str, SensorDefinition], list[str]]:
    """Sammelt lesbare Pakete und meldet Fehler je Paket oder Suchwurzel."""
    sensors = {}
    names = set()
    errors = []
    automatic = local_root(instance)
    roots = dict.fromkeys(Path(root).absolute() for root in extra_roots)
    if automatic.exists():
        roots[automatic] = None
    for index, root in enumerate((_PACKAGE_ROOT, *roots)):
        try:
            directories = sorted(root.iterdir())
        except OSError as exc:
            errors.append(f"Sensorpaket-Suchwurzel {root} nicht lesbar: {exc}")
            continue
        for directory in directories:
            if directory.name.startswith(".") or directory.name == "__pycache__":
                continue
            try:
                if not directory.is_dir():
                    continue
                if directory.is_symlink():
                    raise ValueError("Symlink als Paketverzeichnis unzulaessig")
                sensor = load_definition(directory)
                if index and sensor.status == "verified":
                    raise ValueError(f"Lokales Sensorpaket {sensor.id!r} darf nicht 'verified' sein")
                if sensor.id in sensors:
                    raise ValueError(f"Doppelte Sensor-id {sensor.id!r}")
                package_names = (sensor.id, *sensor.aliases)
                if names.intersection(package_names) or len(set(package_names)) != len(package_names):
                    raise ValueError(f"Doppelter Sensoralias fuer {sensor.id!r}")
            except (OSError, ValueError) as exc:
                errors.append(f"{directory}: {exc}")
                continue
            sensors[sensor.id] = sensor
            names.update(package_names)
    return sensors, errors



def registry(extra_roots: Iterable[Path | str] = (), *, instance=None) -> dict[str, SensorDefinition]:
    """Liefert gueltige Pakete; ausdrueckliche Suchwurzeln bleiben strikt."""
    extra_roots = tuple(extra_roots)
    sensors, errors = registry_with_errors(extra_roots, instance=instance)
    if extra_roots and errors:
        raise ValueError("\n".join(errors))
    return sensors


def get_sensor(id: str = DEFAULT_SENSOR_ID, extra_roots: Iterable[Path | str] = (), *, instance=None) -> SensorDefinition:
    """Liefert das Paket zur Kennung oder meldet eine unbekannte Kennung."""
    if id == DEFAULT_SENSOR_ID:
        return load_definition(_PACKAGE_ROOT / DEFAULT_SENSOR_ID)
    sensors, errors = registry_with_errors(extra_roots, instance=instance)
    if id not in sensors:
        detail = f" ({'; '.join(errors)})" if errors else ""
        raise ValueError(f"Unbekannte Sensor-id {id!r}{detail}")
    return sensors[id]
