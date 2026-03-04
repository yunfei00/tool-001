from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)

    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "configs" / "default.yaml"

    window = MainWindow(config_path=config_path)
    window.show()

    auto_close_ms = os.getenv("TOOL001_AUTOCLOSE_MS")
    if auto_close_ms:
        QTimer.singleShot(int(auto_close_ms), app.quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
