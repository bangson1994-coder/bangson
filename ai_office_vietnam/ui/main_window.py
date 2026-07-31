from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ai_office_vietnam.config import AppSettings, get_api_key
from ai_office_vietnam.models import ConversionResult
from ai_office_vietnam.services.converter import (
    IMAGE_EXTENSIONS,
    ConversionCancelled,
    DocumentConverter,
)
from ai_office_vietnam.ui.settings_dialog import SettingsDialog

APP_NAME = "Đổi PDF sang Word (Băng Sơn)"
SUPPORTED_EXTENSIONS = {".pdf", *IMAGE_EXTENSIONS}
FILE_FILTER = "PDF và ảnh (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)"


class DropArea(QFrame):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setMinimumHeight(78)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        title = QLabel("Kéo thả PDF hoặc ảnh vào đây")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("dropTitle")
        sub = QLabel("PDF, JPG, PNG, WEBP, BMP, TIFF • Có thể chọn nhiều file")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setObjectName("dropSub")
        layout.addWidget(title)
        layout.addWidget(sub)

    @staticmethod
    def _supported(path: str) -> bool:
        return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(
            self._supported(url.toLocalFile()) for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if self._supported(url.toLocalFile())
        ]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()


class ConversionWorker(QThread):
    progress = Signal(int, int, str)
    file_started = Signal(str, int, int)
    file_finished = Signal(object)
    file_failed = Signal(str, str)
    all_finished = Signal(int, int, bool)

    def __init__(
        self,
        files: list[Path],
        output_dir: Path,
        settings: AppSettings,
        api_key: str,
    ) -> None:
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.settings = settings
        self.api_key = api_key
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        succeeded = failed = 0
        converter = DocumentConverter()
        total = max(1, len(self.files))
        for index, input_path in enumerate(self.files):
            if self._cancelled:
                break
            self.file_started.emit(input_path.name, index + 1, total)
            try:
                result = converter.convert(
                    input_path,
                    self.output_dir,
                    self.settings,
                    self.api_key,
                    progress_callback=lambda value, message, i=index: self.progress.emit(
                        value,
                        min(99, int(((i + value / 100) / total) * 100)),
                        message,
                    ),
                    is_cancelled=lambda: self._cancelled,
                )
                succeeded += 1
                self.file_finished.emit(result)
            except ConversionCancelled:
                break
            except Exception as exc:
                failed += 1
                self.file_failed.emit(str(input_path), str(exc))
        self.all_finished.emit(succeeded, failed, self._cancelled)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = AppSettings.load()
        self.worker: ConversionWorker | None = None
        self.errors: list[str] = []
        self.setWindowTitle(APP_NAME)
        self.resize(740, 525)
        self.setMinimumSize(650, 455)
        self._build_ui()
        self._apply_styles()
        self._refresh_summary()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("ĐỔI PDF SANG WORD")
        title.setObjectName("appTitle")
        subtitle = QLabel("Băng Sơn • OCR tiếng Việt • A4 Times New Roman")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        self.settings_button = QPushButton("Cài đặt")
        self.settings_button.clicked.connect(self._open_settings)
        header.addWidget(self.settings_button)
        root.addLayout(header)

        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self._add_files)
        root.addWidget(self.drop_area)

        toolbar = QHBoxLayout()
        self.add_button = QPushButton("Chọn PDF/ảnh")
        self.remove_button = QPushButton("Xóa chọn")
        self.clear_button = QPushButton("Xóa hết")
        self.output_button = QPushButton("Thư mục lưu")
        self.add_button.clicked.connect(self._choose_files)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self._clear_files)
        self.output_button.clicked.connect(self._choose_output)
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.remove_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addStretch()
        toolbar.addWidget(self.output_button)
        root.addLayout(toolbar)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setMinimumHeight(105)
        root.addWidget(self.file_list, 1)

        self.summary = QLabel()
        self.summary.setObjectName("summary")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.current_file = QLabel("Sẵn sàng")
        self.current_file.setObjectName("currentFile")
        root.addWidget(self.current_file)

        progress_row = QHBoxLayout()
        upload_box = QVBoxLayout()
        upload_box.setSpacing(2)
        upload_box.addWidget(QLabel("Đính tệp lên Gemini"))
        self.upload_progress = QProgressBar()
        self.upload_progress.setRange(0, 100)
        self.upload_progress.setValue(0)
        self.upload_progress.setFormat("Chưa bắt đầu")
        upload_box.addWidget(self.upload_progress)
        overall_box = QVBoxLayout()
        overall_box.setSpacing(2)
        overall_box.addWidget(QLabel("Tiến trình xử lý"))
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("0%")
        overall_box.addWidget(self.overall_progress)
        progress_row.addLayout(upload_box, 1)
        progress_row.addLayout(overall_box, 1)
        root.addLayout(progress_row)

        action = QHBoxLayout()
        self.open_output_button = QPushButton("Mở kết quả")
        self.open_output_button.clicked.connect(self._open_output)
        self.cancel_button = QPushButton("Dừng")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        self.convert_button = QPushButton("CHUYỂN SANG WORD")
        self.convert_button.setObjectName("primaryButton")
        self.convert_button.clicked.connect(self._start_conversion)
        action.addWidget(self.open_output_button)
        action.addStretch()
        action.addWidget(self.cancel_button)
        action.addWidget(self.convert_button)
        root.addLayout(action)

        self.setCentralWidget(central)

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI'; font-size: 9.5pt; }
            QMainWindow { background: #f6f7fa; }
            #appTitle { font-size: 17pt; font-weight: 800; color: #163a70; }
            #subtitle { color: #687180; font-size: 9pt; }
            #dropArea { background: white; border: 1.5px dashed #7294c3; border-radius: 8px; }
            #dropTitle { font-size: 12pt; font-weight: 700; color: #245b9e; }
            #dropSub { color: #687180; font-size: 8.5pt; }
            QListWidget { background: white; border: 1px solid #d7dce5; border-radius: 6px; padding: 3px; }
            QPushButton { padding: 6px 10px; border: 1px solid #c5ccd8; border-radius: 6px; background: white; }
            QPushButton:hover { background: #eef4ff; border-color: #7ca1d5; }
            QPushButton:disabled { color: #9ba3af; background: #eeeeee; }
            #primaryButton { background: #1f5fae; color: white; font-weight: 700; border: none; padding: 8px 16px; }
            #primaryButton:hover { background: #174d91; }
            #summary { color: #374151; background: #eaf1fb; border-radius: 5px; padding: 5px 7px; }
            #currentFile { color: #374151; font-weight: 600; }
            QProgressBar { border: 1px solid #cbd2dc; border-radius: 5px; text-align: center; background: white; height: 18px; font-size: 8.5pt; }
            QProgressBar::chunk { background: #2d72c4; border-radius: 4px; }
        """)

    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn PDF hoặc ảnh", "", FILE_FILTER)
        self._add_files(files)

    def _add_files(self, files: list[str]) -> None:
        existing = {
            self.file_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.file_list.count())
        }
        for file in files:
            path_obj = Path(file).resolve()
            path = str(path_obj)
            if (
                path in existing
                or not path_obj.is_file()
                or path_obj.suffix.lower() not in SUPPORTED_EXTENSIONS
            ):
                continue
            kind = "PDF" if path_obj.suffix.lower() == ".pdf" else "Ảnh"
            item = QListWidgetItem(f"{kind}  •  {path_obj.name}")
            item.setToolTip(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.file_list.addItem(item)
            existing.add(path)
        self._refresh_summary()

    def _remove_selected(self) -> None:
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
        self._refresh_summary()

    def _clear_files(self) -> None:
        self.file_list.clear()
        self._refresh_summary()

    def _choose_output(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Chọn thư mục lưu", self.settings.output_dir
        )
        if selected:
            self.settings.output_dir = selected
            self.settings.save()
            self._refresh_summary()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.settings
            self._refresh_summary()

    def _refresh_summary(self) -> None:
        pdf_count = image_count = 0
        for index in range(self.file_list.count()):
            path = Path(self.file_list.item(index).data(Qt.ItemDataRole.UserRole))
            if path.suffix.lower() == ".pdf":
                pdf_count += 1
            else:
                image_count += 1
        mode = self.settings.model if self.settings.use_ai else "Không AI"
        self.summary.setText(
            f"{pdf_count} PDF • {image_count} ảnh • {mode} • A4 • "
            f"{self.settings.font_name} {self.settings.font_size}"
        )

    def _start_conversion(self) -> None:
        files = [
            Path(self.file_list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.file_list.count())
        ]
        if not files:
            QMessageBox.information(self, "Chưa có tệp", "Hãy chọn ít nhất một file PDF hoặc ảnh.")
            return
        has_image = any(path.suffix.lower() in IMAGE_EXTENSIONS for path in files)
        if has_image and not self.settings.use_ai:
            QMessageBox.warning(
                self,
                "Cần bật Gemini",
                "Chuyển ảnh sang Word cần bật Gemini trong Cài đặt.",
            )
            return
        if self.settings.use_ai and not get_api_key():
            QMessageBox.warning(self, "Thiếu API key", "Hãy nhập Gemini API key trong Cài đặt.")
            return

        output = Path(self.settings.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        self.errors.clear()
        self._set_busy(True)
        self.upload_progress.setValue(0)
        self.upload_progress.setFormat("Đang chờ")
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("0%")
        self.worker = ConversionWorker(files, output, self.settings, get_api_key())
        self.worker.file_started.connect(self._file_started)
        self.worker.progress.connect(self._on_progress)
        self.worker.file_finished.connect(self._file_finished)
        self.worker.file_failed.connect(self._file_failed)
        self.worker.all_finished.connect(self._all_finished)
        self.worker.start()

    def _file_started(self, name: str, current: int, total: int) -> None:
        self.current_file.setText(f"Tệp {current}/{total}: {name}")
        self.upload_progress.setValue(0)
        self.upload_progress.setFormat("Đang chờ tải")

    def _on_progress(self, file_value: int, overall_value: int, message: str) -> None:
        self.overall_progress.setValue(overall_value)
        self.overall_progress.setFormat(f"{overall_value}% • {message}")
        lowered = message.lower()
        if "đang tải lên gemini" in lowered or "đang chuẩn bị ảnh" in lowered:
            self.upload_progress.setValue(12)
            self.upload_progress.setFormat("Đang tải…")
        elif "tải lên hoàn thành" in lowered:
            self.upload_progress.setValue(100)
            self.upload_progress.setFormat("Hoàn thành ✓")
        elif "tệp đính kèm đã sẵn sàng" in lowered:
            self.upload_progress.setValue(100)
            self.upload_progress.setFormat("Sẵn sàng ✓")
        elif not self.settings.use_ai:
            self.upload_progress.setValue(100)
            self.upload_progress.setFormat("Không cần tải AI")

    def _file_finished(self, result: ConversionResult) -> None:
        self.current_file.setText(f"Đã tạo: {result.output_path.name} ✓")

    def _file_failed(self, file_path: str, message: str) -> None:
        self.errors.append(f"{Path(file_path).name}: {message}")

    def _all_finished(self, succeeded: int, failed: int, cancelled: bool) -> None:
        self._set_busy(False)
        if cancelled:
            self.current_file.setText("Đã dừng theo yêu cầu")
            self.overall_progress.setFormat("Đã dừng")
            return
        self.overall_progress.setValue(100)
        self.overall_progress.setFormat(f"Hoàn tất • {succeeded} thành công • {failed} lỗi")
        if self.settings.use_ai and succeeded:
            self.upload_progress.setValue(100)
            self.upload_progress.setFormat("Hoàn thành ✓")
        details = ""
        if self.errors:
            details = "\n\n" + "\n".join(self.errors[:8])
        QMessageBox.information(
            self,
            "Hoàn tất",
            f"Đã tạo {succeeded} file Word. Lỗi: {failed}.{details}",
        )

    def _cancel(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.current_file.setText("Đang dừng sau bước hiện tại…")

    def _set_busy(self, busy: bool) -> None:
        self.convert_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        for widget in (
            self.add_button,
            self.remove_button,
            self.clear_button,
            self.output_button,
            self.settings_button,
        ):
            widget.setEnabled(not busy)

    def _open_output(self) -> None:
        path = Path(self.settings.output_dir)
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(path)
