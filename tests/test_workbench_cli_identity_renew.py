"""Bridge identity renewal uses only isolated state and a fake service snapshot."""

import json
import stat
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509

from dispread.admin import probes
from dispread.admin.instance import Instance
from dispread.bridge.identity import DeviceIdentity, verify_certificate
from dispread.workbench import cli

HARDWARE = 'hardware-a'


@pytest.fixture
def bridge(tmp_path):
    directory = tmp_path / 'bridge'
    identity = DeviceIdentity.load_or_create(directory, HARDWARE, host='pi.example')
    export = tmp_path / 'cert.pem'
    export.write_text(identity.certificate_pem)
    export.chmod(0o600)
    config = tmp_path / 'config.toml'
    config.write_text(f'[workbench]\nbridge_directory = "{directory}"\ncert = "{export}"\n')
    instance = Instance('system', 'picam-werkbank.service', 'system', config=str(config),
                        bridge_directory=str(directory), host='pi.example', port=8443)
    return instance, identity, export


def snapshot(state):
    def collect(instance, **_):
        return probes.Snapshot(instance, {'dienst': probes.Fact('dienst', 'Dienst', probes.OK, 'läuft')},
                               {'state': state} if state else None, 0)
    return collect


def test_confirmed_renewal_preserves_id_key_and_san_even_after_expiry(bridge):
    instance, old, export = bridge
    path = old.directory / 'identity.json'
    saved = path.read_bytes()
    expired = datetime.now(UTC) + timedelta(days=370)
    result = cli.renew_bridge_identity(instance, confirmed=True, hardware_id=lambda: HARDWARE,
                                       collect=snapshot('idle'), now=expired)
    new_pem = export.read_text()
    cert = verify_certificate(new_pem, result.certificate_sha256, old.pi_id, now=expired)
    assert result.pi_id == old.pi_id
    assert result.previous_certificate_sha256 == old.fingerprint != result.certificate_sha256
    assert cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(
        x509.DNSName) == ['pi.example']
    assert datetime.fromisoformat(result.not_after_utc) - expired > timedelta(days=364)
    assert result.backup.read_bytes() == saved
    assert stat.S_IMODE(result.backup.stat().st_mode) == 0o600
    assert json.loads(path.read_bytes())['private_key_pem'] == json.loads(saved)['private_key_pem']
    assert json.loads(path.read_bytes())['certificate_pem'] == new_pem
    assert result.restart_required and result.repair_required
    assert result.profile_filename == 'pi.dispread'
    assert result.profile_url == 'https://pi.example:8443/live/bridge/profile'
    assert 'export-profile' in result.profile_export_command


@pytest.mark.parametrize(('confirmed', 'state', 'error'), [
    (False, 'idle', 'Bestätigung'), (True, 'running', 'gesperrt'), (True, None, 'unbekannt'),
])
def test_renewal_refuses_without_consent_or_when_unsafe(bridge, confirmed, state, error):
    instance, old, export = bridge
    existing = set(old.directory.iterdir())
    with pytest.raises(ValueError, match=error):
        cli.renew_bridge_identity(instance, confirmed=confirmed, hardware_id=lambda: HARDWARE,
                                  collect=snapshot(state))
    assert DeviceIdentity.load(old.directory, HARDWARE).fingerprint == old.fingerprint
    assert export.read_text() == old.certificate_pem
    assert set(old.directory.iterdir()) == existing


def test_cli_renews_and_prints_profile_guidance(bridge, monkeypatch, capsys, tmp_path):
    from dispread.admin import instance as admin_instance
    from dispread.bridge import identity

    instance, old, _ = bridge
    monkeypatch.setattr(admin_instance, 'discover', lambda _: instance)
    monkeypatch.setattr(identity, 'local_hardware_id', lambda: HARDWARE)
    monkeypatch.setattr(probes, 'collect', snapshot('idle'))
    argv = ['bridge', 'identity', '--renew', '--config', instance.config]
    assert cli.main(argv) != 0
    capsys.readouterr()
    assert cli.main([*argv, '--yes']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['previous_certificate_sha256'] == old.fingerprint
    assert result['restart_required']
    assert DeviceIdentity.load(old.directory, HARDWARE).fingerprint == result['certificate_sha256']
    monkeypatch.chdir(tmp_path)
    assert cli.main(result['profile_export_command'][3:]) == 0
    profile = json.loads((tmp_path / 'pi.dispread').read_text())
    assert profile['pi_id'] == old.pi_id
    assert profile['certificate_sha256'] == result['certificate_sha256']


def test_renewal_rechecks_the_run_before_publishing(bridge):
    instance, old, export = bridge
    states = iter(['idle', 'running'])
    existing = set(old.directory.iterdir())

    def collect(instance, **kwargs):
        return snapshot(next(states))(instance, **kwargs)

    with pytest.raises(ValueError, match='gesperrt'):
        cli.renew_bridge_identity(instance, confirmed=True, hardware_id=lambda: HARDWARE, collect=collect)
    assert DeviceIdentity.load(old.directory, HARDWARE).fingerprint == old.fingerprint
    assert export.read_text() == old.certificate_pem
    assert set(old.directory.iterdir()) == existing


def test_renewal_restores_trust_copy_if_identity_write_fails(bridge, monkeypatch):
    from dispread.bridge import identity

    instance, old, export = bridge
    write = identity._atomic_private
    path = old.directory / 'identity.json'

    def fail_at_commit(target, data):
        if target == path:
            raise OSError('Schreibfehler')
        write(target, data)

    monkeypatch.setattr(identity, '_atomic_private', fail_at_commit)
    with pytest.raises(ValueError, match='Schreibfehler'):
        cli.renew_bridge_identity(instance, confirmed=True, hardware_id=lambda: HARDWARE,
                                  collect=snapshot('idle'))
    assert DeviceIdentity.load(old.directory, HARDWARE).fingerprint == old.fingerprint
    assert export.read_text() == old.certificate_pem
    [backup] = old.directory.glob('backup-*/identity.json')
    assert backup.read_bytes() == path.read_bytes()


def test_renewal_recovers_when_export_is_ahead_after_interrupted_write(bridge):
    instance, old, export = bridge
    path = old.directory / 'identity.json'
    saved = path.read_bytes()
    interrupted = DeviceIdentity.renew(old.directory, HARDWARE, confirmed=True, check_idle=lambda: None,
                                       certificate_export=export)
    path.write_bytes(saved)  # Simulate the public replacement reaching disk first.
    result = cli.renew_bridge_identity(instance, confirmed=True, hardware_id=lambda: HARDWARE,
                                       collect=snapshot('idle'))
    assert result.previous_certificate_sha256 == old.fingerprint
    assert result.certificate_sha256 != interrupted.certificate_sha256
    verify_certificate(export.read_text(), result.certificate_sha256, old.pi_id)
