"""检测遗漏内容节点"""
import json
from typing import Dict, Any

from app.agents.states.revision_state import RecursiveRevisionState
from app.core.llm import get_llm_for_detection


async def detect_missing_node(state: RecursiveRevisionState) -> Dict[str, Any]:
    """
    检测遗漏内容节点：发现逻辑上缺失的内容
    使用：content_detection - Deepseek内容检测（temperature=0.3）
    """
    llm = get_llm_for_detection()

    structure = state.get('document_structure', {})

    prompt = f"""
基于文档结构分析，识别逻辑上缺失的内容：

文档结构：{json.dumps(structure, ensure_ascii=False)}

当前文档：{state['current_doc']}

列出所有逻辑上应该存在但实际缺失的内容：
{{
    "missing_items": [
        {{
            "category": "缺失类别",
            "description": "缺失内容描述",
            "importance": "high | medium | low",
            "suggested_location": "应插入的位置"
        }}
    ]
}}
"""

    response = await llm.ainvoke(prompt)

    try:
        result = json.loads(response.content)
        missing_items = result.get("missing_items", [])
    except Exception:
        missing_items = []

    return {
        "missing_items": missing_items,
        "is_complete": len(missing_items) == 0
    }
