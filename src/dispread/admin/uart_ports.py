"""Pi-5-Stiftleiste, serielles Inventar und bestätigte Portänderungen."""

from __future__ import annotations

import difflib
import fcntl
import os
import re
import stat
import tempfile
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dispread.gsv2as_serial import REFERENCE_PORT
from dispread.hardware_ports import GSV_UART_PORT, same_port, tty_device, uart_devices, validate_port_pair
from dispread.workbench.config import parse_config

from . import calibrate, configedit, probes
from .instance import Instance, discover

BOOT_CONFIG = Path('/boot/firmware/config.txt')
MARKER = '# picam-uart'
CHECK_AFTER_REBOOT = 'Gerätenamen nach Neustart prüfen'
DEVICE_NAME = re.compile(r'tty(?:AMA|USB|ACM)[0-9]+')
Runner = Callable[[list[str]], tuple[int, str, str]]
ChoiceStatus = Literal['active', 'reboot_required', 'conflict', 'reserved']


@dataclass(frozen=True)
class UartFunction:
    uart: str
    tx_gpio: int
    rx_gpio: int
    tx_pin: int
    rx_pin: int
    overlay_line: str
    conflicts: tuple[str, ...] = ()


UARTS = (
    UartFunction('uart0', 14, 15, 8, 10, 'dtoverlay=uart0-pi5'),
    UartFunction('uart1', 0, 1, 27, 28, 'dtoverlay=uart1-pi5', ('HAT-EEPROM (ID_SD/ID_SC)', 'I2C0')),
    UartFunction('uart2', 4, 5, 7, 29, 'dtoverlay=uart2-pi5'),
    UartFunction('uart3', 8, 9, 24, 21, 'dtoverlay=uart3-pi5', ('SPI0 (CE0/MISO)',)),
    UartFunction('uart4', 12, 13, 32, 33, 'dtoverlay=uart4-pi5'),
)


@dataclass(frozen=True)
class Process:
    pid: int
    name: str | None


@dataclass(frozen=True)
class SerialDevice:
    path: str
    kind: Literal['uart', 'usb']
    by_id: tuple[str, ...]
    manufacturer: str | None
    serial_number: str | None
    holders: tuple[Process, ...]
    uart: str | None = None
    reserved: bool = False


@dataclass(frozen=True)
class UartChoice:
    function: UartFunction
    pin: int
    signal: Literal['TX', 'RX']
    device: SerialDevice | None
    status: ChoiceStatus
    reason: str = ''
    warnings: tuple[str, ...] = ()

    @property
    def selectable(self) -> bool:
        return self.status in ('active', 'reboot_required')


@dataclass(frozen=True)
class ReferenceChoice:
    value: str
    device: SerialDevice
    selectable: bool
    reason: str = ''


@dataclass
class BootConfig:
    enabled_uarts: set[str] = field(default_factory=set)
    spi: bool = False
    i2c: bool = False
    i2c0: bool = False
    flow_control: set[str] = field(default_factory=set)
    uncertain: set[str] = field(default_factory=set)


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding='utf-8', errors='replace').strip() or None
    except OSError:
        return None


def _boot_text(path: Path) -> str:
    # Preserve CRLF and existing comments in the diff and backup.
    return path.read_bytes().decode('utf-8')


def read_boot_config(path: Path = BOOT_CONFIG) -> BootConfig:
    """Read Pi 5 and global sections, following includes without editing them."""
    result = BootConfig()
    other_models = {'none', 'pi0', 'pi0w', 'pi02', 'pi1', 'pi2', 'pi3', 'pi3+', 'pi4',
                    'pi400', 'cm1', 'cm3', 'cm4', 'cm4s', 'cm5', 'pi500'}

    def parse(source: Path, section: str, conditional: bool, stack: tuple[Path, ...]):
        source = source.resolve()
        if source in stack:
            raise ValueError(f'Zyklisches include in {source}')
        for line in _boot_text(source).splitlines():
            line = line.partition('#')[0].strip()
            if line.startswith('[') and line.endswith(']'):
                condition = line[1:-1].strip().lower()
                if condition == 'all':
                    section, conditional = 'all', False
                elif condition == 'pi5' or condition in other_models:
                    section = condition
                else:
                    conditional = True
                continue
            if section in other_models:
                continue
            if match := re.fullmatch(r'include\s+(.+)', line):
                parse(source.parent / match[1], section, conditional, (*stack, source))
                continue
            name, sep, value = re.sub(r'\s+', '', line).partition('=')
            if not sep:
                continue
            option, *params = value.split(',')
            overlay_uart = re.fullmatch(r'(uart[0-4])-pi5', option) if name == 'dtoverlay' else None
            if overlay_uart:
                uart = overlay_uart[1]
                if conditional:
                    result.uncertain.add(uart)
                    continue
                result.enabled_uarts.add(uart)
                if any(param in {'ctsrts', 'ctsrts=on', 'ctsrts=1', 'ctsrts=true'} for param in params):
                    result.flow_control.add(uart)
            if name == 'dtoverlay' and re.fullmatch(r'spi0-(?:[012]cs|[012]cs-pi5)', option):
                if not conditional:
                    result.spi = True
                else:
                    result.uncertain.add('spi')
            if name != 'dtparam':
                continue
            for part in (option, *params):
                key, _, state = part.partition('=')
                key = {'i2c_arm': 'i2c', 'i2c_vc': 'i2c0'}.get(key, key)
                if key not in {'spi', 'i2c', 'i2c0', 'uart0'}:
                    continue
                if conditional:
                    result.uncertain.add(key)
                    continue
                enabled = state not in {'off', 'false', '0'}
                if key == 'uart0':
                    if enabled:
                        result.enabled_uarts.add(key)
                    else:
                        result.enabled_uarts.discard(key)
                else:
                    setattr(result, key, enabled)

    parse(Path(path), 'all', False, ())
    return result


@dataclass(frozen=True)
class FileChange:
    path: Path
    before: str
    after: str

    @property
    def diff(self) -> str:
        lines = difflib.unified_diff(self.before.splitlines(keepends=True), self.after.splitlines(keepends=True),
                                     fromfile=str(self.path), tofile=str(self.path))
        return ''.join(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n'
                       for line in lines)


@dataclass(frozen=True)
class ChangePlan:
    previous_output: str
    previous_reference: str
    output: str
    reference: str
    boot: FileChange | None
    config: FileChange | None
    service_restart: bool
    restart_manually: bool
    reboot_required: bool
    sudo_required: bool
    warnings: tuple[str, ...]
    _backend: UartPorts = field(repr=False, compare=False)
    _requested: tuple[str | None, str | None] = field(repr=False, compare=False)

    @property
    def boot_diff(self) -> str:
        return self.boot.diff if self.boot else ''

    @property
    def config_diff(self) -> str:
        return self.config.diff if self.config else ''


@dataclass(frozen=True)
class ChangeResult:
    backup: Path | None
    service_restarted: bool
    reboot_required: bool
    message: str
    restart_error: str | None = None


def _ports_held(proc: Path, nodes: dict[Path, str]) -> dict[str, tuple[Process, ...]]:
    owners: dict[str, list[Process]] = {}
    for process in sorted(proc.glob('[0-9]*')):
        if not process.name.isdigit():
            continue
        try:
            descriptors = list((process / 'fd').iterdir())
        except OSError:
            continue
        held = set()
        for fd in descriptors:
            try:
                target = Path(os.readlink(fd))
                name = nodes.get(target.resolve()) if target.is_absolute() else None
            except (OSError, RuntimeError):
                continue
            if name:
                held.add(name)
        for name in held:
            owners.setdefault(name, []).append(Process(int(process.name), _read(process / 'comm')))
    return {path: tuple(processes) for path, processes in owners.items()}


def _instance_text(path: Path, before: str, updates: dict) -> str:
    if not updates:
        return before
    current = tomllib.loads(before)
    lines = before.splitlines()
    if 'workbench' not in current:
        lines[0:0] = ['[workbench]', '']
    for key, value in updates.items():
        configedit._replace_key(lines, key, value)
    after = '\n'.join(lines) + '\n'
    parsed = tomllib.loads(after)
    current.setdefault('workbench', {}).update(updates)
    if current != parsed:
        raise ValueError('config.toml: UART-Felder müssen in [workbench] einzeln stehen')
    parse_config(parsed, path.parent)
    return after


class UartPorts:
    def __init__(self, instance: Instance, *, config_txt: Path = BOOT_CONFIG,
                 sysfs_root: Path = Path('/sys'), dev_root: Path = Path('/dev'),
                 proc_root: Path = Path('/proc'), device_tree: Path | None = None,
                 blocker: Callable[[], str | None] | None = None):
        self.instance = instance
        self.config_txt = Path(config_txt)
        self.sysfs_root, self.dev_root, self.proc_root = map(Path, (sysfs_root, dev_root, proc_root))
        self.device_tree = Path(device_tree) if device_tree is not None else self.proc_root / 'device-tree'
        self._blocker = blocker or self._live_blocker

    def _live_blocker(self) -> str | None:
        service = probes.fact_service(self.instance)
        if (self.instance.unit is None and service.level == probes.OFF
                and self.instance.socket and Path(self.instance.socket).exists()):
            return 'Laufstatus unbekannt (Steuerung nicht erreichbar)'
        live = probes.socket_request(self.instance.socket, 'live.status') if service.level in (probes.OK, probes.WARN) else None
        snapshot = probes.Snapshot(self.instance, {'dienst': service}, live, 0)
        return snapshot.stop_blocker

    def _logical(self, path: Path) -> str:
        return '/dev/' + path.relative_to(self.dev_root).as_posix()

    def _local(self, path: str) -> Path:
        return self.dev_root / Path(path).relative_to('/dev')

    def inventory(self) -> tuple[SerialDevice, ...]:
        mapped = uart_devices(sysfs_root=self.sysfs_root, device_tree=self.device_tree, dev_root=self.dev_root)
        labels = {Path(path).name: label for label, path in mapped.items()}
        devices = sorted(path for path in self.dev_root.iterdir()
                         if DEVICE_NAME.fullmatch(path.name) and path.exists())
        nodes = {path.resolve(): self._logical(path) for path in devices}
        holders = _ports_held(self.proc_root, nodes)
        by_id: dict[Path, list[str]] = {}
        for link in sorted((self.dev_root / 'serial/by-id').glob('*')):
            if link.is_symlink() and link.exists():
                by_id.setdefault(link.resolve(), []).append(self._logical(link))
        debug = self.dev_root / 'serial0'
        result = []
        for path in devices:
            resolved = path.resolve()
            kind = 'uart' if path.name.startswith('ttyAMA') else 'usb'
            manufacturer = serial = None
            if kind == 'usb':
                device = tty_device(self.sysfs_root / 'class/tty' / path.name)
                for node in (device, *device.parents):
                    if not node.is_relative_to(self.sysfs_root.resolve()):
                        break
                    manufacturer = manufacturer or _read(node / 'manufacturer')
                    serial = serial or _read(node / 'serial')
                    if manufacturer and serial:
                        break
            name = self._logical(path)
            result.append(SerialDevice(name, kind, tuple(by_id.get(resolved, ())), manufacturer, serial,
                                       holders.get(name, ()), labels.get(path.name),
                                       path.name == 'ttyAMA10' or resolved == debug.resolve()))
        return tuple(result)

    def _console_ports(self) -> set[str]:
        names = (_read(self.sysfs_root / 'class/tty/console/active') or '').split()
        for source in (self.proc_root / 'cmdline', self.config_txt.with_name('cmdline.txt')):
            names.extend(re.findall(r'(?:^|\s)console=([^,\s]+)', _read(source) or ''))
        ports = set()
        for name in names:
            if DEVICE_NAME.fullmatch(name):
                ports.add('/dev/' + name)
            elif name == 'serial0':
                path = self.dev_root / name
                if path.exists() and path.resolve().is_relative_to(self.dev_root.resolve()):
                    ports.add('/dev/' + path.resolve().relative_to(self.dev_root.resolve()).as_posix())
        return ports

    def _runtime_bus(self, *symbols: str) -> bool:
        for symbol in symbols:
            target = _read(self.device_tree / '__symbols__' / symbol)
            if target:
                node = self.device_tree / target.rstrip('\0').lstrip('/')
                if node.is_dir() and (_read(node / 'status') or 'okay').rstrip('\0') in {'ok', 'okay'}:
                    return True
        return False

    def _choice(self, function: UartFunction, pin: int, boot: BootConfig,
                devices: tuple[SerialDevice, ...], reference: str) -> UartChoice:
        uart = function.uart
        device = next((item for item in devices if item.uart == uart and not item.reserved), None)
        signal = 'TX' if pin == function.tx_pin else 'RX'
        warnings = ('HAT-EEPROM: nur ohne Belegung von ID_SD/ID_SC verwenden.',) if uart == 'uart1' else ()
        status: ChoiceStatus = 'active'
        reason = ''
        uncertain = {uart}
        if uart == 'uart1':
            uncertain.add('i2c0')
        if uart == 'uart3':
            uncertain.add('spi')
        if signal == 'RX':
            status, reason = 'reserved', 'RX ist Eingang. Für GSVmulti den TX-Pin wählen.'
        elif uncertain & boot.uncertain:
            status, reason = 'conflict', 'Bedingte Bootkonfiguration zuerst prüfen'
        elif uart == 'uart1' and (boot.i2c0 or self._runtime_bus('i2c0', 'i2c0if')):
            status, reason = 'conflict', 'I2C0 belegt GPIO0/1'
        elif uart == 'uart3' and (boot.spi or self._runtime_bus('spi0')):
            status, reason = 'conflict', 'SPI0 belegt GPIO8/9'
        elif uart == 'uart0' and 'uart4' in boot.flow_control:
            status, reason = 'conflict', 'UART4-Flusssteuerung belegt GPIO14/15'
        elif uart in boot.flow_control:
            status, reason = 'conflict', 'Hardware-Flusssteuerung (ctsrts) konfiguriert'
        elif device and device.path in self._console_ports():
            status, reason = 'conflict', 'Serielle Konsole belegt den Port'
        elif device and self._bound_to(device, reference):
            status, reason = 'conflict', 'Port ist für Referenz belegt'
        elif device and device.holders:
            status, reason = 'conflict', 'Port ist durch einen Prozess belegt'
        elif not device or uart not in boot.enabled_uarts:
            status = 'reboot_required'
            reason = CHECK_AFTER_REBOOT if uart in boot.enabled_uarts else 'config.txt ergänzen und Pi neu starten'
        return UartChoice(function, pin, signal, device, status, reason, warnings)

    def choices(self, pin: int) -> tuple[UartChoice, ...]:
        functions = [function for function in UARTS if pin in (function.tx_pin, function.rx_pin)]
        if not functions:
            return ()
        boot = read_boot_config(self.config_txt)
        devices = self.inventory()
        return tuple(self._choice(function, pin, boot, devices, self.instance.reference_port)
                     for function in functions)

    def _bound_to(self, device: SerialDevice, port: str) -> bool:
        if not port.startswith('/dev/'):
            return device.uart == port
        return same_port(str(self._local(device.path)), str(self._local(port)))

    def reference_choices(self) -> tuple[ReferenceChoice, ...]:
        result = []
        consoles = self._console_ports()
        for device in self.inventory():
            if device.kind != 'usb':
                continue
            reason = ''
            if device.reserved or self._bound_to(device, self.instance.output_port):
                reason = 'Port ist reserviert'
            elif device.path in consoles or device.holders:
                reason = 'Port ist belegt'
            value = next(iter(device.by_id), device.path)
            result.append(ReferenceChoice(value, device, not reason, reason))
        return tuple(result)

    def plan_change(self, *, output: str | None = None, reference: str | None = None) -> ChangePlan:
        if not self.instance.config or self.instance.problem:
            raise ValueError(self.instance.problem or 'Instanz hat keine config.toml')
        if any(value is not None and (not isinstance(value, str) or not value) for value in (output, reference)):
            raise ValueError('UART-Auswahl muss einen Port oder eine UART-Funktion angeben')
        if reason := self._blocker():
            raise ValueError(reason)
        config_path = Path(self.instance.config).resolve()
        before = _boot_text(config_path)
        current, _, _ = parse_config(tomllib.loads(before), config_path.parent)
        old_output = current.get('output_port', GSV_UART_PORT)
        old_reference = current.get('reference_port', REFERENCE_PORT)
        selected_output = old_output if output is None else output
        selected_reference = old_reference if reference is None else reference
        validate_port_pair(selected_output, selected_reference)
        boot_edit = None
        reboot = False
        warnings = ()
        if output is not None:
            devices = self.inventory()
            boot = read_boot_config(self.config_txt)
            function = next((item for item in UARTS if item.uart == selected_output), None)
            if function is None and selected_output.startswith('/dev/'):
                mapped = next((item.uart for item in devices if item.path == selected_output), None)
                function = next((item for item in UARTS if item.uart == mapped), None)
                if function is None and selected_output == GSV_UART_PORT:
                    function = UARTS[0]
            if function is None:
                raise ValueError('Ausgang braucht eine zugeordnete Pi-5-UART-Funktion')
            choice = self._choice(function, function.tx_pin, boot, devices, selected_reference)
            if not choice.selectable:
                raise ValueError(choice.reason)
            selected_output = function.uart
            if choice.device:
                validate_port_pair(choice.device.path, selected_reference)
                if self._bound_to(choice.device, selected_reference):
                    raise ValueError('Ausgang und Referenz müssen verschiedene Ports verwenden')
            warnings = choice.warnings
            reboot = choice.status == 'reboot_required'
            if choice.device is None:
                warnings += (CHECK_AFTER_REBOOT,)
            if function.uart not in boot.enabled_uarts:
                boot_path = self.config_txt.resolve()
                original = _boot_text(boot_path)
                newline = '\r\n' if '\r\n' in original else '\n'
                addition = newline.join(('', MARKER, '[all]', '[pi5]', function.overlay_line, ''))
                if original and not original.endswith('\n'):
                    addition = newline + addition
                boot_edit = FileChange(boot_path, original, original + addition)
        if reference is not None and reference != old_reference:
            ref = next((item for item in self.reference_choices()
                        if reference in (item.device.path, *item.device.by_id)), None)
            if ref is None or not ref.selectable:
                raise ValueError(ref.reason if ref else 'USB-RS232-Referenzadapter fehlt')
        updates = {key: new for key, old, new in (('output_port', old_output, selected_output),
                                                   ('reference_port', old_reference, selected_reference)) if new != old}
        after = _instance_text(config_path, before, updates)
        config_edit = FileChange(config_path, before, after) if updates else None
        restart = bool(config_edit and not reboot)
        manual = restart and self.instance.unit is None
        sudo = os.geteuid() != 0 and (boot_edit is not None
               or (config_edit is not None and not _writable(config_path))
               or (restart and not manual and self.instance.scope == 'system'))
        return ChangePlan(old_output, old_reference, selected_output, selected_reference,
                          boot_edit, config_edit, restart, manual, reboot, sudo, warnings, self, (output, reference))


def _writable(path: Path) -> bool:
    return os.access(path, os.W_OK) and os.access(path.parent, os.W_OK)


def _command(runner: Runner, argv: list[str]) -> None:
    code, output, error = runner(argv)
    if code:
        raise OSError((error or output).strip() or f'{argv[0]} fehlgeschlagen (Exit {code})')


def _privileged(argv: list[str]) -> list[str]:
    return ['sudo', '-n', '--', *argv] if os.geteuid() != 0 else argv


def _write(edit: FileChange, runner: Runner, *, privileged: bool) -> None:
    if _boot_text(edit.path) != edit.before:
        raise ValueError(f'{edit.path} wurde zwischenzeitlich geändert; Plan neu erstellen')
    if not privileged and _writable(edit.path):
        configedit.apply(edit.path, edit.after)
        return
    info = edit.path.stat()
    with tempfile.TemporaryDirectory(prefix='picam-uart-') as directory:
        source = Path(directory) / 'configuration'
        source.write_bytes(edit.after.encode('utf-8'))
        staged = str(edit.path.with_name(f'.{edit.path.name}.picam-uart-{uuid4().hex}'))
        try:
            _command(runner, _privileged(['install', '-m', f'{stat.S_IMODE(info.st_mode):o}',
                                         '-o', str(info.st_uid), '-g', str(info.st_gid), '--', str(source), staged]))
            if _boot_text(edit.path) != edit.before:
                raise ValueError(f'{edit.path} wurde zwischenzeitlich geändert; Plan neu erstellen')
            _command(runner, _privileged(['mv', '-T', '--', staged, str(edit.path)]))
        except (OSError, ValueError):
            runner(_privileged(['rm', '-f', '--', staged]))
            raise


def plan_change(*, output: str | None = None, reference: str | None = None,
                instance: Instance | None = None, **paths) -> ChangePlan:
    return UartPorts(instance or discover(), **paths).plan_change(output=output, reference=reference)


def choices(pin: int, *, instance: Instance | None = None, **paths) -> tuple[UartChoice, ...]:
    return UartPorts(instance or discover(), **paths).choices(pin)


def reference_choices(*, instance: Instance | None = None, **paths) -> tuple[ReferenceChoice, ...]:
    return UartPorts(instance or discover(), **paths).reference_choices()


def sudo_needed(plan: ChangePlan) -> bool:
    return plan.sudo_required


sudo_cached = calibrate.sudo_cached
sudo_validate = calibrate.sudo_validate


def apply_change(plan: ChangePlan, *, confirmed: bool = False, runner: Runner | None = None) -> ChangeResult:
    if confirmed is not True:
        raise ValueError('UART-Änderung zuerst bestätigen')
    run = runner or (lambda argv: probes.run_command(argv, timeout=120))
    # Lock the directory inode, which survives the atomic file replacements.
    # All picam UART operations that share a boot partition use this lock.
    directory = plan._backend.config_txt.resolve().parent
    if not directory.is_dir():
        directory = Path(plan._backend.instance.config).resolve().parent
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Eine andere UART-Änderung läuft bereits') from error
        return _apply(plan, run)
    finally:
        os.close(fd)


def _apply(plan: ChangePlan, run: Runner) -> ChangeResult:
    if plan.sudo_required:
        _command(run, ['sudo', '-n', 'true'])
    backend = plan._backend
    output, reference = plan._requested
    fresh = backend.plan_change(output=output, reference=reference)
    if fresh != plan:
        raise ValueError('UART-Auswahl oder Konfiguration wurde zwischenzeitlich geändert; Plan neu erstellen')
    backup = None
    if plan.boot:
        stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
        backup = plan.boot.path.with_name(f'{plan.boot.path.name}.bak-{stamp}')
        _command(run, _privileged(['cp', '-p', '--', str(plan.boot.path), str(backup)]))
        _write(plan.boot, run, privileged=True)
    try:
        if plan.config:
            _write(plan.config, run, privileged=False)
    except (OSError, ValueError) as error:
        if plan.boot:
            try:
                _write(FileChange(plan.boot.path, plan.boot.after, plan.boot.before), run, privileged=True)
            except (OSError, ValueError) as rollback_error:
                raise OSError(f'{error}. Rückweg fehlgeschlagen ({rollback_error}). Sicherung: {backup}') from error
        raise
    if plan.reboot_required:
        return ChangeResult(backup, False, True, 'Pi-Neustart nötig. ' + CHECK_AFTER_REBOOT + '.')
    if plan.restart_manually:
        return ChangeResult(backup, False, False, 'Konfiguration gespeichert. Portable Werkbank manuell neu starten.')
    if plan.service_restart:
        instance = backend.instance
        argv = probes.systemctl(instance) + ['restart', instance.unit]
        try:
            if reason := backend._blocker():
                raise ValueError(reason)
            _command(run, _privileged(argv) if instance.scope == 'system' else argv)
        except (OSError, ValueError) as error:
            return ChangeResult(backup, False, False,
                                'Konfiguration gespeichert. Dienstneustart steht aus.', str(error))
        return ChangeResult(backup, True, False, 'Werkbank-Dienst neu gestartet.')
    return ChangeResult(backup, False, False, 'Konfiguration gespeichert.' if plan.config else 'Keine Änderung.')
