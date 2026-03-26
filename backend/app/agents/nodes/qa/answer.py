"""生成答案节点"""
from typing import Dict, Any

from app.agents.states import IterativeQAState
from app.agents.nodes.kb_user_qa.generate_answer import should_skip_kb_llm
from app.core.llm import get_llm_for_generation


async def answer_node(state: IterativeQAState) -> Dict[str, Any]:
    """
    生成答案节点：生成详细、准确的答案
    知识库正文来自 state['context']，条数由检索节点的 final_top_k / llm_reference_top_k 决定。
    迭代时（iteration > 0）利用上一轮评估反馈，有针对性地改进
    """
    fixed = should_skip_kb_llm(state)
    if fixed:
        return {
            "answer": fixed,
            "messages": [{"role": "assistant", "content": fixed}],
        }

    llm = get_llm_for_generation()
    query = state.get("optimized_query") or state.get("query", "")
    iteration = state.get("iteration", 0)
    last_feedback = state.get("last_evaluation_feedback")

    base_prompt = f"""
基于以下知识库内容回答用户问题。

知识库内容：
{state['context']}

用户问题：{query}

要求：
1. 答案必须基于知识库内容
2. 如果知识库中没有相关信息，明确说明
3. 答案要详细、准确、结构化
"""

    if iteration > 0 and last_feedback:
        base_prompt += f"""

【上一轮反馈】上一轮答案未通过评估，请针对以下反馈改进：
- 未通过原因：{last_feedback.get('reason', '')}
- 修改建议：{last_feedback.get('suggestion', '')}

请避免重复上一轮的无效回答方式，有针对性地补充或修正，生成符合要求的答案。
"""

    prompt = base_prompt + "\n回答：\n"
    
    response = await llm.ainvoke(prompt)
    
    return {
        "answer": response.content,
        "messages": [{"role": "assistant", "content": response.content}]
    }
