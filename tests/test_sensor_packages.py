"""Sensorpakete beschreiben die eingefrorene Anzeige und lehnen fehlerhafte Daten ab."""
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from dispread.layout import CharLayout
from dispread.live import DEFAULT_TEMPLATES_SHA256, RELEASE_NOTICE
from dispread.live.setup import DEFAULT_TARGET_SIZE, GSV2AS_EMPTY_CELLS, LATTICE_GRID
from dispread.setup_checks import GRID, TARGET_SIZE

PACKAGE = Path(__file__).resolve().parents[1] / "src/dispread/data/sensors/gsv2as-161a"
SHA256 = "6f20dec4f558e98be41203d0ab48eb4788d16e02c1350313a740c25cc03f693a"


def test_default_package_matches_live_reader():
    from dispread.sensors import DEFAULT_SENSOR_ID, get_sensor, templates

    sensor = get_sensor(DEFAULT_SENSOR_ID)
    assert sensor.profile_ref == "gsv2as-161a@1"
    assert (sensor.status, sensor.device_id, sensor.unit) == ("verified", "gsv-sensor-161a", "mV/V")
    assert sensor.release_notice == RELEASE_NOTICE
    assert sensor.templates_path == PACKAGE / "templates.json"
    assert hashlib.sha256(sensor.templates_path.read_bytes()).hexdigest() == sensor.templates.sha256 == SHA256
    assert sensor.templates.sha256 == DEFAULT_TEMPLATES_SHA256
    assert "+" in templates(sensor).mean
    display = sensor.display
    layout = CharLayout(grid=GRID, unit=sensor.unit)
    assert display.empty_cells == GSV2AS_EMPTY_CELLS
    assert display.blank_cells == layout.blank_cells
    assert display.classified_cells == layout.classified_cells
    assert display.format.rule == layout.format_id
    assert (display.format.digits, display.format.sign_chars, display.format.leading_zero_rule) == (
        6, ("+",), "gsv2as_leading_zero_v2")
    assert (display.anchor.cell, display.anchor.char) == (0, "+")
    assert display.lattice.target_size == TARGET_SIZE == DEFAULT_TARGET_SIZE
    for grid in (GRID, LATTICE_GRID):
        assert display.cells == grid.n_cells
        for field in ("left", "pitch", "top", "bottom"):
            assert getattr(display.lattice, field) == getattr(grid, field)


def change(directory, filename, key, value):
    path = directory / filename
    data = json.loads(path.read_text())
    obj = data
    *parents, name = key.split(".")
    for parent in parents:
        obj = obj[parent]
    if value is ...:
        del obj[name]
    else:
        obj[name] = value
    path.write_text(json.dumps(data))


@pytest.mark.parametrize(("filename", "key", "value", "match"), [
    ("sensor.json", "extra", 1, "extra"),
    ("display.json", "lattice.extra", 1, "extra"),
    ("sensor.json", "unit", ..., "unit"),
    ("display.json", "anchor.char", ..., "char"),
    ("sensor.json", "schema", True, "schema"),
    ("display.json", "schema", 2, "schema"),
    ("sensor.json", "aliases", "GSV", "aliases"),
    ("sensor.json", "version", "1", "version"),
    ("sensor.json", "status", "Verified", "status"),
    ("sensor.json", "status", "verified ", "status"),
    ("sensor.json", "status", "freigegeben", "status"),
    ("sensor.json", "templates.sha256", "123", "sha256"),
    *[("sensor.json", "templates.file", path, "file") for path in
      ("x/t.json", "..", "../t.json", "/t.json", "a..b", r"x\t.json", "C:t.json")],
    ("sensor.json", "id", "anderes-geraet", "Verzeichnis"),
    ("sensor.json", "id", "-ungueltig", "id"),
    ("display.json", "roles.unit", [8, 9], "Rolle"),
    ("display.json", "roles.blank", [16], "Zelle"),
    ("display.json", "roles.unit", [True], "unit"),
    ("display.json", "roles.number", [1, 3, 4, 5, 6, 7], "zusammen"),
    ("display.json", "lattice.target_size", [400], "target_size"),
    ("display.json", "lattice.target_size", [401, 160], r"cells \* pitch"),
    ("display.json", "format.rule", "unbekannt", "rule"),
    ("display.json", "format.sign_chars", ["-"], "anchor.char"),
    ("display.json", "format.digits", 8, "format.digits"),
    ("display.json", "family", "unbekannt", "family"),
    ("display.json", "polarity", "unbekannt", "polarity"),
    ("display.json", "anchor.char", "-", "char"),
])
def test_invalid_package(tmp_path, filename, key, value, match):
    from dispread.sensors import load_definition

    directory = shutil.copytree(PACKAGE, tmp_path / PACKAGE.name)
    change(directory, filename, key, value)
    with pytest.raises(ValueError, match=match):
        load_definition(directory)


def test_derived_cells_follow_roles(tmp_path):
    from dispread.sensors import load_definition

    directory = shutil.copytree(PACKAGE, tmp_path / PACKAGE.name)
    change(directory, "display.json", "roles.separator", [])
    change(directory, "display.json", "roles.blank", [15, 8, 14, 13])
    display = load_definition(directory).display
    assert display.empty_cells == (8, 13, 14, 15)
    assert display.classified_cells == 8
    assert display.blank_cells == (15, 8, 14, 13)


def test_template_checksum_and_symlink(tmp_path):
    from dispread.sensors import load_definition, templates

    directory = shutil.copytree(PACKAGE, tmp_path / PACKAGE.name)
    template = directory / "templates.json"
    original = template.rename(tmp_path / "outside.json")
    template.symlink_to(original)
    with pytest.raises(ValueError, match="Verzeichnis|Symlink"):
        load_definition(directory)
    template.unlink()
    template.write_text("{}")
    with pytest.raises(ValueError, match="Pruefsumme"):
        templates(load_definition(directory))


def test_registry_rejects_external_verified_and_duplicate_ids(tmp_path):
    from dispread.sensors import get_sensor, registry

    directory = shutil.copytree(PACKAGE, tmp_path / "labor-01")
    change(directory, "sensor.json", "id", directory.name)
    change(directory, "sensor.json", "aliases", ["Labor 01"])
    with pytest.raises(ValueError, match="verified"):
        registry([tmp_path])
    change(directory, "sensor.json", "status", "provisional")
    assert get_sensor("labor-01", [tmp_path]).templates_path.parent == directory
    with pytest.raises(ValueError, match="unbekannt|Unbekannt"):
        get_sensor("anderer-sensor", [tmp_path])
    directory = directory.rename(tmp_path / PACKAGE.name)
    change(directory, "sensor.json", "id", PACKAGE.name)
    with pytest.raises(ValueError, match="[Dd]oppelt"):
        registry([tmp_path])


def test_registry_collects_errors_and_keeps_bundled_sensor_available(tmp_path):
    from dispread.sensors import DEFAULT_SENSOR_ID, get_sensor, registry, registry_with_errors

    for name in (".alt", "__pycache__", "fremd", "defekt"):
        (tmp_path / name).mkdir()
    (tmp_path / "defekt/sensor.json").write_text("{")
    missing = tmp_path / "fehlt"
    extra = [tmp_path, missing]
    sensors, errors = registry_with_errors(extra)
    assert sensors[DEFAULT_SENSOR_ID] == get_sensor(DEFAULT_SENSOR_ID, extra)
    assert len(errors) == 3
    assert all(any(name in error for error in errors) for name in ("fremd", "defekt", "Suchwurzel"))
    with pytest.raises(ValueError, match="Suchwurzel"):
        registry([missing])


def test_registry_rejects_duplicate_aliases(tmp_path):
    from dispread.sensors import get_sensor, registry, registry_with_errors

    for name in ("labor-01", "labor-02"):
        directory = shutil.copytree(PACKAGE, tmp_path / name)
        change(directory, "sensor.json", "id", name)
        change(directory, "sensor.json", "status", "draft")
        change(directory, "sensor.json", "aliases", ["Labor"])
    sensors, errors = registry_with_errors([tmp_path])
    assert get_sensor().id in sensors
    assert len(errors) == 1
    with pytest.raises(ValueError, match="Doppelter Sensoralias"):
        registry([tmp_path])


def test_connection_is_optional_and_checked(tmp_path):
    from dispread.sensors import load_definition

    assert load_definition(PACKAGE).connection == 'rs232'         # Referenzgerät GSV-2AS
    directory = shutil.copytree(PACKAGE, tmp_path / PACKAGE.name)
    data = json.loads((directory / 'sensor.json').read_text(encoding='utf-8'))
    data.pop('connection')
    (directory / 'sensor.json').write_text(json.dumps(data), encoding='utf-8')
    assert load_definition(directory).connection == 'unknown'     # ältere Pakete bleiben gültig
    change(directory, 'sensor.json', 'connection', 'wlan')
    with pytest.raises(ValueError, match='connection'):
        load_definition(directory)
