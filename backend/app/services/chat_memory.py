"""Persistence helpers for KB chat memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage, ChatSession
from app.db.session import AsyncSessionLocal

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
            session.updated_at = datetime.utcnow()

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
