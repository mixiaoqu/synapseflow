"""Dramatiq actors for evaluation runs."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.application.evaluation_service import evaluation_service
from app.core.config.settings import settings
from app.db.models import User
from app.db.session import AsyncSessionLocal
from app.workers.broker import configure_broker, dramatiq_is_available

if dramatiq_is_available():
    import dramatiq

    configure_broker()
else:  # pragma: no cover - local environments without dramatiq installed
    dramatiq = None  # type: ignore[assignment]


class _MissingActor:
    def __init__(self, name: str) -> None:
        self.name = name

    def send(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            f"Dramatiq actor '{self.name}' is unavailable because Dramatiq is not installed."
        )


async def _execute_evaluation_run(run_id: int, user_id: int) -> None:
    async with AsyncSessionLocal() as db:
        current_user = await db.get(User, user_id)
        if current_user is None:
            logger.warning("Skip evaluation run because user is missing run_id={} user_id={}", run_id, user_id)
            return
        await evaluation_service.execute_run(
            db=db,
            current_user=current_user,
            run_id=run_id,
        )


if dramatiq is not None:

    @dramatiq.actor(queue_name=settings.DRAMATIQ_EVALUATION_QUEUE)
    async def execute_evaluation_run_actor(run_id: int, user_id: int) -> None:
        await _execute_evaluation_run(run_id=run_id, user_id=user_id)


else:
    execute_evaluation_run_actor = _MissingActor("execute_evaluation_run_actor")
