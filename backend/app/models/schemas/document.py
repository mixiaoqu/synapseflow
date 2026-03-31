"""文档相关 Schema。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    """通过文本内容创建文档的请求体。"""

    title: str = Field(..., description="文档标题")
    content: str = Field(..., description="文档内容")
    document_type: Optional[str] = Field(None, description="文档类型，如 txt/md/pdf/docx")
    collection_id: Optional[int] = Field(None, description="所属集合 ID")


class DocumentResponse(BaseModel):
    """文档详情响应，包含完整内容。"""

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
    """文档列表项，不包含完整内容。"""

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
    """分页文档列表响应。"""

    items: list[DocumentListItem]
    total: int
    page: int
    page_size: int


class DocumentContentUpdate(BaseModel):
    """文档内容更新请求。"""

    content: str = Field(..., description="更新后的文档内容")


class DocumentVersionItem(BaseModel):
    """文档版本记录。"""

    id: int
    title: str
    version: int
    is_latest: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentVersionsResponse(BaseModel):
    """文档版本列表响应。"""

    items: list[DocumentVersionItem]
