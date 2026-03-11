from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import serial
from serial.tools import list_ports


@dataclass
class SerialPortSettings:
    port: str
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    timeout: float = 1.0


class SerialPortService:
    """Encapsulate serial port scanning and command transfer details."""

    _BYTE_SIZE_MAP = {
        5: serial.FIVEBITS,
        6: serial.SIXBITS,
        7: serial.SEVENBITS,
        8: serial.EIGHTBITS,
    }
    _STOP_BITS_MAP = {
        1: serial.STOPBITS_ONE,
        1.5: serial.STOPBITS_ONE_POINT_FIVE,
        2: serial.STOPBITS_TWO,
    }
    _PARITY_MAP = {
        "N": serial.PARITY_NONE,
        "E": serial.PARITY_EVEN,
        "O": serial.PARITY_ODD,
        "M": serial.PARITY_MARK,
        "S": serial.PARITY_SPACE,
    }

    def list_available_ports(self) -> list[dict[str, str | None]]:
        ports: list[dict[str, str | None]] = []
        for info in list_ports.comports():
            ports.append(
                {
                    "port": info.device,
                    "description": info.description,
                    "hwid": info.hwid,
                    "serial_number": getattr(info, "serial_number", None),
                }
            )
        return ports

    def open_port(self, settings: SerialPortSettings) -> serial.Serial:
        return serial.Serial(
            port=settings.port,
            baudrate=settings.baudrate,
            bytesize=self._BYTE_SIZE_MAP.get(settings.bytesize, serial.EIGHTBITS),
            parity=self._PARITY_MAP.get(settings.parity.upper(), serial.PARITY_NONE),
            stopbits=self._STOP_BITS_MAP.get(settings.stopbits, serial.STOPBITS_ONE),
            timeout=settings.timeout,
            write_timeout=settings.timeout,
        )

    @staticmethod
    def normalize_response(raw_text: str) -> str:
        return raw_text.replace("\r", "").replace("\n", "")

    def send_command(self, conn: serial.Serial, command: str) -> None:
        payload = f"{command.rstrip()}\r\n".encode("utf-8")
        conn.write(payload)
        conn.flush()

    def read_available(self, conn: serial.Serial) -> str:
        raw = conn.read_all()
        if not raw:
            return ""
        return self.normalize_response(raw.decode("utf-8", errors="replace"))

    def send_and_receive(self, conn: serial.Serial, command: str) -> str:
        self.send_command(conn, command)
        raw = conn.read_until(expected=b"OK\r\n")
        if not raw:
            raw = conn.read_all()
        return self.normalize_response(raw.decode("utf-8", errors="replace"))

    @staticmethod
    def validate_settings(raw_settings: dict[str, Any]) -> SerialPortSettings:
        port = str(raw_settings.get("port", "")).strip()
        if not port:
            raise ValueError("未选择串口")

        return SerialPortSettings(
            port=port,
            baudrate=int(raw_settings.get("baudrate", 9600)),
            bytesize=int(raw_settings.get("bytesize", 8)),
            parity=str(raw_settings.get("parity", "N")).strip().upper() or "N",
            stopbits=float(raw_settings.get("stopbits", 1)),
            timeout=float(raw_settings.get("timeout", 1.0)),
        )
