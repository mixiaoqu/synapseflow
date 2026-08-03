from app.application.evaluation_service import EvaluationService


def test_retrieval_metrics_require_selected_chunk_match():
    docs = [
        {
            "content": "账号创建后，系统会立即发送通知。",
            "metadata": {
                "document_id": 10,
                "child_chunk_id": 999,
            },
        }
    ]

    metrics = EvaluationService._calculate_retrieval_metrics(
        expected_doc_ids=[10],
        expected_chunk_ids=[123],
        expected_snippets=["系统会立即 发送通知"],
        retrieved_docs=docs,
        retrieved_doc_ids=[10],
        retrieved_chunk_ids=[999],
    )

    assert metrics["evidence_basis"] == "chunk"
    assert metrics["evidence_matched"] is False
    assert metrics["chunk_matched"] is False
    assert metrics["snippet_recall"] == 1.0
    assert metrics["reciprocal_rank"] == 1.0


def test_retrieval_metrics_ignore_document_match_without_selected_chunks():
    chunk_metrics = EvaluationService._calculate_retrieval_metrics(
        expected_doc_ids=[10],
        expected_chunk_ids=[123],
        expected_snippets=[],
        retrieved_docs=[
            {
                "content": "相关内容",
                "metadata": {"document_id": 10, "merged_child_chunk_ids": [122, 123]},
            }
        ],
        retrieved_doc_ids=[10],
        retrieved_chunk_ids=[122, 123],
    )
    document_metrics = EvaluationService._calculate_retrieval_metrics(
        expected_doc_ids=[10],
        expected_chunk_ids=[],
        expected_snippets=[],
        retrieved_docs=[{"content": "相关内容", "metadata": {"document_id": 10}}],
        retrieved_doc_ids=[10],
        retrieved_chunk_ids=[],
    )

    assert chunk_metrics["evidence_basis"] == "chunk"
    assert chunk_metrics["evidence_matched"] is True
    assert document_metrics["evidence_basis"] == "unconstrained"
    assert document_metrics["evidence_matched"] is True
