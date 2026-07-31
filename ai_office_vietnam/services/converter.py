from __future__ import annotations

from pathlib import Path
from typing import Callable

from ai_office_vietnam.config import AppSettings
from ai_office_vietnam.models import ConversionResult
from ai_office_vietnam.services.gemini_service import GeminiService
from ai_office_vietnam.services.pdf_service import PDFService
from ai_office_vietnam.services.word_service import WordService

ProgressCallback = Callable[[int, str], None]
CancelCallback = Callable[[], bool]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


class ConversionCancelled(Exception):
    pass


class DocumentConverter:
    def __init__(self) -> None:
        self.pdf = PDFService()
        self.word = WordService()

    def convert(
        self,
        input_path: Path,
        output_dir: Path,
        settings: AppSettings,
        api_key: str,
        progress_callback: ProgressCallback | None = None,
        is_cancelled: CancelCallback | None = None,
    ) -> ConversionResult:
        progress = progress_callback or (lambda _v, _m: None)
        cancelled = is_cancelled or (lambda: False)
        suffix = input_path.suffix.lower()
        if suffix == ".pdf":
            return self._convert_pdf(input_path, output_dir, settings, api_key, progress, cancelled)
        if suffix in IMAGE_EXTENSIONS:
            return self._convert_image(input_path, output_dir, settings, api_key, progress, cancelled)
        raise ValueError(f"Định dạng chưa được hỗ trợ: {input_path.suffix}")

    def _convert_pdf(
        self,
        pdf_path: Path,
        output_dir: Path,
        settings: AppSettings,
        api_key: str,
        progress: ProgressCallback,
        cancelled: CancelCallback,
    ) -> ConversionResult:
        progress(2, f"Đang kiểm tra {pdf_path.name}…")
        info = self.pdf.inspect(pdf_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        pages = []
        if settings.use_ai:
            if not api_key:
                raise ValueError("Chưa nhập Gemini API key.")
            gemini = GeminiService(api_key, settings.model)
            with self.pdf.temporary_directory() as temp_name:
                chunks = list(self.pdf.chunk_files(pdf_path, settings.chunk_pages, Path(temp_name)))
                for index, (chunk, start, end) in enumerate(chunks):
                    if cancelled():
                        raise ConversionCancelled()
                    chunk_start = 4 + int(index / max(1, len(chunks)) * 76)
                    chunk_span = max(8, int(76 / max(1, len(chunks))))
                    pages.extend(
                        gemini.process_pdf_chunk(
                            chunk,
                            start,
                            end,
                            status_callback=lambda value, message, base=chunk_start, span=chunk_span: progress(
                                min(80, base + int(value * span / 100)), message
                            ),
                        )
                    )
        else:
            pages = self.pdf.extract_local_pages(pdf_path)
            if sum(len(p.markdown) for p in pages) < max(80, info.page_count * 20):
                raise ValueError("PDF này có vẻ là bản scan. Hãy bật Gemini.")

        if cancelled():
            raise ConversionCancelled()
        progress(84, "Đang tạo Word A4, font Times New Roman…")
        output = self._unique(output_dir, pdf_path.stem)
        images = self.pdf.extract_images(pdf_path) if settings.preserve_images else {}
        self.word.create_document(pages, output, settings, images)
        log = self._write_corrections(output, pages)
        progress(100, f"Hoàn tất: {output.name} ✓")
        correction_count = sum(len(page.corrections) for page in pages)
        return ConversionResult(pdf_path, output, log, info.page_count, correction_count)

    def _convert_image(
        self,
        image_path: Path,
        output_dir: Path,
        settings: AppSettings,
        api_key: str,
        progress: ProgressCallback,
        cancelled: CancelCallback,
    ) -> ConversionResult:
        if not settings.use_ai:
            raise ValueError("Chuyển ảnh sang Word cần bật Gemini trong Cài đặt.")
        if not api_key:
            raise ValueError("Chưa nhập Gemini API key.")
        if cancelled():
            raise ConversionCancelled()
        output_dir.mkdir(parents=True, exist_ok=True)
        gemini = GeminiService(api_key, settings.model)
        pages = gemini.process_image(image_path, status_callback=progress)
        if cancelled():
            raise ConversionCancelled()
        progress(92, "Đang tạo Word A4, font Times New Roman…")
        output = self._unique(output_dir, image_path.stem)
        self.word.create_document(pages, output, settings)
        log = self._write_corrections(output, pages)
        progress(100, f"Hoàn tất: {output.name} ✓")
        correction_count = sum(len(page.corrections) for page in pages)
        return ConversionResult(image_path, output, log, 1, correction_count)

    @staticmethod
    def _write_corrections(output: Path, pages) -> Path | None:
        corrections = [f"Trang {p.page_number}: {c}" for p in pages for c in p.corrections]
        if not corrections:
            return None
        log = output.with_name(output.stem + " - Nhat ky sua loi.txt")
        log.write_text("\n".join(corrections), encoding="utf-8")
        return log

    @staticmethod
    def _unique(folder: Path, stem: str) -> Path:
        path = folder / f"{stem}.docx"
        index = 2
        while path.exists():
            path = folder / f"{stem} ({index}).docx"
            index += 1
        return path
