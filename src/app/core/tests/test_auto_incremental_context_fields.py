from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.command_processor import CommandProcessor
from app.core.config_manager import AppConfig, ConfigManager


class AutoIncrementalContextFieldsTest(unittest.TestCase):
    def test_parse_incremental_context_requires_complete_fields(self) -> None:
        config = AppConfig(auto_project_name="p", auto_band="n78", auto_frequency="", auto_power="10")
        self.assertIsNone(CommandProcessor._parse_incremental_context(config))

    def test_parse_incremental_context_accepts_valid_values(self) -> None:
        config = AppConfig(auto_project_name="p", auto_band="n78", auto_frequency="3500", auto_power="10.5")
        parsed = CommandProcessor._parse_incremental_context(config)
        self.assertIsNotNone(parsed)
        context, power = parsed  # type: ignore[misc]
        self.assertEqual(context.project_name, "p")
        self.assertEqual(context.band, "n78")
        self.assertEqual(context.frequency, "3500")
        self.assertEqual(power, 10.5)

    def test_config_manager_persists_incremental_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "default.yaml"
            manager = ConfigManager(config_path)
            manager.save(
                AppConfig(
                    mode="auto",
                    auto_project_name="project-a",
                    auto_band="n41",
                    auto_frequency="2570",
                    auto_power="18",
                )
            )
            loaded = manager.load()
            self.assertEqual(loaded.auto_project_name, "project-a")
            self.assertEqual(loaded.auto_band, "n41")
            self.assertEqual(loaded.auto_frequency, "2570")
            self.assertEqual(loaded.auto_power, "18")

    def test_config_manager_persists_auto_context_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "default.yaml"
            manager = ConfigManager(config_path)
            manager.save(
                AppConfig(
                    mode="auto",
                    auto_context_history=[
                        {"project_name": "p1", "band": "n78", "frequency": "3500", "power": "10"},
                        {"project_name": "p2", "band": "n41", "frequency": "2600", "power": "12"},
                    ],
                )
            )
            loaded = manager.load()
            self.assertEqual(
                loaded.auto_context_history,
                [
                    {"project_name": "p1", "band": "n78", "frequency": "3500", "power": "10"},
                    {"project_name": "p2", "band": "n41", "frequency": "2600", "power": "12"},
                ],
            )

    def test_config_manager_filters_invalid_auto_context_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "default.yaml"
            config_path.write_text(
                """
{
  "mode": "auto",
  "auto_context_history": [
    {"project_name": "p1", "band": "n78", "frequency": "3500", "power": "10"},
    {"project_name": "", "band": "n78", "frequency": "3500", "power": "10"},
    {"project_name": "p1", "band": "n78", "frequency": "3500", "power": "10"}
  ]
}
""".strip(),
                encoding="utf-8",
            )
            manager = ConfigManager(config_path)
            loaded = manager.load()
            self.assertEqual(
                loaded.auto_context_history,
                [{"project_name": "p1", "band": "n78", "frequency": "3500", "power": "10"}],
            )


if __name__ == "__main__":
    unittest.main()
