from __future__ import annotations

from datetime import datetime
import shlex
import subprocess
import time

from .config_manager import AppConfig
from .eye_scan_module import EyeScanCommand, EyeScanModule
from .seninf_path_resolver import SeninfPathResolver


class CommandProcessor:
    """Command handler that sends real EYE_SCAN commands through adb."""

    _AUTO_SENSOR_INDEXES = (1, 2, 4, 8, 16)
    _NON_EYE_STEPS = {"mode", "adb device", "sensor idx", "sensor mode"}
    _STEP_REGISTER_MAP = {
        "cdr delay": "CDR_DELAY",
        "eq offset": "EQ_OFFSET",
        "eq dg0 enable": "EQ_DG0_ENABLE",
        "eq sr0": "EQ_SR0",
        "eq dg1 enable": "EQ_DG1_ENABLE",
        "eq sr1": "EQ_SR1",
        "eq bw": "EQ_BW",
        "phy mode": "PHY_MODE",
    }
    _PHY_MODE_TO_VALUE = {"auto": 0, "master": 1, "slave": 2}

    def send(self, command: str, config: AppConfig) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S")
        adb_device = config.adb_device
        if not adb_device:
            return f"[{timestamp}] No adb device selected."

        try:
            seninf_path = SeninfPathResolver(adb_device).resolve()
        except Exception as error:  # noqa: BLE001
            return f"[{timestamp}] Resolve seninf path failed: {error}"

        targets = self._build_targets(config)
        lines: list[str] = []

        for sensor_idx, sensor_mode in targets:
            try:
                line = self._send_to_target(
                    command=command,
                    config=config,
                    adb_device=adb_device,
                    seninf_path=seninf_path,
                    sensor_idx=sensor_idx,
                    sensor_mode=sensor_mode,
                )
            except Exception as error:  # noqa: BLE001
                line = (
                    f"[{timestamp}] serial={adb_device} sensor_idx={sensor_idx} "
                    f"sensor_mode={sensor_mode} ERROR: {error}"
                )
            lines.append(line)

        return "\n".join(lines)

    def _build_targets(self, config: AppConfig) -> list[tuple[int, int]]:
        if config.mode not in {"auto", "dify"}:
            sensor_mode = config.sensor_mode[0] if config.sensor_mode else 0
            return [(config.sensor_idx, sensor_mode)]

        sensor_modes = config.sensor_mode or [0, 1, 2]
        return [
            (sensor_idx, sensor_mode)
            for sensor_idx in self._AUTO_SENSOR_INDEXES
            for sensor_mode in sensor_modes
        ]

    def _send_to_target(
        self,
        *,
        command: str,
        config: AppConfig,
        adb_device: str,
        seninf_path: str,
        sensor_idx: int,
        sensor_mode: int,
    ) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S")
        driver_sensor_idx = self._map_dts_idx(sensor_idx)

        with _SentestSession(adb_device, sensor_idx, sensor_mode):
            eye = EyeScanModule(serial=adb_device, seninf_path=seninf_path)
            eye_command = self._build_eye_command(command, config, driver_sensor_idx)
            result = eye.execute(eye_command)

        state = "SUCCESS" if result.ok else "FAIL"
        return (
            f"[{timestamp}] serial={adb_device} sensor_idx={sensor_idx} sensor_mode={sensor_mode} "
            f"register={eye_command.register} value={eye_command.value} {state}: {result.raw_output.strip()}"
        )

    def _build_eye_command(self, command: str, config: AppConfig, driver_sensor_idx: int) -> EyeScanCommand:
        normalized = command.strip().lower()
        if normalized in self._NON_EYE_STEPS:
            raise ValueError(f"Step '{command}' does not map to an EYE_SCAN register.")

        if normalized in self._STEP_REGISTER_MAP:
            register = self._STEP_REGISTER_MAP[normalized]
            value = self._step_value(normalized, config)
            return EyeScanCommand(driver_sensor_idx=driver_sensor_idx, register=register, value=value)

        tokens = shlex.split(command)
        if not tokens:
            raise ValueError("Empty command.")

        register = tokens[0].upper()
        if len(tokens) == 1:
            return EyeScanCommand(driver_sensor_idx=driver_sensor_idx, register=register)

        value = int(tokens[1], 0)
        return EyeScanCommand(driver_sensor_idx=driver_sensor_idx, register=register, value=value)

    def _step_value(self, step: str, config: AppConfig) -> int | None:
        if step == "cdr delay":
            return config.cdr_delay_start
        if step == "eq offset":
            return config.eq_offset
        if step == "eq dg0 enable":
            return config.eq_dg0_enable
        if step == "eq sr0":
            return config.eq_sr0
        if step == "eq dg1 enable":
            return config.eq_dg1_enable
        if step == "eq sr1":
            return config.eq_sr1
        if step == "eq bw":
            return config.eq_bw
        if step == "phy mode":
            return self._PHY_MODE_TO_VALUE[config.phy_mode]
        return None

    @staticmethod
    def _map_dts_idx(sensor_idx: int) -> int:
        return sensor_idx.bit_length() - 1


class _SentestSession:
    def __init__(self, serial: str, sensor_idx: int, sensor_mode: int) -> None:
        self._serial = serial
        self._sensor_idx = sensor_idx
        self._sensor_mode = sensor_mode
        self._proc: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> _SentestSession:
        cmd = (
            f'adb -s {self._serial} shell "sentest_v412 '
            f'{self._sensor_idx} {self._sensor_mode}"'
        )
        self._proc = subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(1)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if self._proc is None:
            return

        try:
            if self._proc.stdin is not None:
                self._proc.stdin.write(b"\n")
                self._proc.stdin.flush()
            self._proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.communicate()
