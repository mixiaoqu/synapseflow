"""Persistence helpers for KB chat memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage, ChatSession, DocumentCategory, KnowledgeBase
from app.db.session import AsyncSessionLocal
from app.utils.time import utc_now

_ROLE_LABELS = {
    "user": "User",
    "assistant": "Assistant",
    "system": "System",
}


@dataclass(slots=True)
class ChatMemoryContext:
    """Loaded memory for one chat session."""

    messages: list[dict[str, str]]
    summary: str | None = None


@dataclass(slots=True)
class ChatSessionSummaryRecord:
    """Session summary returned for history navigation."""

    session_id: str
    title: str
    preview: str | None
    knowledge_base_id: int | None
    knowledge_base_name: str | None
    category_id: int | None
    category_name: str | None
    message_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ChatSessionDetailRecord(ChatSessionSummaryRecord):
    """Session detail including messages."""

    messages: list[dict[str, str | datetime]]


class ChatMemoryStore(Protocol):
    """Read/write memory interface for KB chat."""

    async def load_context(
        self,
        *,
        user_id: int,
        session_id: str,
    ) -> ChatMemoryContext: ...

    async def save_turn(
        self,
        *,
        user_id: int,
        session_id: str,
        knowledge_base_id: int | None,
        category_id: int | None,
        user_message: str,
        assistant_message: str,
    ) -> None: ...

    async def list_sessions(
        self,
        *,
        user_id: int,
        limit: int = 30,
    ) -> list[ChatSessionSummaryRecord]: ...

    async def get_session_detail(
        self,
        *,
        user_id: int,
        session_id: str,
    ) -> ChatSessionDetailRecord | None: ...


def format_chat_history(
    messages: list[dict[str, str]] | None,
    *,
    max_messages: int | None = None,
) -> str:
    """Format recent messages into a compact prompt-friendly transcript."""

    items = list(messages or [])
    if max_messages is not None and max_messages > 0:
        items = items[-max_messages:]

    lines: list[str] = []
    for message in items:
        role = str(message.get("role") or "").strip().lower() or "assistant"
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{_ROLE_LABELS.get(role, role.title())}: {content}")
    return "\n".join(lines)


class DatabaseChatMemoryStore:
    """Database-backed chat memory store for KB chat sessions."""

    def __init__(self, *, history_limit: int = 8):
        self.history_limit = max(1, history_limit)

    async def load_context(
        self,
        *,
        user_id: int,
        session_id: str,
    ) -> ChatMemoryContext:
        async with AsyncSessionLocal() as db:
            session = await self._get_session(db, user_id=user_id, session_id=session_id)
            if not session:
                return ChatMemoryContext(messages=[], summary=None)

            result = await db.execute(
                select(ChatMessage.role, ChatMessage.content)
                .where(ChatMessage.chat_session_id == session.id)
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .limit(self.history_limit)
            )
            messages = [
                {"role": role, "content": content}
                for role, content in reversed(result.all())
                if str(content or "").strip()
            ]
            return ChatMemoryContext(messages=messages, summary=session.summary)

    async def save_turn(
        self,
        *,
        user_id: int,
        session_id: str,
        knowledge_base_id: int | None,
        category_id: int | None,
        user_message: str,
        assistant_message: str,
    ) -> None:
        normalized_user = (user_message or "").strip()
        normalized_assistant = (assistant_message or "").strip()
        if not normalized_user and not normalized_assistant:
            return

        async with AsyncSessionLocal() as db:
            session = await self._get_or_create_session(
                db,
                user_id=user_id,
                session_id=session_id,
            )
            session.knowledge_base_id = knowledge_base_id
            session.category_id = category_id
            session.updated_at = utc_now()

            if normalized_user:
                db.add(
                    ChatMessage(
                        chat_session_id=session.id,
                        role="user",
                        content=normalized_user,
                    )
                )
            if normalized_assistant:
                db.add(
                    ChatMessage(
                        chat_session_id=session.id,
                        role="assistant",
                        content=normalized_assistant,
                    )
                )

            await db.commit()

    async def list_sessions(
        self,
        *,
        user_id: int,
        limit: int = 30,
    ) -> list[ChatSessionSummaryRecord]:
        normalized_limit = max(1, min(limit, 100))
        async with AsyncSessionLocal() as db:
            rows = await db.execute(
                select(ChatSession, KnowledgeBase.name, DocumentCategory.name)
                .outerjoin(KnowledgeBase, KnowledgeBase.id == ChatSession.knowledge_base_id)
                .outerjoin(DocumentCategory, DocumentCategory.id == ChatSession.category_id)
                .where(ChatSession.user_id == user_id)
                .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
                .limit(normalized_limit)
            )
            sessions = rows.all()
            if not sessions:
                return []

            messages_by_session = await self._load_messages_for_sessions(
                db,
                [session.id for session, _, _ in sessions],
            )
            return [
                self._build_session_summary(
                    session,
                    kb_name=knowledge_base_name,
                    category_name=category_name,
                    messages=messages_by_session.get(session.id, []),
                )
                for session, knowledge_base_name, category_name in sessions
            ]

    async def get_session_detail(
        self,
        *,
        user_id: int,
        session_id: str,
    ) -> ChatSessionDetailRecord | None:
        async with AsyncSessionLocal() as db:
            row = await db.execute(
                select(ChatSession, KnowledgeBase.name, DocumentCategory.name)
                .outerjoin(KnowledgeBase, KnowledgeBase.id == ChatSession.knowledge_base_id)
                .outerjoin(DocumentCategory, DocumentCategory.id == ChatSession.category_id)
                .where(
                    ChatSession.user_id == user_id,
                    ChatSession.session_id == session_id,
                )
            )
            result = row.one_or_none()
            if result is None:
                return None

            session, knowledge_base_name, category_name = result
            messages_by_session = await self._load_messages_for_sessions(db, [session.id])
            messages = messages_by_session.get(session.id, [])
            summary = self._build_session_summary(
                session,
                kb_name=knowledge_base_name,
                category_name=category_name,
                messages=messages,
            )
            return ChatSessionDetailRecord(
                session_id=summary.session_id,
                title=summary.title,
                preview=summary.preview,
                knowledge_base_id=summary.knowledge_base_id,
                knowledge_base_name=summary.knowledge_base_name,
                category_id=summary.category_id,
                category_name=summary.category_name,
                message_count=summary.message_count,
                created_at=summary.created_at,
                updated_at=summary.updated_at,
                messages=messages,
            )

    @staticmethod
    async def _get_session(
        db: AsyncSession,
        *,
        user_id: int,
        session_id: str,
    ) -> ChatSession | None:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_or_create_session(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        session_id: str,
    ) -> ChatSession:
        session = await self._get_session(db, user_id=user_id, session_id=session_id)
        if session:
            return session

        session = ChatSession(
            user_id=user_id,
            session_id=session_id,
        )
        db.add(session)
        await db.flush()
        return session

    @staticmethod
    async def _load_messages_for_sessions(
        db: AsyncSession,
        session_ids: list[int],
    ) -> dict[int, list[dict[str, str | datetime]]]:
        if not session_ids:
            return {}

        result = await db.execute(
            select(
                ChatMessage.chat_session_id,
                ChatMessage.role,
                ChatMessage.content,
                ChatMessage.created_at,
            )
            .where(ChatMessage.chat_session_id.in_(session_ids))
            .order_by(
                ChatMessage.chat_session_id.asc(),
                ChatMessage.created_at.asc(),
                ChatMessage.id.asc(),
            )
        )

        grouped: dict[int, list[dict[str, str | datetime]]] = {session_id: [] for session_id in session_ids}
        for chat_session_id, role, content, created_at in result.all():
            grouped.setdefault(chat_session_id, []).append(
                {
                    "role": role,
                    "content": content,
                    "created_at": created_at,
                }
            )
        return grouped

    @staticmethod
    def _build_session_summary(
        session: ChatSession,
        *,
        kb_name: str | None,
        category_name: str | None,
        messages: list[dict[str, str | datetime]],
    ) -> ChatSessionSummaryRecord:
        title = "New conversation"
        preview: str | None = None

        for message in messages:
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            if preview is None:
                preview = DatabaseChatMemoryStore._truncate(content, 120)
            if str(message.get("role") or "").lower() == "user":
                title = DatabaseChatMemoryStore._truncate(content, 60)
                break
            if title == "New conversation":
                title = DatabaseChatMemoryStore._truncate(content, 60)

        if messages:
            last_content = str(messages[-1].get("content") or "").strip()
            if last_content:
                preview = DatabaseChatMemoryStore._truncate(last_content, 120)

        return ChatSessionSummaryRecord(
            session_id=session.session_id,
            title=title,
            preview=preview,
            knowledge_base_id=session.knowledge_base_id,
            knowledge_base_name=kb_name,
            category_id=session.category_id,
            category_name=category_name,
            message_count=len(messages),
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        normalized = " ".join(value.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: max(1, limit - 1)].rstrip() + "…"
