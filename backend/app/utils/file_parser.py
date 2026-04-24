"""Deprecated compatibility shims for document parsing.

Prefer importing from ``app.utils.document_parse`` directly.
"""

from app.utils.document_parse import MAX_FILE_SIZE, SUPPORTED_EXTENSIONS, parse_uploaded_document

__all__ = [
    "parse_uploaded_document",
    "SUPPORTED_EXTENSIONS",
    "MAX_FILE_SIZE",
]
