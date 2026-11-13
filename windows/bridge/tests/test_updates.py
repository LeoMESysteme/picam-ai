"""Signed manifests and interrupted staging; all release data is test-only."""
import base64
import hashlib
import hmac
import json
from contextlib import contextmanager
from dataclasses import replace

import pytest
from dispread_bridge_app.types import InstallResult
from dispread_bridge_app.updates import DownloadResponse, ManifestError, TrustedReleaseKey, UpdateManager

PAYLOAD = b'synthetic installer fixture'
TEST_SECRET = b'test-only not a product release key'
ORIGIN = 'https://releases.example.test'


def verifier(public_key, signature, message):
    if public_key != b'test-key' or not hmac.compare_digest(signature, hmac.digest(TEST_SECRET, message, 'sha512')):
        raise ValueError('invalid test signature')


def manifest(**changes):
    body = {'schema_version': 1, 'version': '1.2.3', 'source_commit': 'a' * 40,
            'target': 'windows11-x64', 'artifacts': [{'id': 'bridge-setup', 'url': ORIGIN + '/1.2.3/setup.exe',
            'size': len(PAYLOAD), 'sha256': hashlib.sha256(PAYLOAD).hexdigest()}]}
    body.update(changes)
    signature = hmac.digest(TEST_SECRET, json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii'), 'sha512')
    return json.dumps({**body, 'signature': {'algorithm': 'ed25519', 'key_id': 'test', 'value': base64.b64encode(signature).decode('ascii')}}).encode()


class Transport:
    def __init__(self, chunks=(PAYLOAD,), final_url=None):
        self.chunks = chunks
        self.final_url = final_url
        self.requests = []
        self.closed = False
    @contextmanager
    def __call__(self, url):
        self.requests.append(url)
        try:
            yield DownloadResponse(self.final_url or url, iter(self.chunks))
        finally:
            self.closed = True


class Deployment:
    """Filesystem fake for the externally supplied transactional Windows deployer."""
    def __init__(self, root, fail=False, result=None):
        self.root = root
        root.mkdir()
        (root / 'version').write_text('1.0.0')
        (root / 'config-v1').write_text('old-config')
        self.fail = fail
        self.result = result or InstallResult('ready', False, None, None)
    def backup(self):
        (self.root / 'backup-version').write_bytes((self.root / 'version').read_bytes())
        return 'backup-1'
    def prepare(self, release, artifacts, backup_id):
        assert backup_id == 'backup-1'
        assert artifacts[0].read_bytes() == PAYLOAD
        (self.root / 'config-v2').write_text('migrated-copy')
    def activate(self, backup_id):
        (self.root / 'version').write_text('1.2.3')
        if self.fail:
            raise OSError('UAC or activation failure')
        return self.result
    def verify_installed(self, release):
        if (self.root / 'version').read_text() == release.version:
            return InstallResult('ready', False, None, None)
        return InstallResult('unverified', False, None, 'installed_version_unverified')
    def rollback(self, backup_id):
        assert backup_id == 'backup-1'
        (self.root / 'version').write_bytes((self.root / 'backup-version').read_bytes())


def manager(tmp_path, **kwargs):
    return UpdateManager(state_path=tmp_path / 'update.json', cache_dir=tmp_path / 'cache',
                         trusted_key=TrustedReleaseKey('test', b'test-key', verifier),
                         allowed_origins=(ORIGIN,), **kwargs)


def test_valid_manifest_has_explicit_source_and_artifacts(tmp_path):
    release = manager(tmp_path).check(manifest())
    assert release.version == '1.2.3'
    assert release.source_commit == 'a' * 40
    assert release.artifacts[0].sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    assert len(release.signature) == 64


def test_no_product_default_trust_key(tmp_path):
    with pytest.raises(ManifestError, match='trust'):
        UpdateManager(state_path=tmp_path / 's', cache_dir=tmp_path / 'c').check(manifest())


def test_signature_error_does_not_stage_or_install(tmp_path):
    body = json.loads(manifest())
    body['version'] = '9.9.9'
    with pytest.raises(ManifestError, match='signature'):
        manager(tmp_path).check(json.dumps(body).encode())
    assert not (tmp_path / 'cache').exists()


@pytest.mark.parametrize('changes', [
    {'command': 'whoami'}, {'version': '../1.2'}, {'source_commit': 'HEAD'},
    {'target': 'linux'}, {'artifacts': []},
    {'artifacts': [{'id': '../escape', 'url': ORIGIN + '/a.exe', 'size': 10, 'sha256': 'f' * 64}]},
    {'artifacts': [{'id': 'bridge-setup', 'url': 'http://releases.example.test/a.exe', 'size': 10, 'sha256': 'f' * 64}]},
    {'artifacts': [{'id': 'bridge-setup', 'url': 'https://evil.test/a.exe', 'size': 10, 'sha256': 'f' * 64}]},
    {'artifacts': [{'id': 'bridge-setup', 'url': ORIGIN + '/a.exe', 'size': True, 'sha256': 'f' * 64}]},
])
def test_strict_manifest_schema_and_sources(tmp_path, changes):
    with pytest.raises(ManifestError):
        manager(tmp_path).check(manifest(**changes))


@pytest.mark.parametrize('raw', [b'{"schema_version":1,"schema_version":1}', b'x' * 65537])
def test_duplicate_or_oversized_manifest_is_rejected(tmp_path, raw):
    with pytest.raises(ManifestError):
        manager(tmp_path).check(raw)


def test_update_while_output_active_is_refused(tmp_path):
    transport = Transport()
    deployment = Deployment(tmp_path / 'app')
    mgr = manager(tmp_path, downloader=transport, deployment=deployment)
    assert mgr.install(mgr.check(manifest()), output_active=True).error_code == 'output_active'
    assert transport.requests == []
    assert (deployment.root / 'version').read_text() == '1.0.0'


def test_hash_error_leaves_retryable_state(tmp_path):
    deployment = Deployment(tmp_path / 'app')
    mgr = manager(tmp_path, downloader=Transport((b'x' * len(PAYLOAD),)), deployment=deployment)
    result = mgr.install(mgr.check(manifest()), output_active=False)
    assert result.error_code == 'artifact_hash_mismatch'
    assert json.loads((tmp_path / 'update.json').read_text())['phase'] == 'downloading'
    assert (deployment.root / 'version').read_text() == '1.0.0'
    assert not list((tmp_path / 'cache').glob('*.verified'))


def test_proxy_interruption_can_resume_on_new_manager(tmp_path):
    def interrupted():
        yield PAYLOAD[:3]
        raise OSError('proxy reset')
    deployment = Deployment(tmp_path / 'app')
    transport = Transport(interrupted())
    mgr = manager(tmp_path, downloader=transport, deployment=deployment)
    assert mgr.install(mgr.check(manifest()), output_active=False).error_code == 'download_failed'
    assert transport.closed
    retry = manager(tmp_path, downloader=Transport(), deployment=deployment)
    assert retry.resume(output_active=False).state == 'ready'
    assert (deployment.root / 'version').read_text() == '1.2.3'
    assert (deployment.root / 'config-v1').read_text() == 'old-config'
    assert (deployment.root / 'backup-version').read_text() == '1.0.0'


def test_low_disk_never_overwrites_previous_install(tmp_path):
    transport = Transport()
    mgr = manager(tmp_path, downloader=transport, free_space=lambda _: 1)
    assert mgr.install(mgr.check(manifest()), output_active=False).error_code == 'insufficient_space'
    assert transport.requests == []
    assert (tmp_path / 'update.json').is_file()


def test_cancel_download_then_resume(tmp_path):
    cancel = [True]
    deployment = Deployment(tmp_path / 'app')
    mgr = manager(tmp_path, downloader=Transport(), deployment=deployment, cancel_requested=lambda: cancel[0])
    assert mgr.install(mgr.check(manifest()), output_active=False).state == 'cancelled'
    cancel[0] = False
    assert mgr.resume(output_active=False).state == 'ready'


def test_failed_activation_rolls_back_version_and_keeps_old_config(tmp_path):
    deployment = Deployment(tmp_path / 'app', fail=True)
    mgr = manager(tmp_path, downloader=Transport(), deployment=deployment)
    assert mgr.install(mgr.check(manifest()), output_active=False).error_code == 'activation_failed_rolled_back'
    assert (deployment.root / 'version').read_text() == '1.0.0'
    assert (deployment.root / 'config-v1').read_text() == 'old-config'
    deployment.fail = False
    assert mgr.resume(output_active=False).state == 'ready'


def test_reboot_is_pending_not_ready_and_resume_rolls_back_before_retry(tmp_path):
    deployment = Deployment(tmp_path / 'app', result=InstallResult('reboot_required', True, None, 'restart_then_verify'))
    mgr = manager(tmp_path, downloader=Transport(), deployment=deployment)
    assert mgr.install(mgr.check(manifest()), output_active=False).reboot_required
    assert json.loads((tmp_path / 'update.json').read_text())['phase'] == 'activation_pending'
    deployment.result = InstallResult('ready', False, None, None)
    assert mgr.resume(output_active=False).state == 'ready'
    assert (deployment.root / 'backup-version').read_text() == '1.0.0'


def test_forged_release_info_cannot_bypass_manifest_validation(tmp_path):
    mgr = manager(tmp_path)
    release = replace(mgr.check(manifest()), version='9.9.9')
    assert mgr.install(release, output_active=False).error_code == 'release_not_verified'


def test_redirect_to_other_source_is_never_accepted(tmp_path):
    mgr = manager(tmp_path, downloader=Transport(final_url='https://evil.test/setup.exe'))
    assert mgr.install(mgr.check(manifest()), output_active=False).error_code == 'download_source_changed'


def test_actual_ed25519_verifier_checks_canonical_bytes(tmp_path):
    ed25519 = pytest.importorskip('cryptography.hazmat.primitives.asymmetric.ed25519')
    serialization = pytest.importorskip('cryptography.hazmat.primitives.serialization')
    private = ed25519.Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    body = json.loads(manifest())
    del body['signature']
    payload = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    body['signature'] = {'algorithm': 'ed25519', 'key_id': 'actual-test-only', 'value': base64.b64encode(private.sign(payload)).decode('ascii')}
    mgr = UpdateManager(state_path=tmp_path / 's', cache_dir=tmp_path / 'c', trusted_key=TrustedReleaseKey('actual-test-only', public), allowed_origins=(ORIGIN,))
    assert mgr.check(json.dumps(body).encode()).version == '1.2.3'
    body['version'] = '4.5.6'
    with pytest.raises(ManifestError, match='signature'):
        mgr.check(json.dumps(body).encode())


def test_complete_state_is_reverified_against_current_install(tmp_path):
    deployment = Deployment(tmp_path / 'app')
    mgr = manager(tmp_path, downloader=Transport(), deployment=deployment)
    assert mgr.install(mgr.check(manifest()), output_active=False).state == 'ready'
    (deployment.root / 'version').write_text('removed-or-replaced')
    assert mgr.resume(output_active=False).state != 'ready'


def test_complete_state_without_native_provider_is_not_success(tmp_path):
    mgr = manager(tmp_path)
    release = mgr.check(manifest())
    (tmp_path / 'update.json').write_text(json.dumps({'schema_version': 1,
        'manifest': base64.b64encode(release.manifest_bytes).decode(), 'phase': 'complete',
        'backup_id': None, 'result': {'state': 'ready'}}))
    assert mgr.resume(output_active=False).error_code == 'deployment_provider_unverified'


def test_uac_denial_during_update_retains_previous_version(tmp_path):
    deployment = Deployment(tmp_path / 'app', result=InstallResult('admin_required', False, None, 'elevation_denied'))
    mgr = manager(tmp_path, downloader=Transport(), deployment=deployment)
    result = mgr.install(mgr.check(manifest()), output_active=False)
    assert (result.state, result.error_code) == ('admin_required', 'elevation_denied')
    assert (deployment.root / 'version').read_text() == '1.0.0'


def test_process_death_during_activation_recovers_old_version_first(tmp_path):
    class CrashedDeployment(Deployment):
        crash = True
        def activate(self, backup_id):
            result = super().activate(backup_id)
            if self.crash:
                raise KeyboardInterrupt('power loss')
            return result
    deployment = CrashedDeployment(tmp_path / 'app')
    mgr = manager(tmp_path, downloader=Transport(), deployment=deployment)
    with pytest.raises(KeyboardInterrupt):
        mgr.install(mgr.check(manifest()), output_active=False)
    assert (deployment.root / 'version').read_text() == '1.2.3'
    deployment.crash = False
    assert mgr.resume(output_active=False).state == 'ready'
    assert (deployment.root / 'backup-version').read_text() == '1.0.0'
