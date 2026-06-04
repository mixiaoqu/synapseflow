"""Persistence helpers for content-risk detection logs."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AssistantProfile,
    ContentRiskLog,
    KnowledgeBase,
    Product,
    Project,
    ProjectApp,
)


class ContentRiskLogRepository:
    """Persist and query content-risk detection decisions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_log(self, log: ContentRiskLog) -> ContentRiskLog:
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def list_logs(
        self,
        *,
        limit: int = 50,
        scene: str | None = None,
        action: str | None = None,
        blocked: bool | None = None,
        risk_level: str | None = None,
        chat_log_id: int | None = None,
    ) -> tuple[list[tuple[ContentRiskLog, str | None, str | None, str | None, str | None, str | None]], int]:
        normalized_limit = max(1, min(limit, 200))
        stmt = (
            select(
                ContentRiskLog,
                Product.name.label("product_name"),
                Project.name.label("project_name"),
                ProjectApp.name.label("project_app_name"),
                KnowledgeBase.name.label("knowledge_base_name"),
                AssistantProfile.name.label("assistant_name"),
            )
            .outerjoin(Product, ContentRiskLog.product_id == Product.id)
            .outerjoin(Project, ContentRiskLog.project_id == Project.id)
            .outerjoin(ProjectApp, ContentRiskLog.project_app_id == ProjectApp.id)
            .outerjoin(KnowledgeBase, ContentRiskLog.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(AssistantProfile, ContentRiskLog.assistant_id == AssistantProfile.id)
        )
        total_stmt = select(func.count()).select_from(ContentRiskLog)
        stmt = self._apply_filters(
            stmt,
            scene=scene,
            action=action,
            blocked=blocked,
            risk_level=risk_level,
            chat_log_id=chat_log_id,
        )
        total_stmt = self._apply_filters(
            total_stmt,
            scene=scene,
            action=action,
            blocked=blocked,
            risk_level=risk_level,
            chat_log_id=chat_log_id,
        )
        stmt = stmt.order_by(ContentRiskLog.created_at.desc(), ContentRiskLog.id.desc()).limit(normalized_limit)
        rows = (await self.db.execute(stmt)).all()
        total = (await self.db.execute(total_stmt)).scalar() or 0
        return list(rows), int(total)

    @staticmethod
    def _apply_filters(
        stmt,
        *,
        scene: str | None,
        action: str | None,
        blocked: bool | None,
        risk_level: str | None,
        chat_log_id: int | None,
    ):
        if scene:
            stmt = stmt.where(ContentRiskLog.scene == scene)
        if action:
            stmt = stmt.where(ContentRiskLog.action == action)
        if blocked is not None:
            stmt = stmt.where(ContentRiskLog.blocked.is_(blocked))
        if risk_level:
            stmt = stmt.where(ContentRiskLog.risk_level == risk_level)
        if chat_log_id is not None:
            stmt = stmt.where(ContentRiskLog.chat_log_id == chat_log_id)
        return stmt
