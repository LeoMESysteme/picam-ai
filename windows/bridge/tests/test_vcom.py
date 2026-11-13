"""Port ownership, PnP proof and bounded bidirectional checks."""
from dataclasses import replace

import pytest
from dispread_bridge_app.types import PortPair
from dispread_bridge_app.vcom import (
    MutationResult,
    PairStatus,
    VcomAdapter,
    VcomUnverifiedError,
)

PAIR = PortPair("pair-1", "COM11", "COM12", True)


class Backend:
    def __init__(self, statuses=(), *, admin=True, mutation=None, after=None):
        self.statuses = tuple(statuses)
        self.admin = admin
        self.mutation = mutation or MutationResult(0)
        self.after = after
        self.operations = []

    def inventory(self):
        return self.statuses

    def can_modify(self):
        return self.admin

    def _mutate(self, name):
        self.operations.append(name)
        if isinstance(self.mutation, Exception):
            raise self.mutation
        if self.after is not None:
            self.statuses = tuple(self.after)
        return self.mutation

    def create_pair(self):
        return self._mutate("create")

    def repair_pair(self, pair):
        return self._mutate(("repair", pair.pair_id))


class SerialLink:
    """External serial endpoints; records transferred bytes and released handles."""
    def __init__(self, *, drop_reverse=False, fail_second=False):
        self.buffers = {"COM11": bytearray(), "COM12": bytearray()}
        self.open = set()
        self.drop_reverse = drop_reverse
        self.fail_second = fail_second
        self.transfers = []

    def __call__(self, *, port, **kwargs):
        if self.fail_second and port == "COM12":
            raise PermissionError("occupied")
        link = self
        class Handle:
            def __enter__(self):
                link.open.add(port)
                return self
            def __exit__(self, *args):
                link.open.remove(port)
            def reset_input_buffer(self):
                link.buffers[port].clear()
            def write(self, data):
                link.transfers.append((port, data))
                other = "COM12" if port == "COM11" else "COM11"
                if not (link.drop_reverse and port == "COM12"):
                    link.buffers[other].extend(data)
                return len(data)
            def flush(self):
                pass
            def read(self, count):
                data = bytes(link.buffers[port][:count])
                del link.buffers[port][:count]
                return data
        return Handle()


def adapter(backend, link=None, **kwargs):
    return VcomAdapter(backend, serial_factory=link or SerialLink(), **kwargs)


def test_existing_busy_pair_is_not_changed():
    backend = Backend([PairStatus(PAIR, (0, 0), True)])
    result = adapter(backend, allow_mutations=True, allow_probe=True).ensure_pair(PAIR)
    assert (result.state, result.error_code) == ("busy", "pair_in_use")
    assert backend.operations == []


def test_uac_denied_is_resumable():
    backend = Backend(admin=False)
    vcom = adapter(backend, allow_mutations=True, allow_probe=True)
    assert vcom.ensure_pair(None).state == "admin_required"
    assert backend.operations == []
    backend.admin = True
    backend.after = [PairStatus(PAIR, (0, 0), False)]
    assert vcom.ensure_pair(None).state == "ready"


def test_installer_exit_zero_with_pnp_error_is_failure():
    backend = Backend(after=[PairStatus(PAIR, (0, 52), False)])
    result = adapter(backend, allow_mutations=True, allow_probe=True).ensure_pair(None)
    assert (result.state, result.error_code) == ("failed", "pnp_error:52")


def test_repair_creates_no_duplicate_pair():
    backend = Backend([PairStatus(PAIR, (28, 28), False)],
                      after=[PairStatus(PAIR, (0, 0), False)])
    vcom = adapter(backend, allow_mutations=True, allow_probe=True)
    assert vcom.ensure_pair(PAIR).state == "ready"
    assert vcom.ensure_pair(PAIR).state == "ready"
    assert backend.operations == [("repair", "pair-1")]


def test_foreign_broken_pair_is_never_repaired():
    foreign = replace(PAIR, owned=False)
    backend = Backend([PairStatus(foreign, (28, 28), False)])
    result = adapter(backend, allow_mutations=True).ensure_pair(foreign)
    assert result.error_code == "foreign_pair_unhealthy"
    assert backend.operations == []


def test_unselected_pair_needs_operator_even_if_only_one():
    backend = Backend([PairStatus(PAIR, (0, 0), False)])
    assert adapter(backend, allow_mutations=True).ensure_pair(None).state == "selection_required"
    assert backend.operations == []


def test_default_backend_refuses_unknown_driver_commands():
    vcom = VcomAdapter()
    assert vcom.ensure_pair(None).error_code == "driver_provider_unverified"
    with pytest.raises(VcomUnverifiedError):
        vcom.inventory()


def test_mutation_requires_explicit_authorization():
    backend = Backend()
    assert adapter(backend).ensure_pair(None).error_code == "mutation_not_authorized"
    assert backend.operations == []


def test_installer_without_device_is_not_success():
    result = adapter(Backend(), allow_mutations=True).ensure_pair(None)
    assert (result.state, result.error_code) == ("failed", "pair_not_created")


def test_reboot_needed_preserves_pair_for_resume():
    backend = Backend(mutation=MutationResult(3010, reboot_required=True),
                      after=[PairStatus(PAIR, (0, 0), False)])
    result = adapter(backend, allow_mutations=True).ensure_pair(None)
    assert (result.state, result.reboot_required, result.pair) == ("reboot_required", True, PAIR)


def test_unknown_pnp_health_never_releases_pair():
    backend = Backend([PairStatus(PAIR, (None, 0), False)])
    assert adapter(backend, allow_probe=True).ensure_pair(PAIR).error_code == "pnp_health_unknown"


def test_probe_needs_explicit_permission_in_setup():
    backend = Backend([PairStatus(PAIR, (0, 0), False)])
    assert adapter(backend).ensure_pair(PAIR).error_code == "probe_required"


def test_probe_checks_both_directions_and_releases_handles():
    backend = Backend([PairStatus(PAIR, (0, 0), False)])
    link = SerialLink()
    assert adapter(backend, link).probe_pair(PAIR)
    assert [port for port, data in link.transfers] == ["COM11", "COM12"]
    assert link.open == set()


def test_probe_reverse_failure_is_not_ready():
    backend = Backend([PairStatus(PAIR, (0, 0), False)])
    link = SerialLink(drop_reverse=True)
    result = adapter(backend, link, allow_probe=True).ensure_pair(PAIR)
    assert (result.state, result.error_code) == ("failed", "bidirectional_probe_failed")
    assert link.open == set()


def test_probe_second_handle_failure_releases_first():
    backend = Backend([PairStatus(PAIR, (0, 0), False)])
    link = SerialLink(fail_second=True)
    assert not adapter(backend, link).probe_pair(PAIR)
    assert link.open == set()


def test_saved_pair_missing_never_creates_replacement():
    backend = Backend()
    assert adapter(backend, allow_mutations=True).ensure_pair(PAIR).error_code == "saved_pair_missing"
    assert backend.operations == []


def test_duplicate_endpoint_inventory_is_ambiguous():
    other = PortPair("pair-2", "COM12", "COM13", False)
    backend = Backend([PairStatus(PAIR, (0, 0), False), PairStatus(other, (0, 0), False)])
    assert adapter(backend, allow_mutations=True).ensure_pair(PAIR).error_code == "ambiguous_pair_inventory"
    assert backend.operations == []


def test_stored_ownership_does_not_override_current_foreign_pair():
    backend = Backend([PairStatus(replace(PAIR, owned=False), (28, 28), False)])
    assert adapter(backend, allow_mutations=True).ensure_pair(PAIR).error_code == "foreign_pair_unhealthy"
    assert backend.operations == []


def test_cancelled_uac_remains_resumable():
    backend = Backend(mutation=PermissionError("UAC cancelled"))
    assert adapter(backend, allow_mutations=True).ensure_pair(None).state == "admin_required"


def test_unknown_usage_prevents_even_repair():
    backend = Backend([PairStatus(PAIR, (28, 28), None)])
    assert adapter(backend, allow_mutations=True).ensure_pair(PAIR).error_code == "pair_usage_unknown"
    assert backend.operations == []


@pytest.mark.parametrize("port", ["COM0", "COM11;whoami", "com1", "\\\\.\\COM1"])
def test_pair_rejects_unvalidated_port_names(port):
    with pytest.raises(ValueError):
        PortPair("unsafe", port, "COM12", True)


def test_renumbered_pair_is_resolved_by_pair_id():
    current = replace(PAIR, bridge_port="COM21", gsv_port="COM22")
    backend = Backend([PairStatus(current, (0, 0), False)])
    result = adapter(backend).ensure_pair(PAIR)
    assert result.pair == current
    assert result.error_code == "probe_required"
    assert backend.operations == []


def test_probe_failure_if_pnp_changed_between_setup_and_open():
    class ChangedBackend(Backend):
        queries = 0
        def inventory(self):
            self.queries += 1
            return (PairStatus(PAIR, (0, 0) if self.queries == 1 else (52, 0), False),)
    link = SerialLink()
    assert adapter(ChangedBackend(), link, allow_probe=True).ensure_pair(PAIR).state == "failed"
    assert link.transfers == []


def test_partial_write_fails_probe_and_closes_handles():
    class PartialLink(SerialLink):
        def __call__(self, **kwargs):
            handle = super().__call__(**kwargs)
            handle.write = lambda data: len(data) - 1
            return handle
    backend = Backend([PairStatus(PAIR, (0, 0), False)])
    link = PartialLink()
    assert not adapter(backend, link).probe_pair(PAIR)
    assert link.open == set()


def test_nonzero_installer_exit_never_releases_healthy_pair():
    backend = Backend(mutation=MutationResult(1), after=[PairStatus(PAIR, (0, 0), False)])
    result = adapter(backend, allow_mutations=True, allow_probe=True).ensure_pair(None)
    assert result.error_code == "installer_exit:1"
    assert result.state == "failed"


def test_probe_does_not_use_unbounded_driver_flush():
    class NoFlushLink(SerialLink):
        def __call__(self, **kwargs):
            handle = super().__call__(**kwargs)
            def unbounded_flush():
                raise AssertionError("FlushFileBuffers can block without write_timeout")
            handle.flush = unbounded_flush
            return handle
    backend = Backend([PairStatus(PAIR, (0, 0), False)])
    assert adapter(backend, NoFlushLink()).probe_pair(PAIR)


@pytest.mark.parametrize("existing", [None, PAIR], ids=["create", "repair"])
@pytest.mark.parametrize("mutation, state, code, reboot", [
    (MutationResult(3010, True), "reboot_required", "restart_then_verify", True),
    (MutationResult(1223), "admin_required", "elevation_denied", False),
    (MutationResult(5), "admin_required", "elevation_denied", False),
])
def test_resumable_mutation_outcome_survives_unavailable_inventory(existing, mutation, state, code, reboot):
    class RestartingBackend(Backend):
        def inventory(self):
            if self.operations:
                raise OSError("PnP temporarily unavailable during driver restart")
            return self.statuses
    backend = RestartingBackend(
        [PairStatus(PAIR, (28, 28), False)] if existing else (), mutation=mutation,
    )
    result = adapter(backend, allow_mutations=True, allow_probe=True).ensure_pair(existing)
    assert (result.state, result.error_code, result.reboot_required) == (state, code, reboot)
    assert result.pair == existing
