from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json


@dataclass
class AppConfig:
    mode: str = "manual"
    sensor_idx: int = 0
    sensor_mode: list[int] | None = None
    phy_mode: str = "auto"


class ConfigManager:
    """Load and save application configuration from a YAML-compatible JSON file."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def load(self) -> AppConfig:
        if not self.config_path.exists():
            return AppConfig()

        raw_data = json.loads(self.config_path.read_text(encoding="utf-8"))
        return AppConfig(
            mode=str(raw_data.get("mode", "manual")),
            sensor_idx=int(raw_data.get("sensor_idx", 0)),
            sensor_mode=self._normalize_sensor_modes(raw_data.get("sensor_mode")),
            phy_mode=str(raw_data.get("phy_mode", "auto")),
        )

    def save(self, config: AppConfig) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(config)
        if config.mode == "manual":
            payload.pop("sensor_mode", None)
        self.config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _normalize_sensor_modes(raw_sensor_mode: object) -> list[int] | None:
        if raw_sensor_mode is None:
            return None

        if isinstance(raw_sensor_mode, list):
            values = raw_sensor_mode
        else:
            values = [raw_sensor_mode]

        normalized = []
        for value in values:
            try:
                mode = int(value)
            except (TypeError, ValueError):
                continue
            if mode in (0, 1, 2):
                normalized.append(mode)

        if not normalized:
            return None

        return sorted(set(normalized))
