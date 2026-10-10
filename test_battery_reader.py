"""Verify percentage validation and connection cleanup without real hardware.

Run from the application repository:
    .venv/Scripts/python -m unittest discover -p 'test_battery*.py' -v
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from bleak.exc import BleakError

from battery_reader import decode_battery_level, read_battery_level


class BatteryReadingTests(unittest.IsolatedAsyncioTestCase):
    def test_valid_percentage_boundaries(self):
        for percentage in (0, 55, 100):
            with self.subTest(percentage=percentage):
                self.assertEqual(decode_battery_level(bytes([percentage])), percentage)

    def test_invalid_reading_is_not_reported_as_zero(self):
        for raw_value in (b"", b"\x01\x02", b"\x65", b"\xff"):
            with self.subTest(raw_value=raw_value):
                with self.assertRaises(ValueError):
                    decode_battery_level(raw_value)

    async def test_absent_headset_does_not_open_connection(self):
        with patch("battery_reader.BleakScanner.find_device_by_address", new=AsyncMock(return_value=None)):
            with patch("battery_reader.BleakClient") as client_factory:
                with patch("battery_reader.asyncio.sleep", new=AsyncMock()):
                    with self.assertRaisesRegex(BleakError, "Headset not found"):
                        await read_battery_level("00:02:5B:00:FF:0B")
                client_factory.assert_not_called()

    async def exercise_connection(self, outcome):
        device = MagicMock()
        connection = MagicMock()
        connection.read_gatt_char = AsyncMock()
        if isinstance(outcome, BaseException):
            connection.read_gatt_char.side_effect = outcome
        else:
            connection.read_gatt_char.return_value = outcome

        connection_context = AsyncMock()
        connection_context.__aenter__.return_value = connection
        connection_context.__aexit__.return_value = False

        with patch("battery_reader.BleakScanner.find_device_by_address", new=AsyncMock(return_value=device)):
            with patch("battery_reader.BleakClient", return_value=connection_context):
                try:
                    result = await read_battery_level("00:02:5B:00:FF:0B")
                    self.assertEqual(result, 55)
                    self.assertFalse(connection.read_gatt_char.call_args.kwargs["use_cached"])
                finally:
                    connection_context.__aexit__.assert_awaited_once()

    async def test_success_uses_fresh_read_and_disconnects(self):
        await self.exercise_connection(b"\x37")

    async def test_read_failure_disconnects(self):
        with self.assertRaisesRegex(RuntimeError, "Read failed"):
            await self.exercise_connection(RuntimeError("Read failed"))

    async def test_cancellation_disconnects(self):
        with self.assertRaises(asyncio.CancelledError):
            await self.exercise_connection(asyncio.CancelledError())

    async def test_transient_gatt_failure_reconnects_with_fresh_discovery(self):
        connection = MagicMock()
        connection.read_gatt_char = AsyncMock(side_effect=[BleakError("GATT unreachable"), b"\x37"])
        connection_context = AsyncMock()
        connection_context.__aenter__.return_value = connection
        connection_context.__aexit__.return_value = False
        with patch("battery_reader.BleakScanner.find_device_by_address", new=AsyncMock(return_value=MagicMock())):
            with patch("battery_reader.BleakClient", return_value=connection_context) as factory:
                with patch("battery_reader.asyncio.sleep", new=AsyncMock()):
                    self.assertEqual(await read_battery_level("00:02:5B:00:FF:0B"), 55)
        self.assertEqual(connection_context.__aexit__.await_count, 2)
        self.assertTrue(factory.call_args_list[0].kwargs["winrt"]["use_cached_services"])
        self.assertFalse(factory.call_args_list[1].kwargs["winrt"]["use_cached_services"])
        self.assertEqual(factory.call_args.kwargs["services"], ["0000180f-0000-1000-8000-00805f9b34fb"])


if __name__ == "__main__":
    unittest.main()
