"""Archive provenance must never be mistaken for a verified session roundtrip."""
import json
import os
import subprocess
import sys
import zipfile
from hashlib import sha256
from pathlib import Path

import pytest
from dispread_bridge_app import session_templates as templates

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / 'tests/fixtures/gsvmulti/session-templates'
ARCHIVE = ROOT / 'docs/quellen/gsvmulti-validation-2026-11-04.zip'
ORIGINAL_HASHES = {
    'uart-demo-11.ucf': '0880ab1c2406e4761624de904407060579d85ca8126ce411bdf31455734f2b4e',
    'uart-demo-14.ucf': 'f7ee09ad481d6d38612d54fda049f0d2d9be7d4d9d4f6a9e3b50a9dbb44c844c',
    'uart-demo-11-receiver.txt': '24617dc71f18f14ca4d261f00a00d66ce197f21a622ce44e4ebf95c07db3f7ba',
}


def test_archive_original_is_known_but_not_a_verified_template():
    evidence = templates.inspect_template(FIXTURES / 'uart-demo-11.ucf')
    assert evidence.template_id == 'uart-direct-demo-20261104-11'
    assert evidence.source_sha256 == ORIGINAL_HASHES['uart-demo-11.ucf']
    assert evidence.gsv_version is None
    assert evidence.allowed_fields == ()
    assert evidence.roundtrip_verified is False


def test_template_manifest_matches_original_hash():
    manifest = json.loads((FIXTURES / 'manifest.json').read_text())
    assert sha256(ARCHIVE.read_bytes()).hexdigest() == (
        'e7e6742acee9203ed0f1da251006e9c9bb9a8eb4c10f2ce06992512daf1ae5e3')
    with zipfile.ZipFile(ARCHIVE) as archive:
        for artifact in manifest['templates'] + manifest['recordings']:
            local = (FIXTURES / artifact['file']).read_bytes()
            assert sha256(local).hexdigest() == ORIGINAL_HASHES[artifact['file']]
            assert local == archive.read(artifact['archive_member'])
    assert len(templates.validate_manifest(FIXTURES / 'manifest.json')) == 2


@pytest.mark.parametrize('filename', ['uart-demo-11.ucf', 'uart-demo-14.ucf'])
def test_roundtrip_filter_unit_scale_and_port_stays_blocked(filename):
    evidence = templates.inspect_template(FIXTURES / filename)
    with pytest.raises(templates.SessionTemplateError, match='automatic_export_blocked'):
        evidence.require_automatic_export()
    assert evidence.allowed_fields == ()
    assert not evidence.roundtrip_verified


def test_unknown_file_is_unsupported_even_with_ucf_extension(tmp_path):
    path = tmp_path / 'session.ucf'
    path.write_bytes((FIXTURES / 'uart-demo-11.ucf').read_bytes() + b'\r\n')
    with pytest.raises(templates.SessionTemplateError, match='unknown_template'):
        templates.inspect_template(path)


@pytest.mark.parametrize('version', ['9.99-unknown', '2.03 Pro'])
def test_unknown_gsv_version_is_unsupported(tmp_path, version):
    manifest = json.loads((FIXTURES / 'manifest.json').read_text())
    manifest['templates'][0]['gsv_version'] = version
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    with pytest.raises(templates.SessionTemplateError, match='unsupported_manifest'):
        templates.validate_manifest(path)


@pytest.mark.parametrize('change', [
    {'allowed_fields': ['ComNr']},
    {'roundtrip_verified': True},
    {'file': '../uart-demo-11.ucf'},
    {'source_sha256': '0' * 64},
])
def test_unproven_manifest_claims_are_unsupported(tmp_path, change):
    manifest = json.loads((FIXTURES / 'manifest.json').read_text())
    manifest['templates'][0].update(change)
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    with pytest.raises(templates.SessionTemplateError, match='unsupported_manifest'):
        templates.validate_manifest(path)


def test_changed_fixture_bytes_fail_manifest_validation(tmp_path):
    for source in FIXTURES.iterdir():
        if source.is_file():
            (tmp_path / source.name).write_bytes(source.read_bytes())
    (tmp_path / 'uart-demo-11.ucf').write_bytes(b'not the archive original')
    with pytest.raises(templates.SessionTemplateError, match='source_hash_mismatch'):
        templates.validate_manifest(tmp_path / 'manifest.json')


@pytest.mark.parametrize('kind', ['duplicate', 'missing'])
def test_manifest_requires_complete_unique_archive_catalog(tmp_path, kind):
    manifest = json.loads((FIXTURES / 'manifest.json').read_text())
    if kind == 'duplicate':
        manifest['templates'].append(manifest['templates'][0])
    else:
        manifest['templates'].pop()
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    with pytest.raises(templates.SessionTemplateError, match='unsupported_manifest'):
        templates.validate_manifest(path)


def test_manifest_does_not_follow_fixture_symlinks(tmp_path):
    for source in FIXTURES.iterdir():
        if source.is_file():
            (tmp_path / source.name).write_bytes(source.read_bytes())
    (tmp_path / 'uart-demo-11.ucf').unlink()
    try:
        (tmp_path / 'uart-demo-11.ucf').symlink_to(FIXTURES / 'uart-demo-11.ucf')
    except OSError as error:
        if getattr(error, 'winerror', None) == 1314:
            pytest.skip('Windows account lacks symlink privilege')
        raise
    with pytest.raises(templates.SessionTemplateError, match='unsupported_manifest'):
        templates.validate_manifest(tmp_path / 'manifest.json')


def test_probe_reports_blocked_export_without_loading_windows_or_qt():
    result = subprocess.run(
        [sys.executable, str(ROOT / 'windows/bridge/probes/inspect_session.py'),
         str(FIXTURES / 'uart-demo-11.ucf')],
        capture_output=True, text=True, check=False,
        env={**os.environ, 'PYTHONPATH': os.pathsep.join([
            str(ROOT / 'src'), str(ROOT / 'windows/bridge/src')])},
    )
    assert result.returncode == 2, result.stderr
    report = json.loads(result.stdout)
    assert report['gsv_version'] is None
    assert report['allowed_fields'] == []
    assert report['roundtrip_verified'] is False
    assert report['automatic_export_allowed'] is False
    assert report['provisional'] is True
    assert report['time_claim'] is False
    assert report['status'] == 'automatic_export_blocked'


def test_probe_rejects_unknown_template(tmp_path):
    path = tmp_path / 'unknown.ucf'
    path.write_text('[UserDevice]\nComNo = 10\n')
    result = subprocess.run(
        [sys.executable, str(ROOT / 'windows/bridge/probes/inspect_session.py'), str(path)],
        capture_output=True, text=True, check=False,
        env={**os.environ, 'PYTHONPATH': str(ROOT / 'windows/bridge/src')},
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)['status'] == 'unknown_template'
