from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
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

from ..core.adb_device_service import AdbDeviceService
from ..core.command_processor import CommandProcessor
from ..core.config_manager import AppConfig, ConfigManager


class MainWindow(QMainWindow):
    _SENSOR_INDEX_OPTIONS = (1, 2, 4, 8, 16)

    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("tool-001")
        self.resize(900, 520)

        self._config_manager = ConfigManager(config_path)
        self._command_processor = CommandProcessor()
        self._adb_device_service = AdbDeviceService()

        self._mode = _SingleSelectCheckGroup(["manual", "auto", "dify"], default="manual")

        self._adb_device_combo = QComboBox()
        self._scan_adb_button = QPushButton("Scan ADB")
        self._adb_devices: list[str] = []

        self._sensor_idx = _SingleSelectCheckGroup([str(value) for value in self._SENSOR_INDEX_OPTIONS], default="1")

        self._sensor_mode = _SingleSelectCheckGroup(["0", "1", "2"], default="0")

        self._cdr_delay_start = QSpinBox()
        self._cdr_delay_start.setRange(0, 31)

        self._eq_offset = QSpinBox()
        self._eq_offset.setRange(-31, 31)

        self._eq_dg0_enable = _SingleSelectCheckGroup(["0", "1"], default="0")

        self._eq_sr0 = QSpinBox()
        self._eq_sr0.setRange(0, 15)

        self._eq_dg1_enable = _SingleSelectCheckGroup(["0", "1"], default="0")

        self._eq_sr1 = QSpinBox()
        self._eq_sr1.setRange(0, 15)

        self._eq_bw = _SingleSelectCheckGroup(["0", "1", "2", "3"], default="0")

        self._phy_mode = _SingleSelectCheckGroup(["auto", "master", "slave"], default="auto")

        self._command_input = QLineEdit()
        self._command_input.setPlaceholderText("Enter debug command...")

        self._send_button = QPushButton("Send")
        self._load_button = QPushButton("Load Config")
        self._save_button = QPushButton("Save Config")

        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)

        self._param_detail = QTextEdit()
        self._param_detail.setReadOnly(True)

        self._build_ui()
        self._bind_events()
        self.load_config()

    def _build_ui(self) -> None:
        config_group = QGroupBox("Configuration")
        self._config_form = QFormLayout()
        self._config_form.addRow("Mode", self._mode)

        adb_device_row = QWidget()
        adb_device_layout = QHBoxLayout()
        adb_device_layout.setContentsMargins(0, 0, 0, 0)
        adb_device_layout.addWidget(self._adb_device_combo)
        adb_device_layout.addWidget(self._scan_adb_button)
        adb_device_row.setLayout(adb_device_layout)
        self._config_form.addRow("ADB Device", adb_device_row)

        self._config_form.addRow("Sensor idx", self._sensor_idx)
        self._sensor_mode_label = "Sensor mode"
        self._config_form.addRow(self._sensor_mode_label, self._sensor_mode)
        self._config_form.addRow("CDR delay start", self._cdr_delay_start)
        self._config_form.addRow("EQ offset", self._eq_offset)
        self._config_form.addRow("EQ dg0 enable", self._eq_dg0_enable)
        self._config_form.addRow("EQ sr0", self._eq_sr0)
        self._config_form.addRow("EQ dg1 enable", self._eq_dg1_enable)
        self._config_form.addRow("EQ sr1", self._eq_sr1)
        self._config_form.addRow("EQ bw", self._eq_bw)
        self._config_form.addRow("Phy mode", self._phy_mode)
        config_group.setLayout(self._config_form)

        detail_group = QGroupBox("Parameter Details")
        detail_layout = QVBoxLayout()
        detail_layout.addWidget(self._param_detail)
        detail_group.setLayout(detail_layout)

        top_layout = QHBoxLayout()
        top_layout.addWidget(config_group, stretch=2)
        top_layout.addWidget(detail_group, stretch=3)

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
        root_layout.addLayout(top_layout)
        root_layout.addLayout(config_actions_layout)
        root_layout.addWidget(command_group)
        root_layout.addWidget(log_group, stretch=1)

        container = QWidget()
        container.setLayout(root_layout)
        self.setCentralWidget(container)

    def _bind_events(self) -> None:
        self._mode.selection_changed.connect(self._on_mode_changed)
        self._load_button.clicked.connect(self.load_config)
        self._save_button.clicked.connect(self.save_config)
        self._send_button.clicked.connect(self.send_command)
        self._command_input.returnPressed.connect(self.send_command)
        self._scan_adb_button.clicked.connect(self.scan_adb_devices)

    def _collect_config(self) -> AppConfig:
        selected_mode = self._mode.selected_text
        sensor_modes = self._parse_sensor_modes() if selected_mode in {"auto", "dify"} else None
        sensor_idx_value = int(self._sensor_idx.selected_text)
        return AppConfig(
            mode=selected_mode,
            adb_device=self._selected_adb_device(),
            sensor_idx=sensor_idx_value,
            sensor_mode=sensor_modes,
            cdr_delay_start=self._cdr_delay_start.value(),
            eq_offset=self._eq_offset.value(),
            eq_dg0_enable=int(self._eq_dg0_enable.selected_text),
            eq_sr0=self._eq_sr0.value(),
            eq_dg1_enable=int(self._eq_dg1_enable.selected_text),
            eq_sr1=self._eq_sr1.value(),
            eq_bw=int(self._eq_bw.selected_text),
            phy_mode=self._phy_mode.selected_text,
        )

    def _apply_config(self, config: AppConfig) -> None:
        self._mode.select(config.mode if config.mode in {"manual", "auto", "dify"} else "manual")
        self._refresh_adb_devices(preferred=config.adb_device, should_log=False)
        self._sensor_idx.select(str(config.sensor_idx))
        if config.sensor_mode:
            self._sensor_mode.select(str(config.sensor_mode[0]))
        else:
            self._sensor_mode.select("0")
        self._cdr_delay_start.setValue(config.cdr_delay_start)
        self._eq_offset.setValue(config.eq_offset)
        self._eq_dg0_enable.select(str(config.eq_dg0_enable))
        self._eq_sr0.setValue(config.eq_sr0)
        self._eq_dg1_enable.select(str(config.eq_dg1_enable))
        self._eq_sr1.setValue(config.eq_sr1)
        self._eq_bw.select(str(config.eq_bw))
        self._phy_mode.select(config.phy_mode)
        self._update_mode_dependent_fields(self._mode.selected_text)

    def _parse_sensor_modes(self) -> list[int]:
        return [int(self._sensor_mode.selected_text)]

    def _selected_adb_device(self) -> str | None:
        current = self._adb_device_combo.currentText().strip()
        if not current or current not in self._adb_devices:
            return None
        return current

    def _refresh_adb_devices(self, *, preferred: str | None = None, should_log: bool = True) -> None:
        devices, error = self._adb_device_service.list_devices()
        self._adb_devices = devices
        self._adb_device_combo.clear()

        if devices:
            self._adb_device_combo.addItems(devices)
            self._adb_device_combo.setEnabled(True)
            if preferred and preferred in devices:
                self._adb_device_combo.setCurrentText(preferred)
            if should_log:
                self._append_log(f"Found {len(devices)} adb device(s).")
            return

        self._adb_device_combo.addItem("<no adb device>")
        self._adb_device_combo.setEnabled(False)
        if should_log:
            if error:
                self._append_log(f"ADB scan failed: {error}")
            else:
                self._append_log("No adb device found.")

    def scan_adb_devices(self) -> None:
        self._refresh_adb_devices(should_log=True)

    def _on_mode_changed(self, _button: QCheckBox) -> None:
        self._update_mode_dependent_fields(self._mode.selected_text)

    def _update_mode_dependent_fields(self, mode: str) -> None:
        has_sensor_mode = mode in {"auto", "dify"}
        self._sensor_mode.setVisible(has_sensor_mode)
        sensor_mode_label = self._config_form.labelForField(self._sensor_mode)
        if sensor_mode_label is not None:
            sensor_mode_label.setVisible(has_sensor_mode)

        cdr_max = 254 if mode == "dify" else 31
        self._cdr_delay_start.setMaximum(cdr_max)

        self._refresh_param_details(cdr_max)

    def _refresh_param_details(self, cdr_max: int) -> None:
        lines = [
            "1) adb device - 单步发送",
            "- source: adb devices",
            "- behavior: if multiple devices are found, user selects one manually",
            "",
            "2) sensor idx - 单步发送",
            "- type: single-select checkbox",
            "- allowed: 1, 2, 4, 8, 16",
            "",
            "3) sensor mode - 单步发送",
            "- type: single-select checkbox",
            "- allowed: 0, 1, 2",
            "",
            "4) cdr delay start - 单步发送",
            f"- range: 0 ~ {cdr_max}",
            "- mode linkage: mode=dify -> 0 ~ 254, others -> 0 ~ 31",
            "",
            "5) eq offset - 单步发送",
            "- range: -31 ~ 31",
            "",
            "6) eq dg0 enable - 单步发送",
            "- type: single-select checkbox",
            "- allowed: 0, 1",
            "",
            "7) eq sr0 - 单步发送",
            "- range: 0 ~ 15",
            "",
            "8) eq dg1 enable - 单步发送",
            "- type: single-select checkbox",
            "- allowed: 0, 1",
            "",
            "9) eq sr1 - 单步发送",
            "- range: 0 ~ 15",
            "",
            "10) eq bw - 单步发送",
            "- type: single-select checkbox",
            "- allowed: 0, 1, 2, 3",
            "",
            "11) mode - 单步发送",
            "- type: single-select checkbox",
            "- allowed: manual, auto, dify",
            "",
            "12) phy mode - 单步发送",
            "- type: single-select checkbox",
            "- allowed: auto, master, slave",
        ]
        self._param_detail.setPlainText("\n".join(lines))

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

        if not self._selected_adb_device():
            self._append_log("No adb device selected. Please scan and choose one device first.")
            return

        response = self._command_processor.send(command, self._collect_config())
        self._append_log(response)
        self._command_input.clear()


class _SingleSelectCheckGroup(QWidget):
    def __init__(self, options: list[str], *, default: str | None = None) -> None:
        super().__init__()
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._checks: dict[str, QCheckBox] = {}
        for option in options:
            check = QCheckBox(option)
            self._button_group.addButton(check)
            self._checks[option] = check
            layout.addWidget(check)
        layout.addStretch(1)
        self.setLayout(layout)

        initial_option = default if default in self._checks else options[0]
        self.select(initial_option)

    @property
    def selected_text(self) -> str:
        checked = self._button_group.checkedButton()
        return checked.text() if checked is not None else ""

    @property
    def selection_changed(self):
        return self._button_group.buttonClicked

    def select(self, value: str) -> None:
        target = self._checks.get(value)
        if target is None:
            target = next(iter(self._checks.values()))
        target.setChecked(True)
