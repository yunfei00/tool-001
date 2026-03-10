from __future__ import annotations

from pathlib import Path

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

        self._build_ui()
        self._bind_events()
        self._refresh_adb_devices()
        self._refresh_ports()

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

    def _refresh_adb_devices(self) -> None:
        devices, _ = self._adb_device_service.list_devices()
        self._adb_devices = devices
        self._adb_device_combo.clear()
        if devices:
            self._adb_device_combo.addItems(devices)
            self._adb_device_combo.setEnabled(True)
            self._refresh_ports()
            return

        self._adb_device_combo.addItem("<no adb device>")
        self._adb_device_combo.setEnabled(False)
        self._refresh_ports()

    def _refresh_ports(self) -> None:
        self._port_combo.clear()
        ports = self._port_service.list_available_ports()
        selected_adb = self._adb_device_combo.currentText().strip()

        matched_ports = []
        for port in ports:
            description = (port["description"] or "").lower()
            serial_number = (port["serial_number"] or "").strip()
            if "pcui" not in description:
                continue
            if selected_adb and selected_adb != "<no adb device>" and serial_number != selected_adb:
                continue
            matched_ports.append(port)

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
