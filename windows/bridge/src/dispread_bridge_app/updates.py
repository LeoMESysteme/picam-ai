"""Fail-closed release verification and resumable transactional update policy.

No release key, hosting origin, or Windows deployer is built in. Native deployers
must stage versioned config copies, retain the preceding app/config, serialize
with output startup and only activate while idle. These contracts do not claim
that an actual Windows install, signature qualification or rollback was tested.
"""
import base64
import binascii
import hashlib
import json
import re
import shutil
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .install import _read_json, _state_lock, _strict_object, _write_json
from .types import InstallResult

_MAX_MANIFEST = 65536
_MAX_ARTIFACT = 2 * 1024**3
_RESERVE = 16 * 1024**2


class ManifestError(ValueError):
    pass


def _ed25519_verify(public_key: bytes, signature: bytes, payload: bytes):
    # Dependency/provider qualification is an external release prerequisite;
    # unavailable crypto raises and fails closed, never bypasses verification.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature, payload)


@dataclass(frozen=True)
class TrustedReleaseKey:
    key_id: str
    public_key: bytes
    verifier: Callable[[bytes, bytes, bytes], None] = field(default=_ed25519_verify, repr=False, compare=False)


@dataclass(frozen=True)
class ReleaseArtifact:
    id: str
    url: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    source_commit: str
    artifacts: tuple[ReleaseArtifact, ...]
    signature: bytes
    manifest_bytes: bytes = field(repr=False)


@dataclass(frozen=True)
class DownloadResponse:
    final_url: str
    chunks: Iterable[bytes]


class DeploymentBackend(Protocol):
    """Trusted native backend, not selected by a manifest or Pi profile.

    backup returns an opaque local checkpoint ID. prepare stages app and a
    versioned configuration copy without changing the current working version.
    activate MUST atomically refuse active output, verify installed signatures,
    and return ready only after native installation/PnP checks. rollback is
    idempotent across reboot/process death and restores that checkpoint without
    deleting logs or the old configuration. verify_installed checks current
    installation rather than trusting a past state-file result. Recheck artifact
    bytes/signatures inside the native privilege boundary before execution.
    Never execute a state/manifest path.
    This repository supplies no native backend pending Windows qualification.
    """
    def backup(self) -> str: ...
    def prepare(self, release: ReleaseInfo, artifacts: tuple[Path, ...], backup_id: str) -> None: ...
    def activate(self, backup_id: str) -> InstallResult: ...
    def rollback(self, backup_id: str) -> None: ...
    def verify_installed(self, release: ReleaseInfo) -> InstallResult: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OSError('release redirects are forbidden')


def _download(url):
    """HTTPS defaults, normal proxy support, bounded reads; redirects refused."""
    from contextlib import contextmanager
    @contextmanager
    def response():
        with build_opener(_NoRedirect()).open(Request(url, headers={'Accept-Encoding': 'identity'}), timeout=30) as stream:
            def chunks():
                while chunk := stream.read(64 * 1024):
                    yield chunk
            yield DownloadResponse(stream.geturl(), chunks())
    return response()


def _origin(value):
    if not isinstance(value, str) or len(value) > 2048 or not value.isascii():
        raise ManifestError('invalid artifact URL')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or not re.fullmatch(r'[A-Za-z0-9.-]+(?::443)?', parsed.netloc)
            or parsed.netloc != parsed.netloc.lower()):
        raise ManifestError('invalid artifact URL')
    if not re.fullmatch(r'/[A-Za-z0-9/_.-]*', parsed.path) or '..' in parsed.path.split('/'):
        raise ManifestError('invalid artifact path')
    return 'https://' + parsed.netloc


class _UpdateFailure(Exception):
    pass


class UpdateManager:
    def __init__(self, *, state_path: Path, cache_dir: Path,
                 trusted_key: TrustedReleaseKey | None = None,
                 allowed_origins: tuple[str, ...] = (), downloader=None,
                 deployment: DeploymentBackend | None = None,
                 free_space=None, cancel_requested=None):
        self.state_path = Path(state_path)
        self.cache_dir = Path(cache_dir)
        self._key = trusted_key
        for origin in allowed_origins:
            if _origin(origin + '/') != origin:
                raise ValueError('origins must be exact HTTPS origins')
        self._origins = frozenset(allowed_origins)
        self._downloader = downloader or _download
        self._deployment = deployment
        self._free_space = free_space or (lambda path: shutil.disk_usage(path).free)
        self._cancel = cancel_requested or (lambda: False)

    def check(self, manifest_bytes: bytes) -> ReleaseInfo:
        if self._key is None or not self._origins:
            raise ManifestError('release trust key and sources must be provisioned')
        try:
            if not isinstance(manifest_bytes, bytes) or not 1 <= len(manifest_bytes) <= _MAX_MANIFEST:
                raise ValueError('manifest size')
            data = json.loads(manifest_bytes, object_pairs_hook=_strict_object)
            keys = {'schema_version', 'version', 'source_commit', 'target', 'artifacts', 'signature'}
            if not isinstance(data, dict) or set(data) != keys:
                raise ValueError('manifest fields')
            if type(data['schema_version']) is not int or data['schema_version'] != 1 or data['target'] != 'windows11-x64':
                raise ValueError('manifest target/schema')
            if not isinstance(data['version'], str) or not re.fullmatch(r'(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})', data['version']):
                raise ValueError('release version')
            if not isinstance(data['source_commit'], str) or not re.fullmatch(r'[0-9a-f]{40}', data['source_commit']):
                raise ValueError('source commit')
            artifacts = data['artifacts']
            if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 3:
                raise ValueError('artifacts')
            seen = set()
            for artifact in artifacts:
                if not isinstance(artifact, dict) or set(artifact) != {'id', 'url', 'size', 'sha256'}:
                    raise ValueError('artifact fields')
                if artifact['id'] not in ('bridge-setup', 'usb-driver', 'vcom-driver') or artifact['id'] in seen:
                    raise ValueError('artifact identity')
                seen.add(artifact['id'])
                if type(artifact['size']) is not int or not 1 <= artifact['size'] <= _MAX_ARTIFACT:
                    raise ValueError('artifact size')
                if not isinstance(artifact['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', artifact['sha256']):
                    raise ValueError('artifact digest')
                if _origin(artifact['url']) not in self._origins:
                    raise ValueError('artifact origin not trusted')
            if 'bridge-setup' not in seen or sum(item['size'] for item in artifacts) > 4 * 1024**3:
                raise ValueError('missing setup/oversized release')
            signature = data.pop('signature')
            if (not isinstance(signature, dict) or set(signature) != {'algorithm', 'key_id', 'value'}
                    or signature['algorithm'] != 'ed25519' or not isinstance(signature['key_id'], str)
                    or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', signature['key_id'])
                    or signature['key_id'] != self._key.key_id
                    or not isinstance(signature['value'], str) or len(signature['value']) != 88):
                raise ValueError('signature descriptor')
            raw_signature = base64.b64decode(signature['value'], validate=True)
            if len(raw_signature) != 64 or base64.b64encode(raw_signature).decode('ascii') != signature['value']:
                raise ValueError('signature encoding')
            canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
        except (ValueError, TypeError, KeyError, RecursionError, binascii.Error) as exc:
            raise ManifestError('invalid release manifest schema or signature descriptor') from exc
        try:
            if self._key.verifier(self._key.public_key, raw_signature, canonical) is not None:
                raise ValueError('verifier must raise on failure and return None on success')
        except Exception as exc:
            raise ManifestError('release signature verification failed') from exc
        return ReleaseInfo(data['version'], data['source_commit'], tuple(ReleaseArtifact(**item) for item in artifacts), raw_signature, manifest_bytes)

    def _state(self, release):
        return {'schema_version': 1, 'manifest': base64.b64encode(release.manifest_bytes).decode('ascii'),
                'phase': 'downloading', 'backup_id': None, 'result': None}

    def _load(self):
        state = _read_json(self.state_path)
        if not isinstance(state, dict) or set(state) != {'schema_version', 'manifest', 'phase', 'backup_id', 'result'}:
            raise ValueError('invalid update state')
        if type(state['schema_version']) is not int or state['schema_version'] != 1 or state['phase'] not in ('downloading', 'staged', 'activation_pending', 'complete'):
            raise ValueError('invalid update phase')
        if state['backup_id'] is not None and (not isinstance(state['backup_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', state['backup_id'])):
            raise ValueError('invalid rollback checkpoint')
        if state['phase'] == 'activation_pending' and state['backup_id'] is None:
            raise ValueError('missing rollback checkpoint')
        if not isinstance(state['manifest'], str):
            raise ValueError('invalid manifest checkpoint')
        release = self.check(base64.b64decode(state['manifest'], validate=True))
        return state, release

    def _result(self, state, result, *, phase=None):
        if phase:
            state['phase'] = phase
        state['result'] = asdict(result)
        _write_json(self.state_path, state)
        return result

    def _artifact_path(self, artifact):
        # Manifest URLs and filenames are never interpreted as local paths.
        return self.cache_dir / (artifact.id + '-' + artifact.sha256 + '.verified')

    @staticmethod
    def _verified(path, artifact):
        if not path.is_file() or path.stat().st_size != artifact.size:
            return False
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest() == artifact.sha256

    def _fetch(self, artifact):
        destination = self._artifact_path(artifact)
        if self._verified(destination, artifact):
            return destination
        temporary = destination.with_suffix('.partial')
        digest = hashlib.sha256()
        count = 0
        with self._downloader(artifact.url) as response:
            if response.final_url != artifact.url:
                raise _UpdateFailure('download_source_changed')
            with temporary.open('wb') as stream:
                for chunk in response.chunks:
                    if self._cancel():
                        raise _UpdateFailure('operator_cancelled')
                    if not isinstance(chunk, bytes) or len(chunk) > 1024**2:
                        raise _UpdateFailure('invalid_download_chunk')
                    count += len(chunk)
                    if count > artifact.size:
                        raise _UpdateFailure('artifact_size_mismatch')
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                import os
                os.fsync(stream.fileno())
        if count != artifact.size:
            raise _UpdateFailure('artifact_size_mismatch')
        if digest.hexdigest() != artifact.sha256:
            raise _UpdateFailure('artifact_hash_mismatch')
        temporary.replace(destination)
        return destination

    def install(self, release: ReleaseInfo, *, output_active: bool) -> InstallResult:
        # Refusal occurs before network, storage writes or backup/activation.
        if output_active is not False:
            return InstallResult('busy', False, None, 'output_active')
        try:
            verified = self.check(release.manifest_bytes)
            if verified != release:
                raise ManifestError('release differs from verified manifest')
        except (ManifestError, AttributeError):
            return InstallResult('failed', False, None, 'release_not_verified')
        try:
            with _state_lock(self.state_path):
                state = self._state(verified)
                if self.state_path.exists():
                    saved, pending_release = self._load()
                    if pending_release != verified and saved['phase'] != 'complete':
                        return InstallResult('busy', False, None, 'resume_pending_update_first')
                    if pending_release == verified:
                        state = saved
                _write_json(self.state_path, state)
                return self._install_locked(verified, state)
        except (ValueError, binascii.Error):
            return InstallResult('failed', False, None, 'invalid_update_state')
        except OSError:
            return InstallResult('failed', False, None, 'update_state_unavailable')

    def _install_locked(self, release, state):
        if state['phase'] == 'complete':
            if self._deployment is None:
                return self._result(state, InstallResult('unverified', False, None, 'deployment_provider_unverified'))
            try:
                result = self._deployment.verify_installed(release)
                if not isinstance(result, InstallResult):
                    raise ValueError('invalid current installation result')
            except Exception:
                result = InstallResult('unverified', False, None, 'installed_version_unverified')
            return self._result(state, result)
        if self._cancel():
            return self._result(state, InstallResult('cancelled', False, None, 'operator_cancelled'))
        # Recover a crash/reboot before attempting another migration/activation.
        if state['phase'] == 'activation_pending':
            if self._deployment is None:
                return self._result(state, InstallResult('unverified', False, None, 'deployment_provider_unverified'))
            try:
                self._deployment.rollback(state['backup_id'])
            except Exception:
                return self._result(state, InstallResult('recovery_required', False, None, 'rollback_failed'))
            state['backup_id'] = None
            state['phase'] = 'staged'
            _write_json(self.state_path, state)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        needed = sum(item.size for item in release.artifacts) * 2 + _RESERVE
        if self._free_space(self.cache_dir) < needed:
            return self._result(state, InstallResult('failed', False, None, 'insufficient_space'))
        try:
            paths = tuple(self._fetch(artifact) for artifact in release.artifacts)
        except _UpdateFailure as exc:
            code = str(exc)
            return self._result(state, InstallResult('cancelled' if code == 'operator_cancelled' else 'failed', False, None, code), phase='downloading')
        except OSError:
            return self._result(state, InstallResult('failed', False, None, 'download_failed'), phase='downloading')
        state['phase'] = 'staged'
        _write_json(self.state_path, state)
        if self._deployment is None:
            return self._result(state, InstallResult('unverified', False, None, 'deployment_provider_unverified'))
        if self._cancel():
            return self._result(state, InstallResult('cancelled', False, None, 'operator_cancelled'))
        try:
            backup_id = self._deployment.backup()
            if not isinstance(backup_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', backup_id):
                raise ValueError('invalid backend backup ID')
        except Exception:
            return self._result(state, InstallResult('failed', False, None, 'backup_failed'))
        state['backup_id'] = backup_id
        state['phase'] = 'activation_pending'
        _write_json(self.state_path, state)
        refused = None
        try:
            self._deployment.prepare(release, paths, backup_id)
            result = self._deployment.activate(backup_id)
            if not isinstance(result, InstallResult):
                raise ValueError('invalid activation result')
            if result.reboot_required or result.state == 'reboot_required':
                return self._result(state, InstallResult('reboot_required', True, result.pair, result.error_code))
            if result.state != 'ready':
                refused = result
                raise OSError('native installer did not verify readiness')
        except Exception:
            try:
                self._deployment.rollback(backup_id)
            except Exception:
                return self._result(state, InstallResult('recovery_required', False, None, 'rollback_failed'))
            state['backup_id'] = None
            return self._result(state, refused or InstallResult('failed', False, None, 'activation_failed_rolled_back'), phase='staged')
        return self._result(state, result, phase='complete')

    def resume(self, *, output_active: bool) -> InstallResult:
        if output_active is not False:
            return InstallResult('busy', False, None, 'output_active')
        try:
            _, release = self._load()
        except (OSError, ValueError, binascii.Error):
            return InstallResult('failed', False, None, 'invalid_update_state')
        return self.install(release, output_active=output_active)
