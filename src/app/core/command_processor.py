from __future__ import annotations

from datetime import datetime
from itertools import product
from pathlib import Path
from collections.abc import Callable
import time
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
    _SENTEST_LOCAL_PATH = Path("tool") / "sentest_v4l2"
    _SENTEST_REMOTE_PATH = "/data/local/tmp/sentest_v4l2"
    _ADB_SHORT_TIMEOUT_SECONDS = 10
    _ADB_STOP_TIMEOUT_SECONDS = 5

    def send(self, command: str, config: AppConfig, *, start_stream: bool = False) -> str:
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
                if start_stream:
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

    def start_stream_debug(self, config: AppConfig) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S")
        adb_device = config.adb_device
        if not adb_device:
            return f"[{timestamp}] No adb device selected."

        lines: list[str] = []
        for sensor_idx, sensor_mode in self._build_targets(config):
            try:
                self._start_stream(adb_device=adb_device, sensor_idx=sensor_idx, sensor_mode=sensor_mode)
            except Exception as error:  # noqa: BLE001
                lines.append(
                    f"[{timestamp}] serial={adb_device} sensor_idx={sensor_idx} "
                    f"sensor_mode={sensor_mode} START_STREAM FAIL: {error}"
                )
                continue

            lines.append(
                f"[{timestamp}] serial={adb_device} sensor_idx={sensor_idx} "
                f"sensor_mode={sensor_mode} START_STREAM SUCCESS"
            )
        return "\n".join(lines)

    def stop_stream_debug(self, config: AppConfig) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S")
        adb_device = config.adb_device
        if not adb_device:
            return f"[{timestamp}] No adb device selected."

        lines: list[str] = []
        for sensor_idx, sensor_mode in self._build_targets(config):
            try:
                self._stop_stream(adb_device=adb_device)
            except Exception as error:  # noqa: BLE001
                lines.append(
                    f"[{timestamp}] serial={adb_device} sensor_idx={sensor_idx} "
                    f"sensor_mode={sensor_mode} STOP_STREAM FAIL: {error}"
                )
                continue

            lines.append(
                f"[{timestamp}] serial={adb_device} sensor_idx={sensor_idx} "
                f"sensor_mode={sensor_mode} STOP_STREAM SUCCESS"
            )
        return "\n".join(lines)

    def _start_stream(self, *, adb_device: str, sensor_idx: int, sensor_mode: int) -> None:
        sentest_path = self._SENTEST_LOCAL_PATH
        if not sentest_path.exists():
            raise RuntimeError(f"Missing stream tool: {sentest_path}")

        if not self._remote_tool_exists(adb_device=adb_device):
            push_cmd = ["adb", "-s", adb_device, "push", str(sentest_path), self._SENTEST_REMOTE_PATH]
            push_result = subprocess.run(
                push_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._ADB_SHORT_TIMEOUT_SECONDS,
            )
            if push_result.returncode != 0:
                output = (push_result.stdout or "") + (push_result.stderr or "")
                raise RuntimeError(f"Push sentest_v4l2 failed: {output.strip()}")

        chmod_cmd = ["adb", "-s", adb_device, "shell", f"chmod 755 {self._SENTEST_REMOTE_PATH}"]
        subprocess.run(
            chmod_cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=self._ADB_SHORT_TIMEOUT_SECONDS,
        )

        errors: list[str] = []
        for stream_cmd in self._build_stream_commands(
            adb_device=adb_device,
            sensor_idx=sensor_idx,
            sensor_mode=sensor_mode,
        ):
            try:
                result = subprocess.run(
                    stream_cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self._ADB_SHORT_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                # Some sentest variants keep running in foreground after startup.
                # A timeout here generally means stream has started and command did not return.
                return
            if result.returncode == 0:
                return
            output = ((result.stdout or "") + (result.stderr or "")).strip()
            errors.append(f"{' '.join(stream_cmd)} -> {output}")

        raise RuntimeError(
            "Start stream failed: sentest_v4l2 command returned non-zero. "
            + " | ".join(errors)
        )

    def _remote_tool_exists(self, *, adb_device: str) -> bool:
        check_cmd = [
            "adb",
            "-s",
            adb_device,
            "shell",
            f"if [ -f {self._SENTEST_REMOTE_PATH} ]; then echo __EXISTS__; fi",
        ]
        result = subprocess.run(check_cmd, check=False, capture_output=True, text=True)
        return result.returncode == 0 and "__EXISTS__" in (result.stdout or "")

    def _stop_stream(self, *, adb_device: str) -> None:
        stop_commands = [
            ["adb", "-s", adb_device, "shell", f"{self._SENTEST_REMOTE_PATH} --stop-stream"],
            ["adb", "-s", adb_device, "shell", f"{self._SENTEST_REMOTE_PATH} --stop"],
            ["adb", "-s", adb_device, "shell", f"pkill -f {self._SENTEST_REMOTE_PATH}"],
        ]
        for stop_cmd in stop_commands:
            try:
                subprocess.run(
                    stop_cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self._ADB_STOP_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                continue

    def _build_stream_commands(self, *, adb_device: str, sensor_idx: int, sensor_mode: int) -> list[list[str]]:
        return [
            [
                "adb",
                "-s",
                adb_device,
                "shell",
                (
                    f"nohup {self._SENTEST_REMOTE_PATH} "
                    f"--sensor-idx {sensor_idx} --sensor-mode {sensor_mode} --start-stream "
                    ">/dev/null 2>&1 &"
                ),
            ],
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

    def run_automated_test(
        self,
        config: AppConfig,
        step_text: str = "",
        progress_callback: Callable[[str], None] | None = None,
        should_stop_callback: Callable[[], bool] | None = None,
    ) -> str:
        display_steps = self._parse_auto_steps(step_text)
        steps = self._execution_steps(display_steps)
        estimated_cases = self.estimate_auto_cases(config, step_text)
        self._emit_progress(
            progress_callback,
            (
                "自动化任务已创建："
                f"steps={', '.join(display_steps)}；"
                f"预计组合数={estimated_cases}。"
            ),
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("configs") / "auto_test_outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        if set(steps) == {"cdr delay", "eq offset"} and len(steps) == 2:
            cdr_path = output_dir / f"cdr_delay_{timestamp}.txt"
            eq_path = output_dir / f"eq_offset_{timestamp}.txt"
            self._run_single_param_sweep("cdr delay", config, cdr_path, progress_callback, should_stop_callback)
            self._run_single_param_sweep("eq offset", config, eq_path, progress_callback, should_stop_callback)
            return (
                "自动化测试完成。\n"
                f"cdr delay 输出文件: {cdr_path}\n"
                f"eq offset 输出文件: {eq_path}"
            )

        csv_path = output_dir / f"multi_param_{timestamp}.csv"
        row_count = self._run_multi_param_sweep(steps, config, csv_path, progress_callback, should_stop_callback)
        return f"自动化测试完成。共 {row_count} 行，CSV 输出: {csv_path}"

    def estimate_auto_cases(self, config: AppConfig, step_text: str = "") -> int:
        steps = self._execution_steps(self._parse_auto_steps(step_text))
        candidates = [self._step_candidates(step, config) for step in steps]
        target_count = len(self._build_targets(config))
        total = 1
        for values in candidates:
            total *= len(values)
        return total * target_count

    def _parse_auto_steps(self, step_text: str) -> list[str]:
        if not step_text.strip():
            return list(self._DEFAULT_AUTO_STEPS)
        parts = [part.strip().lower() for part in step_text.replace(";", ",").split(",")]
        valid_steps = {*self._STEP_REGISTER_MAP, *self._NON_EYE_STEPS}
        steps: list[str] = []
        seen: set[str] = set()
        for part in parts:
            if part not in valid_steps or part in seen:
                continue
            seen.add(part)
            steps.append(part)
        return steps or list(self._DEFAULT_AUTO_STEPS)

    @staticmethod
    def _execution_steps(steps: list[str]) -> list[str]:
        """Keep user-specified step order while filtering duplicates and non-register steps."""
        seen: set[str] = set()
        ordered: list[str] = []
        for step in steps:
            if step in seen or step in CommandProcessor._NON_EYE_STEPS:
                continue
            seen.add(step)
            ordered.append(step)
        return ordered

    def _run_single_param_sweep(
        self,
        step: str,
        config: AppConfig,
        output_path: Path,
        progress_callback: Callable[[str], None] | None,
        should_stop_callback: Callable[[], bool] | None,
    ) -> None:
        values = self._step_candidates(step, config)
        targets = self._build_targets(config)
        total = max(len(values), 1) * max(len(targets), 1)
        with output_path.open("w", encoding="utf-8") as handle:
            index = 0
            for sensor_idx, sensor_mode in targets:
                run_config = self._config_with_target(config, sensor_idx=sensor_idx, sensor_mode=sensor_mode)
                self._start_stream_for_config(run_config)
                applied_value: int | None = None
                for value in values:
                    if self._should_stop(should_stop_callback):
                        self._emit_progress(progress_callback, "收到停止请求，终止当前自动化任务。")
                        return
                    index += 1
                    self._emit_progress(
                        progress_callback,
                        f"[{index}/{total}] 执行 sensor idx={sensor_idx}, sensor mode={sensor_mode}, {step}={value}",
                    )
                    if applied_value == value:
                        self._emit_progress(
                            progress_callback,
                            f"[{index}/{total}] 跳过未变化参数 step={step} value={value}",
                        )
                        continue
                    run_config = self._config_with_step_value(run_config, step, value)
                    self._emit_progress(
                        progress_callback,
                        f"[{index}/{total}] 准备执行命令 step={step} value={value}",
                    )
                    start_ts = time.perf_counter()
                    result = self.send(step, run_config, start_stream=False)
                    elapsed = time.perf_counter() - start_ts
                    self._emit_progress(
                        progress_callback,
                        f"[{index}/{total}] 完成 step={step} value={value} 用时={elapsed:.2f}s",
                    )
                    applied_value = value
                    handle.write(f"sensor idx={sensor_idx} sensor mode={sensor_mode} {step}={value}\n{result}\n\n")

    def _run_multi_param_sweep(
        self,
        steps: list[str],
        config: AppConfig,
        csv_path: Path,
        progress_callback: Callable[[str], None] | None,
        should_stop_callback: Callable[[], bool] | None,
    ) -> int:
        candidates = [self._step_candidates(step, config) for step in steps]
        targets = self._build_targets(config)
        header = ["sensor idx", "sensor mode", *steps, "final_result"]
        count = 0
        total = max(len(targets), 1)
        for values in candidates:
            total *= len(values)

        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            index = 0
            for sensor_idx, sensor_mode in targets:
                run_config = self._config_with_target(config, sensor_idx=sensor_idx, sensor_mode=sensor_mode)
                self._start_stream_for_config(run_config)
                applied_values: dict[str, int] = {}
                for values in product(*candidates):
                    if self._should_stop(should_stop_callback):
                        self._emit_progress(progress_callback, "收到停止请求，终止当前自动化任务。")
                        return count
                    index += 1
                    progress_detail = ", ".join(f"{step}={value}" for step, value in zip(steps, values))
                    self._emit_progress(
                        progress_callback,
                        f"[{index}/{total}] 执行 sensor idx={sensor_idx}, sensor mode={sensor_mode}, {progress_detail}",
                    )
                    final_result = ""
                    for step, value in zip(steps, values):
                        if self._should_stop(should_stop_callback):
                            self._emit_progress(progress_callback, "收到停止请求，终止当前自动化任务。")
                            return count
                        if applied_values.get(step) == value:
                            self._emit_progress(
                                progress_callback,
                                f"[{index}/{total}] 跳过未变化参数 step={step} value={value}",
                            )
                            continue
                        run_config = self._config_with_step_value(run_config, step, value)
                        self._emit_progress(
                            progress_callback,
                            f"[{index}/{total}] 开始执行子步骤 step={step} value={value}",
                        )
                        start_ts = time.perf_counter()
                        final_result = self.send(step, run_config, start_stream=False)
                        elapsed = time.perf_counter() - start_ts
                        self._emit_progress(
                            progress_callback,
                            f"[{index}/{total}] 子步骤完成 step={step} value={value} 用时={elapsed:.2f}s",
                        )
                        applied_values[step] = value
                    writer.writerow([sensor_idx, sensor_mode, *values, final_result])
                    count += 1
        return count

    def _start_stream_for_config(self, config: AppConfig) -> None:
        adb_device = config.adb_device
        if not adb_device:
            raise RuntimeError("No adb device selected.")
        sensor_mode = config.sensor_mode[0] if config.sensor_mode else 0
        self._start_stream(adb_device=adb_device, sensor_idx=config.sensor_idx, sensor_mode=sensor_mode)


    @staticmethod
    def _should_stop(should_stop_callback: Callable[[], bool] | None) -> bool:
        if should_stop_callback is None:
            return False
        return should_stop_callback()

    @staticmethod
    def _emit_progress(progress_callback: Callable[[str], None] | None, message: str) -> None:
        if progress_callback is not None:
            progress_callback(message)

    def _step_candidates(self, step: str, config: AppConfig) -> list[int]:
        if step == "cdr delay":
            cdr_max = 254 if config.is_dphy else 31
            return self._inclusive_range(
                start=config.auto_cdr_delay_start,
                end=config.auto_cdr_delay_end,
                minimum=0,
                maximum=cdr_max,
            )
        if step == "eq offset":
            return self._inclusive_range(
                start=config.auto_eq_offset_start,
                end=config.auto_eq_offset_end,
                minimum=-31,
                maximum=31,
            )
        if step == "eq dg0 enable":
            values = config.auto_eq_dg0_enable_values
            return values or [0, 1]
        if step == "eq sr0":
            return self._inclusive_range(
                start=config.auto_eq_sr0_start,
                end=config.auto_eq_sr0_end,
                minimum=0,
                maximum=15,
            )
        if step == "eq dg1 enable":
            values = config.auto_eq_dg1_enable_values
            return values or [0, 1]
        if step == "eq sr1":
            return self._inclusive_range(
                start=config.auto_eq_sr1_start,
                end=config.auto_eq_sr1_end,
                minimum=0,
                maximum=15,
            )
        if step == "eq bw":
            values = config.auto_eq_bw_values
            return values or [0, 1, 2, 3]
        return [0]

    @staticmethod
    def _inclusive_range(*, start: int, end: int, minimum: int, maximum: int) -> list[int]:
        bounded_start = min(max(start, minimum), maximum)
        bounded_end = min(max(end, minimum), maximum)
        lower, upper = sorted((bounded_start, bounded_end))
        return list(range(lower, upper + 1))

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

    def _config_with_target(self, config: AppConfig, *, sensor_idx: int, sensor_mode: int) -> AppConfig:
        return AppConfig(
            mode="manual",
            adb_device=config.adb_device,
            is_dphy=config.is_dphy,
            sensor_idx=sensor_idx,
            auto_sensor_idx=[sensor_idx],
            sensor_mode=[sensor_mode],
            cdr_delay_start=config.cdr_delay_start,
            eq_offset=config.eq_offset,
            eq_dg0_enable=config.eq_dg0_enable,
            eq_sr0=config.eq_sr0,
            eq_dg1_enable=config.eq_dg1_enable,
            eq_sr1=config.eq_sr1,
            eq_bw=config.eq_bw,
            auto_cdr_delay_start=config.auto_cdr_delay_start,
            auto_cdr_delay_end=config.auto_cdr_delay_end,
            auto_eq_offset_start=config.auto_eq_offset_start,
            auto_eq_offset_end=config.auto_eq_offset_end,
            auto_eq_dg0_enable_values=config.auto_eq_dg0_enable_values,
            auto_eq_sr0_start=config.auto_eq_sr0_start,
            auto_eq_sr0_end=config.auto_eq_sr0_end,
            auto_eq_dg1_enable_values=config.auto_eq_dg1_enable_values,
            auto_eq_sr1_start=config.auto_eq_sr1_start,
            auto_eq_sr1_end=config.auto_eq_sr1_end,
            auto_eq_bw_values=config.auto_eq_bw_values,
        )

    def _build_targets(self, config: AppConfig) -> list[tuple[int, int]]:
        if config.mode != "auto":
            sensor_mode = config.sensor_mode[0] if config.sensor_mode else 0
            return [(config.sensor_idx, sensor_mode)]

        sensor_modes = config.sensor_mode or [0, 1, 2]
        sensor_indexes = config.auto_sensor_idx or list(self._AUTO_SENSOR_INDEXES)
        return [
            (sensor_idx, sensor_mode)
            for sensor_idx in sensor_indexes
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
