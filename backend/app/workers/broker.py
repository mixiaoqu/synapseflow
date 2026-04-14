"""Dramatiq broker setup for Redis-backed background jobs."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.core.config.settings import settings

try:
    import dramatiq
    from dramatiq.brokers.redis import RedisBroker
    from dramatiq.middleware.asyncio import AsyncIO
except ImportError:  # pragma: no cover - exercised in local fallback paths
    dramatiq = None  # type: ignore[assignment]
    RedisBroker = None  # type: ignore[assignment]
    AsyncIO = None  # type: ignore[assignment]


_broker_configured = False


def dramatiq_is_available() -> bool:
    """Return whether Dramatiq is importable in the current environment."""
    return bool(dramatiq and RedisBroker and AsyncIO)


def configure_broker() -> Any:
    """Configure the global Dramatiq broker once."""
    global _broker_configured

    if not dramatiq_is_available():
        raise RuntimeError(
            "Dramatiq is not installed. Rebuild the backend environment after updating dependencies."
        )

    if _broker_configured:
        return dramatiq.get_broker()

    broker = RedisBroker(url=settings.REDIS_URL)
    broker.add_middleware(AsyncIO())
    dramatiq.set_broker(broker)
    _broker_configured = True
    logger.info("Configured Dramatiq Redis broker url={}", settings.REDIS_URL)
    return broker
