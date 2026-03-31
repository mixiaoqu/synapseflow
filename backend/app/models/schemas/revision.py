"""文档修订相关 Schema。"""

from typing import Optional

from pydantic import BaseModel, Field


class SuggestRevisionRequest(BaseModel):
    """建议驱动的文档修订请求。"""

    document: str = Field(..., description="待修订的文档内容")
    suggestions: str = Field(..., description="用户输入的修订建议")
    doc_id: Optional[int] = Field(default=None, description="文档库中的文档 ID（可选）")


class SuggestRevisionResponse(BaseModel):
    """建议驱动的文档修订响应。"""

    revised_document: str = Field(..., description="修订后的文档内容")
