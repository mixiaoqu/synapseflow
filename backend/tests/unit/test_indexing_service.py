from fastapi import BackgroundTasks

from app.application.indexing_service import indexing_service


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
