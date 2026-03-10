from __future__ import annotations

import json
from pathlib import Path


class SerialBindingStore:
    """Persist ADB serial to PCUI port mapping."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (Path("configs") / "serial_bindings.json")

    def load(self) -> dict[str, str]:
        if not self._path.exists():
            return {}

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}

        bindings = raw.get("bindings", {}) if isinstance(raw, dict) else {}
        if not isinstance(bindings, dict):
            return {}

        return {
            str(serial).strip(): str(port).strip()
            for serial, port in bindings.items()
            if str(serial).strip() and str(port).strip()
        }

    def save(self, bindings: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "bindings": {
                serial: port
                for serial, port in bindings.items()
                if serial.strip() and port.strip()
            }
        }
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

