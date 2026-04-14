"""Sensitive-word persistence helpers."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SensitiveWord, SensitiveWordSetting


def normalize_sensitive_word(value: str) -> str:
    return value.strip().lower()


class SensitiveWordRepository:
    """Persists scoped sensitive-word settings and rules."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_settings(self, team_id: int | None) -> SensitiveWordSetting | None:
        stmt = select(SensitiveWordSetting)
        if team_id is None:
            stmt = stmt.where(SensitiveWordSetting.team_id.is_(None))
        else:
            stmt = stmt.where(SensitiveWordSetting.team_id == team_id)
        result = await self.db.execute(stmt.order_by(SensitiveWordSetting.id.asc()))
        return result.scalars().first()

    async def upsert_settings(
        self,
        *,
        team_id: int | None,
        enabled: bool,
        block_query: bool,
        block_document_publish: bool,
        actor_user_id: int | None,
    ) -> SensitiveWordSetting:
        row = await self.get_settings(team_id)
        if row is None:
            row = SensitiveWordSetting(
                team_id=team_id,
                enabled=enabled,
                block_query=block_query,
                block_document_publish=block_document_publish,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
            self.db.add(row)
        else:
            row.enabled = enabled
            row.block_query = block_query
            row.block_document_publish = block_document_publish
            row.updated_by_user_id = actor_user_id
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def list_words(
        self,
        *,
        team_id: int | None = None,
        keyword: str | None = None,
        enabled: bool | None = None,
    ) -> list[SensitiveWord]:
        stmt = self._build_list_words_stmt(team_id=team_id, keyword=keyword, enabled=enabled)
        result = await self.db.execute(
            stmt.order_by(SensitiveWord.created_at.desc(), SensitiveWord.id.desc())
        )
        return list(result.scalars().all())

    def _build_list_words_stmt(
        self,
        *,
        team_id: int | None = None,
        keyword: str | None = None,
        enabled: bool | None = None,
    ):
        stmt = select(SensitiveWord)
        if team_id is None:
            stmt = stmt.where(SensitiveWord.team_id.is_(None))
        elif team_id >= 0:
            stmt = stmt.where(SensitiveWord.team_id == team_id)
        if keyword:
            needle = f"%{keyword.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    SensitiveWord.normalized_word.like(needle),
                    SensitiveWord.category.ilike(needle),
                )
            )
        if enabled is not None:
            stmt = stmt.where(SensitiveWord.enabled.is_(enabled))
        return stmt

    async def list_words_paginated(
        self,
        *,
        team_id: int | None = None,
        keyword: str | None = None,
        enabled: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SensitiveWord], int, int, int]:
        stmt = self._build_list_words_stmt(team_id=team_id, keyword=keyword, enabled=enabled)
        stmt_subquery = stmt.subquery()
        total_stmt = select(func.count()).select_from(stmt_subquery)
        enabled_count_stmt = (
            select(func.count())
            .select_from(stmt_subquery)
            .where(stmt_subquery.c.enabled.is_(True))
        )
        disabled_count_stmt = (
            select(func.count())
            .select_from(stmt_subquery)
            .where(stmt_subquery.c.enabled.is_(False))
        )
        total = int((await self.db.execute(total_stmt)).scalar_one() or 0)
        enabled_count = int((await self.db.execute(enabled_count_stmt)).scalar_one() or 0)
        disabled_count = int((await self.db.execute(disabled_count_stmt)).scalar_one() or 0)
        result = await self.db.execute(
            stmt.order_by(SensitiveWord.created_at.desc(), SensitiveWord.id.desc())
            .offset(max(0, (page - 1) * page_size))
            .limit(max(1, page_size))
        )
        return list(result.scalars().all()), total, enabled_count, disabled_count

    async def list_all_words(
        self,
        *,
        keyword: str | None = None,
        enabled: bool | None = None,
    ) -> list[SensitiveWord]:
        stmt = select(SensitiveWord)
        if keyword:
            needle = f"%{keyword.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    SensitiveWord.normalized_word.like(needle),
                    SensitiveWord.category.ilike(needle),
                )
            )
        if enabled is not None:
            stmt = stmt.where(SensitiveWord.enabled.is_(enabled))
        result = await self.db.execute(
            stmt.order_by(SensitiveWord.team_id.asc().nullsfirst(), SensitiveWord.id.desc())
        )
        return list(result.scalars().all())

    async def list_effective_words(self, team_id: int | None) -> list[SensitiveWord]:
        stmt = select(SensitiveWord).where(SensitiveWord.enabled.is_(True))
        if team_id is None:
            stmt = stmt.where(SensitiveWord.team_id.is_(None))
        else:
            stmt = stmt.where(
                or_(
                    SensitiveWord.team_id.is_(None),
                    SensitiveWord.team_id == team_id,
                )
            )
        result = await self.db.execute(
            stmt.order_by(SensitiveWord.team_id.asc().nullsfirst(), SensitiveWord.id.asc())
        )
        return list(result.scalars().all())

    async def get_word_by_id(self, word_id: int) -> SensitiveWord | None:
        result = await self.db.execute(select(SensitiveWord).where(SensitiveWord.id == word_id))
        return result.scalar_one_or_none()

    async def get_word_by_normalized(
        self,
        *,
        team_id: int | None,
        normalized_word: str,
    ) -> SensitiveWord | None:
        stmt = select(SensitiveWord).where(SensitiveWord.normalized_word == normalized_word)
        if team_id is None:
            stmt = stmt.where(SensitiveWord.team_id.is_(None))
        else:
            stmt = stmt.where(SensitiveWord.team_id == team_id)
        result = await self.db.execute(stmt.order_by(SensitiveWord.id.asc()))
        return result.scalars().first()

    async def create_word(
        self,
        *,
        team_id: int | None,
        word: str,
        category: str | None,
        enabled: bool,
        remark: str | None,
        actor_user_id: int | None,
    ) -> SensitiveWord:
        row = SensitiveWord(
            team_id=team_id,
            word=word.strip(),
            normalized_word=normalize_sensitive_word(word),
            category=(category or "").strip() or None,
            match_mode="contains",
            enabled=enabled,
            remark=(remark or "").strip() or None,
            created_by_user_id=actor_user_id,
            updated_by_user_id=actor_user_id,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def update_word(
        self,
        word_id: int,
        *,
        word: str,
        category: str | None,
        enabled: bool,
        remark: str | None,
        actor_user_id: int | None,
    ) -> SensitiveWord | None:
        row = await self.get_word_by_id(word_id)
        if row is None:
            return None
        row.word = word.strip()
        row.normalized_word = normalize_sensitive_word(word)
        row.category = (category or "").strip() or None
        row.enabled = enabled
        row.remark = (remark or "").strip() or None
        row.updated_by_user_id = actor_user_id
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def delete_word(self, word_id: int) -> bool:
        row = await self.get_word_by_id(word_id)
        if row is None:
            return False
        await self.db.delete(row)
        await self.db.commit()
        return True

    async def create_many(
        self,
        *,
        team_id: int | None,
        words: Sequence[str],
        category: str | None,
        enabled: bool,
        actor_user_id: int | None,
    ) -> list[SensitiveWord]:
        rows = [
            SensitiveWord(
                team_id=team_id,
                word=item.strip(),
                normalized_word=normalize_sensitive_word(item),
                category=(category or "").strip() or None,
                match_mode="contains",
                enabled=enabled,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
            for item in words
        ]
        self.db.add_all(rows)
        await self.db.commit()
        for row in rows:
            await self.db.refresh(row)
        return rows
