"""Structured query planning owned by the knowledge QA workflow."""

from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any, Callable

from loguru import logger

from app.agents.common.llm_json import parse_llm_json_object
from app.core.llm import get_llm_for_planner
from app.services.kb_query_rewrite import generate_hyde_document

ALLOWED_QUESTION_TYPES = {
    "summary_lookup",
    "relationship_lookup",
    "dependency_lookup",
    "call_chain_lookup",
    "flow_lookup",
    "location_lookup",
    "attribute_lookup",
    "definition_lookup",
}
ALLOWED_RETRIEVAL_COMPLEXITIES = {"fast", "standard", "broad"}
HYDE_QUESTION_TYPES = {
    "summary_lookup",
    "relationship_lookup",
    "dependency_lookup",
    "call_chain_lookup",
    "flow_lookup",
}


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item if isinstance(item, str) else str(item.get("text", ""))
            for item in content
            if isinstance(item, (str, dict))
        )
    return str(content or "")


def _compact_text(value: Any, *, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit].strip()


def _normalize_choice(value: Any, allowed: set[str], default: str) -> str:
    normalized = re.sub(r"\s+", "_", str(value or "").strip().lower())
    return normalized if normalized in allowed else default


def _string_list(value: Any, *, limit: int, item_limit: int = 160) -> list[str]:
    items = [value] if isinstance(value, str) else list(value or [])
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _compact_text(item, limit=item_limit)
        if not normalized or normalized.casefold() in seen:
            continue
        result.append(normalized)
        seen.add(normalized.casefold())
        if len(result) >= limit:
            break
    return result


def _object_list(value: Any, *, limit: int) -> list[dict[str, Any]]:
    return [dict(item) for item in list(value or []) if isinstance(item, dict)][:limit]


def _should_use_hyde(*, question_type: str, retrieval_complexity: str) -> bool:
    return retrieval_complexity == "broad" or question_type in HYDE_QUESTION_TYPES


def _build_prompt(
    goal: str,
    *,
    chat_history: list[dict[str, Any]],
    memory_summary: str | None,
    page_context: dict[str, Any],
) -> str:
    history = "\n".join(
        f"{str(item.get('role') or 'user')}: {_compact_text(item.get('content'), limit=500)}"
        for item in chat_history[-4:]
        if _compact_text(item.get("content"), limit=500)
    )
    return f"""
你是知识库检索规划器。针对已经消解上下文的用户目标，生成一次完整、结构化的检索计划。

只返回 JSON，不要回答用户，也不要选择具体检索策略、Top K、图谱模式或精排参数。

输出格式：
{{
  "question_type": "definition_lookup | attribute_lookup | location_lookup | flow_lookup | relationship_lookup | dependency_lookup | call_chain_lookup | summary_lookup",
  "retrieval_complexity": "fast | standard | broad",
  "semantic_queries": ["完整、无歧义的向量检索查询"],
  "lexical_terms": ["关键词或不可拆短语"],
  "candidate_entities": ["用于图谱匹配的实体"],
  "relation_pairs": [{{"source": "", "target": ""}}],
  "relation_queries": [{{"anchor_entity": "", "target_entity": "", "direction": "outgoing | incoming"}}],
  "target_attributes": ["需要查询的属性"],
  "entity_constraints": {{}},
  "needs_path": false,
  "needs_relation": false,
  "needs_summary": false,
  "reason": "简短规划依据"
}}

规则：
- definition_lookup 用于定义或解释；attribute_lookup 用于字段、属性、配置或状态；location_lookup 用于文件、函数、模块或配置位置。
- flow_lookup 用于流程；relationship_lookup 用于关联或归属；dependency_lookup 和 call_chain_lookup 分别用于依赖方向与调用链；summary_lookup 用于概览或多方面总结。
- semantic_queries 必须保留完整问题语义；lexical_terms 只保留用于精确命中的词或短语；candidate_entities 只保留可匹配的实体名。
- 能根据会话和页面上下文消解指代时，应将其补全到查询中。不要编造事实或不存在的实体。
- retrieval_complexity 描述检索宽度：精确单目标用 fast，常规问题用 standard，概览、多关系或多目标问题用 broad。

会话摘要：
{_compact_text(memory_summary, limit=2000) or "(none)"}

最近对话：
{history or "(none)"}

页面上下文：
{json.dumps(page_context, ensure_ascii=False, default=str)}

用户目标：
{goal}
""".strip()


async def build_knowledge_query_plan(
    goal: str,
    *,
    chat_history: list[dict[str, Any]] | None = None,
    memory_summary: str | None = None,
    page_context: dict[str, Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Build the complete structured retrieval input in one model call."""

    normalized_goal = _compact_text(goal, limit=800)
    llm = llm_factory() if llm_factory is not None else get_llm_for_planner(
        temperature=0,
        max_tokens=900,
    )
    started_at = perf_counter()
    response = await llm.ainvoke(
        _build_prompt(
            normalized_goal,
            chat_history=list(chat_history or []),
            memory_summary=memory_summary,
            page_context=dict(page_context or {}),
        )
    )
    parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
    question_type = _normalize_choice(
        parsed.get("question_type"), ALLOWED_QUESTION_TYPES, "definition_lookup"
    )
    retrieval_complexity = _normalize_choice(
        parsed.get("retrieval_complexity"), ALLOWED_RETRIEVAL_COMPLEXITIES, "standard"
    )
    semantic_queries = _string_list(parsed.get("semantic_queries"), limit=4)
    if not semantic_queries and normalized_goal:
        semantic_queries = [normalized_goal]

    hyde_used = _should_use_hyde(
        question_type=question_type,
        retrieval_complexity=retrieval_complexity,
    )
    if hyde_used:
        try:
            hyde_document = await generate_hyde_document(
                normalized_goal,
                llm=llm,
                question_type=question_type,
                chat_history=list(chat_history or []),
                memory_summary=memory_summary,
                runtime_context=dict(page_context or {}),
            )
            semantic_queries = _string_list([*semantic_queries, hyde_document], limit=5, item_limit=400)
        except Exception as exc:
            hyde_used = False
            logger.warning("Knowledge query plan HyDE generation failed: {}", exc)

    return {
        "question_type": question_type,
        "retrieval_complexity": retrieval_complexity,
        "semantic_queries": semantic_queries,
        "lexical_terms": _string_list(parsed.get("lexical_terms"), limit=12, item_limit=120),
        "candidate_entities": _string_list(parsed.get("candidate_entities"), limit=8, item_limit=120),
        "relation_pairs": _object_list(parsed.get("relation_pairs"), limit=8),
        "relation_queries": _object_list(parsed.get("relation_queries"), limit=8),
        "target_attributes": _string_list(parsed.get("target_attributes"), limit=12, item_limit=120),
        "entity_constraints": (
            dict(parsed.get("entity_constraints") or {})
            if isinstance(parsed.get("entity_constraints"), dict)
            else {}
        ),
        "needs_path": bool(parsed.get("needs_path")),
        "needs_relation": bool(parsed.get("needs_relation")),
        "needs_summary": bool(parsed.get("needs_summary")),
        "retrieval_analysis": {
            "question_type": question_type,
            "retrieval_complexity": retrieval_complexity,
            "needs_path": bool(parsed.get("needs_path")),
            "needs_relation": bool(parsed.get("needs_relation")),
            "needs_summary": bool(parsed.get("needs_summary")),
            "reason": _compact_text(parsed.get("reason"), limit=240)
            or "知识库子图已完成检索规划。",
        },
        "query_plan_trace": {
            "engine": "llm",
            "hyde_used": hyde_used,
            "semantic_query_count": len(semantic_queries),
            "lexical_term_count": len(_string_list(parsed.get("lexical_terms"), limit=12, item_limit=120)),
            "entity_count": len(_string_list(parsed.get("candidate_entities"), limit=8, item_limit=120)),
            "latency_ms": int((perf_counter() - started_at) * 1000),
        },
    }
