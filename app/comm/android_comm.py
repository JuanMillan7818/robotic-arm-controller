"""
app/comm/android_comm.py
Android Bluetooth Classic (RFCOMM/SPP) via pyjnius Java bridge.
This module is ONLY functional inside a Flet APK build on Android.

The HC-05 must be paired first via Android Bluetooth settings.
Device list shows paired (bonded) devices — user selects HC-05.

Protocol: single ASCII char per command (A/D/W/S/K/I/J/L/C/O).
"""
from __future__ import annotations

import logging

from app.comm.base import BtComm

log = logging.getLogger(__name__)

# SPP (Serial Port Profile) service UUID — standard for HC-05
_SPP_UUID = "00001101-0000-1000-8000-00805F9B34FB"

_BT_PERMISSIONS = [
    "android.permission.BLUETOOTH",
    "android.permission.BLUETOOTH_ADMIN",
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.BLUETOOTH_SCAN",
    "android.permission.ACCESS_FINE_LOCATION",
]


def _request_permissions() -> None:
    """Request BT runtime permissions via python-for-android (p4a built-in).
    Uses string literals — avoids missing Permission.* constants on older p4a.
    """
    try:
        from android.permissions import request_permissions  # type: ignore[import]
        request_permissions(_BT_PERMISSIONS)
        log.info("BT permissions requested")
    except Exception as exc:
        log.warning("android.permissions unavailable: %s", exc)



class AndroidComm(BtComm):
    """Bluetooth Classic RFCOMM via pyjnius (Android only)."""

    def __init__(self) -> None:
        self._socket = None
        self._out_stream = None
        self._connected = False

    # ── Device discovery ────────────────────────────────────────────────────

    def list_devices(self) -> list[dict[str, str]]:
        """Return paired (bonded) Bluetooth devices.

        Requests permissions on every call if not yet granted (async dialog).
        Uses try/except instead of pre-check to avoid false negatives.
        """
        _request_permissions()
        try:
            from jnius import autoclass  # type: ignore[import]

            BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")

            adapter = BluetoothAdapter.getDefaultAdapter()
            if adapter is None:
                log.error("No BluetoothAdapter found")
                return []

            paired_set = adapter.getBondedDevices()
            if paired_set is None or paired_set.size() == 0:
                log.info("No paired BT devices")
                return []

            BluetoothDevice = autoclass("android.bluetooth.BluetoothDevice")
            devices: list[dict[str, str]] = []
            iterator = paired_set.iterator()
            while iterator.hasNext():
                from jnius import cast  # type: ignore[import]
                dev = cast(BluetoothDevice, iterator.next())
                name = dev.getName() or "Desconocido"
                addr = dev.getAddress()
                devices.append({"name": name, "address": addr})
                log.info("BT device: %s  %s", name, addr)

            return devices

        except Exception as exc:
            log.error("list_devices error: %s", exc)
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
            log.info("BT connected to %s", address)
            return True
        except Exception as exc:
            log.error("BT connect error (%s): %s", address, exc)
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
        except Exception as exc:
            log.error("BT send error: %s", exc)
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
