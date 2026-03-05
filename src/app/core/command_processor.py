from __future__ import annotations

from datetime import datetime
from itertools import product
from pathlib import Path
import shlex
import csv
import subprocess

from app.core.config_manager import AppConfig
from app.core.eye_scan_module import EyeScanCommand, EyeScanModule
from app.core.seninf_path_resolver import SeninfPathResolver


class CommandProcessor:
    """Command handler that sends real EYE_SCAN commands through adb."""

    _AUTO_SENSOR_INDEXES = (1, 2, 4, 8, 16)
    _NON_EYE_STEPS = {"mode", "adb device", "sensor idx", "sensor mode"}
    _STEP_REGISTER_MAP = {
        "cdr delay": "CDR_DELAY",
        "eq offset": "EQ_OFFSET",
        "eq dg0 enable": "EQ_DG0_EN",
        "eq sr0": "EQ_SR0",
        "eq dg1 enable": "EQ_DG1_EN",
        "eq sr1": "EQ_SR1",
        "eq bw": "EQ_BW",
    }
    _DEFAULT_AUTO_STEPS = (
        "cdr delay",
        "eq offset",
        "eq dg0 enable",
        "eq sr0",
        "eq dg1 enable",
        "eq sr1",
        "eq bw",
    )
    _SENTEST_LOCAL_PATH = Path("tool") / "sentest_v412"
    _SENTEST_REMOTE_PATH = "/data/local/tmp/sentest_v412"

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
                self._start_stream(adb_device=adb_device, sensor_idx=sensor_idx, sensor_mode=sensor_mode)
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

    def _start_stream(self, *, adb_device: str, sensor_idx: int, sensor_mode: int) -> None:
        sentest_path = self._SENTEST_LOCAL_PATH
        if not sentest_path.exists():
            raise RuntimeError(f"Missing stream tool: {sentest_path}")

        push_cmd = ["adb", "-s", adb_device, "push", str(sentest_path), self._SENTEST_REMOTE_PATH]
        push_result = subprocess.run(push_cmd, check=False, capture_output=True, text=True)
        if push_result.returncode != 0:
            output = (push_result.stdout or "") + (push_result.stderr or "")
            raise RuntimeError(f"Push sentest_v412 failed: {output.strip()}")

        chmod_cmd = ["adb", "-s", adb_device, "shell", f"chmod 755 {self._SENTEST_REMOTE_PATH}"]
        subprocess.run(chmod_cmd, check=False, capture_output=True, text=True)

        errors: list[str] = []
        for stream_cmd in self._build_stream_commands(
            adb_device=adb_device,
            sensor_idx=sensor_idx,
            sensor_mode=sensor_mode,
        ):
            result = subprocess.run(stream_cmd, check=False, capture_output=True, text=True)
            if result.returncode == 0:
                return
            output = ((result.stdout or "") + (result.stderr or "")).strip()
            errors.append(f"{' '.join(stream_cmd)} -> {output}")

        raise RuntimeError(
            "Start stream failed: sentest_v412 command returned non-zero. "
            + " | ".join(errors)
        )

    def _build_stream_commands(self, *, adb_device: str, sensor_idx: int, sensor_mode: int) -> list[list[str]]:
        return [
            [
                "adb",
                "-s",
                adb_device,
                "shell",
                f"{self._SENTEST_REMOTE_PATH} --sensor-idx {sensor_idx} --sensor-mode {sensor_mode} --start-stream",
            ],
            [
                "adb",
                "-s",
                adb_device,
                "shell",
                f"{self._SENTEST_REMOTE_PATH} {sensor_idx} {sensor_mode}",
            ],
            [
                "adb",
                "-s",
                adb_device,
                "shell",
                f"{self._SENTEST_REMOTE_PATH}",
            ],
        ]

    def run_automated_test(self, config: AppConfig, step_text: str = "") -> str:
        steps = self._parse_auto_steps(step_text)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("configs") / "auto_test_outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        if set(steps) == {"cdr delay", "eq offset"} and len(steps) == 2:
            cdr_path = output_dir / f"cdr_delay_{timestamp}.txt"
            eq_path = output_dir / f"eq_offset_{timestamp}.txt"
            self._run_single_param_sweep("cdr delay", config, cdr_path)
            self._run_single_param_sweep("eq offset", config, eq_path)
            return (
                "自动化测试完成。\n"
                f"cdr delay 输出文件: {cdr_path}\n"
                f"eq offset 输出文件: {eq_path}"
            )

        csv_path = output_dir / f"multi_param_{timestamp}.csv"
        row_count = self._run_multi_param_sweep(steps, config, csv_path)
        return f"自动化测试完成。共 {row_count} 行，CSV 输出: {csv_path}"

    def _parse_auto_steps(self, step_text: str) -> list[str]:
        if not step_text.strip():
            return list(self._DEFAULT_AUTO_STEPS)
        parts = [part.strip().lower() for part in step_text.replace(";", ",").split(",")]
        steps = [step for step in parts if step in self._STEP_REGISTER_MAP]
        return steps or list(self._DEFAULT_AUTO_STEPS)

    def _run_single_param_sweep(self, step: str, config: AppConfig, output_path: Path) -> None:
        with output_path.open("w", encoding="utf-8") as handle:
            for value in self._step_candidates(step, config):
                run_config = self._config_with_step_value(config, step, value)
                result = self.send(step, run_config)
                handle.write(f"{step}={value}\n{result}\n\n")

    def _run_multi_param_sweep(self, steps: list[str], config: AppConfig, csv_path: Path) -> int:
        candidates = [self._step_candidates(step, config) for step in steps]
        header = [*steps, "final_result"]
        count = 0
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            for values in product(*candidates):
                run_config = config
                final_result = ""
                for step, value in zip(steps, values):
                    run_config = self._config_with_step_value(run_config, step, value)
                    final_result = self.send(step, run_config)
                writer.writerow([*values, final_result])
                count += 1
        return count

    def _step_candidates(self, step: str, config: AppConfig) -> list[int]:
        if step == "cdr delay":
            cdr_max = 254 if config.is_dphy else 31
            return list(range(0, cdr_max + 1))
        if step == "eq offset":
            return list(range(-31, 32))
        if step == "eq dg0 enable":
            return [0, 1]
        if step == "eq sr0":
            return list(range(0, 16))
        if step == "eq dg1 enable":
            return [0, 1]
        if step == "eq sr1":
            return list(range(0, 16))
        if step == "eq bw":
            return [0, 1, 2, 3]
        return [0]

    def _config_with_step_value(self, config: AppConfig, step: str, value: int) -> AppConfig:
        return AppConfig(
            mode=config.mode,
            adb_device=config.adb_device,
            is_dphy=config.is_dphy,
            sensor_idx=config.sensor_idx,
            sensor_mode=config.sensor_mode,
            cdr_delay_start=value if step == "cdr delay" else config.cdr_delay_start,
            eq_offset=value if step == "eq offset" else config.eq_offset,
            eq_dg0_enable=value if step == "eq dg0 enable" else config.eq_dg0_enable,
            eq_sr0=value if step == "eq sr0" else config.eq_sr0,
            eq_dg1_enable=value if step == "eq dg1 enable" else config.eq_dg1_enable,
            eq_sr1=value if step == "eq sr1" else config.eq_sr1,
            eq_bw=value if step == "eq bw" else config.eq_bw,
        )

    def _build_targets(self, config: AppConfig) -> list[tuple[int, int]]:
        if config.mode != "auto":
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

        eye = EyeScanModule(serial=adb_device, seninf_path=seninf_path)
        eye_command = self._build_eye_command(command, config, driver_sensor_idx)
        result = eye.execute(eye_command)

        state = "SUCCESS" if result.ok else "FAIL"
        return (
            f"[{timestamp}] serial={adb_device} sensor_idx={sensor_idx} sensor_mode={sensor_mode} "
            f"register={eye_command.register} value={eye_command.value} adb_cmd={result.adb_command} "
            f"{state}: {result.raw_output.strip()}"
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
        return None

    @staticmethod
    def _map_dts_idx(sensor_idx: int) -> int:
        return sensor_idx.bit_length() - 1
