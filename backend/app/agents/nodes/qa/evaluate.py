"""评估答案质量节点"""
import json
from typing import Dict, Any

from app.agents.states import IterativeQAState
from app.core.llm import get_llm_for_analysis


async def evaluate_node(state: IterativeQAState) -> Dict[str, Any]:
    """
    评估节点：快速评估答案质量并打分，并记录迭代历史
    使用：quick_evaluation - Deepseek快速评估（temperature=0.3）
    """
    llm = get_llm_for_analysis()

    # 用于本轮展示的问题（优先用优化后的问题）
    current_query = state.get("optimized_query") or state.get("query", "")

    eval_prompt = f"""
评估以下答案的质量，返回 JSON 格式。

问题：{current_query}
答案：{state['answer']}

评估维度：
1. 相关性：答案是否直接回答问题
2. 完整性：答案是否涵盖问题的所有方面
3. 准确性：答案是否基于提供的上下文

返回 JSON 格式（不要其他内容）：
{{
    "score": 0.85,
    "reason": "不达标原因简述（若达标可省略）",
    "suggestion": "优化建议或下一轮建议提问方向（若达标可省略）"
}}
"""
    response = await llm.ainvoke(eval_prompt)

    try:
        result = json.loads(response.content)
        score = float(result.get("score", 0.5))
        reason = result.get("reason", "")
        suggestion = result.get("suggestion", "")
    except Exception:
        score = 0.7
        reason = ""
        suggestion = ""

    should_continue = (
        score < 0.75 and
        state["iteration"] < state["max_iterations"]
    )

    new_iteration = state["iteration"] + 1
    passed = score >= 0.75

    # 本轮迭代记录
    round_record = {
        "round": new_iteration,
        "question": current_query,
        "original_question": state.get("query", ""),
        "answer": state["answer"],
        "score": round(score, 2),
        "passed": passed,
    }
    if not passed:
        round_record["reason"] = reason
        round_record["suggestion"] = suggestion

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
    }
