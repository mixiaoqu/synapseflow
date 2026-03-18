"""文档修订相关Schema（用户建议驱动）"""
from pydantic import BaseModel, Field
from typing import Optional


class SuggestRevisionRequest(BaseModel):
    """用户建议驱动修订请求"""
    document: str = Field(..., description="待修订文档内容")
    suggestions: str = Field(..., description="用户修订建议（自然语言）")
    doc_id: Optional[int] = Field(default=None, description="若从文档库选择，则传文档ID")


class SuggestRevisionResponse(BaseModel):
    """用户建议驱动修订响应"""
    revised_document: str = Field(..., description="修订后的文档")
