"""Agent conversation query and deletion use cases."""

from __future__ import annotations

from app.models.schemas.kb_chat import (
    KbChatSessionDetail,
    KbChatSessionMessage,
    KbChatSessionSummary,
)
from app.services.chat_memory import ChatMemoryStore, DatabaseChatMemoryStore


class AgentConversationService:
    """Query and delete persisted Agent conversations."""

    def __init__(self, memory_store: ChatMemoryStore | None = None):
        self._memory_store = memory_store or DatabaseChatMemoryStore()

    async def list_sessions(
        self,
        *,
        user_id: int | None,
        limit: int = 30,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ) -> list[KbChatSessionSummary]:
        records = await self._memory_store.list_sessions(
            user_id=user_id,
            limit=limit,
            project_app_id=project_app_id,
            external_user_id=external_user_id,
        )
        return [
            KbChatSessionSummary(
                session_id=record.session_id,
                title=record.title,
                preview=record.preview,
                product_id=record.product_id,
                project_id=record.project_id,
                project_app_id=record.project_app_id,
                external_user_id=record.external_user_id,
                external_user_name=record.external_user_name,
                team_id=record.team_id,
                knowledge_base_id=record.knowledge_base_id,
                knowledge_base_name=record.knowledge_base_name,
                assistant_id=record.assistant_id,
                assistant_name=record.assistant_name,
                category_id=record.category_id,
                category_name=record.category_name,
                message_count=record.message_count,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
            for record in records
        ]

    async def get_session(
        self,
        *,
        user_id: int | None,
        session_id: str,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ) -> KbChatSessionDetail | None:
        record = await self._memory_store.get_session_detail(
            user_id=user_id,
            session_id=session_id,
            project_app_id=project_app_id,
            external_user_id=external_user_id,
        )
        if record is None:
            return None

        return KbChatSessionDetail(
            session_id=record.session_id,
            title=record.title,
            preview=record.preview,
            product_id=record.product_id,
            project_id=record.project_id,
            project_app_id=record.project_app_id,
            external_user_id=record.external_user_id,
            external_user_name=record.external_user_name,
            team_id=record.team_id,
            knowledge_base_id=record.knowledge_base_id,
            knowledge_base_name=record.knowledge_base_name,
            assistant_id=record.assistant_id,
            assistant_name=record.assistant_name,
            category_id=record.category_id,
            category_name=record.category_name,
            message_count=record.message_count,
            created_at=record.created_at,
            updated_at=record.updated_at,
            messages=[
                KbChatSessionMessage(
                    role=str(message.get("role") or ""),
                    content=str(message.get("content") or ""),
                    retrieved_docs=list(
                        ((message.get("metadata") or {}).get("retrieved_docs") or [])
                    ),
                    answer_status=(
                        (message.get("metadata") or {}).get("answer_status")
                        if isinstance(
                            (message.get("metadata") or {}).get("answer_status"),
                            str,
                        )
                        else None
                    ),
                    log_id=(
                        (message.get("metadata") or {}).get("log_id")
                        if isinstance((message.get("metadata") or {}).get("log_id"), int)
                        else None
                    ),
                    created_at=message["created_at"],
                )
                for message in record.messages
            ],
        )

    async def delete_session(
        self,
        *,
        user_id: int | None,
        session_id: str,
        project_app_id: int | None = None,
        external_user_id: str | None = None,
    ) -> bool:
        return await self._memory_store.delete_session(
            user_id=user_id,
            session_id=session_id,
            project_app_id=project_app_id,
            external_user_id=external_user_id,
        )
