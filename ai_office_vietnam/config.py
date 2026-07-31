from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

SERVICE_NAME = "AI Office Việt Nam"
KEYRING_USER = "gemini_api_key"
DEFAULT_MODEL = "gemini-3.1-flash-lite"
LEGACY_MODELS = {
    "gemini-2.5-flash",
    "models/gemini-2.5-flash",
    "gemini-2.0-flash",
    "models/gemini-2.0-flash",
}


def _qsettings():
    from PySide6.QtCore import QSettings

    return QSettings()


def _load_keyring() -> ModuleType | None:
    """Nạp keyring khi thật sự cần, tránh làm chậm màn hình khởi động."""
    try:
        return importlib.import_module("keyring")
    except ImportError:
        return None


def normalize_model_name(model: str | None) -> str:
    value = (model or "").strip()
    if not value or value in LEGACY_MODELS:
        return DEFAULT_MODEL
    if value.startswith("models/"):
        return value.removeprefix("models/")
    return value


@dataclass(slots=True)
class AppSettings:
    model: str = DEFAULT_MODEL
    font_name: str = "Times New Roman"
    font_size: int = 14
    line_spacing: float = 1.5
    margin_left_cm: float = 3.0
    margin_right_cm: float = 2.0
    margin_top_cm: float = 2.0
    margin_bottom_cm: float = 2.0
    chunk_pages: int = 6
    preserve_images: bool = True
    use_ai: bool = True
    output_dir: str = ""

    @classmethod
    def load(cls) -> "AppSettings":
        store = _qsettings()
        default_output = str(Path.home() / "Documents" / "Đổi PDF sang Word - Kết quả")
        model = normalize_model_name(str(store.value("gemini/model", DEFAULT_MODEL)))
        store.setValue("gemini/model", model)
        return cls(
            model=model,
            font_name=str(store.value("document/font_name", "Times New Roman")),
            font_size=int(store.value("document/font_size", 14)),
            line_spacing=float(store.value("document/line_spacing", 1.5)),
            margin_left_cm=float(store.value("document/margin_left_cm", 3.0)),
            margin_right_cm=float(store.value("document/margin_right_cm", 2.0)),
            margin_top_cm=float(store.value("document/margin_top_cm", 2.0)),
            margin_bottom_cm=float(store.value("document/margin_bottom_cm", 2.0)),
            chunk_pages=int(store.value("gemini/chunk_pages", 6)),
            preserve_images=str(store.value("document/preserve_images", "true")).lower() == "true",
            use_ai=str(store.value("gemini/use_ai", "true")).lower() == "true",
            output_dir=str(store.value("paths/output_dir", default_output)),
        )

    def save(self) -> None:
        self.model = normalize_model_name(self.model)
        store = _qsettings()
        store.setValue("gemini/model", self.model)
        store.setValue("document/font_name", self.font_name)
        store.setValue("document/font_size", self.font_size)
        store.setValue("document/line_spacing", self.line_spacing)
        store.setValue("document/margin_left_cm", self.margin_left_cm)
        store.setValue("document/margin_right_cm", self.margin_right_cm)
        store.setValue("document/margin_top_cm", self.margin_top_cm)
        store.setValue("document/margin_bottom_cm", self.margin_bottom_cm)
        store.setValue("gemini/chunk_pages", self.chunk_pages)
        store.setValue("document/preserve_images", self.preserve_images)
        store.setValue("gemini/use_ai", self.use_ai)
        store.setValue("paths/output_dir", self.output_dir)
        store.sync()


def get_api_key() -> str:
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    keyring = _load_keyring()
    try:
        if keyring is None:
            return str(_qsettings().value("gemini/api_key_fallback", "")).strip()
        return (keyring.get_password(SERVICE_NAME, KEYRING_USER) or "").strip()
    except Exception:
        return str(_qsettings().value("gemini/api_key_fallback", "")).strip()


def save_api_key(api_key: str) -> None:
    api_key = api_key.strip()
    keyring = _load_keyring()
    try:
        if keyring is None:
            raise RuntimeError("Không có keyring")
        if api_key:
            keyring.set_password(SERVICE_NAME, KEYRING_USER, api_key)
        else:
            try:
                keyring.delete_password(SERVICE_NAME, KEYRING_USER)
            except keyring.errors.PasswordDeleteError:
                pass
        _qsettings().remove("gemini/api_key_fallback")
    except Exception:
        _qsettings().setValue("gemini/api_key_fallback", api_key)
