"""Application service for KB chat evaluations."""

from __future__ import annotations

import csv
from datetime import timedelta
import json
import re
from io import StringIO
from time import perf_counter
from typing import Any

from app.application.agent.input_builder import AgentRunRequest
from app.application.agent.run_service import get_agent_run_service
from app.core.llm.factory import get_llm_for_analysis
from app.db.models import EvalCase, EvalDataset, EvalRun, KnowledgeBase, User
from app.models.schemas.evaluation import (
    EvalCaseCreate,
    EvalCaseImportError,
    EvalCaseImportItem,
    EvalCaseImportPreviewResponse,
    EvalCaseUpdate,
    EvalChunkCandidate,
    EvalChunkSearchResponse,
    EvalDatasetCreate,
    EvalDatasetUpdate,
    EvalRunCreate,
)
from app.repositories.assistant_profile_repository import AssistantProfileRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.utils.time import utc_now

EVALUATION_PURPOSE = "evaluation"
BUSINESS_PURPOSE = "business"
ANSWER_PASSING_SCORE = 80
EVAL_CASE_IMPORT_MAX_ROWS = 1000
EVAL_CASE_IMPORT_HEADERS = ("question", "expected_answer", "expected_evidence")
EVALUATION_RUN_HEARTBEAT_TIMEOUT_SECONDS = 300


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

    async def preview_case_import(
        self,
        *,
        db,
        current_user: User,
        dataset_id: int,
        content: bytes,
    ) -> EvalCaseImportPreviewResponse | None:
        repo = EvaluationRepository(db, current_user.id, current_user)
        dataset = await repo.get_dataset(dataset_id)
        if dataset is None:
            return None
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("文件编码无效，请使用 CSV UTF-8 格式保存后再上传") from exc

        reader = csv.DictReader(StringIO(text))
        headers = {str(item or "").strip() for item in (reader.fieldnames or [])}
        missing_headers = [header for header in EVAL_CASE_IMPORT_HEADERS[:2] if header not in headers]
        if missing_headers:
            raise ValueError(f"缺少必填列：{', '.join(missing_headers)}")

        existing_questions = {
            self._normalize_import_question(case.question)
            for case in await repo.list_cases(dataset_id)
        }
        valid_cases: list[EvalCaseImportItem] = []
        errors: list[EvalCaseImportError] = []
        imported_questions: set[str] = set()
        total_rows = 0
        for row_number, row in enumerate(reader, start=2):
            normalized_row = {
                str(key or "").strip(): str(value or "").strip()
                for key, value in row.items()
            }
            if not any(normalized_row.values()):
                continue
            total_rows += 1
            if total_rows > EVAL_CASE_IMPORT_MAX_ROWS:
                raise ValueError(f"单次最多导入 {EVAL_CASE_IMPORT_MAX_ROWS} 条用例")

            question = normalized_row.get("question", "")
            expected_answer = normalized_row.get("expected_answer", "")
            expected_evidence = normalized_row.get("expected_evidence", "") or None
            row_errors: list[EvalCaseImportError] = []
            if not question:
                row_errors.append(EvalCaseImportError(row_number=row_number, field="question", message="问题不能为空"))
            elif len(question) > 1000:
                row_errors.append(EvalCaseImportError(row_number=row_number, field="question", message="问题不能超过 1000 个字符"))
            if not expected_answer:
                row_errors.append(EvalCaseImportError(row_number=row_number, field="expected_answer", message="期望答案不能为空"))
            elif len(expected_answer) > 4000:
                row_errors.append(EvalCaseImportError(row_number=row_number, field="expected_answer", message="期望答案不能超过 4000 个字符"))
            if expected_evidence and len(expected_evidence) > 4000:
                row_errors.append(EvalCaseImportError(row_number=row_number, field="expected_evidence", message="期望依据不能超过 4000 个字符"))

            normalized_question = self._normalize_import_question(question)
            if question and normalized_question in existing_questions:
                row_errors.append(EvalCaseImportError(row_number=row_number, field="question", message="该问题已存在于当前评测集"))
            elif question and normalized_question in imported_questions:
                row_errors.append(EvalCaseImportError(row_number=row_number, field="question", message="文件内存在重复问题"))
            if row_errors:
                errors.extend(row_errors)
                continue
            imported_questions.add(normalized_question)
            valid_cases.append(EvalCaseImportItem(
                row_number=row_number,
                question=question,
                expected_answer=expected_answer,
                expected_evidence=expected_evidence,
            ))

        if total_rows == 0:
            errors.append(EvalCaseImportError(row_number=1, message="CSV 中没有可导入的数据行"))
        return EvalCaseImportPreviewResponse(
            total_rows=total_rows,
            valid_cases=valid_cases,
            errors=errors,
            can_import=bool(valid_cases) and not errors,
        )

    async def import_cases(
        self,
        *,
        db,
        current_user: User,
        dataset_id: int,
        cases: list[EvalCaseImportItem],
    ) -> int | None:
        repo = EvaluationRepository(db, current_user.id, current_user)
        dataset = await repo.get_dataset(dataset_id)
        if dataset is None:
            return None
        if len(cases) > EVAL_CASE_IMPORT_MAX_ROWS:
            raise ValueError(f"单次最多导入 {EVAL_CASE_IMPORT_MAX_ROWS} 条用例")

        existing_questions = {
            self._normalize_import_question(case.question)
            for case in await repo.list_cases(dataset_id)
        }
        imported_questions: set[str] = set()
        normalized_cases: list[dict[str, Any]] = []
        for case in cases:
            question = case.question.strip()
            expected_answer = case.expected_answer.strip()
            evidence = (case.expected_evidence or "").strip()
            if not question:
                raise ValueError(f"第 {case.row_number} 行问题不能为空，请重新预检")
            if not expected_answer:
                raise ValueError(f"第 {case.row_number} 行期望答案不能为空，请重新预检")
            normalized_question = self._normalize_import_question(question)
            if normalized_question in existing_questions:
                raise ValueError(f"第 {case.row_number} 行问题已存在于当前评测集，请重新预检")
            if normalized_question in imported_questions:
                raise ValueError(f"第 {case.row_number} 行与文件内其他问题重复，请重新预检")
            imported_questions.add(normalized_question)
            normalized_cases.append({
                "question": question,
                "expected_answer": expected_answer,
                "expected_snippets": [evidence] if evidence else [],
            })
        return await repo.create_cases(dataset_id=dataset_id, cases=normalized_cases)

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

        knowledge_base = await self._require_evaluation_knowledge_base(
            db=db,
            current_user=current_user,
            knowledge_base_id=int(dataset.knowledge_base_id),
        )
        assistant_record = await AssistantProfileRepository(
            db, current_user.id, current_user
        ).get_by_id(body.assistant_id, active_only=True)
        if assistant_record is None:
            raise ValueError("Assistant 不存在、未启用或无权访问")
        assistant = assistant_record.assistant
        if int(assistant.team_id) != int(knowledge_base.team_id):
            raise ValueError("Assistant 与评测知识库必须属于同一团队")

        cases = await repo.list_cases(dataset_id, enabled_only=True)
        case_items = [self._build_case_snapshot(case) for case in cases]
        return await repo.create_run(
            dataset_id=dataset_id,
            run_name=body.run_name,
            kb_snapshot={
                "knowledge_base_id": int(dataset.knowledge_base_id),
                "knowledge_base_name": knowledge_base.name,
                "knowledge_base_purpose": knowledge_base.purpose,
                "team_id": int(knowledge_base.team_id),
                "dataset_id": int(dataset.id),
                "dataset_name": dataset.name,
                "dataset_version": dataset.version,
            },
            assistant_snapshot={
                "assistant_id": int(assistant.id),
                "name": assistant.name,
                "llm_model_key": assistant.llm_model_key,
                "persona_prompt": assistant.persona_prompt,
                "rule_template": assistant.rule_template,
            },
            case_snapshot={"items": case_items},
            policy_snapshot={
                "agent_workflow": "agent",
                "judge_model_role": "analysis",
                "answer_passing_score": ANSWER_PASSING_SCORE,
                "evidence_match_rule": "selected_chunk_only",
            },
            model_config={
                "agent_workflow": "agent",
                "judge_model_role": "analysis",
                "answer_passing_score": ANSWER_PASSING_SCORE,
            },
            total_cases=len(case_items),
        )

    async def submit_dataset_runs(
        self,
        *,
        db,
        current_user: User,
        dataset_ids: list[int],
        run_name: str | None,
        assistant_id: int,
    ) -> list[EvalRun]:
        runs: list[EvalRun] = []
        for dataset_id in self._unique_ints(dataset_ids):
            run = await self.submit_dataset_run(
                db=db,
                current_user=current_user,
                dataset_id=dataset_id,
                body=EvalRunCreate(run_name=run_name, assistant_id=assistant_id),
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
        run = await repo.claim_pending_run(run_id)
        if run is None:
            return await repo.get_run(run_id)
        existing_results = await repo.list_case_results(int(run.id))
        completed_case_ids = set(
            self._unique_ints(
                [
                    result.case_id
                    or dict(result.case_snapshot or {}).get("case_id")
                    for result in existing_results
                ]
            )
        )
        case_items = [
            case
            for case in list(dict(run.case_snapshot or {}).get("items") or [])
            if int(case.get("case_id") or 0) not in completed_case_ids
        ]
        passed_cases = sum(1 for result in existing_results if result.status == "passed")
        failed_cases = sum(1 for result in existing_results if result.status == "failed")
        scores = [int(result.score) for result in existing_results]
        try:
            for case in case_items:
                if not await repo.is_run_claim_current(int(run.id), run.started_at):
                    return await repo.get_run(int(run.id))
                result_status, score = await self._execute_case(
                    db=db,
                    current_user=current_user,
                    repo=repo,
                    run=run,
                    case=case,
                )
                scores.append(score)
                if result_status == "passed":
                    passed_cases += 1
                else:
                    failed_cases += 1
                await repo.touch_run(run)

            average_score = int(round(sum(scores) / len(scores))) if scores else 0
            return await repo.finish_run(
                run,
                status="completed",
                passed_cases=passed_cases,
                failed_cases=failed_cases,
                average_score=average_score,
            )
        except Exception as exc:
            run.error_message = str(exc) or "评测任务执行失败"
            return await repo.mark_run_failed(run)

    async def resume_run(
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
        if not self._is_run_resumable(run):
            raise ValueError("当前评测任务仍在正常运行，不能继续执行")

        results = await repo.list_case_results(run_id)
        passed_cases = sum(1 for result in results if result.status == "passed")
        failed_cases = sum(1 for result in results if result.status == "failed")
        scores = [int(result.score) for result in results]
        average_score = int(round(sum(scores) / len(scores))) if scores else 0
        return await repo.prepare_run_for_resume(
            run,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            average_score=average_score,
        )

    async def _execute_case(
        self,
        *,
        db,
        current_user: User,
        repo: EvaluationRepository,
        run: EvalRun,
        case: dict[str, Any],
    ) -> tuple[str, int]:
        started_at = perf_counter()
        actual_answer = ""
        retrieved_docs: list[dict[str, Any]] = []
        judge_result: dict[str, Any] = {}
        error_message: str | None = None
        score = 0
        status = "failed"

        try:
            assistant_snapshot = dict(run.assistant_snapshot or {})
            agent_result = await get_agent_run_service().execute_stateless(
                AgentRunRequest(
                    query=str(case["question"]),
                    team_id=int(dict(run.kb_snapshot or {}).get("team_id") or 0) or None,
                    knowledge_base_id=int(dict(run.kb_snapshot or {}).get("knowledge_base_id") or 0) or None,
                    assistant_id=assistant_snapshot.get("assistant_id"),
                    assistant_name=assistant_snapshot.get("name"),
                    assistant_llm_model_key=assistant_snapshot.get("llm_model_key"),
                    assistant_persona_prompt=assistant_snapshot.get("persona_prompt"),
                    assistant_rule_template=assistant_snapshot.get("rule_template"),
                    source_surface="evaluation",
                ),
                user_id=current_user.id,
            )
            actual_answer = str(agent_result.get("answer") or "")
            retrieved_docs = list(agent_result.get("retrieved_docs") or [])
            if agent_result.get("answer_status") == "blocked":
                judge_result = {"blocked": True, "content_risk_hits": agent_result.get("content_risk_hits", [])}
                error_message = None
                raise RuntimeError("__evaluation_risk_blocked__")
            judge_result = await self._judge_answer(
                question=str(case["question"]),
                expected_answer=str(case["expected_answer"]),
                actual_answer=actual_answer,
                expected_snippets=list(case.get("expected_snippets") or []),
                retrieved_docs=retrieved_docs,
            )
            score = self._normalize_score(judge_result.get("score"))
            retrieved_doc_ids = self._extract_retrieved_doc_ids(retrieved_docs)
            retrieved_chunk_ids = self._extract_retrieved_chunk_ids(retrieved_docs)
            retrieval_metrics = self._calculate_retrieval_metrics(
                expected_doc_ids=self._unique_ints(case.get("expected_doc_ids") or []),
                expected_chunk_ids=self._unique_ints(case.get("expected_chunk_ids") or []),
                expected_snippets=self._non_empty_strings(case.get("expected_snippets") or []),
                retrieved_docs=retrieved_docs,
                retrieved_doc_ids=retrieved_doc_ids,
                retrieved_chunk_ids=retrieved_chunk_ids,
            )
            passing_score = int(
                dict(run.policy_snapshot or {}).get("answer_passing_score") or ANSWER_PASSING_SCORE
            )
            judge_result["chunk_matched"] = retrieval_metrics["chunk_matched"]
            judge_result["evidence_matched"] = retrieval_metrics["evidence_matched"]
            judge_result["retrieval_metrics"] = retrieval_metrics
            judge_result["answer_passing_score"] = passing_score
            status = (
                "passed"
                if score >= passing_score and bool(retrieval_metrics["evidence_matched"])
                else "failed"
            )
        except Exception as exc:
            if str(exc) != "__evaluation_risk_blocked__":
                error_message = str(exc) or "评测用例执行失败"
            retrieved_chunk_ids = []

        latency_ms = int((perf_counter() - started_at) * 1000)
        await repo.create_case_result(
            run_id=int(run.id),
            case_id=case.get("case_id"),
            case_snapshot=case,
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

    @staticmethod
    def _build_case_snapshot(case: EvalCase) -> dict[str, Any]:
        return {
            "case_id": int(case.id),
            "question": case.question,
            "expected_answer": case.expected_answer,
            "expected_doc_ids": list(case.expected_doc_ids or []),
            "expected_snippets": list(case.expected_snippets or []),
            "expected_chunk_ids": list(case.expected_chunk_ids or []),
        }

    @staticmethod
    def _is_run_resumable(run: EvalRun) -> bool:
        if run.status in {"canceled", "failed"}:
            return True
        if run.status != "running":
            return False
        if run.heartbeat_at is None:
            return True
        return utc_now() - run.heartbeat_at >= timedelta(
            seconds=EVALUATION_RUN_HEARTBEAT_TIMEOUT_SECONDS
        )

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
    def _calculate_retrieval_metrics(
        *,
        expected_doc_ids: list[int],
        expected_chunk_ids: list[int],
        expected_snippets: list[str],
        retrieved_docs: list[dict[str, Any]],
        retrieved_doc_ids: list[int],
        retrieved_chunk_ids: list[int],
    ) -> dict[str, Any]:
        expected_doc_set = set(expected_doc_ids)
        expected_chunk_set = set(expected_chunk_ids)
        retrieved_doc_set = set(retrieved_doc_ids)
        retrieved_chunk_set = set(retrieved_chunk_ids)

        normalized_snippets: list[str] = []
        for item in expected_snippets:
            normalized = EvaluationService._normalize_evidence_text(item)
            if normalized:
                normalized_snippets.append(normalized)
        normalized_contents = [
            EvaluationService._normalize_evidence_text(
                str(doc.get("content") or doc.get("chunk_text") or "")
            )
            for doc in retrieved_docs
        ]
        matched_snippets = [
            snippet
            for snippet in normalized_snippets
            if any(snippet in content for content in normalized_contents)
        ]

        doc_recall = (
            len(expected_doc_set.intersection(retrieved_doc_set)) / len(expected_doc_set)
            if expected_doc_set
            else 1.0
        )
        chunk_recall = (
            len(expected_chunk_set.intersection(retrieved_chunk_set)) / len(expected_chunk_set)
            if expected_chunk_set
            else 1.0
        )
        snippet_recall = (
            len(matched_snippets) / len(normalized_snippets)
            if normalized_snippets
            else 1.0
        )

        first_relevant_rank = EvaluationService._first_relevant_rank(
            retrieved_docs=retrieved_docs,
            expected_doc_ids=expected_doc_set,
            expected_chunk_ids=expected_chunk_set,
            normalized_snippets=normalized_snippets,
        )
        chunk_matched = not expected_chunk_set or chunk_recall > 0
        if expected_chunk_set:
            evidence_matched = chunk_matched
            evidence_basis = "chunk"
        else:
            evidence_matched = True
            evidence_basis = "unconstrained"

        return {
            "retrieved_count": len(retrieved_docs),
            "document_recall": round(doc_recall, 4),
            "chunk_recall": round(chunk_recall, 4),
            "snippet_recall": round(snippet_recall, 4),
            "first_relevant_rank": first_relevant_rank,
            "reciprocal_rank": round(1 / first_relevant_rank, 4) if first_relevant_rank else 0.0,
            "chunk_matched": chunk_matched,
            "evidence_matched": evidence_matched,
            "evidence_basis": evidence_basis,
        }

    @staticmethod
    def _first_relevant_rank(
        *,
        retrieved_docs: list[dict[str, Any]],
        expected_doc_ids: set[int],
        expected_chunk_ids: set[int],
        normalized_snippets: list[str],
    ) -> int | None:
        for rank, doc in enumerate(retrieved_docs, start=1):
            metadata = dict(doc.get("metadata") or {})
            doc_id = metadata.get("document_id") or doc.get("document_id")
            normalized_doc_ids = EvaluationService._unique_ints([doc_id])
            chunk_ids = set(
                EvaluationService._unique_ints(
                    [
                        metadata.get("document_chunk_id"),
                        metadata.get("child_chunk_id"),
                        *(metadata.get("merged_child_chunk_ids") or []),
                    ]
                )
            )
            content = EvaluationService._normalize_evidence_text(
                str(doc.get("content") or doc.get("chunk_text") or "")
            )
            if normalized_snippets and any(snippet in content for snippet in normalized_snippets):
                return rank
            if not normalized_snippets and expected_chunk_ids.intersection(chunk_ids):
                return rank
            if (
                not normalized_snippets
                and not expected_chunk_ids
                and expected_doc_ids
                and normalized_doc_ids
                and normalized_doc_ids[0] in expected_doc_ids
            ):
                return rank
        return None

    @staticmethod
    def _normalize_evidence_text(value: str) -> str:
        return re.sub(r"\s+", "", str(value or "")).casefold()

    @staticmethod
    def _normalize_score(value: Any) -> int:
        try:
            score = int(round(float(value)))
        except (TypeError, ValueError):
            return 0
        return max(0, min(100, score))

    @staticmethod
    def _normalize_import_question(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip()).casefold()

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
