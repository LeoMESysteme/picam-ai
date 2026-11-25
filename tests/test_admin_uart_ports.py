from pathlib import Path

import pytest

from dispread.admin import calibrate, uart_ports
from dispread.admin.instance import Instance
from dispread.gsv_transport import OutputConfig
from dispread.live.output import normalize_output
from dispread.live.service import LiveService
from dispread.workbench.config import load_config


@pytest.fixture
def uart(tmp_path):
    config = tmp_path / 'config.toml'
    config.write_text('[workbench]\nhost = "localhost"\n\n[live]\ncalibration = "timing.json"\n')
    boot = tmp_path / 'boot' / 'config.txt'
    boot.parent.mkdir()
    boot.write_text('# keep\n[all]\ndtparam=uart0=on,spi=on,i2c_arm=on\n[pi4]\ndtparam=i2c_vc=on\n')
    dev, proc, sys = (tmp_path / component for component in ('dev', 'proc', 'sys'))
    for path in (dev, proc, sys / 'class/tty'):
        path.mkdir(parents=True)
    instance = Instance('user', 'picam-werkbank.service', 'user', config=str(config))
    backend = uart_ports.UartPorts(instance, config_txt=boot, sysfs_root=sys, dev_root=dev,
                                   proc_root=proc, blocker=lambda: None)
    return backend


def add_uart(uart, label, tty, *, alias=False, address=None):
    node = f'/axi/pcie/rp1/serial@{address or "30000"}'
    target = uart.device_tree / node.lstrip('/')
    target.mkdir(parents=True, exist_ok=True)
    directory = 'aliases' if alias else '__symbols__'
    entry = 'serial' + label[-1] if alias else label
    metadata = uart.device_tree / directory / entry
    metadata.parent.mkdir(exist_ok=True)
    metadata.write_bytes(node.encode() + b'\0')
    platform = uart.sysfs_root / 'devices' / tty
    device = platform / 'port' / 'subport'
    device.mkdir(parents=True)
    (platform / 'of_node').symlink_to(target)
    link = uart.sysfs_root / 'class/tty' / tty
    link.mkdir()
    (link / 'device').symlink_to(device)
    (uart.dev_root / tty).touch()


def add_usb(uart, name='ttyUSB3'):
    path = uart.dev_root / name
    path.touch()
    link = uart.dev_root / 'serial/by-id/usb-Test_adapter'
    link.parent.mkdir(parents=True)
    link.symlink_to(path)
    usb = uart.sysfs_root / 'devices/usb1/1-2'
    device = usb / 'port'
    device.mkdir(parents=True)
    (usb / 'manufacturer').write_text('Adapter AG\n')
    (usb / 'serial').write_text('SN007\n')
    tty = uart.sysfs_root / 'class/tty' / name
    tty.mkdir()
    (tty / 'device').symlink_to(device)
    return '/dev/serial/by-id/usb-Test_adapter'


def fake_runner(calls, *, fail=None):
    def run(argv):
        calls.append(argv)
        if argv[:3] == ['sudo', '-n', '--']:
            argv = argv[3:]
        command = argv[0]
        if command == fail:
            return 1, '', 'absichtlicher Fehler'
        if command == 'cp':
            Path(argv[-1]).write_bytes(Path(argv[-2]).read_bytes())
        elif command == 'install':
            Path(argv[-1]).write_bytes(Path(argv[-2]).read_bytes())
        elif command == 'mv':
            Path(argv[-2]).replace(argv[-1])
        elif command == 'rm':
            Path(argv[-1]).unlink(missing_ok=True)
        elif command not in {'systemctl', 'sudo'}:
            pytest.fail(f'unerwarteter Befehl: {argv!r}')
        return 0, '', ''
    return run


def test_pin_filter_runtime_mapping_and_conflicts(uart):
    add_uart(uart, 'uart0', 'ttyAMA0')
    add_uart(uart, 'uart4', 'ttyAMA7', alias=True, address='40000')
    assert uart.choices(8)[0].status == 'active'
    assert uart.choices(10)[0].status == 'reserved'
    assert uart.choices(1) == ()
    assert uart.choices(7)[0].status == 'reboot_required'
    assert 'SPI0' in uart.choices(24)[0].reason
    assert 'HAT-EEPROM' in uart.choices(27)[0].warnings[0]
    assert uart.choices(32)[0].device.path == '/dev/ttyAMA7'
    assert uart.choices(32)[0].status == 'reboot_required'
    (uart.proc_root / 'cmdline').write_text('console=ttyAMA0,115200 console=tty1')
    assert 'Konsole' in uart.choices(8)[0].reason


def test_debug_alias_is_never_mapped_to_uart0(uart):
    add_uart(uart, 'uart0', 'ttyAMA10', alias=True, address='7d001000')
    (uart.dev_root / 'serial0').symlink_to(uart.dev_root / 'ttyAMA10')
    device, = uart.inventory()
    assert device.reserved and device.uart is None
    assert uart.choices(8)[0].device is None
    for port in ('/dev/serial0', '/dev/ttyAMA10'):
        with pytest.raises(ValueError, match='Debugport'):
            uart.plan_change(output=port)


def test_serial0_pointing_to_data_port_does_not_reserve_it(uart):
    """raspi01 25.11.: /dev/serial0 -> ttyAMA0; der Dienst brach mit „Debugport ist reserviert“ ab."""
    from dispread.hardware_ports import debug_port, validate_port_pair

    add_uart(uart, 'uart0', 'ttyAMA0', alias=True)
    (uart.dev_root / 'serial0').symlink_to(uart.dev_root / 'ttyAMA0')
    (uart.dev_root / 'ttyAMA10').touch()
    data = str(uart.dev_root / 'ttyAMA0')
    assert not debug_port(data, dev_root=str(uart.dev_root))
    assert debug_port(str(uart.dev_root / 'ttyAMA10'), dev_root=str(uart.dev_root))
    assert debug_port(str(uart.dev_root / 'serial0'), dev_root=str(uart.dev_root))   # Verweis bleibt verboten
    validate_port_pair('/dev/ttyAMA0', '/dev/ttyUSB0')                                  # echter Pi: kein Fehler
    assert not any(device.reserved for device in uart.inventory() if device.path.endswith('ttyAMA0'))


def test_inventory_prefers_usb_by_id_and_reports_visible_holders(uart):
    stable = add_usb(uart, 'ttyACM3')
    choice, = uart.reference_choices()
    assert (choice.value, choice.device.manufacturer, choice.device.serial_number) == (stable, 'Adapter AG', 'SN007')
    assert choice.selectable
    process = uart.proc_root / '42'
    (process / 'fd').mkdir(parents=True)
    (process / 'comm').write_text('terminal\n')
    (process / 'fd/1').symlink_to(uart.dev_root / 'ttyACM3')
    choice, = uart.reference_choices()
    assert not choice.selectable
    assert choice.device.holders == (uart_ports.Process(42, 'terminal'),)
    with pytest.raises(ValueError, match='belegt'):
        uart.plan_change(reference=stable)


def test_boot_config_includes_sections_and_flow_control(uart):
    uart.config_txt.write_text(
        '[all]\ndtparam=spi, i2c_arm, i2c_vc\ninclude uarts.txt\n'
        '[pi4]\ndtoverlay=uart1-pi5\n[pi5]\ndtparam=spi=off\n'
        '[gpio20=1]\ndtoverlay=uart4-pi5\n')
    uart.config_txt.with_name('uarts.txt').write_text('dtoverlay=uart2-pi5,ctsrts\n')
    boot = uart_ports.read_boot_config(uart.config_txt)
    assert boot.enabled_uarts == {'uart2'}
    assert boot.i2c and boot.i2c0 and not boot.spi
    assert boot.flow_control == {'uart2'}
    assert uart.choices(27)[0].status == 'conflict'
    assert 'ctsrts' in uart.choices(7)[0].reason
    assert 'Bedingte' in uart.choices(32)[0].reason


def test_reference_change_restarts_only_workbench(uart):
    stable = add_usb(uart)
    calls = []
    plan = uart.plan_change(reference=stable)
    assert plan.service_restart and not plan.reboot_required
    assert plan.boot_diff == ''
    assert '+reference_port = ' in plan.config_diff
    result = uart_ports.apply_change(plan, confirmed=True, runner=fake_runner(calls))
    assert result.service_restarted and result.backup is None and not result.reboot_required
    assert calls == [['systemctl', '--user', 'restart', uart.instance.unit]]
    assert load_config(uart.instance.config)[0]['reference_port'] == stable


def test_boot_edit_keeps_old_lines_has_backup_and_never_reboots(uart):
    reference = add_usb(uart)
    before = uart.config_txt.read_bytes()
    plan = uart.plan_change(output='uart2', reference=reference)
    assert plan.reboot_required and not plan.service_restart
    assert '+dtoverlay=uart2-pi5' in plan.boot_diff
    assert 'ctsrts' not in plan.boot.after
    assert 'Gerätenamen nach Neustart prüfen' in plan.warnings
    calls = []
    with pytest.raises(ValueError, match='bestätigen'):
        uart_ports.apply_change(plan, runner=fake_runner(calls))
    assert not calls
    result = uart_ports.apply_change(plan, confirmed=True, runner=fake_runner(calls))
    assert result.backup.name.startswith('config.txt.bak-') and result.backup.name.endswith('Z')
    assert result.backup.read_bytes() == before
    assert uart.config_txt.read_bytes().startswith(before)
    assert load_config(uart.instance.config)[0]['output_port'] == 'uart2'
    assert result.reboot_required and not result.service_restarted
    assert all('reboot' not in argv and 'systemctl' not in argv for argv in calls)


def test_selecting_ready_uart_restarts_service_without_boot_change(uart):
    add_uart(uart, 'uart2', 'ttyAMA5', address='38000')
    with uart.config_txt.open('a') as stream:
        stream.write('[pi5]\ndtoverlay=uart2-pi5\n')
    plan = uart.plan_change(output='/dev/ttyAMA5')
    assert plan.service_restart and plan.output == 'uart2'
    assert plan.boot is None
    result = uart_ports.apply_change(plan, confirmed=True, runner=fake_runner([]))
    assert result.service_restarted


def test_conflicts_missing_usb_and_active_run_block_plans(uart):
    for args, message in (({'output': 'uart3'}, 'SPI0'),
                          ({'reference': '/dev/ttyUSB8'}, 'fehlt'),
                          ({'output': '/dev/ttyUSB0'}, 'verschiedene Ports')):
        with pytest.raises(ValueError, match=message):
            uart.plan_change(**args)
    uart._blocker = lambda: 'Lauf aktiv'
    with pytest.raises(ValueError, match='Lauf aktiv'):
        uart.plan_change(output='uart2')


def test_changes_in_boot_or_run_state_invalidate_a_confirmed_plan(uart):
    plan = uart.plan_change(output='uart2')
    calls = []
    run = fake_runner(calls)
    uart._blocker = lambda: 'Lauf aktiv'
    with pytest.raises(ValueError, match='Lauf aktiv'):
        uart_ports.apply_change(plan, confirmed=True, runner=run)
    uart._blocker = lambda: None
    with uart.config_txt.open('a') as stream:
        stream.write('# external edit\n')
    with pytest.raises(ValueError, match='zwischenzeitlich'):
        uart_ports.apply_change(plan, confirmed=True, runner=run)
    assert all('cp' not in argv for argv in calls)


def test_boot_rolls_back_if_instance_write_fails(uart, monkeypatch):
    plan = uart.plan_change(output='uart2')
    before = uart.config_txt.read_bytes()
    original = uart_ports._write

    def write(edit, runner, *, privileged):
        if edit == plan.config:
            raise PermissionError('EACCES')
        original(edit, runner, privileged=privileged)

    monkeypatch.setattr(uart_ports, '_write', write)
    with pytest.raises(PermissionError, match='EACCES'):
        uart_ports.apply_change(plan, confirmed=True, runner=fake_runner([]))
    assert uart.config_txt.read_bytes() == before


def test_restart_failure_is_visible_with_the_new_configuration(uart):
    stable = add_usb(uart)
    plan = uart.plan_change(reference=stable)
    result = uart_ports.apply_change(plan, confirmed=True, runner=fake_runner([], fail='systemctl'))
    assert not result.service_restarted
    assert result.restart_error == 'absichtlicher Fehler'
    assert load_config(uart.instance.config)[0]['reference_port'] == stable


def test_custom_ports_reach_service_and_calibration(uart):
    stable = add_usb(uart)
    uart.instance.reference_port = stable
    options = calibrate.Options().for_instance(uart.instance)
    assert options.port == stable
    service = LiveService(None, uart.dev_root, reference_port=stable, reference_present=lambda: True)
    assert service.setup_reference_status() == {'serial_present': True, 'port': stable}
    output = normalize_output({'transport': 'uart'}, output_port='/dev/ttyAMA7', reference_port=stable)
    assert output['serial_port'] == '/dev/ttyAMA7'
    direct = normalize_output({'transport': 'serial'}, output_port='/dev/ttyAMA7', reference_port=stable)
    assert direct['port'] == '/dev/ttyAMA7'
    with pytest.raises(ValueError, match='verschiedene Ports'):
        OutputConfig(serial_port=stable, output_port=stable, reference_port=stable)
    with pytest.raises(ValueError, match='Debugport'):
        OutputConfig(serial_port='/dev/ttyAMA10', output_port='/dev/ttyAMA10', reference_port=stable)


def test_concurrent_uart_apply_is_rejected(uart):
    import fcntl
    import os

    plan = uart.plan_change(output='uart2')
    fd = os.open(uart.config_txt.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='andere UART-Änderung'):
            uart_ports.apply_change(plan, confirmed=True, runner=fake_runner([]))
    finally:
        os.close(fd)


def test_enabled_but_unmapped_controller_needs_reboot_without_boot_edit(uart):
    with uart.config_txt.open('a') as stream:
        stream.write('[pi5]\ndtoverlay=uart4-pi5\n')
    plan = uart.plan_change(output='uart4')
    assert plan.boot is None and plan.reboot_required
    calls = []
    result = uart_ports.apply_change(plan, confirmed=True, runner=fake_runner(calls))
    assert result.reboot_required and not calls


def test_sudo_failure_leaves_every_file_in_place(uart, monkeypatch):
    monkeypatch.setattr(uart_ports.os, 'geteuid', lambda: 1000)
    plan = uart.plan_change(output='uart2')
    assert uart_ports.sudo_needed(plan)
    calls = []
    with pytest.raises(OSError, match='absichtlicher Fehler'):
        uart_ports.apply_change(plan, confirmed=True, runner=fake_runner(calls, fail='sudo'))
    assert calls == [['sudo', '-n', 'true']]
    assert uart.config_txt.read_text() == plan.boot.before
    assert Path(uart.instance.config).read_text() == plan.config.before


def test_serve_resolves_instance_uart_and_passes_config_to_live_and_bridge(uart, monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from dispread.bridge import hub
    from dispread.workbench import server

    runtime = uart.config_txt.parent / 'runtime'
    runtime.mkdir(mode=0o700)
    monkeypatch.setattr(server, 'service_pam_user', lambda value: 'operator')
    monkeypatch.setattr(server, 'bridge_service_config', lambda args: ({
        'bridge_identity': SimpleNamespace(pi_id='pi'), 'bridge_pairing_store': object(),
    }, None))
    monkeypatch.setattr(server, 'CameraOwner', lambda *args, **kwargs: object())
    monkeypatch.setattr(server, 'uart_devices', lambda: {'uart2': '/dev/ttyAMA7'})
    settings = {}

    def start_bridge(*args, output_port, reference_port, **kwargs):
        settings['bridge'] = (output_port, reference_port)
        return object()

    class ReachedLiveService(Exception):
        pass

    def start_live(*args, output_port, reference_port, **kwargs):
        settings['live'] = (output_port, reference_port)
        raise ReachedLiveService

    monkeypatch.setattr(hub, 'BridgeHub', start_bridge)
    monkeypatch.setattr(server, 'LiveService', start_live)
    reference = add_usb(uart)
    args = SimpleNamespace(simulate=True, socket=str(runtime / 'control.sock'),
                           output_port='uart2', reference_port=reference)
    with pytest.raises(ReachedLiveService):
        asyncio.run(server.serve(args))
    assert settings == {'bridge': ('/dev/ttyAMA7', reference), 'live': ('/dev/ttyAMA7', reference)}


def test_unresolved_output_blocks_uart_before_creating_a_run(uart):
    from dispread.live.service import LiveError

    service = LiveService(None, uart.dev_root, output_port='uart2', diagnostic_staging_root=uart.dev_root)
    with pytest.raises(LiveError, match='Gerätenamen nach Neustart prüfen'):
        service.start_run(output={'transport': 'uart'}, reference=False)


def test_portable_instance_reports_manual_restart(uart):
    uart.instance.kind = 'portable'
    uart.instance.unit = None
    plan = uart.plan_change(reference=add_usb(uart))
    assert plan.service_restart and plan.restart_manually
    calls = []
    result = uart_ports.apply_change(plan, confirmed=True, runner=fake_runner(calls))
    assert 'manuell neu starten' in result.message
    assert not calls


def test_manual_calibration_restore_uses_the_saved_reference_device(uart):
    import json

    from dispread.admin.cli import Style

    saved = uart.config_txt.parent / 'point.json'
    reference = add_usb(uart)
    saved.write_text(json.dumps({
        'port': reference, 'register': {'norm': {'daten': [1, 2, 3]}, 'dpoint': {'daten': [1]}},
    }))
    checked = []
    deps = calibrate.Deps(port_exists=lambda port: checked.append(port) or False)
    result = calibrate.restore_from_file(saved, calibrate.Options(yes=True), calibrate.Console(Style(None, color=False)), deps)
    assert result == calibrate.EXIT_BLOCKED
    assert checked == [reference]
