"""解析用户建议节点：将自然语言转为结构化任务"""
from typing import Dict, Any, List

from loguru import logger

from app.agents.states.revision_state import UserDrivenRevisionState
from app.utils import extract_json_from_llm_response
from app.core.llm import get_llm_for_analysis


async def parse_suggestions_node(state: UserDrivenRevisionState) -> Dict[str, Any]:
    """
    解析用户修改建议，将自然语言转为结构化任务。

    输入：user_suggestions（自然语言）、可选 current_doc 片段作上下文
    输出：parsed_tasks = [
        {
            "action": "add|modify|delete",
            "target": "位置/章节",
            "content_requirement": "具体内容要求"
        },
        ...
    ]
    """
    llm = get_llm_for_analysis()
    doc_preview = (state.get("current_doc", "") or "")[:1500]
    edit_request = (state.get("user_suggestions", "") or "").strip()

    if not edit_request:
        return {"parsed_tasks": []}

    prompt = f"""你是一个文档修订助手。用户提供了以下修改需求，请解析为结构化指令列表。

# 用户修改需求
{edit_request}

# 文档片段（供上下文参考，可选）
{doc_preview}

# 指令格式
将每一条需求解析为：
- action: "add"（补充内容）、"modify"（修改现有）、"delete"（删除）
- target: 目标位置，必须精确，例如：
  - 在末尾/结尾添加 → target 填「文档末尾」或「结尾」
  - 在开头添加 → target 填「开头」
  - 修改第 X 章 → target 填「第X章」
  - 全文修改 → target 填「全文」
  - 不要用模糊的「文档」「整篇」除非确实是全文修改
- content_requirement: 具体内容要求

返回 JSON：
{{
  "tasks": [
    {{"action": "add", "target": "第三章", "content_requirement": "补充 2-3 个案例分析"}},
    {{"action": "modify", "target": "第二段", "content_requirement": "改得更简洁"}}
  ]
}}
"""

    response = await llm.ainvoke(prompt)
    data = extract_json_from_llm_response(response.content or "")
    tasks: List[Dict[str, Any]] = data.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    logger.info("[修订 1/4] parse_suggestions 完成，共 {} 条任务", len(tasks))

    return {"parsed_tasks": tasks}
