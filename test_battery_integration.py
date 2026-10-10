import asyncio
import queue
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from battery_worker import BatteryWorker, BluetoothOff, check_bluetooth
from paired_device import PairedDevice, format_address, selected_device
from FlooStateMachine import FlooStateMachine
from FlooMsgFn import FlooMsgFn


class DeviceTests(unittest.TestCase):
    def test_protocol_index_is_hex(self):
        message = FlooMsgFn.create_valid_msg(b"FN=0A,00025B00FF0B,Headset")
        self.assertEqual(message.index, 10)
        self.assertEqual(message.btAddress, "00025B00FF0B")
        self.assertEqual(FlooMsgFn.create_valid_msg(b"FN=0B").index, 11)

    def test_address_and_selection(self):
        self.assertEqual(format_address("00025b00ff0b"), "00:02:5B:00:FF:0B")
        for value in (None, "", "not an address", "00025B00FF0", "00025B00FF0G"):
            self.assertIsNone(format_address(value))
        one = PairedDevice(3, "Same name", "00025B00FF0B")
        two = PairedDevice(7, "Same name", "112233445566")
        self.assertEqual(selected_device([one], -1), one)
        self.assertIsNone(selected_device([one, two], -1))
        self.assertEqual(selected_device([one, two], 1), two)

    def test_initial_and_later_enumeration_keep_identity_and_snapshot(self):
        for state in (FlooStateMachine.INIT, FlooStateMachine.CONNECTED):
            with self.subTest(state=state), patch("FlooStateMachine.wx.CallAfter") as dispatch:
                delegate = Mock()
                sm = FlooStateMachine(delegate)
                sm.inf = Mock()
                sm.state = state
                sm.lastCmd = FlooMsgFn(True)
                sm.handleMessage(FlooMsgFn(False, 3, "00025B00FF0B", "Headset"))
                sm.handleMessage(FlooMsgFn(False, 4))
                call = next(c for c in dispatch.call_args_list
                            if c.args[0] == delegate.pairedDevicesUpdateInd)
                snapshot = call.args[1]
                self.assertEqual(snapshot, (PairedDevice(3, "Headset", "00025B00FF0B"),))
                sm.pairedDevices.clear()
                self.assertEqual(len(snapshot), 1)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.callbacks = queue.Queue()
        self.workers = []

    def make_worker(self, reader, **kwargs):
        worker = BatteryWorker(lambda *args: self.events.append(args),
                               lambda *args: self.callbacks.put(args), reader, **kwargs)
        self.workers.append(worker)
        return worker

    def deliver(self):
        callback, *args = self.callbacks.get(timeout=3)
        callback(*args)

    def tearDown(self):
        for worker in self.workers:
            worker.stop()
            self.assertTrue(worker.join(3), "BLE worker did not stop")

    def test_boundaries_errors_and_recovery(self):
        outcomes = iter([0, 100, RuntimeError("gone"), BluetoothOff("off"), 44])

        async def reader(address):
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        worker = self.make_worker(reader)
        worker.set_target("A")
        for expected in ("0%", "100%", "Unavailable", "Bluetooth off", "44%"):
            self.assertEqual(self.events[-1][0], "Reading")
            self.deliver()
            self.assertEqual(self.events[-1][0], expected)
            if expected != "44%":
                self.assertTrue(worker.refresh())

    def test_overlap_cancellation_and_shutdown_wait_for_cleanup(self):
        entered = threading.Event()
        cleaning = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        calls = []

        async def reader(address):
            calls.append(address)
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                while not release.is_set():
                    await asyncio.sleep(.005)
                finished.set()

        worker = self.make_worker(reader)
        worker.set_target("A")
        self.assertTrue(entered.wait(2))
        for _ in range(20):
            self.assertFalse(worker.refresh())
        worker.set_target("B")
        self.assertTrue(cleaning.wait(2))
        worker.set_target("C")
        worker.stop()
        self.assertFalse(worker.join(.05))
        self.assertEqual(calls, ["A"])
        release.set()
        self.assertTrue(worker.join(2))
        self.assertTrue(finished.is_set())
        self.assertTrue(self.callbacks.empty())

    def test_late_results_discarded_for_target_and_destroyed_window(self):
        async def reader(address):
            return 10 if address == "A" else 90

        worker = self.make_worker(reader)
        worker.set_target("A")
        old_callback = self.callbacks.get(timeout=2)
        worker.set_target("B")
        callback, *args = old_callback
        callback(*args)
        self.assertEqual(self.events[-1][0], "Reading")
        self.deliver()
        self.assertEqual(self.events[-1][0], "90%")
        worker.refresh()
        late = self.callbacks.get(timeout=2)
        worker.stop()
        count = len(self.events)
        callback, *args = late
        callback(*args)
        self.assertEqual(len(self.events), count)

    def test_target_change_starts_latest_only_after_cleanup(self):
        entered = threading.Event()
        cleaned = threading.Event()

        async def reader(address):
            if address == "A":
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    await asyncio.sleep(.03)
                    cleaned.set()
            self.assertTrue(cleaned.is_set())
            return 71

        worker = self.make_worker(reader)
        worker.set_target("A")
        self.assertTrue(entered.wait(2))
        worker.set_target("B")
        self.deliver()
        self.assertEqual(self.events[-1][0], "71%")

    def test_timeout_cleans_up_and_allows_retry(self):
        cleaned = threading.Event()

        async def reader(address):
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        worker = self.make_worker(reader, deadline=.03)
        worker.set_target("A")
        self.deliver()
        self.assertTrue(cleaned.is_set())
        self.assertEqual(self.events[-1][0], "Unavailable")
        self.assertTrue(worker.refresh())


class RadioTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows radio API")
    async def test_radio_inspection_never_writes_state(self):
        from unittest.mock import AsyncMock
        import winrt.windows.devices.radios as radios_module

        fake_radio = Mock()
        fake_radio.get_radios_async = AsyncMock()
        with patch("battery_worker.sys.platform", "win32"), patch.object(radios_module, "Radio", fake_radio):
            fake_radio.get_radios_async.return_value = []
            with self.assertRaisesRegex(RuntimeError, "No PC Bluetooth adapter"):
                await check_bluetooth()
            radio = SimpleNamespace(kind=radios_module.RadioKind.BLUETOOTH,
                                    state=radios_module.RadioState.OFF)
            fake_radio.get_radios_async.return_value = [radio]
            with self.assertRaises(BluetoothOff):
                await check_bluetooth()
            radio.state = radios_module.RadioState.ON
            await check_bluetooth()
            radio.state = radios_module.RadioState.UNKNOWN
            with self.assertRaisesRegex(RuntimeError, "state is unavailable"):
                await check_bluetooth()
            self.assertEqual([c[0] for c in fake_radio.mock_calls],
                             ["get_radios_async"] * 4)

    async def test_non_windows_does_not_import_radio_module(self):
        with patch("battery_worker.sys.platform", "linux"), patch.dict(
                "sys.modules", {"winrt.windows.devices.radios": None}):
            await check_bluetooth()


if __name__ == "__main__":
    unittest.main()
