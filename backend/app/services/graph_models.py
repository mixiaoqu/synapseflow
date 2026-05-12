"""Shared graph extraction/indexing data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GraphChunkRecord:
    document_id: int
    document_chunk_id: int
    document_title: str | None
    section_path: str | None


@dataclass(frozen=True, slots=True)
class GraphEntityRecord:
    document_id: int
    document_chunk_id: int
    normalized_name: str
    display_name: str
    entity_type: str
    aliases: tuple[str, ...]
    evidence: str


@dataclass(frozen=True, slots=True)
class GraphRelationRecord:
    document_id: int
    document_chunk_id: int
    source_normalized_name: str
    target_normalized_name: str
    relation_type: str
    evidence: str


@dataclass(frozen=True, slots=True)
class ChunkGraphExtraction:
    chunk: GraphChunkRecord
    entities: list[GraphEntityRecord]
    relations: list[GraphRelationRecord]
