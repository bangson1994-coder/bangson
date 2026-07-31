from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from ai_office_vietnam.ui.main_window import MainWindow

APP_DISPLAY_NAME = "Đổi PDF sang Word (Băng Sơn)"


def main() -> int:
    QCoreApplication.setOrganizationName("BangSon")
    QCoreApplication.setApplicationName("AI Office Việt Nam")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    try:
        window = MainWindow()
        window.show()
        return app.exec()
    except Exception as exc:
        QMessageBox.critical(
            None,
            APP_DISPLAY_NAME,
            f"Không thể khởi động ứng dụng:\n{exc}",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
