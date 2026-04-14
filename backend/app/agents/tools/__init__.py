"""
智能体工具目录

存放可供智能体使用的工具函数。
- 节点可直接调用（如 retrieve_node 使用 search_knowledge_base）
- 可绑定给 LLM 实现 ReAct/Agentic 模式（llm.bind_tools(tools)）
"""
from .qa_tools import (
    search_knowledge_base,
    rerank_documents,
)
from .general_tools import (
    get_current_time,
    calculate,
)

# QA 图常用工具集，用于 bind_tools
QA_TOOLS = [search_knowledge_base, rerank_documents]

# 通用工具集
GENERAL_TOOLS = [get_current_time, calculate]

# 全部工具
ALL_TOOLS = QA_TOOLS + GENERAL_TOOLS

__all__ = [
    "search_knowledge_base",
    "rerank_documents",
    "get_current_time",
    "calculate",
    "QA_TOOLS",
    "GENERAL_TOOLS",
    "ALL_TOOLS",
]
