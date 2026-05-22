"""Graph store abstractions used by graph indexing services."""

from __future__ import annotations

from typing import Any, Protocol

from app.core.config.registry import config_registry
from app.services.graph_models import (
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationRecord,
)


class GraphStore(Protocol):
    """Minimal async graph-store contract for indexing services."""

    async def delete_document_graph(self, *, document_id: int) -> None: ...

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

    async def search_related_evidence(
        self,
        *,
        entity_names: list[str],
        knowledge_base_id: int,
        team_id: int,
        limit: int,
    ) -> list[dict[str, Any]]: ...


class NullGraphStore:
    """No-op graph store used before a real Neo4j driver is wired in."""

    async def delete_document_graph(self, *, document_id: int) -> None:
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

    async def search_related_evidence(
        self,
        *,
        entity_names: list[str],
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
                "normalized_name": entity.normalized_name,
                "display_name": entity.display_name,
                "entity_type": entity.entity_type,
                "aliases": list(entity.aliases),
            }
            for entity in entities
        ]
        await self._run(
            """
            UNWIND $rows AS row
            MERGE (e:Entity {normalized_name: row.normalized_name})
            SET e.display_name = row.display_name,
                e.entity_type = row.entity_type,
                e.aliases = row.aliases
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
                }
            ]
        )

    async def link_entities_to_chunks(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return None
        await self._run(
            """
            UNWIND $rows AS row
            MATCH (e:Entity {normalized_name: row.normalized_name})
            MATCH (c:Chunk {document_chunk_id: row.document_chunk_id})
            MERGE (e)-[r:MENTIONED_IN {document_chunk_id: row.document_chunk_id}]->(c)
            SET r.team_id = row.team_id,
                r.knowledge_base_id = row.knowledge_base_id,
                r.document_id = row.document_id
            """,
            rows=rows,
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
            }
            for relation in relations
        ]
        await self._run(
            """
            UNWIND $rows AS row
            MATCH (source:Entity {normalized_name: row.source_normalized_name})
            MATCH (target:Entity {normalized_name: row.target_normalized_name})
            MERGE (source)-[r:RELATED {
                source_normalized_name: row.source_normalized_name,
                target_normalized_name: row.target_normalized_name,
                relation_type: row.relation_type
            }]->(target)
            SET r.team_id = row.team_id,
                r.knowledge_base_id = row.knowledge_base_id,
                r.document_id = row.document_id,
                r.document_chunk_id = row.document_chunk_id,
                r.evidence = row.evidence
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
        WHERE e.normalized_name IN $entity_names
           OR any(alias IN coalesce(e.aliases, []) WHERE toLower(alias) IN $entity_names)
        OPTIONAL MATCH (e)-[:MENTIONED_IN]->(mention_chunk:Chunk)
        OPTIONAL MATCH (e)-[rel:RELATED]-(other:Entity)
        OPTIONAL MATCH (other)-[:MENTIONED_IN]->(relation_chunk:Chunk)
        WITH e, mention_chunk, rel, other, relation_chunk
        WITH e,
             coalesce(relation_chunk, mention_chunk) AS chunk,
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
             rel.evidence AS evidence,
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

    async def _run(self, query: str, **params) -> None:
        async with self._driver.session(database=self._database) as session:
            await session.run(query, params)


def get_graph_store(*, require_indexing: bool = True) -> GraphStore:
    """Return the runtime graph store implementation."""

    cfg = config_registry.get_graph_config()
    if not cfg.enabled or (require_indexing and not cfg.indexing_enabled):
        return NullGraphStore()
    return Neo4jGraphStore(
        uri=cfg.uri,
        username=cfg.username,
        password=cfg.password,
        database=cfg.database,
    )
