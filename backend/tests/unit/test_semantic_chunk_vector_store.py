import asyncio

from app.services.semantic_chunk import build_chunk_plan, build_vector_index_chunks
from app.services.vector_store import add_document_chunks
from app.utils.document_parse import ParsedBlock, ParsedDocument


class _DummyDB:
    def __init__(self) -> None:
        self.rows = []
        self.commits = 0

    def add_all(self, rows) -> None:
        self.rows.extend(rows)

    async def commit(self) -> None:
        self.commits += 1


def test_build_chunk_plan_creates_parent_child_hierarchy():
    parsed = ParsedDocument(
        title="System Design Notes",
        blocks=[
            ParsedBlock(type="heading", text="Parent", level=1),
            ParsedBlock(type="paragraph", text="A" * 1400),
            ParsedBlock(type="heading", text="Child", level=2),
            ParsedBlock(type="paragraph", text="B" * 700),
            ParsedBlock(type="list", text="- item 1\n- item 2"),
        ],
    )

    plan = build_chunk_plan(parsed, document_title=parsed.title)

    assert plan.full_text.startswith("# Parent")
    assert len(plan.parent_chunks) >= 1
    assert len(plan.child_chunks) >= 2
    assert all(chunk.parent_local_id is not None for chunk in plan.child_chunks)
    assert plan.child_chunks[0].next_local_id == plan.child_chunks[1].local_id
    assert plan.child_chunks[1].prev_local_id == plan.child_chunks[0].local_id
    assert any(chunk.section_path == "Parent > Child" for chunk in plan.child_chunks)


def test_add_document_chunks_stores_document_chunk_relationships():
    parsed = ParsedDocument(
        title="System Design Notes",
        blocks=[
            ParsedBlock(type="heading", text="Parent", level=1),
            ParsedBlock(type="paragraph", text="Rendered body " * 40),
        ],
    )
    plan = build_chunk_plan(parsed, document_title=parsed.title)
    vector_chunks = build_vector_index_chunks(plan, document_id=7)
    document_chunk_ids = [101 + index for index, _ in enumerate(vector_chunks)]
    db = _DummyDB()

    count = asyncio.run(
        add_document_chunks(
            db,
            7,
            vector_chunks,
            [[0.1, 0.2] for _ in vector_chunks],
            document_chunk_ids=document_chunk_ids,
            commit=False,
        )
    )

    assert count == len(vector_chunks)
    assert len(db.rows) == len(vector_chunks)
    row = db.rows[0]
    assert row.document_id == 7
    assert row.document_chunk_id == document_chunk_ids[0]
    assert row.chunk_index == vector_chunks[0].metadata["chunk_index"]
    assert row.metadata_["document_chunk_id"] == document_chunk_ids[0]
