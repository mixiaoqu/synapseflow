"""Document upload session repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentUploadSession
from app.utils.time import utc_now


class DocumentUploadSessionRepository:
    """Persist upload session records for direct object-storage uploads."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def create_session(
        self,
        *,
        team_id: int,
        knowledge_base_id: int,
        category_id: int | None,
        original_filename: str,
        source_path: str | None,
        bucket_name: str,
        object_key: str,
        file_size: int,
        content_type: str | None,
        expires_at: datetime,
        commit: bool = True,
    ) -> DocumentUploadSession:
        session = DocumentUploadSession(
            user_id=self.user_id,
            team_id=team_id,
            knowledge_base_id=knowledge_base_id,
            category_id=category_id,
            original_filename=original_filename,
            source_path=source_path,
            bucket_name=bucket_name,
            object_key=object_key,
            file_size=file_size,
            content_type=content_type,
            status="initialized",
            expires_at=expires_at,
            completed_at=None,
        )
        self.db.add(session)
        if commit:
            await self.db.commit()
            await self.db.refresh(session)
        else:
            await self.db.flush()
        return session

    async def get_by_id(self, session_id: int) -> DocumentUploadSession | None:
        result = await self.db.execute(
            select(DocumentUploadSession).where(DocumentUploadSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, session_id: int) -> DocumentUploadSession | None:
        result = await self.db.execute(
            select(DocumentUploadSession).where(
                DocumentUploadSession.id == session_id,
                DocumentUploadSession.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_completed(
        self,
        session: DocumentUploadSession,
        *,
        document_id: int | None = None,
        commit: bool = True,
    ) -> DocumentUploadSession:
        session.status = "completed"
        session.document_id = document_id
        session.completed_at = utc_now()
        if commit:
            await self.db.commit()
            await self.db.refresh(session)
        else:
            await self.db.flush()
        return session

    async def mark_aborted(
        self,
        session: DocumentUploadSession,
        *,
        commit: bool = True,
    ) -> DocumentUploadSession:
        session.status = "aborted"
        session.completed_at = None
        if commit:
            await self.db.commit()
            await self.db.refresh(session)
        else:
            await self.db.flush()
        return session

    async def mark_expired(
        self,
        session: DocumentUploadSession,
        *,
        commit: bool = True,
    ) -> DocumentUploadSession:
        session.status = "expired"
        session.completed_at = None
        if commit:
            await self.db.commit()
            await self.db.refresh(session)
        else:
            await self.db.flush()
        return session
