import asyncio
from types import SimpleNamespace

from app.application.indexing_service import indexing_service
from app.core.config.registry import config_registry
from app.services.semantic_chunk import VectorIndexChunk


def test_enqueue_document_sends_dramatiq_message(monkeypatch):
    captured = {}

    class DummyActor:
        def send(self, **kwargs):
            captured["kwargs"] = kwargs

    class DummyModule:
        index_document_actor = DummyActor()

    monkeypatch.setattr(indexing_service, "_actor_module", lambda: DummyModule)

    indexing_service.enqueue_document(document_id=42, expected_content_hash="abc123", job_id=7)

    assert captured["kwargs"] == {
        "document_id": 42,
        "expected_content_hash": "abc123",
        "job_id": 7,
    }


def test_enqueue_current_document_reindex_sends_transition_task(monkeypatch):
    captured = {}

    class DummyActor:
        def send(self, **kwargs):
            captured["kwargs"] = kwargs

    class DummyModule:
        reindex_current_document_actor = DummyActor()

    monkeypatch.setattr(indexing_service, "_actor_module", lambda: DummyModule)

    indexing_service.enqueue_current_document_reindex(
        target_document_id=9,
        target_content_hash="hash-9",
        job_id=11,
        previous_document_id=3,
    )

    assert captured["kwargs"] == {
        "target_document_id": 9,
        "target_content_hash": "hash-9",
        "job_id": 11,
        "previous_document_id": 3,
    }


def test_enqueue_documents_batch_sends_serialized_document_chunks(monkeypatch):
    captured = []

    class DummyActor:
        def send(self, **kwargs):
            captured.append(kwargs)

    class DummyModule:
        index_documents_batch_actor = DummyActor()

    monkeypatch.setattr(indexing_service, "_actor_module", lambda: DummyModule)

    indexing_service.enqueue_documents_batch(
        documents=[(index, f"hash-{index}") for index in range(1, 46)],
        job_id=23,
    )

    assert [len(item["documents"]) for item in captured] == [20, 20, 5]
    assert captured[0]["documents"][0] == {
        "document_id": 1,
        "expected_content_hash": "hash-1",
    }
    assert captured[-1]["documents"][-1] == {
        "document_id": 45,
        "expected_content_hash": "hash-45",
    }
    assert {item["job_id"] for item in captured} == {23}


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

    class FakeIndexJobRepository:
        def __init__(self, db):
            pass

        async def refresh_job_state(self, *, job_id):
            assert job_id == 5

        async def is_job_active(self, *, job_id):
            assert job_id == 5
            return True

    async def fake_prepare_batch_candidates(db, documents, *, job_id=None):
        assert documents == [(1, "hash-1"), (2, "hash-2"), (3, "hash-3")]
        assert job_id == 5
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

    async def fake_run_document_batch_index(db, *, batch, job_id=None):
        assert job_id == 5
        seen_batches.append([item["document_id"] for item in batch])
        return {int(item["document_id"]): int(item["chunk_count"]) for item in batch}

    monkeypatch.setattr("app.application.indexing_service.AsyncSessionLocal", lambda: DummySession())
    monkeypatch.setattr(
        "app.application.indexing_service.IndexJobRepository",
        FakeIndexJobRepository,
    )
    monkeypatch.setattr(indexing_service, "_prepare_batch_candidates", fake_prepare_batch_candidates)
    monkeypatch.setattr(
        indexing_service,
        "_build_dynamic_batches",
        lambda documents: [list(documents[:2]), list(documents[2:])],
    )
    monkeypatch.setattr(indexing_service, "_run_document_batch_index", fake_run_document_batch_index)

    asyncio.run(
        indexing_service.index_documents_batch_task(
            documents=[(1, "hash-1"), (2, "hash-2"), (3, "hash-3")],
            job_id=5,
        )
    )

    assert seen_batches == [[1, 2], [3]]


def test_prepare_batch_candidates_skips_terminal_and_already_indexed_docs(monkeypatch):
    class FakeIndexJobRepository:
        def __init__(self, db):
            pass

        async def get_document_statuses(self, *, job_id, documents):
            assert job_id == 9
            return {
                (1, "hash-1"): "indexed",
                (2, "hash-2"): "failed",
            }

    docs = {
        1: SimpleNamespace(
            id=1,
            content_hash="hash-1",
            index_status="queued",
            indexed_at=None,
            content="one",
            title="One",
        ),
        2: SimpleNamespace(
            id=2,
            content_hash="hash-2",
            index_status="queued",
            indexed_at=None,
            content="two",
            title="Two",
        ),
        3: SimpleNamespace(
            id=3,
            content_hash="hash-3",
            index_status="indexed",
            indexed_at=None,
            content="three",
            title="Three",
        ),
        4: SimpleNamespace(
            id=4,
            content_hash="hash-4",
            index_status="queued",
            indexed_at=None,
            content="four",
            title="Four",
        ),
    }
    processing_ids = []
    status_updates = []

    async def fake_get_documents_for_ids(db, document_ids):
        return {doc_id: docs[doc_id] for doc_id in document_ids}

    async def fake_get_document(db, document_id):
        return docs[document_id]

    async def fake_set_job_document_status(db, **kwargs):
        status_updates.append(kwargs)

    async def fake_mark_processing(db, *, document_id, expected_content_hash):
        processing_ids.append(document_id)
        return True

    monkeypatch.setattr(
        "app.application.indexing_service.IndexJobRepository",
        FakeIndexJobRepository,
    )
    monkeypatch.setattr(indexing_service, "_get_documents_for_ids", fake_get_documents_for_ids)
    monkeypatch.setattr(indexing_service, "_get_document", fake_get_document)
    monkeypatch.setattr(indexing_service, "_set_job_document_status", fake_set_job_document_status)
    monkeypatch.setattr(indexing_service, "_mark_processing", fake_mark_processing)

    prepared = asyncio.run(
        indexing_service._prepare_batch_candidates(
            object(),
            [(1, "hash-1"), (2, "hash-2"), (3, "hash-3"), (4, "hash-4")],
            job_id=9,
        )
    )

    assert [item["document_id"] for item in prepared] == [4]
    assert processing_ids == [4]
    assert len(status_updates) == 2
    assert status_updates[0]["job_id"] == 9
    assert status_updates[0]["document_id"] == 3
    assert status_updates[0]["expected_content_hash"] == "hash-3"
    assert status_updates[0]["status"] == "indexed"
    assert status_updates[1] == {
        "job_id": 9,
        "document_id": 4,
        "expected_content_hash": "hash-4",
        "status": "processing",
    }


def test_run_document_batch_index_reuses_prepared_chunks(monkeypatch):
    batch = [
        {
            "document_id": 1,
            "expected_content_hash": "hash-1",
            "content": "original content should not be rechunked",
            "title": "Doc 1",
            "char_count": 10,
            "chunk_count": 1,
            "chunks": [
                VectorIndexChunk(
                    display_text="prepared body",
                    embedding_text="prepared embedding text",
                    search_text="prepared search text",
                    metadata={"chunk_index": 0},
                )
            ],
        }
    ]

    captured: dict[str, object] = {}

    async def fake_index_prepared_documents_batch(db, prepared_docs, *, commit):
        captured["prepared_docs"] = prepared_docs
        captured["commit"] = commit
        return {1: 1}

    async def fake_get_document_hashes(db, document_ids):
        assert document_ids == [1]
        return {1: "hash-1"}

    class DummyExecuteResult:
        rowcount = 1

    class DummyDB:
        def __init__(self) -> None:
            self.commits = 0
            self.executed = []

        async def execute(self, stmt):
            self.executed.append(stmt)
            return DummyExecuteResult()

        async def commit(self):
            self.commits += 1

    monkeypatch.setattr(
        "app.application.indexing_service.index_prepared_documents_batch",
        fake_index_prepared_documents_batch,
    )
    monkeypatch.setattr(indexing_service, "_get_document_hashes", fake_get_document_hashes)

    db = DummyDB()
    counts = asyncio.run(indexing_service._run_document_batch_index(db, batch=batch))

    assert counts == {1: 1}
    assert captured["commit"] is False
    prepared_docs = captured["prepared_docs"]
    assert prepared_docs[0][0] == 1
    assert prepared_docs[0][1][0].display_text == "prepared body"
    assert db.commits == 1
