from types import SimpleNamespace

import pytest

from app.application.document_service import DocumentService


@pytest.mark.asyncio
async def test_get_document_chunks_returns_child_chunks(monkeypatch):
    service = DocumentService()

    class DummyDocumentRepository:
        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id

        async def get_by_id_for_user(self, doc_id: int):
            assert doc_id == 42
            return SimpleNamespace(id=42, knowledge_base_id=7)

        async def get_category_name(self, category_id):
            return None

    class DummyChunkRepository:
        def __init__(self, db):
            self.db = db

        async def get_child_chunks_for_document(self, document_id: int):
            assert document_id == 42
            return [
                SimpleNamespace(
                    id=101,
                    document_id=42,
                    chunk_kind="child",
                    parent_chunk_id=11,
                    chunk_index=0,
                    prev_chunk_id=None,
                    next_chunk_id=102,
                    section_path="第一章/概述",
                    block_types=["paragraph"],
                    start_offset=0,
                    end_offset=68,
                    content="第一段分块内容",
                    search_text="第一段分块内容",
                    created_at="2026-05-19T00:00:00Z",
                    updated_at="2026-05-19T00:00:00Z",
                ),
                SimpleNamespace(
                    id=102,
                    document_id=42,
                    chunk_kind="child",
                    parent_chunk_id=11,
                    chunk_index=1,
                    prev_chunk_id=101,
                    next_chunk_id=None,
                    section_path="第一章/概述",
                    block_types=["paragraph"],
                    start_offset=69,
                    end_offset=126,
                    content="第二段分块内容",
                    search_text="第二段分块内容",
                    created_at="2026-05-19T00:00:01Z",
                    updated_at="2026-05-19T00:00:01Z",
                ),
            ]

    monkeypatch.setattr("app.application.document_service.DocumentRepository", DummyDocumentRepository)
    monkeypatch.setattr("app.application.document_service.DocumentChunkRepository", DummyChunkRepository)

    result = await service.get_document_chunks(db=object(), user_id=9, doc_id=42)

    assert result.total == 2
    assert result.items[0].id == 101
    assert result.items[0].section_path == "第一章/概述"
    assert result.items[1].prev_chunk_id == 101
