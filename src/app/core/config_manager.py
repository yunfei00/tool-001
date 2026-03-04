from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json


@dataclass
class AppConfig:
    mode: str = "manual"
    adb_device: str | None = None
    sensor_idx: int = 1
    sensor_mode: list[int] | None = None
    cdr_delay_start: int = 0
    eq_offset: int = 0
    eq_dg0_enable: int = 0
    eq_sr0: int = 0
    eq_dg1_enable: int = 0
    eq_sr1: int = 0
    eq_bw: int = 0
    phy_mode: str = "auto"


class ConfigManager:
    """Load and save application configuration from a YAML-compatible JSON file."""

    _SENSOR_INDEXES = (1, 2, 4, 8, 16)

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def load(self) -> AppConfig:
        if not self.config_path.exists():
            return AppConfig()

        raw_data = json.loads(self.config_path.read_text(encoding="utf-8"))
        mode = str(raw_data.get("mode", "manual"))
        return AppConfig(
            mode=mode,
            adb_device=self._normalize_adb_device(raw_data.get("adb_device")),
            sensor_idx=self._normalize_sensor_idx(raw_data.get("sensor_idx")),
            sensor_mode=self._normalize_sensor_modes(raw_data.get("sensor_mode")),
            cdr_delay_start=self._normalize_cdr_delay_start(raw_data.get("cdr_delay_start"), mode),
            eq_offset=self._normalize_integer(raw_data.get("eq_offset"), minimum=-31, maximum=31, default=0),
            eq_dg0_enable=self._normalize_integer(raw_data.get("eq_dg0_enable"), minimum=0, maximum=1, default=0),
            eq_sr0=self._normalize_integer(raw_data.get("eq_sr0"), minimum=0, maximum=15, default=0),
            eq_dg1_enable=self._normalize_integer(raw_data.get("eq_dg1_enable"), minimum=0, maximum=1, default=0),
            eq_sr1=self._normalize_integer(raw_data.get("eq_sr1"), minimum=0, maximum=15, default=0),
            eq_bw=self._normalize_integer(raw_data.get("eq_bw"), minimum=0, maximum=3, default=0),
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

    @classmethod
    def _normalize_sensor_idx(cls, raw_sensor_idx: object) -> int:
        try:
            sensor_idx = int(raw_sensor_idx)
        except (TypeError, ValueError):
            return 1
        if sensor_idx in cls._SENSOR_INDEXES:
            return sensor_idx
        return 1

    @staticmethod
    def _normalize_adb_device(raw_adb_device: object) -> str | None:
        if raw_adb_device is None:
            return None
        adb_device = str(raw_adb_device).strip()
        return adb_device or None

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

    @staticmethod
    def _normalize_cdr_delay_start(raw_cdr_delay_start: object, mode: str) -> int:
        try:
            cdr_delay_start = int(raw_cdr_delay_start)
        except (TypeError, ValueError):
            return 0

        maximum = 254 if mode == "dify" else 31
        return min(max(cdr_delay_start, 0), maximum)

    @staticmethod
    def _normalize_integer(raw_value: object, *, minimum: int, maximum: int, default: int) -> int:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return default
        return min(max(value, minimum), maximum)
