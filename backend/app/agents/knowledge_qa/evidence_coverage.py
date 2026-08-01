"""单目标知识检索的证据充分性审计。"""

from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any, Callable

from app.agents.common.llm_json import parse_llm_json_object
from app.core.llm import get_llm_for_planner

ALLOWED_COVERAGE_STATUSES = {"covered", "partial", "missed"}
ALLOWED_FAILURE_REASONS = {
    "none",
    "no_candidates",
    "terminology_mismatch",
    "parameter_over_specific",
    "intent_mismatch",
    "insufficient_evidence",
    "below_rerank_threshold",
}
EVIDENCE_AUDIT_MAX_DOCS = 8
EVIDENCE_AUDIT_CONTENT_MAX_CHARS = 700


def _compact_text(value: Any, *, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit].strip()


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


def _string_list(value: Any, *, limit: int, item_limit: int = 240) -> list[str]:
    items = [value] if isinstance(value, str) else list(value or [])
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _compact_text(item, limit=item_limit)
        if not text or text.casefold() in seen:
            continue
        result.append(text)
        seen.add(text.casefold())
        if len(result) >= limit:
            break
    return result


def _build_prompt(result: dict[str, Any]) -> str:
    evidence = []
    for index, doc in enumerate(
        list(result.get("retrieved_docs") or [])[:EVIDENCE_AUDIT_MAX_DOCS], start=1
    ):
        if not isinstance(doc, dict):
            continue
        metadata = dict(doc.get("metadata") or {})
        evidence.append(
            {
                "index": index,
                "document_title": metadata.get("document_title"),
                "section_path": metadata.get("section_path"),
                "rerank_score": metadata.get("rerank_score"),
                "content": _compact_text(
                    doc.get("content"), limit=EVIDENCE_AUDIT_CONTENT_MAX_CHARS
                ),
            }
        )
    payload = {
        "goal": result.get("goal"),
        "evidence_requirements": result.get("evidence_requirements"),
        "evidence": evidence,
    }
    return f"""
你是知识库证据分析器。把所有候选视为同一个目标的证据集合，判断它们是否足以回答当前目标。

只返回 JSON：
{{
  "status": "covered | partial | missed",
  "failure_reason": "none | terminology_mismatch | parameter_over_specific | intent_mismatch | insufficient_evidence",
  "reason": "基于证据的简短判断",
  "supported_evidence_indices": [1, 3],
  "supported_claims": ["证据直接支持的结论"],
  "discovered_terms": ["证据中实际出现的术语"]
}}

规则：
- covered 表示能完整回答；partial 表示至少支持一个可直接告诉用户的事实；missed 表示没有可回答事实。
- evidence_requirements 是期望事实范围，不要求单篇资料一次覆盖全部内容。
- 可以综合多段明确事实，但不得补充资料中没有的条件、因果或步骤。
- 参数化问题只要资料说明通用规则、字段和操作方式即可，不要求出现相同数值。
- 主题、标题或词语相似不能单独构成支持。
- partial 必须同时给出 supported_claims 和对应 evidence indices。
- discovered_terms 只能摘取候选中实际出现的术语。

待审计内容：{json.dumps(payload, ensure_ascii=False, default=str)}
""".strip()


async def assess_goal_coverage(
    result: dict[str, Any],
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """审计一个目标的累计候选证据。"""

    if result.get("provider_error"):
        return {
            "status": "missed",
            "failure_reason": "no_candidates",
            "reason": "检索服务异常，未获得可审计证据。",
            "supported_evidence_indices": [],
            "supported_claims": [],
            "discovered_terms": [],
            "latency_ms": 0,
        }
    docs = [item for item in list(result.get("retrieved_docs") or []) if isinstance(item, dict)]
    if not docs:
        return {
            "status": "missed",
            "failure_reason": result.get("empty_reason") or "no_candidates",
            "reason": "没有获得可用于回答的候选证据。",
            "supported_evidence_indices": [],
            "supported_claims": [],
            "discovered_terms": [],
            "latency_ms": 0,
        }

    llm = llm_factory() if llm_factory is not None else get_llm_for_planner(
        temperature=0, max_tokens=700
    )
    started_at = perf_counter()
    response = await llm.ainvoke(_build_prompt(result))
    parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
    status = str(parsed.get("status") or "").strip().lower()
    if status not in ALLOWED_COVERAGE_STATUSES:
        raise ValueError(f"证据审计返回未知状态: {status}")
    evidence_count = min(len(docs), EVIDENCE_AUDIT_MAX_DOCS)
    supported_indices = list(
        dict.fromkeys(
            index
            for raw_index in list(parsed.get("supported_evidence_indices") or [])
            if str(raw_index).strip().isdigit()
            if 1 <= (index := int(raw_index)) <= evidence_count
        )
    )
    supported_claims = _string_list(parsed.get("supported_claims"), limit=6)
    if status == "covered" and not supported_indices:
        supported_indices = list(range(1, evidence_count + 1))
    if status == "partial" and (not supported_indices or not supported_claims):
        status = "missed"
    failure_reason = str(parsed.get("failure_reason") or "none").strip().lower()
    if failure_reason not in ALLOWED_FAILURE_REASONS:
        failure_reason = "insufficient_evidence"
    return {
        "status": status,
        "failure_reason": "none" if status == "covered" else failure_reason,
        "reason": _compact_text(parsed.get("reason"), limit=240),
        "supported_evidence_indices": supported_indices,
        "supported_claims": supported_claims,
        "discovered_terms": _string_list(parsed.get("discovered_terms"), limit=8, item_limit=120),
        "latency_ms": int((perf_counter() - started_at) * 1000),
    }
