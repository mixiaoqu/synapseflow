"""User persistence helpers."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import ROLE_END_USER, normalize_role
from app.core.security import hash_password
from app.db.models import User


def _normalize_username(value: str) -> str:
    return value.strip().lower()


def _normalize_email(value: str) -> str:
    return value.strip().lower()


class UserRepository:
    """Persists application users."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        normalized = _normalize_username(username)
        result = await self.db.execute(select(User).where(User.username == normalized))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        normalized = _normalize_email(email)
        result = await self.db.execute(select(User).where(User.email == normalized))
        return result.scalar_one_or_none()

    async def get_by_identity(self, username_or_email: str) -> User | None:
        identity = username_or_email.strip().lower()
        result = await self.db.execute(
            select(User).where(
                or_(
                    User.username == identity,
                    User.email == identity,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_users(self) -> list[User]:
        result = await self.db.execute(select(User).order_by(User.created_at.desc(), User.id.desc()))
        return list(result.scalars().all())

    async def list_users_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> tuple[list[User], int]:
        base_query = select(User)
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            base_query = base_query.where(
                or_(
                    User.username.ilike(pattern),
                    User.email.ilike(pattern),
                    User.full_name.ilike(pattern),
                )
            )
        count_result = await self.db.execute(select(func.count()).select_from(base_query.subquery()))
        total = count_result.scalar_one()
        offset = (page - 1) * page_size
        result = await self.db.execute(
            base_query.order_by(User.created_at.desc(), User.id.desc()).offset(offset).limit(page_size)
        )
        rows = list(result.scalars().all())
        return rows, total

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        full_name: str | None = None,
        role: str = ROLE_END_USER,
        is_active: bool = True,
    ) -> User:
        user = User(
            username=_normalize_username(username),
            email=_normalize_email(email),
            full_name=(full_name or "").strip() or None,
            hashed_password=hash_password(password),
            role=normalize_role(role),
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
            user.role = normalize_role(role)
        if is_active is not None:
            user.is_active = is_active

        await self.db.commit()
        await self.db.refresh(user)
        return user
