"""Read-only serial baseline; run only while all FlooCast instances are closed."""
import asyncio
import datetime
import sys
import time

import serial
from battery_worker import check_bluetooth


async def radios():
    from winrt.windows.devices.radios import Radio, RadioKind
    for radio in await Radio.get_radios_async():
        if radio.kind == RadioKind.BLUETOOTH:
            print("PC radio:", radio.name, radio.state.name)


print(datetime.datetime.now(datetime.timezone.utc).isoformat())
asyncio.run(radios())
with serial.Serial("COM7", 921600, timeout=.2) as port:
    for command in ("VR", "AM", "ST", "LA", "LF", "FT", "AC", "FN"):
        port.write(f"BC:{command}\r\n".encode("ascii"))
        until = time.monotonic() + .5
        while time.monotonic() < until:
            line = port.readline()
            if line:
                print(line.decode("utf-8", errors="replace").strip())
