"""评估答案质量节点"""
import re
from typing import Any, Dict

from app.agents.prompts import build_kb_curation_evaluation_prompt
from app.agents.states import KbCurationState
from app.utils import extract_json_from_llm_response
from app.core.config.registry import config_registry
from app.core.llm import get_llm_for_analysis

# 仅匹配「明确拒答 / 检索失败 / 无法据库作答」类话术。
# 注意：不要匹配「文档未说明具体步骤」「本节未包含某字段」等——那是如实描述局限，属于合格答案，否则会误触 0.5 封顶。
ANSWER_DECLINES_PATTERN = re.compile(
    r"(?:无法|不能)(?:从)?(?:知识库|当前文档)(?:中)?检索不到|"
    r"未检索到(?:相关)?(?:文档|资料|内容)|"
    r"无法(?:基于|根据)(?:当前)?(?:知识库|文档)(?:内容)?(?:提供(?:完整)?回答|回答该问题|给出答案)|"
    r"无法提供(?:基于知识库)?的?(?:有效)?(?:答案|回复)(?:[，,。]|$)|"
    r"无法回答(?:本|该)问题|无法确定(?:如何|能否)(?:基于知识库)?回答|"
    r"知识库(?:中)?(?:暂无|没有任何)(?:相关)?(?:文档|条目|记录)|"
    r"暂无相关(?:文档|资料)(?:可供)?|"
    r"未找到(?:任何)?(?:相关)?(?:文档|资料)"
)

# 规则封顶：无检索时无法验证依据，总分不应达到「通过」
NO_RETRIEVAL_SCORE_CAP = 0.45

# suggestion 过短则视为未给出可执行指示，由规则兜底（保证问题优化器有明确依据）
_MIN_SUGGESTION_LEN = 12


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _compute_weighted_score(
    result: Dict[str, Any], weights: Dict[str, float]
) -> tuple[float, Dict[str, float] | None]:
    """
    优先使用 relevance / groundedness / completeness（0~1）加权得到总分；
    若缺任一项则回退到 result['score']。
    权重来自 config/embedding.yaml evaluate.weights。
    """
    raw_r = result.get("relevance")
    raw_g = result.get("groundedness")
    raw_c = result.get("completeness")
    if raw_r is not None and raw_g is not None and raw_c is not None:
        try:
            r = _clamp01(float(raw_r))
            g = _clamp01(float(raw_g))
            c = _clamp01(float(raw_c))
            dims = {"relevance": r, "groundedness": g, "completeness": c}
            wr, wg, wc = weights["relevance"], weights["groundedness"], weights["completeness"]
            s = wr * r + wg * g + wc * c
            return _clamp01(s), dims
        except (TypeError, ValueError):
            pass
    try:
        return _clamp01(float(result.get("score", 0.5))), None
    except (TypeError, ValueError):
        return 0.5, None


def _apply_accuracy_constraints(
    score: float,
    *,
    retrieved_docs: list,
    answer: str,
    context: str,
) -> float:
    """
    将总分与可观测事实对齐：空答案、无检索片段等强制上限。
    不再对「拒答话术」单独压到 0.5，交由模型分项打分体现。
    """
    s = _clamp01(score)
    ans = (answer or "").strip()

    if not ans:
        return _clamp01(min(s, 0.25))

    if not retrieved_docs:
        return _clamp01(min(s, NO_RETRIEVAL_SCORE_CAP))

    # 有检索且 context 实质为空字符串（非正常占位）：略压分，避免虚高
    if retrieved_docs and not (context or "").strip():
        return _clamp01(min(s, 0.55))

    return s


def _apply_dimension_floor_penalty(
    score: float, dims: Dict[str, float] | None
) -> float:
    """分项极差时压低总分，避免加权均值掩盖「某一维完全失败」。"""
    if not dims:
        return score
    vals = [dims["relevance"], dims["groundedness"], dims["completeness"]]
    if any(v < 0.35 for v in vals):
        return _clamp01(min(score, 0.52))
    if any(v < 0.5 for v in vals):
        return _clamp01(min(score, 0.72))
    return score


def _ensure_actionable_suggestion(
    suggestion: str,
    retrieved_docs: list,
    answer: str,
    context: str,
) -> str:
    """评估模型未给出足够具体的 suggestion 时，按场景兜底，供下一轮检索改写使用。"""
    s = (suggestion or "").strip()
    if len(s) >= _MIN_SUGGESTION_LEN:
        return s
    if not retrieved_docs:
        return (
            "【下一轮检索】请用更宽泛、更短的问句；去掉非必要限定词；尝试同义词或更基础的上位概念；"
            "若原问题含多个子问题，先只保留最核心的一条用于检索。"
        )
    if ANSWER_DECLINES_PATTERN.search(answer or ""):
        return (
            "【下一轮检索】知识库片段中可能已有相关信息。请将用户问题改写为与片段主题、用词更贴近的检索问句；"
            "可换问法，或拆成与片段中术语一致的具体子问题。"
        )
    if not (context or "").strip():
        return (
            "【下一轮检索】请突出用户问题中的核心实体与任务；若之前检索方向过窄，可尝试同义扩展或补全维度（谁/何时/如何）。"
        )
    return (
        "【下一轮检索】请根据上述原因，将用户问题改写为单条便于向量检索的问句；"
        "若未覆盖多维度，优先输出本轮最缺失的那一条子问题。"
    )


async def evaluate_node(state: KbCurationState) -> Dict[str, Any]:
    """
    评估节点：快速评估答案质量并打分，并记录迭代历史。
    未达标时输出面向「下一轮向量检索」的可执行 suggestion（结合检索片段与答案）；
    suggestion 过短时由规则按场景兜底。
    """
    llm = get_llm_for_analysis()
    ev_cfg = config_registry.get_rag_config().evaluate
    weights = ev_cfg.weights
    weights_dict = {
        "relevance": weights.relevance,
        "groundedness": weights.groundedness,
        "completeness": weights.completeness,
    }
    context_max_chars = ev_cfg.context_max_chars
    pass_threshold = ev_cfg.pass_threshold
    wr, wg, wc = weights.relevance, weights.groundedness, weights.completeness

    current_query = state.get("optimized_query") or state.get("query", "")
    context = state.get("context") or ""
    if len(context) > context_max_chars:
        context = context[:context_max_chars] + "\n\n...(已截断)"

    eval_prompt = build_kb_curation_evaluation_prompt(
        query=current_query,
        context=context,
        answer=state["answer"],
        pass_threshold=pass_threshold,
        weights=weights,
    )
    response = await llm.ainvoke(eval_prompt)
    raw = response.content or ""

    retrieved_docs = state.get("retrieved_docs") or []
    dims: Dict[str, float] | None = None

    try:
        result = extract_json_from_llm_response(raw)
        score, dims = _compute_weighted_score(result, weights_dict)
        score = _apply_dimension_floor_penalty(score, dims)
        score = _apply_accuracy_constraints(
            score,
            retrieved_docs=retrieved_docs,
            answer=state.get("answer") or "",
            context=context,
        )
        reason = result.get("reason", "") or ""
        suggestion = result.get("suggestion", "") or ""
        raw_doc_issues = result.get("document_issues", [])
        doc_issues = [
            {"round": state["iteration"] + 1, **issue}
            for issue in (raw_doc_issues if isinstance(raw_doc_issues, list) else [])
            if isinstance(issue, dict)
        ]
    except Exception:
        score = 0.5
        dims = None
        reason = ""
        suggestion = ""
        doc_issues = []
        score = _apply_accuracy_constraints(
            score,
            retrieved_docs=retrieved_docs,
            answer=state.get("answer") or "",
            context=context,
        )

    if not retrieved_docs and not reason:
        reason = "未检索到相关文档，无法基于知识库验证答案"

    # 未达标时保证 suggestion 可执行；达标时不必改写 suggestion
    if score < pass_threshold:
        suggestion = _ensure_actionable_suggestion(
            suggestion, retrieved_docs, state.get("answer") or "", context
        )

    should_continue = (
        score < pass_threshold and
        state["iteration"] < state["max_iterations"]
    )

    new_iteration = state["iteration"] + 1
    passed = score >= pass_threshold

    # 本轮迭代记录
    round_record: Dict[str, Any] = {
        "round": new_iteration,
        "question": current_query,
        "original_question": state.get("query", ""),
        "answer": state["answer"],
        "score": round(score, 2),
        "passed": passed,
    }
    if dims is not None:
        round_record["dimensions"] = {
            "relevance": round(dims["relevance"], 3),
            "groundedness": round(dims["groundedness"], 3),
            "completeness": round(dims["completeness"], 3),
        }
    if not passed:
        round_record["reason"] = reason
        round_record["suggestion"] = suggestion
        round_record["document_issues"] = doc_issues

    # 累积文档问题到 state
    existing_issues = list(state.get("document_issues") or [])
    existing_issues.extend(doc_issues)

    history = list(state.get("iteration_history") or [])
    history.append(round_record)

    last_feedback = None
    if should_continue:
        last_feedback = {
            "reason": reason,
            "suggestion": suggestion,
        }

    return {
        "confidence_score": score,
        "iteration": new_iteration,
        "should_continue": should_continue,
        "iteration_history": history,
        "last_evaluation_feedback": last_feedback,
        "document_issues": existing_issues,
    }
