from docx import Document
from docx.shared import Mm

from ai_office_vietnam.config import AppSettings
from ai_office_vietnam.models import PageContent
from ai_office_vietnam.services.text_normalizer import normalize_text
from ai_office_vietnam.services.word_service import WordService


def test_normalize_vietnamese_errors():
    assert normalize_text("Bác Hố\n\n\nĐảng uỷ") == "Bác Hồ\n\nĐảng ủy"


def test_word_is_a4_times_new_roman(tmp_path):
    output = tmp_path / "result.docx"
    WordService().create_document(
        [PageContent(1, "[TITLE]QUYẾT ĐỊNH[/TITLE]\nNội dung văn bản")],
        output,
        AppSettings(),
    )
    doc = Document(output)
    section = doc.sections[0]
    assert abs(section.page_width - Mm(210)) < 1000
    assert abs(section.page_height - Mm(297)) < 1000
    assert doc.styles["Normal"].font.name == "Times New Roman"
