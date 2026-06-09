"""Evaluation module endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_content_roles
from app.api.v1.endpoints.knowledge_bases import (
    _build_knowledge_base_list_item,
    _require_manage_knowledge_base,
)
from app.application.evaluation_service import EVALUATION_PURPOSE, evaluation_service
from app.db.models import Document, DocumentChunk, User
from app.db.session import get_db
from app.models.schemas.evaluation import (
    EvalCaseCreate,
    EvalCaseBulkDelete,
    EvalCaseListResponse,
    EvalCaseResponse,
    EvalCaseResultDetailResponse,
    EvalCaseResultResponse,
    EvalCaseUpdate,
    EvalChunkSearchResponse,
    EvalDatasetCreate,
    EvalDatasetBulkRun,
    EvalDatasetBulkRunResponse,
    EvalDatasetListResponse,
    EvalDatasetResponse,
    EvalDatasetUpdate,
    EvalKnowledgeBaseCreate,
    EvalRetrievedChunkEvidence,
    EvalRetrievedDocumentEvidence,
    EvalRunCreate,
    EvalRunDetailResponse,
    EvalRunListItemResponse,
    EvalRunListResponse,
    EvalRunResponse,
)
from app.models.schemas.knowledge_base import KnowledgeBaseListResponse, KnowledgeBaseResponse
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.workers.evaluation_tasks import execute_evaluation_run_actor

router = APIRouter()


def _unique_ints(values: list[int]) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for value in values:
        item = int(value)
        if item <= 0 or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _build_expected_evidence_payload(
    *,
    chunk_ids: list[int],
    chunk_detail_by_id: dict[int, tuple[DocumentChunk, Document]],
) -> list[EvalRetrievedDocumentEvidence]:
    grouped_documents: dict[int, EvalRetrievedDocumentEvidence] = {}
    for chunk_id in _unique_ints([int(value) for value in list(chunk_ids or [])]):
        detail = chunk_detail_by_id.get(chunk_id)
        if detail is None:
            continue
        chunk, document = detail
        document_id = int(document.id)
        if document_id not in grouped_documents:
            grouped_documents[document_id] = EvalRetrievedDocumentEvidence(
                document_id=document_id,
                document_title=document.title,
                chunks=[],
            )
        grouped_documents[document_id].chunks.append(
            EvalRetrievedChunkEvidence(
                chunk_id=int(chunk.id),
                chunk_index=int(chunk.chunk_index),
                section_path=chunk.section_path,
                content=chunk.content,
            )
        )
    return list(grouped_documents.values())


def _build_run_list_item_payload(run, dataset) -> EvalRunListItemResponse:
    payload = EvalRunResponse.model_validate(run).model_dump()
    return EvalRunListItemResponse(
        **payload,
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        knowledge_base_id=int(dataset.knowledge_base_id),
    )


@router.get("/knowledge-bases", response_model=KnowledgeBaseListResponse)
async def list_evaluation_knowledge_bases(
    team_id: int | None = Query(None, description="Filter by team id"),
    active_only: bool = Query(False, description="Only return active knowledge bases"),
    keyword: str | None = Query(None, description="Search by knowledge-base name or description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = KnowledgeBaseRepository(db, user_id=current_user.id, user=current_user)
    normalized_page = max(1, int(page))
    normalized_page_size = min(100, max(1, int(page_size)))
    total = await repo.count_knowledge_bases(
        team_id=team_id,
        purpose=EVALUATION_PURPOSE,
        active_only=active_only,
        keyword=keyword,
    )
    rows = await repo.list_with_count(
        team_id=team_id,
        purpose=EVALUATION_PURPOSE,
        active_only=active_only,
        keyword=keyword,
        offset=(normalized_page - 1) * normalized_page_size,
        limit=normalized_page_size,
    )
    return KnowledgeBaseListResponse(
        items=[_build_knowledge_base_list_item(row) for row in rows],
        total=total,
        page=normalized_page,
        page_size=normalized_page_size,
    )


@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse)
async def create_evaluation_knowledge_base(
    body: EvalKnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    await _require_manage_knowledge_base(
        db=db,
        current_user=current_user,
        team_id=body.team_id,
    )
    return await evaluation_service.create_evaluation_knowledge_base(
        db=db,
        current_user=current_user,
        name=body.name,
        team_id=body.team_id,
        description=body.description,
    )


@router.get("/datasets", response_model=EvalDatasetListResponse)
async def list_eval_datasets(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = EvaluationRepository(db, current_user.id, current_user)
    normalized_page = max(1, int(page))
    normalized_page_size = min(100, max(1, int(page_size)))
    total = await repo.count_datasets(keyword=keyword)
    rows = await repo.list_datasets(
        keyword=keyword,
        offset=(normalized_page - 1) * normalized_page_size,
        limit=normalized_page_size,
    )
    return EvalDatasetListResponse(
        items=[EvalDatasetResponse.model_validate(row) for row in rows],
        total=total,
        page=normalized_page,
        page_size=normalized_page_size,
    )


@router.post("/datasets", response_model=EvalDatasetResponse)
async def create_eval_dataset(
    body: EvalDatasetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    try:
        return await evaluation_service.create_dataset(
            db=db,
            current_user=current_user,
            body=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _enqueue_evaluation_run(run_id: int, user_id: int) -> None:
    execute_evaluation_run_actor.send(run_id, user_id)


@router.get("/datasets/{dataset_id}", response_model=EvalDatasetResponse)
async def get_eval_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    dataset = await EvaluationRepository(db, current_user.id, current_user).get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="评测集不存在或无权访问")
    return dataset


@router.put("/datasets/{dataset_id}", response_model=EvalDatasetResponse)
async def update_eval_dataset(
    dataset_id: int,
    body: EvalDatasetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    try:
        dataset = await evaluation_service.update_dataset(
            db=db,
            current_user=current_user,
            dataset_id=dataset_id,
            body=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if dataset is None:
        raise HTTPException(status_code=404, detail="评测集不存在或无权访问")
    return dataset


@router.get("/datasets/{dataset_id}/cases", response_model=EvalCaseListResponse)
async def list_eval_cases(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = EvaluationRepository(db, current_user.id, current_user)
    dataset = await repo.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="评测集不存在或无权访问")
    cases = await repo.list_cases(dataset_id)
    chunk_ids = _unique_ints(
        [
            int(chunk_id)
            for item in cases
            for chunk_id in list(item.expected_chunk_ids or [])
        ]
    )
    chunk_rows = await repo.list_expected_chunk_details(
        knowledge_base_id=int(dataset.knowledge_base_id),
        chunk_ids=chunk_ids,
    )
    chunk_detail_by_id = {int(chunk.id): (chunk, document) for chunk, document in chunk_rows}
    return EvalCaseListResponse(
        items=[
            EvalCaseResponse(
                **EvalCaseResponse.model_validate(item).model_dump(exclude={"expected_evidence"}),
                expected_evidence=_build_expected_evidence_payload(
                    chunk_ids=list(item.expected_chunk_ids or []),
                    chunk_detail_by_id=chunk_detail_by_id,
                ),
            )
            for item in cases
        ],
        total=len(cases),
    )


@router.post("/datasets/{dataset_id}/cases", response_model=EvalCaseResponse)
async def create_eval_case(
    dataset_id: int,
    body: EvalCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    row = await evaluation_service.create_case(
        db=db,
        current_user=current_user,
        dataset_id=dataset_id,
        body=body,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="评测集不存在或无权访问")
    return row


@router.put("/datasets/{dataset_id}/cases/{case_id}", response_model=EvalCaseResponse)
async def update_eval_case(
    dataset_id: int,
    case_id: int,
    body: EvalCaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    row = await evaluation_service.update_case(
        db=db,
        current_user=current_user,
        dataset_id=dataset_id,
        case_id=case_id,
        body=body,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="评测用例不存在或无权访问")
    return row


@router.delete("/datasets/{dataset_id}/cases/{case_id}")
async def delete_eval_case(
    dataset_id: int,
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    ok = await evaluation_service.delete_case(
        db=db,
        current_user=current_user,
        dataset_id=dataset_id,
        case_id=case_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="评测用例不存在或无权访问")
    return {"message": "删除成功"}


@router.post("/datasets/{dataset_id}/cases/bulk-delete")
async def bulk_delete_eval_cases(
    dataset_id: int,
    body: EvalCaseBulkDelete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    deleted_count = await evaluation_service.delete_cases(
        db=db,
        current_user=current_user,
        dataset_id=dataset_id,
        case_ids=body.case_ids,
    )
    if deleted_count is None:
        raise HTTPException(status_code=404, detail="评测集不存在或无权访问")
    return {"deleted_count": deleted_count}


@router.get("/datasets/{dataset_id}/chunks", response_model=EvalChunkSearchResponse)
async def search_eval_chunks(
    dataset_id: int,
    query: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    items = await evaluation_service.search_dataset_chunks(
        db=db,
        current_user=current_user,
        dataset_id=dataset_id,
        query=query,
        offset=offset,
        limit=limit,
    )
    if items is None:
        raise HTTPException(status_code=404, detail="评测集不存在或无权访问")
    return items


@router.get("/runs", response_model=EvalRunListResponse)
async def list_eval_run_tasks(
    keyword: str | None = Query(None),
    status: str | None = Query(None),
    dataset_id: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = EvaluationRepository(db, current_user.id, current_user)
    normalized_page = max(1, int(page))
    normalized_page_size = min(100, max(1, int(page_size)))
    normalized_status = status.strip() if status and status.strip() else None
    if normalized_status and normalized_status not in {"pending", "running", "completed", "failed"}:
        raise HTTPException(status_code=400, detail="评测任务状态无效")

    total = await repo.count_runs(
        keyword=keyword,
        status=normalized_status,
        dataset_id=dataset_id,
    )
    rows = await repo.list_runs_page(
        keyword=keyword,
        status=normalized_status,
        dataset_id=dataset_id,
        offset=(normalized_page - 1) * normalized_page_size,
        limit=normalized_page_size,
    )
    return EvalRunListResponse(
        items=[_build_run_list_item_payload(run, dataset) for run, dataset in rows],
        total=total,
        page=normalized_page,
        page_size=normalized_page_size,
    )


@router.post("/datasets/{dataset_id}/runs", response_model=EvalRunResponse)
async def execute_eval_dataset(
    dataset_id: int,
    body: EvalRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    run = await evaluation_service.submit_dataset_run(
        db=db,
        current_user=current_user,
        dataset_id=dataset_id,
        body=body,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="评测集不存在或无权访问")
    _enqueue_evaluation_run(int(run.id), int(current_user.id))
    return run


@router.post("/datasets/bulk-runs", response_model=EvalDatasetBulkRunResponse)
async def execute_eval_datasets(
    body: EvalDatasetBulkRun,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    try:
        runs = await evaluation_service.submit_dataset_runs(
            db=db,
            current_user=current_user,
            dataset_ids=body.dataset_ids,
            run_name=body.run_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    for run in runs:
        _enqueue_evaluation_run(int(run.id), int(current_user.id))
    return EvalDatasetBulkRunResponse(
        items=[EvalRunResponse.model_validate(run) for run in runs],
        total=len(runs),
    )


@router.get("/runs/{run_id}", response_model=EvalRunDetailResponse)
async def get_eval_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_content_roles),
):
    repo = EvaluationRepository(db, current_user.id, current_user)
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="评测运行不存在")
    dataset = await repo.get_dataset(int(run.dataset_id))
    if dataset is None:
        raise HTTPException(status_code=404, detail="评测运行不存在或无权访问")
    results = await repo.list_case_results(run_id)
    chunk_ids = _unique_ints(
        [
            int(chunk_id)
            for item in results
            for chunk_id in list(item.retrieved_chunk_ids or [])
        ]
    )
    chunk_rows = await repo.list_retrieved_chunk_details(chunk_ids=chunk_ids)
    chunk_detail_by_id = {int(chunk.id): (chunk, document) for chunk, document in chunk_rows}

    result_payloads: list[EvalCaseResultDetailResponse] = []
    for item in results:
        grouped_documents: dict[int, EvalRetrievedDocumentEvidence] = {}
        for chunk_id in _unique_ints([int(value) for value in list(item.retrieved_chunk_ids or [])]):
            detail = chunk_detail_by_id.get(chunk_id)
            if detail is None:
                continue
            chunk, document = detail
            document_id = int(document.id)
            if document_id not in grouped_documents:
                grouped_documents[document_id] = EvalRetrievedDocumentEvidence(
                    document_id=document_id,
                    document_title=document.title,
                    chunks=[],
                )
            grouped_documents[document_id].chunks.append(
                EvalRetrievedChunkEvidence(
                    chunk_id=int(chunk.id),
                    chunk_index=int(chunk.chunk_index),
                    section_path=chunk.section_path,
                    content=chunk.content,
                )
            )

        result_payload = EvalCaseResultResponse.model_validate(item).model_dump()
        result_payloads.append(
            EvalCaseResultDetailResponse(
                **result_payload,
                retrieved_evidence=list(grouped_documents.values()),
            )
        )

    payload = EvalRunResponse.model_validate(run).model_dump()
    return EvalRunDetailResponse(
        **payload,
        results=result_payloads,
    )
