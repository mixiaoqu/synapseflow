import asyncio
from types import SimpleNamespace

from app.application.document_service import DocumentService


def test_delete_graph_for_documents_deletes_each_document_once(monkeypatch):
    events = []

    class FakeStore:
        async def delete_document_graph(self, *, document_id):
            events.append(("delete", document_id))

        async def prune_orphan_entities(self):
            events.append(("prune",))

    monkeypatch.setattr(
        "app.application.document_service.get_graph_store",
        lambda: FakeStore(),
    )

    docs = [
        SimpleNamespace(id=11),
        SimpleNamespace(id=12),
        SimpleNamespace(id=11),
    ]

    asyncio.run(DocumentService._delete_graph_for_documents(docs))

    assert events == [("delete", 11), ("delete", 12), ("prune",)]
