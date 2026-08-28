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


async def _dispatch_evaluation_run(run_id: int, user_id: int) -> None:
    async with AsyncSessionLocal() as db:
        current_user = await db.get(User, user_id)
        if current_user is None:
            logger.warning("Skip evaluation run because user is missing run_id={} user_id={}", run_id, user_id)
            return
        case_keys = await evaluation_service.start_run(
            db=db,
            current_user=current_user,
            run_id=run_id,
        )
    for case_key in case_keys:
        execute_evaluation_case_actor.send(run_id, user_id, case_key)


async def _execute_evaluation_case(run_id: int, user_id: int, case_key: str) -> None:
    async with AsyncSessionLocal() as db:
        current_user = await db.get(User, user_id)
        if current_user is None:
            logger.warning(
                "Skip evaluation case because user is missing run_id={} user_id={} case_key={}",
                run_id,
                user_id,
                case_key,
            )
            return
        await evaluation_service.execute_case(
            db=db,
            current_user=current_user,
            run_id=run_id,
            case_key=case_key,
        )


if dramatiq is not None:

    @dramatiq.actor(queue_name=settings.DRAMATIQ_EVALUATION_QUEUE, time_limit=120000, max_retries=0)
    async def execute_evaluation_run_actor(run_id: int, user_id: int) -> None:
        await _dispatch_evaluation_run(run_id=run_id, user_id=user_id)

    @dramatiq.actor(
        queue_name=settings.DRAMATIQ_EVALUATION_QUEUE,
        time_limit=(settings.EVALUATION_CASE_TIMEOUT_SECONDS + 30) * 1000,
        max_retries=0,
    )
    async def execute_evaluation_case_actor(run_id: int, user_id: int, case_key: str) -> None:
        await _execute_evaluation_case(run_id=run_id, user_id=user_id, case_key=case_key)


else:
    execute_evaluation_run_actor = _MissingActor("execute_evaluation_run_actor")
    execute_evaluation_case_actor = _MissingActor("execute_evaluation_case_actor")
