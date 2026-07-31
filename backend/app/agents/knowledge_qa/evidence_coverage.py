"""Evidence sufficiency assessment for knowledge retrieval subtasks."""

from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any, Callable

from app.agents.common.llm_json import parse_llm_json_object
from app.core.llm import get_llm_for_planner

ALLOWED_COVERAGE_STATUSES = {"covered", "partial", "weak", "missed"}
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


def _string_list(value: Any, *, limit: int, item_limit: int = 120) -> list[str]:
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


def _evidence_sample(result: dict[str, Any]) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for index, doc in enumerate(
        list(result.get("retrieved_docs") or [])[:EVIDENCE_AUDIT_MAX_DOCS],
        start=1,
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
                    doc.get("content"),
                    limit=EVIDENCE_AUDIT_CONTENT_MAX_CHARS,
                ),
            }
        )
    return {
        "id": result.get("id"),
        "goal": result.get("goal"),
        "evidence_requirement": result.get("evidence_requirement"),
        "used_queries": list(result.get("semantic_queries") or []),
        "used_lexical_terms": list(result.get("lexical_terms") or []),
        "raw_hit_count": int(result.get("raw_hit_count") or 0),
        "evidence": evidence,
    }


def _build_prompt(results: list[dict[str, Any]]) -> str:
    return f"""
你是知识库证据分析器。你的首要目标是从候选资料中识别能够可靠回答用户的事实，并判断这些事实能够回答到什么程度，而不是用完整答案标准淘汰不完整但有价值的证据。

只返回 JSON：
{{
  "subtasks": [
    {{
      "id": "task_1",
      "status": "covered | partial | missed",
      "failure_reason": "none | no_candidates | terminology_mismatch | parameter_over_specific | intent_mismatch | insufficient_evidence | below_rerank_threshold",
      "reason": "简短、基于证据的判断",
      "supported_evidence_indices": [1, 3],
      "supported_claims": ["候选证据能够直接支持的具体结论"],
      "discovered_terms": ["候选标题、章节或正文中出现的标准业务术语"]
    }}
  ]
}}

规则：
- 将同一子任务下的多条候选视为一个证据集合，允许综合不同片段中相互兼容的事实，不要求单个片段独立包含完整答案。
- goal 和 evidence_requirement 用于说明理想检索目标，不是必须逐项满足的硬性验收清单。先提取与用户目标直接相关、能够安全表达的事实，再判断覆盖程度。
- 证据可以通过明确陈述支持结论，也可以由多个明确事实组合出其直接蕴含的结论。组合后的每个关键事实都必须能追溯到候选内容，不得添加未记载的对象、条件、目的、因果或操作步骤。
- 不要求候选资料复述用户问题、使用相同句式、提供专门的定义段落或一次给出完整流程。
- 文档明确给出的同义词、括号别名、页面归属和跨模块关联可以作为对象一致性的依据；不能因为字面写法不同就判为 intent_mismatch。
- 对“如何设置、如何配置”等宽泛问题，只要证据能够支持明确的设置入口、配置范围或相关操作，就可在该证据范围内判为 covered；不要额外要求并不存在于目标中的创建、开通或启用步骤。
- 对包含具体金额、数量、日期或比例的问题，如果证据说明了对应的通用业务规则、配置字段和操作方式，应判为 covered；文档不需要原样出现用户输入的具体参数值。最终回答可以把用户参数代入这些字段。
- 仅仅主题相关、标题相似、出现相同名词或者返回了很多候选，都不能算 covered。
- covered 表示证据能够完整回答子目标；partial 表示证据只能回答子目标的一部分，但至少支持一个可直接告诉用户的具体结论；missed 表示没有任何可回答结论。
- partial 不是失败。必须通过 supported_claims 写出能够回答的部分，并通过 supported_evidence_indices 标出直接支持这些结论的候选证据。
- 只要存在一个与目标直接相关且可追溯的具体事实，就应判为 partial，而不是因为缺少完整答案判为 missed。
- 只有术语或标题线索、主题相似但没有可表达事实时，才判为 missed。
- supported_evidence_indices 使用候选证据中的 index，只选择直接支持 supported_claims 的证据，不要选择仅仅主题相关的片段。
- discovered_terms 只能摘取候选证据中实际出现的术语，不得推测或编造。
- 分数只能作为辅助信号，不能替代证据内容判断。

待审计内容：
{json.dumps([_evidence_sample(item) for item in results], ensure_ascii=False, default=str)}
""".strip()


async def assess_subtask_coverage(
    results: list[dict[str, Any]],
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Assess all retrieved subtasks in one structured model call."""

    if not results:
        return {"subtasks": [], "latency_ms": 0}

    deterministic: list[dict[str, Any]] = []
    auditable: list[dict[str, Any]] = []
    for result in results:
        if result.get("provider_error"):
            deterministic.append(
                {
                    "id": result.get("id"),
                    "status": "missed",
                    "failure_reason": "no_candidates",
                    "reason": "检索服务异常，未获得可审计证据。",
                    "supported_evidence_indices": [],
                    "supported_claims": [],
                    "discovered_terms": [],
                }
            )
        elif not list(result.get("retrieved_docs") or []):
            deterministic.append(
                {
                    "id": result.get("id"),
                    "status": "missed",
                    "failure_reason": result.get("empty_reason") or "no_candidates",
                    "reason": "没有获得可用于回答的候选证据。",
                    "supported_evidence_indices": [],
                    "supported_claims": [],
                    "discovered_terms": [],
                }
            )
        else:
            auditable.append(result)

    if not auditable:
        return {"subtasks": deterministic, "latency_ms": 0}

    llm = llm_factory() if llm_factory is not None else get_llm_for_planner(
        temperature=0,
        max_tokens=900,
    )
    started_at = perf_counter()
    response = await llm.ainvoke(_build_prompt(auditable))
    parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
    parsed_items = {
        str(item.get("id") or "").strip(): dict(item)
        for item in list(parsed.get("subtasks") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    assessed: list[dict[str, Any]] = []
    for result in auditable:
        subtask_id = str(result.get("id") or "").strip()
        item = parsed_items.get(subtask_id)
        if item is None:
            raise ValueError(f"证据审计缺少子任务结果: {subtask_id}")
        status = str(item.get("status") or "").strip().lower()
        if status not in ALLOWED_COVERAGE_STATUSES:
            raise ValueError(f"证据审计返回未知状态: {status}")
        if status == "weak":
            status = "partial"
        evidence_count = min(
            len(list(result.get("retrieved_docs") or [])),
            EVIDENCE_AUDIT_MAX_DOCS,
        )
        supported_indices = list(
            dict.fromkeys(
                index
                for raw_index in list(item.get("supported_evidence_indices") or [])
                if str(raw_index).strip().isdigit()
                if 1 <= (index := int(raw_index)) <= evidence_count
            )
        )
        if status == "covered" and not supported_indices:
            supported_indices = list(range(1, evidence_count + 1))
        supported_claims = _string_list(
            item.get("supported_claims"),
            limit=6,
            item_limit=240,
        )
        if status == "partial" and (not supported_indices or not supported_claims):
            status = "missed"
        failure_reason = str(item.get("failure_reason") or "none").strip().lower()
        if failure_reason not in ALLOWED_FAILURE_REASONS:
            failure_reason = "insufficient_evidence"
        assessed.append(
            {
                "id": subtask_id,
                "status": status,
                "failure_reason": "none" if status == "covered" else failure_reason,
                "reason": _compact_text(item.get("reason"), limit=240),
                "supported_evidence_indices": supported_indices,
                "supported_claims": supported_claims,
                "discovered_terms": _string_list(
                    item.get("discovered_terms"),
                    limit=8,
                ),
            }
        )
    return {
        "subtasks": [*deterministic, *assessed],
        "latency_ms": int((perf_counter() - started_at) * 1000),
    }
