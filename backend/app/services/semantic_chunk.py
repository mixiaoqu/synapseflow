"""Structured chunk planning for document indexing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config.registry import config_registry
from app.utils.document_parse import ParsedBlock, ParsedDocument, ParsedNode, render_parsed_document

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？!?；;\.])")
_BOLD_INTRO_RE = re.compile(r"^\*\*[^*\n]+\*\*$")


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


def _resolve_chunk_offsets(full_text: str, content: str, search_from: int) -> tuple[int, int]:
    if not content:
        return search_from, search_from

    start_offset = full_text.find(content, search_from)
    if start_offset >= 0:
        return start_offset, start_offset + len(content)

    first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
    if first_line:
        start_offset = full_text.find(first_line, search_from)
        if start_offset >= 0:
            return start_offset, start_offset + len(content)

    prefix = content[:80].strip()
    if prefix:
        start_offset = full_text.find(prefix, search_from)
        if start_offset >= 0:
            return start_offset, start_offset + len(content)

    return search_from, search_from + len(content)


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
        parent_content = _fit_tree_content(unit.content, chunk_settings.parent_target_max)
        parent_start, text_cursor = _resolve_chunk_offsets(full_text, parent_content, text_cursor)
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
                search_text=_build_search_text(document_title, unit.section_path, parent_content),
                metadata={
                    "node_type": unit.node_type,
                    "numbering": unit.numbering,
                    "tree_path": list(unit.tree_path),
                    "block_count": max(1, len(unit.children)),
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
            child_content = _fit_tree_content(child.content, chunk_settings.child_target_max)
            child_start, child_cursor = _resolve_chunk_offsets(full_text, child_content, child_cursor)
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
                    search_text=_build_search_text(document_title, unit.section_path, child_content),
                    metadata={
                        "node_type": child.node_type,
                        "numbering": child.numbering,
                        "tree_path": list(child.tree_path),
                        "block_count": 1,
                        "hit_window_hint": {"prev": 0, "next": 0},
                        "parent_chunk_index": parent_index,
                        "child_index_within_parent": child_index,
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
        units: list[_TreeParentUnit] = []
        section_children = [child for child in node.children if child.node_type != "heading"]
        if section_children:
            units.append(
                _build_heading_parent_unit(
                    node,
                    section_children,
                    heading_path=next_heading,
                    chunk_settings=chunk_settings,
                )
            )
        for child in node.children:
            if child.node_type == "heading":
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
    children: list[ParsedNode],
    *,
    heading_path: tuple[str, ...],
    chunk_settings: _ChunkSettings,
) -> _TreeParentUnit:
    heading_line = _render_heading_line(node)
    rendered_children = [_render_tree_node(child).strip() for child in children]
    child_content = "\n\n".join(child for child in rendered_children if child)
    content = "\n\n".join(part for part in (heading_line, child_content) if part.strip()).strip()
    return _TreeParentUnit(
        node_type="heading",
        numbering=None,
        section_path=" > ".join(heading_path) or None,
        block_types=_unique_node_types(children),
        tree_path=list(heading_path),
        content=content,
        children=_build_section_child_units(children, heading_path, chunk_settings=chunk_settings),
    )


def _build_section_child_units(
    nodes: list[ParsedNode],
    heading_path: tuple[str, ...],
    *,
    chunk_settings: _ChunkSettings,
) -> list[_TreeChildUnit]:
    units: list[_TreeChildUnit] = []
    paragraph_buffer: list[str] = []

    def flush_paragraphs() -> None:
        if not paragraph_buffer:
            return
        content = "\n\n".join(paragraph_buffer).strip()
        paragraph_buffer.clear()
        if not content:
            return
        units.append(
            _TreeChildUnit(
                node_type="paragraph",
                numbering=None,
                block_types=["paragraph"],
                tree_path=list(heading_path),
                content=content,
            )
        )

    index = 0
    while index < len(nodes):
        node = nodes[index]
        rendered = _render_tree_node(node).strip()
        if not rendered:
            index += 1
            continue

        if node.node_type == "paragraph":
            next_node = nodes[index + 1] if index + 1 < len(nodes) else None
            next_rendered = _render_tree_node(next_node).strip() if next_node is not None else ""
            if _is_question_text(rendered) and _is_answer_text(next_rendered):
                flush_paragraphs()
                units.append(
                    _TreeChildUnit(
                        node_type="qa_pair",
                        numbering=None,
                        block_types=["paragraph"],
                        tree_path=list(heading_path),
                        content=f"{rendered}\n\n{next_rendered}".strip(),
                    )
                )
                index += 2
                continue
            semantic_group = None
            if not paragraph_buffer:
                semantic_group = _build_semantic_group_after_paragraph(
                    nodes,
                    index,
                    heading_path=heading_path,
                    target_max=chunk_settings.child_target_max,
                )
            if semantic_group is not None:
                unit, next_index = semantic_group
                flush_paragraphs()
                units.append(unit)
                index = next_index
                continue
            paragraph_buffer.append(rendered)
            index += 1
            continue

        flush_paragraphs()
        if node.node_type == "clause":
            clause_unit = _build_clause_parent_unit(node, heading_path, chunk_settings=chunk_settings)
            units.extend(clause_unit.children)
        elif node.node_type == "list":
            units.extend(_list_child_units(node, list(heading_path), chunk_settings.child_target_max))
        elif node.node_type == "table":
            if len(rendered) <= chunk_settings.child_target_max:
                units.append(
                    _TreeChildUnit(
                        node_type="table",
                        numbering=None,
                        block_types=["table"],
                        tree_path=list(heading_path),
                        content=rendered,
                    )
                )
            else:
                units.extend(_table_child_units(node, list(heading_path), chunk_settings.child_target_max))
        else:
            units.append(
                _TreeChildUnit(
                    node_type=node.node_type,
                    numbering=node.numbering,
                    block_types=[node.node_type],
                    tree_path=list(heading_path),
                    content=rendered,
                )
            )
        index += 1

    flush_paragraphs()
    return units


def _build_semantic_group_after_paragraph(
    nodes: list[ParsedNode],
    start_index: int,
    *,
    heading_path: tuple[str, ...],
    target_max: int,
) -> tuple[_TreeChildUnit, int] | None:
    intro = _render_tree_node(nodes[start_index]).strip()
    if not _is_short_semantic_intro(intro):
        return None

    parts = [intro]
    block_types = ["paragraph"]
    index = start_index + 1
    merged_structured = False

    while index < len(nodes):
        node = nodes[index]
        if node.node_type not in {"list", "clause"}:
            break
        rendered = _render_tree_node(node).strip()
        if not rendered or not _is_compact_semantic_body(node, rendered):
            break
        candidate = "\n\n".join([*parts, rendered]).strip()
        if len(candidate) > target_max:
            break
        parts.append(rendered)
        block_types.append(node.node_type)
        merged_structured = True
        index += 1

    if not merged_structured:
        return None

    return (
        _TreeChildUnit(
            node_type="semantic_group",
            numbering=None,
            block_types=_dedupe_preserve_order(block_types),
            tree_path=list(heading_path),
            content="\n\n".join(parts).strip(),
        ),
        index,
    )


def _is_short_semantic_intro(text: str) -> bool:
    intro = text.strip()
    if not intro or len(intro) > 120:
        return False
    if _BOLD_INTRO_RE.match(intro):
        return True
    if "\n" in intro:
        return False
    return intro.endswith(("：", ":"))


def _is_compact_semantic_body(node: ParsedNode, rendered: str) -> bool:
    if len(rendered) > 720:
        return False
    if node.node_type == "list":
        return True
    if node.node_type == "clause":
        return True
    return False


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


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
    children = _list_child_units(node, tree_path, _get_chunk_settings().child_target_max)
    return _TreeParentUnit(
        node_type="list",
        numbering=None,
        section_path=" > ".join(heading_path) or None,
        block_types=["list"],
        tree_path=tree_path,
        content=content,
        children=children,
    )


def _list_child_units(
    node: ParsedNode,
    tree_path: list[str],
    target_max: int,
) -> list[_TreeChildUnit]:
    content = _render_tree_node(node)
    if len(content) <= target_max:
        return [
            _TreeChildUnit(
                node_type="list",
                numbering=None,
                block_types=["list"],
                tree_path=tree_path,
                content=content,
            )
        ]

    units: list[_TreeChildUnit] = []
    current: list[str] = []
    current_length = 0
    for item in node.children:
        item_content = _render_list_item_subtree(item, tree_path, include_self_label=False)
        joiner = 1 if current else 0
        if current and current_length + joiner + len(item_content) > target_max:
            units.append(
                _TreeChildUnit(
                    node_type="list",
                    numbering=None,
                    block_types=["list"],
                    tree_path=tree_path,
                    content="\n".join(current).strip(),
                )
            )
            current = []
            current_length = 0
        current.append(item_content)
        current_length += len(item_content) if not current_length else joiner + len(item_content)

    if current:
        units.append(
            _TreeChildUnit(
                node_type="list",
                numbering=None,
                block_types=["list"],
                tree_path=tree_path,
                content="\n".join(current).strip(),
            )
        )
    return units or [
        _TreeChildUnit(
            node_type="list",
            numbering=None,
            block_types=["list"],
            tree_path=tree_path,
            content=content,
        )
    ]


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
        parts = [_render_heading_line(node)]
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


def _render_heading_line(node: ParsedNode) -> str:
    prefix = "#" * max(1, min(node.level or 1, 6))
    return f"{prefix} {node.text.strip()}"


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
    if node.node_type == "clause" and node.numbering:
        numbering = node.numbering
        if re.fullmatch(r"\d+", numbering):
            numbering = f"{numbering}."
        return f"{numbering} {node.text}".strip()
    return node.text.strip()


def _normalize_marker_text(value: str) -> str:
    return value.strip().strip("*").strip()


def _is_question_text(value: str) -> bool:
    return bool(re.match(r"^Q\d*[：:]", _normalize_marker_text(value), flags=re.IGNORECASE))


def _is_answer_text(value: str) -> bool:
    return bool(re.match(r"^A[：:]", _normalize_marker_text(value), flags=re.IGNORECASE))


def _unique_node_types(nodes: list[ParsedNode]) -> list[str]:
    seen: list[str] = []
    for node in nodes:
        if node.node_type not in seen:
            seen.append(node.node_type)
    return seen


def _fit_tree_content(content: str, target_max: int) -> str:
    content = content.strip()
    if len(content) <= target_max:
        return content
    lines = [line.strip() for line in content.split("\n") if line.strip()]
    if len(lines) <= 1:
        return content[:target_max].strip()
    kept: list[str] = []
    used = 0
    for line in lines:
        gap = 2 if kept else 0
        if kept and used + gap + len(line) > target_max:
            break
        kept.append(line)
        used += gap + len(line)
    return "\n\n".join(kept).strip() or content[:target_max].strip()


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
