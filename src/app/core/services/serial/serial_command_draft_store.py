from __future__ import annotations

from pathlib import Path


class SerialCommandDraftStore:
    """Persist the serial command editor draft across app restarts."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (Path("configs") / "serial_command_draft.txt")

    def load(self) -> str:
        if not self._path.exists():
            return ""
        try:
            return self._path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            return ""

    def save(self, content: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(content, encoding="utf-8")
