"""Battery-reading code to reuse in FlooCast.

Uses the computer's Bluetooth adapter, not the FlooGoo USB control port.
The neckband can keep playing audio through the dongle during the read.
Bluetooth must already be enabled before calling read_battery_level().
"""

import asyncio
import logging

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError


# Standard Battery Level characteristic, inside Battery Service 0x180F.
# Discover by UUID: characteristic handles can differ between devices.
BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"
logger = logging.getLogger(__name__)


class BatteryServiceUnavailable(RuntimeError):
    """The connected device does not expose the standard battery characteristic."""


def decode_battery_level(raw_value: bytes | bytearray) -> int:
    """Convert the characteristic's single byte to a percentage from 0 to 100.

    Zero means an actual 0% reading. Invalid data raises an error; display it
    as unavailable, rather than as an empty battery.
    """
    if len(raw_value) != 1:
        raise ValueError("Battery Level must contain exactly one byte.")

    percentage = raw_value[0]
    if percentage > 100:
        raise ValueError(f"Battery Level is outside 0–100: {percentage}.")

    return percentage


async def read_battery_level(address: str, timeout: float = 20.0) -> int:
    """Read a fresh percentage, then disconnect the separate BLE connection.

    Args:
        address: Selected headset's Bluetooth address, e.g. "00:02:5B:00:FF:0B".
        timeout: Seconds allowed for scanning and, separately, connecting.
            A failed operation is retried once, after a two-second pause.

    Returns:
        The percentage reported by the headset, as an integer from 0 to 100.

    Raises:
        BatteryServiceUnavailable: Headset has no battery characteristic after rediscovery.
        ValueError: Timeout or returned battery value is invalid.
        BleakError / TimeoutError: Headset not found, or Bluetooth access/read failed.

    Does not pair a Windows audio device or change audio routing. Run on an
    asyncio event loop outside the GUI thread. For an overall deadline, wrap
    the call with asyncio.wait_for(). Cancellation also disconnects.
    """
    if timeout <= 0:
        raise ValueError("The Bluetooth timeout must be positive.")

    # Try the known GATT layout first. If Windows has stale service information
    # or the link temporarily fails, reconnect and rediscover the battery service.
    for attempt in range(2):
        try:
            return await asyncio.wait_for(
                _read_battery_once(address, timeout, use_cached_services=attempt == 0),
                timeout=timeout * 2 + 5,
            )
        except (BatteryServiceUnavailable, BleakError, TimeoutError, OSError) as error:
            if attempt == 1:
                raise
            logger.warning("Battery connection failed; retrying in two seconds: %s", error)
        await asyncio.sleep(2)


async def _read_battery_once(address: str, timeout: float, use_cached_services: bool) -> int:
    """One scan/connect/read attempt; each attempt owns and closes its connection."""
    # 1. Find the selected headset's BLE advertisement using the PC adapter.
    device = await BleakScanner.find_device_by_address(address, timeout=timeout)
    if device is None:
        raise BleakError("Headset not found. Keep it powered on and near the PC.")

    # 2. Open a separate BLE connection. This is not an audio connection.
    # The context manager disconnects on success, failure, or cancellation.
    async with BleakClient(
        device,
        timeout=timeout,
        services=[BATTERY_SERVICE_UUID],
        winrt={"use_cached_services": use_cached_services},
    ) as connection:
        # 3. Locate the standard Battery Level characteristic.
        battery_characteristic = connection.services.get_characteristic(
            BATTERY_LEVEL_UUID
        )
        if battery_characteristic is None:
            raise BatteryServiceUnavailable("This headset does not expose a BLE Battery Level.")

        # 4. Request the current value, rather than a Windows cached reading.
        raw_value = await connection.read_gatt_char(
            battery_characteristic,
            use_cached=False,
        )

        # 5. Interpret the byte as a percentage; no voltage conversion needed.
        return decode_battery_level(raw_value)
