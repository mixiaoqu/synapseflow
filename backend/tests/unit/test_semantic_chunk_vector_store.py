import asyncio

from app.services.semantic_chunk import VectorIndexChunk, split_for_vector_index
from app.services.vector_store import add_document_chunks


class _DummyDB:
    def __init__(self) -> None:
        self.rows = []
        self.commits = 0

    def add_all(self, rows) -> None:
        self.rows.extend(rows)

    async def commit(self) -> None:
        self.commits += 1


def test_split_for_vector_index_returns_structured_chunk_payloads():
    doc = (
        "# Parent\n\n"
        "Parent intro.\n\n"
        "## Child\n\n"
        "Child body sentence one.\n"
        "Child body sentence two."
    )

    chunks = split_for_vector_index(
        doc,
        max_chars=400,
        overlap=40,
        document_title="System Design Notes",
    )

    assert len(chunks) == 2
    child = next(chunk for chunk in chunks if chunk.metadata["section_title"] == "Child")
    assert child.display_text == "Child body sentence one.\nChild body sentence two."
    assert child.embedding_text == (
        "[模块路径] Parent > Child\n\n"
        "Child body sentence one.\nChild body sentence two."
    )
    assert child.search_text == (
        "System Design Notes\n"
        "Parent > Child\n"
        "Child\n\n"
        "Child body sentence one.\nChild body sentence two."
    )
    assert child.metadata["section_path"] == "Parent > Child"
    assert child.metadata["heading_level"] == 2
    assert child.metadata["parent_heading"] == "Parent"

    start = child.metadata["start_offset"]
    end = child.metadata["end_offset"]
    assert doc[start:end] == child.display_text


def test_add_document_chunks_stores_display_search_and_metadata():
    chunk = VectorIndexChunk(
        display_text="Rendered body",
        embedding_text="[模块路径] Parent > Child\n\nRendered body",
        search_text="System Design Notes\nParent > Child\nChild\n\nRendered body",
        metadata={
            "section_path": "Parent > Child",
            "section_title": "Child",
            "heading_level": 2,
            "parent_heading": "Parent",
            "start_offset": 18,
            "end_offset": 31,
        },
    )
    db = _DummyDB()

    count = asyncio.run(add_document_chunks(db, 7, [chunk], [[0.1, 0.2]], commit=False))

    assert count == 1
    assert len(db.rows) == 1
    row = db.rows[0]
    assert row.document_id == 7
    assert row.chunk_text == "Rendered body"
    assert row.search_text == "System Design Notes\nParent > Child\nChild\n\nRendered body"
    assert row.metadata_["chunk_index"] == 0
    assert row.metadata_["section_path"] == "Parent > Child"
    assert row.metadata_["section_title"] == "Child"
