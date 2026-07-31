from __future__ import annotations

import re
import unicodedata

from ftfy import fix_text

COMMON_REPLACEMENTS = {
    "Đảng uỷ": "Đảng ủy",
    "liệt sỹ": "liệt sĩ",
    "Liệt sỹ": "Liệt sĩ",
    "cọng sản": "cộng sản",
    "Cọng sản": "Cộng sản",
    "Bác hố": "Bác Hồ",
    "Bác Hố": "Bác Hồ",
}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    value = text.replace("\ufeff", "").replace("\u00a0", " ")
    value = fix_text(value, normalization="NFC")
    value = unicodedata.normalize("NFC", value)
    for wrong, correct in COMMON_REPLACEMENTS.items():
        value = value.replace(wrong, correct)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def strip_code_fence(text: str) -> str:
    value = text.strip()
    value = re.sub(r"^```(?:markdown|md|text|json)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```$", "", value)
    return value.strip()
