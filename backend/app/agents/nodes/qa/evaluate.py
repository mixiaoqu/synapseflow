"""评估答案质量节点"""
import re
from typing import Any, Dict

from app.agents.states import IterativeQAState
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


async def evaluate_node(state: IterativeQAState) -> Dict[str, Any]:
    """
    评估节点：快速评估答案质量并打分，并记录迭代历史。
    未达标时输出面向「下一轮向量检索」的可执行 suggestion（结合检索片段与答案）；
    suggestion 过短时由规则按场景兜底。
    """
    llm = get_llm_for_analysis()
    ev_cfg = config_registry.get_rag_config()["evaluate"]
    weights = ev_cfg["weights"]
    context_max_chars = ev_cfg["context_max_chars"]
    pass_threshold = ev_cfg["pass_threshold"]
    wr, wg, wc = weights["relevance"], weights["groundedness"], weights["completeness"]

    current_query = state.get("optimized_query") or state.get("query", "")
    context = state.get("context") or ""
    if len(context) > context_max_chars:
        context = context[:context_max_chars] + "\n\n...(已截断)"

    eval_prompt = f"""
你是 RAG 答案质量评估员。请只依据【知识库内容】判断【答案】是否准确、有据、答全用户问题。
最终分数由三个 0~1 的分项经系统加权得到（权重：相关性{wr}、可溯源性{wg}、完整性{wc}），你必须逐项打分，禁止仅凭感觉给一个总分。

【知识库内容】（检索片段，用于核对答案依据）：
{context}

【用户问题】：{current_query}

【答案】：{state['answer']}

—— 分项定义（每项 0.0～1.0，与答案准确性直接挂钩）——
1) relevance（相关性）：答案是否**直接针对**用户问题意图。答非所问、只答边角 → 低分。
   **注意**：若用户问的是「是否有某功能/如何操作/政策依据」等，而【知识库内容】中**没有**可直接支撑的正文，答案仅能通过「未出现某入口」「未提及某服务」等**间接推断**来回应：这算**诚实、有据**，但**不等于**用户已获得所需信息——此时 relevance **不宜高于 0.65～0.70**（除非用户明确只问「库里有没有提到」这类元问题）。
2) groundedness（可溯源性）：答案中的**关键断言**是否可由【知识库内容】支持。从片段中**合理推断「未提供某类服务」**（如仅有侧面表述）可给中高分；明显编造、与片段矛盾 → 极低分；片段为空或无法核对 → ≤ 0.35。
3) completeness（完整性）：**用户为解决问题所需的信息**，是否已能从知识库中**直接获得**或通过片段**完整、无歧义**地覆盖。若实质情况是「库内无相关功能说明/无操作步骤/无政策条文」，仅靠**说明缺失、侧面推断、建议查别处**来收尾，则属于**需求未在库内满足**——此时 completeness **必须偏低（通常 ≤ 0.55）**，**禁止**因文笔严谨、推断合理就打 0.85 以上。

分项参考刻度：
- 0.85～1.0：该维度几乎无问题
- 0.70～0.84：小问题或可接受瑕疵
- 0.50～0.69：明显不足，影响可用性
- 0.35～0.49：严重问题
- 0.0～0.34：该维度基本失败

硬性对齐（打分前自检）：
- 若【知识库内容】为空、或仅为「未检索到」类占位：groundedness ≤ 0.35，且三项不可虚高。
- 若答案出现整段**拒答、拒不基于知识库作答**（而非「据库内事实说明无此信息」）：relevance 与 completeness 均 ≤ 0.45，groundedness ≤ 0.4。
- 若答案核心断言明显不在片段中且无法合理概括自片段：groundedness ≤ 0.35。
- **知识库未覆盖用户核心诉求**（如无下载入口说明、无注销流程、仅能推断「未提供」）：即使答案写得好，**completeness ≤ 0.55**；**relevance** 通常 **≤ 0.70**。此时加权总分往往**不应达到**通过线 {pass_threshold}，除非用户问题本身就是在问「能否从本文推断」。

通过线：加权总分 ≥ {pass_threshold} 且各维度通常应 ≥ 0.65；**若 completeness ≤ 0.55（库内未实质答全），一般视为未通过**。任一项 < 0.5 时总分很难达到通过线。

当不通过时，若存在文档层面的问题，请在 document_issues 中输出，类型为 knowledge_gap / document_incomplete / low_relevance 之一。

重要：每个 document_issue 必须包含 document_title。
- 若知识库内容中有【文档：xxx】标记，从中选取文档名；
- 若知识库完全为空或需新增文档，document_title 填 "需新增文档"。
- **禁止**在 document_issues 里编造一个听起来像真实文件、但并未出现在【知识库内容】中的具体《规范》全名当作「已有文档标题」；若只是建议运营以后补这类文档，请在 description/modification_suggestion 中写「建议补充××类制度/专项说明」，document_title 仍用「需新增文档」或**本次片段里真实出现过的**文档名。

【suggestion 字段（极其重要）】
面向下一轮检索：写关键词、同义扩展、检索方向即可。**禁止在 suggestion 中臆造任何文件名、手册名或《…》篇名**（除非该名称已出现在【知识库内容】的【文档：】标记或正文里）。

未达标时 suggestion 必填（结合片段与答案）。

返回 JSON（不要其他内容），**必须包含 relevance、groundedness、completeness**（0~1 小数，保留两位也可）：
{{
    "relevance": 0.75,
    "groundedness": 0.80,
    "completeness": 0.70,
    "reason": "不达标原因简述（达标可简短或省略）",
    "suggestion": "面向下一轮检索的具体指示（未达标时必填）",
    "document_issues": [
        {{
            "type": "knowledge_gap",
            "document_title": "文档A.pdf",
            "description": "该文档缺少关于 xxx 的说明",
            "modification_suggestion": "建议在文档中增加 xxx 相关章节"
        }}
    ]
}}

document_issues 仅在不通过且存在文档问题时填写，可为空数组 []。document_title 必填。

可选：同时给出 "score" 供对照；**系统以 relevance/groundedness/completeness 加权重算为准**。若无法分项（异常情况），可只给 score，系统会回退使用。
"""
    response = await llm.ainvoke(eval_prompt)
    raw = response.content or ""

    retrieved_docs = state.get("retrieved_docs") or []
    dims: Dict[str, float] | None = None

    try:
        result = extract_json_from_llm_response(raw)
        score, dims = _compute_weighted_score(result, weights)
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
