from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ai_office_vietnam.config import (
    DEFAULT_MODEL,
    AppSettings,
    get_api_key,
    normalize_model_name,
    save_api_key,
)
from ai_office_vietnam.services.gemini_service import GeminiService


class ConnectionWorker(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, api_key: str, model: str) -> None:
        super().__init__()
        self.api_key = api_key
        self.model = model

    def run(self) -> None:
        try:
            service = GeminiService(self.api_key, self.model)
            service.test_connection()
            self.succeeded.emit(service.model)
        except Exception as exc:
            self.failed.emit(str(exc))


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cài đặt - Đổi PDF sang Word (Băng Sơn)")
        self.setMinimumWidth(480)
        self.settings = settings
        self.worker: ConnectionWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        gemini_group = QGroupBox("Gemini AI")
        gemini_form = QFormLayout(gemini_group)
        self.use_ai = QCheckBox("Bật OCR ảnh/PDF scan, sửa chính tả và lỗi font")
        self.use_ai.setChecked(settings.use_ai)
        gemini_form.addRow(self.use_ai)
        self.api_key = QLineEdit(get_api_key())
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Dán Gemini API key")
        gemini_form.addRow("API key:", self.api_key)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItems([DEFAULT_MODEL, "gemini-3.5-flash"])
        self.model.setCurrentText(normalize_model_name(settings.model))
        gemini_form.addRow("Mô hình:", self.model)
        gemini_form.addRow(
            QLabel(
                "Khuyến nghị: Gemini 3.1 Flash-Lite. Ứng dụng tự thử model dự phòng khi model bị ngừng."
            )
        )
        self.chunk_pages = QSpinBox()
        self.chunk_pages.setRange(1, 12)
        self.chunk_pages.setValue(settings.chunk_pages)
        gemini_form.addRow("Trang PDF mỗi lượt:", self.chunk_pages)
        test_row = QHBoxLayout()
        self.test_button = QPushButton("Kiểm tra kết nối")
        self.test_status = QLabel("")
        test_row.addWidget(self.test_button)
        test_row.addWidget(self.test_status, 1)
        gemini_form.addRow(test_row)
        layout.addWidget(gemini_group)

        document_group = QGroupBox("Word đầu ra")
        form = QFormLayout(document_group)
        self.font_name = QLineEdit(settings.font_name)
        form.addRow("Font:", self.font_name)
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 24)
        self.font_size.setValue(settings.font_size)
        form.addRow("Cỡ chữ:", self.font_size)
        self.line_spacing = QDoubleSpinBox()
        self.line_spacing.setRange(1.0, 3.0)
        self.line_spacing.setSingleStep(0.1)
        self.line_spacing.setValue(settings.line_spacing)
        form.addRow("Giãn dòng:", self.line_spacing)
        self.preserve_images = QCheckBox("Giữ hình ảnh, chữ ký và con dấu trong PDF")
        self.preserve_images.setChecked(settings.preserve_images)
        form.addRow(self.preserve_images)
        form.addRow(QLabel("Mặc định A4; lề trái 3 cm, các lề còn lại 2 cm."))
        layout.addWidget(document_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.test_button.clicked.connect(self._test_connection)

    def _test_connection(self) -> None:
        key = self.api_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Thiếu API key", "Hãy nhập Gemini API key.")
            return
        self.test_button.setEnabled(False)
        self.test_status.setText("Đang kiểm tra…")
        self.worker = ConnectionWorker(key, self.model.currentText().strip())
        self.worker.succeeded.connect(self._connection_ok)
        self.worker.failed.connect(self._connection_failed)
        self.worker.start()

    def _connection_ok(self, active_model: str) -> None:
        self.test_button.setEnabled(True)
        self.model.setCurrentText(active_model)
        self.test_status.setText(f"Thành công ✓ ({active_model})")

    def _connection_failed(self, message: str) -> None:
        self.test_button.setEnabled(True)
        self.test_status.setText("Thất bại")
        QMessageBox.critical(self, "Lỗi Gemini", message)

    def accept(self) -> None:
        self.settings.use_ai = self.use_ai.isChecked()
        self.settings.model = normalize_model_name(self.model.currentText())
        self.settings.chunk_pages = self.chunk_pages.value()
        self.settings.font_name = self.font_name.text().strip() or "Times New Roman"
        self.settings.font_size = self.font_size.value()
        self.settings.line_spacing = self.line_spacing.value()
        self.settings.preserve_images = self.preserve_images.isChecked()
        save_api_key(self.api_key.text())
        self.settings.save()
        super().accept()
