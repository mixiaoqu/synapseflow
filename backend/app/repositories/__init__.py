"""Repository 层：封装数据访问逻辑"""
from .document_repository import DocumentRepository
from .collection_repository import CollectionRepository

__all__ = ["DocumentRepository", "CollectionRepository"]
