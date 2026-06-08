"""Lightweight normalization and filtering for graph extraction results."""

from __future__ import annotations

import re

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
_ENTITY_TYPE_ATTRIBUTE_KEYS = {
    "API": {
        "method",
        "path",
        "request_method",
        "route",
        "route_name",
        "route_path",
    },
    "COMPONENT": {
        "module",
        "module_path",
        "route",
        "route_name",
        "route_path",
    },
    "CONFIG": {
        "module",
        "module_path",
    },
    "MENU": {
        "title",
        "path",
        "parent",
    },
    "FORM": {
        "title",
        "fields",
        "submit_label",
        "validation",
    },
    "TABLE": {
        "title",
        "columns",
        "actions",
        "data_source",
    },
    "LIST": {
        "title",
        "item_label",
        "filter",
        "sort",
    },
    "DATABASE": {
        "table_name",
        "table_type",
    },
    "DOCUMENT": {
        "page",
        "section",
        "title",
    },
    "FEATURE": {
        "module",
        "module_path",
        "route",
        "route_name",
        "route_path",
    },
    "WORKFLOW": {
        "name",
        "steps",
        "start",
        "end",
    },
    "STEP": {
        "name",
        "order",
        "action",
        "status",
    },
    "MODULE": {
        "module",
        "module_path",
        "route",
        "route_name",
        "route_path",
    },
    "PERMISSION": {
        "code",
        "name",
        "description",
    },
    "PAGE": {
        "route",
        "route_name",
        "route_path",
        "title",
        "module",
    },
    "BUTTON": {
        "label",
        "action",
        "permission",
        "target",
    },
    "DIALOG": {
        "title",
        "trigger",
        "confirm_text",
        "cancel_text",
    },
    "SERVICE": {
        "module",
        "module_path",
        "route",
        "route_name",
        "route_path",
    },
    "ROLE": {
        "name",
        "description",
        "permissions",
    },
    "STATUS": {
        "value",
        "meaning",
        "type",
    },
    "PERSON": {
        "name",
        "role",
        "company",
        "age",
        "weight",
        "height",
    },
    "TEAM": {
        "role",
    },
    "BUSINESS_OBJECT": {
        "name",
        "description",
        "category",
    },
    "PRODUCT": {
        "brand",
        "sku",
        "price",
        "spec",
    },
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


def _normalize_name(value: str) -> str:
    return _clean_text(value).casefold()


def _normalize_alias_key(value: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", cleaned)
    separated = re.sub(r"[_\-/.]+", " ", separated)
    separated = re.sub(r"\s+", " ", separated)
    return separated.strip().casefold()


def _build_alias_keys(*values: str, aliases: tuple[str, ...]) -> tuple[str, ...]:
    keys: list[str] = []
    seen: set[str] = set()
    for value in (*values, *aliases):
        key = _normalize_alias_key(value)
        if not key or key in seen:
            continue
        keys.append(key)
        seen.add(key)
        compact_key = key.replace(" ", "")
        if compact_key and compact_key != key and compact_key not in seen:
            keys.append(compact_key)
            seen.add(compact_key)
    return tuple(keys)


def _is_noise_entity(name: str) -> bool:
    cleaned = _clean_text(name)
    if len(cleaned) < 2:
        return True
    if cleaned.isdigit():
        return True
    if cleaned in _GENERIC_ENTITY_NAMES:
        return True
    return False


def _allowed_entity_attribute_keys(entity_type: str) -> set[str]:
    return set(_ENTITY_TYPE_ATTRIBUTE_KEYS.get(_clean_text(entity_type or "OTHER").upper(), set()))


def _clean_entity_attributes(
    raw_attributes: dict[str, object] | None,
    *,
    entity_type: str | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    if not raw_attributes:
        return {}, {}
    attributes: dict[str, object] = {}
    extras: dict[str, object] = {}
    allowed_keys = _allowed_entity_attribute_keys(entity_type) if entity_type else set()
    for key, value in raw_attributes.items():
        cleaned_key = _clean_text(str(key)).casefold()
        if not cleaned_key:
            continue
        target = attributes if cleaned_key in allowed_keys else extras
        if isinstance(value, str):
            cleaned_value = _clean_text(value)
            if cleaned_value:
                target[cleaned_key] = cleaned_value
            continue
        if isinstance(value, (int, float, bool)):
            target[cleaned_key] = value
            continue
        if value is None:
            continue
        cleaned_value = _clean_text(str(value))
        if cleaned_value:
            target[cleaned_key] = cleaned_value
    return attributes, extras


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
        canonical_name = _clean_text(entity.canonical_name or display_name) or display_name
        cleaned_aliases = tuple(
            alias
            for alias in (_clean_text(item) for item in entity.aliases)
            if alias and alias.casefold() != normalized_name
        )
        alias_keys = _build_alias_keys(
            normalized_name,
            display_name,
            canonical_name,
            aliases=(*cleaned_aliases, *entity.alias_keys),
        )
        deduped_entities.setdefault(
            normalized_name,
            # Keep raw entity attributes for summary generation, but only
            # persist the filtered subset as node properties.
            GraphEntityRecord(
                team_id=chunk.team_id,
                knowledge_base_id=chunk.knowledge_base_id,
                document_id=chunk.document_id,
                document_chunk_id=chunk.document_chunk_id,
                normalized_name=normalized_name,
                display_name=display_name,
                entity_type=_clean_text(entity.entity_type or "OTHER") or "OTHER",
                aliases=cleaned_aliases,
                attributes=_clean_entity_attributes(entity.attributes, entity_type=entity.entity_type)[0],
                evidence=_clean_text(entity.evidence),
                canonical_name=canonical_name,
                alias_keys=alias_keys,
                raw_attributes=dict(entity.attributes or {}),
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
