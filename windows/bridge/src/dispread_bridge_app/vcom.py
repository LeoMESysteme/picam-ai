"""VCOM lifecycle policy with an injectable, independently verified driver backend.

There is deliberately no guessed setupc command or approved com0com package here.
The default backend refuses installation and inventory instead of treating an
unknown driver as absent. A real backend must prove its package, pair mapping,
PnP health and usage; command exit status alone never satisfies this adapter.
"""
import secrets
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Protocol

from .session_export import GSVMULTI_BAUD
from .types import InstallResult, PortPair


class VcomUnverifiedError(RuntimeError):
    """Real driver/provider evidence is missing; this is not an empty inventory."""


@dataclass(frozen=True)
class PairStatus:
    pair: PortPair
    pnp_errors: tuple[int | None, int | None]
    in_use: bool | None

    def __post_init__(self):
        if len(self.pnp_errors) != 2 or any(
            code is not None and (type(code) is not int or code < 0)
            for code in self.pnp_errors
        ):
            raise ValueError("both PnP error codes must be nonnegative integers or None")
        if self.in_use is not None and type(self.in_use) is not bool:
            raise ValueError("pair usage must be explicit or unknown")


@dataclass(frozen=True)
class MutationResult:
    exit_code: int
    reboot_required: bool = False


class DriverBackend(Protocol):
    """Privileged driver provider boundary, implemented only after Windows proof.

    inventory must return complete pairs, current app ownership, both endpoint
    ConfigManagerErrorCodes and whether another process uses either port.
    Unknown health/usage is None. can_modify includes current administrator
    authorization. create_pair chooses unused names; repair_pair acts on only
    the selected owned pair. Neither may remove foreign devices or drivers.
    Implementations must execute reviewed argument lists without shell=True,
    preserve original driver logs, and map UAC cancellation to PermissionError.
    Privileged operations must recheck availability/ownership atomically and
    serialize create/repair across application instances to avoid TOCTOU races.
    """
    def inventory(self) -> tuple[PairStatus, ...]: ...
    def can_modify(self) -> bool: ...
    def create_pair(self) -> MutationResult: ...
    def repair_pair(self, pair: PortPair) -> MutationResult: ...


class _UnverifiedBackend:
    def inventory(self):
        raise VcomUnverifiedError("driver_provider_unverified")

    def can_modify(self):
        return False

    def create_pair(self):
        raise VcomUnverifiedError("driver_provider_unverified")

    def repair_pair(self, pair):
        raise VcomUnverifiedError("driver_provider_unverified")


def _open_serial(**kwargs):
    if sys.platform != "win32":
        raise OSError("Windows VCOM probe is unavailable on this platform")
    from serial import Serial
    return Serial(**kwargs)


class VcomAdapter:
    def __init__(self, backend: DriverBackend | None = None, *, serial_factory=None,
                 allow_mutations: bool = False, allow_probe: bool = False):
        self._backend = backend if backend is not None else _UnverifiedBackend()
        self._serial_factory = serial_factory or _open_serial
        self._allow_mutations = allow_mutations
        self._allow_probe = allow_probe

    def _statuses(self) -> tuple[PairStatus, ...]:
        statuses = tuple(self._backend.inventory())
        ids = [status.pair.pair_id for status in statuses]
        ports = [port for status in statuses
                 for port in (status.pair.bridge_port, status.pair.gsv_port)]
        if len(set(ids)) != len(ids) or len(set(ports)) != len(ports):
            raise VcomUnverifiedError("ambiguous_pair_inventory")
        return statuses

    def inventory(self) -> tuple[PortPair, ...]:
        return tuple(status.pair for status in self._statuses())

    @staticmethod
    def _result(state, code=None, pair=None, reboot=False):
        return InstallResult(state, reboot, pair, code)

    def _ready(self, status: PairStatus) -> InstallResult:
        if status.in_use is True:
            return self._result("busy", "pair_in_use", status.pair)
        if status.in_use is None:
            return self._result("unverified", "pair_usage_unknown", status.pair)
        failures = [code for code in status.pnp_errors if code not in (0, None)]
        if failures:
            return self._result("failed", f"pnp_error:{failures[0]}", status.pair)
        if None in status.pnp_errors:
            return self._result("unverified", "pnp_health_unknown", status.pair)
        if not self._allow_probe:
            return self._result("unverified", "probe_required", status.pair)
        if not self.probe_pair(status.pair):
            return self._result("failed", "bidirectional_probe_failed", status.pair)
        return self._result("ready", pair=status.pair)

    def ensure_pair(self, existing: PortPair | None) -> InstallResult:
        """Reuse explicit selection, repair owned pairs, or create after authorization.

        UI callers grant mutation/probe permission only after target-system
        approval and after GSVmulti/the bridge release their serial handles.
        Reboot and UAC denial preserve the selected pair for a later call.
        """
        selected = None
        try:
            before = self._statuses()
            if existing is None:
                if before:
                    return self._result("selection_required", "select_existing_pair")
            else:
                matches = [status for status in before if status.pair.pair_id == existing.pair_id]
                if not matches:
                    return self._result("failed", "saved_pair_missing", existing)
                selected = matches[0]
                # Trust current backend ownership and current endpoint mapping.
                if selected.in_use is not False:
                    return self._ready(selected)
                if all(code == 0 for code in selected.pnp_errors):
                    return self._ready(selected)
                if None in selected.pnp_errors:
                    return self._result("unverified", "pnp_health_unknown", selected.pair)
                if not selected.pair.owned:
                    return self._result("failed", "foreign_pair_unhealthy", selected.pair)
            if not self._allow_mutations:
                return self._result("unverified", "mutation_not_authorized",
                                    selected.pair if selected else None)
            if not self._backend.can_modify():
                return self._result("admin_required", "administrator_required",
                                    selected.pair if selected else None)
            mutation = (self._backend.repair_pair(selected.pair) if selected
                        else self._backend.create_pair())
            # A command can require restart/elevation while PnP is unavailable.
            # Preserve that authoritative outcome; discovery only enriches it.
            known_pair = selected.pair if selected else None
            resume = None
            if mutation.exit_code in (5, 1223):
                resume = self._result("admin_required", "elevation_denied", known_pair)
            elif mutation.reboot_required or mutation.exit_code in (3010, 1641):
                resume = self._result("reboot_required", "restart_then_verify", known_pair, True)
            try:
                after = self._statuses()
            except (OSError, ValueError, VcomUnverifiedError):
                if resume is not None:
                    return resume
                raise
            if selected:
                candidates = [status for status in after if status.pair.pair_id == selected.pair.pair_id]
            else:
                old_ids = {status.pair.pair_id for status in before}
                candidates = [status for status in after if status.pair.pair_id not in old_ids
                              and status.pair.owned]
            pair = candidates[0].pair if len(candidates) == 1 else (selected.pair if selected else None)
            if resume is not None:
                return InstallResult(resume.state, resume.reboot_required, pair, resume.error_code)
            if mutation.exit_code != 0:
                return self._result("failed", f"installer_exit:{mutation.exit_code}", pair)
            if len(candidates) != 1:
                code = "pair_not_created" if not candidates else "ambiguous_created_pairs"
                return self._result("failed", code, pair)
            return self._ready(candidates[0])
        except PermissionError:
            return self._result("admin_required", "elevation_denied",
                                selected.pair if selected else existing)
        except VcomUnverifiedError as exc:
            return self._result("unverified", str(exc), selected.pair if selected else existing)
        except (OSError, ValueError):
            return self._result("failed", "driver_inventory_or_command_failed",
                                selected.pair if selected else existing)

    def probe_pair(self, pair: PortPair) -> bool:
        """Explicit self-test: caller closes GSVmulti first; handles always close.

        Only an inventoried, free, healthy pair may be opened. Random short
        markers in both directions prevent a stale echo from passing the check.
        This is a connectivity test, not a timestamp/latency measurement.
        """
        try:
            matches = [status for status in self._statuses() if status.pair == pair]
            if (len(matches) != 1 or matches[0].in_use is not False
                    or matches[0].pnp_errors != (0, 0)):
                return False
            with ExitStack() as stack:
                a, b = [stack.enter_context(self._serial_factory(
                    port=port, baudrate=GSVMULTI_BAUD, timeout=0.25, write_timeout=0.5
                )) for port in (pair.bridge_port, pair.gsv_port)]
                a.reset_input_buffer()
                b.reset_input_buffer()
                for sender, receiver in ((a, b), (b, a)):
                    marker = b"dispread-probe:" + secrets.token_bytes(24)
                    if sender.write(marker) != len(marker):
                        return False
                    # Windows FlushFileBuffers/pySerial.flush has no bounded
                    # timeout; the receiving read proves delivery instead.
                    received = bytearray()
                    deadline = time.monotonic() + 1.0
                    while len(received) < len(marker) and time.monotonic() < deadline:
                        chunk = receiver.read(len(marker) - len(received))
                        if not chunk:
                            return False
                        received.extend(chunk)
                    if received != marker:
                        return False
            return True
        except (OSError, ValueError, VcomUnverifiedError):
            return False
