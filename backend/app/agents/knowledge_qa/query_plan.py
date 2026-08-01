"""单目标知识库查询规划。"""

from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any, Callable

from app.agents.common.llm_json import parse_llm_json_object
from app.core.llm import get_llm_for_planner

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


def _string_list(value: Any, *, limit: int, item_limit: int = 200) -> list[str]:
    items = [value] if isinstance(value, str) else list(value or [])
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = _compact_text(item, limit=item_limit)
        identity = normalized.casefold()
        if not normalized or identity in seen:
            continue
        result.append(normalized)
        seen.add(identity)
        if len(result) >= limit:
            break
    return result


def _object_list(value: Any, *, limit: int) -> list[dict[str, Any]]:
    return [dict(item) for item in list(value or []) if isinstance(item, dict)][:limit]


def _build_prompt(
    goal: str,
    *,
    expected_facts: list[str],
    attempt: int,
    previous_plan: dict[str, Any],
    retrieval_feedback: dict[str, Any],
) -> str:
    return f"""
你是知识库单目标查询规划器。主流程已经消解指代、纠正明确错别字，并把多目标问题拆成了独立目标。你只负责为当前一个目标生成多条检索表达，不得再拆成子任务。

只返回 JSON：
{{
  "question_type": "definition_lookup | attribute_lookup | location_lookup | flow_lookup | relationship_lookup | dependency_lookup | call_chain_lookup | summary_lookup",
  "retrieval_complexity": "fast | standard | broad",
  "goal_query": "忠于目标、适合语义检索的规范表达",
  "semantic_queries": ["目标原表达或等价规范表达"],
  "lexical_terms": ["适合精确匹配的短语"],
  "evidence_requirements": ["回答该目标需要的事实"],
  "business_objects": ["业务对象"],
  "action": "用户动作",
  "parameters": {{}},
  "relation_pairs": [{{"source": "", "target": ""}}],
  "relation_queries": [{{"anchor_entity": "", "target_entity": "", "direction": "outgoing | incoming"}}],
  "target_attributes": [],
  "entity_constraints": {{}},
  "needs_path": false,
  "needs_relation": false,
  "needs_summary": false,
  "reason": "简短规划依据"
}}

规则：
- 当前只有一个回答目标，不得输出 subtasks，不得把同义词变成多个任务。
- semantic_queries 最多 3 条。系统会确定性保留当前目标，因此只补充真正有价值的术语化、规范化或同义表达；不得重复堆砌。
- lexical_terms 最多 3 条，只保留页面、菜单、按钮、字段、代码符号或不可拆业务短语，不要输出完整自然语言问题。
- 同义词必须是可信的等价表达；不能把相邻概念当成同义词，也不能编造产品能力。
- 保留名称、代码、版本、数值、条件和动作边界。明显错别字可规范化，有歧义的词不得猜测。
- evidence_requirements 描述回答所需事实，不是检索查询。优先沿用主流程给出的 expected_facts。
- 参数化问题应检索通用规则、字段与操作方式，不要求资料原样出现用户输入的数值。
- 第一次规划覆盖完整目标；第二次规划只能根据反馈生成尚未使用的新表达。若没有新表达，semantic_queries 和 lexical_terms 均返回空数组。

当前目标：{goal}
主流程预期事实：{json.dumps(expected_facts, ensure_ascii=False)}
规划轮次：{attempt}
上一轮计划：{json.dumps(previous_plan, ensure_ascii=False, default=str)}
检索反馈：{json.dumps(retrieval_feedback, ensure_ascii=False, default=str)}
""".strip()


async def build_knowledge_query_plan(
    goal: str,
    *,
    expected_facts: list[str] | None = None,
    attempt: int = 1,
    previous_plan: dict[str, Any] | None = None,
    retrieval_feedback: dict[str, Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """为一个目标生成最多三条语义查询和三条精确短语。"""

    normalized_goal = _compact_text(goal, limit=800)
    if not normalized_goal:
        raise ValueError("知识库查询规划缺少目标问题")
    normalized_expected_facts = _string_list(expected_facts, limit=6, item_limit=240)
    normalized_attempt = max(1, int(attempt))
    frozen_plan = dict(previous_plan or {}) if normalized_attempt > 1 else {}
    feedback = dict(retrieval_feedback or {})
    used_queries = {
        str(item).strip().casefold()
        for item in list(feedback.get("used_queries") or [])
        if str(item).strip()
    }
    llm = llm_factory() if llm_factory is not None else get_llm_for_planner(
        temperature=0,
        max_tokens=1000,
    )
    started_at = perf_counter()
    response = await llm.ainvoke(
        _build_prompt(
            normalized_goal,
            expected_facts=normalized_expected_facts,
            attempt=normalized_attempt,
            previous_plan=frozen_plan,
            retrieval_feedback=feedback,
        )
    )
    parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))

    model_semantic_queries = [
        item
        for item in _string_list(parsed.get("semantic_queries"), limit=3, item_limit=280)
        if item.casefold() not in used_queries and item.casefold() != normalized_goal.casefold()
    ]
    model_lexical_terms = [
        item
        for item in _string_list(parsed.get("lexical_terms"), limit=3, item_limit=120)
        if item.casefold() not in used_queries
    ]
    if normalized_attempt == 1:
        semantic_queries = _string_list(
            [normalized_goal, *model_semantic_queries], limit=3, item_limit=280
        )
    else:
        semantic_queries = model_semantic_queries[:3]
    lexical_terms = model_lexical_terms[:3]
    replan_exhausted = normalized_attempt > 1 and not semantic_queries and not lexical_terms

    question_type = _normalize_choice(
        frozen_plan.get("question_type") or parsed.get("question_type"),
        ALLOWED_QUESTION_TYPES,
        "definition_lookup",
    )
    retrieval_complexity = _normalize_choice(
        frozen_plan.get("retrieval_complexity") or parsed.get("retrieval_complexity"),
        ALLOWED_RETRIEVAL_COMPLEXITIES,
        "standard",
    )
    goal_query = _compact_text(
        frozen_plan.get("goal_query") or parsed.get("goal_query") or normalized_goal,
        limit=800,
    )
    evidence_requirements = normalized_expected_facts or _string_list(
        frozen_plan.get("evidence_requirements") or parsed.get("evidence_requirements"),
        limit=6,
        item_limit=240,
    )
    business_objects = _string_list(
        frozen_plan.get("business_objects") or parsed.get("business_objects"),
        limit=8,
        item_limit=120,
    )
    if normalized_attempt == 1 and not lexical_terms:
        lexical_terms = business_objects[:1]
    action = _compact_text(frozen_plan.get("action") or parsed.get("action"), limit=160)
    parameters = frozen_plan.get("query_parameters") or parsed.get("parameters") or {}
    query_parameters = dict(parameters) if isinstance(parameters, dict) else {}

    return {
        "question_type": question_type,
        "retrieval_complexity": retrieval_complexity,
        "goal_query": goal_query,
        "evidence_requirements": evidence_requirements,
        "business_objects": business_objects,
        "action": action,
        "query_parameters": query_parameters,
        "semantic_queries": semantic_queries,
        "lexical_terms": lexical_terms,
        "candidate_entities": business_objects,
        "relation_pairs": _object_list(parsed.get("relation_pairs"), limit=8),
        "relation_queries": _object_list(parsed.get("relation_queries"), limit=8),
        "target_attributes": _string_list(parsed.get("target_attributes"), limit=12, item_limit=120),
        "entity_constraints": dict(parsed.get("entity_constraints") or {})
        if isinstance(parsed.get("entity_constraints"), dict)
        else {},
        "needs_path": bool(parsed.get("needs_path")),
        "needs_relation": bool(parsed.get("needs_relation")),
        "needs_summary": bool(parsed.get("needs_summary")),
        "replan_exhausted": replan_exhausted,
        "retrieval_analysis": {
            "question_type": question_type,
            "retrieval_complexity": retrieval_complexity,
            "needs_path": bool(parsed.get("needs_path")),
            "needs_relation": bool(parsed.get("needs_relation")),
            "needs_summary": bool(parsed.get("needs_summary")),
            "reason": _compact_text(parsed.get("reason"), limit=240)
            or "知识库子图已完成单目标查询规划。",
        },
        "query_plan_trace": {
            "engine": "llm",
            "attempt": normalized_attempt,
            "is_replan": normalized_attempt > 1,
            "goal_preserved": normalized_goal in semantic_queries if normalized_attempt == 1 else True,
            "semantic_query_count": len(semantic_queries),
            "lexical_term_count": len(lexical_terms),
            "latency_ms": int((perf_counter() - started_at) * 1000),
        },
        "current_query_plan": {
            "question_type": question_type,
            "retrieval_complexity": retrieval_complexity,
            "goal_query": goal_query,
            "evidence_requirements": evidence_requirements,
            "business_objects": business_objects,
            "action": action,
            "query_parameters": query_parameters,
        },
        "query_plan_attempt": normalized_attempt,
    }
