"""
app/comm/base.py
Abstract base class for Bluetooth communication.
Protocol: single ASCII character per command (matches arduino_code.ino).
"""
from abc import ABC, abstractmethod


class BtComm(ABC):
    """Platform-agnostic Bluetooth communication interface."""

    @abstractmethod
    def list_devices(self) -> list[dict[str, str]]:
        """Return available devices as list of {name, address} dicts."""
        ...

    @abstractmethod
    def connect(self, address: str) -> bool:
        """Open connection to device at `address`. Returns True on success."""
        ...

    @abstractmethod
    def send(self, cmd: str) -> bool:
        """
        Send a single-character command to the Arduino.
        Commands (case-insensitive):
          A/D  — Base ±15°
          W/S  — Hombro (BasePrincipal) ±15°
          K/I  — Codo (Ext1) ±15°
          L/J  — Muñeca (Ext2) ±15°
          C/O  — Pinza cerrar/abrir ±15° (range 110–145)
        Returns True if write succeeded.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection and release resources."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True if there is an active connection."""
        ...
