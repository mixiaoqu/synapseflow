"""向后兼容导出：统一实现见 app.utils.document_parse。"""
from typing import Tuple

from app.utils.document_parse import (
    MAX_FILE_SIZE,
    SUPPORTED_EXTENSIONS,
    parse_uploaded_document,
)

__all__ = [
    "extract_text_from_file",
    "parse_uploaded_document",
    "SUPPORTED_EXTENSIONS",
    "MAX_FILE_SIZE",
]


def extract_text_from_file(filename: str, content: bytes) -> Tuple[str, str | None]:
    return parse_uploaded_document(filename, content)
