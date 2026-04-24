"""Structured chunk planning for document indexing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.utils.document_parse import ParsedBlock, ParsedDocument, render_parsed_document

PARENT_TARGET_MIN = 1200
PARENT_TARGET_MAX = 2500
CHILD_TARGET_MIN = 400
CHILD_TARGET_MAX = 900
OVERLAP_UNITS = 1
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？!?；;\.])")


@dataclass(frozen=True)
class VectorIndexChunk:
    """Structured chunk payload for embedding, lexical search, and display."""

    display_text: str
    embedding_text: str
    search_text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PlannedChunk:
    local_id: str
    chunk_kind: str
    chunk_index: int
    parent_local_id: str | None
    prev_local_id: str | None
    next_local_id: str | None
    section_path: str | None
    block_types: list[str]
    start_offset: int
    end_offset: int
    content: str
    search_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentChunkPlan:
    full_text: str
    parent_chunks: list[PlannedChunk]
    child_chunks: list[PlannedChunk]


@dataclass(frozen=True)
class _RenderedBlock:
    type: str
    text: str
    section_path: str | None
    heading_path: tuple[str, ...]
    start_offset: int
    end_offset: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _Fragment:
    type: str
    text: str
    section_path: str | None
    heading_path: tuple[str, ...]
    start_offset: int
    end_offset: int
    metadata: dict[str, Any]


def build_chunk_plan(
    parsed: ParsedDocument,
    *,
    document_title: str | None = None,
) -> DocumentChunkPlan:
    full_text = render_parsed_document(parsed)
    rendered_blocks = _rendered_blocks_with_offsets(parsed)
    content_blocks = [block for block in rendered_blocks if block.type != "heading" and block.text.strip()]
    parent_payloads = _build_parent_payloads(content_blocks)
    parent_chunks: list[PlannedChunk] = []
    child_chunks: list[PlannedChunk] = []

    for parent_index, payload in enumerate(parent_payloads):
        parent_local_id = f"parent-{parent_index}"
        parent_section_path = _common_section_path(payload)
        parent_content = _join_fragments(payload)
        parent_search = _build_search_text(document_title, parent_section_path, parent_content)
        parent_chunks.append(
            PlannedChunk(
                local_id=parent_local_id,
                chunk_kind="parent",
                chunk_index=parent_index,
                parent_local_id=None,
                prev_local_id=None,
                next_local_id=None,
                section_path=parent_section_path,
                block_types=_unique_block_types(payload),
                start_offset=payload[0].start_offset,
                end_offset=payload[-1].end_offset,
                content=parent_content,
                search_text=parent_search,
                metadata={"block_count": len(payload)},
            )
        )

        child_payloads = _build_child_payloads(payload)
        for child_index, child in enumerate(child_payloads):
            child_chunks.append(
                PlannedChunk(
                    local_id=f"child-{len(child_chunks)}",
                    chunk_kind="child",
                    chunk_index=len(child_chunks),
                    parent_local_id=parent_local_id,
                    prev_local_id=None,
                    next_local_id=None,
                    section_path=_common_section_path(child),
                    block_types=_unique_block_types(child),
                    start_offset=child[0].start_offset,
                    end_offset=child[-1].end_offset,
                    content=_join_fragments(child),
                    search_text=_build_search_text(
                        document_title,
                        _common_section_path(child),
                        _join_fragments(child),
                    ),
                    metadata={
                        "block_count": len(child),
                        "hit_window_hint": {"prev": 1, "next": 1},
                        "parent_chunk_index": parent_index,
                        "child_index_within_parent": child_index,
                    },
                )
            )

    parent_chunks = _link_chunks(parent_chunks)
    child_chunks = _link_chunks(child_chunks)
    return DocumentChunkPlan(
        full_text=full_text,
        parent_chunks=parent_chunks,
        child_chunks=child_chunks,
    )


def plan_text_chunks(
    text: str,
    *,
    document_title: str | None = None,
) -> DocumentChunkPlan:
    parsed = ParsedDocument(
        title=document_title or "Untitled document",
        blocks=[ParsedBlock(type="paragraph", text=text)],
    )
    return build_chunk_plan(parsed, document_title=document_title)


def build_vector_index_chunks(
    plan: DocumentChunkPlan,
    *,
    document_id: int,
) -> list[VectorIndexChunk]:
    rows: list[VectorIndexChunk] = []
    for chunk in plan.child_chunks:
        metadata = {
            "document_id": document_id,
            "parent_local_id": chunk.parent_local_id,
            "section_path": chunk.section_path,
            "block_types": list(chunk.block_types),
            "chunk_index": chunk.chunk_index,
            "prev_child_local_id": chunk.prev_local_id,
            "next_child_local_id": chunk.next_local_id,
            "start_offset": chunk.start_offset,
            "end_offset": chunk.end_offset,
            **dict(chunk.metadata or {}),
        }
        rows.append(
            VectorIndexChunk(
                display_text=chunk.content,
                embedding_text=chunk.search_text,
                search_text=chunk.search_text,
                metadata=metadata,
            )
        )
    return rows


def _rendered_blocks_with_offsets(parsed: ParsedDocument) -> list[_RenderedBlock]:
    rendered: list[_RenderedBlock] = []
    heading_stack: list[str] = []
    cursor = 0
    first = True

    for block in parsed.blocks:
        text = _render_block(block)
        if not text:
            continue
        if not first:
            cursor += 2
        start = cursor
        cursor += len(text)
        end = cursor
        first = False

        if block.type == "heading":
            level = max(1, min(block.level or 1, 6))
            while len(heading_stack) >= level:
                heading_stack.pop()
            heading_stack.append(block.text.strip())
            rendered.append(
                _RenderedBlock(
                    type="heading",
                    text=text,
                    section_path=" > ".join(heading_stack) or None,
                    heading_path=tuple(heading_stack),
                    start_offset=start,
                    end_offset=end,
                    metadata={"heading_level": level},
                )
            )
            continue

        rendered.append(
            _RenderedBlock(
                type=block.type,
                text=text,
                section_path=" > ".join(heading_stack) or None,
                heading_path=tuple(heading_stack),
                start_offset=start,
                end_offset=end,
                metadata=dict(block.metadata or {}),
            )
        )


    return rendered


def _render_block(block: ParsedBlock) -> str:
    if block.type == "heading":
        level = max(1, min(block.level or 1, 6))
        return f"{'#' * level} {block.text.strip()}"
    if block.type == "list":
        lines = [line.strip() for line in block.text.split("\n") if line.strip()]
        normalized: list[str] = []
        for line in lines:
            if line.startswith(("-", "*", "+")):
                normalized.append(line if line.startswith("- ") else f"- {line[1:].strip()}")
            elif re.match(r"^\d+[.)]\s+", line):
                normalized.append(f"- {re.sub(r'^\d+[.)]\s+', '', line)}")
            else:
                normalized.append(f"- {line}")
        return "\n".join(normalized)
    if block.type == "code":
        return f"```\n{block.text.strip()}\n```"
    return block.text.strip()


def _build_parent_payloads(blocks: list[_RenderedBlock]) -> list[list[_Fragment]]:
    sections = _split_sections(blocks)
    payloads: list[list[_Fragment]] = []
    pending: list[_Fragment] = []
    pending_length = 0

    for index, section in enumerate(sections):
        section_len = _payload_length(section)
        same_lineage = bool(
            pending
            and section
            and _shares_lineage(pending[-1].heading_path, section[0].heading_path)
        )

        should_merge_short_section = (
            pending
            and pending_length < PARENT_TARGET_MIN
            and section_len < PARENT_TARGET_MIN
            and same_lineage
            and pending_length + 2 + section_len <= PARENT_TARGET_MAX
        )

        if pending and not should_merge_short_section:
            payloads.append(pending)
            pending = []
            pending_length = 0

        if not section:
            continue

        section_cursor: list[_Fragment] = []
        section_cursor_length = 0
        for fragment in _expand_block_fragments(section, PARENT_TARGET_MAX):
            fragment_length = len(fragment.text)
            joiner = 2 if section_cursor else 0
            if section_cursor and section_cursor_length + joiner + fragment_length > PARENT_TARGET_MAX:
                payloads.append(section_cursor)
                section_cursor = []
                section_cursor_length = 0
            section_cursor.append(fragment)
            section_cursor_length += fragment_length if not section_cursor_length else joiner + fragment_length

        if not section_cursor:
            continue

        if pending and should_merge_short_section:
            pending.extend(section_cursor)
            pending_length = _payload_length(pending)
        else:
            pending = list(section_cursor)
            pending_length = _payload_length(pending)

    if pending:
        payloads.append(pending)
    return payloads


def _build_child_payloads(parent_fragments: list[_Fragment]) -> list[list[_Fragment]]:
    payloads: list[list[_Fragment]] = []
    current: list[_Fragment] = []
    current_length = 0

    for fragment in _expand_fragments_for_children(parent_fragments):
        fragment_length = len(fragment.text)
        joiner = 2 if current else 0
        if current and current_length + joiner + fragment_length > CHILD_TARGET_MAX:
            payloads.append(current)
            current = []
            current_length = 0
        current.append(fragment)
        current_length += fragment_length if not current_length else joiner + fragment_length

    if current:
        payloads.append(current)
    return payloads


def _split_sections(blocks: list[_RenderedBlock]) -> list[list[_RenderedBlock]]:
    buckets: list[list[_RenderedBlock]] = []
    current: list[_RenderedBlock] = []
    current_path: tuple[str, ...] | None = None

    for block in blocks:
        path = block.heading_path
        if current and path != current_path:
            buckets.append(current)
            current = []
        current.append(block)
        current_path = path

    if current:
        buckets.append(current)
    return buckets


def _expand_block_fragments(
    blocks: list[_RenderedBlock],
    target_max: int,
) -> list[_Fragment]:
    fragments: list[_Fragment] = []
    for block in blocks:
        fragments.extend(_split_rendered_block(block, target_max))
    return _merge_tiny_fragments(fragments, target_max)


def _expand_fragments_for_children(parent_fragments: list[_Fragment]) -> list[_Fragment]:
    fragments: list[_Fragment] = []
    for fragment in parent_fragments:
        fragments.extend(_split_fragment_for_children(fragment))
    return _merge_tiny_fragments(fragments, CHILD_TARGET_MAX)


def _split_rendered_block(block: _RenderedBlock, target_max: int) -> list[_Fragment]:
    fragment = _Fragment(
        type=block.type,
        text=block.text,
        section_path=block.section_path,
        heading_path=block.heading_path,
        start_offset=block.start_offset,
        end_offset=block.end_offset,
        metadata=dict(block.metadata or {}),
    )
    return _split_fragment(fragment, target_max)


def _split_fragment_for_children(fragment: _Fragment) -> list[_Fragment]:
    return _split_fragment(fragment, CHILD_TARGET_MAX)


def _split_fragment(fragment: _Fragment, target_max: int) -> list[_Fragment]:
    if len(fragment.text) <= target_max:
        return [fragment]
    if fragment.type == "table":
        return _split_table_fragment(fragment, target_max)
    return _split_text_fragment(fragment, target_max)


def _split_table_fragment(fragment: _Fragment, target_max: int) -> list[_Fragment]:
    rows = [row for row in fragment.text.split("\n") if row.strip()]
    return _split_units(fragment, rows, target_max)


def _split_text_fragment(fragment: _Fragment, target_max: int) -> list[_Fragment]:
    units = _split_sentences(fragment.text)
    if len(units) <= 1:
        units = [line for line in fragment.text.split("\n\n") if line.strip()]
    if len(units) <= 1:
        units = [fragment.text]
    return _split_units(fragment, units, target_max)


def _split_units(fragment: _Fragment, units: list[str], target_max: int) -> list[_Fragment]:
    if not units:
        return [fragment]
    pieces: list[_Fragment] = []
    current_units: list[str] = []
    current_start = fragment.start_offset
    cursor = fragment.start_offset
    text_cursor = 0

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue
        joiner = "\n" if fragment.type == "table" else " "
        candidate = joiner.join(current_units + [unit]).strip() if current_units else unit
        if current_units and len(candidate) > target_max:
            chunk_text = joiner.join(current_units).strip()
            pieces.append(
                _Fragment(
                    type=fragment.type,
                    text=chunk_text,
                    section_path=fragment.section_path,
                    heading_path=fragment.heading_path,
                    start_offset=current_start,
                    end_offset=min(fragment.end_offset, current_start + len(chunk_text)),
                    metadata=dict(fragment.metadata or {}),
                )
            )
            overlap = current_units[-OVERLAP_UNITS:] if OVERLAP_UNITS else []
            current_units = list(overlap)
            current_start = max(fragment.start_offset, current_start + max(1, len(chunk_text) - len(joiner.join(overlap))))
        current_units.append(unit)
        text_cursor += len(unit)
        cursor = min(fragment.end_offset, fragment.start_offset + text_cursor)

    if current_units:
        chunk_text = ("\n" if fragment.type == "table" else " ").join(current_units).strip()
        pieces.append(
            _Fragment(
                type=fragment.type,
                text=chunk_text,
                section_path=fragment.section_path,
                heading_path=fragment.heading_path,
                start_offset=current_start,
                end_offset=max(current_start, min(fragment.end_offset, current_start + len(chunk_text))),
                metadata=dict(fragment.metadata or {}),
            )
        )
    return pieces or [fragment]


def _split_sentences(text: str) -> list[str]:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 1:
        return lines
    return [item.strip() for item in _SENTENCE_BOUNDARY_RE.split(text) if item.strip()]


def _merge_tiny_fragments(fragments: list[_Fragment], target_max: int) -> list[_Fragment]:
    if not fragments:
        return []

    merged: list[_Fragment] = []
    for fragment in fragments:
        if not merged:
            merged.append(fragment)
            continue
        previous = merged[-1]
        if (
            len(previous.text) < max(120, min(CHILD_TARGET_MIN, PARENT_TARGET_MIN) // 2)
            and previous.section_path == fragment.section_path
            and previous.type == fragment.type
            and len(previous.text) + 2 + len(fragment.text) <= target_max
        ):
            merged[-1] = _Fragment(
                type=previous.type,
                text=f"{previous.text}\n\n{fragment.text}".strip(),
                section_path=previous.section_path,
                heading_path=previous.heading_path,
                start_offset=previous.start_offset,
                end_offset=fragment.end_offset,
                metadata=dict(previous.metadata or {}),
            )
        else:
            merged.append(fragment)
    return merged


def _payload_length(payload: list[_Fragment]) -> int:
    return len(_join_fragments(payload))


def _join_fragments(payload: list[_Fragment]) -> str:
    return "\n\n".join(fragment.text.strip() for fragment in payload if fragment.text.strip()).strip()


def _build_search_text(document_title: str | None, section_path: str | None, content: str) -> str:
    titles = [value.strip() for value in (document_title, section_path) if value and value.strip()]
    if titles:
        return ("\n".join(titles) + "\n\n" + content).strip()
    return content.strip()


def _unique_block_types(payload: list[_Fragment]) -> list[str]:
    seen: list[str] = []
    for fragment in payload:
        if fragment.type not in seen:
            seen.append(fragment.type)
    return seen


def _common_section_path(payload: list[_Fragment]) -> str | None:
    if not payload:
        return None
    paths = [fragment.heading_path for fragment in payload if fragment.heading_path]
    if not paths:
        return None
    common = list(paths[0])
    for path in paths[1:]:
        limit = min(len(common), len(path))
        index = 0
        while index < limit and common[index] == path[index]:
            index += 1
        common = common[:index]
        if not common:
            break
    return " > ".join(common) if common else payload[0].section_path


def _shares_lineage(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    if not left or not right:
        return False
    limit = min(len(left), len(right))
    return left[: max(1, limit - 1)] == right[: max(1, limit - 1)]


def _link_chunks(chunks: list[PlannedChunk]) -> list[PlannedChunk]:
    out: list[PlannedChunk] = []
    for index, chunk in enumerate(chunks):
        out.append(
            PlannedChunk(
                local_id=chunk.local_id,
                chunk_kind=chunk.chunk_kind,
                chunk_index=chunk.chunk_index,
                parent_local_id=chunk.parent_local_id,
                prev_local_id=chunks[index - 1].local_id if index > 0 else None,
                next_local_id=chunks[index + 1].local_id if index + 1 < len(chunks) else None,
                section_path=chunk.section_path,
                block_types=list(chunk.block_types),
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                content=chunk.content,
                search_text=chunk.search_text,
                metadata=dict(chunk.metadata or {}),
            )
        )
    return out
