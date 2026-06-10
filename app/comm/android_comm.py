"""
app/comm/android_comm.py
Android Bluetooth Classic (RFCOMM/SPP) via pyjnius Java bridge.
This module is ONLY functional inside a Flet APK build on Android.

The HC-05 must be paired first via Android Bluetooth settings.
Device list shows paired (bonded) devices — user selects HC-05.

Protocol: single ASCII char per command (A/D/W/S/K/I/J/L/C/O).
"""
from __future__ import annotations

from app.comm.base import BtComm

# SPP (Serial Port Profile) service UUID — standard for HC-05
_SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"

_BT_PERMISSIONS = [
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.BLUETOOTH_SCAN",
    "android.permission.ACCESS_FINE_LOCATION",
]


def _request_android_permissions() -> None:
    """Request Bluetooth runtime permissions (Android 12+ requires BLUETOOTH_CONNECT/SCAN)."""
    try:
        from jnius import autoclass  # type: ignore[import]
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        ActivityCompat = autoclass("androidx.core.app.ActivityCompat")
        ContextCompat = autoclass("androidx.core.content.ContextCompat")
        PackageManager = autoclass("android.content.pm.PackageManager")

        activity = PythonActivity.mActivity
        needed = [
            p for p in _BT_PERMISSIONS
            if ContextCompat.checkSelfPermission(activity, p)
            != PackageManager.PERMISSION_GRANTED
        ]
        if needed:
            ActivityCompat.requestPermissions(activity, needed, 1)
    except Exception:
        pass  # not on Android or pyjnius unavailable


class AndroidComm(BtComm):
    """Bluetooth Classic RFCOMM via pyjnius (Android only)."""

    def __init__(self) -> None:
        self._socket = None
        self._out_stream = None
        self._connected = False
        _request_android_permissions()

    # ── Device discovery ────────────────────────────────────────────────────

    def list_devices(self) -> list[dict[str, str]]:
        """Return paired (bonded) Bluetooth devices visible to Android."""
        try:
            from jnius import autoclass  # type: ignore[import]

            BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
            adapter = BluetoothAdapter.getDefaultAdapter()
            if adapter is None:
                return []
            paired_set = adapter.getBondedDevices()
            if paired_set is None:
                return []
            devices = []
            for device in paired_set.toArray():
                devices.append(
                    {
                        "name": device.getName() or "Desconocido",
                        "address": device.getAddress(),
                    }
                )
            return devices
        except Exception:
            return []

    # ── Connection ──────────────────────────────────────────────────────────

    def connect(self, address: str) -> bool:
        """
        Connect to HC-05 at MAC `address` using RFCOMM socket.
        Must be called from a background thread (not the main UI thread).
        """
        try:
            from jnius import autoclass  # type: ignore[import]

            BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
            UUID = autoclass("java.util.UUID")

            adapter = BluetoothAdapter.getDefaultAdapter()
            adapter.cancelDiscovery()  # discovery slows BT throughput

            device = adapter.getRemoteDevice(address)
            uuid = UUID.fromString(_SPP_UUID)
            self._socket = device.createRfcommSocketToServiceRecord(uuid)
            self._socket.connect()
            self._out_stream = self._socket.getOutputStream()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    # ── Communication ───────────────────────────────────────────────────────

    def send(self, cmd: str) -> bool:
        """Write single ASCII character command via RFCOMM output stream."""
        if not self.is_connected or self._out_stream is None:
            return False
        try:
            # OutputStream.write(int) writes one byte — avoids pyjnius byte[] coercion
            self._out_stream.write(ord(cmd[0]))
            self._out_stream.flush()
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        """Close RFCOMM socket and output stream."""
        try:
            if self._out_stream:
                self._out_stream.close()
            if self._socket:
                self._socket.close()
        except Exception:
            pass
        self._out_stream = None
        self._socket = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected
