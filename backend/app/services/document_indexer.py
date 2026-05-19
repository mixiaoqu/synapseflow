"""Document chunk persistence and embedding index services."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.registry import config_registry
from app.db.models import Document, KnowledgeBase
from app.db.session import AsyncSessionLocal
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.embedding import embed_documents
from app.services.graph_extraction import extract_chunk_graph
from app.services.graph_indexer import GraphIndexer
from app.services.graph_models import GraphChunkRecord
from app.services.graph_normalizer import normalize_chunk_graph
from app.services.graph_store import get_graph_store
from app.services.semantic_chunk import DocumentChunkPlan, VectorIndexChunk, build_chunk_plan, build_vector_index_chunks, plan_text_chunks
from app.services.vector_store import add_document_chunks, delete_by_document_id
from app.utils.document_parse import ParsedDocument


def prepare_document_chunk_plan(
    parsed: ParsedDocument,
    title: str | None = None,
) -> DocumentChunkPlan:
    return build_chunk_plan(parsed, document_title=title or parsed.title)


def prepare_text_chunk_plan(
    content: str,
    title: str | None = None,
) -> DocumentChunkPlan:
    return plan_text_chunks(content, document_title=title)


def prepare_document_chunks(
    content: str,
    title: str | None = None,
) -> list[VectorIndexChunk]:
    plan = prepare_text_chunk_plan(content, title)
    return build_vector_index_chunks(plan, document_id=0)


def estimate_document_chunk_count(
    content: str,
    title: str | None = None,
) -> int:
    return len(prepare_document_chunks(content, title))


async def persist_document_chunk_plan(
    db: AsyncSession,
    *,
    document_id: int,
    plan: DocumentChunkPlan,
) -> dict[str, int]:
    repository = DocumentChunkRepository(db)
    return await repository.replace_document_chunks(
        document_id=document_id,
        parent_chunks=plan.parent_chunks,
        child_chunks=plan.child_chunks,
    )


async def _load_indexable_chunks(
    db: AsyncSession,
    *,
    document_id: int,
    content: str,
    title: str | None,
) -> tuple[list[int], list[VectorIndexChunk]]:
    repository = DocumentChunkRepository(db)
    child_rows = await repository.get_child_chunks_for_document(document_id)
    if not child_rows:
        raise ValueError(
            f"Document {document_id} has no persisted child chunks. "
            "Delete and re-upload the document to rebuild the new chunk structure."
        )

    vector_chunks: list[VectorIndexChunk] = []
    document_chunk_ids: list[int] = []
    for row in child_rows:
        metadata = dict(row.metadata_ or {})
        metadata.update(
            {
                "document_id": document_id,
                "document_chunk_id": int(row.id),
                "parent_chunk_id": int(row.parent_chunk_id) if row.parent_chunk_id is not None else None,
                "section_path": row.section_path,
                "block_types": list(row.block_types or []),
                "chunk_index": int(row.chunk_index),
                "prev_child_id": int(row.prev_chunk_id) if row.prev_chunk_id is not None else None,
                "next_child_id": int(row.next_chunk_id) if row.next_chunk_id is not None else None,
                "start_offset": int(row.start_offset),
                "end_offset": int(row.end_offset),
            }
        )
        vector_chunks.append(
            VectorIndexChunk(
                display_text=row.content,
                embedding_text=row.search_text,
                search_text=row.search_text,
                metadata=metadata,
            )
        )
        document_chunk_ids.append(int(row.id))
    return document_chunk_ids, vector_chunks


async def index_document(
    db: AsyncSession,
    doc_id: int,
    content: str,
    title: str | None = None,
    *,
    commit: bool = True,
) -> int:
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
    if not documents:
        return {}

    prepared_docs = []
    for document_id, content, title in documents:
        prepared_docs.append((document_id, content, title))
    return await index_prepared_documents_batch(
        db,
        prepared_docs,
        commit=commit,
    )


async def index_prepared_documents_batch(
    db: AsyncSession,
    prepared_docs: Sequence[tuple[int, str, str | None]],
    *,
    commit: bool = True,
) -> dict[int, int]:
    if not prepared_docs:
        return {}

    counts: dict[int, int] = {}
    embeddings_input: list[str] = []
    vector_payloads: list[tuple[int, list[int], list[VectorIndexChunk]]] = []

    for document_id, content, title in prepared_docs:
        document_chunk_ids, chunks = await _load_indexable_chunks(
            db,
            document_id=document_id,
            content=content,
            title=title,
        )
        vector_payloads.append((document_id, document_chunk_ids, chunks))
        embeddings_input.extend(chunk.embedding_text for chunk in chunks)

    all_vectors = await asyncio.to_thread(embed_documents, embeddings_input) if embeddings_input else []

    offset = 0
    for document_id, document_chunk_ids, chunks in vector_payloads:
        next_offset = offset + len(chunks)
        vectors = all_vectors[offset:next_offset]
        offset = next_offset
        await delete_by_document_id(db, document_id, commit=False)
        if not chunks:
            counts[document_id] = 0
            continue
        counts[document_id] = await add_document_chunks(
            db,
            document_id,
            chunks,
            vectors,
            document_chunk_ids=document_chunk_ids,
            commit=False,
        )

    if commit:
        await db.commit()
    return counts


async def index_document_graph(
    db: AsyncSession,
    document_id: int,
    title: str | None = None,
    *,
    commit: bool = True,
) -> dict[str, int]:
    graph_cfg = config_registry.get_graph_config()
    if not (graph_cfg.enabled and graph_cfg.indexing_enabled):
        return {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0}

    repository = DocumentChunkRepository(db)
    child_rows = await repository.get_child_chunks_for_document(document_id)
    document_scope_result = await db.execute(
        select(
            KnowledgeBase.team_id.label("team_id"),
            Document.knowledge_base_id.label("knowledge_base_id"),
        )
        .join(KnowledgeBase, KnowledgeBase.id == Document.knowledge_base_id)
        .where(Document.id == document_id)
    )
    document_scope = document_scope_result.one_or_none()
    if document_scope is None:
        raise ValueError(f"Document {document_id} must belong to a team and knowledge base")
    store = get_graph_store()
    indexer = GraphIndexer(store)
    summary = {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0}

    await store.delete_document_graph(document_id=document_id)

    for row in child_rows:
        chunk = GraphChunkRecord(
            team_id=int(document_scope.team_id),
            knowledge_base_id=int(document_scope.knowledge_base_id),
            document_id=document_id,
            document_chunk_id=int(row.id),
            document_title=title,
            section_path=row.section_path,
        )
        extracted = await extract_chunk_graph(
            chunk=chunk,
            chunk_text=row.content or "",
        )
        normalized = normalize_chunk_graph(
            chunk=chunk,
            entities=extracted.entities,
            relations=extracted.relations,
        )
        counts = await indexer.index_chunk_graph(
            chunk=chunk,
            entities=normalized.entities,
            relations=normalized.relations,
        )
        for key, value in counts.items():
            summary[key] += value

    await store.prune_orphan_entities()
    if commit:
        await db.commit()
    return summary


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
                logger.warning("Batch reindex failed batch_size={} error={}", len(batch), exc)
    return total_docs
