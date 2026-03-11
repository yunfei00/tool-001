from __future__ import annotations

from pathlib import Path
import csv
import re
from datetime import datetime

from PySide6.QtGui import QDesktopServices
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
    QTableWidget,
    QTableWidgetItem,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)
from PySide6.QtCore import QObject, QThread, Signal, QUrl

from app.core.adb_device_service import AdbDeviceService
from app.core.command_processor import CommandProcessor
from app.core.config_manager import AppConfig, ConfigManager
from app.ui.widgets.serial_command_panel import SerialCommandPanel


class MainWindow(QMainWindow):
    _SENSOR_INDEX_OPTIONS = (1, 2, 4, 8, 16)

    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self.setWindowTitle("MTK 平台CAMERA CTLE参数筛选")
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

        self._manual_sensor_idx = _SingleSelectCheckGroup([str(value) for value in self._SENSOR_INDEX_OPTIONS], default="1")
        self._manual_sensor_mode = _SingleSelectCheckGroup(["0", "1", "2"], default="0")
        self._auto_sensor_idx = _MultiSelectCheckGroup([str(value) for value in self._SENSOR_INDEX_OPTIONS], default=["1"])
        self._auto_sensor_mode = _MultiSelectCheckGroup(["0", "1", "2"], default=["0"])

        self._is_dphy = QCheckBox("DPHY")
        self._auto_is_dphy = QCheckBox("DPHY")
        self._auto_manual_stream = QCheckBox("手动起流(不自动后台起流)")

        self._auto_loop_count = QSpinBox()
        self._auto_loop_count.setRange(1, 9999)
        self._auto_loop_count.setValue(1)

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
        self._command_input.setPlaceholderText("手动模式可输入寄存器命令（范围见下方参数）")
        self._result_file_input = QLineEdit()
        self._result_file_input.setReadOnly(True)
        self._open_result_dir_button = QPushButton("打开文件夹")
        self._view_result_button = QPushButton("查看结果")


        self._send_button = QPushButton("Send")
        self._load_button = QPushButton("Load Config")
        self._save_button = QPushButton("Save Config")
        self._clear_log_button = QPushButton("Clear Logs")
        self._start_stream_debug_button = QPushButton("起流调试")
        self._stop_stream_debug_button = QPushButton("停止流")
        self._read_current_params_button = QPushButton("读取当前参数")

        self._auto_clear_log_button = QPushButton("Clear Logs")
        self._auto_load_button = QPushButton("Load Config")
        self._auto_save_button = QPushButton("Save Config")
        self._start_test_button = QPushButton("开始测试")
        self._stop_test_button = QPushButton("停止测试")
        self._stop_test_button.setEnabled(False)

        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)

        self._auto_log_output = QTextEdit()
        self._auto_log_output.setReadOnly(True)

        self._manual_serial_panel = SerialCommandPanel(title="串口AT调试")
        self._auto_serial_panel = SerialCommandPanel(title="串口AT调试")

        self._analysis_result_path = QLineEdit()
        self._analysis_result_path.setReadOnly(True)
        self._analysis_browse_button = QPushButton("浏览")
        self._analysis_reload_button = QPushButton("刷新")
        self._analysis_status_filter = QComboBox()
        self._analysis_status_filter.addItems(["仅成功", "全部", "失败", "待定"])
        self._analysis_keyword_filter = QLineEdit()
        self._analysis_keyword_filter.setPlaceholderText("可选关键字过滤")
        self._analysis_table = QTableWidget()
        self._analysis_table.setAlternatingRowColors(True)

        self._step_send_buttons: list[QPushButton] = []
        self._auto_test_thread: QThread | None = None
        self._auto_test_worker: _AutoTestWorker | None = None
        self._current_result_file_path: Path | None = None
        self._analysis_rows: list[dict[str, str]] = []

        self._build_ui()
        self._bind_events()
        self.load_manual_config()
        self.load_auto_config()
        self._set_current_result_file(self._discover_latest_result_file())

    def _build_ui(self) -> None:
        adb_group = QGroupBox("ADB Device")
        adb_layout = QHBoxLayout()
        adb_layout.addWidget(self._adb_device_combo)
        adb_layout.addWidget(self._scan_adb_button)
        adb_group.setLayout(adb_layout)

        self._mode_tabs = QTabWidget()
        self._mode_tabs.addTab(self._build_manual_tab(), "单步调试")
        self._mode_tabs.addTab(self._build_auto_tab(), "自动化测试")
        self._mode_tabs.addTab(self._build_analysis_tab(), "结果分析")

        container = QWidget()
        root_layout = QVBoxLayout()
        root_layout.addWidget(adb_group)
        root_layout.addWidget(self._mode_tabs)
        container.setLayout(root_layout)
        self.setCentralWidget(container)

    def _build_manual_tab(self) -> QWidget:
        tab = QWidget()

        notice_group = QGroupBox("Notice")
        notice_layout = QVBoxLayout()
        notice_layout.addWidget(self._manual_mode_notice)
        notice_group.setLayout(notice_layout)

        manual_group = QGroupBox("Manual Parameters")
        manual_form = QFormLayout()
        manual_form.addRow("Sensor idx", self._manual_sensor_idx)
        manual_form.addRow("Sensor mode", self._manual_sensor_mode)
        manual_form.addRow(
            "CDR delay",
            self._with_step_send(
                self._cdr_delay_start,
                "cdr delay",
                self._is_dphy,
                range_text="范围: 0~31(CPHY)/0~254(DPHY)",
            ),
        )
        manual_form.addRow("EQ offset", self._with_step_send(self._eq_offset, "eq offset", range_text="范围: -31~31"))
        manual_form.addRow("EQ dg0 enable", self._with_step_send(self._eq_dg0_enable, "eq dg0 enable"))
        manual_form.addRow("EQ sr0", self._with_step_send(self._eq_sr0, "eq sr0", range_text="范围: 0~15"))
        manual_form.addRow("EQ dg1 enable", self._with_step_send(self._eq_dg1_enable, "eq dg1 enable"))
        manual_form.addRow("EQ sr1", self._with_step_send(self._eq_sr1, "eq sr1", range_text="范围: 0~15"))
        manual_form.addRow("EQ bw", self._with_step_send(self._eq_bw, "eq bw"))
        manual_form.addRow("", self._read_current_params_button)
        manual_group.setLayout(manual_form)

        config_actions_layout = QHBoxLayout()
        config_actions_layout.addWidget(self._load_button)
        config_actions_layout.addWidget(self._save_button)
        config_actions_layout.addStretch(1)

        command_group = QGroupBox("Command Debug")
        command_layout = QHBoxLayout()
        command_layout.addWidget(self._command_input)
        command_layout.addWidget(self._send_button)
        command_layout.addWidget(self._start_stream_debug_button)
        command_layout.addWidget(self._stop_stream_debug_button)
        command_group.setLayout(command_layout)

        log_group = QGroupBox("Log Output")
        log_layout = QVBoxLayout()
        log_actions_layout = QHBoxLayout()
        log_actions_layout.addStretch(1)
        log_actions_layout.addWidget(self._clear_log_button)
        log_layout.addLayout(log_actions_layout)
        log_layout.addWidget(self._log_output)
        log_group.setLayout(log_layout)

        left_layout = QVBoxLayout()
        left_layout.addWidget(notice_group)
        left_layout.addWidget(manual_group)
        left_layout.addLayout(config_actions_layout)
        left_layout.addWidget(command_group)
        left_layout.addWidget(log_group, stretch=1)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        layout = QHBoxLayout()
        layout.addWidget(left_widget, stretch=2)
        layout.addWidget(self._manual_serial_panel, stretch=1)
        tab.setLayout(layout)
        return tab

    def _build_auto_tab(self) -> QWidget:
        tab = QWidget()

        auto_group = QGroupBox("Auto Parameters")
        auto_layout = QVBoxLayout()
        auto_form = QFormLayout()
        auto_form.addRow("压测次数", self._auto_loop_count)
        auto_form.addRow("Sensor idx", self._auto_sensor_idx)
        auto_form.addRow("Sensor mode", self._auto_sensor_mode)
        auto_form.addRow(
            "CDR delay",
            self._auto_range_row(
                self._auto_cdr_delay_start,
                self._auto_cdr_delay_end,
                self._auto_is_dphy,
                range_text="范围: 0~31(CPHY)/0~254(DPHY)",
            ),
        )
        auto_form.addRow(
            "EQ offset",
            self._auto_range_row(
                self._auto_eq_offset_start,
                self._auto_eq_offset_end,
                range_text="范围: -31~31",
            ),
        )
        auto_form.addRow("EQ dg0 enable", self._with_auto_row(self._auto_eq_dg0_enable))
        auto_form.addRow(
            "EQ sr0",
            self._auto_range_row(
                self._auto_eq_sr0_start,
                self._auto_eq_sr0_end,
                range_text="范围: 0~15",
            ),
        )
        auto_form.addRow("EQ dg1 enable", self._with_auto_row(self._auto_eq_dg1_enable))
        auto_form.addRow(
            "EQ sr1",
            self._auto_range_row(
                self._auto_eq_sr1_start,
                self._auto_eq_sr1_end,
                range_text="范围: 0~15",
            ),
        )
        auto_form.addRow("EQ bw", self._with_auto_row(self._auto_eq_bw))
        auto_form.addRow("相机起流", self._auto_manual_stream)
        auto_layout.addLayout(auto_form)
        auto_actions_layout = QHBoxLayout()
        auto_actions_layout.addWidget(self._start_test_button)
        auto_actions_layout.addWidget(self._stop_test_button)
        auto_actions_layout.addStretch(1)
        auto_layout.addLayout(auto_actions_layout)
        auto_group.setLayout(auto_layout)

        config_actions_layout = QHBoxLayout()
        config_actions_layout.addWidget(self._auto_load_button)
        config_actions_layout.addWidget(self._auto_save_button)
        config_actions_layout.addStretch(1)

        result_group = QGroupBox("运行结果")
        result_layout = QHBoxLayout()
        result_layout.addWidget(self._result_file_input)
        result_layout.addWidget(self._open_result_dir_button)
        result_layout.addWidget(self._view_result_button)
        result_group.setLayout(result_layout)

        log_group = QGroupBox("Log Output")
        log_layout = QVBoxLayout()
        log_actions_layout = QHBoxLayout()
        log_actions_layout.addStretch(1)
        log_actions_layout.addWidget(self._auto_clear_log_button)
        log_layout.addLayout(log_actions_layout)
        log_layout.addWidget(self._auto_log_output)
        log_group.setLayout(log_layout)

        left_layout = QVBoxLayout()
        left_layout.addWidget(auto_group)
        left_layout.addLayout(config_actions_layout)
        left_layout.addWidget(result_group)
        left_layout.addWidget(log_group, stretch=1)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        layout = QHBoxLayout()
        layout.addWidget(left_widget, stretch=2)
        layout.addWidget(self._auto_serial_panel, stretch=1)
        tab.setLayout(layout)
        return tab

    def _build_analysis_tab(self) -> QWidget:
        tab = QWidget()

        source_group = QGroupBox("当前结果文件")
        source_layout = QHBoxLayout()
        source_layout.addWidget(self._analysis_result_path)
        source_layout.addWidget(self._analysis_browse_button)
        source_layout.addWidget(self._analysis_reload_button)
        source_group.setLayout(source_layout)

        filter_group = QGroupBox("过滤")
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("状态"))
        filter_layout.addWidget(self._analysis_status_filter)
        filter_layout.addWidget(QLabel("关键字"))
        filter_layout.addWidget(self._analysis_keyword_filter)
        filter_group.setLayout(filter_layout)

        table_group = QGroupBox("结果明细")
        table_layout = QVBoxLayout()
        table_layout.addWidget(self._analysis_table)
        table_group.setLayout(table_layout)

        layout = QVBoxLayout()
        layout.addWidget(source_group)
        layout.addWidget(filter_group)
        layout.addWidget(table_group, stretch=1)
        tab.setLayout(layout)
        return tab

    def _bind_events(self) -> None:
        self._is_dphy.toggled.connect(self._update_mode_dependent_fields)
        self._auto_is_dphy.toggled.connect(self._update_mode_dependent_fields)

        self._load_button.clicked.connect(self.load_manual_config)
        self._save_button.clicked.connect(self.save_manual_config)
        self._send_button.clicked.connect(self.send_manual_command)
        self._command_input.returnPressed.connect(self.send_manual_command)
        self._scan_adb_button.clicked.connect(self.scan_adb_devices)
        self._clear_log_button.clicked.connect(self.clear_manual_logs)
        self._read_current_params_button.clicked.connect(self.read_current_parameters)
        self._start_stream_debug_button.clicked.connect(self.start_stream_debug)
        self._stop_stream_debug_button.clicked.connect(self.stop_stream_debug)

        self._auto_load_button.clicked.connect(self.load_auto_config)
        self._auto_save_button.clicked.connect(self.save_auto_config)
        self._auto_clear_log_button.clicked.connect(self.clear_auto_logs)
        self._start_test_button.clicked.connect(self._start_auto_test)
        self._stop_test_button.clicked.connect(self._stop_auto_test)
        self._open_result_dir_button.clicked.connect(self._open_result_directory)
        self._view_result_button.clicked.connect(self._jump_to_analysis_tab)
        self._analysis_browse_button.clicked.connect(self._browse_analysis_file)
        self._analysis_reload_button.clicked.connect(self._load_result_file_into_analysis)
        self._analysis_status_filter.currentIndexChanged.connect(self._apply_analysis_filter)
        self._analysis_keyword_filter.textChanged.connect(self._apply_analysis_filter)

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
            auto_loop_count=self._auto_loop_count.value(),
        )

    def _collect_auto_config(self) -> AppConfig:
        return AppConfig(
            mode="auto",
            adb_device=self._selected_adb_device(),
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
            auto_manual_stream=self._auto_manual_stream.isChecked(),
            auto_loop_count=self._auto_loop_count.value(),
        )

    def _apply_manual_config(self, config: AppConfig) -> None:
        self._refresh_adb_devices(preferred=config.adb_device, should_log=False)
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
        self._refresh_adb_devices(preferred=config.adb_device, should_log=False)
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
        self._auto_manual_stream.setChecked(config.auto_manual_stream)
        self._auto_loop_count.setValue(config.auto_loop_count)
        self._update_mode_dependent_fields()

    def _parse_auto_sensor_modes(self) -> list[int]:
        selected_modes = [int(value) for value in self._auto_sensor_mode.selected_texts]
        return selected_modes or [0]

    def _selected_adb_device(self) -> str | None:
        current = self._adb_device_combo.currentText().strip()
        if not current or current not in self._adb_devices:
            return None
        return current

    def _selected_manual_adb_device(self) -> str | None:
        return self._selected_adb_device()

    def _selected_auto_adb_device(self) -> str | None:
        return self._selected_adb_device()

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
                message = f"Found {len(devices)} adb device(s)."
                self._append_manual_log(message)
                self._append_auto_log(message)
            return

        self._adb_device_combo.addItem("<no adb device>")
        self._adb_device_combo.setEnabled(False)
        if should_log:
            self._append_manual_log(f"ADB scan failed: {error}" if error else "No adb device found.")
            self._append_auto_log(f"ADB scan failed: {error}" if error else "No adb device found.")

    def scan_adb_devices(self) -> None:
        self._refresh_adb_devices(should_log=True)
        self._manual_serial_panel.refresh_devices()
        self._auto_serial_panel.refresh_devices()

    def _update_mode_dependent_fields(self) -> None:
        source = self.sender()
        if source is self._is_dphy and self._auto_is_dphy.isChecked() != self._is_dphy.isChecked():
            self._auto_is_dphy.blockSignals(True)
            self._auto_is_dphy.setChecked(self._is_dphy.isChecked())
            self._auto_is_dphy.blockSignals(False)
        elif source is self._auto_is_dphy and self._is_dphy.isChecked() != self._auto_is_dphy.isChecked():
            self._is_dphy.blockSignals(True)
            self._is_dphy.setChecked(self._auto_is_dphy.isChecked())
            self._is_dphy.blockSignals(False)

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

    def _with_step_send(
        self,
        field: QWidget,
        command: str,
        extra_widget: QWidget | None = None,
        *,
        range_text: str = "",
    ) -> QWidget:
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
        if range_text:
            layout.addWidget(QLabel(range_text))
        layout.addStretch(1)
        row.setLayout(layout)
        return row

    def _auto_range_row(
        self,
        start_widget: QWidget,
        end_widget: QWidget,
        extra_widget: QWidget | None = None,
        *,
        range_text: str = "",
    ) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("start"))
        start_widget.setMinimumWidth(90)
        end_widget.setMinimumWidth(90)
        layout.addWidget(start_widget)
        layout.addWidget(QLabel("end"))
        layout.addWidget(end_widget)
        if extra_widget is not None:
            layout.addWidget(extra_widget)
        if range_text:
            layout.addWidget(QLabel(range_text))
        layout.addStretch(1)
        row.setLayout(layout)
        return row

    def _with_auto_row(self, field: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field)
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
        self._append_log_with_timestamp(self._log_output, message)

    def _append_auto_log(self, message: str) -> None:
        self._append_log_with_timestamp(self._auto_log_output, message)

    @staticmethod
    def _append_log_with_timestamp(output: QTextEdit, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        lines = message.splitlines() or [message]
        output.append("\n".join(f"[{timestamp}] {line}" for line in lines))

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

    def read_current_parameters(self) -> None:
        if not self._selected_manual_adb_device():
            self._append_manual_log("No adb device selected. Please scan and choose one device first.")
            return

        read_commands = (
            "GET_CDR_DELAY",
            "GET_EQ_OFFSET",
            "GET_EQ_DG0_EN",
            "GET_EQ_SR0",
            "GET_EQ_DG1_EN",
            "GET_EQ_SR1",
            "GET_EQ_BW",
        )
        config = self._collect_manual_config()
        self._append_manual_log("开始读取当前参数...")
        for command in read_commands:
            response = self._command_processor.send(command, config)
            self._append_manual_log(response)

    def start_stream_debug(self) -> None:
        if not self._selected_manual_adb_device():
            self._append_manual_log("No adb device selected. Please scan and choose one device first.")
            return

        response = self._command_processor.start_stream_debug(self._collect_manual_config())
        self._append_manual_log(response)

    def stop_stream_debug(self) -> None:
        if not self._selected_manual_adb_device():
            self._append_manual_log("No adb device selected. Please scan and choose one device first.")
            return

        response = self._command_processor.stop_stream_debug(self._collect_manual_config())
        self._append_manual_log(response)

    def _start_auto_test(self) -> None:
        if self._auto_test_thread is not None:
            self._append_auto_log("自动化测试正在运行，请等待当前任务完成。")
            return

        if not self._selected_auto_adb_device():
            self._append_auto_log("No adb device selected. Please scan and choose one device first.")
            return

        config = self._collect_auto_config()
        range_errors = self._auto_range_errors(config)
        if range_errors:
            self._append_auto_log("自动化测试参数范围错误:\n" + "\n".join(range_errors))
            return

        self._start_test_button.setEnabled(False)
        self._stop_test_button.setEnabled(True)
        self._append_auto_log("自动化测试已启动。")

        self._auto_test_thread = QThread(self)
        self._auto_test_worker = _AutoTestWorker(self._command_processor, config)
        self._auto_test_worker.moveToThread(self._auto_test_thread)

        self._auto_test_thread.started.connect(self._auto_test_worker.run)
        self._auto_test_worker.finished.connect(self._on_auto_test_finished)
        self._auto_test_worker.failed.connect(self._on_auto_test_failed)
        self._auto_test_worker.progress.connect(self._append_auto_log)
        self._auto_test_worker.finished.connect(self._cleanup_auto_test_thread)
        self._auto_test_worker.failed.connect(self._cleanup_auto_test_thread)
        self._auto_test_thread.start()

    def _stop_auto_test(self) -> None:
        if self._auto_test_worker is None:
            self._append_auto_log("当前没有正在运行的自动化测试任务。")
            return
        self._auto_test_worker.request_stop()
        self._stop_test_button.setEnabled(False)
        self._append_auto_log("已发送停止请求，等待当前步骤结束...")

    def _on_auto_test_finished(self, response: str) -> None:
        self._append_auto_log(response)
        self._set_current_result_file(self._extract_result_file_path(response))

    def _on_auto_test_failed(self, error: str) -> None:
        self._append_auto_log(f"自动化测试执行失败: {error}")

    def _cleanup_auto_test_thread(self) -> None:
        if self._auto_test_thread is not None:
            self._auto_test_thread.quit()
            self._auto_test_thread.wait()
        self._auto_test_thread = None
        self._auto_test_worker = None
        self._start_test_button.setEnabled(True)
        self._stop_test_button.setEnabled(False)

    def _set_current_result_file(self, path: Path | None) -> None:
        self._current_result_file_path = path
        text = str(path.resolve()) if path is not None else ""
        self._result_file_input.setText(text)
        self._analysis_result_path.setText(text)

    @staticmethod
    def _extract_result_file_path(response: str) -> Path | None:
        patterns = [
            r"CSV 输出:\s*([^，\n]+)",
            r"输出文件:\s*([^\n]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, response)
            if not match:
                continue
            candidate = Path(match.group(1).strip())
            if candidate.exists():
                return candidate
        return None

    def _open_result_directory(self) -> None:
        if self._current_result_file_path is None:
            self._append_auto_log("当前没有可打开的结果文件路径。")
            return
        target_dir = self._current_result_file_path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_dir.resolve())))

    def _jump_to_analysis_tab(self) -> None:
        self._mode_tabs.setCurrentIndex(2)
        self._load_result_file_into_analysis()

    def _browse_analysis_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择结果文件",
            str((Path("configs") / "auto_test_outputs").resolve()),
            "Result Files (*.csv *.log *.txt);;CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return
        self._set_current_result_file(Path(file_path))
        self._load_result_file_into_analysis()

    def _load_result_file_into_analysis(self) -> None:
        if self._current_result_file_path is None:
            self._set_current_result_file(self._discover_latest_result_file())
        path = self._current_result_file_path
        if path is None or not path.exists():
            self._analysis_rows = []
            self._analysis_table.clear()
            self._analysis_table.setRowCount(0)
            self._analysis_table.setColumnCount(0)
            return

        if path.suffix.lower() == ".csv":
            self._analysis_rows = self._read_csv_rows(path)
        else:
            self._analysis_rows = self._read_text_rows(path)
        self._apply_analysis_filter()

    @staticmethod
    def _discover_latest_result_file() -> Path | None:
        output_dir = Path("configs") / "auto_test_outputs"
        if not output_dir.exists():
            return None
        candidates = [
            item
            for item in output_dir.iterdir()
            if item.is_file() and item.suffix.lower() in {".csv", ".txt", ".log"}
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.stat().st_mtime)

    @staticmethod
    def _read_csv_rows(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows: list[dict[str, str]] = []
            for row in reader:
                normalized = {key: str(value) for key, value in row.items() if key is not None}
                status_symbol = normalized.get("final_result", "")
                normalized["状态"] = {"O": "成功", "X": "失败", "P": "待定"}.get(status_symbol, "待定")
                rows.append(normalized)
            return rows

    @staticmethod
    def _read_text_rows(path: Path) -> list[dict[str, str]]:
        content = path.read_text(encoding="utf-8")
        chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]
        rows: list[dict[str, str]] = []
        for chunk in chunks:
            lines = chunk.splitlines()
            title = lines[0] if lines else ""
            status = "成功" if "SUCCESS" in chunk.upper() else ("失败" if "FAIL" in chunk.upper() else "待定")
            rows.append({"参数": title, "状态": status, "详情": chunk})
        return rows

    def _apply_analysis_filter(self) -> None:
        rows = self._analysis_rows
        status_text = self._analysis_status_filter.currentText()
        keyword = self._analysis_keyword_filter.text().strip().lower()

        def status_match(row: dict[str, str]) -> bool:
            status = row.get("状态", "待定")
            if status_text == "全部":
                return True
            if status_text == "仅成功":
                return status == "成功"
            if status_text == "失败":
                return status == "失败"
            return status == "待定"

        filtered: list[dict[str, str]] = []
        for row in rows:
            if not status_match(row):
                continue
            if keyword:
                haystack = " ".join(row.values()).lower()
                if keyword not in haystack:
                    continue
            filtered.append(row)

        headers = list(filtered[0].keys()) if filtered else list(rows[0].keys()) if rows else []
        self._analysis_table.clear()
        self._analysis_table.setRowCount(len(filtered))
        self._analysis_table.setColumnCount(len(headers))
        self._analysis_table.setHorizontalHeaderLabels(headers)
        for row_index, row in enumerate(filtered):
            for column_index, header in enumerate(headers):
                self._analysis_table.setItem(row_index, column_index, QTableWidgetItem(row.get(header, "")))

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
                errors.append(f"- {name}: start值({start}) 不能大于end值({end})")
        return errors


class _AutoTestWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, command_processor: CommandProcessor, config: AppConfig) -> None:
        super().__init__()
        self._command_processor = command_processor
        self._config = config
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True
        self.progress.emit("停止请求已接收。")

    def _should_stop(self) -> bool:
        return self._stop_requested

    def run(self) -> None:
        try:
            response = self._command_processor.run_automated_test(
                self._config,
                progress_callback=self.progress.emit,
                should_stop_callback=self._should_stop,
            )
        except Exception as error:  # noqa: BLE001
            self.failed.emit(str(error))
            return
        self.finished.emit(response)


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
