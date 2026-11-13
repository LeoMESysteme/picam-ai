"""Portable state and privilege boundary tests; no Windows mutation is executed."""
import json
from dataclasses import replace

import pytest
from dispread_bridge_app.admin_helper import AdminHelper, HelperRequestError
from dispread_bridge_app.install import Installer, InstallRequest
from dispread_bridge_app.vcom import MutationResult, PairStatus, VcomAdapter
from test_vcom import PAIR, Backend, SerialLink


class Devices:
    def inventory(self):
        return ()


def adapter(backend):
    return VcomAdapter(backend, serial_factory=SerialLink(), allow_mutations=True, allow_probe=True)


def test_uac_denial_keeps_previous_working_install(tmp_path):
    backend = Backend([PairStatus(PAIR, (0, 0), False)])
    installer = Installer(tmp_path / 'state.json')
    request = InstallRequest(selected_pair=PAIR)
    assert installer.ensure_components(request, Devices(), adapter(backend)).state == 'ready'
    backend.statuses = (PairStatus(PAIR, (28, 28), False),)
    backend.mutation = PermissionError('UAC denied')
    assert installer.ensure_components(request, Devices(), adapter(backend)).state == 'admin_required'
    state = json.loads((tmp_path / 'state.json').read_text())
    assert state['previous_ready']['pair']['pair_id'] == 'pair-1'
    backend.mutation = MutationResult(0)
    backend.after = [PairStatus(PAIR, (0, 0), False)]
    assert Installer(tmp_path / 'state.json').resume_install(tmp_path / 'state.json', devices=Devices(), vcom=adapter(backend)).state == 'ready'
    assert backend.operations == [('repair', 'pair-1'), ('repair', 'pair-1')]


def test_reboot_resume_reuses_created_pair(tmp_path):
    backend = Backend(mutation=MutationResult(3010, True), after=[PairStatus(PAIR, (0, 0), False)])
    path = tmp_path / 'state.json'
    installer = Installer(path)
    result = installer.ensure_components(InstallRequest(), Devices(), adapter(backend))
    assert result.state == 'reboot_required'
    assert json.loads(path.read_text())['pending']['pair']['pair_id'] == 'pair-1'
    assert Installer(path).resume_install(path, devices=Devices(), vcom=adapter(backend)).state == 'ready'
    assert backend.operations == ['create']


def test_crash_after_create_reconciles_before_retry(tmp_path):
    class CrashedBackend(Backend):
        def create_pair(self):
            self.statuses = (PairStatus(PAIR, (0, 0), False),)
            raise KeyboardInterrupt('power loss before result checkpoint')
    backend = CrashedBackend()
    path = tmp_path / 'state.json'
    with pytest.raises(KeyboardInterrupt):
        Installer(path).ensure_components(InstallRequest(), Devices(), adapter(backend))
    assert Installer(path).resume_install(path, devices=Devices(), vcom=adapter(backend)).state == 'ready'


def test_cancel_persists_without_changing_pair(tmp_path):
    backend = Backend()
    path = tmp_path / 'state.json'
    result = Installer(path).ensure_components(InstallRequest(cancelled=True), Devices(), adapter(backend))
    assert result.state == 'cancelled'
    assert backend.operations == []
    assert json.loads(path.read_text())['result']['state'] == 'cancelled'


def test_unknown_driver_is_not_treated_as_absent(tmp_path):
    result = Installer(tmp_path / 'state.json').ensure_components(InstallRequest(), Devices(), VcomAdapter())
    assert result.state == 'unverified'
    assert result.error_code == 'driver_provider_unverified'


def test_corrupt_state_cannot_trigger_new_pair(tmp_path):
    path = tmp_path / 'state.json'
    path.write_text('{"command":"whoami"}')
    backend = Backend()
    assert Installer(path).resume_install(path, devices=Devices(), vcom=adapter(backend)).error_code == 'invalid_install_state'
    assert backend.operations == []


def test_uninstall_preserves_borrowed_pair_and_audits(tmp_path):
    borrowed = replace(PAIR, owned=False)
    backend = Backend([PairStatus(borrowed, (0, 0), False)])
    audit = tmp_path / 'audit.jsonl'
    audit.write_text('{"existing_audit":true}\n')
    helper = AdminHelper(backend, audit_path=audit, authorized=True)
    result = helper.execute(b'{"schema_version":1,"action":"remove_unused_owned_pair","pair_id":"pair-1"}')
    assert result.error_code == 'borrowed_pair_preserved'
    assert backend.inventory()[0].pair == borrowed
    events = [json.loads(line) for line in audit.read_text().splitlines()]
    assert events[0] == {'existing_audit': True}
    assert events[-1]['error_code'] == 'borrowed_pair_preserved'


@pytest.mark.parametrize('extra', [b',"command":"whoami"', b',"path":"C:\\\\evil.exe"'])
def test_helper_rejects_arbitrary_fields(tmp_path, extra):
    helper = AdminHelper(Backend(), audit_path=tmp_path / 'audit', authorized=True)
    with pytest.raises(HelperRequestError):
        helper.execute(b'{"schema_version":1,"action":"create_pair"' + extra + b'}')


@pytest.mark.parametrize('usage', [True, None])
def test_helper_never_removes_busy_or_unknown_usage(tmp_path, usage):
    backend = Backend([PairStatus(PAIR, (0, 0), usage)])
    result = AdminHelper(backend, audit_path=tmp_path / 'audit', authorized=True).execute(
        b'{"schema_version":1,"action":"remove_unused_owned_pair","pair_id":"pair-1"}')
    assert result.state != 'ready'
    assert backend.inventory()[0].pair == PAIR


def test_helper_requires_explicit_authorization(tmp_path):
    backend = Backend()
    result = AdminHelper(backend, audit_path=tmp_path / 'audit').execute(b'{"schema_version":1,"action":"create_pair"}')
    assert result.error_code == 'administrator_required'
    assert backend.operations == []


def test_audit_failure_prevents_driver_mutation(tmp_path):
    backend = Backend()
    helper = AdminHelper(backend, audit_path=tmp_path, authorized=True)
    result = helper.execute(b'{"schema_version":1,"action":"create_pair"}')
    assert result.error_code == 'audit_unavailable'
    assert backend.operations == []


def test_boolean_schema_cannot_authorize_state_resume(tmp_path):
    path = tmp_path / 'state.json'
    path.write_text(json.dumps({'schema_version': True, 'pending': {'pair': None,
        'before_ids': [], 'operation_started': False}, 'previous_ready': None, 'result': None}))
    backend = Backend(after=[PairStatus(PAIR, (0, 0), False)])
    assert Installer(path).resume_install(path, devices=Devices(), vcom=adapter(backend)).error_code == 'invalid_install_state'
    assert backend.operations == []


def test_failed_inventory_replaces_last_result_but_retains_historical_ready(tmp_path):
    path = tmp_path / 'state.json'
    installer = Installer(path)
    request = InstallRequest(PAIR)
    assert installer.ensure_components(request, Devices(), adapter(Backend([PairStatus(PAIR, (0, 0), False)]))).state == 'ready'
    assert installer.ensure_components(request, Devices(), VcomAdapter()).state == 'unverified'
    state = json.loads(path.read_text())
    assert state['result']['state'] == 'unverified'
    assert state['previous_ready']['state'] == 'ready'


@pytest.mark.parametrize('owned', [False, True], ids=['borrowed', 'owned'])
def test_existing_pair_selection_can_continue_without_new_mutation(tmp_path, owned):
    pair = replace(PAIR, owned=owned)
    backend = Backend([PairStatus(pair, (0, 0), False)])
    path = tmp_path / 'state.json'
    installer = Installer(path)
    assert installer.ensure_components(InstallRequest(), Devices(), adapter(backend)).state == 'selection_required'
    state = json.loads(path.read_text())
    assert state['pending']['operation_started'] is False
    result = Installer(path).ensure_components(InstallRequest(pair), Devices(), adapter(backend))
    assert (result.state, result.pair) == ('ready', pair)
    assert backend.operations == []


def test_multiple_pairs_recovered_after_crash_accept_explicit_choice(tmp_path):
    other = replace(PAIR, pair_id='pair-2', bridge_port='COM21', gsv_port='COM22')
    class CrashedBackend(Backend):
        def create_pair(self):
            self.operations.append('create')
            self.statuses = (PairStatus(PAIR, (0, 0), False), PairStatus(other, (0, 0), False))
            raise KeyboardInterrupt('process died before identifying newly created pair')
    backend = CrashedBackend()
    path = tmp_path / 'state.json'
    with pytest.raises(KeyboardInterrupt):
        Installer(path).ensure_components(InstallRequest(), Devices(), adapter(backend))
    result = Installer(path).resume_install(path, devices=Devices(), vcom=adapter(backend))
    assert (result.state, result.error_code) == ('selection_required', 'ambiguous_created_pairs')
    state = json.loads(path.read_text())
    assert state['pending']['operation_started'] is True
    assert state['pending']['before_ids'] == []
    selected = Installer(path).ensure_components(InstallRequest(PAIR), Devices(), adapter(backend))
    assert (selected.state, selected.pair) == ('ready', PAIR)
    assert backend.operations == ['create']


def test_explicit_pair_selection_rechecks_current_usage(tmp_path):
    backend = Backend([PairStatus(PAIR, (0, 0), False)])
    path = tmp_path / 'state.json'
    assert Installer(path).ensure_components(InstallRequest(), Devices(), adapter(backend)).state == 'selection_required'
    backend.statuses = (PairStatus(PAIR, (0, 0), True),)
    result = Installer(path).ensure_components(InstallRequest(PAIR), Devices(), adapter(backend))
    assert (result.state, result.error_code) == ('busy', 'pair_in_use')
    assert backend.operations == []
