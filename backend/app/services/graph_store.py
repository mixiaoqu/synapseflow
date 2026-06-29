"""Graph store abstractions used by graph indexing services."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any, Protocol

from loguru import logger

from app.core.config.registry import config_registry
from app.services.graph_models import (
    GraphChunkRecord,
    GraphEntityRecord,
    GraphMentionRecord,
    GraphRelationEvidenceRecord,
    GraphRelationRecord,
    clean_graph_text,
)

_GRAPH_STORE_CACHE: dict[tuple[bool, bool, str, str, str, str, bool], GraphStore] = {}
_GRAPH_STORE_MAX_RETRIES = 3
_GRAPH_STORE_RETRY_DELAY_SECONDS = 1.0


def _serialize_json(value: Any) -> str | None:
    if value in (None, {}, [], ()):
        return None
    return json.dumps(value, ensure_ascii=False)


def _normalize_lookup_value(value: Any) -> str:
    return clean_graph_text(value).casefold()


def _normalize_document_ids(document_ids: Sequence[int] | None) -> list[int] | None:
    if document_ids is None:
        return None
    normalized: list[int] = []
    seen: set[int] = set()
    for item in document_ids:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value <= 0 or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


class GraphStore(Protocol):
    """Minimal async graph-store contract for indexing and retrieval."""

    async def delete_document_graph(
        self,
        *,
        document_id: int,
        team_id: int,
        knowledge_base_id: int,
    ) -> None: ...

    async def delete_knowledge_base_graph(self, *, knowledge_base_id: int, team_id: int) -> None: ...

    async def upsert_chunks(self, chunks: list[GraphChunkRecord]) -> None: ...

    async def upsert_entities(self, entities: list[GraphEntityRecord]) -> None: ...

    async def upsert_mentions(self, mentions: list[GraphMentionRecord]) -> None: ...

    async def upsert_relations(self, relations: list[GraphRelationRecord]) -> None: ...

    async def upsert_relation_evidences(self, evidences: list[GraphRelationEvidenceRecord]) -> None: ...

    async def refresh_related_evidence_counts(self, *, team_id: int, knowledge_base_id: int) -> None: ...

    async def prune_orphan_entities(self, *, team_id: int, knowledge_base_id: int) -> None: ...

    async def lookup_entities_for_grounding(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        candidate: str,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]: ...

    async def search_related_evidence(
        self,
        *,
        entity_names: list[str],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]: ...

    async def search_relation_evidence_for_pairs(
        self,
        *,
        relation_pairs: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]: ...

    async def search_relation_evidence_for_queries(
        self,
        *,
        relation_queries: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]: ...

    async def search_relation_paths(
        self,
        *,
        entity_names: list[str],
        relation_pairs: list[dict[str, Any]],
        relation_queries: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        max_hops: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]: ...


class NullGraphStore:
    async def delete_document_graph(
        self,
        *,
        document_id: int,
        team_id: int,
        knowledge_base_id: int,
    ) -> None:
        return None

    async def delete_knowledge_base_graph(self, *, knowledge_base_id: int, team_id: int) -> None:
        return None

    async def upsert_chunks(self, chunks: list[GraphChunkRecord]) -> None:
        return None

    async def upsert_entities(self, entities: list[GraphEntityRecord]) -> None:
        return None

    async def upsert_mentions(self, mentions: list[GraphMentionRecord]) -> None:
        return None

    async def upsert_relations(self, relations: list[GraphRelationRecord]) -> None:
        return None

    async def upsert_relation_evidences(self, evidences: list[GraphRelationEvidenceRecord]) -> None:
        return None

    async def refresh_related_evidence_counts(self, *, team_id: int, knowledge_base_id: int) -> None:
        return None

    async def prune_orphan_entities(self, *, team_id: int, knowledge_base_id: int) -> None:
        return None

    async def lookup_entities_for_grounding(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        candidate: str,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def search_related_evidence(
        self,
        *,
        entity_names: list[str],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def search_relation_evidence_for_pairs(
        self,
        *,
        relation_pairs: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def search_relation_evidence_for_queries(
        self,
        *,
        relation_queries: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def search_relation_paths(
        self,
        *,
        entity_names: list[str],
        relation_pairs: list[dict[str, Any]],
        relation_queries: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        max_hops: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        return []


class Neo4jGraphStore:
    """Async Neo4j-backed graph store."""

    def __init__(
        self,
        *,
        uri: str,
        username: str,
        password: str,
        database: str,
    ) -> None:
        try:
            from neo4j import AsyncGraphDatabase
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("Neo4j driver is not installed") from exc

        self._database = database
        self._driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

    async def delete_document_graph(
        self,
        *,
        document_id: int,
        team_id: int,
        knowledge_base_id: int,
    ) -> None:
        await self._run(
            """
            MATCH (ev:RelationEvidence)
            WHERE ev.document_id = $document_id
              AND ev.team_id = $team_id
              AND ev.knowledge_base_id = $knowledge_base_id
            DETACH DELETE ev
            """,
            document_id=document_id,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )
        await self._run(
            """
            MATCH (c:Chunk)
            WHERE c.document_id = $document_id
              AND c.team_id = $team_id
              AND c.knowledge_base_id = $knowledge_base_id
            DETACH DELETE c
            """,
            document_id=document_id,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )
        await self.refresh_related_evidence_counts(
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )
        await self.prune_orphan_entities(
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )

    async def delete_knowledge_base_graph(self, *, knowledge_base_id: int, team_id: int) -> None:
        await self._run(
            """
            MATCH (s:EntitySummary)
            WHERE s.team_id = $team_id
              AND s.knowledge_base_id = $knowledge_base_id
            DETACH DELETE s
            """,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )
        await self._run(
            """
            MATCH (ev:RelationEvidence)
            WHERE ev.team_id = $team_id
              AND ev.knowledge_base_id = $knowledge_base_id
            DETACH DELETE ev
            """,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )
        await self._run(
            """
            MATCH (c:Chunk)
            WHERE c.team_id = $team_id
              AND c.knowledge_base_id = $knowledge_base_id
            DETACH DELETE c
            """,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )
        await self._run(
            """
            MATCH (e:Entity)
            WHERE e.team_id = $team_id
              AND e.knowledge_base_id = $knowledge_base_id
            DETACH DELETE e
            """,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )
        await self._run(
            """
            MATCH ()-[r:RELATED]->()
            WHERE r.team_id = $team_id
              AND r.knowledge_base_id = $knowledge_base_id
            DELETE r
            """,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )

    async def upsert_chunks(self, chunks: list[GraphChunkRecord]) -> None:
        if not chunks:
            return None
        rows = [
            {
                "document_chunk_id": chunk.document_chunk_id,
                "team_id": chunk.team_id,
                "knowledge_base_id": chunk.knowledge_base_id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "document_title": chunk.document_title,
                "section_path": chunk.section_path,
                "content_hash": chunk.content_hash,
            }
            for chunk in chunks
        ]
        await self._run(
            """
            UNWIND $rows AS row
            MERGE (c:Chunk {document_chunk_id: row.document_chunk_id})
            ON CREATE SET c.created_at = datetime()
            SET c.team_id = row.team_id,
                c.knowledge_base_id = row.knowledge_base_id,
                c.document_id = row.document_id,
                c.chunk_index = row.chunk_index,
                c.document_title = row.document_title,
                c.section_path = row.section_path,
                c.content_hash = row.content_hash,
                c.updated_at = datetime()
            """,
            rows=rows,
        )

    async def upsert_entities(self, entities: list[GraphEntityRecord]) -> None:
        if not entities:
            return None
        rows = [
            {
                "id": entity.id,
                "team_id": entity.team_id,
                "knowledge_base_id": entity.knowledge_base_id,
                "name": entity.name,
                "entity_type": entity.entity_type,
                "canonical_name": entity.canonical_name,
                "aliases": list(entity.aliases),
                "description": entity.description,
                "attributes_json": _serialize_json(entity.attributes),
                "tags": list(entity.tags),
            }
            for entity in entities
        ]
        await self._run(
            """
            UNWIND $rows AS row
            MERGE (e:Entity {id: row.id})
            ON CREATE SET e.created_at = datetime()
            SET e.team_id = row.team_id,
                e.knowledge_base_id = row.knowledge_base_id,
                e.name = row.name,
                e.entity_type = row.entity_type,
                e.canonical_name = row.canonical_name,
                e.aliases = row.aliases,
                e.description = row.description,
                e.attributes_json = row.attributes_json,
                e.tags = row.tags,
                e.updated_at = datetime()
            """,
            rows=rows,
        )

    async def upsert_mentions(self, mentions: list[GraphMentionRecord]) -> None:
        if not mentions:
            return None
        rows = [
            {
                "team_id": mention.team_id,
                "knowledge_base_id": mention.knowledge_base_id,
                "entity_id": mention.entity_id,
                "document_id": mention.document_id,
                "document_chunk_id": mention.document_chunk_id,
                "mention_text": mention.mention_text,
                "confidence": mention.confidence,
            }
            for mention in mentions
        ]
        await self._run(
            """
            UNWIND $rows AS row
            MATCH (e:Entity {id: row.entity_id})
            MATCH (c:Chunk {document_chunk_id: row.document_chunk_id})
            MERGE (e)-[m:MENTIONED_IN]->(c)
            ON CREATE SET m.created_at = datetime()
            SET m.team_id = row.team_id,
                m.knowledge_base_id = row.knowledge_base_id,
                m.document_id = row.document_id,
                m.mention_text = row.mention_text,
                m.confidence = row.confidence,
                m.updated_at = datetime()
            """,
            rows=rows,
        )

    async def upsert_relations(self, relations: list[GraphRelationRecord]) -> None:
        if not relations:
            return None
        rows = [
            {
                "team_id": relation.team_id,
                "knowledge_base_id": relation.knowledge_base_id,
                "source_entity_id": relation.source_entity_id,
                "target_entity_id": relation.target_entity_id,
                "relation_type": relation.relation_type,
                "evidence_count": relation.evidence_count,
            }
            for relation in relations
        ]
        await self._run(
            """
            UNWIND $rows AS row
            MATCH (source:Entity {id: row.source_entity_id})
            MATCH (target:Entity {id: row.target_entity_id})
            MERGE (source)-[r:RELATED {relation_type: row.relation_type}]->(target)
            ON CREATE SET r.created_at = datetime()
            SET r.team_id = row.team_id,
                r.knowledge_base_id = row.knowledge_base_id,
                r.evidence_count = row.evidence_count,
                r.updated_at = datetime()
            """,
            rows=rows,
        )

    async def upsert_relation_evidences(self, evidences: list[GraphRelationEvidenceRecord]) -> None:
        if not evidences:
            return None
        rows = [
            {
                "id": evidence.id,
                "team_id": evidence.team_id,
                "knowledge_base_id": evidence.knowledge_base_id,
                "source_entity_id": evidence.source_entity_id,
                "target_entity_id": evidence.target_entity_id,
                "document_id": evidence.document_id,
                "document_chunk_id": evidence.document_chunk_id,
                "relation_type": evidence.relation_type,
                "evidence_text": evidence.evidence_text,
                "evidence_hash": evidence.evidence_hash,
                "confidence": evidence.confidence,
                "attributes_json": _serialize_json(evidence.attributes),
            }
            for evidence in evidences
        ]
        await self._run(
            """
            UNWIND $rows AS row
            MATCH (source:Entity {id: row.source_entity_id})
            MATCH (target:Entity {id: row.target_entity_id})
            MATCH (chunk:Chunk {document_chunk_id: row.document_chunk_id})
            MERGE (ev:RelationEvidence {evidence_hash: row.evidence_hash})
            ON CREATE SET ev.id = row.id, ev.created_at = datetime()
            SET ev.team_id = row.team_id,
                ev.knowledge_base_id = row.knowledge_base_id,
                ev.source_entity_id = row.source_entity_id,
                ev.target_entity_id = row.target_entity_id,
                ev.document_id = row.document_id,
                ev.document_chunk_id = row.document_chunk_id,
                ev.relation_type = row.relation_type,
                ev.evidence_text = row.evidence_text,
                ev.confidence = row.confidence,
                ev.attributes_json = row.attributes_json,
                ev.updated_at = datetime()
            MERGE (source)-[:HAS_RELATION_EVIDENCE]->(ev)
            MERGE (ev)-[:EVIDENCE_TARGET]->(target)
            MERGE (ev)-[:FROM_CHUNK]->(chunk)
            """,
            rows=rows,
        )

    async def refresh_related_evidence_counts(self, *, team_id: int, knowledge_base_id: int) -> None:
        await self._run(
            """
            MATCH (source:Entity)-[r:RELATED]->(target:Entity)
            WHERE r.team_id = $team_id
              AND r.knowledge_base_id = $knowledge_base_id
            OPTIONAL MATCH (source)-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(target)
            WITH r, sum(
                CASE
                    WHEN ev.team_id = $team_id
                     AND ev.knowledge_base_id = $knowledge_base_id
                     AND ev.relation_type = r.relation_type
                    THEN 1
                    ELSE 0
                END
            ) AS evidence_count
            SET r.evidence_count = evidence_count,
                r.updated_at = datetime()
            """,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )
        await self._run(
            """
            MATCH ()-[r:RELATED]->()
            WHERE r.team_id = $team_id
              AND r.knowledge_base_id = $knowledge_base_id
              AND coalesce(r.evidence_count, 0) <= 0
            DELETE r
            """,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )

    async def prune_orphan_entities(self, *, team_id: int, knowledge_base_id: int) -> None:
        await self._run(
            """
            MATCH (e:Entity)
            WHERE e.team_id = $team_id
              AND e.knowledge_base_id = $knowledge_base_id
              AND NOT EXISTS {
                MATCH (e)-[:MENTIONED_IN]->(chunk:Chunk)
                WHERE chunk.team_id = $team_id
                  AND chunk.knowledge_base_id = $knowledge_base_id
              }
              AND NOT EXISTS {
                MATCH (e)-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)
                WHERE ev.team_id = $team_id
                  AND ev.knowledge_base_id = $knowledge_base_id
              }
              AND NOT EXISTS {
                MATCH (:Entity)-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(e)
                WHERE ev.team_id = $team_id
                  AND ev.knowledge_base_id = $knowledge_base_id
              }
              AND NOT EXISTS {
                MATCH (e)-[r:RELATED]-(:Entity)
                WHERE r.team_id = $team_id
                  AND r.knowledge_base_id = $knowledge_base_id
              }
            DELETE e
            """,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )

    async def lookup_entities_for_grounding(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        candidate: str,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        normalized_candidate = _normalize_lookup_value(candidate)
        if not normalized_candidate:
            return []
        normalized_document_ids = _normalize_document_ids(allowed_document_ids)
        if normalized_document_ids == []:
            return []
        query = """
        MATCH (e:Entity)
        WHERE e.team_id = $team_id
          AND e.knowledge_base_id = $knowledge_base_id
          AND (
            toLower(e.name) = $candidate
            OR toLower(e.canonical_name) = $candidate
            OR any(alias IN coalesce(e.aliases, []) WHERE toLower(alias) = $candidate)
            OR toLower(coalesce(e.description, "")) CONTAINS $candidate
          )
          AND (
            $allowed_document_ids IS NULL
            OR EXISTS {
              MATCH (e)-[:MENTIONED_IN]->(chunk:Chunk)
              WHERE chunk.document_id IN $allowed_document_ids
            }
            OR EXISTS {
              MATCH (e)-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)
              WHERE ev.document_id IN $allowed_document_ids
            }
            OR EXISTS {
              MATCH (:Entity)-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(e)
              WHERE ev.document_id IN $allowed_document_ids
            }
          )
        RETURN
            e.id AS entity_id,
            e.name AS name,
            e.entity_type AS entity_type,
            e.canonical_name AS canonical_name,
            coalesce(e.aliases, []) AS aliases,
            coalesce(e.description, "") AS description,
            coalesce(e.tags, []) AS tags
        LIMIT 12
        """
        return await self._fetch_all(
            query,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            candidate=normalized_candidate,
            allowed_document_ids=normalized_document_ids,
        )

    async def search_related_evidence(
        self,
        *,
        entity_names: list[str],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        normalized_names = [_normalize_lookup_value(item) for item in entity_names if _normalize_lookup_value(item)]
        if not normalized_names:
            return []
        normalized_document_ids = _normalize_document_ids(allowed_document_ids)
        if normalized_document_ids == []:
            return []
        query = """
        MATCH (anchor:Entity)
        WHERE anchor.team_id = $team_id
          AND anchor.knowledge_base_id = $knowledge_base_id
          AND (
            toLower(anchor.name) IN $entity_names
            OR toLower(anchor.canonical_name) IN $entity_names
            OR any(alias IN coalesce(anchor.aliases, []) WHERE toLower(alias) IN $entity_names)
          )
        CALL {
          WITH anchor
          MATCH (anchor)-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(other:Entity)
          WHERE $allowed_document_ids IS NULL OR ev.document_id IN $allowed_document_ids
          OPTIONAL MATCH (ev)-[:FROM_CHUNK]->(chunk:Chunk)
          RETURN ev, anchor AS source_entity, other AS target_entity, chunk
          UNION
          WITH anchor
          MATCH (other:Entity)-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(anchor)
          WHERE $allowed_document_ids IS NULL OR ev.document_id IN $allowed_document_ids
          OPTIONAL MATCH (ev)-[:FROM_CHUNK]->(chunk:Chunk)
          RETURN ev, other AS source_entity, anchor AS target_entity, chunk
        }
        RETURN DISTINCT
            ev.document_id AS document_id,
            ev.document_chunk_id AS document_chunk_id,
            coalesce(chunk.document_title, "Graph relation evidence") AS document_title,
            chunk.section_path AS section_path,
            ev.relation_type AS relation_type,
            ev.evidence_text AS evidence,
            source_entity.id AS source_entity_id,
            source_entity.name AS source_name,
            source_entity.entity_type AS source_entity_type,
            target_entity.id AS target_entity_id,
            target_entity.name AS target_name,
            target_entity.entity_type AS target_entity_type,
            [source_entity.name, target_entity.name] AS matched_entities
        LIMIT $limit
        """
        return await self._fetch_all(
            query,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            entity_names=normalized_names,
            allowed_document_ids=normalized_document_ids,
            limit=max(1, int(limit)),
        )

    async def search_relation_evidence_for_pairs(
        self,
        *,
        relation_pairs: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        rows = [
            {
                "source": _normalize_lookup_value(item.get("source")),
                "target": _normalize_lookup_value(item.get("target")),
            }
            for item in relation_pairs
            if _normalize_lookup_value(item.get("source")) and _normalize_lookup_value(item.get("target"))
        ]
        if not rows:
            return []
        normalized_document_ids = _normalize_document_ids(allowed_document_ids)
        if normalized_document_ids == []:
            return []
        query = """
        UNWIND $rows AS row
        MATCH (source:Entity)-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(target:Entity)
        WHERE ev.team_id = $team_id
          AND ev.knowledge_base_id = $knowledge_base_id
          AND ($allowed_document_ids IS NULL OR ev.document_id IN $allowed_document_ids)
          AND (
            toLower(source.name) = row.source
            OR toLower(source.canonical_name) = row.source
            OR any(alias IN coalesce(source.aliases, []) WHERE toLower(alias) = row.source)
          )
          AND (
            toLower(target.name) = row.target
            OR toLower(target.canonical_name) = row.target
            OR any(alias IN coalesce(target.aliases, []) WHERE toLower(alias) = row.target)
          )
        OPTIONAL MATCH (ev)-[:FROM_CHUNK]->(chunk:Chunk)
        RETURN DISTINCT
            ev.document_id AS document_id,
            ev.document_chunk_id AS document_chunk_id,
            coalesce(chunk.document_title, "Graph relation evidence") AS document_title,
            chunk.section_path AS section_path,
            ev.relation_type AS relation_type,
            ev.evidence_text AS evidence,
            source.id AS source_entity_id,
            source.name AS source_name,
            source.entity_type AS source_entity_type,
            target.id AS target_entity_id,
            target.name AS target_name,
            target.entity_type AS target_entity_type,
            [source.name, target.name] AS matched_entities
        LIMIT $limit
        """
        return await self._fetch_all(
            query,
            rows=rows,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            allowed_document_ids=normalized_document_ids,
            limit=max(1, int(limit)),
        )

    async def search_relation_evidence_for_queries(
        self,
        *,
        relation_queries: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        rows = [
            {
                "anchor_entity": _normalize_lookup_value(item.get("anchor_entity")),
                "target_entity": _normalize_lookup_value(item.get("target_entity")),
                "direction": clean_graph_text(item.get("direction")).lower() or "outgoing",
            }
            for item in relation_queries
            if _normalize_lookup_value(item.get("anchor_entity"))
        ]
        if not rows:
            return []
        normalized_document_ids = _normalize_document_ids(allowed_document_ids)
        if normalized_document_ids == []:
            return []
        query = """
        UNWIND $rows AS row
        MATCH (anchor:Entity)
        WHERE anchor.team_id = $team_id
          AND anchor.knowledge_base_id = $knowledge_base_id
          AND (
            toLower(anchor.name) = row.anchor_entity
            OR toLower(anchor.canonical_name) = row.anchor_entity
            OR any(alias IN coalesce(anchor.aliases, []) WHERE toLower(alias) = row.anchor_entity)
          )
        CALL {
          WITH anchor, row
          MATCH (anchor)-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(other:Entity)
          WHERE row.direction <> 'incoming'
            AND ($allowed_document_ids IS NULL OR ev.document_id IN $allowed_document_ids)
            AND (
              row.target_entity = ''
              OR toLower(other.name) = row.target_entity
              OR toLower(other.canonical_name) = row.target_entity
              OR any(alias IN coalesce(other.aliases, []) WHERE toLower(alias) = row.target_entity)
            )
          RETURN anchor AS source_entity, other AS target_entity, ev
          UNION
          WITH anchor, row
          MATCH (other:Entity)-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(anchor)
          WHERE row.direction = 'incoming'
            AND ($allowed_document_ids IS NULL OR ev.document_id IN $allowed_document_ids)
            AND (
              row.target_entity = ''
              OR toLower(other.name) = row.target_entity
              OR toLower(other.canonical_name) = row.target_entity
              OR any(alias IN coalesce(other.aliases, []) WHERE toLower(alias) = row.target_entity)
            )
          RETURN other AS source_entity, anchor AS target_entity, ev
        }
        OPTIONAL MATCH (ev)-[:FROM_CHUNK]->(chunk:Chunk)
        RETURN DISTINCT
            ev.document_id AS document_id,
            ev.document_chunk_id AS document_chunk_id,
            coalesce(chunk.document_title, "Graph relation evidence") AS document_title,
            chunk.section_path AS section_path,
            ev.relation_type AS relation_type,
            ev.evidence_text AS evidence,
            source_entity.id AS source_entity_id,
            source_entity.name AS source_name,
            source_entity.entity_type AS source_entity_type,
            target_entity.id AS target_entity_id,
            target_entity.name AS target_name,
            target_entity.entity_type AS target_entity_type,
            [source_entity.name, target_entity.name] AS matched_entities
        LIMIT $limit
        """
        return await self._fetch_all(
            query,
            rows=rows,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            allowed_document_ids=normalized_document_ids,
            limit=max(1, int(limit)),
        )

    async def search_relation_paths(
        self,
        *,
        entity_names: list[str],
        relation_pairs: list[dict[str, Any]],
        relation_queries: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        max_hops: int,
        limit: int,
        allowed_document_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        resolved_limit = max(1, int(limit))
        resolved_max_hops = max(2, min(int(max_hops or 2), 4))
        hop_pattern = f"*1..{resolved_max_hops}"
        rows: list[dict[str, Any]] = []
        normalized_document_ids = _normalize_document_ids(allowed_document_ids)
        if normalized_document_ids == []:
            return []

        async def _collect(query: str, **params: Any) -> None:
            rows.extend(await self._fetch_all(query, **params))

        def _apply_hop_pattern(query: str) -> str:
            return query.replace("__HOP_PATTERN__", hop_pattern)

        pair_rows = [
            {
                "source": _normalize_lookup_value(item.get("source")),
                "target": _normalize_lookup_value(item.get("target")),
            }
            for item in relation_pairs
            if _normalize_lookup_value(item.get("source")) and _normalize_lookup_value(item.get("target"))
        ]
        if pair_rows:
            await _collect(
                _apply_hop_pattern(
                    """
                    UNWIND $rows AS row
                    MATCH (source:Entity), (target:Entity)
                    WHERE source.team_id = $team_id
                      AND source.knowledge_base_id = $knowledge_base_id
                      AND target.team_id = $team_id
                      AND target.knowledge_base_id = $knowledge_base_id
                      AND (
                        toLower(source.name) = row.source
                        OR toLower(source.canonical_name) = row.source
                        OR any(alias IN coalesce(source.aliases, []) WHERE toLower(alias) = row.source)
                      )
                      AND (
                        toLower(target.name) = row.target
                        OR toLower(target.canonical_name) = row.target
                        OR any(alias IN coalesce(target.aliases, []) WHERE toLower(alias) = row.target)
                      )
                    MATCH p = shortestPath((source)-[:RELATED__HOP_PATTERN__]->(target))
                    WITH p, nodes(p) AS path_nodes, relationships(p) AS path_relationships
                    WHERE $allowed_document_ids IS NULL OR all(index IN range(0, size(path_relationships) - 1) WHERE EXISTS {
                      MATCH (path_nodes[index])-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(path_nodes[index + 1])
                      WHERE ev.team_id = $team_id
                        AND ev.knowledge_base_id = $knowledge_base_id
                        AND ev.relation_type = path_relationships[index].relation_type
                        AND ev.document_id IN $allowed_document_ids
                    })
                    RETURN
                      [node IN path_nodes | {entity_id: node.id, name: node.name, entity_type: node.entity_type}] AS path_entities,
                      [rel IN path_relationships | {relation_type: rel.relation_type}] AS path_relations
                    LIMIT $limit
                    """
                ),
                rows=pair_rows,
                team_id=team_id,
                knowledge_base_id=knowledge_base_id,
                allowed_document_ids=normalized_document_ids,
                limit=resolved_limit,
            )

        if not pair_rows and len(entity_names) >= 2:
            normalized_names = [_normalize_lookup_value(item) for item in entity_names if _normalize_lookup_value(item)]
            await _collect(
                _apply_hop_pattern(
                    """
                    UNWIND $entity_names AS source_name
                    UNWIND $entity_names AS target_name
                    WITH source_name, target_name
                    WHERE source_name < target_name
                    MATCH (source:Entity), (target:Entity)
                    WHERE source.team_id = $team_id
                      AND source.knowledge_base_id = $knowledge_base_id
                      AND target.team_id = $team_id
                      AND target.knowledge_base_id = $knowledge_base_id
                      AND (
                        toLower(source.name) = source_name
                        OR toLower(source.canonical_name) = source_name
                        OR any(alias IN coalesce(source.aliases, []) WHERE toLower(alias) = source_name)
                      )
                      AND (
                        toLower(target.name) = target_name
                        OR toLower(target.canonical_name) = target_name
                        OR any(alias IN coalesce(target.aliases, []) WHERE toLower(alias) = target_name)
                      )
                    MATCH p = shortestPath((source)-[:RELATED__HOP_PATTERN__]-(target))
                    WITH p, nodes(p) AS path_nodes, relationships(p) AS path_relationships
                    WHERE $allowed_document_ids IS NULL OR all(index IN range(0, size(path_relationships) - 1) WHERE (
                      EXISTS {
                        MATCH (path_nodes[index])-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(path_nodes[index + 1])
                        WHERE ev.team_id = $team_id
                          AND ev.knowledge_base_id = $knowledge_base_id
                          AND ev.relation_type = path_relationships[index].relation_type
                          AND ev.document_id IN $allowed_document_ids
                      }
                    ) OR (
                      EXISTS {
                        MATCH (path_nodes[index + 1])-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(path_nodes[index])
                        WHERE ev.team_id = $team_id
                          AND ev.knowledge_base_id = $knowledge_base_id
                          AND ev.relation_type = path_relationships[index].relation_type
                          AND ev.document_id IN $allowed_document_ids
                      }
                    ))
                    RETURN
                      [node IN path_nodes | {entity_id: node.id, name: node.name, entity_type: node.entity_type}] AS path_entities,
                      [rel IN path_relationships | {relation_type: rel.relation_type}] AS path_relations
                    LIMIT $limit
                    """
                ),
                entity_names=normalized_names[:4],
                team_id=team_id,
                knowledge_base_id=knowledge_base_id,
                allowed_document_ids=normalized_document_ids,
                limit=resolved_limit,
            )

        normalized_rows: list[dict[str, Any]] = []
        for row in rows[:resolved_limit]:
            path_entities = [dict(item) for item in list(row.get("path_entities") or []) if isinstance(item, dict)]
            path_relations = [dict(item) for item in list(row.get("path_relations") or []) if isinstance(item, dict)]
            if len(path_entities) < 2 or not path_relations:
                continue
            matched_entities = [clean_graph_text(item.get("name")) for item in path_entities if clean_graph_text(item.get("name"))]
            signature_parts: list[str] = []
            for index, entity in enumerate(path_entities):
                entity_name = clean_graph_text(entity.get("name"))
                if not entity_name:
                    continue
                signature_parts.append(entity_name)
                if index < len(path_relations):
                    signature_parts.append(f"-[{clean_graph_text(path_relations[index].get('relation_type')) or 'RELATED_TO'}]->")
            signature = " ".join(signature_parts).strip()
            evidence_rows: list[dict[str, Any]] = []
            for source_entity, target_entity, relation in zip(path_entities, path_entities[1:], path_relations):
                evidence_query = """
                MATCH (source:Entity {id: $source_entity_id})-[:HAS_RELATION_EVIDENCE]->(ev:RelationEvidence)-[:EVIDENCE_TARGET]->(target:Entity {id: $target_entity_id})
                WHERE ev.team_id = $team_id
                  AND ev.knowledge_base_id = $knowledge_base_id
                  AND ev.relation_type = $relation_type
                  AND ($allowed_document_ids IS NULL OR ev.document_id IN $allowed_document_ids)
                OPTIONAL MATCH (ev)-[:FROM_CHUNK]->(chunk:Chunk)
                RETURN
                    ev.evidence_text AS evidence,
                    ev.relation_type AS relation_type,
                    ev.document_id AS document_id,
                    ev.document_chunk_id AS document_chunk_id,
                    chunk.document_title AS document_title,
                    chunk.section_path AS section_path
                LIMIT 1
                """
                evidence_rows.extend(
                    await self._fetch_all(
                        evidence_query,
                        source_entity_id=source_entity.get("entity_id"),
                        target_entity_id=target_entity.get("entity_id"),
                        relation_type=clean_graph_text(relation.get("relation_type")) or "RELATED_TO",
                        team_id=team_id,
                        knowledge_base_id=knowledge_base_id,
                        allowed_document_ids=normalized_document_ids,
                    )
                )
            normalized_rows.append(
                {
                    "path_id": signature,
                    "signature": signature,
                    "hop_count": len(path_relations),
                    "content": signature,
                    "matched_entities": matched_entities,
                    "relation_types": [
                        clean_graph_text(item.get("relation_type")) or "RELATED_TO"
                        for item in path_relations
                    ],
                    "evidence": evidence_rows,
                }
            )
        return normalized_rows[:resolved_limit]

    async def _fetch_all(self, query: str, **params: Any) -> list[dict[str, Any]]:
        for attempt in range(1, _GRAPH_STORE_MAX_RETRIES + 1):
            try:
                async with self._driver.session(database=self._database) as session:
                    result = await session.run(query, **params)
                    rows: list[dict[str, Any]] = []
                    async for record in result:
                        rows.append(dict(record))
                    await result.consume()
                    return rows
            except Exception as exc:
                if not _is_retryable_graph_store_error(exc) or attempt >= _GRAPH_STORE_MAX_RETRIES:
                    raise
                await _sleep_before_graph_store_retry(
                    action="fetch",
                    attempt=attempt,
                    database=self._database,
                    error=exc,
                )
        return []

    async def _run(self, query: str, **params: Any) -> None:
        for attempt in range(1, _GRAPH_STORE_MAX_RETRIES + 1):
            try:
                async with self._driver.session(database=self._database) as session:
                    result = await session.run(query, **params)
                    await result.consume()
                    return None
            except Exception as exc:
                if not _is_retryable_graph_store_error(exc) or attempt >= _GRAPH_STORE_MAX_RETRIES:
                    raise
                await _sleep_before_graph_store_retry(
                    action="run",
                    attempt=attempt,
                    database=self._database,
                    error=exc,
                )


def _is_retryable_graph_store_error(error: Exception) -> bool:
    try:
        from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError
    except ModuleNotFoundError:  # pragma: no cover
        return isinstance(error, OSError)

    return isinstance(error, (OSError, ServiceUnavailable, SessionExpired, TransientError))


async def _sleep_before_graph_store_retry(
    *,
    action: str,
    attempt: int,
    database: str,
    error: Exception,
) -> None:
    delay_seconds = _GRAPH_STORE_RETRY_DELAY_SECONDS * attempt
    logger.warning(
        "Neo4j graph store {} failed attempt={}/{} database={} retry_in={}s error={}",
        action,
        attempt,
        _GRAPH_STORE_MAX_RETRIES,
        database,
        delay_seconds,
        error,
    )
    await asyncio.sleep(delay_seconds)


def get_graph_store(*, require_indexing: bool = True) -> GraphStore:
    """Return the runtime graph store implementation."""

    cfg = config_registry.get_graph_config()
    if not cfg.enabled or (require_indexing and not cfg.indexing_enabled):
        return NullGraphStore()
    cache_key = (
        bool(cfg.enabled),
        bool(cfg.indexing_enabled),
        str(cfg.uri),
        str(cfg.username),
        str(cfg.password),
        str(cfg.database),
        bool(require_indexing),
    )
    store = _GRAPH_STORE_CACHE.get(cache_key)
    if store is None:
        store = Neo4jGraphStore(
            uri=cfg.uri,
            username=cfg.username,
            password=cfg.password,
            database=cfg.database,
        )
        _GRAPH_STORE_CACHE[cache_key] = store
    return store
