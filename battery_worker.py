"""One in-process BLE loop; GUI callbacks are dispatched and generation checked."""

import asyncio
import logging
import sys
import threading

log = logging.getLogger(__name__)


class BluetoothOff(RuntimeError):
    pass


async def check_bluetooth():
    """Read radio state only. Never request permission to change it or enable it."""
    if sys.platform != "win32":
        return  # Bleak reports platform-specific adapter/access errors.
    from winrt.windows.devices.radios import Radio, RadioKind, RadioState

    radios = [r for r in await Radio.get_radios_async() if r.kind == RadioKind.BLUETOOTH]
    if not radios:
        raise RuntimeError("No PC Bluetooth adapter is available.")
    states = [radio.state for radio in radios]
    if not any(state == RadioState.ON for state in states):
        if all(state in (RadioState.OFF, RadioState.DISABLED) for state in states):
            raise BluetoothOff("Enable the PC Bluetooth adapter in Windows Settings, then Refresh.")
        raise RuntimeError("PC Bluetooth radio state is unavailable. Try Refresh.")


class HeadsetReader:
    def __init__(self):
        self.connection = None

    async def __call__(self, address):
        # Lazy import keeps FlooCast usable without battery dependencies.
        from battery_reader import BatteryConnection

        # A live GATT connection already establishes adapter availability. Avoid
        # tearing it down because of a transient/lagging radio-state snapshot.
        if self.connection is None or not self.connection.is_connected:
            try:
                await check_bluetooth()
            except BaseException:
                await self.aclose()
                raise
        if self.connection is None:
            self.connection = BatteryConnection()
        return await self.connection.read(address, timeout=10)

    async def aclose(self):
        if self.connection is not None:
            await self.connection.aclose()


class BatteryWorker:
    """Public methods belong to the GUI thread; all BLE work belongs to _loop.

    dispatch must enqueue on the GUI thread (wx.CallAfter in the application).
    A cancelled task retains ownership until its disconnect/cleanup has finished.
    """

    def __init__(self, callback, dispatch, reader=None, deadline=55):
        self.callback = callback
        self.dispatch = dispatch
        self.reader = reader if reader is not None else HeadsetReader()
        self.deadline = deadline
        self.target = None
        self.generation = 0
        self.busy = False
        self.closed = False
        self._loop = asyncio.new_event_loop()
        self._active = None
        self._pending = None
        self._stopping = False
        self._startup_error = None
        self._session_target = None
        self._thread = threading.Thread(target=self._run, name="FlooCast battery", daemon=False)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        ole32 = None
        try:
            if sys.platform == "win32":
                import ctypes
                ole32 = ctypes.OleDLL("ole32")
                # Dedicated thread: MTA, independent of wx's main-thread apartment.
                ole32.CoInitializeEx(None, 0)
        except Exception as error:
            self._startup_error = error
            ole32 = None
        try:
            self._loop.run_forever()
        finally:
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.run_until_complete(self._loop.shutdown_default_executor())
            self._loop.close()
            if ole32 is not None:
                ole32.CoUninitialize()

    def set_target(self, address):
        if self.closed or address == self.target:
            return
        self.generation += 1
        self.target = address
        self.busy = bool(address)
        self.callback("Reading" if address else "Unavailable", "" if address else "Select a headset.")
        self._loop.call_soon_threadsafe(self._replace, self.generation, address)

    def refresh(self):
        if self.closed or self.busy or not self.target:
            return False
        self.busy = True
        self.callback("Reading", "")
        self._loop.call_soon_threadsafe(self._replace, self.generation, self.target)
        return True

    def _replace(self, generation, address):
        if self._stopping:
            return
        # A None target still needs a task to close an idle retained connection.
        self._pending = (generation, address)
        if self._active is not None:
            if not self._active.cancelling():
                self._active.cancel()
        else:
            self._start_pending()

    def _start_pending(self):
        if self._pending is not None and not self._stopping:
            generation, address = self._pending
            self._pending = None
            self._active = self._loop.create_task(self._read(generation, address))
            self._active.add_done_callback(self._finished)

    async def _read(self, generation, address):
        try:
            if self._startup_error is not None:
                raise self._startup_error
            if address != self._session_target:
                await self._close_reader()
                self._session_target = address
            if address is None:
                return
            value = await asyncio.wait_for(self.reader(address), self.deadline)
            if type(value) is not int or not 0 <= value <= 100:
                raise ValueError("Battery Level must be an integer from 0 to 100.")
            state, detail = f"{value}%", address
        except asyncio.CancelledError:
            raise
        except BluetoothOff as error:
            state, detail = "Bluetooth off", str(error)
        except Exception as error:
            log.warning("Battery read for %s failed: %s", address, error)
            state = "Unavailable"
            detail = str(error) or "Battery read timed out. Try Refresh."
        self.dispatch(self._deliver, generation, state, detail)

    def _deliver(self, generation, state, detail):
        if self.closed or generation != self.generation:
            return
        self.busy = False
        self.callback(state, detail)

    def _finished(self, task):
        # Retrieve cancellation/exception before releasing ownership.
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Battery worker callback failed")
        self._active = None
        if self._stopping:
            self._start_shutdown()
        else:
            self._start_pending()

    def stop(self):
        if self.closed:
            return
        self.closed = True
        self.generation += 1
        self.busy = False
        self._loop.call_soon_threadsafe(self._stop)

    def _stop(self):
        self._stopping = True
        self._pending = None
        if self._active is None:
            self._start_shutdown()
        elif not self._active.cancelling():
            self._active.cancel()

    async def _close_reader(self):
        close = getattr(self.reader, "aclose", None)
        if close is not None:
            await close()

    def _start_shutdown(self):
        # Runs even when no read is active: successful polls retain the client.
        self._active = self._loop.create_task(self._close_reader())
        self._active.add_done_callback(self._shutdown_finished)

    def _shutdown_finished(self, task):
        try:
            task.result()
        except BaseException:
            log.exception("Could not cleanly disconnect the battery connection")
        finally:
            self._active = None
            self._loop.stop()

    def join(self, timeout=None):
        self._thread.join(timeout)
        return not self._thread.is_alive()
