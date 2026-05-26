"""Graph store abstractions used by graph indexing services."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from app.core.config.registry import config_registry
from app.services.graph_models import (
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationRecord,
)

_GRAPH_STORE_CACHE: dict[tuple[bool, bool, str, str, str, str, bool], GraphStore] = {}


def _normalize_attribute_key(key: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", (key or "").strip()).strip("_")
    return cleaned.lower()


def _prepare_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    prepared: dict[str, Any] = {}
    for key, value in attributes.items():
        normalized_key = _normalize_attribute_key(str(key))
        if not normalized_key:
            continue
        if value is None:
            continue
        if isinstance(value, str):
            cleaned_value = value.strip()
            if not cleaned_value:
                continue
            prepared[f"attr_{normalized_key}"] = cleaned_value
            continue
        if isinstance(value, (int, float, bool)):
            prepared[f"attr_{normalized_key}"] = value
            continue
        cleaned_value = str(value).strip()
        if cleaned_value:
            prepared[f"attr_{normalized_key}"] = cleaned_value
    return prepared


def _serialize_raw_attributes(attributes: dict[str, Any] | None) -> str | None:
    if not attributes:
        return None
    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        normalized_key = _normalize_attribute_key(str(key))
        if not normalized_key or value is None:
            continue
        if isinstance(value, str):
            cleaned_value = value.strip()
            if not cleaned_value:
                continue
            cleaned[normalized_key] = cleaned_value
            continue
        if isinstance(value, (int, float, bool)):
            cleaned[normalized_key] = value
            continue
        cleaned_value = str(value).strip()
        if cleaned_value:
            cleaned[normalized_key] = cleaned_value
    if not cleaned:
        return None
    return json.dumps(cleaned, ensure_ascii=False)


class GraphStore(Protocol):
    """Minimal async graph-store contract for indexing services."""

    async def delete_document_graph(self, *, document_id: int) -> None: ...

    async def delete_knowledge_base_graph(self, *, knowledge_base_id: int, team_id: int) -> None: ...

    async def upsert_chunk(self, chunk: GraphChunkRecord) -> None: ...

    async def upsert_chunks(self, chunks: list[GraphChunkRecord]) -> None: ...

    async def upsert_entity(self, entity: GraphEntityRecord) -> None: ...

    async def upsert_entities(self, entities: list[GraphEntityRecord]) -> None: ...

    async def link_entity_to_chunk(
        self,
        *,
        normalized_name: str,
        chunk: GraphChunkRecord,
    ) -> None: ...

    async def link_entities_to_chunks(self, rows: list[dict[str, Any]]) -> None: ...

    async def upsert_relation(self, relation: GraphRelationRecord) -> None: ...

    async def upsert_relations(self, relations: list[GraphRelationRecord]) -> None: ...

    async def prune_orphan_entities(self) -> None: ...

    async def lookup_entities_for_grounding(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        candidate: str,
    ) -> list[dict[str, Any]]: ...

    async def list_entity_summary_contexts(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        normalized_names: list[str],
    ) -> list[dict[str, Any]]: ...

    async def upsert_entity_summaries(self, rows: list[dict[str, Any]]) -> None: ...

    async def list_relation_summary_contexts(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        document_id: int | None = None,
    ) -> list[dict[str, Any]]: ...

    async def upsert_relation_summaries(self, rows: list[dict[str, Any]]) -> None: ...

    async def search_related_evidence(
        self,
        *,
        entity_names: list[str],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
    ) -> list[dict[str, Any]]: ...

    async def search_relation_evidence_for_pairs(
        self,
        *,
        relation_pairs: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
    ) -> list[dict[str, Any]]: ...

    async def search_relation_evidence_for_queries(
        self,
        *,
        relation_queries: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
    ) -> list[dict[str, Any]]: ...


class NullGraphStore:
    """No-op graph store used before a real Neo4j driver is wired in."""

    async def delete_document_graph(self, *, document_id: int) -> None:
        return None

    async def delete_knowledge_base_graph(self, *, knowledge_base_id: int, team_id: int) -> None:
        return None

    async def upsert_chunk(self, chunk: GraphChunkRecord) -> None:
        return None

    async def upsert_chunks(self, chunks: list[GraphChunkRecord]) -> None:
        return None

    async def upsert_entity(self, entity: GraphEntityRecord) -> None:
        return None

    async def upsert_entities(self, entities: list[GraphEntityRecord]) -> None:
        return None

    async def link_entity_to_chunk(
        self,
        *,
        normalized_name: str,
        chunk: GraphChunkRecord,
    ) -> None:
        return None

    async def link_entities_to_chunks(self, rows: list[dict[str, Any]]) -> None:
        return None

    async def upsert_relation(self, relation: GraphRelationRecord) -> None:
        return None

    async def upsert_relations(self, relations: list[GraphRelationRecord]) -> None:
        return None

    async def prune_orphan_entities(self) -> None:
        return None

    async def lookup_entities_for_grounding(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        candidate: str,
    ) -> list[dict[str, Any]]:
        return []

    async def list_entity_summary_contexts(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        normalized_names: list[str],
    ) -> list[dict[str, Any]]:
        return []

    async def upsert_entity_summaries(self, rows: list[dict[str, Any]]) -> None:
        return None

    async def list_relation_summary_contexts(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        document_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def upsert_relation_summaries(self, rows: list[dict[str, Any]]) -> None:
        return None

    async def search_related_evidence(
        self,
        *,
        entity_names: list[str],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        return []

    async def search_relation_evidence_for_pairs(
        self,
        *,
        relation_pairs: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        return []

    async def search_relation_evidence_for_queries(
        self,
        *,
        relation_queries: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
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
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on installed extras
            raise RuntimeError("Neo4j driver is not installed") from exc

        self._database = database
        self._driver = AsyncGraphDatabase.driver(uri, auth=(username, password))

    async def delete_document_graph(self, *, document_id: int) -> None:
        await self._run(
            """
            MATCH ()-[r:RELATED]-()
            WHERE r.document_id = $document_id
            DELETE r
            """,
            document_id=document_id,
        )
        await self._run(
            """
            MATCH (c:Chunk)
            WHERE c.document_id = $document_id
            DETACH DELETE c
            """,
            document_id=document_id,
        )

    async def delete_knowledge_base_graph(self, *, knowledge_base_id: int, team_id: int) -> None:
        params = {"knowledge_base_id": knowledge_base_id, "team_id": team_id}
        await self._run(
            """
            MATCH (s:EntitySummary)
            WHERE s.team_id = $team_id
              AND s.knowledge_base_id = $knowledge_base_id
            DETACH DELETE s
            """,
            **params,
        )
        await self._run(
            """
            MATCH (e:Entity)
            WHERE e.team_id = $team_id
              AND e.knowledge_base_id = $knowledge_base_id
            DETACH DELETE e
            """,
            **params,
        )
        await self._run(
            """
            MATCH (c:Chunk)
            WHERE c.team_id = $team_id
              AND c.knowledge_base_id = $knowledge_base_id
            DETACH DELETE c
            """,
            **params,
        )

    async def upsert_chunk(self, chunk: GraphChunkRecord) -> None:
        await self.upsert_chunks([chunk])

    async def upsert_chunks(self, chunks: list[GraphChunkRecord]) -> None:
        if not chunks:
            return None
        rows = [
            {
                "team_id": chunk.team_id,
                "knowledge_base_id": chunk.knowledge_base_id,
                "document_id": chunk.document_id,
                "document_chunk_id": chunk.document_chunk_id,
                "document_title": chunk.document_title,
                "section_path": chunk.section_path,
            }
            for chunk in chunks
        ]
        await self._run(
            """
            UNWIND $rows AS row
            MERGE (c:Chunk {document_chunk_id: row.document_chunk_id})
            SET c.team_id = row.team_id,
                c.knowledge_base_id = row.knowledge_base_id,
                c.document_id = row.document_id,
                c.document_title = row.document_title,
                c.section_path = row.section_path
            """,
            rows=rows,
        )

    async def upsert_entity(self, entity: GraphEntityRecord) -> None:
        await self.upsert_entities([entity])

    async def upsert_entities(self, entities: list[GraphEntityRecord]) -> None:
        if not entities:
            return None
        rows = [
            {
                "team_id": entity.team_id,
                "knowledge_base_id": entity.knowledge_base_id,
                "normalized_name": entity.normalized_name,
                "display_name": entity.display_name,
                "entity_type": entity.entity_type,
                "aliases": list(entity.aliases),
                "attributes": _prepare_attributes(entity.attributes),
                "raw_attributes_json": _serialize_raw_attributes(entity.raw_attributes),
            }
            for entity in entities
        ]
        await self._run(
            """
            UNWIND $rows AS row
            MERGE (e:Entity {
                team_id: row.team_id,
                knowledge_base_id: row.knowledge_base_id,
                normalized_name: row.normalized_name
            })
            SET e.display_name = row.display_name,
                e.entity_type = row.entity_type,
                e.aliases = row.aliases,
                e.raw_attributes_json = row.raw_attributes_json
            SET e += row.attributes
            """,
            rows=rows,
        )

    async def link_entity_to_chunk(
        self,
        *,
        normalized_name: str,
        chunk: GraphChunkRecord,
    ) -> None:
        await self.link_entities_to_chunks(
            [
                {
                    "normalized_name": normalized_name,
                    "team_id": chunk.team_id,
                    "knowledge_base_id": chunk.knowledge_base_id,
                    "document_id": chunk.document_id,
                    "document_chunk_id": chunk.document_chunk_id,
                    "evidence": "",
                    "attributes": {},
                }
            ]
        )

    async def link_entities_to_chunks(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return None
        await self._run(
            """
            UNWIND $rows AS row
            MATCH (e:Entity {
                team_id: row.team_id,
                knowledge_base_id: row.knowledge_base_id,
                normalized_name: row.normalized_name
            })
            MATCH (c:Chunk {document_chunk_id: row.document_chunk_id})
            MERGE (e)-[r:MENTIONED_IN {document_chunk_id: row.document_chunk_id}]->(c)
            SET r.team_id = row.team_id,
                r.knowledge_base_id = row.knowledge_base_id,
                r.document_id = row.document_id,
                r.evidence = row.evidence
            SET r += row.attributes
            """,
            rows=[
                {
                    **row,
                    "attributes": _prepare_attributes(row.get("attributes") or {}),
                }
                for row in rows
            ],
        )

    async def upsert_relation(self, relation: GraphRelationRecord) -> None:
        await self.upsert_relations([relation])

    async def upsert_relations(self, relations: list[GraphRelationRecord]) -> None:
        if not relations:
            return None
        rows = [
            {
                "team_id": relation.team_id,
                "knowledge_base_id": relation.knowledge_base_id,
                "document_id": relation.document_id,
                "document_chunk_id": relation.document_chunk_id,
                "source_normalized_name": relation.source_normalized_name,
                "target_normalized_name": relation.target_normalized_name,
                "relation_type": relation.relation_type,
                "evidence": relation.evidence,
                "attributes": _prepare_attributes(relation.attributes),
            }
            for relation in relations
        ]
        await self._run(
            """
            UNWIND $rows AS row
            MATCH (source:Entity {
                team_id: row.team_id,
                knowledge_base_id: row.knowledge_base_id,
                normalized_name: row.source_normalized_name
            })
            MATCH (target:Entity {
                team_id: row.team_id,
                knowledge_base_id: row.knowledge_base_id,
                normalized_name: row.target_normalized_name
            })
            MERGE (source)-[r:RELATED {
                team_id: row.team_id,
                knowledge_base_id: row.knowledge_base_id,
                source_normalized_name: row.source_normalized_name,
                target_normalized_name: row.target_normalized_name,
                relation_type: row.relation_type
            }]->(target)
            SET r.team_id = row.team_id,
                r.knowledge_base_id = row.knowledge_base_id,
                r.document_id = row.document_id,
                r.document_chunk_id = row.document_chunk_id,
                r.evidence = row.evidence
            SET r += row.attributes
            """,
            rows=rows,
        )

    async def prune_orphan_entities(self) -> None:
        await self._run(
            """
            MATCH (e:Entity)
            WHERE NOT (e)--()
            DELETE e
            """
        )

    async def lookup_entities_for_grounding(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        candidate: str,
    ) -> list[dict[str, Any]]:
        normalized_candidate = " ".join(str(candidate or "").split()).strip().casefold()
        if not normalized_candidate:
            return []
        query = """
        MATCH (e:Entity)
        WHERE e.team_id = $team_id
          AND e.knowledge_base_id = $knowledge_base_id
          AND (
            toLower(e.normalized_name) = $candidate
            OR toLower(e.display_name) = $candidate
            OR any(alias IN coalesce(e.aliases, []) WHERE toLower(alias) = $candidate)
          )
        RETURN
            e.normalized_name AS normalized_name,
            e.display_name AS display_name,
            e.entity_type AS entity_type,
            coalesce(e.aliases, []) AS aliases
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query,
                knowledge_base_id=knowledge_base_id,
                team_id=team_id,
                candidate=normalized_candidate,
            )
            rows: list[dict[str, Any]] = []
            async for record in result:
                rows.append(dict(record))
            return rows

    async def list_entity_summary_contexts(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        normalized_names: list[str],
    ) -> list[dict[str, Any]]:
        lookup_names = [" ".join(item.split()).strip().casefold() for item in normalized_names]
        lookup_names = [item for item in lookup_names if item]
        if not lookup_names:
            return []
        query = """
        MATCH (e:Entity)
        WHERE e.team_id = $team_id
          AND e.knowledge_base_id = $knowledge_base_id
          AND (
            e.normalized_name IN $normalized_names
            OR toLower(e.normalized_name) IN $lookup_names
            OR any(alias IN coalesce(e.aliases, []) WHERE toLower(alias) IN $lookup_names)
          )
        OPTIONAL MATCH (e)-[:HAS_SUMMARY]->(s:EntitySummary)
        OPTIONAL MATCH (e)-[m:MENTIONED_IN]->(c:Chunk)
        WHERE c.knowledge_base_id = $knowledge_base_id
          AND c.team_id = $team_id
        OPTIONAL MATCH (e)-[rel:RELATED]-(other:Entity)
        WHERE rel.knowledge_base_id = $knowledge_base_id
          AND rel.team_id = $team_id
        RETURN
            e.normalized_name AS normalized_name,
            e.display_name AS display_name,
            e.entity_type AS entity_type,
            coalesce(e.aliases, []) AS aliases,
            s.summary AS summary,
            properties(e) AS entity_props,
            e.raw_attributes_json AS raw_attributes_json,
            collect(DISTINCT {
                document_title: c.document_title,
                section_path: c.section_path,
                evidence: m.evidence,
                mention_props: properties(m)
            }) AS mentions,
            collect(DISTINCT {
                other: other.display_name,
                relation_type: rel.relation_type,
                evidence: rel.evidence,
                relation_props: properties(rel)
            }) AS relations
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query,
                normalized_names=normalized_names,
                lookup_names=lookup_names,
                knowledge_base_id=knowledge_base_id,
                team_id=team_id,
            )
            rows: list[dict[str, Any]] = []
            async for record in result:
                rows.append(dict(record))
            return rows

    async def upsert_entity_summaries(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return None
        await self._run(
            """
            UNWIND $rows AS row
            MATCH (e:Entity {
                team_id: row.team_id,
                knowledge_base_id: row.knowledge_base_id,
                normalized_name: row.normalized_name
            })
            MERGE (s:EntitySummary {
                normalized_name: row.normalized_name,
                team_id: row.team_id,
                knowledge_base_id: row.knowledge_base_id
            })
            SET s.display_name = row.display_name,
                s.entity_type = row.entity_type,
                s.summary = row.summary
            MERGE (e)-[:HAS_SUMMARY]->(s)
            """,
            rows=rows,
        )

    async def list_relation_summary_contexts(
        self,
        *,
        knowledge_base_id: int,
        team_id: int,
        document_id: int | None = None,
    ) -> list[dict[str, Any]]:
        query = """
        MATCH (source:Entity)-[r:RELATED]->(target:Entity)
        WHERE r.knowledge_base_id = $knowledge_base_id
          AND r.team_id = $team_id
          AND ($document_id IS NULL OR r.document_id = $document_id)
        OPTIONAL MATCH (source)-[:HAS_SUMMARY]->(source_summary:EntitySummary)
        OPTIONAL MATCH (target)-[:HAS_SUMMARY]->(target_summary:EntitySummary)
        RETURN
            source.normalized_name AS source_normalized_name,
            source.display_name AS source_display_name,
            source.entity_type AS source_entity_type,
            coalesce(source.aliases, []) AS source_aliases,
            source_summary.summary AS source_summary,
            properties(source) AS source_props,
            target.normalized_name AS target_normalized_name,
            target.display_name AS target_display_name,
            target.entity_type AS target_entity_type,
            coalesce(target.aliases, []) AS target_aliases,
            target_summary.summary AS target_summary,
            properties(target) AS target_props,
            r.relation_type AS relation_type,
            r.evidence AS evidence,
            r.summary AS summary,
            properties(r) AS relation_props
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query,
                knowledge_base_id=knowledge_base_id,
                team_id=team_id,
                document_id=document_id,
            )
            rows: list[dict[str, Any]] = []
            async for record in result:
                rows.append(dict(record))
            return rows

    async def upsert_relation_summaries(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return None
        await self._run(
            """
            UNWIND $rows AS row
            MATCH (source:Entity {
                team_id: row.team_id,
                knowledge_base_id: row.knowledge_base_id,
                normalized_name: row.source_normalized_name
            })
            MATCH (target:Entity {
                team_id: row.team_id,
                knowledge_base_id: row.knowledge_base_id,
                normalized_name: row.target_normalized_name
            })
            MATCH (source)-[r:RELATED {
                team_id: row.team_id,
                knowledge_base_id: row.knowledge_base_id,
                source_normalized_name: row.source_normalized_name,
                target_normalized_name: row.target_normalized_name,
                relation_type: row.relation_type
            }]->(target)
            SET r.summary = row.summary
            """,
            rows=rows,
        )

    async def search_related_evidence(
        self,
        *,
        entity_names: list[str],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        normalized_names = [" ".join(item.split()).strip().casefold() for item in entity_names]
        normalized_names = [item for item in normalized_names if item]
        if not normalized_names:
            return []
        query = """
        MATCH (e:Entity)
        WHERE e.team_id = $team_id
          AND e.knowledge_base_id = $knowledge_base_id
          AND (
            e.normalized_name IN $entity_names
            OR any(alias IN coalesce(e.aliases, []) WHERE toLower(alias) IN $entity_names)
          )
        OPTIONAL MATCH (e)-[mention:MENTIONED_IN]->(mention_chunk:Chunk)
        OPTIONAL MATCH (e)-[rel:RELATED]-(other:Entity)
        OPTIONAL MATCH (other)-[:MENTIONED_IN]->(relation_chunk:Chunk)
        WITH e, mention, mention_chunk, rel, other, relation_chunk
        WITH e,
             coalesce(relation_chunk, mention_chunk) AS chunk,
             mention,
             rel,
             other
        WHERE chunk IS NOT NULL
          AND chunk.knowledge_base_id = $knowledge_base_id
          AND chunk.team_id = $team_id
        RETURN DISTINCT
             chunk.knowledge_base_id AS knowledge_base_id,
             chunk.team_id AS team_id,
             chunk.document_id AS document_id,
             chunk.document_chunk_id AS document_chunk_id,
             chunk.document_title AS document_title,
             chunk.section_path AS section_path,
             rel.relation_type AS relation_type,
             coalesce(rel.evidence, mention.evidence) AS evidence,
             [name IN [e.display_name, other.display_name] WHERE name IS NOT NULL] AS matched_entities
        LIMIT $limit
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query,
                entity_names=normalized_names,
                knowledge_base_id=knowledge_base_id,
                team_id=team_id,
                limit=max(1, limit),
            )
            rows: list[dict[str, Any]] = []
            async for record in result:
                rows.append(dict(record))
            return rows

    async def search_relation_evidence_for_pairs(
        self,
        *,
        relation_pairs: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = [
            {
                "source": " ".join(str(item.get("source") or "").split()).strip().casefold(),
                "target": " ".join(str(item.get("target") or "").split()).strip().casefold(),
            }
            for item in relation_pairs
            if str(item.get("source") or "").strip() and str(item.get("target") or "").strip()
        ]
        if not rows:
            return []
        query = """
        UNWIND $rows AS row
        MATCH (source:Entity)-[rel:RELATED]->(target:Entity)
        WHERE rel.knowledge_base_id = $knowledge_base_id
          AND rel.team_id = $team_id
          AND toLower(source.normalized_name) = row.source
          AND toLower(target.normalized_name) = row.target
        MATCH (chunk:Chunk {document_chunk_id: rel.document_chunk_id})
        RETURN DISTINCT
             chunk.knowledge_base_id AS knowledge_base_id,
             chunk.team_id AS team_id,
             chunk.document_id AS document_id,
             chunk.document_chunk_id AS document_chunk_id,
             chunk.document_title AS document_title,
             chunk.section_path AS section_path,
             rel.relation_type AS relation_type,
             rel.evidence AS evidence,
             [name IN [source.display_name, target.display_name] WHERE name IS NOT NULL] AS matched_entities
        LIMIT $limit
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query,
                rows=rows,
                knowledge_base_id=knowledge_base_id,
                team_id=team_id,
                limit=max(1, limit),
            )
            output: list[dict[str, Any]] = []
            async for record in result:
                output.append(dict(record))
            return output

    async def search_relation_evidence_for_queries(
        self,
        *,
        relation_queries: list[dict[str, Any]],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        rows = [
            {
                "anchor_entity": " ".join(str(item.get("anchor_entity") or "").split()).strip().casefold(),
                "direction": str(item.get("direction") or "outgoing").strip().lower() or "outgoing",
            }
            for item in relation_queries
            if str(item.get("anchor_entity") or "").strip()
        ]
        if not rows:
            return []
        query = """
        UNWIND $rows AS row
        MATCH (anchor:Entity)
        WHERE anchor.team_id = $team_id
          AND anchor.knowledge_base_id = $knowledge_base_id
          AND toLower(anchor.normalized_name) = row.anchor_entity
        CALL {
          WITH anchor, row
          MATCH (anchor)-[rel:RELATED]->(other:Entity)
          WHERE row.direction <> 'incoming'
          RETURN rel, other
          UNION
          WITH anchor, row
          MATCH (other:Entity)-[rel:RELATED]->(anchor)
          WHERE row.direction = 'incoming'
          RETURN rel, other
        }
        MATCH (chunk:Chunk {document_chunk_id: rel.document_chunk_id})
        RETURN DISTINCT
             chunk.knowledge_base_id AS knowledge_base_id,
             chunk.team_id AS team_id,
             chunk.document_id AS document_id,
             chunk.document_chunk_id AS document_chunk_id,
             chunk.document_title AS document_title,
             chunk.section_path AS section_path,
             rel.relation_type AS relation_type,
             rel.evidence AS evidence,
             [name IN [anchor.display_name, other.display_name] WHERE name IS NOT NULL] AS matched_entities
        LIMIT $limit
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                query,
                rows=rows,
                knowledge_base_id=knowledge_base_id,
                team_id=team_id,
                limit=max(1, limit),
            )
            output: list[dict[str, Any]] = []
            async for record in result:
                output.append(dict(record))
            return output

    async def _run(self, query: str, **params) -> None:
        async with self._driver.session(database=self._database) as session:
            await session.run(query, params)


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
