"""Evaluation module schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EvalDatasetStatus = Literal["draft", "active", "archived"]
EvalRunStatus = Literal["pending", "running", "completed", "failed", "canceled"]
EvalCaseResultStatus = Literal["pending", "running", "passed", "failed"]


class EvalKnowledgeBaseCreate(BaseModel):
    """Create an evaluation knowledge base."""

    name: str = Field(..., min_length=1, max_length=100)
    team_id: int = 1
    description: str | None = None


class EvalDatasetCreate(BaseModel):
    """Create evaluation dataset request."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    knowledge_base_id: int
    version: str = Field(default="v1", min_length=1, max_length=50)
    status: EvalDatasetStatus = "draft"


class EvalDatasetUpdate(BaseModel):
    """Update evaluation dataset request."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    knowledge_base_id: int
    version: str = Field(default="v1", min_length=1, max_length=50)
    status: EvalDatasetStatus = "draft"


class EvalDatasetResponse(BaseModel):
    """Evaluation dataset response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    knowledge_base_id: int
    version: str
    status: EvalDatasetStatus
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class EvalDatasetListResponse(BaseModel):
    items: list[EvalDatasetResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class EvalDatasetBulkRun(BaseModel):
    """Submit multiple evaluation datasets to run in background."""

    dataset_ids: list[int] = Field(default_factory=list)
    run_name: str | None = Field(default=None, max_length=100)


class EvalCaseCreate(BaseModel):
    """Create evaluation case request."""

    question: str = Field(..., min_length=1)
    expected_answer: str = Field(..., min_length=1)
    expected_doc_ids: list[int] = Field(default_factory=list)
    expected_snippets: list[str] = Field(default_factory=list)
    expected_chunk_ids: list[int] = Field(default_factory=list)
    enabled: bool = True


class EvalCaseUpdate(EvalCaseCreate):
    """Update evaluation case request."""


class EvalCaseBulkDelete(BaseModel):
    """Delete multiple evaluation cases in one dataset."""

    case_ids: list[int] = Field(default_factory=list)


class EvalCaseImportItem(BaseModel):
    """One normalized standard Q&A case parsed from a CSV file."""

    row_number: int = Field(..., ge=2)
    question: str = Field(..., min_length=1, max_length=1000)
    expected_answer: str = Field(..., min_length=1, max_length=4000)
    expected_evidence: str | None = Field(default=None, max_length=4000)


class EvalCaseImportError(BaseModel):
    """One CSV row validation error shown before import confirmation."""

    row_number: int = Field(..., ge=1)
    field: str | None = None
    message: str


class EvalCaseImportPreviewResponse(BaseModel):
    """CSV validation result returned before creating evaluation cases."""

    total_rows: int = 0
    valid_cases: list[EvalCaseImportItem] = Field(default_factory=list)
    errors: list[EvalCaseImportError] = Field(default_factory=list)
    can_import: bool = False


class EvalCaseImportRequest(BaseModel):
    """Confirmed normalized CSV rows to import as evaluation cases."""

    cases: list[EvalCaseImportItem] = Field(default_factory=list, min_length=1, max_length=1000)


class EvalCaseImportResponse(BaseModel):
    """Result of a successful evaluation case import."""

    imported_count: int


class EvalRetrievedChunkEvidence(BaseModel):
    """Retrieved chunk evidence displayed in evaluation reports."""

    chunk_id: int
    chunk_index: int
    section_path: str | None = None
    content: str


class EvalRetrievedDocumentEvidence(BaseModel):
    """Retrieved document evidence displayed in evaluation reports."""

    document_id: int
    document_title: str
    chunks: list[EvalRetrievedChunkEvidence] = Field(default_factory=list)


class EvalCaseResponse(BaseModel):
    """Evaluation case response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    question: str
    expected_answer: str
    expected_doc_ids: list[int] = Field(default_factory=list)
    expected_snippets: list[str] = Field(default_factory=list)
    expected_chunk_ids: list[int] = Field(default_factory=list)
    expected_evidence: list[EvalRetrievedDocumentEvidence] = Field(default_factory=list)
    enabled: bool
    created_at: datetime
    updated_at: datetime


class EvalCaseListResponse(BaseModel):
    items: list[EvalCaseResponse] = Field(default_factory=list)
    total: int = 0


class EvalRunCreate(BaseModel):
    """Create evaluation run request."""

    run_name: str | None = Field(default=None, max_length=100)
    assistant_id: int = Field(..., gt=0)
    assistant_id: int = Field(..., gt=0)


class EvalRunResponse(BaseModel):
    """Evaluation run response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    dataset_id: int
    run_name: str | None = None
    status: EvalRunStatus
    run_config: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="model_config",
        serialization_alias="model_config",
    )
    kb_snapshot: dict[str, Any] = Field(default_factory=dict)
    assistant_snapshot: dict[str, Any] = Field(default_factory=dict)
    case_snapshot: dict[str, Any] = Field(default_factory=dict)
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    total_cases: int
    passed_cases: int
    failed_cases: int
    average_score: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    heartbeat_at: datetime | None = None
    error_message: str | None = None
    created_by: int | None = None
    created_at: datetime


class EvalRunListItemResponse(EvalRunResponse):
    """Evaluation run list item with readable dataset context."""

    dataset_name: str
    dataset_version: str
    knowledge_base_id: int


class EvalDatasetBulkRunResponse(BaseModel):
    items: list[EvalRunResponse] = Field(default_factory=list)
    total: int = 0


class EvalRunListResponse(BaseModel):
    items: list[EvalRunListItemResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10


class EvalCaseResultResponse(BaseModel):
    """Evaluation case result response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    case_id: int | None = None
    case_snapshot: dict[str, Any] = Field(default_factory=dict)
    status: EvalCaseResultStatus
    score: int
    actual_answer: str
    retrieved_doc_ids: list[int] = Field(default_factory=list)
    retrieved_chunk_ids: list[int] = Field(default_factory=list)
    judge_result: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int | None = None
    error_message: str | None = None
    created_at: datetime

    @field_validator("retrieved_doc_ids", "retrieved_chunk_ids", mode="before")
    @classmethod
    def normalize_retrieved_identifiers(cls, value: Any) -> list[int]:
        if not isinstance(value, (list, tuple, set)):
            return []
        result: list[int] = []
        seen: set[int] = set()
        for item in value:
            try:
                identifier = int(item)
            except (TypeError, ValueError):
                continue
            if identifier > 0 and identifier not in seen:
                seen.add(identifier)
                result.append(identifier)
        return result


class EvalCaseResultDetailResponse(EvalCaseResultResponse):
    """Evaluation case result response with readable retrieval evidence."""

    retrieved_evidence: list[EvalRetrievedDocumentEvidence] = Field(default_factory=list)


class EvalCaseRetrievedEvidenceResponse(BaseModel):
    """Lazy-loaded retrieval evidence for one evaluation case result."""

    items: list[EvalRetrievedDocumentEvidence] = Field(default_factory=list)


class EvalRunDetailResponse(EvalRunResponse):
    """Evaluation run detail with case results."""

    results: list[EvalCaseResultDetailResponse] = Field(default_factory=list)
    result_total: int = 0
    result_page: int = 1
    result_page_size: int = 10


class EvalChunkCandidate(BaseModel):
    """Candidate chunk selected while authoring evaluation cases."""

    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    content: str
    section_path: str | None = None
    score: float = 0


class EvalChunkSearchResponse(BaseModel):
    items: list[EvalChunkCandidate] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 20
    has_more: bool = False
