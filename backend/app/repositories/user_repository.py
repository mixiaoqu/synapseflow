"""User persistence helpers."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_USER, normalize_system_role
from app.core.security import hash_password
from app.db.models import Team, TeamMember, User
from app.utils.time import utc_now


def _normalize_username(value: str) -> str:
    return value.strip().lower()


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _deleted_username(user_id: int) -> str:
    return f"deleted_user_{user_id}"


def _deleted_email(user_id: int) -> str:
    return f"deleted_user_{user_id}@deleted.local"


class UserRepository:
    """Persists application users."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int, *, include_deleted: bool = False) -> User | None:
        query = select(User).where(User.id == user_id)
        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_ids(self, user_ids: list[int], *, include_deleted: bool = False) -> list[User]:
        unique_ids = [int(user_id) for user_id in dict.fromkeys(user_ids)]
        if not unique_ids:
            return []
        query = select(User).where(User.id.in_(unique_ids))
        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))
        result = await self.db.execute(query)
        rows = list(result.scalars().all())
        order = {user_id: index for index, user_id in enumerate(unique_ids)}
        return sorted(rows, key=lambda user: order.get(int(user.id), len(order)))

    async def get_by_username(self, username: str, *, include_deleted: bool = True) -> User | None:
        normalized = _normalize_username(username)
        query = select(User).where(User.username == normalized)
        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str, *, include_deleted: bool = True) -> User | None:
        normalized = _normalize_email(email)
        query = select(User).where(User.email == normalized)
        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_identity(self, username_or_email: str) -> User | None:
        identity = username_or_email.strip().lower()
        result = await self.db.execute(
            select(User).where(
                User.deleted_at.is_(None),
                or_(
                    User.username == identity,
                    User.email == identity,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_users(self) -> list[User]:
        result = await self.db.execute(
            select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc(), User.id.desc())
        )
        return list(result.scalars().all())

    async def list_users_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        keyword: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        team_id: int | None = None,
    ) -> tuple[list[User], int]:
        base_query = select(User).where(User.deleted_at.is_(None))
        if team_id is not None:
            base_query = base_query.join(TeamMember, TeamMember.user_id == User.id).where(
                TeamMember.team_id == team_id
            )
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            base_query = base_query.where(
                or_(
                    User.username.ilike(pattern),
                    User.email.ilike(pattern),
                    User.full_name.ilike(pattern),
                )
            )
        if role and role.strip():
            base_query = base_query.where(User.role == normalize_system_role(role))
        if is_active is not None:
            base_query = base_query.where(User.is_active.is_(is_active))
        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar_one()
        offset = (page - 1) * page_size
        result = await self.db.execute(
            base_query.order_by(User.created_at.desc(), User.id.desc()).offset(offset).limit(page_size)
        )
        rows = list(result.scalars().all())
        return rows, total

    async def get_user_team_names(self, user_ids: list[int]) -> dict[int, list[str]]:
        memberships = await self.get_user_team_memberships(user_ids)
        return {
            user_id: [item["team_name"] for item in items]
            for user_id, items in memberships.items()
        }

    async def get_user_team_memberships(self, user_ids: list[int]) -> dict[int, list[dict]]:
        if not user_ids:
            return {}
        result = await self.db.execute(
            select(TeamMember.user_id, Team.id, Team.name, TeamMember.role)
            .join(Team, Team.id == TeamMember.team_id)
            .where(TeamMember.user_id.in_(user_ids))
            .order_by(Team.name.asc(), Team.id.asc())
        )
        mapping: dict[int, list[dict]] = {user_id: [] for user_id in user_ids}
        for user_id, team_id, team_name, role in result.all():
            mapping.setdefault(user_id, []).append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "role": role,
                }
            )
        return mapping

    async def count_active_admins(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(
                User.deleted_at.is_(None),
                User.is_active.is_(True),
                User.role == SYSTEM_ROLE_ADMIN,
            )
        )
        return result.scalar_one()

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        full_name: str | None = None,
        role: str = SYSTEM_ROLE_USER,
        is_active: bool = True,
    ) -> User:
        user = User(
            username=_normalize_username(username),
            email=_normalize_email(email),
            full_name=(full_name or "").strip() or None,
            hashed_password=hash_password(password),
            role=normalize_system_role(role),
            is_active=is_active,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_user(
        self,
        user_id: int,
        *,
        username: str | None = None,
        email: str | None = None,
        password: str | None = None,
        full_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> User | None:
        user = await self.get_by_id(user_id)
        if user is None:
            return None

        if username is not None:
            user.username = _normalize_username(username)
        if email is not None:
            user.email = _normalize_email(email)
        if password is not None:
            user.hashed_password = hash_password(password)
        if full_name is not None:
            user.full_name = full_name.strip() or None
        if role is not None:
            user.role = normalize_system_role(role)
        if is_active is not None:
            user.is_active = is_active

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def soft_delete_user(self, user_id: int) -> User | None:
        user = await self.get_by_id(user_id)
        if user is None:
            return None
        user.is_active = False
        user.deleted_at = utc_now()
        user.username = _deleted_username(user.id)
        user.email = _deleted_email(user.id)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def soft_delete_users(self, user_ids: list[int]) -> list[User]:
        users = await self.get_by_ids(user_ids)
        return await self.soft_delete_loaded_users(users)

    async def soft_delete_loaded_users(self, users: list[User]) -> list[User]:
        deleted: list[User] = []
        now = utc_now()
        for user in users:
            user.is_active = False
            user.deleted_at = now
            user.username = _deleted_username(user.id)
            user.email = _deleted_email(user.id)
            deleted.append(user)
        if deleted:
            await self.db.commit()
            for user in deleted:
                await self.db.refresh(user)
        return deleted

    async def update_users_active(self, users: list[User], is_active: bool) -> int:
        for user in users:
            user.is_active = is_active
        if users:
            await self.db.commit()
        return len(users)
