"""Sensitive-word runtime and admin service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SensitiveWord, SensitiveWordSetting
from app.db.session import AsyncSessionLocal
from app.repositories.sensitive_word_repository import (
    SensitiveWordRepository,
    normalize_sensitive_word,
)

T = TypeVar("T")

DEFAULT_ENABLED = True
DEFAULT_BLOCK_QUERY = True
DEFAULT_BLOCK_DOCUMENT_PUBLISH = False


@dataclass(slots=True)
class SensitiveWordCheckResult:
    """One sensitive-word check result."""

    blocked: bool
    matched_words: list[str]
    scene: str
    reason: str | None = None


class SensitiveWordService:
    """Owns scoped sensitive-word settings and runtime checks."""

    def __init__(self, session_factory: Callable[[], AsyncSession] | None = None):
        self._session_factory = session_factory or AsyncSessionLocal

    async def _run(
        self,
        callback: Callable[[SensitiveWordRepository], Awaitable[T]],
        *,
        db: AsyncSession | None = None,
    ) -> T:
        if db is not None:
            return await callback(SensitiveWordRepository(db))
        async with self._session_factory() as session:
            return await callback(SensitiveWordRepository(session))

    @staticmethod
    def _serialize_settings(row: SensitiveWordSetting | None, *, team_id: int | None) -> dict:
        if row is None:
            return {
                "id": None,
                "team_id": team_id,
                "enabled": DEFAULT_ENABLED,
                "block_query": DEFAULT_BLOCK_QUERY,
                "block_document_publish": DEFAULT_BLOCK_DOCUMENT_PUBLISH,
                "created_by_user_id": None,
                "updated_by_user_id": None,
                "created_at": None,
                "updated_at": None,
            }
        return {
            "id": row.id,
            "team_id": row.team_id,
            "enabled": bool(row.enabled),
            "block_query": bool(row.block_query),
            "block_document_publish": bool(row.block_document_publish),
            "created_by_user_id": row.created_by_user_id,
            "updated_by_user_id": row.updated_by_user_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    async def get_scoped_settings(
        self,
        *,
        team_id: int | None,
        db: AsyncSession | None = None,
    ) -> dict:
        return await self._run(
            lambda repo: self._get_scoped_settings(repo, team_id=team_id),
            db=db,
        )

    async def _get_scoped_settings(
        self,
        repo: SensitiveWordRepository,
        *,
        team_id: int | None,
    ) -> dict:
        return self._serialize_settings(await repo.get_settings(team_id), team_id=team_id)

    async def update_scoped_settings(
        self,
        *,
        team_id: int | None,
        enabled: bool,
        block_query: bool,
        block_document_publish: bool,
        actor_user_id: int | None,
        db: AsyncSession | None = None,
    ) -> SensitiveWordSetting:
        return await self._run(
            lambda repo: repo.upsert_settings(
                team_id=team_id,
                enabled=enabled,
                block_query=block_query,
                block_document_publish=block_document_publish,
                actor_user_id=actor_user_id,
            ),
            db=db,
        )

    async def list_words(
        self,
        *,
        team_id: int | None,
        keyword: str | None = None,
        enabled: bool | None = None,
        db: AsyncSession | None = None,
    ) -> list[SensitiveWord]:
        return await self._run(
            lambda repo: repo.list_words(team_id=team_id, keyword=keyword, enabled=enabled),
            db=db,
        )

    async def list_words_paginated(
        self,
        *,
        team_id: int | None,
        keyword: str | None = None,
        enabled: bool | None = None,
        page: int = 1,
        page_size: int = 20,
        db: AsyncSession | None = None,
    ) -> tuple[list[SensitiveWord], int, int, int]:
        return await self._run(
            lambda repo: repo.list_words_paginated(
                team_id=team_id,
                keyword=keyword,
                enabled=enabled,
                page=page,
                page_size=page_size,
            ),
            db=db,
        )

    async def create_word(
        self,
        *,
        team_id: int | None,
        word: str,
        category: str | None,
        enabled: bool,
        remark: str | None,
        actor_user_id: int | None,
        db: AsyncSession | None = None,
    ) -> SensitiveWord:
        normalized_word = normalize_sensitive_word(word)

        async def _callback(repo: SensitiveWordRepository) -> SensitiveWord:
            duplicate = await repo.get_word_by_normalized(
                team_id=team_id,
                normalized_word=normalized_word,
            )
            if duplicate is not None:
                raise ValueError("Sensitive word already exists in the selected scope")
            return await repo.create_word(
                team_id=team_id,
                word=word,
                category=category,
                enabled=enabled,
                remark=remark,
                actor_user_id=actor_user_id,
            )

        return await self._run(_callback, db=db)

    async def update_word(
        self,
        word_id: int,
        *,
        word: str,
        category: str | None,
        enabled: bool,
        remark: str | None,
        actor_user_id: int | None,
        db: AsyncSession | None = None,
    ) -> SensitiveWord | None:
        normalized_word = normalize_sensitive_word(word)

        async def _callback(repo: SensitiveWordRepository) -> SensitiveWord | None:
            existing = await repo.get_word_by_id(word_id)
            if existing is None:
                return None
            duplicate = await repo.get_word_by_normalized(
                team_id=existing.team_id,
                normalized_word=normalized_word,
            )
            if duplicate is not None and duplicate.id != word_id:
                raise ValueError("Sensitive word already exists in the selected scope")
            return await repo.update_word(
                word_id,
                word=word,
                category=category,
                enabled=enabled,
                remark=remark,
                actor_user_id=actor_user_id,
            )

        return await self._run(_callback, db=db)

    async def delete_word(self, word_id: int, *, db: AsyncSession | None = None) -> bool:
        return await self._run(lambda repo: repo.delete_word(word_id), db=db)

    async def import_words(
        self,
        *,
        team_id: int | None,
        words_text: str,
        category: str | None,
        enabled: bool,
        actor_user_id: int | None,
        db: AsyncSession | None = None,
    ) -> tuple[list[SensitiveWord], int]:
        normalized_to_raw: dict[str, str] = {}
        for line in words_text.splitlines():
            raw = line.strip()
            if not raw:
                continue
            normalized = normalize_sensitive_word(raw)
            if normalized and normalized not in normalized_to_raw:
                normalized_to_raw[normalized] = raw

        async def _callback(repo: SensitiveWordRepository) -> tuple[list[SensitiveWord], int]:
            new_words: list[str] = []
            skipped_count = 0
            for normalized, raw in normalized_to_raw.items():
                duplicate = await repo.get_word_by_normalized(
                    team_id=team_id,
                    normalized_word=normalized,
                )
                if duplicate is not None:
                    skipped_count += 1
                    continue
                new_words.append(raw)
            if not new_words:
                return [], skipped_count
            rows = await repo.create_many(
                team_id=team_id,
                words=new_words,
                category=category,
                enabled=enabled,
                actor_user_id=actor_user_id,
            )
            return rows, skipped_count

        return await self._run(_callback, db=db)

    async def get_effective_settings(
        self,
        *,
        team_id: int | None,
        db: AsyncSession | None = None,
    ) -> dict:
        async def _callback(repo: SensitiveWordRepository) -> dict:
            merged = self._serialize_settings(None, team_id=team_id)
            global_row = await repo.get_settings(None)
            if global_row is not None:
                merged.update(self._serialize_settings(global_row, team_id=None))
                merged["team_id"] = team_id
            if team_id is not None:
                team_row = await repo.get_settings(team_id)
                if team_row is not None:
                    merged.update(self._serialize_settings(team_row, team_id=team_id))
            return merged

        return await self._run(_callback, db=db)

    async def check_text(
        self,
        *,
        scene: str,
        text: str,
        team_id: int | None,
        db: AsyncSession | None = None,
    ) -> SensitiveWordCheckResult:
        normalized_text = normalize_sensitive_word(text)
        if not normalized_text:
            return SensitiveWordCheckResult(
                blocked=False,
                matched_words=[],
                scene=scene,
                reason=None,
            )

        async def _callback(repo: SensitiveWordRepository) -> SensitiveWordCheckResult:
            settings = await self.get_effective_settings(team_id=team_id, db=repo.db)
            if not settings.get("enabled", DEFAULT_ENABLED):
                return SensitiveWordCheckResult(
                    blocked=False,
                    matched_words=[],
                    scene=scene,
                    reason=None,
                )

            if scene == "query" and not settings.get("block_query", DEFAULT_BLOCK_QUERY):
                return SensitiveWordCheckResult(
                    blocked=False,
                    matched_words=[],
                    scene=scene,
                    reason=None,
                )
            if scene == "document_publish" and not settings.get(
                "block_document_publish",
                DEFAULT_BLOCK_DOCUMENT_PUBLISH,
            ):
                return SensitiveWordCheckResult(
                    blocked=False,
                    matched_words=[],
                    scene=scene,
                    reason=None,
                )

            words = await repo.list_effective_words(team_id)
            matches: list[str] = []
            seen_words: set[str] = set()
            for row in sorted(
                words,
                key=lambda item: (-len(item.normalized_word or ""), item.id or 0),
            ):
                needle = row.normalized_word or ""
                if not needle or row.match_mode != "contains":
                    continue
                if needle in normalized_text and needle not in seen_words:
                    matches.append(row.word)
                    seen_words.add(needle)

            blocked = len(matches) > 0
            return SensitiveWordCheckResult(
                blocked=blocked,
                matched_words=matches,
                scene=scene,
                reason=(
                    f"Matched {len(matches)} sensitive word(s)"
                    if blocked
                    else None
                ),
            )

        return await self._run(_callback, db=db)


sensitive_word_service: SensitiveWordService | None = None


def get_sensitive_word_service() -> SensitiveWordService:
    global sensitive_word_service
    if sensitive_word_service is None:
        sensitive_word_service = SensitiveWordService()
    return sensitive_word_service
