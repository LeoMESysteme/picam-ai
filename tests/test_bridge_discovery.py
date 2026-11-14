"""Discovery is untrusted routing information, never a trust anchor."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from cryptography import x509

from dispread.bridge import discovery
from dispread.bridge.identity import DeviceIdentity, verify_certificate


def test_two_same_named_devices_stay_distinct(monkeypatch, tmp_path):
    first = DeviceIdentity.load_or_create(tmp_path / "pi-a", "fixture-hardware-a")
    second = DeviceIdentity.load_or_create(tmp_path / "pi-b", "fixture-hardware-b")
    assert first.pi_id != second.pi_id and first.fingerprint != second.fingerprint
    candidates = (
        discovery.DiscoveryCandidate(first.pi_id, "Labor", ("https://pi-a.local:8080",)),
        discovery.DiscoveryCandidate(second.pi_id, "Labor", ("https://pi-b.local:8080",)),
    )
    monkeypatch.setattr(discovery, "discover_services", lambda timeout_s: candidates)
    assert discovery.discover_with_fallback((), timeout_s=0.01) == candidates


def test_dhcp_change_preserves_pi_identity(tmp_path):
    first = DeviceIdentity.load_or_create(tmp_path / "identity", "same-hardware")
    later = DeviceIdentity.load(tmp_path / "identity", "same-hardware")
    a = discovery.DiscoveryCandidate(first.pi_id, "Labor", ("https://192.0.2.1:8080",))
    b = discovery.DiscoveryCandidate(later.pi_id, "Labor", ("https://192.0.2.2:8080",))
    assert a.pi_id_hint == b.pi_id_hint
    assert a.endpoints != b.endpoints
    assert first.fingerprint == later.fingerprint


def test_mdns_failure_allows_explicit_endpoint(monkeypatch):
    def unavailable(timeout_s):
        raise OSError("mDNS blocked")

    monkeypatch.setattr(discovery, "discover_services", unavailable)
    values = discovery.discover_with_fallback(("https://pi.example:8080",), timeout_s=0.01)
    assert values == (discovery.DiscoveryCandidate(None, "Explicit endpoint", ("https://pi.example:8080",)),)
    with pytest.raises(ValueError):
        discovery.discover_with_fallback(("http://insecure.example",))


def test_missing_optional_mdns_is_bounded_and_empty(monkeypatch):
    def unavailable():
        raise ImportError("optional zeroconf absent")

    monkeypatch.setattr(discovery, "_mdns_module", unavailable)
    assert discovery._browse_services(0.01) == ()
    with pytest.raises(ValueError):
        discovery.discover_services(float("inf"))


def test_tls_pin_and_validity_reject_wrong_or_expired_certificate(tmp_path):
    identity = DeviceIdentity.load_or_create(tmp_path / "identity", "hardware")
    cert = x509.load_pem_x509_certificate(identity.certificate_pem.encode())
    with pytest.raises(ValueError):
        verify_certificate(identity.certificate_pem, "0" * 64, identity.pi_id)
    with pytest.raises(ValueError):
        verify_certificate(identity.certificate_pem, identity.fingerprint, "wrong-pi")
    for when in (cert.not_valid_before_utc - timedelta(seconds=1), cert.not_valid_after_utc):
        with pytest.raises(ValueError, match="valid"):
            verify_certificate(identity.certificate_pem, identity.fingerprint, identity.pi_id, now=when)


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("Running", "running"),
        ("NeedsLogin", "logged_out"),
        ("NeedsMachineAuth", "needs_approval"),
        ("Stopped", "unreachable"),
    ],
)
def test_tailscale_distinguishes_only_proven_states(state, expected):
    import json

    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps({"BackendState": state}), stderr="")

    status = discovery.tailscale_status(run=run)
    assert status.state == expected
    assert calls[0][0] == ["tailscale", "status", "--json"]
    assert calls[0][1]["timeout"] <= 3


def test_tailscale_missing_timeout_and_dns_are_not_guessed():
    import subprocess

    def missing(*args, **kwargs):
        raise FileNotFoundError()

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("tailscale", 2)

    assert discovery.tailscale_status(run=missing).state == "not_installed"
    assert discovery.tailscale_status(run=timeout).state == "unreachable"


def test_tailscale_reports_dns_error_only_with_concrete_lookup_failure():
    import socket

    def run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout='{"BackendState":"Running"}')

    assert (
        discovery.tailscale_status(run=run, connection_error=socket.gaierror(-2, "name unknown")).state == "dns_error"
    )
    assert discovery.tailscale_status(run=run, connection_error=TimeoutError()).state == "running"


def test_mdns_adapter_bounds_resolution_and_publishes_no_secrets(monkeypatch):
    infos = []
    calls = []
    candidate = SimpleNamespace(
        properties={
            b"version": b"2",
            b"pi_id": b"pi-fixture",
            b"name": b"Labor",
            b"endpoints": b'["https://192.0.2.5:8080"]',
        }
    )

    class Zeroconf:
        def get_service_info(self, kind, name, timeout):
            calls.append((kind, name, timeout))
            return candidate

        def close(self):
            calls.append("closed")

        def register_service(self, info):
            infos.append(info)

        def unregister_service(self, info):
            infos.remove(info)

    class Browser:
        def __init__(self, zc, kind, *, listener):
            listener.add_service(zc, kind, "pi-fixture." + kind)

        def cancel(self):
            calls.append("cancelled")

    fake = SimpleNamespace(
        Error=type("MdnsError", (Exception,), {}),
        Zeroconf=Zeroconf,
        ServiceBrowser=Browser,
        ServiceInfo=lambda *args, **kwargs: SimpleNamespace(args=args, **kwargs),
    )
    monkeypatch.setattr(discovery, "_mdns_module", lambda: fake)
    assert discovery._browse_services(0.02) == (
        discovery.DiscoveryCandidate("pi-fixture", "Labor", ("https://192.0.2.5:8080",)),
    )
    assert 0 < calls[0][2] <= 20
    assert calls[-2:] == ["cancelled", "closed"]
    publication = discovery.publish_service(
        SimpleNamespace(pi_id="pi-fixture"), ("https://192.0.2.5:8080",), name="Labor"
    )
    assert set(infos[0].properties) == {"version", "pi_id", "name", "endpoints"}
    publication.close()
    publication.close()
    assert not infos


def test_mdns_rejects_untrusted_bad_endpoints():
    info = SimpleNamespace(
        properties={
            b"version": b"2",
            b"pi_id": b"pi-fixture",
            b"name": b"Labor",
            b"endpoints": b'["https://pi.example:8080?token=secret"]',
        }
    )
    with pytest.raises(ValueError):
        discovery._candidate(info)


def test_mdns_rejects_oversized_txt_and_preserves_explicit_ipv6_scope(monkeypatch):
    calls = []

    class Zc:
        def register_service(self, info):
            calls.append(info)

        def unregister_service(self, info):
            pass

        def close(self):
            pass

    fake = SimpleNamespace(
        Error=type("MdnsError", (Exception,), {}),
        Zeroconf=Zc,
        ServiceInfo=lambda *args, **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(discovery, "_mdns_module", lambda: fake)
    identity = SimpleNamespace(pi_id="pi-fixture")
    with pytest.raises(ValueError, match="TXT"):
        discovery.publish_service(identity, ("https://pi.example/" + "a" * 250,))
    with pytest.raises(ValueError, match="TXT"):
        discovery.publish_service(identity, ("https://pi.example:8080",), name="ü" * 130)
    endpoint = "https://[fe80::1234%25Ethernet]:8080"
    publication = discovery.publish_service(identity, (endpoint,))
    import json

    assert json.loads(calls[-1].properties["endpoints"]) == [endpoint]
    # No fabricated remote-interface-index translation or scope-free rewrite.
    publication.close()


def test_discovery_hard_bound_kills_stalled_startup_and_sdk_shutdown(monkeypatch):
    calls = []

    class StalledProcess:
        exitcode = None

        def join(self, timeout):
            calls.append(("join", timeout))

        def is_alive(self):
            return True

        def terminate(self):
            calls.append("terminate")

        def kill(self):
            calls.append("kill")

    monkeypatch.setattr(discovery, "_start_discovery", lambda result_path, timeout_s: StalledProcess())
    assert discovery.discover_services(0.02) == ()
    assert "terminate" in calls and "kill" in calls
    assert all(0 <= item[1] <= 0.2 for item in calls if isinstance(item, tuple))


def test_discovery_spawn_result_is_bounded_and_untrusted(monkeypatch):
    class FinishedProcess:
        exitcode = 0

        def join(self, timeout):
            pass

        def is_alive(self):
            return False

        def close(self):
            pass

    def start(result_path, timeout_s):
        result_path.write_bytes(b"x" * 65537)
        return FinishedProcess()

    monkeypatch.setattr(discovery, "_start_discovery", start)
    assert discovery.discover_services(0.02) == ()


def test_discovery_real_spawn_worker_is_terminated_and_reaped(monkeypatch):
    import multiprocessing
    import time

    before = {process.pid for process in multiprocessing.active_children()}

    def start(result_path, timeout_s):
        process = multiprocessing.get_context("spawn").Process(target=time.sleep, args=(60,), daemon=True)
        process.start()
        return process

    monkeypatch.setattr(discovery, "_start_discovery", start)
    started = time.monotonic()
    assert discovery.discover_services(0.05) == ()
    assert time.monotonic() - started < 1.5
    assert {process.pid for process in multiprocessing.active_children()} == before


def test_publication_start_failure_is_optional_unavailability(monkeypatch):
    class MdnsError(Exception):
        pass

    def unavailable():
        raise MdnsError("SDK startup failed")

    fake = SimpleNamespace(Error=MdnsError, Zeroconf=unavailable, ServiceInfo=lambda *args, **kwargs: object())
    monkeypatch.setattr(discovery, "_mdns_module", lambda: fake)
    with pytest.raises(OSError, match="unavailable"):
        discovery.publish_service(SimpleNamespace(pi_id="pi-fixture"), ("https://pi.example:8080",))


def test_public_discovery_imports_without_posix_fcntl(monkeypatch):
    import builtins
    import importlib.util
    import sys

    original = builtins.__import__

    def without_fcntl(name, *args, **kwargs):
        if name == "fcntl":
            raise ModuleNotFoundError("Windows has no fcntl")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_fcntl)
    spec = importlib.util.spec_from_file_location("dispread.bridge._portable_discovery", discovery.__file__)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "discover_services", lambda timeout_s: ())
    assert module.discover_with_fallback(("https://pi.example:8080",))[0].endpoints == ("https://pi.example:8080",)


def test_windows_tailscale_process_is_hidden(monkeypatch):
    import subprocess
    import sys
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000, raising=False)
    calls = []
    def run(argv, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(returncode=0, stdout='{"BackendState":"Running"}')
    assert discovery.tailscale_status(run=run).state == 'running'
    assert calls[0]['creationflags'] == 0x08000000
