from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.services.serial.serial_command_service import SerialCommandService
from app.core.services.serial.serial_port_service import SerialPortService
from app.core.adb_device_service import AdbDeviceService


class SerialCommandPanel(QWidget):
    def __init__(self, title: str = "通用串口 AT 命令") -> None:
        super().__init__()
        self._port_service = SerialPortService()
        self._command_service = SerialCommandService(self._port_service)
        self._adb_device_service = AdbDeviceService()

        self._title = QGroupBox(title)
        self._adb_device_combo = QComboBox()
        self._refresh_adb_button = QPushButton("扫描 ADB")
        self._adb_devices: list[str] = []

        self._port_combo = QComboBox()
        self._refresh_port_button = QPushButton("扫描串口")

        self._baudrate_combo = QComboBox()
        self._baudrate_combo.setEditable(True)
        self._baudrate_combo.addItems(["9600", "115200", "230400", "460800", "921600"])
        self._baudrate_combo.setCurrentText("9600")

        self._open_port_button = QPushButton("打开串口")
        self._close_port_button = QPushButton("关闭串口")
        self._close_port_button.setEnabled(False)

        self._command_editor = QTextEdit()
        self._command_editor.setPlaceholderText("支持手工输入/导入，一行一条命令，空行自动忽略")
        self._command_editor.setPlainText(self._command_service.default_commands_text())

        self._import_button = QPushButton("导入命令")
        self._send_button = QPushButton("发送命令")

        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)
        self._clear_log_button = QPushButton("清除日志")

        self._last_binding_hint = ""
        self._last_device_snapshot: tuple[tuple[str, ...], tuple[str, ...]] | None = None
        self._device_watch_timer = QTimer(self)
        self._device_watch_timer.setInterval(2000)

        self._build_ui()
        self._bind_events()
        self._refresh_adb_devices()
        self._refresh_ports()
        self._device_watch_timer.start()

    def _build_ui(self) -> None:
        form = QFormLayout()
        adb_row = QHBoxLayout()
        adb_row.addWidget(self._adb_device_combo)
        adb_row.addWidget(self._refresh_adb_button)
        form.addRow("ADB 设备", self._with_layout_widget(adb_row))

        port_row = QHBoxLayout()
        port_row.addWidget(self._port_combo)
        port_row.addWidget(self._refresh_port_button)
        form.addRow("串口", self._with_layout_widget(port_row))
        form.addRow("波特率", self._baudrate_combo)

        port_actions = QHBoxLayout()
        port_actions.addWidget(self._open_port_button)
        port_actions.addWidget(self._close_port_button)
        port_actions.addStretch(1)
        form.addRow("串口操作", self._with_layout_widget(port_actions))

        command_group = QGroupBox("命令输入")
        command_layout = QVBoxLayout()
        command_actions = QHBoxLayout()
        command_actions.addWidget(self._import_button)
        command_actions.addWidget(self._send_button)
        command_actions.addStretch(1)
        command_layout.addLayout(command_actions)
        command_layout.addWidget(self._command_editor)
        command_group.setLayout(command_layout)

        log_group = QGroupBox("串口日志")
        log_layout = QVBoxLayout()
        log_actions = QHBoxLayout()
        log_actions.addStretch(1)
        log_actions.addWidget(self._clear_log_button)
        log_layout.addLayout(log_actions)
        log_layout.addWidget(self._log_output)
        log_group.setLayout(log_layout)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(command_group)
        layout.addWidget(log_group)
        self._title.setLayout(layout)

        root = QVBoxLayout()
        root.addWidget(self._title)
        self.setLayout(root)

    def _bind_events(self) -> None:
        self._refresh_adb_button.clicked.connect(self._refresh_adb_devices)
        self._refresh_port_button.clicked.connect(self._refresh_ports)
        self._adb_device_combo.currentIndexChanged.connect(self._refresh_ports)
        self._import_button.clicked.connect(self._import_commands)
        self._open_port_button.clicked.connect(self._open_serial_port)
        self._close_port_button.clicked.connect(self._close_serial_port)
        self._send_button.clicked.connect(self._send_commands)
        self._clear_log_button.clicked.connect(self._log_output.clear)
        self._device_watch_timer.timeout.connect(self._watch_device_topology)

    def _refresh_adb_devices(self, *, should_log: bool = True) -> None:
        devices, _ = self._adb_device_service.list_devices()
        previous = self._adb_device_combo.currentText().strip()
        self._adb_devices = devices

        self._adb_device_combo.blockSignals(True)
        self._adb_device_combo.clear()
        if devices:
            self._adb_device_combo.addItems(devices)
            self._adb_device_combo.setEnabled(True)
            if previous in devices:
                self._adb_device_combo.setCurrentText(previous)
            elif len(devices) == 1:
                self._adb_device_combo.setCurrentText(devices[0])
            self._adb_device_combo.blockSignals(False)
            self._refresh_ports()
            return

        self._adb_device_combo.addItem("<no adb device>")
        self._adb_device_combo.setEnabled(False)
        self._adb_device_combo.blockSignals(False)
        if should_log:
            self._append_log("未检测到 ADB 设备")
        self._refresh_ports()

    def _refresh_ports(self) -> None:
        self._port_combo.clear()
        ports = self._port_service.list_available_ports()
        selected_adb = self._adb_device_combo.currentText().strip()

        pcui_ports = [
            port
            for port in ports
            if "pcui" in (port["description"] or "").lower()
        ]

        matched_ports = []
        if len(self._adb_devices) == 1 and len(pcui_ports) == 1:
            matched_ports = [pcui_ports[0]]
            self._append_binding_hint("已自动绑定唯一设备与 PCUI 串口")
        elif len(self._adb_devices) > 1 or len(pcui_ports) > 1:
            self._append_binding_hint("检测到多台 USB 设备，请移除多余设备，仅保留一台后再绑定")
        elif selected_adb and selected_adb != "<no adb device>":
            for port in pcui_ports:
                serial_number = (port["serial_number"] or "").strip()
                if serial_number and serial_number == selected_adb:
                    matched_ports.append(port)
            if matched_ports:
                self._append_binding_hint("已按序列号匹配 PCUI 串口")

        for port in matched_ports:
            label = (
                f"{port['port']} | {port['description'] or '-'} | {port['hwid'] or '-'}"
                f" | SN:{port['serial_number'] or '-'}"
            )
            self._port_combo.addItem(label, port["port"])

        if not matched_ports:
            self._append_log("未扫描到匹配的 PCUI 串口")

    def refresh_devices(self) -> None:
        self._refresh_adb_devices()
        self._refresh_ports()

    def _watch_device_topology(self) -> None:
        devices, _ = self._adb_device_service.list_devices()
        ports = self._port_service.list_available_ports()
        pcui_names = tuple(
            sorted(
                port["port"]
                for port in ports
                if "pcui" in (port["description"] or "").lower()
            )
        )
        snapshot = (tuple(sorted(devices)), pcui_names)
        if snapshot == self._last_device_snapshot:
            return
        self._last_device_snapshot = snapshot
        self._refresh_adb_devices(should_log=False)

    def _append_binding_hint(self, message: str) -> None:
        if message == self._last_binding_hint:
            return
        self._last_binding_hint = message
        self._append_log(message)

    def _import_commands(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "导入 AT 命令",
            "",
            "Command Files (*.txt *.json)",
        )
        if not selected:
            return
        try:
            commands = self._command_service.load_commands_from_file(Path(selected))
        except Exception as error:  # noqa: BLE001
            self._append_log(f"导入失败: {error}")
            return

        self._command_editor.setPlainText("\n".join(commands))
        self._append_log(f"导入完成，共 {len(commands)} 条命令")

    def _build_settings(self):
        port = self._port_combo.currentData()
        return self._port_service.validate_settings(
            {
                "port": port,
                "baudrate": self._baudrate_combo.currentText(),
            }
        )

    def _open_serial_port(self) -> None:
        try:
            settings = self._build_settings()
            self._command_service.open_connection(settings)
        except Exception as error:  # noqa: BLE001
            self._append_log(f"打开串口失败: {error}")
            return

        self._open_port_button.setEnabled(False)
        self._close_port_button.setEnabled(True)
        self._append_log(f"串口已打开: {settings.port}")

    def _close_serial_port(self) -> None:
        opened_port = self._command_service.opened_port
        self._command_service.close_connection()
        self._open_port_button.setEnabled(True)
        self._close_port_button.setEnabled(False)
        if opened_port:
            self._append_log(f"串口已关闭: {opened_port}")

    def _send_commands(self) -> None:
        commands = self._command_service.parse_commands(self._command_editor.toPlainText())
        if not commands:
            self._append_log("没有可发送的命令")
            return

        try:
            results = self._command_service.send_with_opened_connection(commands)
        except Exception as error:  # noqa: BLE001
            self._append_log(f"发送失败: {error}")
            return

        port = self._command_service.opened_port or "-"
        for item in results:
            status = "成功" if item["success"] else "失败"
            log_line = (
                f"[{item['timestamp']}] 端口={port} 命令={item['command']} 状态={status} "
                f"返回={item['response'] or '-'} 错误={item['error'] or '-'}"
            )
            self._append_log(log_line)

    def _append_log(self, message: str) -> None:
        self._log_output.append(message)

    @staticmethod
    def _with_layout_widget(layout: QHBoxLayout) -> QWidget:
        wrapper = QWidget()
        wrapper.setLayout(layout)
        return wrapper
