"""Local Pi identity: atomic private state and independently pinned verification."""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import re
import ssl
import stat
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

_PI_URI = "urn:dispread:pi:"
_PSS = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


class IdentityConflict(ValueError):
    """Copied state on different hardware requires explicit local reprovisioning."""


def private_directory(directory: Path) -> Path:
    """Create or check an owner-only directory; never repair unsafe existing state."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError("private directory must be owned by current user and mode 0700")
    return directory


def _private_fd(path: Path, flags: int):
    fd = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        os.close(fd)
        raise ValueError("private file must be owned by current user and mode 0600")
    return fd


@contextlib.contextmanager
def identity_lock(directory: Path):
    # Only Pi persistence needs POSIX locking; Windows consumers import the
    # certificate and hello verification helpers from this module as well.
    import fcntl

    with os.fdopen(_private_fd(directory / "identity.lock", os.O_CREAT | os.O_RDWR), "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _atomic_private(path: Path, data: bytes):
    fd, temporary = tempfile.mkstemp(prefix=".identity-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _load_certificate(certificate_pem: str):
    if not isinstance(certificate_pem, str) or len(certificate_pem) > 12288:
        raise ValueError("invalid certificate PEM")
    if not re.fullmatch(
        r"-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\r?\n?", certificate_pem
    ):
        raise ValueError("expected exactly one certificate")
    try:
        cert = x509.load_pem_x509_certificate(certificate_pem.encode("ascii"))
        key = cert.public_key()
        if not isinstance(key, rsa.RSAPublicKey) or key.key_size != 3072:
            raise ValueError("certificate requires RSA-3072")
        if not isinstance(cert.signature_hash_algorithm, hashes.SHA256):
            raise ValueError("certificate requires SHA256")
        if cert.issuer != cert.subject:
            raise ValueError("expected provisioned self-signed Pi certificate")
        key.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), hashes.SHA256())
        return cert
    except (TypeError, UnicodeError) as error:
        raise ValueError("invalid certificate") from error


def verify_certificate(
    certificate_pem: str, expected_fingerprint: str, expected_pi_id: str, *, now: datetime | None = None
) -> x509.Certificate:
    """Check pinned DER fingerprint, Pi URI SAN, RSA policy and UTC validity.

    ``now`` is the consumer's aware wall clock, never a monotonic run clock.
    A wrong Windows clock fails closed and must be corrected by the operator.
    """
    cert = _load_certificate(certificate_pem)
    if not isinstance(expected_fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_fingerprint):
        raise ValueError("invalid certificate fingerprint")
    if not hmac.compare_digest(cert.fingerprint(hashes.SHA256()).hex(), expected_fingerprint):
        raise ValueError("certificate fingerprint mismatch")
    if not isinstance(expected_pi_id, str) or not _ID.fullmatch(expected_pi_id):
        raise ValueError("invalid Pi ID")
    try:
        identities = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(
            x509.UniformResourceIdentifier
        )
    except x509.ExtensionNotFound as error:
        raise ValueError("certificate missing Pi identity") from error
    if identities != [_PI_URI + expected_pi_id]:
        raise ValueError("certificate Pi identity mismatch")
    now = datetime.now(UTC) if now is None else now
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("certificate validity requires aware UTC wall clock")
    if not cert.not_valid_before_utc <= now < cert.not_valid_after_utc:
        raise ValueError("certificate outside validity interval; check system clock or renew identity explicitly")
    return cert


def verify_hello(certificate_pem: str, payload: bytes, signature: bytes) -> None:
    """Verify exact canonical UART hello bytes with the already pinned certificate.

    Consumers must first call ``verify_certificate`` with the imported Pi ID and
    fingerprint. This function checks certificate policy/time and PSS signature.
    """
    cert = _load_certificate(certificate_pem)
    try:
        identities = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(
            x509.UniformResourceIdentifier
        )
        if len(identities) != 1 or not identities[0].startswith(_PI_URI):
            raise ValueError("certificate missing Pi identity")
        verify_certificate(certificate_pem, cert.fingerprint(hashes.SHA256()).hex(), identities[0][len(_PI_URI):])
    except x509.ExtensionNotFound as error:
        raise ValueError("certificate missing Pi identity") from error
    cert.public_key().verify(signature, payload, _PSS, hashes.SHA256())


def local_hardware_id() -> str:
    """Read Pi hardware serial locally; never substitute hostname or a network ID."""
    path = Path("/sys/firmware/devicetree/base/serial-number")
    value = path.read_bytes().rstrip(b"\0\n").decode("ascii")
    if not re.fullmatch(r"[0-9a-fA-F]{8,32}", value):
        raise ValueError("Pi hardware serial unavailable or invalid")
    return value.lower()


@dataclass(frozen=True, slots=True, repr=False)
class DeviceIdentity:
    directory: Path
    pi_id: str
    certificate_pem: str
    fingerprint: str
    _key: rsa.RSAPrivateKey = field(repr=False)

    def __repr__(self):
        return f"DeviceIdentity(pi_id={self.pi_id!r}, fingerprint={self.fingerprint!r})"

    @classmethod
    def load_or_create(cls, directory: Path, hardware_id: str) -> DeviceIdentity:
        return cls._open(directory, hardware_id, create=True)

    @classmethod
    def load(cls, directory: Path, hardware_id: str) -> DeviceIdentity:
        """Read existing state only; ordinary service startup never provisions."""
        return cls._open(directory, hardware_id, create=False)

    @classmethod
    def _open(cls, directory, hardware_id, *, create):
        if not isinstance(hardware_id, str) or not hardware_id.strip() or len(hardware_id) > 512:
            raise ValueError("hardware identity required")
        directory = private_directory(Path(directory))
        digest = hashlib.sha256(hardware_id.encode()).hexdigest()
        path = directory / "identity.json"
        with identity_lock(directory):
            try:
                with os.fdopen(_private_fd(path, os.O_RDONLY), "r") as stream:
                    state = json.load(stream)
            except FileNotFoundError:
                if not create:
                    raise ValueError("identity absent; explicit local provisioning required") from None
                key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
                pi_id = str(uuid.uuid4())
                name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "dispread-" + pi_id)])
                now = datetime.now(UTC)
                cert = (
                    x509.CertificateBuilder()
                    .subject_name(name).issuer_name(name).public_key(key.public_key())
                    .serial_number(x509.random_serial_number())
                    .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=365))
                    .add_extension(x509.SubjectAlternativeName([x509.UniformResourceIdentifier(_PI_URI + pi_id)]), critical=False)
                    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                    .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                    .sign(key, hashes.SHA256())
                )
                state = {
                    "schema": 1, "pi_id": pi_id, "hardware_sha256": digest,
                    "certificate_pem": cert.public_bytes(serialization.Encoding.PEM).decode("ascii"),
                    "private_key_pem": key.private_bytes(
                        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
                    ).decode("ascii"),
                }
                _atomic_private(path, json.dumps(state).encode("utf-8"))
            if not isinstance(state, dict) or set(state) != {
                "schema", "pi_id", "hardware_sha256", "certificate_pem", "private_key_pem"
            } or state["schema"] != 1:
                raise ValueError("invalid stored identity; never overwritten automatically")
            if not hmac.compare_digest(state["hardware_sha256"], digest):
                raise IdentityConflict("hardware identity conflict; explicit local reprovisioning required")
            cert = _load_certificate(state["certificate_pem"])
            fingerprint = cert.fingerprint(hashes.SHA256()).hex()
            verify_certificate(state["certificate_pem"], fingerprint, state["pi_id"])
            key = serialization.load_pem_private_key(state["private_key_pem"].encode("ascii"), password=None)
            if not isinstance(key, rsa.RSAPrivateKey) or key.public_key().public_numbers() != cert.public_key().public_numbers():
                raise ValueError("private key and certificate mismatch")
            return cls(directory, state["pi_id"], state["certificate_pem"], fingerprint, key)

    def sign_hello(self, payload: bytes) -> bytes:
        """Sign canonical_uart_hello output with RSA-PSS/SHA256, salt32."""
        if not isinstance(payload, bytes) or len(payload) > 4096:
            raise ValueError("invalid hello payload")
        return self._key.sign(payload, _PSS, hashes.SHA256())

    def tls_context(self) -> ssl.SSLContext:
        """Explicitly serve this identity; never replace an existing TLS setup.

        OpenSSL's file-only API reads private temporary 0600 files inside the
        owner's identity directory. Files disappear as soon as it has loaded.
        """
        verify_certificate(self.certificate_pem, self.fingerprint, self.pi_id)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        with tempfile.TemporaryDirectory(prefix=".tls-", dir=self.directory) as temporary:
            cert_path, key_path = Path(temporary) / "cert.pem", Path(temporary) / "key.pem"
            _atomic_private(cert_path, self.certificate_pem.encode("ascii"))
            _atomic_private(key_path, self._key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            ))
            context.load_cert_chain(cert_path, key_path)
        return context
