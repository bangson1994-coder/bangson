from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field


class AIPage(BaseModel):
    page_number: int = Field(ge=1)
    markdown: str
    corrections: list[str] = Field(default_factory=list)


class AIChunkResult(BaseModel):
    pages: list[AIPage]


@dataclass(slots=True)
class PageContent:
    page_number: int
    markdown: str
    corrections: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ConversionResult:
    input_path: Path
    output_path: Path
    correction_log_path: Path | None
    page_count: int
    correction_count: int
