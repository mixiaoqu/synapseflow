"""Structured chunk planning for document indexing."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config.registry import config_registry
from app.utils.document_parse import ParsedBlock, ParsedDocument, ParsedNode, render_parsed_document

CHUNKING_VERSION = "structure_aware_v2"
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


@dataclass(frozen=True)
class _ChunkSettings:
    parent_target_min: int
    parent_target_max: int
    child_target_min: int
    child_target_max: int
    split_overlap_units: int


def _get_chunk_settings() -> _ChunkSettings:
    chunk_cfg = config_registry.get_rag_config().chunk
    parent_target_max = max(1, int(chunk_cfg.parent_target_max))
    parent_target_min = min(max(1, int(chunk_cfg.parent_target_min)), parent_target_max)
    child_target_max = max(1, int(chunk_cfg.child_target_max))
    child_target_min = min(max(1, int(chunk_cfg.child_target_min)), child_target_max)
    return _ChunkSettings(
        parent_target_min=parent_target_min,
        parent_target_max=parent_target_max,
        child_target_min=child_target_min,
        child_target_max=child_target_max,
        split_overlap_units=max(0, int(chunk_cfg.split_overlap_units)),
    )


def build_chunk_plan(
    parsed: ParsedDocument,
    *,
    document_title: str | None = None,
) -> DocumentChunkPlan:
    chunk_settings = _get_chunk_settings()
    if parsed.roots:
        return _build_tree_chunk_plan(parsed, document_title=document_title, chunk_settings=chunk_settings)
    full_text = render_parsed_document(parsed)
    rendered_blocks = _rendered_blocks_with_offsets(parsed)
    content_blocks = [block for block in rendered_blocks if block.type != "heading" and block.text.strip()]
    parent_payloads = _build_parent_payloads(content_blocks, chunk_settings)
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

        child_payloads = _build_child_payloads(payload, chunk_settings)
        for child_index, child in enumerate(child_payloads):
            child_content = _join_fragments(child)
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
                    content=child_content,
                    search_text=_build_search_text(
                        document_title,
                        _common_section_path(child),
                        child_content,
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


@dataclass(frozen=True)
class _TreeChildUnit:
    node_type: str
    numbering: str | None
    block_types: list[str]
    tree_path: list[str]
    content: str


@dataclass(frozen=True)
class _TreeParentUnit:
    node_type: str
    numbering: str | None
    section_path: str | None
    block_types: list[str]
    tree_path: list[str]
    content: str
    children: list[_TreeChildUnit]


def _resolve_chunk_offsets(
    full_text: str,
    content: str,
    search_from: int,
) -> tuple[int, int]:
    """Resolve character offsets of *content* within *full_text*.

    Returns ``(start_offset, end_offset)`` where ``end_offset`` equals
    ``start_offset + len(content)``.  *search_from* is the leftmost position
    to consider, allowing the caller to enforce forward-only search that
    matches document order.
    """
    if not content:
        return (search_from, search_from)

    pos = full_text.find(content, search_from)
    if pos != -1:
        return (pos, pos + len(content))

    # Fallback 1: search for the first non-empty line (handles slight
    # rendering differences, e.g. clause numbering dot variation).
    first_line = ""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            first_line = stripped
            break
    if first_line:
        pos = full_text.find(first_line, search_from)
        if pos != -1:
            return (pos, pos + len(content))

    # Fallback 2: search for the first 80 characters.
    prefix = content[:80].strip()
    if prefix:
        pos = full_text.find(prefix, search_from)
        if pos != -1:
            return (pos, pos + len(content))

    # Fallback 3: keep the cursor as the best-effort estimate.
    return (search_from, search_from + len(content))


def _build_tree_chunk_plan(
    parsed: ParsedDocument,
    *,
    document_title: str | None,
    chunk_settings: _ChunkSettings,
) -> DocumentChunkPlan:
    full_text = render_parsed_document(parsed)
    parent_units = _collect_tree_parent_units(parsed.roots, chunk_settings=chunk_settings)
    parent_chunks: list[PlannedChunk] = []
    child_chunks: list[PlannedChunk] = []

    text_cursor = 0

    for parent_index, unit in enumerate(parent_units):
        parent_local_id = f"parent-{parent_index}"
        # Parent chunks are context containers and are not embedded directly. Keep
        # the complete structured unit here; retrieval applies its own context
        # budget and can focus on the matching children when the parent is large.
        parent_content = unit.content.strip()
        parent_start, text_cursor = _resolve_chunk_offsets(
            full_text, parent_content, text_cursor
        )
        parent_chunks.append(
            PlannedChunk(
                local_id=parent_local_id,
                chunk_kind="parent",
                chunk_index=parent_index,
                parent_local_id=None,
                prev_local_id=None,
                next_local_id=None,
                section_path=unit.section_path,
                block_types=list(unit.block_types),
                start_offset=parent_start,
                end_offset=text_cursor,
                content=parent_content,
                search_text=_build_search_text(
                    document_title,
                    unit.section_path,
                    parent_content,
                    structure_path=unit.tree_path,
                ),
                metadata={
                    "node_type": unit.node_type,
                    "numbering": unit.numbering,
                    "tree_path": list(unit.tree_path),
                    "block_count": max(1, len(unit.children)),
                    "exceeds_parent_target": len(parent_content) > chunk_settings.parent_target_max,
                },
            )
        )

        child_units = unit.children or [
            _TreeChildUnit(
                node_type=unit.node_type,
                numbering=unit.numbering,
                block_types=list(unit.block_types),
                tree_path=list(unit.tree_path),
                content=parent_content,
            )
        ]
        child_cursor = parent_start
        for child_index, child in enumerate(child_units):
            child_segments = _split_tree_content(child.content, chunk_settings.child_target_max)
            for segment_index, child_content in enumerate(child_segments):
                child_start, child_cursor = _resolve_chunk_offsets(
                    full_text, child_content, child_cursor
                )
                child_chunks.append(
                    PlannedChunk(
                        local_id=f"child-{len(child_chunks)}",
                        chunk_kind="child",
                        chunk_index=len(child_chunks),
                        parent_local_id=parent_local_id,
                        prev_local_id=None,
                        next_local_id=None,
                        section_path=unit.section_path,
                        block_types=list(child.block_types),
                        start_offset=child_start,
                        end_offset=child_cursor,
                        content=child_content,
                        search_text=_build_search_text(
                            document_title,
                            unit.section_path,
                            child_content,
                            structure_path=child.tree_path,
                        ),
                        metadata={
                            "node_type": child.node_type,
                            "numbering": child.numbering,
                            "tree_path": list(child.tree_path),
                            "block_count": 1,
                            "hit_window_hint": {"prev": 0, "next": 0},
                            "parent_chunk_index": parent_index,
                            "child_index_within_parent": child_index,
                            "segment_index": segment_index,
                            "segment_count": len(child_segments),
                        },
                    )
                )

    return DocumentChunkPlan(
        full_text=full_text,
        parent_chunks=_link_chunks(parent_chunks),
        child_chunks=_link_chunks(child_chunks),
    )


def _collect_tree_parent_units(
    roots: list[ParsedNode],
    *,
    chunk_settings: _ChunkSettings,
) -> list[_TreeParentUnit]:
    units: list[_TreeParentUnit] = []
    for node in roots:
        units.extend(_collect_tree_units_for_node(node, heading_path=(), chunk_settings=chunk_settings))
    return units


def _collect_tree_units_for_node(
    node: ParsedNode,
    *,
    heading_path: tuple[str, ...],
    chunk_settings: _ChunkSettings,
) -> list[_TreeParentUnit]:
    if node.node_type == "heading":
        next_heading = heading_path + (node.text.strip(),)
        direct_children = [child for child in node.children if child.node_type != "heading"]
        nested_headings = [child for child in node.children if child.node_type == "heading"]
        units = (
            [
                _build_heading_parent_unit(
                    node,
                    direct_children,
                    heading_path,
                    chunk_settings=chunk_settings,
                )
            ]
            if direct_children
            else []
        )
        for child in nested_headings:
            units.extend(
                _collect_tree_units_for_node(
                    child,
                    heading_path=next_heading,
                    chunk_settings=chunk_settings,
                )
            )
        return units

    if node.node_type == "clause":
        return [_build_clause_parent_unit(node, heading_path, chunk_settings=chunk_settings)]
    if node.node_type == "list":
        return [_build_list_parent_unit(node, heading_path)]
    if node.node_type == "table":
        return [_build_table_parent_unit(node, heading_path, chunk_settings=chunk_settings)]
    if node.node_type in {"paragraph", "code"}:
        return [_build_leaf_parent_unit(node, heading_path)]

    units: list[_TreeParentUnit] = []
    for child in node.children:
        units.extend(
            _collect_tree_units_for_node(
                child,
                heading_path=heading_path,
                chunk_settings=chunk_settings,
            )
        )
    return units


def _build_heading_parent_unit(
    node: ParsedNode,
    direct_children: list[ParsedNode],
    heading_path: tuple[str, ...],
    *,
    chunk_settings: _ChunkSettings,
) -> _TreeParentUnit:
    section_path = " > ".join([*heading_path, node.text.strip()])
    tree_path = [*heading_path, node.text.strip()]
    heading_prefix = "#" * max(1, min(node.level or 1, 6))
    rendered_children: list[str] = []
    for child in direct_children:
        rendered_child = _render_tree_node(child).strip()
        if rendered_child:
            rendered_children.append(rendered_child)
    content = "\n\n".join(
        [f"{heading_prefix} {node.text.strip()}", *rendered_children]
    ).strip()
    child_units = _heading_child_units(
        direct_children,
        tree_path,
        chunk_settings=chunk_settings,
    )
    block_types = list(
        dict.fromkeys(child.node_type for child in direct_children if child.node_type)
    )
    return _TreeParentUnit(
        node_type="heading",
        numbering=None,
        section_path=section_path,
        block_types=block_types or ["heading"],
        tree_path=tree_path,
        content=content,
        children=child_units,
    )


def _heading_child_units(
    children: list[ParsedNode],
    tree_path: list[str],
    *,
    chunk_settings: _ChunkSettings,
) -> list[_TreeChildUnit]:
    rendered: list[tuple[ParsedNode, str]] = []
    for child in children:
        child_content = _render_tree_node(child).strip()
        if child_content:
            rendered.append((child, child_content))
    if not rendered:
        return []

    if len(rendered) == 1 and rendered[0][0].node_type == "clause":
        clause = rendered[0][0]
        if any(child.node_type == "clause" for child in clause.children):
            return _build_clause_parent_unit(
                clause,
                tuple(tree_path),
                chunk_settings=chunk_settings,
            ).children

    combined = "\n\n".join(text for _, text in rendered).strip()
    if len(combined) <= chunk_settings.child_target_max:
        only_type = rendered[0][0].node_type if len(rendered) == 1 else None
        node_type = only_type or ("qa_pair" if _looks_like_qa_group(rendered) else "semantic_group")
        return [
            _TreeChildUnit(
                node_type=node_type,
                numbering=rendered[0][0].numbering if len(rendered) == 1 else None,
                block_types=list(dict.fromkeys(child.node_type for child, _ in rendered)),
                tree_path=list(tree_path),
                content=combined,
            )
        ]

    units: list[_TreeChildUnit] = []
    for child, child_content in rendered:
        if child.node_type == "table":
            units.extend(_table_child_units(child, tree_path, chunk_settings.child_target_max))
            continue
        units.append(
            _TreeChildUnit(
                node_type=child.node_type,
                numbering=child.numbering,
                block_types=[child.node_type],
                tree_path=[*tree_path, _node_label(child)] if _node_label(child) else list(tree_path),
                content=child_content,
            )
        )
    return units


def _looks_like_qa_group(rendered: list[tuple[ParsedNode, str]]) -> bool:
    if len(rendered) < 2:
        return False
    question = rendered[0][1].lstrip("*# \t")
    answer = rendered[1][1].lstrip("*# \t")
    return bool(
        re.match(r"(?i)^q(?:\d+)?\s*[:：]", question)
        and re.match(r"(?i)^a\s*[:：]", answer)
    )


def _build_clause_parent_unit(
    node: ParsedNode,
    heading_path: tuple[str, ...],
    *,
    chunk_settings: _ChunkSettings,
) -> _TreeParentUnit:
    label = _node_label(node)
    tree_path = [*heading_path, label]
    child_units: list[_TreeChildUnit] = []
    intro_parts: list[str] = []

    for child in node.children:
        if child.node_type == "clause":
            child_units.append(
                _TreeChildUnit(
                    node_type="clause",
                    numbering=child.numbering,
                    block_types=["clause"],
                    tree_path=[*tree_path, _node_label(child)],
                    content=_render_clause_subtree(child, tree_path),
                )
            )
        elif child.node_type == "list":
            for list_item in child.children:
                child_units.append(
                    _TreeChildUnit(
                        node_type="list_item",
                        numbering=None,
                        block_types=["list_item"],
                        tree_path=[*tree_path, list_item.text],
                        content=_render_list_item_subtree(list_item, tree_path, include_self_label=False),
                    )
                )
        elif child.node_type == "table":
            child_units.extend(_table_child_units(child, tree_path, chunk_settings.child_target_max))
        else:
            rendered = _render_tree_node(child).strip()
            if rendered:
                intro_parts.append(rendered)

    if intro_parts:
        child_units.insert(
            0,
            _TreeChildUnit(
                node_type="clause",
                numbering=node.numbering,
                block_types=["paragraph"],
                tree_path=list(tree_path),
                content="\n\n".join([label, *intro_parts]).strip(),
            ),
        )

    if not child_units:
        child_units.append(
            _TreeChildUnit(
                node_type="clause",
                numbering=node.numbering,
                block_types=["clause"],
                tree_path=list(tree_path),
                content=_render_tree_node(node),
            )
        )

    return _TreeParentUnit(
        node_type="clause",
        numbering=node.numbering,
        section_path=" > ".join(heading_path) or None,
        block_types=["clause"],
        tree_path=tree_path,
        content=_render_tree_node(node),
        children=child_units,
    )


def _build_list_parent_unit(node: ParsedNode, heading_path: tuple[str, ...]) -> _TreeParentUnit:
    tree_path = list(heading_path)
    content = _render_tree_node(node)
    children = [
        _TreeChildUnit(
            node_type="list_item",
            numbering=None,
            block_types=["list_item"],
            tree_path=[*tree_path, item.text],
            content=_render_list_item_subtree(item, tree_path, include_self_label=False),
        )
        for item in node.children
    ] or [
        _TreeChildUnit(
            node_type="list_item",
            numbering=None,
            block_types=["list_item"],
            tree_path=tree_path,
            content=content,
        )
    ]
    return _TreeParentUnit(
        node_type="list",
        numbering=None,
        section_path=" > ".join(heading_path) or None,
        block_types=["list"],
        tree_path=tree_path,
        content=content,
        children=children,
    )


def _build_table_parent_unit(
    node: ParsedNode,
    heading_path: tuple[str, ...],
    *,
    chunk_settings: _ChunkSettings,
) -> _TreeParentUnit:
    tree_path = list(heading_path)
    content = _render_tree_node(node)
    children = _table_child_units(node, tree_path, chunk_settings.child_target_max) or [
        _TreeChildUnit(
            node_type="table_row_group",
            numbering=None,
            block_types=["table"],
            tree_path=tree_path,
            content=content,
        )
    ]
    return _TreeParentUnit(
        node_type="table",
        numbering=None,
        section_path=" > ".join(heading_path) or None,
        block_types=["table"],
        tree_path=tree_path,
        content=content,
        children=children,
    )


def _build_leaf_parent_unit(node: ParsedNode, heading_path: tuple[str, ...]) -> _TreeParentUnit:
    content = _render_tree_node(node)
    tree_path = [*heading_path, content.splitlines()[0]]
    child = _TreeChildUnit(
        node_type=node.node_type,
        numbering=node.numbering,
        block_types=[node.node_type],
        tree_path=tree_path,
        content=content,
    )
    return _TreeParentUnit(
        node_type=node.node_type,
        numbering=node.numbering,
        section_path=" > ".join(heading_path) or None,
        block_types=[node.node_type],
        tree_path=tree_path,
        content=content,
        children=[child],
    )


def _table_child_units(
    node: ParsedNode,
    tree_path: list[str],
    target_max: int,
) -> list[_TreeChildUnit]:
    header = str(node.metadata.get("header") or "").strip()
    rows = [row.text.strip() for row in node.children if row.text.strip()]
    if not rows:
        return []

    groups: list[list[str]] = []
    current: list[str] = []
    current_length = len(header)
    separator = 1 if header else 0
    for row_text in rows:
        candidate_length = current_length + (separator if current else 0) + len(row_text)
        if current and candidate_length > target_max:
            groups.append(current)
            current = []
            current_length = len(header)
        current.append(row_text)
        current_length = current_length + (separator if len(current) > 1 or header else 0) + len(row_text)
    if current:
        groups.append(current)

    units: list[_TreeChildUnit] = []
    for group in groups:
        label = group[0] if len(group) == 1 else f"{group[0]} .. {group[-1]}"
        content = "\n".join(line for line in [header, *group] if line).strip()
        units.append(
            _TreeChildUnit(
                node_type="table_row_group",
                numbering=None,
                block_types=["table"],
                tree_path=[*tree_path, label],
                content=content,
            )
        )
    return units


def _render_tree_node(node: ParsedNode, *, indent: int = 0) -> str:
    if node.node_type == "heading":
        prefix = "#" * max(1, min(node.level or 1, 6))
        parts = [f"{prefix} {node.text.strip()}"]
        parts.extend(_render_tree_node(child, indent=indent) for child in node.children)
        return "\n\n".join(part for part in parts if part.strip()).strip()
    if node.node_type == "clause":
        parts = [_node_label(node)]
        parts.extend(_render_tree_node(child, indent=indent) for child in node.children)
        return "\n\n".join(part for part in parts if part.strip()).strip()
    if node.node_type == "list":
        return "\n".join(_render_tree_node(child, indent=indent) for child in node.children if child.text or child.children).strip()
    if node.node_type == "list_item":
        line = f"{'  ' * indent}- {node.text}".rstrip()
        child_parts = [_render_tree_node(child, indent=indent + 1) for child in node.children]
        return "\n".join(part for part in [line, *child_parts] if part.strip()).strip()
    if node.node_type == "table":
        header = str(node.metadata.get("header") or "").strip()
        separator = str(node.metadata.get("separator") or "").strip()
        rows = [child.text.strip() for child in node.children if child.text.strip()]
        return "\n".join(line for line in [header, separator, *rows] if line).strip()
    if node.node_type == "code":
        return f"```\n{node.text.strip()}\n```"
    return node.text.strip()


def _render_clause_subtree(node: ParsedNode, ancestor_path: list[str]) -> str:
    return _render_tree_node(node).strip()


def _render_list_item_subtree(
    node: ParsedNode,
    ancestor_path: list[str],
    *,
    include_self_label: bool,
) -> str:
    parts = []
    if include_self_label and ancestor_path:
        parts.append(ancestor_path[-1])
    parts.append(_render_tree_node(node))
    return "\n\n".join(part for part in parts if part.strip()).strip()


def _node_label(node: ParsedNode) -> str:
    # Keep clause numbering rendering consistent with
    # document_parse._render_node so that chunk content matches
    # render_parsed_document output and offsets can be resolved exactly.
    if node.node_type == "clause" and node.numbering:
        numbering = f"{node.numbering}." if node.numbering.isdigit() else node.numbering
        return f"{numbering} {node.text}".strip()
    return node.text.strip()


def _split_tree_content(content: str, target_max: int) -> list[str]:
    """Split one structured leaf without dropping source text.

    Structural units are already the preferred semantic boundaries. This helper
    only handles an individual unit that still exceeds the child budget, choosing
    the latest paragraph, line, or sentence boundary before a hard cut.
    """
    content = content.strip()
    if not content:
        return []
    if len(content) <= target_max:
        return [content]

    minimum_boundary = max(1, target_max // 2)
    segments: list[str] = []
    cursor = 0
    while cursor < len(content):
        hard_end = min(len(content), cursor + target_max)
        end = hard_end
        if hard_end < len(content):
            window = content[cursor:hard_end]
            candidates = [
                window.rfind("\n\n", minimum_boundary),
                window.rfind("\n", minimum_boundary),
            ]
            sentence_matches = list(_SENTENCE_BOUNDARY_RE.finditer(window))
            if sentence_matches:
                candidates.append(sentence_matches[-1].end())
            boundary = max(candidates, default=-1)
            if boundary > 0:
                end = cursor + boundary

        segment = content[cursor:end].strip()
        if segment:
            segments.append(segment)
        cursor = end
        while cursor < len(content) and content[cursor].isspace():
            cursor += 1

    return segments or [content]


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


def plan_jsonl_line_chunks(
    lines: list[str],
    *,
    document_title: str | None = None,
) -> DocumentChunkPlan:
    chunks = [line.strip() for line in lines if line.strip()]
    full_text = "\n".join(chunks)
    if not chunks:
        return DocumentChunkPlan(full_text="", parent_chunks=[], child_chunks=[])

    parent_chunks: list[PlannedChunk] = []
    child_chunks: list[PlannedChunk] = []
    cursor = 0
    for chunk_index, chunk_text in enumerate(chunks):
        start_offset = cursor
        end_offset = start_offset + len(chunk_text)
        parent_local_id = f"parent-{chunk_index}"
        metadata = {
            "chunk_strategy": "jsonl_line",
            "line_no": chunk_index + 1,
        }
        parent_chunks.append(
            PlannedChunk(
                local_id=parent_local_id,
                chunk_kind="parent",
                chunk_index=chunk_index,
                parent_local_id=None,
                prev_local_id=None,
                next_local_id=None,
                section_path=None,
                block_types=["jsonl_line"],
                start_offset=start_offset,
                end_offset=end_offset,
                content=chunk_text,
                search_text=_build_search_text(document_title, None, chunk_text),
                metadata=dict(metadata),
            )
        )
        child_chunks.append(
            PlannedChunk(
                local_id=f"child-{chunk_index}",
                chunk_kind="child",
                chunk_index=chunk_index,
                parent_local_id=parent_local_id,
                prev_local_id=None,
                next_local_id=None,
                section_path=None,
                block_types=["jsonl_line"],
                start_offset=start_offset,
                end_offset=end_offset,
                content=chunk_text,
                search_text=_build_search_text(document_title, None, chunk_text),
                metadata={
                    **metadata,
                    "hit_window_hint": {"prev": 0, "next": 0},
                    "parent_chunk_index": chunk_index,
                    "child_index_within_parent": 0,
                },
            )
        )
        cursor = end_offset + 1

    return DocumentChunkPlan(
        full_text=full_text,
        parent_chunks=_link_chunks(parent_chunks),
        child_chunks=_link_chunks(child_chunks),
    )


def plan_fixed_overlap_chunks(
    text: str,
    *,
    document_title: str | None = None,
) -> DocumentChunkPlan:
    full_text = text.strip()
    if not full_text:
        return DocumentChunkPlan(full_text="", parent_chunks=[], child_chunks=[])

    chunk_cfg = config_registry.get_rag_config().chunk
    chunk_size = max(1, int(chunk_cfg.size))
    chunk_overlap = max(0, int(chunk_cfg.overlap))
    step = max(1, chunk_size - chunk_overlap)

    parent_chunks: list[PlannedChunk] = []
    child_chunks: list[PlannedChunk] = []
    chunk_index = 0
    start_offset = 0

    while start_offset < len(full_text):
        end_offset = min(len(full_text), start_offset + chunk_size)
        chunk_text = full_text[start_offset:end_offset].strip()
        if chunk_text:
            parent_local_id = f"parent-{chunk_index}"
            metadata = {
                "chunk_strategy": "fixed_overlap",
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            }
            parent_chunks.append(
                PlannedChunk(
                    local_id=parent_local_id,
                    chunk_kind="parent",
                    chunk_index=chunk_index,
                    parent_local_id=None,
                    prev_local_id=None,
                    next_local_id=None,
                    section_path=None,
                    block_types=["paragraph"],
                    start_offset=start_offset,
                    end_offset=end_offset,
                    content=chunk_text,
                    search_text=_build_search_text(document_title, None, chunk_text),
                    metadata=dict(metadata),
                )
            )
            child_chunks.append(
                PlannedChunk(
                    local_id=f"child-{chunk_index}",
                    chunk_kind="child",
                    chunk_index=chunk_index,
                    parent_local_id=parent_local_id,
                    prev_local_id=None,
                    next_local_id=None,
                    section_path=None,
                    block_types=["paragraph"],
                    start_offset=start_offset,
                    end_offset=end_offset,
                    content=chunk_text,
                    search_text=_build_search_text(document_title, None, chunk_text),
                    metadata={
                        **metadata,
                        "hit_window_hint": {"prev": 1, "next": 1},
                        "parent_chunk_index": chunk_index,
                        "child_index_within_parent": 0,
                    },
                )
            )
            chunk_index += 1
        if end_offset >= len(full_text):
            break
        start_offset += step

    return DocumentChunkPlan(
        full_text=full_text,
        parent_chunks=_link_chunks(parent_chunks),
        child_chunks=_link_chunks(child_chunks),
    )


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
                item_text = re.sub(r"^\d+[.)]\s+", "", line)
                normalized.append(f"- {item_text}")
            else:
                normalized.append(f"- {line}")
        return "\n".join(normalized)
    if block.type == "code":
        return f"```\n{block.text.strip()}\n```"
    return block.text.strip()


def _build_parent_payloads(
    blocks: list[_RenderedBlock],
    chunk_settings: _ChunkSettings,
) -> list[list[_Fragment]]:
    sections = _split_sections(blocks)
    payloads: list[list[_Fragment]] = []
    pending: list[_Fragment] = []
    pending_length = 0

    for section in sections:
        section_len = _payload_length(section)
        same_lineage = bool(
            pending
            and section
            and _shares_lineage(pending[-1].heading_path, section[0].heading_path)
        )

        should_merge_short_section = (
            pending
            and pending_length < chunk_settings.parent_target_min
            and section_len < chunk_settings.parent_target_min
            and same_lineage
            and pending_length + 2 + section_len <= chunk_settings.parent_target_max
        )

        if pending and not should_merge_short_section:
            payloads.append(pending)
            pending = []
            pending_length = 0

        if not section:
            continue

        section_cursor: list[_Fragment] = []
        section_cursor_length = 0
        for fragment in _expand_block_fragments(
            section,
            chunk_settings.parent_target_max,
            chunk_settings,
        ):
            fragment_length = len(fragment.text)
            joiner = 2 if section_cursor else 0
            if (
                section_cursor
                and section_cursor_length + joiner + fragment_length > chunk_settings.parent_target_max
            ):
                payloads.append(section_cursor)
                section_cursor = []
                section_cursor_length = 0
            section_cursor.append(fragment)
            section_cursor_length += (
                fragment_length if not section_cursor_length else joiner + fragment_length
            )

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


def _build_child_payloads(
    parent_fragments: list[_Fragment],
    chunk_settings: _ChunkSettings,
) -> list[list[_Fragment]]:
    payloads: list[list[_Fragment]] = []
    current: list[_Fragment] = []
    current_length = 0

    for fragment in _expand_fragments_for_children(parent_fragments, chunk_settings):
        fragment_length = len(fragment.text)
        joiner = 2 if current else 0
        if current and current_length + joiner + fragment_length > chunk_settings.child_target_max:
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
    chunk_settings: _ChunkSettings,
) -> list[_Fragment]:
    fragments: list[_Fragment] = []
    for block in blocks:
        fragments.extend(_split_rendered_block(block, target_max, chunk_settings))
    return _merge_tiny_fragments(fragments, target_max, chunk_settings)


def _expand_fragments_for_children(
    parent_fragments: list[_Fragment],
    chunk_settings: _ChunkSettings,
) -> list[_Fragment]:
    fragments: list[_Fragment] = []
    for fragment in parent_fragments:
        fragments.extend(_split_fragment_for_children(fragment, chunk_settings))
    return _merge_tiny_fragments(fragments, chunk_settings.child_target_max, chunk_settings)


def _split_rendered_block(
    block: _RenderedBlock,
    target_max: int,
    chunk_settings: _ChunkSettings,
) -> list[_Fragment]:
    fragment = _Fragment(
        type=block.type,
        text=block.text,
        section_path=block.section_path,
        heading_path=block.heading_path,
        start_offset=block.start_offset,
        end_offset=block.end_offset,
        metadata=dict(block.metadata or {}),
    )
    return _split_fragment(fragment, target_max, chunk_settings)


def _split_fragment_for_children(
    fragment: _Fragment,
    chunk_settings: _ChunkSettings,
) -> list[_Fragment]:
    return _split_fragment(fragment, chunk_settings.child_target_max, chunk_settings)


def _split_fragment(
    fragment: _Fragment,
    target_max: int,
    chunk_settings: _ChunkSettings,
) -> list[_Fragment]:
    if len(fragment.text) <= target_max:
        return [fragment]
    if fragment.type == "table":
        return _split_table_fragment(fragment, target_max, chunk_settings)
    return _split_text_fragment(fragment, target_max, chunk_settings)


def _split_table_fragment(
    fragment: _Fragment,
    target_max: int,
    chunk_settings: _ChunkSettings,
) -> list[_Fragment]:
    rows = [row for row in fragment.text.split("\n") if row.strip()]
    return _split_units(fragment, rows, target_max, chunk_settings)


def _split_text_fragment(
    fragment: _Fragment,
    target_max: int,
    chunk_settings: _ChunkSettings,
) -> list[_Fragment]:
    units = _split_sentences(fragment.text)
    if len(units) <= 1:
        units = [line for line in fragment.text.split("\n\n") if line.strip()]
    if len(units) <= 1:
        units = [fragment.text]
    return _split_units(fragment, units, target_max, chunk_settings)


def _split_units(
    fragment: _Fragment,
    units: list[str],
    target_max: int,
    chunk_settings: _ChunkSettings,
) -> list[_Fragment]:
    if not units:
        return [fragment]
    pieces: list[_Fragment] = []
    current_units: list[str] = []
    current_start = fragment.start_offset

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
            overlap = (
                current_units[-chunk_settings.split_overlap_units:]
                if chunk_settings.split_overlap_units
                else []
            )
            current_units = list(overlap)
            current_start = max(
                fragment.start_offset,
                current_start + max(1, len(chunk_text) - len(joiner.join(overlap))),
            )
        current_units.append(unit)

    if current_units:
        joiner = "\n" if fragment.type == "table" else " "
        chunk_text = joiner.join(current_units).strip()
        pieces.append(
            _Fragment(
                type=fragment.type,
                text=chunk_text,
                section_path=fragment.section_path,
                heading_path=fragment.heading_path,
                start_offset=current_start,
                end_offset=max(
                    current_start,
                    min(fragment.end_offset, current_start + len(chunk_text)),
                ),
                metadata=dict(fragment.metadata or {}),
            )
        )
    return pieces or [fragment]


def _split_sentences(text: str) -> list[str]:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > 1:
        return lines
    return [item.strip() for item in _SENTENCE_BOUNDARY_RE.split(text) if item.strip()]


def _merge_tiny_fragments(
    fragments: list[_Fragment],
    target_max: int,
    chunk_settings: _ChunkSettings,
) -> list[_Fragment]:
    if not fragments:
        return []

    merged: list[_Fragment] = []
    minimum_merge_length = max(
        120,
        min(chunk_settings.child_target_min, chunk_settings.parent_target_min) // 2,
    )
    for fragment in fragments:
        if not merged:
            merged.append(fragment)
            continue
        previous = merged[-1]
        if (
            len(previous.text) < minimum_merge_length
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


def _payload_length(payload: list[_Fragment] | list[_RenderedBlock]) -> int:
    return len(_join_fragments(payload))


def _join_fragments(payload: list[_Fragment] | list[_RenderedBlock]) -> str:
    return "\n\n".join(fragment.text.strip() for fragment in payload if fragment.text.strip()).strip()


def _build_search_text(
    document_title: str | None,
    section_path: str | None,
    content: str,
    *,
    structure_path: list[str] | None = None,
) -> str:
    context_lines: list[str] = []
    seen: set[str] = set()
    resolved_structure_path = " > ".join(
        item.strip() for item in (structure_path or []) if item and item.strip()
    )
    for value in [document_title, resolved_structure_path or section_path]:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen or normalized == content.strip():
            continue
        context_lines.append(normalized)
        seen.add(normalized)
    if context_lines:
        return ("\n".join(context_lines) + "\n\n" + content).strip()
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
        metadata = {
            "chunking_version": CHUNKING_VERSION,
            "content_fingerprint": hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()[:32],
            **dict(chunk.metadata or {}),
        }
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
                metadata=metadata,
            )
        )
    return out
