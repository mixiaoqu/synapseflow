"""文档相关 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    """文档入库用（内部使用）"""
    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="文档内容")
    document_type: Optional[str] = Field(None, description="文档类型 txt/md/pdf/docx")
    collection_id: Optional[int] = Field(None, description="所属集合 ID")


class DocumentResponse(BaseModel):
    """文档详情响应（含 content）"""
    id: int
    title: str
    content: str
    document_type: Optional[str] = None
    size: int = 0
    version: int = 1
    collection_id: Optional[int] = Field(None, description="所属集合 ID")
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
    indexed: bool = False
    collection_id: Optional[int] = None
    collection_name: Optional[str] = None
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


class DocumentContentUpdate(BaseModel):
    """文档内容更新（用于替换/修订保存）"""
    content: str = Field(..., description="更新后的文档内容")


class DocumentVersionItem(BaseModel):
    """版本历史项"""
    id: int
    title: str
    version: int
    is_latest: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentVersionsResponse(BaseModel):
    """版本历史响应"""
    items: list[DocumentVersionItem]
