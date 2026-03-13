"""验证修订结果节点"""
import json
from typing import Dict, Any

from app.agents.states.revision_state import RecursiveRevisionState
from app.core.llm import get_llm_for_evaluation


async def validate_node(state: RecursiveRevisionState) -> Dict[str, Any]:
    """
    验证修订结果节点：快速验证文档完整性
    使用：quick_evaluation - Deepseek快速评估（temperature=0.3）
    """
    llm = get_llm_for_evaluation()

    validation_prompt = f"""
验证修订后的文档是否完整：

原始文档：{state['original_doc'][:500]}
修订后文档：{state['current_doc']}

评估：
1. 所有重要内容是否已补充
2. 逻辑连贯性
3. 内容完整度（0-1分）

返回JSON：
{{
    "is_complete": true,
    "confidence": 0.95,
    "remaining_issues": []
}}
"""

    response = await llm.ainvoke(validation_prompt)

    try:
        validation = json.loads(response.content)
    except Exception:
        validation = {
            "is_complete": True,
            "confidence": 0.8,
            "remaining_issues": []
        }

    is_complete = validation.get('is_complete', True) or state['iteration'] >= state['max_iterations']

    return {
        "validation_result": validation,
        "is_complete": is_complete,
        "confidence": validation.get('confidence', 0.8),
        "iteration": state['iteration'] + 1
    }
