import pytest

from app.repositories.document_category_repository import DocumentCategoryRepository


class _FakeSession:
    def __init__(self) -> None:
        self.executed = []

    async def execute(self, statement):
        self.executed.append(statement)

        class _Result:
            def all(self):
                return []

        return _Result()


@pytest.mark.asyncio
async def test_list_for_knowledge_base_joins_current_documents_only():
    db = _FakeSession()
    repo = DocumentCategoryRepository(db, user_id=7)

    await repo.list_for_knowledge_base(knowledge_base_id=12)

    assert len(db.executed) == 1
    statement = str(db.executed[0])
    assert "document_categories.knowledge_base_id = :knowledge_base_id_1" in statement
    assert "documents.is_current IS true" in statement


@pytest.mark.asyncio
async def test_list_for_knowledge_base_has_no_branch_filter():
    db = _FakeSession()
    repo = DocumentCategoryRepository(db, user_id=7)

    await repo.list_for_knowledge_base(knowledge_base_id=12)

    assert len(db.executed) == 1
    statement = str(db.executed[0])
    assert "document_categories.knowledge_base_id = :knowledge_base_id_1" in statement
    assert "documents.knowledge_base_branch_id = :knowledge_base_branch_id_1" not in statement
