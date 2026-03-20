"""通用工具模块"""
from app.utils.file_parser import extract_text_from_file, SUPPORTED_EXTENSIONS, MAX_FILE_SIZE
from app.utils.qa_utils import build_document_modification_suggestions

__all__ = [
    "extract_text_from_file",
    "SUPPORTED_EXTENSIONS",
    "MAX_FILE_SIZE",
    "build_document_modification_suggestions",
]
