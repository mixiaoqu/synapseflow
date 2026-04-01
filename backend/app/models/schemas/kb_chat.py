"""Knowledge-base chat related schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KbChatRequest(BaseModel):
    """Knowledge-base chat request."""

    query: str = Field(..., description="用户问题")
    knowledge_base_id: Optional[int] = Field(None, description="限定检索知识库 ID")
    session_id: Optional[str] = Field(None, description="会话 ID（可选）")


class KbChatResponse(BaseModel):
    """Knowledge-base chat response."""

    answer: str = Field(..., description="回答内容")
    retrieved_docs: List[Dict[str, Any]] = Field(default_factory=list, description="检索到的文档片段")
    session_id: Optional[str] = None
