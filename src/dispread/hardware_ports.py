"""Feste Port-/Ratenvorgaben ohne Hardwarezugriff beim Import."""

# Pi-5-Datenport; /dev/serial0 ist der reservierte Debug-Header.
GSV_UART_PORT = '/dev/ttyAMA0'
# Direkte UserDefined-Ausgabe. Die Pi/Windows-Bruecke hat ihren eigenen
# UART_BAUD-/LEGACY_UART_BAUD-Vertrag in bridge/baud.py.
DIRECT_UART_BAUD = 115200


def same_port(left: str, right: str) -> bool:
    """Compare symlinks and duplicate device nodes."""
    import stat
    from pathlib import Path

    first, second = Path(left).resolve(), Path(right).resolve()
    if first == second:
        return True
    try:
        a, b = first.stat(), second.stat()
    except FileNotFoundError:
        return False
    return stat.S_ISCHR(a.st_mode) and stat.S_ISCHR(b.st_mode) and a.st_rdev == b.st_rdev


def debug_port(port: str) -> bool:
    from pathlib import Path

    return (Path(port).name in {'serial0', 'ttyAMA10'}
            or any(same_port(port, reserved) for reserved in ('/dev/serial0', '/dev/ttyAMA10')))


def validate_port_pair(output: str, reference: str) -> None:
    if debug_port(output) or debug_port(reference):
        raise ValueError('Debugport ist reserviert (/dev/serial0, /dev/ttyAMA10)')
    if same_port(output, reference):
        raise ValueError('Ausgang und Referenz müssen verschiedene Ports verwenden')


def tty_device(tty):
    """Follow the tty's sysfs link (PL011 may be several levels above it)."""
    if (tty / 'device').exists():
        return (tty / 'device').resolve()
    return tty.resolve()


def uart_devices(*, sysfs_root=None, device_tree=None, dev_root=None) -> dict[str, str]:
    """Map RP1 UART labels to device nodes using live device-tree identity."""
    import re
    from pathlib import Path

    sysfs = Path(sysfs_root or '/sys')
    tree = Path(device_tree or '/proc/device-tree')
    dev = Path(dev_root or '/dev')

    def target(path):
        try:
            value = path.read_bytes().rstrip(b'\0').decode('ascii')
        except (OSError, UnicodeError):
            return None
        return value if value.startswith('/') else None

    def node_id(node):
        parts = node.parts
        if 'base' in parts:
            return '/' + '/'.join(parts[parts.index('base') + 1:])
        if node.is_relative_to(tree.resolve()):
            return '/' + node.relative_to(tree.resolve()).as_posix()
        return None

    aliases = tuple(filter(None, (target(path) for path in (tree / 'aliases').glob('serial*'))))
    targets = {}
    for number in range(5):
        label = f'uart{number}'
        node = target(tree / '__symbols__' / label)
        if node is None:
            # serial0 can point to the debug header. Only accept RP1 UART
            # aliases whose controller address matches the UART label.
            address = 0x30000 + number * 0x4000
            matches = {alias for alias in aliases if alias.endswith(f'/rp1/serial@{address:x}')}
            if len(matches) == 1:
                node = matches.pop()
        if node:
            targets[label] = node
    matches = {}
    for tty in (sysfs / 'class/tty').glob('ttyAMA*'):
        path = dev / tty.name
        if not re.fullmatch(r'ttyAMA\d+', tty.name) or not path.exists() or tty.name == 'ttyAMA10':
            continue
        device = tty_device(tty)
        for parent in (device, *device.parents):
            of_node = parent / 'of_node'
            if not of_node.exists():
                continue
            node = node_id(of_node.resolve())
            for label, expected in targets.items():
                if node == expected:
                    matches.setdefault(label, []).append(str(path))
            break
    return {label: paths[0] for label, paths in matches.items() if len(paths) == 1}
