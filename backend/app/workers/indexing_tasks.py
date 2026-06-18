"""Dramatiq actors for document indexing."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import PurePath
from typing import Any

from app.application.document_parse_service import document_parse_service
from app.application.indexing_service import indexing_service
from app.core.config.settings import settings
from app.services.embedding import warmup_embedding_model
from app.workers.broker import configure_broker, dramatiq_is_available

if dramatiq_is_available():
    import dramatiq

    configure_broker()
    if any(PurePath(arg).name.startswith("dramatiq") for arg in sys.argv[:2]):
        warmup_embedding_model()
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


def _normalize_graph_documents(
    documents: Sequence[dict[str, Any]],
) -> list[tuple[int, str]]:
    return _normalize_documents(documents)


class _MissingActor:
    def __init__(self, name: str) -> None:
        self.name = name

    def send(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            f"Dramatiq actor '{self.name}' is unavailable because Dramatiq is not installed."
        )


if dramatiq is not None:

    @dramatiq.actor(queue_name=settings.DRAMATIQ_INDEXING_QUEUE)
    async def parse_document_actor(document_id: int, expected_staged_file_hash: str) -> None:
        await document_parse_service.parse_document_task(
            document_id=document_id,
            expected_staged_file_hash=expected_staged_file_hash,
        )


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


    @dramatiq.actor(queue_name=settings.DRAMATIQ_GRAPH_INDEXING_QUEUE)
    async def index_document_graph_actor(document_id: int, expected_content_hash: str, job_id: int) -> None:
        await indexing_service.index_document_graph_task(
            document_id=document_id,
            expected_content_hash=expected_content_hash,
            job_id=job_id,
        )


    @dramatiq.actor(queue_name=settings.DRAMATIQ_GRAPH_INDEXING_QUEUE)
    async def index_documents_graph_batch_actor(documents: list[dict[str, Any]], job_id: int) -> None:
        await indexing_service.index_documents_graph_batch_task(
            documents=_normalize_graph_documents(documents),
            job_id=job_id,
        )


    @dramatiq.actor(queue_name=settings.DRAMATIQ_GRAPH_INDEXING_QUEUE)
    async def index_document_graph_chunk_actor(
        document_id: int,
        document_chunk_id: int,
        expected_content_hash: str,
        job_id: int,
        title: str | None = None,
    ) -> None:
        await indexing_service.index_document_graph_chunk_task(
            document_id=document_id,
            document_chunk_id=document_chunk_id,
            expected_content_hash=expected_content_hash,
            job_id=job_id,
            title=title,
        )


    @dramatiq.actor(queue_name=settings.DRAMATIQ_GRAPH_INDEXING_QUEUE)
    async def index_document_graph_chunks_actor(
        document_id: int,
        document_chunk_ids: list[int],
        expected_content_hash: str,
        job_id: int,
        title: str | None = None,
    ) -> None:
        await indexing_service.index_document_graph_chunks_task(
            document_id=document_id,
            document_chunk_ids=document_chunk_ids,
            expected_content_hash=expected_content_hash,
            job_id=job_id,
            title=title,
        )


    @dramatiq.actor(queue_name=settings.DRAMATIQ_GRAPH_INDEXING_QUEUE)
    async def finalize_document_graph_actor(
        document_id: int,
        expected_content_hash: str,
        job_id: int,
        title: str | None = None,
    ) -> None:
        await indexing_service.finalize_document_graph_task(
            document_id=document_id,
            expected_content_hash=expected_content_hash,
            job_id=job_id,
            title=title,
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


    @dramatiq.actor(queue_name=settings.DRAMATIQ_GRAPH_INDEXING_QUEUE)
    async def reindex_current_document_graph_actor(
        target_document_id: int,
        target_content_hash: str,
        job_id: int,
        previous_document_id: int | None = None,
    ) -> None:
        await indexing_service.reindex_current_document_graph_task(
            target_document_id=target_document_id,
            target_content_hash=target_content_hash,
            job_id=job_id,
            previous_document_id=previous_document_id,
        )

else:
    parse_document_actor = _MissingActor("parse_document_actor")
    index_document_actor = _MissingActor("index_document_actor")
    index_documents_batch_actor = _MissingActor("index_documents_batch_actor")
    reindex_current_document_actor = _MissingActor("reindex_current_document_actor")
    index_document_graph_actor = _MissingActor("index_document_graph_actor")
    index_documents_graph_batch_actor = _MissingActor("index_documents_graph_batch_actor")
    index_document_graph_chunk_actor = _MissingActor("index_document_graph_chunk_actor")
    index_document_graph_chunks_actor = _MissingActor("index_document_graph_chunks_actor")
    finalize_document_graph_actor = _MissingActor("finalize_document_graph_actor")
    reindex_current_document_graph_actor = _MissingActor("reindex_current_document_graph_actor")
