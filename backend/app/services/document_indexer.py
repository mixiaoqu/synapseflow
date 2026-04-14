"""Document chunking and embedding index services."""

import asyncio
from typing import Iterable, List, Sequence

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.registry import config_registry
from app.db.models import Document, KnowledgeBase
from app.db.session import AsyncSessionLocal
from app.services.embedding import embed_documents
from app.services.semantic_chunk import VectorIndexChunk, split_for_vector_index
from app.services.vector_store import add_document_chunks, delete_by_document_id


def _chunk_text(content: str, document_title: str | None = None) -> List[VectorIndexChunk]:
    """Split a document into semantic chunks for vector indexing."""
    chunk_cfg = config_registry.get_rag_config().chunk
    return split_for_vector_index(
        content,
        max_chars=chunk_cfg.size,
        overlap=chunk_cfg.overlap,
        document_title=document_title,
    )


def prepare_document_chunks(
    content: str,
    title: str | None = None,
) -> list[VectorIndexChunk]:
    """Build reusable chunk payloads for one document."""
    source = content or ""
    if not source.strip():
        return []
    return _chunk_text(source, title)


def estimate_document_chunk_count(
    content: str,
    title: str | None = None,
) -> int:
    """Estimate how many vector chunks a document will produce."""
    return len(prepare_document_chunks(content, title))


def _prepare_chunk_batches(
    documents: Sequence[tuple[int, str, str | None]],
) -> list[tuple[int, list[VectorIndexChunk]]]:
    prepared: list[tuple[int, list[VectorIndexChunk]]] = []
    for doc_id, content, title in documents:
        prepared.append((doc_id, prepare_document_chunks(content, title)))
    return prepared


async def _write_index_rows(
    db: AsyncSession,
    prepared_docs: Sequence[tuple[int, list[VectorIndexChunk]]],
    vectors_by_doc: Sequence[list[list[float]]],
) -> dict[int, int]:
    counts: dict[int, int] = {}

    for (doc_id, chunks), vectors in zip(prepared_docs, vectors_by_doc):
        await delete_by_document_id(db, doc_id, commit=False)
        if not chunks:
            counts[doc_id] = 0
            continue

        count = await add_document_chunks(
            db,
            doc_id,
            chunks,
            vectors,
            commit=False,
        )
        counts[doc_id] = count

    return counts


async def index_document(
    db: AsyncSession,
    doc_id: int,
    content: str,
    title: str | None = None,
    *,
    commit: bool = True,
) -> int:
    """Rebuild vector index rows for a single document."""
    counts = await index_documents_batch(
        db,
        [(doc_id, content, title)],
        commit=commit,
    )
    return counts.get(doc_id, 0)


async def index_documents_batch(
    db: AsyncSession,
    documents: Sequence[tuple[int, str, str | None]],
    *,
    commit: bool = True,
) -> dict[int, int]:
    """Index multiple documents with one embedding batch and one DB transaction."""
    if not documents:
        return {}

    prepared_docs = _prepare_chunk_batches(documents)
    return await index_prepared_documents_batch(
        db,
        prepared_docs,
        commit=commit,
    )


async def index_prepared_documents_batch(
    db: AsyncSession,
    prepared_docs: Sequence[tuple[int, Sequence[VectorIndexChunk]]],
    *,
    commit: bool = True,
) -> dict[int, int]:
    """Index documents from precomputed chunk payloads."""
    if not prepared_docs:
        return {}

    normalized_docs = [
        (int(doc_id), list(chunks))
        for doc_id, chunks in prepared_docs
    ]
    all_chunks = [chunk.embedding_text for _, chunks in normalized_docs for chunk in chunks]
    all_vectors = await asyncio.to_thread(embed_documents, all_chunks) if all_chunks else []

    vectors_by_doc: list[list[list[float]]] = []
    offset = 0
    for _, chunks in normalized_docs:
        next_offset = offset + len(chunks)
        vectors_by_doc.append(all_vectors[offset:next_offset])
        offset = next_offset

    counts = await _write_index_rows(db, normalized_docs, vectors_by_doc)
    if commit:
        await db.commit()
    return counts


def _chunked(
    items: Sequence[tuple[int, str, str | None]],
    size: int,
) -> Iterable[Sequence[tuple[int, str, str | None]]]:
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
        stmt = select(Document.id, Document.content, Document.title).where(
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
        docs = [(row.id, row.content or "", row.title or "") for row in result.all()]

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
