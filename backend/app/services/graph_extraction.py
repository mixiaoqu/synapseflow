"""LLM-first graph extraction for persisted document chunks."""

from __future__ import annotations

import json
from typing import Any, Callable

from loguru import logger

from app.agents.common.llm_json import parse_llm_json_object
from app.core.config.registry import config_registry
from app.core.llm import get_llm_for_analysis
from app.services.graph_models import (
    ChunkGraphExtraction,
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationCandidate,
    build_entity_id,
    clean_graph_text,
)

_ALLOWED_ENTITY_TYPES = {
    "SYSTEM",
    "PRODUCT",
    "MODULE",
    "FEATURE",
    "COMPONENT",
    "CONFIG",
    "PAGE",
    "MENU",
    "FORM",
    "TABLE",
    "LIST",
    "BUTTON",
    "DIALOG",
    "WORKFLOW",
    "STEP",
    "PERMISSION",
    "ROLE",
    "STATUS",
    "BUSINESS_OBJECT",
    "ERROR",
    "SOLUTION",
    "OPERATION",
    "DOCUMENT",
    "PERSON",
    "TEAM",
    "OTHER",
}

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

_ENTITY_ATTRIBUTE_GUIDANCE = """实体 attributes 只存该实体自身的稳定结构化事实。
如果没有明确、可直接确认的稳定属性，可以返回空对象。
不要把关系事实、长证据原文、摘要、推断内容写进 attributes。"""


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content or "")


def _normalize_entity_type(value: Any) -> str:
    cleaned = clean_graph_text(value).upper()
    if not cleaned:
        return "OTHER"
    return cleaned if cleaned in _ALLOWED_ENTITY_TYPES else "OTHER"


def _normalize_relation_type(value: Any) -> str:
    cleaned = clean_graph_text(value).upper()
    if not cleaned:
        return "RELATED_TO"
    return cleaned if cleaned in _ALLOWED_RELATION_TYPES else "RELATED_TO"


def _parse_attributes(raw_value: Any) -> dict[str, Any]:
    if not raw_value:
        return {}
    if isinstance(raw_value, dict):
        return {
            clean_graph_text(key): value
            for key, value in raw_value.items()
            if clean_graph_text(key)
        }
    if isinstance(raw_value, list):
        attributes: dict[str, Any] = {}
        for item in raw_value:
            if not isinstance(item, dict):
                continue
            key = clean_graph_text(item.get("key") or item.get("name"))
            if not key:
                continue
            attributes[key] = item.get("value")
        return attributes
    return {}


def _parse_confidence(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score < 0:
        return 0.0
    if score > 1:
        return 1.0
    return score


def _truncate_chunk_text(chunk_text: str) -> str:
    max_chars = config_registry.get_graph_config().extraction_max_chars
    return chunk_text[:max_chars]


def _build_graph_extraction_prompt(
    *,
    chunk: GraphChunkRecord,
    chunk_text: str,
) -> str:
    return f"""
你是一个知识图谱抽取器。
请从给定文档片段中抽取适合进入企业知识库图谱的实体和关系。

要求：
1. 仅提取文本中明确出现或可直接确认的实体与关系，不要猜测。
2. 如果关系不明确，不要生成关系。
3. 实体 name 保持原文主要名称，只做最小清洗，不要自己改写成归一化 key。
4. aliases 只写文本中真实出现的别名、简称、代码名。
5. description 只写一句简短介绍，可为空。
6. attributes 只写实体自身稳定属性，不要写关系或长证据。
7. relation 中请尽量补充 source_type / target_type，便于实体对齐。
8. evidence_text 只保留能支持该关系的短证据。
9. 输出必须是 JSON。

允许的实体类型：
{json.dumps(sorted(_ALLOWED_ENTITY_TYPES), ensure_ascii=False)}

允许的关系类型：
{json.dumps(sorted(_ALLOWED_RELATION_TYPES), ensure_ascii=False)}

返回格式：
{{
  "entities": [
    {{
      "name": "实体名",
      "type": "实体类型",
      "aliases": ["别名"],
      "description": "一句话介绍",
      "attributes": {{"key": "value"}}
    }}
  ],
  "relations": [
    {{
      "source": "实体A",
      "source_type": "实体A类型",
      "target": "实体B",
      "target_type": "实体B类型",
      "type": "关系类型",
      "attributes": {{"key": "value"}},
      "evidence_text": "关系证据",
      "confidence": 0.9
    }}
  ]
}}

属性规则：
{_ENTITY_ATTRIBUTE_GUIDANCE}

document_id: {chunk.document_id}
document_chunk_id: {chunk.document_chunk_id}
document_title: {chunk.document_title or ""}
section_path: {chunk.section_path or ""}
chunk_text: {_truncate_chunk_text(chunk_text)}
""".strip()


def _build_graph_extraction_batch_prompt(
    items: list[tuple[GraphChunkRecord, str]],
) -> str:
    chunks_payload = [
        {
            "document_id": chunk.document_id,
            "document_chunk_id": chunk.document_chunk_id,
            "document_title": chunk.document_title or "",
            "section_path": chunk.section_path or "",
            "chunk_text": _truncate_chunk_text(chunk_text),
        }
        for chunk, chunk_text in items
    ]
    return f"""
你是一个知识图谱抽取器。
请从给定的多个文档片段中分别抽取适合进入企业知识库图谱的实体和关系。

要求：
1. 每个 chunk 都必须单独输出，并保留原 document_chunk_id。
2. 仅提取文本中明确出现或可直接确认的实体与关系，不要猜测。
3. 如果某个 chunk 没有结果，返回空数组。
4. source_type / target_type 尽量填写。
5. 输出必须是 JSON。

允许的实体类型：
{json.dumps(sorted(_ALLOWED_ENTITY_TYPES), ensure_ascii=False)}

允许的关系类型：
{json.dumps(sorted(_ALLOWED_RELATION_TYPES), ensure_ascii=False)}

返回格式：
{{
  "chunks": [
    {{
      "document_chunk_id": 123,
      "entities": [
        {{
          "name": "实体名",
          "type": "实体类型",
          "aliases": ["别名"],
          "description": "一句话介绍",
          "attributes": {{"key": "value"}}
        }}
      ],
      "relations": [
        {{
          "source": "实体A",
          "source_type": "实体A类型",
          "target": "实体B",
          "target_type": "实体B类型",
          "type": "关系类型",
          "attributes": {{"key": "value"}},
          "evidence_text": "关系证据",
          "confidence": 0.9
        }}
      ]
    }}
  ]
}}

属性规则：
{_ENTITY_ATTRIBUTE_GUIDANCE}

chunks:
{json.dumps(chunks_payload, ensure_ascii=False)}
""".strip()


def _parse_graph_extraction_payload(
    *,
    chunk: GraphChunkRecord,
    payload: dict[str, Any],
) -> ChunkGraphExtraction:
    raw_entities = payload.get("entities") or []
    raw_relations = payload.get("relations") or []

    entities: list[GraphEntityRecord] = []
    for item in raw_entities:
        if not isinstance(item, dict):
            continue
        name = clean_graph_text(item.get("name"))
        if not name:
            continue
        entity_type = _normalize_entity_type(item.get("type"))
        aliases = tuple(
            alias
            for alias in (clean_graph_text(alias) for alias in list(item.get("aliases") or []))
            if alias and alias != name
        )
        description = clean_graph_text(item.get("description")) or None
        entities.append(
            GraphEntityRecord(
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
                description=description,
                attributes=_parse_attributes(item.get("attributes")),
            )
        )

    relation_candidates: list[GraphRelationCandidate] = []
    for item in raw_relations:
        if not isinstance(item, dict):
            continue
        source_name = clean_graph_text(item.get("source"))
        target_name = clean_graph_text(item.get("target"))
        if not source_name or not target_name:
            continue
        relation_candidates.append(
            GraphRelationCandidate(
                source_name=source_name,
                target_name=target_name,
                relation_type=_normalize_relation_type(item.get("type")),
                source_entity_type=(
                    _normalize_entity_type(item.get("source_type"))
                    if clean_graph_text(item.get("source_type"))
                    else None
                ),
                target_entity_type=(
                    _normalize_entity_type(item.get("target_type"))
                    if clean_graph_text(item.get("target_type"))
                    else None
                ),
                evidence_text=clean_graph_text(item.get("evidence_text")) or None,
                confidence=_parse_confidence(item.get("confidence")),
                attributes=_parse_attributes(item.get("attributes")),
            )
        )

    return ChunkGraphExtraction(
        chunk=chunk,
        entities=entities,
        relation_candidates=relation_candidates,
    )


async def extract_chunk_graph(
    *,
    chunk: GraphChunkRecord,
    chunk_text: str,
    llm_factory: Callable[[], Any] | None = None,
) -> ChunkGraphExtraction:
    if not clean_graph_text(chunk_text):
        return ChunkGraphExtraction(chunk=chunk, entities=[], relation_candidates=[])

    try:
        llm = (llm_factory or get_llm_for_analysis)()
        response = await llm.ainvoke(
            _build_graph_extraction_prompt(
                chunk=chunk,
                chunk_text=chunk_text,
            )
        )
        parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
    except Exception as exc:
        logger.warning("Graph extraction failed for chunk_id={}: {}", chunk.document_chunk_id, exc)
        return ChunkGraphExtraction(chunk=chunk, entities=[], relation_candidates=[])

    return _parse_graph_extraction_payload(chunk=chunk, payload=parsed)


async def extract_chunk_graphs_batch(
    items: list[tuple[GraphChunkRecord, str]],
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> list[ChunkGraphExtraction]:
    if not items:
        return []

    results: dict[int, ChunkGraphExtraction] = {}
    non_empty_items: list[tuple[GraphChunkRecord, str]] = []
    for chunk, chunk_text in items:
        if clean_graph_text(chunk_text):
            non_empty_items.append((chunk, chunk_text))
        else:
            results[chunk.document_chunk_id] = ChunkGraphExtraction(
                chunk=chunk,
                entities=[],
                relation_candidates=[],
            )

    if not non_empty_items:
        return [results[chunk.document_chunk_id] for chunk, _chunk_text in items]

    try:
        llm = (llm_factory or get_llm_for_analysis)()
        response = await llm.ainvoke(_build_graph_extraction_batch_prompt(non_empty_items))
        parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
    except Exception as exc:
        logger.warning("Graph batch extraction failed chunks={}: {}", len(non_empty_items), exc)
        if len(non_empty_items) == 1:
            chunk, chunk_text = non_empty_items[0]
            single = await extract_chunk_graph(chunk=chunk, chunk_text=chunk_text, llm_factory=llm_factory)
            results[chunk.document_chunk_id] = single
        else:
            mid = len(non_empty_items) // 2
            left = await extract_chunk_graphs_batch(non_empty_items[:mid], llm_factory=llm_factory)
            right = await extract_chunk_graphs_batch(non_empty_items[mid:], llm_factory=llm_factory)
            for item in [*left, *right]:
                results[item.chunk.document_chunk_id] = item
        return [results[chunk.document_chunk_id] for chunk, _chunk_text in items]

    raw_chunks = parsed.get("chunks") or []
    chunk_by_id = {chunk.document_chunk_id: chunk for chunk, _chunk_text in non_empty_items}
    for item in raw_chunks:
        if not isinstance(item, dict):
            continue
        try:
            document_chunk_id = int(item.get("document_chunk_id"))
        except (TypeError, ValueError):
            continue
        chunk = chunk_by_id.get(document_chunk_id)
        if chunk is None:
            continue
        results[document_chunk_id] = _parse_graph_extraction_payload(chunk=chunk, payload=item)

    for chunk, _chunk_text in non_empty_items:
        results.setdefault(
            chunk.document_chunk_id,
            ChunkGraphExtraction(chunk=chunk, entities=[], relation_candidates=[]),
        )
    return [results[chunk.document_chunk_id] for chunk, _chunk_text in items]
