"""评估答案质量节点"""
import json
from typing import Dict, Any

from app.agents.states import IterativeQAState
from app.core.llm import get_llm_for_evaluation


async def evaluate_node(state: IterativeQAState) -> Dict[str, Any]:
    """
    评估节点：快速评估答案质量并打分
    使用：quick_evaluation - Deepseek快速评估（temperature=0.3）
    """
    llm = get_llm_for_evaluation()
    
    eval_prompt = f"""
评估以下答案的质量（0-1分）：

问题：{state['query']}
答案：{state['answer']}

评估维度：
1. 相关性：答案是否直接回答问题
2. 完整性：答案是否涵盖问题的所有方面
3. 准确性：答案是否基于提供的上下文

只返回一个0-1之间的分数（JSON格式）：
{{"score": 0.85}}
"""
    
    response = await llm.ainvoke(eval_prompt)
    
    try:
        result = json.loads(response.content)
        score = float(result.get("score", 0.5))
    except Exception:
        score = 0.7
    
    should_continue = (
        score < 0.75 and 
        state['iteration'] < state['max_iterations']
    )
    
    return {
        "confidence_score": score,
        "iteration": state['iteration'] + 1,
        "should_continue": should_continue
    }
