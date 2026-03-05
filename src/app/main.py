from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def _project_root() -> Path:
    """Resolve project root for source run and PyInstaller frozen app."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _config_path() -> Path:
    root = _project_root()
    bundled_config = root / "configs" / "default.yaml"
    if bundled_config.exists():
        return bundled_config

    external_config_dir = Path.home() / ".tool-001" / "configs"
    external_config_dir.mkdir(parents=True, exist_ok=True)
    return external_config_dir / "default.yaml"


def main() -> int:
    app = QApplication(sys.argv)

    window = MainWindow(config_path=_config_path())
    window.show()

    auto_close_ms = os.getenv("TOOL001_AUTOCLOSE_MS")
    if auto_close_ms:
        QTimer.singleShot(int(auto_close_ms), app.quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
