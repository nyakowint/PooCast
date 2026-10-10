# Local Windows build

Run `dist\FlooCast.exe`. Python does not need to be installed on the PC running
the executable. Quit the Microsoft Store version first: only one app can open
the dongle's control COM port at a time. Audio streaming is handled by the dongle.

Start Minimized defaults to on, matching your preference. Open the window from
the FlooCast tray icon, or launch `FlooCast.exe --show` to show it immediately.
An existing saved Start Minimized preference takes precedence over the default.

Gaming mode, Prefer LE Audio off, USB Audio Input on, LED on, and aptX Lossless
off are read from the dongle. This build does not force settings or change the
paired-device list at startup. Broadcast settings are also read from the dongle.

The public source excludes the vendor's firmware updater. The firmware upgrade
button is disabled; use the official FlooCast release for firmware updates.
This build is unsigned and is not a reproduction of the Microsoft Store package.

FMA120 and FMA121 identifiers with USB VID:PID `0A12:4007` are accepted. The
FMA121 on this PC reports an FMA120 USB serial identifier, and the protocol's
audio mode response reports whether analog input is present. This does not
establish that firmware images are interchangeable.

## Verified on this PC

The standalone executable connected to the FMA121 on COM7 and displayed firmware
1.1.7, Gaming mode, active audio streaming, and aptX Adaptive at 48 kHz. USB Audio
Input and LED were on; Prefer LE Audio and aptX Lossless were off. Start Minimized
was on and the firmware upgrade button remained disabled after connection. The
app closed normally with exit code 0. Validation read the current device settings
without toggling controls or modifying the paired-device list.

## Rebuild

From this directory, run:

```powershell
pwsh -File .\build-windows.ps1
```

The script uses an isolated `.venv` with Python 3.13. Install Python 3.13 or `uv`
if recreating the environment. With `uv`, the Python runtime and download cache
are kept in the workspace's `.build-tools` directory. Dependencies are listed in
`requirements-build.txt` and `requirements.txt`.

The output is `dist\FlooCast.exe`, with images, translations, Python, and native
dependencies bundled into the executable. Keep `LICENSE.txt` with redistributed
copies. The public source uses the BSD 3-Clause license.

## Native headset battery

The paired-device panel now contains **Headset battery** and **Refresh**. It uses
the selected device's retained Bluetooth address, or the sole listed device when
nothing is selected. Selecting a row for battery does not connect/disconnect audio.
Device names, addresses, and dongle indices are preserved together in initial
enumeration and subsequent refreshes; context-menu actions use the dongle index.

Battery reads use the **PC Bluetooth adapter**, independently of dongle audio.
Enable PC Bluetooth yourself in Windows Settings. FlooCast never enables/disables
radios, pairs a Windows audio device, changes audio routing, or writes dongle
settings for this feature. No separate reader process, PowerShell window, JSON
status file, or marker-file communication is used.

`battery_reader.py` reads standard BLE Battery Service `180F`, characteristic
`2A19`, with an uncached value read. `battery_worker.py` runs a dedicated asyncio
loop on a Windows MTA thread and `battery_panel.py` delivers updates through
`wx.CallAfter`. Battery imports are deferred so missing dependencies/adapters
produce **Unavailable** while dongle controls continue working. Windows radio
imports are conditional; Linux/macOS do not import WinRT radio management.

The panel polls every 60 seconds and supports manual Refresh. Only one read can
own the BLE connection, including cancellation cleanup. The display replaces any
previous percentage with **Reading**, then a fresh percentage (including 0% and
100%), **Unavailable**, or **Bluetooth off**. Hover over the status for the target
name/address and error details. Scan/connect timeouts are 10 seconds; the reader
retries once after two seconds, and the worker applies a 55-second overall read
deadline. Backend cancellation/disconnection cleanup may extend that deadline.
Failed reads recover on the next poll or manual refresh.

Target changes cancel obsolete work and discard queued results from old targets.
Quit stops polling, cancels and awaits active work, then stops/joins the worker
before destroying the window. The UI continues pumping events while displaying
the closing status. A driver that never finishes cancellation can delay exit;
forced termination cannot guarantee graceful BLE cleanup.

The dongle's 12-digit classic address is formatted as colon-separated pairs.
That address works as the BLE address on the tested BT-5181Pro, but this is not
universal: other headsets may use different/rotating BLE addresses, lack Battery
Service, or disallow simultaneous connections. Such devices show Unavailable.
macOS generally uses CoreBluetooth identifiers instead of classic MAC addresses;
this address-based feature is not hardware-validated there.

The workspace's optional `windows_bluetooth.py` enable/restore helper is deliberately
not included. It remembers which radios it enabled, but cannot distinguish all
external changes to those radios before restoration, and restoration can fail or
be skipped on forced termination. This build uses only read-only radio inspection.

## Battery validation (2026-10-10)

The packaged `dist\FlooCast.exe` displayed **49%** for **BT-5181Pro** while the
FMA121 on **COM7** streamed **aptX Adaptive at 48 kHz**. Manual Refresh displayed
Reading and disabled Refresh while busy, then returned 49%. The PC radio was
already on, enabled by the user for the test.

The read-only serial baseline was firmware `1.1.7G`, `AM=81` (Gaming with analog
input), `ST=06` (audio streaming), `LA=00`, `LF=00` (Prefer LE Audio off),
`FT=09` (USB Audio Input and LED on, aptX Lossless off), `AC=06` (aptX Adaptive),
and `FN=00,00025B00FF0B,BT-5181Pro`. The executable's visible controls also showed
Start Minimized on and firmware upgrade disabled. No other FlooCast instance
was running when the test began.

After exiting the executable during a new read, its processes terminated and
COM7 was available again. The read-only comparison matched the same firmware,
AM/ST/LA/LF/FT values, codec, and paired-device address/name. PC Bluetooth remained
ON; no settings or radio restoration was performed.

The final build was verified again at **2026-10-10 05:53 UTC**: startup and manual
Refresh both returned **48%**, the automatic one-minute poll visibly entered
Reading, and Quit during that poll exited with **code 0**. The final COM7 comparison
again matched the baseline, and PC Bluetooth remained ON. An earlier run briefly
reported Bluetooth off before a later query reported ON; its cause was not
established. The final run recovered successfully. Unknown radio states now
report Unavailable rather than incorrectly claiming Bluetooth is off.

Final executable SHA-256:
`EB2F774B4D1BA1F976129C355730F815E477BE56A063D0C154E394D5FDBB0182`.

Run automated regression tests from this directory:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -p 'test_battery*.py' -v
```

Tests cover address formatting/retention in both enumeration paths, immutable
list snapshots, selection fallback, duplicate names, protocol indices, 0%/100%,
invalid values, missing devices, transient retry, disconnect on success/error/
cancellation, unavailable/Bluetooth-off recovery, prevention of overlapping
reads, stale queued callbacks, timeout cleanup, target replacement, and shutdown
that waits for cleanup. Hardware tests do not establish support for other headsets.
All **18 tests passed** on Windows/Python 3.13, including real wx controls and
CallAfter delivery, Bluetooth-off/unavailable labels, and window destruction.
Linux import behavior was simulated; Linux/macOS hardware was not tested.

The worker's apartment/thread model follows the
[Bleak Windows threading guidance](https://bleak.readthedocs.io/en/stable/troubleshooting.html#not-working-when-threading-model-is-sta).

`validate_hardware.py` sends only read queries to COM7 and must run with FlooCast
closed. `validate_windows_ui.ps1` inspects the running executable and can invoke
Refresh/Quit or save a window screenshot. These are development validation tools,
not application runtime components.
`validate_packaged.ps1` automates a live manual-refresh/minute-poll/shutdown check
with the executable and performs the final read-only hardware comparison.
