"""Top-level decision helper for the agent workflow."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable

from app.agents.common.llm_json import parse_llm_json_object
from app.agents.runtime.capabilities import CapabilityDefinition
from app.core.llm import get_llm_for_planner

ALLOWED_ACTIONS = {"invoke", "clarify", "respond", "unsupported"}
ALLOWED_INTENT_KINDS = {
    "information",
    "data_query",
    "action",
    "conversation",
    "unclear",
}
ALLOWED_RESPONSE_KINDS = {"out_of_scope"}
BUSINESS_OPS_HINT_PATTERN = re.compile(
    r"(?:查询|查一下|搜索|查找|获取|读取|查看|统计|列出|创建|更新|提交|取消|同步)"
    r".*(?:订单|会员|门店|客户|用户|记录|数据|商品|库存|价格|物流|账户|工单|状态)"
    r"|(?:订单|会员|门店|客户|用户|记录|数据|商品|库存|价格|物流|账户|工单|状态)"
    r".*(?:查询|查一下|搜索|查找|获取|读取|查看|统计|列表|明细|数量|创建|更新|提交|取消|同步)"
)
KNOWLEDGE_QA_HINT_PATTERN = re.compile(
    r"(能否|是否|能不能|可不可以|有没有权限|权限|允许|规则|限制|流程|如何|怎么|怎样|说明|手册|文档)"
    r".*(会员|门店负责人|负责人|角色|岗位|员工|账号|资料|页面|列表|功能|操作|配置|冻结|解冻|编辑|新增|删除|审核|条件|筛选|搜索)"
    r"|(?:会员|门店负责人|负责人|角色|岗位|员工|账号|资料|页面|列表|功能|操作|配置|冻结|解冻|编辑|新增|删除|审核)"
    r".*(能否|是否|能不能|可不可以|有没有权限|权限|允许|规则|限制|流程|如何|怎么|怎样|说明|手册|文档|条件|筛选|搜索条件|字段|关系)"
    r"|(?:条件|筛选|搜索条件|筛选条件|查询条件|字段|页面行为|系统如何|系统怎么|同时设置)"
    r".*(关系|如何|怎么|怎样|规则|逻辑|查询|筛选|搜索|生效)"
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


def _coerce_string_list(value: Any, *, item_limit: int = 80) -> list[str]:
    raw_items = [value] if isinstance(value, str) else list(value or [])
    return [
        _compact_text(str(item), limit=item_limit)
        for item in raw_items
        if _compact_text(str(item), limit=item_limit)
    ]


def _resolve_capability_hint(query: str) -> str:
    if KNOWLEDGE_QA_HINT_PATTERN.search(query):
        return "knowledge_qa"
    if BUSINESS_OPS_HINT_PATTERN.search(query):
        return "business_ops"
    return ""


def _capability_catalog(
    capabilities: Iterable[CapabilityDefinition],
) -> list[dict[str, str]]:
    return [
        {
            "capability_id": capability.capability_id,
            "description": capability.description,
        }
        for capability in capabilities
    ]


def _build_prompt(
    query: str,
    *,
    chat_history: list[dict[str, Any]],
    memory_summary: str | None,
    page_context: dict[str, Any],
    capabilities: Iterable[CapabilityDefinition],
) -> str:
    history = "\n".join(
        f"{item.get('role', 'user')}: {_compact_text(str(item.get('content') or ''), limit=240)}"
        for item in chat_history[-4:]
        if str(item.get("content") or "").strip()
    )
    capability_catalog = _capability_catalog(capabilities)
    capability_hint = _resolve_capability_hint(query)
    return f"""
You decide how the top-level agent should handle one user turn.

Return JSON only:
{{
  "action": "invoke",
  "intent": {{
    "kind": "information",
    "goal": "a complete standalone user goal"
  }},
  "capability_id": "knowledge_qa",
  "missing_fields": [],
  "response_kind": null,
  "reason": "short internal reason"
}}

Allowed action values:
- invoke: one available capability can handle the request
- clarify: the high-level user goal is too incomplete to choose a capability
- respond: answer a general conversation request directly without invoking a capability
- unsupported: no available capability can handle the request

Allowed intent.kind values:
- information
- data_query
- action
- conversation
- unclear

Allowed response_kind values:
- out_of_scope

Rules:
- Do not answer the user.
- Resolve references and omitted context using conversation history, memory, and page context.
- intent.goal must be concise, complete, standalone, and free of unresolved pronouns.
- Choose at most one capability and only from the supplied capability catalog.
- Use clarify only when the high-level goal itself is unclear. Capability-specific parameters are validated inside the selected capability.
- Do not extract tool arguments, filters, sorting, retrieval strategy, top-k, or other capability-internal parameters.
- Use respond for greetings, writing, rewriting, translation, summarization, comparison, logical reasoning, conversation review, and contextual continuation that can be completed from the current input and conversation context.
- Use unsupported when the goal is clear but cannot be handled by respond or a supplied capability.
- response_kind is out_of_scope only when no capability is invoked.
- capability_id must be null unless action is invoke.
- Prefer the capability hint only when it is present and consistent with the user goal.

Capability catalog:
{json.dumps(capability_catalog, ensure_ascii=False, indent=2)}

Capability hint:
{capability_hint or "(none)"}

Page context:
{json.dumps(page_context, ensure_ascii=False, default=str)}

Conversation summary:
{_compact_text(memory_summary or "", limit=600) or "(none)"}

Recent history:
{history or "(none)"}

User question:
{query.strip()}
""".strip()


async def build_agent_decision(
    query: str,
    *,
    capabilities: Iterable[CapabilityDefinition],
    chat_history: list[dict[str, Any]] | None = None,
    memory_summary: str | None = None,
    page_context: dict[str, Any] | None = None,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Understand one user turn and select at most one capability."""

    available_capabilities = tuple(capabilities)
    if not query.strip():
        return {
            "action": "clarify",
            "intent": {"kind": "unclear", "goal": ""},
            "capability_id": None,
            "missing_fields": ["query"],
            "response_kind": None,
            "reason": "用户问题为空，需要补齐问题内容。",
        }

    llm = llm_factory() if llm_factory is not None else get_llm_for_planner(
        temperature=0,
        max_tokens=260,
    )
    response = await llm.ainvoke(
        _build_prompt(
            query,
            chat_history=list(chat_history or []),
            memory_summary=memory_summary,
            page_context=dict(page_context or {}),
            capabilities=available_capabilities,
        )
    )
    parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
    if not parsed:
        raise ValueError("Top-level decision model returned no valid JSON object")

    action = re.sub(r"\s+", "_", str(parsed.get("action") or "").strip().lower())
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported top-level decision action: {action or '(empty)'}")

    parsed_intent = dict(parsed.get("intent") or {})
    intent_kind = re.sub(
        r"\s+", "_", str(parsed_intent.get("kind") or "").strip().lower()
    )
    if intent_kind not in ALLOWED_INTENT_KINDS:
        raise ValueError(f"Unsupported top-level intent kind: {intent_kind or '(empty)'}")
    goal = _compact_text(str(parsed_intent.get("goal") or ""), limit=500)
    if not goal and action != "clarify":
        raise ValueError("Top-level decision is missing intent.goal")

    missing_fields = _coerce_string_list(parsed.get("missing_fields"), item_limit=80)
    if action == "clarify":
        missing_fields = missing_fields or ["goal"]
    else:
        missing_fields = []

    capability_id = str(parsed.get("capability_id") or "").strip() or None
    available_ids = {
        capability.capability_id for capability in available_capabilities
    }
    if action == "invoke":
        if capability_id not in available_ids:
            raise ValueError(f"Decision selected unavailable capability: {capability_id}")
    else:
        capability_id = None

    response_kind = str(parsed.get("response_kind") or "").strip().lower() or None
    if action == "unsupported":
        if response_kind not in ALLOWED_RESPONSE_KINDS:
            response_kind = "out_of_scope"
    else:
        response_kind = None

    return {
        "action": action,
        "intent": {"kind": intent_kind, "goal": goal},
        "capability_id": capability_id,
        "missing_fields": missing_fields,
        "response_kind": response_kind,
        "reason": _compact_text(str(parsed.get("reason") or ""), limit=240)
        or "主图已完成用户目标理解和能力选择。",
    }
