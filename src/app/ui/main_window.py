from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.adb_device_service import AdbDeviceService
from app.core.command_processor import CommandProcessor
from app.core.config_manager import AppConfig, ConfigManager


class MainWindow(QMainWindow):
    _SENSOR_INDEX_OPTIONS = (1, 2, 4, 8, 16)

    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("tool-001")
        self.resize(980, 620)

        self._config_manager = ConfigManager(config_path)
        self._command_processor = CommandProcessor()
        self._adb_device_service = AdbDeviceService()

        self._manual_mode_notice = QLabel(
            "参数写入和测试过程中，请始终保持 camera 工作。熄屏或退出会导致写入的参数擦除。"
        )
        self._manual_mode_notice.setWordWrap(True)
        self._manual_mode_notice.setStyleSheet("color: #d32f2f; font-size: 18px; font-weight: 700;")

        self._adb_device_combo = QComboBox()
        self._scan_adb_button = QPushButton("Scan ADB")
        self._adb_devices: list[str] = []

        self._auto_adb_device_combo = QComboBox()
        self._auto_scan_adb_button = QPushButton("Scan ADB")
        self._auto_adb_devices: list[str] = []

        self._manual_sensor_idx = _SingleSelectCheckGroup([str(value) for value in self._SENSOR_INDEX_OPTIONS], default="1")
        self._manual_sensor_mode = _SingleSelectCheckGroup(["0", "1", "2"], default="0")
        self._auto_sensor_idx = _MultiSelectCheckGroup([str(value) for value in self._SENSOR_INDEX_OPTIONS], default=["1"])
        self._auto_sensor_mode = _MultiSelectCheckGroup(["0", "1", "2"], default=["0"])

        self._is_dphy = QCheckBox("DPHY")
        self._auto_is_dphy = QCheckBox("DPHY")

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

        self._auto_cdr_delay_start = QSpinBox()
        self._auto_cdr_delay_start.setRange(0, 31)
        self._auto_cdr_delay_end = QSpinBox()
        self._auto_cdr_delay_end.setRange(0, 31)
        self._auto_cdr_delay_end.setValue(31)

        self._auto_eq_offset_start = QSpinBox()
        self._auto_eq_offset_start.setRange(-31, 31)
        self._auto_eq_offset_start.setValue(-31)
        self._auto_eq_offset_end = QSpinBox()
        self._auto_eq_offset_end.setRange(-31, 31)
        self._auto_eq_offset_end.setValue(31)

        self._auto_eq_dg0_enable = _MultiSelectCheckGroup(["0", "1"], default=["0", "1"])

        self._auto_eq_sr0_start = QSpinBox()
        self._auto_eq_sr0_start.setRange(0, 15)
        self._auto_eq_sr0_end = QSpinBox()
        self._auto_eq_sr0_end.setRange(0, 15)
        self._auto_eq_sr0_end.setValue(15)

        self._auto_eq_dg1_enable = _MultiSelectCheckGroup(["0", "1"], default=["0", "1"])

        self._auto_eq_sr1_start = QSpinBox()
        self._auto_eq_sr1_start.setRange(0, 15)
        self._auto_eq_sr1_end = QSpinBox()
        self._auto_eq_sr1_end.setRange(0, 15)
        self._auto_eq_sr1_end.setValue(15)

        self._auto_eq_bw = _MultiSelectCheckGroup(["0", "1", "2", "3"], default=["0", "1", "2", "3"])

        self._command_input = QLineEdit()
        self._command_input.setPlaceholderText("手动模式可输入寄存器命令")
        self._auto_command_input = QLineEdit()
        self._auto_command_input.setPlaceholderText("自动化测试可选输入测试步骤列表(逗号分隔)")

        self._send_button = QPushButton("Send")
        self._load_button = QPushButton("Load Config")
        self._save_button = QPushButton("Save Config")
        self._clear_log_button = QPushButton("Clear Logs")

        self._auto_clear_log_button = QPushButton("Clear Logs")
        self._auto_load_button = QPushButton("Load Config")
        self._auto_save_button = QPushButton("Save Config")
        self._start_test_button = QPushButton("开始测试")

        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)

        self._auto_log_output = QTextEdit()
        self._auto_log_output.setReadOnly(True)

        self._param_detail = QTextEdit()
        self._param_detail.setReadOnly(True)

        self._auto_param_detail = QTextEdit()
        self._auto_param_detail.setReadOnly(True)

        self._step_send_buttons: list[QPushButton] = []

        self._build_ui()
        self._bind_events()
        self.load_manual_config()
        self.load_auto_config()

    def _build_ui(self) -> None:
        self._mode_tabs = QTabWidget()
        self._mode_tabs.addTab(self._build_manual_tab(), "单步调试")
        self._mode_tabs.addTab(self._build_auto_tab(), "自动化测试")

        container = QWidget()
        root_layout = QVBoxLayout()
        root_layout.addWidget(self._mode_tabs)
        container.setLayout(root_layout)
        self.setCentralWidget(container)

    def _build_manual_tab(self) -> QWidget:
        tab = QWidget()

        config_group = QGroupBox("Configuration")
        config_form = QFormLayout()
        adb_device_row = QWidget()
        adb_device_layout = QHBoxLayout()
        adb_device_layout.setContentsMargins(0, 0, 0, 0)
        adb_device_layout.addWidget(self._adb_device_combo)
        adb_device_layout.addWidget(self._scan_adb_button)
        adb_device_row.setLayout(adb_device_layout)
        config_form.addRow("ADB Device", adb_device_row)
        config_form.addRow("CDR delay", self._with_step_send(self._cdr_delay_start, "cdr delay", self._is_dphy))
        config_form.addRow("EQ offset", self._with_step_send(self._eq_offset, "eq offset"))
        config_form.addRow("EQ dg0 enable", self._with_step_send(self._eq_dg0_enable, "eq dg0 enable"))
        config_form.addRow("EQ sr0", self._with_step_send(self._eq_sr0, "eq sr0"))
        config_form.addRow("EQ dg1 enable", self._with_step_send(self._eq_dg1_enable, "eq dg1 enable"))
        config_form.addRow("EQ sr1", self._with_step_send(self._eq_sr1, "eq sr1"))
        config_form.addRow("EQ bw", self._with_step_send(self._eq_bw, "eq bw"))
        config_group.setLayout(config_form)

        detail_group = QGroupBox("Parameter Details")
        detail_layout = QVBoxLayout()
        detail_layout.addWidget(self._param_detail)
        detail_group.setLayout(detail_layout)

        top_layout = QHBoxLayout()
        top_layout.addWidget(config_group, stretch=2)
        top_layout.addWidget(detail_group, stretch=3)

        mode_group = QGroupBox("Mode")
        mode_layout = QVBoxLayout()
        mode_form = QFormLayout()
        mode_form.addRow("Sensor idx", self._manual_sensor_idx)
        mode_form.addRow("Sensor mode", self._manual_sensor_mode)
        mode_layout.addWidget(self._manual_mode_notice)
        mode_layout.addLayout(mode_form)
        mode_group.setLayout(mode_layout)

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
        log_actions_layout = QHBoxLayout()
        log_actions_layout.addStretch(1)
        log_actions_layout.addWidget(self._clear_log_button)
        log_layout.addLayout(log_actions_layout)
        log_layout.addWidget(self._log_output)
        log_group.setLayout(log_layout)

        layout = QVBoxLayout()
        layout.addLayout(top_layout)
        layout.addWidget(mode_group)
        layout.addLayout(config_actions_layout)
        layout.addWidget(command_group)
        layout.addWidget(log_group, stretch=1)
        tab.setLayout(layout)
        return tab

    def _build_auto_tab(self) -> QWidget:
        tab = QWidget()

        config_group = QGroupBox("Configuration")
        config_form = QFormLayout()
        adb_device_row = QWidget()
        adb_device_layout = QHBoxLayout()
        adb_device_layout.setContentsMargins(0, 0, 0, 0)
        adb_device_layout.addWidget(self._auto_adb_device_combo)
        adb_device_layout.addWidget(self._auto_scan_adb_button)
        adb_device_row.setLayout(adb_device_layout)
        config_form.addRow("ADB Device", adb_device_row)
        config_form.addRow("DPHY", self._auto_is_dphy)
        config_group.setLayout(config_form)

        detail_group = QGroupBox("Parameter Details")
        detail_layout = QVBoxLayout()
        detail_layout.addWidget(self._auto_param_detail)
        detail_group.setLayout(detail_layout)

        top_layout = QHBoxLayout()
        top_layout.addWidget(config_group, stretch=2)
        top_layout.addWidget(detail_group, stretch=3)

        mode_group = QGroupBox("Mode")
        mode_layout = QVBoxLayout()
        mode_form = QFormLayout()
        mode_form.addRow("Sensor idx", self._auto_sensor_idx)
        mode_form.addRow("Sensor mode", self._auto_sensor_mode)
        mode_form.addRow("CDR delay", self._auto_range_row(self._auto_cdr_delay_start, self._auto_cdr_delay_end))
        mode_form.addRow("EQ offset", self._auto_range_row(self._auto_eq_offset_start, self._auto_eq_offset_end))
        mode_form.addRow("EQ dg0 enable", self._auto_eq_dg0_enable)
        mode_form.addRow("EQ sr0", self._auto_range_row(self._auto_eq_sr0_start, self._auto_eq_sr0_end))
        mode_form.addRow("EQ dg1 enable", self._auto_eq_dg1_enable)
        mode_form.addRow("EQ sr1", self._auto_range_row(self._auto_eq_sr1_start, self._auto_eq_sr1_end))
        mode_form.addRow("EQ bw", self._auto_eq_bw)
        mode_layout.addLayout(mode_form)
        mode_layout.addWidget(self._start_test_button)
        mode_group.setLayout(mode_layout)

        config_actions_layout = QHBoxLayout()
        config_actions_layout.addWidget(self._auto_load_button)
        config_actions_layout.addWidget(self._auto_save_button)
        config_actions_layout.addStretch(1)

        command_group = QGroupBox("Command Debug")
        command_layout = QHBoxLayout()
        command_layout.addWidget(self._auto_command_input)
        command_group.setLayout(command_layout)

        log_group = QGroupBox("Log Output")
        log_layout = QVBoxLayout()
        log_actions_layout = QHBoxLayout()
        log_actions_layout.addStretch(1)
        log_actions_layout.addWidget(self._auto_clear_log_button)
        log_layout.addLayout(log_actions_layout)
        log_layout.addWidget(self._auto_log_output)
        log_group.setLayout(log_layout)

        layout = QVBoxLayout()
        layout.addLayout(top_layout)
        layout.addWidget(mode_group)
        layout.addLayout(config_actions_layout)
        layout.addWidget(command_group)
        layout.addWidget(log_group, stretch=1)
        tab.setLayout(layout)
        return tab

    def _bind_events(self) -> None:
        self._is_dphy.toggled.connect(self._update_mode_dependent_fields)
        self._auto_is_dphy.toggled.connect(self._update_mode_dependent_fields)

        self._load_button.clicked.connect(self.load_manual_config)
        self._save_button.clicked.connect(self.save_manual_config)
        self._send_button.clicked.connect(self.send_manual_command)
        self._command_input.returnPressed.connect(self.send_manual_command)
        self._scan_adb_button.clicked.connect(self.scan_manual_adb_devices)
        self._clear_log_button.clicked.connect(self.clear_manual_logs)

        self._auto_load_button.clicked.connect(self.load_auto_config)
        self._auto_save_button.clicked.connect(self.save_auto_config)
        self._auto_scan_adb_button.clicked.connect(self.scan_auto_adb_devices)
        self._auto_clear_log_button.clicked.connect(self.clear_auto_logs)
        self._start_test_button.clicked.connect(self._start_auto_test)

    def _collect_manual_config(self) -> AppConfig:
        return AppConfig(
            mode="manual",
            adb_device=self._selected_manual_adb_device(),
            is_dphy=self._is_dphy.isChecked(),
            sensor_idx=int(self._manual_sensor_idx.selected_text),
            sensor_mode=[int(self._manual_sensor_mode.selected_text)],
            cdr_delay_start=self._cdr_delay_start.value(),
            eq_offset=self._eq_offset.value(),
            eq_dg0_enable=int(self._eq_dg0_enable.selected_text),
            eq_sr0=self._eq_sr0.value(),
            eq_dg1_enable=int(self._eq_dg1_enable.selected_text),
            eq_sr1=self._eq_sr1.value(),
            eq_bw=int(self._eq_bw.selected_text),
            auto_cdr_delay_start=self._auto_cdr_delay_start.value(),
            auto_cdr_delay_end=self._auto_cdr_delay_end.value(),
            auto_eq_offset_start=self._auto_eq_offset_start.value(),
            auto_eq_offset_end=self._auto_eq_offset_end.value(),
            auto_eq_dg0_enable_values=[int(value) for value in self._auto_eq_dg0_enable.selected_texts],
            auto_eq_sr0_start=self._auto_eq_sr0_start.value(),
            auto_eq_sr0_end=self._auto_eq_sr0_end.value(),
            auto_eq_dg1_enable_values=[int(value) for value in self._auto_eq_dg1_enable.selected_texts],
            auto_eq_sr1_start=self._auto_eq_sr1_start.value(),
            auto_eq_sr1_end=self._auto_eq_sr1_end.value(),
            auto_eq_bw_values=[int(value) for value in self._auto_eq_bw.selected_texts],
            auto_sensor_idx=[int(value) for value in self._auto_sensor_idx.selected_texts],
        )

    def _collect_auto_config(self) -> AppConfig:
        return AppConfig(
            mode="auto",
            adb_device=self._selected_auto_adb_device(),
            is_dphy=self._auto_is_dphy.isChecked(),
            sensor_idx=int(self._manual_sensor_idx.selected_text),
            auto_sensor_idx=[int(value) for value in self._auto_sensor_idx.selected_texts],
            sensor_mode=self._parse_auto_sensor_modes(),
            cdr_delay_start=self._cdr_delay_start.value(),
            eq_offset=self._eq_offset.value(),
            eq_dg0_enable=int(self._eq_dg0_enable.selected_text),
            eq_sr0=self._eq_sr0.value(),
            eq_dg1_enable=int(self._eq_dg1_enable.selected_text),
            eq_sr1=self._eq_sr1.value(),
            eq_bw=int(self._eq_bw.selected_text),
            auto_cdr_delay_start=self._auto_cdr_delay_start.value(),
            auto_cdr_delay_end=self._auto_cdr_delay_end.value(),
            auto_eq_offset_start=self._auto_eq_offset_start.value(),
            auto_eq_offset_end=self._auto_eq_offset_end.value(),
            auto_eq_dg0_enable_values=[int(value) for value in self._auto_eq_dg0_enable.selected_texts],
            auto_eq_sr0_start=self._auto_eq_sr0_start.value(),
            auto_eq_sr0_end=self._auto_eq_sr0_end.value(),
            auto_eq_dg1_enable_values=[int(value) for value in self._auto_eq_dg1_enable.selected_texts],
            auto_eq_sr1_start=self._auto_eq_sr1_start.value(),
            auto_eq_sr1_end=self._auto_eq_sr1_end.value(),
            auto_eq_bw_values=[int(value) for value in self._auto_eq_bw.selected_texts],
        )

    def _apply_manual_config(self, config: AppConfig) -> None:
        self._refresh_manual_adb_devices(preferred=config.adb_device, should_log=False)
        self._is_dphy.setChecked(config.is_dphy)
        self._manual_sensor_idx.select(str(config.sensor_idx))
        self._manual_sensor_mode.select(str(config.sensor_mode[0]) if config.sensor_mode else "0")
        self._cdr_delay_start.setValue(config.cdr_delay_start)
        self._eq_offset.setValue(config.eq_offset)
        self._eq_dg0_enable.select(str(config.eq_dg0_enable))
        self._eq_sr0.setValue(config.eq_sr0)
        self._eq_dg1_enable.select(str(config.eq_dg1_enable))
        self._eq_sr1.setValue(config.eq_sr1)
        self._eq_bw.select(str(config.eq_bw))
        self._update_mode_dependent_fields()

    def _apply_auto_config(self, config: AppConfig) -> None:
        self._refresh_auto_adb_devices(preferred=config.adb_device, should_log=False)
        self._auto_is_dphy.setChecked(config.is_dphy)
        self._auto_sensor_mode.select_many([str(value) for value in (config.sensor_mode or [0])])
        self._auto_sensor_idx.select_many([str(value) for value in (config.auto_sensor_idx or [1])])
        self._auto_cdr_delay_start.setValue(config.auto_cdr_delay_start)
        self._auto_cdr_delay_end.setValue(config.auto_cdr_delay_end)
        self._auto_eq_offset_start.setValue(config.auto_eq_offset_start)
        self._auto_eq_offset_end.setValue(config.auto_eq_offset_end)
        self._auto_eq_dg0_enable.select_many([str(value) for value in (config.auto_eq_dg0_enable_values or [0, 1])])
        self._auto_eq_sr0_start.setValue(config.auto_eq_sr0_start)
        self._auto_eq_sr0_end.setValue(config.auto_eq_sr0_end)
        self._auto_eq_dg1_enable.select_many([str(value) for value in (config.auto_eq_dg1_enable_values or [0, 1])])
        self._auto_eq_sr1_start.setValue(config.auto_eq_sr1_start)
        self._auto_eq_sr1_end.setValue(config.auto_eq_sr1_end)
        self._auto_eq_bw.select_many([str(value) for value in (config.auto_eq_bw_values or [0, 1, 2, 3])])
        self._update_mode_dependent_fields()

    def _parse_auto_sensor_modes(self) -> list[int]:
        selected_modes = [int(value) for value in self._auto_sensor_mode.selected_texts]
        return selected_modes or [0]

    def _selected_manual_adb_device(self) -> str | None:
        current = self._adb_device_combo.currentText().strip()
        if not current or current not in self._adb_devices:
            return None
        return current

    def _selected_auto_adb_device(self) -> str | None:
        current = self._auto_adb_device_combo.currentText().strip()
        if not current or current not in self._auto_adb_devices:
            return None
        return current

    def _refresh_manual_adb_devices(self, *, preferred: str | None = None, should_log: bool = True) -> None:
        devices, error = self._adb_device_service.list_devices()
        self._adb_devices = devices
        self._adb_device_combo.clear()

        if devices:
            self._adb_device_combo.addItems(devices)
            self._adb_device_combo.setEnabled(True)
            if preferred and preferred in devices:
                self._adb_device_combo.setCurrentText(preferred)
            if should_log:
                self._append_manual_log(f"Found {len(devices)} adb device(s).")
            return

        self._adb_device_combo.addItem("<no adb device>")
        self._adb_device_combo.setEnabled(False)
        if should_log:
            self._append_manual_log(f"ADB scan failed: {error}" if error else "No adb device found.")

    def _refresh_auto_adb_devices(self, *, preferred: str | None = None, should_log: bool = True) -> None:
        devices, error = self._adb_device_service.list_devices()
        self._auto_adb_devices = devices
        self._auto_adb_device_combo.clear()

        if devices:
            self._auto_adb_device_combo.addItems(devices)
            self._auto_adb_device_combo.setEnabled(True)
            if preferred and preferred in devices:
                self._auto_adb_device_combo.setCurrentText(preferred)
            if should_log:
                self._append_auto_log(f"Found {len(devices)} adb device(s).")
            return

        self._auto_adb_device_combo.addItem("<no adb device>")
        self._auto_adb_device_combo.setEnabled(False)
        if should_log:
            self._append_auto_log(f"ADB scan failed: {error}" if error else "No adb device found.")

    def scan_manual_adb_devices(self) -> None:
        self._refresh_manual_adb_devices(should_log=True)

    def scan_auto_adb_devices(self) -> None:
        self._refresh_auto_adb_devices(should_log=True)

    def _update_mode_dependent_fields(self) -> None:
        manual_cdr_max = 254 if self._is_dphy.isChecked() else 31
        self._cdr_delay_start.setMaximum(manual_cdr_max)
        if self._cdr_delay_start.value() > manual_cdr_max:
            self._cdr_delay_start.setValue(manual_cdr_max)

        auto_cdr_max = 254 if self._auto_is_dphy.isChecked() else 31
        self._auto_cdr_delay_start.setMaximum(auto_cdr_max)
        self._auto_cdr_delay_end.setMaximum(auto_cdr_max)
        if self._auto_cdr_delay_start.value() > auto_cdr_max:
            self._auto_cdr_delay_start.setValue(auto_cdr_max)
        if self._auto_cdr_delay_end.value() > auto_cdr_max:
            self._auto_cdr_delay_end.setValue(auto_cdr_max)

        self._refresh_param_details(manual_cdr_max, auto_cdr_max)

    def _refresh_param_details(self, manual_cdr_max: int, auto_cdr_max: int) -> None:
        manual_lines = [
            "Tab1: 单步调试(manual)",
            "- sensor idx: 单选 checkbox",
            "- sensor mode: 单选 checkbox",
            "",
            "参数范围:",
            f"- cdr delay: 0 ~ {manual_cdr_max}",
            "- eq offset: -31 ~ 31",
            "- eq sr0 / eq sr1: 0 ~ 15",
            "",
            "ADB Device 由 adb devices 获取。",
        ]
        self._param_detail.setPlainText("\n".join(manual_lines))

        auto_lines = [
            "Tab2: 自动化测试(auto)",
            "- sensor idx: 多选 checkbox",
            "- sensor mode: 多选 checkbox",
            "- cdr delay / eq offset / eq sr0 / eq sr1: start-end 遍历",
            "- eq dg0 enable / eq dg1 enable / eq bw: 多选 checkbox",
            "",
            "参数范围:",
            f"- cdr delay: 0 ~ {auto_cdr_max}",
            "- eq offset: -31 ~ 31",
            "- eq sr0 / eq sr1: 0 ~ 15",
            "",
            "ADB Device 由 adb devices 获取。",
        ]
        self._auto_param_detail.setPlainText("\n".join(auto_lines))

    def _with_step_send(self, field: QWidget, command: str, extra_widget: QWidget | None = None) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field)
        if extra_widget is not None:
            layout.addWidget(extra_widget)
        step_send_button = QPushButton("单步发送")
        step_send_button.setFixedWidth(88)
        step_send_button.clicked.connect(lambda: self._send_single_step(command))
        self._step_send_buttons.append(step_send_button)
        layout.addWidget(step_send_button)
        row.setLayout(layout)
        return row

    def _auto_range_row(self, start_widget: QWidget, end_widget: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("开始"))
        layout.addWidget(start_widget)
        layout.addWidget(QLabel("结束"))
        layout.addWidget(end_widget)
        layout.addStretch(1)
        row.setLayout(layout)
        return row

    def _send_single_step(self, command: str) -> None:
        if not self._selected_manual_adb_device():
            self._append_manual_log("No adb device selected. Please scan and choose one device first.")
            return
        response = self._command_processor.send(command, self._collect_manual_config())
        self._append_manual_log(response)

    def _append_manual_log(self, message: str) -> None:
        self._log_output.append(message)

    def _append_auto_log(self, message: str) -> None:
        self._auto_log_output.append(message)

    def clear_manual_logs(self) -> None:
        self._log_output.clear()

    def clear_auto_logs(self) -> None:
        self._auto_log_output.clear()

    def load_manual_config(self) -> None:
        config = self._config_manager.load()
        self._apply_manual_config(config)
        self._append_manual_log(f"Loaded config from {self._config_manager.config_path}")

    def save_manual_config(self) -> None:
        config = self._collect_manual_config()
        self._config_manager.save(config)
        self._append_manual_log(f"Saved config to {self._config_manager.config_path}")

    def load_auto_config(self) -> None:
        config = self._config_manager.load()
        self._apply_auto_config(config)
        self._append_auto_log(f"Loaded config from {self._config_manager.config_path}")

    def save_auto_config(self) -> None:
        config = self._collect_auto_config()
        self._config_manager.save(config)
        self._append_auto_log(f"Saved config to {self._config_manager.config_path}")

    def send_manual_command(self) -> None:
        command = self._command_input.text().strip()
        if not self._selected_manual_adb_device():
            self._append_manual_log("No adb device selected. Please scan and choose one device first.")
            return
        if not command:
            self._append_manual_log("No command entered.")
            return

        response = self._command_processor.send(command, self._collect_manual_config())
        self._append_manual_log(response)
        self._command_input.clear()

    def _start_auto_test(self) -> None:
        if not self._selected_auto_adb_device():
            self._append_auto_log("No adb device selected. Please scan and choose one device first.")
            return

        config = self._collect_auto_config()
        range_errors = self._auto_range_errors(config)
        if range_errors:
            self._append_auto_log("自动化测试参数范围错误:\n" + "\n".join(range_errors))
            return

        command = self._auto_command_input.text().strip()
        response = self._command_processor.run_automated_test(config, command)
        self._append_auto_log(response)
        self._auto_command_input.clear()

    @staticmethod
    def _auto_range_errors(config: AppConfig) -> list[str]:
        checks = [
            ("CDR delay", config.auto_cdr_delay_start, config.auto_cdr_delay_end),
            ("EQ offset", config.auto_eq_offset_start, config.auto_eq_offset_end),
            ("EQ sr0", config.auto_eq_sr0_start, config.auto_eq_sr0_end),
            ("EQ sr1", config.auto_eq_sr1_start, config.auto_eq_sr1_end),
        ]
        errors: list[str] = []
        for name, start, end in checks:
            if start > end:
                errors.append(f"- {name}: 开始值({start}) 不能大于结束值({end})")
        return errors


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

    def select(self, value: str) -> None:
        target = self._checks.get(value)
        if target is None:
            target = next(iter(self._checks.values()))
        target.setChecked(True)


class _MultiSelectCheckGroup(QWidget):
    def __init__(self, options: list[str], *, default: list[str] | None = None) -> None:
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._checks: dict[str, QCheckBox] = {}
        for option in options:
            check = QCheckBox(option)
            self._checks[option] = check
            layout.addWidget(check)
        layout.addStretch(1)
        self.setLayout(layout)

        initial = default or options[:1]
        self.select_many(initial)

    @property
    def selected_texts(self) -> list[str]:
        return [option for option, check in self._checks.items() if check.isChecked()]

    def select_many(self, values: list[str]) -> None:
        matched = set(values) & set(self._checks)
        if not matched and self._checks:
            matched = {next(iter(self._checks))}

        for option, check in self._checks.items():
            check.setChecked(option in matched)
