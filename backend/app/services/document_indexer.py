"""Document chunk persistence, embedding index, and graph index services."""

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
from app.services.graph_models import (
    ChunkGraphExtraction,
    GraphChunkRecord,
    GraphEntityRecord,
    GraphMentionRecord,
    GraphRelationCandidate,
    GraphRelationEvidenceRecord,
    GraphRelationRecord,
    build_chunk_content_hash,
    build_relation_evidence_hash,
    build_relation_evidence_id,
    clean_graph_text,
)
from app.services.graph_normalizer import normalize_chunk_graph
from app.services.graph_store import get_graph_store
from app.services.semantic_chunk import (
    DocumentChunkPlan,
    VectorIndexChunk,
    build_chunk_plan,
    build_vector_index_chunks,
    plan_jsonl_line_chunks,
    plan_text_chunks,
)
from app.services.vector_store import add_document_chunks, delete_by_document_id
from app.utils.document_parse import ParsedDocument, render_parsed_document

GRAPH_EXTRACTION_SCHEMA_VERSION = "graph_alias_identity_v4"


def prepare_document_chunk_plan(
    parsed: ParsedDocument,
    title: str | None = None,
) -> DocumentChunkPlan:
    if str(parsed.metadata.get("document_type") or "").lower() == "jsonl":
        lines = [
            str(line).strip()
            for line in list(parsed.metadata.get("jsonl_lines") or [])
            if str(line).strip()
        ]
        return plan_jsonl_line_chunks(
            lines
            or [
                line.strip()
                for line in render_parsed_document(parsed).splitlines()
                if line.strip()
            ],
            document_title=title or parsed.title,
        )
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
    prepared_docs = [(document_id, content, title) for document_id, content, title in documents]
    return await index_prepared_documents_batch(db, prepared_docs, commit=commit)


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

    logger.bind(document_pipeline_log=True).info("[文档管线] 向量索引开始 docs={}", len(prepared_docs))
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


def _build_chunk_record(
    *,
    team_id: int,
    knowledge_base_id: int,
    document_id: int,
    title: str | None,
    row: Any,
) -> tuple[GraphChunkRecord, str]:
    chunk_text = row.content or ""
    return (
        GraphChunkRecord(
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            document_chunk_id=int(row.id),
            chunk_index=int(row.chunk_index),
            document_title=title,
            section_path=row.section_path,
            content_hash=build_chunk_content_hash(chunk_text),
        ),
        chunk_text,
    )


def _serialize_graph_extraction(extraction: ChunkGraphExtraction) -> dict[str, Any]:
    return {
        "status": "indexed",
        "schema_version": GRAPH_EXTRACTION_SCHEMA_VERSION,
        "content_hash": extraction.chunk.content_hash,
        "entities": [
            {
                "id": entity.id,
                "team_id": entity.team_id,
                "knowledge_base_id": entity.knowledge_base_id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "canonical_name": entity.canonical_name,
                "aliases": list(entity.aliases),
                "description": entity.description,
                "attributes": entity.attributes,
                "tags": list(entity.tags),
            }
            for entity in extraction.entities
        ],
        "relation_candidates": [
            {
                "source_name": relation.source_name,
                "target_name": relation.target_name,
                "relation_type": relation.relation_type,
                "source_entity_type": relation.source_entity_type,
                "target_entity_type": relation.target_entity_type,
                "source_canonical_name": relation.source_canonical_name,
                "target_canonical_name": relation.target_canonical_name,
                "evidence_text": relation.evidence_text,
                "confidence": relation.confidence,
                "attributes": relation.attributes,
            }
            for relation in extraction.relation_candidates
        ],
    }


def _deserialize_graph_extraction(
    *,
    chunk: GraphChunkRecord,
    payload: dict[str, Any],
) -> ChunkGraphExtraction | None:
    if str(payload.get("status") or "").strip() != "indexed":
        return None
    entities: list[GraphEntityRecord] = []
    for item in list(payload.get("entities") or []):
        if not isinstance(item, dict):
            continue
        name = clean_graph_text(item.get("name"))
        entity_id = clean_graph_text(item.get("id"))
        entity_type = clean_graph_text(item.get("entity_type")).upper() or "OTHER"
        if not entity_id or not name:
            continue
        attributes = dict(item.get("attributes") or {})
        canonical_name = (
            clean_graph_text(item.get("canonical_name"))
            or clean_graph_text(item.get("qualified_name"))
            or clean_graph_text(attributes.get("canonical_name"))
            or clean_graph_text(attributes.get("qualified_name"))
            or None
        )
        entities.append(
            GraphEntityRecord(
                id=entity_id,
                team_id=chunk.team_id,
                knowledge_base_id=chunk.knowledge_base_id,
                name=name,
                entity_type=entity_type,
                canonical_name=canonical_name,
                aliases=tuple(
                    alias
                    for alias in (clean_graph_text(value) for value in list(item.get("aliases") or []))
                    if alias
                ),
                description=clean_graph_text(item.get("description")) or None,
                attributes=attributes,
                tags=tuple(
                    tag
                    for tag in (clean_graph_text(value) for value in list(item.get("tags") or []))
                    if tag
                ),
            )
        )

    relation_candidates: list[GraphRelationCandidate] = []
    for item in list(payload.get("relation_candidates") or []):
        if not isinstance(item, dict):
            continue
        source_name = clean_graph_text(item.get("source_name"))
        target_name = clean_graph_text(item.get("target_name"))
        if not source_name or not target_name:
            continue
        relation_candidates.append(
            GraphRelationCandidate(
                source_name=source_name,
                target_name=target_name,
                relation_type=clean_graph_text(item.get("relation_type")).upper() or "RELATED_TO",
                source_entity_type=clean_graph_text(item.get("source_entity_type")).upper() or None,
                target_entity_type=clean_graph_text(item.get("target_entity_type")).upper() or None,
                source_canonical_name=clean_graph_text(item.get("source_canonical_name")) or None,
                target_canonical_name=clean_graph_text(item.get("target_canonical_name")) or None,
                evidence_text=clean_graph_text(item.get("evidence_text")) or None,
                confidence=float(item["confidence"]) if item.get("confidence") is not None else None,
                attributes=dict(item.get("attributes") or {}),
            )
        )

    return ChunkGraphExtraction(
        chunk=chunk,
        entities=entities,
        relation_candidates=relation_candidates,
    )


def _build_graph_extraction_metadata(extraction: ChunkGraphExtraction) -> dict[str, Any]:
    return _serialize_graph_extraction(extraction)


def _chunk_extraction_cache_valid(metadata: dict[str, Any], *, content_hash: str | None) -> bool:
    graph_extraction = dict(metadata.get("graph_extraction") or {})
    if str(graph_extraction.get("status") or "").strip() != "indexed":
        return False
    if clean_graph_text(graph_extraction.get("schema_version")) != GRAPH_EXTRACTION_SCHEMA_VERSION:
        return False
    return clean_graph_text(graph_extraction.get("content_hash")) == clean_graph_text(content_hash)


def _chunk_batches(
    items: Sequence[tuple[GraphChunkRecord, str]],
    *,
    max_chunks: int,
    max_chars: int,
) -> list[list[tuple[GraphChunkRecord, str]]]:
    batches: list[list[tuple[GraphChunkRecord, str]]] = []
    current: list[tuple[GraphChunkRecord, str]] = []
    current_chars = 0
    for item in items:
        chunk_text = item[1]
        chunk_chars = len(chunk_text)
        should_flush = bool(current) and (
            len(current) >= max(1, max_chunks) or current_chars + chunk_chars > max(1, max_chars)
        )
        if should_flush:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += chunk_chars
    if current:
        batches.append(current)
    return batches


async def _extract_batches(
    *,
    items: list[tuple[GraphChunkRecord, str]],
) -> list[ChunkGraphExtraction]:
    if not items:
        return []
    graph_cfg = config_registry.get_graph_config()
    batches = _chunk_batches(
        items,
        max_chunks=graph_cfg.extraction_batch_max_chunks,
        max_chars=graph_cfg.extraction_batch_max_chars,
    )
    semaphore = asyncio.Semaphore(max(1, graph_cfg.extraction_concurrency))

    async def _run_batch(batch: list[tuple[GraphChunkRecord, str]]) -> list[ChunkGraphExtraction]:
        async with semaphore:
            return await extract_chunk_graphs_batch(batch)

    results = await asyncio.gather(*[_run_batch(batch) for batch in batches])
    return [item for batch in results for item in batch]


async def _prepare_chunk_extractions(
    *,
    repository: DocumentChunkRepository,
    rows: Sequence[Any],
    team_id: int,
    knowledge_base_id: int,
    document_id: int,
    title: str | None,
) -> list[ChunkGraphExtraction]:
    ordered_results: dict[int, ChunkGraphExtraction] = {}
    pending_items: list[tuple[GraphChunkRecord, str]] = []
    metadata_updates: list[tuple[int, dict[str, Any]]] = []

    for row in rows:
        chunk, chunk_text = _build_chunk_record(
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            title=title,
            row=row,
        )
        metadata = dict(row.metadata_ or {})
        if _chunk_extraction_cache_valid(metadata, content_hash=chunk.content_hash):
            cached = _deserialize_graph_extraction(
                chunk=chunk,
                payload=dict(metadata.get("graph_extraction") or {}),
            )
            if cached is not None:
                ordered_results[chunk.document_chunk_id] = cached
                continue
        pending_items.append((chunk, chunk_text))

    extracted = await _extract_batches(items=pending_items)
    for extraction in extracted:
        normalized = normalize_chunk_graph(
            chunk=extraction.chunk,
            entities=extraction.entities,
            relation_candidates=extraction.relation_candidates,
        )
        ordered_results[normalized.chunk.document_chunk_id] = normalized
        metadata_updates.append(
            (
                normalized.chunk.document_chunk_id,
                _build_graph_extraction_metadata(normalized),
            )
        )

    for document_chunk_id, graph_metadata in metadata_updates:
        row = next((item for item in rows if int(item.id) == int(document_chunk_id)), None)
        if row is None:
            continue
        metadata = dict(row.metadata_ or {})
        metadata["graph_extraction"] = graph_metadata
        await repository.update_metadata(int(document_chunk_id), metadata)

    return [ordered_results[int(row.id)] for row in rows if int(row.id) in ordered_results]


def _merge_entity_records(existing: GraphEntityRecord, incoming: GraphEntityRecord) -> GraphEntityRecord:
    aliases = tuple(dict.fromkeys([*existing.aliases, *incoming.aliases]).keys())
    tags = tuple(dict.fromkeys([*existing.tags, *incoming.tags]).keys())
    description = existing.description or incoming.description
    attributes = dict(existing.attributes)
    attributes.update({key: value for key, value in incoming.attributes.items() if value is not None})
    return GraphEntityRecord(
        id=existing.id,
        team_id=existing.team_id,
        knowledge_base_id=existing.knowledge_base_id,
        name=existing.name,
        entity_type=existing.entity_type,
        canonical_name=existing.canonical_name or incoming.canonical_name,
        aliases=aliases,
        description=description,
        attributes=attributes,
        tags=tags,
    )


def _entity_lookup_values(entity: GraphEntityRecord) -> set[str]:
    return {
        value.casefold()
        for value in [
            clean_graph_text(entity.name),
            clean_graph_text(entity.canonical_name),
            *[clean_graph_text(alias) for alias in entity.aliases],
        ]
        if value
    }


def _resolve_entity_for_relation(
    entities: Sequence[GraphEntityRecord],
    *,
    name: str,
    entity_type: str | None,
    canonical_name: str | None,
) -> GraphEntityRecord | None:
    cleaned_name = clean_graph_text(name)
    cleaned_type = clean_graph_text(entity_type).upper()
    cleaned_canonical_name = clean_graph_text(canonical_name)
    if cleaned_canonical_name:
        canonical_candidates = [
            entity
            for entity in entities
            if clean_graph_text(entity.canonical_name or entity.name) == cleaned_canonical_name
        ]
        if cleaned_type:
            typed_canonical_candidates = [
                entity for entity in canonical_candidates if entity.entity_type == cleaned_type
            ]
            if len(typed_canonical_candidates) == 1:
                return typed_canonical_candidates[0]
        if len(canonical_candidates) == 1:
            return canonical_candidates[0]
    lookup_name = cleaned_name.casefold()
    typed_candidates = [
        entity
        for entity in entities
        if lookup_name in _entity_lookup_values(entity)
        and (not cleaned_type or entity.entity_type == cleaned_type)
    ]
    if len(typed_candidates) == 1:
        return typed_candidates[0]
    untyped_candidates = [
        entity
        for entity in entities
        if lookup_name in _entity_lookup_values(entity)
    ]
    if len(untyped_candidates) == 1:
        return untyped_candidates[0]
    return None


def _aggregate_graph_records(
    extractions: Sequence[ChunkGraphExtraction],
) -> tuple[
    list[GraphChunkRecord],
    list[GraphEntityRecord],
    list[GraphMentionRecord],
    list[GraphRelationRecord],
    list[GraphRelationEvidenceRecord],
]:
    chunk_records: list[GraphChunkRecord] = []
    entity_records: dict[str, GraphEntityRecord] = {}
    mention_records: dict[tuple[str, int], GraphMentionRecord] = {}
    relation_records: dict[tuple[str, str, str], GraphRelationRecord] = {}
    relation_evidence_records: dict[str, GraphRelationEvidenceRecord] = {}

    for extraction in extractions:
        chunk = extraction.chunk
        chunk_records.append(chunk)
        chunk_entities = list(extraction.entities)
        for entity in chunk_entities:
            existing = entity_records.get(entity.id)
            entity_records[entity.id] = entity if existing is None else _merge_entity_records(existing, entity)
            mention_key = (entity.id, chunk.document_chunk_id)
            mention_records.setdefault(
                mention_key,
                GraphMentionRecord(
                    team_id=chunk.team_id,
                    knowledge_base_id=chunk.knowledge_base_id,
                    entity_id=entity.id,
                    document_id=chunk.document_id,
                    document_chunk_id=chunk.document_chunk_id,
                    mention_text=entity.name,
                ),
            )

        for relation_candidate in extraction.relation_candidates:
            source_entity = _resolve_entity_for_relation(
                chunk_entities,
                name=relation_candidate.source_name,
                entity_type=relation_candidate.source_entity_type,
                canonical_name=relation_candidate.source_canonical_name,
            )
            target_entity = _resolve_entity_for_relation(
                chunk_entities,
                name=relation_candidate.target_name,
                entity_type=relation_candidate.target_entity_type,
                canonical_name=relation_candidate.target_canonical_name,
            )
            if source_entity is None or target_entity is None:
                continue
            relation_key = (
                source_entity.id,
                relation_candidate.relation_type,
                target_entity.id,
            )
            relation_records.setdefault(
                relation_key,
                GraphRelationRecord(
                    team_id=chunk.team_id,
                    knowledge_base_id=chunk.knowledge_base_id,
                    source_entity_id=source_entity.id,
                    target_entity_id=target_entity.id,
                    relation_type=relation_candidate.relation_type,
                ),
            )
            evidence_text = clean_graph_text(relation_candidate.evidence_text)
            if not evidence_text:
                continue
            evidence_hash = build_relation_evidence_hash(
                source_entity_id=source_entity.id,
                target_entity_id=target_entity.id,
                relation_type=relation_candidate.relation_type,
                document_chunk_id=chunk.document_chunk_id,
                evidence_text=evidence_text,
            )
            relation_evidence_records.setdefault(
                evidence_hash,
                GraphRelationEvidenceRecord(
                    id=build_relation_evidence_id(evidence_hash),
                    team_id=chunk.team_id,
                    knowledge_base_id=chunk.knowledge_base_id,
                    source_entity_id=source_entity.id,
                    target_entity_id=target_entity.id,
                    document_id=chunk.document_id,
                    document_chunk_id=chunk.document_chunk_id,
                    relation_type=relation_candidate.relation_type,
                    evidence_text=evidence_text,
                    evidence_hash=evidence_hash,
                    confidence=relation_candidate.confidence,
                    attributes=dict(relation_candidate.attributes or {}),
                ),
            )

    evidence_count_by_relation: dict[tuple[str, str, str], int] = {}
    for evidence in relation_evidence_records.values():
        relation_key = (
            evidence.source_entity_id,
            evidence.relation_type,
            evidence.target_entity_id,
        )
        evidence_count_by_relation[relation_key] = evidence_count_by_relation.get(relation_key, 0) + 1

    finalized_relations = [
        GraphRelationRecord(
            team_id=relation.team_id,
            knowledge_base_id=relation.knowledge_base_id,
            source_entity_id=relation.source_entity_id,
            target_entity_id=relation.target_entity_id,
            relation_type=relation.relation_type,
            evidence_count=evidence_count_by_relation.get(
                (relation.source_entity_id, relation.relation_type, relation.target_entity_id),
                0,
            ),
        )
        for relation in relation_records.values()
    ]
    return (
        chunk_records,
        list(entity_records.values()),
        list(mention_records.values()),
        finalized_relations,
        list(relation_evidence_records.values()),
    )


async def _load_document_scope(
    db: AsyncSession,
    *,
    document_id: int,
) -> tuple[int, int]:
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
    return int(document_scope.team_id), int(document_scope.knowledge_base_id)


async def _write_document_graph(
    *,
    store: Any,
    extractions: Sequence[ChunkGraphExtraction],
    document_id: int,
    team_id: int,
    knowledge_base_id: int,
) -> dict[str, Any]:
    chunk_records, entity_records, mention_records, relation_records, relation_evidence_records = (
        _aggregate_graph_records(extractions)
    )
    indexer = GraphIndexer(store)
    await store.delete_document_graph(
        document_id=document_id,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
    )
    summary = await indexer.index_batch_graph(
        chunks=chunk_records,
        entities=entity_records,
        mentions=mention_records,
        relations=relation_records,
        relation_evidences=relation_evidence_records,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
        batch_size=DEFAULT_GRAPH_BATCH_SIZE,
    )
    await store.prune_orphan_entities(
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
    )
    return summary


async def index_document_graph(
    db: AsyncSession,
    document_id: int,
    title: str | None = None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    graph_cfg = config_registry.get_graph_config()
    if not (graph_cfg.enabled and graph_cfg.indexing_enabled):
        return {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0, "relation_evidences": 0}

    repository = DocumentChunkRepository(db)
    graph_rows = await repository.get_parent_chunks_for_document(document_id)
    team_id, knowledge_base_id = await _load_document_scope(db, document_id=document_id)
    extractions = await _prepare_chunk_extractions(
        repository=repository,
        rows=graph_rows,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        title=title,
    )
    store = get_graph_store()
    summary = await _write_document_graph(
        store=store,
        extractions=extractions,
        document_id=document_id,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
    )
    summary["team_id"] = team_id
    summary["knowledge_base_id"] = knowledge_base_id
    if commit:
        await db.commit()
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
        return {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0, "relation_evidences": 0}
    if not document_chunk_ids:
        return {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0, "relation_evidences": 0}

    repository = DocumentChunkRepository(db)
    graph_rows = []
    for document_chunk_id in document_chunk_ids:
        graph_row = await repository.get_by_id(int(document_chunk_id))
        if graph_row is None or int(graph_row.document_id) != int(document_id):
            raise ValueError(f"Chunk {document_chunk_id} not found for document {document_id}")
        if str(graph_row.chunk_kind) != "parent":
            raise ValueError(f"Chunk {document_chunk_id} is not a graph extraction parent chunk")
        graph_rows.append(graph_row)

    document_row = await db.get(Document, document_id)
    if document_row is None or getattr(document_row, "content_hash", None) != expected_content_hash:
        raise ValueError(f"Document {document_id} content changed before graph chunk processing")

    team_id, knowledge_base_id = await _load_document_scope(db, document_id=document_id)
    extractions = await _prepare_chunk_extractions(
        repository=repository,
        rows=graph_rows,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
        document_id=document_id,
        title=title,
    )
    _, entity_records, mention_records, relation_records, relation_evidence_records = _aggregate_graph_records(extractions)
    if commit:
        await db.commit()
    return {
        "chunks": len(extractions),
        "entities": len(entity_records),
        "mentions": len(mention_records),
        "relations": len(relation_records),
        "relation_evidences": len(relation_evidence_records),
        "team_id": team_id,
        "knowledge_base_id": knowledge_base_id,
    }


async def finalize_document_graph(
    db: AsyncSession,
    document_id: int,
    title: str | None = None,
    *,
    commit: bool = True,
) -> dict[str, Any]:
    graph_cfg = config_registry.get_graph_config()
    if not (graph_cfg.enabled and graph_cfg.indexing_enabled):
        return {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0, "relation_evidences": 0}

    repository = DocumentChunkRepository(db)
    graph_rows = await repository.get_parent_chunks_for_document(document_id)
    team_id, knowledge_base_id = await _load_document_scope(db, document_id=document_id)

    extractions: list[ChunkGraphExtraction] = []
    for row in graph_rows:
        chunk, _chunk_text = _build_chunk_record(
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            title=title,
            row=row,
        )
        metadata = dict(row.metadata_ or {})
        graph_payload = dict(metadata.get("graph_extraction") or {})
        extraction = _deserialize_graph_extraction(chunk=chunk, payload=graph_payload)
        if extraction is None or clean_graph_text(graph_payload.get("content_hash")) != clean_graph_text(chunk.content_hash):
            logger.bind(document_pipeline_log=True).info(
                "[文档管线] 图谱最终合并等待中 doc_id={} missing_chunk_id={}",
                document_id,
                row.id,
            )
            return {"chunks": 0, "entities": 0, "mentions": 0, "relations": 0, "relation_evidences": 0}
        extractions.append(extraction)

    store = get_graph_store()
    summary = await _write_document_graph(
        store=store,
        extractions=extractions,
        document_id=document_id,
        team_id=team_id,
        knowledge_base_id=knowledge_base_id,
    )
    summary["team_id"] = team_id
    summary["knowledge_base_id"] = knowledge_base_id
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
