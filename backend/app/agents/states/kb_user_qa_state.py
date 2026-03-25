"""面向最终用户的知识库单轮问答状态（与迭代 QA 状态分离）"""
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph.message import add_messages


class KbUserQAState(TypedDict, total=False):
    """用户知识库问答：检索 → 生成，无优化/评估字段。"""

    messages: Annotated[List, add_messages]
    query: str
    collection_id: Optional[int]
    retrieved_docs: List[Dict[str, Any]]
    context: str
    answer: str
