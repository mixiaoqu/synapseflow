"""Document chunking and embedding index services."""

import asyncio
from datetime import datetime
from typing import Iterable, List, Sequence

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.registry import config_registry
from app.db.models import Document, KnowledgeBase
from app.db.session import AsyncSessionLocal
from app.services.embedding import embed_documents
from app.services.semantic_chunk import split_for_vector_index
from app.services.vector_store import add_document_chunks, delete_by_document_id


def _chunk_text(content: str) -> List[str]:
    """Split a document into semantic chunks for vector indexing."""
    chunk_cfg = config_registry.get_rag_config().chunk
    return split_for_vector_index(
        content,
        max_chars=chunk_cfg.size,
        overlap=chunk_cfg.overlap,
    )


def _prepare_chunk_batches(
    documents: Sequence[tuple[int, str]],
) -> list[tuple[int, list[str]]]:
    prepared: list[tuple[int, list[str]]] = []
    for doc_id, content in documents:
        normalized = (content or "").strip()
        chunks = _chunk_text(normalized) if normalized else []
        prepared.append((doc_id, chunks))
    return prepared


async def _write_index_rows(
    db: AsyncSession,
    prepared_docs: Sequence[tuple[int, list[str]]],
    vectors_by_doc: Sequence[list[list[float]]],
) -> dict[int, int]:
    counts: dict[int, int] = {}
    now = datetime.utcnow()

    for (doc_id, chunks), vectors in zip(prepared_docs, vectors_by_doc):
        await delete_by_document_id(db, doc_id, commit=False)
        if not chunks:
            await db.execute(
                update(Document).where(Document.id == doc_id).values(indexed_at=None)
            )
            counts[doc_id] = 0
            continue

        count = await add_document_chunks(
            db,
            doc_id,
            chunks,
            vectors,
            commit=False,
        )
        await db.execute(update(Document).where(Document.id == doc_id).values(indexed_at=now))
        counts[doc_id] = count

    return counts


async def index_document(
    db: AsyncSession,
    doc_id: int,
    content: str,
    *,
    commit: bool = True,
) -> int:
    """Rebuild vector index rows for a single document."""
    counts = await index_documents_batch(
        db,
        [(doc_id, content)],
        commit=commit,
    )
    return counts.get(doc_id, 0)


async def index_documents_batch(
    db: AsyncSession,
    documents: Sequence[tuple[int, str]],
    *,
    commit: bool = True,
) -> dict[int, int]:
    """Index multiple documents with one embedding batch and one DB transaction."""
    if not documents:
        return {}

    prepared_docs = _prepare_chunk_batches(documents)
    all_chunks = [chunk for _, chunks in prepared_docs for chunk in chunks]
    all_vectors = await asyncio.to_thread(embed_documents, all_chunks) if all_chunks else []

    vectors_by_doc: list[list[list[float]]] = []
    offset = 0
    for _, chunks in prepared_docs:
        next_offset = offset + len(chunks)
        vectors_by_doc.append(all_vectors[offset:next_offset])
        offset = next_offset

    counts = await _write_index_rows(db, prepared_docs, vectors_by_doc)
    if commit:
        await db.commit()
    return counts


def _chunked(items: Sequence[tuple[int, str]], size: int) -> Iterable[Sequence[tuple[int, str]]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def reindex_all(
    *,
    user_id: int,
    team_id: int | None = None,
    knowledge_base_id: int | None = None,
    batch_size: int = 16,
) -> int:
    """Reindex all current documents in batches."""
    async with AsyncSessionLocal() as session:
        stmt = select(Document.id, Document.content).where(
            Document.is_current.is_(True),
            Document.user_id == user_id,
        )
        if knowledge_base_id is not None:
            stmt = stmt.where(Document.knowledge_base_id == knowledge_base_id)
        elif team_id is not None:
            stmt = stmt.join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id).where(
                KnowledgeBase.team_id == team_id,
            )
        result = await session.execute(stmt)
        docs = [(row.id, row.content or "") for row in result.all()]

    total_docs = 0
    for batch in _chunked(docs, max(1, batch_size)):
        async with AsyncSessionLocal() as session:
            try:
                counts = await index_documents_batch(session, batch, commit=True)
                total_docs += len(counts)
            except Exception as exc:
                await session.rollback()
                logger.warning("批量重建索引失败 batch_size={} error={}", len(batch), exc)
    return total_docs
