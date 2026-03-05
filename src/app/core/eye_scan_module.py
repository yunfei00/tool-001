from __future__ import annotations

from dataclasses import dataclass
import re
import subprocess
from typing import Final


SUCCESS_FLAG: Final[str] = "[EYE_SCAN SUCCESS]"
FAIL_FLAG: Final[str] = "[EYE_SCAN FAIL]"
HEX_VALUE_PATTERN: Final[re.Pattern[str]] = re.compile(r"0x[0-9a-fA-F]+")


@dataclass(frozen=True)
class EyeScanCommand:
    """EYE_SCAN command payload.

    Attributes:
        driver_sensor_idx: Sensor index used by kernel driver (e.g. 0x0, 0x1).
        register: EYE_SCAN register command string (e.g. CDR_DELAY, GET_CRC_STATUS).
        value: Optional value for write operations. Positive values are formatted as hex,
            negative values are formatted as decimal to keep parity with existing scripts.
    """

    driver_sensor_idx: int
    register: str
    value: int | None = None


@dataclass(frozen=True)
class EyeScanResult:
    command: EyeScanCommand
    ok: bool
    raw_output: str
    adb_command: str

    @property
    def readback_hex_values(self) -> list[int]:
        """All hex values found in command output, parsed as integers."""
        return [int(token, 16) for token in HEX_VALUE_PATTERN.findall(self.raw_output)]


class EyeScanModule:
    """Generic EYE_SCAN executor + readback comparator over adb shell."""

    def __init__(
        self,
        serial: str,
        seninf_path: str,
        adb_bin: str = "adb",
    ) -> None:
        self._serial = serial
        self._seninf_path = seninf_path
        self._adb_bin = adb_bin

    def execute(self, command: EyeScanCommand) -> EyeScanResult:
        payload = self._build_eye_scan_payload(command)
        adb_cmd = (
            f'{self._adb_bin} -s {self._serial} shell "cd {self._seninf_path}; '
            f'echo {payload} > debug_ops ; cat debug_ops"'
        )
        output = subprocess.getoutput(adb_cmd)

        ok = SUCCESS_FLAG in output and FAIL_FLAG not in output
        return EyeScanResult(command=command, ok=ok, raw_output=output, adb_command=adb_cmd)

    def execute_and_compare_readback(
        self,
        command: EyeScanCommand,
        expected_value: int,
    ) -> tuple[EyeScanResult, bool]:
        """Execute command then compare the final readback hex value with expectation."""
        result = self.execute(command)
        readback_values = result.readback_hex_values

        if not result.ok or not readback_values:
            return result, False

        return result, readback_values[-1] == expected_value

    def _build_eye_scan_payload(self, command: EyeScanCommand) -> str:
        payload = f"EYE_SCAN {hex(command.driver_sensor_idx)} {command.register}"
        if command.value is None:
            return payload
        if command.value < 0:
            return f"{payload} {command.value}"
        return f"{payload} {hex(command.value)}"
