"""提问优化节点：优化/拆解问题，适配知识库约束"""
import json
from typing import Dict, Any

from app.agents.states import IterativeQAState
from app.core.llm import get_llm_for_analysis


# 知识库约束：单次问题长度建议
MAX_QUESTION_BYTES = 1000


async def query_optimizer_node(state: IterativeQAState) -> Dict[str, Any]:
    """
    提问优化节点：
    - 第1轮：若问题超长则拆解为核心子问题；否则直接透传
    - 第2+轮：根据上一轮评估反馈，生成优化后的问题
    """
    query = state.get("query", "")
    iteration = state.get("iteration", 0)
    last_feedback = state.get("last_evaluation_feedback")

    if not query.strip():
        return {"optimized_query": query}

    # 第1轮：仅做长度检查，超长时提取核心问题
    if iteration == 0:
        if len(query.encode("utf-8")) <= MAX_QUESTION_BYTES:
            return {"optimized_query": query.strip()}
        # 超长：用 LLM 提取一个最核心的子问题
        llm = get_llm_for_analysis()
        prompt = f"""
用户的问题过长（超过{MAX_QUESTION_BYTES}字节），需要精简为适合知识库检索的核心问题。

原始问题：
{query}

要求：
1. 提取一个最核心、最直接的问题（控制在300字以内）
2. 保留关键术语，便于向量检索
3. 只返回优化后的问题文本，不要其他解释

优化后的问题：
"""
        response = await llm.ainvoke(prompt)
        optimized = (response.content or query).strip()
        return {"optimized_query": optimized or query}

    # 第2+轮：根据上一轮反馈优化提问
    if not last_feedback:
        return {"optimized_query": query}

    llm = get_llm_for_analysis()
    feedback_str = json.dumps(last_feedback, ensure_ascii=False)
    prompt = f"""
上一轮问答未达标，请根据评估反馈优化问题后重新提问。

原始问题：{query}
上一轮评估反馈：{feedback_str}

要求：
1. 根据反馈中的「不达标原因」和「优化建议」生成一个更精准的问题
2. 问题要更具体、更有针对性，便于知识库检索
3. 只返回优化后的问题文本，不要其他解释

优化后的问题：
"""
    response = await llm.ainvoke(prompt)
    optimized = (response.content or query).strip()
    return {"optimized_query": optimized or query}
