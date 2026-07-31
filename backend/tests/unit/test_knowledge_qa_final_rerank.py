import asyncio

import app.agents.knowledge_qa.nodes.retrieve as retrieve_module


def test_final_rerank_limits_candidate_count_and_text_size(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_rerank(query, chunks, top_k):
        captured["chunks"] = chunks
        return [
            {
                "_index": index,
                "rerank_score": 1.0 - index / 100,
            }
            for index, _chunk in enumerate(chunks[:top_k])
        ]

    monkeypatch.setattr(retrieve_module, "rerank", fake_rerank)
    docs = [
        {
            "content": "内容" * 2500,
            "metadata": {
                "source": "text",
                "document_title": f"文档 {index}",
                "section_path": "章节",
                "document_chunk_id": index,
            },
        }
        for index in range(40)
    ]

    result, trace = asyncio.run(retrieve_module.rerank_retrieved_docs("如何删除记录", docs, top_k=8))

    rerank_inputs = captured["chunks"]
    assert len(rerank_inputs) <= 24
    assert all(len(item["search_text"]) <= 1200 for item in rerank_inputs)
    assert trace["candidate_count"] == 40
    assert trace["input_count"] == len(rerank_inputs)
    assert trace["truncated"] is True
    assert len(result) == 8


def test_final_rerank_keeps_graph_candidates_when_text_candidates_overflow(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_rerank(query, chunks, top_k):
        captured["chunks"] = chunks
        return [
            {
                "_index": index,
                "rerank_score": 1.0 - index / 100,
            }
            for index, _chunk in enumerate(chunks[:top_k])
        ]

    monkeypatch.setattr(retrieve_module, "rerank", fake_rerank)
    text_docs = [
        {
            "content": f"text candidate {index}",
            "metadata": {
                "source": "text",
                "document_title": f"text {index}",
                "document_chunk_id": index,
            },
        }
        for index in range(40)
    ]
    graph_docs = [
        {
            "content": f"graph candidate {index}",
            "metadata": {
                "source": "graph",
                "document_title": f"graph {index}",
                "document_chunk_id": 100 + index,
                "graph_evidence": "graph relation evidence",
            },
        }
        for index in range(3)
    ]

    _result, trace = asyncio.run(
        retrieve_module.rerank_retrieved_docs("relationship question", [*text_docs, *graph_docs], top_k=8)
    )

    rerank_inputs = captured["chunks"]
    rerank_chunk_ids = [item["document_chunk_id"] for item in rerank_inputs]
    assert len(rerank_inputs) <= 24
    assert any(chunk_id >= 100 for chunk_id in rerank_chunk_ids)
    assert trace["graph_input_count"] == 3
    assert trace["truncated"] is True


def test_final_rerank_prioritizes_child_hit_and_centers_parent_context(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_rerank(query, chunks, top_k):
        captured["chunks"] = chunks
        return [{"_index": 0, "rerank_score": 1.0}]

    monkeypatch.setattr(retrieve_module, "rerank", fake_rerank)
    hit_text = "员工内购模式在会员类型页面的 Tab4 中配置权益"
    parent_content = f"{'前置说明' * 500}{hit_text}{'后续说明' * 500}"
    docs = [
        {
            "content": parent_content,
            "metadata": {
                "source": "text",
                "document_title": "权益中心操作指南",
                "section_path": "跨模块关联",
                "document_chunk_id": 1,
                "evidence_text": hit_text,
            },
        }
    ]

    _result, trace = asyncio.run(
        retrieve_module.rerank_retrieved_docs("员工内购会员模式的权益配置", docs, top_k=1)
    )

    rerank_text = captured["chunks"][0]["search_text"]
    assert f"[命中片段] {hit_text}" in rerank_text
    assert "[父级上下文]" in rerank_text
    assert hit_text in rerank_text
    assert len(rerank_text) <= 1200
    assert trace["hit_text_input_count"] == 1
