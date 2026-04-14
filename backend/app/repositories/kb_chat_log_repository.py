"""Persistence helpers for KB chat logs and feedback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ChatMessage,
    ChatSession,
    DocumentCategory,
    KbChatLog,
    KnowledgeBase,
    Team,
)
from app.utils.time import utc_now


@dataclass(slots=True)
class KbChatLogRecord:
    id: int
    user_id: int
    session_id: str | None
    team_id: int | None
    team_name: str | None
    knowledge_base_id: int | None
    knowledge_base_name: str | None
    category_id: int | None
    category_name: str | None
    query: str
    answer_text: str
    answer_status: str
    retrieval_status: str | None
    retrieved_count: int
    latency_ms: int | None
    feedback_value: str | None
    feedback_note: str | None
    suggested_review_label: str | None
    review_label: str | None
    review_note: str | None
    reviewed_at: datetime | None
    reviewed_by_user_id: int | None
    created_at: object


@dataclass(slots=True)
class KbChatDiagnosticDocRecord:
    rank: int
    content: str
    metadata: dict[str, Any]


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
    retrieval_queries: list[str]
    retrieval_funnel: dict[str, Any] | None
    answer_context: str | None
    retrieved_docs: list[KbChatDiagnosticDocRecord]
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
        user_id: int,
        session_id: str | None,
        knowledge_base_id: int | None,
        category_id: int | None,
        query: str,
        answer_text: str,
        answer_status: str,
        retrieval_status: str | None,
        retrieved_count: int,
        latency_ms: int | None,
    ) -> KbChatLog:
        row = KbChatLog(
            user_id=user_id,
            session_id=session_id,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            query=query,
            answer_text=answer_text,
            answer_status=answer_status,
            retrieval_status=retrieval_status,
            retrieved_count=retrieved_count,
            latency_ms=latency_ms,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def list_logs(
        self,
        *,
        limit: int = 50,
        team_id: int | None = None,
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
        normalized_limit = max(1, min(limit, 200))
        stmt = (
            select(
                KbChatLog,
                KnowledgeBase,
                Team.name.label("team_name"),
                DocumentCategory.name.label("category_name"),
            )
            .outerjoin(KnowledgeBase, KbChatLog.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(Team, KnowledgeBase.team_id == Team.id)
            .outerjoin(DocumentCategory, KbChatLog.category_id == DocumentCategory.id)
        )
        stmt = self._apply_list_log_filters(
            stmt,
            team_id=team_id,
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
            .limit(normalized_limit)
        )
        total_stmt = (
            select(func.count())
            .select_from(KbChatLog)
            .outerjoin(KnowledgeBase, KbChatLog.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(Team, KnowledgeBase.team_id == Team.id)
            .outerjoin(DocumentCategory, KbChatLog.category_id == DocumentCategory.id)
        )
        total_stmt = self._apply_list_log_filters(
            total_stmt,
            team_id=team_id,
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
                    team_id=knowledge_base.team_id if knowledge_base else None,
                    team_name=team_name,
                    knowledge_base_id=item.knowledge_base_id,
                    knowledge_base_name=knowledge_base.name if knowledge_base else None,
                    category_id=item.category_id,
                    category_name=category_name,
                    query=item.query,
                    answer_text=item.answer_text,
                    answer_status=item.answer_status,
                    retrieval_status=item.retrieval_status,
                    retrieved_count=item.retrieved_count,
                    latency_ms=item.latency_ms,
                    feedback_value=item.feedback_value,
                    feedback_note=item.feedback_note,
                    suggested_review_label=self._suggest_review_label(item),
                    review_label=item.review_label,
                    review_note=item.review_note,
                    reviewed_at=item.reviewed_at,
                    reviewed_by_user_id=item.reviewed_by_user_id,
                    created_at=item.created_at,
                )
                for item, knowledge_base, team_name, category_name in rows
            ],
            int(total),
        )

    @staticmethod
    def _apply_list_log_filters(
        stmt,
        *,
        team_id: int | None,
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
            stmt = stmt.where(KbChatLog.retrieved_count == 0)
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
                Team.name.label("team_name"),
                DocumentCategory.name.label("category_name"),
            )
            .outerjoin(KnowledgeBase, KbChatLog.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(Team, KnowledgeBase.team_id == Team.id)
            .outerjoin(DocumentCategory, KbChatLog.category_id == DocumentCategory.id)
            .where(KbChatLog.id == log_id)
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return None

        item, knowledge_base_name, knowledge_base_team_id, team_name, category_name = row
        session = None
        if item.session_id:
            session = await self._get_chat_session(
                user_id=item.user_id,
                session_id=item.session_id,
            )

        session_messages: list[tuple[str, str, dict[str, Any] | None, datetime]] = []
        if session is not None:
            session_messages = await self._load_session_messages(session.id)

        detail = self._build_detail_record(
            item=item,
            knowledge_base_name=knowledge_base_name,
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
        user_id: int,
        session_id: str,
    ) -> ChatSession | None:
        stmt = select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.session_id == session_id,
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
        retrieved_count: int,
    ) -> str | None:
        if retrieval_status in {"empty_collection", "empty_knowledge_base"}:
            return "当前范围内还没有完成索引的知识内容，因此本次没有可用于回答的文档片段。"
        if retrieval_status == "no_hits":
            return "当前范围内存在知识内容，但这次问题没有检索到足够相关的片段。"
        if retrieval_status == "ok" and retrieved_count <= 0:
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
        category_name: str | None,
        team_id: int | None,
        team_name: str | None,
        session_messages: list[tuple[str, str, dict[str, Any] | None, datetime]],
    ) -> KbChatLogDetailRecord:
        target_index = None
        target_metadata: dict[str, Any] = {}

        for index, (role, content, metadata, _) in enumerate(session_messages):
            metadata_obj = metadata if isinstance(metadata, dict) else {}
            if role == "assistant" and metadata_obj.get("log_id") == item.id:
                target_index = index
                target_metadata = metadata_obj
                break

        if target_index is None:
            for index, (role, content, metadata, _) in enumerate(session_messages):
                if role == "assistant" and content == item.answer_text:
                    target_index = index
                    target_metadata = metadata if isinstance(metadata, dict) else {}
                    break

        raw_retrieved_docs = target_metadata.get("retrieved_docs") or []
        answer_context = (
            target_metadata.get("answer_context")
            if isinstance(target_metadata.get("answer_context"), str)
            else None
        )
        retrieval_queries = [
            str(value)
            for value in (target_metadata.get("retrieval_queries") or [])
            if str(value or "").strip()
        ]
        retrieval_funnel = (
            target_metadata.get("retrieval_funnel")
            if isinstance(target_metadata.get("retrieval_funnel"), dict)
            else None
        )

        retrieved_docs: list[KbChatDiagnosticDocRecord] = []

        for index, doc in enumerate(raw_retrieved_docs, start=1):
            if not isinstance(doc, dict):
                continue
            content = str(doc.get("content") or "")
            metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
            record = KbChatDiagnosticDocRecord(
                rank=index,
                content=content,
                metadata=metadata,
            )
            retrieved_docs.append(record)

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
            knowledge_base_id=item.knowledge_base_id,
            knowledge_base_name=knowledge_base_name,
            category_id=item.category_id,
            category_name=category_name,
            query=item.query,
            answer_text=item.answer_text,
            answer_status=item.answer_status,
            retrieval_status=item.retrieval_status,
            retrieved_count=item.retrieved_count,
            latency_ms=item.latency_ms,
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
                retrieved_count=item.retrieved_count,
            ),
            retrieval_queries=retrieval_queries,
            retrieval_funnel=retrieval_funnel,
            answer_context=answer_context,
            retrieved_docs=retrieved_docs,
            conversation_context=context_window,
        )
