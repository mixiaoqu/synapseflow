"""Lightweight normalization and filtering for graph extraction results."""

from __future__ import annotations

from app.services.graph_models import (
    ChunkGraphExtraction,
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationRecord,
)

_ALLOWED_RELATION_TYPES = {
    "RELATED_TO",
    "PART_OF",
    "DEPENDS_ON",
    "USES",
    "CONNECTS_TO",
    "STORES_IN",
    "BELONGS_TO",
    "MENTIONED_WITH",
}
_GENERIC_ENTITY_NAMES = {
    "系统",
    "功能",
    "模块",
    "页面",
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


def _normalize_name(value: str) -> str:
    return _clean_text(value).casefold()


def _is_noise_entity(name: str) -> bool:
    cleaned = _clean_text(name)
    if len(cleaned) < 2:
        return True
    if cleaned.isdigit():
        return True
    if cleaned in _GENERIC_ENTITY_NAMES:
        return True
    return False


def _clean_attributes(raw_attributes: dict[str, object] | None) -> dict[str, object]:
    if not raw_attributes:
        return {}
    attributes: dict[str, object] = {}
    for key, value in raw_attributes.items():
        cleaned_key = _clean_text(str(key))
        if not cleaned_key:
            continue
        if isinstance(value, str):
            cleaned_value = _clean_text(value)
            if not cleaned_value:
                continue
            attributes[cleaned_key] = cleaned_value
            continue
        if isinstance(value, (int, float, bool)):
            attributes[cleaned_key] = value
            continue
        if value is None:
            continue
        cleaned_value = _clean_text(str(value))
        if cleaned_value:
            attributes[cleaned_key] = cleaned_value
    return attributes


def normalize_chunk_graph(
    *,
    chunk: GraphChunkRecord,
    entities: list[GraphEntityRecord],
    relations: list[GraphRelationRecord],
) -> ChunkGraphExtraction:
    deduped_entities: dict[str, GraphEntityRecord] = {}

    for entity in entities:
        display_name = _clean_text(entity.display_name)
        normalized_name = _normalize_name(entity.normalized_name or display_name)
        if _is_noise_entity(display_name) or _is_noise_entity(normalized_name):
            continue
        cleaned_aliases = tuple(
            alias
            for alias in (_clean_text(item) for item in entity.aliases)
            if alias and alias.casefold() != normalized_name
        )
        deduped_entities.setdefault(
            normalized_name,
            GraphEntityRecord(
                document_id=chunk.document_id,
                document_chunk_id=chunk.document_chunk_id,
                normalized_name=normalized_name,
                display_name=display_name,
                entity_type=_clean_text(entity.entity_type or "OTHER") or "OTHER",
                aliases=cleaned_aliases,
                attributes=_clean_attributes(entity.attributes),
                evidence=_clean_text(entity.evidence),
            ),
        )

    allowed_names = set(deduped_entities.keys())
    deduped_relations: dict[tuple[str, str, str], GraphRelationRecord] = {}

    for relation in relations:
        source_name = _normalize_name(relation.source_normalized_name)
        target_name = _normalize_name(relation.target_normalized_name)
        if not source_name or not target_name or source_name == target_name:
            continue
        if source_name not in allowed_names or target_name not in allowed_names:
            continue
        relation_type = _clean_text(relation.relation_type or "RELATED_TO").upper()
        if relation_type not in _ALLOWED_RELATION_TYPES:
            relation_type = "RELATED_TO"
        dedupe_key = (source_name, relation_type, target_name)
        deduped_relations.setdefault(
            dedupe_key,
            GraphRelationRecord(
                team_id=chunk.team_id,
                knowledge_base_id=chunk.knowledge_base_id,
                document_id=chunk.document_id,
                document_chunk_id=chunk.document_chunk_id,
                source_normalized_name=source_name,
                target_normalized_name=target_name,
                relation_type=relation_type,
                attributes=_clean_attributes(relation.attributes),
                evidence=_clean_text(relation.evidence),
            ),
        )

    return ChunkGraphExtraction(
        chunk=chunk,
        entities=list(deduped_entities.values()),
        relations=list(deduped_relations.values()),
    )
