import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.application.document_service import DocumentService
from app.models.schemas.document import DocumentCreate
from app.services.document_index_state import INDEX_STATUS_INDEXED


def test_document_service_normalizes_source_path():
    assert (
        DocumentService._normalize_source_path(r" 项目A\\支付\\FAQ.md ")
        == "项目A/支付/FAQ.md"
    )
    assert DocumentService._normalize_source_path("///") is None


def test_document_service_infers_category_from_top_level_folder():
    assert DocumentService._infer_category_name("支付/FAQ.md") == "支付"
    assert DocumentService._infer_category_name(r"订单\\规则\\退款.md") == "订单"
    assert DocumentService._infer_category_name("FAQ.md") is None


def test_document_service_allows_publish_from_pending_review():
    doc = SimpleNamespace(
        is_current=True,
        index_status=INDEX_STATUS_INDEXED,
        status="pending_review",
    )

    DocumentService._assert_can_publish(doc)


def test_document_service_rejects_publish_from_draft():
    doc = SimpleNamespace(
        is_current=True,
        index_status=INDEX_STATUS_INDEXED,
        status="draft",
    )

    with pytest.raises(HTTPException):
        DocumentService._assert_can_publish(doc)


def test_document_create_schema_does_not_require_knowledge_base_branch_id():
    payload = DocumentCreate(
        title="FAQ",
        content="content",
        knowledge_base_id=3,
    )

    assert payload.knowledge_base_id == 3


@pytest.mark.asyncio
async def test_document_service_resolves_location_without_branch(monkeypatch):
    service = DocumentService()

    class DummyCategoryRepository:
        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id

        async def get_by_id(self, category_id: int):
            return SimpleNamespace(id=category_id, knowledge_base_id=5, name="支付")

        async def get_or_create(self, knowledge_base_id: int, name: str):
            return SimpleNamespace(id=9, knowledge_base_id=knowledge_base_id, name=name)

    class DummyKnowledgeBaseRepository:
        def __init__(self, db, user_id):
            self.db = db
            self.user_id = user_id

        async def get_by_id(self, knowledge_base_id: int):
            return SimpleNamespace(id=knowledge_base_id, team_id=2, name="知识库A")

    monkeypatch.setattr(
        "app.application.document_service.DocumentCategoryRepository",
        DummyCategoryRepository,
    )
    monkeypatch.setattr(
        "app.application.document_service.KnowledgeBaseRepository",
        DummyKnowledgeBaseRepository,
    )

    result = await service._resolve_document_location(
        db=object(),
        user_id=1,
        knowledge_base_id=5,
        category_id=None,
        source_path="支付/FAQ.md",
    )

    assert result == (5, 9, "支付/FAQ.md")


def test_upload_documents_batch_does_not_swallow_unexpected_errors(monkeypatch):
    service = DocumentService()

    class DummyRepository:
        def __init__(self, db, user_id):
            self.user_id = user_id

    class DummyUploadFile:
        def __init__(self, filename: str, payload: bytes) -> None:
            self.filename = filename
            self._payload = payload

        async def read(self) -> bytes:
            return self._payload

    def fake_parse_single_file(file, content):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.application.document_service.DocumentRepository", DummyRepository)
    monkeypatch.setattr(service, "_parse_single_file", fake_parse_single_file)

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(
            service.upload_documents_batch(
                db=object(),
                user_id=1,
                files=[DummyUploadFile("doc.md", b"# title")],
                knowledge_base_id=None,
                category_id=None,
                source_paths=None,
            )
        )
