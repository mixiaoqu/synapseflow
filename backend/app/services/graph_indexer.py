"""Graph indexing orchestration over an abstract graph store."""

from __future__ import annotations

from typing import Any

from app.services.graph_models import (
    GraphChunkRecord,
    GraphEntityRecord,
    GraphMentionRecord,
    GraphRelationEvidenceRecord,
    GraphRelationRecord,
)
from app.services.graph_store import GraphStore

DEFAULT_GRAPH_BATCH_SIZE = 300


class GraphIndexer:
    """Persist graph records through the configured graph store."""

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
        mentions: list[GraphMentionRecord],
        relations: list[GraphRelationRecord],
        relation_evidences: list[GraphRelationEvidenceRecord],
        team_id: int,
        knowledge_base_id: int,
        batch_size: int = DEFAULT_GRAPH_BATCH_SIZE,
    ) -> dict[str, int]:
        for batch in self._chunked(chunks, batch_size):
            await self._store.upsert_chunks(batch)
        for batch in self._chunked(entities, batch_size):
            await self._store.upsert_entities(batch)
        for batch in self._chunked(mentions, batch_size):
            await self._store.upsert_mentions(batch)
        for batch in self._chunked(relations, batch_size):
            await self._store.upsert_relations(batch)
        for batch in self._chunked(relation_evidences, batch_size):
            await self._store.upsert_relation_evidences(batch)

        await self._store.refresh_related_evidence_counts(
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
        )
        return {
            "chunks": len(chunks),
            "entities": len(entities),
            "mentions": len(mentions),
            "relations": len(relations),
            "relation_evidences": len(relation_evidences),
        }
