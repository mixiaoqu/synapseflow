from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.application.document_service import DocumentService
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
