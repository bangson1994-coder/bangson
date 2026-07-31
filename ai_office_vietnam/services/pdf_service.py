from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import fitz

from ai_office_vietnam.models import PageContent
from ai_office_vietnam.services.text_normalizer import normalize_text


@dataclass(slots=True)
class PDFInfo:
    page_count: int
    file_size_bytes: int
    extracted_characters: int


class PDFService:
    def inspect(self, pdf_path: Path) -> PDFInfo:
        with fitz.open(pdf_path) as doc:
            extracted = sum(len(page.get_text("text")) for page in doc)
            return PDFInfo(doc.page_count, pdf_path.stat().st_size, extracted)

    def extract_local_pages(self, pdf_path: Path) -> list[PageContent]:
        pages: list[PageContent] = []
        with fitz.open(pdf_path) as doc:
            for index, page in enumerate(doc):
                blocks = page.get_text("blocks", sort=True)
                text_blocks = [normalize_text(str(block[4])) for block in blocks if len(block) > 4]
                pages.append(PageContent(index + 1, "\n\n".join(v for v in text_blocks if v)))
        return pages

    def chunk_files(self, pdf_path: Path, chunk_pages: int, temp_dir: Path) -> Iterator[tuple[Path, int, int]]:
        chunk_pages = max(1, chunk_pages)
        with fitz.open(pdf_path) as source:
            for start in range(0, source.page_count, chunk_pages):
                end = min(start + chunk_pages - 1, source.page_count - 1)
                target = fitz.open()
                target.insert_pdf(source, from_page=start, to_page=end)
                chunk_path = temp_dir / f"chunk_{start + 1:04d}_{end + 1:04d}.pdf"
                target.save(chunk_path, garbage=4, deflate=True)
                target.close()
                yield chunk_path, start + 1, end + 1

    def extract_images(self, pdf_path: Path) -> dict[int, list[tuple[bytes, str]]]:
        result: dict[int, list[tuple[bytes, str]]] = {}
        with fitz.open(pdf_path) as doc:
            for page_index, page in enumerate(doc):
                page_text = page.get_text("text").strip()
                images = page.get_images(full=True)
                if len(images) == 1 and len(page_text) < 50:
                    continue
                found: list[tuple[bytes, str]] = []
                seen: set[int] = set()
                for image in images[:6]:
                    xref = int(image[0])
                    if xref in seen:
                        continue
                    seen.add(xref)
                    item = doc.extract_image(xref)
                    data = item.get("image")
                    width = int(item.get("width", 0))
                    height = int(item.get("height", 0))
                    if data and width >= 80 and height >= 40:
                        found.append((data, str(item.get("ext", "png"))))
                if found:
                    result[page_index + 1] = found
        return result

    @staticmethod
    def temporary_directory() -> tempfile.TemporaryDirectory[str]:
        return tempfile.TemporaryDirectory(prefix="ai_office_")
