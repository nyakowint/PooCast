"""Preserve dongle device identity separately from its display name."""

from dataclasses import dataclass
import re


def format_address(address):
    if not isinstance(address, str) or re.fullmatch(r"[0-9a-fA-F]{12}", address) is None:
        return None
    return ":".join(address[i:i + 2] for i in range(0, 12, 2)).upper()


@dataclass(frozen=True)
class PairedDevice:
    index: int
    name: str
    btAddress: str

    @property
    def battery_address(self):
        # A candidate only: classic and BLE addresses need not match on other devices.
        return format_address(self.btAddress)


def selected_device(devices, selection):
    if 0 <= selection < len(devices):
        return devices[selection]
    return devices[0] if len(devices) == 1 else None
