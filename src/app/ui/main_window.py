from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.command_processor import CommandProcessor
from ..core.config_manager import AppConfig, ConfigManager


class MainWindow(QMainWindow):
    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("tool-001")
        self.resize(760, 520)

        self._config_manager = ConfigManager(config_path)
        self._command_processor = CommandProcessor()

        self._mode = QComboBox()
        self._mode.addItems(["manual", "auto"])

        self._sensor_idx = QSpinBox()
        self._sensor_idx.setRange(0, 255)

        self._sensor_mode = QLineEdit()
        self._sensor_mode.setPlaceholderText("0,1,2")

        self._phy_mode = QComboBox()
        self._phy_mode.addItems(["auto", "master", "slave"])

        self._command_input = QLineEdit()
        self._command_input.setPlaceholderText("Enter debug command...")

        self._send_button = QPushButton("Send")
        self._load_button = QPushButton("Load Config")
        self._save_button = QPushButton("Save Config")

        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)

        self._build_ui()
        self._bind_events()
        self.load_config()

    def _build_ui(self) -> None:
        config_group = QGroupBox("Configuration")
        self._config_form = QFormLayout()
        self._config_form.addRow("Mode", self._mode)
        self._config_form.addRow("Sensor idx", self._sensor_idx)
        self._sensor_mode_label = "Sensor mode"
        self._config_form.addRow(self._sensor_mode_label, self._sensor_mode)
        self._config_form.addRow("Phy mode", self._phy_mode)
        config_group.setLayout(self._config_form)

        config_actions_layout = QHBoxLayout()
        config_actions_layout.addWidget(self._load_button)
        config_actions_layout.addWidget(self._save_button)
        config_actions_layout.addStretch(1)

        command_group = QGroupBox("Command Debug")
        command_layout = QHBoxLayout()
        command_layout.addWidget(self._command_input)
        command_layout.addWidget(self._send_button)
        command_group.setLayout(command_layout)

        log_group = QGroupBox("Log Output")
        log_layout = QVBoxLayout()
        log_layout.addWidget(self._log_output)
        log_group.setLayout(log_layout)

        root_layout = QVBoxLayout()
        root_layout.addWidget(config_group)
        root_layout.addLayout(config_actions_layout)
        root_layout.addWidget(command_group)
        root_layout.addWidget(log_group, stretch=1)

        container = QWidget()
        container.setLayout(root_layout)
        self.setCentralWidget(container)

    def _bind_events(self) -> None:
        self._mode.currentTextChanged.connect(self._update_mode_visibility)
        self._load_button.clicked.connect(self.load_config)
        self._save_button.clicked.connect(self.save_config)
        self._send_button.clicked.connect(self.send_command)
        self._command_input.returnPressed.connect(self.send_command)

    def _collect_config(self) -> AppConfig:
        selected_mode = self._mode.currentText()
        sensor_modes = self._parse_sensor_modes() if selected_mode == "auto" else None
        return AppConfig(
            mode=selected_mode,
            sensor_idx=self._sensor_idx.value(),
            sensor_mode=sensor_modes,
            phy_mode=self._phy_mode.currentText(),
        )

    def _apply_config(self, config: AppConfig) -> None:
        self._mode.setCurrentText(config.mode if config.mode in {"manual", "auto"} else "manual")
        self._sensor_idx.setValue(config.sensor_idx)
        if config.sensor_mode:
            self._sensor_mode.setText(",".join(str(mode) for mode in config.sensor_mode))
        else:
            self._sensor_mode.clear()
        self._phy_mode.setCurrentText(config.phy_mode)
        self._update_mode_visibility(self._mode.currentText())

    def _parse_sensor_modes(self) -> list[int]:
        text = self._sensor_mode.text().strip()
        if not text:
            return [0, 1, 2]

        parsed = []
        for token in text.split(","):
            token = token.strip()
            if not token:
                continue
            if token in {"0", "1", "2"}:
                parsed.append(int(token))
        if not parsed:
            return [0, 1, 2]
        return sorted(set(parsed))

    def _update_mode_visibility(self, mode: str) -> None:
        is_auto_mode = mode == "auto"
        self._sensor_mode.setVisible(is_auto_mode)
        sensor_mode_label = self._config_form.labelForField(self._sensor_mode)
        if sensor_mode_label is not None:
            sensor_mode_label.setVisible(is_auto_mode)

    def _append_log(self, message: str) -> None:
        self._log_output.append(message)

    def load_config(self) -> None:
        config = self._config_manager.load()
        self._apply_config(config)
        self._append_log(f"Loaded config from {self._config_manager.config_path}")

    def save_config(self) -> None:
        config = self._collect_config()
        self._config_manager.save(config)
        self._append_log(f"Saved config to {self._config_manager.config_path}")

    def send_command(self) -> None:
        command = self._command_input.text().strip()
        if not command:
            self._append_log("No command entered.")
            return

        response = self._command_processor.send(command, self._collect_config())
        self._append_log(response)
        self._command_input.clear()
