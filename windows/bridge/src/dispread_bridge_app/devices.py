"""Read-only Windows PnP + pySerial inventory, including USB driver failures.

PnP properties: https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-pnpentity
Serial metadata: https://pyserial.readthedocs.io/en/latest/tools.html
"""
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from .types import DeviceInfo, valid_port_name

# Static script only: no device IDs, paths or user strings are interpolated into code.
# Missing PortName is normal for a USB device with an uninstalled/broken driver.
_PNP_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$items = @(Get-CimInstance Win32_PnPEntity | Where-Object {
    $_.Present -eq $true -and ($_.PNPDeviceID -like 'USB\*' -or
    $_.PNPDeviceID -like 'FTDIBUS\*' -or $_.PNPClass -eq 'Ports')
} | ForEach-Object {
    $port = $null
    $key = 'Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Enum\' + $_.PNPDeviceID + '\Device Parameters'
    if (Test-Path -LiteralPath $key) {
        $port = (Get-ItemProperty -LiteralPath $key -Name PortName -ErrorAction SilentlyContinue).PortName
    }
    [PSCustomObject]@{
        instance_id = $_.PNPDeviceID
        port = $port
        pnp_error = $_.ConfigManagerErrorCode
    }
})
ConvertTo-Json -InputObject $items -Compress
"""


class DeviceSelectionError(ValueError):
    """Selection requires the operator, or the saved device is unavailable."""


def _execute(argv: tuple[str, ...]):
    if sys.platform != "win32":
        raise OSError("Windows PnP inventory is unavailable on this platform")
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", timeout=30, check=False)


def query_windows_pnp(execute: Callable = _execute) -> tuple[Mapping[str, Any], ...]:
    """Run an unprivileged, read-only inventory. Query failure is never absence."""
    result = execute(("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _PNP_SCRIPT))
    if result.returncode != 0:
        raise OSError(f"Windows PnP inventory failed ({result.returncode}): {result.stderr}")
    try:
        records = json.loads(result.stdout.lstrip("\ufeff"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("invalid Windows PnP inventory JSON") from exc
    if not isinstance(records, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("instance_id"), str)
        or not item["instance_id"] for item in records
    ):
        raise ValueError("invalid Windows PnP inventory records")
    return tuple(records)


def _serial_ports():
    from serial.tools.list_ports import comports
    return comports()


def _usb_fields(instance: str) -> tuple[int | None, int | None, str | None]:
    match = re.search(r"VID_([0-9A-F]{4})[&+]PID_([0-9A-F]{4})", instance, re.IGNORECASE)
    if not match:
        return None, None, None
    vid, pid = (int(value, 16) for value in match.groups())
    # Only the USB enumerator's final component is a serial. Generated location
    # IDs contain '&'; FTDIBUS channel suffixes are not guessed or stripped.
    serial = None
    if instance.upper().startswith("USB\\"):
        tail = instance.rsplit("\\", 1)[-1]
        if tail and "&" not in tail:
            serial = tail
    return vid, pid, serial


class WindowsDevices:
    def __init__(self, pnp_query: Callable[[], Iterable[Mapping]] = query_windows_pnp,
                 port_query: Callable[[], Iterable] = _serial_ports):
        self._pnp_query = pnp_query
        self._port_query = port_query

    def inventory(self) -> tuple[DeviceInfo, ...]:
        records = tuple(self._pnp_query())
        ports = {item.device.upper(): item for item in self._port_query()
                 if isinstance(item.device, str) and valid_port_name(item.device.upper())}
        devices = []
        used_ports = set()
        for row in records:
            instance = row["instance_id"]
            vid, pid, serial = _usb_fields(instance)
            raw_port = row.get("port")
            port = raw_port.upper() if isinstance(raw_port, str) else None
            if port is not None and not valid_port_name(port):
                port = None
            info = ports.get(port)
            location = None
            if info is not None:
                vid = vid if vid is not None else info.vid
                pid = pid if pid is not None else info.pid
                serial = info.serial_number or serial
                location = info.location
                used_ports.add(port)
            error = row.get("pnp_error")
            if error is not None and (not isinstance(error, int) or isinstance(error, bool) or error < 0):
                raise ValueError("invalid PnP error code")
            devices.append(DeviceInfo(instance, port, vid, pid, serial, location, error))
        for port, info in ports.items():
            if port not in used_ports:
                # No PnP record means health unknown, not healthy (0).
                devices.append(DeviceInfo(f"serial:{port}", port, info.vid, info.pid,
                                          info.serial_number, info.location, None))
        return tuple(sorted(devices, key=lambda item: item.instance_id.casefold()))

    def select_supported(self, identity: tuple | None = None) -> DeviceInfo:
        """No-serial instance selection must be confirmed for this attachment.

        A location-derived instance is not proof of the same physical adapter
        after reconnection; callers must obtain a new explicit selection then.
        """
        matches = [item for item in self.inventory() if item.is_supported
                   and (identity is None or item.identity == identity)]
        # A USB parent and its serial child can share the same serial identity.
        # Prefer the port node only when both identify exactly the same device.
        grouped = {}
        for item in matches:
            grouped.setdefault(item.identity, []).append(item)
        candidates = []
        for group in grouped.values():
            port_nodes = [item for item in group if item.port]
            candidates.extend(port_nodes or group)
        if not candidates:
            raise DeviceSelectionError("not_found")
        if len(candidates) != 1:
            raise DeviceSelectionError("selection_required")
        selected = candidates[0]
        if selected.instance_id.startswith("serial:") and not selected.serial:
            raise DeviceSelectionError("identity_unavailable")
        if identity is None and not selected.serial:
            raise DeviceSelectionError("selection_required")
        return selected
