"""Resumable component policy, independent of Windows installation mechanics.

No installation/elevation is performed by importing this module. The caller
supplies N2 adapters with explicit mutation/probe authorization. State and audit
paths are application-owned constructor inputs, never Pi-profile properties.
"""
import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from .types import InstallResult, PortPair
from .vcom import VcomUnverifiedError

_MAX_STATE = 128 * 1024


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON property')
        result[key] = value
    return result


def _read_json(path: Path, limit=_MAX_STATE):
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('state too large')
    return json.loads(raw, object_pairs_hook=_strict_object)


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(raw) > _MAX_STATE:
        raise ValueError('state too large')
    with temporary.open('wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _audit(path: Path, event):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, sort_keys=True, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def _state_lock(path: Path):
    """OS lock survives process crashes without a stale exclusive marker."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + '.lock').open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0, 2)
            if not stream.tell():
                stream.write(b'\0')
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


@dataclass(frozen=True)
class InstallRequest:
    selected_pair: PortPair | None = None
    cancelled: bool = False

    def __post_init__(self):
        if self.selected_pair is not None and not isinstance(self.selected_pair, PortPair):
            raise ValueError('selected_pair must be explicit')
        if type(self.cancelled) is not bool:
            raise ValueError('cancelled must be explicit')


def _pair(data):
    if data is None:
        return None
    if not isinstance(data, dict) or set(data) != {'pair_id', 'bridge_port', 'gsv_port', 'owned'}:
        raise ValueError('invalid pair')
    return PortPair(**data)


def _read_install(path):
    state = _read_json(path)
    if not isinstance(state, dict) or set(state) != {'schema_version', 'pending', 'previous_ready', 'result'} or type(state['schema_version']) is not int or state['schema_version'] != 1:
        raise ValueError('invalid install state')
    pending = state['pending']
    if not isinstance(pending, dict) or set(pending) != {'pair', 'before_ids', 'operation_started'}:
        raise ValueError('invalid pending install')
    _pair(pending['pair'])
    if (type(pending['operation_started']) is not bool or not isinstance(pending['before_ids'], list)
            or len(pending['before_ids']) > 512
            or any(not isinstance(item, str) or len(item) > 256 for item in pending['before_ids'])):
        raise ValueError('invalid inventory checkpoint')
    for result in (state['previous_ready'], state['result']):
        if result is not None:
            if not isinstance(result, dict) or set(result) != {'state', 'reboot_required', 'pair', 'error_code'}:
                raise ValueError('invalid result')
            _pair(result['pair'])
            if not isinstance(result['state'], str) or type(result['reboot_required']) is not bool:
                raise ValueError('invalid result values')
    return state


class Installer:
    def __init__(self, state_path: Path, *, audit_path: Path | None = None):
        self.state_path = Path(state_path)
        self.audit_path = Path(audit_path) if audit_path is not None else self.state_path.with_suffix('.audit.jsonl')

    def _finish(self, state, result):
        state['result'] = asdict(result)
        if result.pair is not None:
            state['pending']['pair'] = asdict(result.pair)
        if result.state == 'selection_required' and result.error_code == 'select_existing_pair':
            # N2 refused an unselected existing inventory before any mutation.
            # This is an operator choice, not an unresolved create checkpoint.
            state['pending']['operation_started'] = False
        if result.state == 'ready':
            state['previous_ready'] = asdict(result)
            state['pending']['operation_started'] = False
        _write_json(self.state_path, state)
        _audit(self.audit_path, {'action': 'ensure_components_result', **asdict(result)})
        return result

    def _run(self, state, request, devices, vcom, *, resume=False):
        if request.cancelled:
            return self._finish(state, InstallResult('cancelled', False, request.selected_pair, 'operator_cancelled'))
        # PnP failures are diagnostic failures, never an empty/healthy inventory.
        tuple(devices.inventory())
        pairs = tuple(vcom.inventory())
        selected = request.selected_pair
        pending = state['pending']
        if resume and selected is None and pending['operation_started']:
            new_owned = [pair for pair in pairs if pair.owned and pair.pair_id not in pending['before_ids']]
            if len(new_owned) > 1:
                return self._finish(state, InstallResult('selection_required', False, None, 'ambiguous_created_pairs'))
            if new_owned:
                selected = new_owned[0]
        # Checkpoint BEFORE any call that can create/repair. On restart inventory
        # reconciles a create whose process died before receiving its result.
        pending['pair'] = asdict(selected) if selected else None
        if not (resume and pending['operation_started']):
            pending['before_ids'] = [pair.pair_id for pair in pairs]
        pending['operation_started'] = True
        _write_json(self.state_path, state)
        _audit(self.audit_path, {'action': 'ensure_components_requested', 'pair_id': selected.pair_id if selected else None})
        return self._finish(state, vcom.ensure_pair(selected))

    def _guarded_run(self, state, request, devices, vcom, *, resume=False):
        try:
            return self._run(state, request, devices, vcom, resume=resume)
        except VcomUnverifiedError as exc:
            result = InstallResult('unverified', False, request.selected_pair, str(exc))
        except (ValueError, OSError):
            result = InstallResult('failed', False, request.selected_pair, 'install_state_or_inventory_unavailable')
        return self._finish(state, result)

    def ensure_components(self, request: InstallRequest, devices, vcom) -> InstallResult:
        try:
            with _state_lock(self.state_path):
                state = (_read_install(self.state_path) if self.state_path.exists() else
                         {'schema_version': 1, 'pending': {'pair': None, 'before_ids': [], 'operation_started': False},
                          'previous_ready': None, 'result': None})
                # Unfinished work must be reconciled before accepting a new request.
                pending = state['pending']
                if pending['operation_started']:
                    saved = _pair(pending['pair'])
                    if saved is not None and request.selected_pair is not None and saved.pair_id != request.selected_pair.pair_id:
                        return InstallResult('busy', False, saved, 'resume_pending_install_first')
                    # A create may have completed before its pair was known.
                    # An explicit current inventory selection resolves that
                    # ambiguity without another create; N2 rechecks the pair.
                    selected = saved if saved is not None else request.selected_pair
                    return self._guarded_run(state, InstallRequest(selected, request.cancelled), devices, vcom, resume=True)
                return self._guarded_run(state, request, devices, vcom)
        except VcomUnverifiedError as exc:
            return InstallResult('unverified', False, request.selected_pair, str(exc))
        except ValueError:
            return InstallResult('failed', False, request.selected_pair, 'invalid_install_state')
        except OSError:
            return InstallResult('failed', False, request.selected_pair, 'install_state_or_inventory_unavailable')

    def resume_install(self, state_path: Path, *, devices=None, vcom=None) -> InstallResult:
        from .devices import WindowsDevices
        from .vcom import VcomAdapter
        if Path(state_path).resolve() != self.state_path.resolve():
            return InstallResult('failed', False, None, 'state_path_mismatch')
        try:
            with _state_lock(self.state_path):
                state = _read_install(self.state_path)
                pair = _pair(state['pending']['pair'])
                return self._guarded_run(state, InstallRequest(pair), devices or WindowsDevices(), vcom or VcomAdapter(), resume=True)
        except VcomUnverifiedError as exc:
            return InstallResult('unverified', False, None, str(exc))
        except ValueError:
            return InstallResult('failed', False, None, 'invalid_install_state')
        except OSError:
            return InstallResult('failed', False, None, 'install_state_or_inventory_unavailable')


def resume_install(state_path: Path, *, devices=None, vcom=None) -> InstallResult:
    """Safe default refuses unqualified driver work; adapters may be injected."""
    return Installer(state_path).resume_install(state_path, devices=devices, vcom=vcom)
