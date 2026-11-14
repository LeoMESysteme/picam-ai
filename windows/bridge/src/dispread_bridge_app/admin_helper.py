"""Structured privileged-provider boundary. This is NOT an elevation launcher.

The native launcher/ACL/package-signature checks still require Windows proof.
Only a provider from the trusted installed package may be injected. Providers
must serialize mutations and recheck ownership/usage atomically (N2 contract).
No executable, shell command, driver URL or write path is accepted as data.
"""
import json
import re
from pathlib import Path

from .install import _audit, _state_lock, _strict_object
from .types import InstallResult
from .vcom import VcomUnverifiedError


class HelperRequestError(ValueError):
    pass


class AdminHelper:
    def __init__(self, backend, *, audit_path: Path, authorized: bool = False):
        self._backend = backend
        self._audit_path = Path(audit_path)
        self._authorized = authorized is True

    @staticmethod
    def _parse(payload):
        try:
            if not isinstance(payload, bytes) or len(payload) > 2048:
                raise ValueError('helper request size')
            request = json.loads(payload, object_pairs_hook=_strict_object)
            if not isinstance(request, dict) or type(request.get('schema_version')) is not int or request['schema_version'] != 1:
                raise ValueError('helper schema')
            action = request.get('action')
            if action not in ('inventory', 'create_pair', 'repair_owned_pair', 'remove_unused_owned_pair'):
                raise ValueError('helper action')
            keys = {'schema_version', 'action'}
            if action in ('repair_owned_pair', 'remove_unused_owned_pair'):
                keys.add('pair_id')
                if not isinstance(request.get('pair_id'), str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', request['pair_id']):
                    raise ValueError('helper pair id')
            if set(request) != keys:
                raise ValueError('unexpected helper fields')
            return request
        except (ValueError, TypeError, RecursionError) as exc:
            raise HelperRequestError('invalid structured helper request') from exc

    def execute(self, payload: bytes):
        request = self._parse(payload)
        pair = None
        try:
            with _state_lock(self._audit_path):
                _audit(self._audit_path, {'event': 'requested', **request})
                statuses = tuple(self._backend.inventory())
                ids = [item.pair.pair_id for item in statuses]
                ports = [port for item in statuses for port in (item.pair.bridge_port, item.pair.gsv_port)]
                if len(set(ids)) != len(ids) or len(set(ports)) != len(ports):
                    result = InstallResult('unverified', False, None, 'ambiguous_pair_inventory')
                elif request['action'] == 'inventory':
                    _audit(self._audit_path, {'event': 'inventory', 'pair_ids': ids})
                    return statuses
                elif not self._authorized or not self._backend.can_modify():
                    result = InstallResult('admin_required', False, None, 'administrator_required')
                else:
                    result = None
                    if 'pair_id' in request:
                        matches = [item for item in statuses if item.pair.pair_id == request['pair_id']]
                        if len(matches) != 1:
                            result = InstallResult('failed', False, None, 'saved_pair_missing')
                        else:
                            status = matches[0]
                            pair = status.pair
                            if not pair.owned:
                                result = InstallResult('retained', False, pair, 'borrowed_pair_preserved')
                            elif status.in_use is not False:
                                result = InstallResult('busy', False, pair, 'pair_usage_unknown' if status.in_use is None else 'pair_in_use')
                    elif statuses:
                        result = InstallResult('selection_required', False, None, 'select_existing_pair')
                    if result is None:
                        action = request['action']
                        if action == 'create_pair':
                            mutation = self._backend.create_pair()
                        elif action == 'repair_owned_pair':
                            mutation = self._backend.repair_pair(pair)
                        else:
                            # Optional provider operation: default N2 adapter does
                            # not invent unverified removal command grammar.
                            remove = getattr(self._backend, 'remove_unused_owned_pair', None)
                            if remove is None:
                                raise VcomUnverifiedError('removal_provider_unverified')
                            mutation = remove(pair)
                        if mutation.reboot_required or mutation.exit_code in (3010, 1641):
                            result = InstallResult('reboot_required', True, pair, 'restart_then_verify')
                        elif mutation.exit_code in (5, 1223):
                            result = InstallResult('admin_required', False, pair, 'elevation_denied')
                        elif mutation.exit_code:
                            result = InstallResult('failed', False, pair, f'installer_exit:{mutation.exit_code}')
                        else:
                            # A successful command alone never proves readiness.
                            result = InstallResult('verification_required', False, pair, 'inventory_and_probe_required')
                _audit(self._audit_path, {'event': 'result', 'action': request['action'], 'state': result.state, 'error_code': result.error_code})
                return result
        except PermissionError:
            return InstallResult('admin_required', False, pair, 'elevation_denied')
        except VcomUnverifiedError as exc:
            return InstallResult('unverified', False, pair, str(exc))
        except OSError:
            return InstallResult('failed', False, pair, 'audit_unavailable')
