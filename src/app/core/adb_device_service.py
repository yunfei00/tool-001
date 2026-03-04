from __future__ import annotations

import subprocess


class AdbDeviceService:
    """Service for listing connected ADB device serial numbers."""

    def list_devices(self) -> tuple[list[str], str | None]:
        try:
            completed = subprocess.run(
                ["adb", "devices"],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return [], "adb command not found."

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            return [], stderr or "Failed to execute adb devices."

        devices: list[str] = []
        for line in completed.stdout.splitlines()[1:]:
            text = line.strip()
            if not text:
                continue
            parts = text.split()
            if len(parts) < 2:
                continue
            serial, status = parts[0], parts[1]
            if status == "device":
                devices.append(serial)

        return devices, None
