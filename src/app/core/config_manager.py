from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json


@dataclass
class AppConfig:
    sensor_idx: int = 0
    sensor_mode: str = "normal"
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
            sensor_idx=int(raw_data.get("sensor_idx", 0)),
            sensor_mode=str(raw_data.get("sensor_mode", "normal")),
            phy_mode=str(raw_data.get("phy_mode", "auto")),
        )

    def save(self, config: AppConfig) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(config)
        self.config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
