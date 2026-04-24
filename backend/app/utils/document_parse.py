"""Document parsing utilities with a structured intermediate representation."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any

SUPPORTED_EXTENSIONS = frozenset({".txt", ".md", ".pdf", ".docx", ".doc"})
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

_PAGE_NOISE_RE = re.compile(r"^\s*(?:第\s*)?\d+\s*(?:页|/\s*\d+)?\s*$")
_TOC_RE = re.compile(r"(?:^|\s)(?:目录|contents)\s*$", flags=re.IGNORECASE)
_DISCLAIMER_RE = re.compile(
    r"(?:仅供内部|机密|版权归|all rights reserved|未经授权)",
    flags=re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_LIST_RE = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)(.+)$")
_TABLE_RE = re.compile(r"^\|.+\|$")


@dataclass(frozen=True)
class ParsedBlock:
    type: str
    text: str
    level: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    metadata: dict[str, Any] = field(default_factory=dict)
    blocks: list[ParsedBlock] = field(default_factory=list)


def normalize_requirements_plaintext(text: str) -> str:
    """Normalize newlines and trim surrounding whitespace."""
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def parse_uploaded_document(filename: str, content: bytes) -> tuple[str, str | None]:
    parsed, error = parse_uploaded_document_structured(filename, content)
    if error or parsed is None:
        return "", error
    return render_parsed_document(parsed), None


def parse_uploaded_document_structured(
    filename: str,
    content: bytes,
) -> tuple[ParsedDocument | None, str | None]:
    if len(content) > MAX_FILE_SIZE:
        return None, "文件大小超过限制（最大 10MB）"

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        return None, "不支持的文件格式: %s，支持 %s" % (
            ext,
            ", ".join(sorted(SUPPORTED_EXTENSIONS)),
        )

    try:
        if ext in {".txt", ".md"}:
            parsed = parse_raw_document_content(
                _parse_text(content),
                title=_title_from_filename(filename),
                document_type=ext.lstrip("."),
                filename=filename,
            )
        elif ext == ".pdf":
            parsed = _parse_pdf_document(filename, content)
        elif ext == ".docx":
            parsed = _parse_docx_document(filename, content)
        elif ext == ".doc":
            return None, "当前版本暂不直接支持 .doc，请先转换为 .docx 再上传"
        else:
            return None, "未实现的解析器: %s" % ext
        return clean_parsed_document(parsed), None
    except Exception as exc:
        return None, "文件解析失败: %s" % str(exc)


def parse_raw_document_content(
    text: str,
    *,
    title: str,
    document_type: str | None = None,
    filename: str | None = None,
) -> ParsedDocument:
    normalized = normalize_requirements_plaintext(text)
    doc_type = (document_type or "txt").lower()
    if doc_type == "md":
        parsed = _parse_markdown_document(normalized, title=title)
    else:
        parsed = _parse_plaintext_document(normalized, title=title)
    metadata = dict(parsed.metadata)
    metadata.update(
        {
            "source_type": "text",
            "filename": filename,
            "document_type": doc_type,
            "parser_name": metadata.get("parser_name") or f"local-{doc_type}",
        }
    )
    return ParsedDocument(title=parsed.title, metadata=metadata, blocks=parsed.blocks)


def clean_parsed_document(document: ParsedDocument) -> ParsedDocument:
    noise_counts: dict[str, int] = {}
    normalized_blocks: list[ParsedBlock] = []

    for block in document.blocks:
        text = _normalize_block_text(block)
        if not text:
            continue
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= 60:
            noise_counts[compact] = noise_counts.get(compact, 0) + 1
        normalized_blocks.append(
            ParsedBlock(
                type=block.type,
                text=text,
                level=block.level,
                metadata=dict(block.metadata or {}),
            )
        )

    repeated_noise = {
        item
        for item, count in noise_counts.items()
        if count >= 3 and (len(item) <= 30 or _PAGE_NOISE_RE.match(item))
    }

    cleaned: list[ParsedBlock] = []
    previous_key: tuple[str, str] | None = None
    for block in normalized_blocks:
        compact = re.sub(r"\s+", " ", block.text).strip()
        if compact in repeated_noise:
            continue
        if _PAGE_NOISE_RE.match(compact):
            continue
        if block.type == "paragraph" and _TOC_RE.search(compact):
            continue
        if block.type == "paragraph" and _DISCLAIMER_RE.search(compact) and len(compact) <= 80:
            continue
        block_key = (block.type, compact)
        if previous_key == block_key:
            continue
        previous_key = block_key
        cleaned.append(block)

    metadata = dict(document.metadata)
    metadata.setdefault("parse_warnings", [])
    return ParsedDocument(title=document.title, metadata=metadata, blocks=cleaned)


def render_parsed_document(document: ParsedDocument) -> str:
    parts = [_render_block(block) for block in document.blocks]
    return "\n\n".join(part for part in parts if part.strip()).strip()


def _title_from_filename(filename: str) -> str:
    if "." in filename:
        name = filename.rsplit(".", 1)[0].strip()
        if name:
            return name
    return filename or "Untitled document"


def _normalize_block_text(block: ParsedBlock) -> str:
    text = normalize_requirements_plaintext(block.text)
    if not text:
        return ""
    if block.type in {"paragraph", "list"}:
        text = _merge_soft_wrapped_lines(text)
    if block.type == "table":
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line)
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def _merge_soft_wrapped_lines(text: str) -> str:
    pieces = [line.strip() for line in normalize_requirements_plaintext(text).split("\n")]
    merged: list[str] = []
    buffer = ""
    for piece in pieces:
        if not piece:
            if buffer:
                merged.append(buffer.strip())
                buffer = ""
            continue
        if not buffer:
            buffer = piece
            continue
        if _should_merge_lines(buffer, piece):
            buffer += _soft_join(buffer, piece)
        else:
            merged.append(buffer.strip())
            buffer = piece
    if buffer:
        merged.append(buffer.strip())
    return "\n\n".join(item for item in merged if item)


def _should_merge_lines(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous.endswith((".", "!", "?", "。", "！", "？", "：", ":", ";", "；")):
        return False
    if _LIST_RE.match(current) or _TABLE_RE.match(current):
        return False
    if len(previous) >= 120:
        return False
    return True


def _soft_join(previous: str, current: str) -> str:
    if previous[-1].isascii() and current[0].isascii():
        return f" {current}"
    return current


def _render_block(block: ParsedBlock) -> str:
    if block.type == "heading":
        level = max(1, min(block.level or 1, 6))
        return f"{'#' * level} {block.text.strip()}"
    if block.type == "list":
        items = [line.strip() for line in block.text.split("\n") if line.strip()]
        normalized = []
        for item in items:
            match = _LIST_RE.match(item)
            value = match.group(1).strip() if match else item
            normalized.append(f"- {value}")
        return "\n".join(normalized)
    if block.type == "code":
        return f"```\n{block.text.strip()}\n```"
    return block.text.strip()


def _parse_text(content: bytes) -> str:
    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            return content.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别文件编码")


def _parse_pdf_document(filename: str, content: bytes) -> ParsedDocument:
    return _parse_with_docling(filename, content)


def _parse_docx_document(filename: str, content: bytes) -> ParsedDocument:
    return _parse_with_docling(filename, content)


def _parse_with_docling(filename: str, content: bytes) -> ParsedDocument:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {".pdf", ".docx"}:
        raise ValueError(f"Docling parser does not support extension: {ext}")

    try:
        converter_module = import_module("docling.document_converter")
    except ImportError as exc:
        raise ImportError("Docling is required for PDF/DOCX parsing. Please install docling.") from exc

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as handle:
            handle.write(content)
            temp_path = handle.name

        converter = converter_module.DocumentConverter()
        result = converter.convert(temp_path)
        document = getattr(result, "document", result)

        markdown = None
        for attr in ("export_to_markdown", "to_markdown"):
            candidate = getattr(document, attr, None)
            if callable(candidate):
                markdown = candidate()
                break

        if not isinstance(markdown, str) or not markdown.strip():
            if ext == ".pdf":
                raise ValueError("Current version does not support OCR; upload a text-based PDF.")
            raise ValueError("Docling returned empty content for the uploaded document.")

        parsed = _parse_markdown_document(markdown, title=_title_from_filename(filename))
        metadata = dict(parsed.metadata)
        metadata.update(
            {
                "source_type": "file",
                "filename": filename,
                "document_type": ext.lstrip("."),
                "parser_name": "docling",
            }
        )
        return ParsedDocument(title=parsed.title, metadata=metadata, blocks=parsed.blocks)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def _parse_plaintext_document(text: str, *, title: str) -> ParsedDocument:
    blocks = [
        ParsedBlock(type="paragraph", text=paragraph)
        for paragraph in _split_paragraphs(text)
        if paragraph.strip()
    ]
    return ParsedDocument(
        title=title,
        metadata={"parser_name": "local-txt"},
        blocks=blocks,
    )


def _parse_markdown_document(text: str, *, title: str) -> ParsedDocument:
    blocks: list[ParsedBlock] = []
    lines = normalize_requirements_plaintext(text).split("\n")
    paragraph_lines: list[str] = []
    list_lines: list[str] = []
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if paragraph_lines:
            blocks.append(ParsedBlock(type="paragraph", text="\n".join(paragraph_lines).strip()))
            paragraph_lines.clear()

    def flush_list() -> None:
        if list_lines:
            blocks.append(ParsedBlock(type="list", text="\n".join(list_lines).strip()))
            list_lines.clear()

    def flush_code() -> None:
        if code_lines:
            blocks.append(ParsedBlock(type="code", text="\n".join(code_lines).rstrip()))
            code_lines.clear()

    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code:
                flush_code()
            in_code = not in_code
            continue

        if in_code:
            code_lines.append(stripped)
            continue

        if not stripped.strip():
            flush_paragraph()
            flush_list()
            continue

        heading = _HEADING_RE.match(stripped.strip())
        if heading:
            flush_paragraph()
            flush_list()
            blocks.append(
                ParsedBlock(
                    type="heading",
                    text=heading.group(2).strip(),
                    level=len(heading.group(1)),
                )
            )
            continue

        if _TABLE_RE.match(stripped.strip()):
            flush_paragraph()
            flush_list()
            blocks.append(ParsedBlock(type="table", text=stripped.strip()))
            continue

        if _LIST_RE.match(stripped.strip()):
            flush_paragraph()
            list_lines.append(stripped.strip())
            continue

        flush_list()
        paragraph_lines.append(stripped.strip())

    flush_paragraph()
    flush_list()
    flush_code()

    return ParsedDocument(
        title=title,
        metadata={"parser_name": "local-md"},
        blocks=blocks,
    )


def _split_paragraphs(text: str) -> list[str]:
    if not text.strip():
        return []
    return [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n+", normalize_requirements_plaintext(text))
        if paragraph.strip()
    ]

