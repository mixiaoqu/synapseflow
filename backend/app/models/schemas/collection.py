"""集合相关 Schema"""
from datetime import datetime
from pydantic import BaseModel, Field


class CollectionCreate(BaseModel):
    """创建集合"""
    name: str = Field(..., min_length=1, max_length=100, description="集合名称")


class CollectionUpdate(BaseModel):
    """更新集合"""
    name: str = Field(..., min_length=1, max_length=100, description="集合名称")


class CollectionResponse(BaseModel):
    """集合响应"""
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CollectionWithCount(CollectionResponse):
    """集合及文档数"""
    document_count: int = 0
