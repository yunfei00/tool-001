from __future__ import annotations

from datetime import datetime

from .config_manager import AppConfig


class CommandProcessor:
    """Simple command handler for debug interactions."""

    _AUTO_SENSOR_INDEXES = (1, 2, 4, 8, 16)

    def send(self, command: str, config: AppConfig) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S")

        adb_device_text = config.adb_device or "not-selected"

        if config.mode == "auto":
            sensor_modes = config.sensor_mode or [0, 1, 2]
            combinations = []
            for sensor_idx in self._AUTO_SENSOR_INDEXES:
                dts_idx = self._map_dts_idx(sensor_idx)
                for sensor_mode in sensor_modes:
                    combinations.append(
                        f"(sensor_idx={sensor_idx}, sensor_mode={sensor_mode}, dts_idx={dts_idx})"
                    )
            combo_text = ", ".join(combinations)
            return (
                f"[{timestamp}] auto command='{command}' adb_device={adb_device_text} combinations={combo_text} "
                f"cdr_delay_start={config.cdr_delay_start} "
                f"eq_offset={config.eq_offset} "
                f"eq_dg0_enable={config.eq_dg0_enable} "
                f"eq_sr0={config.eq_sr0} "
                f"eq_dg1_enable={config.eq_dg1_enable} "
                f"eq_sr1={config.eq_sr1} "
                f"eq_bw={config.eq_bw} "
                f"phy_mode={config.phy_mode}"
            )

        return (
            f"[{timestamp}] {config.mode} command='{command}' adb_device={adb_device_text} "
            f"sensor_idx={config.sensor_idx} "
            f"cdr_delay_start={config.cdr_delay_start} "
            f"eq_offset={config.eq_offset} "
            f"eq_dg0_enable={config.eq_dg0_enable} "
            f"eq_sr0={config.eq_sr0} "
            f"eq_dg1_enable={config.eq_dg1_enable} "
            f"eq_sr1={config.eq_sr1} "
            f"eq_bw={config.eq_bw} "
            f"phy_mode={config.phy_mode}"
        )

    @staticmethod
    def _map_dts_idx(sensor_idx: int) -> int:
        return sensor_idx.bit_length() - 1
