"""Persistence helpers for document chunk relationships."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.registry import config_registry
from app.db.models import DocumentChunk, Embedding
from app.services.semantic_chunk import PlannedChunk


@dataclass(frozen=True)
class ParentWindowExpansion:
    child_chunk_id: int
    parent_chunk_id: int | None
    content: str
    parent_content: str | None
    window_child_ids: list[int]
    expansion_mode: str = "window"


class DocumentChunkRepository:
    """Store and query parent/child chunks for one document set."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def replace_document_chunks(
        self,
        *,
        document_id: int,
        parent_chunks: Sequence[PlannedChunk],
        child_chunks: Sequence[PlannedChunk],
    ) -> dict[str, int]:
        await self.db.execute(delete(Embedding).where(Embedding.document_id == document_id))
        await self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

        local_to_db: dict[str, int] = {}
        inserted_rows: list[DocumentChunk] = []

        for chunk in parent_chunks:
            row = DocumentChunk(
                document_id=document_id,
                chunk_kind=chunk.chunk_kind,
                parent_chunk_id=None,
                chunk_index=chunk.chunk_index,
                prev_chunk_id=None,
                next_chunk_id=None,
                section_path=chunk.section_path,
                block_types=list(chunk.block_types),
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                content=chunk.content,
                search_text=chunk.search_text,
                metadata_=dict(chunk.metadata or {}),
            )
            self.db.add(row)
            inserted_rows.append(row)
            await self.db.flush()
            local_to_db[chunk.local_id] = int(row.id)

        for chunk in child_chunks:
            row = DocumentChunk(
                document_id=document_id,
                chunk_kind=chunk.chunk_kind,
                parent_chunk_id=local_to_db.get(chunk.parent_local_id or ""),
                chunk_index=chunk.chunk_index,
                prev_chunk_id=None,
                next_chunk_id=None,
                section_path=chunk.section_path,
                block_types=list(chunk.block_types),
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
                content=chunk.content,
                search_text=chunk.search_text,
                metadata_=dict(chunk.metadata or {}),
            )
            self.db.add(row)
            inserted_rows.append(row)
            await self.db.flush()
            local_to_db[chunk.local_id] = int(row.id)

        by_id = {int(row.id): row for row in inserted_rows}
        for chunk in [*parent_chunks, *child_chunks]:
            row = by_id[local_to_db[chunk.local_id]]
            row.prev_chunk_id = local_to_db.get(chunk.prev_local_id or "")
            row.next_chunk_id = local_to_db.get(chunk.next_local_id or "")

        await self.db.flush()
        return local_to_db

    async def get_child_chunks_for_document(self, document_id: int) -> list[DocumentChunk]:
        result = await self.db.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.chunk_kind == "child",
            )
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(result.scalars().all())

    async def count_child_chunks_for_document(self, document_id: int) -> int:
        result = await self.db.execute(
            select(DocumentChunk.id)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.chunk_kind == "child",
            )
        )
        return len(result.scalars().all())

    async def get_by_id(self, chunk_id: int) -> DocumentChunk | None:
        result = await self.db.execute(select(DocumentChunk).where(DocumentChunk.id == chunk_id))
        return result.scalar_one_or_none()

    async def update_metadata(self, chunk_id: int, metadata: dict) -> None:
        await self.db.execute(
            update(DocumentChunk)
            .where(DocumentChunk.id == chunk_id)
            .values(metadata_=metadata)
        )
        await self.db.flush()

    async def expand_parent_windows(
        self,
        *,
        child_chunk_ids: Sequence[int],
        max_parent_chars: int | None = None,
        neighbor_span: int | None = None,
    ) -> dict[int, ParentWindowExpansion]:
        chunk_cfg = config_registry.get_rag_config().chunk
        resolved_max_parent_chars = (
            max_parent_chars
            if max_parent_chars is not None
            else max(1, int(chunk_cfg.parent_window_max_chars))
        )
        resolved_neighbor_span = (
            neighbor_span
            if neighbor_span is not None
            else max(0, int(chunk_cfg.parent_window_neighbor_span))
        )
        target_ids = [int(item) for item in child_chunk_ids if item is not None]
        if not target_ids:
            return {}

        hit_result = await self.db.execute(
            select(DocumentChunk).where(DocumentChunk.id.in_(target_ids))
        )
        hit_rows = list(hit_result.scalars().all())
        if not hit_rows:
            return {}

        parent_ids = {
            int(row.parent_chunk_id)
            for row in hit_rows
            if row.parent_chunk_id is not None
        }
        parent_rows: dict[int, DocumentChunk] = {}
        if parent_ids:
            parent_result = await self.db.execute(
                select(DocumentChunk).where(DocumentChunk.id.in_(parent_ids))
            )
            parent_rows = {int(row.id): row for row in parent_result.scalars().all()}

        child_by_parent: dict[int, list[DocumentChunk]] = {}
        if parent_ids:
            grouped = await self.db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.parent_chunk_id.in_(parent_ids))
                .order_by(DocumentChunk.parent_chunk_id.asc(), DocumentChunk.chunk_index.asc())
            )
            for row in grouped.scalars().all():
                if row.parent_chunk_id is None:
                    continue
                child_by_parent.setdefault(int(row.parent_chunk_id), []).append(row)

        expansions: dict[int, ParentWindowExpansion] = {}
        for row in hit_rows:
            parent_id = int(row.parent_chunk_id) if row.parent_chunk_id is not None else None
            if parent_id is None:
                expansions[int(row.id)] = ParentWindowExpansion(
                    child_chunk_id=int(row.id),
                    parent_chunk_id=None,
                    content=row.content,
                    parent_content=None,
                    window_child_ids=[int(row.id)],
                    expansion_mode="child_only",
                )
                continue

            parent_row = parent_rows.get(parent_id)
            siblings = child_by_parent.get(parent_id, [])
            expansion = _resolve_parent_window_expansion(
                row=row,
                parent_row=parent_row,
                siblings=siblings,
                target_ids=target_ids,
                resolved_max_parent_chars=resolved_max_parent_chars,
                resolved_neighbor_span=resolved_neighbor_span,
            )
            expansions[int(row.id)] = ParentWindowExpansion(
                child_chunk_id=int(row.id),
                parent_chunk_id=parent_id,
                content=expansion["content"] or row.content,
                parent_content=expansion["parent_content"],
                window_child_ids=list(expansion["window_child_ids"]),
                expansion_mode=str(expansion["expansion_mode"]),
            )

        return expansions


def _resolve_parent_window_expansion(
    *,
    row,
    parent_row,
    siblings: Sequence,
    target_ids: Sequence[int],
    resolved_max_parent_chars: int,
    resolved_neighbor_span: int,
) -> dict[str, object]:
    parent_text = (getattr(parent_row, "content", "") or "").strip() or None
    parent_metadata = dict(getattr(parent_row, "metadata_", None) or {})
    row_metadata = dict(getattr(row, "metadata_", None) or {})
    if _is_structured_parent(parent_metadata):
        focused_rows = _focused_structure_rows(
            row=row,
            siblings=siblings,
            target_ids=target_ids,
        )
        focused_text = _build_structured_focus_content(
            parent_metadata=parent_metadata,
            parent_text=parent_text,
            focused_rows=focused_rows,
            fallback_content=(getattr(row, "content", "") or "").strip(),
            max_chars=resolved_max_parent_chars,
        )
        if parent_text and len(parent_text) <= resolved_max_parent_chars:
            return {
                "content": parent_text,
                "parent_content": parent_text,
                "window_child_ids": [int(item.id) for item in focused_rows],
                "expansion_mode": "parent",
            }
        return {
            "content": focused_text,
            "parent_content": parent_text,
            "window_child_ids": [int(item.id) for item in focused_rows],
            "expansion_mode": "structured_focus",
        }

    window_rows = _neighbor_window_rows(
        row=row,
        siblings=siblings,
        target_ids=target_ids,
        neighbor_span=resolved_neighbor_span,
    )
    window_text = "\n\n".join(item.content for item in window_rows if (item.content or "").strip()).strip()
    content = parent_text if parent_text and len(parent_text) <= resolved_max_parent_chars else window_text
    return {
        "content": content,
        "parent_content": parent_text,
        "window_child_ids": [int(item.id) for item in window_rows],
        "expansion_mode": "parent" if content == parent_text and parent_text else "window",
    }


def _focused_structure_rows(*, row, siblings: Sequence, target_ids: Sequence[int]) -> list:
    focused = [sibling for sibling in siblings if int(sibling.id) in {int(item) for item in target_ids}]
    if focused:
        return focused
    return [row]


def _neighbor_window_rows(*, row, siblings: Sequence, target_ids: Sequence[int], neighbor_span: int) -> list:
    hit_indexes = [idx for idx, sibling in enumerate(siblings) if int(sibling.id) in {int(item) for item in target_ids}]
    current_index = next(
        (idx for idx, sibling in enumerate(siblings) if int(sibling.id) == int(row.id)),
        0,
    )
    merged_indexes: set[int] = set()
    for hit_index in hit_indexes or [current_index]:
        for offset in range(-neighbor_span, neighbor_span + 1):
            candidate = hit_index + offset
            if 0 <= candidate < len(siblings):
                merged_indexes.add(candidate)
    return [siblings[idx] for idx in sorted(merged_indexes)] or [row]


def _is_structured_parent(metadata: dict) -> bool:
    return str(metadata.get("node_type") or "").strip() in {"clause", "list", "table"}


def _build_structured_focus_content(
    *,
    parent_metadata: dict,
    parent_text: str | None,
    focused_rows: Sequence,
    fallback_content: str,
    max_chars: int,
) -> str:
    unique_parts: list[str] = []
    seen: set[str] = set()
    parent_label = _structured_parent_label(parent_metadata, parent_text)
    if parent_label:
        unique_parts.append(parent_label)
        seen.add(parent_label)

    for row in focused_rows:
        content = (getattr(row, "content", "") or "").strip()
        if not content or content in seen:
            continue
        unique_parts.append(content)
        seen.add(content)

    content = "\n\n".join(unique_parts).strip() or fallback_content.strip()
    if len(content) <= max_chars:
        return content

    if len(unique_parts) == 1:
        return unique_parts[0][:max_chars].strip() or fallback_content[:max_chars].strip()

    label = unique_parts[0].strip() if unique_parts else ""
    focused_parts = list(unique_parts[1:]) or [fallback_content.strip()]
    focused_text = "\n\n".join(part for part in focused_parts if part).strip()
    if not label:
        if len(focused_text) <= max_chars:
            return focused_text
        return focused_text[:max_chars].strip() or fallback_content[:max_chars].strip()

    with_label = "\n\n".join(part for part in [label, focused_text] if part).strip()
    if len(with_label) <= max_chars:
        return with_label

    remaining = max_chars - len(label) - 2
    if remaining > 8:
        return "\n\n".join([label, focused_text[:remaining].strip()]).strip()

    kept: list[str] = []
    used = 0
    for part in focused_parts:
        gap = 2 if kept else 0
        if kept and used + gap + len(part) > max_chars:
            break
        kept.append(part)
        used += gap + len(part)
    return "\n\n".join(kept).strip() or fallback_content[:max_chars].strip()


def _structured_parent_label(metadata: dict, parent_text: str | None) -> str:
    tree_path = metadata.get("tree_path") or []
    if isinstance(tree_path, list) and tree_path:
        return str(tree_path[-1]).strip()
    first_line = str(parent_text or "").splitlines()[0].strip() if parent_text else ""
    return first_line
