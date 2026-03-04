from __future__ import annotations

from datetime import datetime

from .config_manager import AppConfig


class CommandProcessor:
    """Simple command handler for debug interactions."""

    _AUTO_SENSOR_INDEXES = (1, 2, 4, 8, 16)

    def send(self, command: str, config: AppConfig) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S")

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
            return f"[{timestamp}] auto command='{command}' combinations={combo_text} phy_mode={config.phy_mode}"

        return (
            f"[{timestamp}] manual command='{command}' "
            f"sensor_idx={config.sensor_idx} "
            f"phy_mode={config.phy_mode}"
        )

    @staticmethod
    def _map_dts_idx(sensor_idx: int) -> int:
        return sensor_idx.bit_length() - 1
