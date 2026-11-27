"""Sensor-Marktplatz: Schalter, Katalog, Installation, Bundle-Sicherheit, Einreichung (ohne Netz).

Alle HTTP-Aufrufe laufen ueber einen Fake-`opener`; es gibt keine echten Netzzugriffe.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import stat
import tarfile
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from dispread.admin import sensor_cli
from dispread.sensors import _PACKAGE_ROOT, catalog, features, load_definition
from dispread.workbench.config import parse_config

BUNDLED = _PACKAGE_ROOT / 'gsv2as-161a'
RAW = catalog.CATALOG_RAW_BASE + 'sensors/'
API = f'{catalog.FORGEJO_BASE}/api/v1/repos/{catalog.FORGEJO_REPO}'
TOKEN = 'tok_' + 'a1b2c3d4e5f6' * 3


# ----------------------------------------------------------------- Hilfen
class Resp:
    def __init__(self, data, status=200):
        self.data, self.status = data, status

    def read(self, n=-1):
        return self.data if n < 0 else self.data[:n]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Net:
    """Fake-Opener: Routen (Methode, URL ohne Query) -> Bytes/JSON/Fehler/Funktion."""

    def __init__(self):
        self.routes, self.calls = {}, []

    def on(self, method, url, value):
        self.routes[(method, url)] = value

    def __call__(self, req, timeout=None):
        self.calls.append(req)
        value = self.routes.get((req.get_method(), req.full_url.split('?')[0]))
        if value is None:
            raise urllib.error.HTTPError(req.full_url, 404, 'nicht gefunden', {}, None)
        if callable(value):
            value = value(req)
        if isinstance(value, BaseException):
            raise value
        if not isinstance(value, bytes | bytearray):
            value = json.dumps(value).encode()
        return Resp(bytes(value))

    def methods(self):
        return [(c.get_method(), c.full_url.split('?')[0].removeprefix(API)) for c in self.calls]


def unreachable():
    return urllib.error.URLError('Name or service not known')


@pytest.fixture
def instance(tmp_path):
    (tmp_path / 'workbench').mkdir()
    return SimpleNamespace(data=str(tmp_path / 'workbench'), live_data=None, config=None, kind='dev', unit=None,
                           sensor='gsv2as-161a', sensor_assistant=False)


def make_package(root: Path, sensor_id='astra-1', *, status='provisional', version=1, name='Astra Messbox') -> Path:
    directory = root / sensor_id
    directory.mkdir(parents=True)
    data = json.loads((BUNDLED / 'sensor.json').read_text(encoding='utf-8'))
    data.update(id=sensor_id, status=status, version=version, aliases=[], display_name=name,
                device_id=sensor_id, manufacturer='Astra')
    (directory / 'sensor.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    for filename in ('display.json', 'templates.json', 'README.md'):
        shutil.copyfile(BUNDLED / filename, directory / filename)
        (directory / filename).chmod(0o644)
    return directory


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entry_for(directory: Path, **over) -> dict:
    definition = load_definition(directory)
    files = {name: digest(directory / name) for name in catalog.BUNDLE_FILES if (directory / name).is_file()}
    entry = {'id': definition.id, 'version': definition.version, 'status': definition.status,
             'display_name': definition.display_name, 'manufacturer': definition.manufacturer,
             'aliases': list(definition.aliases), 'unit': definition.unit, 'family': 'hd44780_5x8',
             'polarity': 'dark_on_light', 'example': '', 'files': files, 'submitted': '2026-11-27T10:00:00Z',
             'checks': {'runs': 0}}
    entry.update(over)
    return entry


def serve_catalog(net: Net, remote_root: Path, entries):
    index = {'schema': 1, 'generated': '2026-11-27T10:00:00Z', 'sensors': entries}
    net.on('GET', RAW + 'index.json', index)
    for entry in entries:
        for name in entry['files']:
            path = remote_root / entry['id'] / name
            if path.is_file():
                net.on('GET', f"{RAW}{entry['id']}/{name}", path.read_bytes())
    return index


def tar_bytes(members) -> bytes:
    """members: (name, daten, typ, linkname)."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w:gz') as archive:
        for name, data, kind, link in members:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.linkname = link
            info.size = len(data) if kind == tarfile.REGTYPE else 0
            archive.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
    return raw.getvalue()


def package_members(directory: Path):
    return [(name, (directory / name).read_bytes(), tarfile.REGTYPE, '') for name in catalog.BUNDLE_FILES]


def write_bundle(tmp_path, members, name='b.tar.gz') -> Path:
    path = tmp_path / name
    path.write_bytes(tar_bytes(members))
    return path


# ----------------------------------------------------------------- Schalter
def test_feature_is_off_by_default_and_toggles_in_dev_config(instance):
    assert features.enabled(instance) is False
    with pytest.raises(features.FeatureDisabled, match='Einstellungen'):
        features.require(instance)
    result = features.set_enabled(instance, True)
    assert result['changed'] and result['sensor_assistant'] is True and result['restart_required'] is False
    assert features.enabled(instance) is True and instance.sensor_assistant is True
    config = Path(result['config'])
    assert config.name == 'sensor-config.toml' and '[features]' in config.read_text()
    assert features.set_enabled(instance, True)['changed'] is False
    features.set_enabled(instance, False)
    assert features.enabled(instance) is False


def test_feature_in_instance_config_keeps_other_sections(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('[workbench]\nport = 8081\n\n[live]\nsensor = "gsv2as-161a"\n', encoding='utf-8')
    instance = SimpleNamespace(config=str(config), kind='portable', data=None, unit=None)
    features.set_enabled(instance, True)
    text = config.read_text()
    assert 'port = 8081' in text and 'sensor = "gsv2as-161a"' in text and 'sensor_assistant = true' in text
    assert features.enabled(instance) is True


@pytest.mark.parametrize('section', ['[features]\nsensor_assistant = "ja"', '[features]\nunbekannt = true',
                                     '[features]\nsensor_assistant = 1'])
def test_features_section_is_strict(section, tmp_path):
    import tomllib

    with pytest.raises(ValueError, match='features'):
        parse_config(tomllib.loads('[workbench]\nport = 8080\n' + section), tmp_path)


def test_broken_config_means_off(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('[features]\nsensor_assistant = "ja"\n', encoding='utf-8')
    assert features.enabled(SimpleNamespace(config=str(config), kind='portable', data=None)) is False


# ----------------------------------------------------------------- CLI
def parse(*argv):
    parser = argparse.ArgumentParser()
    sensor_cli.add_commands(parser)
    return parser.parse_args(list(argv))


def test_gated_commands_refuse_when_off_but_list_and_check_bundle_work(instance, tmp_path):
    for argv in (('propose', '--run', str(tmp_path), '--id', 'x1'), ('onboard', '--run', str(tmp_path)),
                 ('catalog', 'pull', 'astra-1'), ('catalog', 'submit', 'astra-1', '--consent'),
                 ('catalog', 'pending'), ('catalog', 'token', 'set')):
        with pytest.raises(features.FeatureDisabled, match='aktivieren'):
            sensor_cli.dispatch(parse(*argv), instance)
    assert any(item['id'] == 'gsv2as-161a' for item in sensor_cli.dispatch(parse('list'), instance))
    assert sensor_cli.dispatch(parse('catalog', 'token', 'status'), instance)['present'] is False
    bundle = write_bundle(tmp_path, package_members(make_package(tmp_path / 'p')))
    assert sensor_cli.dispatch(parse('catalog', 'check-bundle', str(bundle)), instance)['ok'] is True
    assert sensor_cli.main(parse('catalog', 'pull', 'astra-1'), instance) == 2


def test_features_command_switches(instance):
    assert sensor_cli.dispatch(parse('features'), instance) == {'sensor_assistant': False}
    sensor_cli.dispatch(parse('features', 'on'), instance)
    assert sensor_cli.dispatch(parse('features', 'status'), instance) == {'sensor_assistant': True}


def test_agent_cannot_use_catalog_or_features(instance):
    tools = sensor_cli._AgentTools(SimpleNamespace(path=Path('.')), instance, {'connection': {}}, None)
    for argv in (['sensor', 'catalog', 'refresh'], ['sensor', 'features', 'on']):
        with pytest.raises(ValueError, match='nicht verfügbar'):
            tools.execute(argv, deadline=1e12)


# ----------------------------------------------------------------- Index
def good_index(tmp_path):
    return {'schema': 1, 'generated': 'x', 'sensors': [entry_for(make_package(tmp_path / 'r'))]}


def test_validate_index_accepts_good_and_rejects_bad(tmp_path):
    index = good_index(tmp_path)
    assert catalog.validate_index(index) is index

    def mutate(fn):
        copy = json.loads(json.dumps(index))
        fn(copy)
        return copy

    bad = [
        mutate(lambda d: d.update(schema=2)),
        mutate(lambda d: d.update(extra=1)),
        mutate(lambda d: d['sensors'][0].update(id='../x')),
        mutate(lambda d: d['sensors'][0].update(version=0)),
        mutate(lambda d: d['sensors'][0].update(status='draft')),
        mutate(lambda d: d['sensors'][0]['files'].update({'evil.sh': 'a' * 64})),
        mutate(lambda d: d['sensors'][0]['files'].update({'sensor.json': 'xyz'})),
        mutate(lambda d: d['sensors'][0].update(surprise=True)),
        mutate(lambda d: d['sensors'][0].update(checks={'runs': -1})),
        mutate(lambda d: d['sensors'][0].update(example='x' * 17)),
        mutate(lambda d: d['sensors'].append(dict(d['sensors'][0]))),
        [], 'text',
    ]
    for item in bad:
        with pytest.raises(ValueError):
            catalog.validate_index(item)


def test_fetch_index_caches_and_enforces_limits(instance, tmp_path):
    net = Net()
    index = serve_catalog(net, tmp_path / 'r', [entry_for(make_package(tmp_path / 'r'))])
    assert catalog.cached_index(instance) is None
    assert catalog.fetch_index(instance, opener=net) == index
    assert catalog.cached_index(instance) == index
    assert net.calls[0].full_url == RAW + 'index.json' and net.calls[0].full_url.startswith('https://')

    big = Net()
    big.on('GET', RAW + 'index.json', b' ' * (catalog.MAX_INDEX_BYTES + 1))
    with pytest.raises(ValueError, match='größer'):
        catalog.fetch_index(instance, opener=big)
    broken = Net()
    broken.on('GET', RAW + 'index.json', b'{"schema": 1')
    with pytest.raises(ValueError, match='nicht lesbar'):
        catalog.fetch_index(instance, opener=broken)
    assert catalog.cached_index(instance) == index  # Fehlversuche lassen den Cache stehen


def test_fetch_index_unreachable_is_clear(instance):
    net = Net()
    net.on('GET', RAW + 'index.json', unreachable())
    with pytest.raises(catalog.CatalogUnreachable, match='nicht erreichbar'):
        catalog.fetch_index(instance, opener=net)


def test_search_matches_name_manufacturer_alias_id_unit():
    entries = [{'id': 'astra-1', 'display_name': 'Astra Messbox', 'manufacturer': 'Astra GmbH', 'unit': 'N',
                'aliases': ['AST-1']},
               {'id': 'gsv2as-161a', 'display_name': 'GSV-2AS', 'manufacturer': 'ME', 'unit': 'mV/V',
                'aliases': []}]
    assert catalog.search(entries, '') == entries
    assert [e['id'] for e in catalog.search(entries, 'ast-1')] == ['astra-1']
    assert [e['id'] for e in catalog.search(entries, 'gmbh messbox')] == ['astra-1']
    assert [e['id'] for e in catalog.search(entries, 'mv/v')] == ['gsv2as-161a']
    assert [e['id'] for e in catalog.search(entries, '161A')] == ['gsv2as-161a']
    assert catalog.search(entries, 'nix') == []


# ----------------------------------------------------------------- Installieren
def test_pull_installs_as_provisional_even_if_catalog_says_verified(instance, tmp_path):
    remote = tmp_path / 'remote'
    package = make_package(remote, status='verified')
    net = Net()
    serve_catalog(net, remote, [entry_for(package)])
    result = catalog.pull(instance, 'astra-1', opener=net)
    assert result['status'] == 'provisional' and result['sensor_id'] == 'astra-1'
    installed = load_definition(Path(result['directory']))
    assert installed.status == 'provisional' and installed.id == 'astra-1'
    assert catalog.installed(instance)['astra-1']['version'] == 1
    assert not any(p.name.startswith('.katalog-') for p in Path(result['directory']).parent.iterdir())
    from dispread.sensors import get_sensor

    assert get_sensor('astra-1', instance=instance).status == 'provisional'


def test_pull_refuses_wrong_sha_and_leaves_nothing(instance, tmp_path):
    remote = tmp_path / 'remote'
    package = make_package(remote)
    entry = entry_for(package)
    entry['files']['display.json'] = '0' * 64
    net = Net()
    serve_catalog(net, remote, [entry])
    with pytest.raises(ValueError, match='Prüfsumme'):
        catalog.pull(instance, 'astra-1', opener=net)
    root = Path(instance.data).parent / 'sensors'
    assert not (root / 'astra-1').exists()
    assert catalog.installed(instance) == {}


def test_pull_refuses_oversized_file(instance, tmp_path):
    remote = tmp_path / 'remote'
    entry = entry_for(make_package(remote))
    net = Net()
    serve_catalog(net, remote, [entry])
    net.on('GET', f'{RAW}astra-1/templates.json', b'0' * (catalog.MAX_FILE_BYTES + 1))
    with pytest.raises(ValueError, match='größer'):
        catalog.pull(instance, 'astra-1', opener=net)


def test_pull_refuses_bundled_existing_and_alias_collision(instance, tmp_path):
    remote = tmp_path / 'remote'
    package = make_package(remote)
    net = Net()
    serve_catalog(net, remote, [entry_for(package)])
    catalog.pull(instance, 'astra-1', opener=net)
    with pytest.raises(ValueError, match='bereits vorhanden'):
        catalog.pull(instance, 'astra-1', opener=net)
    marker = Path(instance.data).parent / 'sensors' / 'astra-1' / 'marker'
    marker.write_text('alt')
    assert catalog.pull(instance, 'astra-1', overwrite=True, opener=net)['status'] == 'provisional'
    assert not marker.exists()

    clash = make_package(tmp_path / 'remote2', 'zweiter', name='Zweiter')
    data = json.loads((clash / 'sensor.json').read_text())
    data['aliases'] = ['astra-1']
    (clash / 'sensor.json').write_text(json.dumps(data))
    net2 = Net()
    serve_catalog(net2, tmp_path / 'remote2', [entry_for(clash)])
    with pytest.raises(ValueError, match='kollidiert'):
        catalog.pull(instance, 'zweiter', opener=net2)

    bundled = make_package(tmp_path / 'remote3', 'gsv2as-161a', status='verified')
    net3 = Net()
    serve_catalog(net3, tmp_path / 'remote3', [entry_for(bundled)])
    with pytest.raises(ValueError, match='mitgeliefert'):
        catalog.pull(instance, 'gsv2as-161a', opener=net3)


def test_pull_unknown_id_and_bad_id(instance, tmp_path):
    net = Net()
    serve_catalog(net, tmp_path / 'r', [entry_for(make_package(tmp_path / 'r'))])
    with pytest.raises(ValueError, match='nicht im Katalog'):
        catalog.pull(instance, 'nope-1', opener=net)
    for bad in ('../x', 'A', 'a/b', ''):
        with pytest.raises(ValueError, match='Ungültige'):
            catalog.pull(instance, bad, opener=net)


def test_pull_falls_back_to_cached_index_when_offline(instance, tmp_path):
    remote = tmp_path / 'remote'
    entry = entry_for(make_package(remote))
    net = Net()
    serve_catalog(net, remote, [entry])
    catalog.fetch_index(instance, opener=net)
    net.on('GET', RAW + 'index.json', unreachable())
    assert catalog.pull(instance, 'astra-1', opener=net)['status'] == 'provisional'


# ----------------------------------------------------------------- Bundle
def local_package(instance, **kw):
    return make_package(Path(instance.data).parent / 'sensors', **kw)


def test_bundle_is_deterministic_and_only_allows_package_files(instance):
    directory = local_package(instance)
    (directory / 'notes.txt').write_text('privat')
    first = catalog.bundle(instance, 'astra-1')
    data = first.read_bytes()
    assert catalog.bundle(instance, 'astra-1').read_bytes() == data
    with tarfile.open(first) as archive:
        assert sorted(archive.getnames()) == sorted(catalog.BUNDLE_FILES)
        assert all(m.isreg() and m.mtime == 0 and m.uid == 0 for m in archive.getmembers())
    assert len(data) <= catalog.MAX_BUNDLE_BYTES
    assert catalog.check_bundle(first) == {'ok': True, 'sensor_id': 'astra-1', 'version': 1,
                                           'display_name': 'Astra Messbox', 'errors': []}


def test_bundle_refuses_bundled_unknown_and_non_provisional(instance):
    with pytest.raises(ValueError, match='Kein lokales'):
        catalog.bundle(instance, 'gsv2as-161a')
    with pytest.raises(ValueError, match='Kein lokales'):
        catalog.bundle(instance, 'nope-1')
    local_package(instance, sensor_id='entwurf-1', status='draft')
    with pytest.raises(ValueError, match='vorläufig'):
        catalog.bundle(instance, 'entwurf-1')


@pytest.mark.parametrize('label,members', [
    ('Pfad nach oben', lambda d: package_members(d) + [('../evil', b'x', tarfile.REGTYPE, '')]),
    ('absoluter Pfad', lambda d: package_members(d) + [('/etc/passwd', b'x', tarfile.REGTYPE, '')]),
    ('fremde Datei', lambda d: package_members(d) + [('run.sh', b'x', tarfile.REGTYPE, '')]),
    ('Unterordner', lambda d: [('sub/sensor.json', b'{}', tarfile.REGTYPE, '')]),
    ('Symlink', lambda d: [m for m in package_members(d) if m[0] != 'README.md']
     + [('README.md', b'', tarfile.SYMTYPE, '/etc/passwd')]),
    ('Hardlink', lambda d: [m for m in package_members(d) if m[0] != 'README.md']
     + [('README.md', b'', tarfile.LNKTYPE, 'sensor.json')]),
    ('Verzeichnis', lambda d: package_members(d) + [('x', b'', tarfile.DIRTYPE, '')]),
    ('doppelt', lambda d: package_members(d) + [('sensor.json', b'{}', tarfile.REGTYPE, '')]),
    ('Datei fehlt', lambda d: [m for m in package_members(d) if m[0] != 'display.json']),
    ('Übergröße', lambda d: [('sensor.json', b'0' * (catalog.MAX_FILE_BYTES + 1), tarfile.REGTYPE, '')]),
])
def test_check_bundle_rejects_unsafe_archives(label, members, tmp_path):
    directory = make_package(tmp_path / 'p')
    path = write_bundle(tmp_path, members(directory))
    result = catalog.check_bundle(path)
    assert result['ok'] is False and result['errors'], label
    assert not (tmp_path / 'evil').exists() and not Path('/etc/passwd.x').exists()


def test_check_bundle_rejects_content_problems(tmp_path):
    def build(name, mutate):
        directory = make_package(tmp_path / name)
        mutate(directory)
        return catalog.check_bundle(write_bundle(tmp_path, package_members(directory), f'{name}.tar.gz'))

    wrong_sha = build('a', lambda d: (d / 'templates.json').write_bytes((d / 'templates.json').read_bytes() + b' '))
    assert not wrong_sha['ok']

    def verified(d):
        data = json.loads((d / 'sensor.json').read_text())
        data['status'] = 'verified'
        (d / 'sensor.json').write_text(json.dumps(data))

    assert 'provisional' in build('b', verified)['errors'][0]

    def alias(d):
        data = json.loads((d / 'sensor.json').read_text())
        data['aliases'] = ['GSV-2AS']
        (d / 'sensor.json').write_text(json.dumps(data))

    assert 'mitgelieferten' in build('c', alias)['errors'][0]

    def polarity(d):
        data = json.loads((d / 'display.json').read_text())
        data['polarity'] = 'bright_on_dark'
        (d / 'display.json').write_text(json.dumps(data))

    assert not build('d', polarity)['ok']

    def bad_id(d):
        data = json.loads((d / 'sensor.json').read_text())
        data['id'] = '../x'
        (d / 'sensor.json').write_text(json.dumps(data))

    assert not build('e', bad_id)['ok']

    def binary_readme(d):
        (d / 'README.md').write_bytes(b'abc\x00def')

    assert 'README' in build('f', binary_readme)['errors'][0]

    def broken_json(d):
        (d / 'display.json').write_text('{')

    assert not build('g', broken_json)['ok']


def test_check_bundle_not_a_gzip_and_missing_file(tmp_path):
    junk = tmp_path / 'junk.tar.gz'
    junk.write_bytes(b'kein archiv')
    assert catalog.check_bundle(junk)['ok'] is False
    assert catalog.check_bundle(tmp_path / 'fehlt.tar.gz')['ok'] is False
    big = tmp_path / 'gross.tar.gz'
    big.write_bytes(b'0' * (catalog.MAX_BUNDLE_BYTES + 1))
    assert 'größer' in catalog.check_bundle(big)['errors'][0]


def test_check_bundle_decompression_bomb_is_stopped(tmp_path):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w:gz') as archive:
        for name in ('sensor.json', 'display.json', 'templates.json', 'README.md'):
            data = b'0' * catalog.MAX_FILE_BYTES
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    path = tmp_path / 'bomb.tar.gz'
    path.write_bytes(raw.getvalue())
    assert path.stat().st_size < catalog.MAX_BUNDLE_BYTES  # klein gepackt
    # vier Dateien an der Grenze sind erlaubt groß, aber kein gültiges Paket
    assert catalog.check_bundle(path)['ok'] is False


def test_check_bundle_version_rule_with_index(tmp_path):
    directory = make_package(tmp_path / 'p', version=2)
    path = write_bundle(tmp_path, package_members(directory))
    older = {'schema': 1, 'generated': 'x', 'sensors': [entry_for(make_package(tmp_path / 'q', version=2))]}
    result = catalog.check_bundle(path, index=older)
    assert not result['ok'] and 'nicht höher' in result['errors'][0]
    older['sensors'][0]['version'] = 1
    assert catalog.check_bundle(path, index=older)['ok'] is True


# ----------------------------------------------------------------- Token
def test_token_roundtrip_is_private_and_never_in_messages(instance):
    status = catalog.token_status(instance)
    assert status['present'] is False
    net = Net()
    net.on('GET', f'{catalog.FORGEJO_BASE}/api/v1/repos/{catalog.FORGEJO_REPO}/labels', [{'id': 1, 'name': catalog.SUBMISSION_LABEL}])
    result = catalog.save_token(instance, TOKEN + '\n', opener=net)
    assert result == {'ok': True, 'label_present': True}
    request = net.calls[0]
    assert request.get_header('Authorization') == f'token {TOKEN}'
    path = Path(catalog.token_status(instance)['path'])
    assert stat.S_IMODE(path.stat().st_mode) == 0o600 and TOKEN in path.read_text()
    assert catalog.token_status(instance)['present'] is True and TOKEN not in json.dumps(catalog.token_status(instance))
    assert catalog.delete_token(instance) == {'deleted': True} and not path.exists()
    assert catalog.delete_token(instance) == {'deleted': False}


def test_token_rejected_unreachable_and_malformed_are_not_stored(instance):
    net = Net()
    net.on('GET', f'{catalog.FORGEJO_BASE}/api/v1/repos/{catalog.FORGEJO_REPO}/labels', urllib.error.HTTPError('u', 401, 'x', {}, None))
    with pytest.raises(ValueError, match='lehnt das Token ab') as error:
        catalog.save_token(instance, TOKEN, opener=net)
    assert TOKEN not in str(error.value)
    net.on('GET', f'{catalog.FORGEJO_BASE}/api/v1/repos/{catalog.FORGEJO_REPO}/labels', unreachable())
    with pytest.raises(catalog.CatalogUnreachable, match='Firmennetz'):
        catalog.save_token(instance, TOKEN, opener=net)
    for bad in ('', 'kurz', 'mit leerzeichen ' + 'x' * 20, 'a\nb' + 'x' * 20):
        with pytest.raises(ValueError, match='Format'):
            catalog.save_token(instance, bad, opener=net)
    assert catalog.token_status(instance)['present'] is False


# ----------------------------------------------------------------- Einreichen
def forgejo(net, *, label=True):
    net.on('GET', f'{API}/labels', [{'id': 7, 'name': catalog.SUBMISSION_LABEL}] if label else [])
    net.on('POST', f'{API}/issues', {'number': 12})
    net.on('POST', f'{API}/issues/12/assets', {'id': 1})
    net.on('POST', f'{API}/issues/12/labels', [])


def with_token(instance):
    path = Path(catalog.token_status(instance)['path'])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TOKEN + '\n')


def test_submit_requires_consent_and_token(instance):
    local_package(instance)
    net = Net()
    forgejo(net)
    with pytest.raises(ValueError, match='Einwilligung'):
        catalog.submit(instance, 'astra-1', consent=False, opener=net)
    with pytest.raises(ValueError, match='Token'):
        catalog.submit(instance, 'astra-1', consent=True, opener=net)
    assert net.calls == [] and catalog.pending(instance) == []


def test_submit_sends_issue_asset_then_label(instance):
    local_package(instance)
    with_token(instance)
    net = Net()
    forgejo(net)
    result = catalog.submit(instance, 'astra-1', consent=True, opener=net)
    assert result == {'sensor_id': 'astra-1', 'issue_number': 12,
                      'issue_url': f'{catalog.FORGEJO_BASE}/{catalog.FORGEJO_REPO}/issues/12'}
    # Das Label kommt zuletzt, damit die CI erst mit vorhandenem Anhang startet.
    assert net.methods() == [('GET', '/labels'), ('POST', '/issues'), ('POST', '/issues/12/assets'),
                             ('POST', '/issues/12/labels')]
    issue = json.loads(net.calls[1].data)
    assert issue['title'] == 'Sensor-Einreichung: Astra Messbox (astra-1)' and 'labels' not in issue
    assert 'keine Bilder' in issue['body'] and 'zugestimmt' in issue['body']
    assert json.loads(net.calls[3].data) == {'labels': [7]}
    asset = net.calls[2]
    assert 'multipart/form-data' in asset.get_header('Content-type') and b'name="attachment"' in asset.data
    assert all(c.get_header('Authorization') == f'token {TOKEN}' for c in net.calls)
    assert catalog.pending(instance) == []
    box = Path(catalog.token_status(instance)['path']).parent / 'outbox'
    assert list(box.iterdir()) == []


def test_submit_unreachable_keeps_package_in_outbox_and_retry_resumes(instance):
    local_package(instance)
    with_token(instance)
    net = Net()
    net.on('GET', f'{API}/labels', unreachable())
    with pytest.raises(catalog.CatalogUnreachable, match='Firmennetz oder über Tailscale'):
        catalog.submit(instance, 'astra-1', consent=True, opener=net)
    queue = catalog.pending(instance)
    assert [(q['sensor_id'], q['version']) for q in queue] == [('astra-1', 1)]
    # Ohne Netz bleibt es ausstehend, ohne Absturz.
    again = catalog.submit_pending(instance, opener=net)
    assert again[0]['ok'] is False and 'Firmennetz' in again[0]['error']
    # Fehlschlag nach dem Issue: Wiederholung legt kein zweites Issue an.
    flaky = Net()
    forgejo(flaky)
    flaky.on('POST', f'{API}/issues/12/assets', urllib.error.HTTPError('u', 500, 'x', {}, None))
    first = catalog.submit_pending(instance, opener=flaky)
    assert first[0]['ok'] is False and 'HTTP 500' in first[0]['error']
    assert catalog.pending(instance)[0]['issue_number'] == 12
    ok = Net()
    forgejo(ok)
    done = catalog.submit_pending(instance, opener=ok)
    assert done[0]['ok'] is True and done[0]['issue_number'] == 12
    assert ('POST', '/issues') not in ok.methods() and catalog.pending(instance) == []


def test_submit_errors_do_not_leak_token(instance):
    local_package(instance)
    with_token(instance)
    net = Net()
    net.on('GET', f'{API}/labels', urllib.error.HTTPError('u', 401, 'x', {}, None))
    with pytest.raises(ValueError, match='lehnt das Token ab') as error:
        catalog.submit(instance, 'astra-1', consent=True, opener=net)
    assert TOKEN not in str(error.value)
    missing = Net()
    forgejo(missing, label=False)
    with pytest.raises(ValueError, match='Label'):
        catalog.submit(instance, 'astra-1', consent=True, opener=missing)


def test_submit_pending_without_token_reports_error(instance):
    local_package(instance)
    with_token(instance)
    net = Net()
    net.on('GET', f'{API}/labels', unreachable())
    with pytest.raises(catalog.CatalogUnreachable):
        catalog.submit(instance, 'astra-1', consent=True, opener=net)
    catalog.delete_token(instance)
    result = catalog.submit_pending(instance, opener=net)
    assert result[0]['ok'] is False and 'Token' in result[0]['error']


def test_default_opener_never_follows_redirects():
    opener_calls = []

    class Spy:
        def __call__(self, req, timeout=None):
            opener_calls.append(req)
            raise urllib.error.HTTPError(req.full_url, 302, 'moved', {}, None)

    with pytest.raises(catalog.HttpStatus):
        catalog._get(RAW + 'index.json', timeout=1, limit=10, opener=Spy())
    with pytest.raises(ValueError, match='HTTPS'):
        catalog._get('http://example.invalid/x', timeout=1, limit=10, opener=Spy())
    assert len(opener_calls) == 1


def test_no_stray_files_in_local_root_after_failed_operations(instance, tmp_path):
    remote = tmp_path / 'remote'
    entry = entry_for(make_package(remote))
    entry['files']['sensor.json'] = '1' * 64
    net = Net()
    serve_catalog(net, remote, [entry])
    with pytest.raises(ValueError):
        catalog.pull(instance, 'astra-1', opener=net)
    root = Path(instance.data).parent / 'sensors'
    assert [p.name for p in root.iterdir() if not p.name.startswith('.pakete')] == []
    assert os.listdir(root.parent / 'sensor-catalog') == ['index.json']


# ----------------------------------------------------------------- Index-Skript und CLI wie in der CI
def run_script(sensors: Path):
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    return subprocess.run([sys.executable, str(root / 'scripts/sensor-catalog-index.py'), '--sensors', str(sensors)],
                          capture_output=True, text=True, check=False, env={**os.environ, 'PYTHONPATH': str(root / 'src')})


def test_index_script_builds_validates_and_is_idempotent(tmp_path):
    sensors = tmp_path / 'sensors'
    make_package(sensors, 'astra-1')
    make_package(sensors, 'beta-2', name='Beta')
    make_package(sensors, 'entwurf-1', status='draft')
    done = run_script(sensors)
    assert done.returncode == 0, done.stderr
    index = catalog.validate_index(json.loads((sensors / 'index.json').read_text()))
    assert [e['id'] for e in index['sensors']] == ['astra-1', 'beta-2']
    assert index['sensors'][0]['files']['sensor.json'] == digest(sensors / 'astra-1' / 'sensor.json')
    before = (sensors / 'index.json').read_text()
    assert run_script(sensors).returncode == 0 and (sensors / 'index.json').read_text() == before
    (sensors / 'astra-1' / 'README.md').write_text('geaendert')
    assert run_script(sensors).returncode == 0
    changed = json.loads((sensors / 'index.json').read_text())
    assert changed['sensors'][0]['files']['README.md'] != index['sensors'][0]['files']['README.md']
    assert changed['sensors'][1]['submitted'] == index['sensors'][1]['submitted']  # unveraenderte Pakete bleiben


def test_ci_check_bundle_command_without_feature_or_instance(tmp_path):
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    good = write_bundle(tmp_path, package_members(make_package(tmp_path / 'p')))
    bad = write_bundle(tmp_path, [('x.sh', b'x', tarfile.REGTYPE, '')], 'bad.tar.gz')
    env = {**os.environ, 'PYTHONPATH': str(root / 'src'), 'HOME': str(tmp_path), 'XDG_CONFIG_HOME': str(tmp_path)}
    env.pop('PICAM_CONFIG', None)
    run = lambda path: subprocess.run([sys.executable, '-m', 'dispread.admin.cli', 'sensor', 'catalog',  # noqa: E731
                                       'check-bundle', str(path)], capture_output=True, text=True, env=env, cwd=tmp_path)
    ok, rejected = run(good), run(bad)
    assert ok.returncode == 0 and json.loads(ok.stdout)['ok'] is True, ok.stderr
    assert rejected.returncode == 1 and json.loads(rejected.stdout)['ok'] is False


def test_submission_workflow_never_interpolates_issue_text():
    text = (Path(__file__).resolve().parents[1] / '.github/workflows/sensor-submission.yml').read_text()
    code = [line for line in text.splitlines() if not line.lstrip().startswith('#')]
    expressions = [line.strip() for line in code if '${{' in line]
    # Ausdruecke stehen nur in env:/runs-on, nie in Skriptzeilen, und nie Titel/Text des Issues.
    assert all(line.split(':', 1)[0] in {'SERVER_URL', 'REPO', 'ISSUE', 'SENSOR_BOT_TOKEN', 'SUBMITTER', 'AUTHOR'} for line in expressions)
    assert 'issue.title' not in text and 'issue.body' not in text
    assert 'sensors/' in text and 'sensor-einreichung' in text and 'check-bundle' in text
