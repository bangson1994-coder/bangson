from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from google import genai
from google.genai import types

from ai_office_vietnam.models import AIChunkResult, PageContent
from ai_office_vietnam.services.text_normalizer import normalize_text, strip_code_fence

PROMPT_TEMPLATE = """
Bạn là chuyên gia số hóa văn bản hành chính tiếng Việt. Hãy đọc trực tiếp các trang PDF đính kèm.
1. Chép đầy đủ nội dung theo đúng thứ tự từ trang {start_page} đến trang {end_page}; không tóm tắt, không tự thêm.
2. Sửa lỗi OCR, dấu tiếng Việt, lỗi mã/font VNI/TCVN3/Unicode và lỗi chính tả rõ ràng theo ngữ cảnh.
3. Không tự đổi họ tên, số văn bản, ngày tháng, số tiền, địa chỉ hoặc số liệu nếu không chắc chắn; chỗ không đọc được ghi [KHÔNG RÕ].
4. Mỗi phần tử pages tương ứng đúng một trang gốc.
5. Trong markdown dùng [TITLE]...[/TITLE], [CENTER]...[/CENTER], [RIGHT]...[/RIGHT], **đậm**, *nghiêng*, danh sách và bảng Markdown.
6. corrections liệt kê từng lỗi đã sửa theo dạng “sai → đúng”.
7. Không bọc markdown trong dấu ```.
""".strip()


class GeminiService:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key.strip():
            raise ValueError("Chưa có Gemini API key.")
        self.client = genai.Client(api_key=api_key.strip())
        self.model = model.strip() or "gemini-2.5-flash"

    def test_connection(self) -> None:
        response = self.client.models.generate_content(
            model=self.model,
            contents="Trả lời duy nhất một từ: OK",
            config=types.GenerateContentConfig(temperature=0, max_output_tokens=10),
        )
        if not response.text:
            raise RuntimeError("Gemini không trả về nội dung.")

    def process_pdf_chunk(self, chunk_path: Path, start_page: int, end_page: int,
                          status_callback: Callable[[str], None] | None = None) -> list[PageContent]:
        status = status_callback or (lambda _message: None)
        status(f"Đang tải trang {start_page}-{end_page} lên Gemini…")
        uploaded = self.client.files.upload(file=str(chunk_path), config=types.UploadFileConfig(mime_type="application/pdf"))
        try:
            uploaded = self._wait_until_ready(uploaded, status)
            response = self.client.models.generate_content(
                model=self.model,
                contents=[PROMPT_TEMPLATE.format(start_page=start_page, end_page=end_page), uploaded],
                config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json", response_schema=AIChunkResult),
            )
            parsed = response.parsed or AIChunkResult.model_validate_json(strip_code_fence(response.text or ""))
            pages = [PageContent(item.page_number, normalize_text(item.markdown),
                                 [normalize_text(c) for c in item.corrections if c.strip()]) for item in parsed.pages]
            by_number = {page.page_number: page for page in pages}
            return [by_number.get(n, PageContent(n, "[KHÔNG RÕ: Gemini chưa trả về nội dung trang này]"))
                    for n in range(start_page, end_page + 1)]
        finally:
            try:
                if getattr(uploaded, "name", None):
                    self.client.files.delete(name=uploaded.name)
            except Exception:
                pass

    def _wait_until_ready(self, uploaded, status: Callable[[str], None]):
        for _ in range(90):
            state_name = getattr(getattr(uploaded, "state", None), "name", str(getattr(uploaded, "state", ""))).upper()
            if "FAILED" in state_name:
                raise RuntimeError("Gemini không xử lý được tệp PDF.")
            if "PROCESSING" not in state_name:
                return uploaded
            status("Gemini đang chuẩn bị tệp PDF…")
            time.sleep(2)
            uploaded = self.client.files.get(name=uploaded.name)
        raise TimeoutError("Quá thời gian chờ Gemini chuẩn bị PDF.")
