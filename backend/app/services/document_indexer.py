"""Document chunk persistence and embedding index services."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.registry import config_registry
from app.db.models import Document, KnowledgeBase
from app.db.session import AsyncSessionLocal
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services.embedding import embed_documents
from app.services.graph_extraction import extract_chunk_graphs_batch
from app.services.graph_indexer import DEFAULT_GRAPH_BATCH_SIZE, GraphIndexer
from app.services.graph_models import ChunkGraphExtraction, GraphChunkRecord, GraphEntityRecord, GraphRelationRecord
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


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _choose_preferred_display_name(existing_name: str, incoming_name: str, normalized_name: str) -> str:
    existing_clean = str(existing_name or "").strip()
    incoming_clean = str(incoming_name or "").strip()
    normalized_clean = str(normalized_name or "").strip()
    candidates = [name for name in [existing_clean, incoming_clean] if name]
    if not candidates:
        return normalized_clean

    def _score(name: str) -> tuple[int, int, int]:
        exact_penalty = 0 if name.casefold() != normalized_clean.casefold() else 1
        cjk_bonus = 1 if _contains_cjk(name) else 0
        return (exact_penalty, -cjk_bonus, len(name))

    return min(candidates, key=_score)


def _merge_entity_records(
    existing: GraphEntityRecord,
    incoming: GraphEntityRecord,
) -> GraphEntityRecord:
    attributes = dict(existing.attributes)
    for key, value in incoming.attributes.items():
        if value is None:
            continue
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                continue
            attributes[key] = cleaned
            continue
        attributes[key] = value

    aliases: list[str] = []
    seen: set[str] = set()
    for alias in (*existing.aliases, *incoming.aliases):
        cleaned = str(alias or "").strip()
        if not cleaned or cleaned in seen:
            continue
        aliases.append(cleaned)
        seen.add(cleaned)

    alias_keys: list[str] = []
    seen_alias_keys: set[str] = set()
    for alias_key in (*existing.alias_keys, *incoming.alias_keys):
        cleaned = str(alias_key or "").strip()
        if not cleaned or cleaned in seen_alias_keys:
            continue
        alias_keys.append(cleaned)
        seen_alias_keys.add(cleaned)

    evidence = existing.evidence.strip()
    incoming_evidence = incoming.evidence.strip()
    if incoming_evidence and incoming_evidence not in evidence:
        evidence = f"{evidence}\n{incoming_evidence}".strip() if evidence else incoming_evidence

    entity_type = existing.entity_type
    if entity_type == "OTHER" and incoming.entity_type != "OTHER":
        entity_type = incoming.entity_type

    display_name = _choose_preferred_display_name(
        existing.display_name,
        incoming.display_name,
        existing.normalized_name,
    )

    return GraphEntityRecord(
        team_id=existing.team_id,
        knowledge_base_id=existing.knowledge_base_id,
        document_id=existing.document_id,
        document_chunk_id=existing.document_chunk_id,
        normalized_name=existing.normalized_name,
        display_name=display_name,
        entity_type=entity_type,
        aliases=tuple(aliases),
        attributes=attributes,
        evidence=evidence,
        canonical_name=existing.canonical_name or incoming.canonical_name or display_name,
        alias_keys=tuple(alias_keys),
    )


def _merge_relation_records(
    existing: GraphRelationRecord,
    incoming: GraphRelationRecord,
) -> GraphRelationRecord:
    attributes = dict(existing.attributes)
    for key, value in incoming.attributes.items():
        if value is None:
            continue
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                continue
            attributes[key] = cleaned
            continue
        attributes[key] = value

    evidence = existing.evidence.strip()
    incoming_evidence = incoming.evidence.strip()
    if incoming_evidence and incoming_evidence not in evidence:
        evidence = f"{evidence}\n{incoming_evidence}".strip() if evidence else incoming_evidence

    return GraphRelationRecord(
        team_id=existing.team_id,
        knowledge_base_id=existing.knowledge_base_id,
        document_id=existing.document_id,
        document_chunk_id=existing.document_chunk_id,
        source_normalized_name=existing.source_normalized_name,
        target_normalized_name=existing.target_normalized_name,
        relation_type=existing.relation_type,
        attributes=attributes,
        evidence=evidence,
    )


def _graph_extraction_metadata(extraction: ChunkGraphExtraction) -> dict[str, Any]:
    return {
        "status": "indexed",
        "entities": [
            {
                "normalized_name": entity.normalized_name,
                "display_name": entity.display_name,
                "entity_type": entity.entity_type,
                "aliases": list(entity.aliases),
                "canonical_name": entity.canonical_name,
                "alias_keys": list(entity.alias_keys),
                "attributes": entity.attributes,
                "evidence": entity.evidence,
            }
            for entity in extraction.entities
        ],
        "relations": [
            {
                "source_normalized_name": relation.source_normalized_name,
                "target_normalized_name": relation.target_normalized_name,
                "relation_type": relation.relation_type,
                "attributes": relation.attributes,
                "evidence": relation.evidence,
            }
            for relation in extraction.relations
        ],
    }


def _build_graph_write_preview(
    entities: Sequence[GraphEntityRecord],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for entity in entities[: max(0, limit)]:
        preview.append(
            {
                "normalized_name": entity.normalized_name,
                "display_name": entity.display_name,
                "canonical_name": entity.canonical_name,
                "alias_keys": list(entity.alias_keys),
                "team_id": entity.team_id,
                "knowledge_base_id": entity.knowledge_base_id,
                "document_id": entity.document_id,
                "document_chunk_id": entity.document_chunk_id,
            }
        )
    return preview


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

    logger.bind(document_pipeline_log=True).info(
        "[文档管线] 向量索引开始 docs={}",
        len(prepared_docs),
    )

    for document_id, content, title in prepared_docs:
        document_chunk_ids, chunks = await _load_indexable_chunks(
            db,
            document_id=document_id,
            content=content,
            title=title,
        )
        vector_payloads.append((document_id, document_chunk_ids, chunks))
        embeddings_input.extend(chunk.embedding_text for chunk in chunks)
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 向量索引加载切片 doc_id={} title={} child_chunks={}",
            document_id,
            title or "-",
            len(chunks),
        )

    logger.bind(document_pipeline_log=True).info(
        "[文档管线] 向量 embedding 开始 docs={} chunks={}",
        len(vector_payloads),
        len(embeddings_input),
    )
    all_vectors = await asyncio.to_thread(embed_documents, embeddings_input) if embeddings_input else []
    logger.bind(document_pipeline_log=True).info(
        "[文档管线] 向量 embedding 完成 vectors={}",
        len(all_vectors),
    )

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
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 向量索引写入完成 doc_id={} chunks={}",
            document_id,
            counts[document_id],
        )

    if commit:
        await db.commit()
    logger.bind(document_pipeline_log=True).info(
        "[文档管线] 向量索引完成 docs={} chunks={}",
        len(counts),
        sum(counts.values()),
    )
    return counts


async def index_document_graph(
    db: AsyncSession,
    document_id: int,
    title: str | None = None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    graph_cfg = config_registry.get_graph_config()
    if not (graph_cfg.enabled and graph_cfg.indexing_enabled):
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 图谱索引跳过 doc_id={} reason=disabled",
            document_id,
        )
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
    await store.delete_document_graph(document_id=document_id)
    logger.bind(document_pipeline_log=True).info(
        "[文档管线] 图谱索引开始 doc_id={} title={} child_chunks={}",
        document_id,
        title or "-",
        len(child_rows),
    )

    chunk_records: list[GraphChunkRecord] = []
    entity_records: dict[str, Any] = {}
    mention_rows: list[dict[str, Any]] = []
    relation_records: dict[tuple[str, str, str], Any] = {}

    extraction_items: list[tuple[GraphChunkRecord, str]] = []
    for row in child_rows:
        chunk = GraphChunkRecord(
            team_id=int(document_scope.team_id),
            knowledge_base_id=int(document_scope.knowledge_base_id),
            document_id=document_id,
            document_chunk_id=int(row.id),
            document_title=title,
            section_path=row.section_path,
        )
        extraction_items.append((chunk, row.content or ""))
    extracted_chunks = await extract_chunk_graphs_batch(extraction_items)

    for extracted in extracted_chunks:
        chunk = extracted.chunk
        normalized = normalize_chunk_graph(
            chunk=chunk,
            entities=extracted.entities,
            relations=extracted.relations,
        )
        chunk_records.append(chunk)
        for entity in normalized.entities:
            existing = entity_records.get(entity.normalized_name)
            if existing is None:
                entity_records[entity.normalized_name] = entity
            else:
                entity_records[entity.normalized_name] = _merge_entity_records(existing, entity)
            mention_rows.append(
                {
                    "normalized_name": entity.normalized_name,
                    "team_id": chunk.team_id,
                    "knowledge_base_id": chunk.knowledge_base_id,
                    "document_id": chunk.document_id,
                    "document_chunk_id": chunk.document_chunk_id,
                    "evidence": entity.evidence,
                    "attributes": entity.attributes,
                }
            )
        for relation in normalized.relations:
            relation_key = (
                relation.source_normalized_name,
                relation.relation_type,
                relation.target_normalized_name,
            )
            existing = relation_records.get(relation_key)
            if existing is None:
                relation_records[relation_key] = relation
            else:
                relation_records[relation_key] = _merge_relation_records(existing, relation)

    logger.bind(document_pipeline_log=True).info(
        "[文档管线] 图谱抽取完成 doc_id={} chunks={} entities={} mentions={} relations={}",
        document_id,
        len(chunk_records),
        len(entity_records),
        len(mention_rows),
        len(relation_records),
    )
    logger.bind(document_pipeline_log=True).info(
        "[文档管线] 图谱写入前 doc_id={} team_id={} knowledge_base_id={} chunks={} entities={} mentions={} relations={}",
        document_id,
        int(document_scope.team_id),
        int(document_scope.knowledge_base_id),
        len(chunk_records),
        len(entity_records),
        len(mention_rows),
        len(relation_records),
    )
    logger.bind(document_pipeline_log=True).info(
        "[文档管线] 图谱写入前实体样本 doc_id={} sample={}",
        document_id,
        _build_graph_write_preview(list(entity_records.values())),
    )
    summary = await indexer.index_batch_graph(
        chunks=chunk_records,
        entities=list(entity_records.values()),
        mentions=mention_rows,
        relations=list(relation_records.values()),
        batch_size=DEFAULT_GRAPH_BATCH_SIZE,
    )

    await store.prune_orphan_entities()
    summary["team_id"] = int(document_scope.team_id)
    summary["knowledge_base_id"] = int(document_scope.knowledge_base_id)
    summary["summary_entity_names"] = list(entity_records.keys())
    if commit:
        await db.commit()
    logger.bind(document_pipeline_log=True).info(
        "[文档管线] 图谱索引完成 doc_id={} chunks={} entities={} mentions={} relations={}",
        document_id,
        summary.get("chunks", 0),
        summary.get("entities", 0),
        summary.get("mentions", 0),
        summary.get("relations", 0),
    )
    return summary


async def index_document_graph_chunk(
    db: AsyncSession,
    document_id: int,
    document_chunk_id: int,
    expected_content_hash: str,
    title: str | None = None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    return await index_document_graph_chunks(
        db,
        document_id=document_id,
        document_chunk_ids=[document_chunk_id],
        expected_content_hash=expected_content_hash,
        title=title,
        commit=commit,
    )


async def index_document_graph_chunks(
    db: AsyncSession,
    document_id: int,
    document_chunk_ids: Sequence[int],
    expected_content_hash: str,
    title: str | None = None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    graph_cfg = config_registry.get_graph_config()
    if not (graph_cfg.enabled and graph_cfg.indexing_enabled):
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 图谱 chunk 索引跳过 doc_id={} chunks={} reason=disabled",
            document_id,
            len(document_chunk_ids),
        )
        return {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0}
    if not document_chunk_ids:
        return {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0}

    repository = DocumentChunkRepository(db)
    child_rows = []
    for document_chunk_id in document_chunk_ids:
        child_row = await repository.get_by_id(int(document_chunk_id))
        if child_row is None or int(child_row.document_id) != int(document_id):
            raise ValueError(f"Chunk {document_chunk_id} not found for document {document_id}")
        child_rows.append(child_row)

    document_row = await db.get(Document, document_id)
    if document_row is None or getattr(document_row, "content_hash", None) != expected_content_hash:
        raise ValueError(f"Document {document_id} content changed before graph chunk processing")

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
    extraction_items = [
        (
            GraphChunkRecord(
                team_id=int(document_scope.team_id),
                knowledge_base_id=int(document_scope.knowledge_base_id),
                document_id=document_id,
                document_chunk_id=int(child_row.id),
                document_title=title,
                section_path=child_row.section_path,
            ),
            child_row.content or "",
        )
        for child_row in child_rows
    ]
    extracted_chunks = await extract_chunk_graphs_batch(extraction_items)

    chunk_records: list[GraphChunkRecord] = []
    entity_records: dict[str, GraphEntityRecord] = {}
    mention_rows: list[dict[str, Any]] = []
    relation_records: dict[tuple[str, str, str], GraphRelationRecord] = {}
    rows_by_id = {int(row.id): row for row in child_rows}
    for extracted in extracted_chunks:
        chunk = extracted.chunk
        normalized = normalize_chunk_graph(
            chunk=chunk,
            entities=extracted.entities,
            relations=extracted.relations,
        )
        logger.bind(document_pipeline_log=True).info(
            "[文档管线] 图谱 chunk 写入前 doc_id={} chunk_id={} team_id={} knowledge_base_id={} entities={} relations={} entity_sample={}",
            document_id,
            chunk.document_chunk_id,
            int(chunk.team_id),
            int(chunk.knowledge_base_id),
            len(normalized.entities),
            len(normalized.relations),
            _build_graph_write_preview(list(normalized.entities)),
        )
        chunk_records.append(chunk)
        for entity in normalized.entities:
            existing = entity_records.get(entity.normalized_name)
            if existing is None:
                entity_records[entity.normalized_name] = entity
            else:
                entity_records[entity.normalized_name] = _merge_entity_records(existing, entity)
            mention_rows.append(
                {
                    "normalized_name": entity.normalized_name,
                    "team_id": chunk.team_id,
                    "knowledge_base_id": chunk.knowledge_base_id,
                    "document_id": chunk.document_id,
                    "document_chunk_id": chunk.document_chunk_id,
                    "evidence": entity.evidence,
                    "attributes": entity.attributes,
                }
            )
        for relation in normalized.relations:
            relation_key = (
                relation.source_normalized_name,
                relation.relation_type,
                relation.target_normalized_name,
            )
            existing = relation_records.get(relation_key)
            if existing is None:
                relation_records[relation_key] = relation
            else:
                relation_records[relation_key] = _merge_relation_records(existing, relation)

        child_row = rows_by_id[chunk.document_chunk_id]
        metadata = dict(child_row.metadata_ or {})
        metadata["graph_extraction"] = _graph_extraction_metadata(normalized)
        await repository.update_metadata(int(child_row.id), metadata)

    summary = await indexer.index_batch_graph(
        chunks=chunk_records,
        entities=list(entity_records.values()),
        mentions=mention_rows,
        relations=list(relation_records.values()),
        batch_size=DEFAULT_GRAPH_BATCH_SIZE,
    )

    if commit:
        await db.commit()
    logger.bind(document_pipeline_log=True).info(
        "[文档管线] 图谱 chunk 批量完成 doc_id={} chunks={} entities={} relations={}",
        document_id,
        len(document_chunk_ids),
        summary.get("entities", 0),
        summary.get("relations", 0),
    )
    return summary


async def finalize_document_graph(
    db: AsyncSession,
    document_id: int,
    title: str | None = None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
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

    completed_rows: list[tuple[Any, dict[str, Any]]] = []
    entity_names: set[str] = set()
    relation_keys: set[tuple[str, str, str]] = set()
    for row in child_rows:
        metadata = dict(row.metadata_ or {})
        extraction = metadata.get("graph_extraction") or {}
        if extraction.get("status") != "indexed":
            logger.bind(document_pipeline_log=True).info(
                "[文档管线] 图谱最终合并等待中 doc_id={} missing_chunk_id={}",
                document_id,
                row.id,
            )
            return {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0}
        completed_rows.append((row, extraction))
        for item in extraction.get("entities") or []:
            name = str(item.get("normalized_name") or "").strip()
            if name:
                entity_names.add(name)
        for item in extraction.get("relations") or []:
            source_name = str(item.get("source_normalized_name") or "").strip()
            relation_type = str(item.get("relation_type") or "").strip()
            target_name = str(item.get("target_normalized_name") or "").strip()
            if source_name and relation_type and target_name:
                relation_keys.add((source_name, relation_type, target_name))

    if not completed_rows:
        return {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0}

    store = get_graph_store()
    await store.prune_orphan_entities()
    summary = {
        "chunks": len(completed_rows),
        "entities": len(entity_names),
        "mentions": len(entity_names),
        "relations": len(relation_keys),
        "team_id": int(document_scope.team_id),
        "knowledge_base_id": int(document_scope.knowledge_base_id),
        "summary_entity_names": sorted(entity_names),
    }

    if commit:
        await db.commit()
    logger.bind(document_pipeline_log=True).info(
        "[文档管线] 图谱最终合并完成 doc_id={} chunks={} entities={}",
        document_id,
        len(completed_rows),
        len(entity_names),
    )
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
