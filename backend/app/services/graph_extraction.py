"""LLM-first graph extraction for one persisted document chunk."""

from __future__ import annotations

import json
from typing import Any, Callable

from loguru import logger

from app.agents.common.llm_json import parse_llm_json_object
from app.core.llm import get_llm_for_analysis
from app.services.graph_models import (
    ChunkGraphExtraction,
    GraphChunkRecord,
    GraphEntityRecord,
    GraphRelationRecord,
)


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
2. 关系不明确时不要强行生成。
3. 输出必须是 JSON。
4. 如果没有结果，返回空数组。

允许的实体类型：
- SYSTEM
- PRODUCT
- MODULE
- FEATURE
- COMPONENT
- CONFIG
- DATABASE
- API
- SERVICE
- DOCUMENT
- PERSON
- TEAM
- OTHER

允许的关系类型：
- RELATED_TO
- PART_OF
- DEPENDS_ON
- USES
- CONNECTS_TO
- STORES_IN
- BELONGS_TO
- MENTIONED_WITH

 返回格式：
 {{
   "entities": [
    {{"name": "实体名", "type": "实体类型", "aliases": ["别名"], "attributes": {{"key": "value"}}, "evidence": "证据"}}
   ],
   "relations": [
    {{"source": "实体A", "target": "实体B", "type": "关系类型", "attributes": {{"key": "value"}}, "evidence": "证据"}}
   ]
 }}

document_id: {chunk.document_id}
document_chunk_id: {chunk.document_chunk_id}
document_title: {chunk.document_title or ""}
section_path: {chunk.section_path or ""}
chunk_text: {chunk_text}
""".strip()


def _normalize_name(value: str) -> str:
    return " ".join((value or "").split()).strip().casefold()


def _parse_attributes(raw_value: Any) -> dict[str, Any]:
    if not raw_value:
        return {}
    attributes: dict[str, Any] = {}
    if isinstance(raw_value, dict):
        items = raw_value.items()
        for key, value in items:
            cleaned_key = str(key or "").strip()
            if cleaned_key:
                attributes[cleaned_key] = value
        return attributes
    if isinstance(raw_value, list):
        for item in raw_value:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or item.get("name") or "").strip()
            if not key:
                continue
            attributes[key] = item.get("value")
        return attributes
    return {}


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
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        aliases = item.get("aliases") or []
        entities.append(
            GraphEntityRecord(
                team_id=chunk.team_id,
                knowledge_base_id=chunk.knowledge_base_id,
                document_id=chunk.document_id,
                document_chunk_id=chunk.document_chunk_id,
                normalized_name=_normalize_name(name),
                display_name=name,
                entity_type=str(item.get("type") or "OTHER").strip() or "OTHER",
                aliases=tuple(str(alias).strip() for alias in aliases if str(alias).strip()),
                attributes=_parse_attributes(item.get("attributes")),
                evidence=str(item.get("evidence") or "").strip(),
            )
        )

    relations: list[GraphRelationRecord] = []
    for item in raw_relations:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        if not source or not target:
            continue
        relations.append(
            GraphRelationRecord(
                team_id=chunk.team_id,
                knowledge_base_id=chunk.knowledge_base_id,
                document_id=chunk.document_id,
                document_chunk_id=chunk.document_chunk_id,
                source_normalized_name=_normalize_name(source),
                target_normalized_name=_normalize_name(target),
                relation_type=str(item.get("type") or "RELATED_TO").strip() or "RELATED_TO",
                attributes=_parse_attributes(item.get("attributes")),
                evidence=str(item.get("evidence") or "").strip(),
            )
        )

    return ChunkGraphExtraction(
        chunk=chunk,
        entities=entities,
        relations=relations,
    )


def _build_graph_extraction_batch_prompt(
    items: list[tuple[GraphChunkRecord, str]],
) -> str:
    chunks_payload = [
        {
            "document_id": chunk.document_id,
            "document_chunk_id": chunk.document_chunk_id,
            "document_title": chunk.document_title or "",
            "section_path": chunk.section_path or "",
            "chunk_text": chunk_text,
        }
        for chunk, chunk_text in items
    ]
    return f"""
你是一个知识图谱抽取器。
请从给定的多个文档片段中分别抽取适合进入企业知识库图谱的实体和关系。

要求：
1. 每个输入 chunk 必须分别输出一个结果，并保留原 document_chunk_id。
2. 仅提取文本中明确出现或可直接确认的实体与关系，不要猜测。
3. 关系不明确时不要强行生成。
4. 输出必须是 JSON。
5. 如果某个 chunk 没有结果，它的 entities 和 relations 返回空数组。

允许的实体类型：
- SYSTEM
- PRODUCT
- MODULE
- FEATURE
- COMPONENT
- CONFIG
- DATABASE
- API
- SERVICE
- DOCUMENT
- PERSON
- TEAM
- OTHER

允许的关系类型：
- RELATED_TO
- PART_OF
- DEPENDS_ON
- USES
- CONNECTS_TO
- STORES_IN
- BELONGS_TO
- MENTIONED_WITH

返回格式：
{{
  "chunks": [
    {{
      "document_chunk_id": 123,
      "entities": [
        {{"name": "实体名", "type": "实体类型", "aliases": ["别名"], "attributes": {{"key": "value"}}, "evidence": "证据"}}
      ],
      "relations": [
        {{"source": "实体A", "target": "实体B", "type": "关系类型", "attributes": {{"key": "value"}}, "evidence": "证据"}}
      ]
    }}
  ]
}}

chunks:
{json.dumps(chunks_payload, ensure_ascii=False)}
""".strip()


async def extract_chunk_graph(
    *,
    chunk: GraphChunkRecord,
    chunk_text: str,
    llm_factory: Callable[[], Any] | None = None,
) -> ChunkGraphExtraction:
    if not (chunk_text or "").strip():
        return ChunkGraphExtraction(chunk=chunk, entities=[], relations=[])

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
        return ChunkGraphExtraction(chunk=chunk, entities=[], relations=[])

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
        if (chunk_text or "").strip():
            non_empty_items.append((chunk, chunk_text))
        else:
            results[chunk.document_chunk_id] = ChunkGraphExtraction(chunk=chunk, entities=[], relations=[])

    if not non_empty_items:
        return [results[chunk.document_chunk_id] for chunk, _chunk_text in items]

    try:
        llm = (llm_factory or get_llm_for_analysis)()
        response = await llm.ainvoke(_build_graph_extraction_batch_prompt(non_empty_items))
        parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
    except Exception as exc:
        logger.warning("Graph batch extraction failed chunks={}: {}", len(non_empty_items), exc)
        return [
            ChunkGraphExtraction(chunk=chunk, entities=[], relations=[])
            for chunk, _chunk_text in items
        ]

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
            ChunkGraphExtraction(chunk=chunk, entities=[], relations=[]),
        )
    return [results[chunk.document_chunk_id] for chunk, _chunk_text in items]
