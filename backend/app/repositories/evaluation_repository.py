"""Evaluation repository."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import case as sql_case
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Document,
    DocumentChunk,
    EvalCase,
    EvalCaseResult,
    EvalDataset,
    EvalRun,
    KnowledgeBase,
    User,
)
from app.repositories.access_scope import accessible_knowledge_base_condition
from app.utils.time import utc_now


class EvaluationRepository:
    """Persist evaluation datasets, cases, runs, and results."""

    def __init__(self, db: AsyncSession, user_id: int, user: User | None = None):
        self.db = db
        self.user_id = user_id
        self.user = user

    async def list_datasets(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        keyword: str | None = None,
    ) -> list[EvalDataset]:
        stmt = (
            select(EvalDataset)
            .join(KnowledgeBase, KnowledgeBase.id == EvalDataset.knowledge_base_id)
            .where(accessible_knowledge_base_condition(self.user_id, user=self.user))
            .order_by(EvalDataset.created_at.desc(), EvalDataset.id.desc())
            .offset(offset)
            .limit(limit)
        )
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(or_(EvalDataset.name.ilike(pattern), EvalDataset.description.ilike(pattern)))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_datasets(self, *, keyword: str | None = None) -> int:
        stmt = (
            select(func.count())
            .select_from(EvalDataset)
            .join(KnowledgeBase, KnowledgeBase.id == EvalDataset.knowledge_base_id)
            .where(accessible_knowledge_base_condition(self.user_id, user=self.user))
        )
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(or_(EvalDataset.name.ilike(pattern), EvalDataset.description.ilike(pattern)))
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def get_dataset(self, dataset_id: int) -> EvalDataset | None:
        result = await self.db.execute(
            select(EvalDataset)
            .join(KnowledgeBase, KnowledgeBase.id == EvalDataset.knowledge_base_id)
            .where(
                EvalDataset.id == dataset_id,
                accessible_knowledge_base_condition(self.user_id, user=self.user),
            )
        )
        return result.scalar_one_or_none()

    async def create_dataset(
        self,
        *,
        name: str,
        knowledge_base_id: int,
        description: str | None,
        version: str,
        status: str,
    ) -> EvalDataset:
        row = EvalDataset(
            name=name.strip(),
            description=(description or "").strip() or None,
            knowledge_base_id=knowledge_base_id,
            version=version.strip(),
            status=status,
            created_by=self.user_id,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def update_dataset(
        self,
        dataset: EvalDataset,
        *,
        name: str,
        knowledge_base_id: int,
        description: str | None,
        version: str,
        status: str,
    ) -> EvalDataset:
        dataset.name = name.strip()
        dataset.description = (description or "").strip() or None
        dataset.knowledge_base_id = knowledge_base_id
        dataset.version = version.strip()
        dataset.status = status
        await self.db.commit()
        await self.db.refresh(dataset)
        return dataset

    async def list_cases(self, dataset_id: int, *, enabled_only: bool = False) -> list[EvalCase]:
        stmt = (
            select(EvalCase)
            .where(EvalCase.dataset_id == dataset_id)
            .order_by(EvalCase.created_at.asc(), EvalCase.id.asc())
        )
        if enabled_only:
            stmt = stmt.where(EvalCase.enabled.is_(True))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_case(self, case_id: int) -> EvalCase | None:
        result = await self.db.execute(select(EvalCase).where(EvalCase.id == case_id))
        return result.scalar_one_or_none()

    async def list_cases_by_ids(self, dataset_id: int, case_ids: list[int]) -> list[EvalCase]:
        normalized_case_ids = [int(item) for item in case_ids if int(item) > 0]
        if not normalized_case_ids:
            return []
        result = await self.db.execute(
            select(EvalCase)
            .where(
                EvalCase.dataset_id == dataset_id,
                EvalCase.id.in_(normalized_case_ids),
            )
            .order_by(EvalCase.id.asc())
        )
        return list(result.scalars().all())

    async def create_case(
        self,
        *,
        dataset_id: int,
        question: str,
        expected_answer: str,
        expected_doc_ids: list[int],
        expected_snippets: list[str],
        expected_chunk_ids: list[int],
        enabled: bool,
    ) -> EvalCase:
        row = EvalCase(
            dataset_id=dataset_id,
            question=question.strip(),
            expected_answer=expected_answer.strip(),
            expected_doc_ids=list(expected_doc_ids),
            expected_snippets=list(expected_snippets),
            expected_chunk_ids=list(expected_chunk_ids),
            enabled=enabled,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def update_case(
        self,
        case: EvalCase,
        *,
        question: str,
        expected_answer: str,
        expected_doc_ids: list[int],
        expected_snippets: list[str],
        expected_chunk_ids: list[int],
        enabled: bool,
    ) -> EvalCase:
        case.question = question.strip()
        case.expected_answer = expected_answer.strip()
        case.expected_doc_ids = list(expected_doc_ids)
        case.expected_snippets = list(expected_snippets)
        case.expected_chunk_ids = list(expected_chunk_ids)
        case.enabled = enabled
        await self.db.commit()
        await self.db.refresh(case)
        return case

    async def create_cases(
        self,
        *,
        dataset_id: int,
        cases: list[dict[str, Any]],
    ) -> int:
        rows = [
            EvalCase(
                dataset_id=dataset_id,
                question=str(item["question"]).strip(),
                expected_answer=str(item["expected_answer"]).strip(),
                expected_doc_ids=[],
                expected_snippets=list(item.get("expected_snippets") or []),
                expected_chunk_ids=[],
                enabled=True,
            )
            for item in cases
        ]
        self.db.add_all(rows)
        await self.db.commit()
        return len(rows)

    async def delete_case(self, case: EvalCase) -> None:
        await self.db.delete(case)
        await self.db.commit()

    async def delete_cases(self, cases: list[EvalCase]) -> int:
        for case in cases:
            await self.db.delete(case)
        await self.db.commit()
        return len(cases)

    async def create_run(
        self,
        *,
        dataset_id: int,
        run_name: str | None,
        kb_snapshot: dict[str, Any],
        assistant_snapshot: dict[str, Any],
        case_snapshot: dict[str, Any],
        policy_snapshot: dict[str, Any],
        model_config: dict[str, Any],
        total_cases: int,
    ) -> EvalRun:
        row = EvalRun(
            dataset_id=dataset_id,
            run_name=(run_name or "").strip() or None,
            status="pending",
            kb_snapshot=dict(kb_snapshot),
            assistant_snapshot=dict(assistant_snapshot),
            case_snapshot=dict(case_snapshot),
            policy_snapshot=dict(policy_snapshot),
            model_config=dict(model_config),
            total_cases=total_cases,
            created_by=self.user_id,
        )
        self.db.add(row)
        await self.db.flush()
        case_items = list(dict(case_snapshot or {}).get("items") or [])
        self.db.add_all(
            [
                EvalCaseResult(
                    run_id=int(row.id),
                    case_key=str(case["case_id"]),
                    case_id=int(case["case_id"]),
                    case_snapshot=dict(case),
                    status="pending",
                )
                for case in case_items
            ]
        )
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def ensure_case_execution_records(self, run: EvalRun) -> None:
        """为历史评测运行补齐按题执行所需的结果记录。"""
        case_items = list(dict(run.case_snapshot or {}).get("items") or [])
        if not case_items:
            return

        results = await self.list_case_results(int(run.id))
        assigned_keys = {str(result.case_key) for result in results if result.case_key}
        results_by_case_id: dict[int, list[EvalCaseResult]] = {}
        for result in results:
            if result.case_id is not None:
                results_by_case_id.setdefault(int(result.case_id), []).append(result)

        has_changes = False
        for case in case_items:
            case_key = str(case["case_id"])
            case_id = int(case["case_id"])
            if case_key in assigned_keys:
                continue

            legacy_results = results_by_case_id.get(case_id, [])
            if legacy_results:
                legacy_results[0].case_key = case_key
            else:
                self.db.add(
                    EvalCaseResult(
                        run_id=int(run.id),
                        case_key=case_key,
                        case_id=case_id,
                        case_snapshot=dict(case),
                        status="pending",
                    )
                )
            assigned_keys.add(case_key)
            has_changes = True

        if has_changes:
            await self.db.commit()

    async def claim_pending_run(self, run_id: int) -> EvalRun | None:
        now = utc_now()
        stmt = (
            update(EvalRun)
            .where(EvalRun.id == run_id, EvalRun.status == "pending")
            .values(status="running", started_at=now, heartbeat_at=now, error_message=None)
            .returning(EvalRun.id)
        )
        if (await self.db.execute(stmt)).scalar_one_or_none() is None:
            await self.db.rollback()
            return None
        await self.db.commit()
        return await self.get_run(run_id)

    async def touch_run(self, run: EvalRun) -> None:
        run.heartbeat_at = utc_now()
        await self.db.commit()

    async def is_run_claim_current(self, run_id: int, started_at) -> bool:
        result = await self.db.execute(
            select(EvalRun.status, EvalRun.started_at).where(EvalRun.id == run_id)
        )
        row = result.one_or_none()
        return bool(row and row.status == "running" and row.started_at == started_at)

    async def is_run_canceled(self, run_id: int) -> bool:
        result = await self.db.execute(select(EvalRun.status).where(EvalRun.id == run_id))
        return result.scalar_one_or_none() == "canceled"

    async def cancel_run(self, run: EvalRun) -> EvalRun | None:
        if run.status not in {"pending", "running"}:
            return None
        run.status = "canceled"
        run.finished_at = utc_now()
        run.heartbeat_at = run.finished_at
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def prepare_run_for_resume(
        self,
        run: EvalRun,
        *,
        passed_cases: int,
        failed_cases: int,
        average_score: int,
    ) -> EvalRun:
        run.status = "pending"
        run.passed_cases = passed_cases
        run.failed_cases = failed_cases
        run.average_score = average_score
        run.started_at = None
        run.finished_at = None
        run.heartbeat_at = None
        run.error_message = None
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def list_pending_case_keys(self, run_id: int) -> list[str]:
        result = await self.db.execute(
            select(EvalCaseResult.case_key)
            .where(EvalCaseResult.run_id == run_id, EvalCaseResult.status == "pending")
            .order_by(EvalCaseResult.id.asc())
        )
        return [str(case_key) for case_key in result.scalars().all() if case_key]

    async def claim_pending_case_result(
        self,
        *,
        run_id: int,
        case_key: str,
    ) -> EvalCaseResult | None:
        stmt = (
            update(EvalCaseResult)
            .where(
                EvalCaseResult.run_id == run_id,
                EvalCaseResult.case_key == case_key,
                EvalCaseResult.status == "pending",
            )
            .values(status="running", error_message=None)
            .returning(EvalCaseResult.id)
        )
        result_id = (await self.db.execute(stmt)).scalar_one_or_none()
        if result_id is None:
            await self.db.rollback()
            return None
        await self.db.commit()
        return await self.get_case_result(run_id=run_id, result_id=int(result_id))

    async def complete_case_result(
        self,
        result: EvalCaseResult,
        *,
        status: str,
        score: int,
        actual_answer: str,
        retrieved_doc_ids: list[int],
        retrieved_chunk_ids: list[int],
        judge_result: dict[str, Any],
        latency_ms: int | None,
        error_message: str | None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        estimated_cost: Any | None = None,
        token_usage: dict[str, Any] | None = None,
    ) -> EvalCaseResult:
        result.status = status
        result.score = score
        result.actual_answer = actual_answer
        result.retrieved_doc_ids = list(retrieved_doc_ids)
        result.retrieved_chunk_ids = list(retrieved_chunk_ids)
        result.judge_result = dict(judge_result)
        result.latency_ms = latency_ms
        result.error_message = error_message
        result.input_tokens = input_tokens
        result.output_tokens = output_tokens
        result.total_tokens = total_tokens
        result.estimated_cost = estimated_cost
        result.token_usage = token_usage
        await self.db.commit()
        await self.db.refresh(result)
        return result

    async def reset_retryable_case_results(self, run_id: int) -> None:
        await self.db.execute(
            update(EvalCaseResult)
            .where(
                EvalCaseResult.run_id == run_id,
                EvalCaseResult.status.in_(("failed", "running")),
            )
            .values(
                status="pending",
                score=0,
                actual_answer="",
                retrieved_doc_ids=[],
                retrieved_chunk_ids=[],
                judge_result={},
                latency_ms=None,
                error_message=None,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                estimated_cost=None,
                token_usage=None,
            )
        )
        await self.db.commit()

    async def sync_run_statistics(self, run_id: int) -> None:
        statistics = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(sql_case((EvalCaseResult.status == "passed", 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(sql_case((EvalCaseResult.status == "failed", 1), else_=0)),
                    0,
                ),
                func.avg(
                    sql_case(
                        (EvalCaseResult.status.in_(("passed", "failed")), EvalCaseResult.score),
                        else_=None,
                    )
                ),
            ).where(EvalCaseResult.run_id == run_id)
        )
        passed_cases, failed_cases, average_score = statistics.one()
        case_results = await self.list_case_results(run_id)
        usage_results = [item for item in case_results if item.total_tokens is not None]
        usage_models: dict[str, dict[str, Any]] = {}
        for item in usage_results:
            payload = item.token_usage if isinstance(item.token_usage, dict) else {}
            for model_key, model_usage in dict(payload.get("models") or {}).items():
                if not isinstance(model_usage, dict):
                    continue
                target = usage_models.setdefault(
                    str(model_key),
                    {
                        "model_key": str(model_usage.get("model_key") or model_key),
                        "provider": model_usage.get("provider"),
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "estimated_cost": Decimal("0"),
                        "input_price": model_usage.get("input_price", 0),
                        "output_price": model_usage.get("output_price", 0),
                    },
                )
                target["input_tokens"] += int(model_usage.get("input_tokens") or 0)
                target["output_tokens"] += int(model_usage.get("output_tokens") or 0)
                target["total_tokens"] += int(model_usage.get("total_tokens") or 0)
                target["estimated_cost"] += Decimal(str(model_usage.get("estimated_cost") or 0))
        token_usage = None
        if usage_results:
            token_usage = {
                "schema_version": 1,
                "currency": "CNY",
                "models": {
                    key: {
                        **value,
                        "estimated_cost": str(value["estimated_cost"]),
                    }
                    for key, value in usage_models.items()
                },
            }
        input_tokens = (
            sum(int(item.input_tokens or 0) for item in usage_results)
            if usage_results
            else None
        )
        output_tokens = (
            sum(int(item.output_tokens or 0) for item in usage_results)
            if usage_results
            else None
        )
        total_tokens = (
            sum(int(item.total_tokens or 0) for item in usage_results)
            if usage_results
            else None
        )
        estimated_cost = (
            sum((item.estimated_cost for item in usage_results), Decimal("0"))
            if usage_results
            else None
        )
        await self.db.execute(
            update(EvalRun)
            .where(EvalRun.id == run_id, EvalRun.status == "running")
            .values(
                passed_cases=int(passed_cases or 0),
                failed_cases=int(failed_cases or 0),
                average_score=int(round(float(average_score or 0))),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                token_usage=token_usage,
            )
        )
        await self.db.commit()

    async def finish_run_if_all_case_results_completed(self, run_id: int) -> EvalRun | None:
        run = await self.get_run(run_id)
        if run is None or run.status != "running":
            return run
        results = await self.list_case_results(run_id)
        if len(results) != int(run.total_cases) or any(
            result.status in {"pending", "running"} for result in results
        ):
            return run
        passed_cases = sum(1 for result in results if result.status == "passed")
        failed_cases = sum(1 for result in results if result.status == "failed")
        average_score = int(round(sum(int(result.score) for result in results) / len(results))) if results else 0
        return await self.finish_run(
            run,
            status="completed",
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            average_score=average_score,
        )

    async def finish_run(
        self,
        run: EvalRun,
        *,
        status: str,
        passed_cases: int,
        failed_cases: int,
        average_score: int,
    ) -> EvalRun:
        run.status = status
        run.passed_cases = passed_cases
        run.failed_cases = failed_cases
        run.average_score = average_score
        run.finished_at = utc_now()
        run.heartbeat_at = run.finished_at
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def mark_run_failed(self, run: EvalRun) -> EvalRun:
        run.status = "failed"
        run.finished_at = utc_now()
        run.heartbeat_at = run.finished_at
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def list_runs_page(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        keyword: str | None = None,
        status: str | None = None,
        dataset_id: int | None = None,
    ) -> list[tuple[EvalRun, EvalDataset]]:
        conditions = [accessible_knowledge_base_condition(self.user_id, user=self.user)]
        if dataset_id is not None:
            conditions.append(EvalRun.dataset_id == dataset_id)
        if status and status.strip():
            conditions.append(EvalRun.status == status.strip())
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            conditions.append(
                or_(
                    EvalRun.run_name.ilike(pattern),
                    EvalDataset.name.ilike(pattern),
                )
            )

        stmt = (
            select(EvalRun, EvalDataset)
            .join(EvalDataset, EvalDataset.id == EvalRun.dataset_id)
            .join(KnowledgeBase, KnowledgeBase.id == EvalDataset.knowledge_base_id)
            .where(*conditions)
            .order_by(EvalRun.created_at.desc(), EvalRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).all())

    async def count_runs(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        dataset_id: int | None = None,
    ) -> int:
        conditions = [accessible_knowledge_base_condition(self.user_id, user=self.user)]
        if dataset_id is not None:
            conditions.append(EvalRun.dataset_id == dataset_id)
        if status and status.strip():
            conditions.append(EvalRun.status == status.strip())
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            conditions.append(
                or_(
                    EvalRun.run_name.ilike(pattern),
                    EvalDataset.name.ilike(pattern),
                )
            )

        stmt = (
            select(func.count())
            .select_from(EvalRun)
            .join(EvalDataset, EvalDataset.id == EvalRun.dataset_id)
            .join(KnowledgeBase, KnowledgeBase.id == EvalDataset.knowledge_base_id)
            .where(*conditions)
        )
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def get_run(self, run_id: int) -> EvalRun | None:
        result = await self.db.execute(select(EvalRun).where(EvalRun.id == run_id))
        return result.scalar_one_or_none()

    async def create_case_result(
        self,
        *,
        run_id: int,
        case_id: int | None,
        case_snapshot: dict[str, Any],
        status: str,
        score: int,
        actual_answer: str,
        retrieved_doc_ids: list[int],
        retrieved_chunk_ids: list[int],
        judge_result: dict[str, Any],
        latency_ms: int | None,
        error_message: str | None,
    ) -> EvalCaseResult:
        row = EvalCaseResult(
            run_id=run_id,
            case_id=case_id,
            case_snapshot=dict(case_snapshot),
            status=status,
            score=score,
            actual_answer=actual_answer,
            retrieved_doc_ids=list(retrieved_doc_ids),
            retrieved_chunk_ids=list(retrieved_chunk_ids),
            judge_result=dict(judge_result),
            latency_ms=latency_ms,
            error_message=error_message,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def list_case_results(self, run_id: int) -> list[EvalCaseResult]:
        result = await self.db.execute(
            select(EvalCaseResult)
            .where(EvalCaseResult.run_id == run_id)
            .order_by(EvalCaseResult.id.asc())
        )
        return list(result.scalars().all())

    async def count_case_results(
        self,
        *,
        run_id: int,
        status: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(EvalCaseResult).where(EvalCaseResult.run_id == run_id)
        if status:
            stmt = stmt.where(EvalCaseResult.status == status)
        return int((await self.db.execute(stmt)).scalar() or 0)

    async def list_case_results_page(
        self,
        *,
        run_id: int,
        offset: int,
        limit: int,
        status: str | None = None,
    ) -> list[EvalCaseResult]:
        stmt = (
            select(EvalCaseResult)
            .where(EvalCaseResult.run_id == run_id)
            .order_by(EvalCaseResult.id.asc())
            .offset(offset)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(EvalCaseResult.status == status)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_case_result(
        self,
        *,
        run_id: int,
        result_id: int,
    ) -> EvalCaseResult | None:
        result = await self.db.execute(
            select(EvalCaseResult).where(
                EvalCaseResult.run_id == run_id,
                EvalCaseResult.id == result_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_retrieved_chunk_details(
        self,
        *,
        chunk_ids: list[int],
    ) -> list[tuple[DocumentChunk, Document]]:
        normalized_chunk_ids = [int(item) for item in chunk_ids if int(item) > 0]
        if not normalized_chunk_ids:
            return []

        stmt = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.id.in_(normalized_chunk_ids))
            .order_by(Document.id.asc(), DocumentChunk.chunk_index.asc(), DocumentChunk.id.asc())
        )
        return list((await self.db.execute(stmt)).all())

    async def list_expected_chunk_details(
        self,
        *,
        knowledge_base_id: int,
        chunk_ids: list[int],
    ) -> list[tuple[DocumentChunk, Document]]:
        normalized_chunk_ids = [int(item) for item in chunk_ids if int(item) > 0]
        if not normalized_chunk_ids:
            return []

        stmt = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.knowledge_base_id == knowledge_base_id,
                DocumentChunk.id.in_(normalized_chunk_ids),
            )
            .order_by(Document.id.asc(), DocumentChunk.chunk_index.asc(), DocumentChunk.id.asc())
        )
        return list((await self.db.execute(stmt)).all())

    async def search_chunks(
        self,
        *,
        knowledge_base_id: int,
        query: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[DocumentChunk, Document, float]], int]:
        conditions = [
            Document.knowledge_base_id == knowledge_base_id,
            Document.is_current.is_(True),
            DocumentChunk.chunk_kind == "child",
        ]
        normalized_query = (query or "").strip()
        if normalized_query:
            pattern = f"%{normalized_query}%"
            conditions.append(
                or_(
                    Document.title.ilike(pattern),
                    DocumentChunk.content.ilike(pattern),
                    DocumentChunk.search_text.ilike(pattern),
                )
            )

        total_stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(*conditions)
        )
        total = int((await self.db.execute(total_stmt)).scalar_one() or 0)

        normalized_limit = max(1, min(50, limit))
        normalized_offset = max(0, offset)
        stmt = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(*conditions)
            .order_by(Document.updated_at.desc(), Document.id.asc(), DocumentChunk.chunk_index.asc())
            .offset(normalized_offset)
            .limit(normalized_limit)
        )
        rows = (await self.db.execute(stmt)).all()
        normalized_query_lower = normalized_query.lower()
        results: list[tuple[DocumentChunk, Document, float]] = []
        for chunk, document in rows:
            content = (chunk.content or "").lower()
            title = (document.title or "").lower()
            score = (
                1.0
                if normalized_query_lower
                and (normalized_query_lower in content or normalized_query_lower in title)
                else 0.0
            )
            results.append((chunk, document, score))
        return results, total
