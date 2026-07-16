"""Application service for KB chat evaluations."""

from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any

from app.application.agent_chat_service import get_agent_chat_service
from app.core.llm.factory import get_llm_for_analysis
from app.db.models import EvalCase, EvalDataset, EvalRun, KnowledgeBase, User
from app.models.schemas.evaluation import (
    EvalCaseCreate,
    EvalCaseUpdate,
    EvalChunkCandidate,
    EvalChunkSearchResponse,
    EvalDatasetCreate,
    EvalDatasetUpdate,
    EvalRunCreate,
)
from app.models.schemas.kb_chat import KbChatRequest
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository

EVALUATION_PURPOSE = "evaluation"
BUSINESS_PURPOSE = "business"
ANSWER_PASSING_SCORE = 80


class EvaluationService:
    """Orchestrate evaluation datasets, cases, runs, and scoring."""

    async def create_evaluation_knowledge_base(
        self,
        *,
        db,
        current_user: User,
        name: str,
        team_id: int,
        description: str | None,
    ) -> KnowledgeBase:
        return await KnowledgeBaseRepository(db, user_id=current_user.id, user=current_user).create(
            name,
            team_id=team_id,
            description=description,
            purpose=EVALUATION_PURPOSE,
        )

    async def create_dataset(
        self,
        *,
        db,
        current_user: User,
        body: EvalDatasetCreate,
    ) -> EvalDataset:
        await self._require_evaluation_knowledge_base(
            db=db,
            current_user=current_user,
            knowledge_base_id=body.knowledge_base_id,
        )
        return await EvaluationRepository(db, current_user.id, current_user).create_dataset(
            name=body.name,
            description=body.description,
            knowledge_base_id=body.knowledge_base_id,
            version=body.version,
            status=body.status,
        )

    async def update_dataset(
        self,
        *,
        db,
        current_user: User,
        dataset_id: int,
        body: EvalDatasetUpdate,
    ) -> EvalDataset | None:
        repo = EvaluationRepository(db, current_user.id, current_user)
        dataset = await repo.get_dataset(dataset_id)
        if dataset is None:
            return None
        await self._require_evaluation_knowledge_base(
            db=db,
            current_user=current_user,
            knowledge_base_id=body.knowledge_base_id,
        )
        return await repo.update_dataset(
            dataset,
            name=body.name,
            description=body.description,
            knowledge_base_id=body.knowledge_base_id,
            version=body.version,
            status=body.status,
        )

    async def create_case(
        self,
        *,
        db,
        current_user: User,
        dataset_id: int,
        body: EvalCaseCreate,
    ) -> EvalCase | None:
        repo = EvaluationRepository(db, current_user.id, current_user)
        dataset = await repo.get_dataset(dataset_id)
        if dataset is None:
            return None
        return await repo.create_case(
            dataset_id=dataset_id,
            question=body.question,
            expected_answer=body.expected_answer,
            expected_doc_ids=self._unique_ints(body.expected_doc_ids),
            expected_snippets=self._non_empty_strings(body.expected_snippets),
            expected_chunk_ids=self._unique_ints(body.expected_chunk_ids),
            enabled=body.enabled,
        )

    async def update_case(
        self,
        *,
        db,
        current_user: User,
        dataset_id: int,
        case_id: int,
        body: EvalCaseUpdate,
    ) -> EvalCase | None:
        repo = EvaluationRepository(db, current_user.id, current_user)
        dataset = await repo.get_dataset(dataset_id)
        case = await repo.get_case(case_id)
        if dataset is None or case is None or int(case.dataset_id) != dataset_id:
            return None
        return await repo.update_case(
            case,
            question=body.question,
            expected_answer=body.expected_answer,
            expected_doc_ids=self._unique_ints(body.expected_doc_ids),
            expected_snippets=self._non_empty_strings(body.expected_snippets),
            expected_chunk_ids=self._unique_ints(body.expected_chunk_ids),
            enabled=body.enabled,
        )

    async def delete_case(
        self,
        *,
        db,
        current_user: User,
        dataset_id: int,
        case_id: int,
    ) -> bool:
        repo = EvaluationRepository(db, current_user.id, current_user)
        dataset = await repo.get_dataset(dataset_id)
        case = await repo.get_case(case_id)
        if dataset is None or case is None or int(case.dataset_id) != dataset_id:
            return False
        await repo.delete_case(case)
        return True

    async def delete_cases(
        self,
        *,
        db,
        current_user: User,
        dataset_id: int,
        case_ids: list[int],
    ) -> int | None:
        repo = EvaluationRepository(db, current_user.id, current_user)
        dataset = await repo.get_dataset(dataset_id)
        if dataset is None:
            return None
        cases = await repo.list_cases_by_ids(dataset_id, self._unique_ints(case_ids))
        if not cases:
            return 0
        return await repo.delete_cases(cases)

    async def search_dataset_chunks(
        self,
        *,
        db,
        current_user: User,
        dataset_id: int,
        query: str | None,
        offset: int,
        limit: int,
    ) -> EvalChunkSearchResponse | None:
        repo = EvaluationRepository(db, current_user.id, current_user)
        dataset = await repo.get_dataset(dataset_id)
        if dataset is None:
            return None
        rows, total = await repo.search_chunks(
            knowledge_base_id=int(dataset.knowledge_base_id),
            query=query,
            offset=offset,
            limit=limit,
        )
        items = [
            EvalChunkCandidate(
                chunk_id=int(chunk.id),
                document_id=int(document.id),
                document_title=document.title,
                chunk_index=int(chunk.chunk_index),
                content=chunk.content,
                section_path=chunk.section_path,
                score=float(score),
            )
            for chunk, document, score in rows
        ]
        normalized_offset = max(0, offset)
        normalized_limit = max(1, min(50, limit))
        return EvalChunkSearchResponse(
            items=items,
            total=total,
            offset=normalized_offset,
            limit=normalized_limit,
            has_more=normalized_offset + len(items) < total,
        )

    async def submit_dataset_run(
        self,
        *,
        db,
        current_user: User,
        dataset_id: int,
        body: EvalRunCreate,
    ) -> EvalRun | None:
        repo = EvaluationRepository(db, current_user.id, current_user)
        dataset = await repo.get_dataset(dataset_id)
        if dataset is None:
            return None

        cases = await repo.list_cases(dataset_id, enabled_only=True)
        return await repo.create_run(
            dataset_id=dataset_id,
            run_name=body.run_name,
            kb_snapshot={
                "knowledge_base_id": int(dataset.knowledge_base_id),
                "dataset_version": dataset.version,
            },
            model_config={
                "chat_chain": "kb_chat.preview",
                "judge_model_role": "analysis",
                "answer_passing_score": ANSWER_PASSING_SCORE,
            },
            total_cases=len(cases),
        )

    async def submit_dataset_runs(
        self,
        *,
        db,
        current_user: User,
        dataset_ids: list[int],
        run_name: str | None,
    ) -> list[EvalRun]:
        runs: list[EvalRun] = []
        for dataset_id in self._unique_ints(dataset_ids):
            run = await self.submit_dataset_run(
                db=db,
                current_user=current_user,
                dataset_id=dataset_id,
                body=EvalRunCreate(run_name=run_name),
            )
            if run is None:
                raise ValueError("评测集不存在或无权访问")
            runs.append(run)
        return runs

    async def execute_dataset(
        self,
        *,
        db,
        current_user: User,
        dataset_id: int,
        body: EvalRunCreate,
    ) -> EvalRun | None:
        run = await self.submit_dataset_run(
            db=db,
            current_user=current_user,
            dataset_id=dataset_id,
            body=body,
        )
        if run is None:
            return None
        return await self.execute_run(
            db=db,
            current_user=current_user,
            run_id=int(run.id),
        )

    async def execute_run(
        self,
        *,
        db,
        current_user: User,
        run_id: int,
    ) -> EvalRun | None:
        repo = EvaluationRepository(db, current_user.id, current_user)
        run = await repo.get_run(run_id)
        if run is None:
            return None
        dataset = await repo.get_dataset(int(run.dataset_id))
        if dataset is None:
            return None
        cases = await repo.list_cases(int(run.dataset_id), enabled_only=True)

        passed_cases = 0
        failed_cases = 0
        scores: list[int] = []
        try:
            for case in cases:
                result_status, score = await self._execute_case(
                    db=db,
                    current_user=current_user,
                    repo=repo,
                    dataset=dataset,
                    run=run,
                    case=case,
                )
                scores.append(score)
                if result_status == "passed":
                    passed_cases += 1
                else:
                    failed_cases += 1

            average_score = int(round(sum(scores) / len(scores))) if scores else 0
            return await repo.finish_run(
                run,
                status="completed",
                passed_cases=passed_cases,
                failed_cases=failed_cases,
                average_score=average_score,
            )
        except Exception:
            return await repo.mark_run_failed(run)

    async def _execute_case(
        self,
        *,
        db,
        current_user: User,
        repo: EvaluationRepository,
        dataset: EvalDataset,
        run: EvalRun,
        case: EvalCase,
    ) -> tuple[str, int]:
        started_at = perf_counter()
        actual_answer = ""
        retrieved_docs: list[dict[str, Any]] = []
        judge_result: dict[str, Any] = {}
        error_message: str | None = None
        score = 0
        status = "failed"

        try:
            response = await get_agent_chat_service().preview(
                KbChatRequest(
                    query=case.question,
                    knowledge_base_id=int(dataset.knowledge_base_id),
                ),
                user_id=current_user.id,
            )
            actual_answer = response.answer_text or response.answer
            retrieved_docs = list(response.retrieved_docs or [])
            judge_result = await self._judge_answer(
                question=case.question,
                expected_answer=case.expected_answer,
                actual_answer=actual_answer,
                expected_snippets=list(case.expected_snippets or []),
                retrieved_docs=retrieved_docs,
            )
            score = self._normalize_score(judge_result.get("score"))
            retrieved_chunk_ids = self._extract_retrieved_chunk_ids(retrieved_docs)
            chunk_matched = self._is_chunk_matched(
                expected_chunk_ids=self._unique_ints(case.expected_chunk_ids or []),
                retrieved_chunk_ids=retrieved_chunk_ids,
            )
            judge_result["chunk_matched"] = chunk_matched
            judge_result["answer_passing_score"] = ANSWER_PASSING_SCORE
            status = "passed" if score >= ANSWER_PASSING_SCORE and chunk_matched else "failed"
        except Exception as exc:
            error_message = str(exc) or "评测用例执行失败"
            retrieved_chunk_ids = []

        latency_ms = int((perf_counter() - started_at) * 1000)
        await repo.create_case_result(
            run_id=int(run.id),
            case_id=int(case.id),
            status=status,
            score=score,
            actual_answer=actual_answer,
            retrieved_doc_ids=self._extract_retrieved_doc_ids(retrieved_docs),
            retrieved_chunk_ids=retrieved_chunk_ids,
            judge_result=judge_result,
            latency_ms=latency_ms,
            error_message=error_message,
        )
        return status, score

    async def _judge_answer(
        self,
        *,
        question: str,
        expected_answer: str,
        actual_answer: str,
        expected_snippets: list[str],
        retrieved_docs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt = self._build_judge_prompt(
            question=question,
            expected_answer=expected_answer,
            actual_answer=actual_answer,
            expected_snippets=expected_snippets,
            retrieved_docs=retrieved_docs,
        )
        response = await get_llm_for_analysis(temperature=0, streaming=False).ainvoke(prompt)
        content = str(getattr(response, "content", response) or "")
        return self._parse_judge_json(content)

    @staticmethod
    def _build_judge_prompt(
        *,
        question: str,
        expected_answer: str,
        actual_answer: str,
        expected_snippets: list[str],
        retrieved_docs: list[dict[str, Any]],
    ) -> str:
        retrieved_text = "\n\n".join(
            str(doc.get("content") or "")[:1200] for doc in retrieved_docs[:5]
        ).strip()
        return (
            "你是知识库问答评测裁判。请比较期望答案和实际回答的语义一致性，"
            "只输出 JSON，不要输出额外文本。\n"
            "评分范围 0-100：100 表示实际回答完整覆盖期望答案且无错误；"
            "80 表示主要含义正确但有轻微遗漏；低于 80 表示不应通过。\n\n"
            f"问题：\n{question}\n\n"
            f"期望答案：\n{expected_answer}\n\n"
            f"期望关键片段：\n{json.dumps(expected_snippets, ensure_ascii=False)}\n\n"
            f"实际回答：\n{actual_answer}\n\n"
            f"实际检索片段：\n{retrieved_text or '(none)'}\n\n"
            "输出格式："
            '{"score": 0, "passed": false, "reason": "", "matched_points": [], "missing_points": []}'
        )

    @staticmethod
    def _parse_judge_json(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text).strip()
        match = re.search(r"\{.*\}", text, re.S)
        payload = match.group(0) if match else text
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ValueError("LLM 裁判返回格式不是 JSON 对象")
        parsed["score"] = EvaluationService._normalize_score(parsed.get("score"))
        parsed["passed"] = bool(parsed.get("passed"))
        parsed["reason"] = str(parsed.get("reason") or "")
        parsed["matched_points"] = list(parsed.get("matched_points") or [])
        parsed["missing_points"] = list(parsed.get("missing_points") or [])
        return parsed

    async def _require_evaluation_knowledge_base(
        self,
        *,
        db,
        current_user: User,
        knowledge_base_id: int,
    ) -> KnowledgeBase:
        knowledge_base = await KnowledgeBaseRepository(
            db,
            user_id=current_user.id,
            user=current_user,
        ).get_by_id(knowledge_base_id)
        if knowledge_base is None:
            raise ValueError("知识库不存在或无权访问")
        if getattr(knowledge_base, "purpose", BUSINESS_PURPOSE) != EVALUATION_PURPOSE:
            raise ValueError("评测集只能绑定评测知识库")
        return knowledge_base

    @staticmethod
    def _extract_retrieved_doc_ids(retrieved_docs: list[dict[str, Any]]) -> list[int]:
        ids: list[int] = []
        for doc in retrieved_docs:
            metadata = dict(doc.get("metadata") or {})
            value = metadata.get("document_id") or doc.get("document_id")
            if value is not None:
                ids.append(int(value))
        return EvaluationService._unique_ints(ids)

    @staticmethod
    def _extract_retrieved_chunk_ids(retrieved_docs: list[dict[str, Any]]) -> list[int]:
        ids: list[int] = []
        for doc in retrieved_docs:
            metadata = dict(doc.get("metadata") or {})
            for key in ("document_chunk_id", "child_chunk_id"):
                value = metadata.get(key) or doc.get(key)
                if value is not None:
                    ids.append(int(value))
            for value in metadata.get("merged_child_chunk_ids") or []:
                ids.append(int(value))
        return EvaluationService._unique_ints(ids)

    @staticmethod
    def _is_chunk_matched(*, expected_chunk_ids: list[int], retrieved_chunk_ids: list[int]) -> bool:
        if not expected_chunk_ids:
            return True
        return bool(set(expected_chunk_ids).intersection(retrieved_chunk_ids))

    @staticmethod
    def _normalize_score(value: Any) -> int:
        try:
            score = int(round(float(value)))
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, score))

    @staticmethod
    def _unique_ints(values: list[Any]) -> list[int]:
        result: list[int] = []
        seen: set[int] = set()
        for value in values:
            try:
                item = int(value)
            except (TypeError, ValueError):
                continue
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    @staticmethod
    def _non_empty_strings(values: list[Any]) -> list[str]:
        result: list[str] = []
        for value in values:
            item = str(value or "").strip()
            if item:
                result.append(item)
        return result


evaluation_service = EvaluationService()
