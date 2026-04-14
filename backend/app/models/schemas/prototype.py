"""原型生成相关Schema"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class PrototypeRequest(BaseModel):
    """原型生成请求"""
    requirements: str = Field(..., description="需求文档内容")


class PrototypeResponse(BaseModel):
    """原型生成响应"""
    preview_url: str = Field(..., description="预览链接")
    html: str = Field(..., description="生成的完整HTML代码")
    is_valid: bool = Field(..., description="是否验证通过")
    validation_errors: List[str] = Field(default_factory=list, description="验证错误列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
