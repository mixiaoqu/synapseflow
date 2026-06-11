"""Application service for knowledge-base workflows."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.document_service import document_service
from app.application.permission_service import PermissionService
from app.core.authz import PERMISSION_MANAGE_KB_DRAFT, has_team_role_permission
from app.db.models import User
from app.models.schemas.knowledge_base import (
    KnowledgeBaseBulkActionFailure,
    KnowledgeBaseBulkActionRequest,
    KnowledgeBaseBulkActionResponse,
)
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository


class KnowledgeBaseService:
    """Coordinates knowledge-base workflows that cross repositories."""

    async def bulk_action(
        self,
        *,
        db: AsyncSession,
        current_user: User,
        body: KnowledgeBaseBulkActionRequest,
    ) -> KnowledgeBaseBulkActionResponse:
        repo = KnowledgeBaseRepository(db, user_id=current_user.id, user=current_user)
        unique_ids = [int(item) for item in dict.fromkeys(body.knowledge_base_ids)]
        knowledge_bases = await repo.get_by_ids(unique_ids)
        kb_by_id = {int(kb.id): kb for kb in knowledge_bases}
        failures = [
            KnowledgeBaseBulkActionFailure(id=kb_id, message="知识库不存在或无权访问")
            for kb_id in unique_ids
            if kb_id not in kb_by_id
        ]
        allowed_kbs = await self._filter_manageable_knowledge_bases(
            db=db,
            current_user=current_user,
            knowledge_bases=knowledge_bases,
            failures=failures,
        )

        affected = 0
        if body.action in {"enable", "disable"}:
            affected = await repo.set_active_many(
                allowed_kbs,
                is_active=(body.action == "enable"),
            )
        elif body.action == "delete":
            affected = await repo.delete_many(allowed_kbs)
        elif body.action == "reindex":
            for knowledge_base in allowed_kbs:
                try:
                    await document_service.reindex_all_documents(
                        db=db,
                        user_id=current_user.id,
                        knowledge_base_id=int(knowledge_base.id),
                    )
                    affected += 1
                except Exception as exc:  # noqa: BLE001
                    failures.append(
                        KnowledgeBaseBulkActionFailure(
                            id=int(knowledge_base.id),
                            message=str(exc) or "重建索引任务提交失败",
                        )
                    )
        else:
            raise HTTPException(status_code=400, detail="不支持的批量操作")

        return KnowledgeBaseBulkActionResponse(
            action=body.action,
            total=len(unique_ids),
            affected=affected,
            failed=failures,
        )

    @staticmethod
    async def _filter_manageable_knowledge_bases(
        *,
        db: AsyncSession,
        current_user: User,
        knowledge_bases: list,
        failures: list[KnowledgeBaseBulkActionFailure],
    ) -> list:
        permission_service = PermissionService(db)
        team_ids = [int(kb.team_id) for kb in knowledge_bases]
        roles = await permission_service.get_team_roles(current_user, team_ids)
        allowed = []
        for knowledge_base in knowledge_bases:
            if PermissionService.is_system_admin(current_user):
                allowed.append(knowledge_base)
                continue
            role = roles.get(int(knowledge_base.team_id))
            if role is not None and has_team_role_permission(role, PERMISSION_MANAGE_KB_DRAFT):
                allowed.append(knowledge_base)
                continue
            failures.append(
                KnowledgeBaseBulkActionFailure(
                    id=int(knowledge_base.id),
                    message="Knowledge-base permission denied",
                )
            )
        return allowed


knowledge_base_service = KnowledgeBaseService()
