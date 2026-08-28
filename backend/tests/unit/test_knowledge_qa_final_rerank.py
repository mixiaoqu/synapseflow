from app.agents.knowledge_qa.nodes.retrieve import _dedupe_docs, _evidence_ref_id


def test_parent_window_identity_is_used_after_child_rerank_expansion():
    docs = [
        {"content": "父窗口内容", "metadata": {"document_chunk_id": 11, "parent_chunk_id": 7}},
        {"content": "同一父窗口内容", "metadata": {"document_chunk_id": 12, "parent_chunk_id": 7}},
    ]

    assert len(_dedupe_docs(docs)) == 1
    assert _evidence_ref_id(docs[0]) == "parent:7"


def test_distinct_parent_windows_remain_distinct_evidence():
    docs = [
        {"content": "窗口一", "metadata": {"parent_chunk_id": 7}},
        {"content": "窗口二", "metadata": {"parent_chunk_id": 8}},
    ]

    assert len(_dedupe_docs(docs)) == 2
