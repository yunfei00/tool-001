from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json


@dataclass
class AppConfig:
    mode: str = "manual"
    adb_device: str | None = None
    is_dphy: bool = False
    sensor_idx: int = 1
    auto_sensor_idx: list[int] | None = None
    sensor_mode: list[int] | None = None
    cdr_delay_start: int = 0
    eq_offset: int = 0
    eq_dg0_enable: int = 0
    eq_sr0: int = 0
    eq_dg1_enable: int = 0
    eq_sr1: int = 0
    eq_bw: int = 0
    auto_cdr_delay_start: int = 0
    auto_cdr_delay_end: int = 31
    auto_eq_offset_start: int = -31
    auto_eq_offset_end: int = 31
    auto_eq_dg0_enable_start: int = 0
    auto_eq_dg0_enable_end: int = 1
    auto_eq_dg0_enable_values: list[int] | None = None
    auto_eq_sr0_start: int = 0
    auto_eq_sr0_end: int = 15
    auto_eq_dg1_enable_start: int = 0
    auto_eq_dg1_enable_end: int = 1
    auto_eq_dg1_enable_values: list[int] | None = None
    auto_eq_sr1_start: int = 0
    auto_eq_sr1_end: int = 15
    auto_eq_bw_start: int = 0
    auto_eq_bw_end: int = 3
    auto_eq_bw_values: list[int] | None = None
    auto_manual_stream: bool = False
    auto_loop_count: int = 1
    auto_project_name: str = ""
    auto_band: str = ""
    auto_frequency: str = ""
    auto_power: str = ""
    auto_context_history: list[dict[str, str]] | None = None


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
        normalized_mode = self._normalize_mode(mode)
        is_dphy = self._normalize_is_dphy(raw_data.get("is_dphy"))
        return AppConfig(
            mode=normalized_mode,
            adb_device=self._normalize_adb_device(raw_data.get("adb_device")),
            is_dphy=is_dphy,
            sensor_idx=self._normalize_sensor_idx(raw_data.get("sensor_idx")),
            auto_sensor_idx=self._normalize_sensor_indexes(raw_data.get("auto_sensor_idx")),
            sensor_mode=self._normalize_sensor_modes(raw_data.get("sensor_mode")),
            cdr_delay_start=self._normalize_cdr_delay_start(raw_data.get("cdr_delay_start"), is_dphy),
            eq_offset=self._normalize_integer(raw_data.get("eq_offset"), minimum=-31, maximum=31, default=0),
            eq_dg0_enable=self._normalize_integer(raw_data.get("eq_dg0_enable"), minimum=0, maximum=1, default=0),
            eq_sr0=self._normalize_integer(raw_data.get("eq_sr0"), minimum=0, maximum=15, default=0),
            eq_dg1_enable=self._normalize_integer(raw_data.get("eq_dg1_enable"), minimum=0, maximum=1, default=0),
            eq_sr1=self._normalize_integer(raw_data.get("eq_sr1"), minimum=0, maximum=15, default=0),
            eq_bw=self._normalize_integer(raw_data.get("eq_bw"), minimum=0, maximum=3, default=0),
            auto_cdr_delay_start=self._normalize_cdr_delay_start(raw_data.get("auto_cdr_delay_start"), is_dphy),
            auto_cdr_delay_end=self._normalize_cdr_delay_start(
                raw_data.get("auto_cdr_delay_end", 254 if is_dphy else 31),
                is_dphy,
            ),
            auto_eq_offset_start=self._normalize_integer(
                raw_data.get("auto_eq_offset_start"), minimum=-31, maximum=31, default=-31
            ),
            auto_eq_offset_end=self._normalize_integer(
                raw_data.get("auto_eq_offset_end"), minimum=-31, maximum=31, default=31
            ),
            auto_eq_dg0_enable_start=self._normalize_integer(
                raw_data.get("auto_eq_dg0_enable_start"), minimum=0, maximum=1, default=0
            ),
            auto_eq_dg0_enable_end=self._normalize_integer(
                raw_data.get("auto_eq_dg0_enable_end"), minimum=0, maximum=1, default=1
            ),
            auto_eq_dg0_enable_values=self._normalize_integer_list(
                raw_data.get("auto_eq_dg0_enable_values"), allowed={0, 1}
            ),
            auto_eq_sr0_start=self._normalize_integer(
                raw_data.get("auto_eq_sr0_start"), minimum=0, maximum=15, default=0
            ),
            auto_eq_sr0_end=self._normalize_integer(
                raw_data.get("auto_eq_sr0_end"), minimum=0, maximum=15, default=15
            ),
            auto_eq_dg1_enable_start=self._normalize_integer(
                raw_data.get("auto_eq_dg1_enable_start"), minimum=0, maximum=1, default=0
            ),
            auto_eq_dg1_enable_end=self._normalize_integer(
                raw_data.get("auto_eq_dg1_enable_end"), minimum=0, maximum=1, default=1
            ),
            auto_eq_dg1_enable_values=self._normalize_integer_list(
                raw_data.get("auto_eq_dg1_enable_values"), allowed={0, 1}
            ),
            auto_eq_sr1_start=self._normalize_integer(
                raw_data.get("auto_eq_sr1_start"), minimum=0, maximum=15, default=0
            ),
            auto_eq_sr1_end=self._normalize_integer(
                raw_data.get("auto_eq_sr1_end"), minimum=0, maximum=15, default=15
            ),
            auto_eq_bw_start=self._normalize_integer(
                raw_data.get("auto_eq_bw_start"), minimum=0, maximum=3, default=0
            ),
            auto_eq_bw_end=self._normalize_integer(
                raw_data.get("auto_eq_bw_end"), minimum=0, maximum=3, default=3
            ),
            auto_eq_bw_values=self._normalize_integer_list(
                raw_data.get("auto_eq_bw_values"), allowed={0, 1, 2, 3}
            ),
            auto_manual_stream=self._normalize_is_dphy(raw_data.get("auto_manual_stream")),
            auto_loop_count=self._normalize_integer(raw_data.get("auto_loop_count"), minimum=1, maximum=9999, default=1),
            auto_project_name=self._normalize_text(raw_data.get("auto_project_name")),
            auto_band=self._normalize_text(raw_data.get("auto_band")),
            auto_frequency=self._normalize_text(raw_data.get("auto_frequency")),
            auto_power=self._normalize_text(raw_data.get("auto_power")),
            auto_context_history=self._normalize_auto_context_history(raw_data.get("auto_context_history")),
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

    @classmethod
    def _normalize_sensor_indexes(cls, raw_sensor_indexes: object) -> list[int] | None:
        return cls._normalize_integer_list(raw_sensor_indexes, allowed=set(cls._SENSOR_INDEXES))

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
    def _normalize_integer_list(raw_values: object, *, allowed: set[int]) -> list[int] | None:
        if raw_values is None:
            return None
        if isinstance(raw_values, list):
            values = raw_values
        else:
            values = [raw_values]

        normalized: list[int] = []
        for value in values:
            try:
                integer_value = int(value)
            except (TypeError, ValueError):
                continue
            if integer_value in allowed:
                normalized.append(integer_value)
        if not normalized:
            return None
        return sorted(set(normalized))

    @staticmethod
    def _normalize_cdr_delay_start(raw_cdr_delay_start: object, is_dphy: bool) -> int:
        try:
            cdr_delay_start = int(raw_cdr_delay_start)
        except (TypeError, ValueError):
            return 0

        maximum = 254 if is_dphy else 31
        return min(max(cdr_delay_start, 0), maximum)

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        if mode in {"manual", "auto"}:
            return mode
        if mode == "dify":
            return "auto"
        return "manual"

    @staticmethod
    def _normalize_is_dphy(raw_is_dphy: object) -> bool:
        if isinstance(raw_is_dphy, bool):
            return raw_is_dphy
        if raw_is_dphy is None:
            return False
        if isinstance(raw_is_dphy, str):
            return raw_is_dphy.strip().lower() in {"1", "true", "yes", "on"}
        try:
            return bool(int(raw_is_dphy))
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _normalize_integer(raw_value: object, *, minimum: int, maximum: int, default: int) -> int:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return default
        return min(max(value, minimum), maximum)

    @staticmethod
    def _normalize_text(raw_value: object) -> str:
        if raw_value is None:
            return ""
        return str(raw_value).strip()

    @classmethod
    def _normalize_auto_context_history(cls, raw_history: object) -> list[dict[str, str]] | None:
        if not isinstance(raw_history, list):
            return None

        normalized: list[dict[str, str]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for item in raw_history:
            if not isinstance(item, dict):
                continue
            project_name = cls._normalize_text(item.get("project_name"))
            band = cls._normalize_text(item.get("band"))
            frequency = cls._normalize_text(item.get("frequency"))
            power = cls._normalize_text(item.get("power"))
            if not all((project_name, band, frequency, power)):
                continue
            key = (project_name, band, frequency, power)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "project_name": project_name,
                    "band": band,
                    "frequency": frequency,
                    "power": power,
                }
            )
        return normalized or None
