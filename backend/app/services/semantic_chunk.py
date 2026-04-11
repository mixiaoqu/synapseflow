"""Semantic chunking for vector indexing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass(frozen=True)
class VectorIndexChunk:
    """Structured chunk payload for embedding, lexical search, and display."""

    display_text: str
    embedding_text: str
    search_text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _Section:
    title: str | None
    heading_level: int | None
    section_path: str | None
    parent_heading: str | None
    section_start: int
    section_end: int
    body_text: str
    body_start: int
    body_end: int


_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", flags=re.MULTILINE)


def _trim_span(text: str, start: int, end: int) -> tuple[str, int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return text[start:end], start, end


def _module_prefix(section_path: str | None) -> str:
    if not section_path:
        return ""
    return f"[模块路径] {section_path}\n\n"


def _search_titles(
    doc_title: str | None,
    section_path: str | None,
    section_title: str | None,
) -> list[str]:
    titles: list[str] = []
    for value in (doc_title, section_path, section_title):
        cleaned = (value or "").strip()
        if cleaned and cleaned not in titles:
            titles.append(cleaned)
    return titles


def _search_text(
    doc_title: str | None,
    section_path: str | None,
    section_title: str | None,
    display_text: str,
) -> str:
    titles = _search_titles(doc_title, section_path, section_title)
    if titles:
        return ("\n".join(titles) + "\n\n" + display_text).strip()
    return display_text


def _body_budget(
    max_chars: int,
    section_path: str | None,
    doc_title: str | None,
    section_title: str | None,
) -> int:
    reserve = max(
        len(_module_prefix(section_path)),
        len(_search_text(doc_title, section_path, section_title, "")),
    )
    return max(1, max_chars - reserve)


def _sections_with_metadata(doc: str) -> list[_Section]:
    matches = list(_HEADING_RE.finditer(doc))
    if not matches:
        body_text, body_start, body_end = _trim_span(doc, 0, len(doc))
        if not body_text:
            return []
        return [
            _Section(
                title=None,
                heading_level=None,
                section_path=None,
                parent_heading=None,
                section_start=body_start,
                section_end=body_end,
                body_text=body_text,
                body_start=body_start,
                body_end=body_end,
            )
        ]

    out: list[_Section] = []
    stack: list[tuple[int, str]] = []
    first_heading = matches[0].start()
    if first_heading > 0:
        body_text, body_start, body_end = _trim_span(doc, 0, first_heading)
        if body_text:
            out.append(
                _Section(
                    title=None,
                    heading_level=None,
                    section_path=None,
                    parent_heading=None,
                    section_start=body_start,
                    section_end=body_end,
                    body_text=body_text,
                    body_start=body_start,
                    body_end=body_end,
                )
            )

    for idx, match in enumerate(matches):
        raw_start = match.start()
        raw_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(doc)
        _, section_start, section_end = _trim_span(doc, raw_start, raw_end)
        if section_start >= section_end:
            continue

        level = len(match.group(1))
        title = match.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        section_path = " > ".join(item for _, item in stack) or None
        parent_heading = stack[-2][1] if len(stack) >= 2 else None

        heading_line_end = doc.find("\n", section_start, section_end)
        if heading_line_end == -1:
            body_text = ""
            body_start = section_end
            body_end = section_end
        else:
            body_text, body_start, body_end = _trim_span(doc, heading_line_end + 1, section_end)

        out.append(
            _Section(
                title=title,
                heading_level=level,
                section_path=section_path,
                parent_heading=parent_heading,
                section_start=section_start,
                section_end=section_end,
                body_text=body_text,
                body_start=body_start,
                body_end=body_end,
            )
        )

    return out


def _split_paragraph_spans(doc: str, start: int, end: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    region = doc[start:end]
    for match in re.finditer(r"\n\s*\n+", region):
        _, para_start, para_end = _trim_span(doc, cursor, start + match.start())
        if para_start < para_end:
            spans.append((para_start, para_end))
        cursor = start + match.end()

    _, para_start, para_end = _trim_span(doc, cursor, end)
    if para_start < para_end:
        spans.append((para_start, para_end))
    return spans


def _spans_text(doc: str, spans: list[tuple[int, int]]) -> str:
    return "\n\n".join(doc[start:end] for start, end in spans).strip()


def _pack_paragraphs(
    spans: list[tuple[int, int]],
    max_chars: int,
) -> list[list[tuple[int, int]]]:
    packed: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    current_len = 0

    for span in spans:
        start, end = span
        part_len = end - start
        joiner = 2 if current else 0
        if current and current_len + joiner + part_len > max_chars:
            packed.append(current)
            current = []
            current_len = 0

        current.append(span)
        current_len += part_len if current_len == 0 else joiner + part_len

    if current:
        packed.append(current)
    return packed


def _split_oversized_with_splitter(
    text: str,
    abs_start: int,
    body_max: int,
    overlap: int,
) -> list[tuple[str, int, int]]:
    if len(text) <= body_max:
        piece, rel_start, rel_end = _trim_span(text, 0, len(text))
        if not piece:
            return []
        return [(piece, abs_start + rel_start, abs_start + rel_end)]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=body_max,
        chunk_overlap=min(overlap, max(0, body_max - 1)),
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "],
    )
    pieces = [item for item in splitter.split_text(text) if item.strip()]

    out: list[tuple[str, int, int]] = []
    cursor = 0
    for piece in pieces:
        search_from = max(0, cursor - overlap - 64)
        rel_start = text.find(piece, search_from)
        if rel_start < 0:
            rel_start = text.find(piece)
        if rel_start < 0:
            rel_start = search_from
        rel_end = min(len(text), rel_start + len(piece))
        trimmed, trimmed_start, trimmed_end = _trim_span(text, rel_start, rel_end)
        if trimmed:
            out.append(
                (trimmed, abs_start + trimmed_start, abs_start + trimmed_end)
            )
        cursor = rel_end
    return out


def _make_chunk(
    *,
    body_text: str,
    body_start: int,
    body_end: int,
    doc_title: str | None,
    section: _Section,
) -> VectorIndexChunk | None:
    display_text = body_text.strip()
    if not display_text:
        return None

    embedding_text = (_module_prefix(section.section_path) + display_text).strip()
    search_text = _search_text(
        doc_title,
        section.section_path,
        section.title,
        display_text,
    )
    metadata = {
        "section_path": section.section_path,
        "section_title": section.title,
        "heading_level": section.heading_level,
        "parent_heading": section.parent_heading,
        "start_offset": body_start,
        "end_offset": body_end,
    }
    return VectorIndexChunk(
        display_text=display_text,
        embedding_text=embedding_text or display_text,
        search_text=search_text or display_text,
        metadata=metadata,
    )


def split_for_vector_index(
    text: str,
    max_chars: int,
    overlap: int,
    *,
    document_title: str | None = None,
) -> list[VectorIndexChunk]:
    """Split a document into structured chunks for indexing."""
    if not text or not text.strip():
        return []

    chunks: list[VectorIndexChunk] = []
    for section in _sections_with_metadata(text):
        if not section.body_text:
            fallback = _make_chunk(
                body_text=section.title or "",
                body_start=section.section_start,
                body_end=section.section_end,
                doc_title=document_title,
                section=section,
            )
            if fallback:
                chunks.append(fallback)
            continue

        body_max = _body_budget(
            max_chars,
            section.section_path,
            document_title,
            section.title,
        )
        if len(section.body_text) <= body_max:
            chunk = _make_chunk(
                body_text=section.body_text,
                body_start=section.body_start,
                body_end=section.body_end,
                doc_title=document_title,
                section=section,
            )
            if chunk:
                chunks.append(chunk)
            continue

        paragraph_spans = _split_paragraph_spans(text, section.body_start, section.body_end)
        packed_spans = _pack_paragraphs(paragraph_spans, body_max)
        for span_group in packed_spans:
            body_text = _spans_text(text, span_group)
            if not body_text:
                continue

            if len(body_text) <= body_max:
                chunk = _make_chunk(
                    body_text=body_text,
                    body_start=span_group[0][0],
                    body_end=span_group[-1][1],
                    doc_title=document_title,
                    section=section,
                )
                if chunk:
                    chunks.append(chunk)
                continue

            start, end = span_group[0]
            oversized = _split_oversized_with_splitter(text[start:end], start, body_max, overlap)
            for sub_text, sub_start, sub_end in oversized:
                chunk = _make_chunk(
                    body_text=sub_text,
                    body_start=sub_start,
                    body_end=sub_end,
                    doc_title=document_title,
                    section=section,
                )
                if chunk:
                    chunks.append(chunk)

    return chunks
