"""知识库单轮问答 Schema（独立于迭代 QA）"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class KbSimpleQARequest(BaseModel):
    query: str = Field(..., description="用户问题")
    collection_id: Optional[int] = Field(None, description="限定检索集合，空则检索全部")
    session_id: Optional[str] = Field(None, description="会话ID（可选）")


class KbSimpleQAResponse(BaseModel):
    answer: str = Field(..., description="答案")
    retrieved_docs: List[Dict[str, Any]] = Field(
        default_factory=list, description="检索到的文档块"
    )
    session_id: Optional[str] = None
