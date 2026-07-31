from __future__ import annotations

from pathlib import Path
from typing import Callable

from ai_office_vietnam.config import AppSettings
from ai_office_vietnam.models import ConversionResult
from ai_office_vietnam.services.gemini_service import GeminiService
from ai_office_vietnam.services.pdf_service import PDFService
from ai_office_vietnam.services.word_service import WordService


class DocumentConverter:
    def __init__(self) -> None:
        self.pdf = PDFService()
        self.word = WordService()

    def convert(self, pdf_path: Path, output_dir: Path, settings: AppSettings, api_key: str,
                progress_callback: Callable[[int, str], None] | None = None) -> ConversionResult:
        progress = progress_callback or (lambda _v, _m: None)
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
                    progress(5 + int(index / max(1, len(chunks)) * 70), f"Đang xử lý trang {start}-{end}…")
                    pages.extend(gemini.process_pdf_chunk(chunk, start, end))
        else:
            pages = self.pdf.extract_local_pages(pdf_path)
            if sum(len(p.markdown) for p in pages) < max(80, info.page_count * 20):
                raise ValueError("PDF này có vẻ là bản scan. Hãy bật Gemini.")
        progress(82, "Đang tạo Word A4 Times New Roman…")
        output = self._unique(output_dir, pdf_path.stem)
        images = self.pdf.extract_images(pdf_path) if settings.preserve_images else {}
        self.word.create_document(pages, output, settings, images)
        corrections = [f"Trang {p.page_number}: {c}" for p in pages for c in p.corrections]
        log = None
        if corrections:
            log = output.with_name(output.stem + " - Nhat ky sua loi.txt")
            log.write_text("\n".join(corrections), encoding="utf-8")
        progress(100, f"Đã tạo {output.name}")
        return ConversionResult(pdf_path, output, log, info.page_count, len(corrections))

    @staticmethod
    def _unique(folder: Path, stem: str) -> Path:
        path = folder / f"{stem}.docx"
        index = 2
        while path.exists():
            path = folder / f"{stem} ({index}).docx"
            index += 1
        return path
