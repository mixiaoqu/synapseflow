"""LLM-based evidence evaluation for kb_chat_v2."""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Callable

from loguru import logger

from app.agents.common.llm_json import parse_llm_json_object
from app.agents.common.streaming import emit_progress, get_optional_stream_writer
from app.agents.states import KbChatV2State
from app.core.llm import get_llm_for_analysis

ALLOWED_STATUSES = {"sufficient", "insufficient", "empty", "clarification_needed"}
ALLOWED_ACTIONS = {"answer", "insufficient", "no_answer", "clarify"}


def _coerce_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item if isinstance(item, str) else str(item.get("text", ""))
            for item in content
            if isinstance(item, str) or isinstance(item, dict)
        )
    return str(content or "")


def _safe_json(value: Any, *, limit: int = 7000) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text[:limit]


def _fallback_evaluation(reason: str) -> dict[str, Any]:
    return {
        "status": "insufficient",
        "next_action": "insufficient",
        "reason": reason,
        "diagnostic": {
            "failure_stage": "evaluate",
            "details": reason,
        },
    }


def _build_prompt(state: dict[str, Any]) -> str:
    return f"""
You are judging whether retrieved evidence can answer the user's question.

Return JSON only:
{{
  "status": "sufficient",
  "next_action": "answer",
  "reason": "short reason",
  "diagnostic": {{"failure_stage": "unknown", "details": "short details"}},
  "clarification_need": null
}}

Allowed status values: sufficient, insufficient, empty, clarification_needed.
Allowed next_action values: answer, insufficient, no_answer, clarify.

Rules:
- Judge only from retrieved evidence, graph evidence, and context.
- Do not use outside knowledge.
- Do not produce the final user-facing answer.
- If evidence directly supports an answer, use sufficient/answer.
- If there are no useful hits, use empty/no_answer.
- If evidence is related but does not directly answer, use insufficient/insufficient.
- If the question lacks a core entity or has unresolved references, use clarification_needed/clarify.

Question:
{state.get("query") or ""}

Question type:
{state.get("question_type") or ""}

Retrieval label:
{state.get("retrieval_label") or ""}

Text queries:
{_safe_json(state.get("text_queries") or [])}

Candidate entities:
{_safe_json(state.get("candidate_entities") or [])}

Retrieved evidence:
{_safe_json(state.get("retrieved_docs") or [])}

Retrieval trace:
{_safe_json(state.get("retrieval_trace") or {})}

Context:
{str(state.get("context") or "")[:7000]}
""".strip()


def _normalize_evaluation(parsed: dict[str, Any]) -> dict[str, Any]:
    status = str(parsed.get("status") or "").strip().lower()
    next_action = str(parsed.get("next_action") or "").strip().lower()
    if status not in ALLOWED_STATUSES:
        status = "insufficient"
    if next_action not in ALLOWED_ACTIONS:
        next_action = {
            "sufficient": "answer",
            "empty": "no_answer",
            "clarification_needed": "clarify",
        }.get(status, "insufficient")
    diagnostic = parsed.get("diagnostic")
    if not isinstance(diagnostic, dict):
        diagnostic = {"failure_stage": "unknown", "details": ""}
    result = {
        "status": status,
        "next_action": next_action,
        "reason": str(parsed.get("reason") or "").strip() or "Evidence judged by LLM.",
        "diagnostic": diagnostic,
    }
    clarification_need = parsed.get("clarification_need")
    if isinstance(clarification_need, dict):
        result["clarification_need"] = clarification_need
    return result


async def evaluate_retrieval_evidence(
    state: dict[str, Any],
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    try:
        llm = llm_factory() if llm_factory is not None else get_llm_for_analysis()
        response = await llm.ainvoke(_build_prompt(state))
        parsed = parse_llm_json_object(_coerce_text(getattr(response, "content", response)))
        return _normalize_evaluation(parsed)
    except Exception as exc:
        logger.warning("kb_chat_v2 evaluate failed: {}", exc)
        return _fallback_evaluation("Evidence evaluation failed; answer generation was blocked.")


async def kb_chat_v2_evaluate_node(
    state: KbChatV2State,
    *,
    llm_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    stream_writer = get_optional_stream_writer()
    emit_progress(
        stream_writer,
        node_id="evaluate",
        stage="evaluate",
        message="正在核对答案依据",
    )
    started_at = perf_counter()
    evaluation = await evaluate_retrieval_evidence(state, llm_factory=llm_factory)
    status = evaluation.get("status")
    return {
        "retrieval_evaluation": evaluation,
        "answer_status": "answered" if status == "sufficient" else status,
        "evaluate_trace": {"latency_ms": int((perf_counter() - started_at) * 1000)},
    }
