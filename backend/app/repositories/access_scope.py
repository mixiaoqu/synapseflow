"""Shared access-scope predicates for team and knowledge-base visibility."""

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import aliased

from app.application.permission_service import PermissionService
from app.db.models import AssistantProfile, Document, KnowledgeBase, KnowledgeBaseMember, TeamMember, User


def accessible_knowledge_base_condition(user_id: int, kb_entity=KnowledgeBase, user: User | None = None):
    """Return a predicate for knowledge bases visible to the given user."""
    if user is not None and PermissionService.is_system_admin(user):
        return True
    return or_(
        kb_entity.user_id == user_id,
        exists(
            select(1)
            .select_from(TeamMember)
            .where(
                TeamMember.team_id == kb_entity.team_id,
                TeamMember.user_id == user_id,
            )
            .correlate(kb_entity)
        ),
        exists(
            select(1)
            .select_from(KnowledgeBaseMember)
            .where(
                KnowledgeBaseMember.knowledge_base_id == kb_entity.id,
                KnowledgeBaseMember.user_id == user_id,
            )
            .correlate(kb_entity)
        ),
    )


def accessible_document_condition(user_id: int, user: User | None = None):
    """Return a predicate for documents visible to the given user."""
    if user is not None and PermissionService.is_system_admin(user):
        return True
    kb_alias = aliased(KnowledgeBase)
    return or_(
        Document.user_id == user_id,
        exists(
            select(1)
            .select_from(kb_alias)
            .where(
                kb_alias.id == Document.knowledge_base_id,
                accessible_knowledge_base_condition(user_id, kb_alias, user),
            )
            .correlate(Document)
        ),
    )


def accessible_assistant_profile_condition(
    user_id: int,
    assistant_entity=AssistantProfile,
    user: User | None = None,
):
    """Return a predicate for assistants visible to the given user."""
    if user is not None and PermissionService.is_system_admin(user):
        return True
    return or_(
        assistant_entity.created_by_user_id == user_id,
        exists(
            select(1)
            .select_from(TeamMember)
            .where(
                TeamMember.team_id == assistant_entity.team_id,
                TeamMember.user_id == user_id,
            )
            .correlate(assistant_entity)
        ),
    )
