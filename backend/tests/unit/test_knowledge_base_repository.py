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

    async def fake_get_by_id(knowledge_base_id: int):
        assert knowledge_base_id == 12
        return knowledge_base

    monkeypatch.setattr(repo, "get_by_id", fake_get_by_id)

    ok = await repo.delete(12)

    assert ok is True
    assert len(db.executed) == 1
    statement = db.executed[0]
    assert statement.__class__.__name__ == "Delete"
    assert "DELETE FROM documents" in str(statement)
    assert "documents.knowledge_base_id = :knowledge_base_id_1" in str(statement)
    assert "documents.user_id = :user_id_1" in str(statement)
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
