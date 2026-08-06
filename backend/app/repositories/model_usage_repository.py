"""Read-only queries for AI cost center usage summaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    EvalDataset,
    EvalRun,
    KbChatLog,
    KnowledgeBase,
    Product,
    Project,
    ProjectApp,
    Team,
)


@dataclass(frozen=True, slots=True)
class ChatUsageRecord:
    created_at: datetime
    team_id: int | None
    team_name: str | None
    product_id: int | None
    product_name: str | None
    project_id: int | None
    project_name: str | None
    project_app_id: int | None
    project_app_name: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost: Any
    token_usage: Any


@dataclass(frozen=True, slots=True)
class EvaluationUsageRecord:
    created_at: datetime
    dataset_id: int
    dataset_name: str
    team_id: int
    team_name: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost: Any
    token_usage: Any


class ModelUsageRepository:
    """Repository that returns only usage columns required by the cost center."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_chat_usage(
        self,
        *,
        team_ids: list[int] | None,
        start_at: datetime,
        end_at: datetime,
    ) -> list[ChatUsageRecord]:
        conditions = [
            KbChatLog.created_at >= start_at,
            KbChatLog.created_at <= end_at,
            KbChatLog.total_tokens.is_not(None),
        ]
        if team_ids is not None:
            conditions.append(KnowledgeBase.team_id.in_(team_ids))
        stmt = (
            select(
                KbChatLog.created_at,
                KnowledgeBase.team_id,
                Team.name,
                KbChatLog.product_id,
                Product.name,
                KbChatLog.project_id,
                Project.name,
                KbChatLog.project_app_id,
                ProjectApp.name,
                KbChatLog.input_tokens,
                KbChatLog.output_tokens,
                KbChatLog.total_tokens,
                KbChatLog.estimated_cost,
                KbChatLog.token_usage,
            )
            .outerjoin(KnowledgeBase, KbChatLog.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(Team, KnowledgeBase.team_id == Team.id)
            .outerjoin(Product, KbChatLog.product_id == Product.id)
            .outerjoin(Project, KbChatLog.project_id == Project.id)
            .outerjoin(ProjectApp, KbChatLog.project_app_id == ProjectApp.id)
            .where(*conditions)
        )
        rows = (await self.db.execute(stmt)).all()
        return [ChatUsageRecord(*row) for row in rows]

    async def list_evaluation_usage(
        self,
        *,
        team_ids: list[int] | None,
        start_at: datetime,
        end_at: datetime,
    ) -> list[EvaluationUsageRecord]:
        conditions = [
            EvalRun.created_at >= start_at,
            EvalRun.created_at <= end_at,
            EvalRun.total_tokens.is_not(None),
        ]
        if team_ids is not None:
            conditions.append(KnowledgeBase.team_id.in_(team_ids))
        stmt = (
            select(
                EvalRun.created_at,
                EvalDataset.id,
                EvalDataset.name,
                KnowledgeBase.team_id,
                Team.name,
                EvalRun.input_tokens,
                EvalRun.output_tokens,
                EvalRun.total_tokens,
                EvalRun.estimated_cost,
                EvalRun.token_usage,
            )
            .join(EvalDataset, EvalRun.dataset_id == EvalDataset.id)
            .join(KnowledgeBase, EvalDataset.knowledge_base_id == KnowledgeBase.id)
            .outerjoin(Team, KnowledgeBase.team_id == Team.id)
            .where(*conditions)
        )
        rows = (await self.db.execute(stmt)).all()
        return [EvaluationUsageRecord(*row) for row in rows]
