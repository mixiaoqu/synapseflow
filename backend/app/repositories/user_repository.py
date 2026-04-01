"""User persistence helpers."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        full_name: str | None = None,
    ) -> User:
        user = User(
            username=_normalize_username(username),
            email=_normalize_email(email),
            full_name=(full_name or "").strip() or None,
            hashed_password=hash_password(password),
            is_active=True,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
