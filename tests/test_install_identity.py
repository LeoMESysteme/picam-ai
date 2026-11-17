"""Installer identity provisioning exports the same public browser/bridge certificate."""

import json

import pytest
from cryptography import x509

from dispread.bridge import identity as identity_module
from dispread.bridge.identity import DeviceIdentity
from dispread.workbench.cli import main


@pytest.fixture(autouse=True)
def fixed_hardware_id(monkeypatch):
    monkeypatch.setattr(identity_module, 'local_hardware_id', lambda: 'fixture-hardware')


def test_cli_provisions_and_exports_public_certificate(tmp_path, capsys):
    directory = tmp_path / 'identity'
    exported = tmp_path / 'cert.pem'
    assert main(['bridge', 'identity', '--directory', str(directory), '--provision',
                 '--host', 'pi.example', '--export-certificate', str(exported)]) == 0
    identity = DeviceIdentity.load(directory, 'fixture-hardware')
    assert exported.read_text() == identity.certificate_pem
    assert exported.stat().st_mode & 0o777 == 0o600
    assert 'PRIVATE KEY' not in exported.read_text()
    assert json.loads(capsys.readouterr().out)['certificate_sha256'] == identity.fingerprint
    names = x509.load_pem_x509_certificate(exported.read_bytes()).extensions.get_extension_for_class(
        x509.SubjectAlternativeName).value
    assert names.get_values_for_type(x509.DNSName) == ['pi.example']


@pytest.mark.parametrize('target_kind', ['file', 'symlink', 'missing-parent'])
def test_cli_export_never_replaces_existing_or_creates_parent(tmp_path, target_kind):
    directory = tmp_path / 'identity'
    identity = DeviceIdentity.load_or_create(directory, 'fixture-hardware')
    if target_kind == 'missing-parent':
        exported = tmp_path / 'absent/cert.pem'
    else:
        exported = tmp_path / 'cert.pem'
        if target_kind == 'symlink':
            target = tmp_path / 'target.pem'
            target.write_text('keep target')
            exported.symlink_to(target)
        else:
            exported.write_text('keep certificate')
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    assert main(['bridge', 'identity', '--directory', str(directory), '--export-certificate', str(exported)]) == 1
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before
    assert DeviceIdentity.load(directory, 'fixture-hardware').fingerprint == identity.fingerprint
    if target_kind == 'file':
        assert exported.read_text() == 'keep certificate'
    elif target_kind == 'symlink':
        assert exported.is_symlink() and target.read_text() == 'keep target'
    else:
        assert not exported.parent.exists()


def test_cli_exports_existing_certificate_without_provisioning(tmp_path):
    directory = tmp_path / 'identity'
    identity = DeviceIdentity.load_or_create(directory, 'fixture-hardware')
    exported = tmp_path / 'cert.pem'
    assert main(['bridge', 'identity', '--directory', str(directory), '--export-certificate', str(exported)]) == 0
    assert exported.read_text() == identity.certificate_pem


def test_host_without_explicit_provision_is_rejected_without_writes(tmp_path):
    directory = tmp_path / 'identity'
    assert main(['bridge', 'identity', '--directory', str(directory), '--host', 'pi.example']) == 1
    assert not directory.exists()


def test_cli_invalid_host_fails_before_any_write(tmp_path):
    directory = tmp_path / 'identity'
    exported = tmp_path / 'cert.pem'
    assert main(['bridge', 'identity', '--directory', str(directory), '--provision',
                 '--host', 'https://pi.example', '--export-certificate', str(exported)]) == 1
    assert not directory.exists() and not exported.exists()
