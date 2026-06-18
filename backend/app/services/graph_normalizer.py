"""Normalization and filtering for graph extraction results."""

from __future__ import annotations

from app.services.graph_models import (
    ChunkGraphExtraction,
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationCandidate,
    build_entity_id,
    clean_graph_text,
)

_ALLOWED_RELATION_TYPES = {
    "RELATED_TO",
    "PART_OF",
    "CONTAINS",
    "DEPENDS_ON",
    "IMPORTS",
    "EXTENDS",
    "IMPLEMENTS",
    "DECLARES",
    "CALLS",
    "EMITS",
    "HANDLES",
    "READS_FROM",
    "WRITES_TO",
    "ROUTES_TO",
    "RENDERS",
    "USES_COMPONENT",
    "TRIGGERS",
    "REQUIRES_PERMISSION",
    "HAS_STATUS",
    "NEXT_STEP",
    "CONFIGURES",
    "RESOLVES_ERROR",
    "MENTIONED_WITH",
}

_GENERIC_ENTITY_NAMES = {
    "系统",
    "功能",
    "模块",
    "页面",
}


def _entity_key(entity_type: str, name: str) -> tuple[str, str]:
    return (clean_graph_text(entity_type).upper() or "OTHER", clean_graph_text(name))


def _is_noise_entity(name: str) -> bool:
    cleaned = clean_graph_text(name)
    if len(cleaned) < 2:
        return True
    if cleaned.isdigit():
        return True
    if cleaned in _GENERIC_ENTITY_NAMES:
        return True
    return False


def _merge_attributes(*attribute_sets: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = {}
    for raw_attributes in attribute_sets:
        for key, value in dict(raw_attributes or {}).items():
            cleaned_key = clean_graph_text(key)
            if not cleaned_key or value is None:
                continue
            if isinstance(value, str):
                cleaned_value = clean_graph_text(value)
                if cleaned_value:
                    merged[cleaned_key] = cleaned_value
                continue
            merged[cleaned_key] = value
    return merged


def _merge_entities(
    *,
    chunk: GraphChunkRecord,
    entities: list[GraphEntityRecord],
) -> list[GraphEntityRecord]:
    deduped: dict[tuple[str, str], GraphEntityRecord] = {}
    for entity in entities:
        name = clean_graph_text(entity.name)
        entity_type = clean_graph_text(entity.entity_type).upper() or "OTHER"
        if _is_noise_entity(name):
            continue
        key = _entity_key(entity_type, name)
        aliases = tuple(
            alias
            for alias in (clean_graph_text(item) for item in entity.aliases)
            if alias and alias != name
        )
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = GraphEntityRecord(
                id=build_entity_id(
                    team_id=chunk.team_id,
                    knowledge_base_id=chunk.knowledge_base_id,
                    entity_type=entity_type,
                    name=name,
                ),
                team_id=chunk.team_id,
                knowledge_base_id=chunk.knowledge_base_id,
                name=name,
                entity_type=entity_type,
                aliases=aliases,
                description=clean_graph_text(entity.description) or None,
                attributes=_merge_attributes(entity.attributes),
                tags=tuple(clean_graph_text(tag) for tag in entity.tags if clean_graph_text(tag)),
            )
            continue
        merged_aliases = tuple(
            dict.fromkeys([*existing.aliases, *aliases]).keys()
        )
        merged_tags = tuple(
            dict.fromkeys([*existing.tags, *entity.tags]).keys()
        )
        description = existing.description or (clean_graph_text(entity.description) or None)
        deduped[key] = GraphEntityRecord(
            id=existing.id,
            team_id=existing.team_id,
            knowledge_base_id=existing.knowledge_base_id,
            name=existing.name,
            entity_type=existing.entity_type,
            aliases=merged_aliases,
            description=description,
            attributes=_merge_attributes(existing.attributes, entity.attributes),
            tags=merged_tags,
        )
    return list(deduped.values())


def _resolve_relation_endpoint(
    *,
    name: str,
    entity_type: str | None,
    entities_by_key: dict[tuple[str, str], GraphEntityRecord],
) -> GraphEntityRecord | None:
    cleaned_name = clean_graph_text(name)
    if not cleaned_name:
        return None
    if entity_type:
        direct = entities_by_key.get(_entity_key(entity_type, cleaned_name))
        if direct is not None:
            return direct
    candidates = [
        entity
        for entity in entities_by_key.values()
        if entity.name == cleaned_name
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _normalize_relation_candidates(
    *,
    entities: list[GraphEntityRecord],
    relation_candidates: list[GraphRelationCandidate],
) -> list[GraphRelationCandidate]:
    entities_by_key = {
        _entity_key(entity.entity_type, entity.name): entity
        for entity in entities
    }
    deduped: dict[tuple[str, str, str], GraphRelationCandidate] = {}
    for relation in relation_candidates:
        relation_type = clean_graph_text(relation.relation_type).upper() or "RELATED_TO"
        if relation_type not in _ALLOWED_RELATION_TYPES:
            relation_type = "RELATED_TO"
        source_entity = _resolve_relation_endpoint(
            name=relation.source_name,
            entity_type=relation.source_entity_type,
            entities_by_key=entities_by_key,
        )
        target_entity = _resolve_relation_endpoint(
            name=relation.target_name,
            entity_type=relation.target_entity_type,
            entities_by_key=entities_by_key,
        )
        if source_entity is None or target_entity is None:
            continue
        if source_entity.id == target_entity.id:
            continue
        key = (source_entity.id, relation_type, target_entity.id)
        if key in deduped:
            continue
        deduped[key] = GraphRelationCandidate(
            source_name=source_entity.name,
            target_name=target_entity.name,
            relation_type=relation_type,
            source_entity_type=source_entity.entity_type,
            target_entity_type=target_entity.entity_type,
            evidence_text=clean_graph_text(relation.evidence_text) or None,
            confidence=relation.confidence,
            attributes=_merge_attributes(relation.attributes),
        )
    return list(deduped.values())


def normalize_chunk_graph(
    *,
    chunk: GraphChunkRecord,
    entities: list[GraphEntityRecord],
    relation_candidates: list[GraphRelationCandidate],
) -> ChunkGraphExtraction:
    normalized_entities = _merge_entities(chunk=chunk, entities=entities)
    normalized_relations = _normalize_relation_candidates(
        entities=normalized_entities,
        relation_candidates=relation_candidates,
    )
    return ChunkGraphExtraction(
        chunk=chunk,
        entities=normalized_entities,
        relation_candidates=normalized_relations,
    )
