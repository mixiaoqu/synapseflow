"""Persistence helpers for document chunk relationships."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentChunk, Embedding
from app.services.semantic_chunk import PlannedChunk


@dataclass(frozen=True)
class ParentWindowExpansion:
    child_chunk_id: int
    parent_chunk_id: int | None
    content: str
    parent_content: str | None
    window_child_ids: list[int]


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

    async def expand_parent_windows(
        self,
        *,
        child_chunk_ids: Sequence[int],
        max_parent_chars: int = 1800,
        neighbor_span: int = 1,
    ) -> dict[int, ParentWindowExpansion]:
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
                )
                continue

            parent_row = parent_rows.get(parent_id)
            siblings = child_by_parent.get(parent_id, [])
            hit_indexes = [idx for idx, sibling in enumerate(siblings) if int(sibling.id) in target_ids]
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

            window_rows = [siblings[idx] for idx in sorted(merged_indexes)] or [row]
            window_text = "\n\n".join(item.content for item in window_rows if item.content.strip()).strip()
            parent_text = (parent_row.content if parent_row else "").strip() or None
            content = parent_text if parent_text and len(parent_text) <= max_parent_chars else window_text
            expansions[int(row.id)] = ParentWindowExpansion(
                child_chunk_id=int(row.id),
                parent_chunk_id=parent_id,
                content=content or row.content,
                parent_content=parent_text,
                window_child_ids=[int(item.id) for item in window_rows],
            )

        return expansions
