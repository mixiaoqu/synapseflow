from app.db.models import Document
from app.models.schemas.document import DocumentListItem, DocumentResponse
from app.services.graph_index_state import (
    ACTIVE_GRAPH_INDEX_STATUSES,
    GRAPH_INDEX_STATUS_FAILED,
    GRAPH_INDEX_STATUS_INDEXED,
    GRAPH_INDEX_STATUS_PROCESSING,
    GRAPH_INDEX_STATUS_QUEUED,
    is_graph_indexed_status,
)


def test_graph_index_state_constants_are_defined():
    assert GRAPH_INDEX_STATUS_QUEUED == "queued"
    assert GRAPH_INDEX_STATUS_PROCESSING == "processing"
    assert GRAPH_INDEX_STATUS_INDEXED == "indexed"
    assert GRAPH_INDEX_STATUS_FAILED == "failed"
    assert ACTIVE_GRAPH_INDEX_STATUSES == ("queued", "processing")
    assert is_graph_indexed_status("indexed") is True
    assert is_graph_indexed_status("failed") is False


def test_document_schemas_expose_graph_index_fields():
    response = DocumentResponse.model_construct(
        id=1,
        title="Doc",
        content="content",
        created_at=None,
        updated_at=None,
    )
    item = DocumentListItem.model_construct(
        id=1,
        title="Doc",
        created_at=None,
        updated_at=None,
    )

    assert response.graph_index_status == "queued"
    assert response.graph_index_error is None
    assert response.graph_indexed_at is None
    assert item.graph_index_status == "queued"
    assert item.graph_index_error is None
    assert item.graph_indexed_at is None


def test_document_model_has_graph_index_columns():
    columns = Document.__table__.columns

    assert "graph_index_status" in columns
    assert "graph_index_error" in columns
    assert "graph_indexed_at" in columns
