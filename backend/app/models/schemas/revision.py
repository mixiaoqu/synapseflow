"""文档修订相关Schema"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any


class RevisionRequest(BaseModel):
    """文档修订请求"""
    document: str = Field(..., description="原始文档内容")
    max_iterations: int = Field(default=5, ge=1, le=10, description="最大迭代次数")


class RevisionResponse(BaseModel):
    """文档修订响应"""
    revised_document: str = Field(..., description="修订后的文档")
    revision_history: List[Dict[str, Any]] = Field(..., description="修订历史")
    confidence: float = Field(..., description="完整性置信度")
    iterations: int = Field(..., description="实际迭代次数")
