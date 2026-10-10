"""Exercise real wx controls and CallAfter without touching Bluetooth/serial."""
import time
import unittest
from unittest.mock import patch

import wx
from battery_panel import BatteryPanel
from battery_worker import BatteryWorker, BluetoothOff
from paired_device import PairedDevice


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App.Get() or wx.App(False)

    def test_native_labels_refresh_and_destruction(self):
        outcomes = iter([0, 100, RuntimeError("lost connection"), BluetoothOff("off")])

        async def reader(address):
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        def make_worker(callback, dispatch):
            return BatteryWorker(callback, dispatch, reader)

        frame = wx.Frame(None)
        with patch("battery_panel.BatteryWorker", make_worker):
            panel = BatteryPanel(frame)
        try:
            panel.set_devices([PairedDevice(0, "Headset", "00025B00FF0B")], -1)
            for expected in ("0%", "100%", "Unavailable", "Bluetooth off"):
                self.assertEqual(panel.label.GetLabel(), "Headset battery: Reading")
                self.assertFalse(panel.refresh_button.IsEnabled())
                deadline = time.monotonic() + 3
                while panel.worker.busy and time.monotonic() < deadline:
                    wx.Yield()
                    time.sleep(.005)
                self.assertEqual(panel.label.GetLabel(), "Headset battery: " + expected)
                self.assertTrue(panel.refresh_button.IsEnabled())
                if expected != "Bluetooth off":
                    panel.worker.refresh()
            panel.set_devices([], -1)
            self.assertFalse(panel.refresh_button.IsEnabled())
            self.assertEqual(panel.label.GetLabel(), "Headset battery: Unavailable")
        finally:
            frame.Destroy()
            wx.Yield()
            self.assertTrue(panel.worker.closed)
            self.assertTrue(panel.worker.join(3))
