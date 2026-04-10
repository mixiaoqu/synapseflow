import asyncio
from fastapi import BackgroundTasks

from app.application.indexing_service import indexing_service
from app.core.config.registry import config_registry


def test_enqueue_document_adds_background_task():
    tasks = BackgroundTasks()

    indexing_service.enqueue_document(
        tasks,
        document_id=42,
        expected_content_hash="abc123",
    )

    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func == indexing_service.index_document_task
    assert task.kwargs == {
        "document_id": 42,
        "expected_content_hash": "abc123",
    }


def test_enqueue_current_document_reindex_adds_transition_task():
    tasks = BackgroundTasks()

    indexing_service.enqueue_current_document_reindex(
        tasks,
        target_document_id=9,
        target_content_hash="hash-9",
        previous_document_id=3,
    )

    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func == indexing_service.reindex_current_document_task
    assert task.kwargs == {
        "target_document_id": 9,
        "target_content_hash": "hash-9",
        "previous_document_id": 3,
    }


def test_enqueue_documents_batch_adds_background_task():
    tasks = BackgroundTasks()

    indexing_service.enqueue_documents_batch(
        tasks,
        documents=[(1, "hash-1"), (2, "hash-2")],
    )

    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.func == indexing_service.index_documents_batch_task
    assert task.kwargs == {"documents": [(1, "hash-1"), (2, "hash-2")]}


def test_build_dynamic_batches_splits_on_chunk_and_char_limits():
    documents = [
        {"document_id": 1, "char_count": 20_000, "chunk_count": 40},
        {"document_id": 2, "char_count": 30_000, "chunk_count": 60},
        {"document_id": 3, "char_count": 190_000, "chunk_count": 20},
        {"document_id": 4, "char_count": 10_000, "chunk_count": 250},
        {"document_id": 5, "char_count": 15_000, "chunk_count": 20},
    ]

    batches = indexing_service._build_dynamic_batches(documents)

    assert [[item["document_id"] for item in batch] for batch in batches] == [
        [1, 2],
        [3],
        [4],
        [5],
    ]


def test_build_dynamic_batches_uses_configurable_thresholds(monkeypatch):
    class DummyBatchConfig:
        max_docs = 2
        max_chunks = 50
        max_chars = 50_000

    monkeypatch.setattr(config_registry, "get_indexing_batch_config", lambda: DummyBatchConfig())
    documents = [
        {"document_id": 1, "char_count": 10_000, "chunk_count": 20},
        {"document_id": 2, "char_count": 10_000, "chunk_count": 20},
        {"document_id": 3, "char_count": 10_000, "chunk_count": 20},
    ]

    batches = indexing_service._build_dynamic_batches(documents)

    assert [[item["document_id"] for item in batch] for batch in batches] == [
        [1, 2],
        [3],
    ]


def test_index_documents_batch_task_processes_dynamic_batches(monkeypatch):
    class DummySession:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_prepare_batch_candidates(db, documents):
        assert documents == [(1, "hash-1"), (2, "hash-2"), (3, "hash-3")]
        return [
            {
                "document_id": 1,
                "expected_content_hash": "hash-1",
                "content": "a",
                "title": "Doc 1",
                "char_count": 10,
                "chunk_count": 2,
            },
            {
                "document_id": 2,
                "expected_content_hash": "hash-2",
                "content": "b",
                "title": "Doc 2",
                "char_count": 10,
                "chunk_count": 2,
            },
            {
                "document_id": 3,
                "expected_content_hash": "hash-3",
                "content": "c",
                "title": "Doc 3",
                "char_count": 10,
                "chunk_count": 2,
            },
        ]

    seen_batches = []

    async def fake_run_document_batch_index(db, *, batch):
        seen_batches.append([item["document_id"] for item in batch])
        return {int(item["document_id"]): int(item["chunk_count"]) for item in batch}

    monkeypatch.setattr("app.application.indexing_service.AsyncSessionLocal", lambda: DummySession())
    monkeypatch.setattr(indexing_service, "_prepare_batch_candidates", fake_prepare_batch_candidates)
    monkeypatch.setattr(
        indexing_service,
        "_build_dynamic_batches",
        lambda documents: [list(documents[:2]), list(documents[2:])],
    )
    monkeypatch.setattr(indexing_service, "_run_document_batch_index", fake_run_document_batch_index)

    asyncio.run(
        indexing_service.index_documents_batch_task(
            documents=[(1, "hash-1"), (2, "hash-2"), (3, "hash-3")]
        )
    )

    assert seen_batches == [[1, 2], [3]]
