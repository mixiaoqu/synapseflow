"""Graph indexing orchestration over an abstract graph store."""

from __future__ import annotations

from typing import Any

from app.services.graph_models import (
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationRecord,
)
from app.services.graph_store import GraphStore

DEFAULT_GRAPH_BATCH_SIZE = 300


class GraphIndexer:
    """Persist one chunk's graph records through the configured graph store."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    @staticmethod
    def _chunked(items: list[Any], batch_size: int) -> list[list[Any]]:
        size = max(1, int(batch_size))
        return [items[start : start + size] for start in range(0, len(items), size)]

    async def index_batch_graph(
        self,
        *,
        chunks: list[GraphChunkRecord],
        entities: list[GraphEntityRecord],
        mentions: list[dict[str, Any]],
        relations: list[GraphRelationRecord],
        batch_size: int = DEFAULT_GRAPH_BATCH_SIZE,
    ) -> dict[str, int]:
        for batch in self._chunked(chunks, batch_size):
            await self._store.upsert_chunks(batch)
        for batch in self._chunked(entities, batch_size):
            await self._store.upsert_entities(batch)
        for batch in self._chunked(mentions, batch_size):
            await self._store.link_entities_to_chunks(batch)
        for batch in self._chunked(relations, batch_size):
            await self._store.upsert_relations(batch)

        return {
            "chunks": len(chunks),
            "entities": len(entities),
            "mentions": len(mentions),
            "relations": len(relations),
        }

    async def index_chunk_graph(
        self,
        *,
        chunk: GraphChunkRecord,
        entities: list[GraphEntityRecord],
        relations: list[GraphRelationRecord],
    ) -> dict[str, int]:
        await self._store.upsert_chunk(chunk)

        known_entities: set[str] = set()
        mention_count = 0
        relation_count = 0

        for entity in entities:
            await self._store.upsert_entity(entity)
            await self._store.link_entity_to_chunk(
                normalized_name=entity.normalized_name,
                chunk=chunk,
            )
            known_entities.add(entity.normalized_name)
            mention_count += 1

        for relation in relations:
            if (
                relation.source_normalized_name not in known_entities
                or relation.target_normalized_name not in known_entities
            ):
                continue
            await self._store.upsert_relation(relation)
            relation_count += 1

        return {
            "chunks": 1,
            "entities": len(entities),
            "mentions": mention_count,
            "relations": relation_count,
        }
