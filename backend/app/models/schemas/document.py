"""文档相关 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    """文档入库用（内部使用）"""
    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="文档内容")
    document_type: Optional[str] = Field(None, description="文档类型 txt/md/pdf/docx")


class DocumentResponse(BaseModel):
    """文档详情响应（含 content）"""
    id: int
    title: str
    content: str
    document_type: Optional[str] = None
    size: int = 0
    version: int = 1
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListItem(BaseModel):
    """文档列表项（不包含 content）"""
    id: int
    title: str
    document_type: Optional[str] = None
    size: int = 0
    version: int = 1
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """分页列表响应"""
    items: list[DocumentListItem]
    total: int
    page: int
    page_size: int
