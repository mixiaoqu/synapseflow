"""Persistence helpers for KB chat logs and feedback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AssistantProfile,
    ChatMessage,
    ChatSession,
    DocumentCategory,
    KbChatLog,
    KnowledgeBase,
    Product,
    Project,
    ProjectApp,
    Team,
)
from app.utils.time import utc_now


@dataclass(slots=True)
class KbChatLogRecord:
    id: int
    user_id: int | None
    session_id: str | None
    product_id: int | None
    product_name: str | None
    project_id: int | None
    project_name: str | None
    project_app_id: int | None
    project_app_name: str | None
    external_user_id: str | None
    external_user_name: str | None
    team_id: int | None
    team_name: str | None
    knowledge_base_id: int | None
    knowledge_base_name: str | None
    assistant_id: int | None
    assistant_name: str | None
    category_id: int | None
    category_name: str | None
    query: str
    answer_text: str
    answer_status: str
    retrieval_status: str | None
    latency_ms: int | None
    text_hit_count: int
    graph_hit_count: int
    merged_candidate_count: int
    final_context_count: int
    empty_reason: str | None
    rerank_enabled: bool
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost: object | None
    token_usage: dict[str, Any] | None
    feedback_value: str | None
    feedback_note: str | None
    suggested_review_label: str | None
    review_label: str | None
    review_note: str | None
    reviewed_at: datetime | None
    reviewed_by_user_id: int | None
    created_at: object


@dataclass(slots=True)
class KbChatDiagnosticMessageRecord:
    role: str
    content: str
    created_at: datetime
    is_current_turn: bool


@dataclass(slots=True)
class KbChatLogDetailRecord(KbChatLogRecord):
    team_id: int | None
    team_name: str | None
    category_name: str | None
    retrieval_status_reason: str | None
    trace_payload: dict[str, Any] | None
    conversation_context: list[KbChatDiagnosticMessageRecord]


class KbChatLogRepository:
    """Persist KB chat executions and user feedback."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, log_id: int) -> KbChatLog | None:
        return await self.db.get(KbChatLog, log_id)

    async def create_log(
        self,
        *,
        user_id: int | None,
        session_id: str | None,
        product_id: int | None = None,
        project_id: int | None = None,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
        external_user_name: str | None = None,
        knowledge_base_id: int | None,
        assistant_id: int | None,
        category_id: int | None,
        query: str,
        answer_text: str,
        answer_status: str,
        retrieval_status: str | None,
        latency_ms: int | None,
        text_hit_count: int = 0,
        graph_hit_count: int = 0,
        merged_candidate_count: int = 0,
        final_context_count: int = 0,
        empty_reason: str | None = None,
        rerank_enabled: bool = False,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        estimated_cost: Any | None = None,
        token_usage: dict[str, Any] | None = None,
        trace_payload: dict[str, Any] | None = None,
    ) -> KbChatLog:
        row = KbChatLog(
            user_id=user_id,
            session_id=session_id,
            product_id=product_id,
            project_id=project_id,
            project_app_id=project_app_id,
            external_user_id=external_user_id,
            external_user_name=external_user_name,
            knowledge_base_id=knowledge_base_id,
            assistant_id=assistant_id,
            category_id=category_id,
            query=query,
            answer_text=answer_text,
            answer_status=answer_status,
            retrieval_status=retrieval_status,
            latency_ms=latency_ms,
            text_hit_count=text_hit_count,
            graph_hit_count=graph_hit_count,
            merged_candidate_count=merged_candidate_count,
            final_context_count=final_context_count,
            empty_reason=empty_reason,
            rerank_enabled=rerank_enabled,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            token_usage=token_usage,
            trace_payload=trace_payload,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def list_logs(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        team_id: int | None = None,
        team_ids: list[int] | None = None,
        project_id: int | None = None,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
        knowledge_base_id: int | None = None,
        category_id: int | None = None,
        answer_status: str | None = None,
        retrieval_status: str | None = None,
        feedback_value: str | None = None,
        query_keyword: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        zero_hits_only: bool = False,
        high_latency_only: bool = False,
        high_latency_threshold_ms: int = 5000,
    ) -> tuple[list[KbChatLogRecord], int]:
        normalized_page = max(1, page)
        normalized_page_size = max(1, min(page_size, 200))
        offset = (normalized_page - 1) * normalized_page_size
        stmt = (
            select(
                KbChatLog,
                KnowledgeBase,
                AssistantProfile.name.label("assistant_name"),
                Product.name.label("product_name"),
                Project.name.label("project_name"),
                ProjectApp.name.label("project_app_name"),
                Team.name.label("team_name"),
                DocumentCategory.name.label("category_name"),
            )
            .outerjoin(KnowledgeBase, KbChatLog.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(AssistantProfile, KbChatLog.assistant_id == AssistantProfile.id)
            .outerjoin(Product, KbChatLog.product_id == Product.id)
            .outerjoin(Project, KbChatLog.project_id == Project.id)
            .outerjoin(ProjectApp, KbChatLog.project_app_id == ProjectApp.id)
            .outerjoin(Team, KnowledgeBase.team_id == Team.id)
            .outerjoin(DocumentCategory, KbChatLog.category_id == DocumentCategory.id)
        )
        stmt = self._apply_list_log_filters(
            stmt,
            team_id=team_id,
            team_ids=team_ids,
            project_id=project_id,
            project_app_id=project_app_id,
            external_user_id=external_user_id,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            answer_status=answer_status,
            retrieval_status=retrieval_status,
            feedback_value=feedback_value,
            query_keyword=query_keyword,
            created_from=created_from,
            created_to=created_to,
            zero_hits_only=zero_hits_only,
            high_latency_only=high_latency_only,
            high_latency_threshold_ms=high_latency_threshold_ms,
        )
        stmt = (
            stmt
            .order_by(KbChatLog.created_at.desc(), KbChatLog.id.desc())
            .offset(offset)
            .limit(normalized_page_size)
        )
        total_stmt = (
            select(func.count())
            .select_from(KbChatLog)
            .outerjoin(KnowledgeBase, KbChatLog.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(AssistantProfile, KbChatLog.assistant_id == AssistantProfile.id)
            .outerjoin(Product, KbChatLog.product_id == Product.id)
            .outerjoin(Project, KbChatLog.project_id == Project.id)
            .outerjoin(ProjectApp, KbChatLog.project_app_id == ProjectApp.id)
            .outerjoin(Team, KnowledgeBase.team_id == Team.id)
            .outerjoin(DocumentCategory, KbChatLog.category_id == DocumentCategory.id)
        )
        total_stmt = self._apply_list_log_filters(
            total_stmt,
            team_id=team_id,
            team_ids=team_ids,
            project_id=project_id,
            project_app_id=project_app_id,
            external_user_id=external_user_id,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            answer_status=answer_status,
            retrieval_status=retrieval_status,
            feedback_value=feedback_value,
            query_keyword=query_keyword,
            created_from=created_from,
            created_to=created_to,
            zero_hits_only=zero_hits_only,
            high_latency_only=high_latency_only,
            high_latency_threshold_ms=high_latency_threshold_ms,
        )
        rows = (await self.db.execute(stmt)).all()
        total = (await self.db.execute(total_stmt)).scalar() or 0
        return (
            [
                KbChatLogRecord(
                    id=item.id,
                    user_id=item.user_id,
                    session_id=item.session_id,
                    product_id=item.product_id,
                    product_name=product_name,
                    project_id=item.project_id,
                    project_name=project_name,
                    project_app_id=item.project_app_id,
                    project_app_name=project_app_name,
                    external_user_id=item.external_user_id,
                    external_user_name=item.external_user_name,
                    team_id=knowledge_base.team_id if knowledge_base else None,
                    team_name=team_name,
                    knowledge_base_id=item.knowledge_base_id,
                    knowledge_base_name=knowledge_base.name if knowledge_base else None,
                    assistant_id=item.assistant_id,
                    assistant_name=assistant_name,
                    category_id=item.category_id,
                    category_name=category_name,
                    query=item.query,
                    answer_text=item.answer_text,
                    answer_status=item.answer_status,
                    retrieval_status=item.retrieval_status,
                    latency_ms=item.latency_ms,
                    text_hit_count=int(item.text_hit_count or 0),
                    graph_hit_count=int(item.graph_hit_count or 0),
                    merged_candidate_count=int(item.merged_candidate_count or 0),
                    final_context_count=int(item.final_context_count or 0),
                    empty_reason=item.empty_reason,
                    rerank_enabled=bool(item.rerank_enabled),
                    input_tokens=item.input_tokens,
                    output_tokens=item.output_tokens,
                    total_tokens=item.total_tokens,
                    estimated_cost=item.estimated_cost,
                    token_usage=item.token_usage if isinstance(item.token_usage, dict) else None,
                    feedback_value=item.feedback_value,
                    feedback_note=item.feedback_note,
                    suggested_review_label=self._suggest_review_label(item),
                    review_label=item.review_label,
                    review_note=item.review_note,
                    reviewed_at=item.reviewed_at,
                    reviewed_by_user_id=item.reviewed_by_user_id,
                    created_at=item.created_at,
                )
                for (
                    item,
                    knowledge_base,
                    assistant_name,
                    product_name,
                    project_name,
                    project_app_name,
                    team_name,
                    category_name,
                ) in rows
            ],
            int(total),
        )

    @staticmethod
    def _apply_list_log_filters(
        stmt,
        *,
        team_id: int | None,
        team_ids: list[int] | None,
        project_id: int | None,
        project_app_id: int | None,
        external_user_id: str | None,
        knowledge_base_id: int | None,
        category_id: int | None,
        answer_status: str | None,
        retrieval_status: str | None,
        feedback_value: str | None,
        query_keyword: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        zero_hits_only: bool,
        high_latency_only: bool,
        high_latency_threshold_ms: int,
    ):
        if team_id is not None:
            stmt = stmt.where(KnowledgeBase.team_id == team_id)
        if team_ids is not None:
            if not team_ids:
                stmt = stmt.where(False)
            else:
                stmt = stmt.where(KnowledgeBase.team_id.in_(team_ids))
        if project_id is not None:
            stmt = stmt.where(KbChatLog.project_id == project_id)
        if project_app_id is not None:
            stmt = stmt.where(KbChatLog.project_app_id == project_app_id)
        if external_user_id:
            stmt = stmt.where(KbChatLog.external_user_id == external_user_id.strip())
        if knowledge_base_id is not None:
            stmt = stmt.where(KbChatLog.knowledge_base_id == knowledge_base_id)
        if category_id is not None:
            stmt = stmt.where(KbChatLog.category_id == category_id)
        if answer_status:
            stmt = stmt.where(KbChatLog.answer_status == answer_status)
        if retrieval_status:
            stmt = stmt.where(KbChatLog.retrieval_status == retrieval_status)
        if feedback_value:
            stmt = stmt.where(KbChatLog.feedback_value == feedback_value)
        if query_keyword:
            keyword = query_keyword.strip()
            if keyword:
                stmt = stmt.where(KbChatLog.query.ilike(f"%{keyword}%"))
        if created_from is not None:
            stmt = stmt.where(KbChatLog.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(KbChatLog.created_at <= created_to)
        if zero_hits_only:
            stmt = stmt.where(KbChatLog.final_context_count == 0)
        if high_latency_only:
            stmt = stmt.where(
                KbChatLog.latency_ms.is_not(None),
                KbChatLog.latency_ms >= max(1, high_latency_threshold_ms),
            )
        return stmt

    async def get_log_detail(self, *, log_id: int) -> KbChatLogDetailRecord | None:
        stmt = (
            select(
                KbChatLog,
                KnowledgeBase.name.label("knowledge_base_name"),
                KnowledgeBase.team_id.label("knowledge_base_team_id"),
                AssistantProfile.name.label("assistant_name"),
                Product.name.label("product_name"),
                Project.name.label("project_name"),
                ProjectApp.name.label("project_app_name"),
                Team.name.label("team_name"),
                DocumentCategory.name.label("category_name"),
            )
            .outerjoin(KnowledgeBase, KbChatLog.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(AssistantProfile, KbChatLog.assistant_id == AssistantProfile.id)
            .outerjoin(Product, KbChatLog.product_id == Product.id)
            .outerjoin(Project, KbChatLog.project_id == Project.id)
            .outerjoin(ProjectApp, KbChatLog.project_app_id == ProjectApp.id)
            .outerjoin(Team, KnowledgeBase.team_id == Team.id)
            .outerjoin(DocumentCategory, KbChatLog.category_id == DocumentCategory.id)
            .where(KbChatLog.id == log_id)
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None

        (
            item,
            knowledge_base_name,
            knowledge_base_team_id,
            assistant_name,
            product_name,
            project_name,
            project_app_name,
            team_name,
            category_name,
        ) = row
        session = None
        if item.session_id:
            session = await self._get_chat_session(
                user_id=item.user_id,
                session_id=item.session_id,
                project_app_id=item.project_app_id,
                external_user_id=item.external_user_id,
            )

        session_messages: list[tuple[str, str, dict[str, Any] | None, datetime]] = []
        if session is not None:
            session_messages = await self._load_session_messages(session.id)

        detail = self._build_detail_record(
            item=item,
            knowledge_base_name=knowledge_base_name,
            assistant_name=assistant_name,
            product_name=product_name,
            project_name=project_name,
            project_app_name=project_app_name,
            category_name=category_name,
            team_id=(session.team_id if session is not None else knowledge_base_team_id),
            team_name=team_name,
            session_messages=session_messages,
        )
        return detail

    async def submit_feedback(
        self,
        *,
        log_id: int,
        feedback_value: str,
        feedback_note: str | None,
    ) -> KbChatLog | None:
        row = await self.db.get(KbChatLog, log_id)
        if row is None:
            return None
        row.feedback_value = feedback_value.strip()
        row.feedback_note = (feedback_note or "").strip() or None
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def submit_review(
        self,
        *,
        log_id: int,
        review_label: str | None,
        review_note: str | None,
        reviewer_user_id: int,
    ) -> KbChatLog | None:
        row = await self.db.get(KbChatLog, log_id)
        if row is None:
            return None

        normalized_label = (review_label or "").strip() or None
        normalized_note = (review_note or "").strip() or None
        row.review_label = normalized_label
        row.review_note = normalized_note
        if normalized_label or normalized_note:
            row.reviewed_at = utc_now()
            row.reviewed_by_user_id = reviewer_user_id
        else:
            row.reviewed_at = None
            row.reviewed_by_user_id = None
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def _get_chat_session(
        self,
        *,
        user_id: int | None,
        session_id: str,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ) -> ChatSession | None:
        stmt = select(ChatSession).where(ChatSession.session_id == session_id)
        if user_id is not None:
            stmt = stmt.where(ChatSession.user_id == user_id)
        else:
            stmt = stmt.where(
                ChatSession.project_app_id == project_app_id,
                ChatSession.external_user_id == external_user_id,
            )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _load_session_messages(
        self,
        chat_session_id: int,
    ) -> list[tuple[str, str, dict[str, Any] | None, datetime]]:
        stmt = (
            select(
                ChatMessage.role,
                ChatMessage.content,
                ChatMessage.metadata_,
                ChatMessage.created_at,
            )
            .where(ChatMessage.chat_session_id == chat_session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        return list((await self.db.execute(stmt)).all())

    @staticmethod
    def _build_retrieval_status_reason(
        retrieval_status: str | None,
        *,
        final_context_count: int,
    ) -> str | None:
        if retrieval_status in {"empty_collection", "empty_knowledge_base"}:
            return "当前范围内还没有完成索引的知识内容，因此本次没有可用于回答的文档片段。"
        if retrieval_status == "no_hits":
            return "当前范围内存在知识内容，但这次问题没有检索到足够相关的片段。"
        if retrieval_status == "ok" and final_context_count <= 0:
            return "检索流程执行成功，但没有保留可展示的命中文档片段。"
        return None

    @staticmethod
    def _suggest_review_label(item: KbChatLog) -> str | None:
        if item.retrieval_status in {"empty_collection", "empty_knowledge_base"}:
            return "知识库缺内容"
        if item.retrieval_status == "no_hits":
            return "检索失败"
        if item.answer_status in {"partial", "insufficient"}:
            return "答案正确但不完整"
        if item.feedback_value == "not_helpful" and item.retrieval_status == "ok":
            return "答案有依据但表达差"
        return None

    @staticmethod
    def _build_detail_record(
        *,
        item: KbChatLog,
        knowledge_base_name: str | None,
        assistant_name: str | None,
        product_name: str | None,
        project_name: str | None,
        project_app_name: str | None,
        category_name: str | None,
        team_id: int | None,
        team_name: str | None,
        session_messages: list[tuple[str, str, dict[str, Any] | None, datetime]],
    ) -> KbChatLogDetailRecord:
        target_index = None
        for index, (role, content, metadata, _) in enumerate(session_messages):
            metadata_obj = metadata if isinstance(metadata, dict) else {}
            if role == "assistant" and metadata_obj.get("log_id") == item.id:
                target_index = index
                break

        if target_index is None:
            for index, (role, content, _metadata, _) in enumerate(session_messages):
                if role == "assistant" and content == item.answer_text:
                    target_index = index
                    break

        trace_payload = item.trace_payload if isinstance(item.trace_payload, dict) else {}

        context_window: list[KbChatDiagnosticMessageRecord] = []
        if target_index is not None:
            start = max(0, target_index - 6)
            for index, (role, content, _, created_at) in enumerate(
                session_messages[start : target_index + 1],
                start=start,
            ):
                is_current_turn = index in {target_index, max(start, target_index - 1)}
                context_window.append(
                    KbChatDiagnosticMessageRecord(
                        role=role,
                        content=content,
                        created_at=created_at,
                        is_current_turn=is_current_turn,
                    )
                )
        else:
            for role, content, _, created_at in session_messages[-6:]:
                context_window.append(
                    KbChatDiagnosticMessageRecord(
                        role=role,
                        content=content,
                        created_at=created_at,
                        is_current_turn=False,
                    )
                )

        return KbChatLogDetailRecord(
            id=item.id,
            user_id=item.user_id,
            session_id=item.session_id,
            product_id=item.product_id,
            product_name=product_name,
            project_id=item.project_id,
            project_name=project_name,
            project_app_id=item.project_app_id,
            project_app_name=project_app_name,
            external_user_id=item.external_user_id,
            external_user_name=item.external_user_name,
            knowledge_base_id=item.knowledge_base_id,
            knowledge_base_name=knowledge_base_name,
            assistant_id=item.assistant_id,
            assistant_name=assistant_name,
            category_id=item.category_id,
            category_name=category_name,
            query=item.query,
            answer_text=item.answer_text,
            answer_status=item.answer_status,
            retrieval_status=item.retrieval_status,
            latency_ms=item.latency_ms,
            text_hit_count=int(item.text_hit_count or 0),
            graph_hit_count=int(item.graph_hit_count or 0),
            merged_candidate_count=int(item.merged_candidate_count or 0),
            final_context_count=int(item.final_context_count or 0),
            empty_reason=item.empty_reason,
            rerank_enabled=bool(item.rerank_enabled),
            input_tokens=item.input_tokens,
            output_tokens=item.output_tokens,
            total_tokens=item.total_tokens,
            estimated_cost=item.estimated_cost,
            token_usage=item.token_usage if isinstance(item.token_usage, dict) else None,
            feedback_value=item.feedback_value,
            feedback_note=item.feedback_note,
            suggested_review_label=KbChatLogRepository._suggest_review_label(item),
            review_label=item.review_label,
            review_note=item.review_note,
            reviewed_at=item.reviewed_at,
            reviewed_by_user_id=item.reviewed_by_user_id,
            created_at=item.created_at,
            team_id=team_id,
            team_name=team_name,
            retrieval_status_reason=KbChatLogRepository._build_retrieval_status_reason(
                item.retrieval_status,
                final_context_count=int(item.final_context_count or 0),
            ),
            trace_payload=trace_payload or None,
            conversation_context=context_window,
        )
