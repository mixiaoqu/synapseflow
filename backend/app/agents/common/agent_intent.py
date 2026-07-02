"""Top-level intent routing helper for agent workflows."""

from __future__ import annotations

import re
from typing import Any, Callable

from app.agents.common.llm_json import parse_llm_json_object
from app.core.llm import get_llm_for_planner

ALLOWED_INTENT_TYPES = {"knowledge_qa", "business_ops", "clarify", "direct_answer"}
ALLOWED_DIRECT_ANSWER_KINDS = {"chitchat", "out_of_scope"}
BUSINESS_OPS_HINT_PATTERN = re.compile(
    r"(商品|库存|价格|售价|条码|sku|SKU|查一下|查询|搜索).*(商品|库存|价格|售价|条码|sku|SKU|可乐)"
    r"|(?:可乐|雪碧|冰红茶|矿泉水).*(库存|价格|售价|有没有|有吗)"
    r"|(?:查询|查一下|搜索|查找|看看|统计|列出).*(订单|会员|门店|客户|用户|记录|数据|数据库|表|商品|库存|价格)"
    r"|(?:订单|会员|门店|客户|用户|记录|数据|数据库|表).*(查询|查一下|搜索|查找|统计|列表|明细|数量)"
)
KNOWLEDGE_QA_HINT_PATTERN = re.compile(
    r"(能否|是否|能不能|可不可以|有没有权限|权限|允许|规则|限制|流程|如何|怎么|怎样|说明|手册|文档)"
    r".*(会员|门店负责人|负责人|角色|岗位|员工|账号|资料|页面|列表|功能|操作|配置|冻结|解冻|编辑|新增|删除|审核)"
    r"|(?:会员|门店负责人|负责人|角色|岗位|员工|账号|资料|页面|列表|功能|操作|配置|冻结|解冻|编辑|新增|删除|审核)"
    r".*(能否|是否|能不能|可不可以|有没有权限|权限|允许|规则|限制|流程|如何|怎么|怎样|说明|手册|文档)"
)


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content or "")


def _compact_text(text: str, *, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:limit].strip()


def _normalize_choice(value: Any, allowed: set[str], default: str) -> str:
    normalized = re.sub(r"\s+", "_", str(value or "").strip().lower())
    return normalized if normalized in allowed else default


def _coerce_string_list(value: Any, *, item_limit: int = 80) -> list[str]:
    if isinstance(value, str):
        raw_items = [value]
    else:
        raw_items = list(value or [])
    return [
        _compact_text(str(item), limit=item_limit)
        for item in raw_items
        if _compact_text(str(item), limit=item_limit)
    ]


def _build_prompt(
    query: str,
    *,
    chat_history: list[dict[str, Any]],
    memory_summary: str | None,
    page_type: str | None,
) -> str:
    history = "\n".join(
        f"{item.get('role', 'user')}: {_compact_text(str(item.get('content') or ''), limit=240)}"
        for item in chat_history[-4:]
        if str(item.get("content") or "").strip()
    )
    return f"""
You route one user turn for the top-level agent workflow.

Return JSON only:
{{
  "intent_type": "direct_answer",
  "needs_clarification": false,
  "missing_fields": [],
  "direct_answer_kind": "out_of_scope",
  "reason": "short reason"
}}

Allowed intent_type values:
- knowledge_qa
- business_ops
- clarify
- direct_answer

Allowed direct_answer_kind values when intent_type=direct_answer:
- chitchat
- out_of_scope

Rules:
- Do not answer the user.
- Decide only the top-level route: knowledge QA, clarification, or direct reply.
- Use business_ops when the user asks to query or operate concrete business data through tools, such as product inventory, prices, orders, members, stores, database records, tables, reports, or operational records.
- Use knowledge_qa when the user asks about rules, permissions, roles, feature behavior, documentation, operation steps, or "whether someone can do something", even if the question mentions stores, members, orders, or other business nouns.
- Do not classify the knowledge question type.
- Do not extract entities.
- Do not choose retrieval strategy, graph strategy, top-k, or rerank policy.
- Use knowledge_qa when the user asks about content that should be answered from the current knowledge base or conversation context.
- Use clarify only when the request is too incomplete to choose a route, such as an empty question or unresolved reference with no usable context.
- Use direct_answer only for greetings, simple social turns, or requests clearly outside knowledge-base answering.

Page type:
{page_type or "(none)"}

Conversation summary:
{_compact_text(memory_summary or "", limit=600) or "(none)"}

Recent history:
{history or "(none)"}

User question:
{query.strip()}
""".strip()


async def build_agent_intent(
    query: str,
    *,
    chat_history: list[dict[str, Any]] | None = None,
    memory_summary: str | None = None,
    page_type: str | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Classify the user turn for top-level agent routing only."""

    if not query.strip():
        return {
            "type": "clarify",
            "needs_clarification": True,
            "missing_fields": ["query"],
            "direct_answer_kind": None,
            "reason": "用户问题为空，需要补齐问题内容。",
        }
    if BUSINESS_OPS_HINT_PATTERN.search(query):
        return {
            "type": "business_ops",
            "needs_clarification": False,
            "missing_fields": [],
            "direct_answer_kind": None,
            "reason": "用户正在查询或操作具体业务数据。",
        }
    if KNOWLEDGE_QA_HINT_PATTERN.search(query):
        return {
            "type": "knowledge_qa",
            "needs_clarification": False,
            "missing_fields": [],
            "direct_answer_kind": None,
            "reason": "用户正在询问业务规则、权限或操作说明，应从知识库回答。",
        }

    llm = llm_factory() if llm_factory is not None else get_llm_for_planner(
        temperature=0,
        max_tokens=160,
    )
    response = await llm.ainvoke(
        _build_prompt(
            query,
            chat_history=list(chat_history or []),
            memory_summary=memory_summary,
            page_type=page_type,
        )
    )
    parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
    intent_type = _normalize_choice(
        parsed.get("intent_type") or parsed.get("type"),
        ALLOWED_INTENT_TYPES,
        "direct_answer",
    )
    needs_clarification = bool(parsed.get("needs_clarification"))
    missing_fields = _coerce_string_list(parsed.get("missing_fields"), item_limit=80)
    if needs_clarification or missing_fields:
        intent_type = "clarify"

    direct_answer_kind = None
    if intent_type == "direct_answer":
        direct_answer_kind = _normalize_choice(
            parsed.get("direct_answer_kind"),
            ALLOWED_DIRECT_ANSWER_KINDS,
            "out_of_scope",
        )

    return {
        "type": intent_type,
        "needs_clarification": intent_type == "clarify",
        "missing_fields": missing_fields,
        "direct_answer_kind": direct_answer_kind,
        "reason": _compact_text(str(parsed.get("reason") or ""), limit=240)
        or "主图无法确认需要调用知识库或业务数据能力，按直接回复处理。",
    }
