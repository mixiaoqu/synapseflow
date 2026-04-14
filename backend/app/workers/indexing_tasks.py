"""Dramatiq actors for document indexing."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.application.indexing_service import indexing_service
from app.core.config.settings import settings
from app.workers.broker import configure_broker, dramatiq_is_available

if dramatiq_is_available():
    import dramatiq

    configure_broker()
else:  # pragma: no cover - local environments without dramatiq installed
    dramatiq = None  # type: ignore[assignment]


def _normalize_documents(
    documents: Sequence[dict[str, Any]],
) -> list[tuple[int, str]]:
    normalized: list[tuple[int, str]] = []
    for item in documents:
        normalized.append(
            (
                int(item["document_id"]),
                str(item["expected_content_hash"]),
            )
        )
    return normalized


class _MissingActor:
    def __init__(self, name: str) -> None:
        self.name = name

    def send(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            f"Dramatiq actor '{self.name}' is unavailable because Dramatiq is not installed."
        )


if dramatiq is not None:

    @dramatiq.actor(queue_name=settings.DRAMATIQ_INDEXING_QUEUE)
    async def index_document_actor(document_id: int, expected_content_hash: str, job_id: int) -> None:
        await indexing_service.index_document_task(
            document_id=document_id,
            expected_content_hash=expected_content_hash,
            job_id=job_id,
        )


    @dramatiq.actor(queue_name=settings.DRAMATIQ_INDEXING_QUEUE)
    async def index_documents_batch_actor(documents: list[dict[str, Any]], job_id: int) -> None:
        await indexing_service.index_documents_batch_task(
            documents=_normalize_documents(documents),
            job_id=job_id,
        )


    @dramatiq.actor(queue_name=settings.DRAMATIQ_INDEXING_QUEUE)
    async def reindex_current_document_actor(
        target_document_id: int,
        target_content_hash: str,
        job_id: int,
        previous_document_id: int | None = None,
    ) -> None:
        await indexing_service.reindex_current_document_task(
            target_document_id=target_document_id,
            target_content_hash=target_content_hash,
            job_id=job_id,
            previous_document_id=previous_document_id,
        )

else:
    index_document_actor = _MissingActor("index_document_actor")
    index_documents_batch_actor = _MissingActor("index_documents_batch_actor")
    reindex_current_document_actor = _MissingActor("reindex_current_document_actor")
