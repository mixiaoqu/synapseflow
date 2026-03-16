"""解析用户修改需求节点：将自然语言转为结构化指令"""
import json
from typing import Dict, Any, List

from loguru import logger

from app.agents.states.revision_state import UserDrivenRevisionState
from app.core.llm import get_llm_for_extraction


def _extract_json(content: str) -> Dict[str, Any]:
    """从 LLM 回复中提取 JSON"""
    content = content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    try:
        return json.loads(content.strip())
    except Exception:
        return {}


async def parse_edit_request_node(state: UserDrivenRevisionState) -> Dict[str, Any]:
    """
    解析用户修改需求，将自然语言转为结构化指令。

    输入：user_suggestions（自然语言）
    输出：parsed_tasks = [
        {
            "action": "add|modify|delete",
            "target": "位置/章节",
            "content_requirement": "具体内容要求"
        }
    ]
    """
    llm = get_llm_for_extraction()
    doc_preview = state.get("current_doc", "") or ""
    edit_request = state.get("user_suggestions", "")

    if not edit_request.strip():
        return {"parsed_tasks": []}

    prompt = f"""你是一个文档修订助手。用户提供了以下修改需求，请解析为结构化指令列表。

# 用户修改需求
{edit_request}

# 文档片段（供上下文参考）
{doc_preview}

# 指令格式
将每一条需求解析为：
- action: "add"（补充内容）、"modify"（修改现有）、"delete"（删除）
- target: 目标位置（如「第三章」「第二段」「开头」）
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
    data = _extract_json(response.content or "")
    tasks: List[Dict[str, Any]] = data.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    # 打印解析后的结构化建议
    if tasks:
        logger.info("解析后的修改建议 (parsed_tasks):")
        for i, t in enumerate(tasks, 1):
            logger.info(
                "  [{}] action={} target={} → {}",
                i,
                t.get("action", "?"),
                t.get("target", ""),
                t.get("content_requirement", ""),
            )
    else:
        logger.info("解析后无结构化任务 (parsed_tasks=[])")

    return {"parsed_tasks": tasks}
