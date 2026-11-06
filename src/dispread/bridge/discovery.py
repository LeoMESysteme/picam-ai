"""Optional, bounded discovery. Every result remains an unverified candidate."""

from __future__ import annotations

import importlib
import ipaddress
import json
import math
import multiprocessing
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from .protocol import _endpoint, _identifier

SERVICE_TYPE = "_dispread-bridge._tcp.local."


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    pi_id_hint: str | None
    name: str
    endpoints: tuple[str, ...]


def _timeout(timeout_s):
    if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or not 0 < timeout_s <= 10:
        raise ValueError("discovery timeout must be finite and in (0, 10] seconds")
    return float(timeout_s)


def _mdns_module():
    # Optional Debian python3-zeroconf. Explicit endpoints do not depend on it.
    return importlib.import_module("zeroconf")


def _candidate(info):
    props = info.properties
    if props.get(b"version") != b"2":
        raise ValueError("unsupported discovered protocol")
    raw = props[b"endpoints"]
    if len(raw) > 8192:
        raise ValueError("oversized discovery TXT")
    endpoints = json.loads(raw.decode("utf-8"))
    if not isinstance(endpoints, list) or not 1 <= len(endpoints) <= 8:
        raise ValueError("invalid discovered endpoints")
    for endpoint in endpoints:
        _endpoint(endpoint)
    name = props[b"name"].decode("utf-8")
    pi_id = props[b"pi_id"].decode("ascii")
    if not name or len(name) > 256 or any(ord(c) < 32 for c in name):
        raise ValueError("invalid discovered name")
    _identifier(pi_id)
    return DiscoveryCandidate(pi_id, name, tuple(dict.fromkeys(endpoints)))


def _browse_services(timeout_s: float) -> tuple[DiscoveryCandidate, ...]:
    """Browse for at most ten seconds, then resolve inside the remaining budget.

    Missing optional support yields no candidates. Names and TXT records are
    attacker controlled: bounded parsing here does not verify a Pi identity.
    """
    timeout_s = _timeout(timeout_s)
    try:
        mdns = _mdns_module()
    except ImportError:
        return ()
    names = set()
    lock = threading.Lock()

    class Listener:
        def add_service(self, zc, kind, name):
            with lock:
                if len(names) < 64:
                    names.add(name)

        update_service = add_service

        def remove_service(self, zc, kind, name):
            with lock:
                names.discard(name)

    zc = mdns.Zeroconf()
    browser = None
    deadline = time.monotonic() + timeout_s
    try:
        browser = mdns.ServiceBrowser(zc, SERVICE_TYPE, listener=Listener())
        threading.Event().wait(timeout_s / 2)
        with lock:
            snapshot = tuple(sorted(names))
        candidates = []
        for name in snapshot:
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                break
            info = zc.get_service_info(SERVICE_TYPE, name, timeout=remaining_ms)
            if info is not None:
                try:
                    candidate = _candidate(info)
                except (KeyError, TypeError, UnicodeError, ValueError):
                    continue
                if candidate not in candidates:
                    candidates.append(candidate)
        return tuple(candidates)
    except mdns.Error as error:
        raise OSError("mDNS discovery unavailable") from error
    finally:
        if browser is not None:
            browser.cancel()
        zc.close()


def _discovery_worker(result_path, timeout_s):
    """Spawn-safe worker; only bounded public hints cross the process boundary."""
    try:
        candidates = _browse_services(timeout_s)
        values = []
        for candidate in candidates[:64]:
            proposed = values + [asdict(candidate)]
            if len(json.dumps(proposed).encode("utf-8")) <= 65536:
                values = proposed
        raw = json.dumps(values).encode("utf-8")
    except Exception:  # Optional adapter errors are unavailable discovery, never trust.
        raw = b"[]"
    Path(result_path).write_bytes(raw)


def _start_discovery(result_path, timeout_s):
    process = multiprocessing.get_context("spawn").Process(
        target=_discovery_worker,
        args=(str(result_path), timeout_s),
        daemon=True,
    )
    process.start()
    return process


def discover_services(timeout_s: float) -> tuple[DiscoveryCandidate, ...]:
    """Hard deadline for optional SDK import/start/query/shutdown, plus <=0.4s cleanup.

    The spawned worker's bounded regular result file is read only after exit;
    unlike a pipe read, a partial IPC frame cannot block the caller. Frozen
    Windows entrypoints must use multiprocessing.freeze_support().
    """
    timeout_s = _timeout(timeout_s)
    deadline = time.monotonic() + timeout_s
    with tempfile.TemporaryDirectory(prefix="dispread-discovery-") as directory:
        result_path = Path(directory) / "candidates.json"
        process = None
        try:
            process = _start_discovery(result_path, timeout_s)
            process.join(timeout=max(0, deadline - time.monotonic()))
            if process.is_alive() or process.exitcode != 0:
                return ()
            with result_path.open("rb") as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                return ()
            values = json.loads(raw)
            if not isinstance(values, list) or len(values) > 64:
                return ()
            candidates = []
            for value in values:
                if not isinstance(value, dict) or set(value) != {"pi_id_hint", "name", "endpoints"}:
                    return ()
                # Revalidate all worker output, including strict endpoint URLs.
                props = {
                    b"version": b"2",
                    b"pi_id": value["pi_id_hint"].encode("ascii"),
                    b"name": value["name"].encode("utf-8"),
                    b"endpoints": json.dumps(value["endpoints"]).encode("utf-8"),
                }
                candidates.append(_candidate(SimpleNamespace(properties=props)))
            return tuple(candidates)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
            return ()
        finally:
            if process is not None:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=0.2)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=0.2)
                if not process.is_alive():
                    process.close()


def discover_with_fallback(
    explicit_endpoints: tuple[str, ...], *, timeout_s: float = 2
) -> tuple[DiscoveryCandidate, ...]:
    """Keep configured addresses usable even when multicast is unavailable."""
    if len(explicit_endpoints) > 8:
        raise ValueError("too many explicit endpoints")
    for endpoint in explicit_endpoints:
        _endpoint(endpoint)
    explicit = (DiscoveryCandidate(None, "Explicit endpoint", tuple(explicit_endpoints)),) if explicit_endpoints else ()
    try:
        return explicit + discover_services(timeout_s)
    except (ImportError, OSError):
        return explicit


class _Publication:
    def __init__(self, zc, info):
        self.zc, self.info = zc, info

    def close(self):
        if self.zc is not None:
            try:
                self.zc.unregister_service(self.info)
            finally:
                self.zc.close()
                self.zc = None


def publish_service(identity, endpoints: tuple[str, ...], *, name: str = "Dispread Pi"):
    """Publish only public routing hints; caller handles missing optional mDNS.

    This opens only mDNS sockets, never an application listener or identity provisioning. No offers, keys, tokens
    or audit/run data are advertised. close() withdraws the advertisement.
    """
    if not endpoints or len(endpoints) > 8:
        raise ValueError("publication requires 1..8 configured endpoints")
    for endpoint in endpoints:
        _endpoint(endpoint)
    if not isinstance(name, str) or not 1 <= len(name) <= 256 or any(ord(c) < 32 for c in name):
        raise ValueError("invalid service name")
    properties = {
        "version": "2",
        "pi_id": identity.pi_id,
        "name": name,
        "endpoints": json.dumps(endpoints, separators=(",", ":")),
    }
    # One DNS TXT string has a one-byte length. Oversized optional discovery
    # is refused explicitly; the complete configured profile remains usable.
    if any(len(key.encode("utf-8")) + 1 + len(value.encode("utf-8")) > 255 for key, value in properties.items()):
        raise ValueError("discovery TXT entry exceeds 255 bytes; use explicit profile endpoints")
    mdns = _mdns_module()
    url = urlsplit(endpoints[0])
    addresses = []
    for endpoint in endpoints:
        host = urlsplit(endpoint).hostname
        try:
            addresses.append(ipaddress.ip_address(host).packed)
        except ValueError:
            pass  # No unbounded hostname lookup during publication.
    info = mdns.ServiceInfo(
        SERVICE_TYPE,
        f"dispread-{identity.pi_id}.{SERVICE_TYPE}",
        addresses=addresses,
        port=url.port or 443,
        server=(url.hostname.rstrip(".") + ".") if not addresses else f"dispread-{identity.pi_id}.local.",
        properties=properties,
    )
    try:
        zc = mdns.Zeroconf()
    except mdns.Error as error:
        raise OSError("mDNS publication unavailable") from error
    try:
        zc.register_service(info)
    except mdns.Error as error:
        zc.close()
        raise OSError("mDNS publication unavailable") from error
    except BaseException:
        zc.close()
        raise
    return _Publication(zc, info)


@dataclass(frozen=True, slots=True)
class TailscaleStatus:
    state: str


def tailscale_status(*, run=subprocess.run, connection_error: OSError | None = None) -> TailscaleStatus:
    """Read-only evidence, never infer ACL denial/offline from a timeout.

    connection_error may be a concrete DNS exception from the endpoint attempt;
    this function does not perform a DNS query or change network configuration.
    """
    try:
        result = run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=2, check=False)
    except FileNotFoundError:
        return TailscaleStatus("not_installed")
    except (OSError, subprocess.TimeoutExpired):
        return TailscaleStatus("unreachable")
    if result.returncode != 0 or len(result.stdout) > 65536:
        return TailscaleStatus("unreachable")
    try:
        data = json.loads(result.stdout)
        state = data.get("BackendState") if isinstance(data, dict) else None
    except (ValueError, TypeError):
        return TailscaleStatus("unreachable")
    if state == "NeedsLogin":
        return TailscaleStatus("logged_out")
    if state == "NeedsMachineAuth":
        return TailscaleStatus("needs_approval")
    if state == "Running":
        return TailscaleStatus("dns_error" if isinstance(connection_error, socket.gaierror) else "running")
    return TailscaleStatus("unreachable")
