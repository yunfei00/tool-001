from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
from threading import Lock

from .serial_port_service import SerialPortService, SerialPortSettings


@dataclass
class SerialCommandResult:
    command: str
    success: bool
    response: str
    error: str
    timestamp: str

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "command": self.command,
            "success": self.success,
            "response": self.response,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class SerialCommandService:
    def __init__(self, serial_port_service: SerialPortService | None = None) -> None:
        self._serial_port_service = serial_port_service or SerialPortService()
        self._connection = None
        self._opened_settings: SerialPortSettings | None = None
        self._io_lock = Lock()

    @staticmethod
    def default_commands_text() -> str:
        return "\n".join(
            [
                "AT+ERFTX=6,0,0",
                'AT+EGMC=1,"NrAntSwAging",0',
                "AT^WITX=0",
            ]
        )

    @staticmethod
    def parse_commands(raw_text: str) -> list[str]:
        return [line.strip() for line in raw_text.splitlines() if line.strip()]

    def load_commands_from_file(self, file_path: Path) -> list[str]:
        suffix = file_path.suffix.lower()
        if suffix == ".txt":
            return self.parse_commands(file_path.read_text(encoding="utf-8"))

        if suffix == ".json":
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            commands = payload.get("commands") if isinstance(payload, dict) else None
            if not isinstance(commands, list):
                raise ValueError("JSON 文件格式错误，应为 {\"commands\": [...]} ")
            return [str(command).strip() for command in commands if str(command).strip()]

        raise ValueError("仅支持导入 txt 或 json 文件")

    def export_commands_to_file(self, file_path: Path, commands: list[str]) -> None:
        suffix = file_path.suffix.lower()
        if suffix == ".txt":
            payload = "\n".join(commands)
            file_path.write_text(payload, encoding="utf-8")
            return

        if suffix == ".json":
            payload = {"commands": commands}
            file_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return

        raise ValueError("仅支持导出 txt 或 json 文件")

    def send_commands(self, settings: SerialPortSettings, commands: list[str]) -> list[dict[str, str | bool]]:
        if not commands:
            return []

        results: list[SerialCommandResult] = []
        try:
            connection = self._serial_port_service.open_port(settings)
        except Exception as error:  # noqa: BLE001
            timestamp = datetime.now().isoformat(timespec="seconds")
            for command in commands:
                results.append(
                    SerialCommandResult(
                        command=command,
                        success=False,
                        response="",
                        error=str(error),
                        timestamp=timestamp,
                    )
                )
            return [item.to_dict() for item in results]

        with connection:
            for command in commands:
                timestamp = datetime.now().isoformat(timespec="seconds")
                try:
                    response = self._serial_port_service.send_and_receive(connection, command)
                    results.append(
                        SerialCommandResult(
                            command=command,
                            success=True,
                            response=response,
                            error="",
                            timestamp=timestamp,
                        )
                    )
                except Exception as error:  # noqa: BLE001
                    results.append(
                        SerialCommandResult(
                            command=command,
                            success=False,
                            response="",
                            error=str(error),
                            timestamp=timestamp,
                        )
                    )
        return [item.to_dict() for item in results]

    @property
    def is_open(self) -> bool:
        return bool(self._connection and getattr(self._connection, "is_open", False))

    @property
    def opened_port(self) -> str:
        if not self._opened_settings:
            return ""
        return self._opened_settings.port

    def open_connection(self, settings: SerialPortSettings) -> None:
        self.close_connection()
        self._connection = self._serial_port_service.open_port(settings)
        self._opened_settings = settings

    def close_connection(self) -> None:
        if self._connection:
            try:
                self._connection.close()
            finally:
                self._connection = None
                self._opened_settings = None

    def send_with_opened_connection(self, commands: list[str]) -> list[dict[str, str | bool]]:
        if not commands:
            return []
        if not self.is_open or self._connection is None:
            raise RuntimeError("串口未打开，请先打开串口")

        results: list[SerialCommandResult] = []
        for command in commands:
            timestamp = datetime.now().isoformat(timespec="seconds")
            try:
                with self._io_lock:
                    self._serial_port_service.send_command(self._connection, command)
                results.append(
                    SerialCommandResult(
                        command=command,
                        success=True,
                        response="",
                        error="",
                        timestamp=timestamp,
                    )
                )
            except Exception as error:  # noqa: BLE001
                results.append(
                    SerialCommandResult(
                        command=command,
                        success=False,
                        response="",
                        error=str(error),
                        timestamp=timestamp,
                    )
                )
        return [item.to_dict() for item in results]

    def receive_with_opened_connection(self) -> str:
        if not self.is_open or self._connection is None:
            return ""
        with self._io_lock:
            return self._serial_port_service.read_available(self._connection)
