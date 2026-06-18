"""Shared graph extraction and indexing data models."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any
from uuid import NAMESPACE_URL, uuid5


def clean_graph_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def build_entity_id(
    *,
    team_id: int,
    knowledge_base_id: int,
    entity_type: str,
    name: str,
) -> str:
    payload = "|".join(
        [
            str(int(team_id)),
            str(int(knowledge_base_id)),
            clean_graph_text(entity_type).upper() or "OTHER",
            clean_graph_text(name),
        ]
    )
    return str(uuid5(NAMESPACE_URL, f"synapseflow:entity:{payload}"))


def build_relation_evidence_hash(
    *,
    source_entity_id: str,
    target_entity_id: str,
    relation_type: str,
    document_chunk_id: int,
    evidence_text: str,
) -> str:
    payload = "|".join(
        [
            clean_graph_text(source_entity_id),
            clean_graph_text(relation_type).upper() or "RELATED_TO",
            clean_graph_text(target_entity_id),
            str(int(document_chunk_id)),
            clean_graph_text(evidence_text),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def build_relation_evidence_id(evidence_hash: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"synapseflow:relation-evidence:{clean_graph_text(evidence_hash)}"))


def build_chunk_content_hash(content: str) -> str:
    return hashlib.sha1((content or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class GraphChunkRecord:
    team_id: int
    knowledge_base_id: int
    document_id: int
    document_chunk_id: int
    chunk_index: int
    document_title: str | None
    section_path: str | None
    content_hash: str | None = None


@dataclass(frozen=True, slots=True)
class GraphEntityRecord:
    id: str
    team_id: int
    knowledge_base_id: int
    name: str
    entity_type: str
    aliases: tuple[str, ...] = ()
    description: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphMentionRecord:
    team_id: int
    knowledge_base_id: int
    entity_id: str
    document_id: int
    document_chunk_id: int
    mention_text: str | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class GraphRelationRecord:
    team_id: int
    knowledge_base_id: int
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    evidence_count: int = 0


@dataclass(frozen=True, slots=True)
class GraphRelationEvidenceRecord:
    id: str
    team_id: int
    knowledge_base_id: int
    source_entity_id: str
    target_entity_id: str
    document_id: int
    document_chunk_id: int
    relation_type: str
    evidence_text: str
    evidence_hash: str
    confidence: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphRelationCandidate:
    source_name: str
    target_name: str
    relation_type: str
    source_entity_type: str | None = None
    target_entity_type: str | None = None
    evidence_text: str | None = None
    confidence: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChunkGraphExtraction:
    chunk: GraphChunkRecord
    entities: list[GraphEntityRecord]
    relation_candidates: list[GraphRelationCandidate]
