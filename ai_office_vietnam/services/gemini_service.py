from __future__ import annotations

import io
import tempfile
import time
from pathlib import Path
from typing import Callable

from google import genai
from google.genai import types
from PIL import Image, ImageOps

from ai_office_vietnam.config import DEFAULT_MODEL, normalize_model_name
from ai_office_vietnam.models import AIChunkResult, PageContent
from ai_office_vietnam.services.text_normalizer import normalize_text, strip_code_fence

StageCallback = Callable[[int, str], None]

PDF_PROMPT = """
Bạn là chuyên gia số hóa văn bản hành chính tiếng Việt. Hãy đọc trực tiếp các trang PDF đính kèm.
1. Chép đầy đủ nội dung theo đúng thứ tự từ trang {start_page} đến trang {end_page}; không tóm tắt, không tự thêm.
2. Sửa lỗi OCR, dấu tiếng Việt, lỗi mã/font VNI/TCVN3/Unicode và lỗi chính tả rõ ràng theo ngữ cảnh.
3. Không tự đổi họ tên, số văn bản, ngày tháng, số tiền, địa chỉ hoặc số liệu nếu không chắc chắn; chỗ không đọc được ghi [KHÔNG RÕ].
4. Mỗi phần tử pages tương ứng đúng một trang gốc.
5. Trong markdown dùng [TITLE]...[/TITLE], [CENTER]...[/CENTER], [RIGHT]...[/RIGHT], **đậm**, *nghiêng*, danh sách và bảng Markdown.
6. corrections liệt kê từng lỗi đã sửa theo dạng “sai → đúng”.
7. Không bọc markdown trong dấu ```.
""".strip()

IMAGE_PROMPT = """
Bạn là chuyên gia số hóa văn bản tiếng Việt. Hãy đọc toàn bộ chữ trong ảnh đính kèm và tạo nội dung Word có thể chỉnh sửa.
1. Chép đầy đủ theo đúng thứ tự, không tóm tắt và không tự thêm.
2. Sửa lỗi OCR, dấu tiếng Việt, lỗi mã/font VNI/TCVN3/Unicode và lỗi chính tả rõ ràng theo ngữ cảnh.
3. Không tự đổi họ tên, số văn bản, ngày tháng, số tiền, địa chỉ hoặc số liệu nếu không chắc chắn; chỗ không đọc được ghi [KHÔNG RÕ].
4. Trả về đúng một phần tử pages với page_number là 1.
5. Trong markdown dùng [TITLE]...[/TITLE], [CENTER]...[/CENTER], [RIGHT]...[/RIGHT], **đậm**, *nghiêng*, danh sách và bảng Markdown.
6. corrections liệt kê từng lỗi đã sửa theo dạng “sai → đúng”.
7. Không bọc markdown trong dấu ```.
""".strip()


class GeminiService:
    FALLBACK_MODELS = (DEFAULT_MODEL, "gemini-3.5-flash")

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key.strip():
            raise ValueError("Chưa có Gemini API key.")
        self.client = genai.Client(api_key=api_key.strip())
        self.model = normalize_model_name(model)

    def test_connection(self) -> None:
        response = self._generate_with_fallback(
            contents="Trả lời duy nhất một từ: OK",
            config=types.GenerateContentConfig(temperature=0, max_output_tokens=10),
        )
        if not response.text:
            raise RuntimeError("Gemini không trả về nội dung.")

    def process_pdf_chunk(
        self,
        chunk_path: Path,
        start_page: int,
        end_page: int,
        status_callback: StageCallback | None = None,
    ) -> list[PageContent]:
        status = status_callback or (lambda _value, _message: None)
        status(8, f"Đính PDF trang {start_page}-{end_page}: đang tải lên Gemini…")
        uploaded = self.client.files.upload(
            file=str(chunk_path),
            config=types.UploadFileConfig(mime_type="application/pdf"),
        )
        status(25, f"Đính PDF trang {start_page}-{end_page}: tải lên hoàn thành ✓")
        try:
            uploaded = self._wait_until_ready(uploaded, status)
            status(48, f"Gemini đang đọc trang {start_page}-{end_page}…")
            response = self._generate_with_fallback(
                contents=[PDF_PROMPT.format(start_page=start_page, end_page=end_page), uploaded],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=AIChunkResult,
                ),
            )
            status(90, f"Đã nhận dạng xong trang {start_page}-{end_page} ✓")
            pages = self._parse_response(response)
            return self._repair_page_sequence(pages, start_page, end_page)
        finally:
            try:
                if getattr(uploaded, "name", None):
                    self.client.files.delete(name=uploaded.name)
            except Exception:
                pass

    def process_image(
        self,
        image_path: Path,
        status_callback: StageCallback | None = None,
    ) -> list[PageContent]:
        status = status_callback or (lambda _value, _message: None)
        status(5, f"Đang chuẩn bị ảnh {image_path.name}…")
        png_bytes = self._image_as_png(image_path)
        with tempfile.TemporaryDirectory(prefix="bang-son-image-") as temp_name:
            prepared = Path(temp_name) / "image.png"
            prepared.write_bytes(png_bytes)
            status(8, f"Đính ảnh {image_path.name}: đang tải lên Gemini…")
            uploaded = self.client.files.upload(
                file=str(prepared),
                config=types.UploadFileConfig(mime_type="image/png"),
            )
            status(25, f"Đính ảnh {image_path.name}: tải lên hoàn thành ✓")
            try:
                uploaded = self._wait_until_ready(uploaded, status)
                status(48, f"Gemini đang đọc chữ trong {image_path.name}…")
                response = self._generate_with_fallback(
                    contents=[uploaded, IMAGE_PROMPT],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                        response_schema=AIChunkResult,
                    ),
                )
                status(90, f"Đã nhận dạng ảnh {image_path.name} ✓")
                pages = self._parse_response(response)
                return self._repair_page_sequence(pages, 1, 1)
            finally:
                try:
                    if getattr(uploaded, "name", None):
                        self.client.files.delete(name=uploaded.name)
                except Exception:
                    pass

    def _generate_with_fallback(self, *, contents, config):
        candidates: list[str] = []
        for model in (self.model, *self.FALLBACK_MODELS):
            normalized = normalize_model_name(model)
            if normalized not in candidates:
                candidates.append(normalized)

        last_error: Exception | None = None
        for model in candidates:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                self.model = model
                return response
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                model_error = any(
                    token in message
                    for token in (
                        "404",
                        "not_found",
                        "not found",
                        "no longer available",
                        "unsupported model",
                    )
                )
                if not model_error:
                    raise
        raise RuntimeError(f"Không tìm thấy mô hình Gemini phù hợp. Chi tiết: {last_error}")

    @staticmethod
    def _image_as_png(image_path: Path) -> bytes:
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")
            output = io.BytesIO()
            image.save(output, format="PNG", optimize=True)
            return output.getvalue()

    @staticmethod
    def _parse_response(response) -> list[PageContent]:
        parsed = response.parsed
        if parsed is None:
            parsed = AIChunkResult.model_validate_json(strip_code_fence(response.text or ""))
        return [
            PageContent(
                page_number=item.page_number,
                markdown=normalize_text(item.markdown),
                corrections=[normalize_text(c) for c in item.corrections if c.strip()],
            )
            for item in parsed.pages
        ]

    def _wait_until_ready(self, uploaded, status: StageCallback):
        for _ in range(90):
            state = getattr(uploaded, "state", None)
            state_name = getattr(state, "name", str(state or "")).upper()
            if "FAILED" in state_name:
                raise RuntimeError("Gemini không xử lý được tệp đã tải lên.")
            if "PROCESSING" not in state_name:
                status(35, "Tệp đính kèm đã sẵn sàng để nhận dạng ✓")
                return uploaded
            status(30, "Tệp đã tải xong; Gemini đang chuẩn bị dữ liệu…")
            time.sleep(2)
            uploaded = self.client.files.get(name=uploaded.name)
        raise TimeoutError("Quá thời gian chờ Gemini chuẩn bị tệp.")

    @staticmethod
    def _repair_page_sequence(
        pages: list[PageContent], start_page: int, end_page: int
    ) -> list[PageContent]:
        by_number = {page.page_number: page for page in pages}
        return [
            by_number.get(
                page_number,
                PageContent(page_number, "[KHÔNG RÕ: Gemini chưa trả về nội dung trang này]"),
            )
            for page_number in range(start_page, end_page + 1)
        ]
