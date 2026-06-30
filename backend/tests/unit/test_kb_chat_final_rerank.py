import asyncio

import app.agents.nodes.kb_chat.retrieve as retrieve_module


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
    assert len(rerank_inputs) <= 16
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
    assert len(rerank_inputs) <= 16
    assert any(chunk_id >= 100 for chunk_id in rerank_chunk_ids)
    assert trace["graph_input_count"] == 3
    assert trace["truncated"] is True
