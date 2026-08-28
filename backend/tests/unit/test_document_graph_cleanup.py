import asyncio
from types import SimpleNamespace

from app.application.document_service import DocumentService


def test_delete_graph_for_documents_deletes_each_document_once(monkeypatch):
    events = []

    class FakeStore:
        async def delete_document_graph(self, *, document_id, team_id, knowledge_base_id):
            events.append(("delete", document_id, team_id, knowledge_base_id))

    monkeypatch.setattr(
        "app.application.document_service.get_graph_store",
        lambda: FakeStore(),
    )
    async def fake_resolve_document_team_id(*, db, user_id, doc):
        return 21 if int(doc.id) == 11 else 22

    monkeypatch.setattr(
        DocumentService,
        "_resolve_document_team_id",
        fake_resolve_document_team_id,
    )

    docs = [
        SimpleNamespace(id=11, knowledge_base_id=101),
        SimpleNamespace(id=12, knowledge_base_id=102),
        SimpleNamespace(id=11, knowledge_base_id=101),
    ]

    asyncio.run(DocumentService._delete_graph_for_documents(db=object(), user_id=7, docs=docs))

    assert events == [("delete", 11, 21, 101), ("delete", 12, 22, 102)]
