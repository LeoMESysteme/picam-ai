"""Windows application types, kept separate from Pi measurement contracts."""
import re
from dataclasses import dataclass


def valid_port_name(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"COM[1-9][0-9]{0,3}", value) is not None


@dataclass(frozen=True)
class DeviceInfo:
    instance_id: str
    port: str | None
    vid: int | None
    pid: int | None
    serial: str | None
    location: str | None
    pnp_error: int | None

    @property
    def identity(self) -> tuple:
        """Serial identity survives COM renumbering; no-serial devices use PnP ID."""
        if self.serial and self.vid is not None and self.pid is not None:
            return ("usb", self.vid, self.pid, self.serial.casefold())
        return ("instance", self.instance_id.casefold())

    @property
    def is_supported(self) -> bool:
        return (self.vid, self.pid) == (0x0403, 0x6001)


@dataclass(frozen=True)
class PortPair:
    pair_id: str
    bridge_port: str
    gsv_port: str
    owned: bool

    def __post_init__(self) -> None:
        if not self.pair_id or not isinstance(self.pair_id, str):
            raise ValueError("pair_id is required")
        if not valid_port_name(self.bridge_port) or not valid_port_name(self.gsv_port):
            raise ValueError("invalid COM port name")
        if self.bridge_port == self.gsv_port:
            raise ValueError("pair endpoints must differ")
        if not isinstance(self.owned, bool):
            raise ValueError("owned must be explicit")


@dataclass(frozen=True)
class InstallResult:
    state: str
    reboot_required: bool
    pair: PortPair | None
    error_code: str | None
