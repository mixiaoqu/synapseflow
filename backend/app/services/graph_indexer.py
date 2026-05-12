"""Graph indexing orchestration over an abstract graph store."""

from __future__ import annotations

from app.services.graph_models import (
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationRecord,
)
from app.services.graph_store import GraphStore


class GraphIndexer:
    """Persist one chunk's graph records through the configured graph store."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store

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
