from types import SimpleNamespace

import pytest

from app.repositories.knowledge_base_repository import KnowledgeBaseRepository


class _FakeSession:
    def __init__(self) -> None:
        self.executed = []
        self.deleted = []
        self.commits = 0

    async def execute(self, statement):
        self.executed.append(statement)
        return None

    async def delete(self, obj) -> None:
        self.deleted.append(obj)

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_delete_knowledge_base_removes_documents_before_deleting_kb(monkeypatch):
    db = _FakeSession()
    repo = KnowledgeBaseRepository(db, user_id=7)
    knowledge_base = SimpleNamespace(id=12)
    graph_events = []

    async def fake_get_by_id(knowledge_base_id: int):
        assert knowledge_base_id == 12
        return knowledge_base

    class _Scalars:
        def all(self):
            return [101, 102]

    class _ExecuteResult:
        def scalars(self):
            return _Scalars()

    async def fake_execute(statement):
        db.executed.append(statement)
        text = str(statement)
        if "SELECT documents.id" in text:
            return _ExecuteResult()
        return None

    class FakeStore:
        async def delete_document_graph(self, *, document_id):
            graph_events.append(("delete", document_id))

        async def prune_orphan_entities(self):
            graph_events.append(("prune",))

    monkeypatch.setattr(repo, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(db, "execute", fake_execute)
    monkeypatch.setattr(
        "app.repositories.knowledge_base_repository.IndexJobRepository.cancel_active_jobs_for_knowledge_base",
        lambda *args, **kwargs: __import__("asyncio").sleep(0, result=0),
    )
    monkeypatch.setattr(
        "app.repositories.knowledge_base_repository.get_graph_store",
        lambda: FakeStore(),
    )

    ok = await repo.delete(12)

    assert ok is True
    assert graph_events == [("delete", 101), ("delete", 102), ("prune",)]
    assert len(db.executed) == 3
    assert "SELECT documents.id" in str(db.executed[0])
    assert "DELETE FROM documents" in str(db.executed[1])
    assert "documents.knowledge_base_id = :knowledge_base_id_1" in str(db.executed[1])
    assert db.deleted == [knowledge_base]
    assert db.commits == 1


@pytest.mark.asyncio
async def test_delete_knowledge_base_returns_false_when_missing(monkeypatch):
    db = _FakeSession()
    repo = KnowledgeBaseRepository(db, user_id=7)

    async def fake_get_by_id(_: int):
        return None

    monkeypatch.setattr(repo, "get_by_id", fake_get_by_id)

    ok = await repo.delete(99)

    assert ok is False
    assert db.executed == []
    assert db.deleted == []
    assert db.commits == 0
