from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QSpinBox, QVBoxLayout, QWidget
)

from ai_office_vietnam.config import AppSettings, get_api_key, save_api_key
from ai_office_vietnam.services.converter import DocumentConverter


class Worker(QThread):
    progress = Signal(int, str)
    done = Signal(int, int)
    failed = Signal(str)

    def __init__(self, files: list[Path], output: Path, settings: AppSettings, api_key: str):
        super().__init__()
        self.files, self.output, self.settings, self.api_key = files, output, settings, api_key

    def run(self):
        ok = bad = 0
        converter = DocumentConverter()
        for index, file in enumerate(self.files):
            try:
                converter.convert(file, self.output, self.settings, self.api_key,
                                  lambda value, message, i=index: self.progress.emit(
                                      min(99, int((i + value / 100) / len(self.files) * 100)), message))
                ok += 1
            except Exception as exc:
                bad += 1
                self.failed.emit(f"{file.name}: {exc}")
        self.done.emit(ok, bad)


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Cài đặt Gemini và Word")
        form = QFormLayout(self)
        self.use_ai = QCheckBox("Bật Gemini sửa chính tả, lỗi font và đọc PDF scan")
        self.use_ai.setChecked(settings.use_ai)
        self.api_key = QLineEdit(get_api_key())
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.model = QLineEdit(settings.model)
        self.font = QLineEdit(settings.font_name)
        self.size = QSpinBox(); self.size.setRange(8, 24); self.size.setValue(settings.font_size)
        self.images = QCheckBox("Giữ hình ảnh, chữ ký và con dấu")
        self.images.setChecked(settings.preserve_images)
        form.addRow(self.use_ai)
        form.addRow("Gemini API key:", self.api_key)
        form.addRow("Mô hình:", self.model)
        form.addRow("Font:", self.font)
        form.addRow("Cỡ chữ:", self.size)
        form.addRow(self.images)
        form.addRow(QLabel("Khổ giấy cố định A4; lề trái 3 cm, các lề còn lại 2 cm."))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self):
        self.settings.use_ai = self.use_ai.isChecked()
        self.settings.model = self.model.text().strip() or "gemini-2.5-flash"
        self.settings.font_name = self.font.text().strip() or "Times New Roman"
        self.settings.font_size = self.size.value()
        self.settings.preserve_images = self.images.isChecked()
        save_api_key(self.api_key.text())
        self.settings.save()
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = AppSettings.load()
        self.worker = None
        self.setWindowTitle("AI Office Việt Nam — PDF sang Word")
        self.resize(850, 620)
        root = QVBoxLayout()
        title = QLabel("AI OFFICE VIỆT NAM")
        title.setStyleSheet("font-size:26px;font-weight:800;color:#174f91")
        root.addWidget(title)
        root.addWidget(QLabel("Chuyển PDF sang Word • Sửa chính tả • Khôi phục lỗi font • A4 Times New Roman"))
        row = QHBoxLayout()
        choose = QPushButton("Chọn file PDF")
        choose.clicked.connect(self.choose_files)
        settings = QPushButton("Cài đặt Gemini")
        settings.clicked.connect(self.open_settings)
        row.addWidget(choose); row.addWidget(settings); row.addStretch()
        root.addLayout(row)
        self.list = QListWidget(); self.list.setAcceptDrops(True)
        root.addWidget(self.list, 1)
        self.summary = QLabel(); root.addWidget(self.summary)
        self.progress = QProgressBar(); root.addWidget(self.progress)
        row2 = QHBoxLayout()
        output = QPushButton("Chọn thư mục lưu"); output.clicked.connect(self.choose_output)
        open_output = QPushButton("Mở thư mục kết quả"); open_output.clicked.connect(self.open_output)
        self.convert = QPushButton("CHUYỂN SANG WORD"); self.convert.clicked.connect(self.start)
        row2.addWidget(output); row2.addWidget(open_output); row2.addStretch(); row2.addWidget(self.convert)
        root.addLayout(row2)
        widget = QWidget(); widget.setLayout(root); self.setCentralWidget(widget)
        self.setStyleSheet("QWidget{font-family:'Segoe UI';font-size:10pt} QPushButton{padding:9px} QListWidget{background:white}")
        self.refresh()

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn PDF", "", "PDF (*.pdf)")
        existing = {self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())}
        for file in files:
            path = str(Path(file).resolve())
            if path not in existing:
                from PySide6.QtWidgets import QListWidgetItem
                item = QListWidgetItem(Path(path).name); item.setData(Qt.ItemDataRole.UserRole, path)
                self.list.addItem(item)
        self.refresh()

    def choose_output(self):
        selected = QFileDialog.getExistingDirectory(self, "Thư mục kết quả", self.settings.output_dir)
        if selected:
            self.settings.output_dir = selected; self.settings.save(); self.refresh()

    def open_settings(self):
        SettingsDialog(self.settings, self).exec(); self.refresh()

    def refresh(self):
        mode = self.settings.model if self.settings.use_ai else "Không AI"
        self.summary.setText(f"{self.list.count()} file • {mode} • A4 • {self.settings.font_name} {self.settings.font_size} • {self.settings.output_dir}")

    def start(self):
        files = [Path(self.list.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(self.list.count())]
        if not files:
            QMessageBox.information(self, "Chưa có file", "Hãy chọn ít nhất một file PDF."); return
        if self.settings.use_ai and not get_api_key():
            QMessageBox.warning(self, "Thiếu API key", "Hãy nhập Gemini API key trong Cài đặt."); return
        output = Path(self.settings.output_dir); output.mkdir(parents=True, exist_ok=True)
        self.convert.setEnabled(False)
        self.worker = Worker(files, output, self.settings, get_api_key())
        self.worker.progress.connect(lambda v, m: (self.progress.setValue(v), self.progress.setFormat(m)))
        self.worker.failed.connect(lambda m: QMessageBox.critical(self, "Lỗi chuyển đổi", m))
        self.worker.done.connect(self.finished)
        self.worker.start()

    def finished(self, ok: int, bad: int):
        self.convert.setEnabled(True); self.progress.setValue(100)
        self.progress.setFormat(f"Hoàn tất: {ok} thành công, {bad} lỗi")
        QMessageBox.information(self, "Hoàn tất", f"Đã tạo {ok} file Word. Lỗi: {bad}.")

    def open_output(self):
        path = Path(self.settings.output_dir); path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt": os.startfile(path)
