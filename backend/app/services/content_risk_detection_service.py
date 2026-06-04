"""Runtime detection for global content-risk rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from time import perf_counter
from typing import Awaitable, Callable, Literal, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ContentRiskRule
from app.db.session import AsyncSessionLocal
from app.repositories.content_risk_library_repository import ContentRiskLibraryRepository

ContentRiskScene = Literal["query", "answer"]
ContentRiskAction = Literal["pass", "block", "review", "log"]
ContentRiskLevel = Literal["low", "medium", "high"]

T = TypeVar("T")


@dataclass(slots=True)
class ContentRiskRuleHit:
    """One matched runtime rule."""

    rule_id: int
    library_id: int
    rule_name: str
    risk_category: str
    risk_level: ContentRiskLevel
    action: Literal["block", "review", "log"]
    match_mode: str
    pattern: str
    matched_text: str


@dataclass(slots=True)
class ContentRiskDetectionResult:
    """Aggregated detection result for one text."""

    scene: ContentRiskScene
    action: ContentRiskAction
    blocked: bool
    risk_level: ContentRiskLevel | None
    hits: list[ContentRiskRuleHit]
    elapsed_ms: int


class ContentRiskDetectionService:
    """Checks text against all enabled global content-risk rules."""

    def __init__(self, session_factory: Callable[[], AsyncSession] | None = None):
        self._session_factory = session_factory or AsyncSessionLocal

    async def _run(
        self,
        callback: Callable[[ContentRiskLibraryRepository], Awaitable[T]],
        *,
        db: AsyncSession | None = None,
    ) -> T:
        if db is not None:
            return await callback(ContentRiskLibraryRepository(db))
        async with self._session_factory() as session:
            return await callback(ContentRiskLibraryRepository(session))

    async def check_text(
        self,
        *,
        scene: ContentRiskScene,
        text: str,
        db: AsyncSession | None = None,
    ) -> ContentRiskDetectionResult:
        started_at = perf_counter()
        content = text or ""
        if not content.strip():
            return self._build_result(scene=scene, hits=[], started_at=started_at)

        async def _callback(repo: ContentRiskLibraryRepository) -> ContentRiskDetectionResult:
            rules = await repo.list_enabled_rules_for_scene(scene)
            hits: list[ContentRiskRuleHit] = []
            for rule in rules:
                matched_text = self._match_rule(rule, content)
                if matched_text is None:
                    continue
                hits.append(
                    ContentRiskRuleHit(
                        rule_id=rule.id,
                        library_id=rule.library_id,
                        rule_name=rule.name,
                        risk_category=rule.risk_category,
                        risk_level=rule.risk_level,
                        action=rule.default_action,
                        match_mode=rule.match_mode,
                        pattern=rule.pattern,
                        matched_text=matched_text,
                    )
                )
            return self._build_result(scene=scene, hits=hits, started_at=started_at)

        return await self._run(_callback, db=db)

    @classmethod
    def _match_rule(cls, rule: ContentRiskRule, text: str) -> str | None:
        if rule.match_mode == "regex" or rule.rule_type == "regex":
            return cls._match_regex(rule.pattern, text)

        candidates = cls._split_keyword_pattern(rule.pattern)
        if rule.match_mode == "exact":
            text_for_compare = text.strip().casefold()
            for candidate in candidates:
                if text_for_compare == candidate.casefold():
                    return candidate
            return None

        text_for_compare = text.casefold()
        for candidate in candidates:
            if candidate.casefold() in text_for_compare:
                return candidate
        return None

    @staticmethod
    def _split_keyword_pattern(pattern: str) -> list[str]:
        return [
            item.strip()
            for item in re.split(r"[,，\n\r]+", pattern or "")
            if item.strip()
        ]

    @staticmethod
    def _match_regex(pattern: str, text: str) -> str | None:
        try:
            match = re.search(pattern, text, flags=re.IGNORECASE)
        except re.error:
            return None
        return match.group(0) if match else None

    @staticmethod
    def _build_result(
        *,
        scene: ContentRiskScene,
        hits: list[ContentRiskRuleHit],
        started_at: float,
    ) -> ContentRiskDetectionResult:
        action = ContentRiskDetectionService._resolve_action(hits)
        return ContentRiskDetectionResult(
            scene=scene,
            action=action,
            blocked=action == "block",
            risk_level=ContentRiskDetectionService._resolve_risk_level(hits),
            hits=hits,
            elapsed_ms=max(1, int((perf_counter() - started_at) * 1000)),
        )

    @staticmethod
    def _resolve_action(hits: list[ContentRiskRuleHit]) -> ContentRiskAction:
        actions = {hit.action for hit in hits}
        if "block" in actions:
            return "block"
        if "review" in actions:
            return "review"
        if "log" in actions:
            return "log"
        return "pass"

    @staticmethod
    def _resolve_risk_level(hits: list[ContentRiskRuleHit]) -> ContentRiskLevel | None:
        levels = {hit.risk_level for hit in hits}
        if "high" in levels:
            return "high"
        if "medium" in levels:
            return "medium"
        if "low" in levels:
            return "low"
        return None


content_risk_detection_service: ContentRiskDetectionService | None = None


def get_content_risk_detection_service() -> ContentRiskDetectionService:
    global content_risk_detection_service
    if content_risk_detection_service is None:
        content_risk_detection_service = ContentRiskDetectionService()
    return content_risk_detection_service
