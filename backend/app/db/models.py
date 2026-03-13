"""数据库 ORM 模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from pgvector.sqlalchemy import Vector

from app.db.session import Base
from app.core.config import settings


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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Embedding(Base):
    """向量嵌入表 ORM 模型，对应 embeddings 表"""

    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(Vector(settings.VECTOR_DIMENSION), nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)
