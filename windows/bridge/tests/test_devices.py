"""PnP inventory must not confuse a failed driver with an absent adapter."""
from types import SimpleNamespace

import pytest
from dispread_bridge_app.devices import DeviceSelectionError, WindowsDevices, query_windows_pnp


def pnp(instance=r"USB\VID_0403&PID_6001\FT123", port=None, error=0):
    return {"instance_id": instance, "port": port, "pnp_error": error}


def serial(port="COM6", serial="FT123"):
    return SimpleNamespace(device=port, vid=0x0403, pid=0x6001,
                           serial_number=serial, location="1-2")


def test_usb_without_driver_is_not_absent():
    devices = WindowsDevices(lambda: [pnp(error=28)], lambda: []).inventory()
    assert len(devices) == 1
    assert (devices[0].vid, devices[0].pid, devices[0].port, devices[0].pnp_error) == (
        0x0403, 0x6001, None, 28)
    assert devices[0].is_supported


def test_renumbered_usb_keeps_serial_identity():
    first = WindowsDevices(lambda: [pnp(port="COM6")], lambda: [serial()])
    later = WindowsDevices(lambda: [pnp(port="COM9")], lambda: [serial("COM9")])
    selected = first.select_supported()
    found = later.select_supported(selected.identity)
    assert found.identity == selected.identity
    assert found.port == "COM9"


def test_duplicate_vid_pid_needs_selection():
    devices = WindowsDevices(lambda: [pnp(), pnp(r"USB\VID_0403&PID_6001\FT456")], lambda: [])
    with pytest.raises(DeviceSelectionError, match="selection_required"):
        devices.select_supported()


def test_missing_serial_uses_instance_identity_not_port():
    devices = WindowsDevices(lambda: [pnp(r"USB\VID_0403&PID_6001\5&abc&0&2", "COM6")], lambda: [])
    found = devices.inventory()[0]
    assert found.serial is None
    assert found.identity == ("instance", r"usb\vid_0403&pid_6001\5&abc&0&2")


def test_pnp_failure_is_preserved_despite_serial_listing():
    found = WindowsDevices(lambda: [pnp(port="COM6", error=52)], lambda: [serial()]).inventory()[0]
    assert found.pnp_error == 52


def test_unrelated_usb_is_not_selected():
    devices = WindowsDevices(lambda: [pnp(r"USB\VID_1234&PID_5678\OTHER")], lambda: [])
    with pytest.raises(DeviceSelectionError, match="not_found"):
        devices.select_supported()


def test_inventory_does_not_silently_hide_query_failure():
    def broken():
        raise OSError("PnP access failed")
    with pytest.raises(OSError, match="PnP access failed"):
        WindowsDevices(broken, lambda: []).inventory()


def test_windows_query_is_read_only_argv_and_rejects_bad_output():
    commands = []
    def execute(argv):
        commands.append(argv)
        return SimpleNamespace(returncode=0, stdout='[{"instance_id":"USB\\\\VID_0403&PID_6001\\\\FT123","pnp_error":28,"port":null}]', stderr="")
    assert query_windows_pnp(execute)[0]["pnp_error"] == 28
    assert commands[0][:3] == ("powershell.exe", "-NoProfile", "-NonInteractive")
    with pytest.raises(ValueError, match="inventory"):
        query_windows_pnp(lambda argv: SimpleNamespace(returncode=0, stdout='null', stderr=""))


def test_serial_only_port_has_unknown_pnp_health():
    found = WindowsDevices(lambda: [], lambda: [serial()]).inventory()[0]
    assert found.pnp_error is None
    assert found.serial == "FT123"


def test_usb_parent_and_ftdi_child_share_serial_selection():
    devices = WindowsDevices(lambda: [
        pnp(), pnp(r"FTDIBUS\VID_0403+PID_6001+FT123A\0000", "COM6"),
    ], lambda: [serial()])
    found = devices.select_supported()
    assert found.port == "COM6"
    assert found.identity == ("usb", 0x0403, 0x6001, "ft123")


def test_port_without_serial_or_pnp_identity_cannot_be_persistently_selected():
    devices = WindowsDevices(lambda: [], lambda: [serial(serial=None)])
    with pytest.raises(DeviceSelectionError, match="identity_unavailable"):
        devices.select_supported()


def test_duplicate_serial_on_two_port_nodes_is_ambiguous():
    devices = WindowsDevices(lambda: [
        pnp(r"FTDIBUS\VID_0403+PID_6001+FT123A\0000", "COM6"),
        pnp(r"FTDIBUS\VID_0403+PID_6001+FT123B\0000", "COM9"),
    ], lambda: [serial(), serial("COM9")])
    with pytest.raises(DeviceSelectionError, match="selection_required"):
        devices.select_supported()


def test_no_serial_device_requires_explicit_instance_selection():
    devices = WindowsDevices(lambda: [
        pnp(r"USB\VID_0403&PID_6001\5&abc&0&2", "COM6"),
    ], lambda: [])
    with pytest.raises(DeviceSelectionError, match="selection_required"):
        devices.select_supported()
    selected = devices.select_supported(("instance", r"usb\vid_0403&pid_6001\5&abc&0&2"))
    assert selected.port == "COM6"
    assert selected.serial is None


def test_pnp_inventory_is_cached_but_serial_presence_is_live():
    now, calls, attached = [0.], [], [serial()]
    def query():
        calls.append(now[0])
        return [pnp(port='COM6')]
    devices = WindowsDevices(query, lambda: attached, clock=lambda: now[0])
    assert devices.inventory()[0].port == 'COM6'
    devices.inventory()
    assert calls == [0.]
    now[0] = 31.
    devices.inventory()
    assert calls == [0., 31.]
    devices.invalidate_pnp()
    devices.inventory()
    assert calls == [0., 31., 31.]


def test_windows_pnp_process_has_no_console(monkeypatch):
    from dispread_bridge_app import devices
    monkeypatch.setattr(devices.sys, 'platform', 'win32')
    monkeypatch.setattr(devices.subprocess, 'CREATE_NO_WINDOW', 0x08000000, raising=False)
    seen = []
    def run(argv, **kw):
        seen.append(kw)
        return SimpleNamespace(returncode=0, stdout='[]')
    monkeypatch.setattr(devices.subprocess, 'run', run)
    assert devices.query_windows_pnp() == ()
    assert seen[0]['creationflags'] == 0x08000000


def test_failed_pnp_query_is_cached_until_explicit_rescan():
    calls = []
    def broken():
        calls.append(1)
        raise OSError('unavailable')
    devices = WindowsDevices(broken, lambda: [])
    for _ in range(3):
        with pytest.raises(OSError):
            devices.inventory()
    assert len(calls) == 1
    devices.invalidate_pnp()
    with pytest.raises(OSError):
        devices.inventory()
    assert len(calls) == 2
