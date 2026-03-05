from __future__ import annotations

import subprocess


class SeninfPathResolver:
    """Resolve seninf top path from Android device via adb."""

    def __init__(self, serial: str, adb_bin: str = "adb") -> None:
        self._serial = serial
        self._adb_bin = adb_bin

    def resolve(self) -> str:
        completed = subprocess.run(
            [
                self._adb_bin,
                "-s",
                self._serial,
                "shell",
                'cd /sys/devices/platform/; find . -name "*seninf*top" -type d',
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        find_result = completed.stdout.strip()
        if not find_result:
            stderr = completed.stderr.strip()
            if stderr:
                raise RuntimeError(f"Unable to locate seninf top path from device: {stderr}")
            raise RuntimeError("Unable to locate seninf top path from device.")

        # adb shell returns paths like './xxxx', normalize to absolute path.
        if find_result.startswith("./"):
            return "/sys/devices/platform/" + find_result[2:]

        if find_result.startswith("/"):
            return find_result

        return "/sys/devices/platform/" + find_result
