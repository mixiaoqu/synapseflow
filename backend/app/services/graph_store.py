"""Graph store abstractions used by graph indexing services."""

from __future__ import annotations

from typing import Protocol

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

    async def upsert_entity(self, entity: GraphEntityRecord) -> None: ...

    async def link_entity_to_chunk(
        self,
        *,
        normalized_name: str,
        chunk: GraphChunkRecord,
    ) -> None: ...

    async def upsert_relation(self, relation: GraphRelationRecord) -> None: ...

    async def prune_orphan_entities(self) -> None: ...


class NullGraphStore:
    """No-op graph store used before a real Neo4j driver is wired in."""

    async def delete_document_graph(self, *, document_id: int) -> None:
        return None

    async def upsert_chunk(self, chunk: GraphChunkRecord) -> None:
        return None

    async def upsert_entity(self, entity: GraphEntityRecord) -> None:
        return None

    async def link_entity_to_chunk(
        self,
        *,
        normalized_name: str,
        chunk: GraphChunkRecord,
    ) -> None:
        return None

    async def upsert_relation(self, relation: GraphRelationRecord) -> None:
        return None

    async def prune_orphan_entities(self) -> None:
        return None


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
        await self._run(
            """
            MERGE (c:Chunk {document_chunk_id: $document_chunk_id})
            SET c.document_id = $document_id,
                c.document_title = $document_title,
                c.section_path = $section_path
            """,
            document_chunk_id=chunk.document_chunk_id,
            document_id=chunk.document_id,
            document_title=chunk.document_title,
            section_path=chunk.section_path,
        )

    async def upsert_entity(self, entity: GraphEntityRecord) -> None:
        await self._run(
            """
            MERGE (e:Entity {normalized_name: $normalized_name})
            SET e.display_name = $display_name,
                e.entity_type = $entity_type,
                e.aliases = $aliases
            """,
            normalized_name=entity.normalized_name,
            display_name=entity.display_name,
            entity_type=entity.entity_type,
            aliases=list(entity.aliases),
        )

    async def link_entity_to_chunk(
        self,
        *,
        normalized_name: str,
        chunk: GraphChunkRecord,
    ) -> None:
        await self._run(
            """
            MATCH (e:Entity {normalized_name: $normalized_name})
            MATCH (c:Chunk {document_chunk_id: $document_chunk_id})
            MERGE (e)-[r:MENTIONED_IN {document_chunk_id: $document_chunk_id}]->(c)
            SET r.document_id = $document_id
            """,
            normalized_name=normalized_name,
            document_chunk_id=chunk.document_chunk_id,
            document_id=chunk.document_id,
        )

    async def upsert_relation(self, relation: GraphRelationRecord) -> None:
        await self._run(
            """
            MATCH (source:Entity {normalized_name: $source_normalized_name})
            MATCH (target:Entity {normalized_name: $target_normalized_name})
            MERGE (source)-[r:RELATED {
                source_normalized_name: $source_normalized_name,
                target_normalized_name: $target_normalized_name,
                relation_type: $relation_type,
                document_chunk_id: $document_chunk_id
            }]->(target)
            SET r.document_id = $document_id,
                r.evidence = $evidence
            """,
            source_normalized_name=relation.source_normalized_name,
            target_normalized_name=relation.target_normalized_name,
            relation_type=relation.relation_type,
            document_chunk_id=relation.document_chunk_id,
            document_id=relation.document_id,
            evidence=relation.evidence,
        )

    async def prune_orphan_entities(self) -> None:
        await self._run(
            """
            MATCH (e:Entity)
            WHERE NOT (e)--()
            DELETE e
            """
        )

    async def _run(self, query: str, **params) -> None:
        async with self._driver.session(database=self._database) as session:
            await session.run(query, params)


def get_graph_store() -> GraphStore:
    """Return the runtime graph store implementation."""

    cfg = config_registry.get_graph_config()
    if not (cfg.enabled and cfg.indexing_enabled):
        return NullGraphStore()
    return Neo4jGraphStore(
        uri=cfg.uri,
        username=cfg.username,
        password=cfg.password,
        database=cfg.database,
    )
