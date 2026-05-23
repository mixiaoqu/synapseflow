"""Entity summary generation for graph data."""

from __future__ import annotations

import json
from typing import Any, Callable

from loguru import logger

from app.core.llm import get_llm_for_analysis
from app.services.graph_store import GraphStore

_FIXED_RELATION_KEYS = {
    "team_id",
    "knowledge_base_id",
    "document_id",
    "document_chunk_id",
    "evidence",
}


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


def _extract_attribute_map(raw_props: dict[str, Any] | None) -> dict[str, Any]:
    if not raw_props:
        return {}
    attributes: dict[str, Any] = {}
    for key, value in raw_props.items():
        if not key.startswith("attr_"):
            continue
        attr_key = key[5:]
        if not attr_key:
            continue
        attributes[attr_key] = value
    return attributes


def _normalize_summary_context(context: dict[str, Any]) -> dict[str, Any]:
    mentions: list[dict[str, Any]] = []
    for item in context.get("mentions") or []:
        if not isinstance(item, dict):
            continue
        evidence = str(item.get("evidence") or "").strip()
        document_title = str(item.get("document_title") or "").strip()
        section_path = str(item.get("section_path") or "").strip()
        mention_attributes = _extract_attribute_map(item.get("mention_props"))
        if not any((evidence, document_title, section_path, mention_attributes)):
            continue
        mentions.append(
            {
                "document_title": document_title,
                "section_path": section_path,
                "evidence": evidence,
                "attributes": mention_attributes,
            }
        )

    relations: list[dict[str, Any]] = []
    for item in context.get("relations") or []:
        if not isinstance(item, dict):
            continue
        other = str(item.get("other") or "").strip()
        relation_type = str(item.get("relation_type") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        relation_attributes = _extract_attribute_map(item.get("relation_props"))
        if not any((other, relation_type, evidence, relation_attributes)):
            continue
        relations.append(
            {
                "other": other,
                "relation_type": relation_type,
                "evidence": evidence,
                "attributes": relation_attributes,
            }
        )

    return {
        "normalized_name": context.get("normalized_name"),
        "display_name": context.get("display_name"),
        "entity_type": context.get("entity_type"),
        "aliases": list(context.get("aliases") or []),
        "attributes": _extract_attribute_map(context.get("entity_props")),
        "mentions": mentions[:8],
        "relations": relations[:12],
    }


def _normalize_relation_summary_context(context: dict[str, Any]) -> dict[str, Any]:
    source_attributes = _extract_attribute_map(context.get("source_props"))
    target_attributes = _extract_attribute_map(context.get("target_props"))
    relation_attributes = _extract_attribute_map(context.get("relation_props"))
    return {
        "source_normalized_name": context.get("source_normalized_name"),
        "source_display_name": context.get("source_display_name"),
        "source_entity_type": context.get("source_entity_type"),
        "source_aliases": list(context.get("source_aliases") or []),
        "source_attributes": source_attributes,
        "target_normalized_name": context.get("target_normalized_name"),
        "target_display_name": context.get("target_display_name"),
        "target_entity_type": context.get("target_entity_type"),
        "target_aliases": list(context.get("target_aliases") or []),
        "target_attributes": target_attributes,
        "relation_type": context.get("relation_type"),
        "relation_attributes": relation_attributes,
        "evidence": str(context.get("evidence") or "").strip(),
    }


def build_entity_summary_prompt(context: dict[str, Any]) -> str:
    payload = _normalize_summary_context(context)
    return (
        "你是知识库图谱摘要器。\n"
        "请仅根据输入内容，为该实体生成 1-3 句中文摘要。\n"
        "要求：\n"
        "1. 只能基于提供的信息总结，不要补充外部知识。\n"
        "2. 优先说明该实体是什么、关键特征以及在当前知识库中的作用。\n"
        "3. 如果信息不足，就如实保持简洁，不要猜测。\n"
        "4. 输出纯文本，不要 JSON，不要使用项目符号。\n\n"
        f"实体上下文：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_relation_summary_prompt(context: dict[str, Any]) -> str:
    payload = _normalize_relation_summary_context(context)
    return (
        "你是知识库图谱关系摘要器。\n"
        "请仅根据输入内容，为该关系生成 1-2 句中文摘要。\n"
        "要求：\n"
        "1. 只能基于提供的信息总结，不要补充外部知识。\n"
        "2. 优先说明两端实体是什么关系，以及关系成立的关键上下文。\n"
        "3. 如果信息不足，就如实保持简洁，不要猜测。\n"
        "4. 输出纯文本，不要 JSON，不要使用项目符号。\n\n"
        f"关系上下文：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


async def summarize_entity_context(
    context: dict[str, Any],
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> str:
    try:
        llm = (llm_factory or get_llm_for_analysis)()
        response = await llm.ainvoke(build_entity_summary_prompt(context))
        return " ".join(_coerce_text(getattr(response, "content", response)).split()).strip()
    except Exception as exc:
        logger.warning(
            "Entity summary generation failed for normalized_name={}: {}",
            context.get("normalized_name"),
            exc,
        )
        return ""


async def summarize_relation_context(
    context: dict[str, Any],
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> str:
    try:
        llm = (llm_factory or get_llm_for_analysis)()
        response = await llm.ainvoke(build_relation_summary_prompt(context))
        return " ".join(_coerce_text(getattr(response, "content", response)).split()).strip()
    except Exception as exc:
        logger.warning(
            "Relation summary generation failed for relation_type={}: {}",
            context.get("relation_type"),
            exc,
        )
        return ""


async def refresh_entity_summaries(
    *,
    store: GraphStore,
    knowledge_base_id: int,
    team_id: int,
    normalized_names: list[str],
    llm_factory: Callable[[], Any] | None = None,
) -> int:
    contexts = await store.list_entity_summary_contexts(
        knowledge_base_id=knowledge_base_id,
        team_id=team_id,
        normalized_names=normalized_names,
    )
    rows: list[dict[str, Any]] = []
    for context in contexts:
        summary = await summarize_entity_context(context, llm_factory=llm_factory)
        if not summary:
            continue
        rows.append(
            {
                "normalized_name": context.get("normalized_name"),
                "display_name": context.get("display_name"),
                "entity_type": context.get("entity_type"),
                "team_id": team_id,
                "knowledge_base_id": knowledge_base_id,
                "summary": summary,
            }
        )
    await store.upsert_entity_summaries(rows)
    return len(rows)


async def refresh_relation_summaries(
    *,
    store: GraphStore,
    knowledge_base_id: int,
    team_id: int,
    document_id: int | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> int:
    contexts = await store.list_relation_summary_contexts(
        knowledge_base_id=knowledge_base_id,
        team_id=team_id,
        document_id=document_id,
    )
    rows: list[dict[str, Any]] = []
    for context in contexts:
        summary = await summarize_relation_context(context, llm_factory=llm_factory)
        if not summary:
            continue
        rows.append(
            {
                "source_normalized_name": context.get("source_normalized_name"),
                "target_normalized_name": context.get("target_normalized_name"),
                "relation_type": context.get("relation_type"),
                "summary": summary,
            }
        )
    await store.upsert_relation_summaries(rows)
    return len(rows)
