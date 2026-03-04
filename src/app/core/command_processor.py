from __future__ import annotations

from datetime import datetime

from .config_manager import AppConfig


class CommandProcessor:
    """Simple command handler for debug interactions."""

    def send(self, command: str, config: AppConfig) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S")
        return (
            f"[{timestamp}] command='{command}' "
            f"sensor_idx={config.sensor_idx} "
            f"sensor_mode={config.sensor_mode} "
            f"phy_mode={config.phy_mode}"
        )
