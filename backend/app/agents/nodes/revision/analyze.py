"""分析文档结构节点"""
import json
from typing import Dict, Any

from app.agents.states.revision_state import RecursiveRevisionState
from app.core.llm import get_llm_for_extraction


async def analyze_structure_node(state: RecursiveRevisionState) -> Dict[str, Any]:
    """
    分析文档结构节点：提取大纲和框架
    使用：structured_extraction - Kimi结构化提取（temperature=0.3）
    """
    llm = get_llm_for_extraction()

    prompt = f"""
分析以下文档的结构，提取：
1. 主要章节和小节
2. 核心论点和支撑论据
3. 预期应包含的内容框架

文档：
{state['current_doc']}

返回JSON格式的结构分析：
{{
    "sections": [
        {{"title": "章节标题", "content_summary": "内容摘要", "expected_topics": ["应包含的话题"]}}
    ],
    "main_arguments": ["核心论点"],
    "document_type": "文档类型"
}}
"""

    response = await llm.ainvoke(prompt)

    try:
        structure = json.loads(response.content)
    except Exception:
        structure = {
            "sections": [],
            "main_arguments": [],
            "document_type": "unknown"
        }

    return {"document_structure": structure}
