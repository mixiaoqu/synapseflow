"""原型需求分块：纯逻辑单测（无 LLM）"""
import asyncio

from app.agents.nodes.prototype.chunking import (
    build_requirements_chunks,
    PROTOTYPE_DOC_SPLIT_THRESHOLD,
    extract_section_title,
)


def test_extract_section_title():
    assert extract_section_title("## 标题A\n正文") == "标题A"
    assert extract_section_title("#### 小标题\nx") == "小标题"
    assert extract_section_title("无标题") == ""


def test_short_doc_single_chunk():
    doc = "hello " * 100
    assert len(doc) < PROTOTYPE_DOC_SPLIT_THRESHOLD
    chunks = build_requirements_chunks(doc)
    assert len(chunks) == 1
    assert chunks[0]["id"] == "c0"
    assert chunks[0]["order"] == 0
    assert chunks[0]["text"] == doc


def test_long_doc_multiple_chunks():
    # 超过阈值且无 # 标题时按段落合并再切
    body = ("段落说明。" * 400) + "\n\n"
    doc = body * 40
    assert len(doc) > PROTOTYPE_DOC_SPLIT_THRESHOLD
    chunks = build_requirements_chunks(doc, max_section_chars=3000)
    assert len(chunks) >= 2
    for i, c in enumerate(chunks):
        assert c["order"] == i
        assert c["id"] == "c%s" % i
        assert len(c["text"]) <= 3500


def test_heading_split_preserves_sections():
    parts = []
    for i in range(15):
        parts.append("## 章节%s\n\n%s" % (i, ("内容%d。" % i) * 800))
    doc = "\n\n".join(parts)
    chunks = build_requirements_chunks(
        doc,
        split_threshold=len(doc) // 2,
        max_section_chars=4000,
    )
    assert len(chunks) >= 2


def test_prepare_node_writes_chunks():
    from app.agents.states.prototype import prototype_state
    from app.agents.nodes.prototype.prepare_chunks import prepare_requirement_chunks_node
    from app.utils.document_parse import normalize_requirements_plaintext

    async def _run():
        state = prototype_state(
            normalize_requirements_plaintext("# A\n\n" + ("x" * 100)),
        )
        return await prepare_requirement_chunks_node(state)

    out = asyncio.run(_run())
    assert "requirements_chunks" in out
    assert len(out["requirements_chunks"]) >= 1
