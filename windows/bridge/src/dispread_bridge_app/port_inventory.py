"""Cheap pySerial inventory; cached reads never perform OS I/O in context()."""
import threading

from .types import valid_port_name
from .ui.port import PortChoice


def serial_ports():
    from serial.tools.list_ports import comports
    return comports()


def usb_vid_pid(item):
    """USB product identity only; never serial, PnP instance ID or description."""
    vid, pid = getattr(item, 'vid', None), getattr(item, 'pid', None)
    if all(type(v) is int and 0 <= v <= 0xffff for v in (vid, pid)):
        return f'{vid:04x}:{pid:04x}'
    return None


def choice(item):
    if isinstance(item, PortChoice):
        return item
    if isinstance(item, str):
        return PortChoice(item, item)
    port = item.device
    description = getattr(item, 'description', '') or port
    hwid = getattr(item, 'hwid', '') or ''
    kind = ('com0com' if 'com0com' in (description + hwid).lower() else
            'usb_serial' if getattr(item, 'vid', None) is not None else 'other')
    return PortChoice(port, f'{port} · {description}', kind, device_id=port if kind == 'usb_serial' else None)


class PortInventory:
    def __init__(self, query, clock):
        self.query, self.clock = query, clock
        self._lock = threading.Lock()
        self._items = ()
        self._usb_ids = {}
        self._attempt = self._updated = float('-inf')
        self._known, self._scanning = False, False

    def refresh(self):
        with self._lock:
            if self._scanning or self.clock() - self._attempt < 2:
                return self._items
            self._attempt, self._scanning = self.clock(), True
        try:
            raw = tuple(self.query())
            usb_ids = {choice(p).port: usb_vid_pid(p) for p in raw}
            items = tuple(sorted((p for p in map(choice, raw) if valid_port_name(p.port)),
                                 key=lambda p: int(p.port[3:])))
            known = True
        except Exception:
            items, known, usb_ids = (), False, {}
        with self._lock:
            self._items, self._known = items, known
            self._usb_ids = usb_ids
            self._updated, self._scanning = self.clock(), False
            return items

    def cached(self):
        with self._lock:
            return self._items

    def usb_id(self, port):
        with self._lock:
            return self._usb_ids.get(port)

    def present(self, port, *, usb_only=True):
        with self._lock:
            if port is None or not self._known or self.clock() - self._updated > 4:
                return None
            return any(p.port == port and (not usb_only or p.kind == 'usb_serial') for p in self._items)
