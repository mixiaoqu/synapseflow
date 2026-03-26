"""数据库 ORM 模型"""
from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector

from app.db.session import Base
from app.core.config import settings


class Collection(Base):
    """集合表 ORM 模型，用于分组管理文档"""

    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, default=1)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Document(Base):
    """文档表 ORM 模型，对应 documents 表"""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, default=1)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    document_type = Column(String(50), nullable=True)
    size = Column(Integer, nullable=False, default=0)  # 字节大小
    version = Column(Integer, nullable=False, default=1)
    parent_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    root_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)
    is_latest = Column(Boolean, nullable=False, default=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="SET NULL"), nullable=True, index=True)
    indexed_at = Column(DateTime, nullable=True)  # 向量索引成功时间
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Embedding(Base):
    """向量嵌入表 ORM 模型，对应 embeddings 表"""

    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_tsv = Column(TSVECTOR, nullable=True)
    embedding = Column(Vector(settings.VECTOR_DIMENSION), nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)
