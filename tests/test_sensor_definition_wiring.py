"""Paketwerte im Lesepfad und Weiterbetrieb bestehender Konfigurationen."""

import shutil
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from dispread.admin.instance import discover
from dispread.admin.probes import fact_templates
from dispread.charcells import CharGrid
from dispread.layout import CharLayout
from dispread.live import DEFAULT_TEMPLATES, DEFAULT_TEMPLATES_SHA256, RELEASE_NOTICE, setup
from dispread.live.service import DEVICE_ID
from dispread.live.session import LiveConfig
from dispread.ocr.dotmatrix import FORMAT_RULES, DotMatrixReader, parse_gsv2as
from dispread.sensors import DEFAULT_SENSOR_ID, get_sensor
from dispread.setup_checks import BLANK_CELLS, GRID, TARGET_SIZE
from dispread.setup_overlays import GRID as OVERLAY_GRID
from dispread.workbench.config import apply_config


def _load(path):
    return apply_config(Namespace(command='serve', config=path), argv=[]).live_config


def test_live_defaults_come_from_sensor_package():
    definition = get_sensor(DEFAULT_SENSOR_ID)
    display = definition.display
    assert setup.N_CELLS == display.cells
    assert setup.GSV2AS_EMPTY_CELLS == BLANK_CELLS == display.empty_cells
    assert setup.DEFAULT_TARGET_SIZE == TARGET_SIZE == display.lattice.target_size
    assert setup.LATTICE_GRID == GRID == OVERLAY_GRID == CharGrid.from_display(display)
    assert (DEFAULT_TEMPLATES, DEFAULT_TEMPLATES_SHA256) == (definition.templates_path, definition.templates.sha256)
    assert (DEVICE_ID, RELEASE_NOTICE) == (definition.device_id, definition.release_notice)
    assert FORMAT_RULES[display.format.rule] is parse_gsv2as

    assert CharLayout.from_definition(definition) == CharLayout(grid=GRID, unit='mV/V')
    profile = SimpleNamespace(resolution_ok=True, confirmed_by='Bediener', grid=CharGrid(16, 0, 24, 14, 150))
    assert CharLayout.from_profile(profile, definition=definition) == CharLayout(
        grid=profile.grid, unit=definition.unit)
    assert CharLayout.from_profile(profile, 'mV/V') == CharLayout.from_profile(profile, definition=definition)

    config = LiveConfig()
    assert config.sensor == 'gsv2as-161a'
    assert config.definition == definition
    assert config.unit == definition.unit
    assert config.templates == definition.templates_path
    assert config.templates_sha256 == '6f20dec4f558e98be41203d0ab48eb4788d16e02c1350313a740c25cc03f693a'
    DotMatrixReader.from_file(config.templates, config.templates_sha256)


@pytest.mark.parametrize('state', ['vorhanden', 'fehlt', 'verändert'])
def test_legacy_template_config_after_update(tmp_path, caplog, monkeypatch, state):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'packaging'))
    from picam_installer.update import activate

    prefix = tmp_path / 'installation'
    release = prefix / 'releases' / 'nach-update'
    previous = prefix / 'releases' / 'vor-update'
    previous.mkdir(parents=True)
    (prefix / 'current').symlink_to(previous, target_is_directory=True)
    legacy = release / 'src/dispread/data/templates-stufe2c-2026-09-30.json'
    legacy.parent.mkdir(parents=True)
    old_template = previous / legacy.relative_to(release)
    old_template.parent.mkdir(parents=True)
    shutil.copyfile(DEFAULT_TEMPLATES, old_template)
    if state == 'vorhanden':
        shutil.copyfile(DEFAULT_TEMPLATES, legacy)
    elif state == 'verändert':
        legacy.write_text('{}')
    config_path = prefix / 'config.toml'
    old_path = prefix / 'current' / legacy.relative_to(release)
    original = f'[live]\ntemplates = "{old_path}"\n'
    config_path.write_text(original)
    (release / 'release.json').write_text('{}')
    python = release / '.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.touch()
    assert _load(config_path).templates == old_template
    assert activate(prefix, release.name) == {'current': release.name, 'previous': previous.name}
    assert config_path.read_text() == original

    config = _load(config_path)
    admin_fact = fact_templates(discover(str(config_path)))
    assert config.sensor == DEFAULT_SENSOR_ID
    assert config.templates == (DEFAULT_TEMPLATES if state == 'fehlt' else legacy)
    if state == 'verändert':
        assert admin_fact.value == 'verändert'
        with pytest.raises(ValueError, match='Pruefsumme'):
            DotMatrixReader.from_file(config.templates, config.templates_sha256)
    else:
        assert admin_fact.value == 'geprüft'
        DotMatrixReader.from_file(config.templates, config.templates_sha256)
    if state == 'fehlt':
        assert 'Paketvorlage' in caplog.text
        assert any(name == 'Paketvorlage verwendet' for name, _ in admin_fact.detail)


def test_explicit_sensor_without_templates(tmp_path):
    path = tmp_path / 'config.toml'
    path.write_text(f'[live]\nsensor = "{DEFAULT_SENSOR_ID}"\n')
    assert _load(path).templates == DEFAULT_TEMPLATES
    assert fact_templates(discover(str(path))).value == 'geprüft'
    path.write_text('[live]\nsensor = "unbekannt"\n')
    with pytest.raises(ValueError, match='Unbekannte Sensor-id'):
        _load(path)


def test_missing_unrelated_template_remains_an_error(tmp_path):
    path = tmp_path / 'config.toml'
    path.write_text('[live]\ntemplates = "andere-vorlage.json"\n')
    config = _load(path)
    assert config.templates == Path(tmp_path, 'andere-vorlage.json')
    assert fact_templates(discover(str(path))).value == 'fehlt'
    with pytest.raises(FileNotFoundError, match="andere-vorlage.json"):
        DotMatrixReader.from_file(config.templates, config.templates_sha256)
