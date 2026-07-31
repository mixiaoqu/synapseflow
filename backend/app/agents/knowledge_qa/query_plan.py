"""Structured query planning owned by the knowledge QA workflow."""

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


def _normalize_subtasks(
    value: Any,
    *,
    expected_ids: list[str] | None = None,
    excluded_queries: set[str] | None = None,
) -> list[dict[str, Any]]:
    subtasks: list[dict[str, Any]] = []
    excluded = {item.casefold() for item in set(excluded_queries or set())}
    for index, item in enumerate(_object_list(value, limit=3), start=1):
        goal = _compact_text(item.get("goal"), limit=240)
        evidence_requirement = _compact_text(item.get("evidence_requirement"), limit=240)
        if not goal or not evidence_requirement:
            continue
        subtask_id = (
            expected_ids[index - 1]
            if expected_ids and index <= len(expected_ids)
            else f"task_{index}"
        )
        semantic_queries = [
            query
            for query in _string_list(
                item.get("semantic_queries"),
                limit=3,
                item_limit=240,
            )
            if query.casefold() not in excluded
        ][:2]
        parameter_abstract_queries = [
            query
            for query in _string_list(
                item.get("parameter_abstract_queries"),
                limit=3,
                item_limit=240,
            )
            if query.casefold() not in excluded
        ][:2]
        subtasks.append(
            {
                "id": subtask_id,
                "goal": goal,
                "semantic_queries": semantic_queries,
                "parameter_abstract_queries": parameter_abstract_queries,
                "lexical_terms": _string_list(
                    item.get("lexical_terms"),
                    limit=6,
                    item_limit=120,
                ),
                "evidence_requirement": evidence_requirement,
            }
        )
    return subtasks


def _build_prompt(
    goal: str,
    *,
    original_query: str,
    chat_history: list[dict[str, Any]],
    memory_summary: str | None,
    page_context: dict[str, Any],
    attempt: int,
    previous_plan: dict[str, Any] | None,
    retrieval_feedback: dict[str, Any] | None,
) -> str:
    history = "\n".join(
        f"{str(item.get('role') or 'user')}: {_compact_text(item.get('content'), limit=500)}"
        for item in chat_history[-4:]
        if _compact_text(item.get("content"), limit=500)
    )
    return f"""
你是知识库检索规划器。根据当前所有已知信息，生成下一步可独立执行和验证的检索计划。

只返回 JSON，不要回答用户，也不要选择具体检索策略、Top K、图谱模式或精排参数。

输出格式：
{{
  "question_type": "definition_lookup | attribute_lookup | location_lookup | flow_lookup | relationship_lookup | dependency_lookup | call_chain_lookup | summary_lookup",
  "retrieval_complexity": "fast | standard | broad",
  "standalone_query": "补全上下文后仍忠于原意的完整问题",
  "business_objects": ["问题涉及的业务对象"],
  "action": "用户要了解或执行的动作",
  "parameters": {{"threshold": 1000, "discount": 50}},
  "ambiguity": {{
    "needs_clarification": false,
    "clarification_question": "",
    "candidates": []
  }},
  "subtasks": [
    {{
      "goal": "单一、可检索的子目标",
      "semantic_queries": ["使用知识库标准业务术语表达的查询"],
      "parameter_abstract_queries": ["去掉具体数值、保留规则类型和动作的查询"],
      "lexical_terms": ["页面、菜单、按钮、字段、业务对象等精确词"],
      "evidence_requirement": "什么证据足以回答这个子目标；具体参数问题应说明可复用的配置字段或规则，不要求文档出现相同参数值"
    }}
  ],
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
- standalone_query 只补全指代和上下文，不得偷偷改变用户问题。
- 严格保留用户动作的范围。“设置、配置、管理、怎么弄”等宽泛动作，可以规划“入口、可配置项、操作说明”，但不得擅自收窄成“创建、开通、启用、导入、分配”等具体动作；只有用户原文或可信上下文明示时才可使用这些动作。
- subtasks 最多 3 个；简单问题只生成 1 个。每个子任务只解决一个目标，并明确证据要求。
- evidence_requirement 用于描述哪些事实能够为回答提供依据，不是完整答案的硬性验收清单。应写成可接受的事实范围，避免要求文档必须采用特定句式、包含专门说明章节或一次覆盖所有细节。
- semantic_queries 使用知识库可能采用的标准业务术语。原业务对象、可能的规范名称、上位概念应作为不同检索表达并行保留，不得用未经证实的术语替换原对象，也不得编造产品能力。
- 参数抽象查询用于具体数字、日期、比例、名称未必原样出现在文档中的情况。例如“满1000减50在哪创建”可抽象为“满减活动创建入口”和“满减规则设置流程”。
- 用户原文包含明确数字、日期、比例或金额时，必须提取到 parameters；这些值用于最终回答时回填，不得要求知识库文档原样包含同一组参数。
- lexical_terms 只保留适合精确匹配的页面、菜单、按钮、字段和不可拆业务短语，不要放完整自然语言问题。
- 原始问题由系统确定性保留，不要为了增加数量而重复原文。
- lexical_terms 必须包含能够区分业务对象的核心短语。用户使用“模块、功能、页面、系统”等泛化载体词时，同时生成去除载体词后的核心业务短语和可能的标准业务表达。
- 宽泛设置问题的 evidence_requirement 不得反过来要求文档必须证明用户没有问到的“创建或启用”。能够明确说明设置入口、配置范围或相关操作的证据即可支持对应范围的回答。
- 参数化问题的 evidence_requirement 应以“文档是否说明适用的通用规则、字段含义和操作方式”为准。例如“满1000减49”只需找到满减活动中满足金额、优惠金额及保存流程，不要求文档举例中恰好出现 1000 和 49。
- 示例：“PLUS会员如何设置”应围绕“PLUS会员/付费会员的设置入口、可配置项和操作说明”检索，可并行尝试“PLUS会员配置”“付费会员模式”“会员类型页面”“权益配置”等表达；不能直接改成“创建PLUS会员类型”。
- 确实存在会改变答案的歧义时设置 needs_clarification=true，提供一个简洁澄清问题，并且 subtasks 返回空数组；不要猜测。
- 能根据会话和页面上下文消解指代时，应将其补全到查询中。不要编造事实或不存在的实体。
- retrieval_complexity 描述检索宽度：精确单目标用 fast，常规问题用 standard，概览、多关系或多目标问题用 broad。
- 当前是第 {attempt} 次规划。首次规划应覆盖完整目标；再次规划只能处理 retrieval_feedback 中未覆盖的子任务。
- 再次规划时冻结原始问题、用户目标和已覆盖子任务；只处理 retrieval_feedback 中未覆盖的目标，利用候选标题、章节、片段和发现术语生成与首轮不同的检索表达，不得重复 used_queries。
- 一个失败目标可以被拆成多个更小的检索子任务，不要求二次规划结果与失败目标保持一一对应；如果根据现有反馈无法产生新的有效查询，可以返回空 subtasks，系统将停止重试并整理已有证据。
- 候选线索只用于发现别名、页面、菜单和上位概念，不能因为命中了相邻的通用流程，就把原业务对象等同为该通用对象；线索与原对象不一致时，应改查二者的关联或新的标准表达。

会话摘要：
{_compact_text(memory_summary, limit=2000) or "(none)"}

最近对话：
{history or "(none)"}

页面上下文：
{json.dumps(page_context, ensure_ascii=False, default=str)}

用户原文：
{original_query}

用户目标：
{goal}

上一轮计划：
{json.dumps(previous_plan or {}, ensure_ascii=False, default=str)}

检索反馈：
{json.dumps(retrieval_feedback or {}, ensure_ascii=False, default=str)}
""".strip()


async def build_knowledge_query_plan(
    goal: str,
    *,
    original_query: str | None = None,
    chat_history: list[dict[str, Any]] | None = None,
    memory_summary: str | None = None,
    page_context: dict[str, Any] | None = None,
    attempt: int = 1,
    previous_plan: dict[str, Any] | None = None,
    retrieval_feedback: dict[str, Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Build the complete structured retrieval input in one model call."""

    normalized_goal = _compact_text(goal, limit=800)
    normalized_original_query = _compact_text(original_query, limit=800) or normalized_goal
    llm = llm_factory() if llm_factory is not None else get_llm_for_planner(
        temperature=0,
        max_tokens=1400,
    )
    started_at = perf_counter()
    response = await llm.ainvoke(
        _build_prompt(
            normalized_goal,
            original_query=normalized_original_query,
            chat_history=list(chat_history or []),
            memory_summary=memory_summary,
            page_context=dict(page_context or {}),
            attempt=max(1, int(attempt)),
            previous_plan=dict(previous_plan or {}),
            retrieval_feedback=dict(retrieval_feedback or {}),
        )
    )
    parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
    question_type = _normalize_choice(
        parsed.get("question_type"), ALLOWED_QUESTION_TYPES, "definition_lookup"
    )
    retrieval_complexity = _normalize_choice(
        parsed.get("retrieval_complexity"), ALLOWED_RETRIEVAL_COMPLEXITIES, "standard"
    )
    frozen_plan = dict(previous_plan or {}) if attempt > 1 else {}
    standalone_query = _compact_text(
        frozen_plan.get("standalone_query") or parsed.get("standalone_query"),
        limit=800,
    )
    if not standalone_query:
        raise ValueError("知识库查询规划缺少 standalone_query")
    business_objects = _string_list(
        frozen_plan.get("business_objects") or parsed.get("business_objects"),
        limit=8,
        item_limit=120,
    )
    action = _compact_text(
        frozen_plan.get("action") or parsed.get("action"),
        limit=160,
    )
    query_parameters = (
        dict(frozen_plan.get("query_parameters") or parsed.get("parameters") or {})
        if isinstance(
            frozen_plan.get("query_parameters") or parsed.get("parameters"),
            dict,
        )
        else {}
    )
    raw_ambiguity_value = frozen_plan.get("ambiguity") or parsed.get("ambiguity")
    raw_ambiguity = (
        dict(raw_ambiguity_value or {})
        if isinstance(raw_ambiguity_value, dict)
        else {}
    )
    needs_clarification = bool(raw_ambiguity.get("needs_clarification"))
    ambiguity = {
        "needs_clarification": needs_clarification,
        "clarification_question": _compact_text(
            raw_ambiguity.get("clarification_question"),
            limit=240,
        ),
        "candidates": _string_list(raw_ambiguity.get("candidates"), limit=5, item_limit=120),
    }
    if needs_clarification and not ambiguity["clarification_question"]:
        raise ValueError("知识库查询规划标记存在歧义，但未提供 clarification_question")

    feedback = dict(retrieval_feedback or {})
    failed_subtasks = [
        dict(item)
        for item in list(feedback.get("failed_subtasks") or [])
        if isinstance(item, dict)
    ]
    expected_ids = [
        str(item.get("id") or "").strip()
        for item in failed_subtasks
        if str(item.get("id") or "").strip()
    ]
    excluded_queries = {
        str(item).strip()
        for item in list(feedback.get("used_queries") or [])
        if str(item or "").strip()
    }
    retrieval_subtasks = _normalize_subtasks(
        parsed.get("subtasks"),
        expected_ids=expected_ids or None,
        excluded_queries=excluded_queries,
    )
    replan_exhausted = (
        attempt > 1
        and bool(expected_ids)
        and not retrieval_subtasks
        and not needs_clarification
    )
    if attempt <= 1 and not needs_clarification and not retrieval_subtasks:
        raise ValueError("知识库查询规划没有生成可执行的检索子任务")

    planned_semantic_queries = [
        query
        for subtask in retrieval_subtasks
        for query in [
            subtask["goal"],
            *subtask["semantic_queries"],
            *subtask["parameter_abstract_queries"],
        ]
    ]
    semantic_queries = _string_list(
        [
            normalized_original_query,
            standalone_query,
            *planned_semantic_queries,
        ],
        limit=12,
    )
    lexical_terms = _string_list(
        [
            *business_objects,
            *[
                term
                for subtask in retrieval_subtasks
                for term in subtask["lexical_terms"]
            ],
        ],
        limit=18,
        item_limit=120,
    )

    result = {
        "question_type": question_type,
        "retrieval_complexity": retrieval_complexity,
        "standalone_query": standalone_query,
        "business_objects": business_objects,
        "action": action,
        "query_parameters": query_parameters,
        "ambiguity": ambiguity,
        "retrieval_subtasks": retrieval_subtasks,
        "replan_exhausted": replan_exhausted,
        "semantic_queries": semantic_queries,
        "lexical_terms": lexical_terms,
        "candidate_entities": business_objects,
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
            "attempt": max(1, int(attempt)),
            "is_replan": max(1, int(attempt)) > 1,
            "hyde_used": False,
            "original_query_preserved": bool(normalized_original_query),
            "standalone_query_generated": True,
            "subtask_count": len(retrieval_subtasks),
            "replan_exhausted": replan_exhausted,
            "needs_clarification": needs_clarification,
            "semantic_query_count": len(semantic_queries),
            "lexical_term_count": len(lexical_terms),
            "entity_count": len(business_objects),
            "latency_ms": int((perf_counter() - started_at) * 1000),
        },
    }
    result["current_query_plan"] = {
        key: result[key]
        for key in (
            "question_type",
            "retrieval_complexity",
            "standalone_query",
            "business_objects",
            "action",
            "query_parameters",
            "ambiguity",
            "retrieval_subtasks",
            "replan_exhausted",
            "semantic_queries",
            "lexical_terms",
        )
    }
    result["query_plan_attempt"] = max(1, int(attempt))
    return result
