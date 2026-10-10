"""Native wx controls for battery status; selection never changes audio."""

import wx
from battery_worker import BatteryWorker
from paired_device import selected_device


class BatteryPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.stopped = False
        self.device = None
        self.label = wx.StaticText(self, label="Headset battery: Unavailable")
        self.refresh_button = wx.Button(self, label="Refresh")
        self.refresh_button.Disable()
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.label, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        row.Add(self.refresh_button)
        self.help = wx.StaticText(
            self, label="Battery uses PC Bluetooth (enable in Settings). Dongle audio is independent.")
        self.help.Wrap(520)
        self.help.SetToolTip("Keeps the battery connection open while FlooCast is running, including in the tray. "
                             "Changing headset or quitting releases it.")
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(row, 0, wx.EXPAND)
        layout.Add(self.help, 0, wx.TOP, 2)
        self.SetSizer(layout)
        self.worker = BatteryWorker(self.show_status, wx.CallAfter)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda event: self.worker.refresh(), self.timer)
        self.refresh_button.Bind(wx.EVT_BUTTON, lambda event: self.worker.refresh())
        self.Bind(wx.EVT_WINDOW_DESTROY, self.on_destroy)
        self.timer.Start(60000)

    def set_devices(self, devices, selection):
        if self.stopped:
            return
        self.device = selected_device(devices, selection)
        address = self.device.battery_address if self.device else None
        self.worker.set_target(address)
        if not address:
            self.show_status("Unavailable", "Select a headset with a valid Bluetooth address.")

    def show_status(self, state, detail):
        if self.stopped or not self or self.IsBeingDeleted():
            return
        self.label.SetLabel(f"Headset battery: {state}")
        target = f"{self.device.name} ({self.device.battery_address})" if self.device else "No headset selected"
        self.label.SetToolTip(target + "\n" + detail +
                             "\nRequires BLE Battery Service; some headsets use a different BLE address.")
        self.refresh_button.Enable(bool(self.device and self.device.battery_address) and state != "Reading")
        self.Layout()

    def stop(self):
        if not self.stopped:
            self.stopped = True
            self.timer.Stop()
            self.worker.stop()

    def on_destroy(self, event):
        if event.GetEventObject() is self:
            self.stop()
        event.Skip()
