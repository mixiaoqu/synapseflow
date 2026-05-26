"""Entity summary generation for graph data."""

from __future__ import annotations

import json
from typing import Any, Callable

from loguru import logger

from app.agents.common.llm_json import parse_llm_json_object
from app.core.llm import get_llm_for_analysis
from app.services.graph_store import GraphStore

SUMMARY_BATCH_SIZE = 8

_FIXED_RELATION_KEYS = {
    "team_id",
    "knowledge_base_id",
    "document_id",
    "document_chunk_id",
    "evidence",
}

_ENTITY_SUMMARY_TEMPLATE = (
    "请按固定三句骨架生成摘要：\n"
    "第一句：定义该实体是什么。\n"
    "第二句：只写它在当前知识库中的核心角色或最关键用途，不要重复罗列关系。\n"
    "第三句：写最重要的范围、约束、别名、状态；如果有 extra_attributes，请优先挑选最能补全实体理解的一两个点。\n"
    "要求：\n"
    "1. 只能基于提供的信息总结，不要补充外部知识。\n"
    "2. 信息不足时允许只输出1-2句，不要为了凑满三句而编造内容。\n"
    "3. 输出纯文本，不要 JSON，不要使用项目符号。"
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


def _extract_raw_attribute_map(raw_value: Any) -> dict[str, Any]:
    if not raw_value:
        return {}
    if isinstance(raw_value, dict):
        return {str(key).strip(): value for key, value in raw_value.items() if str(key).strip()}
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return {str(key).strip(): value for key, value in parsed.items() if str(key).strip()}
    return {}


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

    entity_attributes = _extract_attribute_map(context.get("entity_props"))
    raw_attributes = _extract_raw_attribute_map(context.get("raw_attributes_json"))
    extra_attributes = {
        key: value
        for key, value in raw_attributes.items()
        if key and key not in entity_attributes
    }
    return {
        "normalized_name": context.get("normalized_name"),
        "display_name": context.get("display_name"),
        "entity_type": context.get("entity_type"),
        "aliases": list(context.get("aliases") or []),
        "attributes": entity_attributes,
        "extra_attributes": extra_attributes,
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
        f"{_ENTITY_SUMMARY_TEMPLATE}\n\n"
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


def _chunked(items: list[dict[str, Any]], size: int = SUMMARY_BATCH_SIZE) -> list[list[dict[str, Any]]]:
    chunk_size = max(1, size)
    return [items[start : start + chunk_size] for start in range(0, len(items), chunk_size)]


def build_entity_summary_batch_prompt(contexts: list[dict[str, Any]]) -> str:
    payload = [_normalize_summary_context(context) for context in contexts]
    return (
        "你是知识库图谱摘要器。\n"
        f"{_ENTITY_SUMMARY_TEMPLATE}\n"
        "4. 输出 JSON，不要输出 JSON 之外的文字。\n"
        "5. 每个结果必须保留输入中的 normalized_name。\n\n"
        "返回格式：\n"
        '{"summaries":[{"normalized_name":"实体规范名","summary":"摘要"}]}\n\n'
        f"实体上下文列表：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def build_relation_summary_batch_prompt(contexts: list[dict[str, Any]]) -> str:
    payload = [_normalize_relation_summary_context(context) for context in contexts]
    return (
        "你是知识库图谱关系摘要器。\n"
        "请仅根据输入内容，为每条关系生成 1-2 句中文摘要。\n"
        "要求：\n"
        "1. 只能基于提供的信息总结，不要补充外部知识。\n"
        "2. 优先说明两端实体是什么关系，以及关系成立的关键上下文。\n"
        "3. 如果某条关系信息不足，就如实保持简洁，不要猜测。\n"
        "4. 输出 JSON，不要输出 JSON 之外的文字。\n"
        "5. 每个结果必须保留输入中的 source_normalized_name、target_normalized_name 和 relation_type。\n\n"
        "返回格式：\n"
        '{"summaries":[{"source_normalized_name":"源实体规范名","target_normalized_name":"目标实体规范名","relation_type":"关系类型","summary":"摘要"}]}\n\n'
        f"关系上下文列表：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _parse_json_payload(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    return parse_llm_json_object(_coerce_text(content))


async def summarize_entity_context(
    context: dict[str, Any],
    *,
    llm_factory: Callable[[], Any] | None = None,
    llm: Any | None = None,
) -> str:
    try:
        resolved_llm = llm or (llm_factory or get_llm_for_analysis)()
        response = await resolved_llm.ainvoke(build_entity_summary_prompt(context))
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
    llm: Any | None = None,
) -> str:
    try:
        resolved_llm = llm or (llm_factory or get_llm_for_analysis)()
        response = await resolved_llm.ainvoke(build_relation_summary_prompt(context))
        return " ".join(_coerce_text(getattr(response, "content", response)).split()).strip()
    except Exception as exc:
        logger.warning(
            "Relation summary generation failed for relation_type={}: {}",
            context.get("relation_type"),
            exc,
        )
        return ""


async def summarize_entity_contexts_batch(
    contexts: list[dict[str, Any]],
    *,
    llm: Any,
) -> dict[str, str]:
    if not contexts:
        return {}
    try:
        response = await llm.ainvoke(build_entity_summary_batch_prompt(contexts))
        parsed = _parse_json_payload(getattr(response, "content", response))
    except Exception as exc:
        logger.warning("Entity batch summary generation failed batch_size={}: {}", len(contexts), exc)
        return {}

    summaries: dict[str, str] = {}
    for item in parsed.get("summaries") or []:
        if not isinstance(item, dict):
            continue
        normalized_name = str(item.get("normalized_name") or "").strip()
        summary = " ".join(str(item.get("summary") or "").split()).strip()
        if normalized_name and summary:
            summaries[normalized_name] = summary
    return summaries


async def summarize_relation_contexts_batch(
    contexts: list[dict[str, Any]],
    *,
    llm: Any,
) -> dict[tuple[str, str, str], str]:
    if not contexts:
        return {}
    try:
        response = await llm.ainvoke(build_relation_summary_batch_prompt(contexts))
        parsed = _parse_json_payload(getattr(response, "content", response))
    except Exception as exc:
        logger.warning("Relation batch summary generation failed batch_size={}: {}", len(contexts), exc)
        return {}

    summaries: dict[tuple[str, str, str], str] = {}
    for item in parsed.get("summaries") or []:
        if not isinstance(item, dict):
            continue
        source_name = str(item.get("source_normalized_name") or "").strip()
        target_name = str(item.get("target_normalized_name") or "").strip()
        relation_type = str(item.get("relation_type") or "").strip()
        summary = " ".join(str(item.get("summary") or "").split()).strip()
        if source_name and target_name and relation_type and summary:
            summaries[(source_name, target_name, relation_type)] = summary
    return summaries


async def refresh_entity_summaries(
    *,
    store: GraphStore,
    knowledge_base_id: int,
    team_id: int,
    normalized_names: list[str],
    llm_factory: Callable[[], Any] | None = None,
    llm: Any | None = None,
) -> int:
    contexts = await store.list_entity_summary_contexts(
        knowledge_base_id=knowledge_base_id,
        team_id=team_id,
        normalized_names=normalized_names,
    )
    resolved_llm = llm or (llm_factory or get_llm_for_analysis)()
    rows: list[dict[str, Any]] = []
    for batch in _chunked(list(contexts)):
        summaries = await summarize_entity_contexts_batch(batch, llm=resolved_llm)
        for context in batch:
            normalized_name = str(context.get("normalized_name") or "").strip()
            summary = summaries.get(normalized_name)
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
    llm: Any | None = None,
) -> int:
    contexts = await store.list_relation_summary_contexts(
        knowledge_base_id=knowledge_base_id,
        team_id=team_id,
        document_id=document_id,
    )
    resolved_llm = llm or (llm_factory or get_llm_for_analysis)()
    rows: list[dict[str, Any]] = []
    for batch in _chunked(list(contexts)):
        summaries = await summarize_relation_contexts_batch(batch, llm=resolved_llm)
        for context in batch:
            source_name = str(context.get("source_normalized_name") or "").strip()
            target_name = str(context.get("target_normalized_name") or "").strip()
            relation_type = str(context.get("relation_type") or "").strip()
            summary = summaries.get((source_name, target_name, relation_type))
            if not summary:
                continue
            rows.append(
                {
                    "source_normalized_name": context.get("source_normalized_name"),
                    "target_normalized_name": context.get("target_normalized_name"),
                    "relation_type": context.get("relation_type"),
                    "team_id": team_id,
                    "knowledge_base_id": knowledge_base_id,
                    "summary": summary,
                }
            )
    await store.upsert_relation_summaries(rows)
    return len(rows)
