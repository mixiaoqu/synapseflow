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


def _entity_identity_name(entity: GraphEntityRecord) -> str:
    return clean_graph_text(entity.canonical_name) or clean_graph_text(entity.name)


def _lookup_values(entity: GraphEntityRecord) -> set[str]:
    return {
        value.casefold()
        for value in [
            clean_graph_text(entity.name),
            clean_graph_text(entity.canonical_name),
            *[clean_graph_text(alias) for alias in entity.aliases],
        ]
        if value
    }


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
        canonical_name = clean_graph_text(entity.canonical_name) or None
        entity_type = clean_graph_text(entity.entity_type).upper() or "OTHER"
        if _is_noise_entity(name):
            continue
        key = _entity_key(entity_type, canonical_name or name)
        aliases = tuple(
            dict.fromkeys(
                alias
                for alias in [
                    *[clean_graph_text(item) for item in entity.aliases],
                    canonical_name or "",
                ]
                if alias and alias != name
            )
        )
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = GraphEntityRecord(
                id=build_entity_id(
                    team_id=chunk.team_id,
                    knowledge_base_id=chunk.knowledge_base_id,
                    entity_type=entity_type,
                    name=name,
                    canonical_name=canonical_name,
                ),
                team_id=chunk.team_id,
                knowledge_base_id=chunk.knowledge_base_id,
                name=name,
                entity_type=entity_type,
                canonical_name=canonical_name,
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
            canonical_name=existing.canonical_name or canonical_name,
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
    canonical_name: str | None,
    entities_by_key: dict[tuple[str, str], GraphEntityRecord],
) -> GraphEntityRecord | None:
    cleaned_name = clean_graph_text(name)
    cleaned_canonical_name = clean_graph_text(canonical_name)
    if not cleaned_name:
        return None
    if cleaned_canonical_name:
        direct = entities_by_key.get(_entity_key(entity_type or "", cleaned_canonical_name))
        if direct is not None:
            return direct
        canonical_candidates = [
            entity
            for entity in entities_by_key.values()
            if _entity_identity_name(entity) == cleaned_canonical_name
        ]
        if len(canonical_candidates) == 1:
            return canonical_candidates[0]
    if entity_type:
        direct = entities_by_key.get(_entity_key(entity_type, cleaned_name))
        if direct is not None:
            return direct
    lookup_name = cleaned_name.casefold()
    candidates = [
        entity
        for entity in entities_by_key.values()
        if lookup_name in _lookup_values(entity)
    ]
    cleaned_type = clean_graph_text(entity_type).upper()
    if cleaned_type:
        typed_candidates = [entity for entity in candidates if entity.entity_type == cleaned_type]
        if len(typed_candidates) == 1:
            return typed_candidates[0]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _normalize_relation_candidates(
    *,
    entities: list[GraphEntityRecord],
    relation_candidates: list[GraphRelationCandidate],
) -> list[GraphRelationCandidate]:
    entities_by_key = {
        _entity_key(entity.entity_type, _entity_identity_name(entity)): entity
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
            canonical_name=relation.source_canonical_name,
            entities_by_key=entities_by_key,
        )
        target_entity = _resolve_relation_endpoint(
            name=relation.target_name,
            entity_type=relation.target_entity_type,
            canonical_name=relation.target_canonical_name,
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
            source_canonical_name=source_entity.canonical_name,
            target_canonical_name=target_entity.canonical_name,
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
