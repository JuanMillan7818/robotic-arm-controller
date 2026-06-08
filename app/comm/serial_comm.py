"""
app/comm/serial_comm.py
Desktop Bluetooth via pyserial — HC-05 creates a virtual COM port
once paired through the OS Bluetooth settings (Windows/Linux/macOS).

Usage:
    comm = SerialComm()
    devices = comm.list_devices()          # list available COM ports
    comm.connect("COM3")                   # or "/dev/rfcomm0" on Linux
    comm.send("PINZA", 90)                 # → writes "PINZA:90\n"
    comm.disconnect()
"""
import logging
import re
import sys
import serial
import serial.tools.list_ports

from app.comm.base import BtComm

log = logging.getLogger(__name__)


def _bt_friendly_name(hwid: str) -> str | None:
    """
    Parse MAC address from COM port hwid and look up the Bluetooth device
    friendly name in the Windows registry.
    hwid example: BTHENUM\\{UUID}_LOCALMFG&0002\\8&...&0&000A3A0001AC_C00000000
    """
    if sys.platform != "win32":
        return None
    match = re.search(r"&0&([0-9A-Fa-f]{12})_", hwid or "")
    if not match:
        return None
    mac = match.group(1).lower()
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            rf"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices\{mac}",
        )
        name_bytes, _ = winreg.QueryValueEx(key, "Name")
        winreg.CloseKey(key)
        # REG_BINARY: null-terminated UTF-8 bytes
        return name_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")
    except Exception:
        return None


class SerialComm(BtComm):
    """Bluetooth Classic (RFCOMM/SPP) via OS virtual COM port + pyserial."""

    # HC-05 default baud rate. Change if configured differently.
    DEFAULT_BAUD = 9600

    def __init__(self, baud_rate: int = DEFAULT_BAUD) -> None:
        self._baud = baud_rate
        self._conn: serial.Serial | None = None

    # ── Device discovery ────────────────────────────────────────────────────

    def list_devices(self) -> list[dict[str, str]]:
        """
        Return all available serial/COM ports.
        On Windows, paired HC-05 appears as 'Standard Serial over Bluetooth link (COMx)'.
        """
        ports = serial.tools.list_ports.comports()
        all_ports = sorted(ports, key=lambda p: p.device)
        log.debug("Todos los COM: %s", [(p.device, p.description, p.hwid) for p in all_ports])
        bt_ports = [p for p in all_ports if "bluetooth" in p.description.lower()]
        display = bt_ports if bt_ports else all_ports

        result = []
        for p in display:
            bt_name = _bt_friendly_name(p.hwid)
            name = f"{bt_name} ({p.device})" if bt_name else p.description
            result.append({"name": name, "address": p.device})

        log.info("Dispositivos BT encontrados: %s", result)
        return result

    # ── Connection ──────────────────────────────────────────────────────────

    def connect(self, address: str) -> bool:
        """Open serial connection to COM port `address`."""
        try:
            self.disconnect()
            log.info("Conectando a %s @ %d baud...", address, self._baud)
            self._conn = serial.Serial(
                port=address,
                baudrate=self._baud,
                timeout=2,
                write_timeout=2,
            )
            log.info("Conexión exitosa: %s", address)
            return self._conn.is_open
        except (serial.SerialException, OSError) as e:
            log.error("Error al conectar a %s: %s", address, e)
            self._conn = None
            return False

    # ── Communication ───────────────────────────────────────────────────────

    def send(self, cmd: str) -> bool:
        """Write single ASCII character command to Arduino (e.g. 'A', 'W', 'C')."""
        if not self.is_connected:
            return False
        try:
            self._conn.write(cmd[0].encode("utf-8"))  # type: ignore[union-attr]
            log.debug("Enviado: %r", cmd[0])
            return True
        except (serial.SerialException, OSError) as e:
            log.error("Error al enviar '%s': %s", cmd, e)
            return False

    def disconnect(self) -> None:
        """Close serial port if open."""
        if self._conn and self._conn.is_open:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and self._conn.is_open
