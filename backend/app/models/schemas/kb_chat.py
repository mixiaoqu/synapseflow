"""知识库问答相关 Schema。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KbChatRequest(BaseModel):
    """知识库问答请求。"""

    query: str = Field(..., description="用户问题")
    collection_id: Optional[int] = Field(
        None, description="限定检索集合，留空则检索全部知识库"
    )
    session_id: Optional[str] = Field(None, description="会话 ID（可选）")


class KbChatResponse(BaseModel):
    """知识库问答响应。"""

    answer: str = Field(..., description="回答内容")
    retrieved_docs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="检索到的文档片段",
    )
    session_id: Optional[str] = None
