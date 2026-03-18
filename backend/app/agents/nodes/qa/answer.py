"""生成答案节点"""
from typing import Dict, Any

from app.agents.states import IterativeQAState
from app.core.llm import get_llm_for_generation


async def answer_node(state: IterativeQAState) -> Dict[str, Any]:
    """
    生成答案节点：生成详细、准确的答案
    """
    llm = get_llm_for_generation()
    
    prompt = f"""
基于以下知识库内容回答用户问题。

知识库内容：
{state['context']}

用户问题：{state.get('optimized_query') or state['query']}

要求：
1. 答案必须基于知识库内容
2. 如果知识库中没有相关信息，明确说明
3. 答案要详细、准确、结构化

回答：
"""
    
    response = await llm.ainvoke(prompt)
    
    return {
        "answer": response.content,
        "messages": [{"role": "assistant", "content": response.content}]
    }
